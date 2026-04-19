"""Single-cycle task worker used by Day 6 to Day 9."""

from dataclasses import asdict, dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.project_role import ProjectRoleCode
from app.domain.prompt_contract import BuiltPromptEnvelope
from app.domain.prompt_contract import TokenAccountingSnapshot
from app.domain.run import (
    Run,
    RunBudgetPressureLevel,
    RunBudgetStrategyAction,
    RunFailureCategory,
    RunRoutingScoreItem,
    RunStatus,
)
from app.domain.task import (
    Task,
    TaskBlockingReasonCategory,
    TaskBlockingReasonCode,
    TaskStatus,
)
from app.repositories.failure_review_repository import FailureReviewRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.project_role_repository import ProjectRoleRepository
from app.repositories.run_repository import RunRepository
from app.repositories.skill_repository import SkillRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.agent_message_repository import AgentMessageRepository
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.deliverable_repository import DeliverableRepository
from app.services.agent_conversation_service import AgentConversationService
from app.services.budget_guard_service import BudgetGuardDecision, BudgetGuardService
from app.services.context_budget_service import ContextBudgetService
from app.services.context_builder_service import ContextBuilderService, TaskContextPackage
from app.services.cost_estimator_service import CostEstimate, CostEstimatorService
from app.services.event_stream_service import event_stream_service
from app.services.executor_service import ExecutionPlan, ExecutionResult, ExecutorService
from app.services.failure_review_service import FailureReviewService
from app.services.model_routing_service import ModelRoutingService
from app.services.memory_compaction_service import MemoryCompactionService
from app.services.prompt_builder_service import PromptBuilderService
from app.services.prompt_registry_service import PromptRegistryService
from app.services.project_memory_service import ProjectMemoryService
from app.services.role_catalog_service import RoleCatalogService
from app.services.run_logging_service import RunLoggingService
from app.services.skill_registry_service import SkillRegistryService
from app.services.strategy_engine_service import StrategyEngineService
from app.services.task_readiness_service import TaskReadinessService
from app.services.task_router_service import TaskRouterService, TaskRoutingDecision
from app.services.task_state_machine_service import (
    TaskStateMachineService,
    TaskStateTransition,
)
from app.services.token_accounting_service import TokenAccountingService
from app.services.verifier_service import VerificationResult, VerifierService


_RUN_RESULT_SUMMARY_MAX_LENGTH = 2_000
_CLAIM_RETRY_LIMIT = 3


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
    routing_score_breakdown: list[RunRoutingScoreItem] = field(default_factory=list)
    budget_pressure_level: RunBudgetPressureLevel | None = None
    budget_action: RunBudgetStrategyAction | None = None
    budget_strategy_code: str | None = None
    budget_strategy_summary: str | None = None
    result_summary: str | None = None
    context_summary: str | None = None
    model_name: str | None = None
    model_tier: str | None = None
    selected_skill_codes: list[str] = field(default_factory=list)
    selected_skill_names: list[str] = field(default_factory=list)
    strategy_code: str | None = None
    strategy_summary: str | None = None
    owner_role_code: ProjectRoleCode | None = None
    upstream_role_code: ProjectRoleCode | None = None
    downstream_role_code: ProjectRoleCode | None = None
    handoff_reason: str | None = None
    dispatch_status: str | None = None
    project_memory_enabled: bool | None = None
    project_memory_query_text: str | None = None
    project_memory_item_count: int | None = None
    project_memory_context_summary: str | None = None
    memory_governance_checkpoint_id: str | None = None
    memory_governance_rolling_summary: str | None = None
    memory_governance_bad_context_detected: bool | None = None
    memory_governance_bad_context_reasons: list[str] = field(default_factory=list)
    memory_governance_pressure_level: str | None = None
    memory_governance_usage_ratio: float | None = None
    memory_governance_compaction_applied: bool | None = None
    memory_governance_compaction_ratio: float | None = None
    memory_governance_rehydrated: bool | None = None
    memory_governance_rehydrate_source_checkpoint_id: str | None = None
    agent_session_id: UUID | None = None
    agent_session_status: str | None = None
    agent_review_status: str | None = None
    agent_current_phase: str | None = None
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
        model_routing_service: ModelRoutingService,
        prompt_registry_service: PromptRegistryService,
        prompt_builder_service: PromptBuilderService,
        token_accounting_service: TokenAccountingService,
        task_state_machine_service: TaskStateMachineService,
        failure_review_service: FailureReviewService,
        agent_conversation_service: AgentConversationService,
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
        self.model_routing_service = model_routing_service
        self.prompt_registry_service = prompt_registry_service
        self.prompt_builder_service = prompt_builder_service
        self.token_accounting_service = token_accounting_service
        self.task_state_machine_service = task_state_machine_service
        self.failure_review_service = failure_review_service
        self.agent_conversation_service = agent_conversation_service

    def run_once(self, *, project_id: UUID | None = None) -> WorkerRunResult:
        """Execute one conservative worker loop.

        When ``project_id`` is provided, routing is scoped to pending tasks
        under that project only.
        """

        task: Task | None = None
        run: Run | None = None
        log_path: str | None = None
        context_package: TaskContextPackage | None = None
        routing_decision: TaskRoutingDecision | None = None
        claim_transition: TaskStateTransition | None = None
        agent_session_id: UUID | None = None
        agent_session_status: str | None = None
        agent_review_status: str | None = None
        agent_current_phase: str | None = None

        try:
            for _ in range(_CLAIM_RETRY_LIMIT):
                routing_decision = self.task_router_service.route_next_task(
                    project_id=project_id
                )
                if routing_decision.selected_task is None:
                    return WorkerRunResult(
                        claimed=False,
                        message=routing_decision.message,
                        budget_pressure_level=routing_decision.budget_pressure_level,
                        budget_action=routing_decision.budget_action,
                        budget_strategy_code=routing_decision.budget_strategy_code,
                        budget_strategy_summary=routing_decision.budget_strategy_summary,
                    )

                claim_transition = self.task_state_machine_service.build_claim_transition(
                    task=routing_decision.selected_task,
                )
                task = self.task_repository.claim_pending_task(routing_decision.selected_task.id)
                if task is not None:
                    break

                self.session.rollback()
            else:
                return WorkerRunResult(
                    claimed=False,
                    message=(
                        "Router repeatedly selected tasks that were already claimed by "
                        "another worker."
                    ),
                )

            self.session.commit()
            assert task is not None
            assert routing_decision is not None
            assert routing_decision.selected_task is not None
            assert claim_transition is not None
            event_stream_service.publish_task_updated(
                task=task,
                reason=claim_transition.event_reason,
                previous_status=routing_decision.selected_task.status,
            )

            guard_decision = self.budget_guard_service.evaluate_before_execution(task.id)
            if not guard_decision.allowed:
                run = self.run_repository.create_running_run(
                    task_id=task.id,
                    model_name=routing_decision.model_name if routing_decision else None,
                    route_reason=routing_decision.route_reason if routing_decision else None,
                    routing_score=(
                        routing_decision.routing_score if routing_decision else None
                    ),
                    routing_score_breakdown=(
                        routing_decision.routing_score_breakdown
                        if routing_decision
                        else []
                    ),
                    strategy_decision=(
                        routing_decision.strategy_decision if routing_decision else None
                    ),
                    owner_role_code=(
                        routing_decision.owner_role_code if routing_decision else None
                    ),
                    upstream_role_code=(
                        routing_decision.upstream_role_code if routing_decision else None
                    ),
                    downstream_role_code=(
                        routing_decision.downstream_role_code if routing_decision else None
                    ),
                    handoff_reason=(
                        routing_decision.handoff_reason if routing_decision else None
                    ),
                    dispatch_status=(
                        routing_decision.dispatch_status if routing_decision else None
                    ),
                )
                run = self._initialize_run_log(task=task, run=run)
                log_path = run.log_path
                if routing_decision is not None:
                    self._log_routing_decision(run=run, routing_decision=routing_decision)
                    self._log_role_handoff(
                        task=task,
                        run=run,
                        routing_decision=routing_decision,
                    )

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

                task, run = self._finalize_guard_blocked_path(
                    task=task,
                    run=run,
                    decision=guard_decision,
                )
                self.session.commit()
                self._record_failure_review_if_needed(task=task, run=run)

                return WorkerRunResult(
                    claimed=True,
                    message=guard_decision.summary or "Budget guard blocked execution.",
                    failure_category=run.failure_category,
                    quality_gate_passed=run.quality_gate_passed,
                    route_reason=run.route_reason,
                    routing_score=run.routing_score,
                    routing_score_breakdown=run.routing_score_breakdown,
                    budget_pressure_level=guard_decision.pressure_level,
                    budget_action=guard_decision.suggested_action,
                    budget_strategy_code=guard_decision.strategy_code,
                    budget_strategy_summary=guard_decision.budget.strategy_summary,
                    result_summary=run.result_summary,
                    model_name=run.model_name,
                    model_tier=(
                        run.strategy_decision.model_tier
                        if run.strategy_decision is not None
                        else None
                    ),
                    selected_skill_codes=(
                        list(run.strategy_decision.selected_skill_codes)
                        if run.strategy_decision is not None
                        else []
                    ),
                    selected_skill_names=(
                        list(run.strategy_decision.selected_skill_names)
                        if run.strategy_decision is not None
                        else []
                    ),
                    strategy_code=(
                        run.strategy_decision.strategy_code
                        if run.strategy_decision is not None
                        else None
                    ),
                    strategy_summary=(
                        run.strategy_decision.summary
                        if run.strategy_decision is not None
                        else None
                    ),
                    owner_role_code=run.owner_role_code,
                    upstream_role_code=run.upstream_role_code,
                    downstream_role_code=run.downstream_role_code,
                    handoff_reason=run.handoff_reason,
                    dispatch_status=run.dispatch_status,
                    task=task,
                    run=run,
                )

            run = self.run_repository.create_running_run(
                task_id=task.id,
                model_name=routing_decision.model_name if routing_decision else None,
                route_reason=routing_decision.route_reason if routing_decision else None,
                routing_score=(
                    routing_decision.routing_score if routing_decision else None
                ),
                routing_score_breakdown=(
                    routing_decision.routing_score_breakdown
                    if routing_decision
                    else []
                ),
                strategy_decision=(
                    routing_decision.strategy_decision if routing_decision else None
                ),
                owner_role_code=(
                    routing_decision.owner_role_code if routing_decision else None
                ),
                upstream_role_code=(
                    routing_decision.upstream_role_code if routing_decision else None
                ),
                downstream_role_code=(
                    routing_decision.downstream_role_code if routing_decision else None
                ),
                handoff_reason=(
                    routing_decision.handoff_reason if routing_decision else None
                ),
                dispatch_status=(
                    routing_decision.dispatch_status if routing_decision else None
                ),
            )
            run = self._initialize_run_log(task=task, run=run)
            log_path = run.log_path
            if routing_decision is not None:
                self._log_routing_decision(run=run, routing_decision=routing_decision)
                self._log_role_handoff(
                    task=task,
                    run=run,
                    routing_decision=routing_decision,
                )

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
            self.session.commit()

            context_package = self.context_builder_service.build_context_package(
                task=task,
                run_id=run.id,
                include_project_memory=True,
            )
            if task.project_id is not None:
                context_seed = self.context_builder_service.build_agent_thread_context_seed(
                    task=task,
                    context_package=context_package,
                )
                agent_session = self.agent_conversation_service.start_session(
                    project_id=task.project_id,
                    task_id=task.id,
                    run_id=run.id,
                    owner_role_code=run.owner_role_code,
                    context_seed=context_seed,
                )
                agent_session = self.agent_conversation_service.record_execution_started(
                    session_id=agent_session.id
                )
                agent_session_id = agent_session.id
                agent_session_status = agent_session.status.value
                agent_review_status = agent_session.review_status.value
                agent_current_phase = agent_session.current_phase.value
            self._log_context_package(run=run, context_package=context_package)
            if run.log_path is not None and context_package.governance_checkpoint_id is not None:
                self.run_logging_service.append_event(
                    log_path=run.log_path,
                    event="memory_governance_checkpointed",
                    message=(
                        "Day09 memory governance checkpoint was persisted for this task context."
                    ),
                    data={
                        "checkpoint_id": context_package.governance_checkpoint_id,
                        "pressure_level": context_package.governance_pressure_level,
                        "usage_ratio": context_package.governance_usage_ratio,
                        "bad_context_detected": (
                            context_package.governance_bad_context_detected
                        ),
                        "bad_context_reasons": (
                            context_package.governance_bad_context_reasons
                        ),
                        "compaction_applied": (
                            context_package.governance_compaction_applied
                        ),
                        "rehydrated": context_package.governance_rehydrated,
                    },
                )
            routing_contract = self.model_routing_service.build_contract_from_strategy_decision(
                routing_decision.strategy_decision if routing_decision is not None else None
            )
            execution_plan = self.executor_service.build_execution_plan(
                task=task,
                routing_contract=routing_contract,
            )
            self._log_execution_plan(
                run=run,
                execution_plan=execution_plan,
            )
            prompt_envelope = self.prompt_builder_service.build_execution_prompt(
                task=task,
                context_package=context_package,
                execution_plan=execution_plan,
                routing_contract=routing_contract,
            )
            self._log_prompt_contract(
                run=run,
                execution_plan=execution_plan,
                prompt_envelope=prompt_envelope,
            )

            execution = self.executor_service.execute_task(
                task,
                context_package=context_package,
                routing_contract=routing_contract,
                prompt_envelope=prompt_envelope,
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

            token_accounting = self.token_accounting_service.build_snapshot(
                prompt_envelope=prompt_envelope,
                completion_text="\n".join(
                    part
                    for part in (
                        execution.summary.strip(),
                        verification.summary.strip() if verification is not None else "",
                    )
                    if part
                ),
                execution_mode=execution.mode,
                provider_usage_receipt=execution.provider_usage_receipt,
            )
            self._log_token_accounting(run=run, token_accounting=token_accounting)

            cost_estimate = self.cost_estimator_service.estimate_run_cost(
                task=task,
                execution=execution,
                verification=verification,
                prompt_envelope=prompt_envelope,
                token_accounting_snapshot=token_accounting,
            )
            self._log_cost_estimate(run=run, cost_estimate=cost_estimate)

            task, run, final_summary = self._finalize_execution(
                task=task,
                run=run,
                execution=execution,
                verification=verification,
                cost_estimate=cost_estimate,
                prompt_envelope=prompt_envelope,
                token_accounting=token_accounting,
            )
            if agent_session_id is not None:
                agent_session = self.agent_conversation_service.record_execution_outcome(
                    session_id=agent_session_id,
                    execution_success=execution.success,
                    execution_summary=execution.summary,
                    verification_present=verification is not None,
                    verification_success=verification.success if verification else False,
                    verification_summary=verification.summary if verification else None,
                    run_failure_category=(
                        verification.failure_category
                        if verification is not None
                        else None
                    ),
                )
                agent_session = self.agent_conversation_service.finalize_session(
                    session_id=agent_session.id,
                    run_status=run.status,
                    run_failure_category=run.failure_category,
                    final_summary=final_summary,
                )
                agent_session_status = agent_session.status.value
                agent_review_status = agent_session.review_status.value
                agent_current_phase = agent_session.current_phase.value
            self._log_finalization(
                task=task,
                run=run,
                final_summary=final_summary,
                execution=execution,
            )

            self.session.commit()
            self._record_failure_review_if_needed(task=task, run=run)

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
                routing_score_breakdown=(
                    run.routing_score_breakdown if run else []
                ),
                budget_pressure_level=(
                    routing_decision.budget_pressure_level
                    if routing_decision is not None
                    else None
                ),
                budget_action=(
                    routing_decision.budget_action
                    if routing_decision is not None
                    else None
                ),
                budget_strategy_code=(
                    routing_decision.budget_strategy_code
                    if routing_decision is not None
                    else None
                ),
                budget_strategy_summary=(
                    routing_decision.budget_strategy_summary
                    if routing_decision is not None
                    else None
                ),
                result_summary=final_summary,
                context_summary=(
                    context_package.context_summary if context_package is not None else None
                ),
                project_memory_enabled=(
                    context_package.project_memory_enabled
                    if context_package is not None
                    else None
                ),
                project_memory_query_text=(
                    context_package.project_memory_query_text
                    if context_package is not None
                    else None
                ),
                project_memory_item_count=(
                    context_package.project_memory_item_count
                    if context_package is not None
                    else None
                ),
                project_memory_context_summary=(
                    context_package.project_memory_context_summary
                    if context_package is not None
                    else None
                ),
                memory_governance_checkpoint_id=(
                    context_package.governance_checkpoint_id
                    if context_package is not None
                    else None
                ),
                memory_governance_rolling_summary=(
                    context_package.governance_rolling_summary
                    if context_package is not None
                    else None
                ),
                memory_governance_bad_context_detected=(
                    context_package.governance_bad_context_detected
                    if context_package is not None
                    else None
                ),
                memory_governance_bad_context_reasons=(
                    list(context_package.governance_bad_context_reasons)
                    if context_package is not None
                    else []
                ),
                memory_governance_pressure_level=(
                    context_package.governance_pressure_level
                    if context_package is not None
                    else None
                ),
                memory_governance_usage_ratio=(
                    context_package.governance_usage_ratio
                    if context_package is not None
                    else None
                ),
                memory_governance_compaction_applied=(
                    context_package.governance_compaction_applied
                    if context_package is not None
                    else None
                ),
                memory_governance_compaction_ratio=(
                    context_package.governance_compaction_ratio
                    if context_package is not None
                    else None
                ),
                memory_governance_rehydrated=(
                    context_package.governance_rehydrated
                    if context_package is not None
                    else None
                ),
                memory_governance_rehydrate_source_checkpoint_id=(
                    context_package.governance_rehydrate_source_checkpoint_id
                    if context_package is not None
                    else None
                ),
                agent_session_id=agent_session_id,
                agent_session_status=agent_session_status,
                agent_review_status=agent_review_status,
                agent_current_phase=agent_current_phase,
                model_name=run.model_name if run else None,
                model_tier=(
                    run.strategy_decision.model_tier
                    if run and run.strategy_decision is not None
                    else None
                ),
                selected_skill_codes=(
                    list(run.strategy_decision.selected_skill_codes)
                    if run and run.strategy_decision is not None
                    else []
                ),
                selected_skill_names=(
                    list(run.strategy_decision.selected_skill_names)
                    if run and run.strategy_decision is not None
                    else []
                ),
                strategy_code=(
                    run.strategy_decision.strategy_code
                    if run and run.strategy_decision is not None
                    else None
                ),
                strategy_summary=(
                    run.strategy_decision.summary
                    if run and run.strategy_decision is not None
                    else None
                ),
                owner_role_code=run.owner_role_code if run else None,
                upstream_role_code=run.upstream_role_code if run else None,
                downstream_role_code=run.downstream_role_code if run else None,
                handoff_reason=run.handoff_reason if run else None,
                dispatch_status=run.dispatch_status if run else None,
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
            if task is not None and run is not None:
                self._best_effort_finalize_crashed_run(
                    task_id=task.id,
                    run_id=run.id,
                    exception_summary=(
                        f"Worker raised {type(exc).__name__}: {exc}. "
                        "Run was recovered into a failed state."
                    ),
                )
            raise

    def _initialize_run_log(self, *, task: Task, run: Run) -> Run:
        """Create the runtime log file and persist its relative path."""

        log_path = self.run_logging_service.initialize_run_log(
            task_id=task.id,
            run_id=run.id,
        )
        return self.run_repository.set_log_path(run.id, log_path)

    def _finalize_guard_blocked_path(
        self,
        *,
        task: Task,
        run: Run,
        decision: BudgetGuardDecision,
    ) -> tuple[Task, Run]:
        """Persist and log a blocked task/run pair when the guard rejects execution."""

        self._log_guard_blocked(run=run, decision=decision)
        updated_task, updated_run = self._finalize_guard_blocked_run(
            task=task,
            run=run,
            decision=decision,
        )
        self._log_finalization(
            task=updated_task,
            run=updated_run,
            final_summary=updated_run.result_summary or "",
        )
        return updated_task, updated_run

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

    def _best_effort_finalize_crashed_run(
        self,
        *,
        task_id: UUID,
        run_id: UUID,
        exception_summary: str,
    ) -> None:
        """Recover a crashed in-flight run into a stable failed state."""

        persisted_task = self.task_repository.get_by_id(task_id)
        persisted_run = self.run_repository.get_by_id(run_id)
        if (
            persisted_task is None
            or persisted_run is None
            or persisted_task.status != TaskStatus.RUNNING
            or persisted_run.status != RunStatus.RUNNING
        ):
            return

        resolution = self.task_state_machine_service.build_execution_resolution(
            task=persisted_task,
            execution_succeeded=False,
            verification_present=False,
            verification_succeeded=False,
            verification_quality_gate_passed=False,
            verification_failure_category=None,
        )
        updated_task = self._apply_task_transition(
            task_id=task_id,
            transition=resolution.task_transition,
        )
        updated_run = self.run_repository.finish_run(
            run_id,
            status=resolution.run_status,
            result_summary=self._truncate_summary(exception_summary),
            verification_summary="Verification skipped because the worker crashed.",
            failure_category=resolution.failure_category,
            quality_gate_passed=resolution.quality_gate_passed,
        )
        if updated_run.log_path is not None:
            self.run_logging_service.append_event(
                log_path=updated_run.log_path,
                event="run_recovered",
                level="error",
                message="Worker crash was converted into a failed run.",
                data={
                    "task_status": updated_task.status.value,
                    "run_status": updated_run.status.value,
                    "failure_category": (
                        updated_run.failure_category.value
                        if updated_run.failure_category is not None
                        else None
                    ),
                },
            )

        self._log_finalization(
            task=updated_task,
            run=updated_run,
            final_summary=updated_run.result_summary or exception_summary,
        )
        self.session.commit()
        event_stream_service.publish_task_updated(
            task=updated_task,
            reason=resolution.task_transition.event_reason,
            previous_status=TaskStatus.RUNNING,
        )
        self._record_failure_review_if_needed(task=updated_task, run=updated_run)

    def _record_failure_review_if_needed(self, *, task: Task, run: Run) -> None:
        """Persist one failure review for failed, cancelled or guard-blocked runs."""

        self.failure_review_service.ensure_review(task=task, run=run)

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
        prompt_envelope: BuiltPromptEnvelope,
        token_accounting: TokenAccountingSnapshot,
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
            provider_key=token_accounting.provider_key,
            prompt_template_key=prompt_envelope.template_ref.prompt_key,
            prompt_template_version=prompt_envelope.template_ref.version,
            prompt_char_count=prompt_envelope.prompt_char_count,
            token_accounting_mode=token_accounting.accounting_mode.value,
            provider_receipt_id=token_accounting.provider_receipt_id,
            total_tokens=token_accounting.total_tokens,
            token_pricing_source=token_accounting.pricing_source,
            prompt_tokens=token_accounting.prompt_tokens,
            completion_tokens=token_accounting.completion_tokens,
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
                "prompt_key": execution.prompt_key,
                "prompt_char_count": execution.prompt_char_count,
                "requested_provider_key": execution.requested_provider_key,
                "actual_execution_mode": (
                    execution.actual_execution_mode or execution.mode
                ),
                "fallback_applied": execution.fallback_applied,
                "fallback_reason_category": execution.fallback_reason_category,
                "fallback_from": execution.fallback_from,
                "fallback_to": execution.fallback_to,
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
                "daily_usage_ratio": decision.budget.daily_usage_ratio,
                "session_budget_usd": decision.budget.session_budget_usd,
                "session_cost_used": decision.budget.session_cost_used,
                "session_usage_ratio": decision.budget.session_usage_ratio,
                "pressure_level": decision.pressure_level.value,
                "suggested_action": decision.suggested_action.value,
                "strategy_code": decision.strategy_code,
                "strategy_summary": decision.budget.strategy_summary,
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

    def _log_prompt_contract(
        self,
        *,
        run: Run,
        execution_plan: ExecutionPlan,
        prompt_envelope: BuiltPromptEnvelope,
    ) -> None:
        """Write the Day06-Step1 prompt contract snapshot to the JSONL log."""

        if run.log_path is None:
            return

        self.run_logging_service.append_event(
            log_path=run.log_path,
            event="prompt_contract_built",
            message="Worker prepared the Day06-Step1 prompt contract skeleton.",
            data={
                "execution_mode": execution_plan.mode,
                "prompt_key": prompt_envelope.template_ref.prompt_key,
                "prompt_version": prompt_envelope.template_ref.version,
                "provider_key": prompt_envelope.provider_key,
                "model_name": prompt_envelope.model_name,
                "prompt_char_count": prompt_envelope.prompt_char_count,
                "section_keys": [section.key for section in prompt_envelope.sections],
            },
        )

    def _log_token_accounting(
        self,
        *,
        run: Run,
        token_accounting: TokenAccountingSnapshot,
    ) -> None:
        """Write the Day06-Step2 token snapshot to the JSONL log."""

        if run.log_path is None:
            return

        self.run_logging_service.append_event(
            log_path=run.log_path,
            event="token_accounting_ready",
            message="Worker recorded the Day06-Step2 token accounting snapshot.",
            data=token_accounting.model_dump(mode="json"),
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
                "owner_role_code": routing_decision.owner_role_code,
                "upstream_role_code": routing_decision.upstream_role_code,
                "downstream_role_code": routing_decision.downstream_role_code,
                "dispatch_status": routing_decision.dispatch_status,
                "handoff_reason": routing_decision.handoff_reason,
                "routing_score_breakdown": [
                    item.model_dump()
                    for item in routing_decision.routing_score_breakdown
                ],
                "budget_pressure_level": routing_decision.budget_pressure_level.value,
                "budget_action": routing_decision.budget_action.value,
                "budget_strategy_code": routing_decision.budget_strategy_code,
                "budget_strategy_summary": routing_decision.budget_strategy_summary,
                "project_stage": (
                    routing_decision.project_stage.value
                    if routing_decision.project_stage is not None
                    else None
                ),
                "model_name": routing_decision.model_name,
                "model_tier": routing_decision.model_tier,
                "selected_skill_codes": list(routing_decision.selected_skill_codes),
                "selected_skill_names": list(routing_decision.selected_skill_names),
                "strategy_code": routing_decision.strategy_code,
                "strategy_summary": routing_decision.strategy_summary,
                "strategy_reasons": [
                    reason.model_dump() for reason in routing_decision.strategy_reasons
                ],
                "candidates": [
                    {
                        "task_id": str(candidate.task.id),
                        "title": candidate.task.title,
                        "ready": candidate.ready,
                        "routing_score": candidate.routing_score,
                        "route_reason": candidate.route_reason,
                        "owner_role_code": candidate.owner_role_code,
                        "upstream_role_code": candidate.upstream_role_code,
                        "downstream_role_code": candidate.downstream_role_code,
                        "dispatch_status": candidate.dispatch_status,
                        "handoff_reason": candidate.handoff_reason,
                        "matched_terms": list(candidate.matched_terms),
                        "routing_score_breakdown": [
                            item.model_dump()
                            for item in candidate.routing_score_breakdown
                        ],
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
                        "budget_pressure_level": candidate.budget_pressure_level.value,
                        "budget_action": candidate.budget_action.value,
                        "budget_strategy_code": candidate.budget_strategy_code,
                        "budget_score_adjustment": candidate.budget_score_adjustment,
                        "project_stage": (
                            candidate.project_stage.value
                            if candidate.project_stage is not None
                            else None
                        ),
                        "model_name": candidate.model_name,
                        "model_tier": candidate.model_tier,
                        "selected_skill_codes": list(candidate.selected_skill_codes),
                        "selected_skill_names": list(candidate.selected_skill_names),
                        "strategy_code": candidate.strategy_code,
                        "strategy_summary": candidate.strategy_summary,
                        "strategy_reasons": [
                            reason.model_dump() for reason in candidate.strategy_reasons
                        ],
                    }
                    for candidate in routing_decision.candidates
                ],
            },
        )

    def _log_execution_plan(self, *, run: Run, execution_plan: ExecutionPlan) -> None:
        """Write the executor plan and consumed routing contract to the JSONL log."""

        if run.log_path is None:
            return

        routing_contract = execution_plan.routing_contract
        primary_target = routing_contract.primary_target if routing_contract is not None else None
        strategy_hint = routing_contract.strategy_hint if routing_contract is not None else None
        self.run_logging_service.append_event(
            log_path=run.log_path,
            event="execution_plan_ready",
            level="info",
            message=(
                "Executor prepared the merged execution plan."
                if routing_contract is None
                else "Executor prepared a provider-routed execution plan."
            ),
            data={
                "mode": execution_plan.mode,
                "has_routing_contract": routing_contract is not None,
                "provider_key": (
                    primary_target.provider_key if primary_target is not None else None
                ),
                "provider_model_name": (
                    primary_target.model_name if primary_target is not None else None
                ),
                "provider_api_family": (
                    primary_target.api_family if primary_target is not None else None
                ),
                "fallback_mode": (
                    routing_contract.implicit_fallback_mode.value
                    if routing_contract is not None
                    else None
                ),
                "strategy_code": (
                    strategy_hint.strategy_code if strategy_hint is not None else None
                ),
                "route_reason": (
                    routing_contract.route_reason if routing_contract is not None else None
                ),
            },
        )

    def _log_role_handoff(
        self,
        *,
        task: Task,
        run: Run,
        routing_decision: TaskRoutingDecision,
    ) -> None:
        """Write the Day07 role handoff event to the JSONL log."""

        if run.log_path is None:
            return

        self.run_logging_service.append_role_handoff_event(
            log_path=run.log_path,
            project_id=task.project_id,
            owner_role_code=routing_decision.owner_role_code,
            upstream_role_code=routing_decision.upstream_role_code,
            downstream_role_code=routing_decision.downstream_role_code,
            dispatch_status=routing_decision.dispatch_status,
            handoff_reason=routing_decision.handoff_reason,
        )

    def _log_finalization(
        self,
        *,
        task: Task,
        run: Run,
        final_summary: str,
        execution: ExecutionResult | None = None,
    ) -> None:
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
                "model_name": run.model_name,
                "route_reason": run.route_reason,
                "routing_score": run.routing_score,
                "routing_score_breakdown": [
                    item.model_dump() for item in run.routing_score_breakdown
                ],
                "strategy_decision": (
                    run.strategy_decision.model_dump(mode="json")
                    if run.strategy_decision is not None
                    else None
                ),
                "owner_role_code": run.owner_role_code,
                "upstream_role_code": run.upstream_role_code,
                "downstream_role_code": run.downstream_role_code,
                "handoff_reason": run.handoff_reason,
                "dispatch_status": run.dispatch_status,
                "result_summary": final_summary,
                "verification_mode": run.verification_mode,
                "verification_template": run.verification_template,
                "verification_summary": run.verification_summary,
                "failure_category": (
                    run.failure_category.value if run.failure_category else None
                ),
                "quality_gate_passed": run.quality_gate_passed,
                "requested_provider_key": (
                    execution.requested_provider_key if execution is not None else None
                ),
                "actual_execution_mode": (
                    (execution.actual_execution_mode or execution.mode)
                    if execution is not None
                    else None
                ),
                "fallback_applied": (
                    execution.fallback_applied if execution is not None else False
                ),
                "fallback_reason_category": (
                    execution.fallback_reason_category if execution is not None else None
                ),
                "fallback_from": (
                    execution.fallback_from if execution is not None else None
                ),
                "fallback_to": execution.fallback_to if execution is not None else None,
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

    @staticmethod
    def _truncate_summary(summary: str) -> str:
        """Trim crash summaries to the persisted `result_summary` budget."""

        if len(summary) <= _RUN_RESULT_SUMMARY_MAX_LENGTH:
            return summary

        return summary[: _RUN_RESULT_SUMMARY_MAX_LENGTH - 3] + "..."


def build_task_worker(*, session: Session) -> TaskWorker:
    """Create the minimal worker graph for one session."""

    task_repository = TaskRepository(session)
    run_repository = RunRepository(session)
    budget_guard_service = BudgetGuardService(run_repository=run_repository)
    executor_service = ExecutorService()
    verifier_service = VerifierService(executor_service=executor_service)
    model_routing_service = ModelRoutingService()
    prompt_registry_service = PromptRegistryService()
    prompt_builder_service = PromptBuilderService(
        prompt_registry_service=prompt_registry_service,
    )
    token_accounting_service = TokenAccountingService()
    run_logging_service = RunLoggingService()
    cost_estimator_service = CostEstimatorService()
    task_state_machine_service = TaskStateMachineService()
    task_readiness_service = TaskReadinessService(
        task_repository=task_repository,
        run_repository=run_repository,
    )
    failure_review_service = FailureReviewService(
        failure_review_repository=FailureReviewRepository(),
        run_logging_service=run_logging_service,
    )
    agent_session_repository = AgentSessionRepository(session)
    agent_message_repository = AgentMessageRepository(session)
    agent_conversation_service = AgentConversationService(
        agent_session_repository=agent_session_repository,
        agent_message_repository=agent_message_repository,
    )
    project_memory_service = ProjectMemoryService(
        project_repository=ProjectRepository(session),
        task_repository=task_repository,
        run_repository=run_repository,
        deliverable_repository=DeliverableRepository(session),
        approval_repository=ApprovalRepository(session),
        failure_review_service=failure_review_service,
    )
    context_budget_service = ContextBudgetService()
    memory_compaction_service = MemoryCompactionService()
    context_builder_service = ContextBuilderService(
        run_repository=run_repository,
        task_readiness_service=task_readiness_service,
        project_memory_service=project_memory_service,
        context_budget_service=context_budget_service,
        memory_compaction_service=memory_compaction_service,
    )
    role_catalog_service = RoleCatalogService(
        project_repository=ProjectRepository(session),
        project_role_repository=ProjectRoleRepository(session),
    )
    skill_registry_service = SkillRegistryService(
        project_repository=ProjectRepository(session),
        role_catalog_service=role_catalog_service,
        skill_repository=SkillRepository(session),
    )
    strategy_engine_service = StrategyEngineService(
        project_repository=ProjectRepository(session),
        role_catalog_service=role_catalog_service,
        skill_registry_service=skill_registry_service,
        budget_guard_service=budget_guard_service,
    )
    task_router_service = TaskRouterService(
        task_repository=task_repository,
        run_repository=run_repository,
        task_readiness_service=task_readiness_service,
        budget_guard_service=budget_guard_service,
        strategy_engine_service=strategy_engine_service,
    )
    return TaskWorker(
        session=session,
        task_repository=task_repository,
        run_repository=run_repository,
        executor_service=executor_service,
        verifier_service=verifier_service,
        budget_guard_service=budget_guard_service,
        run_logging_service=run_logging_service,
        cost_estimator_service=cost_estimator_service,
        context_builder_service=context_builder_service,
        task_router_service=task_router_service,
        model_routing_service=model_routing_service,
        prompt_registry_service=prompt_registry_service,
        prompt_builder_service=prompt_builder_service,
        token_accounting_service=token_accounting_service,
        task_state_machine_service=task_state_machine_service,
        failure_review_service=failure_review_service,
        agent_conversation_service=agent_conversation_service,
    )
