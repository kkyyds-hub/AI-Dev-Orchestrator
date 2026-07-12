"""Deterministic automated review disposition gate for Project Director P21-D-B."""

from __future__ import annotations

import hashlib
import json
import re
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
from app.domain.project_director_sandbox_candidate_diff_review_disposition import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionResult,
    ReviewDispositionType,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.services.project_director_sandbox_candidate_diff_readonly_review_execution_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_candidate_diff_review_execution_preflight_service import (
    REVIEW_OUTPUT_SCHEMA_VERSION,
)


P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL = (
    "p21_d_sandbox_candidate_diff_review_disposition_computed"
)
P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_ACTION_TYPE = (
    "p21_d_sandbox_candidate_diff_review_disposition_record"
)
REVIEW_DISPOSITION_SCHEMA_VERSION = "p21-d-b.v1"

EVALUATED_TRIGGER_KINDS = ["high_review_risk"]
DEFERRED_TRIGGER_KINDS = [
    "confirmed_scope_or_plan_expansion",
    "protected_surface_change",
    "bounded_rework_budget_exhausted",
    "repeated_non_convergence",
    "trusted_reviewer_conflict",
    "human_controlled_stage_or_milestone_checkpoint",
    "protected_future_transition",
    "explicit_governance_policy_escalation",
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_VALID_REVIEWER_EXECUTORS = ("codex", "claude-code")
_VALID_VERDICTS = (
    "no_blocking_findings",
    "non_blocking_findings",
    "changes_required",
)
_VALID_RISK_LEVELS = ("low", "medium", "high")
_SOURCE_REVIEW_FALSE_FLAGS = (
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
)
_DISPOSITION_FORBIDDEN_ACTIONS = [
    "no_continuation_start",
    "no_rework_start",
    "no_human_escalation_package",
    "no_human_decision",
    "no_patch_apply",
    "no_product_runtime_git_write",
    "no_worker_dispatch",
    "no_task_creation",
    "no_run_creation",
    "no_worktree_creation",
]


@dataclass(frozen=True, slots=True)
class ComputedSandboxCandidateDiffReviewDisposition:
    """P21-D-B disposition result and optional append-only audit message."""

    result: ProjectDirectorSandboxCandidateDiffReviewDispositionResult
    message: ProjectDirectorMessage | None


@dataclass(frozen=True, slots=True)
class RevalidatedPersistedReviewResultFingerprint:
    """Pure revalidation result for one exact persisted P21-C review message."""

    review_result_fingerprint: str
    blocked_reasons: list[str]
    source_preflight_message_id: UUID | None = None
    source_diff_message_id: UUID | None = None
    requested_reviewer_executor: str = ""
    source_diff_sha256: str = ""
    review_prompt_sha256: str = ""
    review_scope_paths: list[str] | None = None
    review_output_schema_version: str = ""
    verdict: str = ""
    risk_level: str = ""


@dataclass(frozen=True, slots=True)
class RevalidatedPersistedReviewDisposition:
    """Pure reconstruction of one exact persisted P21-D disposition message."""

    disposition_message_id: UUID
    disposition_id: UUID | None
    source_review_message_id: UUID | None
    source_preflight_message_id: UUID | None
    source_diff_message_id: UUID | None
    review_result_fingerprint: str
    source_diff_sha256: str
    review_output_schema_version: str
    source_review_verdict: str
    source_review_risk_level: str
    disposition_status: str
    disposition_type: str | None
    disposition_message_created_at: datetime | None
    blocked_reasons: list[str]


@dataclass(frozen=True, slots=True)
class _ValidatedReviewEvidence:
    source_preflight_message_id: UUID
    source_diff_message_id: UUID
    requested_reviewer_executor: str
    source_diff_sha256: str
    review_prompt_sha256: str
    review_scope_paths: list[str]
    review_output_schema_version: str
    raw_output_sha256: str
    output_validation_status: str
    strict_json_valid: bool
    schema_valid: bool
    semantics_valid: bool
    evidence_scope_valid: bool
    review_status: str
    verdict: str
    risk_level: str
    summary: str
    findings: list[dict[str, Any]]
    recommended_next_step: str


class ProjectDirectorSandboxCandidateDiffReviewDispositionService:
    """Validate persisted P21-C review evidence and persist one disposition."""

    def __init__(
        self,
        *,
        session_repository: ProjectDirectorSessionRepository | None = None,
        message_repository: ProjectDirectorMessageRepository | None = None,
    ) -> None:
        self._session_repository = session_repository
        self._message_repository = message_repository

    @classmethod
    def revalidate_persisted_review_result_fingerprint(
        cls,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_review_message_id: UUID,
        source_review_message: ProjectDirectorMessage | None,
    ) -> RevalidatedPersistedReviewResultFingerprint:
        """Rebuild the D-B fingerprint without persistence or disposition work."""

        blocked_reasons: list[str] = []
        review_action = cls._source_review_action(
            source_review_message=source_review_message,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        evidence = cls._validated_review_evidence(
            review_action,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        stable_blocked_reasons = cls._dedupe(blocked_reasons)
        if stable_blocked_reasons or evidence is None:
            return RevalidatedPersistedReviewResultFingerprint(
                review_result_fingerprint="",
                blocked_reasons=stable_blocked_reasons,
            )

        return RevalidatedPersistedReviewResultFingerprint(
            review_result_fingerprint=cls._review_result_fingerprint(
                session_id=session_id,
                source_task_id=source_task_id,
                source_review_message_id=source_review_message_id,
                evidence=evidence,
            ),
            blocked_reasons=[],
            source_preflight_message_id=evidence.source_preflight_message_id,
            source_diff_message_id=evidence.source_diff_message_id,
            requested_reviewer_executor=evidence.requested_reviewer_executor,
            source_diff_sha256=evidence.source_diff_sha256,
            review_prompt_sha256=evidence.review_prompt_sha256,
            review_scope_paths=list(evidence.review_scope_paths),
            review_output_schema_version=evidence.review_output_schema_version,
            verdict=evidence.verdict,
            risk_level=evidence.risk_level,
        )

    def revalidate_persisted_review_disposition(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        source_task_id: UUID,
        source_disposition_message_id: UUID,
    ) -> RevalidatedPersistedReviewDisposition:
        """Rebuild one exact P21-D record without append, flush, or commit."""

        blocked_reasons: list[str] = []
        if self._message_repository is None:
            blocked_reasons.append("review_disposition_repository_missing")
            message = None
        else:
            message = self._message_repository.get_by_id(
                source_disposition_message_id
            )
        if message is None:
            blocked_reasons.append("review_disposition_message_missing")
            return RevalidatedPersistedReviewDisposition(
                disposition_message_id=source_disposition_message_id,
                disposition_id=None,
                source_review_message_id=None,
                source_preflight_message_id=None,
                source_diff_message_id=None,
                review_result_fingerprint="",
                source_diff_sha256="",
                review_output_schema_version="",
                source_review_verdict="",
                source_review_risk_level="",
                disposition_status="",
                disposition_type=None,
                disposition_message_created_at=None,
                blocked_reasons=self._dedupe(blocked_reasons),
            )

        if (
            message.id != source_disposition_message_id
            or message.session_id != session_id
            or message.related_project_id != project_id
            or message.related_task_id != source_task_id
            or message.role != ProjectDirectorMessageRole.ASSISTANT
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent != "sandbox_candidate_diff_review_disposition"
            or message.source_detail
            != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL
            or message.requires_confirmation
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
            or message.forbidden_actions_detected != _DISPOSITION_FORBIDDEN_ACTIONS
        ):
            blocked_reasons.append("review_disposition_message_invalid")

        action = self._single_action(message)
        if (
            action is None
            or action.get("type")
            != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_ACTION_TYPE
            or action.get("schema_version") != REVIEW_DISPOSITION_SCHEMA_VERSION
            or action.get("session_id") != str(session_id)
            or action.get("source_task_id") != str(source_task_id)
        ):
            blocked_reasons.append("review_disposition_action_invalid")
            action = action or {}

        disposition_id = self._uuid_from_action(action, "disposition_id")
        source_review_message_id = self._uuid_from_action(
            action, "source_review_message_id"
        )
        source_preflight_message_id = self._uuid_from_action(
            action, "source_preflight_message_id"
        )
        source_diff_message_id = self._uuid_from_action(
            action, "source_diff_message_id"
        )
        if any(
            value is None
            for value in (
                disposition_id,
                source_review_message_id,
                source_preflight_message_id,
                source_diff_message_id,
            )
        ):
            blocked_reasons.append("review_disposition_binding_invalid")

        review_result_fingerprint = action.get("review_result_fingerprint")
        source_diff_sha256 = action.get("source_diff_sha256")
        if not self._is_sha256(review_result_fingerprint):
            blocked_reasons.append("review_disposition_fingerprint_invalid")
            review_result_fingerprint = ""
        if not self._is_sha256(source_diff_sha256):
            blocked_reasons.append("review_disposition_diff_invalid")
            source_diff_sha256 = ""

        disposition_created_at: datetime | None = None
        raw_created_at = action.get("disposition_created_at")
        if isinstance(raw_created_at, str):
            try:
                disposition_created_at = datetime.fromisoformat(
                    raw_created_at.replace("Z", "+00:00")
                ).astimezone(timezone.utc)
            except ValueError:
                disposition_created_at = None
        if (
            disposition_created_at is None
            or disposition_created_at != message.created_at
            or action.get("actor") != "system"
            or action.get("client_request_id") is not None
            or action.get("ai_project_director_total_loop") != "Partial"
        ):
            blocked_reasons.append("review_disposition_metadata_invalid")

        try:
            result = (
                ProjectDirectorSandboxCandidateDiffReviewDispositionResult.model_validate(
                    {
                        field_name: action.get(field_name)
                        for field_name in ProjectDirectorSandboxCandidateDiffReviewDispositionResult.model_fields
                    }
                )
            )
        except (ValidationError, ValueError, TypeError):
            result = None
            blocked_reasons.append("review_disposition_result_invalid")

        disposition_status = action.get("disposition_status")
        disposition_type = action.get("disposition_type")
        if (
            result is None
            or result.disposition_status != disposition_status
            or result.disposition_type != disposition_type
            or result.source_review_message_id != source_review_message_id
            or result.review_result_fingerprint != review_result_fingerprint
        ):
            blocked_reasons.append("review_disposition_result_invalid")

        return RevalidatedPersistedReviewDisposition(
            disposition_message_id=source_disposition_message_id,
            disposition_id=disposition_id,
            source_review_message_id=source_review_message_id,
            source_preflight_message_id=source_preflight_message_id,
            source_diff_message_id=source_diff_message_id,
            review_result_fingerprint=review_result_fingerprint,
            source_diff_sha256=source_diff_sha256,
            review_output_schema_version=str(
                action.get("review_output_schema_version") or ""
            ),
            source_review_verdict=str(action.get("source_review_verdict") or ""),
            source_review_risk_level=str(
                action.get("source_review_risk_level") or ""
            ),
            disposition_status=str(disposition_status or ""),
            disposition_type=(
                str(disposition_type) if disposition_type is not None else None
            ),
            disposition_message_created_at=disposition_created_at,
            blocked_reasons=self._dedupe(blocked_reasons),
        )

    def compute_candidate_diff_review_disposition(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
    ) -> ComputedSandboxCandidateDiffReviewDisposition:
        """Compute from exact persisted P21-C evidence and append one audit record."""

        if self._session_repository is None or self._message_repository is None:
            raise ValueError("review disposition repositories are required")

        with self._message_repository.sqlite_immediate_transaction():
            return self._compute_candidate_diff_review_disposition(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
            )

    def _compute_candidate_diff_review_disposition(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
    ) -> ComputedSandboxCandidateDiffReviewDisposition:
        """在同一 immediate transaction 内完成校验、防重与创建。"""

        blocked_reasons: list[str] = []
        session_obj = self._session_repository.get_by_id(session_id)
        source_review_message = self._message_repository.get_by_id(
            source_message_id
        )

        if session_obj is None:
            blocked_reasons.append("session_missing")

        review_action = self._source_review_action(
            source_review_message=source_review_message,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        evidence = self._validated_review_evidence(
            review_action,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )

        blocked_reasons = self._dedupe(blocked_reasons)
        if blocked_reasons or evidence is None or session_obj is None:
            return ComputedSandboxCandidateDiffReviewDisposition(
                result=self._blocked_result(
                    source_review_message_id=source_message_id,
                    blocked_reasons=blocked_reasons,
                ),
                message=None,
            )

        review_result_fingerprint = self._review_result_fingerprint(
            session_id=session_id,
            source_task_id=source_task_id,
            source_review_message_id=source_message_id,
            evidence=evidence,
        )
        disposition_type, disposition_reason, escalation_triggers = (
            self._calculate_disposition(evidence)
        )
        replay = self._existing_disposition_for_exact_review(
            session_id=session_id,
            source_task_id=source_task_id,
            source_review_message_id=source_message_id,
            review_result_fingerprint=review_result_fingerprint,
            evidence=evidence,
            disposition_type=disposition_type,
            disposition_reason=disposition_reason,
            escalation_triggers=escalation_triggers,
        )
        if replay is not None:
            return replay

        result = ProjectDirectorSandboxCandidateDiffReviewDispositionResult(
            disposition_status="computed",
            disposition_type=disposition_type,
            source_review_message_id=source_message_id,
            review_result_fingerprint=review_result_fingerprint,
            disposition_reason=disposition_reason,
            escalation_triggers=escalation_triggers,
            evaluated_trigger_kinds=list(EVALUATED_TRIGGER_KINDS),
            deferred_trigger_kinds=list(DEFERRED_TRIGGER_KINDS),
        )

        disposition_id = uuid4()
        disposition_created_at = datetime.now(timezone.utc)
        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "Automated review disposition was computed from persisted, "
                    "validated P21-C review evidence. This record does not start "
                    "continuation or rework, create a human escalation package, "
                    "apply a patch, or authorize Git writes. AI Project Director "
                    "total loop remains Partial."
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="sandbox_candidate_diff_review_disposition",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=(
                    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL
                ),
                suggested_actions=[
                    self._disposition_action(
                        session_id=session_id,
                        source_task_id=source_task_id,
                        source_review_message_id=source_message_id,
                        evidence=evidence,
                        result=result,
                        disposition_id=disposition_id,
                        disposition_created_at=disposition_created_at,
                    )
                ],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                forbidden_actions_detected=[
                    "no_continuation_start",
                    "no_rework_start",
                    "no_human_escalation_package",
                    "no_human_decision",
                    "no_patch_apply",
                    "no_product_runtime_git_write",
                    "no_worker_dispatch",
                    "no_task_creation",
                    "no_run_creation",
                    "no_worktree_creation",
                ],
                created_at=disposition_created_at,
            )
        )
        return ComputedSandboxCandidateDiffReviewDisposition(
            result=result,
            message=message,
        )

    def _existing_disposition_for_exact_review(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_review_message_id: UUID,
        review_result_fingerprint: str,
        evidence: _ValidatedReviewEvidence,
        disposition_type: ReviewDispositionType,
        disposition_reason: str,
        escalation_triggers: list[str],
    ) -> ComputedSandboxCandidateDiffReviewDisposition | None:
        """分页扫描并采用唯一合法的同链 D-B disposition。"""

        matched: list[
            tuple[
                ProjectDirectorSandboxCandidateDiffReviewDispositionResult,
                ProjectDirectorMessage,
            ]
        ] = []
        conflict_detected = False
        before_message_id: UUID | None = None

        while True:
            messages, has_more = self._message_repository.list_by_session_id(
                session_id=session_id,
                limit=100,
                before_message_id=before_message_id,
            )
            for message in messages:
                if (
                    message.source_detail
                    != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL
                ):
                    continue
                action = self._single_action(message)
                if action is None:
                    if message.related_task_id == source_task_id:
                        conflict_detected = True
                    continue
                action_review_message_id = action.get("source_review_message_id")
                if action_review_message_id is None:
                    if message.related_task_id == source_task_id:
                        conflict_detected = True
                    continue
                if action_review_message_id != str(source_review_message_id):
                    continue
                result = self._trusted_replayed_disposition(
                    message=message,
                    action=action,
                    session_id=session_id,
                    source_task_id=source_task_id,
                    source_review_message_id=source_review_message_id,
                    review_result_fingerprint=review_result_fingerprint,
                    evidence=evidence,
                    disposition_type=disposition_type,
                    disposition_reason=disposition_reason,
                    escalation_triggers=escalation_triggers,
                )
                if result is None:
                    conflict_detected = True
                else:
                    matched.append((result, message))
            if not has_more or not messages:
                break
            before_message_id = messages[0].id

        if conflict_detected or len(matched) > 1:
            return ComputedSandboxCandidateDiffReviewDisposition(
                result=self._blocked_result(
                    source_review_message_id=source_review_message_id,
                    blocked_reasons=["review_disposition_replay_conflict"],
                ),
                message=None,
            )
        if matched:
            result, message = matched[0]
            return ComputedSandboxCandidateDiffReviewDisposition(
                result=result,
                message=message,
            )
        return None

    @staticmethod
    def _single_action(message: ProjectDirectorMessage) -> dict[str, Any] | None:
        if len(message.suggested_actions) != 1:
            return None
        action = message.suggested_actions[0]
        return action if isinstance(action, dict) else None

    @staticmethod
    def _trusted_replayed_disposition(
        *,
        message: ProjectDirectorMessage,
        action: dict[str, Any],
        session_id: UUID,
        source_task_id: UUID,
        source_review_message_id: UUID,
        review_result_fingerprint: str,
        evidence: _ValidatedReviewEvidence,
        disposition_type: ReviewDispositionType,
        disposition_reason: str,
        escalation_triggers: list[str],
    ) -> ProjectDirectorSandboxCandidateDiffReviewDispositionResult | None:
        """严格重建 D-B domain，任何绑定异常均视为 replay conflict。"""

        if (
            message.session_id != session_id
            or message.role != ProjectDirectorMessageRole.ASSISTANT
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent != "sandbox_candidate_diff_review_disposition"
            or message.related_task_id != source_task_id
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
            or action.get("type")
            != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_ACTION_TYPE
            or action.get("schema_version") != REVIEW_DISPOSITION_SCHEMA_VERSION
            or action.get("session_id") != str(session_id)
            or action.get("source_task_id") != str(source_task_id)
            or action.get("source_review_message_id")
            != str(source_review_message_id)
            or action.get("review_result_fingerprint")
            != review_result_fingerprint
            or action.get("source_preflight_message_id")
            != str(evidence.source_preflight_message_id)
            or action.get("source_diff_message_id")
            != str(evidence.source_diff_message_id)
            or action.get("requested_reviewer_executor")
            != evidence.requested_reviewer_executor
            or action.get("source_diff_sha256") != evidence.source_diff_sha256
            or action.get("review_prompt_sha256") != evidence.review_prompt_sha256
            or action.get("review_scope_paths") != evidence.review_scope_paths
            or action.get("review_output_schema_version")
            != evidence.review_output_schema_version
            or action.get("source_review_verdict") != evidence.verdict
            or action.get("source_review_risk_level") != evidence.risk_level
        ):
            return None
        try:
            UUID(str(action.get("disposition_id")))
            result = ProjectDirectorSandboxCandidateDiffReviewDispositionResult.model_validate(
                {
                    field_name: action.get(field_name)
                    for field_name in ProjectDirectorSandboxCandidateDiffReviewDispositionResult.model_fields
                }
            )
        except (ValidationError, ValueError, TypeError):
            return None
        if (
            result.disposition_status != "computed"
            or result.source_review_message_id != source_review_message_id
            or result.review_result_fingerprint != review_result_fingerprint
            or result.disposition_type != disposition_type
            or result.disposition_reason != disposition_reason
            or result.escalation_triggers != escalation_triggers
            or result.evaluated_trigger_kinds != EVALUATED_TRIGGER_KINDS
            or result.deferred_trigger_kinds != DEFERRED_TRIGGER_KINDS
        ):
            return None
        return result

    @staticmethod
    def _source_review_action(
        *,
        source_review_message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> dict[str, Any] | None:
        if source_review_message is None:
            blocked_reasons.append("source_review_message_missing")
            return None
        if source_review_message.session_id != session_id:
            blocked_reasons.append("source_review_message_session_mismatch")
        if source_review_message.related_task_id != source_task_id:
            blocked_reasons.append("source_review_message_task_mismatch")
        if (
            source_review_message.source_detail
            != P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL
        ):
            blocked_reasons.append(
                "source_message_is_not_p21_c_readonly_review_execution"
            )
        if not source_review_message.suggested_actions:
            blocked_reasons.append("p21_c_readonly_review_execution_record_missing")
            return None
        first_action = source_review_message.suggested_actions[0]
        if (
            not isinstance(first_action, dict)
            or first_action.get("type")
            != P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE
        ):
            blocked_reasons.append("p21_c_readonly_review_execution_record_missing")
            return None
        return first_action

    @classmethod
    def _validated_review_evidence(
        cls,
        action: dict[str, Any] | None,
        *,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> _ValidatedReviewEvidence | None:
        if action is None:
            return None

        if action.get("session_id") != str(session_id):
            blocked_reasons.append("source_review_action_session_mismatch")
        if action.get("source_task_id") != str(source_task_id):
            blocked_reasons.append("source_review_action_task_mismatch")

        source_preflight_message_id = cls._uuid_from_action(
            action,
            "source_preflight_message_id",
        )
        source_diff_message_id = cls._uuid_from_action(
            action,
            "source_diff_message_id",
        )
        if source_preflight_message_id is None or source_diff_message_id is None:
            blocked_reasons.append("source_review_binding_invalid")

        requested_reviewer_executor = action.get("requested_reviewer_executor")
        if requested_reviewer_executor not in _VALID_REVIEWER_EXECUTORS:
            blocked_reasons.append("requested_reviewer_executor_invalid")

        source_diff_sha256 = action.get("source_diff_sha256")
        if not cls._is_sha256(source_diff_sha256):
            blocked_reasons.append("source_diff_sha256_invalid")

        review_prompt_sha256 = action.get("review_prompt_sha256")
        if not cls._is_sha256(review_prompt_sha256):
            blocked_reasons.append("review_prompt_sha256_invalid")

        review_scope_paths = cls._review_scope_paths(
            action,
            blocked_reasons=blocked_reasons,
        )

        review_output_schema_version = action.get("review_output_schema_version")
        if review_output_schema_version != REVIEW_OUTPUT_SCHEMA_VERSION:
            blocked_reasons.append("review_output_schema_version_mismatch")

        raw_output_sha256 = action.get("raw_output_sha256")
        source_review_validated = (
            action.get("adapter_status") == "validated_output"
            and action.get("output_validation_status") == "validated"
            and action.get("strict_json_valid") is True
            and action.get("schema_valid") is True
            and action.get("semantics_valid") is True
            and action.get("evidence_scope_valid") is True
            and action.get("review_status") == "reviewed"
            and cls._is_sha256(raw_output_sha256)
            and isinstance(action.get("summary"), str)
            and isinstance(action.get("recommended_next_step"), str)
        )
        if not source_review_validated:
            blocked_reasons.append("source_review_not_validated")

        verdict = action.get("verdict")
        if verdict not in _VALID_VERDICTS:
            blocked_reasons.append("source_review_verdict_invalid")

        risk_level = action.get("risk_level")
        if risk_level not in _VALID_RISK_LEVELS:
            blocked_reasons.append("source_review_risk_level_invalid")

        findings = cls._findings(action, blocked_reasons=blocked_reasons)

        if not all(action.get(flag) is False for flag in _SOURCE_REVIEW_FALSE_FLAGS):
            blocked_reasons.append("source_review_write_boundary_violated")
        if action.get("ai_project_director_total_loop") != "Partial":
            blocked_reasons.append("source_review_write_boundary_violated")

        if blocked_reasons:
            return None
        if source_preflight_message_id is None or source_diff_message_id is None:
            return None
        return _ValidatedReviewEvidence(
            source_preflight_message_id=source_preflight_message_id,
            source_diff_message_id=source_diff_message_id,
            requested_reviewer_executor=requested_reviewer_executor,
            source_diff_sha256=source_diff_sha256,
            review_prompt_sha256=review_prompt_sha256,
            review_scope_paths=review_scope_paths,
            review_output_schema_version=review_output_schema_version,
            raw_output_sha256=raw_output_sha256,
            output_validation_status=action["output_validation_status"],
            strict_json_valid=action["strict_json_valid"],
            schema_valid=action["schema_valid"],
            semantics_valid=action["semantics_valid"],
            evidence_scope_valid=action["evidence_scope_valid"],
            review_status=action["review_status"],
            verdict=verdict,
            risk_level=risk_level,
            summary=action["summary"],
            findings=findings,
            recommended_next_step=action["recommended_next_step"],
        )

    @staticmethod
    def _review_result_fingerprint(
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_review_message_id: UUID,
        evidence: _ValidatedReviewEvidence,
    ) -> str:
        canonical_payload = {
            "session_id": str(session_id),
            "source_task_id": str(source_task_id),
            "source_review_message_id": str(source_review_message_id),
            "source_preflight_message_id": str(
                evidence.source_preflight_message_id
            ),
            "source_diff_message_id": str(evidence.source_diff_message_id),
            "requested_reviewer_executor": evidence.requested_reviewer_executor,
            "source_diff_sha256": evidence.source_diff_sha256,
            "review_prompt_sha256": evidence.review_prompt_sha256,
            "review_scope_paths": list(evidence.review_scope_paths),
            "review_output_schema_version": evidence.review_output_schema_version,
            "raw_output_sha256": evidence.raw_output_sha256,
            "output_validation_status": evidence.output_validation_status,
            "strict_json_valid": evidence.strict_json_valid,
            "schema_valid": evidence.schema_valid,
            "semantics_valid": evidence.semantics_valid,
            "evidence_scope_valid": evidence.evidence_scope_valid,
            "review_status": evidence.review_status,
            "verdict": evidence.verdict,
            "risk_level": evidence.risk_level,
            "summary": evidence.summary,
            "findings": evidence.findings,
            "recommended_next_step": evidence.recommended_next_step,
        }
        canonical_json = json.dumps(
            canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @staticmethod
    def _calculate_disposition(
        evidence: _ValidatedReviewEvidence,
    ) -> tuple[ReviewDispositionType, str, list[str]]:
        high_review_risk = evidence.risk_level == "high" or any(
            finding.get("severity") == "high" for finding in evidence.findings
        )
        if high_review_risk:
            return (
                "ESCALATE_TO_HUMAN",
                "high_review_risk_requires_human_escalation",
                ["high_review_risk"],
            )
        if evidence.verdict == "changes_required":
            return (
                "AUTO_REWORK",
                "review_changes_required_within_automatic_rework_boundary",
                [],
            )
        if evidence.verdict == "no_blocking_findings":
            return (
                "AUTO_CONTINUE",
                "review_has_no_blocking_findings",
                [],
            )
        return (
            "AUTO_CONTINUE",
            "review_has_only_non_blocking_findings",
            [],
        )

    @staticmethod
    def _disposition_action(
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_review_message_id: UUID,
        evidence: _ValidatedReviewEvidence,
        result: ProjectDirectorSandboxCandidateDiffReviewDispositionResult,
        disposition_id: UUID,
        disposition_created_at: datetime,
    ) -> dict[str, Any]:
        return {
            "type": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_ACTION_TYPE,
            "schema_version": REVIEW_DISPOSITION_SCHEMA_VERSION,
            "disposition_status": result.disposition_status,
            "session_id": str(session_id),
            "source_task_id": str(source_task_id),
            "source_review_message_id": str(source_review_message_id),
            "source_preflight_message_id": str(
                evidence.source_preflight_message_id
            ),
            "source_diff_message_id": str(evidence.source_diff_message_id),
            "requested_reviewer_executor": evidence.requested_reviewer_executor,
            "source_diff_sha256": evidence.source_diff_sha256,
            "review_prompt_sha256": evidence.review_prompt_sha256,
            "review_scope_paths": list(evidence.review_scope_paths),
            "review_output_schema_version": evidence.review_output_schema_version,
            "review_result_fingerprint": result.review_result_fingerprint,
            "disposition_id": str(disposition_id),
            "disposition_type": result.disposition_type,
            "disposition_reason": result.disposition_reason,
            "source_review_verdict": evidence.verdict,
            "source_review_risk_level": evidence.risk_level,
            "escalation_triggers": list(result.escalation_triggers),
            "evaluated_trigger_kinds": list(result.evaluated_trigger_kinds),
            "deferred_trigger_kinds": list(result.deferred_trigger_kinds),
            "blocked_reasons": list(result.blocked_reasons),
            "actor": "system",
            "client_request_id": None,
            "disposition_created_at": disposition_created_at.isoformat(),
            "continuation_started": False,
            "rework_started": False,
            "human_escalation_package_created": False,
            "human_decision_recorded": False,
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
        source_review_message_id: UUID,
        blocked_reasons: list[str],
    ) -> ProjectDirectorSandboxCandidateDiffReviewDispositionResult:
        return ProjectDirectorSandboxCandidateDiffReviewDispositionResult(
            disposition_status="blocked",
            source_review_message_id=source_review_message_id,
            deferred_trigger_kinds=list(DEFERRED_TRIGGER_KINDS),
            blocked_reasons=ProjectDirectorSandboxCandidateDiffReviewDispositionService._dedupe(
                blocked_reasons
            ),
        )

    @staticmethod
    def _review_scope_paths(
        action: dict[str, Any],
        *,
        blocked_reasons: list[str],
    ) -> list[str]:
        raw_paths = action.get("review_scope_paths")
        if not isinstance(raw_paths, list) or not raw_paths:
            blocked_reasons.append("review_scope_paths_invalid")
            return []
        paths: list[str] = []
        seen_paths: set[str] = set()
        invalid = False
        for raw_path in raw_paths:
            if not isinstance(raw_path, str) or not raw_path:
                invalid = True
                continue
            if raw_path in seen_paths:
                invalid = True
                continue
            paths.append(raw_path)
            seen_paths.add(raw_path)
        if invalid:
            blocked_reasons.append("review_scope_paths_invalid")
        return paths

    @staticmethod
    def _findings(
        action: dict[str, Any],
        *,
        blocked_reasons: list[str],
    ) -> list[dict[str, Any]]:
        raw_findings = action.get("findings")
        if not isinstance(raw_findings, list):
            blocked_reasons.append("source_review_findings_invalid")
            return []
        invalid = False
        findings: list[dict[str, Any]] = []
        for raw_finding in raw_findings:
            if not isinstance(raw_finding, dict):
                invalid = True
                continue
            if (
                "severity" in raw_finding
                and raw_finding.get("severity") not in _VALID_RISK_LEVELS
            ):
                invalid = True
            findings.append(raw_finding)
        if invalid:
            blocked_reasons.append("source_review_findings_invalid")
        return findings

    @staticmethod
    def _uuid_from_action(action: dict[str, Any], key: str) -> UUID | None:
        raw_value = action.get(key)
        if not isinstance(raw_value, str) or not raw_value:
            return None
        try:
            return UUID(raw_value)
        except ValueError:
            return None

    @staticmethod
    def _is_sha256(value: Any) -> bool:
        return isinstance(value, str) and _LOWER_HEX_SHA256.match(value) is not None

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
    "ComputedSandboxCandidateDiffReviewDisposition",
    "DEFERRED_TRIGGER_KINDS",
    "EVALUATED_TRIGGER_KINDS",
    "P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_ACTION_TYPE",
    "P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL",
    "ProjectDirectorSandboxCandidateDiffReviewDispositionService",
    "RevalidatedPersistedReviewDisposition",
    "RevalidatedPersistedReviewResultFingerprint",
    "REVIEW_DISPOSITION_SCHEMA_VERSION",
)
