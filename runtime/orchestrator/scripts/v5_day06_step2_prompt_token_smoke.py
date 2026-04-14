"""Day06 Step2 smoke for prompt/token main-chain wiring."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from uuid import uuid4

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    from app.domain.project_role import ProjectRoleCode
    from app.domain.run import (
        RunBudgetPressureLevel,
        RunBudgetStrategyAction,
        RunStrategyDecision,
    )
    from app.domain.task import Task, TaskHumanStatus, TaskPriority, TaskRiskLevel
    from app.services.context_builder_service import TaskContextPackage
    from app.services.executor_service import ExecutorService
    from app.services.model_routing_service import ModelRoutingService
    from app.services.prompt_builder_service import PromptBuilderService
    from app.services.prompt_registry_service import PromptRegistryService
    from app.services.token_accounting_service import TokenAccountingService

    provider_task = Task(
        project_id=uuid4(),
        title="接入 Prompt / Token 合同到 provider mock 执行链",
        input_summary="实现 Prompt / Token 主链接线的最小切片",
        acceptance_criteria=["provider/mock provider 消费 prompt 合同", "产出 token accounting"],
        priority=TaskPriority.HIGH,
        risk_level=TaskRiskLevel.NORMAL,
        owner_role_code=ProjectRoleCode.ENGINEER,
    )
    context_package = TaskContextPackage(
        task_id=provider_task.id,
        task_title=provider_task.title,
        input_summary=provider_task.input_summary,
        acceptance_criteria=list(provider_task.acceptance_criteria),
        priority=provider_task.priority,
        risk_level=provider_task.risk_level,
        human_status=TaskHumanStatus.NONE,
        paused_reason=None,
        ready_for_execution=True,
        blocking_signals=[],
        blocking_reasons=[],
        dependency_items=[],
        recent_runs=[],
        context_summary="Day06-Step2 smoke context.",
    )
    strategy_decision = RunStrategyDecision(
        owner_role_code=ProjectRoleCode.ENGINEER,
        model_tier="standard",
        model_name="gpt-4.1",
        selected_skill_codes=["write-v5-runtime-backend"],
        selected_skill_names=["write-v5-runtime-backend"],
        budget_pressure_level=RunBudgetPressureLevel.NORMAL,
        budget_action=RunBudgetStrategyAction.FULL_SPEED,
        strategy_code="day06.step2.smoke",
        summary="Smoke uses provider mock path.",
        reasons=[],
        rule_codes=["smoke.provider"],
    )

    model_routing_service = ModelRoutingService()
    prompt_registry_service = PromptRegistryService()
    prompt_builder_service = PromptBuilderService(
        prompt_registry_service=prompt_registry_service,
    )
    token_accounting_service = TokenAccountingService()
    executor_service = ExecutorService()

    routing_contract = model_routing_service.build_contract_from_strategy_decision(strategy_decision)
    execution_plan = executor_service.build_execution_plan(
        task=provider_task,
        routing_contract=routing_contract,
    )
    prompt_envelope = prompt_builder_service.build_execution_prompt(
        task=provider_task,
        context_package=context_package,
        execution_plan=execution_plan,
        routing_contract=routing_contract,
    )
    provider_execution = executor_service.execute_task(
        provider_task,
        context_package=context_package,
        routing_contract=routing_contract,
        prompt_envelope=prompt_envelope,
    )
    token_snapshot = token_accounting_service.build_snapshot(
        prompt_envelope=prompt_envelope,
        completion_text=provider_execution.summary,
    )

    _assert(provider_execution.mode == "provider_mock", "provider mock path was not used")
    _assert(
        prompt_envelope.template_ref.prompt_key in provider_execution.summary,
        "provider mock path did not consume prompt contract",
    )
    _assert(token_snapshot.prompt_tokens > 0, "token accounting prompt tokens were not produced")
    _assert(
        token_snapshot.total_tokens == token_snapshot.prompt_tokens + token_snapshot.completion_tokens,
        "token accounting total_tokens mismatch",
    )

    shell_task = Task(
        title="shell prefix regression",
        input_summary="shell: Write-Output 'day06-step2-shell'",
        acceptance_criteria=["shell prefix still works"],
        priority=TaskPriority.NORMAL,
        risk_level=TaskRiskLevel.LOW,
    )
    shell_result = executor_service.execute_task(shell_task)
    _assert(shell_result.mode == "shell", "shell explicit prefix was broken")
    _assert(shell_result.success, "shell explicit prefix execution failed")

    simulate_task = Task(
        title="simulate prefix regression",
        input_summary="simulate: keep explicit simulate mode",
        acceptance_criteria=["simulate prefix still works"],
        priority=TaskPriority.NORMAL,
        risk_level=TaskRiskLevel.LOW,
    )
    simulate_result = executor_service.execute_task(simulate_task)
    _assert(simulate_result.mode == "simulate", "simulate explicit prefix was broken")
    _assert(simulate_result.success, "simulate explicit prefix execution failed")

    print(
        json.dumps(
            {
                "provider_execution_mode": provider_execution.mode,
                "provider_prompt_key": provider_execution.prompt_key,
                "provider_prompt_char_count": provider_execution.prompt_char_count,
                "token_snapshot": token_snapshot.model_dump(mode="json"),
                "shell_mode": shell_result.mode,
                "simulate_mode": simulate_result.mode,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
