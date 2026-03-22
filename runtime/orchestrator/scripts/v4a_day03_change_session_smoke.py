"""V4-A Day03 smoke checks for change-session snapshots and dirty-state guards."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_ROOT = RUNTIME_ROOT / "tmp" / "v4-day03-change-session-smoke"
SMOKE_RUNTIME_DATA_DIR = SMOKE_ROOT / "runtime-data"
SMOKE_DB_PATH = SMOKE_RUNTIME_DATA_DIR / "db" / "orchestrator.db"
SMOKE_ALLOWED_WORKSPACE_ROOT = SMOKE_ROOT / "allowed-workspaces"
SMOKE_REPOSITORY_ROOT = SMOKE_ALLOWED_WORKSPACE_ROOT / "change-session-repository"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _remove_readonly(func: Any, path: str, _: Any) -> None:
    Path(path).chmod(stat.S_IWRITE)
    func(path)


def _run_git(*args: str) -> str:
    completed_process = subprocess.run(
        ["git", *args],
        cwd=SMOKE_REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed_process.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed: {completed_process.stderr or completed_process.stdout}"
        )

    return (completed_process.stdout or "").strip()


def _prepare_env() -> None:
    if SMOKE_ROOT.exists():
        shutil.rmtree(SMOKE_ROOT, onerror=_remove_readonly)

    (SMOKE_REPOSITORY_ROOT / "src").mkdir(parents=True, exist_ok=True)
    (SMOKE_REPOSITORY_ROOT / "docs").mkdir(parents=True, exist_ok=True)
    (SMOKE_REPOSITORY_ROOT / "README.md").write_text(
        "# Day03 smoke repo\n",
        encoding="utf-8",
    )
    (SMOKE_REPOSITORY_ROOT / "src" / "main.ts").write_text(
        "export const smoke = 'day03';\n",
        encoding="utf-8",
    )
    (SMOKE_REPOSITORY_ROOT / "docs" / "notes.md").write_text(
        "# Day03 snapshot\n",
        encoding="utf-8",
    )

    _run_git("init")
    _run_git("checkout", "-b", "main")
    _run_git("config", "user.email", "smoke@example.com")
    _run_git("config", "user.name", "Smoke Bot")
    _run_git("add", ".")
    _run_git("commit", "-m", "init day03 smoke repo")
    _run_git("checkout", "-b", "feature/day03-session")

    os.environ["RUNTIME_DATA_DIR"] = str(SMOKE_RUNTIME_DATA_DIR)
    os.environ["REPOSITORY_WORKSPACE_ROOT_DIR"] = str(SMOKE_ALLOWED_WORKSPACE_ROOT)
    os.environ["DAILY_BUDGET_USD"] = "0.05"
    os.environ["SESSION_BUDGET_USD"] = "0.20"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"


def _request_json(
    client: Any,
    method: str,
    path: str,
    *,
    expected_status: int,
    json_body: dict[str, Any] | None = None,
) -> Any:
    response = client.request(method, path, json=json_body)
    if response.status_code != expected_status:
        raise AssertionError(
            f"{method} {path} expected {expected_status}, got {response.status_code}: {response.text}"
        )

    return response.json()


def main() -> None:
    _prepare_env()

    from fastapi.testclient import TestClient

    from app.main import create_application

    app = create_application()

    with TestClient(app) as client:
        project = _request_json(
            client,
            "POST",
            "/projects",
            expected_status=201,
            json_body={
                "name": "V4 Day03 Smoke Project",
                "summary": "Exercise Day03 change-session capture and dirty guard states.",
            },
        )

        _request_json(
            client,
            "PUT",
            f"/repositories/projects/{project['id']}",
            expected_status=200,
            json_body={
                "root_path": str(SMOKE_REPOSITORY_ROOT),
                "display_name": "Day03 smoke repo",
                "default_base_branch": "main",
            },
        )

        snapshot = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project['id']}/snapshot/refresh",
            expected_status=200,
        )
        _assert(
            snapshot["status"] == "success",
            "Day03 smoke expects the Day02 snapshot refresh to succeed first.",
        )

        clean_session = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project['id']}/change-session",
            expected_status=200,
        )
        _assert(
            clean_session["current_branch"] == "feature/day03-session",
            "The active change session should record the current feature branch.",
        )
        _assert(
            clean_session["head_ref"] == "refs/heads/feature/day03-session",
            "The active change session should record the current HEAD ref.",
        )
        _assert(
            clean_session["baseline_branch"] == "main",
            "The active change session should keep the configured baseline branch.",
        )
        _assert(
            clean_session["baseline_ref"] == "refs/heads/main",
            "The active change session should resolve the baseline ref against the local main branch.",
        )
        _assert(
            clean_session["workspace_status"] == "clean"
            and clean_session["guard_status"] == "ready",
            "A clean feature branch should be recorded as a ready Day03 session.",
        )
        _assert(
            clean_session["dirty_file_count"] == 0 and clean_session["dirty_files"] == [],
            "Clean sessions should not carry dirty-file previews.",
        )

        fetched_clean_session = _request_json(
            client,
            "GET",
            f"/repositories/projects/{project['id']}/change-session",
            expected_status=200,
        )
        _assert(
            fetched_clean_session == clean_session,
            "GET change-session should return the latest persisted clean session payload.",
        )

        (SMOKE_REPOSITORY_ROOT / "README.md").write_text(
            "# Day03 smoke repo\n\nDirty change pending.\n",
            encoding="utf-8",
        )
        (SMOKE_REPOSITORY_ROOT / "src" / "generated.ts").write_text(
            "export const generated = true;\n",
            encoding="utf-8",
        )

        dirty_session = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project['id']}/change-session",
            expected_status=200,
        )
        _assert(
            dirty_session["id"] == clean_session["id"],
            "Refreshing the active change session should update the existing Day03 row.",
        )
        _assert(
            dirty_session["workspace_status"] == "dirty"
            and dirty_session["guard_status"] == "blocked",
            "Dirty workspaces should be recorded as blocked Day03 sessions.",
        )
        _assert(
            dirty_session["dirty_file_count"] == 2,
            "The Day03 session should count both modified and untracked files.",
        )
        _assert(
            {item["change_scope"] for item in dirty_session["dirty_files"]}
            == {"unstaged", "untracked"},
            "The dirty-file preview should distinguish unstaged and untracked files.",
        )
        _assert(
            any("工作区存在 2 个" in reason for reason in dirty_session["blocking_reasons"]),
            "Blocked Day03 sessions should preserve the dirty-workspace reason.",
        )

        fetched_dirty_session = _request_json(
            client,
            "GET",
            f"/repositories/projects/{project['id']}/change-session",
            expected_status=200,
        )
        _assert(
            fetched_dirty_session == dirty_session,
            "GET change-session should return the latest persisted dirty session payload.",
        )

    connection = sqlite3.connect(SMOKE_DB_PATH)
    try:
        session_row = connection.execute(
            """
            SELECT current_branch, baseline_branch, workspace_status, guard_status, dirty_file_count
            FROM change_sessions
            """
        ).fetchone()
    finally:
        connection.close()

    _assert(session_row is not None, "change_sessions table should contain one row.")
    _assert(
        session_row[0] == "feature/day03-session",
        "The persisted change-session row should keep the current feature branch name.",
    )
    _assert(
        session_row[1] == "main",
        "The persisted change-session row should keep the configured baseline branch.",
    )
    _assert(
        session_row[2] == "dirty" and session_row[3] == "blocked",
        "The latest persisted change-session row should keep the dirty/blocked state.",
    )
    _assert(
        session_row[4] == 2,
        "The persisted change-session row should store the dirty file count.",
    )
    print("V4 Day03 change session smoke passed.")


if __name__ == "__main__":
    main()
