"""Real P25-B integration support with no synthetic P25 messages."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from app.core.db_tables import ProjectDirectorMessageTable, TaskTable
from app.domain.project_role import ProjectRoleCode
from app.domain.run import (
    RunBudgetPressureLevel,
    RunBudgetStrategyAction,
    RunRoutingScoreItem,
    RunStrategyDecision,
)
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.repositories.project_director_repository_binding_config_repository import (
    ProjectDirectorRepositoryBindingConfigRepository,
)
from app.repositories.project_director_skill_binding_config_repository import (
    ProjectDirectorSkillBindingConfigRepository,
)
from app.repositories.project_director_verification_config_repository import (
    ProjectDirectorVerificationConfigRepository,
)
from app.repositories.repository_workspace_repository import RepositoryWorkspaceRepository
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
from app.services.task_readiness_service import TaskReadinessResult
from app.services.task_router_service import TaskRoutingCandidate
from tests.p23_test_support import (
    FakeBudgetGuardService,
    FakeTaskReadinessService,
    FakeTaskStateMachineService,
    make_repos,
    make_session_factory,
    make_test_engine,
    seed_base_records,
)
from tests.p25_package_real_chain_fixture_support import (
    _P25EvidenceDiff,
    _P25EvidenceHandoff,
    _create_p25_repository_and_workspace,
    _persist_minimal_p25_control_plane,
    _seed_real_p20_p21_review_chain,
)


class P25FakeTaskRouterService:
    """P25-local router fixture independent of uncommitted P23 test support."""

    def evaluate_exact_task_for_dispatch(self, *, task):
        return TaskRoutingCandidate(
            task=task,
            readiness=TaskReadinessResult(
                task_id=task.id,
                ready_for_execution=True,
                blocking_signals=[],
                blocking_reasons=[],
                dependency_items=[],
            ),
            ready=True,
            routing_score=1.0,
            route_reason="test",
            routing_score_breakdown=[
                RunRoutingScoreItem(
                    code="test", label="Test", score=1.0, detail="test"
                )
            ],
            execution_attempts=0,
            recent_failure_count=0,
            budget_pressure_level=RunBudgetPressureLevel.NORMAL,
            budget_action=RunBudgetStrategyAction.FULL_SPEED,
            budget_strategy_code="normal",
            budget_score_adjustment=0.0,
            project_stage=None,
            owner_role_code=ProjectRoleCode.ARCHITECT,
            upstream_role_code=None,
            downstream_role_code=None,
            dispatch_status="dispatched",
            handoff_reason="test",
            matched_terms=(),
            model_name="test-model",
            model_tier="standard",
            selected_skill_codes=("test-skill",),
            selected_skill_names=("Test skill",),
            strategy_code="normal",
            strategy_summary="Normal execution",
            strategy_reasons=[],
            strategy_decision=RunStrategyDecision(
                budget_pressure_level=RunBudgetPressureLevel.NORMAL,
                budget_action=RunBudgetStrategyAction.FULL_SPEED,
                strategy_code="normal",
                summary="Normal execution",
                owner_role_code=ProjectRoleCode.ARCHITECT,
                model_name="test-model",
                model_tier="standard",
                selected_skill_codes=("test-skill",),
                selected_skill_names=("Test skill",),
            ),
        )


def _make_p22_service(
    session,
    msg_repo,
    sess_repo,
    task_repo,
    *,
    candidate_diff_service=None,
    review_handoff_service=None,
):
    """Create a real P22 service with all real sub-services."""
    from app.services.project_director_post_review_automation_service import (
        ProjectDirectorPostReviewAutomationService,
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

    return ProjectDirectorPostReviewAutomationService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        disposition_service=ProjectDirectorSandboxCandidateDiffReviewDispositionService(
            session_repository=sess_repo,
            message_repository=msg_repo,
        ),
        preflight_service=ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightService(
            session_repository=sess_repo,
            message_repository=msg_repo,
        ),
        consumption_service=ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
            review_handoff_service=review_handoff_service or _StubHandoff(),
            candidate_diff_service=candidate_diff_service or _StubDiff(),
        ),
        handoff_service=ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
        ),
        human_escalation_package_service=ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
        ),
        freshness_service=ProjectDirectorProtectedTransitionEvidenceFreshnessService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
            review_handoff_service=review_handoff_service or _StubHandoff(),
            candidate_diff_service=candidate_diff_service or _StubDiff(),
        ),
    )


@dataclass(slots=True)
class RealP25AttemptZeroPackageContext:
    engine: object
    session_local: object
    session: object
    msg_repo: object
    environment: dict[str, object]
    session_id: UUID
    project_id: UUID
    task_id: UUID
    run_id: UUID
    source_p23_consumption_message_id: UUID
    package_service: ProjectDirectorBoundedReworkPackagePreparationService
    evidence_resolver: ProjectDirectorBoundedReworkEvidenceResolver

    def close(self) -> None:
        self.session.close()
        self.engine.dispose()


def build_real_p25_attempt_zero_package_context(
    tmp_path: Path,
) -> RealP25AttemptZeroPackageContext:
    """Persist the exact P21-C -> P23 inputs consumed by P25-B."""

    engine = make_test_engine(str(tmp_path / "real-p25-package-chain.db"))
    session_local = make_session_factory(engine)
    session_id, project_id, task_id = uuid4(), uuid4(), uuid4()
    setup_session = session_local()
    seed_base_records(
        setup_session,
        session_id=session_id,
        project_id=project_id,
        task_id=task_id,
        task_status="pending",
    )
    task_row = setup_session.get(TaskTable, task_id)
    assert task_row is not None
    task_row.owner_role_code = "architect"
    setup_session.commit()
    setup_session.close()

    session, msg_repo, session_repo, task_repo, run_repo, _ = make_repos(session_local)
    environment = _create_p25_repository_and_workspace(tmp_path, session_id)
    _persist_minimal_p25_control_plane(
        session,
        session_id=session_id,
        project_id=project_id,
        task_id=task_id,
        environment=environment,
    )
    root_diff_service = _P25EvidenceDiff(environment)
    root_handoff_service = _P25EvidenceHandoff(environment)
    root_p22_service = _make_p22_service(
        session,
        msg_repo,
        session_repo,
        task_repo,
        candidate_diff_service=root_diff_service,
        review_handoff_service=root_handoff_service,
    )
    root_review_message_id = _seed_real_p20_p21_review_chain(
        msg_repo,
        session_id=session_id,
        project_id=project_id,
        task_id=task_id,
        environment=environment,
    )
    root_review_row = session.get(ProjectDirectorMessageTable, root_review_message_id)
    assert root_review_row is not None
    root_review_actions = json.loads(root_review_row.suggested_actions_json)
    assert len(root_review_actions) == 1
    root_review_actions[0]["findings"] = [
        {
            "finding_id": "root-p25-package-finding",
            "severity": "medium",
            "title": "Bounded root review finding",
            "summary": "The reviewed candidate needs one bounded correction.",
            "evidence_paths": ["src/example.py"],
            "recommended_action": "Apply the bounded correction.",
        }
    ]
    root_review_actions[0]["recommended_next_step"] = (
        "Prepare the bounded rework package."
    )
    root_review_row.suggested_actions_json = json.dumps(root_review_actions)
    session.commit()
    root_p22 = root_p22_service.orchestrate_post_review(
        session_id=session_id,
        source_task_id=task_id,
        source_review_message_id=root_review_message_id,
    )
    assert root_p22.message is not None

    root_intent_service = ProjectDirectorProtectedTransitionDispatchIntentService(
        session_repository=session_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
    )
    root_intent = root_intent_service.prepare_protected_transition_dispatch_intent(
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=root_p22.message.id,
    )
    assert root_intent.message is not None

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
    root_preflight = preflight_service.prepare_protected_transition_dispatch_consumption_preflight(
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=root_intent.message.id,
    )
    assert root_preflight.message is not None
    root_consumption = consumption_service.consume_protected_transition_dispatch_preflight(
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=root_preflight.message.id,
    )
    assert root_consumption.message is not None

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
    return RealP25AttemptZeroPackageContext(
        engine=engine,
        session_local=session_local,
        session=session,
        msg_repo=msg_repo,
        environment=environment,
        session_id=session_id,
        project_id=project_id,
        task_id=task_id,
        run_id=root_consumption.result.run_id,
        source_p23_consumption_message_id=root_consumption.message.id,
        package_service=package_service,
        evidence_resolver=evidence_resolver,
    )
