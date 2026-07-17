"""Real P25-H-C support composed from the committed P25-B through P25-H-B chain."""

from __future__ import annotations

from dataclasses import dataclass

from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_bounded_rework_post_review_orchestration_service import (
    ProjectDirectorBoundedReworkPostReviewOrchestrationService,
)
from app.services.project_director_post_review_automation_service import (
    ProjectDirectorPostReviewAutomationService,
)
from app.services.project_director_post_review_source_evidence_resolver import (
    ProjectDirectorPostReviewSourceEvidenceResolver,
)
from app.services.project_director_protected_transition_evidence_freshness_service import (
    ProjectDirectorProtectedTransitionEvidenceFreshnessService,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_consumption_preflight_service import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightService,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_consumption_service import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionService,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_handoff_service import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_service import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionService,
)
from app.services.project_director_sandbox_candidate_diff_review_human_escalation_package_service import (
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService,
)
from tests.p23_test_support import _StubDiff, _StubHandoff
from tests.p25_review_execution_real_chain_test_support import (
    RealP25AttemptZeroReviewExecutionContext,
    build_real_p25_attempt_zero_review_execution_context,
)


@dataclass(slots=True)
class RealP25AttemptZeroPostReviewContext:
    review_execution_context: RealP25AttemptZeroReviewExecutionContext
    h_b_result: object
    disposition_service: ProjectDirectorSandboxCandidateDiffReviewDispositionService
    post_review_automation_service: ProjectDirectorPostReviewAutomationService
    orchestration_service: ProjectDirectorBoundedReworkPostReviewOrchestrationService

    @property
    def session(self):
        return self.review_execution_context.session

    @property
    def session_id(self):
        return self.review_execution_context.session_id

    @property
    def task_id(self):
        return self.review_execution_context.task_id

    @property
    def message_repository(self):
        return self.review_execution_context.message_repository

    @property
    def transport(self):
        return self.review_execution_context.transport

    @property
    def executor(self):
        return self.review_execution_context.review_preflight_context.candidate_context.outcome_context.executor

    def close(self) -> None:
        self.review_execution_context.close()


def _build_post_review_services(context: RealP25AttemptZeroReviewExecutionContext):
    message_repository = context.message_repository
    session_repository = ProjectDirectorSessionRepository(context.session)
    task_repository = TaskRepository(context.session)
    disposition_service = ProjectDirectorSandboxCandidateDiffReviewDispositionService(
        session_repository=session_repository,
        message_repository=message_repository,
    )
    source_evidence_resolver = ProjectDirectorPostReviewSourceEvidenceResolver(
        review_execution_service=context.review_execution_service,
    )
    post_review_automation_service = ProjectDirectorPostReviewAutomationService(
        session_repository=session_repository,
        message_repository=message_repository,
        task_repository=task_repository,
        disposition_service=disposition_service,
        preflight_service=(
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightService(
                session_repository=session_repository,
                message_repository=message_repository,
            )
        ),
        consumption_service=(
            ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionService(
                session_repository=session_repository,
                message_repository=message_repository,
                task_repository=task_repository,
                review_handoff_service=_StubHandoff(),
                candidate_diff_service=_StubDiff(),
            )
        ),
        handoff_service=(
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService(
                session_repository=session_repository,
                message_repository=message_repository,
                task_repository=task_repository,
            )
        ),
        human_escalation_package_service=(
            ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService(
                session_repository=session_repository,
                message_repository=message_repository,
                task_repository=task_repository,
            )
        ),
        freshness_service=ProjectDirectorProtectedTransitionEvidenceFreshnessService(
            session_repository=session_repository,
            message_repository=message_repository,
            task_repository=task_repository,
            review_handoff_service=_StubHandoff(),
            candidate_diff_service=_StubDiff(),
        ),
    )
    return disposition_service, post_review_automation_service


def build_real_p25_attempt_zero_post_review_context(tmp_path):
    review_execution_context = build_real_p25_attempt_zero_review_execution_context(tmp_path)
    h_b_result = review_execution_context.review_execution_service.execute_claimed_readonly_review(
        session_id=review_execution_context.session_id,
        source_task_id=review_execution_context.task_id,
        source_review_claim_message_id=(
            review_execution_context.h_a_result.review_claim_message.id
        ),
    )
    assert h_b_result.status == "review_outcome_persisted", h_b_result.blocked_reasons
    assert h_b_result.review_outcome is not None
    assert h_b_result.review_outcome.outcome_status == "validated_output"

    disposition_service, post_review_automation_service = _build_post_review_services(
        review_execution_context
    )
    return RealP25AttemptZeroPostReviewContext(
        review_execution_context=review_execution_context,
        h_b_result=h_b_result,
        disposition_service=disposition_service,
        post_review_automation_service=post_review_automation_service,
        orchestration_service=ProjectDirectorBoundedReworkPostReviewOrchestrationService(
            review_execution_service=review_execution_context.review_execution_service,
            disposition_service=disposition_service,
            post_review_automation_service=post_review_automation_service,
        ),
    )
