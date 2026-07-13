"""P24-B3A source-Task completion evidence issuance and revalidation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.domain._base import utc_now
from app.domain.agent_session import (
    AgentSession,
    AgentSessionPhase,
    AgentSessionReviewStatus,
    AgentSessionStatus,
    CodingSessionActivityState,
    CodingSessionStatus,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_source_execution_authority import (
    SourceExecutionAuthoritySnapshot,
)
from app.domain.project_director_source_completion_review_evidence import (
    ProjectDirectorSourceCompletionReviewEvidence,
)
from app.domain.project_director_source_completion_delivery_evidence import (
    ProjectDirectorSourceCompletionDeliveryEvidence,
)
from app.domain.project_director_source_completion_approval_evidence import (
    ProjectDirectorSourceCompletionApprovalEvidence,
)
from app.domain.project_director_source_task_completion_evidence import (
    ProjectDirectorSourceTaskCompletionEvidence,
    SOURCE_TASK_COMPLETION_EVIDENCE_SCHEMA_VERSION,
    SourceTaskCompletionBlockedReason,
    SourceTaskCompletionEvidenceResult,
)
from app.domain.project_director_task_completion_policy import (
    ProjectDirectorTaskCompletionPolicySnapshot,
)
from app.domain.run import Run, RunStatus
from app.domain.task import Task, TaskHumanStatus, TaskStatus
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.deliverable_repository import DeliverableRepository
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.project_director_source_execution_authority_resolver import (
    ProjectDirectorSourceExecutionAuthorityResolver,
)
from app.services.project_director_source_completion_delivery_evidence_adapter import (
    ProjectDirectorSourceCompletionDeliveryEvidenceAdapter,
)
from app.services.project_director_source_completion_approval_evidence_adapter import (
    ProjectDirectorSourceCompletionApprovalEvidenceAdapter,
)
from app.services.project_director_source_completion_review_evidence_adapter import (
    ProjectDirectorSourceCompletionReviewEvidenceAdapter,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_service import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionService,
)
from app.services.project_director_task_completion_policy_service import (
    ProjectDirectorTaskCompletionPolicyService,
)


P24_SOURCE_TASK_COMPLETION_EVIDENCE_ACTION_TYPE = (
    "p24_source_task_completion_evidence_record"
)
P24_SOURCE_TASK_COMPLETION_EVIDENCE_SOURCE_DETAIL = (
    "p24_source_task_completion_evidence_recorded"
)

_EVIDENCE_INTENT = "source_task_completion_evidence"
_REPLAY_ACTION = "issue_source_task_completion_evidence"
_NOT_REQUIRED_EVIDENCE_KIND = "human_owner_policy_decision"
_WORKER_QUALITY_GATE_EVIDENCE_KIND = "worker_quality_gate_passed"
_PAGE_SIZE = 200


@dataclass(frozen=True)
class _AxisEvidence:
    requirement: str
    satisfaction_status: str
    evidence_kind: str
    evidence_ids: list[UUID]


@dataclass(frozen=True)
class _ValidatedInputs:
    authority: SourceExecutionAuthoritySnapshot
    policy: ProjectDirectorTaskCompletionPolicySnapshot
    task: Task
    run: Run
    agent_session: AgentSession | None
    axes: dict[str, _AxisEvidence]
    completion_review: ProjectDirectorSourceCompletionReviewEvidence | None
    completion_delivery: (
        ProjectDirectorSourceCompletionDeliveryEvidence | None
    )
    completion_approval: (
        ProjectDirectorSourceCompletionApprovalEvidence | None
    )


class _Blocked(Exception):
    def __init__(self, *reasons: SourceTaskCompletionBlockedReason) -> None:
        self.reasons = tuple(dict.fromkeys(reasons))
        super().__init__(
            self.reasons[0]
            if self.reasons
            else "source_completion_axis_unsatisfied"
        )


class ProjectDirectorSourceTaskCompletionEvidenceService:
    """Issue one immutable certificate without mutating execution state."""

    def __init__(
        self,
        *,
        authority_resolver: ProjectDirectorSourceExecutionAuthorityResolver,
        completion_policy_service: ProjectDirectorTaskCompletionPolicyService,
        message_repository: ProjectDirectorMessageRepository,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        agent_session_repository: AgentSessionRepository,
        completion_review_evidence_adapter: ProjectDirectorSourceCompletionReviewEvidenceAdapter
        | None = None,
        completion_delivery_evidence_adapter: (
            ProjectDirectorSourceCompletionDeliveryEvidenceAdapter | None
        ) = None,
        completion_approval_evidence_adapter: (
            ProjectDirectorSourceCompletionApprovalEvidenceAdapter | None
        ) = None,
    ) -> None:
        self._authority_resolver = authority_resolver
        self._completion_policy_service = completion_policy_service
        self._message_repository = message_repository
        self._task_repository = task_repository
        self._run_repository = run_repository
        self._agent_session_repository = agent_session_repository
        self._completion_review_evidence_adapter = (
            completion_review_evidence_adapter
            or ProjectDirectorSourceCompletionReviewEvidenceAdapter(
                message_repository=message_repository,
                review_disposition_service=(
                    ProjectDirectorSandboxCandidateDiffReviewDispositionService(
                        message_repository=message_repository
                    )
                ),
            )
        )
        self._completion_delivery_evidence_adapter = (
            completion_delivery_evidence_adapter
            or ProjectDirectorSourceCompletionDeliveryEvidenceAdapter(
                deliverable_repository=DeliverableRepository(
                    message_repository._session
                )
            )
        )
        self._completion_approval_evidence_adapter = (
            completion_approval_evidence_adapter
            or ProjectDirectorSourceCompletionApprovalEvidenceAdapter(
                approval_repository=ApprovalRepository(message_repository._session)
            )
        )
        self._require_shared_session()

    def issue_source_task_completion_evidence(
        self,
        *,
        authority_kind: str,
        authority_record_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
        completion_policy_id: UUID,
        review_evidence_ids: list[UUID] | None = None,
        delivery_evidence_ids: list[UUID] | None = None,
        approval_evidence_ids: list[UUID] | None = None,
    ) -> SourceTaskCompletionEvidenceResult:
        """Append or replay evidence after rebuilding every persisted authority."""

        try:
            with self._message_repository.sqlite_immediate_transaction():
                validated = self._load_validated_inputs(
                    authority_kind=authority_kind,
                    authority_record_id=authority_record_id,
                    source_task_id=source_task_id,
                    source_run_id=source_run_id,
                    completion_policy_id=completion_policy_id,
                    review_evidence_ids=review_evidence_ids,
                    delivery_evidence_ids=delivery_evidence_ids,
                    approval_evidence_ids=approval_evidence_ids,
                )
                replay_key = self._build_replay_key(
                    authority=validated.authority,
                    policy=validated.policy,
                    source_task_id=source_task_id,
                    source_run_id=source_run_id,
                )
                history = self._load_evidence_history(validated.authority.session_id)
                semantic_identity = self._semantic_identity_from_inputs(
                    authority=validated.authority,
                    policy=validated.policy,
                    source_task_id=source_task_id,
                    source_run_id=source_run_id,
                )
                semantic_matches = [
                    evidence
                    for _, evidence in history
                    if self._semantic_identity(evidence) == semantic_identity
                ]
                replay_matches = [
                    evidence
                    for _, evidence in history
                    if evidence.source_completion_evidence_replay_key == replay_key
                ]
                if len(semantic_matches) > 1 or len(replay_matches) > 1:
                    raise _Blocked("source_completion_evidence_replay_conflict")
                if replay_matches and (
                    not semantic_matches or replay_matches[0] != semantic_matches[0]
                ):
                    raise _Blocked("source_completion_evidence_replay_conflict")
                if semantic_matches:
                    existing = semantic_matches[0]
                    if existing.source_completion_evidence_replay_key != replay_key:
                        raise _Blocked("source_completion_evidence_replay_conflict")
                    expected = self._build_evidence(
                        evidence_id=existing.source_completion_evidence_id,
                        created_at=existing.created_at,
                        replay_key=replay_key,
                        validated=validated,
                    )
                    if existing != expected:
                        raise _Blocked("source_completion_evidence_replay_conflict")
                    return SourceTaskCompletionEvidenceResult(
                        status="evidence_replayed",
                        evidence=existing,
                    )

                evidence = self._build_evidence(
                    evidence_id=uuid4(),
                    created_at=utc_now(),
                    replay_key=replay_key,
                    validated=validated,
                )
                self._append_evidence_message(evidence)
                return SourceTaskCompletionEvidenceResult(
                    status="evidence_recorded",
                    evidence=evidence,
                )
        except _Blocked as exc:
            return SourceTaskCompletionEvidenceResult.blocked(*exc.reasons)

    def revalidate_persisted_source_task_completion_evidence(
        self,
        *,
        source_completion_evidence_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
    ) -> SourceTaskCompletionEvidenceResult:
        """Read and deterministically rebuild one immutable evidence record."""

        try:
            message = self._message_repository.get_by_id(source_completion_evidence_id)
            if message is None:
                raise _Blocked("source_completion_evidence_missing")
            evidence = self._parse_evidence_message(message)
            if (
                evidence.source_completion_evidence_id
                != source_completion_evidence_id
                or evidence.source_task_id != source_task_id
                or evidence.source_success_run_id != source_run_id
            ):
                raise _Blocked("source_completion_evidence_lineage_invalid")

            validated = self._load_validated_inputs(
                authority_kind=evidence.source_execution_authority_kind,
                authority_record_id=evidence.source_outcome_id,
                source_task_id=source_task_id,
                source_run_id=source_run_id,
                completion_policy_id=evidence.completion_policy_id,
                review_evidence_ids=(
                    list(evidence.review_evidence_ids)
                    if evidence.review_requirement == "required"
                    else None
                ),
                delivery_evidence_ids=(
                    list(evidence.delivery_evidence_ids)
                    if evidence.delivery_requirement == "required"
                    else None
                ),
                approval_evidence_ids=(
                    list(evidence.approval_evidence_ids)
                    if evidence.approval_requirement == "required"
                    else None
                ),
                historical_revalidation=True,
            )
            replay_key = self._build_replay_key(
                authority=validated.authority,
                policy=validated.policy,
                source_task_id=source_task_id,
                source_run_id=source_run_id,
            )
            expected = self._build_evidence(
                evidence_id=evidence.source_completion_evidence_id,
                created_at=evidence.created_at,
                replay_key=replay_key,
                validated=validated,
            )
            if evidence != expected:
                raise _Blocked("source_completion_evidence_lineage_invalid")

            history = self._load_evidence_history(evidence.session_id)
            semantic_matches = [
                item
                for _, item in history
                if self._semantic_identity(item) == self._semantic_identity(evidence)
            ]
            replay_matches = [
                item
                for _, item in history
                if item.source_completion_evidence_replay_key
                == evidence.source_completion_evidence_replay_key
            ]
            if (
                len(semantic_matches) != 1
                or len(replay_matches) != 1
                or semantic_matches[0] != evidence
                or replay_matches[0] != evidence
            ):
                raise _Blocked("source_completion_evidence_replay_conflict")
            return SourceTaskCompletionEvidenceResult(
                status="evidence_revalidated",
                evidence=evidence,
            )
        except _Blocked as exc:
            return SourceTaskCompletionEvidenceResult.blocked(*exc.reasons)

    def _load_validated_inputs(
        self,
        *,
        authority_kind: str,
        authority_record_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
        completion_policy_id: UUID,
        review_evidence_ids: list[UUID] | None,
        delivery_evidence_ids: list[UUID] | None,
        approval_evidence_ids: list[UUID] | None,
        historical_revalidation: bool = False,
    ) -> _ValidatedInputs:
        authority_result = self._authority_resolver.resolve(
            authority_kind=authority_kind,
            authority_record_id=authority_record_id,
            source_task_id=source_task_id,
            source_run_id=source_run_id,
        )
        if not authority_result.resolved or authority_result.snapshot is None:
            raise _Blocked(*self._map_authority_reasons(authority_result.blocked_reasons))
        authority = authority_result.snapshot

        policy_result = (
            self._completion_policy_service
            .revalidate_persisted_task_completion_policy(
                completion_policy_id=completion_policy_id,
                task_id=source_task_id,
            )
        )
        if policy_result.snapshot is None or policy_result.blocked_reasons:
            raise _Blocked(*self._map_policy_reasons(policy_result.blocked_reasons))
        policy = policy_result.snapshot

        if authority.task_id != source_task_id or authority.run_id != source_run_id:
            raise _Blocked("source_completion_authority_task_run_mismatch")
        if policy.task_id != source_task_id:
            raise _Blocked("source_completion_policy_task_mismatch")
        if (
            authority.session_id != policy.session_id
            or authority.project_id != policy.project_id
            or policy.product_runtime_git_write_allowed
        ):
            raise _Blocked("source_completion_policy_invalid")
        if authority.product_runtime_git_write_allowed:
            raise _Blocked("source_completion_git_boundary_violation")

        task = self._task_repository.get_by_id(source_task_id)
        if task is None:
            raise _Blocked("source_completion_task_missing")
        run = self._run_repository.get_by_id(source_run_id)
        if run is None:
            raise _Blocked("source_completion_run_missing")
        if task.project_id != authority.project_id:
            raise _Blocked("source_completion_authority_task_run_mismatch")
        if run.task_id != source_task_id:
            raise _Blocked("source_completion_task_run_mismatch")
        if task.status != TaskStatus.COMPLETED:
            raise _Blocked("source_completion_task_not_completed")
        if task.human_status not in {
            TaskHumanStatus.NONE,
            TaskHumanStatus.RESOLVED,
        }:
            raise _Blocked("source_completion_task_human_state_pending")
        if task.paused_reason is not None:
            raise _Blocked("source_completion_task_paused")
        if run.status != RunStatus.SUCCEEDED:
            raise _Blocked("source_completion_run_not_succeeded")
        if run.finished_at is None:
            raise _Blocked("source_completion_run_not_finished")
        if run.failure_category is not None:
            raise _Blocked("source_completion_run_failure_category_present")

        if authority.task_status_after != TaskStatus.COMPLETED.value:
            raise _Blocked("source_completion_terminal_state_mismatch")
        if authority.run_status_after != RunStatus.SUCCEEDED.value:
            raise _Blocked("source_completion_terminal_state_mismatch")
        quality_gate_reasons: list[SourceTaskCompletionBlockedReason] = []
        if run.quality_gate_passed is None:
            quality_gate_reasons.append(
                "source_completion_run_quality_gate_missing"
            )
        elif run.quality_gate_passed is not True:
            quality_gate_reasons.append(
                "source_completion_run_quality_gate_failed"
            )
        if authority.worker_quality_gate_passed is None:
            quality_gate_reasons.append("source_completion_quality_gate_missing")
        elif authority.worker_quality_gate_passed is not True:
            quality_gate_reasons.append("source_completion_quality_gate_failed")
        if (
            run.quality_gate_passed is not None
            and authority.worker_quality_gate_passed is not None
            and run.quality_gate_passed
            != authority.worker_quality_gate_passed
        ):
            quality_gate_reasons.append("source_completion_quality_gate_mismatch")
        if quality_gate_reasons:
            raise _Blocked(*quality_gate_reasons)

        agent_session = self._validate_agent_session(
            authority=authority,
            source_task_id=source_task_id,
            source_run_id=source_run_id,
        )
        axes, completion_review, completion_delivery, completion_approval = (
            self._evaluate_axes(
                policy=policy,
                authority=authority,
                source_run_finished_at=run.finished_at,
                review_evidence_ids=review_evidence_ids,
                delivery_evidence_ids=delivery_evidence_ids,
                approval_evidence_ids=approval_evidence_ids,
                historical_revalidation=historical_revalidation,
            )
        )
        return _ValidatedInputs(
            authority=authority,
            policy=policy,
            task=task,
            run=run,
            agent_session=agent_session,
            axes=axes,
            completion_review=completion_review,
            completion_delivery=completion_delivery,
            completion_approval=completion_approval,
        )

    def _validate_agent_session(
        self,
        *,
        authority: SourceExecutionAuthoritySnapshot,
        source_task_id: UUID,
        source_run_id: UUID,
    ) -> AgentSession | None:
        agent_sessions = self._agent_session_repository.list_by_run_id(
            source_run_id
        )
        if len(agent_sessions) > 1:
            raise _Blocked("source_completion_agent_session_conflict")
        if not agent_sessions:
            if authority.agent_session_id is not None:
                raise _Blocked("source_completion_agent_session_missing")
            if authority.agent_session_status is not None:
                raise _Blocked("source_completion_agent_session_mismatch")
            return None
        agent_session = agent_sessions[0]
        if (
            authority.agent_session_id is None
            or authority.agent_session_id != agent_session.id
            or agent_session.task_id != source_task_id
            or agent_session.run_id != source_run_id
            or agent_session.project_id != authority.project_id
            or authority.agent_session_status != AgentSessionStatus.COMPLETED.value
            or agent_session.status != AgentSessionStatus.COMPLETED
            or agent_session.current_phase != AgentSessionPhase.FINALIZED
            or agent_session.status.value != authority.agent_session_status
        ):
            raise _Blocked("source_completion_agent_session_mismatch")
        if agent_session.review_status != AgentSessionReviewStatus.REVIEW_PASSED:
            raise _Blocked("source_completion_agent_session_review_pending")
        if agent_session.finished_at is None:
            raise _Blocked("source_completion_agent_session_not_finished")
        if (
            agent_session.coding_status
            in {
                CodingSessionStatus.SPAWNING,
                CodingSessionStatus.WORKING,
                CodingSessionStatus.IDLE,
                CodingSessionStatus.NEEDS_INPUT,
                CodingSessionStatus.STUCK,
            }
            or agent_session.activity_state
            in {
                CodingSessionActivityState.ACTIVE,
                CodingSessionActivityState.READY,
                CodingSessionActivityState.IDLE,
                CodingSessionActivityState.WAITING_INPUT,
                CodingSessionActivityState.BLOCKED,
            }
        ):
            raise _Blocked("source_completion_runtime_active")
        if (
            agent_session.coding_status != CodingSessionStatus.COMPLETED
            or agent_session.activity_state != CodingSessionActivityState.EXITED
        ):
            raise _Blocked("source_completion_runtime_terminal_unproven")
        return agent_session

    def _evaluate_axes(
        self,
        *,
        policy: ProjectDirectorTaskCompletionPolicySnapshot,
        authority: SourceExecutionAuthoritySnapshot,
        source_run_finished_at: datetime,
        review_evidence_ids: list[UUID] | None,
        delivery_evidence_ids: list[UUID] | None,
        approval_evidence_ids: list[UUID] | None,
        historical_revalidation: bool,
    ) -> tuple[
        dict[str, _AxisEvidence],
        ProjectDirectorSourceCompletionReviewEvidence | None,
        ProjectDirectorSourceCompletionDeliveryEvidence | None,
        ProjectDirectorSourceCompletionApprovalEvidence | None,
    ]:
        axes: dict[str, _AxisEvidence] = {}
        completion_review: ProjectDirectorSourceCompletionReviewEvidence | None = None
        completion_delivery: (
            ProjectDirectorSourceCompletionDeliveryEvidence | None
        ) = None
        completion_approval: (
            ProjectDirectorSourceCompletionApprovalEvidence | None
        ) = None
        for axis in ("review", "verification", "delivery", "approval"):
            requirement = getattr(policy, f"{axis}_requirement")
            if requirement == "not_required":
                if axis == "review" and review_evidence_ids:
                    raise _Blocked("source_completion_review_evidence_conflict")
                if axis == "delivery" and delivery_evidence_ids:
                    raise _Blocked("source_completion_delivery_evidence_conflict")
                if axis == "approval" and approval_evidence_ids:
                    raise _Blocked("source_completion_approval_evidence_conflict")
                axes[axis] = _AxisEvidence(
                    requirement=requirement,
                    satisfaction_status="not_required_by_policy",
                    evidence_kind=_NOT_REQUIRED_EVIDENCE_KIND,
                    evidence_ids=[policy.source_decision_id],
                )
                continue
            if requirement != "required":
                raise _Blocked("source_completion_axis_unsatisfied")
            if axis == "review":
                resolution = self._completion_review_evidence_adapter.resolve_required_completion_review(
                    session_id=authority.session_id,
                    project_id=authority.project_id,
                    source_task_id=authority.task_id,
                    source_run_id=authority.run_id,
                    source_run_finished_at=source_run_finished_at,
                    declared_review_evidence_ids=list(review_evidence_ids or []),
                    allowed_review_terminal_results=(
                        policy.required_review_terminal_results
                    ),
                )
                if resolution.snapshot is None or resolution.blocked_reasons:
                    raise _Blocked(*resolution.blocked_reasons)
                completion_review = resolution.snapshot
                axes[axis] = _AxisEvidence(
                    requirement=requirement,
                    satisfaction_status="satisfied",
                    evidence_kind=completion_review.review_evidence_kind,
                    evidence_ids=[
                        completion_review.review_message_id,
                        completion_review.disposition_message_id,
                    ],
                )
                continue
            if axis == "delivery":
                resolution = (
                    self._completion_delivery_evidence_adapter
                    .resolve_required_completion_delivery(
                        project_id=authority.project_id,
                        source_task_id=authority.task_id,
                        source_run_id=authority.run_id,
                        declared_delivery_evidence_ids=list(
                            delivery_evidence_ids or []
                        ),
                        allowed_delivery_evidence_kinds=(
                            policy.required_delivery_evidence_kinds
                        ),
                    )
                )
                if resolution.snapshot is None or resolution.blocked_reasons:
                    if historical_revalidation:
                        raise _Blocked("source_completion_evidence_lineage_invalid")
                    raise _Blocked(*resolution.blocked_reasons)
                completion_delivery = resolution.snapshot
                axes[axis] = _AxisEvidence(
                    requirement=requirement,
                    satisfaction_status="satisfied",
                    evidence_kind=completion_delivery.delivery_evidence_kind,
                    evidence_ids=[
                        completion_delivery.deliverable_id,
                        completion_delivery.deliverable_version_id,
                    ],
                )
                continue
            if axis == "approval":
                if completion_delivery is None:
                    raise _Blocked(
                        "source_completion_approval_delivery_evidence_required"
                    )
                resolution = (
                    self._completion_approval_evidence_adapter
                    .resolve_required_completion_approval(
                        project_id=authority.project_id,
                        source_task_id=authority.task_id,
                        source_run_id=authority.run_id,
                        completion_delivery=completion_delivery,
                        declared_approval_evidence_ids=list(
                            approval_evidence_ids or []
                        ),
                        allowed_approval_terminal_results=(
                            policy.required_approval_terminal_results
                        ),
                    )
                )
                if resolution.snapshot is None or resolution.blocked_reasons:
                    if historical_revalidation:
                        raise _Blocked("source_completion_evidence_lineage_invalid")
                    raise _Blocked(*resolution.blocked_reasons)
                completion_approval = resolution.snapshot
                axes[axis] = _AxisEvidence(
                    requirement=requirement,
                    satisfaction_status="satisfied",
                    evidence_kind=completion_approval.approval_evidence_kind,
                    evidence_ids=[
                        completion_approval.approval_request_id,
                        completion_approval.approval_decision_id,
                    ],
                )
                continue
            allowed_kinds = policy.required_verification_evidence_kinds
            if _WORKER_QUALITY_GATE_EVIDENCE_KIND not in allowed_kinds:
                raise _Blocked(
                    "source_completion_verification_evidence_kind_unsupported"
                )
            if authority.worker_quality_gate_passed is not True:
                raise _Blocked("source_completion_axis_unsatisfied")
            axes[axis] = _AxisEvidence(
                requirement=requirement,
                satisfaction_status="satisfied",
                evidence_kind=_WORKER_QUALITY_GATE_EVIDENCE_KIND,
                evidence_ids=[authority.outcome_id],
            )
        return axes, completion_review, completion_delivery, completion_approval

    def _build_evidence(
        self,
        *,
        evidence_id: UUID,
        created_at: datetime,
        replay_key: str,
        validated: _ValidatedInputs,
    ) -> ProjectDirectorSourceTaskCompletionEvidence:
        authority = validated.authority
        policy = validated.policy
        payload = {
            "schema_version": SOURCE_TASK_COMPLETION_EVIDENCE_SCHEMA_VERSION,
            "source_completion_evidence_id": evidence_id,
            "source_completion_evidence_replay_key": replay_key,
            "created_at": created_at,
            "session_id": authority.session_id,
            "project_id": authority.project_id,
            "plan_version_id": policy.plan_version_id,
            "plan_version_no": policy.plan_version_no,
            "task_creation_record_id": policy.task_creation_record_id,
            "source_task_id": authority.task_id,
            "source_success_run_id": authority.run_id,
            "source_execution_authority_kind": authority.authority_kind,
            "source_execution_authority_id": authority.authority_id,
            "source_execution_authority_fingerprint": authority.authority_fingerprint,
            "source_reservation_id": authority.reservation_id,
            "source_claim_id": authority.claim_id,
            "source_outcome_id": authority.outcome_id,
            "source_outcome_schema_version": authority.outcome_schema_version,
            "source_outcome_fingerprint": authority.outcome_fingerprint,
            "source_review_id": authority.source_review_id,
            "source_review_outcome": authority.source_review_outcome,
            "source_transition_evidence_ids": list(
                authority.source_transition_evidence_ids
            ),
            "completion_policy_id": policy.completion_policy_id,
            "completion_policy_version": policy.completion_policy_version,
            "completion_policy_fingerprint": policy.completion_policy_fingerprint,
            "source_completion_review_id": (
                validated.completion_review.review_message_id
                if validated.completion_review is not None
                else None
            ),
            "source_completion_review_result_fingerprint": (
                validated.completion_review.review_result_fingerprint
                if validated.completion_review is not None
                else None
            ),
            "source_completion_review_verdict": (
                validated.completion_review.review_verdict
                if validated.completion_review is not None
                else None
            ),
            "source_completion_review_disposition_id": (
                validated.completion_review.disposition_id
                if validated.completion_review is not None
                else None
            ),
            "source_completion_review_disposition_type": (
                validated.completion_review.disposition_type
                if validated.completion_review is not None
                else None
            ),
            "source_completion_review_diff_id": (
                validated.completion_review.source_diff_message_id
                if validated.completion_review is not None
                else None
            ),
            "source_completion_review_diff_sha256": (
                validated.completion_review.source_diff_sha256
                if validated.completion_review is not None
                else None
            ),
            "source_completion_deliverable_id": (
                validated.completion_delivery.deliverable_id
                if validated.completion_delivery is not None
                else None
            ),
            "source_completion_deliverable_version_id": (
                validated.completion_delivery.deliverable_version_id
                if validated.completion_delivery is not None
                else None
            ),
            "source_completion_deliverable_version_fingerprint": (
                validated.completion_delivery.deliverable_version_fingerprint
                if validated.completion_delivery is not None
                else None
            ),
            "source_completion_deliverable_version_number": (
                validated.completion_delivery.version_number
                if validated.completion_delivery is not None
                else None
            ),
            "source_completion_deliverable_type": (
                validated.completion_delivery.deliverable_type
                if validated.completion_delivery is not None
                else None
            ),
            "source_completion_deliverable_stage": (
                validated.completion_delivery.deliverable_stage
                if validated.completion_delivery is not None
                else None
            ),
            "source_completion_deliverable_content_format": (
                validated.completion_delivery.version_content_format
                if validated.completion_delivery is not None
                else None
            ),
            "source_completion_deliverable_content_sha256": (
                validated.completion_delivery.version_content_sha256
                if validated.completion_delivery is not None
                else None
            ),
            "source_completion_deliverable_content_bytes": (
                validated.completion_delivery.version_content_bytes
                if validated.completion_delivery is not None
                else None
            ),
            "source_completion_deliverable_version_created_at": (
                validated.completion_delivery.version_created_at
                if validated.completion_delivery is not None
                else None
            ),
            "source_completion_approval_request_id": (
                validated.completion_approval.approval_request_id
                if validated.completion_approval is not None
                else None
            ),
            "source_completion_approval_decision_id": (
                validated.completion_approval.approval_decision_id
                if validated.completion_approval is not None
                else None
            ),
            "source_completion_approval_fingerprint": (
                validated.completion_approval.approval_evidence_fingerprint
                if validated.completion_approval is not None
                else None
            ),
            "source_completion_approval_status": (
                validated.completion_approval.approval_status
                if validated.completion_approval is not None
                else None
            ),
            "source_completion_approval_action": (
                validated.completion_approval.approval_decision_action
                if validated.completion_approval is not None
                else None
            ),
            "source_completion_approval_deliverable_id": (
                validated.completion_approval.deliverable_id
                if validated.completion_approval is not None
                else None
            ),
            "source_completion_approval_deliverable_version_id": (
                validated.completion_approval.deliverable_version_id
                if validated.completion_approval is not None
                else None
            ),
            "source_completion_approval_decided_at": (
                validated.completion_approval.decided_at
                if validated.completion_approval is not None
                else None
            ),
            "source_completion_approval_actor_name": (
                validated.completion_approval.decision_actor_name
                if validated.completion_approval is not None
                else None
            ),
            "source_completion_approval_summary_sha256": (
                validated.completion_approval.decision_summary_sha256
                if validated.completion_approval is not None
                else None
            ),
            "source_completion_approval_summary_bytes": (
                validated.completion_approval.decision_summary_bytes
                if validated.completion_approval is not None
                else None
            ),
            "terminal_task_status": TaskStatus.COMPLETED.value,
            "terminal_task_human_status": validated.task.human_status.value,
            "task_paused_reason_absent": validated.task.paused_reason is None,
            "terminal_run_status": RunStatus.SUCCEEDED.value,
            "run_finished_at": validated.run.finished_at,
            "run_quality_gate_passed": validated.run.quality_gate_passed,
            "run_failure_category_absent": validated.run.failure_category is None,
            "quality_gate_passed": True,
            "authority_task_status_after": authority.task_status_after,
            "authority_run_status_after": authority.run_status_after,
            "authority_agent_session_id": authority.agent_session_id,
            "authority_agent_session_status": authority.agent_session_status,
            "agent_session_phase": (
                validated.agent_session.current_phase.value
                if validated.agent_session is not None
                else None
            ),
            "agent_session_review_status": (
                validated.agent_session.review_status.value
                if validated.agent_session is not None
                else None
            ),
            "agent_session_finished_at": (
                validated.agent_session.finished_at
                if validated.agent_session is not None
                else None
            ),
            "agent_coding_status": (
                validated.agent_session.coding_status.value
                if validated.agent_session is not None
                else None
            ),
            "agent_activity_state": (
                validated.agent_session.activity_state.value
                if validated.agent_session is not None
                else None
            ),
            "runtime_handle_recorded": (
                validated.agent_session.runtime_handle_id is not None
                if validated.agent_session is not None
                else False
            ),
            "runtime_terminal": True,
            "completion_status": "completed",
            "product_runtime_git_write_allowed": False,
            "forbidden_actions": self._forbidden_actions(),
        }
        for axis, axis_evidence in validated.axes.items():
            payload[f"{axis}_requirement"] = axis_evidence.requirement
            payload[f"{axis}_satisfaction_status"] = axis_evidence.satisfaction_status
            payload[f"{axis}_evidence_kind"] = axis_evidence.evidence_kind
            payload[f"{axis}_evidence_ids"] = axis_evidence.evidence_ids
        fingerprint = self._fingerprint(payload)
        try:
            return ProjectDirectorSourceTaskCompletionEvidence(
                **payload,
                source_completion_evidence_fingerprint=fingerprint,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("source_completion_evidence_schema_mismatch") from exc

    def _append_evidence_message(
        self,
        evidence: ProjectDirectorSourceTaskCompletionEvidence,
    ) -> None:
        if (
            evidence.product_runtime_git_write_allowed
            or evidence.forbidden_actions != self._forbidden_actions()
        ):
            raise _Blocked("source_completion_git_boundary_violation")
        action = {
            "type": P24_SOURCE_TASK_COMPLETION_EVIDENCE_ACTION_TYPE,
            **evidence.model_dump(mode="json"),
        }
        self._message_repository.create(
            ProjectDirectorMessage(
                id=evidence.source_completion_evidence_id,
                session_id=evidence.session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "P24 source Task completion evidence: "
                    f"{evidence.source_completion_evidence_id}"
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=evidence.session_id
                ),
                intent=_EVIDENCE_INTENT,
                related_plan_version_id=evidence.plan_version_id,
                related_project_id=evidence.project_id,
                related_task_id=evidence.source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=P24_SOURCE_TASK_COMPLETION_EVIDENCE_SOURCE_DETAIL,
                suggested_actions=[action],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                forbidden_actions_detected=list(evidence.forbidden_actions),
                created_at=evidence.created_at,
            )
        )

    def _load_evidence_history(
        self,
        session_id: UUID,
    ) -> list[tuple[ProjectDirectorMessage, ProjectDirectorSourceTaskCompletionEvidence]]:
        history: list[
            tuple[ProjectDirectorMessage, ProjectDirectorSourceTaskCompletionEvidence]
        ] = []
        for message in self._iter_session_messages(session_id):
            if self._is_evidence_message(message):
                history.append((message, self._parse_evidence_message(message)))
        return history

    def _parse_evidence_message(
        self,
        message: ProjectDirectorMessage,
    ) -> ProjectDirectorSourceTaskCompletionEvidence:
        if (
            message.role != ProjectDirectorMessageRole.ASSISTANT
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent != _EVIDENCE_INTENT
            or message.source_detail
            != P24_SOURCE_TASK_COMPLETION_EVIDENCE_SOURCE_DETAIL
            or message.requires_confirmation
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
            or len(message.suggested_actions) != 1
            or not isinstance(message.suggested_actions[0], dict)
        ):
            raise _Blocked("source_completion_evidence_schema_mismatch")
        action = message.suggested_actions[0]
        if (
            action.get("type") != P24_SOURCE_TASK_COMPLETION_EVIDENCE_ACTION_TYPE
            or action.get("schema_version")
            != SOURCE_TASK_COMPLETION_EVIDENCE_SCHEMA_VERSION
        ):
            raise _Blocked("source_completion_evidence_schema_mismatch")
        payload = dict(action)
        payload.pop("type", None)
        try:
            evidence = ProjectDirectorSourceTaskCompletionEvidence.model_validate(payload)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("source_completion_evidence_schema_mismatch") from exc
        if evidence.source_completion_evidence_id != message.id:
            raise _Blocked("source_completion_evidence_lineage_invalid")
        expected_fingerprint = self._fingerprint(
            evidence.model_dump(
                mode="json",
                exclude={"source_completion_evidence_fingerprint"},
            )
        )
        if expected_fingerprint != evidence.source_completion_evidence_fingerprint:
            raise _Blocked("source_completion_evidence_fingerprint_mismatch")
        expected_replay_key = self._build_replay_key_from_evidence(evidence)
        if expected_replay_key != evidence.source_completion_evidence_replay_key:
            raise _Blocked("source_completion_evidence_replay_conflict")
        if (
            message.session_id != evidence.session_id
            or message.related_project_id != evidence.project_id
            or message.related_plan_version_id != evidence.plan_version_id
            or message.related_task_id != evidence.source_task_id
            or message.created_at != evidence.created_at
            or message.forbidden_actions_detected != evidence.forbidden_actions
        ):
            raise _Blocked("source_completion_evidence_lineage_invalid")
        if (
            evidence.product_runtime_git_write_allowed
            or evidence.forbidden_actions != self._forbidden_actions()
        ):
            raise _Blocked("source_completion_git_boundary_violation")
        return evidence

    @classmethod
    def _build_replay_key(
        cls,
        *,
        authority: SourceExecutionAuthoritySnapshot,
        policy: ProjectDirectorTaskCompletionPolicySnapshot,
        source_task_id: UUID,
        source_run_id: UUID,
    ) -> str:
        return cls._fingerprint(
            {
                "schema_version": SOURCE_TASK_COMPLETION_EVIDENCE_SCHEMA_VERSION,
                "action": _REPLAY_ACTION,
                "authority_kind": authority.authority_kind,
                "authority_id": authority.authority_id,
                "authority_fingerprint": authority.authority_fingerprint,
                "source_task_id": source_task_id,
                "source_run_id": source_run_id,
                "completion_policy_id": policy.completion_policy_id,
                "completion_policy_version": policy.completion_policy_version,
                "completion_policy_fingerprint": policy.completion_policy_fingerprint,
            }
        )

    @classmethod
    def _build_replay_key_from_evidence(
        cls,
        evidence: ProjectDirectorSourceTaskCompletionEvidence,
    ) -> str:
        return cls._fingerprint(
            {
                "schema_version": evidence.schema_version,
                "action": _REPLAY_ACTION,
                "authority_kind": evidence.source_execution_authority_kind,
                "authority_id": evidence.source_execution_authority_id,
                "authority_fingerprint": (
                    evidence.source_execution_authority_fingerprint
                ),
                "source_task_id": evidence.source_task_id,
                "source_run_id": evidence.source_success_run_id,
                "completion_policy_id": evidence.completion_policy_id,
                "completion_policy_version": evidence.completion_policy_version,
                "completion_policy_fingerprint": (
                    evidence.completion_policy_fingerprint
                ),
            }
        )

    @staticmethod
    def _semantic_identity(
        evidence: ProjectDirectorSourceTaskCompletionEvidence,
    ) -> tuple[str, UUID, UUID, UUID, UUID]:
        return (
            evidence.source_execution_authority_kind,
            evidence.source_execution_authority_id,
            evidence.source_task_id,
            evidence.source_success_run_id,
            evidence.completion_policy_id,
        )

    @staticmethod
    def _semantic_identity_from_inputs(
        *,
        authority: SourceExecutionAuthoritySnapshot,
        policy: ProjectDirectorTaskCompletionPolicySnapshot,
        source_task_id: UUID,
        source_run_id: UUID,
    ) -> tuple[str, UUID, UUID, UUID, UUID]:
        return (
            authority.authority_kind,
            authority.authority_id,
            source_task_id,
            source_run_id,
            policy.completion_policy_id,
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
    def _is_evidence_message(message: ProjectDirectorMessage) -> bool:
        action_matches = any(
            isinstance(action, dict)
            and action.get("type") == P24_SOURCE_TASK_COMPLETION_EVIDENCE_ACTION_TYPE
            for action in message.suggested_actions
        )
        return (
            message.intent == _EVIDENCE_INTENT
            or message.source_detail
            == P24_SOURCE_TASK_COMPLETION_EVIDENCE_SOURCE_DETAIL
            or action_matches
        )

    @staticmethod
    def _map_authority_reasons(
        reasons: list[str],
    ) -> list[SourceTaskCompletionBlockedReason]:
        mapped: list[SourceTaskCompletionBlockedReason] = []
        for reason in reasons:
            if reason == "source_execution_authority_missing":
                mapped.append("source_completion_authority_missing")
            elif reason == "source_execution_authority_task_run_mismatch":
                mapped.append("source_completion_authority_task_run_mismatch")
            elif reason == "source_execution_authority_git_boundary_violation":
                mapped.append("source_completion_git_boundary_violation")
            else:
                mapped.append("source_completion_authority_invalid")
        return list(dict.fromkeys(mapped)) or ["source_completion_authority_invalid"]

    @staticmethod
    def _map_policy_reasons(
        reasons: list[str],
    ) -> list[SourceTaskCompletionBlockedReason]:
        mapped: list[SourceTaskCompletionBlockedReason] = []
        for reason in reasons:
            if reason == "completion_policy_snapshot_missing":
                mapped.append("source_completion_policy_missing")
            elif "task" in reason or "lineage" in reason:
                mapped.append("source_completion_policy_task_mismatch")
            elif "git_boundary" in reason:
                mapped.append("source_completion_git_boundary_violation")
            else:
                mapped.append("source_completion_policy_invalid")
        return list(dict.fromkeys(mapped)) or ["source_completion_policy_invalid"]

    def _require_shared_session(self) -> None:
        session = self._message_repository._session
        repositories = [
            self._task_repository,
            self._run_repository,
            self._agent_session_repository,
            self._completion_delivery_evidence_adapter._deliverable_repository,
            self._completion_approval_evidence_adapter._approval_repository,
            self._completion_review_evidence_adapter._message_repository,
            self._completion_review_evidence_adapter._review_disposition_service._message_repository,
            self._completion_policy_service._message_repository,
            self._completion_policy_service._plan_version_repository,
            self._completion_policy_service._task_creation_repository,
            self._completion_policy_service._task_repository,
            self._completion_policy_service._verification_config_repository,
            self._completion_policy_service._repository_binding_config_repository,
            self._completion_policy_service._agent_team_config_repository,
        ]
        for adapter in self._authority_resolver._adapters.values():
            adapter_message_repository = getattr(adapter, "_message_repository", None)
            if adapter_message_repository is not None:
                repositories.append(adapter_message_repository)
        if any(self._repository_session(item) is not session for item in repositories):
            raise ValueError("completion evidence dependencies must share one session")

    @staticmethod
    def _repository_session(repository: Any) -> Any:
        session = getattr(repository, "session", None)
        if session is not None:
            return session
        return getattr(repository, "_session", None)

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
            return value.isoformat().replace("+00:00", "Z")
        return value

    @staticmethod
    def _forbidden_actions() -> list[str]:
        return [
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
    "P24_SOURCE_TASK_COMPLETION_EVIDENCE_ACTION_TYPE",
    "P24_SOURCE_TASK_COMPLETION_EVIDENCE_SOURCE_DETAIL",
    "ProjectDirectorSourceTaskCompletionEvidenceService",
)
