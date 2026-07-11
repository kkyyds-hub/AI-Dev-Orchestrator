"""Trusted disposition consumption preflight for Project Director P21-D-C1."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_sandbox_candidate_diff_review_disposition import (
    ReviewDispositionType,
)
from app.domain.project_director_sandbox_candidate_diff_review_disposition_consumption_preflight import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightResult,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_service import (
    DEFERRED_TRIGGER_KINDS,
    EVALUATED_TRIGGER_KINDS,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL,
    REVIEW_DISPOSITION_SCHEMA_VERSION,
    ProjectDirectorSandboxCandidateDiffReviewDispositionService,
    RevalidatedPersistedReviewResultFingerprint,
)
from app.services.project_director_sandbox_candidate_diff_review_execution_preflight_service import (
    REVIEW_OUTPUT_SCHEMA_VERSION,
)


P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL = (
    "p21_d_sandbox_candidate_diff_review_disposition_consumption_preflight_ready"
)
P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_ACTION_TYPE = (
    "p21_d_sandbox_candidate_diff_review_disposition_consumption_preflight_record"
)
DISPOSITION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION = "p21-d-c1.v1"

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_VALID_REVIEWER_EXECUTORS = ("codex", "claude-code")
_VALID_DISPOSITION_TYPES = (
    "AUTO_CONTINUE",
    "AUTO_REWORK",
    "ESCALATE_TO_HUMAN",
)
_VALID_REVIEW_VERDICTS = (
    "no_blocking_findings",
    "non_blocking_findings",
    "changes_required",
)
_VALID_REVIEW_RISK_LEVELS = ("low", "medium", "high")
_DISPOSITION_FALSE_FLAGS = (
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
class PreparedSandboxCandidateDiffReviewDispositionConsumptionPreflight:
    """P21-D-C1 eligibility result and optional append-only ready record."""

    result: ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightResult
    message: ProjectDirectorMessage | None


@dataclass(frozen=True, slots=True)
class _ValidatedDispositionEvidence:
    source_review_message_id: UUID
    source_preflight_message_id: UUID
    source_diff_message_id: UUID
    disposition_id: UUID
    requested_reviewer_executor: str
    source_diff_sha256: str
    review_prompt_sha256: str
    review_scope_paths: list[str]
    review_output_schema_version: str
    review_result_fingerprint: str
    disposition_type: ReviewDispositionType
    disposition_reason: str
    source_review_verdict: str
    source_review_risk_level: str


class ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightService:
    """Validate exact persisted evidence before any future disposition consumption."""

    def __init__(
        self,
        *,
        session_repository: ProjectDirectorSessionRepository | None = None,
        message_repository: ProjectDirectorMessageRepository | None = None,
    ) -> None:
        self._session_repository = session_repository
        self._message_repository = message_repository

    def prepare_candidate_diff_review_disposition_consumption(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
    ) -> PreparedSandboxCandidateDiffReviewDispositionConsumptionPreflight:
        """Return future eligibility without consuming the persisted disposition."""

        if self._session_repository is None or self._message_repository is None:
            raise ValueError(
                "disposition consumption preflight repositories are required"
            )

        with self._message_repository.sqlite_immediate_transaction():
            return self._prepare_candidate_diff_review_disposition_consumption(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
            )

    def _prepare_candidate_diff_review_disposition_consumption(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
    ) -> PreparedSandboxCandidateDiffReviewDispositionConsumptionPreflight:
        blocked_reasons: list[str] = []
        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            blocked_reasons.append("session_missing")

        source_disposition_message = self._message_repository.get_by_id(
            source_message_id
        )
        disposition_action = self._source_disposition_action(
            source_disposition_message=source_disposition_message,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        evidence = self._validated_disposition_evidence(
            disposition_action,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )

        revalidation: RevalidatedPersistedReviewResultFingerprint | None = None
        replay_check_completed = False
        prior_preflight_detected = False

        if not blocked_reasons and evidence is not None:
            if evidence.disposition_type == "ESCALATE_TO_HUMAN":
                blocked_reasons.append("disposition_type_escalation_unhandled")
            else:
                source_review_message = self._message_repository.get_by_id(
                    evidence.source_review_message_id
                )
                revalidation = (
                    ProjectDirectorSandboxCandidateDiffReviewDispositionService.revalidate_persisted_review_result_fingerprint(
                        session_id=session_id,
                        source_task_id=source_task_id,
                        source_review_message_id=evidence.source_review_message_id,
                        source_review_message=source_review_message,
                    )
                )
                blocked_reasons.extend(revalidation.blocked_reasons)
                if not revalidation.blocked_reasons:
                    if (
                        evidence.review_result_fingerprint
                        != revalidation.review_result_fingerprint
                    ):
                        blocked_reasons.append("review_result_fingerprint_mismatch")
                    if not self._source_binding_matches(evidence, revalidation):
                        blocked_reasons.append("disposition_source_binding_mismatch")

        if not blocked_reasons and evidence is not None:
            prior_preflight_detected = self._prior_ready_preflight_exists(
                session_id=session_id,
                source_disposition_message_id=source_message_id,
            )
            replay_check_completed = True
            if prior_preflight_detected:
                blocked_reasons.append("disposition_already_preflighted")

        blocked_reasons = self._dedupe(blocked_reasons)
        if (
            blocked_reasons
            or evidence is None
            or revalidation is None
            or session_obj is None
        ):
            return PreparedSandboxCandidateDiffReviewDispositionConsumptionPreflight(
                result=self._blocked_result(
                    source_disposition_message_id=source_message_id,
                    evidence=evidence,
                    revalidation=revalidation,
                    replay_check_completed=replay_check_completed,
                    prior_preflight_detected=prior_preflight_detected,
                    blocked_reasons=blocked_reasons,
                ),
                message=None,
            )

        result = ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightResult(
            preflight_status="ready",
            source_disposition_message_id=source_message_id,
            source_review_message_id=evidence.source_review_message_id,
            disposition_id=evidence.disposition_id,
            disposition_type=evidence.disposition_type,
            review_result_fingerprint=evidence.review_result_fingerprint,
            revalidated_review_result_fingerprint=(
                revalidation.review_result_fingerprint
            ),
            continuation_eligible=evidence.disposition_type == "AUTO_CONTINUE",
            rework_eligible=evidence.disposition_type == "AUTO_REWORK",
            replay_check_completed=True,
            prior_preflight_detected=False,
        )
        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "Disposition consumption preflight is ready for future bounded "
                    "automation. No disposition was consumed, no continuation or "
                    "rework was started, and no write was authorized. AI Project "
                    "Director total loop remains Partial."
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="sandbox_candidate_diff_review_disposition_consumption_preflight",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=(
                    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL
                ),
                suggested_actions=[
                    self._preflight_action(
                        session_id=session_id,
                        source_task_id=source_task_id,
                        source_disposition_message_id=source_message_id,
                        evidence=evidence,
                        result=result,
                    )
                ],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                forbidden_actions_detected=[
                    "no_disposition_consumption",
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
            )
        )
        return PreparedSandboxCandidateDiffReviewDispositionConsumptionPreflight(
            result=result,
            message=message,
        )

    @staticmethod
    def _source_disposition_action(
        *,
        source_disposition_message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> dict[str, Any] | None:
        if source_disposition_message is None:
            blocked_reasons.append("source_disposition_message_missing")
            return None
        if source_disposition_message.session_id != session_id:
            blocked_reasons.append("source_disposition_message_session_mismatch")
        if source_disposition_message.related_task_id != source_task_id:
            blocked_reasons.append("source_disposition_message_task_mismatch")
        if source_disposition_message.source != ProjectDirectorMessageSource.SYSTEM:
            blocked_reasons.append("source_disposition_message_source_invalid")
        if source_disposition_message.requires_confirmation is not False:
            blocked_reasons.append(
                "source_disposition_message_confirmation_contract_invalid"
            )
        if (
            source_disposition_message.source_detail
            != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL
        ):
            blocked_reasons.append("source_message_is_not_p21_d_review_disposition")
        if not source_disposition_message.suggested_actions:
            blocked_reasons.append("p21_d_review_disposition_record_missing")
            return None
        first_action = source_disposition_message.suggested_actions[0]
        if (
            not isinstance(first_action, dict)
            or first_action.get("type")
            != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_ACTION_TYPE
        ):
            blocked_reasons.append("p21_d_review_disposition_record_missing")
            return None
        return first_action

    @classmethod
    def _validated_disposition_evidence(
        cls,
        action: dict[str, Any] | None,
        *,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> _ValidatedDispositionEvidence | None:
        if action is None:
            return None

        if action.get("schema_version") != REVIEW_DISPOSITION_SCHEMA_VERSION:
            blocked_reasons.append("disposition_schema_version_mismatch")
        if action.get("disposition_status") != "computed":
            blocked_reasons.append("disposition_status_not_computed")
        if action.get("session_id") != str(session_id):
            blocked_reasons.append("disposition_action_session_mismatch")
        if action.get("source_task_id") != str(source_task_id):
            blocked_reasons.append("disposition_action_task_mismatch")

        source_review_message_id = cls._uuid_from_action(
            action, "source_review_message_id"
        )
        source_preflight_message_id = cls._uuid_from_action(
            action, "source_preflight_message_id"
        )
        source_diff_message_id = cls._uuid_from_action(
            action, "source_diff_message_id"
        )
        if (
            source_review_message_id is None
            or source_preflight_message_id is None
            or source_diff_message_id is None
        ):
            blocked_reasons.append("disposition_binding_invalid")

        disposition_id = cls._uuid_from_action(action, "disposition_id")
        if disposition_id is None:
            blocked_reasons.append("disposition_id_invalid")

        requested_reviewer_executor = action.get("requested_reviewer_executor")
        source_diff_sha256 = action.get("source_diff_sha256")
        review_prompt_sha256 = action.get("review_prompt_sha256")
        review_scope_paths = cls._review_scope_paths(action)
        review_output_schema_version = action.get("review_output_schema_version")
        source_review_verdict = action.get("source_review_verdict")
        source_review_risk_level = action.get("source_review_risk_level")
        if (
            requested_reviewer_executor not in _VALID_REVIEWER_EXECUTORS
            or not cls._is_sha256(source_diff_sha256)
            or not cls._is_sha256(review_prompt_sha256)
            or review_scope_paths is None
            or review_output_schema_version != REVIEW_OUTPUT_SCHEMA_VERSION
            or source_review_verdict not in _VALID_REVIEW_VERDICTS
            or source_review_risk_level not in _VALID_REVIEW_RISK_LEVELS
        ):
            blocked_reasons.append("disposition_binding_invalid")

        review_result_fingerprint = action.get("review_result_fingerprint")
        if not cls._is_sha256(review_result_fingerprint):
            blocked_reasons.append("disposition_review_result_fingerprint_invalid")

        disposition_type = action.get("disposition_type")
        if disposition_type not in _VALID_DISPOSITION_TYPES:
            blocked_reasons.append("disposition_type_invalid")
        disposition_reason = action.get("disposition_reason")
        if not isinstance(disposition_reason, str) or not disposition_reason:
            blocked_reasons.append("disposition_reason_missing")

        if not cls._trigger_contract_valid(action, disposition_type):
            blocked_reasons.append("disposition_trigger_contract_invalid")
        if action.get("actor") != "system":
            blocked_reasons.append("disposition_actor_invalid")
        if action.get("client_request_id") is not None:
            blocked_reasons.append("disposition_client_request_id_invalid")
        if not cls._timezone_aware_iso_datetime(
            action.get("disposition_created_at")
        ):
            blocked_reasons.append("disposition_timestamp_invalid")
        if not all(action.get(flag) is False for flag in _DISPOSITION_FALSE_FLAGS):
            blocked_reasons.append("disposition_write_boundary_violated")
        if action.get("ai_project_director_total_loop") != "Partial":
            blocked_reasons.append("disposition_write_boundary_violated")

        if blocked_reasons:
            return None
        if (
            source_review_message_id is None
            or source_preflight_message_id is None
            or source_diff_message_id is None
            or disposition_id is None
            or review_scope_paths is None
        ):
            return None
        return _ValidatedDispositionEvidence(
            source_review_message_id=source_review_message_id,
            source_preflight_message_id=source_preflight_message_id,
            source_diff_message_id=source_diff_message_id,
            disposition_id=disposition_id,
            requested_reviewer_executor=requested_reviewer_executor,
            source_diff_sha256=source_diff_sha256,
            review_prompt_sha256=review_prompt_sha256,
            review_scope_paths=review_scope_paths,
            review_output_schema_version=review_output_schema_version,
            review_result_fingerprint=review_result_fingerprint,
            disposition_type=disposition_type,
            disposition_reason=disposition_reason,
            source_review_verdict=source_review_verdict,
            source_review_risk_level=source_review_risk_level,
        )

    def _prior_ready_preflight_exists(
        self,
        *,
        session_id: UUID,
        source_disposition_message_id: UUID,
    ) -> bool:
        if self._message_repository is None:
            raise ValueError(
                "disposition consumption preflight repository is required"
            )

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
                    != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL
                    or not message.suggested_actions
                ):
                    continue
                first_action = message.suggested_actions[0]
                if (
                    isinstance(first_action, dict)
                    and first_action.get("type")
                    == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_ACTION_TYPE
                    and first_action.get("source_disposition_message_id")
                    == str(source_disposition_message_id)
                ):
                    return True
            if not has_more:
                return False
            if not messages:
                return False
            before_message_id = messages[0].id

    @staticmethod
    def _source_binding_matches(
        evidence: _ValidatedDispositionEvidence,
        revalidation: RevalidatedPersistedReviewResultFingerprint,
    ) -> bool:
        return (
            evidence.source_preflight_message_id
            == revalidation.source_preflight_message_id
            and evidence.source_diff_message_id == revalidation.source_diff_message_id
            and evidence.requested_reviewer_executor
            == revalidation.requested_reviewer_executor
            and evidence.source_diff_sha256 == revalidation.source_diff_sha256
            and evidence.review_prompt_sha256 == revalidation.review_prompt_sha256
            and evidence.review_scope_paths == (revalidation.review_scope_paths or [])
            and evidence.review_output_schema_version
            == revalidation.review_output_schema_version
            and evidence.source_review_verdict == revalidation.verdict
            and evidence.source_review_risk_level == revalidation.risk_level
        )

    @staticmethod
    def _preflight_action(
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_disposition_message_id: UUID,
        evidence: _ValidatedDispositionEvidence,
        result: ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightResult,
    ) -> dict[str, Any]:
        return {
            "type": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_ACTION_TYPE,
            "schema_version": DISPOSITION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION,
            "preflight_status": result.preflight_status,
            "session_id": str(session_id),
            "source_task_id": str(source_task_id),
            "source_disposition_message_id": str(source_disposition_message_id),
            "source_review_message_id": str(evidence.source_review_message_id),
            "source_preflight_message_id": str(evidence.source_preflight_message_id),
            "source_diff_message_id": str(evidence.source_diff_message_id),
            "disposition_id": str(evidence.disposition_id),
            "disposition_type": evidence.disposition_type,
            "disposition_reason": evidence.disposition_reason,
            "review_result_fingerprint": result.review_result_fingerprint,
            "revalidated_review_result_fingerprint": (
                result.revalidated_review_result_fingerprint
            ),
            "source_diff_sha256": evidence.source_diff_sha256,
            "review_prompt_sha256": evidence.review_prompt_sha256,
            "review_scope_paths": list(evidence.review_scope_paths),
            "review_output_schema_version": evidence.review_output_schema_version,
            "source_review_verdict": evidence.source_review_verdict,
            "source_review_risk_level": evidence.source_review_risk_level,
            "continuation_eligible": result.continuation_eligible,
            "rework_eligible": result.rework_eligible,
            "replay_check_completed": result.replay_check_completed,
            "prior_preflight_detected": result.prior_preflight_detected,
            "blocked_reasons": list(result.blocked_reasons),
            "continuation_started": False,
            "rework_started": False,
            "disposition_consumed": False,
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
        source_disposition_message_id: UUID,
        evidence: _ValidatedDispositionEvidence | None,
        revalidation: RevalidatedPersistedReviewResultFingerprint | None,
        replay_check_completed: bool,
        prior_preflight_detected: bool,
        blocked_reasons: list[str],
    ) -> ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightResult:
        return ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightResult(
            preflight_status="blocked",
            source_disposition_message_id=source_disposition_message_id,
            source_review_message_id=(
                evidence.source_review_message_id if evidence is not None else None
            ),
            disposition_id=evidence.disposition_id if evidence is not None else None,
            disposition_type=(
                evidence.disposition_type if evidence is not None else None
            ),
            review_result_fingerprint=(
                evidence.review_result_fingerprint if evidence is not None else ""
            ),
            revalidated_review_result_fingerprint=(
                revalidation.review_result_fingerprint
                if revalidation is not None
                else ""
            ),
            replay_check_completed=replay_check_completed,
            prior_preflight_detected=prior_preflight_detected,
            blocked_reasons=ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightService._dedupe(
                blocked_reasons
            ),
        )

    @staticmethod
    def _trigger_contract_valid(
        action: dict[str, Any],
        disposition_type: Any,
    ) -> bool:
        if action.get("evaluated_trigger_kinds") != EVALUATED_TRIGGER_KINDS:
            return False
        if action.get("deferred_trigger_kinds") != DEFERRED_TRIGGER_KINDS:
            return False
        expected_triggers = (
            ["high_review_risk"]
            if disposition_type == "ESCALATE_TO_HUMAN"
            else []
        )
        return action.get("escalation_triggers") == expected_triggers

    @staticmethod
    def _review_scope_paths(action: dict[str, Any]) -> list[str] | None:
        raw_paths = action.get("review_scope_paths")
        if not isinstance(raw_paths, list) or not raw_paths:
            return None
        if any(not isinstance(path, str) or not path for path in raw_paths):
            return None
        if len(set(raw_paths)) != len(raw_paths):
            return None
        return list(raw_paths)

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
    "DISPOSITION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION",
    "P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_ACTION_TYPE",
    "P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL",
    "PreparedSandboxCandidateDiffReviewDispositionConsumptionPreflight",
    "ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightService",
)
