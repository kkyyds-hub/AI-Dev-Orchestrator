"""V3-A Day03 smoke checks for project-level planning entry and task mapping."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v3-day03-project-planning-smoke"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _prepare_env() -> None:
    if SMOKE_RUNTIME_DATA_DIR.exists():
        shutil.rmtree(SMOKE_RUNTIME_DATA_DIR)
    SMOKE_RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)

    os.environ["RUNTIME_DATA_DIR"] = str(SMOKE_RUNTIME_DATA_DIR)
    os.environ["DAILY_BUDGET_USD"] = "0.10"
    os.environ["SESSION_BUDGET_USD"] = "0.30"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"


def main() -> None:
    """Exercise the Day03 project draft -> apply -> detail workflow."""

    _prepare_env()

    from fastapi.testclient import TestClient

    from app.core.db import init_database
    from app.main import app

    init_database()

    with TestClient(app) as client:
        draft_response = client.post(
            "/planning/drafts",
            json={
                "brief": "\n".join(
                    [
                        "为老板工作台补一个项目级规划入口。",
                        "1. 先根据 brief 生成项目草案与项目摘要",
                        "2. 再把任务映射到项目下，并保留人工调整空间",
                        "3. 项目详情里要能看见任务树与草案来源",
                    ]
                ),
                "max_tasks": 5,
            },
        )
        _assert(
            draft_response.status_code == 200,
            f"planning/drafts failed: {draft_response.status_code}",
        )
        draft_payload = draft_response.json()

        _assert(
            draft_payload["project"] is not None,
            "project draft should be present in Day03 draft response",
        )
        _assert(
            draft_payload["project"]["stage"] == "planning",
            f"expected project draft stage=planning, got {draft_payload['project']['stage']}",
        )
        _assert(
            len(draft_payload["tasks"]) >= 3,
            "project planning draft should contain at least 3 task drafts",
        )

        edited_tasks = json.loads(json.dumps(draft_payload["tasks"]))
        edited_tasks[1]["title"] = "梳理项目草案与任务映射接口"
        edited_tasks[1]["acceptance_criteria"].append("确认项目详情页能读取草案来源")
        edited_project = {
            **draft_payload["project"],
            "name": "项目级规划入口 MVP",
            "summary": "先生成项目草案，再把任务映射到项目下，并在项目详情中展示任务树和草案来源。",
        }

        apply_response = client.post(
            "/planning/apply",
            json={
                "project_summary": edited_project["summary"],
                "project": edited_project,
                "tasks": edited_tasks,
            },
        )
        _assert(
            apply_response.status_code == 201,
            f"planning/apply in project mode failed: {apply_response.status_code}",
        )
        apply_payload = apply_response.json()

        _assert(
            apply_payload["project"] is not None,
            "project mode apply should return the created project",
        )
        project_id = apply_payload["project"]["id"]
        _assert(
            apply_payload["project"]["name"] == edited_project["name"],
            "edited project name should persist after applying the draft",
        )
        _assert(
            apply_payload["created_count"] == len(edited_tasks),
            "created task count should match the reviewed draft count",
        )
        _assert(
            all(task["project_id"] == project_id for task in apply_payload["tasks"]),
            "all created tasks should attach to the created project",
        )
        _assert(
            all(task["status"] == "pending" for task in apply_payload["tasks"]),
            "applying a project draft should not auto-run tasks",
        )
        _assert(
            any(
                task["title"] == "梳理项目草案与任务映射接口"
                for task in apply_payload["tasks"]
            ),
            "manual task edits should be preserved before apply",
        )
        _assert(
            all(task["source_draft_id"] == task["draft_id"] for task in apply_payload["tasks"]),
            "created tasks should keep their source draft mapping",
        )

        detail_response = client.get(f"/projects/{project_id}")
        _assert(
            detail_response.status_code == 200,
            f"project detail failed: {detail_response.status_code}",
        )
        detail_payload = detail_response.json()

        _assert(
            detail_payload["task_stats"]["total_tasks"] == apply_payload["created_count"],
            "project detail should aggregate mapped task count",
        )
        _assert(
            len(detail_payload["tasks"]) == apply_payload["created_count"],
            "project detail should expose the mapped task tree payload",
        )
        _assert(
            any(task["depth"] > 0 for task in detail_payload["tasks"]),
            "project detail should expose dependency depth for the task tree",
        )
        _assert(
            any(task["source_draft_id"] for task in detail_payload["tasks"]),
            "project detail should expose source draft IDs",
        )

        legacy_draft_response = client.post(
            "/planning/drafts",
            json={
                "brief": "Keep the original planner mode compatible without creating a project first.",
                "max_tasks": 4,
            },
        )
        _assert(
            legacy_draft_response.status_code == 200,
            f"legacy planning/drafts failed: {legacy_draft_response.status_code}",
        )
        legacy_draft_payload = legacy_draft_response.json()
        legacy_apply_response = client.post(
            "/planning/apply",
            json={
                "project_summary": legacy_draft_payload["project_summary"],
                "tasks": legacy_draft_payload["tasks"],
            },
        )
        _assert(
            legacy_apply_response.status_code == 201,
            f"legacy planning/apply failed: {legacy_apply_response.status_code}",
        )
        legacy_apply_payload = legacy_apply_response.json()
        _assert(
            legacy_apply_payload["project"] is None,
            "legacy apply should remain project-agnostic when no project draft is provided",
        )
        _assert(
            all(task["project_id"] is None for task in legacy_apply_payload["tasks"]),
            "legacy planner mode should still create unassigned tasks",
        )

    report = {
        "project_mode": {
            "project_name": apply_payload["project"]["name"],
            "project_id": project_id,
            "created_count": apply_payload["created_count"],
            "task_sources": [
                {
                    "draft_id": task["draft_id"],
                    "task_id": task["id"],
                    "project_id": task["project_id"],
                    "source_draft_id": task["source_draft_id"],
                }
                for task in apply_payload["tasks"]
            ],
            "detail_task_depths": {
                task["title"]: task["depth"] for task in detail_payload["tasks"]
            },
        },
        "legacy_mode": {
            "created_count": legacy_apply_payload["created_count"],
            "all_unassigned": all(
                task["project_id"] is None for task in legacy_apply_payload["tasks"]
            ),
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
