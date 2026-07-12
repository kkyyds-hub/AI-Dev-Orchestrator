from __future__ import annotations

import ast
import re
from pathlib import Path


TASK_WORKER_PATH = Path("app/workers/task_worker.py")
WORKER_POOL_PATH = Path("app/workers/worker_pool.py")
WORKERS_ROUTE_PATH = Path("app/api/routes/workers.py")

# P23-D2 adds one approved grouped snapshot field; this is not a new flat capability field.
WORKER_RUN_RESULT_TOP_LEVEL_FIELD_LIMIT = 260
EXPECTED_GROUPED_SNAPSHOTS = (
    "runtime_snapshot",
    "external_executor_snapshot",
    "reserved_run_execution_snapshot",
    "delivery_snapshot",
    "approval_snapshot",
    "cost_snapshot",
)


def _source(path: Path) -> str:
    return path.read_text()


def _task_worker_module() -> ast.Module:
    return ast.parse(_source(TASK_WORKER_PATH))


def _worker_run_result_class() -> ast.ClassDef:
    for node in _task_worker_module().body:
        if isinstance(node, ast.ClassDef) and node.name == "WorkerRunResult":
            return node
    raise AssertionError("WorkerRunResult class was not found")


def _worker_run_result_field_names() -> list[str]:
    return [
        item.target.id
        for item in _worker_run_result_class().body
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
    ]


def _literal_tuple_constant(name: str) -> tuple[str, ...]:
    for node in _task_worker_module().body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == name
        ):
            value = ast.literal_eval(node.value)
            assert isinstance(value, tuple)
            return value
    raise AssertionError(f"{name} constant was not found")


def test_worker_run_result_can_be_located() -> None:
    worker_run_result = _worker_run_result_class()

    assert worker_run_result.name == "WorkerRunResult"
    assert any(
        isinstance(decorator, ast.Call)
        and getattr(decorator.func, "id", None) == "dataclass"
        for decorator in worker_run_result.decorator_list
    )


def test_worker_run_result_declares_no_more_flat_fields_guardrail_near_class() -> None:
    source = _source(TASK_WORKER_PATH)
    guard_index = source.index("WORKER_RUN_RESULT_TOP_LEVEL_FIELD_GUARD")
    class_index = source.index("class WorkerRunResult")
    nearby_source = source[guard_index:class_index + 600]

    assert "historical compatibility fields" in nearby_source
    assert "Do not add more flat fields" in nearby_source
    assert "prefer grouped snapshots" in nearby_source
    assert "external executor results" in nearby_source


def test_worker_run_result_grouped_snapshot_recommendations_are_declared() -> None:
    grouped_snapshots = _literal_tuple_constant(
        "WORKER_RUN_RESULT_FUTURE_GROUPED_SNAPSHOTS",
    )

    assert grouped_snapshots == EXPECTED_GROUPED_SNAPSHOTS


def test_worker_run_result_top_level_field_count_is_frozen() -> None:
    field_names = _worker_run_result_field_names()

    assert len(field_names) == WORKER_RUN_RESULT_TOP_LEVEL_FIELD_LIMIT


def test_worker_run_result_existing_fields_are_not_removed_by_guardrail() -> None:
    field_names = set(_worker_run_result_field_names())

    expected_legacy_fields = {
        "claimed",
        "message",
        "runtime_lifecycle_snapshot",
        "delivery_human_approval_gate_allows_write",
        "failure_recovery_decision",
        "agent_dispatch_decision",
        "task",
        "run",
    }
    assert expected_legacy_fields <= field_names


def test_task_worker_does_not_gain_actual_executor_integration_terms() -> None:
    source = _source(TASK_WORKER_PATH)

    forbidden_absent_terms = {
        "RealExecutorAdapter",
        "Codex CLI",
        "Claude Code",
        "DeepSeek CLI",
        "os.popen",
        "tmux",
        "shell=True",
    }
    for term in forbidden_absent_terms:
        assert term not in source

    assert source.count("subprocess") == 1
    assert re.search(r"\bpty\b", source) is None
    assert "actual_silent_launch_service" in source
    assert "actual_native_launcher" in source
    assert "actual_prelaunch" not in source


def test_worker_pool_and_workers_route_do_not_gain_external_executor_logic() -> None:
    forbidden_terms = {
        "RealExecutorAdapter",
        "external_executors",
        "external_executor_snapshot",
        "Codex CLI",
        "Claude Code",
        "DeepSeek CLI",
        "os.popen",
        "tmux",
        "shell=True",
    }

    for path in (WORKER_POOL_PATH, WORKERS_ROUTE_PATH):
        source = _source(path)
        for term in forbidden_terms:
            assert term not in source


def test_no_api_frontend_or_migration_entrypoints_added_for_guardrail() -> None:
    assert not Path("app/api/routes/worker_result_guardrails.py").exists()
    assert not Path("app/api/routes/external_executor.py").exists()
    assert not any(Path("migrations").glob("*worker_result*"))
    assert not any(Path("migrations").glob("*external_executor*"))
    assert not Path("../../apps/web/worker-result-guardrails").exists()
    assert not Path("../../apps/web/external-executors").exists()
