"""Real P25-I support composed from the committed P25-B through P25-H-C chain."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from app.services.project_director_bounded_rework_convergence_service import (
    ProjectDirectorBoundedReworkConvergenceService,
)
from app.services.project_director_bounded_rework_post_review_orchestration_service import (
    ProjectDirectorBoundedReworkPostReviewOrchestrationService,
)
from tests.p25_post_review_real_chain_test_support import (
    RealP25AttemptZeroPostReviewContext,
    _build_post_review_services,
    build_real_p25_attempt_zero_post_review_context,
)
from tests.p25_review_execution_real_chain_test_support import (
    FreshP25ReviewExecutionServices,
    build_fresh_review_execution_services,
)


@dataclass(slots=True)
class RealP25AttemptZeroConvergenceContext:
    post_review_context: RealP25AttemptZeroPostReviewContext
    h_c_result: object
    convergence_service: ProjectDirectorBoundedReworkConvergenceService

    @property
    def session(self):
        return self.post_review_context.session

    @property
    def session_id(self):
        return self.post_review_context.session_id

    @property
    def task_id(self):
        return self.post_review_context.task_id

    def close(self) -> None:
        self.post_review_context.close()


@dataclass(slots=True)
class FreshP25ConvergenceServices:
    review_execution_services: FreshP25ReviewExecutionServices
    post_review_automation_service: object
    orchestration_service: ProjectDirectorBoundedReworkPostReviewOrchestrationService
    convergence_service: ProjectDirectorBoundedReworkConvergenceService

    @property
    def session(self):
        return self.review_execution_services.session

    @property
    def message_repository(self):
        return (
            self.review_execution_services.review_preflight_services.candidate_services
            .outcome_services.claim_services.reservation_services.message_repository
        )

    def close(self) -> None:
        self.review_execution_services.close()


def build_real_p25_attempt_zero_convergence_context(tmp_path):
    """Create P25-B through P25-H-C only through their public APIs."""

    post_review_context = build_real_p25_attempt_zero_post_review_context(tmp_path)
    h_c_result = post_review_context.orchestration_service.orchestrate_fresh_post_review(
        session_id=post_review_context.session_id,
        source_task_id=post_review_context.task_id,
        source_review_outcome_message_id=(
            post_review_context.h_b_result.review_outcome_message.id
        ),
    )
    assert h_c_result.status == "post_review_orchestrated", h_c_result.blocked_reasons
    assert h_c_result.p22_summary is not None
    assert h_c_result.p22_summary_message is not None

    review_execution_context = post_review_context.review_execution_context
    candidate_context = review_execution_context.review_preflight_context.candidate_context
    return RealP25AttemptZeroConvergenceContext(
        post_review_context=post_review_context,
        h_c_result=h_c_result,
        convergence_service=ProjectDirectorBoundedReworkConvergenceService(
            message_repository=post_review_context.message_repository,
            candidate_diff_service=candidate_context.candidate_diff_service,
            review_execution_service=review_execution_context.review_execution_service,
            post_review_automation_service=(
                post_review_context.post_review_automation_service
            ),
        ),
    )


def build_fresh_convergence_services(
    context: RealP25AttemptZeroConvergenceContext,
) -> FreshP25ConvergenceServices:
    """Rebuild the P25-B through P25-H-C graph with a new Session."""

    review_execution_services = build_fresh_review_execution_services(
        context.post_review_context.review_execution_context
    )
    message_repository = (
        review_execution_services.review_preflight_services.candidate_services
        .outcome_services.claim_services.reservation_services.message_repository
    )
    disposition_service, post_review_automation_service = _build_post_review_services(
        SimpleNamespace(
            session=review_execution_services.session,
            message_repository=message_repository,
            review_execution_service=review_execution_services.review_execution_service,
        )
    )
    orchestration_service = ProjectDirectorBoundedReworkPostReviewOrchestrationService(
        review_execution_service=review_execution_services.review_execution_service,
        disposition_service=disposition_service,
        post_review_automation_service=post_review_automation_service,
    )
    return FreshP25ConvergenceServices(
        review_execution_services=review_execution_services,
        post_review_automation_service=post_review_automation_service,
        orchestration_service=orchestration_service,
        convergence_service=ProjectDirectorBoundedReworkConvergenceService(
            message_repository=(
                review_execution_services.review_preflight_services.candidate_services
                .outcome_services.claim_services.reservation_services.message_repository
            ),
            candidate_diff_service=(
                review_execution_services.review_preflight_services.candidate_services
                .candidate_diff_service
            ),
            review_execution_service=review_execution_services.review_execution_service,
            post_review_automation_service=post_review_automation_service,
        ),
    )
