"""Real P25-D reservation support built on the committed P25-B chain."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.repositories.project_director_repository_binding_config_repository import (
    ProjectDirectorRepositoryBindingConfigRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.project_director_skill_binding_config_repository import (
    ProjectDirectorSkillBindingConfigRepository,
)
from app.repositories.project_director_verification_config_repository import (
    ProjectDirectorVerificationConfigRepository,
)
from app.repositories.repository_workspace_repository import RepositoryWorkspaceRepository
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.project_director_bounded_rework_attempt_reservation_service import (
    ProjectDirectorBoundedReworkAttemptReservationService,
)
from app.services.project_director_bounded_rework_evidence_resolver import (
    ProjectDirectorBoundedReworkEvidenceResolver,
)
from app.services.project_director_bounded_rework_package_preparation_service import (
    ProjectDirectorBoundedReworkPackagePreparationService,
)
from app.services.project_director_protected_transition_dispatch_consumption_preflight_service import (
    ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService,
)
from app.services.project_director_protected_transition_dispatch_consumption_service import (
    ProjectDirectorProtectedTransitionDispatchConsumptionService,
)
from app.services.project_director_protected_transition_dispatch_intent_service import (
    ProjectDirectorProtectedTransitionDispatchIntentService,
)
from app.services.project_director_protected_transition_evidence_freshness_service import (
    ProjectDirectorProtectedTransitionEvidenceFreshnessService,
)
from app.services.project_director_protected_transition_worker_invocation_service import (
    ProjectDirectorProtectedTransitionWorkerInvocationService,
)
from app.services.project_director_protected_transition_worker_start_reservation_service import (
    ProjectDirectorProtectedTransitionWorkerStartReservationService,
)
from tests.p23_test_support import (
    FakeBudgetGuardService,
    FakeTaskReadinessService,
    FakeTaskStateMachineService,
    FakeTaskWorker,
)
from tests.p25_package_real_chain_test_support import (
    RealP25AttemptZeroPackageContext,
    _P25EvidenceDiff,
    _P25EvidenceHandoff,
    P25FakeTaskRouterService,
    build_real_p25_attempt_zero_package_context,
)


@dataclass(slots=True)
class RealP25AttemptZeroReservationContext:
    package_context: RealP25AttemptZeroPackageContext
    reservation_service: ProjectDirectorBoundedReworkAttemptReservationService

    @property
    def session(self):
        return self.package_context.session

    @property
    def msg_repo(self):
        return self.package_context.msg_repo

    @property
    def package_service(self):
        return self.package_context.package_service

    def close(self) -> None:
        self.package_context.close()


def _build_services(
    context: RealP25AttemptZeroPackageContext,
    *,
    session: object,
) -> tuple[
    ProjectDirectorBoundedReworkPackagePreparationService,
    ProjectDirectorBoundedReworkAttemptReservationService,
    object,
]:
    msg_repo = context.msg_repo.__class__(session)
    session_repo = ProjectDirectorSessionRepository(session)
    task_repo = TaskRepository(session)
    run_repo = RunRepository(session)
    agent_session_repo = AgentSessionRepository(session)
    environment = context.environment
    root_diff_service = _P25EvidenceDiff(environment)
    root_handoff_service = _P25EvidenceHandoff(environment)
    root_intent_service = ProjectDirectorProtectedTransitionDispatchIntentService(
        session_repository=session_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
    )
    freshness_service = ProjectDirectorProtectedTransitionEvidenceFreshnessService(
        session_repository=session_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        review_handoff_service=root_handoff_service,
        candidate_diff_service=root_diff_service,
    )
    preflight_service = ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService(
        session_repository=session_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        dispatch_intent_service=root_intent_service,
        freshness_service=freshness_service,
        task_readiness_service=FakeTaskReadinessService(),
        task_state_machine_service=FakeTaskStateMachineService(),
        budget_guard_service=FakeBudgetGuardService(session=session),
    )
    consumption_service = ProjectDirectorProtectedTransitionDispatchConsumptionService(
        session_repository=session_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        run_repository=run_repo,
        preflight_service=preflight_service,
        task_readiness_service=FakeTaskReadinessService(),
        task_state_machine_service=FakeTaskStateMachineService(),
        task_router_service=P25FakeTaskRouterService(),
        budget_guard_service=FakeBudgetGuardService(session=session),
    )
    worker_start_service = ProjectDirectorProtectedTransitionWorkerStartReservationService(
        session_repository=session_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        run_repository=run_repo,
        agent_session_repository=agent_session_repo,
        dispatch_consumption_service=consumption_service,
        freshness_service=freshness_service,
        budget_guard_service=FakeBudgetGuardService(session=session),
    )
    worker_invocation_service = ProjectDirectorProtectedTransitionWorkerInvocationService(
        session_repository=session_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        run_repository=run_repo,
        agent_session_repository=agent_session_repo,
        worker_start_reservation_service=worker_start_service,
        freshness_service=freshness_service,
        task_worker=FakeTaskWorker(session=session),
    )
    evidence_resolver = ProjectDirectorBoundedReworkEvidenceResolver(
        message_repository=msg_repo,
        task_repository=task_repo,
        run_repository=run_repo,
        plan_version_repository=ProjectDirectorPlanVersionRepository(session),
        repository_binding_config_repository=ProjectDirectorRepositoryBindingConfigRepository(session),
        skill_binding_config_repository=ProjectDirectorSkillBindingConfigRepository(session),
        verification_config_repository=ProjectDirectorVerificationConfigRepository(session),
        repository_workspace_repository=RepositoryWorkspaceRepository(session),
        freshness_service=freshness_service,
    )
    package_service = ProjectDirectorBoundedReworkPackagePreparationService(
        message_repository=msg_repo,
        dispatch_consumption_service=consumption_service,
        dispatch_intent_service=root_intent_service,
        evidence_resolver=evidence_resolver,
    )
    reservation_service = ProjectDirectorBoundedReworkAttemptReservationService(
        message_repository=msg_repo,
        task_repository=task_repo,
        run_repository=run_repo,
        package_preparation_service=package_service,
        worker_start_reservation_service=worker_start_service,
        worker_invocation_service=worker_invocation_service,
    )
    return package_service, reservation_service, msg_repo


def build_real_p25_attempt_zero_reservation_context(
    tmp_path: Path,
) -> RealP25AttemptZeroReservationContext:
    package_context = build_real_p25_attempt_zero_package_context(tmp_path)
    _, reservation_service, _ = _build_services(
        package_context,
        session=package_context.session,
    )
    return RealP25AttemptZeroReservationContext(
        package_context=package_context,
        reservation_service=reservation_service,
    )


def rebuild_reservation_service_with_new_session(
    context: RealP25AttemptZeroReservationContext,
) -> tuple[object, ProjectDirectorBoundedReworkAttemptReservationService, object]:
    session = context.package_context.session_local()
    _, reservation_service, msg_repo = _build_services(
        context.package_context,
        session=session,
    )
    return session, reservation_service, msg_repo
