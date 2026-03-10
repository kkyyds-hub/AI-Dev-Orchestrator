"""Single-cycle task worker used by Day 6 to Day 9."""

from dataclasses import asdict, dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.run import Run, RunFailureCategory, RunStatus
from app.domain.task import Task, TaskBlockingReasonCategory, TaskBlockingReasonCode
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.budget_guard_service import BudgetGuardDecision, BudgetGuardService
from app.services.context_builder_service import ContextBuilderService, TaskContextPackage
from app.services.cost_estimator_service import CostEstimate, CostEstimatorService
from app.services.event_stream_service import event_stream_service
from app.services.executor_service import ExecutionResult, ExecutorService
from app.services.run_logging_service import RunLoggingService
from app.services.task_router_service import TaskRouterService, TaskRoutingDecision
from app.services.task_state_machine_service import (
    TaskStateMachineService,
    TaskStateTransition,
)
from app.services.verifier_service import VerificationResult, VerifierService


_RUN_RESULT_SUMMARY_MAX_LENGTH = 2_000


@dataclass(slots=True)
class WorkerRunResult:
    """Single worker-cycle result returned to the API layer."""

    claimed: bool
    message: str
    execution_mode: str | None = None
    verification_mode: str | None = None
    verification_template: str | None = None
    verification_summary: str | None = None
    failure_category: RunFailureCategory | None = None
    quality_gate_passed: bool | None = None
    route_reason: str | None = None
    routing_score: float | None = None
    result_summary: str | None = None
    context_summary: str | None = None
    task: Task | None = None
    run: Run | None = None


class TaskWorker:
    """Claim one pending task, execute it and persist the outcome."""

    def __init__(
        self,
        *,
        session: Session,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        executor_service: ExecutorService,
        verifier_service: VerifierService,
        budget_guard_service: BudgetGuardService,
        run_logging_service: RunLoggingService,
        cost_estimator_service: CostEstimatorService,
        context_builder_service: ContextBuilderService,
        task_router_service: TaskRouterService,
        task_state_machine_service: TaskStateMachineService,
    ) -> None:
        self.session = session
        self.task_repository = task_repository
        self.run_repository = run_repository
        self.executor_service = executor_service
        self.verifier_service = verifier_service
        self.budget_guard_service = budget_guard_service
        self.run_logging_service = run_logging_service
        self.cost_estimator_service = cost_estimator_service
        self.context_builder_service = context_builder_service
        self.task_router_service = task_router_service
        self.task_state_machine_service = task_state_machine_service

    def run_once(self) -> WorkerRunResult:
        """Execute one conservative worker loop."""

        log_path: str | None = None
        context_package: TaskContextPackage | None = None
        routing_decision: TaskRoutingDecision | None = None

        try:
            routing_decision = self.task_router_service.route_next_task()
            if routing_decision.selected_task is None:
                return WorkerRunResult(
                    claimed=False,
                    message=routing_decision.message,
                )

            claim_transition = self.task_state_machine_service.build_claim_transition(
                task=routing_decision.selected_task,
            )
            task = self.task_repository.claim_pending_task(routing_decision.selected_task.id)
            if task is None:
                return WorkerRunResult(
                    claimed=False,
                    message="Router selected a task, but it was no longer pending when claimed.",
                )

            event_stream_service.publish_task_updated(
                task=task,
                reason=claim_transition.event_reason,
                previous_status=routing_decision.selected_task.status,
            )

            guard_decision = self.budget_guard_service.evaluate_before_execution(task.id)
            if not guard_decision.allowed:
                run = self.run_repository.create_running_run(
                    task_id=task.id,
                    route_reason=routing_decision.route_reason if routing_decision else None,
                    routing_score=(
                        routing_decision.routing_score if routing_decision else None
                    ),
                )
                run = self._initialize_run_log(task=task, run=run)
                log_path = run.log_path
                if routing_decision is not None:
                    self._log_routing_decision(run=run, routing_decision=routing_decision)

                self.run_logging_service.append_event(
                    log_path=log_path,
                    event="run_claimed",
                    message="Worker claimed a pending task and created a running run record.",
                    data={
                        "task_id": str(task.id),
                        "run_id": str(run.id),
                        "task_status": task.status.value,
                        "run_status": run.status.value,
                    },
                )

                self._log_guard_blocked(run=run, decision=guard_decision)
                task, run = self._finalize_guard_blocked_run(
                    task=task,
                    run=run,
                    decision=guard_decision,
                )
                self._log_finalization(task=task, run=run, final_summary=run.result_summary or "")
                self.session.commit()

                return WorkerRunResult(
                    claimed=True,
                    message=guard_decision.summary or "Budget guard blocked execution.",
                    failure_category=run.failure_category,
                    quality_gate_passed=run.quality_gate_passed,
                    route_reason=run.route_reason,
                    routing_score=run.routing_score,
                    result_summary=run.result_summary,
                    task=task,
                    run=run,
                )

            run = self.run_repository.create_running_run(
                task_id=task.id,
                route_reason=routing_decision.route_reason if routing_decision else None,
                routing_score=(
                    routing_decision.routing_score if routing_decision else None
                ),
            )
            run = self._initialize_run_log(task=task, run=run)
            log_path = run.log_path
            if routing_decision is not None:
                self._log_routing_decision(run=run, routing_decision=routing_decision)

            self.run_logging_service.append_event(
                log_path=log_path,
                event="run_claimed",
                message="Worker claimed a pending task and created a running run record.",
                data={
                    "task_id": str(task.id),
                    "run_id": str(run.id),
                    "task_status": task.status.value,
                    "run_status": run.status.value,
                },
            )

            context_package = self.context_builder_service.build_context_package(task=task)
            self._log_context_package(run=run, context_package=context_package)

            execution = self.executor_service.execute_task(
                task,
                context_package=context_package,
            )
            self._log_execution_result(run=run, execution=execution)

            verification = self._verify_if_needed(
                task=task,
                execution=execution,
            )
            self._log_verification_result(
                run=run,
                execution=execution,
                verification=verification,
            )

            cost_estimate = self.cost_estimator_service.estimate_run_cost(
                task=task,
                execution=execution,
                verification=verification,
            )
            self._log_cost_estimate(run=run, cost_estimate=cost_estimate)

            task, run, final_summary = self._finalize_execution(
                task=task,
                run=run,
                execution=execution,
                verification=verification,
                cost_estimate=cost_estimate,
            )
            self._log_finalization(task=task, run=run, final_summary=final_summary)

            self.session.commit()

            return WorkerRunResult(
                claimed=True,
                message=self._build_result_message(execution, verification),
                execution_mode=execution.mode,
                verification_mode=run.verification_mode if run else None,
                verification_template=run.verification_template if run else None,
                verification_summary=run.verification_summary if run else None,
                failure_category=run.failure_category if run else None,
                quality_gate_passed=run.quality_gate_passed if run else None,
                route_reason=run.route_reason if run else None,
                routing_score=run.routing_score if run else None,
                result_summary=final_summary,
                context_summary=(
                    context_package.context_summary if context_package is not None else None
                ),
                task=task,
                run=run,
            )
        except Exception as exc:
            if log_path is not None:
                self.run_logging_service.append_event(
                    log_path=log_path,
                    event="worker_rolled_back",
                    level="error",
                    message=f"Worker cycle raised {type(exc).__name__}: {exc}",
                    data={"exception_type": type(exc).__name__},
                )

            self.session.rollback()
            raise

    def _initialize_run_log(self, *, task: Task, run: Run) -> Run:
        """Create the runtime log file and persist its relative path."""

        log_path = self.run_logging_service.initialize_run_log(
            task_id=task.id,
            run_id=run.id,
        )
        return self.run_repository.set_log_path(run.id, log_path)

    def _finalize_guard_blocked_run(
        self,
        *,
        task: Task,
        run: Run,
        decision: BudgetGuardDecision,
    ) -> tuple[Task, Run]:
        """Persist a blocked task/run pair when Day 15 guard rejects execution."""

        resolution = self.task_state_machine_service.build_guard_blocked_resolution(
            task=task,
            failure_category=decision.failure_category,
        )
        updated_task = self._apply_task_transition(
            task_id=task.id,
            transition=resolution.task_transition,
        )
        updated_run = self.run_repository.finish_run(
            run.id,
            status=resolution.run_status,
            result_summary=decision.summary or "Budget guard blocked execution.",
            failure_category=resolution.failure_category,
            quality_gate_passed=resolution.quality_gate_passed,
        )
        event_stream_service.publish_task_updated(
            task=updated_task,
            reason=resolution.task_transition.event_reason,
            previous_status=task.status,
        )
        return updated_task, updated_run

    def _verify_if_needed(
        self,
        *,
        task: Task,
        execution: ExecutionResult,
    ) -> VerificationResult | None:
        """Run the Day 8 verification step only after a successful execution."""

        if not execution.success:
            return None

        return self.verifier_service.verify_task(
            task=task,
            execution_result=execution,
        )

    def _finalize_execution(
        self,
        *,
        task: Task,
        run: Run,
        execution: ExecutionResult,
        verification: VerificationResult | None,
        cost_estimate: CostEstimate,
    ) -> tuple[Task, Run, str]:
        """Persist final task/run statuses plus Day 9 / Day 14 metadata."""

        final_summary = self._build_combined_summary(execution, verification)
        failure_category: RunFailureCategory | None = None
        verification_summary: str | None = verification.summary if verification else None
        verification_mode = verification.mode if verification else None
        verification_template = verification.template_name if verification else None
        verification_command = verification.command if verification else None

        resolution = self.task_state_machine_service.build_execution_resolution(
            task=task,
            execution_succeeded=execution.success,
            verification_present=verification is not None,
            verification_succeeded=verification.success if verification else False,
            verification_quality_gate_passed=(
                verification.quality_gate_passed if verification else False
            ),
            verification_failure_category=(
                verification.failure_category if verification else None
            ),
        )
        if not execution.success:
            verification_summary = "Verification skipped because execution did not succeed."
        failure_category = resolution.failure_category

        updated_task = self._apply_task_transition(
            task_id=task.id,
            transition=resolution.task_transition,
        )
        updated_run = self.run_repository.finish_run(
            run.id,
            status=resolution.run_status,
            result_summary=final_summary,
            prompt_tokens=cost_estimate.prompt_tokens,
            completion_tokens=cost_estimate.completion_tokens,
            estimated_cost=cost_estimate.estimated_cost,
            verification_mode=verification_mode,
            verification_template=verification_template,
            verification_command=verification_command,
            verification_summary=verification_summary,
            failure_category=failure_category,
            quality_gate_passed=resolution.quality_gate_passed,
        )
        event_stream_service.publish_task_updated(
            task=updated_task,
            reason=resolution.task_transition.event_reason,
            previous_status=task.status,
        )
        return updated_task, updated_run, final_summary

    def _apply_task_transition(
        self,
        *,
        task_id: UUID,
        transition: TaskStateTransition,
    ) -> Task:
        """Persist one validated task transition."""

        update_kwargs: dict[str, object] = {"status": transition.status}
        if transition.update_human_status:
            update_kwargs["human_status"] = transition.human_status
        if transition.update_paused_reason:
            update_kwargs["paused_reason"] = transition.paused_reason

        return self.task_repository.update_control_state(task_id, **update_kwargs)

    def _log_execution_result(self, *, run: Run, execution: ExecutionResult) -> None:
        """Write the execution result to the JSONL log."""

        if run.log_path is None:
            return

        self.run_logging_service.append_event(
            log_path=run.log_path,
            event="execution_finished",
            level="info" if execution.success else "error",
            message=execution.summary,
            data={
                "mode": execution.mode,
                "success": execution.success,
                "command": execution.command,
                "exit_code": execution.exit_code,
            },
        )

    def _log_guard_blocked(
        self,
        *,
        run: Run,
        decision: BudgetGuardDecision,
    ) -> None:
        """Write the Day 15 budget or retry guard result to the JSONL log."""

        if run.log_path is None:
            return

        self.run_logging_service.append_event(
            log_path=run.log_path,
            event="guard_blocked",
            level="warning",
            message=decision.summary or "Budget guard blocked execution.",
            data={
                "blocking_signals": [
                    {
                        "code": TaskBlockingReasonCode.BUDGET_GUARD_BLOCKED,
                        "category": TaskBlockingReasonCategory.BUDGET,
                        "message": decision.summary
                        or "Budget guard blocked execution.",
                    }
                ],
                "failure_category": (
                    decision.failure_category.value if decision.failure_category else None
                ),
                "daily_budget_usd": decision.budget.daily_budget_usd,
                "daily_cost_used": decision.budget.daily_cost_used,
                "session_budget_usd": decision.budget.session_budget_usd,
                "session_cost_used": decision.budget.session_cost_used,
                "max_task_retries": decision.retry_status.max_task_retries,
                "execution_attempts": decision.retry_status.execution_attempts,
                "retries_used": decision.retry_status.retries_used,
                "retries_remaining": decision.retry_status.retries_remaining,
            },
        )

    def _log_verification_result(
        self,
        *,
        run: Run,
        execution: ExecutionResult,
        verification: VerificationResult | None,
    ) -> None:
        """Write verification outcome or skip information to the JSONL log."""

        if run.log_path is None:
            return

        if verification is None:
            self.run_logging_service.append_event(
                log_path=run.log_path,
                event="verification_skipped",
                message="Verification was skipped because execution did not succeed.",
                data={"execution_success": execution.success},
            )
            return

        self.run_logging_service.append_event(
            log_path=run.log_path,
            event="verification_finished",
            level="info" if verification.success else "error",
            message=verification.summary,
            data={
                "mode": verification.mode,
                "template_name": verification.template_name,
                "success": verification.success,
                "command": verification.command,
                "exit_code": verification.exit_code,
                "failure_category": (
                    verification.failure_category.value
                    if verification.failure_category is not None
                    else None
                ),
                "quality_gate_passed": verification.quality_gate_passed,
            },
        )

    def _log_cost_estimate(self, *, run: Run, cost_estimate: CostEstimate) -> None:
        """Write the heuristic token and cost estimate to the JSONL log."""

        if run.log_path is None:
            return

        self.run_logging_service.append_event(
            log_path=run.log_path,
            event="cost_estimated",
            message="Worker recorded the Day 9 heuristic token and cost estimate.",
            data=asdict(cost_estimate),
        )

    def _log_context_package(
        self,
        *,
        run: Run,
        context_package: TaskContextPackage,
    ) -> None:
        """Write the execution context package to the JSONL log."""

        if run.log_path is None:
            return

        self.run_logging_service.append_event(
            log_path=run.log_path,
            event="context_built",
            message="Worker assembled the minimal execution context package.",
            data=asdict(context_package),
        )

    def _log_routing_decision(
        self,
        *,
        run: Run,
        routing_decision: TaskRoutingDecision,
    ) -> None:
        """Write the routing decision and candidate scores to the JSONL log."""

        if run.log_path is None:
            return

        self.run_logging_service.append_event(
            log_path=run.log_path,
            event="task_routed",
            message=routing_decision.message,
            data={
                "selected_task_id": (
                    str(routing_decision.selected_task.id)
                    if routing_decision.selected_task is not None
                    else None
                ),
                "routing_score": routing_decision.routing_score,
                "route_reason": routing_decision.route_reason,
                "candidates": [
                    {
                        "task_id": str(candidate.task.id),
                        "title": candidate.task.title,
                        "ready": candidate.ready,
                        "routing_score": candidate.routing_score,
                        "route_reason": candidate.route_reason,
                        "blocking_signals": [
                            {
                                "code": signal.code.value,
                                "category": signal.category.value,
                                "message": signal.message,
                            }
                            for signal in candidate.readiness.blocking_signals
                        ],
                        "execution_attempts": candidate.execution_attempts,
                        "recent_failure_count": candidate.recent_failure_count,
                    }
                    for candidate in routing_decision.candidates
                ],
            },
        )

    def _log_finalization(self, *, task: Task, run: Run, final_summary: str) -> None:
        """Write the final persisted state to the JSONL log."""

        if run.log_path is None:
            return

        self.run_logging_service.append_event(
            log_path=run.log_path,
            event="run_finalized",
            message="Task and run were finalized.",
            data={
                "task_status": task.status.value,
                "run_status": run.status.value,
                "prompt_tokens": run.prompt_tokens,
                "completion_tokens": run.completion_tokens,
                "estimated_cost": run.estimated_cost,
                "route_reason": run.route_reason,
                "routing_score": run.routing_score,
                "result_summary": final_summary,
                "verification_mode": run.verification_mode,
                "verification_template": run.verification_template,
                "verification_summary": run.verification_summary,
                "failure_category": (
                    run.failure_category.value if run.failure_category else None
                ),
                "quality_gate_passed": run.quality_gate_passed,
            },
        )

    @staticmethod
    def _build_result_message(
        execution: ExecutionResult,
        verification: VerificationResult | None,
    ) -> str:
        """Build the API-facing summary for one worker cycle."""

        if not execution.success:
            return (
                f"Worker execution failed via {execution.mode}. "
                "Quality gate blocked completion."
            )

        if verification is None:
            return (
                f"Worker execution succeeded via {execution.mode}. "
                "Task and run were finalized."
            )

        if verification.success:
            return (
                f"Worker execution succeeded via {execution.mode} "
                f"and verification succeeded via {verification.mode}. "
                "Quality gate allowed completion."
            )

        if verification.failure_category == RunFailureCategory.VERIFICATION_CONFIGURATION_FAILED:
            return (
                f"Worker execution succeeded via {execution.mode} "
                "but verification configuration was invalid. "
                "Quality gate blocked completion."
            )

        return (
            f"Worker execution succeeded via {execution.mode} "
            f"but verification failed via {verification.mode}. "
            "Quality gate blocked completion."
        )

    @staticmethod
    def _build_combined_summary(
        execution: ExecutionResult,
        verification: VerificationResult | None,
    ) -> str:
        """Combine execution and verification summaries into the persisted result."""

        summary_parts = [f"Execution: {execution.summary}"]
        if verification is not None:
            summary_parts.append(f"Verification: {verification.summary}")

        summary = "\n".join(summary_parts)
        if len(summary) <= _RUN_RESULT_SUMMARY_MAX_LENGTH:
            return summary

        return summary[: _RUN_RESULT_SUMMARY_MAX_LENGTH - 3] + "..."
