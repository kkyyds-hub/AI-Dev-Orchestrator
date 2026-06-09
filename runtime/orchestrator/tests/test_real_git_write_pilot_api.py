from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import api_router
from app.api.routes import real_git_write_pilot as pilot_route
from app.services.real_git_write_pilot_approval_service import (
    RealGitWritePilotApprovalReadbackService,
)
from app.services.real_git_write_pilot_dry_run_plan_service import (
    RealGitWritePilotDryRunPlanService,
)
from app.services.real_git_write_pilot_preview_service import (
    RealGitWritePilotPreviewRequest,
    RealGitWritePilotPreviewService,
)
from app.services.real_git_write_pilot_readiness_service import (
    RealGitWritePilotReadinessRequest,
    RealGitWritePilotReadinessService,
)


NOW = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(minutes=5)
BASE_COMMIT = "60193910875933d8582737a7d8991cd3bf4c38e1"

FORBIDDEN_RESPONSE_KEYS = {
    "command",
    "raw_command",
    "raw_args",
    "cwd",
    "env",
    "env_vars",
    "token_value",
    "api_key",
    "secret",
    "raw_diff",
    "subprocess_output",
    "error_output",
}


@pytest.fixture
def pilot_client() -> TestClient:
    app = FastAPI()
    app.include_router(api_router)
    service = RealGitWritePilotPreviewService()
    readiness_service = RealGitWritePilotReadinessService()
    dry_run_plan_service = RealGitWritePilotDryRunPlanService()
    approval_readback_service = RealGitWritePilotApprovalReadbackService()
    app.dependency_overrides[
        pilot_route.get_real_git_write_pilot_preview_service
    ] = lambda: service
    app.dependency_overrides[
        pilot_route.get_real_git_write_pilot_readiness_service
    ] = lambda: readiness_service
    app.dependency_overrides[
        pilot_route.get_real_git_write_pilot_dry_run_plan_service
    ] = lambda: dry_run_plan_service
    app.dependency_overrides[
        pilot_route.get_real_git_write_pilot_approval_readback_service
    ] = lambda: approval_readback_service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _payload(**overrides: object) -> dict:
    payload = {
        "pilot_id": "pilot-1",
        "project_id": "project-1",
        "run_id": "run-1",
        "executor_id": "codex",
        "workspace_id": "workspace-1",
        "repository_id": "repo-1",
        "base_commit": BASE_COMMIT,
        "target_branch": "ai/gitwrite-pilot/2026-06-09-doc-only",
        "file_paths": ["docs/product/pilot.md"],
        "requested_by": "user-1",
        "requested_at": NOW.isoformat(),
        "expires_at": LATER.isoformat(),
        "feature_flags": {
            "p9_real_executor_launch_enabled": True,
            "product_runtime_git_write_enabled": True,
            "real_git_write_pilot_enabled": True,
        },
        "gate_inputs": {
            "executor_ready": True,
            "workspace_bound": True,
            "target_branch_allowed": True,
            "diff_preview_ready": True,
            "secret_scan_passed": True,
            "human_approved": False,
            "one_shot_token_issued": False,
            "budget_within_limit": True,
            "timeout_configured": True,
            "rollback_plan_ready": True,
            "append_only_audit_ready": True,
            "force_push_requested": False,
            "auto_pr_requested": False,
            "auto_merge_requested": False,
        },
        "diff_summary": "single doc-only markdown file candidate",
        "rollback_summary": "rollback remains a manual contract",
    }
    payload.update(overrides)
    return payload


def _readiness_payload(**overrides: object) -> dict:
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
            "checked_at": NOW.isoformat(),
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
            "checked_at": NOW.isoformat(),
        },
        "requested_by": "user-1",
        "requested_at": NOW.isoformat(),
    }
    payload.update(overrides)
    return payload


def _dry_run_plan_payload(**overrides: object) -> dict:
    preview = RealGitWritePilotPreviewService().build_preview(
        RealGitWritePilotPreviewRequest(**_payload()),
    )
    readiness = RealGitWritePilotReadinessService().build_readiness(
        RealGitWritePilotReadinessRequest(**_readiness_payload()),
    )
    payload = {
        "pilot_id": "pilot-1",
        "preview": preview.model_dump(mode="json"),
        "readiness": readiness.model_dump(mode="json"),
        "requested_by": "user-1",
        "requested_at": NOW.isoformat(),
    }
    payload.update(overrides)
    return payload


def _approval_readback_payload(**overrides: object) -> dict:
    dry_run_plan_response = RealGitWritePilotDryRunPlanService().build_plan(
        pilot_route.RealGitWritePilotDryRunPlanRequest(**_dry_run_plan_payload()),
    )
    requested_at = datetime.now(timezone.utc)
    expires_at = requested_at + timedelta(minutes=30)
    payload = {
        "pilot_id": "pilot-1",
        "dry_run_plan": dry_run_plan_response.model_dump(mode="json"),
        "approved_by": "user-1",
        "approval_phrase": "我确认此次试点写入",
        "approved_scope_summary": "approval covers the dry-run doc-only pilot scope",
        "requested_at": requested_at.isoformat(),
        "expires_at": expires_at.isoformat(),
    }
    payload.update(overrides)
    return payload


def _assert_no_forbidden_keys(value) -> None:
    if isinstance(value, dict):
        assert FORBIDDEN_RESPONSE_KEYS.isdisjoint(value.keys())
        for nested in value.values():
            _assert_no_forbidden_keys(nested)
    elif isinstance(value, list):
        for item in value:
            _assert_no_forbidden_keys(item)


def test_real_git_write_pilot_preview_endpoint_returns_preview_only_response(
    pilot_client: TestClient,
) -> None:
    response = pilot_client.post("/real-git-write-pilot/preview", json=_payload())
    data = response.json()

    assert response.status_code == 200
    assert data["pilot_id"] == "pilot-1"
    assert data["status"] == "approval_required"
    assert data["product_runtime_git_write_executed"] is False
    assert data["real_executor_started"] is False
    assert data["gate_snapshot"]["all_passed"] is False
    assert data["command_plan"]["safe_steps"] == [
        "validate pilot branch",
        "prepare doc-only file candidate",
        "prepare local commit candidate",
        "prepare rollback plan",
    ]
    assert data["command_plan"]["forbidden_operations"] == [
        "main write",
        "force push",
        "auto PR",
        "auto merge",
        "raw shell execution",
    ]
    assert data["rollback_plan"]["pilot_commit_id"] is None
    _assert_no_forbidden_keys(data)


def test_real_git_write_pilot_preview_endpoint_default_flags_block_full_gate(
    pilot_client: TestClient,
) -> None:
    payload = _payload(feature_flags={})

    response = pilot_client.post("/real-git-write-pilot/preview", json=payload)
    data = response.json()

    assert response.status_code == 200
    assert data["status"] == "blocked"
    assert "feature_flag_disabled" in data["gate_snapshot"]["blocking_reasons"]
    assert data["product_runtime_git_write_executed"] is False
    assert data["real_executor_started"] is False


def test_real_git_write_pilot_readiness_endpoint_returns_readback(
    pilot_client: TestClient,
) -> None:
    response = pilot_client.post(
        "/real-git-write-pilot/readiness",
        json=_readiness_payload(),
    )
    data = response.json()

    assert response.status_code == 200
    assert data["pilot_id"] == "pilot-1"
    assert data["executor_readiness"]["ready"] is True
    assert data["workspace_binding"]["bound"] is True
    assert data["ready_for_preview"] is True
    assert data["ready_for_execution"] is False
    assert data["product_runtime_git_write_executed"] is False
    assert data["real_executor_started"] is False
    assert [gate["gate_name"] for gate in data["gate_checks"]] == [
        "executor_readiness",
        "workspace_binding",
        "target_branch_allowlist",
        "file_scope",
    ]
    _assert_no_forbidden_keys(data)


def test_real_git_write_pilot_readiness_endpoint_blocks_unsafe_workspace(
    pilot_client: TestClient,
) -> None:
    payload = _readiness_payload()
    payload["workspace"] = {
        **payload["workspace"],
        "safe_path_confirmed": False,
    }

    response = pilot_client.post("/real-git-write-pilot/readiness", json=payload)
    data = response.json()

    assert response.status_code == 200
    assert data["ready_for_preview"] is False
    assert data["workspace_binding"]["bound"] is False
    assert "workspace_not_bound" in [
        gate["block_reason"]
        for gate in data["gate_checks"]
        if gate["block_reason"] is not None
    ]
    assert data["ready_for_execution"] is False


@pytest.mark.parametrize(
    "target_branch",
    ["main", "master", "release", "production", "staging", "gh-pages"],
)
def test_real_git_write_pilot_readiness_endpoint_blocks_protected_branches(
    pilot_client: TestClient,
    target_branch: str,
) -> None:
    payload = _readiness_payload()
    payload["workspace"] = {**payload["workspace"], "target_branch": target_branch}

    response = pilot_client.post("/real-git-write-pilot/readiness", json=payload)
    data = response.json()

    assert response.status_code == 200
    assert data["ready_for_preview"] is False
    assert "main_branch_blocked" in [
        gate["block_reason"]
        for gate in data["gate_checks"]
        if gate["block_reason"] is not None
    ]


def test_real_git_write_pilot_readiness_endpoint_blocks_non_docs_markdown_file(
    pilot_client: TestClient,
) -> None:
    payload = _readiness_payload()
    payload["workspace"] = {
        **payload["workspace"],
        "file_paths": ["runtime/orchestrator/app/main.py"],
    }

    response = pilot_client.post("/real-git-write-pilot/readiness", json=payload)
    data = response.json()

    assert response.status_code == 200
    assert data["ready_for_preview"] is False
    assert "file_scope_not_allowed" in [
        gate["block_reason"]
        for gate in data["gate_checks"]
        if gate["block_reason"] is not None
    ]


def test_real_git_write_pilot_dry_run_plan_endpoint_returns_readback(
    pilot_client: TestClient,
) -> None:
    response = pilot_client.post(
        "/real-git-write-pilot/dry-run-plan",
        json=_dry_run_plan_payload(),
    )
    data = response.json()

    assert response.status_code == 200
    assert data["pilot_id"] == "pilot-1"
    assert data["readiness_ready_for_preview"] is True
    assert data["preview_status"] == "approval_required"
    assert data["dry_run_ready"] is True
    assert data["ready_for_execution"] is False
    assert data["product_runtime_git_write_executed"] is False
    assert data["real_executor_started"] is False
    assert [step["step_order"] for step in data["semantic_steps"]] == list(range(1, 12))
    assert data["forbidden_operations"] == [
        "raw shell execution",
        "direct main write",
        "git force push",
        "automatic PR creation",
        "automatic merge",
        "branch delete",
        "reset hard",
        "tag creation",
        "stash operation",
    ]
    _assert_no_forbidden_keys(data)


def test_real_git_write_pilot_dry_run_plan_endpoint_blocks_when_readiness_not_ready(
    pilot_client: TestClient,
) -> None:
    readiness = RealGitWritePilotReadinessService().build_readiness(
        RealGitWritePilotReadinessRequest(
            **_readiness_payload(
                executor={
                    "executor_id": "codex",
                    "executor_kind": "codex",
                    "configured": True,
                    "authenticated": True,
                    "available": False,
                    "model_or_profile": "gpt-5-codex",
                    "safe_summary": "executor profile is unavailable",
                    "checked_at": NOW.isoformat(),
                },
            ),
        ),
    )
    response = pilot_client.post(
        "/real-git-write-pilot/dry-run-plan",
        json=_dry_run_plan_payload(readiness=readiness.model_dump(mode="json")),
    )
    data = response.json()

    assert response.status_code == 200
    assert data["readiness_ready_for_preview"] is False
    assert data["dry_run_ready"] is False
    assert data["ready_for_execution"] is False


def test_real_git_write_pilot_approval_readback_endpoint_returns_readback(
    pilot_client: TestClient,
) -> None:
    response = pilot_client.post(
        "/real-git-write-pilot/approval-readback",
        json=_approval_readback_payload(),
    )
    data = response.json()

    assert response.status_code == 200
    assert data["approval_id"] == "pilot-approval-readback-pilot-1"
    assert data["pilot_id"] == "pilot-1"
    assert data["decision"] == "approved"
    assert data["approved_by"] == "user-1"
    assert data["approval_phrase_matched"] is True
    assert data["dry_run_ready"] is True
    assert data["ready_for_execution"] is False
    assert data["one_shot_token_issued"] is False
    assert data["product_runtime_git_write_executed"] is False
    assert data["real_executor_started"] is False
    assert data["safe_summary"]
    assert data["audit_event_summaries"]
    assert data["created_at"]
    assert data["expires_at"]
    _assert_no_forbidden_keys(data)


def test_real_git_write_pilot_approval_readback_endpoint_keeps_broad_phrase_pending(
    pilot_client: TestClient,
) -> None:
    response = pilot_client.post(
        "/real-git-write-pilot/approval-readback",
        json=_approval_readback_payload(approval_phrase="approve"),
    )
    data = response.json()

    assert response.status_code == 200
    assert data["decision"] == "pending"
    assert data["approval_phrase_matched"] is False
    assert data["ready_for_execution"] is False


@pytest.mark.parametrize(
    "target_branch",
    ["main", "master", "release", "production", "staging", "gh-pages"],
)
def test_real_git_write_pilot_preview_endpoint_rejects_protected_branches(
    pilot_client: TestClient,
    target_branch: str,
) -> None:
    response = pilot_client.post(
        "/real-git-write-pilot/preview",
        json=_payload(target_branch=target_branch),
    )

    assert response.status_code == 422


def test_real_git_write_pilot_preview_endpoint_rejects_non_docs_markdown_file(
    pilot_client: TestClient,
) -> None:
    response = pilot_client.post(
        "/real-git-write-pilot/preview",
        json=_payload(file_paths=["runtime/orchestrator/app/main.py"]),
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "path",
    [
        "/real-git-write-pilot/execute",
        "/real-git-write-pilot/commit",
        "/real-git-write-pilot/push",
        "/real-git-write-pilot/pr",
        "/real-git-write-pilot/merge",
        "/real-git-write-pilot/checkout",
        "/real-git-write-pilot/reset",
        "/real-git-write-pilot/rebase",
        "/real-git-write-pilot/stash",
        "/real-git-write-pilot/tag",
    ],
)
def test_real_git_write_pilot_api_has_no_write_endpoint(
    pilot_client: TestClient,
    path: str,
) -> None:
    response = pilot_client.post(path, json={})

    assert response.status_code == 404


def test_real_git_write_pilot_api_files_have_preview_only_boundaries() -> None:
    sources = [
        Path("app/services/real_git_write_pilot_preview_service.py").read_text(
            encoding="utf-8",
        ),
        Path("app/services/real_git_write_pilot_readiness_service.py").read_text(
            encoding="utf-8",
        ),
        Path("app/services/real_git_write_pilot_dry_run_plan_service.py").read_text(
            encoding="utf-8",
        ),
        Path("app/services/real_git_write_pilot_approval_service.py").read_text(
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
        "git add ",
        "git commit ",
        "git push ",
        "git merge ",
        "git reset ",
        "git checkout ",
        "git switch ",
        "git rebase ",
        "git stash ",
        "git tag ",
        "/Users/kk/project explore/agent-orchestrator",
        "@aoagents/ao-core",
        "workspace-worktree",
        "CleanupStack",
        "Zod",
        "tmux",
    ]

    for source in sources:
        for fragment in forbidden_fragments:
            assert fragment not in source
