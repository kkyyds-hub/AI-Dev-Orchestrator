"""Pure persisted P25-H Outcome validation for readonly evidence consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.domain.project_director_bounded_rework_contract import (
    compute_p25_contract_sha256,
)
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
from app.domain.project_director_sandbox_candidate_diff_readonly_reviewer_adapter import (
    ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)


P25_BOUNDED_REWORK_REVIEW_OUTCOME_SOURCE_DETAIL = (
    "p25_h_bounded_rework_review_invocation_outcome_persisted"
)
P25_BOUNDED_REWORK_REVIEW_OUTCOME_ACTION_TYPE = (
    "p25_h_bounded_rework_review_invocation_outcome_record"
)
P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT = (
    "bounded_rework_review_reentry_invocation_outcome"
)

_P25_H_OUTCOME_FALSE_BOUNDARIES = (
    "provider_called=false",
    "main_project_write_allowed=false",
    "product_runtime_git_write_allowed=false",
    "patch_apply_allowed=false",
    "git_write_allowed=false",
    "task_created=false",
    "run_created=false",
)


@dataclass(frozen=True, slots=True)
class RevalidatedProjectDirectorBoundedReworkReviewOutcomeEvidence:
    outcome: ProjectDirectorBoundedReworkReviewInvocationOutcome | None
    message: ProjectDirectorMessage | None
    blocked_reasons: tuple[str, ...]


class ProjectDirectorBoundedReworkReviewOutcomeEvidenceAdapter:
    """Validate a persisted P25-H Outcome without service-level dependencies."""

    def __init__(self, *, message_repository: ProjectDirectorMessageRepository) -> None:
        self._message_repository = message_repository

    def load_validated_outcome(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        source_task_id: UUID,
        source_review_outcome_message_id: UUID,
    ) -> RevalidatedProjectDirectorBoundedReworkReviewOutcomeEvidence:
        message = self._message_repository.get_by_id(source_review_outcome_message_id)
        try:
            action = self._exact_outcome_action(
                message,
                session_id=session_id,
                project_id=project_id,
                source_task_id=source_task_id,
            )
            outcome = ProjectDirectorBoundedReworkReviewInvocationOutcome.model_validate(
                {name: action.get(name) for name in ProjectDirectorBoundedReworkReviewInvocationOutcome.model_fields}
            )
            if not self._outcome_message_is_valid(message, outcome):
                raise ValueError("P25-H Outcome message does not match its Domain record")
            if not self._validated_output_is_safe(outcome):
                raise ValueError("P25-H Outcome is not validated output")
            return RevalidatedProjectDirectorBoundedReworkReviewOutcomeEvidence(
                outcome=outcome,
                message=message,
                blocked_reasons=(),
            )
        except (TypeError, ValueError, ValidationError):
            return RevalidatedProjectDirectorBoundedReworkReviewOutcomeEvidence(
                outcome=None,
                message=None,
                blocked_reasons=("history_invalid",),
            )

    @staticmethod
    def _exact_outcome_action(
        message: ProjectDirectorMessage | None,
        *,
        session_id: UUID,
        project_id: UUID,
        source_task_id: UUID,
    ) -> dict[str, Any]:
        if (
            message is None
            or message.session_id != session_id
            or message.related_project_id != project_id
            or message.related_task_id != source_task_id
            or message.role != ProjectDirectorMessageRole.ASSISTANT
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent != P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT
            or message.source_detail != P25_BOUNDED_REWORK_REVIEW_OUTCOME_SOURCE_DETAIL
            or message.requires_confirmation is not False
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
            or message.token_count is not None
            or message.estimated_cost is not None
            or len(message.suggested_actions) != 1
            or not isinstance(message.suggested_actions[0], dict)
            or message.suggested_actions[0].get("type")
            != P25_BOUNDED_REWORK_REVIEW_OUTCOME_ACTION_TYPE
            or message.suggested_actions[0].get("schema_version")
            != P25_BOUNDED_REWORK_REVIEW_OUTCOME_SCHEMA_VERSION
        ):
            raise ValueError("P25-H Outcome message metadata is invalid")
        return message.suggested_actions[0]

    @staticmethod
    def _validated_output_is_safe(
        outcome: ProjectDirectorBoundedReworkReviewInvocationOutcome,
    ) -> bool:
        adapter = outcome.adapter_result
        if (
            outcome.outcome_status != "validated_output"
            or adapter is None
            or adapter.adapter_status != "validated_output"
            or outcome.safe_error_code is not None
            or outcome.blocked_reasons
            or outcome.recovery_required
            or outcome.human_escalation_required
            or outcome.review_semantic_fingerprint is None
            or outcome.rework_attempt_limit != 3
        ):
            return False
        try:
            canonical_adapter = (
                ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult.model_validate(
                    adapter.model_dump(mode="python")
                )
            )
        except (TypeError, ValueError, ValidationError):
            return False
        return bool(
            canonical_adapter == adapter
            and canonical_adapter.strict_json_valid
            and canonical_adapter.schema_valid
            and canonical_adapter.semantics_valid
            and canonical_adapter.evidence_scope_valid
            and canonical_adapter.review_status == "reviewed"
            and canonical_adapter.output_validation_status == "validated"
            and canonical_adapter.transport_status == "completed"
            and canonical_adapter.transport_invoked
            and canonical_adapter.verdict is not None
            and canonical_adapter.risk_level is not None
            and not canonical_adapter.provider_called
            and outcome.review_result_fingerprint
            == ProjectDirectorBoundedReworkReviewOutcomeEvidenceAdapter._review_result_fingerprint(
                outcome
            )
            and outcome.review_semantic_fingerprint
            == ProjectDirectorBoundedReworkReviewOutcomeEvidenceAdapter._semantic_fingerprint(
                adapter=canonical_adapter,
                source_candidate_diff_sha256=outcome.source_candidate_diff_sha256,
                review_scope_paths=outcome.review_scope_paths,
            )
        )

    @staticmethod
    def _review_result_fingerprint(
        outcome: ProjectDirectorBoundedReworkReviewInvocationOutcome,
    ) -> str:
        return compute_p25_contract_sha256(
            {
                "review_attempt_id": outcome.review_attempt_id,
                "review_attempt_fingerprint": outcome.review_attempt_fingerprint,
                "review_claim_id": outcome.review_claim_id,
                "review_claim_fingerprint": outcome.review_claim_fingerprint,
                "preflight_id": outcome.preflight_id,
                "preflight_fingerprint": outcome.preflight_fingerprint,
                "source_candidate_diff_id": outcome.source_candidate_diff_id,
                "source_candidate_diff_fingerprint": outcome.source_candidate_diff_fingerprint,
                "source_candidate_diff_sha256": outcome.source_candidate_diff_sha256,
                "review_prompt_sha256": outcome.review_prompt_sha256,
                "review_prompt_bytes": outcome.review_prompt_bytes,
                "requested_reviewer_executor": outcome.requested_reviewer_executor,
                "authority": outcome.authority,
                "exact_task_id": outcome.exact_task_id,
                "exact_run_id": outcome.exact_run_id,
                "rework_attempt_index": outcome.rework_attempt_index,
                "review_scope_paths": outcome.review_scope_paths,
                "adapter_result": (
                    outcome.adapter_result.model_dump(mode="python")
                    if outcome.adapter_result is not None
                    else None
                ),
                "safe_error_code": outcome.safe_error_code,
            }
        )

    @staticmethod
    def _semantic_fingerprint(
        *,
        adapter: ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult,
        source_candidate_diff_sha256: str,
        review_scope_paths: tuple[str, ...],
    ) -> str:
        findings = [
            {
                "finding_id": finding.finding_id,
                "severity": finding.severity,
                "title": finding.title,
                "summary": finding.summary,
                "evidence_paths": sorted(finding.evidence_paths),
                "recommended_action": finding.recommended_action,
            }
            for finding in adapter.findings
        ]
        findings.sort(key=compute_p25_contract_sha256)
        return compute_p25_contract_sha256(
            {
                "verdict": adapter.verdict,
                "risk_level": adapter.risk_level,
                "summary": adapter.summary,
                "findings": findings,
                "recommended_next_step": adapter.recommended_next_step,
                "review_scope_paths": review_scope_paths,
                "source_candidate_diff_sha256": source_candidate_diff_sha256,
            }
        )

    @staticmethod
    def _outcome_message_is_valid(
        message: ProjectDirectorMessage | None,
        outcome: ProjectDirectorBoundedReworkReviewInvocationOutcome,
    ) -> bool:
        if message is None:
            return False
        expected_action = {
            "type": P25_BOUNDED_REWORK_REVIEW_OUTCOME_ACTION_TYPE,
            **outcome.model_dump(mode="json"),
        }
        verdict = (
            f" verdict {outcome.adapter_result.verdict}"
            if outcome.adapter_result is not None
            and outcome.adapter_result.verdict is not None
            else ""
        )
        summary = (
            "validated_review_output"
            if outcome.outcome_status == "validated_output"
            else "review_output_blocked"
            if outcome.outcome_status == "blocked"
            else "reviewer_execution_raised"
        )
        return bool(
            message.id == outcome.review_outcome_id
            and message.created_at == outcome.created_at
            and message.session_id == outcome.authority.session_id
            and message.related_project_id == outcome.authority.project_id
            and message.related_task_id == outcome.exact_task_id
            and message.content
            == (
                "P25 bounded rework review outcome persisted: "
                f"{outcome.review_outcome_id} attempt {outcome.review_attempt_id} "
                f"status {outcome.outcome_status}{verdict} summary {summary}"
            )
            and message.suggested_actions == [expected_action]
            and tuple(message.forbidden_actions_detected)
            == _P25_H_OUTCOME_FALSE_BOUNDARIES
        )
