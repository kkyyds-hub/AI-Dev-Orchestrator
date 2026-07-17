"""Real P25-G support composed from the committed P25-B/D/E/F chain."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.project_director_bounded_rework_candidate_diff_service import (
    ProjectDirectorBoundedReworkCandidateDiffService,
)
from app.services.project_director_sandbox_candidate_diff_service import (
    ProjectDirectorSandboxCandidateDiffService,
)
from tests.p25_outcome_real_chain_test_support import (
    FreshP25OutcomeServices,
    RealP25AttemptZeroOutcomeContext,
    build_fresh_outcome_services,
    build_real_p25_attempt_zero_outcome_context,
)


@dataclass(slots=True)
class RealP25AttemptZeroCandidateDiffContext:
    outcome_context: RealP25AttemptZeroOutcomeContext
    candidate_diff_service: ProjectDirectorBoundedReworkCandidateDiffService

    @property
    def session(self):
        return self.outcome_context.session

    @property
    def session_id(self):
        return self.outcome_context.session_id

    @property
    def task_id(self):
        return self.outcome_context.task_id

    @property
    def environment(self):
        return self.outcome_context.environment

    def close(self) -> None:
        self.outcome_context.close()


@dataclass(slots=True)
class FreshP25CandidateDiffServices:
    outcome_services: FreshP25OutcomeServices
    candidate_diff_service: ProjectDirectorBoundedReworkCandidateDiffService

    @property
    def session(self):
        return self.outcome_services.session

    def close(self) -> None:
        self.outcome_services.close()


def build_real_p25_attempt_zero_candidate_diff_context(tmp_path, *, executor=None):
    """Compose P25-G without seeding any candidate manifest or diff evidence."""

    outcome_context = build_real_p25_attempt_zero_outcome_context(
        tmp_path, executor=executor
    )
    return RealP25AttemptZeroCandidateDiffContext(
        outcome_context=outcome_context,
        candidate_diff_service=ProjectDirectorBoundedReworkCandidateDiffService(
            message_repository=outcome_context.claim_context.package_context.msg_repo,
            claim_service=outcome_context.claim_context.claim_service,
            candidate_diff_service=ProjectDirectorSandboxCandidateDiffService(),
        ),
    )


def build_fresh_candidate_diff_services(
    context: RealP25AttemptZeroCandidateDiffContext,
) -> FreshP25CandidateDiffServices:
    """Reconstruct P25-B/D/E/F/G dependencies with a fresh database Session."""

    outcome_services = build_fresh_outcome_services(context.outcome_context)
    return FreshP25CandidateDiffServices(
        outcome_services=outcome_services,
        candidate_diff_service=ProjectDirectorBoundedReworkCandidateDiffService(
            message_repository=(
                outcome_services.claim_services.reservation_services.message_repository
            ),
            claim_service=outcome_services.claim_services.claim_service,
            candidate_diff_service=ProjectDirectorSandboxCandidateDiffService(),
        ),
    )
