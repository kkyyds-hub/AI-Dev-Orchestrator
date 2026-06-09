from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import api_router
from app.api.routes import git_write as git_write_route
from app.services.git_write_readback_service import GitWriteReadbackService


FORBIDDEN_RESPONSE_KEYS = {
    "command",
    "raw_command",
    "raw_args",
    "env",
    "env_vars",
    "api_key",
    "token_value",
    "auth_token",
    "secret",
    "password",
    "cwd",
    "raw_diff",
    "raw_output",
    "raw_error",
}


@pytest.fixture
def git_write_client() -> TestClient:
    app = FastAPI()
    app.include_router(api_router)
    service = GitWriteReadbackService()
    app.dependency_overrides[
        git_write_route.get_git_write_readback_service
    ] = lambda: service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def safe_payload(**overrides) -> dict:
    payload = {
        "intent_id": "intent-1",
        "workspace_id": "workspace-1",
        "repository_id": "repo-1",
        "project_id": "project-1",
        "task_id": "task-1",
        "run_id": "run-1",
        "requested_by": "user-1",
        "target_branch": "feature/git-write",
        "base_branch": "main",
        "file_paths": ["runtime/orchestrator/app/domain/git_write.py"],
        "changed_files": [
            {
                "path": "runtime/orchestrator/app/domain/git_write.py",
                "change_type": "modified",
                "additions": 5,
                "deletions": 1,
                "reviewed": True,
                "safe_summary": "Readback route update.",
            }
        ],
        "allowed_branches": ["feature/git-write"],
        "feature_flag_enabled": True,
        "diff_summary": "1 file changed with readback route update.",
        "commit_message": "Add GitWrite readback API",
    }
    payload.update(overrides)
    return payload


def create_intent(client: TestClient, **overrides) -> dict:
    response = client.post("/git-write/intents", json=safe_payload(**overrides))
    assert response.status_code == 201
    return response.json()


def assert_no_forbidden_keys(value) -> None:
    if isinstance(value, dict):
        assert FORBIDDEN_RESPONSE_KEYS.isdisjoint(value.keys())
        for nested in value.values():
            assert_no_forbidden_keys(nested)
    elif isinstance(value, list):
        for item in value:
            assert_no_forbidden_keys(item)


def gate(data: dict, gate_name: str) -> dict:
    checks = data["preview"]["safety_snapshot"]["gate_checks"]
    for check in checks:
        if check["gate_name"] == gate_name:
            return check
    raise AssertionError(f"missing gate {gate_name}")


def test_create_intent_returns_preview_ready_without_write_ready(
    git_write_client: TestClient,
) -> None:
    data = create_intent(git_write_client)

    assert data["preview"]["status"] == "ready"
    assert data["preview"]["safety_snapshot"]["preview_gates_passed"] is True
    assert data["preview"]["safety_snapshot"]["all_passed"] is False
    assert gate(data, "human_approval")["status"] == "pending"
    assert gate(data, "one_shot_token")["status"] == "pending"
    assert data["product_runtime_git_write_executed"] is False
    assert data["adapter_evidence"] is None
    assert data["rollback_plan"]["plan_id"] == "rollback-intent-1"
    assert_no_forbidden_keys(data)


@pytest.mark.parametrize(
    ("payload_overrides", "gate_name", "reason"),
    [
        (
            {"feature_flag_enabled": False},
            "feature_flag",
            "feature_flag_disabled",
        ),
        (
            {"allowed_branches": ["release/only"]},
            "target_branch_allowlist",
            "target_branch_not_allowed",
        ),
        (
            {"diff_text": "+ OPENAI_API_KEY=sk-real-value"},
            "secret_scan",
            "secret_detected",
        ),
        (
            {
                "changed_files": [
                    {
                        "path": "runtime/orchestrator/app/domain/git_write.py",
                        "change_type": "modified",
                        "additions": 5,
                        "deletions": 1,
                        "reviewed": False,
                        "safe_summary": "Readback route update.",
                    }
                ],
            },
            "reviewed_files",
            "unreviewed_files",
        ),
    ],
)
def test_create_intent_returns_blocked_preview_for_failed_gates(
    git_write_client: TestClient,
    payload_overrides: dict,
    gate_name: str,
    reason: str,
) -> None:
    data = create_intent(git_write_client, **payload_overrides)

    assert data["preview"]["status"] == "blocked"
    assert gate(data, gate_name)["status"] == "blocked"
    assert gate(data, gate_name)["block_reason"] == reason
    assert data["product_runtime_git_write_executed"] is False
    assert_no_forbidden_keys(data)
    assert "sk-real-value" not in str(data)
    assert "OPENAI_API_KEY" not in str(data)


def test_get_intent_reads_back_intent_preview_and_rollback_plan(
    git_write_client: TestClient,
) -> None:
    created = create_intent(git_write_client)

    response = git_write_client.get(
        f"/git-write/intents/{created['intent']['intent_id']}",
    )
    data = response.json()

    assert response.status_code == 200
    assert data["intent"]["intent_id"] == "intent-1"
    assert data["preview"]["preview_id"] == "preview-intent-1"
    assert data["rollback_plan"]["plan_id"] == "rollback-intent-1"
    assert data["product_runtime_git_write_executed"] is False


def test_approve_ready_preview_returns_safe_approval_readback(
    git_write_client: TestClient,
) -> None:
    created = create_intent(git_write_client)

    response = git_write_client.post(
        f"/git-write/intents/{created['intent']['intent_id']}/approve",
        json={"actor": "user-1", "approval_note": "reviewed readback"},
    )
    data = response.json()

    assert response.status_code == 200
    assert data["approval"]["intent_id"] == "intent-1"
    assert data["approval"]["one_shot_token"]["token_id"]
    assert data["approval"]["one_shot_token"]["token_hint"] == "approval readback hint"
    assert data["approval"]["one_shot_token"]["status"] == "pending"
    assert set(data["approval"]["one_shot_token"]) == {
        "token_id",
        "token_hint",
        "status",
        "expires_at",
    }
    assert "no commit or push has run" in data["approval_summary"]
    assert data["product_runtime_git_write_executed"] is False
    assert data["preview"]["safety_snapshot"]["all_passed"] is False
    assert_no_forbidden_keys(data)


def test_blocked_preview_cannot_be_approved(git_write_client: TestClient) -> None:
    created = create_intent(git_write_client, feature_flag_enabled=False)

    response = git_write_client.post(
        f"/git-write/intents/{created['intent']['intent_id']}/approve",
        json={"actor": "user-1"},
    )

    assert response.status_code == 409
    assert "preview is not ready" in response.json()["detail"]


def test_audit_readback_records_safe_timeline(git_write_client: TestClient) -> None:
    created = create_intent(git_write_client)

    response = git_write_client.get(
        f"/git-write/intents/{created['intent']['intent_id']}/audit",
    )
    create_events = response.json()

    assert response.status_code == 200
    assert [event["event_type"] for event in create_events] == [
        "git_write.intent_created",
        "git_write.preview_generated",
    ]
    assert_no_forbidden_keys(create_events)

    approve_response = git_write_client.post(
        f"/git-write/intents/{created['intent']['intent_id']}/approve",
        json={"actor": "user-1"},
    )
    assert approve_response.status_code == 200

    audit_response = git_write_client.get(
        f"/git-write/intents/{created['intent']['intent_id']}/audit",
    )
    audit_events = audit_response.json()

    assert [event["event_type"] for event in audit_events] == [
        "git_write.intent_created",
        "git_write.preview_generated",
        "git_write.approval_recorded",
    ]
    assert_no_forbidden_keys(audit_events)


def test_unknown_intent_returns_404(git_write_client: TestClient) -> None:
    response = git_write_client.get("/git-write/intents/missing")

    assert response.status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/git-write/execute",
        "/git-write/commit",
        "/git-write/push",
        "/git-write/pr",
        "/git-write/merge",
        "/git-write/intents/intent-1/execute",
        "/git-write/intents/intent-1/commit",
        "/git-write/intents/intent-1/push",
        "/git-write/intents/intent-1/pr",
        "/git-write/intents/intent-1/merge",
    ],
)
def test_git_write_api_has_no_write_endpoint(
    git_write_client: TestClient,
    path: str,
) -> None:
    response = git_write_client.post(path, json={})

    assert response.status_code == 404


def test_git_write_api_files_have_no_forbidden_runtime_operations() -> None:
    sources = [
        Path("app/services/git_write_readback_service.py").read_text(encoding="utf-8"),
        Path("app/api/routes/git_write.py").read_text(encoding="utf-8"),
    ]
    forbidden_fragments = [
        "subprocess",
        "os.popen",
        "asyncio.subprocess",
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
        "/execute",
        "/commit",
        "/push",
        "/pr",
        "/merge",
        "/checkout",
        "/reset",
        "/rebase",
        "/stash",
        "/tag",
        "agent-orchestrator",
        "project-explore-one",
        "@aoagents",
        "workspace-worktree",
    ]

    for source in sources:
        for fragment in forbidden_fragments:
            assert fragment not in source
