"""Real P25-H-A support composed from the committed P25-B through P25-G chain."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.project_director_bounded_rework_review_reentry_preflight_service import (
    ProjectDirectorBoundedReworkReviewReentryPreflightService,
)
from tests.p25_candidate_diff_real_chain_test_support import (
    FreshP25CandidateDiffServices,
    RealP25AttemptZeroCandidateDiffContext,
    build_fresh_candidate_diff_services,
    build_real_p25_attempt_zero_candidate_diff_context,
)


@dataclass(slots=True)
class RealP25AttemptZeroReviewPreflightContext:
    """One real attempt-zero chain through a persisted P25-G candidate diff."""

    candidate_context: RealP25AttemptZeroCandidateDiffContext
    outcome_result: object
    candidate_diff_result: object
    review_preflight_service: ProjectDirectorBoundedReworkReviewReentryPreflightService

    @property
    def session(self):
        return self.candidate_context.session

    @property
    def session_id(self):
        return self.candidate_context.session_id

    @property
    def task_id(self):
        return self.candidate_context.task_id

    @property
    def project_id(self):
        return self.candidate_context.outcome_context.claim_context.project_id

    @property
    def environment(self):
        return self.candidate_context.environment

    @property
    def message_repository(self):
        return self.candidate_context.outcome_context.claim_context.package_context.msg_repo

    def close(self) -> None:
        self.candidate_context.close()


@dataclass(slots=True)
class FreshP25ReviewPreflightServices:
    candidate_services: FreshP25CandidateDiffServices
    review_preflight_service: ProjectDirectorBoundedReworkReviewReentryPreflightService

    @property
    def session(self):
        return self.candidate_services.session

    def close(self) -> None:
        self.candidate_services.close()


def build_real_p25_attempt_zero_review_preflight_context(tmp_path):
    """Create P25-F and P25-G only through their public APIs."""

    candidate_context = build_real_p25_attempt_zero_candidate_diff_context(tmp_path)
    outcome_result = (
        candidate_context.outcome_context.outcome_service.execute_bounded_rework_from_reservation(
            session_id=candidate_context.session_id,
            source_task_id=candidate_context.task_id,
            source_reservation_message_id=(
                candidate_context.outcome_context.claim_context.reservation_result.message.id
            ),
        )
    )
    assert outcome_result.status == "outcome_recorded", outcome_result.blocked_reasons
    assert outcome_result.outcome_message is not None
    candidate_diff_result = candidate_context.candidate_diff_service.regenerate_candidate_manifest_and_diff(
        session_id=candidate_context.session_id,
        source_task_id=candidate_context.task_id,
        source_outcome_message_id=outcome_result.outcome_message.id,
    )
    assert candidate_diff_result.status == "candidate_diff_generated", (
        candidate_diff_result.blocked_reasons
    )
    assert candidate_diff_result.diff_message is not None
    return RealP25AttemptZeroReviewPreflightContext(
        candidate_context=candidate_context,
        outcome_result=outcome_result,
        candidate_diff_result=candidate_diff_result,
        review_preflight_service=(
            ProjectDirectorBoundedReworkReviewReentryPreflightService(
                message_repository=candidate_context.outcome_context.claim_context.package_context.msg_repo,
                candidate_diff_service=candidate_context.candidate_diff_service,
            )
        ),
    )


def build_fresh_review_preflight_services(
    context: RealP25AttemptZeroReviewPreflightContext,
) -> FreshP25ReviewPreflightServices:
    """Rebuild P25-B through P25-H-A dependencies with a fresh Session."""

    candidate_services = build_fresh_candidate_diff_services(context.candidate_context)
    return FreshP25ReviewPreflightServices(
        candidate_services=candidate_services,
        review_preflight_service=ProjectDirectorBoundedReworkReviewReentryPreflightService(
            message_repository=(
                candidate_services.outcome_services.claim_services.reservation_services.message_repository
            ),
            candidate_diff_service=candidate_services.candidate_diff_service,
        ),
    )
