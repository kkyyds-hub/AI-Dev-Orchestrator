"""Real-service P25 convergence gate coverage for P23 dispatch intents."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4, uuid5

import pytest

from app.domain.project_director_bounded_rework_contract import (
    ProjectDirectorBoundedReworkAuthorityEnvelope,
)
from app.domain.project_director_bounded_rework_review_reentry import (
    P25_BOUNDED_REWORK_REVIEW_OUTCOME_NAMESPACE,
    P25_BOUNDED_REWORK_REVIEW_OUTPUT_SCHEMA_VERSION,
    ProjectDirectorBoundedReworkReviewInvocationOutcome,
)
from app.domain.project_director_message import ProjectDirectorMessage
from app.domain.project_director_sandbox_candidate_diff_readonly_reviewer_adapter import (
    ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult,
)
from app.domain.project_director_sandbox_candidate_diff_review_output import (
    ProjectDirectorSandboxCandidateDiffReviewFinding,
)
from app.services.project_director_bounded_rework_review_execution_service import (
    P25_BOUNDED_REWORK_REVIEW_OUTCOME_ACTION_TYPE,
    P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT,
    P25_BOUNDED_REWORK_REVIEW_OUTCOME_SOURCE_DETAIL,
    ProjectDirectorBoundedReworkReviewExecutionService,
)
from app.services.project_director_bounded_rework_terminal_escalation_service import (
    P25_BOUNDED_REWORK_TERMINAL_ESCALATION_SOURCE_DETAIL,
    ProjectDirectorBoundedReworkTerminalEscalationService,
)
from app.services.project_director_protected_transition_dispatch_intent_service import (
    P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL,
    ProjectDirectorProtectedTransitionDispatchIntentService,
)
from tests.p23_test_support import (
    DIFF_SHA256,
    _make_p22_service,
    _seed_p21_c_review_chain,
    count_messages_by_source_detail,
    make_repos,
    make_session_factory,
    make_test_engine,
    seed_base_records,
)
from tests.p25_dynamic_test_support import (
    FakeCandidateDiffService,
    FakeReviewExecutionService,
    make_convergence_service,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


@pytest.fixture()
def session_local(tmp_path):
    engine = make_test_engine(str(tmp_path / "p25-p23.db"))
    return make_session_factory(engine)


def _authority(
    *,
    ids: dict[str, UUID],
    source_review_message_id: UUID,
    source_disposition_message_id: UUID,
    source_p22_summary_message_id: UUID,
    source_p23_dispatch_intent_id: UUID,
    previous_semantic_fingerprint: str,
) -> ProjectDirectorBoundedReworkAuthorityEnvelope:
    return ProjectDirectorBoundedReworkAuthorityEnvelope(
        session_id=ids["session_id"],
        project_id=ids["project_id"],
        source_task_id=ids["task_id"],
        target_task_id=ids["task_id"],
        source_run_id=uuid4(),
        source_review_message_id=source_review_message_id,
        source_review_fingerprint=_sha("source-review"),
        source_review_semantic_fingerprint=previous_semantic_fingerprint,
        source_disposition_message_id=source_disposition_message_id,
        source_p22_summary_message_id=source_p22_summary_message_id,
        source_p23_dispatch_intent_id=source_p23_dispatch_intent_id,
        source_p23_dispatch_intent_fingerprint=_sha("source-intent"),
        source_p23_dispatch_consumption_id=uuid4(),
        source_p23_dispatch_consumption_fingerprint=_sha("source-consumption"),
    )


def _persist_valid_review_outcome(
    *,
    msg_repo,
    ids: dict[str, UUID],
    authority: ProjectDirectorBoundedReworkAuthorityEnvelope,
    candidate_diff_id: UUID,
    attempt_index: int,
    risk_level: str = "medium",
) -> tuple[ProjectDirectorBoundedReworkReviewInvocationOutcome, ProjectDirectorMessage]:
    finding = ProjectDirectorSandboxCandidateDiffReviewFinding(
        finding_id=f"finding-{attempt_index}",
        severity="medium",
        title=f"Fresh guard {attempt_index}",
        summary="A fresh blocking issue remains.",
        evidence_paths=["src/example.py"],
        recommended_action="Resolve the fresh blocking issue.",
    )
    adapter = ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult(
        adapter_status="validated_output",
        requested_reviewer_executor="codex",
        review_prompt_verified=True,
        review_prompt_sha256=_sha(f"prompt-{attempt_index}"),
        review_prompt_bytes=100,
        review_scope_paths=["src/example.py"],
        review_output_schema_version=P25_BOUNDED_REWORK_REVIEW_OUTPUT_SCHEMA_VERSION,
        transport_invoked=True,
        transport_status="completed",
        output_validation_status="validated",
        raw_output_sha256=_sha(f"raw-{attempt_index}"),
        raw_output_bytes=100,
        strict_json_valid=True,
        schema_valid=True,
        semantics_valid=True,
        evidence_scope_valid=True,
        review_status="reviewed",
        verdict="changes_required",
        risk_level=risk_level,
        summary=f"Fresh review {attempt_index} completed.",
        findings=[finding],
        recommended_next_step="Prepare the next bounded rework attempt.",
    )
    attempt_replay_key = _sha(f"attempt-replay-{attempt_index}-{candidate_diff_id}")
    values = {
        "review_outcome_id": uuid5(P25_BOUNDED_REWORK_REVIEW_OUTCOME_NAMESPACE, attempt_replay_key),
        "review_outcome_replay_key": ProjectDirectorBoundedReworkReviewInvocationOutcome.compute_outcome_replay_key(
            review_attempt_replay_key=attempt_replay_key,
            source_candidate_diff_sha256=DIFF_SHA256,
            review_prompt_sha256=adapter.review_prompt_sha256,
            invocation_ordinal=0,
        ),
        "created_at": datetime.now(timezone.utc),
        "outcome_status": "validated_output",
        "review_attempt_id": uuid4(),
        "review_attempt_fingerprint": _sha(f"attempt-{attempt_index}"),
        "review_attempt_replay_key": attempt_replay_key,
        "review_claim_id": uuid4(),
        "review_claim_fingerprint": _sha(f"claim-{attempt_index}"),
        "preflight_id": uuid4(),
        "preflight_fingerprint": _sha(f"preflight-{attempt_index}"),
        "source_candidate_diff_message_id": candidate_diff_id,
        "source_candidate_diff_id": candidate_diff_id,
        "source_candidate_diff_fingerprint": _sha(f"candidate-{attempt_index}"),
        "source_candidate_diff_sha256": DIFF_SHA256,
        "source_candidate_manifest_id": uuid4(),
        "source_candidate_manifest_fingerprint": _sha(f"manifest-{attempt_index}"),
        "source_executor_outcome_id": uuid4(),
        "source_package_id": uuid4(),
        "source_attempt_id": uuid4(),
        "authority": authority,
        "exact_task_id": ids["task_id"],
        "exact_run_id": authority.source_run_id,
        "rework_attempt_index": attempt_index,
        "rework_attempt_limit": 3,
        "requested_reviewer_executor": "codex",
        "review_prompt_sha256": adapter.review_prompt_sha256,
        "review_prompt_bytes": adapter.review_prompt_bytes,
        "review_scope_paths": ("src/example.py",),
        "review_output_schema_version": P25_BOUNDED_REWORK_REVIEW_OUTPUT_SCHEMA_VERSION,
        "invocation_ordinal": 0,
        "adapter_result": adapter,
        "review_semantic_fingerprint": ProjectDirectorBoundedReworkReviewExecutionService._review_semantic_fingerprint(
            adapter_result=adapter,
            source_candidate_diff_sha256=DIFF_SHA256,
            review_scope_paths=("src/example.py",),
        ),
        "safe_error_code": None,
        "blocked_reasons": (),
        "recovery_required": False,
        "human_escalation_required": False,
    }
    draft = ProjectDirectorBoundedReworkReviewInvocationOutcome.model_construct(
        review_outcome_fingerprint="0" * 64,
        review_result_fingerprint="0" * 64,
        **values,
    )
    result_fingerprint = ProjectDirectorBoundedReworkReviewExecutionService.rebuild_persisted_review_result_fingerprint(draft)
    fingerprint_draft = ProjectDirectorBoundedReworkReviewInvocationOutcome.model_construct(
        review_outcome_fingerprint="0" * 64,
        review_result_fingerprint=result_fingerprint,
        **values,
    )
    outcome = ProjectDirectorBoundedReworkReviewInvocationOutcome(
        review_outcome_fingerprint=fingerprint_draft.compute_fingerprint(),
        review_result_fingerprint=result_fingerprint,
        **values,
    )
    message = ProjectDirectorMessage(
        id=outcome.review_outcome_id,
        session_id=ids["session_id"],
        role="assistant",
        content=(
            "P25 bounded rework review outcome persisted: "
            f"{outcome.review_outcome_id} attempt {outcome.review_attempt_id} "
            "status validated_output verdict changes_required summary validated_review_output"
        ),
        sequence_no=msg_repo.get_next_sequence_no(session_id=ids["session_id"]),
        intent=P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT,
        related_project_id=ids["project_id"],
        related_task_id=ids["task_id"],
        source="system",
        source_detail=P25_BOUNDED_REWORK_REVIEW_OUTCOME_SOURCE_DETAIL,
        suggested_actions=[{"type": P25_BOUNDED_REWORK_REVIEW_OUTCOME_ACTION_TYPE, **outcome.model_dump(mode="json")}],
        requires_confirmation=False,
        risk_level="high",
        forbidden_actions_detected=[
            "provider_called=false",
            "main_project_write_allowed=false",
            "product_runtime_git_write_allowed=false",
            "patch_apply_allowed=false",
            "git_write_allowed=false",
            "task_created=false",
            "run_created=false",
        ],
        created_at=outcome.created_at,
    )
    persisted = msg_repo.create(message)
    msg_repo.commit()
    assert ProjectDirectorBoundedReworkReviewExecutionService.persisted_review_invocation_outcome_message_is_valid(persisted, outcome)
    return outcome, persisted


def _persist_candidate_message(*, msg_repo, ids: dict[str, UUID], candidate_id: UUID):
    candidate_write_id = uuid4()
    candidate_write = ProjectDirectorMessage(
        id=candidate_write_id,
        session_id=ids["session_id"],
        role="assistant",
        content="Candidate files written in the isolated workspace.",
        sequence_no=msg_repo.get_next_sequence_no(session_id=ids["session_id"]),
        intent="sandbox_candidate_files_write",
        related_project_id=ids["project_id"],
        related_task_id=ids["task_id"],
        source="system",
        source_detail="p21_c_sandbox_candidate_files_write_executed",
        suggested_actions=[
            {
                "type": "p21_c_sandbox_candidate_files_write_record",
                "session_id": str(ids["session_id"]),
                "source_task_id": str(ids["task_id"]),
                "workspace_path": "/tmp/test-workspace-p23-d3",
            }
        ],
        requires_confirmation=False,
        risk_level="high",
    )
    msg_repo.create(candidate_write)
    message = ProjectDirectorMessage(
        id=candidate_id,
        session_id=ids["session_id"],
        role="assistant",
        content="Persisted P25 candidate diff evidence.",
        sequence_no=msg_repo.get_next_sequence_no(session_id=ids["session_id"]),
        intent="bounded_rework_candidate_diff",
        related_project_id=ids["project_id"],
        related_task_id=ids["task_id"],
        source="system",
        source_detail="p25_g_candidate_diff_generated",
        suggested_actions=[
            {
                "type": "p25_bounded_rework_candidate_diff_record",
                "source_message_id": str(candidate_write_id),
                "workspace_path": "/tmp/test-workspace-p23-d3",
            }
        ],
        requires_confirmation=False,
        risk_level="high",
    )
    persisted = msg_repo.create(message)
    msg_repo.commit()
    return persisted


def _prepare_scenario(session_local, *, target_index: int):
    session, msg_repo, sess_repo, task_repo, *_ = make_repos(session_local)
    ids = seed_base_records(session)
    p22_service = _make_p22_service(session, msg_repo, sess_repo, task_repo)
    initial_review_id = _seed_p21_c_review_chain(
        session,
        session_id=ids["session_id"],
        task_id=ids["task_id"],
        project_id=ids["project_id"],
        verdict="changes_required",
        risk_level="medium",
    )
    initial_summary = p22_service.orchestrate_post_review(
        session_id=ids["session_id"],
        source_task_id=ids["task_id"],
        source_review_message_id=initial_review_id,
    )
    assert initial_summary.result.orchestration_status == "ready_for_future_transition"
    legacy_intent_service = ProjectDirectorProtectedTransitionDispatchIntentService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
    )
    prior_intent = legacy_intent_service.prepare_protected_transition_dispatch_intent(
        session_id=ids["session_id"],
        source_task_id=ids["task_id"],
        source_message_id=initial_summary.message.id,
    )
    assert prior_intent.result.intent_status == "prepared"
    assert prior_intent.result.rework_attempt_index == 0

    prior_summary = initial_summary
    prior_review_id = initial_review_id
    latest = None
    for attempt_index in range(target_index):
        candidate_id = uuid4()
        candidate_message = _persist_candidate_message(msg_repo=msg_repo, ids=ids, candidate_id=candidate_id)
        authority = _authority(
            ids=ids,
            source_review_message_id=prior_review_id,
            source_disposition_message_id=prior_summary.result.source_disposition_message_id,
            source_p22_summary_message_id=prior_summary.message.id,
            source_p23_dispatch_intent_id=prior_intent.message.id,
            previous_semantic_fingerprint=_sha(f"previous-semantic-{attempt_index}"),
        )
        outcome, outcome_message = _persist_valid_review_outcome(
            msg_repo=msg_repo,
            ids=ids,
            authority=authority,
            candidate_diff_id=candidate_id,
            attempt_index=attempt_index,
        )
        p22_summary = p22_service.orchestrate_post_review(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_review_message_id=outcome_message.id,
        )
        assert p22_summary.result.orchestration_status == "ready_for_future_transition", (
            p22_summary.result.blocked_reasons
        )
        assert p22_summary.result.disposition_type == "AUTO_REWORK"
        previous_finding = ProjectDirectorSandboxCandidateDiffReviewFinding(
            finding_id=f"previous-{attempt_index}",
            severity="high",
            title=f"Previous guard {attempt_index}",
            summary="A previous blocking issue remained.",
            evidence_paths=["src/example.py"],
            recommended_action="Resolve the previous blocking issue.",
        )
        package = SimpleNamespace(
            package_id=uuid4(),
            package_fingerprint=_sha(f"package-{attempt_index}"),
            authority=authority,
            rework_attempt_index=attempt_index,
            blocking_findings=(previous_finding,),
        )
        candidate_diff = SimpleNamespace(
            candidate_diff_id=candidate_id,
            candidate_diff_fingerprint=outcome.source_candidate_diff_fingerprint,
            candidate_diff_replay_key=_sha(f"candidate-replay-{candidate_id}"),
            diff_status="generated",
            non_convergence_reason=None,
            authority=authority,
            source_attempt_id=outcome.source_attempt_id,
            rework_attempt_index=attempt_index,
            rework_attempt_limit=3,
            previous_diff_sha256=_sha(f"previous-diff-{attempt_index}"),
            new_diff_sha256=DIFF_SHA256,
        )
        candidate_service = FakeCandidateDiffService(
            message_repository=msg_repo,
            candidate_diff=candidate_diff,
            candidate_diff_message=candidate_message,
            package=package,
            invocation_outcome=SimpleNamespace(outcome_id=outcome.source_executor_outcome_id),
        )
        review_service = FakeReviewExecutionService(
            message_repository=msg_repo,
            review_outcome=outcome,
            review_outcome_message=outcome_message,
        )
        convergence_service, _, _ = make_convergence_service(
            session_local,
            msg_repo=msg_repo,
            candidate_diff_svc=candidate_service,
            review_execution_svc=review_service,
            post_review_automation_svc=p22_service,
        )
        convergence = convergence_service.decide_bounded_rework_convergence(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_candidate_diff_message_id=candidate_id,
        )
        assert convergence.status == "decision_persisted"
        assert convergence.decision.decision_type == "NEXT_ATTEMPT_ELIGIBLE"
        assert convergence.decision.next_rework_attempt_index == attempt_index + 1
        intent_service = ProjectDirectorProtectedTransitionDispatchIntentService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
            bounded_rework_convergence_service=convergence_service,
        )
        prepared = intent_service.prepare_protected_transition_dispatch_intent(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_message_id=p22_summary.message.id,
        )
        latest = SimpleNamespace(
            prepared=prepared,
            intent_service=intent_service,
            convergence=convergence,
            candidate_message=candidate_message,
            outcome_message=outcome_message,
            p22_summary=p22_summary,
        )
        prior_intent = prepared
        prior_summary = p22_summary
        prior_review_id = outcome_message.id
    return SimpleNamespace(session=session, msg_repo=msg_repo, ids=ids, latest=latest)


@pytest.mark.parametrize("target_index", [1, 2])
def test_real_p25_next_attempt_prepares_exact_p23_intent_and_replays(session_local, target_index):
    scenario = _prepare_scenario(session_local, target_index=target_index)
    latest = scenario.latest
    first = latest.prepared
    assert first.result.intent_status == "prepared"
    assert first.result.dispatch_kind == "auto_rework"
    assert first.result.rework_attempt_index == target_index
    assert first.result.source_p25_convergence_decision_message_id == latest.convergence.decision_message.id
    assert first.result.source_p25_candidate_diff_message_id == latest.candidate_message.id
    assert first.result.source_p25_review_outcome_message_id == latest.outcome_message.id
    assert first.result.source_p22_summary_message_id == latest.p22_summary.message.id
    before = count_messages_by_source_detail(
        scenario.msg_repo,
        scenario.ids["session_id"],
        P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL,
    )
    scenario.session.rollback()
    replay = latest.intent_service.prepare_protected_transition_dispatch_intent(
        session_id=scenario.ids["session_id"],
        source_task_id=scenario.ids["task_id"],
        source_message_id=latest.p22_summary.message.id,
    )
    assert replay.result.resumed_from_existing_intent is True
    assert replay.message.id == first.message.id
    assert count_messages_by_source_detail(
        scenario.msg_repo,
        scenario.ids["session_id"],
        P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL,
    ) == before
    scenario.session.close()


def test_high_risk_reuses_p21_d_package_and_p23_blocks(session_local):
    session, msg_repo, sess_repo, task_repo, *_ = make_repos(session_local)
    ids = seed_base_records(session)
    p22_service = _make_p22_service(session, msg_repo, sess_repo, task_repo)
    candidate_id = uuid4()
    candidate_message = _persist_candidate_message(
        msg_repo=msg_repo,
        ids=ids,
        candidate_id=candidate_id,
    )
    authority = _authority(
        ids=ids,
        source_review_message_id=uuid4(),
        source_disposition_message_id=uuid4(),
        source_p22_summary_message_id=uuid4(),
        source_p23_dispatch_intent_id=uuid4(),
        previous_semantic_fingerprint=_sha("high-risk-previous-semantic"),
    )
    outcome, outcome_message = _persist_valid_review_outcome(
        msg_repo=msg_repo,
        ids=ids,
        authority=authority,
        candidate_diff_id=candidate_id,
        attempt_index=0,
        risk_level="high",
    )
    p22_summary = p22_service.orchestrate_post_review(
        session_id=ids["session_id"],
        source_task_id=ids["task_id"],
        source_review_message_id=outcome_message.id,
    )
    assert p22_summary.result.orchestration_status == "waiting_for_human"
    assert p22_summary.result.source_human_escalation_package_message_id is not None

    previous_finding = ProjectDirectorSandboxCandidateDiffReviewFinding(
        finding_id="previous-high-risk",
        severity="high",
        title="Previous high-risk guard",
        summary="A previous high-risk issue remained.",
        evidence_paths=["src/example.py"],
        recommended_action="Resolve the previous high-risk issue.",
    )
    package = SimpleNamespace(
        package_id=uuid4(),
        package_fingerprint=_sha("high-risk-package"),
        authority=authority,
        rework_attempt_index=0,
        blocking_findings=(previous_finding,),
    )
    candidate_diff = SimpleNamespace(
        candidate_diff_id=candidate_id,
        candidate_diff_fingerprint=outcome.source_candidate_diff_fingerprint,
        candidate_diff_replay_key=_sha(f"candidate-replay-{candidate_id}"),
        diff_status="generated",
        non_convergence_reason=None,
        authority=authority,
        source_attempt_id=outcome.source_attempt_id,
        rework_attempt_index=0,
        rework_attempt_limit=3,
        previous_diff_sha256=_sha("high-risk-previous-diff"),
        new_diff_sha256=DIFF_SHA256,
    )
    convergence_service, _, _ = make_convergence_service(
        session_local,
        msg_repo=msg_repo,
        candidate_diff_svc=FakeCandidateDiffService(
            message_repository=msg_repo,
            candidate_diff=candidate_diff,
            candidate_diff_message=candidate_message,
            package=package,
            invocation_outcome=SimpleNamespace(
                outcome_id=outcome.source_executor_outcome_id
            ),
        ),
        review_execution_svc=FakeReviewExecutionService(
            message_repository=msg_repo,
            review_outcome=outcome,
            review_outcome_message=outcome_message,
        ),
        post_review_automation_svc=p22_service,
    )
    convergence = convergence_service.decide_bounded_rework_convergence(
        session_id=ids["session_id"],
        source_task_id=ids["task_id"],
        source_candidate_diff_message_id=candidate_id,
    )
    assert convergence.status == "decision_persisted"
    assert convergence.decision.decision_reason == "high_review_risk"

    terminal_service = ProjectDirectorBoundedReworkTerminalEscalationService(
        message_repository=msg_repo,
        convergence_service=convergence_service,
    )
    terminal = terminal_service.prepare_bounded_rework_terminal_escalation(
        session_id=ids["session_id"],
        source_task_id=ids["task_id"],
        source_convergence_decision_message_id=convergence.decision_message.id,
    )
    assert terminal.status == "existing_human_package_reused"
    assert terminal.existing_human_package_message.id == p22_summary.result.source_human_escalation_package_message_id
    assert terminal.message is None
    assert count_messages_by_source_detail(
        msg_repo,
        ids["session_id"],
        P25_BOUNDED_REWORK_TERMINAL_ESCALATION_SOURCE_DETAIL,
    ) == 0
    session.rollback()

    p23_service = ProjectDirectorProtectedTransitionDispatchIntentService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        bounded_rework_convergence_service=convergence_service,
    )
    p23 = p23_service.prepare_protected_transition_dispatch_intent(
        session_id=ids["session_id"],
        source_task_id=ids["task_id"],
        source_message_id=p22_summary.message.id,
    )
    assert p23.result.intent_status == "blocked"
    assert p23.result.blocked_reasons == ["p25_human_escalation_required"]
    assert p23.message is None
    session.close()
