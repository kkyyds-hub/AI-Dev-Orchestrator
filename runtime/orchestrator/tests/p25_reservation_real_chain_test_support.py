"""Real P25-D reservation support built from the committed P25-B fixture."""

from __future__ import annotations

from dataclasses import dataclass

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
from tests.p23_test_support import (
    FakeBudgetGuardService,
    FakeTaskReadinessService,
    FakeTaskStateMachineService,
    FakeTaskWorker,
    make_b1_service,
    make_repos,
)
from tests.p25_package_real_chain_fixture_support import _P25EvidenceDiff, _P25EvidenceHandoff
from tests.p25_package_real_chain_test_support import (
    P25FakeTaskRouterService,
    RealP25AttemptZeroPackageContext,
)


@dataclass(slots=True)
class FreshP25ReservationServices:
    session: object
    message_repository: object
    task_repository: TaskRepository
    run_repository: RunRepository
    package_service: ProjectDirectorBoundedReworkPackagePreparationService
    reservation_service: ProjectDirectorBoundedReworkAttemptReservationService

    def close(self) -> None:
        self.session.close()


def build_reservation_service(
    *,
    session_local,
    message_repository,
    task_repository: TaskRepository,
    run_repository: RunRepository,
    package_service: ProjectDirectorBoundedReworkPackagePreparationService,
) -> ProjectDirectorBoundedReworkAttemptReservationService:
    """Compose the formal P25-D API with repositories sharing one Session."""

    session = message_repository._session
    session_repository = ProjectDirectorSessionRepository(session)
    worker_start_reservation_service, _, _, _, _, agent_session_repository = (
        make_b1_service(
            session_local,
            msg_repo=message_repository,
            task_repo=task_repository,
            run_repo=run_repository,
        )
    )
    worker_invocation_service = ProjectDirectorProtectedTransitionWorkerInvocationService(
        session_repository=session_repository,
        message_repository=message_repository,
        task_repository=task_repository,
        run_repository=run_repository,
        agent_session_repository=agent_session_repository,
        worker_start_reservation_service=worker_start_reservation_service,
        freshness_service=worker_start_reservation_service._freshness_service,
        task_worker=FakeTaskWorker(session=session),
    )
    return ProjectDirectorBoundedReworkAttemptReservationService(
        message_repository=message_repository,
        task_repository=task_repository,
        run_repository=run_repository,
        package_preparation_service=package_service,
        worker_start_reservation_service=worker_start_reservation_service,
        worker_invocation_service=worker_invocation_service,
    )


def build_reservation_service_from_context(
    context: RealP25AttemptZeroPackageContext,
) -> ProjectDirectorBoundedReworkAttemptReservationService:
    """Use the original P25-B fixture Session for normal P25-D calls."""

    return build_reservation_service(
        session_local=context.session_local,
        message_repository=context.msg_repo,
        task_repository=TaskRepository(context.session),
        run_repository=RunRepository(context.session),
        package_service=context.package_service,
    )


def build_fresh_reservation_services(
    context: RealP25AttemptZeroPackageContext,
) -> FreshP25ReservationServices:
    """Open a new Session and reconstruct every P25-D dependency from storage."""

    session, message_repository, session_repository, task_repository, run_repository, _ = (
        make_repos(context.session_local)
    )
    evidence_diff = _P25EvidenceDiff(context.environment)
    evidence_handoff = _P25EvidenceHandoff(context.environment)
    freshness_service = ProjectDirectorProtectedTransitionEvidenceFreshnessService(
        session_repository=session_repository,
        message_repository=message_repository,
        task_repository=task_repository,
        review_handoff_service=evidence_handoff,
        candidate_diff_service=evidence_diff,
    )
    dispatch_intent_service = ProjectDirectorProtectedTransitionDispatchIntentService(
        session_repository=session_repository,
        message_repository=message_repository,
        task_repository=task_repository,
    )
    dispatch_preflight_service = (
        ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService(
            session_repository=session_repository,
            message_repository=message_repository,
            task_repository=task_repository,
            dispatch_intent_service=dispatch_intent_service,
            freshness_service=freshness_service,
            task_readiness_service=FakeTaskReadinessService(),
            task_state_machine_service=FakeTaskStateMachineService(),
            budget_guard_service=FakeBudgetGuardService(session=session),
        )
    )
    dispatch_consumption_service = (
        ProjectDirectorProtectedTransitionDispatchConsumptionService(
            session_repository=session_repository,
            message_repository=message_repository,
            task_repository=task_repository,
            run_repository=run_repository,
            preflight_service=dispatch_preflight_service,
            task_readiness_service=FakeTaskReadinessService(),
            task_state_machine_service=FakeTaskStateMachineService(),
            task_router_service=P25FakeTaskRouterService(),
            budget_guard_service=FakeBudgetGuardService(session=session),
        )
    )
    evidence_resolver = ProjectDirectorBoundedReworkEvidenceResolver(
        message_repository=message_repository,
        task_repository=task_repository,
        run_repository=run_repository,
        plan_version_repository=ProjectDirectorPlanVersionRepository(session),
        repository_binding_config_repository=(
            ProjectDirectorRepositoryBindingConfigRepository(session)
        ),
        skill_binding_config_repository=ProjectDirectorSkillBindingConfigRepository(
            session
        ),
        verification_config_repository=ProjectDirectorVerificationConfigRepository(
            session
        ),
        repository_workspace_repository=RepositoryWorkspaceRepository(session),
        freshness_service=freshness_service,
    )
    package_service = ProjectDirectorBoundedReworkPackagePreparationService(
        message_repository=message_repository,
        dispatch_consumption_service=dispatch_consumption_service,
        dispatch_intent_service=dispatch_intent_service,
        evidence_resolver=evidence_resolver,
    )
    reservation_service = build_reservation_service(
        session_local=context.session_local,
        message_repository=message_repository,
        task_repository=task_repository,
        run_repository=run_repository,
        package_service=package_service,
    )
    return FreshP25ReservationServices(
        session=session,
        message_repository=message_repository,
        task_repository=task_repository,
        run_repository=run_repository,
        package_service=package_service,
        reservation_service=reservation_service,
    )
