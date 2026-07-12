"""P24 Task completion-policy proposal, decision, and replay service."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.domain._base import utc_now
from app.domain.project_director_agent_team_config import AgentTeamConfigStatus
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_plan_version import (
    PlanVersionStatus,
    ProjectDirectorPlanVersion,
)
from app.domain.project_director_repository_binding_config import (
    RepositoryBindingConfigStatus,
)
from app.domain.project_director_task_completion_policy import (
    ConfirmedTaskCompletionRequirement,
    ProjectDirectorTaskCompletionPolicyDecision,
    ProjectDirectorTaskCompletionPolicyProposal,
    ProjectDirectorTaskCompletionPolicyResult,
    ProjectDirectorTaskCompletionPolicySnapshot,
    TASK_COMPLETION_POLICY_DECISION_SCHEMA_VERSION,
    TASK_COMPLETION_POLICY_PROPOSAL_SCHEMA_VERSION,
    TASK_COMPLETION_POLICY_SNAPSHOT_SCHEMA_VERSION,
    TaskCompletionPolicyBlockedReason,
)
from app.domain.project_director_task_creation import (
    ProjectDirectorTaskCreationRecord,
)
from app.domain.project_director_verification_config import VerificationConfigStatus
from app.domain.task import Task
from app.repositories.project_director_agent_team_config_repository import (
    ProjectDirectorAgentTeamConfigRepository,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.repositories.project_director_repository_binding_config_repository import (
    ProjectDirectorRepositoryBindingConfigRepository,
)
from app.repositories.project_director_task_creation_repository import (
    ProjectDirectorTaskCreationRecordRepository,
)
from app.repositories.project_director_verification_config_repository import (
    ProjectDirectorVerificationConfigRepository,
)
from app.repositories.task_repository import TaskRepository


P24_TASK_COMPLETION_POLICY_PROPOSAL_ACTION_TYPE = (
    "p24_task_completion_policy_proposal_record"
)
P24_TASK_COMPLETION_POLICY_DECISION_ACTION_TYPE = (
    "p24_task_completion_policy_decision_record"
)
P24_TASK_COMPLETION_POLICY_SNAPSHOT_ACTION_TYPE = (
    "p24_task_completion_policy_snapshot_record"
)

P24_TASK_COMPLETION_POLICY_PROPOSAL_SOURCE_DETAIL = (
    "p24_task_completion_policy_proposed"
)
P24_TASK_COMPLETION_POLICY_DECISION_SOURCE_DETAIL = (
    "p24_task_completion_policy_decided"
)
P24_TASK_COMPLETION_POLICY_SNAPSHOT_SOURCE_DETAIL = (
    "p24_task_completion_policy_confirmed"
)

_PROPOSAL_INTENT = "task_completion_policy_proposal"
_DECISION_INTENT = "task_completion_policy_decision"
_SNAPSHOT_INTENT = "task_completion_policy_snapshot"
_PAGE_SIZE = 200
_POLICY_SOURCE = "human_owner_decision"


@dataclass(frozen=True)
class _Lineage:
    plan: ProjectDirectorPlanVersion
    creation_record: ProjectDirectorTaskCreationRecord
    task: Task
    task_index: int


@dataclass(frozen=True)
class _SourceBundle:
    bundle_fingerprint: str
    plan_fingerprint: str
    task_fingerprint: str
    config_fingerprints: dict[str, str]
    proposal_sources: dict[str, list[str]]
    reason_codes: dict[str, list[str]]


@dataclass(frozen=True)
class _PolicyHistory:
    proposals: list[tuple[ProjectDirectorMessage, ProjectDirectorTaskCompletionPolicyProposal]]
    decisions: list[tuple[ProjectDirectorMessage, ProjectDirectorTaskCompletionPolicyDecision]]
    snapshots: list[tuple[ProjectDirectorMessage, ProjectDirectorTaskCompletionPolicySnapshot]]


class _Blocked(Exception):
    def __init__(self, *reasons: TaskCompletionPolicyBlockedReason) -> None:
        self.reasons = tuple(dict.fromkeys(reasons))
        super().__init__(self.reasons[0] if self.reasons else "completion_policy_decision_invalid")


class ProjectDirectorTaskCompletionPolicyService:
    """Persist completion-policy authority without executing completion work."""

    def __init__(
        self,
        *,
        message_repository: ProjectDirectorMessageRepository,
        plan_version_repository: ProjectDirectorPlanVersionRepository,
        task_creation_repository: ProjectDirectorTaskCreationRecordRepository,
        task_repository: TaskRepository,
        verification_config_repository: ProjectDirectorVerificationConfigRepository,
        repository_binding_config_repository: ProjectDirectorRepositoryBindingConfigRepository,
        agent_team_config_repository: ProjectDirectorAgentTeamConfigRepository,
    ) -> None:
        self._message_repository = message_repository
        self._plan_version_repository = plan_version_repository
        self._task_creation_repository = task_creation_repository
        self._task_repository = task_repository
        self._verification_config_repository = verification_config_repository
        self._repository_binding_config_repository = repository_binding_config_repository
        self._agent_team_config_repository = agent_team_config_repository

    def prepare_task_completion_policy_proposal(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        plan_version_id: UUID,
        task_creation_record_id: UUID,
        task_id: UUID,
    ) -> ProjectDirectorTaskCompletionPolicyResult:
        """Append or replay one conservative proposal in an immediate transaction."""

        try:
            with self._message_repository.sqlite_immediate_transaction():
                lineage = self._load_current_lineage(
                    session_id=session_id,
                    project_id=project_id,
                    plan_version_id=plan_version_id,
                    task_creation_record_id=task_creation_record_id,
                    task_id=task_id,
                )
                source_bundle = self._build_source_bundle(lineage)
                replay_key = self._build_proposal_replay_key(
                    session_id=session_id,
                    project_id=project_id,
                    plan_version_id=plan_version_id,
                    task_creation_record_id=task_creation_record_id,
                    task_id=task_id,
                    policy_source_bundle_fingerprint=source_bundle.bundle_fingerprint,
                )

                history = self._load_policy_history(session_id)
                task_proposals = self._validated_task_proposal_chain(
                    history,
                    task_id=task_id,
                )
                requested_lineage = (
                    session_id,
                    project_id,
                    plan_version_id,
                    task_creation_record_id,
                    task_id,
                )
                if (
                    task_proposals
                    and self._proposal_semantic_identity(task_proposals[0][1])[:5]
                    != requested_lineage
                ):
                    raise _Blocked("completion_policy_proposal_replay_conflict")
                semantic_candidates = [
                    proposal
                    for _, proposal in task_proposals
                    if self._proposal_semantic_identity(proposal)
                    == (
                        *requested_lineage,
                        source_bundle.bundle_fingerprint,
                    )
                ]
                if len(semantic_candidates) > 1:
                    raise _Blocked("completion_policy_proposal_replay_conflict")
                if semantic_candidates:
                    replayed = semantic_candidates[0]
                    if replayed.proposal_replay_key != replay_key:
                        raise _Blocked("completion_policy_proposal_replay_conflict")
                    return ProjectDirectorTaskCompletionPolicyResult(
                        status="proposal_replayed",
                        proposal=replayed,
                    )

                supersedes_proposal_id = (
                    task_proposals[-1][1].proposal_id
                    if task_proposals
                    else None
                )
                proposal_id = uuid4()
                created_at = utc_now()
                proposal_payload = {
                    "schema_version": TASK_COMPLETION_POLICY_PROPOSAL_SCHEMA_VERSION,
                    "proposal_id": proposal_id,
                    "proposal_replay_key": replay_key,
                    "proposal_status": "proposed",
                    "created_at": created_at,
                    "session_id": session_id,
                    "project_id": project_id,
                    "plan_version_id": plan_version_id,
                    "plan_version_no": lineage.plan.version_no,
                    "task_creation_record_id": task_creation_record_id,
                    "task_id": task_id,
                    "policy_source_bundle_fingerprint": source_bundle.bundle_fingerprint,
                    "source_plan_fingerprint": source_bundle.plan_fingerprint,
                    "source_task_fingerprint": source_bundle.task_fingerprint,
                    "source_config_fingerprints": source_bundle.config_fingerprints,
                    "review_requirement_proposal": "unresolved",
                    "verification_requirement_proposal": "unresolved",
                    "delivery_requirement_proposal": "unresolved",
                    "approval_requirement_proposal": "unresolved",
                    "review_proposal_sources": source_bundle.proposal_sources["review"],
                    "verification_proposal_sources": source_bundle.proposal_sources[
                        "verification"
                    ],
                    "delivery_proposal_sources": source_bundle.proposal_sources["delivery"],
                    "approval_proposal_sources": source_bundle.proposal_sources["approval"],
                    "review_reason_codes": source_bundle.reason_codes["review"],
                    "verification_reason_codes": source_bundle.reason_codes["verification"],
                    "delivery_reason_codes": source_bundle.reason_codes["delivery"],
                    "approval_reason_codes": source_bundle.reason_codes["approval"],
                    "supersedes_proposal_id": supersedes_proposal_id,
                    "product_runtime_git_write_allowed": False,
                    "forbidden_actions": self._forbidden_actions(),
                }
                proposal = ProjectDirectorTaskCompletionPolicyProposal(
                    **proposal_payload,
                    proposal_fingerprint=self._fingerprint(proposal_payload),
                )
                self._append_policy_message(
                    record=proposal,
                    record_id=proposal.proposal_id,
                    action_type=P24_TASK_COMPLETION_POLICY_PROPOSAL_ACTION_TYPE,
                    source_detail=P24_TASK_COMPLETION_POLICY_PROPOSAL_SOURCE_DETAIL,
                    intent=_PROPOSAL_INTENT,
                    requires_confirmation=True,
                )
                return ProjectDirectorTaskCompletionPolicyResult(
                    status="proposal_prepared",
                    proposal=proposal,
                )
        except _Blocked as exc:
            return ProjectDirectorTaskCompletionPolicyResult.blocked(*exc.reasons)

    def decide_task_completion_policy(
        self,
        *,
        proposal_id: UUID,
        proposal_fingerprint: str,
        review_requirement: ConfirmedTaskCompletionRequirement,
        verification_requirement: ConfirmedTaskCompletionRequirement,
        delivery_requirement: ConfirmedTaskCompletionRequirement,
        approval_requirement: ConfirmedTaskCompletionRequirement,
        review_reason_codes: list[str],
        verification_reason_codes: list[str],
        delivery_reason_codes: list[str],
        approval_reason_codes: list[str],
        review_acceptable_evidence_kinds: list[str],
        verification_acceptable_evidence_kinds: list[str],
        delivery_acceptable_evidence_kinds: list[str],
        approval_acceptable_terminal_results: list[str],
        confirmed_source_evidence_ids: list[UUID],
        decided_by: str,
        client_request_id: str,
    ) -> ProjectDirectorTaskCompletionPolicyResult:
        """Atomically append an explicit owner decision and confirmed snapshot."""

        try:
            self._validate_owner_input(
                requirements=(
                    review_requirement,
                    verification_requirement,
                    delivery_requirement,
                    approval_requirement,
                ),
                reasons=(
                    review_reason_codes,
                    verification_reason_codes,
                    delivery_reason_codes,
                    approval_reason_codes,
                ),
                acceptable_results=(
                    review_acceptable_evidence_kinds,
                    verification_acceptable_evidence_kinds,
                    delivery_acceptable_evidence_kinds,
                    approval_acceptable_terminal_results,
                ),
                decided_by=decided_by,
                client_request_id=client_request_id,
            )
            with self._message_repository.sqlite_immediate_transaction():
                proposal_message = self._message_repository.get_by_id(proposal_id)
                proposal = self._parse_proposal_message(proposal_message)
                if proposal.proposal_fingerprint != proposal_fingerprint:
                    raise _Blocked("completion_policy_proposal_fingerprint_mismatch")
                lineage = self._load_current_lineage(
                    session_id=proposal.session_id,
                    project_id=proposal.project_id,
                    plan_version_id=proposal.plan_version_id,
                    task_creation_record_id=proposal.task_creation_record_id,
                    task_id=proposal.task_id,
                )
                history = self._load_policy_history(proposal.session_id)
                self._require_proposal_unique(history, proposal)
                self._validated_task_proposal_chain(
                    history,
                    task_id=proposal.task_id,
                )
                request = self._decision_request_payload(
                    proposal=proposal,
                    review_requirement=review_requirement,
                    verification_requirement=verification_requirement,
                    delivery_requirement=delivery_requirement,
                    approval_requirement=approval_requirement,
                    review_reason_codes=review_reason_codes,
                    verification_reason_codes=verification_reason_codes,
                    delivery_reason_codes=delivery_reason_codes,
                    approval_reason_codes=approval_reason_codes,
                    review_acceptable_evidence_kinds=review_acceptable_evidence_kinds,
                    verification_acceptable_evidence_kinds=verification_acceptable_evidence_kinds,
                    delivery_acceptable_evidence_kinds=delivery_acceptable_evidence_kinds,
                    approval_acceptable_terminal_results=approval_acceptable_terminal_results,
                    confirmed_source_evidence_ids=confirmed_source_evidence_ids,
                    decided_by=decided_by.strip(),
                    client_request_id=client_request_id.strip(),
                )
                self._require_difference_reasons(proposal, request)

                replay_decisions = [
                    decision
                    for _, decision in history.decisions
                    if decision.proposal_id == proposal_id
                    and decision.client_request_id == client_request_id.strip()
                ]
                if len(replay_decisions) > 1:
                    raise _Blocked("completion_policy_decision_conflict")
                if replay_decisions:
                    decision = replay_decisions[0]
                    if not self._decision_matches_request(decision, request):
                        raise _Blocked("completion_policy_decision_conflict")
                    snapshot = self._snapshot_for_decision(history, decision.decision_id)
                    self._require_snapshot_lineage(snapshot, decision, proposal)
                    return ProjectDirectorTaskCompletionPolicyResult(
                        status="decision_replayed",
                        proposal=proposal,
                        decision=decision,
                        snapshot=snapshot,
                    )

                if any(
                    decision.proposal_id == proposal_id
                    for _, decision in history.decisions
                ):
                    raise _Blocked("completion_policy_decision_conflict")

                current_bundle = self._build_source_bundle(lineage)
                if (
                    current_bundle.bundle_fingerprint
                    != proposal.policy_source_bundle_fingerprint
                ):
                    raise _Blocked("completion_policy_task_lineage_invalid")

                task_snapshots = self._validated_task_snapshot_chain(
                    history,
                    task_id=proposal.task_id,
                )
                previous_snapshot = task_snapshots[-1] if task_snapshots else None
                decision_id = uuid4()
                decision_created_at = utc_now()
                decision_payload = {
                    "schema_version": TASK_COMPLETION_POLICY_DECISION_SCHEMA_VERSION,
                    "decision_id": decision_id,
                    "created_at": decision_created_at,
                    **request,
                    "decision_actor_type": "human_owner",
                    "product_runtime_git_write_allowed": False,
                    "forbidden_actions": self._forbidden_actions(),
                }
                decision = ProjectDirectorTaskCompletionPolicyDecision(
                    **decision_payload,
                    decision_fingerprint=self._fingerprint(decision_payload),
                )

                snapshot_id = uuid4()
                snapshot_created_at = utc_now()
                axis_evidence_ids = list(
                    dict.fromkeys([*confirmed_source_evidence_ids, decision_id])
                )
                snapshot_payload = {
                    "schema_version": TASK_COMPLETION_POLICY_SNAPSHOT_SCHEMA_VERSION,
                    "completion_policy_id": snapshot_id,
                    "completion_policy_version": (
                        previous_snapshot.completion_policy_version + 1
                        if previous_snapshot
                        else 1
                    ),
                    "completion_policy_status": "confirmed",
                    "created_at": snapshot_created_at,
                    "session_id": proposal.session_id,
                    "project_id": proposal.project_id,
                    "plan_version_id": proposal.plan_version_id,
                    "plan_version_no": proposal.plan_version_no,
                    "task_creation_record_id": proposal.task_creation_record_id,
                    "task_id": proposal.task_id,
                    "source_proposal_id": proposal.proposal_id,
                    "source_proposal_fingerprint": proposal.proposal_fingerprint,
                    "source_decision_id": decision.decision_id,
                    "source_decision_fingerprint": decision.decision_fingerprint,
                    "supersedes_completion_policy_id": (
                        previous_snapshot.completion_policy_id
                        if previous_snapshot
                        else None
                    ),
                    "review_requirement": decision.review_requirement,
                    "verification_requirement": decision.verification_requirement,
                    "delivery_requirement": decision.delivery_requirement,
                    "approval_requirement": decision.approval_requirement,
                    "review_policy_source": _POLICY_SOURCE,
                    "verification_policy_source": _POLICY_SOURCE,
                    "delivery_policy_source": _POLICY_SOURCE,
                    "approval_policy_source": _POLICY_SOURCE,
                    "review_policy_evidence_ids": axis_evidence_ids,
                    "verification_policy_evidence_ids": axis_evidence_ids,
                    "delivery_policy_evidence_ids": axis_evidence_ids,
                    "approval_policy_evidence_ids": axis_evidence_ids,
                    "required_terminal_task_status": "completed",
                    "required_terminal_run_status": "succeeded",
                    "required_quality_gate_result": True,
                    "required_review_terminal_results": (
                        decision.review_acceptable_evidence_kinds
                    ),
                    "required_verification_evidence_kinds": (
                        decision.verification_acceptable_evidence_kinds
                    ),
                    "required_delivery_evidence_kinds": (
                        decision.delivery_acceptable_evidence_kinds
                    ),
                    "required_approval_terminal_results": (
                        decision.approval_acceptable_terminal_results
                    ),
                    "human_confirmation_required": True,
                    "human_confirmation_evidence_id": decision.decision_id,
                    "product_runtime_git_write_allowed": False,
                    "forbidden_actions": self._forbidden_actions(),
                }
                snapshot = ProjectDirectorTaskCompletionPolicySnapshot(
                    **snapshot_payload,
                    completion_policy_fingerprint=self._fingerprint(snapshot_payload),
                )
                self._require_snapshot_lineage(snapshot, decision, proposal)
                self._append_policy_message(
                    record=decision,
                    record_id=decision.decision_id,
                    action_type=P24_TASK_COMPLETION_POLICY_DECISION_ACTION_TYPE,
                    source_detail=P24_TASK_COMPLETION_POLICY_DECISION_SOURCE_DETAIL,
                    intent=_DECISION_INTENT,
                    requires_confirmation=False,
                )
                self._append_policy_message(
                    record=snapshot,
                    record_id=snapshot.completion_policy_id,
                    action_type=P24_TASK_COMPLETION_POLICY_SNAPSHOT_ACTION_TYPE,
                    source_detail=P24_TASK_COMPLETION_POLICY_SNAPSHOT_SOURCE_DETAIL,
                    intent=_SNAPSHOT_INTENT,
                    requires_confirmation=False,
                )
                return ProjectDirectorTaskCompletionPolicyResult(
                    status="decision_confirmed",
                    proposal=proposal,
                    decision=decision,
                    snapshot=snapshot,
                )
        except (ValidationError, ValueError):
            return ProjectDirectorTaskCompletionPolicyResult.blocked(
                "completion_policy_decision_invalid"
            )
        except _Blocked as exc:
            return ProjectDirectorTaskCompletionPolicyResult.blocked(*exc.reasons)

    def revalidate_persisted_task_completion_policy(
        self,
        *,
        completion_policy_id: UUID,
        task_id: UUID,
    ) -> ProjectDirectorTaskCompletionPolicyResult:
        """Strictly reconstruct immutable policy history without writing or re-inferring."""

        try:
            snapshot_message = self._message_repository.get_by_id(completion_policy_id)
            if snapshot_message is None:
                raise _Blocked("completion_policy_snapshot_missing")
            snapshot = self._parse_snapshot_message(snapshot_message)
            if snapshot.task_id != task_id:
                raise _Blocked("completion_policy_snapshot_lineage_invalid")
            history = self._load_policy_history(snapshot.session_id)
            task_chain = self._validated_task_snapshot_chain(history, task_id=task_id)
            matching_snapshots = [
                item
                for item in task_chain
                if item.completion_policy_id == completion_policy_id
            ]
            if len(matching_snapshots) != 1:
                raise _Blocked("completion_policy_version_conflict")
            decision_matches = [
                decision
                for _, decision in history.decisions
                if decision.decision_id == snapshot.source_decision_id
            ]
            proposal_matches = [
                proposal
                for _, proposal in history.proposals
                if proposal.proposal_id == snapshot.source_proposal_id
            ]
            if len(decision_matches) != 1 or len(proposal_matches) != 1:
                raise _Blocked("completion_policy_snapshot_lineage_invalid")
            decision = decision_matches[0]
            proposal = proposal_matches[0]
            self._require_snapshot_lineage(snapshot, decision, proposal)
            return ProjectDirectorTaskCompletionPolicyResult(
                status="policy_revalidated",
                proposal=proposal,
                decision=decision,
                snapshot=snapshot,
            )
        except _Blocked as exc:
            return ProjectDirectorTaskCompletionPolicyResult.blocked(*exc.reasons)

    def _load_current_lineage(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        plan_version_id: UUID,
        task_creation_record_id: UUID,
        task_id: UUID,
    ) -> _Lineage:
        plan = self._plan_version_repository.get_by_id(plan_version_id)
        if plan is None:
            raise _Blocked("completion_policy_plan_missing")
        if plan.status != PlanVersionStatus.CONFIRMED:
            raise _Blocked("completion_policy_plan_not_confirmed")
        if plan.session_id != session_id or plan.project_id != project_id:
            raise _Blocked("completion_policy_task_lineage_invalid")

        record = self._task_creation_repository.get_by_plan_version_id(plan_version_id)
        if record is None:
            raise _Blocked("completion_policy_task_creation_record_missing")
        if (
            record.id != task_creation_record_id
            or record.plan_version_id != plan_version_id
            or record.session_id != session_id
            or record.project_id != project_id
            or record.version_no != plan.version_no
            or record.task_count != len(record.task_ids)
            or record.task_count != len(plan.proposed_tasks)
        ):
            raise _Blocked("completion_policy_task_lineage_invalid")
        if record.task_ids.count(task_id) != 1:
            raise _Blocked("completion_policy_task_not_in_plan")

        task = self._task_repository.get_by_id(task_id)
        if task is None:
            raise _Blocked("completion_policy_task_not_in_plan")
        expected_source_draft_id = f"pdv:{plan_version_id}:{plan.version_no}"
        if task.project_id != project_id or task.source_draft_id != expected_source_draft_id:
            raise _Blocked("completion_policy_task_lineage_invalid")
        return _Lineage(
            plan=plan,
            creation_record=record,
            task=task,
            task_index=record.task_ids.index(task_id),
        )

    def _build_source_bundle(self, lineage: _Lineage) -> _SourceBundle:
        plan = lineage.plan
        task = lineage.task
        proposed_task = plan.proposed_tasks[lineage.task_index]
        plan_payload = {
            "id": plan.id,
            "session_id": plan.session_id,
            "project_id": plan.project_id,
            "version_no": plan.version_no,
            "status": plan.status,
            "proposed_tasks": plan.proposed_tasks,
            "acceptance_criteria": plan.acceptance_criteria,
            "verification_mechanisms": plan.verification_mechanisms,
            "deliverable_boundaries": plan.deliverable_boundaries,
            "forbidden_actions": plan.forbidden_actions,
        }
        task_payload = {
            "id": task.id,
            "project_id": task.project_id,
            "title": task.title,
            "input_summary": task.input_summary,
            "acceptance_criteria": task.acceptance_criteria,
            "owner_role_code": task.owner_role_code,
            "source_draft_id": task.source_draft_id,
            "plan_task_index": lineage.task_index,
            "proposed_task": proposed_task,
        }
        creation_payload = {
            "id": lineage.creation_record.id,
            "plan_version_id": lineage.creation_record.plan_version_id,
            "session_id": lineage.creation_record.session_id,
            "project_id": lineage.creation_record.project_id,
            "version_no": lineage.creation_record.version_no,
            "task_ids": lineage.creation_record.task_ids,
            "task_count": lineage.creation_record.task_count,
        }
        plan_fingerprint = self._fingerprint(plan_payload)
        task_fingerprint = self._fingerprint(task_payload)
        config_fingerprints: dict[str, str] = {}
        config_sources: dict[str, list[str]] = {
            "review": ["confirmed_plan", "exact_task", "task_creation_record"],
            "verification": ["confirmed_plan", "exact_task", "task_creation_record"],
            "delivery": ["confirmed_plan", "exact_task", "task_creation_record"],
            "approval": ["confirmed_plan", "exact_task", "task_creation_record"],
        }

        verification_config = self._verification_config_repository.get_by_plan_version_id(
            plan.id
        )
        self._require_config_lineage(verification_config, plan)
        if (
            verification_config is not None
            and verification_config.status == VerificationConfigStatus.CONFIRMED
        ):
            config_fingerprints["verification"] = self._fingerprint(
                self._safe_config_payload(verification_config)
            )
            config_sources["verification"].append("confirmed_verification_config")

        repository_config = (
            self._repository_binding_config_repository.get_by_plan_version_id(plan.id)
        )
        self._require_config_lineage(repository_config, plan)
        if (
            repository_config is not None
            and repository_config.status == RepositoryBindingConfigStatus.CONFIRMED
        ):
            config_fingerprints["repository_binding"] = self._fingerprint(
                self._safe_config_payload(repository_config)
            )
            for sources in config_sources.values():
                sources.append("confirmed_repository_binding_config")

        team_config = self._agent_team_config_repository.get_by_plan_version_id(plan.id)
        self._require_config_lineage(team_config, plan)
        if (
            team_config is not None
            and team_config.status == AgentTeamConfigStatus.CONFIRMED
        ):
            config_fingerprints["agent_team"] = self._fingerprint(
                self._safe_config_payload(team_config)
            )
            for sources in config_sources.values():
                sources.append("confirmed_agent_team_config")

        bundle_payload = {
            "schema_version": "p24-b-completion-policy-source-bundle.v1",
            "source_plan_fingerprint": plan_fingerprint,
            "source_task_fingerprint": task_fingerprint,
            "task_creation_record_fingerprint": self._fingerprint(creation_payload),
            "source_config_fingerprints": config_fingerprints,
            "plan_acceptance_criteria": plan.acceptance_criteria,
            "plan_deliverable_boundaries": plan.deliverable_boundaries,
            "task_acceptance_criteria": task.acceptance_criteria,
        }
        return _SourceBundle(
            bundle_fingerprint=self._fingerprint(bundle_payload),
            plan_fingerprint=plan_fingerprint,
            task_fingerprint=task_fingerprint,
            config_fingerprints=dict(sorted(config_fingerprints.items())),
            proposal_sources=config_sources,
            reason_codes={
                "review": ["completion_policy_task_review_requirement_unresolved"],
                "verification": [
                    "completion_policy_task_verification_requirement_unresolved"
                ],
                "delivery": ["completion_policy_task_delivery_requirement_unresolved"],
                "approval": ["completion_policy_task_approval_requirement_unresolved"],
            },
        )

    def _load_policy_history(self, session_id: UUID) -> _PolicyHistory:
        proposals: list[tuple[ProjectDirectorMessage, ProjectDirectorTaskCompletionPolicyProposal]] = []
        decisions: list[tuple[ProjectDirectorMessage, ProjectDirectorTaskCompletionPolicyDecision]] = []
        snapshots: list[tuple[ProjectDirectorMessage, ProjectDirectorTaskCompletionPolicySnapshot]] = []
        for message in self._iter_session_messages(session_id):
            if self._is_policy_message(
                message,
                _PROPOSAL_INTENT,
                P24_TASK_COMPLETION_POLICY_PROPOSAL_SOURCE_DETAIL,
                P24_TASK_COMPLETION_POLICY_PROPOSAL_ACTION_TYPE,
            ):
                proposals.append((message, self._parse_proposal_message(message)))
            elif self._is_policy_message(
                message,
                _DECISION_INTENT,
                P24_TASK_COMPLETION_POLICY_DECISION_SOURCE_DETAIL,
                P24_TASK_COMPLETION_POLICY_DECISION_ACTION_TYPE,
            ):
                decisions.append((message, self._parse_decision_message(message)))
            elif self._is_policy_message(
                message,
                _SNAPSHOT_INTENT,
                P24_TASK_COMPLETION_POLICY_SNAPSHOT_SOURCE_DETAIL,
                P24_TASK_COMPLETION_POLICY_SNAPSHOT_ACTION_TYPE,
            ):
                snapshots.append((message, self._parse_snapshot_message(message)))
        return _PolicyHistory(proposals=proposals, decisions=decisions, snapshots=snapshots)

    def _parse_proposal_message(
        self,
        message: ProjectDirectorMessage | None,
    ) -> ProjectDirectorTaskCompletionPolicyProposal:
        if message is None:
            raise _Blocked("completion_policy_proposal_missing")
        action = self._require_action(
            message,
            action_type=P24_TASK_COMPLETION_POLICY_PROPOSAL_ACTION_TYPE,
            schema_version=TASK_COMPLETION_POLICY_PROPOSAL_SCHEMA_VERSION,
            intent=_PROPOSAL_INTENT,
            source_detail=P24_TASK_COMPLETION_POLICY_PROPOSAL_SOURCE_DETAIL,
            requires_confirmation=True,
            schema_reason="completion_policy_proposal_schema_mismatch",
        )
        try:
            proposal = ProjectDirectorTaskCompletionPolicyProposal.model_validate(
                {key: value for key, value in action.items() if key != "type"}
            )
        except ValidationError as exc:
            raise _Blocked("completion_policy_proposal_schema_mismatch") from exc
        if (
            proposal.proposal_id != message.id
            or self._fingerprint(self._without_fingerprint(proposal, "proposal_fingerprint"))
            != proposal.proposal_fingerprint
        ):
            raise _Blocked("completion_policy_proposal_fingerprint_mismatch")
        expected_replay_key = self._build_proposal_replay_key(
            session_id=proposal.session_id,
            project_id=proposal.project_id,
            plan_version_id=proposal.plan_version_id,
            task_creation_record_id=proposal.task_creation_record_id,
            task_id=proposal.task_id,
            policy_source_bundle_fingerprint=(
                proposal.policy_source_bundle_fingerprint
            ),
        )
        if proposal.proposal_replay_key != expected_replay_key:
            raise _Blocked("completion_policy_proposal_replay_conflict")
        self._require_message_lineage(message, proposal)
        return proposal

    def _parse_decision_message(
        self,
        message: ProjectDirectorMessage | None,
    ) -> ProjectDirectorTaskCompletionPolicyDecision:
        if message is None:
            raise _Blocked("completion_policy_decision_invalid")
        action = self._require_action(
            message,
            action_type=P24_TASK_COMPLETION_POLICY_DECISION_ACTION_TYPE,
            schema_version=TASK_COMPLETION_POLICY_DECISION_SCHEMA_VERSION,
            intent=_DECISION_INTENT,
            source_detail=P24_TASK_COMPLETION_POLICY_DECISION_SOURCE_DETAIL,
            requires_confirmation=False,
            schema_reason="completion_policy_decision_invalid",
        )
        if action.get("decision_actor_type") != "human_owner":
            raise _Blocked("completion_policy_decision_actor_invalid")
        try:
            decision = ProjectDirectorTaskCompletionPolicyDecision.model_validate(
                {key: value for key, value in action.items() if key != "type"}
            )
        except ValidationError as exc:
            raise _Blocked("completion_policy_decision_invalid") from exc
        if decision.decision_actor_type != "human_owner":
            raise _Blocked("completion_policy_decision_actor_invalid")
        if (
            decision.decision_id != message.id
            or self._fingerprint(self._without_fingerprint(decision, "decision_fingerprint"))
            != decision.decision_fingerprint
        ):
            raise _Blocked("completion_policy_decision_invalid")
        self._require_message_lineage(message, decision)
        return decision

    def _parse_snapshot_message(
        self,
        message: ProjectDirectorMessage | None,
    ) -> ProjectDirectorTaskCompletionPolicySnapshot:
        if message is None:
            raise _Blocked("completion_policy_snapshot_missing")
        action = self._require_action(
            message,
            action_type=P24_TASK_COMPLETION_POLICY_SNAPSHOT_ACTION_TYPE,
            schema_version=TASK_COMPLETION_POLICY_SNAPSHOT_SCHEMA_VERSION,
            intent=_SNAPSHOT_INTENT,
            source_detail=P24_TASK_COMPLETION_POLICY_SNAPSHOT_SOURCE_DETAIL,
            requires_confirmation=False,
            schema_reason="completion_policy_snapshot_schema_mismatch",
        )
        try:
            snapshot = ProjectDirectorTaskCompletionPolicySnapshot.model_validate(
                {key: value for key, value in action.items() if key != "type"}
            )
        except ValidationError as exc:
            raise _Blocked("completion_policy_snapshot_schema_mismatch") from exc
        if (
            snapshot.completion_policy_id != message.id
            or self._fingerprint(
                self._without_fingerprint(snapshot, "completion_policy_fingerprint")
            )
            != snapshot.completion_policy_fingerprint
        ):
            raise _Blocked("completion_policy_snapshot_fingerprint_mismatch")
        self._require_message_lineage(message, snapshot)
        return snapshot

    def _validated_task_proposal_chain(
        self,
        history: _PolicyHistory,
        *,
        task_id: UUID,
    ) -> list[
        tuple[ProjectDirectorMessage, ProjectDirectorTaskCompletionPolicyProposal]
    ]:
        proposals = sorted(
            [
                item
                for item in history.proposals
                if item[1].task_id == task_id
            ],
            key=lambda item: item[0].sequence_no,
        )
        proposal_ids: set[UUID] = set()
        sequence_numbers: set[int] = set()
        semantic_identities: set[tuple[UUID, UUID, UUID, UUID, UUID, str]] = set()
        expected_lineage = None
        if proposals:
            expected_lineage = (
                proposals[0][1].session_id,
                proposals[0][1].project_id,
                proposals[0][1].plan_version_id,
                proposals[0][1].task_creation_record_id,
                proposals[0][1].task_id,
            )
        for index, (message, proposal) in enumerate(proposals):
            expected_parent = proposals[index - 1][1].proposal_id if index else None
            semantic_identity = self._proposal_semantic_identity(proposal)
            if (
                message.sequence_no in sequence_numbers
                or proposal.proposal_id in proposal_ids
                or proposal.proposal_id == proposal.supersedes_proposal_id
                or proposal.supersedes_proposal_id != expected_parent
                or semantic_identity[:5] != expected_lineage
                or semantic_identity in semantic_identities
            ):
                raise _Blocked("completion_policy_proposal_replay_conflict")
            proposal_ids.add(proposal.proposal_id)
            sequence_numbers.add(message.sequence_no)
            semantic_identities.add(semantic_identity)
        return proposals

    @staticmethod
    def _proposal_semantic_identity(
        proposal: ProjectDirectorTaskCompletionPolicyProposal,
    ) -> tuple[UUID, UUID, UUID, UUID, UUID, str]:
        return (
            proposal.session_id,
            proposal.project_id,
            proposal.plan_version_id,
            proposal.task_creation_record_id,
            proposal.task_id,
            proposal.policy_source_bundle_fingerprint,
        )

    def _build_proposal_replay_key(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        plan_version_id: UUID,
        task_creation_record_id: UUID,
        task_id: UUID,
        policy_source_bundle_fingerprint: str,
    ) -> str:
        return self._fingerprint(
            {
                "schema_version": TASK_COMPLETION_POLICY_PROPOSAL_SCHEMA_VERSION,
                "action": "prepare_task_completion_policy_proposal",
                "session_id": session_id,
                "project_id": project_id,
                "plan_version_id": plan_version_id,
                "task_creation_record_id": task_creation_record_id,
                "task_id": task_id,
                "policy_source_bundle_fingerprint": (
                    policy_source_bundle_fingerprint
                ),
            }
        )

    def _validated_task_snapshot_chain(
        self,
        history: _PolicyHistory,
        *,
        task_id: UUID,
    ) -> list[ProjectDirectorTaskCompletionPolicySnapshot]:
        snapshots = sorted(
            [snapshot for _, snapshot in history.snapshots if snapshot.task_id == task_id],
            key=lambda item: item.completion_policy_version,
        )
        ids: set[UUID] = set()
        for index, snapshot in enumerate(snapshots, start=1):
            expected_parent = snapshots[index - 2].completion_policy_id if index > 1 else None
            if (
                snapshot.completion_policy_version != index
                or snapshot.supersedes_completion_policy_id != expected_parent
                or snapshot.completion_policy_id in ids
            ):
                raise _Blocked("completion_policy_version_conflict")
            ids.add(snapshot.completion_policy_id)
            decisions = [
                decision
                for _, decision in history.decisions
                if decision.decision_id == snapshot.source_decision_id
            ]
            proposals = [
                proposal
                for _, proposal in history.proposals
                if proposal.proposal_id == snapshot.source_proposal_id
            ]
            if len(decisions) != 1 or len(proposals) != 1:
                raise _Blocked("completion_policy_snapshot_lineage_invalid")
            self._require_snapshot_lineage(snapshot, decisions[0], proposals[0])
        return snapshots

    def _require_snapshot_lineage(
        self,
        snapshot: ProjectDirectorTaskCompletionPolicySnapshot,
        decision: ProjectDirectorTaskCompletionPolicyDecision,
        proposal: ProjectDirectorTaskCompletionPolicyProposal,
    ) -> None:
        shared = (
            "session_id",
            "project_id",
            "plan_version_id",
            "task_creation_record_id",
            "task_id",
        )
        expected_axis_evidence_ids = list(
            dict.fromkeys(
                [
                    *decision.confirmed_source_evidence_ids,
                    decision.decision_id,
                ]
            )
        )
        requirements_match = (
            snapshot.review_requirement == decision.review_requirement
            and snapshot.verification_requirement
            == decision.verification_requirement
            and snapshot.delivery_requirement == decision.delivery_requirement
            and snapshot.approval_requirement == decision.approval_requirement
        )
        terminal_evidence_matches = (
            snapshot.required_review_terminal_results
            == decision.review_acceptable_evidence_kinds
            and snapshot.required_verification_evidence_kinds
            == decision.verification_acceptable_evidence_kinds
            and snapshot.required_delivery_evidence_kinds
            == decision.delivery_acceptable_evidence_kinds
            and snapshot.required_approval_terminal_results
            == decision.approval_acceptable_terminal_results
        )
        policy_sources_match = all(
            value == _POLICY_SOURCE
            for value in (
                snapshot.review_policy_source,
                snapshot.verification_policy_source,
                snapshot.delivery_policy_source,
                snapshot.approval_policy_source,
            )
        )
        policy_evidence_matches = all(
            values == expected_axis_evidence_ids
            for values in (
                snapshot.review_policy_evidence_ids,
                snapshot.verification_policy_evidence_ids,
                snapshot.delivery_policy_evidence_ids,
                snapshot.approval_policy_evidence_ids,
            )
        )
        forbidden_actions = self._forbidden_actions()
        if (
            snapshot.source_decision_fingerprint != decision.decision_fingerprint
            or snapshot.source_proposal_fingerprint != proposal.proposal_fingerprint
            or snapshot.source_decision_id != decision.decision_id
            or snapshot.source_proposal_id != proposal.proposal_id
            or decision.proposal_id != proposal.proposal_id
            or decision.proposal_fingerprint != proposal.proposal_fingerprint
            or any(getattr(snapshot, field) != getattr(decision, field) for field in shared)
            or any(getattr(decision, field) != getattr(proposal, field) for field in shared)
            or snapshot.plan_version_no != proposal.plan_version_no
            or not requirements_match
            or not terminal_evidence_matches
            or not policy_sources_match
            or not policy_evidence_matches
            or snapshot.human_confirmation_required is not True
            or snapshot.human_confirmation_evidence_id != decision.decision_id
            or snapshot.required_terminal_task_status != "completed"
            or snapshot.required_terminal_run_status != "succeeded"
            or snapshot.required_quality_gate_result is not True
            or snapshot.product_runtime_git_write_allowed is not False
            or proposal.forbidden_actions != forbidden_actions
            or decision.forbidden_actions != forbidden_actions
            or snapshot.forbidden_actions != forbidden_actions
        ):
            raise _Blocked("completion_policy_snapshot_lineage_invalid")

    def _append_policy_message(
        self,
        *,
        record: Any,
        record_id: UUID,
        action_type: str,
        source_detail: str,
        intent: str,
        requires_confirmation: bool,
    ) -> None:
        if record.forbidden_actions != self._forbidden_actions():
            raise _Blocked("completion_policy_git_boundary_violation")
        action = {"type": action_type, **record.model_dump(mode="json")}
        self._message_repository.create(
            ProjectDirectorMessage(
                id=record_id,
                session_id=record.session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=f"P24 Task completion policy record: {record_id}",
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=record.session_id
                ),
                intent=intent,
                related_plan_version_id=record.plan_version_id,
                related_project_id=record.project_id,
                related_task_id=record.task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=source_detail,
                suggested_actions=[action],
                requires_confirmation=requires_confirmation,
                risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                forbidden_actions_detected=list(record.forbidden_actions),
                created_at=record.created_at,
            )
        )

    def _require_action(
        self,
        message: ProjectDirectorMessage,
        *,
        action_type: str,
        schema_version: str,
        intent: str,
        source_detail: str,
        requires_confirmation: bool,
        schema_reason: TaskCompletionPolicyBlockedReason,
    ) -> dict[str, Any]:
        if (
            message.session_id is None
            or message.role != ProjectDirectorMessageRole.ASSISTANT
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent != intent
            or message.source_detail != source_detail
            or message.requires_confirmation is not requires_confirmation
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
            or len(message.suggested_actions) != 1
            or not isinstance(message.suggested_actions[0], dict)
        ):
            raise _Blocked(schema_reason)
        action = message.suggested_actions[0]
        if action.get("type") != action_type or action.get("schema_version") != schema_version:
            raise _Blocked(schema_reason)
        if action.get("product_runtime_git_write_allowed") is not False:
            raise _Blocked("completion_policy_git_boundary_violation")
        return action

    def _require_message_lineage(
        self,
        message: ProjectDirectorMessage,
        record: Any,
    ) -> None:
        expected_forbidden_actions = self._forbidden_actions()
        if (
            record.forbidden_actions != expected_forbidden_actions
            or not set(record.forbidden_actions).issubset(
                set(message.forbidden_actions_detected)
            )
        ):
            raise _Blocked("completion_policy_git_boundary_violation")
        if (
            message.session_id != record.session_id
            or message.related_plan_version_id != record.plan_version_id
            or message.related_project_id != record.project_id
            or message.related_task_id != record.task_id
            or message.created_at != record.created_at
        ):
            if hasattr(record, "completion_policy_id"):
                raise _Blocked("completion_policy_snapshot_lineage_invalid")
            if hasattr(record, "decision_id"):
                raise _Blocked("completion_policy_decision_invalid")
            raise _Blocked("completion_policy_proposal_schema_mismatch")

    @staticmethod
    def _is_policy_message(
        message: ProjectDirectorMessage,
        intent: str,
        source_detail: str,
        action_type: str,
    ) -> bool:
        action_matches = any(
            isinstance(action, dict) and action.get("type") == action_type
            for action in message.suggested_actions
        )
        return (
            message.intent == intent
            or message.source_detail == source_detail
            or action_matches
        )

    def _iter_session_messages(self, session_id: UUID) -> list[ProjectDirectorMessage]:
        messages: list[ProjectDirectorMessage] = []
        before_message_id: UUID | None = None
        while True:
            page, has_more = self._message_repository.list_by_session_id(
                session_id=session_id,
                limit=_PAGE_SIZE,
                before_message_id=before_message_id,
            )
            messages.extend(page)
            if not has_more or not page:
                return sorted(messages, key=lambda item: item.sequence_no)
            before_message_id = page[0].id

    @staticmethod
    def _validate_owner_input(
        *,
        requirements: tuple[str, str, str, str],
        reasons: tuple[list[str], list[str], list[str], list[str]],
        acceptable_results: tuple[list[str], list[str], list[str], list[str]],
        decided_by: str,
        client_request_id: str,
    ) -> None:
        if not decided_by.strip() or not client_request_id.strip():
            raise _Blocked("completion_policy_decision_actor_invalid")
        if decided_by.strip().casefold() in {
            "system",
            "assistant",
            "ai_project_director",
        }:
            raise _Blocked("completion_policy_decision_actor_invalid")
        for requirement, axis_reasons, results in zip(
            requirements, reasons, acceptable_results, strict=True
        ):
            if requirement not in {"required", "not_required"}:
                raise _Blocked("completion_policy_unresolved")
            if requirement == "not_required" and not ProjectDirectorTaskCompletionPolicyService._clean_strings(axis_reasons):
                raise _Blocked("completion_policy_decision_reason_missing")
            if requirement == "required" and not ProjectDirectorTaskCompletionPolicyService._clean_strings(results):
                raise _Blocked("completion_policy_decision_evidence_kind_missing")

    @staticmethod
    def _require_difference_reasons(
        proposal: ProjectDirectorTaskCompletionPolicyProposal,
        request: dict[str, Any],
    ) -> None:
        for axis in ("review", "verification", "delivery", "approval"):
            if (
                getattr(proposal, f"{axis}_requirement_proposal")
                != request[f"{axis}_requirement"]
                and not request[f"{axis}_reason_codes"]
            ):
                raise _Blocked("completion_policy_decision_reason_missing")

    @staticmethod
    def _decision_request_payload(
        *,
        proposal: ProjectDirectorTaskCompletionPolicyProposal,
        review_requirement: str,
        verification_requirement: str,
        delivery_requirement: str,
        approval_requirement: str,
        review_reason_codes: list[str],
        verification_reason_codes: list[str],
        delivery_reason_codes: list[str],
        approval_reason_codes: list[str],
        review_acceptable_evidence_kinds: list[str],
        verification_acceptable_evidence_kinds: list[str],
        delivery_acceptable_evidence_kinds: list[str],
        approval_acceptable_terminal_results: list[str],
        confirmed_source_evidence_ids: list[UUID],
        decided_by: str,
        client_request_id: str,
    ) -> dict[str, Any]:
        return {
            "proposal_id": proposal.proposal_id,
            "proposal_fingerprint": proposal.proposal_fingerprint,
            "session_id": proposal.session_id,
            "project_id": proposal.project_id,
            "plan_version_id": proposal.plan_version_id,
            "task_creation_record_id": proposal.task_creation_record_id,
            "task_id": proposal.task_id,
            "review_requirement": review_requirement,
            "verification_requirement": verification_requirement,
            "delivery_requirement": delivery_requirement,
            "approval_requirement": approval_requirement,
            "review_reason_codes": ProjectDirectorTaskCompletionPolicyService._clean_strings(review_reason_codes),
            "verification_reason_codes": ProjectDirectorTaskCompletionPolicyService._clean_strings(verification_reason_codes),
            "delivery_reason_codes": ProjectDirectorTaskCompletionPolicyService._clean_strings(delivery_reason_codes),
            "approval_reason_codes": ProjectDirectorTaskCompletionPolicyService._clean_strings(approval_reason_codes),
            "review_acceptable_evidence_kinds": ProjectDirectorTaskCompletionPolicyService._clean_strings(review_acceptable_evidence_kinds),
            "verification_acceptable_evidence_kinds": ProjectDirectorTaskCompletionPolicyService._clean_strings(verification_acceptable_evidence_kinds),
            "delivery_acceptable_evidence_kinds": ProjectDirectorTaskCompletionPolicyService._clean_strings(delivery_acceptable_evidence_kinds),
            "approval_acceptable_terminal_results": ProjectDirectorTaskCompletionPolicyService._clean_strings(approval_acceptable_terminal_results),
            "confirmed_source_evidence_ids": list(dict.fromkeys(confirmed_source_evidence_ids)),
            "decided_by": decided_by,
            "client_request_id": client_request_id,
        }

    @staticmethod
    def _decision_matches_request(
        decision: ProjectDirectorTaskCompletionPolicyDecision,
        request: dict[str, Any],
    ) -> bool:
        return all(getattr(decision, key) == value for key, value in request.items())

    @staticmethod
    def _require_proposal_unique(
        history: _PolicyHistory,
        proposal: ProjectDirectorTaskCompletionPolicyProposal,
    ) -> None:
        matches = [
            item
            for _, item in history.proposals
            if item.proposal_id == proposal.proposal_id
        ]
        if len(matches) != 1:
            raise _Blocked("completion_policy_proposal_replay_conflict")

    @staticmethod
    def _snapshot_for_decision(
        history: _PolicyHistory,
        decision_id: UUID,
    ) -> ProjectDirectorTaskCompletionPolicySnapshot:
        matches = [
            snapshot
            for _, snapshot in history.snapshots
            if snapshot.source_decision_id == decision_id
        ]
        if len(matches) != 1:
            raise _Blocked("completion_policy_decision_conflict")
        return matches[0]

    @staticmethod
    def _without_fingerprint(record: Any, field: str) -> dict[str, Any]:
        return record.model_dump(mode="json", exclude={field})

    @staticmethod
    def _safe_config_payload(config: Any) -> dict[str, Any]:
        payload = config.model_dump(mode="json")
        for key in (
            "review_note",
            "warnings",
            "created_at",
            "updated_at",
            "confirmed_at",
            "rejected_at",
        ):
            payload.pop(key, None)
        return payload

    @staticmethod
    def _require_config_lineage(
        config: Any | None,
        plan: ProjectDirectorPlanVersion,
    ) -> None:
        if config is None:
            return
        if (
            config.plan_version_id != plan.id
            or config.project_id != plan.project_id
            or config.source_draft_id != f"pdv:{plan.id}:{plan.version_no}"
        ):
            raise _Blocked("completion_policy_task_lineage_invalid")

    @classmethod
    def _fingerprint(cls, payload: Any) -> str:
        canonical = json.dumps(
            cls._canonicalize(payload),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def _canonicalize(cls, value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return cls._canonicalize(value.model_dump(mode="json"))
        if isinstance(value, dict):
            return {str(key): cls._canonicalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._canonicalize(item) for item in value]
        if isinstance(value, UUID):
            return str(value).lower()
        if isinstance(value, datetime):
            normalized = value
            if normalized.tzinfo is None:
                normalized = normalized.replace(tzinfo=timezone.utc)
            normalized = normalized.astimezone(timezone.utc)
            return normalized.isoformat().replace("+00:00", "Z")
        if isinstance(value, Enum):
            return value.value
        return value

    @staticmethod
    def _clean_strings(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))

    @staticmethod
    def _forbidden_actions() -> list[str]:
        return [
            "no_source_completion_evidence",
            "no_next_task_resolution",
            "no_task_creation_or_mutation",
            "no_run_creation_or_mutation",
            "no_worker_reservation_or_invocation",
            "no_provider_or_native_executor_call",
            "no_workspace_write",
            "no_product_runtime_git_write",
            "no_pr_creation",
            "no_merge",
            "no_ci_trigger",
        ]


__all__ = (
    "P24_TASK_COMPLETION_POLICY_DECISION_ACTION_TYPE",
    "P24_TASK_COMPLETION_POLICY_DECISION_SOURCE_DETAIL",
    "P24_TASK_COMPLETION_POLICY_PROPOSAL_ACTION_TYPE",
    "P24_TASK_COMPLETION_POLICY_PROPOSAL_SOURCE_DETAIL",
    "P24_TASK_COMPLETION_POLICY_SNAPSHOT_ACTION_TYPE",
    "P24_TASK_COMPLETION_POLICY_SNAPSHOT_SOURCE_DETAIL",
    "ProjectDirectorTaskCompletionPolicyService",
)
