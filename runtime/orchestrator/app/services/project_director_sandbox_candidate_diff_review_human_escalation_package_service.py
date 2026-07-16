"""Single-source human escalation package gate for Project Director P21-D-D1."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.domain.project_director_bounded_rework_review_reentry import (
    P25_BOUNDED_REWORK_REVIEW_OUTCOME_SCHEMA_VERSION,
    ProjectDirectorBoundedReworkReviewInvocationOutcome,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_sandbox_candidate_diff_review_disposition import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionResult,
)
from app.domain.project_director_sandbox_candidate_diff_review_human_escalation_package import (
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult,
)
from app.domain.project_director_sandbox_candidate_diff_review_output import (
    ProjectDirectorSandboxCandidateDiffReviewFinding,
    ProjectDirectorSandboxCandidateDiffValidatedReviewOutput,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_bounded_rework_review_execution_service import (
    P25_BOUNDED_REWORK_REVIEW_OUTCOME_ACTION_TYPE,
    P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT,
    P25_BOUNDED_REWORK_REVIEW_OUTCOME_SOURCE_DETAIL,
    ProjectDirectorBoundedReworkReviewExecutionService,
)
from app.services.project_director_sandbox_candidate_diff_readonly_review_execution_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
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


P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_SOURCE_DETAIL = (
    "p21_d_sandbox_candidate_diff_review_human_escalation_package_prepared"
)
P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_ACTION_TYPE = (
    "p21_d_sandbox_candidate_diff_review_human_escalation_package_record"
)
HUMAN_ESCALATION_PACKAGE_SCHEMA_VERSION = "p21-d-d1.v1"

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_VALID_REVIEWER_EXECUTORS = ("codex", "claude-code")
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
class PreparedSandboxCandidateDiffReviewHumanEscalationPackage:
    """P21-D-D1 result and optional append-only escalation package message."""

    result: ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult
    message: ProjectDirectorMessage | None


@dataclass(frozen=True, slots=True)
class RevalidatedPersistedHumanEscalationPackageFingerprint:
    """Pure aggregate fingerprint revalidation for one persisted D1 action."""

    aggregate_evidence_fingerprint: str
    blocked_reasons: list[str]
    source_package_message_id: UUID | None = None
    escalation_package_id: UUID | None = None
    source_disposition_message_id: UUID | None = None
    source_review_message_id: UUID | None = None
    source_preflight_message_id: UUID | None = None
    source_diff_message_id: UUID | None = None
    disposition_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class _ValidatedEscalationDispositionEvidence:
    disposition: ProjectDirectorSandboxCandidateDiffReviewDispositionResult
    source_review_message_id: UUID
    source_preflight_message_id: UUID
    source_diff_message_id: UUID
    disposition_id: UUID
    requested_reviewer_executor: str
    source_diff_sha256: str
    review_prompt_sha256: str
    review_scope_paths: list[str]
    review_output_schema_version: str
    source_review_verdict: str
    source_review_risk_level: str


@dataclass(frozen=True, slots=True)
class _ValidatedStrictReviewEvidence:
    source_review_kind: str
    output: ProjectDirectorSandboxCandidateDiffValidatedReviewOutput
    source_preflight_message_id: UUID
    source_diff_message_id: UUID
    requested_reviewer_executor: str
    source_diff_sha256: str
    review_prompt_sha256: str
    review_scope_paths: list[str]
    review_output_schema_version: str


@dataclass(frozen=True, slots=True)
class _NormalizedReviewSource:
    source_review_kind: str
    message: ProjectDirectorMessage
    action: dict[str, Any]
    outcome: ProjectDirectorBoundedReworkReviewInvocationOutcome | None = None


class ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService:
    """Prepare one append-only package from one exact human escalation source."""

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

    @classmethod
    def revalidate_persisted_human_escalation_package_fingerprint(
        cls,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_package_message_id: UUID,
        source_package_action: dict[str, Any],
    ) -> RevalidatedPersistedHumanEscalationPackageFingerprint:
        """Recompute one D1 aggregate fingerprint without repository side effects."""

        blocked_reasons: list[str] = []
        action = source_package_action
        if (
            action.get("type")
            != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_ACTION_TYPE
        ):
            blocked_reasons.append("human_escalation_package_action_type_invalid")
        if action.get("schema_version") != HUMAN_ESCALATION_PACKAGE_SCHEMA_VERSION:
            blocked_reasons.append("human_escalation_package_schema_version_mismatch")
        if action.get("session_id") != str(session_id):
            blocked_reasons.append("human_escalation_package_session_mismatch")
        if action.get("source_task_id") != str(source_task_id):
            blocked_reasons.append("human_escalation_package_task_mismatch")

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
            blocked_reasons.append("human_escalation_package_domain_reconstruction_invalid")

        review_scope_paths = cls._review_scope_paths(action)
        requested_reviewer_executor = action.get("requested_reviewer_executor")
        source_diff_sha256 = action.get("source_diff_sha256")
        review_prompt_sha256 = action.get("review_prompt_sha256")
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
            blocked_reasons.append("human_escalation_package_fingerprint_material_invalid")

        if blocked_reasons or package is None or review_scope_paths is None:
            return RevalidatedPersistedHumanEscalationPackageFingerprint(
                aggregate_evidence_fingerprint="",
                blocked_reasons=cls._dedupe(blocked_reasons),
                source_package_message_id=source_package_message_id,
            )

        canonical_payload = cls._aggregate_evidence_canonical_payload(
            session_id=session_id,
            source_task_id=source_task_id,
            source_disposition_message_id=package.source_disposition_message_id,
            source_review_message_id=package.source_review_message_id,
            source_preflight_message_id=package.source_preflight_message_id,
            source_diff_message_id=package.source_diff_message_id,
            disposition_id=package.disposition_id,
            disposition_type=package.disposition_type,
            disposition_reason=package.disposition_reason,
            review_result_fingerprint=package.review_result_fingerprint,
            revalidated_review_result_fingerprint=(
                package.revalidated_review_result_fingerprint
            ),
            requested_reviewer_executor=requested_reviewer_executor,
            source_diff_sha256=source_diff_sha256,
            review_prompt_sha256=review_prompt_sha256,
            review_scope_paths=review_scope_paths,
            review_output_schema_version=review_output_schema_version,
            source_review_verdict=source_review_verdict,
            source_review_risk_level=source_review_risk_level,
            escalation_triggers=package.escalation_triggers,
            escalation_scope=package.escalation_scope,
            related_task_ids=package.related_task_ids,
            related_review_message_ids=package.related_review_message_ids,
            unresolved_findings=package.unresolved_blocking_findings,
            risk_summary=package.risk_summary,
            proposed_human_decision_scope=package.proposed_human_decision_scope,
        )
        return RevalidatedPersistedHumanEscalationPackageFingerprint(
            aggregate_evidence_fingerprint=cls._canonical_payload_fingerprint(
                canonical_payload
            ),
            blocked_reasons=[],
            source_package_message_id=source_package_message_id,
            escalation_package_id=package.escalation_package_id,
            source_disposition_message_id=package.source_disposition_message_id,
            source_review_message_id=package.source_review_message_id,
            source_preflight_message_id=package.source_preflight_message_id,
            source_diff_message_id=package.source_diff_message_id,
            disposition_id=package.disposition_id,
        )

    def prepare_human_escalation_package(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
    ) -> PreparedSandboxCandidateDiffReviewHumanEscalationPackage:
        """Validate B/C evidence and append a package without a human decision."""

        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("human escalation package repositories are required")

        with self._message_repository.sqlite_immediate_transaction():
            return self._prepare_candidate_diff_review_human_escalation_package(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
            )

    def _prepare_candidate_diff_review_human_escalation_package(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
    ) -> PreparedSandboxCandidateDiffReviewHumanEscalationPackage:
        blocked_reasons: list[str] = []
        evidence: _ValidatedEscalationDispositionEvidence | None = None
        review_evidence: _ValidatedStrictReviewEvidence | None = None
        revalidation: RevalidatedPersistedReviewResultFingerprint | None = None
        replay_check_completed = False
        prior_escalation_package_detected = False

        def blocked_result() -> PreparedSandboxCandidateDiffReviewHumanEscalationPackage:
            return PreparedSandboxCandidateDiffReviewHumanEscalationPackage(
                result=self._blocked_result(
                    source_disposition_message_id=source_message_id,
                    evidence=evidence,
                    revalidation=revalidation,
                    replay_check_completed=replay_check_completed,
                    prior_escalation_package_detected=(
                        prior_escalation_package_detected
                    ),
                    blocked_reasons=blocked_reasons,
                ),
                message=None,
            )

        session_obj = self._session_repository.get_by_id(session_id)
        source_task = self._task_repository.get_by_id(source_task_id)
        source_disposition_message = self._message_repository.get_by_id(
            source_message_id
        )
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
        blocked_reasons = self._dedupe(blocked_reasons)
        if blocked_reasons:
            return blocked_result()

        disposition_action = self._source_disposition_action(
            source_disposition_message=source_disposition_message,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        evidence = self._validated_escalation_disposition_evidence(
            disposition_action,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        blocked_reasons = self._dedupe(blocked_reasons)
        if blocked_reasons or evidence is None or session_obj is None:
            return blocked_result()

        source_review_message = self._message_repository.get_by_id(
            evidence.source_review_message_id
        )
        source_review = self._source_review_action(
            source_review_message=source_review_message,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        blocked_reasons = self._dedupe(blocked_reasons)
        if blocked_reasons or source_review is None:
            return blocked_result()

        revalidate_fingerprint = (
            ProjectDirectorSandboxCandidateDiffReviewDispositionService
            .revalidate_persisted_review_result_fingerprint
        )
        revalidation = revalidate_fingerprint(
            session_id=session_id,
            source_task_id=source_task_id,
            source_review_message_id=evidence.source_review_message_id,
            source_review_message=source_review_message,
        )
        blocked_reasons.extend(revalidation.blocked_reasons)
        blocked_reasons = self._dedupe(blocked_reasons)
        if blocked_reasons:
            return blocked_result()

        if (
            evidence.disposition.review_result_fingerprint
            != revalidation.review_result_fingerprint
        ):
            blocked_reasons.append("review_result_fingerprint_mismatch")
        if not self._review_source_binding_matches(evidence, revalidation):
            blocked_reasons.append("disposition_source_binding_mismatch")
        blocked_reasons = self._dedupe(blocked_reasons)
        if blocked_reasons:
            return blocked_result()

        review_evidence = self._strict_review_evidence(
            source_review=source_review,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        if (
            review_evidence is not None
            and not self._strict_review_binding_matches(evidence, review_evidence)
        ):
            blocked_reasons.append(
                "exact_p21_c_review_evidence_binding_mismatch"
                if review_evidence.source_review_kind == "p21_c"
                else "exact_p25_h_review_evidence_binding_mismatch"
            )
        blocked_reasons = self._dedupe(blocked_reasons)
        if blocked_reasons or review_evidence is None:
            return blocked_result()

        prior_escalation_package_detected = self._prior_escalation_package_exists(
            session_id=session_id,
            source_disposition_message_id=source_message_id,
            disposition_id=evidence.disposition_id,
            source_review_message_id=evidence.source_review_message_id,
        )
        replay_check_completed = True
        if prior_escalation_package_detected:
            blocked_reasons.append("human_escalation_package_already_created")
            return blocked_result()

        unresolved_findings = [
            finding
            for finding in review_evidence.output.findings
            if finding.severity == "high"
        ]
        escalation_scope = "single_source_review"
        related_task_ids = [source_task_id]
        related_review_message_ids = [evidence.source_review_message_id]
        proposed_human_decision_scope = (
            "resolve_single_source_review_escalation"
        )
        risk_summary = review_evidence.output.summary
        aggregate_evidence_fingerprint = self._aggregate_evidence_fingerprint(
            session_id=session_id,
            source_task_id=source_task_id,
            source_disposition_message_id=source_message_id,
            evidence=evidence,
            revalidation=revalidation,
            review_evidence=review_evidence,
            escalation_scope=escalation_scope,
            related_task_ids=related_task_ids,
            related_review_message_ids=related_review_message_ids,
            unresolved_findings=unresolved_findings,
            risk_summary=risk_summary,
            proposed_human_decision_scope=proposed_human_decision_scope,
        )

        escalation_package_id = uuid4()
        package_created_at = datetime.now(timezone.utc)
        result = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(
            package_status="prepared",
            escalation_package_id=escalation_package_id,
            source_disposition_message_id=source_message_id,
            source_review_message_id=evidence.source_review_message_id,
            source_preflight_message_id=evidence.source_preflight_message_id,
            source_diff_message_id=evidence.source_diff_message_id,
            disposition_id=evidence.disposition_id,
            disposition_type=evidence.disposition.disposition_type,
            disposition_reason=evidence.disposition.disposition_reason,
            review_result_fingerprint=(
                evidence.disposition.review_result_fingerprint
            ),
            revalidated_review_result_fingerprint=(
                revalidation.review_result_fingerprint
            ),
            aggregate_evidence_fingerprint=aggregate_evidence_fingerprint,
            escalation_triggers=list(evidence.disposition.escalation_triggers),
            escalation_scope=escalation_scope,
            related_task_ids=related_task_ids,
            related_review_message_ids=related_review_message_ids,
            unresolved_blocking_findings=unresolved_findings,
            risk_summary=risk_summary,
            proposed_human_decision_scope=proposed_human_decision_scope,
            source_review_validated=True,
            replay_check_completed=True,
            prior_escalation_package_detected=False,
            package_created_at=package_created_at,
            human_escalation_package_created=True,
        )
        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "A single-source human escalation package was prepared from "
                    "exact persisted P21-D-B and validated review evidence and is "
                    "waiting for "
                    "a future structured human decision. No human decision has "
                    "been recorded, no execution has started, and no file write, "
                    "patch, or Git write has been authorized. "
                    "requires_confirmation means only that the package awaits that "
                    "future decision; it is not human approval or Git-write "
                    "authorization. AI Project Director total loop remains Partial."
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="sandbox_candidate_diff_review_human_escalation_package",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=(
                    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_SOURCE_DETAIL
                ),
                suggested_actions=[
                    self._escalation_package_action(
                        session_id=session_id,
                        source_task_id=source_task_id,
                        evidence=evidence,
                        result=result,
                    )
                ],
                requires_confirmation=True,
                risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                forbidden_actions_detected=[
                    "no_human_decision",
                    "no_approval_request",
                    "no_legacy_approval_decision",
                    "no_continuation_start",
                    "no_rework_start",
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
                    "no_pr_creation",
                    "no_merge",
                    "no_ci_trigger",
                ],
                created_at=package_created_at,
            )
        )
        return PreparedSandboxCandidateDiffReviewHumanEscalationPackage(
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
        if source_disposition_message.role != ProjectDirectorMessageRole.ASSISTANT:
            blocked_reasons.append("source_disposition_message_role_invalid")
        if source_disposition_message.source != ProjectDirectorMessageSource.SYSTEM:
            blocked_reasons.append("source_disposition_message_source_invalid")
        if (
            source_disposition_message.intent
            != "sandbox_candidate_diff_review_disposition"
        ):
            blocked_reasons.append("source_disposition_message_intent_invalid")
        if source_disposition_message.requires_confirmation is not False:
            blocked_reasons.append(
                "source_disposition_message_confirmation_contract_invalid"
            )
        if (
            source_disposition_message.risk_level
            != ProjectDirectorMessageRiskLevel.HIGH
        ):
            blocked_reasons.append("source_disposition_message_risk_level_invalid")
        if (
            source_disposition_message.source_detail
            != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL
        ):
            blocked_reasons.append("source_message_is_not_p21_d_review_disposition")
        if len(source_disposition_message.suggested_actions) != 1:
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
    def _validated_escalation_disposition_evidence(
        cls,
        action: dict[str, Any] | None,
        *,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> _ValidatedEscalationDispositionEvidence | None:
        if action is None:
            return None

        if action.get("schema_version") != REVIEW_DISPOSITION_SCHEMA_VERSION:
            blocked_reasons.append("disposition_schema_version_mismatch")
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
        disposition_id = cls._uuid_from_action(action, "disposition_id")
        if (
            source_review_message_id is None
            or source_preflight_message_id is None
            or source_diff_message_id is None
            or disposition_id is None
        ):
            blocked_reasons.append("disposition_binding_invalid")

        domain_payload = {
            field_name: action.get(field_name)
            for field_name in (
                "disposition_status",
                "disposition_type",
                "source_review_message_id",
                "review_result_fingerprint",
                "disposition_reason",
                "escalation_triggers",
                "evaluated_trigger_kinds",
                "deferred_trigger_kinds",
                "blocked_reasons",
                *_DISPOSITION_FALSE_FLAGS,
                "ai_project_director_total_loop",
            )
        }
        domain_payload["blocked_reasons"] = action.get("blocked_reasons", [])
        disposition: ProjectDirectorSandboxCandidateDiffReviewDispositionResult | None
        try:
            disposition = ProjectDirectorSandboxCandidateDiffReviewDispositionResult.model_validate(
                domain_payload
            )
        except ValidationError:
            disposition = None
            blocked_reasons.append("disposition_domain_reconstruction_invalid")

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

        if (
            disposition is None
            or disposition.disposition_status != "computed"
            or disposition.disposition_type != "ESCALATE_TO_HUMAN"
        ):
            blocked_reasons.append("disposition_type_not_human_escalation")
        if (
            action.get("escalation_triggers") != ["high_review_risk"]
            or action.get("evaluated_trigger_kinds") != EVALUATED_TRIGGER_KINDS
            or action.get("deferred_trigger_kinds") != DEFERRED_TRIGGER_KINDS
        ):
            blocked_reasons.append("disposition_trigger_contract_invalid")
        if action.get("actor") != "system":
            blocked_reasons.append("disposition_actor_invalid")
        if action.get("client_request_id") is not None:
            blocked_reasons.append("disposition_client_request_id_invalid")
        if not cls._timezone_aware_iso_datetime(action.get("disposition_created_at")):
            blocked_reasons.append("disposition_timestamp_invalid")
        if not all(action.get(flag) is False for flag in _DISPOSITION_FALSE_FLAGS):
            blocked_reasons.append("disposition_write_boundary_violated")
        if action.get("ai_project_director_total_loop") != "Partial":
            blocked_reasons.append("disposition_write_boundary_violated")

        if blocked_reasons:
            return None
        if (
            disposition is None
            or source_review_message_id is None
            or source_preflight_message_id is None
            or source_diff_message_id is None
            or disposition_id is None
            or review_scope_paths is None
        ):
            return None
        return _ValidatedEscalationDispositionEvidence(
            disposition=disposition,
            source_review_message_id=source_review_message_id,
            source_preflight_message_id=source_preflight_message_id,
            source_diff_message_id=source_diff_message_id,
            disposition_id=disposition_id,
            requested_reviewer_executor=requested_reviewer_executor,
            source_diff_sha256=source_diff_sha256,
            review_prompt_sha256=review_prompt_sha256,
            review_scope_paths=review_scope_paths,
            review_output_schema_version=review_output_schema_version,
            source_review_verdict=source_review_verdict,
            source_review_risk_level=source_review_risk_level,
        )

    @staticmethod
    def _source_review_action(
        *,
        source_review_message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> _NormalizedReviewSource | None:
        if source_review_message is None:
            blocked_reasons.append("source_review_message_missing")
            return None
        if source_review_message.session_id != session_id:
            blocked_reasons.append("source_review_message_session_mismatch")
        if source_review_message.related_task_id != source_task_id:
            blocked_reasons.append("source_review_message_task_mismatch")
        if source_review_message.role != ProjectDirectorMessageRole.ASSISTANT:
            blocked_reasons.append("source_review_message_role_invalid")
        if source_review_message.source != ProjectDirectorMessageSource.SYSTEM:
            blocked_reasons.append("source_review_message_source_invalid")
        if source_review_message.requires_confirmation is not False:
            blocked_reasons.append(
                "source_review_message_confirmation_contract_invalid"
            )
        if (
            source_review_message.risk_level
            != ProjectDirectorMessageRiskLevel.HIGH
        ):
            blocked_reasons.append("source_review_message_risk_level_invalid")

        p25_marked = bool(
            source_review_message.intent == P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT
            or source_review_message.source_detail
            == P25_BOUNDED_REWORK_REVIEW_OUTCOME_SOURCE_DETAIL
            or any(
                isinstance(action, dict)
                and (
                    action.get("type")
                    == P25_BOUNDED_REWORK_REVIEW_OUTCOME_ACTION_TYPE
                    or action.get("schema_version")
                    == P25_BOUNDED_REWORK_REVIEW_OUTCOME_SCHEMA_VERSION
                )
                for action in source_review_message.suggested_actions
            )
        )
        if p25_marked:
            if (
                source_review_message.intent
                != P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT
                or source_review_message.source_detail
                != P25_BOUNDED_REWORK_REVIEW_OUTCOME_SOURCE_DETAIL
                or len(source_review_message.suggested_actions) != 1
                or not isinstance(source_review_message.suggested_actions[0], dict)
                or source_review_message.suggested_actions[0].get("type")
                != P25_BOUNDED_REWORK_REVIEW_OUTCOME_ACTION_TYPE
                or source_review_message.suggested_actions[0].get("schema_version")
                != P25_BOUNDED_REWORK_REVIEW_OUTCOME_SCHEMA_VERSION
            ):
                blocked_reasons.append("p25_h_review_outcome_marker_invalid")
                return None
            action = source_review_message.suggested_actions[0]
            payload = dict(action)
            payload.pop("type", None)
            try:
                outcome = (
                    ProjectDirectorBoundedReworkReviewInvocationOutcome.model_validate(
                        payload
                    )
                )
            except (TypeError, ValueError, ValidationError):
                blocked_reasons.append("p25_h_review_outcome_domain_invalid")
                return None
            if not ProjectDirectorBoundedReworkReviewExecutionService.persisted_review_invocation_outcome_message_is_valid(
                source_review_message,
                outcome,
            ):
                blocked_reasons.append("p25_h_review_outcome_message_invalid")
            if (
                outcome.authority.session_id != session_id
                or outcome.exact_task_id != source_task_id
            ):
                blocked_reasons.append("p25_h_review_outcome_authority_mismatch")
            if (
                outcome.review_outcome_fingerprint != outcome.compute_fingerprint()
                or outcome.review_result_fingerprint
                != ProjectDirectorBoundedReworkReviewExecutionService.rebuild_persisted_review_result_fingerprint(
                    outcome
                )
            ):
                blocked_reasons.append("p25_h_review_outcome_fingerprint_mismatch")
            if (
                outcome.outcome_status != "validated_output"
                or outcome.adapter_result is None
                or outcome.adapter_result.adapter_status != "validated_output"
                or not ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService._is_sha256(
                    outcome.review_semantic_fingerprint
                )
                or outcome.recovery_required is not False
                or outcome.human_escalation_required is not False
                or outcome.safe_error_code is not None
                or outcome.blocked_reasons
            ):
                blocked_reasons.append("p25_h_review_outcome_not_validated")
            return _NormalizedReviewSource(
                source_review_kind="p25_h",
                message=source_review_message,
                action=action,
                outcome=outcome,
            )

        if (
            source_review_message.intent
            != "sandbox_candidate_diff_readonly_review_execution"
        ):
            blocked_reasons.append("source_review_message_intent_invalid")
        if (
            source_review_message.source_detail
            != P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL
        ):
            blocked_reasons.append(
                "source_message_is_not_p21_c_readonly_review_execution"
            )
        if len(source_review_message.suggested_actions) != 1:
            blocked_reasons.append("p21_c_readonly_review_execution_record_missing")
            return None
        action = source_review_message.suggested_actions[0]
        if (
            not isinstance(action, dict)
            or action.get("type")
            != P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE
        ):
            blocked_reasons.append("p21_c_readonly_review_execution_record_missing")
            return None
        return _NormalizedReviewSource(
            source_review_kind="p21_c",
            message=source_review_message,
            action=action,
        )

    @classmethod
    def _strict_review_evidence(
        cls,
        *,
        source_review: _NormalizedReviewSource,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> _ValidatedStrictReviewEvidence | None:
        if source_review.source_review_kind == "p25_h":
            return cls._strict_p25_h_review_evidence(
                source_review=source_review,
                blocked_reasons=blocked_reasons,
            )
        action = source_review.action

        source_preflight_message_id = cls._uuid_from_action(
            action, "source_preflight_message_id"
        )
        source_diff_message_id = cls._uuid_from_action(
            action, "source_diff_message_id"
        )
        requested_reviewer_executor = action.get("requested_reviewer_executor")
        source_diff_sha256 = action.get("source_diff_sha256")
        review_prompt_sha256 = action.get("review_prompt_sha256")
        review_scope_paths = cls._review_scope_paths(action)
        review_output_schema_version = action.get("review_output_schema_version")
        if action.get("session_id") != str(session_id):
            blocked_reasons.append("source_review_action_session_mismatch")
        if action.get("source_task_id") != str(source_task_id):
            blocked_reasons.append("source_review_action_task_mismatch")
        if (
            source_preflight_message_id is None
            or source_diff_message_id is None
            or requested_reviewer_executor not in _VALID_REVIEWER_EXECUTORS
            or not cls._is_sha256(source_diff_sha256)
            or not cls._is_sha256(review_prompt_sha256)
            or review_scope_paths is None
            or review_output_schema_version != REVIEW_OUTPUT_SCHEMA_VERSION
        ):
            blocked_reasons.append("source_review_binding_invalid")

        output_payload = {
            "review_status": action.get("review_status"),
            "verdict": action.get("verdict"),
            "risk_level": action.get("risk_level"),
            "summary": action.get("summary"),
            "findings": action.get("findings"),
            "recommended_next_step": action.get("recommended_next_step"),
        }
        output: ProjectDirectorSandboxCandidateDiffValidatedReviewOutput | None
        try:
            output = ProjectDirectorSandboxCandidateDiffValidatedReviewOutput.model_validate(
                output_payload
            )
        except ValidationError:
            output = None
            blocked_reasons.append("source_review_strict_output_invalid")

        if blocked_reasons:
            return None
        if (
            output is None
            or source_preflight_message_id is None
            or source_diff_message_id is None
            or review_scope_paths is None
        ):
            return None
        return _ValidatedStrictReviewEvidence(
            source_review_kind="p21_c",
            output=output,
            source_preflight_message_id=source_preflight_message_id,
            source_diff_message_id=source_diff_message_id,
            requested_reviewer_executor=requested_reviewer_executor,
            source_diff_sha256=source_diff_sha256,
            review_prompt_sha256=review_prompt_sha256,
            review_scope_paths=review_scope_paths,
            review_output_schema_version=review_output_schema_version,
        )

    @classmethod
    def _strict_p25_h_review_evidence(
        cls,
        *,
        source_review: _NormalizedReviewSource,
        blocked_reasons: list[str],
    ) -> _ValidatedStrictReviewEvidence | None:
        outcome = source_review.outcome
        adapter_result = outcome.adapter_result if outcome is not None else None
        if outcome is None or adapter_result is None:
            blocked_reasons.append("p25_h_review_outcome_not_validated")
            return None

        review_scope_paths = list(outcome.review_scope_paths)
        if (
            outcome.requested_reviewer_executor not in _VALID_REVIEWER_EXECUTORS
            or not cls._is_sha256(outcome.source_candidate_diff_sha256)
            or not cls._is_sha256(outcome.review_prompt_sha256)
            or not review_scope_paths
            or outcome.review_output_schema_version != REVIEW_OUTPUT_SCHEMA_VERSION
        ):
            blocked_reasons.append("source_review_binding_invalid")

        output_payload = {
            "review_status": adapter_result.review_status,
            "verdict": adapter_result.verdict,
            "risk_level": adapter_result.risk_level,
            "summary": adapter_result.summary,
            "findings": [
                finding.model_dump(mode="python")
                for finding in adapter_result.findings
            ],
            "recommended_next_step": adapter_result.recommended_next_step,
        }
        try:
            output = ProjectDirectorSandboxCandidateDiffValidatedReviewOutput.model_validate(
                output_payload
            )
        except ValidationError:
            blocked_reasons.append("source_review_strict_output_invalid")
            return None
        if blocked_reasons:
            return None
        return _ValidatedStrictReviewEvidence(
            source_review_kind="p25_h",
            output=output,
            source_preflight_message_id=outcome.preflight_id,
            source_diff_message_id=outcome.source_candidate_diff_message_id,
            requested_reviewer_executor=outcome.requested_reviewer_executor,
            source_diff_sha256=outcome.source_candidate_diff_sha256,
            review_prompt_sha256=outcome.review_prompt_sha256,
            review_scope_paths=review_scope_paths,
            review_output_schema_version=outcome.review_output_schema_version,
        )

    def _prior_escalation_package_exists(
        self,
        *,
        session_id: UUID,
        source_disposition_message_id: UUID,
        disposition_id: UUID,
        source_review_message_id: UUID,
    ) -> bool:
        if self._message_repository is None:
            raise ValueError("human escalation package repository is required")

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
                    != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_SOURCE_DETAIL
                    or not message.suggested_actions
                ):
                    continue
                first_action = message.suggested_actions[0]
                if not isinstance(first_action, dict) or first_action.get("type") != (
                    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_ACTION_TYPE
                ):
                    continue
                if (
                    first_action.get("source_disposition_message_id")
                    == str(source_disposition_message_id)
                    or first_action.get("disposition_id") == str(disposition_id)
                    or first_action.get("related_review_message_ids")
                    == [str(source_review_message_id)]
                ):
                    return True
            if not has_more or not messages:
                return False
            before_message_id = messages[0].id

    @staticmethod
    def _review_source_binding_matches(
        evidence: _ValidatedEscalationDispositionEvidence,
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
    def _strict_review_binding_matches(
        evidence: _ValidatedEscalationDispositionEvidence,
        review_evidence: _ValidatedStrictReviewEvidence,
    ) -> bool:
        return (
            evidence.source_preflight_message_id
            == review_evidence.source_preflight_message_id
            and evidence.source_diff_message_id
            == review_evidence.source_diff_message_id
            and evidence.requested_reviewer_executor
            == review_evidence.requested_reviewer_executor
            and evidence.source_diff_sha256 == review_evidence.source_diff_sha256
            and evidence.review_prompt_sha256 == review_evidence.review_prompt_sha256
            and evidence.review_scope_paths == review_evidence.review_scope_paths
            and evidence.review_output_schema_version
            == review_evidence.review_output_schema_version
            and evidence.source_review_verdict == review_evidence.output.verdict
            and evidence.source_review_risk_level == review_evidence.output.risk_level
        )

    @staticmethod
    def _aggregate_evidence_fingerprint(
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_disposition_message_id: UUID,
        evidence: _ValidatedEscalationDispositionEvidence,
        revalidation: RevalidatedPersistedReviewResultFingerprint,
        review_evidence: _ValidatedStrictReviewEvidence,
        escalation_scope: str,
        related_task_ids: list[UUID],
        related_review_message_ids: list[UUID],
        unresolved_findings: list[ProjectDirectorSandboxCandidateDiffReviewFinding],
        risk_summary: str,
        proposed_human_decision_scope: str,
    ) -> str:
        canonical_payload = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService._aggregate_evidence_canonical_payload(
            session_id=session_id,
            source_task_id=source_task_id,
            source_disposition_message_id=source_disposition_message_id,
            source_review_message_id=evidence.source_review_message_id,
            source_preflight_message_id=evidence.source_preflight_message_id,
            source_diff_message_id=evidence.source_diff_message_id,
            disposition_id=evidence.disposition_id,
            disposition_type=evidence.disposition.disposition_type,
            disposition_reason=evidence.disposition.disposition_reason,
            review_result_fingerprint=evidence.disposition.review_result_fingerprint,
            revalidated_review_result_fingerprint=(
                revalidation.review_result_fingerprint
            ),
            requested_reviewer_executor=evidence.requested_reviewer_executor,
            source_diff_sha256=evidence.source_diff_sha256,
            review_prompt_sha256=evidence.review_prompt_sha256,
            review_scope_paths=evidence.review_scope_paths,
            review_output_schema_version=evidence.review_output_schema_version,
            source_review_verdict=review_evidence.output.verdict,
            source_review_risk_level=review_evidence.output.risk_level,
            escalation_triggers=evidence.disposition.escalation_triggers,
            escalation_scope=escalation_scope,
            related_task_ids=related_task_ids,
            related_review_message_ids=related_review_message_ids,
            unresolved_findings=unresolved_findings,
            risk_summary=risk_summary,
            proposed_human_decision_scope=proposed_human_decision_scope,
        )
        return ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService._canonical_payload_fingerprint(
            canonical_payload
        )

    @staticmethod
    def _aggregate_evidence_canonical_payload(
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_disposition_message_id: UUID,
        source_review_message_id: UUID | None,
        source_preflight_message_id: UUID | None,
        source_diff_message_id: UUID | None,
        disposition_id: UUID | None,
        disposition_type: str | None,
        disposition_reason: str,
        review_result_fingerprint: str,
        revalidated_review_result_fingerprint: str,
        requested_reviewer_executor: str,
        source_diff_sha256: str,
        review_prompt_sha256: str,
        review_scope_paths: list[str],
        review_output_schema_version: str,
        source_review_verdict: str,
        source_review_risk_level: str,
        escalation_triggers: list[str],
        escalation_scope: str | None,
        related_task_ids: list[UUID],
        related_review_message_ids: list[UUID],
        unresolved_findings: list[ProjectDirectorSandboxCandidateDiffReviewFinding],
        risk_summary: str,
        proposed_human_decision_scope: str | None,
    ) -> dict[str, Any]:
        return {
            "session_id": str(session_id),
            "source_task_id": str(source_task_id),
            "source_disposition_message_id": str(source_disposition_message_id),
            "source_review_message_id": str(source_review_message_id),
            "source_preflight_message_id": str(source_preflight_message_id),
            "source_diff_message_id": str(source_diff_message_id),
            "disposition_id": str(disposition_id),
            "disposition_type": disposition_type,
            "disposition_reason": disposition_reason,
            "review_result_fingerprint": review_result_fingerprint,
            "revalidated_review_result_fingerprint": (
                revalidated_review_result_fingerprint
            ),
            "requested_reviewer_executor": requested_reviewer_executor,
            "source_diff_sha256": source_diff_sha256,
            "review_prompt_sha256": review_prompt_sha256,
            "review_scope_paths": list(review_scope_paths),
            "review_output_schema_version": review_output_schema_version,
            "source_review_verdict": source_review_verdict,
            "source_review_risk_level": source_review_risk_level,
            "escalation_triggers": list(escalation_triggers),
            "escalation_scope": escalation_scope,
            "related_task_ids": [str(task_id) for task_id in related_task_ids],
            "related_review_message_ids": [
                str(message_id) for message_id in related_review_message_ids
            ],
            "unresolved_blocking_findings": [
                finding.model_dump(mode="json") for finding in unresolved_findings
            ],
            "risk_summary": risk_summary,
            "proposed_human_decision_scope": proposed_human_decision_scope,
        }

    @staticmethod
    def _canonical_payload_fingerprint(canonical_payload: dict[str, Any]) -> str:
        canonical_json = json.dumps(
            canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @staticmethod
    def _escalation_package_action(
        *,
        session_id: UUID,
        source_task_id: UUID,
        evidence: _ValidatedEscalationDispositionEvidence,
        result: ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult,
    ) -> dict[str, Any]:
        return {
            "type": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_ACTION_TYPE,
            "schema_version": HUMAN_ESCALATION_PACKAGE_SCHEMA_VERSION,
            "package_status": result.package_status,
            "escalation_package_id": str(result.escalation_package_id),
            "session_id": str(session_id),
            "source_task_id": str(source_task_id),
            "source_disposition_message_id": str(
                result.source_disposition_message_id
            ),
            "source_review_message_id": str(result.source_review_message_id),
            "source_preflight_message_id": str(result.source_preflight_message_id),
            "source_diff_message_id": str(result.source_diff_message_id),
            "disposition_id": str(result.disposition_id),
            "disposition_type": result.disposition_type,
            "disposition_reason": result.disposition_reason,
            "review_result_fingerprint": result.review_result_fingerprint,
            "revalidated_review_result_fingerprint": (
                result.revalidated_review_result_fingerprint
            ),
            "aggregate_evidence_fingerprint": result.aggregate_evidence_fingerprint,
            "requested_reviewer_executor": evidence.requested_reviewer_executor,
            "source_diff_sha256": evidence.source_diff_sha256,
            "review_prompt_sha256": evidence.review_prompt_sha256,
            "review_scope_paths": list(evidence.review_scope_paths),
            "review_output_schema_version": evidence.review_output_schema_version,
            "source_review_verdict": evidence.source_review_verdict,
            "source_review_risk_level": evidence.source_review_risk_level,
            "escalation_triggers": list(result.escalation_triggers),
            "escalation_scope": result.escalation_scope,
            "related_task_ids": [str(value) for value in result.related_task_ids],
            "related_review_message_ids": [
                str(value) for value in result.related_review_message_ids
            ],
            "unresolved_blocking_findings": [
                finding.model_dump(mode="json")
                for finding in result.unresolved_blocking_findings
            ],
            "risk_summary": result.risk_summary,
            "proposed_human_decision_scope": (
                result.proposed_human_decision_scope
            ),
            "source_review_validated": result.source_review_validated,
            "replay_check_completed": result.replay_check_completed,
            "prior_escalation_package_detected": (
                result.prior_escalation_package_detected
            ),
            "package_created_at": result.package_created_at.isoformat(),
            "actor": "system",
            "client_request_id": None,
            "blocked_reasons": list(result.blocked_reasons),
            "continuation_started": False,
            "rework_started": False,
            "human_escalation_package_created": True,
            "human_decision_recorded": False,
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
        source_disposition_message_id: UUID,
        evidence: _ValidatedEscalationDispositionEvidence | None,
        revalidation: RevalidatedPersistedReviewResultFingerprint | None,
        replay_check_completed: bool,
        prior_escalation_package_detected: bool,
        blocked_reasons: list[str],
    ) -> ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult:
        return ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(
            package_status="blocked",
            source_disposition_message_id=source_disposition_message_id,
            source_review_message_id=(
                evidence.source_review_message_id if evidence is not None else None
            ),
            source_preflight_message_id=(
                evidence.source_preflight_message_id if evidence is not None else None
            ),
            source_diff_message_id=(
                evidence.source_diff_message_id if evidence is not None else None
            ),
            disposition_id=evidence.disposition_id if evidence is not None else None,
            disposition_type=(
                evidence.disposition.disposition_type
                if evidence is not None
                else None
            ),
            disposition_reason=(
                evidence.disposition.disposition_reason
                if evidence is not None
                else ""
            ),
            review_result_fingerprint=(
                evidence.disposition.review_result_fingerprint
                if evidence is not None
                else ""
            ),
            revalidated_review_result_fingerprint=(
                revalidation.review_result_fingerprint
                if revalidation is not None
                else ""
            ),
            escalation_triggers=(
                list(evidence.disposition.escalation_triggers)
                if evidence is not None
                else []
            ),
            replay_check_completed=replay_check_completed,
            prior_escalation_package_detected=prior_escalation_package_detected,
            blocked_reasons=ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService._dedupe(
                blocked_reasons
            ),
        )

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
    "HUMAN_ESCALATION_PACKAGE_SCHEMA_VERSION",
    "P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_ACTION_TYPE",
    "P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_SOURCE_DETAIL",
    "PreparedSandboxCandidateDiffReviewHumanEscalationPackage",
    "ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService",
    "RevalidatedPersistedHumanEscalationPackageFingerprint",
)
