from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.services.real_git_write_pilot_readiness_service import (
    RealGitWritePilotReadinessRequest,
    RealGitWritePilotReadinessService,
)


NOW = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)
BASE_COMMIT = "febc0f57200d573c69b9912cc4dc1a41808635b4"

FORBIDDEN_READBACK_FRAGMENTS = [
    "raw command",
    "raw_command",
    "cwd",
    "env",
    "token value",
    "secret",
    "subprocess output",
]


def _request(**overrides: object) -> RealGitWritePilotReadinessRequest:
    payload = {
        "pilot_id": "pilot-1",
        "executor": {
            "executor_id": "codex",
            "executor_kind": "codex",
            "configured": True,
            "authenticated": True,
            "available": True,
            "model_or_profile": "gpt-5-codex",
            "safe_summary": "executor profile is ready",
            "checked_at": NOW,
        },
        "workspace": {
            "workspace_id": "workspace-1",
            "repository_id": "repo-1",
            "base_commit": BASE_COMMIT,
            "target_branch": "ai/gitwrite-pilot/2026-06-09-doc-only",
            "file_paths": ["docs/product/pilot.md"],
            "workspace_bound": True,
            "worktree_registered": True,
            "stale_workspace_detected": False,
            "safe_path_confirmed": True,
            "safe_summary": "workspace binding is ready",
            "checked_at": NOW,
        },
        "requested_by": "user-1",
        "requested_at": NOW,
    }
    payload.update(overrides)
    return RealGitWritePilotReadinessRequest(**payload)


def _gate_map(readback) -> dict[str, object]:
    return {gate.gate_name: gate for gate in readback.gate_checks}


def test_readiness_service_returns_preview_ready_when_executor_and_workspace_are_safe() -> None:
    readback = RealGitWritePilotReadinessService().build_readiness(_request())
    gates = _gate_map(readback)

    assert readback.pilot_id == "pilot-1"
    assert readback.executor_readiness.ready is True
    assert readback.workspace_binding.bound is True
    assert readback.ready_for_preview is True
    assert gates["executor_readiness"].passed is True
    assert gates["workspace_binding"].passed is True
    assert gates["target_branch_allowlist"].passed is True
    assert gates["file_scope"].passed is True


def test_readiness_readback_never_marks_execution_or_runtime_writes_started() -> None:
    readback = RealGitWritePilotReadinessService().build_readiness(_request())

    assert readback.ready_for_execution is False
    assert readback.product_runtime_git_write_executed is False
    assert readback.real_executor_started is False


@pytest.mark.parametrize("field", ["configured", "authenticated", "available"])
def test_executor_not_ready_blocks_executor_gate(field: str) -> None:
    request = _request(
        executor={
            "executor_id": "codex",
            "executor_kind": "codex",
            "configured": field != "configured",
            "authenticated": field != "authenticated",
            "available": field != "available",
            "model_or_profile": "gpt-5-codex",
            "safe_summary": "executor profile checked by caller",
            "checked_at": NOW,
        },
    )

    readback = RealGitWritePilotReadinessService().build_readiness(request)
    gate = _gate_map(readback)["executor_readiness"]

    assert readback.ready_for_preview is False
    assert readback.executor_readiness.ready is False
    assert gate.status.value == "blocked"
    assert gate.block_reason.value == "executor_not_ready"


@pytest.mark.parametrize(
    "workspace_overrides",
    [
        {"workspace_bound": False},
        {"worktree_registered": False},
        {"stale_workspace_detected": True},
        {"safe_path_confirmed": False},
    ],
)
def test_workspace_binding_problems_block_workspace_gate(
    workspace_overrides: dict[str, object],
) -> None:
    workspace = _request().workspace.model_dump()
    workspace.update(workspace_overrides)

    readback = RealGitWritePilotReadinessService().build_readiness(
        _request(workspace=workspace),
    )
    gate = _gate_map(readback)["workspace_binding"]

    assert readback.ready_for_preview is False
    assert readback.workspace_binding.bound is False
    assert gate.status.value == "blocked"
    assert gate.block_reason.value == "workspace_not_bound"


@pytest.mark.parametrize(
    "target_branch",
    ["main", "master", "release", "production", "staging", "gh-pages"],
)
def test_protected_target_branches_block_readiness(target_branch: str) -> None:
    workspace = _request().workspace.model_dump()
    workspace["target_branch"] = target_branch

    readback = RealGitWritePilotReadinessService().build_readiness(
        _request(workspace=workspace),
    )
    gate = _gate_map(readback)["target_branch_allowlist"]

    assert readback.ready_for_preview is False
    assert gate.status.value == "blocked"
    assert gate.block_reason.value == "main_branch_blocked"


@pytest.mark.parametrize(
    "target_branch",
    ["feature/doc-only", "ai/gitwrite-pilot/not-a-date-doc-only", "HEAD"],
)
def test_invalid_pilot_branch_blocks_readiness(target_branch: str) -> None:
    workspace = _request().workspace.model_dump()
    workspace["target_branch"] = target_branch

    readback = RealGitWritePilotReadinessService().build_readiness(
        _request(workspace=workspace),
    )
    gate = _gate_map(readback)["target_branch_allowlist"]

    assert readback.ready_for_preview is False
    assert gate.status.value == "blocked"
    assert gate.block_reason.value == "target_branch_not_allowed"


@pytest.mark.parametrize(
    "file_paths",
    [
        ["runtime/orchestrator/app/main.py"],
        ["docs/pilot.txt"],
        ["README.md"],
    ],
)
def test_non_docs_markdown_file_scope_blocks_readiness(file_paths: list[str]) -> None:
    workspace = _request().workspace.model_dump()
    workspace["file_paths"] = file_paths

    readback = RealGitWritePilotReadinessService().build_readiness(
        _request(workspace=workspace),
    )
    gate = _gate_map(readback)["file_scope"]

    assert readback.ready_for_preview is False
    assert gate.status.value == "blocked"
    assert gate.block_reason.value == "file_scope_not_allowed"


@pytest.mark.parametrize(
    "file_paths",
    [["/Users/kk/private/pilot.md"], ["../docs/pilot.md"], ["C:\\repo\\pilot.md"]],
)
def test_raw_or_unsafe_file_paths_fail_validation(file_paths: list[str]) -> None:
    workspace = _request().workspace.model_dump()
    workspace["file_paths"] = file_paths

    with pytest.raises(ValidationError):
        _request(workspace=workspace)


def test_readiness_readback_excludes_raw_execution_material() -> None:
    readback = RealGitWritePilotReadinessService().build_readiness(_request())
    body = json.dumps(readback.model_dump(mode="json"), sort_keys=True)

    for fragment in FORBIDDEN_READBACK_FRAGMENTS:
        assert fragment not in body


def test_readiness_service_and_route_static_boundaries() -> None:
    sources = [
        Path("app/services/real_git_write_pilot_readiness_service.py").read_text(
            encoding="utf-8",
        ),
        Path("app/api/routes/real_git_write_pilot.py").read_text(encoding="utf-8"),
    ]
    forbidden_fragments = [
        "import subprocess",
        "from subprocess",
        "os.popen",
        "asyncio.subprocess",
        "app.workers",
        "os.environ",
    ]

    for source in sources:
        for fragment in forbidden_fragments:
            assert fragment not in source
