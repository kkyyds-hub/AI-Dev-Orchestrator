"""Tests for P23 Protected Transition Dispatch Intent and Auto-Advance."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4

import pytest
from sqlalchemy.orm import sessionmaker

from app.domain.project_director_protected_transition_auto_advance import (
    ProjectDirectorProtectedTransitionAutoAdvanceResult,
)
from app.domain.project_director_protected_transition_dispatch_consumption import (
    ProjectDirectorProtectedTransitionDispatchConsumptionResult,
)
from app.domain.project_director_protected_transition_dispatch_consumption_preflight import (
    ProjectDirectorProtectedTransitionDispatchConsumptionPreflightResult,
)
from app.domain.project_director_protected_transition_dispatch_intent import (
    ProjectDirectorProtectedTransitionDispatchIntentResult,
)
from app.domain.project_director_protected_transition_worker_invocation import (
    ProjectDirectorProtectedTransitionWorkerInvocationClaimResult,
    ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult,
)
from app.domain.project_director_protected_transition_worker_start_reservation import (
    ProjectDirectorProtectedTransitionWorkerStartReservationResult,
)
from tests.p23_test_support import (
    make_repos,
    make_session_factory,
    make_test_engine,
    seed_base_records,
)


# ══════════════════════════════════════════════════════════════════════
# DomainModel Validator Tests
# ══════════════════════════════════════════════════════════════════════


class TestDispatchIntentDomainModel:
    def test_prepared_requires_evidence_ids(self) -> None:
        with pytest.raises(ValueError, match="完整证据身份"):
            ProjectDirectorProtectedTransitionDispatchIntentResult(
                intent_status="prepared",
                session_id=uuid4(),
                source_task_id=uuid4(),
                source_p22_summary_message_id=uuid4(),
            )

    def test_blocked_requires_reasons(self) -> None:
        with pytest.raises(ValueError, match="blocked 调度意图必须包含原因"):
            ProjectDirectorProtectedTransitionDispatchIntentResult(
                intent_status="blocked",
                session_id=uuid4(),
                source_task_id=uuid4(),
                source_p22_summary_message_id=uuid4(),
                blocked_reasons=[],
            )

    def test_prepared_target_must_equal_source(self) -> None:
        with pytest.raises(ValueError, match="调度目标必须是来源任务"):
            ProjectDirectorProtectedTransitionDispatchIntentResult(
                intent_status="prepared",
                dispatch_intent_id=uuid4(),
                dispatch_intent_fingerprint="a" * 64,
                session_id=uuid4(),
                project_id=uuid4(),
                source_task_id=uuid4(),
                target_task_id=uuid4(),
                source_p22_summary_message_id=uuid4(),
                source_review_message_id=uuid4(),
                source_disposition_message_id=uuid4(),
                source_consumption_preflight_message_id=uuid4(),
                source_consumption_message_id=uuid4(),
                source_handoff_message_id=uuid4(),
                source_freshness_message_id=uuid4(),
                disposition_type="AUTO_CONTINUE",
                transition_kind="CONTINUE_GUARDRAIL",
                transition_authority="AUTOMATED_DISPOSITION",
                dispatch_kind="auto_continue",
                target_task_strategy="source_task_continue",
                review_result_fingerprint="a" * 64,
                review_semantic_fingerprint="a" * 64,
                freshness_evidence_fingerprint="a" * 64,
                source_diff_sha256="a" * 64,
                review_scope_paths=["src/example.py"],
                workspace_path="/tmp/ws",
                workspace_path_within_root=True,
                source_freshness_validated_at="2026-01-01T00:00:00Z",
                replay_check_completed=True,
            )

    def test_prepared_no_blocked_reasons(self) -> None:
        sid = uuid4()
        with pytest.raises(ValueError, match="prepared 调度意图不得包含 blocked 原因"):
            ProjectDirectorProtectedTransitionDispatchIntentResult(
                intent_status="prepared",
                dispatch_intent_id=uuid4(),
                dispatch_intent_fingerprint="a" * 64,
                session_id=uuid4(),
                project_id=uuid4(),
                source_task_id=sid,
                target_task_id=sid,
                source_p22_summary_message_id=uuid4(),
                source_review_message_id=uuid4(),
                source_disposition_message_id=uuid4(),
                source_consumption_preflight_message_id=uuid4(),
                source_consumption_message_id=uuid4(),
                source_handoff_message_id=uuid4(),
                source_freshness_message_id=uuid4(),
                disposition_type="AUTO_CONTINUE",
                transition_kind="CONTINUE_GUARDRAIL",
                transition_authority="AUTOMATED_DISPOSITION",
                dispatch_kind="auto_continue",
                target_task_strategy="source_task_continue",
                review_result_fingerprint="a" * 64,
                review_semantic_fingerprint="a" * 64,
                freshness_evidence_fingerprint="a" * 64,
                source_diff_sha256="a" * 64,
                review_scope_paths=["src/example.py"],
                workspace_path="/tmp/ws",
                workspace_path_within_root=True,
                source_freshness_validated_at="2026-01-01T00:00:00Z",
                replay_check_completed=True,
                blocked_reasons=["x"],
            )

    @pytest.mark.parametrize("flag", [
        "task_status_mutated", "task_created", "run_created", "worker_started",
        "runtime_started", "continuation_started", "rework_started", "worktree_created",
        "main_project_file_written", "sandbox_file_written", "manifest_file_written",
        "diff_file_written", "file_written", "patch_applied", "git_write_performed",
        "gate_allows_write", "product_runtime_git_write_allowed",
    ])
    def test_forbidden_side_effect_flag_rejected(self, flag: str) -> None:
        with pytest.raises(ValueError, match="调度意图准备不得产生执行或写入副作用"):
            ProjectDirectorProtectedTransitionDispatchIntentResult(
                intent_status="blocked",
                session_id=uuid4(),
                source_task_id=uuid4(),
                source_p22_summary_message_id=uuid4(),
                blocked_reasons=["x"],
                **{flag: True},
            )


class TestConsumptionDomainModel:
    def test_blocked_requires_reasons(self) -> None:
        with pytest.raises(ValueError, match="blocked 消费必须包含原因"):
            ProjectDirectorProtectedTransitionDispatchConsumptionResult(
                consumption_status="blocked",
                session_id=uuid4(),
                source_task_id=uuid4(),
                source_preflight_message_id=uuid4(),
                blocked_reasons=[],
            )

    def test_blocked_no_consumption_id(self) -> None:
        with pytest.raises(ValueError, match="blocked 消费不得创建 consumption 记录"):
            ProjectDirectorProtectedTransitionDispatchConsumptionResult(
                consumption_status="blocked",
                consumption_id=uuid4(),
                session_id=uuid4(),
                source_task_id=uuid4(),
                source_preflight_message_id=uuid4(),
                blocked_reasons=["x"],
            )

    def test_continuation_and_rework_both_true_rejected(self) -> None:
        with pytest.raises(ValueError):
            ProjectDirectorProtectedTransitionAutoAdvanceResult(
                auto_advance_status="worker_returned",
                session_id=uuid4(),
                source_task_id=uuid4(),
                source_review_message_id=uuid4(),
                source_p22_summary_message_id=uuid4(),
                source_dispatch_intent_message_id=uuid4(),
                source_dispatch_consumption_preflight_message_id=uuid4(),
                source_dispatch_consumption_message_id=uuid4(),
                source_worker_start_reservation_message_id=uuid4(),
                source_worker_invocation_claim_message_id=uuid4(),
                source_worker_invocation_outcome_message_id=uuid4(),
                route="automatic_continuation",
                disposition_type="AUTO_CONTINUE",
                dispatch_kind="auto_continue",
                target_task_strategy="source_task_continue",
                run_id=uuid4(),
                worker_invocation_claimed=True,
                worker_call_attempted=True,
                worker_returned=True,
                worker_outcome_status="returned",
                continuation_started=True,
                rework_started=True,
            )

    def test_git_write_authority_rejected(self) -> None:
        with pytest.raises(ValueError):
            ProjectDirectorProtectedTransitionAutoAdvanceResult(
                auto_advance_status="blocked",
                session_id=uuid4(),
                source_task_id=uuid4(),
                source_review_message_id=uuid4(),
                blocked_reasons=["x"],
                product_runtime_git_write_allowed=True,
            )

    def test_coordinator_created_task_rejected(self) -> None:
        with pytest.raises(ValueError):
            ProjectDirectorProtectedTransitionAutoAdvanceResult(
                auto_advance_status="blocked",
                session_id=uuid4(),
                source_task_id=uuid4(),
                source_review_message_id=uuid4(),
                blocked_reasons=["x"],
                coordinator_created_task=True,
            )


class TestWorkerInvocationOutcomeDomainModel:
    def test_not_invoked_no_worker_call(self) -> None:
        claim_id = uuid4()
        with pytest.raises(ValueError, match="not_invoked outcome has contradictory"):
            ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult(
                outcome_status="not_invoked",
                outcome_id=uuid4(),
                outcome_fingerprint="a" * 64,
                session_id=uuid4(),
                project_id=uuid4(),
                source_task_id=uuid4(),
                run_id=uuid4(),
                source_claim_message_id=claim_id,
                source_claim_id=claim_id,
                source_claim_fingerprint="a" * 64,
                source_claim_token="token",
                source_reservation_message_id=uuid4(),
                source_reservation_fingerprint="a" * 64,
                source_consumption_message_id=uuid4(),
                disposition_type="AUTO_CONTINUE",
                dispatch_kind="auto_continue",
                target_task_strategy="source_task_continue",
                worker_call_attempted=True,
                worker_returned=False,
                worker_raised=False,
                worker_result_contract_valid=False,
                reserved_snapshot_present=False,
                replay_check_completed=True,
                blocked_reasons=["x"],
            )

    def test_git_boundary_requires_human_recovery(self) -> None:
        with pytest.raises(ValueError, match="reported Git activity requires explicit human recovery"):
            ProjectDirectorProtectedTransitionAutoAdvanceResult(
                auto_advance_status="worker_returned",
                current_step="worker_invocation_outcome",
                session_id=uuid4(),
                source_task_id=uuid4(),
                source_review_message_id=uuid4(),
                source_p22_summary_message_id=uuid4(),
                source_dispatch_intent_message_id=uuid4(),
                source_dispatch_consumption_preflight_message_id=uuid4(),
                source_dispatch_consumption_message_id=uuid4(),
                source_worker_start_reservation_message_id=uuid4(),
                source_worker_invocation_claim_message_id=uuid4(),
                source_worker_invocation_outcome_message_id=uuid4(),
                route="automatic_continuation",
                disposition_type="AUTO_CONTINUE",
                dispatch_kind="auto_continue",
                target_task_strategy="source_task_continue",
                run_id=uuid4(),
                worker_invocation_claimed=True,
                worker_call_attempted=True,
                worker_returned=True,
                worker_outcome_status="returned",
                continuation_started=True,
                worker_reported_git_write_activity=True,
                human_recovery_required=False,
            )


class TestAutoAdvanceDomainModel:
    def test_waiting_for_human_no_p23_ids(self) -> None:
        with pytest.raises(ValueError, match="waiting_for_human evidence is inconsistent"):
            ProjectDirectorProtectedTransitionAutoAdvanceResult(
                auto_advance_status="waiting_for_human",
                current_step="p22_waiting_for_human",
                session_id=uuid4(),
                source_task_id=uuid4(),
                source_review_message_id=uuid4(),
                source_p22_summary_message_id=uuid4(),
                route="human_escalation",
                source_dispatch_intent_message_id=uuid4(),
            )

    def test_blocked_no_worker_invocation(self) -> None:
        with pytest.raises(ValueError, match="blocked status must precede Worker invocation claim"):
            ProjectDirectorProtectedTransitionAutoAdvanceResult(
                auto_advance_status="blocked",
                current_step="dispatch_intent",
                session_id=uuid4(),
                source_task_id=uuid4(),
                source_review_message_id=uuid4(),
                blocked_reasons=["x"],
                worker_invocation_claimed=True,
            )

    def test_recovery_requires_human_recovery(self) -> None:
        with pytest.raises(ValueError, match="recovery_required needs reasons"):
            ProjectDirectorProtectedTransitionAutoAdvanceResult(
                auto_advance_status="recovery_required",
                current_step="worker_invocation_outcome",
                session_id=uuid4(),
                source_task_id=uuid4(),
                source_review_message_id=uuid4(),
                human_recovery_required=False,
                blocked_reasons=["x"],
            )


class TestWorkerStartReservationDomainModel:
    def test_blocked_no_reservation_id(self) -> None:
        with pytest.raises(ValueError, match="blocked reservation cannot create a reservation record"):
            ProjectDirectorProtectedTransitionWorkerStartReservationResult(
                reservation_status="blocked",
                reservation_id=uuid4(),
                session_id=uuid4(),
                source_task_id=uuid4(),
                source_consumption_message_id=uuid4(),
                blocked_reasons=["x"],
            )

    @pytest.mark.parametrize("flag", [
        "worker_started", "agent_session_created", "runtime_started",
        "continuation_started", "rework_started", "task_created", "run_created",
        "task_status_mutated", "run_status_mutated", "git_write_performed",
        "gate_allows_write", "product_runtime_git_write_allowed",
    ])
    def test_forbidden_side_effect_flag_rejected(self, flag: str) -> None:
        with pytest.raises(ValueError, match="Worker start reservation cannot report side effects"):
            ProjectDirectorProtectedTransitionWorkerStartReservationResult(
                reservation_status="blocked",
                session_id=uuid4(),
                source_task_id=uuid4(),
                source_consumption_message_id=uuid4(),
                blocked_reasons=["x"],
                **{flag: True},
            )
