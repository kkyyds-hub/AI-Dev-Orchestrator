"""V4-A Day04 smoke checks for boss-home repository entry integration."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_ROOT = RUNTIME_ROOT / "tmp" / "v4-day04-repository-home-smoke"
SMOKE_RUNTIME_DATA_DIR = SMOKE_ROOT / "runtime-data"
SMOKE_ALLOWED_WORKSPACE_ROOT = SMOKE_ROOT / "allowed-workspaces"
SMOKE_REPOSITORY_ROOT = SMOKE_ALLOWED_WORKSPACE_ROOT / "repository-home"


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
        "# Day04 smoke repo\n",
        encoding="utf-8",
    )
    (SMOKE_REPOSITORY_ROOT / "src" / "main.ts").write_text(
        "export const feature = 'day04-home';\n",
        encoding="utf-8",
    )
    (SMOKE_REPOSITORY_ROOT / "src" / "index.py").write_text(
        "print('day04 home smoke')\n",
        encoding="utf-8",
    )
    (SMOKE_REPOSITORY_ROOT / "docs" / "notes.md").write_text(
        "# Day04 repository home\n",
        encoding="utf-8",
    )

    _run_git("init")
    _run_git("checkout", "-b", "main")
    _run_git("config", "user.email", "EMAIL_REDACTED")
    _run_git("config", "user.name", "Smoke Bot")
    _run_git("add", ".")
    _run_git("commit", "-m", "init day04 smoke repo")
    _run_git("checkout", "-b", "feature/day04-home")

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
        bound_project = _request_json(
            client,
            "POST",
            "/projects",
            expected_status=201,
            json_body={
                "name": "Day04 Bound Project",
                "summary": "Boss home should expose repository binding, snapshot and change session.",
            },
        )
        unbound_project = _request_json(
            client,
            "POST",
            "/projects",
            expected_status=201,
            json_body={
                "name": "Day04 Unbound Project",
                "summary": "Boss home should show the next step instead of an empty repository area.",
            },
        )

        binding = _request_json(
            client,
            "PUT",
            f"/repositories/projects/{bound_project['id']}",
            expected_status=200,
            json_body={
                "root_path": str(SMOKE_REPOSITORY_ROOT.resolve()),
                "display_name": "Day04 smoke repo",
                "default_base_branch": "main",
            },
        )
        snapshot = _request_json(
            client,
            "POST",
            f"/repositories/projects/{bound_project['id']}/snapshot/refresh",
            expected_status=200,
        )
        change_session = _request_json(
            client,
            "POST",
            f"/repositories/projects/{bound_project['id']}/change-session",
            expected_status=200,
        )

        project_list = _request_json(
            client,
            "GET",
            "/projects",
            expected_status=200,
        )
        overview = _request_json(
            client,
            "GET",
            "/console/project-overview",
            expected_status=200,
        )
        bound_detail = _request_json(
            client,
            "GET",
            f"/projects/{bound_project['id']}",
            expected_status=200,
        )
        unbound_detail = _request_json(
            client,
            "GET",
            f"/projects/{unbound_project['id']}",
            expected_status=200,
        )

    project_list_map = {item["name"]: item for item in project_list}
    overview_map = {item["name"]: item for item in overview["projects"]}

    _assert(
        len(overview["projects"]) == 2,
        "Boss home should expose both the bound and unbound projects.",
    )
    _assert(
        overview_map["Day04 Bound Project"]["repository_workspace"]["display_name"]
        == "Day04 smoke repo",
        "Boss home should expose the bound repository display name.",
    )
    _assert(
        overview_map["Day04 Bound Project"]["latest_repository_snapshot"]["status"] == "success",
        "Boss home should expose the latest snapshot summary for bound projects.",
    )
    _assert(
        overview_map["Day04 Bound Project"]["current_change_session"]["current_branch"]
        == "feature/day04-home",
        "Boss home should expose the active change-session branch.",
    )
    _assert(
        overview_map["Day04 Unbound Project"]["repository_workspace"] is None,
        "Unbound projects should keep repository_workspace as null on boss home.",
    )
    _assert(
        overview_map["Day04 Unbound Project"]["latest_repository_snapshot"] is None,
        "Unbound projects should keep latest_repository_snapshot as null on boss home.",
    )
    _assert(
        overview_map["Day04 Unbound Project"]["current_change_session"] is None,
        "Unbound projects should keep current_change_session as null on boss home.",
    )

    _assert(
        project_list_map["Day04 Bound Project"]["current_change_session"]["baseline_branch"]
        == "main",
        "Project list should expose the same change-session field naming as the detail API.",
    )
    _assert(
        bound_detail["repository_workspace"] == binding,
        "Project detail should expose the same repository binding payload as the repository API.",
    )
    _assert(
        bound_detail["latest_repository_snapshot"] == snapshot,
        "Project detail should expose the latest repository snapshot summary.",
    )
    _assert(
        bound_detail["current_change_session"] == change_session,
        "Project detail should expose the latest change-session summary.",
    )
    _assert(
        bound_detail["latest_repository_snapshot"]["language_breakdown"][0]["file_count"] >= 1,
        "Project detail should keep the Day02 language breakdown summary.",
    )
    _assert(
        unbound_detail["repository_workspace"] is None
        and unbound_detail["latest_repository_snapshot"] is None
        and unbound_detail["current_change_session"] is None,
        "Unbound project detail should keep all repository entry fields empty.",
    )

    report = {
        "overview": {
            "total_projects": overview["total_projects"],
            "bound_project_repository": {
                "display_name": overview_map["Day04 Bound Project"]["repository_workspace"][
                    "display_name"
                ],
                "snapshot_status": overview_map["Day04 Bound Project"][
                    "latest_repository_snapshot"
                ]["status"],
                "change_branch": overview_map["Day04 Bound Project"][
                    "current_change_session"
                ]["current_branch"],
            },
            "unbound_project_repository": {
                "repository_workspace": overview_map["Day04 Unbound Project"][
                    "repository_workspace"
                ],
                "latest_repository_snapshot": overview_map["Day04 Unbound Project"][
                    "latest_repository_snapshot"
                ],
                "current_change_session": overview_map["Day04 Unbound Project"][
                    "current_change_session"
                ],
            },
        },
        "project_detail": {
            "bound_project_id": bound_detail["id"],
            "snapshot_id": bound_detail["latest_repository_snapshot"]["id"],
            "change_session_id": bound_detail["current_change_session"]["id"],
            "baseline_branch": bound_detail["current_change_session"]["baseline_branch"],
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
