"""V4-A Day02 smoke checks for repository scanning and snapshot summaries."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sqlite3
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_ROOT = RUNTIME_ROOT / "tmp" / "v4-day02-repository-snapshot-smoke"
SMOKE_RUNTIME_DATA_DIR = SMOKE_ROOT / "runtime-data"
SMOKE_DB_PATH = SMOKE_RUNTIME_DATA_DIR / "db" / "orchestrator.db"
SMOKE_ALLOWED_WORKSPACE_ROOT = SMOKE_ROOT / "allowed-workspaces"
SMOKE_REPOSITORY_ROOT = SMOKE_ALLOWED_WORKSPACE_ROOT / "snapshot-repository"
SMOKE_REPOSITORY_RENAMED_ROOT = SMOKE_ALLOWED_WORKSPACE_ROOT / "snapshot-repository-moved"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _prepare_env() -> None:
    if SMOKE_ROOT.exists():
        shutil.rmtree(SMOKE_ROOT)

    (SMOKE_REPOSITORY_ROOT / ".git").mkdir(parents=True, exist_ok=True)
    (SMOKE_REPOSITORY_ROOT / "node_modules" / "react").mkdir(parents=True, exist_ok=True)
    (SMOKE_REPOSITORY_ROOT / ".venv" / "Scripts").mkdir(parents=True, exist_ok=True)
    (SMOKE_REPOSITORY_ROOT / "dist").mkdir(parents=True, exist_ok=True)
    (SMOKE_REPOSITORY_ROOT / "src" / "components").mkdir(parents=True, exist_ok=True)
    (SMOKE_REPOSITORY_ROOT / "docs").mkdir(parents=True, exist_ok=True)
    (SMOKE_REPOSITORY_ROOT / "config").mkdir(parents=True, exist_ok=True)

    (SMOKE_REPOSITORY_ROOT / ".git" / "HEAD").write_text(
        "ref: refs/heads/main\n",
        encoding="utf-8",
    )
    (SMOKE_REPOSITORY_ROOT / "node_modules" / "react" / "index.js").write_text(
        "export const ignored = true;\n",
        encoding="utf-8",
    )
    (SMOKE_REPOSITORY_ROOT / ".venv" / "pyvenv.cfg").write_text(
        "home = fake\n",
        encoding="utf-8",
    )
    (SMOKE_REPOSITORY_ROOT / "dist" / "bundle.js").write_text(
        "console.log('ignored');\n",
        encoding="utf-8",
    )
    (SMOKE_REPOSITORY_ROOT / "src" / "main.py").write_text(
        "print('hello day02')\n",
        encoding="utf-8",
    )
    (SMOKE_REPOSITORY_ROOT / "src" / "components" / "App.tsx").write_text(
        "export function App() { return <div>day02</div>; }\n",
        encoding="utf-8",
    )
    (SMOKE_REPOSITORY_ROOT / "docs" / "notes.md").write_text(
        "# Snapshot notes\n",
        encoding="utf-8",
    )
    (SMOKE_REPOSITORY_ROOT / "config" / "settings.yaml").write_text(
        "mode: smoke\n",
        encoding="utf-8",
    )
    (SMOKE_REPOSITORY_ROOT / "package.json").write_text(
        '{\n  "name": "snapshot-smoke"\n}\n',
        encoding="utf-8",
    )

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


def _language_count(snapshot: dict[str, Any], language: str) -> int:
    for item in snapshot["language_breakdown"]:
        if item["language"] == language:
            return int(item["file_count"])

    return 0


def _find_tree_node(snapshot: dict[str, Any], relative_path: str) -> dict[str, Any] | None:
    pending_nodes = list(snapshot["tree"])
    while pending_nodes:
        node = pending_nodes.pop()
        if node["relative_path"] == relative_path:
            return node
        pending_nodes.extend(node.get("children", []))

    return None


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
                "name": "Day02 smoke project",
                "summary": "Verify repository snapshots stay within Day02 scope.",
                "status": "active",
                "stage": "intake",
            },
        )

        repository_binding = _request_json(
            client,
            "PUT",
            f"/repositories/projects/{project['id']}",
            expected_status=200,
            json_body={
                "root_path": str(SMOKE_REPOSITORY_ROOT.resolve()),
                "display_name": "Snapshot smoke repo",
                "access_mode": "read_only",
                "default_base_branch": "main",
                "ignore_rule_summary": [],
            },
        )
        _assert(
            repository_binding["root_path"] == str(SMOKE_REPOSITORY_ROOT.resolve()),
            "Repository binding should succeed before scanning.",
        )

        refresh_response = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project['id']}/snapshot/refresh",
            expected_status=200,
        )
        _assert(
            refresh_response["status"] == "success",
            "The first snapshot refresh should succeed for the prepared repository.",
        )
        _assert(
            refresh_response["directory_count"] == 4,
            "Directory count should exclude ignored folders and only include kept directories.",
        )
        _assert(
            refresh_response["file_count"] == 5,
            "File count should exclude ignored folders and only include kept files.",
        )
        _assert(
            refresh_response["scan_error"] is None,
            "Successful snapshots should not report scan errors.",
        )
        _assert(
            refresh_response["ignored_directory_names"]
            == [".git", ".venv", "__pycache__", "node_modules", "dist", "build"],
            "Snapshot refresh should apply the Day01/Day02 default ignored-directory baseline.",
        )
        _assert(
            _language_count(refresh_response, "Python") == 1,
            "Language breakdown should count Python files from the kept workspace.",
        )
        _assert(
            _language_count(refresh_response, "TypeScript") == 1,
            "Language breakdown should count TypeScript files from the kept workspace.",
        )
        _assert(
            _language_count(refresh_response, "Markdown") == 1,
            "Language breakdown should count Markdown files from the kept workspace.",
        )
        _assert(
            _language_count(refresh_response, "YAML") == 1,
            "Language breakdown should count YAML files from the kept workspace.",
        )
        _assert(
            _language_count(refresh_response, "JSON") == 1,
            "Language breakdown should count JSON files from the kept workspace.",
        )
        _assert(
            {node["name"] for node in refresh_response["tree"]} == {
                "config",
                "docs",
                "package.json",
                "src",
            },
            "Top-level tree summary should hide ignored directories but keep visible folders/files.",
        )
        src_node = _find_tree_node(refresh_response, "src")
        _assert(
            src_node is not None and src_node["file_count"] == 2,
            "The src directory summary should expose nested kept files.",
        )
        components_node = _find_tree_node(refresh_response, "src/components")
        _assert(
            components_node is not None and components_node["file_count"] == 1,
            "Nested directory summaries should remain readable inside the stored tree.",
        )

        fetched_snapshot = _request_json(
            client,
            "GET",
            f"/repositories/projects/{project['id']}/snapshot",
            expected_status=200,
        )
        _assert(
            fetched_snapshot == refresh_response,
            "GET snapshot should return the latest persisted snapshot payload.",
        )

        project_detail = _request_json(
            client,
            "GET",
            f"/projects/{project['id']}",
            expected_status=200,
        )
        _assert(
            project_detail["latest_repository_snapshot"] == refresh_response,
            "Project detail should expose the same latest snapshot payload as the repository API.",
        )

        SMOKE_REPOSITORY_ROOT.rename(SMOKE_REPOSITORY_RENAMED_ROOT)

        failed_refresh_response = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project['id']}/snapshot/refresh",
            expected_status=200,
        )
        _assert(
            failed_refresh_response["status"] == "failed",
            "Broken workspace paths should be recorded as failed snapshots, not hidden as empty repos.",
        )
        _assert(
            "does not exist" in (failed_refresh_response["scan_error"] or ""),
            "Failed snapshots should preserve the explicit scan error.",
        )
        _assert(
            failed_refresh_response["file_count"] == 0
            and failed_refresh_response["directory_count"] == 0,
            "Failed snapshots may zero counts, but must be clearly marked as failures.",
        )

        failed_project_detail = _request_json(
            client,
            "GET",
            f"/projects/{project['id']}",
            expected_status=200,
        )
        _assert(
            failed_project_detail["latest_repository_snapshot"]["status"] == "failed",
            "Project detail should surface the latest failed snapshot state after a broken refresh.",
        )

    connection = sqlite3.connect(SMOKE_DB_PATH)
    try:
        snapshot_row = connection.execute(
            """
            SELECT status, directory_count, file_count, scan_error
            FROM repository_snapshots
            """
        ).fetchone()
    finally:
        connection.close()

    _assert(snapshot_row is not None, "repository_snapshots table should contain one row.")
    _assert(
        snapshot_row[0] == "failed",
        "The latest persisted snapshot row should keep the failed status after the failure refresh.",
    )
    _assert(
        "does not exist" in (snapshot_row[3] or ""),
        "The persisted snapshot row should store the explicit scan failure reason.",
    )
    print("V4 Day02 repository snapshot smoke passed.")


if __name__ == "__main__":
    main()
