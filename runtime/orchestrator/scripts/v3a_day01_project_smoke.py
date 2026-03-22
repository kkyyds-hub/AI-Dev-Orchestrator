"""V3-A Day01 smoke checks for project modeling and lifecycle basics."""

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
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v3-day01-project-smoke"
SMOKE_DB_PATH = SMOKE_RUNTIME_DATA_DIR / "db" / "orchestrator.db"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _prepare_env() -> None:
    if SMOKE_RUNTIME_DATA_DIR.exists():
        shutil.rmtree(SMOKE_RUNTIME_DATA_DIR)
    SMOKE_RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)

    os.environ["RUNTIME_DATA_DIR"] = str(SMOKE_RUNTIME_DATA_DIR)
    os.environ["DAILY_BUDGET_USD"] = "0.05"
    os.environ["SESSION_BUDGET_USD"] = "0.20"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"


def _seed_legacy_schema() -> dict[str, str]:
    """Create a pre-Day01 schema snapshot without `projects` / `tasks.project_id`."""

    SMOKE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(SMOKE_DB_PATH)
    try:
        task_id = uuid4().hex
        run_id = uuid4().hex
        now = datetime.now(timezone.utc).isoformat()

        connection.executescript(
            """
            CREATE TABLE tasks (
                id CHAR(32) PRIMARY KEY NOT NULL,
                title VARCHAR(200) NOT NULL,
                status VARCHAR(20) NOT NULL,
                priority VARCHAR(20) NOT NULL,
                input_summary TEXT NOT NULL,
                acceptance_criteria TEXT NOT NULL DEFAULT '[]',
                depends_on_task_ids TEXT NOT NULL DEFAULT '[]',
                risk_level VARCHAR(20) NOT NULL DEFAULT 'normal',
                human_status VARCHAR(20) NOT NULL DEFAULT 'none',
                paused_reason TEXT,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );

            CREATE TABLE runs (
                id CHAR(32) PRIMARY KEY NOT NULL,
                task_id CHAR(32) NOT NULL,
                status VARCHAR(20) NOT NULL,
                model_name VARCHAR(100),
                route_reason TEXT,
                routing_score FLOAT,
                routing_score_breakdown TEXT,
                started_at DATETIME,
                finished_at DATETIME,
                result_summary TEXT,
                prompt_tokens INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                estimated_cost FLOAT NOT NULL DEFAULT 0.0,
                log_path TEXT,
                verification_mode TEXT,
                verification_template TEXT,
                verification_command TEXT,
                verification_summary TEXT,
                failure_category TEXT,
                quality_gate_passed INTEGER,
                created_at DATETIME NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            );
            """
        )

        connection.execute(
            """
            INSERT INTO tasks (
                id, title, status, priority, input_summary, acceptance_criteria,
                depends_on_task_ids, risk_level, human_status, paused_reason,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                "legacy-task",
                "pending",
                "normal",
                "Legacy task preserved across Day01 migration.",
                "[]",
                "[]",
                "normal",
                "none",
                None,
                now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO runs (
                id, task_id, status, model_name, route_reason, routing_score,
                routing_score_breakdown, started_at, finished_at, result_summary,
                prompt_tokens, completion_tokens, estimated_cost, log_path,
                verification_mode, verification_template, verification_command,
                verification_summary, failure_category, quality_gate_passed, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                task_id,
                "queued",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                0,
                0,
                0.0,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                now,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    return {"legacy_task_id": task_id, "legacy_run_id": run_id}


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


def _request_list(
    client,
    method: str,
    path: str,
    *,
    expected_status: int,
) -> list[dict[str, Any]]:
    response = client.request(method=method, url=path)
    if response.status_code != expected_status:
        raise AssertionError(
            f"{method} {path} expected {expected_status}, got {response.status_code}: "
            f"{response.text}"
        )

    data = response.json()
    if not isinstance(data, list):
        raise AssertionError(f"{method} {path} did not return one JSON list.")
    return data


def main() -> None:
    """Run migration and API-level smoke checks for Day01."""

    _prepare_env()
    legacy_ids = _seed_legacy_schema()

    from fastapi.testclient import TestClient

    from app.core.db import init_database
    from app.main import app

    init_database()

    connection = sqlite3.connect(SMOKE_DB_PATH)
    try:
        task_columns = [
            row[1] for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
        ]
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        legacy_task_count = connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        legacy_run_count = connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    finally:
        connection.close()

    _assert("projects" in table_names, "Day01 should create the projects table.")
    _assert("project_id" in task_columns, "Day01 migration should add tasks.project_id.")
    _assert(legacy_task_count == 1, "Legacy task rows should survive Day01 migration.")
    _assert(legacy_run_count == 1, "Legacy run rows should survive Day01 migration.")

    with TestClient(app) as client:
        project = _request_json(
            client,
            "POST",
            "/projects",
            expected_status=201,
            json_body={
                "name": "V3 Day01 smoke project",
                "summary": "Validate project creation, task linking and aggregate stats.",
            },
        )
        pending_task = _request_json(
            client,
            "POST",
            "/tasks",
            expected_status=201,
            json_body={
                "project_id": project["id"],
                "title": "pending-task",
                "input_summary": "Stay pending for aggregate verification.",
            },
        )
        waiting_human_task = _request_json(
            client,
            "POST",
            "/tasks",
            expected_status=201,
            json_body={
                "project_id": project["id"],
                "title": "waiting-human-task",
                "input_summary": "Start in waiting_human.",
                "human_status": "requested",
            },
        )
        paused_task = _request_json(
            client,
            "POST",
            "/tasks",
            expected_status=201,
            json_body={
                "project_id": project["id"],
                "title": "paused-task",
                "input_summary": "Start in paused.",
                "paused_reason": "Waiting for business confirmation.",
            },
        )
        project_detail = _request_json(
            client,
            "GET",
            f"/projects/{project['id']}",
            expected_status=200,
        )
        project_list = _request_list(
            client,
            "GET",
            "/projects",
            expected_status=200,
        )
        invalid_task_response = client.post(
            "/tasks",
            json={
                "project_id": str(uuid4()),
                "title": "invalid-project-task",
                "input_summary": "This should fail because the project does not exist.",
            },
        )

    task_stats = project_detail["task_stats"]
    _assert(project_detail["status"] == "active", "Project should default to active.")
    _assert(project_detail["stage"] == "intake", "Project should default to intake.")
    _assert(task_stats["total_tasks"] == 3, "Project should aggregate all linked tasks.")
    _assert(task_stats["pending_tasks"] == 1, "Project should count pending tasks.")
    _assert(
        task_stats["waiting_human_tasks"] == 1,
        "Project should count waiting-human tasks.",
    )
    _assert(task_stats["paused_tasks"] == 1, "Project should count paused tasks.")
    _assert(pending_task["project_id"] == project["id"], "Task should keep the project link.")
    _assert(
        waiting_human_task["status"] == "waiting_human",
        "Requested-human tasks should start in waiting_human.",
    )
    _assert(paused_task["status"] == "paused", "Paused tasks should start in paused.")
    _assert(project_list[0]["id"] == project["id"], "Projects list should expose the created project.")
    _assert(
        invalid_task_response.status_code == 409,
        "Linking a task to a missing project should be rejected.",
    )

    report = {
        "migration": {
            "projects_table_created": True,
            "task_columns": task_columns,
            "legacy_task_count": legacy_task_count,
            "legacy_run_count": legacy_run_count,
            "legacy_task_id": legacy_ids["legacy_task_id"],
            "legacy_run_id": legacy_ids["legacy_run_id"],
        },
        "api": {
            "project_id": project["id"],
            "project_status": project_detail["status"],
            "project_stage": project_detail["stage"],
            "task_stats": task_stats,
            "created_task_ids": [
                pending_task["id"],
                waiting_human_task["id"],
                paused_task["id"],
            ],
            "invalid_project_link_status": invalid_task_response.status_code,
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
