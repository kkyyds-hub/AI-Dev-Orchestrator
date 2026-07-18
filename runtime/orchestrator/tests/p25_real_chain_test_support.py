"""Real P25-B through P25-H integration support with no synthetic P25 messages."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from app.external_executors.readonly_reviewer_transport import (
    FakeReadonlyReviewerTransport,
)
from app.core.db_tables import ProjectDirectorMessageTable
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
from app.services.project_director_bounded_rework_attempt_reservation_service import (
    ProjectDirectorBoundedReworkAttemptReservationService,
)
from app.services.project_director_bounded_rework_candidate_diff_service import (
    ProjectDirectorBoundedReworkCandidateDiffService,
)
from app.services.project_director_bounded_rework_evidence_resolver import (
    ProjectDirectorBoundedReworkEvidenceResolver,
)
from app.services.project_director_bounded_rework_execution_orchestration_service import (
    ProjectDirectorBoundedReworkExecutionOrchestrationService,
)
from app.services.project_director_bounded_rework_invocation_claim_service import (
    ProjectDirectorBoundedReworkInvocationClaimService,
)
from app.services.project_director_bounded_rework_invocation_outcome_service import (
    ProjectDirectorBoundedReworkInvocationOutcomeService,
)
from app.services.project_director_bounded_rework_package_preparation_service import (
    ProjectDirectorBoundedReworkPackagePreparationService,
)
from app.services.project_director_bounded_rework_post_review_orchestration_service import (
    ProjectDirectorBoundedReworkPostReviewOrchestrationService,
)
from app.services.project_director_bounded_rework_review_execution_service import (
    ProjectDirectorBoundedReworkReviewExecutionService,
)
from app.services.project_director_bounded_rework_review_reentry_preflight_service import (
    ProjectDirectorBoundedReworkReviewReentryPreflightService,
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
    FakeBoundedReworkExecutor,
    FakeBudgetGuardService,
    FakeTaskReadinessService,
    FakeTaskRouterService,
    FakeTaskStateMachineService,
    FakeTaskWorker,
    _P25EvidenceDiff,
    _P25EvidenceHandoff,
    _create_p25_repository_and_workspace,
    _make_p22_service,
    _persist_minimal_p25_control_plane,
    _seed_real_p20_p21_review_chain,
    make_repos,
    make_session_factory,
    make_test_engine,
    seed_base_records,
)


@dataclass(slots=True)
class RealP25AttemptZeroThroughReviewOutcome:
    engine: object
    session: object
    msg_repo: object
    task_repo: object
    run_repo: object
    session_id: UUID
    project_id: UUID
    task_id: UUID
    run_id: UUID
    root_p21c_review_message_id: UUID
    source_p23_intent_message_id: UUID
    source_p23_preflight_message_id: UUID
    source_p23_consumption_message_id: UUID
    p25_package_message_id: UUID
    p25_reservation_message_id: UUID
    p25_claim_message_id: UUID
    p25_executor_outcome_message_id: UUID
    p25_candidate_manifest_message_id: UUID
    p25_candidate_diff_message_id: UUID
    p25_review_preflight_message_id: UUID
    p25_review_claim_message_id: UUID
    p25_review_attempt_message_id: UUID
    p25_review_outcome_message_id: UUID
    p25_freshness_message_id: UUID
    p25_review_outcome: object
    evidence_resolver: ProjectDirectorBoundedReworkEvidenceResolver
    coordinator: ProjectDirectorBoundedReworkExecutionOrchestrationService
    bounded_executor: FakeBoundedReworkExecutor
    readonly_reviewer: FakeReadonlyReviewerTransport
    workspace_path: Path
    repository_path: Path

    def close(self) -> None:
        self.session.close()
        self.engine.dispose()


@dataclass(slots=True)
class RealP25AttemptZeroPackageContext:
    engine: object
    session: object
    msg_repo: object
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


def build_real_p25_attempt_zero_through_review_outcome(
    tmp_path: Path,
    *,
    stop_before_package: bool = False,
) -> RealP25AttemptZeroThroughReviewOutcome | RealP25AttemptZeroPackageContext:
    """Persist the exact P21-C -> P23 -> P25-B..H chain through real services."""
    engine = make_test_engine(str(tmp_path / "real-p25-chain.db"))
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
    setup_session.close()

    session, msg_repo, session_repo, task_repo, run_repo, agent_session_repo = make_repos(
        session_local
    )
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
        task_router_service=FakeTaskRouterService(),
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
    worker = FakeTaskWorker(session=session)
    worker_invocation_service = ProjectDirectorProtectedTransitionWorkerInvocationService(
        session_repository=session_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        run_repository=run_repo,
        agent_session_repository=agent_session_repo,
        worker_start_reservation_service=worker_start_service,
        freshness_service=freshness_service,
        task_worker=worker,
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
    reservation_service = ProjectDirectorBoundedReworkAttemptReservationService(
        message_repository=msg_repo,
        task_repository=task_repo,
        run_repository=run_repo,
        package_preparation_service=package_service,
        worker_start_reservation_service=worker_start_service,
        worker_invocation_service=worker_invocation_service,
    )
    claim_service = ProjectDirectorBoundedReworkInvocationClaimService(
        message_repository=msg_repo,
        attempt_reservation_service=reservation_service,
    )
    bounded_executor = FakeBoundedReworkExecutor()
    outcome_service = ProjectDirectorBoundedReworkInvocationOutcomeService(
        message_repository=msg_repo,
        claim_service=claim_service,
        bounded_rework_executor=bounded_executor,
    )
    coordinator = ProjectDirectorBoundedReworkExecutionOrchestrationService(
        package_preparation_service=package_service,
        attempt_reservation_service=reservation_service,
        invocation_outcome_service=outcome_service,
    )
    if stop_before_package:
        return RealP25AttemptZeroPackageContext(
            engine=engine,
            session=session,
            msg_repo=msg_repo,
            session_id=session_id,
            project_id=project_id,
            task_id=task_id,
            run_id=root_consumption.result.run_id,
            source_p23_consumption_message_id=root_consumption.message.id,
            package_service=package_service,
            evidence_resolver=evidence_resolver,
        )
    authority = package_service._revalidate_authority(
        session_id=session_id,
        source_task_id=task_id,
        source_consumption_message_id=root_consumption.message.id,
    )
    root_evidence = evidence_resolver.resolve_bounded_rework_evidence_snapshot(
        session_id=session_id,
        project_id=project_id,
        source_task_id=task_id,
        source_run_id=authority.authority.source_run_id,
        source_review_message_id=authority.authority.source_review_message_id,
        source_review_fingerprint=authority.authority.source_review_fingerprint,
        source_review_semantic_fingerprint=(
            authority.authority.source_review_semantic_fingerprint
        ),
        source_freshness_message_id=authority.source_freshness_message_id,
        source_diff_message_id=authority.source_diff_message_id,
    )
    assert root_evidence.snapshot is not None, root_evidence.blocked_reasons
    root_revalidation = evidence_resolver.revalidate_bounded_rework_evidence_snapshot(
        root_evidence.snapshot
    )
    assert root_revalidation.snapshot is not None, root_revalidation.blocked_reasons
    attempt_zero = coordinator.execute_bounded_rework_from_consumption(
        session_id=session_id,
        source_task_id=task_id,
        source_p23_dispatch_consumption_message_id=root_consumption.message.id,
    )
    assert attempt_zero.status == "outcome_recorded", (
        attempt_zero.blocked_reasons,
        attempt_zero.package_message,
        attempt_zero.reservation_message,
        attempt_zero.claim_message,
        attempt_zero.outcome_message,
    )
    assert attempt_zero.outcome is not None and attempt_zero.outcome_message is not None

    candidate_service = ProjectDirectorBoundedReworkCandidateDiffService(
        message_repository=msg_repo,
        claim_service=claim_service,
    )
    candidate = candidate_service.regenerate_candidate_manifest_and_diff(
        session_id=session_id,
        source_task_id=task_id,
        source_outcome_message_id=attempt_zero.outcome_message.id,
    )
    assert candidate.status == "candidate_diff_generated", candidate.blocked_reasons
    assert candidate.candidate_manifest_message is not None
    assert candidate.candidate_diff_message is not None

    review_preflight_service = ProjectDirectorBoundedReworkReviewReentryPreflightService(
        message_repository=msg_repo,
        candidate_diff_service=candidate_service,
    )
    review_preflight = review_preflight_service.prepare_review_reentry_preflight_and_claim(
        session_id=session_id,
        source_task_id=task_id,
        source_candidate_diff_message_id=candidate.candidate_diff_message.id,
    )
    assert review_preflight.status == "review_preflight_claimed", review_preflight.blocked_reasons
    assert review_preflight.review_claim_message is not None
    readonly_reviewer = FakeReadonlyReviewerTransport(
        raw_output_text=json.dumps(
            {
                "review_status": "reviewed",
                "verdict": "changes_required",
                "risk_level": "medium",
                "summary": "A bounded follow-up remains.",
                "findings": [
                    {
                        "finding_id": "fresh-p25-finding",
                        "severity": "medium",
                        "title": "Fresh review finding",
                        "summary": "The reworked file needs one more bounded change.",
                        "evidence_paths": ["src/example.py"],
                        "recommended_action": "Apply the bounded correction.",
                    }
                ],
                "recommended_next_step": "Prepare the next bounded attempt.",
            }
        )
    )
    review_execution_service = ProjectDirectorBoundedReworkReviewExecutionService(
        message_repository=msg_repo,
        preflight_service=review_preflight_service,
        transport_resolver_factory=lambda _workspace: lambda _executor: readonly_reviewer,
    )
    review_execution = review_execution_service.execute_claimed_readonly_review(
        session_id=session_id,
        source_task_id=task_id,
        source_review_claim_message_id=review_preflight.review_claim_message.id,
    )
    assert review_execution.status == "review_outcome_persisted", review_execution.blocked_reasons
    assert review_execution.review_outcome is not None
    assert review_execution.review_outcome_message is not None

    post_p22_service = _make_p22_service(
        session,
        msg_repo,
        session_repo,
        task_repo,
        candidate_diff_service=candidate_service,
        review_handoff_service=root_handoff_service,
    )
    post_review = ProjectDirectorBoundedReworkPostReviewOrchestrationService(
        review_execution_service=review_execution_service,
        disposition_service=post_p22_service._disposition_service,
        post_review_automation_service=post_p22_service,
    ).orchestrate_fresh_post_review(
        session_id=session_id,
        source_task_id=task_id,
        source_review_outcome_message_id=review_execution.review_outcome_message.id,
    )
    assert post_review.p22_summary is not None, post_review.blocked_reasons
    assert post_review.p22_summary.source_freshness_message_id is not None

    return RealP25AttemptZeroThroughReviewOutcome(
        engine=engine,
        session=session,
        msg_repo=msg_repo,
        task_repo=task_repo,
        run_repo=run_repo,
        session_id=session_id,
        project_id=project_id,
        task_id=task_id,
        run_id=attempt_zero.package.authority.source_run_id,
        root_p21c_review_message_id=root_review_message_id,
        source_p23_intent_message_id=root_intent.message.id,
        source_p23_preflight_message_id=root_preflight.message.id,
        source_p23_consumption_message_id=root_consumption.message.id,
        p25_package_message_id=attempt_zero.package_message.id,
        p25_reservation_message_id=attempt_zero.reservation_message.id,
        p25_claim_message_id=attempt_zero.claim_message.id,
        p25_executor_outcome_message_id=attempt_zero.outcome_message.id,
        p25_candidate_manifest_message_id=candidate.candidate_manifest_message.id,
        p25_candidate_diff_message_id=candidate.candidate_diff_message.id,
        p25_review_preflight_message_id=review_preflight.preflight_message.id,
        p25_review_claim_message_id=review_preflight.review_claim_message.id,
        p25_review_attempt_message_id=review_execution.review_attempt_message.id,
        p25_review_outcome_message_id=review_execution.review_outcome_message.id,
        p25_freshness_message_id=post_review.p22_summary.source_freshness_message_id,
        p25_review_outcome=review_execution.review_outcome,
        evidence_resolver=evidence_resolver,
        coordinator=coordinator,
        bounded_executor=bounded_executor,
        readonly_reviewer=readonly_reviewer,
        workspace_path=environment["workspace_path"],
        repository_path=environment["repository_root"],
    )
