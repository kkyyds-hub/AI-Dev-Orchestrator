"""Deterministic automated review disposition gate for Project Director P21-D-B."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

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


@dataclass(frozen=True, slots=True)
class ComputedSandboxCandidateDiffReviewDisposition:
    """P21-D-B disposition result and optional append-only audit message."""

    result: ProjectDirectorSandboxCandidateDiffReviewDispositionResult
    message: ProjectDirectorMessage | None


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
        self._message_repository.commit()
        return ComputedSandboxCandidateDiffReviewDisposition(
            result=result,
            message=message,
        )

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
    "REVIEW_DISPOSITION_SCHEMA_VERSION",
)
