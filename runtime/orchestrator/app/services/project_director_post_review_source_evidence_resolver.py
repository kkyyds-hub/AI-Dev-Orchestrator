"""Resolve exact readonly review evidence for P21-C and P25-H post-review flows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.services.project_director_bounded_rework_review_execution_service import (
    P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT,
    P25_BOUNDED_REWORK_REVIEW_OUTCOME_SOURCE_DETAIL,
    ProjectDirectorBoundedReworkReviewExecutionService,
)


PostReviewSourceKind = Literal["p21_c", "p25_h"]


@dataclass(frozen=True, slots=True)
class ResolvedProjectDirectorPostReviewSourceEvidence:
    source_review_kind: PostReviewSourceKind
    source_review_message_id: UUID
    source_preflight_message_id: UUID | None
    source_diff_message_id: UUID | None
    source_diff_sha256: str
    review_result_fingerprint: str
    review_semantic_fingerprint: str | None
    requested_reviewer_executor: str | None
    review_prompt_sha256: str
    review_scope_paths: tuple[str, ...]
    review_output_schema_version: str
    source_review_verdict: str | None
    source_review_risk_level: str | None
    exact_task_id: UUID | None
    exact_run_id: UUID | None
    workspace_path: str | None
    blocked_reasons: tuple[str, ...]


class ProjectDirectorPostReviewSourceEvidenceResolver:
    """Rebuild P25-H evidence from its public readonly revalidation service."""

    def __init__(
        self,
        *,
        review_execution_service: ProjectDirectorBoundedReworkReviewExecutionService,
    ) -> None:
        self._review_execution_service = review_execution_service
        self._message_repository: ProjectDirectorMessageRepository = (
            review_execution_service._message_repository
        )

    def resolve(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_review_message_id: UUID,
    ) -> ResolvedProjectDirectorPostReviewSourceEvidence:
        message = self._message_repository.get_by_id(source_review_message_id)
        if not self._is_p25_h_outcome_message(message):
            return self._blocked(source_review_message_id, "source_review_kind_unsupported")

        revalidated = (
            self._review_execution_service.revalidate_persisted_review_invocation_outcome(
                session_id=session_id,
                source_task_id=source_task_id,
                source_review_outcome_message_id=source_review_message_id,
            )
        )
        outcome = revalidated.review_outcome
        preflight = revalidated.preflight
        candidate_diff = revalidated.candidate_diff
        candidate_manifest = revalidated.candidate_manifest
        if (
            revalidated.status != "validated_output"
            or outcome is None
            or preflight is None
            or candidate_diff is None
            or candidate_manifest is None
            or outcome.adapter_result is None
        ):
            return self._blocked(
                source_review_message_id,
                *(revalidated.blocked_reasons or ("history_invalid",)),
            )

        if not (
            outcome.outcome_status == "validated_output"
            and outcome.adapter_result.adapter_status == "validated_output"
            and outcome.exact_task_id == source_task_id
            and outcome.authority.session_id == session_id
            and outcome.preflight_id == preflight.preflight_id
            and outcome.preflight_fingerprint == preflight.preflight_fingerprint
            and outcome.source_candidate_diff_message_id
            == candidate_diff.candidate_diff_id
            and outcome.source_candidate_diff_id == candidate_diff.candidate_diff_id
            and outcome.source_candidate_diff_fingerprint
            == candidate_diff.candidate_diff_fingerprint
            and outcome.source_candidate_diff_sha256 == candidate_diff.new_diff_sha256
            and outcome.source_candidate_manifest_id
            == candidate_manifest.candidate_manifest_id
            and outcome.source_candidate_manifest_fingerprint
            == candidate_manifest.candidate_manifest_fingerprint
            and outcome.source_executor_outcome_id == candidate_diff.source_outcome_id
            and outcome.source_attempt_id == candidate_diff.source_attempt_id
            and outcome.source_package_id == candidate_diff.source_package_id
            and outcome.authority == candidate_diff.authority
            and outcome.exact_task_id == candidate_diff.exact_task_id
            and outcome.exact_run_id == candidate_diff.exact_run_id
            and outcome.rework_attempt_index == candidate_diff.rework_attempt_index
        ):
            return self._blocked(source_review_message_id, "history_invalid")

        return ResolvedProjectDirectorPostReviewSourceEvidence(
            source_review_kind="p25_h",
            source_review_message_id=source_review_message_id,
            source_preflight_message_id=preflight.preflight_id,
            source_diff_message_id=candidate_diff.candidate_diff_id,
            source_diff_sha256=candidate_diff.new_diff_sha256,
            review_result_fingerprint=outcome.review_result_fingerprint,
            review_semantic_fingerprint=outcome.review_semantic_fingerprint,
            requested_reviewer_executor=outcome.requested_reviewer_executor,
            review_prompt_sha256=outcome.review_prompt_sha256,
            review_scope_paths=outcome.review_scope_paths,
            review_output_schema_version=outcome.review_output_schema_version,
            source_review_verdict=outcome.adapter_result.verdict,
            source_review_risk_level=outcome.adapter_result.risk_level,
            exact_task_id=outcome.exact_task_id,
            exact_run_id=outcome.exact_run_id,
            workspace_path=preflight.workspace_path,
            blocked_reasons=(),
        )

    @staticmethod
    def _is_p25_h_outcome_message(message: object) -> bool:
        return bool(
            message is not None
            and getattr(message, "intent", None)
            == P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT
            and getattr(message, "source_detail", None)
            == P25_BOUNDED_REWORK_REVIEW_OUTCOME_SOURCE_DETAIL
        )

    @staticmethod
    def _blocked(
        source_review_message_id: UUID,
        *blocked_reasons: str,
    ) -> ResolvedProjectDirectorPostReviewSourceEvidence:
        return ResolvedProjectDirectorPostReviewSourceEvidence(
            source_review_kind="p25_h",
            source_review_message_id=source_review_message_id,
            source_preflight_message_id=None,
            source_diff_message_id=None,
            source_diff_sha256="",
            review_result_fingerprint="",
            review_semantic_fingerprint=None,
            requested_reviewer_executor=None,
            review_prompt_sha256="",
            review_scope_paths=(),
            review_output_schema_version="",
            source_review_verdict=None,
            source_review_risk_level=None,
            exact_task_id=None,
            exact_run_id=None,
            workspace_path=None,
            blocked_reasons=tuple(dict.fromkeys(blocked_reasons)),
        )


__all__ = (
    "ProjectDirectorPostReviewSourceEvidenceResolver",
    "ResolvedProjectDirectorPostReviewSourceEvidence",
)
