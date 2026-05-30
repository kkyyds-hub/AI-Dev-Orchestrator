"""Safe simulate execution override coverage for worker evidence runs."""

from app.domain.model_policy import (
    ExecutorModelRoutingContract,
    ExecutorRouteMode,
    ExecutorRoutingStrategyHint,
    ExecutorRoutingTarget,
)
from app.domain.task import Task
from app.services.executor_service import ExecutorService


def _provider_routing_contract() -> ExecutorModelRoutingContract:
    return ExecutorModelRoutingContract(
        primary_mode=ExecutorRouteMode.PROVIDER,
        primary_target=ExecutorRoutingTarget(
            provider_key="deepseek",
            model_name="deepseek-v4-pro",
            api_family="chat_completions",
        ),
        route_reason="test provider route",
        strategy_hint=ExecutorRoutingStrategyHint(
            strategy_code="test-provider-route",
            model_tier="balanced",
        ),
    )


def test_default_provider_routing_still_selects_provider_mode() -> None:
    task = Task(title="provider task", input_summary="created through API only")
    executor = ExecutorService(force_simulate_execution_override=False)

    plan = executor.build_execution_plan(
        task=task,
        routing_contract=_provider_routing_contract(),
    )

    assert plan.mode == ExecutorRouteMode.PROVIDER.value
    assert plan.payload == "created through API only"
    assert plan.routing_contract is not None


def test_simulate_override_forces_provider_routing_to_simulate() -> None:
    task = Task(title="evidence task", input_summary="created through API only")
    executor = ExecutorService(force_simulate_execution_override=True)

    plan = executor.build_execution_plan(
        task=task,
        routing_contract=_provider_routing_contract(),
    )

    assert plan.mode == ExecutorRouteMode.SIMULATE.value
    assert plan.payload == "created through API only"
    assert plan.routing_contract is not None


def test_simulate_override_execute_task_bypasses_provider_path(monkeypatch) -> None:
    task = Task(title="evidence task", input_summary="created through API only")
    executor = ExecutorService(force_simulate_execution_override=True)

    def fail_provider_path(*args, **kwargs):  # pragma: no cover - only called on regression
        raise AssertionError("provider path must not run under simulate override")

    monkeypatch.setattr(executor, "_execute_provider_mode", fail_provider_path)

    result = executor.execute_task(
        task,
        routing_contract=_provider_routing_contract(),
    )

    assert result.success is True
    assert result.mode == ExecutorRouteMode.SIMULATE.value
    assert result.actual_execution_mode == ExecutorRouteMode.SIMULATE.value
    assert result.requested_provider_key is None


def test_simulate_failure_mode_failed_returns_failed_simulate_result() -> None:
    task = Task(title="evidence task", input_summary="created through API only")
    executor = ExecutorService(
        force_simulate_execution_override=True,
        simulate_failure_mode="failed",
    )

    result = executor.execute_task(
        task,
        routing_contract=_provider_routing_contract(),
    )

    assert result.success is False
    assert result.mode == ExecutorRouteMode.SIMULATE.value
    assert result.actual_execution_mode == ExecutorRouteMode.SIMULATE.value
    assert result.fallback_reason_category == "simulate_failure_injection"
    assert result.simulate_failure_mode == "failed"
    assert "intentionally failed" in result.summary


def test_invalid_simulate_failure_mode_keeps_default_success_path() -> None:
    task = Task(title="evidence task", input_summary="created through API only")
    executor = ExecutorService(
        force_simulate_execution_override=True,
        simulate_failure_mode="not-a-mode",
    )

    result = executor.execute_task(
        task,
        routing_contract=_provider_routing_contract(),
    )

    assert result.success is True
    assert result.mode == ExecutorRouteMode.SIMULATE.value
    assert result.simulate_failure_mode is None


def test_simulate_failure_mode_blocked_returns_blocked_injection_signal() -> None:
    task = Task(title="evidence task", input_summary="created through API only")
    executor = ExecutorService(
        force_simulate_execution_override=True,
        simulate_failure_mode="blocked",
    )

    result = executor.execute_task(
        task,
        routing_contract=_provider_routing_contract(),
    )

    assert result.success is False
    assert result.mode == ExecutorRouteMode.SIMULATE.value
    assert result.actual_execution_mode == ExecutorRouteMode.SIMULATE.value
    assert result.fallback_reason_category == "simulate_failure_injection"
    assert result.simulate_failure_mode == "blocked"
