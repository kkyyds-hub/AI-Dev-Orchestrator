from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import api_router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(api_router)
    return TestClient(app)


def test_evidence_to_agent_dry_run_api_returns_safe_summary() -> None:
    with _client() as client:
        response = client.post(
            "/project-director/evidence-to-agent/dry-run",
            json={"user_goal": "P11-A expose evidence-to-agent dry-run API"},
        )

    assert response.status_code == 200
    summary = response.json()
    assert summary["dry_run_status"] == "passed"
    assert summary["evidence_pack_created"] is True
    assert summary["task_composer_consumed_evidence"] is True
    assert summary["composed_tasks_count"] > 0
    assert summary["programmer_assignment_created"] is True
    assert summary["reviewer_assignment_created"] is True
    assert summary["reviewer_readonly"] is True
    assert summary["director_permanent_executor"] is False
    assert summary["native_executor_started"] is False
    assert summary["codex_started"] is False
    assert summary["claude_code_started"] is False
    assert summary["worker_started"] is False
    assert summary["real_task_created"] is False
    assert summary["product_runtime_git_write_allowed"] is False
    assert summary["frontend_required"] is False
    assert summary["ai_project_director_total_loop"] == "Partial"
    assert summary["blocked_reasons"] == []

    payload = json.dumps(summary, ensure_ascii=False).lower()
    for forbidden in (
        "api_key",
        "token",
        "secret",
        "pid",
        "raw command",
        "raw stdout",
        "raw stderr",
    ):
        assert forbidden not in payload


def test_evidence_to_agent_dry_run_api_rejects_empty_goal() -> None:
    with _client() as client:
        response = client.post(
            "/project-director/evidence-to-agent/dry-run",
            json={"user_goal": "   "},
        )

    assert response.status_code == 422
