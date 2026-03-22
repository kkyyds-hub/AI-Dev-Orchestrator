"""V4-A Day01 smoke checks for repository binding and path boundaries."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
from typing import Any
from uuid import uuid4


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_ROOT = RUNTIME_ROOT / "tmp" / "v4-day01-repository-binding-smoke"
SMOKE_RUNTIME_DATA_DIR = SMOKE_ROOT / "runtime-data"
SMOKE_DB_PATH = SMOKE_RUNTIME_DATA_DIR / "db" / "orchestrator.db"
SMOKE_ALLOWED_WORKSPACE_ROOT = SMOKE_ROOT / "allowed-workspaces"
SMOKE_BOUND_REPOSITORY_ROOT = SMOKE_ALLOWED_WORKSPACE_ROOT / "bound-repository"
SMOKE_OUTSIDE_WORKSPACE_ROOT = SMOKE_ROOT / "outside-workspaces"
SMOKE_OUTSIDE_REPOSITORY_ROOT = SMOKE_OUTSIDE_WORKSPACE_ROOT / "outside-repository"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _prepare_env() -> None:
    if SMOKE_ROOT.exists():
        shutil.rmtree(SMOKE_ROOT)

    SMOKE_BOUND_REPOSITORY_ROOT.mkdir(parents=True, exist_ok=True)
    SMOKE_OUTSIDE_REPOSITORY_ROOT.mkdir(parents=True, exist_ok=True)
    (SMOKE_BOUND_REPOSITORY_ROOT / ".git").mkdir(parents=True, exist_ok=True)
    (SMOKE_OUTSIDE_REPOSITORY_ROOT / ".git").mkdir(parents=True, exist_ok=True)
    (SMOKE_BOUND_REPOSITORY_ROOT / "src").mkdir(parents=True, exist_ok=True)
    (SMOKE_OUTSIDE_REPOSITORY_ROOT / "src").mkdir(parents=True, exist_ok=True)
    (SMOKE_BOUND_REPOSITORY_ROOT / "README.md").write_text(
        "# Bound repo\n",
        encoding="utf-8",
    )
    (SMOKE_OUTSIDE_REPOSITORY_ROOT / "README.md").write_text(
        "# Outside repo\n",
        encoding="utf-8",
    )

    os.environ["RUNTIME_DATA_DIR"] = str(SMOKE_RUNTIME_DATA_DIR)
    os.environ["REPOSITORY_WORKSPACE_ROOT_DIR"] = str(SMOKE_ALLOWED_WORKSPACE_ROOT)
    os.environ["DAILY_BUDGET_USD"] = "0.05"
    os.environ["SESSION_BUDGET_USD"] = "0.20"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"


def _seed_legacy_schema() -> dict[str, str]:
    """Create one pre-Day01 schema snapshot without repository bindings."""

    SMOKE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(SMOKE_DB_PATH)
    try:
        project_id = uuid4().hex
        task_id = uuid4().hex
        deliverable_id = uuid4().hex
        now = datetime.now(timezone.utc).isoformat()

        connection.executescript(
            """
            CREATE TABLE projects (
                id CHAR(32) PRIMARY KEY NOT NULL,
                name VARCHAR(200) NOT NULL,
                summary TEXT NOT NULL,
                status VARCHAR(20) NOT NULL,
                stage VARCHAR(20) NOT NULL,
                sop_template_code VARCHAR(100),
                stage_history_json TEXT NOT NULL DEFAULT '[]',
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );

            CREATE TABLE tasks (
                id CHAR(32) PRIMARY KEY NOT NULL,
                project_id CHAR(32),
                title VARCHAR(200) NOT NULL,
                status VARCHAR(20) NOT NULL,
                priority VARCHAR(20) NOT NULL,
                input_summary TEXT NOT NULL,
                acceptance_criteria TEXT NOT NULL DEFAULT '[]',
                depends_on_task_ids TEXT NOT NULL DEFAULT '[]',
                risk_level VARCHAR(20) NOT NULL DEFAULT 'normal',
                owner_role_code TEXT,
                upstream_role_code TEXT,
                downstream_role_code TEXT,
                human_status VARCHAR(20) NOT NULL DEFAULT 'none',
                paused_reason TEXT,
                source_draft_id VARCHAR(50),
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE SET NULL
            );

            CREATE TABLE deliverables (
                id CHAR(32) PRIMARY KEY NOT NULL,
                project_id CHAR(32) NOT NULL,
                type VARCHAR(50) NOT NULL,
                title VARCHAR(200) NOT NULL,
                stage VARCHAR(20) NOT NULL,
                created_by_role_code VARCHAR(50) NOT NULL,
                current_version_number INTEGER NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            """
        )

        connection.execute(
            """
            INSERT INTO projects (
                id, name, summary, status, stage, sop_template_code,
                stage_history_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                "legacy-project",
                "Legacy project preserved across Day01 repository binding upgrade.",
                "active",
                "intake",
                None,
                json.dumps([]),
                now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO tasks (
                id, project_id, title, status, priority, input_summary,
                acceptance_criteria, depends_on_task_ids, risk_level,
                owner_role_code, upstream_role_code, downstream_role_code,
                human_status, paused_reason, source_draft_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                project_id,
                "legacy-task",
                "pending",
                "normal",
                "Legacy task should survive the Day01 schema upgrade.",
                json.dumps([]),
                json.dumps([]),
                "normal",
                None,
                None,
                None,
                "none",
                None,
                None,
                now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO deliverables (
                id, project_id, type, title, stage, created_by_role_code,
                current_version_number, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                deliverable_id,
                project_id,
                "prd",
                "legacy-deliverable",
                "intake",
                "product_manager",
                1,
                now,
                now,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    return {
        "legacy_project_id": project_id,
        "legacy_task_id": task_id,
        "legacy_deliverable_id": deliverable_id,
    }


def _request_json(
    client,
    method: str,
    path: str,
    *,
    expected_status: int,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = client.request(method=method, url=path, json=json_body)
    if response.status_code != expected_status:
        raise AssertionError(
            f"{method} {path} expected {expected_status}, got {response.status_code}: "
            f"{response.text}"
        )

    data = response.json()
    if not isinstance(data, dict):
        raise AssertionError(f"{method} {path} did not return one JSON object.")
    return data


def _request_error(
    client,
    method: str,
    path: str,
    *,
    expected_status: int,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = client.request(method=method, url=path, json=json_body)
    if response.status_code != expected_status:
        raise AssertionError(
            f"{method} {path} expected {expected_status}, got {response.status_code}: "
            f"{response.text}"
        )

    data = response.json()
    if not isinstance(data, dict):
        raise AssertionError(f"{method} {path} did not return one JSON object.")
    return data


def main() -> None:
    """Run migration and API-level smoke checks for V4 Day01."""

    _prepare_env()
    _seed_legacy_schema()

    from fastapi.testclient import TestClient

    from app.core.db import init_database
    from app.main import app

    init_database()

    connection = sqlite3.connect(SMOKE_DB_PATH)
    try:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        legacy_project_count = connection.execute(
            "SELECT COUNT(*) FROM projects"
        ).fetchone()[0]
        legacy_task_count = connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        legacy_deliverable_count = connection.execute(
            "SELECT COUNT(*) FROM deliverables"
        ).fetchone()[0]
        repository_binding_count = connection.execute(
            "SELECT COUNT(*) FROM repository_workspaces"
        ).fetchone()[0]
    finally:
        connection.close()

    _assert(
        "repository_workspaces" in table_names,
        "Day01 should create the repository_workspaces table.",
    )
    _assert(
        legacy_project_count == 1,
        "Legacy project rows should survive the Day01 schema upgrade.",
    )
    _assert(
        legacy_task_count == 1,
        "Legacy task rows should survive the Day01 schema upgrade.",
    )
    _assert(
        legacy_deliverable_count == 1,
        "Legacy deliverable rows should survive the Day01 schema upgrade.",
    )
    _assert(
        repository_binding_count == 0,
        "Legacy schema should start without repository bindings.",
    )

    with TestClient(app) as client:
        project = _request_json(
            client,
            "POST",
            "/projects",
            expected_status=201,
            json_body={
                "name": "V4 Day01 smoke project",
                "summary": "Validate repository binding, retrieval, unbinding and path boundaries.",
            },
        )

        binding_request = {
            "root_path": str(SMOKE_BOUND_REPOSITORY_ROOT.resolve()),
            "display_name": "Smoke Bound Repository",
            "access_mode": "read_only",
            "default_base_branch": "main",
            "ignore_rule_summary": [".git", "node_modules", "dist"],
        }
        repository_binding = _request_json(
            client,
            "PUT",
            f"/repositories/projects/{project['id']}",
            expected_status=200,
            json_body=binding_request,
        )
        _assert(
            repository_binding["root_path"] == binding_request["root_path"],
            "Repository binding should persist the normalized repository root path.",
        )
        _assert(
            repository_binding["display_name"] == binding_request["display_name"],
            "Repository binding should persist the display name.",
        )
        _assert(
            repository_binding["access_mode"] == "read_only",
            "Repository binding should expose the Day01 read_only access mode.",
        )
        _assert(
            repository_binding["default_base_branch"] == "main",
            "Repository binding should persist the default baseline branch.",
        )
        _assert(
            repository_binding["ignore_rule_summary"] == [".git", "node_modules", "dist"],
            "Repository binding should persist the ignore-rule summary.",
        )
        _assert(
            repository_binding["allowed_workspace_root"]
            == str(SMOKE_ALLOWED_WORKSPACE_ROOT.resolve()),
            "Repository binding should expose the configured allowed workspace root.",
        )

        fetched_repository_binding = _request_json(
            client,
            "GET",
            f"/repositories/projects/{project['id']}",
            expected_status=200,
        )
        _assert(
            fetched_repository_binding == repository_binding,
            "Repository GET should match the persisted binding payload.",
        )

        project_detail = _request_json(
            client,
            "GET",
            f"/projects/{project['id']}",
            expected_status=200,
        )
        _assert(
            project_detail["repository_workspace"] == repository_binding,
            "Project detail should expose the same repository binding payload as the repository API.",
        )

        missing_path_response = _request_error(
            client,
            "PUT",
            f"/repositories/projects/{project['id']}",
            expected_status=422,
            json_body={
                "root_path": str((SMOKE_ALLOWED_WORKSPACE_ROOT / "missing-repository").resolve()),
                "display_name": "Missing repo",
                "access_mode": "read_only",
                "default_base_branch": "main",
                "ignore_rule_summary": [],
            },
        )
        _assert(
            "does not exist" in missing_path_response["detail"],
            "Non-existent repository paths should be rejected by the path boundary guard.",
        )

        outside_boundary_response = _request_error(
            client,
            "PUT",
            f"/repositories/projects/{project['id']}",
            expected_status=422,
            json_body={
                "root_path": str(SMOKE_OUTSIDE_REPOSITORY_ROOT.resolve()),
                "display_name": "Outside repo",
                "access_mode": "read_only",
                "default_base_branch": "main",
                "ignore_rule_summary": [],
            },
        )
        _assert(
            "allowed workspace root" in outside_boundary_response["detail"],
            "Repository paths outside the configured workspace boundary should be rejected.",
        )

        removed_repository_binding = _request_json(
            client,
            "DELETE",
            f"/repositories/projects/{project['id']}",
            expected_status=200,
        )
        _assert(
            removed_repository_binding == repository_binding,
            "Repository DELETE should return the removed binding payload.",
        )

        _request_error(
            client,
            "GET",
            f"/repositories/projects/{project['id']}",
            expected_status=404,
        )
        project_detail_after_unbind = _request_json(
            client,
            "GET",
            f"/projects/{project['id']}",
            expected_status=200,
        )
        _assert(
            project_detail_after_unbind["repository_workspace"] is None,
            "Project detail should clear the repository binding after unbinding.",
        )

    connection = sqlite3.connect(SMOKE_DB_PATH)
    try:
        final_repository_binding_count = connection.execute(
            "SELECT COUNT(*) FROM repository_workspaces"
        ).fetchone()[0]
    finally:
        connection.close()

    _assert(
        final_repository_binding_count == 0,
        "Repository bindings should be fully removed after the Day01 unbind smoke step.",
    )
    print("V4 Day01 repository binding smoke passed.")


if __name__ == "__main__":
    main()
