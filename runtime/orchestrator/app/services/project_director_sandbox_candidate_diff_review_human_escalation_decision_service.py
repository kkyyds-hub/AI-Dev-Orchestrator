"""Structured human escalation decision recorder for Project Director P21-D-D2."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_sandbox_candidate_diff_review_human_escalation_decision import (
    HumanEscalationDecisionAction,
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult,
)
from app.domain.project_director_sandbox_candidate_diff_review_human_escalation_package import (
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_sandbox_candidate_diff_review_human_escalation_package_service import (
    HUMAN_ESCALATION_PACKAGE_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService,
    RevalidatedPersistedHumanEscalationPackageFingerprint,
)


P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_SOURCE_DETAIL = (
    "p21_d_sandbox_candidate_diff_review_human_escalation_decision_recorded"
)
P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_ACTION_TYPE = (
    "p21_d_sandbox_candidate_diff_review_human_escalation_decision_record"
)
HUMAN_ESCALATION_DECISION_SCHEMA_VERSION = "p21-d-d2.v1"

_VALID_DECISION_ACTIONS = (
    "APPROVE_CONTINUE",
    "REQUEST_REWORK",
    "REJECT",
)
_PACKAGE_FALSE_FLAGS = (
    "continuation_started",
    "rework_started",
    "human_decision_recorded",
    "approval_request_created",
    "legacy_approval_decision_created",
    "main_project_file_written",
    "sandbox_file_written",
    "manifest_file_written",
    "diff_file_written",
    "patch_applied",
    "git_write_performed",
    "worktree_created",
    "worker_started",
    "task_created",
    "run_created",
    "gate_allows_write",
)


@dataclass(frozen=True, slots=True)
class RecordedSandboxCandidateDiffReviewHumanEscalationDecision:
    """D2 result and optional append-only structured decision message."""

    result: ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult
    message: ProjectDirectorMessage | None


@dataclass(frozen=True, slots=True)
class _ValidatedHumanEscalationPackageEvidence:
    package: ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult
    action: dict[str, Any]


class ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionService:
    """Record one exact human decision without consuming or executing it."""

    def __init__(
        self,
        *,
        session_repository: ProjectDirectorSessionRepository | None = None,
        message_repository: ProjectDirectorMessageRepository | None = None,
        task_repository: TaskRepository | None = None,
    ) -> None:
        self._session_repository = session_repository
        self._message_repository = message_repository
        self._task_repository = task_repository

    def record_human_escalation_decision(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        decision_action: HumanEscalationDecisionAction,
        actor: str,
        client_request_id: str,
        decision_expires_at: datetime,
    ) -> RecordedSandboxCandidateDiffReviewHumanEscalationDecision:
        """Append one structured decision bound to one exact persisted D1 package."""

        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("human escalation decision repositories are required")

        with self._message_repository.sqlite_immediate_transaction():
            return self._record_human_escalation_decision(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
                decision_action=decision_action,
                actor=actor,
                client_request_id=client_request_id,
                decision_expires_at=decision_expires_at,
            )

    def _record_human_escalation_decision(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        decision_action: HumanEscalationDecisionAction,
        actor: str,
        client_request_id: str,
        decision_expires_at: datetime,
    ) -> RecordedSandboxCandidateDiffReviewHumanEscalationDecision:
        blocked_reasons: list[str] = []
        package_evidence: _ValidatedHumanEscalationPackageEvidence | None = None
        revalidation: RevalidatedPersistedHumanEscalationPackageFingerprint | None = (
            None
        )
        source_package_validated = False
        aggregate_fingerprint_revalidated = False
        replay_check_completed = False
        prior_decision_detected = False
        normalized_actor = actor.strip() if isinstance(actor, str) else ""
        normalized_client_request_id = (
            client_request_id.strip() if isinstance(client_request_id, str) else ""
        )
        normalized_expires_at = (
            decision_expires_at
            if self._timezone_aware_datetime(decision_expires_at)
            else None
        )

        def blocked_result() -> RecordedSandboxCandidateDiffReviewHumanEscalationDecision:
            return RecordedSandboxCandidateDiffReviewHumanEscalationDecision(
                result=self._blocked_result(
                    source_package_message_id=source_message_id,
                    package_evidence=package_evidence,
                    decision_action=(
                        decision_action
                        if decision_action in _VALID_DECISION_ACTIONS
                        else None
                    ),
                    actor=normalized_actor,
                    client_request_id=normalized_client_request_id,
                    decision_expires_at=normalized_expires_at,
                    source_package_validated=source_package_validated,
                    aggregate_fingerprint_revalidated=(
                        aggregate_fingerprint_revalidated
                    ),
                    replay_check_completed=replay_check_completed,
                    prior_decision_detected=prior_decision_detected,
                    blocked_reasons=blocked_reasons,
                ),
                message=None,
            )

        if decision_action not in _VALID_DECISION_ACTIONS:
            blocked_reasons.append("human_escalation_decision_action_invalid")
        if not normalized_actor or len(normalized_actor) > 200:
            blocked_reasons.append("human_escalation_decision_actor_invalid")
            normalized_actor = ""
        if (
            not normalized_client_request_id
            or len(normalized_client_request_id) > 200
        ):
            blocked_reasons.append("human_decision_client_request_id_invalid")
            normalized_client_request_id = ""
        if normalized_expires_at is None:
            blocked_reasons.append("human_escalation_decision_expiry_invalid")

        session_obj = self._session_repository.get_by_id(session_id)
        source_task = self._task_repository.get_by_id(source_task_id)
        source_package_message = self._message_repository.get_by_id(source_message_id)
        if session_obj is None:
            blocked_reasons.append("session_missing")
        if source_task is None:
            blocked_reasons.append("source_task_missing")
        if (
            session_obj is not None
            and source_task is not None
            and source_task.project_id != session_obj.project_id
        ):
            blocked_reasons.append("source_task_project_mismatch")
        if blocked_reasons or session_obj is None or source_task is None:
            return blocked_result()

        source_package_action = self._source_package_action(
            source_package_message=source_package_message,
            session_id=session_id,
            source_task_id=source_task_id,
            source_project_id=session_obj.project_id,
            blocked_reasons=blocked_reasons,
        )
        package_evidence = self._validated_package_evidence(
            source_package_action=source_package_action,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        if blocked_reasons or package_evidence is None:
            return blocked_result()
        source_package_validated = True

        revalidation = (
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService
            .revalidate_persisted_human_escalation_package_fingerprint(
                session_id=session_id,
                source_task_id=source_task_id,
                source_package_message_id=source_message_id,
                source_package_action=package_evidence.action,
            )
        )
        blocked_reasons.extend(revalidation.blocked_reasons)
        if blocked_reasons:
            return blocked_result()
        if (
            package_evidence.package.aggregate_evidence_fingerprint
            != revalidation.aggregate_evidence_fingerprint
        ):
            blocked_reasons.append("aggregate_evidence_fingerprint_mismatch")
            return blocked_result()
        aggregate_fingerprint_revalidated = True

        prior_decision_detected = self._scan_prior_decisions(
            session_id=session_id,
            source_package_message_id=source_message_id,
            escalation_package_id=package_evidence.package.escalation_package_id,
            client_request_id=normalized_client_request_id,
            blocked_reasons=blocked_reasons,
        )
        replay_check_completed = True
        if blocked_reasons:
            return blocked_result()

        decision_created_at = datetime.now(timezone.utc)
        if normalized_expires_at <= decision_created_at:
            blocked_reasons.append("human_escalation_decision_expiry_invalid")
            return blocked_result()

        decision_id = uuid4()
        decision_scope = "resolve_single_source_review_escalation"
        decision_confirmation_fingerprint = self._decision_confirmation_fingerprint(
            session_id=session_id,
            source_task_id=source_task_id,
            source_package_message_id=source_message_id,
            package=package_evidence.package,
            decision_scope=decision_scope,
            decision_action=decision_action,
            actor=normalized_actor,
            client_request_id=normalized_client_request_id,
            decision_id=decision_id,
            decision_created_at=decision_created_at,
            decision_expires_at=normalized_expires_at,
        )
        result = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(
            decision_status="recorded",
            decision_id=decision_id,
            source_package_message_id=source_message_id,
            escalation_package_id=package_evidence.package.escalation_package_id,
            source_disposition_message_id=(
                package_evidence.package.source_disposition_message_id
            ),
            source_review_message_id=package_evidence.package.source_review_message_id,
            source_preflight_message_id=(
                package_evidence.package.source_preflight_message_id
            ),
            source_diff_message_id=package_evidence.package.source_diff_message_id,
            disposition_id=package_evidence.package.disposition_id,
            aggregate_evidence_fingerprint=(
                package_evidence.package.aggregate_evidence_fingerprint
            ),
            decision_scope=decision_scope,
            decision_action=decision_action,
            actor_type="human",
            actor=normalized_actor,
            client_request_id=normalized_client_request_id,
            decision_created_at=decision_created_at,
            decision_expires_at=normalized_expires_at,
            decision_confirmation_fingerprint=decision_confirmation_fingerprint,
            source_package_validated=True,
            aggregate_evidence_fingerprint_revalidated=True,
            replay_check_completed=True,
            prior_decision_detected=False,
            human_escalation_package_created=True,
            human_decision_recorded=True,
        )
        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.USER,
                content=(
                    "One structured human escalation decision was recorded and "
                    "bound to the exact D1 package. The decision has not been "
                    "consumed. APPROVE_CONTINUE does not start continuation, "
                    "REQUEST_REWORK does not start rework, and REJECT performs no "
                    "cleanup or state change. No Task, Run, Worker, or worktree was "
                    "created. No file write, patch apply, or Git write was authorized. "
                    "AI Project Director total loop remains Partial."
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="sandbox_candidate_diff_review_human_escalation_decision",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=(
                    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_SOURCE_DETAIL
                ),
                suggested_actions=[
                    self._decision_action(
                        session_id=session_id,
                        source_task_id=source_task_id,
                        result=result,
                    )
                ],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                forbidden_actions_detected=[
                    "no_decision_consumption",
                    "no_continuation_start",
                    "no_rework_start",
                    "no_task_creation",
                    "no_run_creation",
                    "no_worker_dispatch",
                    "no_worktree_creation",
                    "no_workspace_write",
                    "no_main_project_file_write",
                    "no_manifest_write",
                    "no_diff_file_write",
                    "no_patch_apply",
                    "no_product_runtime_git_write",
                    "no_pr_creation",
                    "no_merge",
                    "no_ci_trigger",
                    "no_legacy_approval_request",
                    "no_legacy_approval_decision",
                    "no_raw_human_confirmation_text",
                ],
                created_at=decision_created_at,
            )
        )
        return RecordedSandboxCandidateDiffReviewHumanEscalationDecision(
            result=result,
            message=message,
        )

    @staticmethod
    def _source_package_action(
        *,
        source_package_message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        source_project_id: UUID | None,
        blocked_reasons: list[str],
    ) -> dict[str, Any] | None:
        if source_package_message is None:
            blocked_reasons.append("source_human_escalation_package_message_missing")
            return None
        if source_package_message.session_id != session_id:
            blocked_reasons.append("source_package_message_session_mismatch")
        if source_package_message.related_project_id != source_project_id:
            blocked_reasons.append("source_package_message_project_mismatch")
        if source_package_message.related_task_id != source_task_id:
            blocked_reasons.append("source_package_message_task_mismatch")
        if source_package_message.role != ProjectDirectorMessageRole.ASSISTANT:
            blocked_reasons.append("source_package_message_role_invalid")
        if source_package_message.source != ProjectDirectorMessageSource.SYSTEM:
            blocked_reasons.append("source_package_message_source_invalid")
        if (
            source_package_message.intent
            != "sandbox_candidate_diff_review_human_escalation_package"
        ):
            blocked_reasons.append("source_package_message_intent_invalid")
        if source_package_message.source_detail != (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_SOURCE_DETAIL
        ):
            blocked_reasons.append("source_message_is_not_p21_d_d1_package")
        if source_package_message.requires_confirmation is not True:
            blocked_reasons.append("source_package_confirmation_contract_invalid")
        if source_package_message.risk_level != ProjectDirectorMessageRiskLevel.HIGH:
            blocked_reasons.append("source_package_message_risk_level_invalid")
        if len(source_package_message.suggested_actions) != 1:
            blocked_reasons.append("source_human_escalation_package_record_missing")
            return None
        action = source_package_message.suggested_actions[0]
        if (
            not isinstance(action, dict)
            or action.get("type")
            != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_ACTION_TYPE
        ):
            blocked_reasons.append("source_human_escalation_package_record_missing")
            return None
        return action

    @classmethod
    def _validated_package_evidence(
        cls,
        *,
        source_package_action: dict[str, Any] | None,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> _ValidatedHumanEscalationPackageEvidence | None:
        if source_package_action is None:
            return None
        action = source_package_action
        if action.get("schema_version") != HUMAN_ESCALATION_PACKAGE_SCHEMA_VERSION:
            blocked_reasons.append("source_package_schema_version_mismatch")
        if action.get("package_status") != "prepared":
            blocked_reasons.append("source_package_status_invalid")
        if action.get("session_id") != str(session_id):
            blocked_reasons.append("source_package_action_session_mismatch")
        if action.get("source_task_id") != str(source_task_id):
            blocked_reasons.append("source_package_action_task_mismatch")

        domain_fields = (
            "package_status",
            "escalation_package_id",
            "source_disposition_message_id",
            "source_review_message_id",
            "source_preflight_message_id",
            "source_diff_message_id",
            "disposition_id",
            "disposition_type",
            "disposition_reason",
            "review_result_fingerprint",
            "revalidated_review_result_fingerprint",
            "aggregate_evidence_fingerprint",
            "escalation_triggers",
            "escalation_scope",
            "related_task_ids",
            "related_review_message_ids",
            "unresolved_blocking_findings",
            "risk_summary",
            "proposed_human_decision_scope",
            "source_review_validated",
            "replay_check_completed",
            "prior_escalation_package_detected",
            "blocked_reasons",
            "package_created_at",
            "continuation_started",
            "rework_started",
            "human_escalation_package_created",
            "human_decision_recorded",
            "approval_request_created",
            "legacy_approval_decision_created",
            "main_project_file_written",
            "sandbox_file_written",
            "manifest_file_written",
            "diff_file_written",
            "patch_applied",
            "git_write_performed",
            "worktree_created",
            "worker_started",
            "task_created",
            "run_created",
            "gate_allows_write",
            "ai_project_director_total_loop",
        )
        package: ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult | None
        try:
            package = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult.model_validate(
                {field_name: action.get(field_name) for field_name in domain_fields}
            )
        except ValidationError:
            package = None
            blocked_reasons.append("source_package_domain_reconstruction_invalid")

        if package is not None:
            if package.related_task_ids != [source_task_id]:
                blocked_reasons.append("source_package_related_task_binding_mismatch")
            if package.related_review_message_ids != [package.source_review_message_id]:
                blocked_reasons.append("source_package_related_review_binding_mismatch")
        if action.get("actor") != "system":
            blocked_reasons.append("source_package_actor_invalid")
        if action.get("client_request_id") is not None:
            blocked_reasons.append("source_package_client_request_id_invalid")
        if not cls._timezone_aware_iso_datetime(action.get("package_created_at")):
            blocked_reasons.append("source_package_timestamp_invalid")
        if not all(action.get(flag) is False for flag in _PACKAGE_FALSE_FLAGS):
            blocked_reasons.append("source_package_write_boundary_violated")
        if action.get("ai_project_director_total_loop") != "Partial":
            blocked_reasons.append("source_package_write_boundary_violated")
        if blocked_reasons or package is None:
            return None
        return _ValidatedHumanEscalationPackageEvidence(package=package, action=action)

    def _scan_prior_decisions(
        self,
        *,
        session_id: UUID,
        source_package_message_id: UUID,
        escalation_package_id: UUID | None,
        client_request_id: str,
        blocked_reasons: list[str],
    ) -> bool:
        if self._message_repository is None:
            raise ValueError("human escalation decision message repository is required")
        prior_decision_detected = False
        before_message_id: UUID | None = None
        while True:
            messages, has_more = self._message_repository.list_by_session_id(
                session_id=session_id,
                limit=100,
                before_message_id=before_message_id,
            )
            for message in messages:
                if message.source_detail != (
                    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_SOURCE_DETAIL
                ):
                    continue
                action = self._trusted_prior_decision_action(message)
                if action is None:
                    blocked_reasons.append(
                        "prior_human_escalation_decision_record_invalid"
                    )
                    continue
                if action["source_package_message_id"] == str(
                    source_package_message_id
                ):
                    blocked_reasons.append(
                        "human_escalation_decision_already_recorded"
                    )
                    prior_decision_detected = True
                if action["escalation_package_id"] == str(escalation_package_id):
                    blocked_reasons.append("human_escalation_package_already_decided")
                    prior_decision_detected = True
                if action["client_request_id"] == client_request_id:
                    blocked_reasons.append("human_decision_client_request_id_reused")
                    prior_decision_detected = True
            if not has_more or not messages:
                break
            before_message_id = messages[0].id
        blocked_reasons[:] = self._dedupe(blocked_reasons)
        return prior_decision_detected

    @staticmethod
    def _trusted_prior_decision_action(
        message: ProjectDirectorMessage,
    ) -> dict[str, Any] | None:
        if (
            message.role != ProjectDirectorMessageRole.USER
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent
            != "sandbox_candidate_diff_review_human_escalation_decision"
            or message.requires_confirmation is not False
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
            or len(message.suggested_actions) != 1
        ):
            return None
        action = message.suggested_actions[0]
        if not isinstance(action, dict):
            return None
        if (
            action.get("type")
            != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_ACTION_TYPE
            or action.get("schema_version") != HUMAN_ESCALATION_DECISION_SCHEMA_VERSION
            or action.get("session_id") != str(message.session_id)
            or action.get("source_task_id") != str(message.related_task_id)
        ):
            return None
        domain_fields = (
            "decision_status",
            "decision_id",
            "source_package_message_id",
            "escalation_package_id",
            "source_disposition_message_id",
            "source_review_message_id",
            "source_preflight_message_id",
            "source_diff_message_id",
            "disposition_id",
            "aggregate_evidence_fingerprint",
            "decision_scope",
            "decision_action",
            "actor_type",
            "actor",
            "client_request_id",
            "decision_created_at",
            "decision_expires_at",
            "decision_confirmation_fingerprint",
            "source_package_validated",
            "aggregate_evidence_fingerprint_revalidated",
            "replay_check_completed",
            "prior_decision_detected",
            "blocked_reasons",
            "human_escalation_package_created",
            "human_decision_recorded",
            "decision_consumption_started",
            "decision_consumed",
            "decision_revoked",
            "decision_expired",
            "continuation_started",
            "rework_started",
            "approval_request_created",
            "legacy_approval_decision_created",
            "main_project_file_written",
            "sandbox_file_written",
            "manifest_file_written",
            "diff_file_written",
            "patch_applied",
            "git_write_performed",
            "worktree_created",
            "worker_started",
            "task_created",
            "run_created",
            "gate_allows_write",
            "ai_project_director_total_loop",
        )
        try:
            decision = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult.model_validate(
                {field_name: action.get(field_name) for field_name in domain_fields}
            )
        except ValidationError:
            return None
        if (
            action.get("actor") != decision.actor
            or action.get("client_request_id") != decision.client_request_id
        ):
            return None
        return action

    @staticmethod
    def _decision_confirmation_fingerprint(
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_package_message_id: UUID,
        package: ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult,
        decision_scope: str,
        decision_action: HumanEscalationDecisionAction,
        actor: str,
        client_request_id: str,
        decision_id: UUID,
        decision_created_at: datetime,
        decision_expires_at: datetime,
    ) -> str:
        canonical_payload = {
            "schema_version": HUMAN_ESCALATION_DECISION_SCHEMA_VERSION,
            "session_id": str(session_id),
            "source_task_id": str(source_task_id),
            "source_package_message_id": str(source_package_message_id),
            "escalation_package_id": str(package.escalation_package_id),
            "source_disposition_message_id": str(
                package.source_disposition_message_id
            ),
            "source_review_message_id": str(package.source_review_message_id),
            "source_preflight_message_id": str(package.source_preflight_message_id),
            "source_diff_message_id": str(package.source_diff_message_id),
            "disposition_id": str(package.disposition_id),
            "aggregate_evidence_fingerprint": package.aggregate_evidence_fingerprint,
            "decision_scope": decision_scope,
            "decision_action": decision_action,
            "actor_type": "human",
            "actor": actor,
            "client_request_id": client_request_id,
            "decision_id": str(decision_id),
            "decision_created_at": decision_created_at.isoformat(),
            "decision_expires_at": decision_expires_at.isoformat(),
        }
        canonical_json = json.dumps(
            canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @staticmethod
    def _decision_action(
        *,
        session_id: UUID,
        source_task_id: UUID,
        result: ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult,
    ) -> dict[str, Any]:
        return {
            "type": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_ACTION_TYPE,
            "schema_version": HUMAN_ESCALATION_DECISION_SCHEMA_VERSION,
            "decision_status": result.decision_status,
            "decision_id": str(result.decision_id),
            "session_id": str(session_id),
            "source_task_id": str(source_task_id),
            "source_package_message_id": str(result.source_package_message_id),
            "escalation_package_id": str(result.escalation_package_id),
            "source_disposition_message_id": str(
                result.source_disposition_message_id
            ),
            "source_review_message_id": str(result.source_review_message_id),
            "source_preflight_message_id": str(result.source_preflight_message_id),
            "source_diff_message_id": str(result.source_diff_message_id),
            "disposition_id": str(result.disposition_id),
            "aggregate_evidence_fingerprint": result.aggregate_evidence_fingerprint,
            "decision_scope": result.decision_scope,
            "decision_action": result.decision_action,
            "actor_type": result.actor_type,
            "actor": result.actor,
            "client_request_id": result.client_request_id,
            "decision_created_at": result.decision_created_at.isoformat(),
            "decision_expires_at": result.decision_expires_at.isoformat(),
            "decision_confirmation_fingerprint": (
                result.decision_confirmation_fingerprint
            ),
            "source_package_validated": result.source_package_validated,
            "aggregate_evidence_fingerprint_revalidated": (
                result.aggregate_evidence_fingerprint_revalidated
            ),
            "replay_check_completed": result.replay_check_completed,
            "prior_decision_detected": result.prior_decision_detected,
            "blocked_reasons": list(result.blocked_reasons),
            "human_escalation_package_created": True,
            "human_decision_recorded": True,
            "decision_consumption_started": False,
            "decision_consumed": False,
            "decision_revoked": False,
            "decision_expired": False,
            "continuation_started": False,
            "rework_started": False,
            "approval_request_created": False,
            "legacy_approval_decision_created": False,
            "main_project_file_written": False,
            "sandbox_file_written": False,
            "manifest_file_written": False,
            "diff_file_written": False,
            "patch_applied": False,
            "git_write_performed": False,
            "worktree_created": False,
            "worker_started": False,
            "task_created": False,
            "run_created": False,
            "gate_allows_write": False,
            "ai_project_director_total_loop": "Partial",
        }

    @staticmethod
    def _blocked_result(
        *,
        source_package_message_id: UUID,
        package_evidence: _ValidatedHumanEscalationPackageEvidence | None,
        decision_action: HumanEscalationDecisionAction | None,
        actor: str,
        client_request_id: str,
        decision_expires_at: datetime | None,
        source_package_validated: bool,
        aggregate_fingerprint_revalidated: bool,
        replay_check_completed: bool,
        prior_decision_detected: bool,
        blocked_reasons: list[str],
    ) -> ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult:
        package = package_evidence.package if package_evidence is not None else None
        return ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(
            decision_status="blocked",
            source_package_message_id=source_package_message_id,
            escalation_package_id=(package.escalation_package_id if package else None),
            source_disposition_message_id=(
                package.source_disposition_message_id if package else None
            ),
            source_review_message_id=(package.source_review_message_id if package else None),
            source_preflight_message_id=(
                package.source_preflight_message_id if package else None
            ),
            source_diff_message_id=(package.source_diff_message_id if package else None),
            disposition_id=package.disposition_id if package else None,
            aggregate_evidence_fingerprint=(
                package.aggregate_evidence_fingerprint if package else ""
            ),
            decision_scope="resolve_single_source_review_escalation",
            decision_action=decision_action,
            actor_type="human",
            actor=actor,
            client_request_id=client_request_id,
            decision_expires_at=decision_expires_at,
            source_package_validated=source_package_validated,
            aggregate_evidence_fingerprint_revalidated=(
                aggregate_fingerprint_revalidated
            ),
            replay_check_completed=replay_check_completed,
            prior_decision_detected=prior_decision_detected,
            human_escalation_package_created=(package is not None),
            blocked_reasons=ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionService._dedupe(
                blocked_reasons
            ),
        )

    @staticmethod
    def _timezone_aware_datetime(value: Any) -> bool:
        return (
            isinstance(value, datetime)
            and value.tzinfo is not None
            and value.utcoffset() is not None
        )

    @staticmethod
    def _timezone_aware_iso_datetime(value: Any) -> bool:
        if not isinstance(value, str) or not value:
            return False
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return False
        return parsed.tzinfo is not None and parsed.utcoffset() is not None

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value in seen:
                continue
            result.append(value)
            seen.add(value)
        return result


__all__ = (
    "HUMAN_ESCALATION_DECISION_SCHEMA_VERSION",
    "P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_ACTION_TYPE",
    "P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_SOURCE_DETAIL",
    "ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionService",
    "RecordedSandboxCandidateDiffReviewHumanEscalationDecision",
)
