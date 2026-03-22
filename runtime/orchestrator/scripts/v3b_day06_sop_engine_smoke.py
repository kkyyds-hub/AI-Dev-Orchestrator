"""V3-B Day06 smoke checks for SOP templates and stage-driven task generation."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
from uuid import UUID


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v3-day06-sop-engine-smoke"


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
    """Exercise the Day06 SOP workflow end to end."""

    _prepare_env()

    from fastapi.testclient import TestClient

    from app.core.db import SessionLocal, init_database
    from app.domain.task import TaskStatus
    from app.main import app
    from app.repositories.task_repository import TaskRepository

    init_database()

    with TestClient(app) as client:
        project_response = client.post(
            "/projects",
            json={
                "name": "Day06 SOP Smoke",
                "summary": "验证 SOP 模板选择、阶段清单、模板任务生成与阶段推进联动。",
                "stage": "planning",
            },
        )
        _assert(project_response.status_code == 201, "project create failed")
        project_id = project_response.json()["id"]

        templates_response = client.get("/projects/sop-templates")
        _assert(templates_response.status_code == 200, "template list failed")
        templates_payload = templates_response.json()
        template_codes = [item["code"] for item in templates_payload]
        _assert(
            template_codes == ["std_delivery", "hotfix_flow"],
            f"unexpected template codes: {template_codes}",
        )

        select_response = client.put(
            f"/projects/{project_id}/sop-template",
            json={"template_code": "std_delivery"},
        )
        _assert(select_response.status_code == 200, "template select failed")
        select_payload = select_response.json()
        _assert(
            select_payload["created_task_count"] == 2,
            f"expected 2 planning tasks, got {select_payload['created_task_count']}",
        )
        _assert(
            select_payload["sop_snapshot"]["has_template"] is True,
            "snapshot should report a selected template",
        )
        _assert(
            select_payload["sop_snapshot"]["current_stage"] == "planning",
            "snapshot stage should remain planning after template binding",
        )
        _assert(
            len(select_payload["sop_snapshot"]["stage_tasks"]) == 2,
            "planning snapshot should expose two current-stage tasks",
        )
        _assert(
            {role["role_code"] for role in select_payload["sop_snapshot"]["owner_roles"]}
            == {"product_manager", "architect"},
            "planning stage should expose PM + Architect as owner roles",
        )

        detail_after_select = client.get(f"/projects/{project_id}")
        _assert(detail_after_select.status_code == 200, "project detail failed after select")
        detail_payload = detail_after_select.json()
        _assert(
            detail_payload["stage_guard"]["can_advance"] is False,
            "planning stage must stay blocked until SOP tasks complete",
        )
        _assert(
            detail_payload["stage_guard"]["current_stage_task_count"] == 2,
            "guard should expose current-stage task totals",
        )
        _assert(
            all(
                task["source_draft_id"] and task["source_draft_id"].startswith("sop:")
                for task in detail_payload["tasks"]
            ),
            "generated planning tasks should be tagged as SOP-managed tasks",
        )

        blocked_advance_response = client.post(
            f"/projects/{project_id}/advance-stage",
            json={"note": "planning tasks are still pending"},
        )
        _assert(
            blocked_advance_response.status_code == 200,
            "blocked advance should still return structured payload",
        )
        blocked_advance_payload = blocked_advance_response.json()
        _assert(
            blocked_advance_payload["advanced"] is False,
            "planning stage should not advance while stage tasks are incomplete",
        )

        planning_task_ids = [
            UUID(task["task_id"])
            for task in select_payload["sop_snapshot"]["stage_tasks"]
        ]
        with SessionLocal() as session:
            task_repository = TaskRepository(session)
            for task_id in planning_task_ids:
                task_repository.set_status(task_id, TaskStatus.COMPLETED)
            session.commit()

        execution_advance_response = client.post(
            f"/projects/{project_id}/advance-stage",
            json={"note": "planning checklist completed"},
        )
        _assert(
            execution_advance_response.status_code == 200,
            "execution advance failed",
        )
        execution_advance_payload = execution_advance_response.json()
        _assert(
            execution_advance_payload["advanced"] is True,
            "project should advance after all planning SOP tasks complete",
        )
        _assert(
            execution_advance_payload["current_stage"] == "execution",
            "project should now be in execution stage",
        )

        execution_detail_response = client.get(f"/projects/{project_id}")
        _assert(execution_detail_response.status_code == 200, "execution detail failed")
        execution_detail_payload = execution_detail_response.json()
        execution_snapshot = execution_detail_payload["sop_snapshot"]
        _assert(
            execution_snapshot["current_stage"] == "execution",
            "SOP snapshot should move with the project stage",
        )
        _assert(
            execution_snapshot["current_stage_task_count"] == 2,
            "execution stage should auto-generate its two template tasks",
        )
        _assert(
            execution_snapshot["stage_tasks"][0]["task_code"] == "build_core",
            "execution tasks should be generated from the execution stage template",
        )

    report = {
        "project_id": project_id,
        "template_codes": template_codes,
        "selected_template": select_payload["template_code"],
        "planning_stage_task_count": select_payload["sop_snapshot"]["current_stage_task_count"],
        "execution_stage_task_count": execution_snapshot["current_stage_task_count"],
        "advance_message": execution_advance_payload["message"],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
