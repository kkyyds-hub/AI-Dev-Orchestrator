"""P2-B Worker AgentSession.workspace_path read-only validation.

These tests cover the pure validation seam only. They do not invoke the worker
loop, do not start services, do not run git commands, and do not create or
clean real git worktrees.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.api.routes.workers import WorkerRunOnceResponse
from app.domain._base import utc_now
from app.domain.agent_session import (
    AgentSession,
    AgentSessionPhase,
    AgentSessionReviewStatus,
    AgentSessionStatus,
    AgentType,
    CodingSessionActivityState,
    CodingSessionStatus,
    RuntimeType,
    WorkspaceType,
)
from app.domain.delivery_gate_evidence import DELIVERY_AUDIT_COLLECTED_EVENT_TYPE
from app.domain.prompt_contract import BuiltPromptEnvelope, PromptTemplateRef
from app.domain.run import (
    Run,
    RunBudgetPressureLevel,
    RunBudgetStrategyAction,
    RunFailureCategory,
    RunStatus,
)
from app.domain.task import (
    Task,
    TaskHumanStatus,
    TaskPriority,
    TaskRiskLevel,
    TaskStatus,
)
from app.services.budget_guard_service import (
    BudgetGuardDecision,
    BudgetSnapshot,
    RetryStatus,
)
from app.services.cost_estimator_service import CostEstimatorService
from app.services.context_builder_service import (
    AgentThreadContextSeed,
    TaskContextPackage,
)
from app.services.executor_service import ExecutionPlan, ExecutionResult
from app.services.git_diff_dry_run_runner import GitDiffDryRunResult
from app.services.task_router_service import TaskRoutingDecision
from app.services.task_state_machine_service import TaskStateMachineService
from app.services.token_accounting_service import TokenAccountingService
from app.services.verifier_service import VerificationResult
from app.workers.task_worker import (
    TaskWorker,
    WorkerRunResult,
    build_worker_runtime_launch_dry_run,
    resolve_worker_workspace_context,
    validate_worker_agent_workspace,
)
from app.workers.runtime_adapter import (
    RuntimeLifecycleReason,
    RuntimeLifecycleSnapshot,
    RuntimeLifecycleState,
)
from app.workers.worktree_safe_command import (
    WorkerPwdCommandResult,
    WorkerPwdCommandSpec,
    WorkerWorktreeSafeCommandProof,
    WorkerWorktreeSafeCommandProofRunner,
)


class _FakePwdCommandRunner:
    def __init__(
        self,
        *,
        return_code: int = 0,
        stdout: str | None = None,
        stderr: str = "",
        mutates_workspace: bool = False,
    ) -> None:
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr
        self.mutates_workspace = mutates_workspace
        self.requested_cwd: str | None = None
        self.ran_spec: WorkerPwdCommandSpec | None = None

    def pwd(
        self,
        *,
        cwd: str,
    ) -> WorkerPwdCommandSpec:
        self.requested_cwd = cwd
        return WorkerPwdCommandSpec(
            argv=("pwd",),
            cwd=cwd,
            timeout_seconds=30,
            mutates_workspace=self.mutates_workspace,
        )

    def run(self, spec: WorkerPwdCommandSpec) -> WorkerPwdCommandResult:
        self.ran_spec = spec
        return WorkerPwdCommandResult(
            spec=spec,
            return_code=self.return_code,
            stdout=self.stdout if self.stdout is not None else f"{spec.cwd}\n",
            stderr=self.stderr,
        )


class _SpyRuntimeEventAuditService:
    def __init__(self, *, raises: Exception | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.raises = raises

    def record_launch_gate_event(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises is not None:
            raise self.raises
        return None


class _SpyDeliveryEventAuditService:
    def __init__(self, *, raises: Exception | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.raises = raises

    def record_diff_dry_run_event(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises is not None:
            raise self.raises
        return SimpleNamespace(event_type=DELIVERY_AUDIT_COLLECTED_EVENT_TYPE)


def _session(
    *,
    workspace_type: WorkspaceType | None = WorkspaceType.WORKTREE,
    workspace_path: str | None = None,
    workspace_clean: bool | None = None,
    branch_name: str | None = None,
    agent_type: AgentType | None = AgentType.OPENAI_PROVIDER,
    runtime_type: RuntimeType | None = RuntimeType.SUBPROCESS,
) -> AgentSession:
    return AgentSession(
        project_id=uuid4(),
        task_id=uuid4(),
        run_id=uuid4(),
        agent_type=agent_type,
        runtime_type=runtime_type,
        branch_name=branch_name,
        workspace_type=workspace_type,
        workspace_path=workspace_path,
        workspace_clean=workspace_clean,
    )


def test_validate_worker_agent_workspace_skips_non_worktree_sessions():
    result = validate_worker_agent_workspace(
        _session(workspace_type=WorkspaceType.IN_PLACE)
    )

    assert result.ready is True
    assert result.reason_code is None
    assert result.workspace_type == "in_place"
    assert result.resolved_workspace_path is None

    context = resolve_worker_workspace_context(result)

    assert context.ready is True
    assert context.source == "agent_session_non_worktree"
    assert context.uses_agent_workspace is False
    assert context.changes_cwd is False
    assert context.runs_git is False
    assert context.runs_write_git is False
    assert context.launches_runtime is False


def test_validate_worker_agent_workspace_blocks_missing_worktree_path():
    result = validate_worker_agent_workspace(_session(workspace_path=None))

    assert result.ready is False
    assert result.reason_code == "workspace_path_missing"
    assert "requires workspace_path" in result.summary

    context = resolve_worker_workspace_context(result)

    assert context.ready is False
    assert context.source == "agent_session_worktree_blocked"
    assert context.reason_code == "workspace_path_missing"
    assert context.uses_agent_workspace is False
    assert context.changes_cwd is False
    assert context.runs_write_git is False


def test_validate_worker_agent_workspace_blocks_relative_worktree_path():
    result = validate_worker_agent_workspace(
        _session(workspace_path="relative/worktree", workspace_clean=True)
    )

    assert result.ready is False
    assert result.reason_code == "workspace_path_not_absolute"


def test_validate_worker_agent_workspace_blocks_missing_directory(tmp_path):
    missing_path = tmp_path / "missing-worktree"
    result = validate_worker_agent_workspace(
        _session(workspace_path=missing_path.as_posix(), workspace_clean=True)
    )

    assert result.ready is False
    assert result.reason_code == "workspace_path_not_found"
    assert result.resolved_workspace_path == missing_path.as_posix()


def test_validate_worker_agent_workspace_blocks_file_path(tmp_path):
    file_path = tmp_path / "not-a-directory"
    file_path.write_text("not a worktree directory\n")

    result = validate_worker_agent_workspace(
        _session(workspace_path=file_path.as_posix(), workspace_clean=True)
    )

    assert result.ready is False
    assert result.reason_code == "workspace_path_not_directory"


def test_validate_worker_agent_workspace_blocks_unknown_clean_state(tmp_path):
    result = validate_worker_agent_workspace(
        _session(workspace_path=tmp_path.as_posix(), workspace_clean=None)
    )

    assert result.ready is False
    assert result.reason_code == "workspace_clean_unknown"
    assert "does not run git status" in result.summary


def test_validate_worker_agent_workspace_blocks_dirty_metadata(tmp_path):
    result = validate_worker_agent_workspace(
        _session(workspace_path=tmp_path.as_posix(), workspace_clean=False)
    )

    assert result.ready is False
    assert result.reason_code == "workspace_dirty"


def test_validate_worker_agent_workspace_accepts_existing_clean_worktree_metadata(
    tmp_path,
):
    result = validate_worker_agent_workspace(
        _session(workspace_path=tmp_path.as_posix(), workspace_clean=True)
    )

    assert result.ready is True
    assert result.reason_code is None
    assert result.workspace_type == "worktree"
    assert result.workspace_path == tmp_path.as_posix()
    assert result.workspace_clean is True
    assert result.resolved_workspace_path == tmp_path.as_posix()

    context = resolve_worker_workspace_context(result)

    assert context.ready is True
    assert context.source == "agent_session_worktree"
    assert context.workspace_path == tmp_path.as_posix()
    assert context.resolved_workspace_path == tmp_path.as_posix()
    assert context.uses_agent_workspace is True
    assert context.changes_cwd is False
    assert context.runs_git is False
    assert context.runs_write_git is False
    assert context.launches_runtime is False


def test_runtime_launch_dry_run_targets_clean_worktree_without_execution(tmp_path):
    session = _session(workspace_path=tmp_path.as_posix(), workspace_clean=True)
    validation = validate_worker_agent_workspace(session)
    context = resolve_worker_workspace_context(validation)

    dry_run = build_worker_runtime_launch_dry_run(
        agent_session=session,
        workspace_context=context,
    )

    assert dry_run.ready is True
    assert dry_run.source == "agent_session_worktree_runtime_dry_run"
    assert dry_run.reason_code is None
    assert dry_run.session_id == str(session.id)
    assert dry_run.agent_type == "openai_provider"
    assert dry_run.runtime_type == "subprocess"
    assert dry_run.workspace_path == tmp_path.as_posix()
    assert dry_run.resolved_workspace_path == tmp_path.as_posix()
    assert dry_run.launch_cwd_preview == tmp_path.as_posix()
    assert tmp_path.as_posix() in (dry_run.launch_command_preview or "")
    assert dry_run.uses_agent_workspace is True
    assert dry_run.command_preview_uses_workspace is True
    assert dry_run.execution_enabled is False
    assert dry_run.changes_cwd is False
    assert dry_run.runs_command is False
    assert dry_run.runs_git is False
    assert dry_run.runs_write_git is False
    assert dry_run.launches_runtime is False


def test_worktree_safe_command_proof_runs_one_allowlisted_probe_in_worktree(
    tmp_path,
):
    session = _session(workspace_path=tmp_path.as_posix(), workspace_clean=True)
    validation = validate_worker_agent_workspace(session)
    context = resolve_worker_workspace_context(validation)
    fake_runner = _FakePwdCommandRunner()
    proof_runner = WorkerWorktreeSafeCommandProofRunner(
        command_runner=fake_runner,
    )

    proof = proof_runner.run_probe(workspace_context=context)

    assert proof.ready is True
    assert proof.source == "agent_session_worktree_safe_command"
    assert proof.reason_code is None
    assert proof.command == "pwd"
    assert proof.cwd == tmp_path.as_posix()
    assert proof.expected_workspace_path == tmp_path.as_posix()
    assert proof.observed_pwd == tmp_path.as_posix()
    assert proof.pwd_matches_workspace_path is True
    assert proof.exit_code == 0
    assert proof.stdout == tmp_path.as_posix()
    assert proof.stderr == ""
    assert proof.timed_out is False
    assert proof.read_only is True
    assert proof.allowlisted is True
    assert proof.uses_agent_workspace is True
    assert proof.changes_process_cwd is False
    assert proof.runs_command is True
    assert proof.runs_git is False
    assert proof.runs_write_git is False
    assert proof.launches_worker_loop is False
    assert proof.launches_ai_runtime is False
    assert fake_runner.requested_cwd == tmp_path.as_posix()
    assert fake_runner.ran_spec is not None
    assert fake_runner.ran_spec.argv == ("pwd",)
    assert fake_runner.ran_spec.cwd == tmp_path.as_posix()
    assert fake_runner.ran_spec.mutates_workspace is False


def test_worktree_safe_command_proof_blocks_failed_probe(tmp_path):
    session = _session(workspace_path=tmp_path.as_posix(), workspace_clean=True)
    validation = validate_worker_agent_workspace(session)
    context = resolve_worker_workspace_context(validation)
    proof_runner = WorkerWorktreeSafeCommandProofRunner(
        command_runner=_FakePwdCommandRunner(
            return_code=128,
            stdout="",
            stderr="pwd failed",
        ),
    )

    proof = proof_runner.run_probe(workspace_context=context)

    assert proof.ready is False
    assert proof.source == "agent_session_worktree_safe_command_blocked"
    assert proof.reason_code == "safe_command_failed"
    assert proof.command == "pwd"
    assert proof.cwd == tmp_path.as_posix()
    assert proof.expected_workspace_path == tmp_path.as_posix()
    assert proof.observed_pwd is None
    assert proof.pwd_matches_workspace_path is False
    assert proof.exit_code == 128
    assert proof.stderr == "pwd failed"
    assert proof.read_only is True
    assert proof.allowlisted is True
    assert proof.runs_command is True
    assert proof.runs_git is False
    assert proof.runs_write_git is False
    assert proof.launches_worker_loop is False
    assert proof.launches_ai_runtime is False


def test_worktree_safe_command_proof_blocks_pwd_workspace_path_mismatch(tmp_path):
    session = _session(workspace_path=tmp_path.as_posix(), workspace_clean=True)
    validation = validate_worker_agent_workspace(session)
    context = resolve_worker_workspace_context(validation)
    proof_runner = WorkerWorktreeSafeCommandProofRunner(
        command_runner=_FakePwdCommandRunner(stdout="/different/worktree\n"),
    )

    proof = proof_runner.run_probe(workspace_context=context)

    assert proof.ready is False
    assert proof.reason_code == "pwd_mismatch_workspace_path"
    assert proof.command == "pwd"
    assert proof.cwd == tmp_path.as_posix()
    assert proof.expected_workspace_path == tmp_path.as_posix()
    assert proof.observed_pwd == "/different/worktree"
    assert proof.pwd_matches_workspace_path is False
    assert proof.read_only is True
    assert proof.allowlisted is True
    assert proof.runs_command is True
    assert proof.runs_git is False
    assert proof.runs_write_git is False
    assert proof.launches_worker_loop is False
    assert proof.launches_ai_runtime is False


def test_worktree_safe_command_proof_skips_non_worktree_without_execution():
    session = _session(workspace_type=WorkspaceType.IN_PLACE)
    validation = validate_worker_agent_workspace(session)
    context = resolve_worker_workspace_context(validation)
    fake_runner = _FakePwdCommandRunner()
    proof_runner = WorkerWorktreeSafeCommandProofRunner(
        command_runner=fake_runner,
    )

    proof = proof_runner.run_probe(workspace_context=context)

    assert proof.ready is True
    assert proof.source == "agent_session_non_worktree_safe_command_skipped"
    assert proof.command is None
    assert proof.cwd is None
    assert proof.expected_workspace_path is None
    assert proof.observed_pwd is None
    assert proof.pwd_matches_workspace_path is None
    assert proof.allowlisted is False
    assert proof.uses_agent_workspace is False
    assert proof.runs_command is False
    assert proof.runs_git is False
    assert proof.runs_write_git is False
    assert proof.launches_worker_loop is False
    assert proof.launches_ai_runtime is False
    assert fake_runner.ran_spec is None


def test_worktree_safe_command_proof_rejects_mutating_probe_spec(tmp_path):
    session = _session(workspace_path=tmp_path.as_posix(), workspace_clean=True)
    validation = validate_worker_agent_workspace(session)
    context = resolve_worker_workspace_context(validation)
    proof_runner = WorkerWorktreeSafeCommandProofRunner(
        command_runner=_FakePwdCommandRunner(mutates_workspace=True),
    )

    proof = proof_runner.run_probe(workspace_context=context)

    assert proof.ready is False
    assert proof.reason_code == "safe_command_not_allowlisted"
    assert proof.read_only is False
    assert proof.allowlisted is False
    assert proof.runs_command is True
    assert proof.runs_git is False
    assert proof.runs_write_git is False
    assert proof.launches_worker_loop is False
    assert proof.launches_ai_runtime is False


class _NoopDbSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class _FakeTaskRepository:
    def __init__(self, task: Task) -> None:
        self.task = task

    def get_by_id(self, task_id):
        assert task_id == self.task.id
        return self.task

    def claim_pending_task(self, task_id):
        assert task_id == self.task.id
        if self.task.status != TaskStatus.PENDING:
            return None
        self.task = self.task.model_copy(
            update={"status": TaskStatus.RUNNING, "updated_at": utc_now()}
        )
        return self.task

    def update_control_state(self, task_id, **kwargs):
        assert task_id == self.task.id
        self.task = self.task.model_copy(
            update={**kwargs, "updated_at": utc_now()}
        )
        return self.task


class _FakeRunRepository:
    def __init__(self) -> None:
        self.run: Run | None = None

    def get_by_id(self, run_id):
        assert self.run is not None
        assert run_id == self.run.id
        return self.run

    def create_running_run(self, *, task_id, **kwargs):
        self.run = Run(
            task_id=task_id,
            status=RunStatus.RUNNING,
            started_at=utc_now(),
            **kwargs,
        )
        return self.run

    def set_log_path(self, run_id, log_path):
        assert self.run is not None
        assert run_id == self.run.id
        self.run = self.run.model_copy(update={"log_path": log_path})
        return self.run

    def finish_run(self, run_id, **kwargs):
        assert self.run is not None
        assert run_id == self.run.id
        self.run = self.run.model_copy(
            update={**kwargs, "finished_at": utc_now()}
        )
        return self.run


class _ExplodingExecutorService:
    def __init__(self) -> None:
        self.build_execution_plan_calls = 0
        self.execute_task_calls = 0

    def build_execution_plan(self, *args, **kwargs):
        self.build_execution_plan_calls += 1
        raise AssertionError("executor plan must not be built when proof fails")

    def execute_task(self, *args, **kwargs):
        self.execute_task_calls += 1
        raise AssertionError("executor must not run when proof fails")


class _FakeExecutorService:
    def __init__(self, *, success: bool = True) -> None:
        self.success = success
        self.build_execution_plan_calls = 0
        self.execute_task_calls = 0

    def build_execution_plan(self, *, task, routing_contract):
        self.build_execution_plan_calls += 1
        return ExecutionPlan(
            mode="simulate",
            payload=task.input_summary,
            routing_contract=routing_contract,
        )

    def execute_task(
        self,
        task,
        *,
        context_package,
        routing_contract,
        prompt_envelope,
    ):
        self.execute_task_calls += 1
        return ExecutionResult(
            success=self.success,
            mode="simulate",
            summary=(
                "Fake execution succeeded."
                if self.success
                else "Fake execution failed."
            ),
            prompt_key=prompt_envelope.template_ref.prompt_key,
            prompt_char_count=prompt_envelope.prompt_char_count,
            actual_execution_mode="simulate",
        )


class _FakeModelRoutingService:
    def build_contract_from_strategy_decision(self, strategy_decision):
        return None


class _FakePromptBuilderService:
    def build_execution_prompt(
        self,
        *,
        task,
        context_package,
        execution_plan,
        routing_contract,
    ):
        prompt_text = f"{task.title}\n{task.input_summary}"
        return BuiltPromptEnvelope(
            template_ref=PromptTemplateRef(
                prompt_key="test.worker.diff_dry_run",
                version="p4-b2-r1",
                description="Test prompt envelope for worker diff dry-run evidence.",
            ),
            prompt_text=prompt_text,
            prompt_char_count=len(prompt_text),
        )


class _PassingVerifierService:
    def verify_task(self, *, task, execution_result):
        return VerificationResult(
            success=True,
            mode="test",
            summary="Fake verification passed.",
            quality_gate_passed=True,
        )


class _AllowingBudgetGuardService:
    def evaluate_before_execution(self, task_id, *, project_id=None):
        budget = BudgetSnapshot(
            daily_budget_usd=100.0,
            daily_cost_used=0.0,
            daily_cost_remaining=100.0,
            daily_usage_ratio=0.0,
            daily_budget_exceeded=False,
            daily_window_started_at=utc_now(),
            session_budget_usd=100.0,
            session_cost_used=0.0,
            session_cost_remaining=100.0,
            session_usage_ratio=0.0,
            session_budget_exceeded=False,
            session_started_at=utc_now(),
            max_task_retries=3,
            pressure_level=RunBudgetPressureLevel.NORMAL,
            suggested_action=RunBudgetStrategyAction.FULL_SPEED,
            strategy_code="test_allow",
            strategy_label="Test allow",
            strategy_summary="Test budget allows execution.",
            preferred_model_tier="standard",
            budget_blocked_runs_daily=0,
            budget_blocked_runs_session=0,
        )
        retry_status = RetryStatus(
            execution_attempts=0,
            max_task_retries=3,
            retries_used=0,
            retries_remaining=3,
            retry_limit_reached=False,
        )
        return BudgetGuardDecision(
            allowed=True,
            summary=None,
            failure_category=None,
            pressure_level=RunBudgetPressureLevel.NORMAL,
            suggested_action=RunBudgetStrategyAction.FULL_SPEED,
            strategy_code="test_allow",
            budget=budget,
            retry_status=retry_status,
        )


class _NoopRunLoggingService:
    def __init__(self) -> None:
        self.events: list[str] = []

    def initialize_run_log(self, *, task_id, run_id):
        return f"runs/{task_id}/{run_id}.jsonl"

    def append_event(self, *, log_path, event, message, data, level="info"):
        self.events.append(event)

    def append_role_handoff_event(self, *, log_path, **kwargs):
        self.events.append("role_handoff")


class _FakeContextBuilderService:
    def build_context_package(
        self,
        *,
        task,
        run_id,
        include_project_memory,
    ):
        return TaskContextPackage(
            task_id=task.id,
            task_title=task.title,
            input_summary=task.input_summary,
            acceptance_criteria=list(task.acceptance_criteria),
            priority=task.priority,
            risk_level=task.risk_level,
            human_status=task.human_status,
            paused_reason=task.paused_reason,
            ready_for_execution=True,
            blocking_signals=[],
            blocking_reasons=[],
            dependency_items=[],
            recent_runs=[],
            context_summary="fake context ready",
        )

    def build_agent_thread_context_seed(self, *, task, context_package):
        return AgentThreadContextSeed(
            task_id=task.id,
            context_checkpoint_id=None,
            context_rehydrated=False,
            pressure_level=None,
            usage_ratio=None,
            bad_context_detected=False,
            bad_context_reasons=[],
            context_contract_summary="fake context seed",
        )


class _FakeTaskRouterService:
    def __init__(self, task: Task) -> None:
        self.task = task

    def route_next_task(self, *, project_id=None):
        return TaskRoutingDecision(
            selected_task=self.task,
            routing_score=100.0,
            route_reason="test route",
            routing_score_breakdown=[],
            candidates=[],
            message="selected fake task",
            budget_pressure_level=RunBudgetPressureLevel.NORMAL,
            budget_action=RunBudgetStrategyAction.FULL_SPEED,
            budget_strategy_code="test_allow",
            budget_strategy_summary="Test budget allows execution.",
            project_stage=None,
            owner_role_code=None,
            upstream_role_code=None,
            downstream_role_code=None,
            dispatch_status=None,
            handoff_reason=None,
            model_name=None,
            model_tier=None,
            selected_skill_codes=(),
            selected_skill_names=(),
            strategy_code=None,
            strategy_summary=None,
            strategy_reasons=[],
            strategy_decision=None,
        )


class _FakeAgentSessionRepository:
    def __init__(self, agent_session: AgentSession) -> None:
        self.agent_session = agent_session

    def update_status(self, session_id, **kwargs):
        assert session_id == self.agent_session.id
        updates = dict(kwargs)
        if updates.pop("finished", False):
            updates["finished_at"] = utc_now()
        updates["updated_at"] = utc_now()
        self.agent_session = self.agent_session.model_copy(update=updates)
        return self.agent_session


class _FakeAgentConversationService:
    def __init__(self, agent_session: AgentSession) -> None:
        self.agent_session_repository = _FakeAgentSessionRepository(agent_session)

    def start_session(
        self,
        *,
        project_id,
        task_id,
        run_id,
        owner_role_code,
        context_seed,
    ):
        self.agent_session_repository.agent_session = (
            self.agent_session_repository.agent_session.model_copy(
                update={
                    "project_id": project_id,
                    "task_id": task_id,
                    "run_id": run_id,
                    "status": AgentSessionStatus.RUNNING,
                    "current_phase": AgentSessionPhase.CONTEXT_READY,
                    "coding_status": CodingSessionStatus.WORKING,
                    "activity_state": CodingSessionActivityState.ACTIVE,
                }
            )
        )
        return self.agent_session_repository.agent_session

    def record_execution_started(self, *, session_id):
        return self.agent_session_repository.update_status(
            session_id,
            current_phase=AgentSessionPhase.EXECUTING,
            summary="Execution has started in the worker chain.",
        )

    def record_execution_outcome(
        self,
        *,
        session_id,
        execution_success,
        execution_summary,
        verification_present,
        verification_success,
        verification_summary,
        run_failure_category,
    ):
        review_status = (
            AgentSessionReviewStatus.REVIEW_PASSED
            if execution_success and (not verification_present or verification_success)
            else AgentSessionReviewStatus.REWORK_REQUIRED
        )
        return self.agent_session_repository.update_status(
            session_id,
            review_status=review_status,
            summary=execution_summary,
        )

    def finalize_session(
        self,
        *,
        session_id,
        run_status,
        run_failure_category,
        final_summary,
    ):
        if run_status == RunStatus.CANCELLED:
            status = AgentSessionStatus.BLOCKED
            coding_status = CodingSessionStatus.TERMINATED
            activity_state = CodingSessionActivityState.EXITED
        elif run_status == RunStatus.FAILED:
            status = AgentSessionStatus.FAILED
            coding_status = CodingSessionStatus.FAILED
            activity_state = CodingSessionActivityState.EXITED
        else:
            assert run_status == RunStatus.SUCCEEDED
            status = AgentSessionStatus.COMPLETED
            coding_status = CodingSessionStatus.COMPLETED
            activity_state = CodingSessionActivityState.IDLE
        return self.agent_session_repository.update_status(
            session_id,
            status=status,
            current_phase=AgentSessionPhase.FINALIZED,
            summary=final_summary,
            coding_status=coding_status,
            activity_state=activity_state,
            finished=True,
        )


def test_worker_run_once_blocks_executor_when_worktree_safe_command_proof_fails(
    monkeypatch,
    tmp_path,
):
    task = Task(
        project_id=uuid4(),
        title="Proof blocks executor",
        input_summary="simulate: should not reach executor",
        status=TaskStatus.PENDING,
        priority=TaskPriority.NORMAL,
        risk_level=TaskRiskLevel.NORMAL,
        human_status=TaskHumanStatus.NONE,
    )
    agent_session = _session(
        workspace_path=tmp_path.as_posix(),
        workspace_clean=True,
        branch_name="main",
    )
    proof = WorkerWorktreeSafeCommandProof(
        ready=False,
        source="agent_session_worktree_safe_command_blocked",
        reason_code="pwd_mismatch_workspace_path",
        command="pwd",
        cwd=tmp_path.as_posix(),
        expected_workspace_path=tmp_path.as_posix(),
        observed_pwd="/unexpected/worktree",
        pwd_matches_workspace_path=False,
        exit_code=0,
        stdout="/unexpected/worktree",
        stderr="",
        timed_out=False,
        read_only=True,
        allowlisted=True,
        uses_agent_workspace=True,
        runs_command=True,
    )

    class _FailingProofRunner:
        def run_probe(self, *, workspace_context):
            assert workspace_context.ready is True
            assert workspace_context.uses_agent_workspace is True
            return proof

    class _ExplodingGitDiffDryRunRunner:
        def __init__(self):
            raise AssertionError("git diff dry-run must not run on proof-blocked path")

    class _ExplodingGitOperationDryRunBuilder:
        @staticmethod
        def build_from_diff_evidence(**kwargs):
            raise AssertionError(
                "git operation dry-run builder must not run on proof-blocked path"
            )

    monkeypatch.setattr(
        "app.workers.worktree_safe_command.WorkerWorktreeSafeCommandProofRunner",
        lambda: _FailingProofRunner(),
    )
    monkeypatch.setattr(
        "app.workers.task_worker.GitDiffDryRunRunner",
        _ExplodingGitDiffDryRunRunner,
    )
    monkeypatch.setattr(
        "app.workers.task_worker.GitOperationDryRunBuilder",
        _ExplodingGitOperationDryRunBuilder,
    )
    monkeypatch.setattr(
        "app.workers.task_worker.event_stream_service.publish_task_updated",
        lambda **kwargs: None,
    )

    executor_service = _ExplodingExecutorService()
    task_repository = _FakeTaskRepository(task)
    run_repository = _FakeRunRepository()
    agent_conversation_service = _FakeAgentConversationService(agent_session)
    worker = TaskWorker(
        session=_NoopDbSession(),
        task_repository=task_repository,
        run_repository=run_repository,
        executor_service=executor_service,
        verifier_service=None,
        budget_guard_service=_AllowingBudgetGuardService(),
        run_logging_service=_NoopRunLoggingService(),
        cost_estimator_service=None,
        context_builder_service=_FakeContextBuilderService(),
        task_router_service=_FakeTaskRouterService(task),
        model_routing_service=None,
        prompt_registry_service=None,
        prompt_builder_service=None,
        token_accounting_service=None,
        task_state_machine_service=TaskStateMachineService(),
        failure_review_service=type(
            "_NoopFailureReviewService",
            (),
            {"ensure_review": lambda self, *, task, run: None},
        )(),
        agent_conversation_service=agent_conversation_service,
    )

    result = worker.run_once()

    assert result.claimed is True
    assert result.execution_mode == "worktree_safe_command_proof"
    assert "blocked executor dispatch" in result.message
    assert result.worktree_safe_command_proof_ready is False
    assert result.worktree_safe_command_proof_reason_code == (
        "pwd_mismatch_workspace_path"
    )
    assert result.task is not None
    assert result.task.status == TaskStatus.BLOCKED
    assert result.run is not None
    assert result.run.status == RunStatus.CANCELLED
    assert result.run.failure_category == RunFailureCategory.EXECUTION_FAILED
    assert result.run.quality_gate_passed is False
    assert result.run.verification_summary == (
        "Verification skipped because worker worktree safe command proof failed."
    )
    assert result.agent_session_status == "blocked"
    assert result.agent_current_phase == "finalized"
    assert result.coding_status == "terminated"
    assert result.activity_state == "exited"
    assert result.last_workspace_error is not None
    assert "reason_code=pwd_mismatch_workspace_path" in result.last_workspace_error
    assert result.git_operation_dry_run_ready is None
    assert result.git_operation_dry_run_reason_code is None
    assert executor_service.build_execution_plan_calls == 0
    assert executor_service.execute_task_calls == 0


def test_worker_run_once_success_path_collects_git_diff_dry_run_evidence(
    monkeypatch,
    tmp_path,
):
    task = Task(
        project_id=uuid4(),
        title="Successful run collects diff evidence",
        input_summary="simulate: collect diff preview",
        status=TaskStatus.PENDING,
        priority=TaskPriority.NORMAL,
        risk_level=TaskRiskLevel.NORMAL,
        human_status=TaskHumanStatus.NONE,
    )
    agent_session = _session(
        workspace_path=tmp_path.as_posix(),
        workspace_clean=True,
        branch_name="main",
    )
    proof = WorkerWorktreeSafeCommandProof(
        ready=True,
        source="agent_session_worktree_safe_command",
        reason_code=None,
        command="pwd",
        cwd=tmp_path.as_posix(),
        expected_workspace_path=tmp_path.as_posix(),
        observed_pwd=tmp_path.as_posix(),
        pwd_matches_workspace_path=True,
        exit_code=0,
        stdout=tmp_path.as_posix(),
        stderr="",
        timed_out=False,
        read_only=True,
        allowlisted=True,
        uses_agent_workspace=True,
        runs_command=True,
    )
    collect_calls: list[dict[str, str | None]] = []

    class _PassingProofRunner:
        def run_probe(self, *, workspace_context):
            assert workspace_context.ready is True
            assert workspace_context.uses_agent_workspace is True
            return proof

    class _SpyGitDiffDryRunRunner:
        def collect(self, *, repository_path, compare_branch=None):
            collect_calls.append(
                {
                    "repository_path": repository_path,
                    "compare_branch": compare_branch,
                }
            )
            return GitDiffDryRunResult(
                ready=True,
                source="agent_session_worktree_diff",
                reason_code=None,
                worktree_path=repository_path,
                has_changes=True,
                changed_files_count=1,
                changed_files=["README.md"],
                added_files=[],
                modified_files=["README.md"],
                deleted_files=[],
                renamed_files=[],
                status_summary_cn="1 个文件修改",
                diff_stat=" README.md | 1 +",
                diff_shortstat="1 file changed, 1 insertion(+)",
                branch_name="main",
                compare_branch=compare_branch,
                command="git status --porcelain=v1 --untracked-files=all",
                peek_command="git diff --name-status",
                danger_commands_applied=False,
            )

    monkeypatch.setattr(
        "app.workers.worktree_safe_command.WorkerWorktreeSafeCommandProofRunner",
        lambda: _PassingProofRunner(),
    )
    monkeypatch.setattr(
        "app.workers.task_worker.GitDiffDryRunRunner",
        _SpyGitDiffDryRunRunner,
    )
    monkeypatch.setattr(
        "app.workers.task_worker.event_stream_service.publish_task_updated",
        lambda **kwargs: None,
    )

    executor_service = _FakeExecutorService(success=True)
    delivery_event_audit_service = _SpyDeliveryEventAuditService()
    worker = TaskWorker(
        session=_NoopDbSession(),
        task_repository=_FakeTaskRepository(task),
        run_repository=_FakeRunRepository(),
        executor_service=executor_service,
        verifier_service=_PassingVerifierService(),
        budget_guard_service=_AllowingBudgetGuardService(),
        run_logging_service=_NoopRunLoggingService(),
        cost_estimator_service=CostEstimatorService(),
        context_builder_service=_FakeContextBuilderService(),
        task_router_service=_FakeTaskRouterService(task),
        model_routing_service=_FakeModelRoutingService(),
        prompt_registry_service=None,
        prompt_builder_service=_FakePromptBuilderService(),
        token_accounting_service=TokenAccountingService(),
        task_state_machine_service=TaskStateMachineService(),
        failure_review_service=type(
            "_NoopFailureReviewService",
            (),
            {"ensure_review": lambda self, *, task, run: None},
        )(),
        agent_conversation_service=_FakeAgentConversationService(agent_session),
        delivery_event_audit_service=delivery_event_audit_service,
    )

    result = worker.run_once()

    assert result.claimed is True
    assert result.execution_mode == "simulate"
    assert result.task is not None
    assert result.task.status == TaskStatus.COMPLETED
    assert result.run is not None
    assert result.run.status == RunStatus.SUCCEEDED
    assert executor_service.build_execution_plan_calls == 1
    assert executor_service.execute_task_calls == 1
    assert collect_calls == [
            {
                "repository_path": tmp_path.as_posix(),
                "compare_branch": "main",
            }
        ]
    assert result.git_diff_dry_run_ready is True
    assert result.git_diff_dry_run_status_summary_cn == "1 个文件修改"
    assert result.git_diff_dry_run_changed_files == ["README.md"]
    assert result.git_diff_dry_run_runs_git is True
    assert result.git_diff_dry_run_runs_write_git is False
    assert result.git_operation_dry_run_ready is True
    assert result.git_operation_dry_run_source == "git_operation_dry_run"
    assert result.git_operation_dry_run_reason_code is None
    assert result.git_operation_dry_run_worktree_path == tmp_path.as_posix()
    assert result.git_operation_dry_run_branch_name == "main"
    assert result.git_operation_dry_run_changed_files_count == 1
    assert result.git_operation_dry_run_changed_files == ["README.md"]
    assert result.git_operation_dry_run_modified_files == ["README.md"]
    assert result.git_operation_dry_run_proposed_operation == "git_add_commit"
    assert result.git_operation_dry_run_proposed_commit_message == (
        "chore: update 1 files from agent work"
    )
    assert result.git_operation_dry_run_proposed_steps == [
        "准备加入待提交区（git add，预览不执行）",
        "准备生成本地提交（git commit，预览不执行）："
        "chore: update 1 files from agent work",
    ]
    assert result.git_operation_dry_run_summary_cn == (
        "已生成提交预览：检测到 1 个文件变更。"
        "如果确认，将把这些文件提交到分支 main。"
        "尚未加入待提交区、尚未生成本地提交、尚未推送。"
    )
    assert result.git_operation_dry_run_user_confirmation_required is True
    assert result.git_operation_dry_run_human_approval_required is True
    assert result.git_operation_dry_run_feature_flag_required is True
    assert result.git_operation_dry_run_runs_git is False
    assert result.git_operation_dry_run_runs_write_git is False
    assert result.git_operation_dry_run_git_add_triggered is False
    assert result.git_operation_dry_run_git_commit_triggered is False
    assert result.git_operation_dry_run_git_push_triggered is False
    assert result.git_operation_dry_run_pr_opened is False
    assert result.git_operation_dry_run_ci_triggered is False
    assert result.git_operation_dry_run_execution_enabled is False
    assert result.git_operation_dry_run_operation_applied is False
    assert result.git_operation_dry_run_approval_granted is False
    assert result.delivery_gate_evidence_ready is True
    assert result.delivery_gate_evidence_source == "delivery_gate_evidence"
    assert result.delivery_gate_evidence_reason_code is None
    assert result.delivery_gate_evidence_worktree_path == tmp_path.as_posix()
    assert result.delivery_gate_evidence_branch_name == "main"
    assert result.delivery_gate_evidence_proposed_operation == "git_add_commit"
    assert result.delivery_gate_evidence_changed_files_count == 1
    assert result.delivery_gate_evidence_changed_files == ["README.md"]
    assert result.delivery_gate_evidence_next_required_action == (
        "await_user_confirmation"
    )
    assert result.delivery_gate_evidence_user_confirmation_required is True
    assert result.delivery_gate_evidence_human_approval_required is True
    assert (
        result.delivery_gate_evidence_delivery_audit_event_present is True
    )
    assert result.delivery_gate_evidence_delivery_audit_event_type == (
        DELIVERY_AUDIT_COLLECTED_EVENT_TYPE
    )
    assert result.delivery_gate_evidence_delivery_audit_event_ready is True
    assert result.delivery_gate_evidence_satisfied_conditions == [
        f"G{index}" for index in range(1, 22)
    ]
    assert result.delivery_gate_evidence_blocking_reasons == []
    assert result.delivery_gate_evidence_runs_git is False
    assert result.delivery_gate_evidence_runs_write_git is False
    assert result.delivery_gate_evidence_git_add_triggered is False
    assert result.delivery_gate_evidence_git_commit_triggered is False
    assert result.delivery_gate_evidence_git_push_triggered is False
    assert result.delivery_gate_evidence_pr_opened is False
    assert result.delivery_gate_evidence_ci_triggered is False
    assert result.delivery_gate_evidence_execution_enabled is False
    assert result.delivery_gate_evidence_operation_applied is False
    assert result.delivery_gate_evidence_approval_granted is False
    assert result.delivery_gate_evidence_gate_allows_write is False
    assert result.delivery_gate_evidence_gate_allows_user_confirmation is True
    assert len(delivery_event_audit_service.calls) == 1
    delivery_call = delivery_event_audit_service.calls[0]
    assert delivery_call["session"].id == result.agent_session_id
    assert delivery_call["result"].ready is True
    assert delivery_call["result"].status_summary_cn == "1 个文件修改"
    assert delivery_call["skipped_reason_code"] is None
    assert delivery_call["workspace_path"] == tmp_path.as_posix()
    response_payload = WorkerRunOnceResponse.from_result(result).model_dump(
        mode="json"
    )
    assert response_payload["git_diff_dry_run_status_summary_cn"] == "1 个文件修改"
    assert response_payload["git_operation_dry_run_ready"] is True
    assert response_payload["git_operation_dry_run_source"] == "git_operation_dry_run"
    assert response_payload["git_operation_dry_run_changed_files"] == ["README.md"]
    assert response_payload["git_operation_dry_run_proposed_operation"] == (
        "git_add_commit"
    )
    assert response_payload["git_operation_dry_run_runs_git"] is False
    assert response_payload["git_operation_dry_run_runs_write_git"] is False
    assert response_payload["git_operation_dry_run_git_add_triggered"] is False
    assert response_payload["git_operation_dry_run_git_commit_triggered"] is False
    assert response_payload["git_operation_dry_run_git_push_triggered"] is False
    assert response_payload["git_operation_dry_run_pr_opened"] is False
    assert response_payload["git_operation_dry_run_operation_applied"] is False
    assert response_payload["delivery_gate_evidence_ready"] is True
    assert response_payload["delivery_gate_evidence_source"] == (
        "delivery_gate_evidence"
    )
    assert response_payload["delivery_gate_evidence_reason_code"] is None
    assert response_payload["delivery_gate_evidence_changed_files"] == ["README.md"]
    assert response_payload["delivery_gate_evidence_proposed_operation"] == (
        "git_add_commit"
    )
    assert response_payload["delivery_gate_evidence_next_required_action"] == (
        "await_user_confirmation"
    )
    assert response_payload[
        "delivery_gate_evidence_delivery_audit_event_present"
    ] is True
    assert response_payload["delivery_gate_evidence_delivery_audit_event_type"] == (
        DELIVERY_AUDIT_COLLECTED_EVENT_TYPE
    )
    assert response_payload[
        "delivery_gate_evidence_delivery_audit_event_ready"
    ] is True
    assert response_payload["delivery_gate_evidence_gate_allows_write"] is False
    assert response_payload[
        "delivery_gate_evidence_gate_allows_user_confirmation"
    ] is True
    old_status_summary_key = "git_diff_dry_run_status_" + "summary"
    assert old_status_summary_key not in response_payload


def test_worker_run_once_success_path_builds_blocked_operation_dry_run_for_no_changes(
    monkeypatch,
    tmp_path,
):
    task = Task(
        project_id=uuid4(),
        title="Successful run with no git changes",
        input_summary="simulate: collect no-change preview",
        status=TaskStatus.PENDING,
        priority=TaskPriority.NORMAL,
        risk_level=TaskRiskLevel.NORMAL,
        human_status=TaskHumanStatus.NONE,
    )
    agent_session = _session(
        workspace_path=tmp_path.as_posix(),
        workspace_clean=True,
        branch_name="main",
    )
    proof = WorkerWorktreeSafeCommandProof(
        ready=True,
        source="agent_session_worktree_safe_command",
        reason_code=None,
        command="pwd",
        cwd=tmp_path.as_posix(),
        expected_workspace_path=tmp_path.as_posix(),
        observed_pwd=tmp_path.as_posix(),
        pwd_matches_workspace_path=True,
        exit_code=0,
        stdout=tmp_path.as_posix(),
        stderr="",
        timed_out=False,
        read_only=True,
        allowlisted=True,
        uses_agent_workspace=True,
        runs_command=True,
    )
    collect_calls: list[dict[str, str | None]] = []

    class _PassingProofRunner:
        def run_probe(self, *, workspace_context):
            assert workspace_context.ready is True
            assert workspace_context.uses_agent_workspace is True
            return proof

    class _NoChangesGitDiffDryRunRunner:
        def collect(self, *, repository_path, compare_branch=None):
            collect_calls.append(
                {
                    "repository_path": repository_path,
                    "compare_branch": compare_branch,
                }
            )
            return GitDiffDryRunResult(
                ready=True,
                source="agent_session_worktree_diff",
                reason_code=None,
                worktree_path=repository_path,
                has_changes=False,
                changed_files_count=0,
                changed_files=[],
                added_files=[],
                modified_files=[],
                deleted_files=[],
                renamed_files=[],
                status_summary_cn="当前没有代码改动",
                diff_stat="",
                diff_shortstat="",
                branch_name="main",
                compare_branch=compare_branch,
                command="git status --porcelain=v1 --untracked-files=all",
                peek_command="git diff --name-status",
                danger_commands_applied=False,
            )

    monkeypatch.setattr(
        "app.workers.worktree_safe_command.WorkerWorktreeSafeCommandProofRunner",
        lambda: _PassingProofRunner(),
    )
    monkeypatch.setattr(
        "app.workers.task_worker.GitDiffDryRunRunner",
        _NoChangesGitDiffDryRunRunner,
    )
    monkeypatch.setattr(
        "app.workers.task_worker.event_stream_service.publish_task_updated",
        lambda **kwargs: None,
    )

    executor_service = _FakeExecutorService(success=True)
    delivery_event_audit_service = _SpyDeliveryEventAuditService()
    worker = TaskWorker(
        session=_NoopDbSession(),
        task_repository=_FakeTaskRepository(task),
        run_repository=_FakeRunRepository(),
        executor_service=executor_service,
        verifier_service=_PassingVerifierService(),
        budget_guard_service=_AllowingBudgetGuardService(),
        run_logging_service=_NoopRunLoggingService(),
        cost_estimator_service=CostEstimatorService(),
        context_builder_service=_FakeContextBuilderService(),
        task_router_service=_FakeTaskRouterService(task),
        model_routing_service=_FakeModelRoutingService(),
        prompt_registry_service=None,
        prompt_builder_service=_FakePromptBuilderService(),
        token_accounting_service=TokenAccountingService(),
        task_state_machine_service=TaskStateMachineService(),
        failure_review_service=type(
            "_NoopFailureReviewService",
            (),
            {"ensure_review": lambda self, *, task, run: None},
        )(),
        agent_conversation_service=_FakeAgentConversationService(agent_session),
        delivery_event_audit_service=delivery_event_audit_service,
    )

    result = worker.run_once()

    assert result.claimed is True
    assert result.execution_mode == "simulate"
    assert result.task is not None
    assert result.task.status == TaskStatus.COMPLETED
    assert result.run is not None
    assert result.run.status == RunStatus.SUCCEEDED
    assert executor_service.build_execution_plan_calls == 1
    assert executor_service.execute_task_calls == 1
    assert collect_calls == [
            {
                "repository_path": tmp_path.as_posix(),
                "compare_branch": "main",
            }
        ]
    assert result.git_diff_dry_run_ready is True
    assert result.git_diff_dry_run_has_changes is False
    assert result.git_diff_dry_run_changed_files_count == 0
    assert result.git_diff_dry_run_changed_files == []
    assert result.git_operation_dry_run_ready is False
    assert result.git_operation_dry_run_source == "git_operation_dry_run"
    assert result.git_operation_dry_run_reason_code == "no_changes"
    assert result.git_operation_dry_run_worktree_path == tmp_path.as_posix()
    assert result.git_operation_dry_run_branch_name == "main"
    assert result.git_operation_dry_run_changed_files_count == 0
    assert result.git_operation_dry_run_changed_files == []
    assert result.git_operation_dry_run_proposed_operation == "none"
    assert result.git_operation_dry_run_proposed_steps == []
    assert result.git_operation_dry_run_proposed_commit_message is None
    assert result.git_operation_dry_run_summary_cn == "当前没有可提交的代码改动。"
    assert result.git_operation_dry_run_runs_git is False
    assert result.git_operation_dry_run_runs_write_git is False
    assert result.git_operation_dry_run_git_add_triggered is False
    assert result.git_operation_dry_run_git_commit_triggered is False
    assert result.git_operation_dry_run_git_push_triggered is False
    assert result.git_operation_dry_run_pr_opened is False
    assert result.git_operation_dry_run_ci_triggered is False
    assert result.git_operation_dry_run_execution_enabled is False
    assert result.git_operation_dry_run_operation_applied is False
    assert result.git_operation_dry_run_approval_granted is False
    assert result.delivery_gate_evidence_ready is False
    assert result.delivery_gate_evidence_source == "delivery_gate_evidence"
    assert result.delivery_gate_evidence_reason_code == "no_changes"
    assert result.delivery_gate_evidence_proposed_operation == "none"
    assert result.delivery_gate_evidence_changed_files_count == 0
    assert result.delivery_gate_evidence_changed_files == []
    assert result.delivery_gate_evidence_next_required_action == (
        "resolve_blocking_conditions"
    )
    assert result.delivery_gate_evidence_user_confirmation_required is False
    assert result.delivery_gate_evidence_human_approval_required is False
    assert (
        result.delivery_gate_evidence_delivery_audit_event_present is True
    )
    assert result.delivery_gate_evidence_delivery_audit_event_type == (
        DELIVERY_AUDIT_COLLECTED_EVENT_TYPE
    )
    assert result.delivery_gate_evidence_delivery_audit_event_ready is True
    assert "G8:no_changes" in result.delivery_gate_evidence_blocking_reasons
    assert "G9:no_changes" in result.delivery_gate_evidence_blocking_reasons
    assert result.delivery_gate_evidence_gate_allows_write is False
    assert result.delivery_gate_evidence_gate_allows_user_confirmation is False
    assert len(delivery_event_audit_service.calls) == 1

    response_payload = WorkerRunOnceResponse.from_result(result).model_dump(
        mode="json"
    )
    assert response_payload["git_operation_dry_run_ready"] is False
    assert response_payload["git_operation_dry_run_reason_code"] == "no_changes"
    assert response_payload["git_operation_dry_run_proposed_operation"] == "none"
    assert response_payload["git_operation_dry_run_proposed_steps"] == []
    assert response_payload["git_operation_dry_run_runs_git"] is False
    assert response_payload["git_operation_dry_run_git_add_triggered"] is False
    assert response_payload["delivery_gate_evidence_ready"] is False
    assert response_payload["delivery_gate_evidence_reason_code"] == "no_changes"
    assert response_payload["delivery_gate_evidence_proposed_operation"] == "none"
    assert response_payload["delivery_gate_evidence_changed_files"] == []
    assert response_payload[
        "delivery_gate_evidence_delivery_audit_event_present"
    ] is True
    assert response_payload["delivery_gate_evidence_delivery_audit_event_type"] == (
        DELIVERY_AUDIT_COLLECTED_EVENT_TYPE
    )
    assert response_payload[
        "delivery_gate_evidence_delivery_audit_event_ready"
    ] is True
    assert response_payload["delivery_gate_evidence_gate_allows_write"] is False
    assert response_payload[
        "delivery_gate_evidence_gate_allows_user_confirmation"
    ] is False


def test_worker_run_once_execution_failure_does_not_collect_git_diff_dry_run(
    monkeypatch,
    tmp_path,
):
    task = Task(
        project_id=uuid4(),
        title="Failed run skips diff evidence",
        input_summary="simulate: fail before diff preview",
        status=TaskStatus.PENDING,
        priority=TaskPriority.NORMAL,
        risk_level=TaskRiskLevel.NORMAL,
        human_status=TaskHumanStatus.NONE,
    )
    agent_session = _session(
        workspace_path=tmp_path.as_posix(),
        workspace_clean=True,
    )
    proof = WorkerWorktreeSafeCommandProof(
        ready=True,
        source="agent_session_worktree_safe_command",
        reason_code=None,
        command="pwd",
        cwd=tmp_path.as_posix(),
        expected_workspace_path=tmp_path.as_posix(),
        observed_pwd=tmp_path.as_posix(),
        pwd_matches_workspace_path=True,
        exit_code=0,
        stdout=tmp_path.as_posix(),
        stderr="",
        timed_out=False,
        read_only=True,
        allowlisted=True,
        uses_agent_workspace=True,
        runs_command=True,
    )

    class _PassingProofRunner:
        def run_probe(self, *, workspace_context):
            assert workspace_context.ready is True
            assert workspace_context.uses_agent_workspace is True
            return proof

    class _ExplodingGitDiffDryRunRunner:
        def __init__(self):
            raise AssertionError("git diff dry-run must not run on failed execution")

    class _ExplodingGitOperationDryRunBuilder:
        @staticmethod
        def build_from_diff_evidence(**kwargs):
            raise AssertionError(
                "git operation dry-run builder must not run on failed execution"
            )

    monkeypatch.setattr(
        "app.workers.worktree_safe_command.WorkerWorktreeSafeCommandProofRunner",
        lambda: _PassingProofRunner(),
    )
    monkeypatch.setattr(
        "app.workers.task_worker.GitDiffDryRunRunner",
        _ExplodingGitDiffDryRunRunner,
    )
    monkeypatch.setattr(
        "app.workers.task_worker.GitOperationDryRunBuilder",
        _ExplodingGitOperationDryRunBuilder,
    )
    monkeypatch.setattr(
        "app.workers.task_worker.event_stream_service.publish_task_updated",
        lambda **kwargs: None,
    )

    executor_service = _FakeExecutorService(success=False)
    delivery_event_audit_service = _SpyDeliveryEventAuditService()
    worker = TaskWorker(
        session=_NoopDbSession(),
        task_repository=_FakeTaskRepository(task),
        run_repository=_FakeRunRepository(),
        executor_service=executor_service,
        verifier_service=_PassingVerifierService(),
        budget_guard_service=_AllowingBudgetGuardService(),
        run_logging_service=_NoopRunLoggingService(),
        cost_estimator_service=CostEstimatorService(),
        context_builder_service=_FakeContextBuilderService(),
        task_router_service=_FakeTaskRouterService(task),
        model_routing_service=_FakeModelRoutingService(),
        prompt_registry_service=None,
        prompt_builder_service=_FakePromptBuilderService(),
        token_accounting_service=TokenAccountingService(),
        task_state_machine_service=TaskStateMachineService(),
        failure_review_service=type(
            "_NoopFailureReviewService",
            (),
            {"ensure_review": lambda self, *, task, run: None},
        )(),
        agent_conversation_service=_FakeAgentConversationService(agent_session),
        delivery_event_audit_service=delivery_event_audit_service,
    )

    result = worker.run_once()

    assert result.claimed is True
    assert result.execution_mode == "simulate"
    assert result.task is not None
    assert result.task.status == TaskStatus.FAILED
    assert result.run is not None
    assert result.run.status == RunStatus.FAILED
    assert result.git_diff_dry_run_ready is None
    assert result.git_diff_dry_run_status_summary_cn is None
    assert result.git_operation_dry_run_ready is None
    assert result.git_operation_dry_run_reason_code is None
    assert executor_service.build_execution_plan_calls == 1
    assert executor_service.execute_task_calls == 1
    assert delivery_event_audit_service.calls == []


def test_worker_run_once_blocks_executor_when_runtime_launch_gate_fails(
    monkeypatch,
    tmp_path,
):
    task = Task(
        project_id=uuid4(),
        title="Runtime gate blocks executor",
        input_summary="simulate: should not reach executor",
        status=TaskStatus.PENDING,
        priority=TaskPriority.NORMAL,
        risk_level=TaskRiskLevel.NORMAL,
        human_status=TaskHumanStatus.NONE,
    )
    agent_session = _session(
        workspace_path=tmp_path.as_posix(),
        workspace_clean=True,
        runtime_type=None,
    )
    proof = WorkerWorktreeSafeCommandProof(
        ready=True,
        source="agent_session_worktree_safe_command",
        reason_code=None,
        command="pwd",
        cwd=tmp_path.as_posix(),
        expected_workspace_path=tmp_path.as_posix(),
        observed_pwd=tmp_path.as_posix(),
        pwd_matches_workspace_path=True,
        exit_code=0,
        stdout=tmp_path.as_posix(),
        stderr="",
        timed_out=False,
        read_only=True,
        allowlisted=True,
        uses_agent_workspace=True,
        runs_command=True,
    )
    adapter_calls = {"can_launch": 0, "launch": 0}

    class _PassingProofRunner:
        def run_probe(self, *, workspace_context):
            assert workspace_context.ready is True
            assert workspace_context.uses_agent_workspace is True
            return proof

    class _LaunchExplodingAdapter:
        def adapter_kind(self):
            return "fake"

        def can_launch(self, *, agent_type, runtime_type):
            adapter_calls["can_launch"] += 1
            return True

        def launch(self, *, request):
            adapter_calls["launch"] += 1
            raise AssertionError("fake launch must not run when gate fails")

    monkeypatch.setattr(
        "app.workers.worktree_safe_command.WorkerWorktreeSafeCommandProofRunner",
        lambda: _PassingProofRunner(),
    )
    monkeypatch.setattr(
        "app.workers.task_worker.FakeRuntimeAdapter",
        _LaunchExplodingAdapter,
    )
    monkeypatch.setattr(
        "app.workers.task_worker.event_stream_service.publish_task_updated",
        lambda **kwargs: None,
    )

    executor_service = _ExplodingExecutorService()
    runtime_event_audit_service = _SpyRuntimeEventAuditService()
    worker = TaskWorker(
        session=_NoopDbSession(),
        task_repository=_FakeTaskRepository(task),
        run_repository=_FakeRunRepository(),
        executor_service=executor_service,
        verifier_service=None,
        budget_guard_service=_AllowingBudgetGuardService(),
        run_logging_service=_NoopRunLoggingService(),
        cost_estimator_service=None,
        context_builder_service=_FakeContextBuilderService(),
        task_router_service=_FakeTaskRouterService(task),
        model_routing_service=None,
        prompt_registry_service=None,
        prompt_builder_service=None,
        token_accounting_service=None,
        task_state_machine_service=TaskStateMachineService(),
        failure_review_service=type(
            "_NoopFailureReviewService",
            (),
            {"ensure_review": lambda self, *, task, run: None},
        )(),
        agent_conversation_service=_FakeAgentConversationService(agent_session),
        runtime_event_audit_service=runtime_event_audit_service,
    )

    result = worker.run_once()

    assert result.claimed is True
    assert result.execution_mode == "runtime_launch_gate"
    assert "Runtime launch gate blocked executor dispatch" in result.message
    assert result.runtime_launch_gate_ready is False
    assert result.runtime_launch_gate_gates_failed == ["runtime_dry_run"]
    assert result.runtime_launch_gate_blocking_reason_code == "runtime_type_missing"
    assert result.runtime_launch_gate_execution_enabled is False
    assert result.runtime_launch_gate_launches_ai_runtime is False
    assert result.runtime_launch_dry_run_ready is False
    assert result.runtime_launch_dry_run_reason_code == "runtime_type_missing"
    assert result.worktree_safe_command_proof_ready is True
    assert result.runtime_lifecycle_snapshot is not None
    assert result.runtime_lifecycle_snapshot.ready is False
    assert result.runtime_lifecycle_snapshot.reason_code == "runtime_type_missing"
    assert result.runtime_lifecycle_snapshot.fake_launch_started is False
    assert result.runtime_lifecycle_snapshot.real_runtime_started is False
    assert result.runtime_lifecycle_snapshot.runtime_probe_started is False
    assert result.runtime_handle_id is None
    assert result.task is not None
    assert result.task.status == TaskStatus.BLOCKED
    assert result.run is not None
    assert result.run.status == RunStatus.CANCELLED
    assert result.run.failure_category == RunFailureCategory.EXECUTION_FAILED
    assert result.run.quality_gate_passed is False
    assert result.run.verification_summary == (
        "Verification skipped because runtime launch gate failed before "
        "executor dispatch."
    )
    assert result.agent_session_status == "blocked"
    assert result.agent_current_phase == "finalized"
    assert result.coding_status == "terminated"
    assert result.activity_state == "exited"
    assert result.last_workspace_error is not None
    assert "reason_code=runtime_type_missing" in result.last_workspace_error
    assert "fake_launch_started=False" in result.last_workspace_error
    assert "real_runtime_started=False" in result.last_workspace_error
    assert adapter_calls == {"can_launch": 0, "launch": 0}
    assert executor_service.build_execution_plan_calls == 0
    assert executor_service.execute_task_calls == 0
    assert len(runtime_event_audit_service.calls) == 1
    call = runtime_event_audit_service.calls[0]
    assert call["session"].id == result.agent_session_id
    assert call["gate_result"].ready is False
    assert call["gate_result"].gates_failed == ["runtime_dry_run"]
    assert call["adapter_kind"] == "fake"
    assert call["workspace_path"] == tmp_path.as_posix()
    assert call["observed_pwd"] == tmp_path.as_posix()
    assert call["launch_cwd_preview"] is None


def test_worker_run_once_stops_before_executor_when_runtime_gate_audit_fails(
    monkeypatch,
    tmp_path,
):
    task = Task(
        project_id=uuid4(),
        title="Runtime gate audit failure blocks executor",
        input_summary="simulate: audit failure should not reach executor",
        status=TaskStatus.PENDING,
        priority=TaskPriority.NORMAL,
        risk_level=TaskRiskLevel.NORMAL,
        human_status=TaskHumanStatus.NONE,
    )
    agent_session = _session(
        workspace_path=tmp_path.as_posix(),
        workspace_clean=True,
    )
    proof = WorkerWorktreeSafeCommandProof(
        ready=True,
        source="agent_session_worktree_safe_command",
        reason_code=None,
        command="pwd",
        cwd=tmp_path.as_posix(),
        expected_workspace_path=tmp_path.as_posix(),
        observed_pwd=tmp_path.as_posix(),
        pwd_matches_workspace_path=True,
        exit_code=0,
        stdout=tmp_path.as_posix(),
        stderr="",
        timed_out=False,
        read_only=True,
        allowlisted=True,
        uses_agent_workspace=True,
        runs_command=True,
    )
    adapter_calls = {"can_launch": 0, "launch": 0, "is_alive": 0}

    class _PassingProofRunner:
        def run_probe(self, *, workspace_context):
            assert workspace_context.ready is True
            assert workspace_context.uses_agent_workspace is True
            return proof

    class _LaunchExplodingAdapter:
        def adapter_kind(self):
            return "fake"

        def can_launch(self, *, agent_type, runtime_type):
            adapter_calls["can_launch"] += 1
            return True

        def launch(self, *, request):
            adapter_calls["launch"] += 1
            raise AssertionError("fake launch must not run when audit fails")

        def is_alive(self, *, handle):
            adapter_calls["is_alive"] += 1
            raise AssertionError("runtime probe must not run when audit fails")

    monkeypatch.setattr(
        "app.workers.worktree_safe_command.WorkerWorktreeSafeCommandProofRunner",
        lambda: _PassingProofRunner(),
    )
    monkeypatch.setattr(
        "app.workers.task_worker.FakeRuntimeAdapter",
        _LaunchExplodingAdapter,
    )
    monkeypatch.setattr(
        "app.workers.task_worker.event_stream_service.publish_task_updated",
        lambda **kwargs: None,
    )

    executor_service = _ExplodingExecutorService()
    task_repository = _FakeTaskRepository(task)
    run_repository = _FakeRunRepository()
    runtime_event_audit_service = _SpyRuntimeEventAuditService(
        raises=RuntimeError("simulated runtime gate audit write failure")
    )
    worker = TaskWorker(
        session=_NoopDbSession(),
        task_repository=task_repository,
        run_repository=run_repository,
        executor_service=executor_service,
        verifier_service=None,
        budget_guard_service=_AllowingBudgetGuardService(),
        run_logging_service=_NoopRunLoggingService(),
        cost_estimator_service=None,
        context_builder_service=_FakeContextBuilderService(),
        task_router_service=_FakeTaskRouterService(task),
        model_routing_service=None,
        prompt_registry_service=None,
        prompt_builder_service=None,
        token_accounting_service=None,
        task_state_machine_service=TaskStateMachineService(),
        failure_review_service=type(
            "_NoopFailureReviewService",
            (),
            {"ensure_review": lambda self, *, task, run: None},
        )(),
        agent_conversation_service=_FakeAgentConversationService(agent_session),
        runtime_event_audit_service=runtime_event_audit_service,
    )

    try:
        worker.run_once()
    except RuntimeError as exc:
        assert "simulated runtime gate audit write failure" in str(exc)
    else:
        raise AssertionError("runtime gate audit failure must propagate")

    assert len(runtime_event_audit_service.calls) == 1
    call = runtime_event_audit_service.calls[0]
    assert call["gate_result"].ready is True
    assert call["gate_result"].gates_failed == []
    assert call["adapter_kind"] == "fake"
    assert call["workspace_path"] == tmp_path.as_posix()
    assert call["observed_pwd"] == tmp_path.as_posix()
    assert call["launch_cwd_preview"] == tmp_path.as_posix()
    assert adapter_calls == {"can_launch": 1, "launch": 0, "is_alive": 0}
    assert executor_service.build_execution_plan_calls == 0
    assert executor_service.execute_task_calls == 0
    assert task_repository.task.status == TaskStatus.FAILED
    assert run_repository.run is not None
    assert run_repository.run.status == RunStatus.FAILED
    assert run_repository.run.verification_summary == (
        "Verification skipped because the worker crashed."
    )


def test_runtime_launch_dry_run_blocks_non_worktree_without_execution():
    session = _session(workspace_type=WorkspaceType.IN_PLACE)
    validation = validate_worker_agent_workspace(session)
    context = resolve_worker_workspace_context(validation)

    dry_run = build_worker_runtime_launch_dry_run(
        agent_session=session,
        workspace_context=context,
    )

    assert dry_run.ready is False
    assert dry_run.source == "agent_session_non_worktree"
    assert dry_run.reason_code == "agent_worktree_not_available"
    assert dry_run.launch_command_preview is None
    assert dry_run.uses_agent_workspace is False
    assert dry_run.command_preview_uses_workspace is False
    assert dry_run.execution_enabled is False
    assert dry_run.runs_command is False
    assert dry_run.launches_runtime is False


def test_runtime_launch_dry_run_blocks_invalid_worktree_context(tmp_path):
    session = _session(workspace_path=(tmp_path / "missing").as_posix())
    validation = validate_worker_agent_workspace(session)
    context = resolve_worker_workspace_context(validation)

    dry_run = build_worker_runtime_launch_dry_run(
        agent_session=session,
        workspace_context=context,
    )

    assert dry_run.ready is False
    assert dry_run.source == "workspace_context_blocked"
    assert dry_run.reason_code == "workspace_path_not_found"
    assert dry_run.launch_cwd_preview is None
    assert dry_run.launch_command_preview is None
    assert dry_run.runs_command is False
    assert dry_run.launches_runtime is False


def test_worker_run_once_response_exposes_workspace_context_evidence_fields():
    payload = WorkerRunOnceResponse.from_result(
        WorkerRunResult(
            claimed=True,
            message="resolver evidence only",
            workspace_type="worktree",
            workspace_path="/tmp/aido-worktree",
            workspace_clean=True,
            workspace_context_ready=True,
            workspace_context_source="agent_session_worktree",
            workspace_context_reason_code=None,
            workspace_context_path="/tmp/aido-worktree",
            workspace_context_resolved_path="/tmp/aido-worktree",
            workspace_context_uses_agent_workspace=True,
            workspace_context_changes_cwd=False,
            workspace_context_runs_git=False,
            workspace_context_runs_write_git=False,
            workspace_context_launches_runtime=False,
            runtime_launch_dry_run_ready=True,
            runtime_launch_dry_run_source=(
                "agent_session_worktree_runtime_dry_run"
            ),
            runtime_launch_dry_run_reason_code=None,
            runtime_launch_dry_run_session_id="session-123",
            runtime_launch_dry_run_agent_type="openai_provider",
            runtime_launch_dry_run_runtime_type="subprocess",
            runtime_launch_dry_run_workspace_path="/tmp/aido-worktree",
            runtime_launch_dry_run_resolved_workspace_path="/tmp/aido-worktree",
            runtime_launch_dry_run_launch_cwd_preview="/tmp/aido-worktree",
            runtime_launch_dry_run_launch_command_preview=(
                "RuntimeCreateConfig(session_id=session-123, "
                "runtime_type=subprocess, agent_type=openai_provider, "
                "workspace_path=/tmp/aido-worktree)"
            ),
            runtime_launch_dry_run_uses_agent_workspace=True,
            runtime_launch_dry_run_command_preview_uses_workspace=True,
            runtime_launch_dry_run_execution_enabled=False,
            runtime_launch_dry_run_changes_cwd=False,
            runtime_launch_dry_run_runs_command=False,
            runtime_launch_dry_run_runs_git=False,
            runtime_launch_dry_run_runs_write_git=False,
            runtime_launch_dry_run_launches_runtime=False,
            runtime_launch_gate_ready=True,
            runtime_launch_gate_gates_passed=[
                "workspace_validation",
                "workspace_context",
                "runtime_dry_run",
                "safe_command_proof",
                "adapter_capability",
            ],
            runtime_launch_gate_gates_failed=[],
            runtime_launch_gate_blocking_reason_code=None,
            runtime_launch_gate_blocking_summary=None,
            runtime_launch_gate_changes_process_cwd=False,
            runtime_launch_gate_runs_real_command=False,
            runtime_launch_gate_runs_git=False,
            runtime_launch_gate_runs_write_git=False,
            runtime_launch_gate_launches_ai_runtime=False,
            runtime_launch_gate_execution_enabled=False,
            runtime_lifecycle_snapshot=RuntimeLifecycleSnapshot(
                ready=True,
                source="runtime_lifecycle_snapshot_ready",
                state=RuntimeLifecycleState.UNKNOWN,
                reason=RuntimeLifecycleReason.SNAPSHOT_ONLY,
                reason_code="snapshot_only",
                summary=(
                    "Runtime lifecycle snapshot captured launch-gate-ready "
                    "evidence only; fake_launch_started=False; "
                    "real_runtime_started=False; runtime_probe_started=False."
                ),
                session_id="session-123",
                agent_type="openai_provider",
                runtime_type="subprocess",
                adapter_kind="fake",
                workspace_path="/tmp/aido-worktree",
                resolved_workspace_path="/tmp/aido-worktree",
                launch_cwd_preview="/tmp/aido-worktree",
                gates_passed=[
                    "workspace_validation",
                    "workspace_context",
                    "runtime_dry_run",
                    "safe_command_proof",
                    "adapter_capability",
                ],
                gates_failed=[],
                launch_requested=False,
                fake_launch_started=False,
                real_runtime_started=False,
                runtime_probe_started=False,
                execution_enabled=False,
                changes_process_cwd=False,
                runs_real_command=False,
                runs_git=False,
                runs_write_git=False,
                launches_ai_runtime=False,
            ),
            worktree_safe_command_proof_ready=True,
            worktree_safe_command_proof_source=(
                "agent_session_worktree_safe_command"
            ),
            worktree_safe_command_proof_reason_code=None,
            worktree_safe_command_proof_command="pwd",
            worktree_safe_command_proof_cwd="/tmp/aido-worktree",
            worktree_safe_command_proof_expected_workspace_path=(
                "/tmp/aido-worktree"
            ),
            worktree_safe_command_proof_observed_pwd="/tmp/aido-worktree",
            worktree_safe_command_proof_pwd_matches_workspace_path=True,
            worktree_safe_command_proof_exit_code=0,
            worktree_safe_command_proof_stdout="/tmp/aido-worktree",
            worktree_safe_command_proof_stderr="",
            worktree_safe_command_proof_timed_out=False,
            worktree_safe_command_proof_read_only=True,
            worktree_safe_command_proof_allowlisted=True,
            worktree_safe_command_proof_uses_agent_workspace=True,
            worktree_safe_command_proof_changes_process_cwd=False,
            worktree_safe_command_proof_runs_command=True,
            worktree_safe_command_proof_runs_git=False,
            worktree_safe_command_proof_runs_write_git=False,
            worktree_safe_command_proof_launches_worker_loop=False,
            worktree_safe_command_proof_launches_ai_runtime=False,
            git_diff_dry_run_ready=True,
            git_diff_dry_run_source="agent_session_worktree_diff",
            git_diff_dry_run_reason_code=None,
            git_diff_dry_run_worktree_path="/tmp/aido-worktree",
            git_diff_dry_run_has_changes=True,
            git_diff_dry_run_changed_files_count=3,
            git_diff_dry_run_changed_files=[
                "README.md",
                "src/app.py",
                "src/old_name.py",
            ],
            git_diff_dry_run_added_files=["src/app.py"],
            git_diff_dry_run_modified_files=["README.md"],
            git_diff_dry_run_deleted_files=[],
            git_diff_dry_run_renamed_files=["src/old_name.py"],
            git_diff_dry_run_status_summary_cn=(
                "1 个文件修改，1 个文件新增，1 个文件重命名"
            ),
            git_diff_dry_run_diff_stat=(
                " README.md | 2 +-\n src/app.py | 1 +"
            ),
            git_diff_dry_run_diff_shortstat=(
                "2 files changed, 2 insertions(+), 1 deletion(-)"
            ),
            git_diff_dry_run_branch_name="feature/p4-b2",
            git_diff_dry_run_compare_branch="main",
            git_diff_dry_run_command=(
                "git status --porcelain=v1 --untracked-files=all"
            ),
            git_diff_dry_run_peek_command="git diff --name-status",
            git_diff_dry_run_danger_commands_applied=False,
            git_diff_dry_run_runs_git=True,
            git_diff_dry_run_runs_write_git=False,
            git_diff_dry_run_git_add_triggered=False,
            git_diff_dry_run_git_commit_triggered=False,
            git_diff_dry_run_git_push_triggered=False,
            git_diff_dry_run_pr_opened=False,
            git_diff_dry_run_ci_triggered=False,
            git_diff_dry_run_execution_enabled=False,
            git_operation_dry_run_ready=True,
            git_operation_dry_run_source="git_operation_dry_run",
            git_operation_dry_run_reason_code=None,
            git_operation_dry_run_session_id="session-123",
            git_operation_dry_run_project_id="project-123",
            git_operation_dry_run_task_id="task-123",
            git_operation_dry_run_run_id="run-123",
            git_operation_dry_run_worktree_path="/tmp/aido-worktree",
            git_operation_dry_run_branch_name="feature/p4-b2",
            git_operation_dry_run_changed_files_count=3,
            git_operation_dry_run_changed_files=[
                "README.md",
                "src/app.py",
                "src/old_name.py",
            ],
            git_operation_dry_run_added_files=["src/app.py"],
            git_operation_dry_run_modified_files=["README.md"],
            git_operation_dry_run_deleted_files=[],
            git_operation_dry_run_renamed_files=["src/old_name.py"],
            git_operation_dry_run_proposed_operation="git_add_commit",
            git_operation_dry_run_proposed_steps=[
                "准备加入待提交区（git add，预览不执行）",
                "准备生成本地提交（git commit，预览不执行）："
                "chore: update 3 files from agent work",
            ],
            git_operation_dry_run_proposed_commit_message=(
                "chore: update 3 files from agent work"
            ),
            git_operation_dry_run_proposed_pr_title=None,
            git_operation_dry_run_proposed_pr_body=None,
            git_operation_dry_run_user_confirmation_required=True,
            git_operation_dry_run_human_approval_required=True,
            git_operation_dry_run_feature_flag_required=True,
            git_operation_dry_run_summary_cn=(
                "已生成提交预览：检测到 3 个文件变更。"
                "如果确认，将把这些文件提交到分支 feature/p4-b2。"
                "尚未加入待提交区、尚未生成本地提交、尚未推送。"
            ),
            git_operation_dry_run_runs_git=False,
            git_operation_dry_run_runs_write_git=False,
            git_operation_dry_run_git_add_triggered=False,
            git_operation_dry_run_git_commit_triggered=False,
            git_operation_dry_run_git_push_triggered=False,
            git_operation_dry_run_pr_opened=False,
            git_operation_dry_run_ci_triggered=False,
            git_operation_dry_run_execution_enabled=False,
            git_operation_dry_run_operation_applied=False,
            git_operation_dry_run_approval_granted=False,
        )
    ).model_dump(mode="json")

    assert payload["workspace_context_ready"] is True
    assert payload["workspace_context_source"] == "agent_session_worktree"
    assert payload["workspace_context_reason_code"] is None
    assert payload["workspace_context_path"] == "/tmp/aido-worktree"
    assert payload["workspace_context_resolved_path"] == "/tmp/aido-worktree"
    assert payload["workspace_context_uses_agent_workspace"] is True
    assert payload["workspace_context_changes_cwd"] is False
    assert payload["workspace_context_runs_git"] is False
    assert payload["workspace_context_runs_write_git"] is False
    assert payload["workspace_context_launches_runtime"] is False
    assert payload["runtime_launch_dry_run_ready"] is True
    assert (
        payload["runtime_launch_dry_run_source"]
        == "agent_session_worktree_runtime_dry_run"
    )
    assert payload["runtime_launch_dry_run_reason_code"] is None
    assert payload["runtime_launch_dry_run_session_id"] == "session-123"
    assert payload["runtime_launch_dry_run_agent_type"] == "openai_provider"
    assert payload["runtime_launch_dry_run_runtime_type"] == "subprocess"
    assert payload["runtime_launch_dry_run_workspace_path"] == "/tmp/aido-worktree"
    assert (
        payload["runtime_launch_dry_run_resolved_workspace_path"]
        == "/tmp/aido-worktree"
    )
    assert (
        payload["runtime_launch_dry_run_launch_cwd_preview"]
        == "/tmp/aido-worktree"
    )
    assert (
        "/tmp/aido-worktree"
        in payload["runtime_launch_dry_run_launch_command_preview"]
    )
    assert payload["runtime_launch_dry_run_uses_agent_workspace"] is True
    assert (
        payload["runtime_launch_dry_run_command_preview_uses_workspace"] is True
    )
    assert payload["runtime_launch_dry_run_execution_enabled"] is False
    assert payload["runtime_launch_dry_run_changes_cwd"] is False
    assert payload["runtime_launch_dry_run_runs_command"] is False
    assert payload["runtime_launch_dry_run_runs_git"] is False
    assert payload["runtime_launch_dry_run_runs_write_git"] is False
    assert payload["runtime_launch_dry_run_launches_runtime"] is False
    assert payload["runtime_launch_gate_ready"] is True
    assert payload["runtime_launch_gate_gates_passed"] == [
        "workspace_validation",
        "workspace_context",
        "runtime_dry_run",
        "safe_command_proof",
        "adapter_capability",
    ]
    assert payload["runtime_launch_gate_gates_failed"] == []
    assert payload["runtime_launch_gate_blocking_reason_code"] is None
    assert payload["runtime_launch_gate_blocking_summary"] is None
    assert payload["runtime_launch_gate_changes_process_cwd"] is False
    assert payload["runtime_launch_gate_runs_real_command"] is False
    assert payload["runtime_launch_gate_runs_git"] is False
    assert payload["runtime_launch_gate_runs_write_git"] is False
    assert payload["runtime_launch_gate_launches_ai_runtime"] is False
    assert payload["runtime_launch_gate_execution_enabled"] is False
    assert payload["runtime_lifecycle_snapshot"] == {
        "ready": True,
        "source": "runtime_lifecycle_snapshot_ready",
        "state": "unknown",
        "reason": "snapshot_only",
        "reason_code": "snapshot_only",
        "summary": (
            "Runtime lifecycle snapshot captured launch-gate-ready "
            "evidence only; fake_launch_started=False; "
            "real_runtime_started=False; runtime_probe_started=False."
        ),
        "session_id": "session-123",
        "agent_type": "openai_provider",
        "runtime_type": "subprocess",
        "adapter_kind": "fake",
        "workspace_path": "/tmp/aido-worktree",
        "resolved_workspace_path": "/tmp/aido-worktree",
        "launch_cwd_preview": "/tmp/aido-worktree",
        "runtime_handle_id": None,
        "gates_passed": [
            "workspace_validation",
            "workspace_context",
            "runtime_dry_run",
            "safe_command_proof",
            "adapter_capability",
        ],
        "gates_failed": [],
        "blocking_reason_code": None,
        "blocking_summary": None,
        "launch_requested": False,
        "fake_launch_started": False,
        "real_runtime_started": False,
        "runtime_probe_started": False,
        "probe_state": None,
        "probe_reason_code": None,
        "probe_error_summary": None,
        "execution_enabled": False,
        "changes_process_cwd": False,
        "runs_real_command": False,
        "runs_git": False,
        "runs_write_git": False,
        "launches_ai_runtime": False,
    }
    assert payload["worktree_safe_command_proof_ready"] is True
    assert (
        payload["worktree_safe_command_proof_source"]
        == "agent_session_worktree_safe_command"
    )
    assert payload["worktree_safe_command_proof_reason_code"] is None
    assert payload["worktree_safe_command_proof_command"] == "pwd"
    assert payload["worktree_safe_command_proof_cwd"] == "/tmp/aido-worktree"
    assert (
        payload["worktree_safe_command_proof_expected_workspace_path"]
        == "/tmp/aido-worktree"
    )
    assert (
        payload["worktree_safe_command_proof_observed_pwd"]
        == "/tmp/aido-worktree"
    )
    assert payload["worktree_safe_command_proof_pwd_matches_workspace_path"] is True
    assert payload["worktree_safe_command_proof_exit_code"] == 0
    assert payload["worktree_safe_command_proof_stdout"] == "/tmp/aido-worktree"
    assert payload["worktree_safe_command_proof_stderr"] == ""
    assert payload["worktree_safe_command_proof_timed_out"] is False
    assert payload["worktree_safe_command_proof_read_only"] is True
    assert payload["worktree_safe_command_proof_allowlisted"] is True
    assert payload["worktree_safe_command_proof_uses_agent_workspace"] is True
    assert payload["worktree_safe_command_proof_changes_process_cwd"] is False
    assert payload["worktree_safe_command_proof_runs_command"] is True
    assert payload["worktree_safe_command_proof_runs_git"] is False
    assert payload["worktree_safe_command_proof_runs_write_git"] is False
    assert payload["worktree_safe_command_proof_launches_worker_loop"] is False
    assert payload["worktree_safe_command_proof_launches_ai_runtime"] is False
    assert payload["git_diff_dry_run_ready"] is True
    assert payload["git_diff_dry_run_source"] == "agent_session_worktree_diff"
    assert payload["git_diff_dry_run_reason_code"] is None
    assert payload["git_diff_dry_run_worktree_path"] == "/tmp/aido-worktree"
    assert payload["git_diff_dry_run_has_changes"] is True
    assert payload["git_diff_dry_run_changed_files_count"] == 3
    assert payload["git_diff_dry_run_changed_files"] == [
        "README.md",
        "src/app.py",
        "src/old_name.py",
    ]
    assert payload["git_diff_dry_run_added_files"] == ["src/app.py"]
    assert payload["git_diff_dry_run_modified_files"] == ["README.md"]
    assert payload["git_diff_dry_run_deleted_files"] == []
    assert payload["git_diff_dry_run_renamed_files"] == ["src/old_name.py"]
    assert (
        payload["git_diff_dry_run_status_summary_cn"]
        == "1 个文件修改，1 个文件新增，1 个文件重命名"
    )
    assert "README.md" in payload["git_diff_dry_run_diff_stat"]
    assert "2 files changed" in payload["git_diff_dry_run_diff_shortstat"]
    assert payload["git_diff_dry_run_branch_name"] == "feature/p4-b2"
    assert payload["git_diff_dry_run_compare_branch"] == "main"
    assert (
        payload["git_diff_dry_run_command"]
        == "git status --porcelain=v1 --untracked-files=all"
    )
    assert payload["git_diff_dry_run_peek_command"] == "git diff --name-status"
    assert payload["git_diff_dry_run_danger_commands_applied"] is False
    assert payload["git_diff_dry_run_runs_git"] is True
    assert payload["git_diff_dry_run_runs_write_git"] is False
    assert payload["git_diff_dry_run_git_add_triggered"] is False
    assert payload["git_diff_dry_run_git_commit_triggered"] is False
    assert payload["git_diff_dry_run_git_push_triggered"] is False
    assert payload["git_diff_dry_run_pr_opened"] is False
    assert payload["git_diff_dry_run_ci_triggered"] is False
    assert payload["git_diff_dry_run_execution_enabled"] is False
    assert payload["git_operation_dry_run_ready"] is True
    assert payload["git_operation_dry_run_source"] == "git_operation_dry_run"
    assert payload["git_operation_dry_run_reason_code"] is None
    assert payload["git_operation_dry_run_session_id"] == "session-123"
    assert payload["git_operation_dry_run_project_id"] == "project-123"
    assert payload["git_operation_dry_run_task_id"] == "task-123"
    assert payload["git_operation_dry_run_run_id"] == "run-123"
    assert payload["git_operation_dry_run_worktree_path"] == "/tmp/aido-worktree"
    assert payload["git_operation_dry_run_branch_name"] == "feature/p4-b2"
    assert payload["git_operation_dry_run_changed_files_count"] == 3
    assert payload["git_operation_dry_run_changed_files"] == [
        "README.md",
        "src/app.py",
        "src/old_name.py",
    ]
    assert payload["git_operation_dry_run_added_files"] == ["src/app.py"]
    assert payload["git_operation_dry_run_modified_files"] == ["README.md"]
    assert payload["git_operation_dry_run_deleted_files"] == []
    assert payload["git_operation_dry_run_renamed_files"] == ["src/old_name.py"]
    assert payload["git_operation_dry_run_proposed_operation"] == "git_add_commit"
    assert payload["git_operation_dry_run_proposed_steps"] == [
        "准备加入待提交区（git add，预览不执行）",
        "准备生成本地提交（git commit，预览不执行）："
        "chore: update 3 files from agent work",
    ]
    assert payload["git_operation_dry_run_proposed_commit_message"] == (
        "chore: update 3 files from agent work"
    )
    assert payload["git_operation_dry_run_proposed_pr_title"] is None
    assert payload["git_operation_dry_run_proposed_pr_body"] is None
    assert payload["git_operation_dry_run_user_confirmation_required"] is True
    assert payload["git_operation_dry_run_human_approval_required"] is True
    assert payload["git_operation_dry_run_feature_flag_required"] is True
    assert payload["git_operation_dry_run_summary_cn"] == (
        "已生成提交预览：检测到 3 个文件变更。"
        "如果确认，将把这些文件提交到分支 feature/p4-b2。"
        "尚未加入待提交区、尚未生成本地提交、尚未推送。"
    )
    assert payload["git_operation_dry_run_runs_git"] is False
    assert payload["git_operation_dry_run_runs_write_git"] is False
    assert payload["git_operation_dry_run_git_add_triggered"] is False
    assert payload["git_operation_dry_run_git_commit_triggered"] is False
    assert payload["git_operation_dry_run_git_push_triggered"] is False
    assert payload["git_operation_dry_run_pr_opened"] is False
    assert payload["git_operation_dry_run_ci_triggered"] is False
    assert payload["git_operation_dry_run_execution_enabled"] is False
    assert payload["git_operation_dry_run_operation_applied"] is False
    assert payload["git_operation_dry_run_approval_granted"] is False
