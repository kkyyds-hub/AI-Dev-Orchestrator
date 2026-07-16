"""Real-service P25 convergence gate coverage for P23 dispatch intents."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4, uuid5

import pytest
from sqlalchemy import text

from app.core.db_tables import ProjectDirectorMessageTable
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
from app.services.project_director_protected_transition_dispatch_consumption_preflight_service import (
    ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService,
)
from tests.p23_test_support import (
    DIFF_SHA256,
    FakeBudgetGuardService,
    FakeTaskReadinessService,
    FakeTaskStateMachineService,
    _make_p22_service,
    _seed_p21_c_review_chain,
    count_messages_by_source_detail,
    make_b1_service,
    make_d1_service,
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
    verdict: str = "changes_required",
    risk_level: str = "medium",
    summary_suffix: str = "",
) -> tuple[ProjectDirectorBoundedReworkReviewInvocationOutcome, ProjectDirectorMessage]:
    finding = ProjectDirectorSandboxCandidateDiffReviewFinding(
        finding_id=f"finding-{attempt_index}",
        severity="medium",
        title=f"Fresh guard {attempt_index}",
        summary=f"A fresh blocking issue remains. {summary_suffix}".strip(),
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
        verdict=verdict,
        risk_level=risk_level,
        summary=f"Fresh review {attempt_index} completed. {summary_suffix}".strip(),
        findings=[] if verdict != "changes_required" else [finding],
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
            "status validated_output "
            f"verdict {outcome.adapter_result.verdict} "
            "summary validated_review_output"
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


def _prepare_scenario(
    session_local,
    *,
    target_index: int,
    prepare_final_intent: bool = True,
    persist_final_convergence: bool = True,
    final_verdict: str = "changes_required",
    final_risk_level: str = "medium",
    final_summary_suffix: str = "",
):
    session, msg_repo, sess_repo, task_repo, run_repo, *_ = make_repos(
        session_local
    )
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
            verdict=(
                final_verdict
                if attempt_index == target_index - 1
                else "changes_required"
            ),
            risk_level=(
                final_risk_level
                if attempt_index == target_index - 1
                else "medium"
            ),
            summary_suffix=(
                final_summary_suffix
                if attempt_index == target_index - 1
                else ""
            ),
        )
        p22_summary = p22_service.orchestrate_post_review(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_review_message_id=outcome_message.id,
        )
        assert p22_summary.result.orchestration_status == "ready_for_future_transition", (
            p22_summary.result.blocked_reasons
        )
        if outcome.adapter_result.verdict == "changes_required":
            assert p22_summary.result.disposition_type in {
                "AUTO_REWORK",
                "ESCALATE_TO_HUMAN",
            }
        else:
            assert p22_summary.result.disposition_type == "AUTO_CONTINUE"
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
        should_persist_convergence = (
            persist_final_convergence or attempt_index < target_index - 1
        )
        convergence = (
            convergence_service.decide_bounded_rework_convergence(
                session_id=ids["session_id"],
                source_task_id=ids["task_id"],
                source_candidate_diff_message_id=candidate_id,
            )
            if should_persist_convergence
            else None
        )
        if convergence is None:
            latest = SimpleNamespace(
                prepared=None,
                intent_service=ProjectDirectorProtectedTransitionDispatchIntentService(
                    session_repository=sess_repo,
                    message_repository=msg_repo,
                    task_repository=task_repo,
                    bounded_rework_convergence_service=convergence_service,
                ),
                convergence=None,
                convergence_service=convergence_service,
                candidate_service=candidate_service,
                review_service=review_service,
                candidate_message=candidate_message,
                candidate_diff=candidate_diff,
                package=package,
                outcome=outcome,
                outcome_message=outcome_message,
                p22_summary=p22_summary,
            )
            continue
        assert convergence.status == "decision_persisted"
        expected_converged = outcome.adapter_result.verdict != "changes_required"
        expected_terminal = (
            attempt_index + 1 >= candidate_diff.rework_attempt_limit
            or outcome.adapter_result.risk_level == "high"
        )
        if expected_converged:
            assert convergence.decision.decision_type == "CONVERGED"
            assert convergence.decision.decision_reason == "review_converged"
        elif expected_terminal:
            assert convergence.decision.decision_type == "ESCALATE_TO_HUMAN"
            assert convergence.decision.decision_reason in {
                "attempt_limit_exhausted",
                "high_review_risk",
            }
        else:
            assert convergence.decision.decision_type == "NEXT_ATTEMPT_ELIGIBLE"
            assert convergence.decision.next_rework_attempt_index == attempt_index + 1
        intent_service = ProjectDirectorProtectedTransitionDispatchIntentService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
            bounded_rework_convergence_service=convergence_service,
        )
        should_prepare = (
            not expected_terminal
            and not expected_converged
            and (prepare_final_intent or attempt_index < target_index - 1)
        )
        prepared = (
            intent_service.prepare_protected_transition_dispatch_intent(
                session_id=ids["session_id"],
                source_task_id=ids["task_id"],
                source_message_id=p22_summary.message.id,
            )
            if should_prepare
            else None
        )
        latest = SimpleNamespace(
            prepared=prepared,
            intent_service=intent_service,
            convergence=convergence,
            convergence_service=convergence_service,
            candidate_service=candidate_service,
            review_service=review_service,
            candidate_message=candidate_message,
            candidate_diff=candidate_diff,
            package=package,
            outcome=outcome,
            outcome_message=outcome_message,
            p22_summary=p22_summary,
        )
        if prepared is not None:
            prior_intent = prepared
            prior_summary = p22_summary
            prior_review_id = outcome_message.id
    return SimpleNamespace(
        session=session,
        msg_repo=msg_repo,
        sess_repo=sess_repo,
        task_repo=task_repo,
        run_repo=run_repo,
        ids=ids,
        p22_service=p22_service,
        latest=latest,
    )


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
    package_count = count_messages_by_source_detail(
        msg_repo,
        ids["session_id"],
        "p21_d_sandbox_candidate_diff_review_human_escalation_package_prepared",
    )
    session.rollback()
    replay = p23_service.prepare_protected_transition_dispatch_intent(
        session_id=ids["session_id"],
        source_task_id=ids["task_id"],
        source_message_id=p22_summary.message.id,
    )
    assert replay.result.blocked_reasons == ["p25_human_escalation_required"]
    assert replay.message is None
    assert count_messages_by_source_detail(
        msg_repo,
        ids["session_id"],
        "p21_d_sandbox_candidate_diff_review_human_escalation_package_prepared",
    ) == package_count
    assert count_messages_by_source_detail(
        msg_repo,
        ids["session_id"],
        P25_BOUNDED_REWORK_TERMINAL_ESCALATION_SOURCE_DETAIL,
    ) == 0
    assert count_messages_by_source_detail(
        msg_repo,
        ids["session_id"],
        P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL,
    ) == 0
    session.close()


_DELETE = object()
_P23_SENTINEL = "P25_J_A_P23_SECRET_SENTINEL_91ab73"


def _call_latest_p23(scenario):
    if scenario.session.in_transaction():
        scenario.session.rollback()
    return scenario.latest.intent_service.prepare_protected_transition_dispatch_intent(
        session_id=scenario.ids["session_id"],
        source_task_id=scenario.ids["task_id"],
        source_message_id=scenario.latest.p22_summary.message.id,
    )


def _tamper_action(scenario, message_id, field, value):
    row = scenario.session.get(ProjectDirectorMessageTable, message_id)
    assert row is not None
    actions = json.loads(row.suggested_actions_json)
    assert len(actions) == 1
    if value is _DELETE:
        actions[0].pop(field, None)
    else:
        actions[0][field] = value
    row.suggested_actions_json = json.dumps(actions)
    scenario.session.commit()


def _clone_message(scenario, message, *, action_updates=None, metadata_updates=None):
    payload = message.model_dump()
    payload.update(
        id=uuid4(),
        sequence_no=scenario.msg_repo.get_next_sequence_no(
            session_id=scenario.ids["session_id"]
        ),
    )
    actions = json.loads(json.dumps(payload["suggested_actions"], default=str))
    if action_updates:
        for field, value in action_updates.items():
            if value is _DELETE:
                actions[0].pop(field, None)
            else:
                actions[0][field] = value
    payload["suggested_actions"] = actions
    if metadata_updates:
        payload.update(metadata_updates)
    cloned = scenario.msg_repo.create(ProjectDirectorMessage.model_validate(payload))
    scenario.msg_repo.commit()
    return cloned


def test_missing_convergence_decision_blocks_without_p23_write(session_local):
    scenario = _prepare_scenario(
        session_local,
        target_index=1,
        prepare_final_intent=False,
        persist_final_convergence=False,
    )
    before = count_messages_by_source_detail(
        scenario.msg_repo,
        scenario.ids["session_id"],
        P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL,
    )
    scenario.session.rollback()
    result = _call_latest_p23(scenario)
    assert result.result.blocked_reasons == ["next_attempt_decision_missing"]
    assert result.message is None
    assert count_messages_by_source_detail(
        scenario.msg_repo,
        scenario.ids["session_id"],
        P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL,
    ) == before
    scenario.session.close()


def test_converged_decision_is_terminal_for_p23(session_local):
    scenario = _prepare_scenario(
        session_local,
        target_index=1,
        prepare_final_intent=False,
        final_verdict="no_blocking_findings",
    )
    assert scenario.latest.convergence.decision.decision_type == "CONVERGED"
    result = _call_latest_p23(scenario)
    assert result.result.blocked_reasons == ["p25_convergence_terminal"]
    assert result.message is None
    scenario.session.close()


def test_attempt_limit_decision_is_terminal_for_p23(session_local):
    scenario = _prepare_scenario(
        session_local,
        target_index=3,
        prepare_final_intent=False,
    )
    decision = scenario.latest.convergence.decision
    assert decision.decision_type == "ESCALATE_TO_HUMAN"
    assert decision.decision_reason == "attempt_limit_exhausted"
    result = _call_latest_p23(scenario)
    assert result.result.blocked_reasons == ["p25_convergence_terminal"]
    assert result.message is None
    scenario.session.close()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("decision_fingerprint", "d" * 64),
        ("decision_replay_key", "c" * 64),
        ("decision_type", "CONVERGED"),
    ],
)
def test_tampered_convergence_decision_blocks_p23(
    session_local,
    field,
    value,
):
    scenario = _prepare_scenario(
        session_local,
        target_index=1,
        prepare_final_intent=False,
    )
    _tamper_action(
        scenario,
        scenario.latest.convergence.decision_message.id,
        field,
        value,
    )
    result = _call_latest_p23(scenario)
    assert result.result.intent_status == "blocked"
    assert result.result.blocked_reasons == ["history_invalid"]
    assert result.message is None
    scenario.session.close()


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("candidate_diff_id", uuid4()),
        ("candidate_diff_fingerprint", "f" * 64),
    ],
)
def test_candidate_diff_revalidation_conflict_blocks_p23(
    session_local,
    attribute,
    value,
):
    scenario = _prepare_scenario(
        session_local,
        target_index=1,
        prepare_final_intent=False,
    )
    current = scenario.latest.candidate_service._candidate_diff
    values = vars(current).copy()
    values[attribute] = value
    scenario.latest.candidate_service._candidate_diff = SimpleNamespace(**values)
    result = _call_latest_p23(scenario)
    assert result.result.blocked_reasons == ["convergence_decision_conflict"]
    assert result.message is None
    scenario.session.close()


@pytest.mark.parametrize(
    "attribute",
    [
        "review_result_fingerprint",
        "review_semantic_fingerprint",
    ],
)
def test_review_outcome_revalidation_conflict_blocks_p23(
    session_local,
    attribute,
):
    scenario = _prepare_scenario(
        session_local,
        target_index=1,
        prepare_final_intent=False,
    )
    scenario.latest.review_service._review_outcome = (
        scenario.latest.outcome.model_copy(update={attribute: "e" * 64})
    )
    result = _call_latest_p23(scenario)
    assert result.result.blocked_reasons == ["convergence_decision_conflict"]
    assert result.message is None
    scenario.session.close()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_review_outcome_message_id", str(uuid4())),
        ("source_p22_summary_message_id", str(uuid4())),
    ],
)
def test_persisted_binding_tamper_fails_closed(
    session_local,
    field,
    value,
):
    scenario = _prepare_scenario(
        session_local,
        target_index=1,
        prepare_final_intent=False,
    )
    _tamper_action(
        scenario,
        scenario.latest.convergence.decision_message.id,
        field,
        value,
    )
    result = _call_latest_p23(scenario)
    assert result.result.blocked_reasons == ["history_invalid"]
    assert result.message is None
    scenario.session.close()


def test_attempt_history_gap_blocks_p23(session_local):
    scenario = _prepare_scenario(
        session_local,
        target_index=2,
        prepare_final_intent=False,
    )
    history, _ = scenario.msg_repo.list_by_session_id(
        session_id=scenario.ids["session_id"], limit=200
    )
    index_one = [
        item
        for item in history
        if item.source_detail
        == P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL
        and item.suggested_actions[0].get("rework_attempt_index") == 1
    ]
    assert len(index_one) == 1
    row = scenario.session.get(ProjectDirectorMessageTable, index_one[0].id)
    scenario.session.delete(row)
    scenario.session.commit()
    result = _call_latest_p23(scenario)
    assert result.result.blocked_reasons == ["rework_attempt_history_invalid"]
    assert result.message is None
    scenario.session.close()


@pytest.mark.parametrize("target_index", [1, 2])
def test_persisted_intent_revalidates_exact_p25_bindings(
    session_local,
    target_index,
):
    scenario = _prepare_scenario(session_local, target_index=target_index)
    message = scenario.latest.prepared.message
    revalidated = (
        scenario.latest.intent_service
        .revalidate_persisted_protected_transition_dispatch_intent(
            session_id=scenario.ids["session_id"],
            source_task_id=scenario.ids["task_id"],
            source_intent_message_id=message.id,
        )
    )
    assert revalidated.blocked_reasons == []
    assert revalidated.result is not None
    assert revalidated.result.rework_attempt_index == target_index
    assert revalidated.result.source_p25_convergence_decision_message_id is not None
    assert revalidated.result.source_p25_candidate_diff_message_id is not None
    assert revalidated.result.source_p25_review_outcome_message_id is not None
    scenario.session.close()


def test_tampered_persisted_intent_fingerprint_fails_revalidation(session_local):
    scenario = _prepare_scenario(session_local, target_index=1)
    message = scenario.latest.prepared.message
    _tamper_action(
        scenario,
        message.id,
        "dispatch_intent_fingerprint",
        "f" * 64,
    )
    revalidated = (
        scenario.latest.intent_service
        .revalidate_persisted_protected_transition_dispatch_intent(
            session_id=scenario.ids["session_id"],
            source_task_id=scenario.ids["task_id"],
            source_intent_message_id=message.id,
        )
    )
    assert revalidated.result is None
    assert revalidated.blocked_reasons == ["source_dispatch_intent_invalid"]
    scenario.session.close()


@pytest.mark.parametrize(
    ("action_updates", "metadata_updates"),
    [
        ({"type": "wrong"}, None),
        ({"schema_version": _DELETE}, None),
        ({"source_p22_summary_message_id": _DELETE}, None),
        (None, {"role": "user"}),
        (None, {"source": "ai"}),
        (None, {"risk_level": "low"}),
        (None, {"requires_confirmation": True}),
    ],
)
def test_partial_p23_marker_poisoning_fails_closed(
    session_local,
    action_updates,
    metadata_updates,
):
    scenario = _prepare_scenario(session_local, target_index=1)
    before = count_messages_by_source_detail(
        scenario.msg_repo,
        scenario.ids["session_id"],
        P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL,
    )
    _clone_message(
        scenario,
        scenario.latest.prepared.message,
        action_updates=action_updates,
        metadata_updates=metadata_updates,
    )
    result = _call_latest_p23(scenario)
    assert result.result.intent_status == "blocked"
    assert result.result.blocked_reasons == ["rework_attempt_history_invalid"]
    assert result.message is None
    assert count_messages_by_source_detail(
        scenario.msg_repo,
        scenario.ids["session_id"],
        P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL,
    ) == before + 1
    scenario.session.close()


def test_missing_action_p23_marker_poisoning_fails_closed(session_local):
    scenario = _prepare_scenario(session_local, target_index=1)
    cloned = _clone_message(scenario, scenario.latest.prepared.message)
    row = scenario.session.get(ProjectDirectorMessageTable, cloned.id)
    row.suggested_actions_json = "[]"
    scenario.session.commit()
    result = _call_latest_p23(scenario)
    assert result.result.blocked_reasons == ["rework_attempt_history_invalid"]
    assert result.message is None
    scenario.session.close()


def test_duplicate_exact_p23_history_blocks_without_third_write(session_local):
    scenario = _prepare_scenario(session_local, target_index=1)
    _clone_message(scenario, scenario.latest.prepared.message)
    before = count_messages_by_source_detail(
        scenario.msg_repo,
        scenario.ids["session_id"],
        P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL,
    )
    result = _call_latest_p23(scenario)
    assert result.result.blocked_reasons == ["rework_attempt_history_invalid"]
    assert result.message is None
    assert count_messages_by_source_detail(
        scenario.msg_repo,
        scenario.ids["session_id"],
        P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL,
    ) == before
    scenario.session.close()


def _thread_intent_service(session_local, scenario):
    session, msg_repo, sess_repo, task_repo, *_ = make_repos(session_local)
    candidate_service = FakeCandidateDiffService(
        message_repository=msg_repo,
        candidate_diff=scenario.latest.candidate_diff,
        candidate_diff_message=msg_repo.get_by_id(
            scenario.latest.candidate_message.id
        ),
        package=scenario.latest.package,
        invocation_outcome=SimpleNamespace(
            outcome_id=scenario.latest.outcome.source_executor_outcome_id
        ),
    )
    review_service = FakeReviewExecutionService(
        message_repository=msg_repo,
        review_outcome=scenario.latest.outcome,
        review_outcome_message=msg_repo.get_by_id(
            scenario.latest.outcome_message.id
        ),
    )
    p22_service = _make_p22_service(session, msg_repo, sess_repo, task_repo)
    convergence_service, _, _ = make_convergence_service(
        session_local,
        msg_repo=msg_repo,
        candidate_diff_svc=candidate_service,
        review_execution_svc=review_service,
        post_review_automation_svc=p22_service,
    )
    session.rollback()
    return (
        session,
        ProjectDirectorProtectedTransitionDispatchIntentService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=task_repo,
            bounded_rework_convergence_service=convergence_service,
        ),
    )


def test_concurrent_exact_p23_input_persists_once(session_local):
    scenario = _prepare_scenario(
        session_local,
        target_index=1,
        prepare_final_intent=False,
    )
    scenario.session.close()
    barrier = threading.Barrier(2)
    results = []
    errors = []
    lock = threading.Lock()

    def invoke():
        session = None
        try:
            session, service = _thread_intent_service(session_local, scenario)
            barrier.wait()
            prepared = service.prepare_protected_transition_dispatch_intent(
                session_id=scenario.ids["session_id"],
                source_task_id=scenario.ids["task_id"],
                source_message_id=scenario.latest.p22_summary.message.id,
            )
            with lock:
                results.append(prepared)
        except BaseException as exc:
            with lock:
                errors.append(exc)
        finally:
            if session is not None:
                session.close()

    threads = [threading.Thread(target=invoke) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(results) == 2
    assert {item.result.intent_status for item in results} == {"prepared"}
    assert sorted(
        item.result.resumed_from_existing_intent for item in results
    ) == [False, True]
    assert len({item.message.id for item in results}) == 1
    check_session, check_repo, *_ = make_repos(session_local)
    assert count_messages_by_source_detail(
        check_repo,
        scenario.ids["session_id"],
        P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL,
    ) == 2
    check_session.close()


def test_blocked_path_releases_lock_and_has_no_partial_writes(session_local):
    scenario = _prepare_scenario(
        session_local,
        target_index=1,
        prepare_final_intent=False,
        persist_final_convergence=False,
    )
    before_intents = count_messages_by_source_detail(
        scenario.msg_repo,
        scenario.ids["session_id"],
        P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL,
    )
    before_runs = len(
        scenario.run_repo.list_by_task_id(scenario.ids["task_id"])
    )
    before_task = scenario.task_repo.get_by_id(scenario.ids["task_id"])
    assert before_task is not None
    before_task_status = before_task.status
    worker_details = (
        "p23_d2_worker_start_reserved",
        "p23_d2_worker_invocation_claimed",
        "p23_d2_worker_invocation_outcome_recorded",
    )
    before_worker_counts = {
        detail: count_messages_by_source_detail(
            scenario.msg_repo,
            scenario.ids["session_id"],
            detail,
        )
        for detail in worker_details
    }
    scenario.session.rollback()
    result = _call_latest_p23(scenario)
    assert result.result.blocked_reasons == ["next_attempt_decision_missing"]
    assert result.message is None
    assert count_messages_by_source_detail(
        scenario.msg_repo,
        scenario.ids["session_id"],
        P23_PROTECTED_TRANSITION_DISPATCH_INTENT_SOURCE_DETAIL,
    ) == before_intents
    assert len(
        scenario.run_repo.list_by_task_id(scenario.ids["task_id"])
    ) == before_runs
    assert (
        scenario.task_repo.get_by_id(scenario.ids["task_id"]).status
        == before_task_status
    )
    assert {
        detail: count_messages_by_source_detail(
            scenario.msg_repo,
            scenario.ids["session_id"],
            detail,
        )
        for detail in worker_details
    } == before_worker_counts
    scenario.session.close()

    lock_session = session_local()
    lock_session.execute(text("BEGIN IMMEDIATE"))
    lock_session.commit()
    lock_session.close()


def test_p23_intent_does_not_project_sensitive_upstream_text(session_local):
    scenario = _prepare_scenario(
        session_local,
        target_index=1,
        final_summary_suffix=_P23_SENTINEL,
    )
    message = scenario.latest.prepared.message
    serialized = json.dumps(message.model_dump(mode="json"), sort_keys=True)
    assert _P23_SENTINEL not in serialized
    scenario.session.close()


def test_valid_p25_auto_rework_reaches_b1_reservation(session_local):
    scenario = _prepare_scenario(session_local, target_index=1)
    freshness_service = scenario.p22_service._freshness_service
    preflight_service = (
        ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService(
            session_repository=scenario.sess_repo,
            message_repository=scenario.msg_repo,
            task_repository=scenario.task_repo,
            dispatch_intent_service=scenario.latest.intent_service,
            freshness_service=freshness_service,
            task_readiness_service=FakeTaskReadinessService(),
            task_state_machine_service=FakeTaskStateMachineService(),
            budget_guard_service=FakeBudgetGuardService(
                session=scenario.session
            ),
        )
    )
    preflight = (
        preflight_service
        .prepare_protected_transition_dispatch_consumption_preflight(
            session_id=scenario.ids["session_id"],
            source_task_id=scenario.ids["task_id"],
            source_message_id=scenario.latest.prepared.message.id,
        )
    )
    assert preflight.result.preflight_status == "ready"
    assert preflight.message is not None

    d1_service, *_ = make_d1_service(
        session_local,
        preflight_svc=preflight_service,
        msg_repo=scenario.msg_repo,
        task_repo=scenario.task_repo,
        run_repo=scenario.run_repo,
    )
    d1 = d1_service.consume_protected_transition_dispatch_preflight(
        session_id=scenario.ids["session_id"],
        source_task_id=scenario.ids["task_id"],
        source_message_id=preflight.message.id,
    )
    assert d1.result.consumption_status == "reserved_for_worker_start"
    assert d1.message is not None

    b1_service, *_ = make_b1_service(
        session_local,
        msg_repo=scenario.msg_repo,
        task_repo=scenario.task_repo,
        run_repo=scenario.run_repo,
        d1_service=d1_service,
    )
    b1 = b1_service.prepare_protected_transition_worker_start_reservation(
        session_id=scenario.ids["session_id"],
        source_task_id=scenario.ids["task_id"],
        source_message_id=d1.message.id,
    )
    assert b1.result.blocked_reasons == []
    assert b1.result.reservation_status == "reserved"
    assert b1.message is not None
    scenario.session.close()
