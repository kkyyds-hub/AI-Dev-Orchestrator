"""Single-cycle task worker used by Day 6 to Day 9."""

from dataclasses import asdict, dataclass

from sqlalchemy.orm import Session

from app.domain.run import Run, RunStatus
from app.domain.task import Task, TaskStatus
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.cost_estimator_service import CostEstimate, CostEstimatorService
from app.services.executor_service import ExecutionResult, ExecutorService
from app.services.run_logging_service import RunLoggingService
from app.services.verifier_service import VerificationResult, VerifierService


_RUN_RESULT_SUMMARY_MAX_LENGTH = 2_000


@dataclass(slots=True)
class WorkerRunResult:
    """Single worker-cycle result returned to the API layer."""

    claimed: bool
    message: str
    execution_mode: str | None = None
    verification_mode: str | None = None
    verification_summary: str | None = None
    result_summary: str | None = None
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
        run_logging_service: RunLoggingService,
        cost_estimator_service: CostEstimatorService,
    ) -> None:
        self.session = session
        self.task_repository = task_repository
        self.run_repository = run_repository
        self.executor_service = executor_service
        self.verifier_service = verifier_service
        self.run_logging_service = run_logging_service
        self.cost_estimator_service = cost_estimator_service

    def run_once(self) -> WorkerRunResult:
        """Execute one conservative worker loop."""

        log_path: str | None = None

        try:
            task = self.task_repository.claim_next_pending()
            if task is None:
                return WorkerRunResult(
                    claimed=False,
                    message="No pending tasks available.",
                )

            run = self.run_repository.create_running_run(task_id=task.id)
            run = self._initialize_run_log(task=task, run=run)
            log_path = run.log_path

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

            execution = self.executor_service.execute_task(task)
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
                verification_mode=verification.mode if verification else None,
                verification_summary=verification.summary if verification else None,
                result_summary=final_summary,
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
        """Persist final task/run statuses plus Day 9 cost fields."""

        final_summary = self._build_combined_summary(execution, verification)
        run_status = (
            RunStatus.SUCCEEDED
            if execution.success and (verification is None or verification.success)
            else RunStatus.FAILED
        )
        task_status = (
            TaskStatus.COMPLETED
            if execution.success and (verification is None or verification.success)
            else TaskStatus.FAILED
        )

        updated_task = self.task_repository.set_status(task.id, task_status)
        updated_run = self.run_repository.finish_run(
            run.id,
            status=run_status,
            result_summary=final_summary,
            prompt_tokens=cost_estimate.prompt_tokens,
            completion_tokens=cost_estimate.completion_tokens,
            estimated_cost=cost_estimate.estimated_cost,
        )
        return updated_task, updated_run, final_summary

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
                "success": verification.success,
                "command": verification.command,
                "exit_code": verification.exit_code,
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
                "result_summary": final_summary,
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
                "Task and run were finalized with failure."
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
                "Task and run were finalized."
            )

        return (
            f"Worker execution succeeded via {execution.mode} "
            f"but verification failed via {verification.mode}. "
            "Task and run were finalized with failure."
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
