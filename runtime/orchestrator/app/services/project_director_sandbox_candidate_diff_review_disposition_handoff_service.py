"""Append-only disposition handoff gate for Project Director P21-D-C3."""

from __future__ import annotations

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
from app.domain.project_director_sandbox_candidate_diff_review_disposition_consumption import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult,
)
from app.domain.project_director_sandbox_candidate_diff_review_disposition_handoff import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_sandbox_candidate_diff_review_disposition_consumption_service import (
    DISPOSITION_CONSUMPTION_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMED_SOURCE_DETAIL,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_ACTION_TYPE,
)


P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_SOURCE_DETAIL = (
    "p21_d_sandbox_candidate_diff_review_disposition_handoff_prepared"
)
P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_ACTION_TYPE = (
    "p21_d_sandbox_candidate_diff_review_disposition_handoff_record"
)
DISPOSITION_HANDOFF_SCHEMA_VERSION = "p21-d-c3.v1"

MAX_AUTOMATIC_REWORK_HANDOFFS_PER_TASK = 1

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_VALID_REVIEW_VERDICTS = (
    "no_blocking_findings",
    "non_blocking_findings",
    "changes_required",
)
_VALID_REVIEW_RISK_LEVELS = ("low", "medium", "high")
_C2_FALSE_FLAGS = (
    "continuation_started",
    "rework_started",
    "human_escalation_package_created",
    "human_decision_recorded",
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
class PreparedSandboxCandidateDiffReviewDispositionHandoff:
    """P21-D-C3 result and optional append-only handoff message."""

    result: ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult
    message: ProjectDirectorMessage | None


@dataclass(frozen=True, slots=True)
class _ValidatedC2Evidence:
    consumption: ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult
    disposition_reason: str
    review_prompt_sha256: str
    review_output_schema_version: str
    source_review_verdict: str
    source_review_risk_level: str


class ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService:
    """Prepare one bounded handoff without starting continuation or rework."""

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

    def prepare_candidate_diff_review_disposition_handoff(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
    ) -> PreparedSandboxCandidateDiffReviewDispositionHandoff:
        """Validate one exact C2 consumption and append its handoff record."""

        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("disposition handoff dependencies are required")

        with self._message_repository.sqlite_immediate_transaction():
            return self._prepare_candidate_diff_review_disposition_handoff(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
            )

    def _prepare_candidate_diff_review_disposition_handoff(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
    ) -> PreparedSandboxCandidateDiffReviewDispositionHandoff:
        blocked_reasons: list[str] = []
        evidence: _ValidatedC2Evidence | None = None
        replay_check_completed = False
        prior_handoff_detected = False
        prior_rework_handoff_count = 0
        bounded_rework_budget_exhausted = False
        rework_non_convergence_detected = False

        def blocked_result() -> PreparedSandboxCandidateDiffReviewDispositionHandoff:
            return PreparedSandboxCandidateDiffReviewDispositionHandoff(
                result=self._blocked_result(
                    source_consumption_message_id=source_message_id,
                    evidence=evidence,
                    replay_check_completed=replay_check_completed,
                    prior_handoff_detected=prior_handoff_detected,
                    prior_rework_handoff_count=prior_rework_handoff_count,
                    bounded_rework_budget_exhausted=(
                        bounded_rework_budget_exhausted
                    ),
                    rework_non_convergence_detected=(
                        rework_non_convergence_detected
                    ),
                    blocked_reasons=blocked_reasons,
                ),
                message=None,
            )

        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            blocked_reasons.append("session_missing")

        source_task = self._task_repository.get_by_id(source_task_id)
        if source_task is None:
            blocked_reasons.append("source_task_missing")

        source_message = self._message_repository.get_by_id(source_message_id)
        source_action = self._source_c2_action(
            source_message=source_message,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        evidence = self._validated_c2_evidence(
            source_action,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        blocked_reasons = self._dedupe(blocked_reasons)
        if (
            blocked_reasons
            or evidence is None
            or session_obj is None
            or source_task is None
        ):
            return blocked_result()

        (
            prior_handoff_detected,
            prior_rework_handoff_count,
        ) = self._scan_prior_handoffs(
            session_id=session_id,
            source_task_id=source_task_id,
            source_consumption_message_id=source_message_id,
        )
        replay_check_completed = True
        if prior_handoff_detected:
            blocked_reasons.append("handoff_already_prepared")
            return blocked_result()

        if (
            evidence.consumption.disposition_type == "AUTO_REWORK"
            and prior_rework_handoff_count
            >= MAX_AUTOMATIC_REWORK_HANDOFFS_PER_TASK
        ):
            bounded_rework_budget_exhausted = True
            rework_non_convergence_detected = True
            blocked_reasons.extend(
                [
                    "bounded_rework_budget_exhausted",
                    "rework_non_convergence",
                ]
            )
            return blocked_result()

        prepared_at = datetime.now(timezone.utc)
        result = ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(
            handoff_status="prepared",
            handoff_id=uuid4(),
            source_consumption_message_id=source_message_id,
            source_consumption_id=evidence.consumption.consumption_id,
            source_consumption_preflight_message_id=(
                evidence.consumption.source_consumption_preflight_message_id
            ),
            source_disposition_message_id=(
                evidence.consumption.source_disposition_message_id
            ),
            source_review_message_id=evidence.consumption.source_review_message_id,
            source_diff_message_id=evidence.consumption.source_diff_message_id,
            disposition_id=evidence.consumption.disposition_id,
            disposition_type=evidence.consumption.disposition_type,
            disposition_reason=evidence.disposition_reason,
            handoff_kind=(
                "automatic_continuation"
                if evidence.consumption.disposition_type == "AUTO_CONTINUE"
                else "bounded_automatic_rework"
            ),
            review_result_fingerprint=(
                evidence.consumption.review_result_fingerprint
            ),
            revalidated_review_result_fingerprint=(
                evidence.consumption.revalidated_review_result_fingerprint
            ),
            reviewed_diff_sha256=evidence.consumption.reviewed_diff_sha256,
            persisted_source_diff_sha256=(
                evidence.consumption.persisted_source_diff_sha256
            ),
            current_diff_sha256=evidence.consumption.current_diff_sha256,
            review_prompt_sha256=evidence.review_prompt_sha256,
            reviewed_scope_paths=list(evidence.consumption.reviewed_scope_paths),
            persisted_source_scope_paths=list(
                evidence.consumption.persisted_source_scope_paths
            ),
            current_scope_paths=list(evidence.consumption.current_scope_paths),
            workspace_path=evidence.consumption.workspace_path,
            workspace_path_within_root=True,
            source_consumption_validated=True,
            replay_check_completed=True,
            prior_handoff_detected=False,
            prior_rework_handoff_count=prior_rework_handoff_count,
            rework_attempt_number=(
                1 if evidence.consumption.disposition_type == "AUTO_REWORK" else 0
            ),
            rework_attempt_limit=MAX_AUTOMATIC_REWORK_HANDOFFS_PER_TASK,
            continuation_handoff_prepared=(
                evidence.consumption.disposition_type == "AUTO_CONTINUE"
            ),
            rework_handoff_prepared=(
                evidence.consumption.disposition_type == "AUTO_REWORK"
            ),
            prepared_at=prepared_at,
        )
        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "A bounded disposition handoff was prepared only. No "
                    "continuation or rework execution was started, no Task, Run, "
                    "Worker, or worktree was created, no file was written, no "
                    "patch was applied, and no Git write was performed. AI Project "
                    "Director total loop remains Partial."
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="sandbox_candidate_diff_review_disposition_handoff",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=(
                    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_SOURCE_DETAIL
                ),
                suggested_actions=[
                    self._handoff_action(
                        session_id=session_id,
                        source_task_id=source_task_id,
                        evidence=evidence,
                        result=result,
                    )
                ],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                forbidden_actions_detected=[
                    "no_continuation_start",
                    "no_rework_start",
                    "no_human_escalation_package",
                    "no_human_decision",
                    "no_workspace_write",
                    "no_main_project_file_write",
                    "no_manifest_write",
                    "no_diff_file_write",
                    "no_patch_apply",
                    "no_product_runtime_git_write",
                    "no_worker_dispatch",
                    "no_task_creation",
                    "no_run_creation",
                    "no_worktree_creation",
                ],
                created_at=prepared_at,
            )
        )
        return PreparedSandboxCandidateDiffReviewDispositionHandoff(
            result=result,
            message=message,
        )

    @staticmethod
    def _source_c2_action(
        *,
        source_message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> dict[str, Any] | None:
        if source_message is None:
            blocked_reasons.append("source_consumption_message_missing")
            return None
        if source_message.session_id != session_id:
            blocked_reasons.append("source_consumption_message_session_mismatch")
        if source_message.related_task_id != source_task_id:
            blocked_reasons.append("source_consumption_message_task_mismatch")
        if (
            source_message.role != ProjectDirectorMessageRole.ASSISTANT
            or source_message.source != ProjectDirectorMessageSource.SYSTEM
        ):
            blocked_reasons.append("source_consumption_message_source_invalid")
        if source_message.requires_confirmation is not False:
            blocked_reasons.append("source_consumption_confirmation_contract_invalid")
        if source_message.risk_level != ProjectDirectorMessageRiskLevel.HIGH:
            blocked_reasons.append("source_consumption_message_risk_invalid")
        if (
            source_message.source_detail
            != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMED_SOURCE_DETAIL
        ):
            blocked_reasons.append("source_message_is_not_p21_d_c2_consumption")
        if len(source_message.suggested_actions) != 1:
            blocked_reasons.append("p21_d_c2_consumption_record_missing")
            return None
        first_action = source_message.suggested_actions[0]
        if (
            not isinstance(first_action, dict)
            or first_action.get("type")
            != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_ACTION_TYPE
        ):
            blocked_reasons.append("p21_d_c2_consumption_record_missing")
            return None
        return first_action

    @classmethod
    def _validated_c2_evidence(
        cls,
        action: dict[str, Any] | None,
        *,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> _ValidatedC2Evidence | None:
        if action is None:
            return None
        if action.get("schema_version") != DISPOSITION_CONSUMPTION_SCHEMA_VERSION:
            blocked_reasons.append("source_consumption_schema_version_mismatch")
        if (
            action.get("session_id") != str(session_id)
            or action.get("source_task_id") != str(source_task_id)
        ):
            blocked_reasons.append("source_consumption_binding_invalid")

        uuid_fields = (
            "consumption_id",
            "source_consumption_preflight_message_id",
            "source_disposition_message_id",
            "source_review_message_id",
            "source_diff_message_id",
            "disposition_id",
        )
        parsed_ids = {key: cls._uuid_from_action(action, key) for key in uuid_fields}
        if any(value is None for value in parsed_ids.values()):
            blocked_reasons.append("source_consumption_binding_invalid")

        fingerprint_fields = (
            "review_result_fingerprint",
            "revalidated_review_result_fingerprint",
            "reviewed_diff_sha256",
            "persisted_source_diff_sha256",
            "current_diff_sha256",
        )
        if not all(cls._is_sha256(action.get(key)) for key in fingerprint_fields):
            blocked_reasons.append("source_consumption_fingerprint_invalid")
        review_prompt_sha256 = action.get("review_prompt_sha256")
        if not cls._is_sha256(review_prompt_sha256):
            blocked_reasons.append("source_consumption_fingerprint_invalid")

        if not all(action.get(flag) is False for flag in _C2_FALSE_FLAGS):
            blocked_reasons.append("source_consumption_write_boundary_violated")
        if action.get("ai_project_director_total_loop") != "Partial":
            blocked_reasons.append("source_consumption_write_boundary_violated")

        review_output_schema_version = action.get("review_output_schema_version")
        source_review_verdict = action.get("source_review_verdict")
        source_review_risk_level = action.get("source_review_risk_level")
        disposition_reason = action.get("disposition_reason")
        if (
            not isinstance(review_output_schema_version, str)
            or not review_output_schema_version.strip()
            or source_review_verdict not in _VALID_REVIEW_VERDICTS
            or source_review_risk_level not in _VALID_REVIEW_RISK_LEVELS
            or not isinstance(disposition_reason, str)
            or not disposition_reason.strip()
        ):
            blocked_reasons.append("source_consumption_binding_invalid")

        try:
            consumption = (
                ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(
                    consumption_status=action.get("consumption_status"),
                    consumption_id=parsed_ids["consumption_id"],
                    source_consumption_preflight_message_id=parsed_ids[
                        "source_consumption_preflight_message_id"
                    ],
                    source_disposition_message_id=parsed_ids[
                        "source_disposition_message_id"
                    ],
                    source_review_message_id=parsed_ids["source_review_message_id"],
                    source_diff_message_id=parsed_ids["source_diff_message_id"],
                    disposition_id=parsed_ids["disposition_id"],
                    disposition_type=action.get("disposition_type"),
                    review_result_fingerprint=action.get(
                        "review_result_fingerprint"
                    ),
                    revalidated_review_result_fingerprint=action.get(
                        "revalidated_review_result_fingerprint"
                    ),
                    reviewed_diff_sha256=action.get("reviewed_diff_sha256"),
                    persisted_source_diff_sha256=action.get(
                        "persisted_source_diff_sha256"
                    ),
                    current_diff_sha256=action.get("current_diff_sha256"),
                    reviewed_scope_paths=action.get("reviewed_scope_paths"),
                    persisted_source_scope_paths=action.get(
                        "persisted_source_scope_paths"
                    ),
                    current_scope_paths=action.get("current_scope_paths"),
                    workspace_path=action.get("workspace_path"),
                    workspace_path_within_root=action.get(
                        "workspace_path_within_root"
                    ),
                    source_diff_revalidated=action.get("source_diff_revalidated"),
                    current_diff_regenerated=action.get(
                        "current_diff_regenerated"
                    ),
                    evidence_fresh=action.get("evidence_fresh"),
                    disposition_consumed=action.get("disposition_consumed"),
                    continuation_eligible=action.get("continuation_eligible"),
                    rework_eligible=action.get("rework_eligible"),
                    replay_check_completed=action.get("replay_check_completed"),
                    prior_consumption_detected=action.get(
                        "prior_consumption_detected"
                    ),
                    blocked_reasons=action.get("blocked_reasons"),
                    consumed_at=action.get("consumed_at"),
                    **{flag: action.get(flag) for flag in _C2_FALSE_FLAGS},
                    ai_project_director_total_loop=action.get(
                        "ai_project_director_total_loop"
                    ),
                )
            )
        except (ValidationError, ValueError, TypeError):
            blocked_reasons.append("source_consumption_contract_invalid")
            return None

        if blocked_reasons:
            return None

        return _ValidatedC2Evidence(
            consumption=consumption,
            disposition_reason=disposition_reason,
            review_prompt_sha256=review_prompt_sha256,
            review_output_schema_version=review_output_schema_version,
            source_review_verdict=source_review_verdict,
            source_review_risk_level=source_review_risk_level,
        )

    def _scan_prior_handoffs(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_consumption_message_id: UUID,
    ) -> tuple[bool, int]:
        prior_handoff_detected = False
        prior_rework_handoff_count = 0
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
                    != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_SOURCE_DETAIL
                    or not message.suggested_actions
                ):
                    continue
                first_action = message.suggested_actions[0]
                if (
                    not isinstance(first_action, dict)
                    or first_action.get("type")
                    != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_ACTION_TYPE
                ):
                    continue
                if first_action.get("source_consumption_message_id") == str(
                    source_consumption_message_id
                ):
                    prior_handoff_detected = True
                if (
                    first_action.get("source_task_id") == str(source_task_id)
                    and first_action.get("handoff_status") == "prepared"
                    and first_action.get("disposition_type") == "AUTO_REWORK"
                    and first_action.get("rework_handoff_prepared") is True
                ):
                    prior_rework_handoff_count += 1
            if not has_more or not messages:
                return prior_handoff_detected, prior_rework_handoff_count
            before_message_id = messages[0].id

    @staticmethod
    def _handoff_action(
        *,
        session_id: UUID,
        source_task_id: UUID,
        evidence: _ValidatedC2Evidence,
        result: ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult,
    ) -> dict[str, Any]:
        return {
            "type": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_ACTION_TYPE,
            "schema_version": DISPOSITION_HANDOFF_SCHEMA_VERSION,
            "handoff_status": result.handoff_status,
            "handoff_id": str(result.handoff_id),
            "prepared_at": result.prepared_at.isoformat(),
            "handoff_kind": result.handoff_kind,
            "session_id": str(session_id),
            "source_task_id": str(source_task_id),
            "source_consumption_message_id": str(
                result.source_consumption_message_id
            ),
            "source_consumption_id": str(result.source_consumption_id),
            "source_consumption_preflight_message_id": str(
                result.source_consumption_preflight_message_id
            ),
            "source_disposition_message_id": str(
                result.source_disposition_message_id
            ),
            "source_review_message_id": str(result.source_review_message_id),
            "source_diff_message_id": str(result.source_diff_message_id),
            "disposition_id": str(result.disposition_id),
            "disposition_type": result.disposition_type,
            "disposition_reason": result.disposition_reason,
            "review_result_fingerprint": result.review_result_fingerprint,
            "revalidated_review_result_fingerprint": (
                result.revalidated_review_result_fingerprint
            ),
            "reviewed_diff_sha256": result.reviewed_diff_sha256,
            "persisted_source_diff_sha256": result.persisted_source_diff_sha256,
            "current_diff_sha256": result.current_diff_sha256,
            "review_prompt_sha256": result.review_prompt_sha256,
            "reviewed_scope_paths": list(result.reviewed_scope_paths),
            "persisted_source_scope_paths": list(
                result.persisted_source_scope_paths
            ),
            "current_scope_paths": list(result.current_scope_paths),
            "review_output_schema_version": evidence.review_output_schema_version,
            "source_review_verdict": evidence.source_review_verdict,
            "source_review_risk_level": evidence.source_review_risk_level,
            "workspace_path": result.workspace_path,
            "workspace_path_within_root": result.workspace_path_within_root,
            "source_consumption_validated": result.source_consumption_validated,
            "replay_check_completed": result.replay_check_completed,
            "prior_handoff_detected": result.prior_handoff_detected,
            "prior_rework_handoff_count": result.prior_rework_handoff_count,
            "rework_attempt_number": result.rework_attempt_number,
            "rework_attempt_limit": result.rework_attempt_limit,
            "bounded_rework_budget_exhausted": (
                result.bounded_rework_budget_exhausted
            ),
            "rework_non_convergence_detected": (
                result.rework_non_convergence_detected
            ),
            "continuation_handoff_prepared": (
                result.continuation_handoff_prepared
            ),
            "rework_handoff_prepared": result.rework_handoff_prepared,
            "blocked_reasons": list(result.blocked_reasons),
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
        source_consumption_message_id: UUID,
        evidence: _ValidatedC2Evidence | None,
        replay_check_completed: bool,
        prior_handoff_detected: bool,
        prior_rework_handoff_count: int,
        bounded_rework_budget_exhausted: bool,
        rework_non_convergence_detected: bool,
        blocked_reasons: list[str],
    ) -> ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult:
        consumption = evidence.consumption if evidence is not None else None
        return ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(
            handoff_status="blocked",
            source_consumption_message_id=source_consumption_message_id,
            source_consumption_id=(
                consumption.consumption_id if consumption is not None else None
            ),
            source_consumption_preflight_message_id=(
                consumption.source_consumption_preflight_message_id
                if consumption is not None
                else None
            ),
            source_disposition_message_id=(
                consumption.source_disposition_message_id
                if consumption is not None
                else None
            ),
            source_review_message_id=(
                consumption.source_review_message_id
                if consumption is not None
                else None
            ),
            source_diff_message_id=(
                consumption.source_diff_message_id
                if consumption is not None
                else None
            ),
            disposition_id=(
                consumption.disposition_id if consumption is not None else None
            ),
            disposition_type=(
                consumption.disposition_type if consumption is not None else None
            ),
            disposition_reason=(
                evidence.disposition_reason if evidence is not None else ""
            ),
            review_result_fingerprint=(
                consumption.review_result_fingerprint
                if consumption is not None
                else ""
            ),
            revalidated_review_result_fingerprint=(
                consumption.revalidated_review_result_fingerprint
                if consumption is not None
                else ""
            ),
            reviewed_diff_sha256=(
                consumption.reviewed_diff_sha256 if consumption is not None else ""
            ),
            persisted_source_diff_sha256=(
                consumption.persisted_source_diff_sha256
                if consumption is not None
                else ""
            ),
            current_diff_sha256=(
                consumption.current_diff_sha256 if consumption is not None else ""
            ),
            review_prompt_sha256=(
                evidence.review_prompt_sha256 if evidence is not None else ""
            ),
            reviewed_scope_paths=(
                list(consumption.reviewed_scope_paths)
                if consumption is not None
                else []
            ),
            persisted_source_scope_paths=(
                list(consumption.persisted_source_scope_paths)
                if consumption is not None
                else []
            ),
            current_scope_paths=(
                list(consumption.current_scope_paths)
                if consumption is not None
                else []
            ),
            workspace_path=(
                consumption.workspace_path if consumption is not None else ""
            ),
            workspace_path_within_root=(
                consumption.workspace_path_within_root
                if consumption is not None
                else False
            ),
            source_consumption_validated=evidence is not None,
            replay_check_completed=replay_check_completed,
            prior_handoff_detected=prior_handoff_detected,
            prior_rework_handoff_count=prior_rework_handoff_count,
            rework_attempt_limit=MAX_AUTOMATIC_REWORK_HANDOFFS_PER_TASK,
            bounded_rework_budget_exhausted=bounded_rework_budget_exhausted,
            rework_non_convergence_detected=rework_non_convergence_detected,
            blocked_reasons=(
                ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService._dedupe(
                    blocked_reasons
                )
            ),
        )

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
    "DISPOSITION_HANDOFF_SCHEMA_VERSION",
    "MAX_AUTOMATIC_REWORK_HANDOFFS_PER_TASK",
    "P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_ACTION_TYPE",
    "P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_SOURCE_DETAIL",
    "PreparedSandboxCandidateDiffReviewDispositionHandoff",
    "ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService",
)
