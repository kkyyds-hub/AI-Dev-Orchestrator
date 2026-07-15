"""Orchestrate fresh P25-H review disposition and existing P22 evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.domain.project_director_bounded_rework_review_reentry import (
    ProjectDirectorBoundedReworkReviewInvocationOutcome,
)
from app.domain.project_director_message import ProjectDirectorMessage
from app.domain.project_director_post_review_automation import (
    ProjectDirectorPostReviewAutomationResult,
)
from app.domain.project_director_sandbox_candidate_diff_review_disposition import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionResult,
)
from app.services.project_director_bounded_rework_review_execution_service import (
    ProjectDirectorBoundedReworkReviewExecutionService,
)
from app.services.project_director_post_review_automation_service import (
    ProjectDirectorPostReviewAutomationService,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_service import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionService,
)


BoundedReworkPostReviewOrchestrationStatus = Literal[
    "post_review_orchestrated",
    "post_review_replayed",
    "blocked",
    "recovery_required",
]


@dataclass(frozen=True, slots=True)
class OrchestratedProjectDirectorBoundedReworkPostReview:
    status: BoundedReworkPostReviewOrchestrationStatus
    source_review_outcome: ProjectDirectorBoundedReworkReviewInvocationOutcome | None
    source_review_outcome_message: ProjectDirectorMessage | None
    disposition: ProjectDirectorSandboxCandidateDiffReviewDispositionResult | None
    disposition_message: ProjectDirectorMessage | None
    p22_summary: ProjectDirectorPostReviewAutomationResult | None
    p22_summary_message: ProjectDirectorMessage | None
    blocked_reasons: tuple[str, ...]


class ProjectDirectorBoundedReworkPostReviewOrchestrationService:
    """Connect one exact validated P25-H outcome to P21-D and P22."""

    def __init__(
        self,
        *,
        review_execution_service: ProjectDirectorBoundedReworkReviewExecutionService,
        disposition_service: ProjectDirectorSandboxCandidateDiffReviewDispositionService,
        post_review_automation_service: ProjectDirectorPostReviewAutomationService,
    ) -> None:
        self._review_execution_service = review_execution_service
        self._disposition_service = disposition_service
        self._post_review_automation_service = post_review_automation_service
        if (
            review_execution_service._message_repository
            is not disposition_service._message_repository
            or post_review_automation_service._disposition_service
            is not disposition_service
        ):
            raise ValueError("P25-H-C dependencies must share disposition evidence")

    def orchestrate_fresh_post_review(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_review_outcome_message_id: UUID,
    ) -> OrchestratedProjectDirectorBoundedReworkPostReview:
        revalidated = self._review_execution_service.revalidate_persisted_review_invocation_outcome(
            session_id=session_id,
            source_task_id=source_task_id,
            source_review_outcome_message_id=source_review_outcome_message_id,
        )
        if revalidated.status != "validated_output":
            return OrchestratedProjectDirectorBoundedReworkPostReview(
                status=(
                    "recovery_required"
                    if revalidated.status == "recovery_required"
                    else "blocked"
                ),
                source_review_outcome=revalidated.review_outcome,
                source_review_outcome_message=revalidated.review_outcome_message,
                disposition=None,
                disposition_message=None,
                p22_summary=None,
                p22_summary_message=None,
                blocked_reasons=revalidated.blocked_reasons,
            )

        disposition = self._disposition_service.compute_candidate_diff_review_disposition(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_review_outcome_message_id,
        )
        if disposition.result.disposition_status != "computed":
            return OrchestratedProjectDirectorBoundedReworkPostReview(
                status="blocked",
                source_review_outcome=revalidated.review_outcome,
                source_review_outcome_message=revalidated.review_outcome_message,
                disposition=disposition.result,
                disposition_message=disposition.message,
                p22_summary=None,
                p22_summary_message=None,
                blocked_reasons=tuple(disposition.result.blocked_reasons),
            )

        p22 = self._post_review_automation_service.orchestrate_post_review(
            session_id=session_id,
            source_task_id=source_task_id,
            source_review_message_id=source_review_outcome_message_id,
        )
        if p22.result.orchestration_status == "blocked":
            status: BoundedReworkPostReviewOrchestrationStatus = "blocked"
        elif p22.result.resumed_from_existing_evidence:
            status = "post_review_replayed"
        else:
            status = "post_review_orchestrated"
        return OrchestratedProjectDirectorBoundedReworkPostReview(
            status=status,
            source_review_outcome=revalidated.review_outcome,
            source_review_outcome_message=revalidated.review_outcome_message,
            disposition=disposition.result,
            disposition_message=disposition.message,
            p22_summary=p22.result,
            p22_summary_message=p22.message,
            blocked_reasons=tuple(p22.result.blocked_reasons),
        )


__all__ = (
    "OrchestratedProjectDirectorBoundedReworkPostReview",
    "ProjectDirectorBoundedReworkPostReviewOrchestrationService",
)
