"""V3-B Day07 smoke checks for role dispatching and collaboration handoffs."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v3-day07-role-flow-smoke"


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
    """Exercise the Day07 role-routing and handoff workflow."""

    _prepare_env()

    from fastapi.testclient import TestClient

    from app.core.db import init_database
    from app.main import app

    init_database()

    with TestClient(app) as client:
        routing_project_response = client.post(
            "/projects",
            json={
                "name": "Day07 Manual Role Routing",
                "summary": "验证任务能根据角色职责自动分派，并在运行日志记录角色接力。",
                "stage": "planning",
            },
        )
        _assert(routing_project_response.status_code == 201, "manual project create failed")
        routing_project_id = routing_project_response.json()["id"]

        manual_task_response = client.post(
            "/tasks",
            json={
                "project_id": routing_project_id,
                "title": "整理架构设计与接口边界",
                "input_summary": (
                    "为新的规划结果整理技术方案、模块边界和接口契约，"
                    "并补充依赖与风险说明。"
                ),
                "priority": "high",
                "acceptance_criteria": [
                    "说明系统模块边界",
                    "列出关键接口契约",
                    "标记主要依赖与风险",
                ],
                "risk_level": "normal",
            },
        )
        _assert(manual_task_response.status_code == 201, "manual task create failed")
        manual_task_payload = manual_task_response.json()
        _assert(
            manual_task_payload["owner_role_code"] == "architect",
            f"expected architect owner role, got {manual_task_payload['owner_role_code']}",
        )
        _assert(
            manual_task_payload["upstream_role_code"] == "product_manager",
            "manual task should inherit PM as the upstream role",
        )
        _assert(
            manual_task_payload["downstream_role_code"] == "engineer",
            "manual task should default the next handoff to engineer",
        )

        worker_response = client.post("/workers/run-once")
        _assert(worker_response.status_code == 200, "worker run failed")
        worker_payload = worker_response.json()
        _assert(worker_payload["claimed"] is True, "worker should claim the manual task")
        _assert(
            worker_payload["owner_role_code"] == "architect",
            "worker response should surface the routed owner role",
        )
        _assert(
            worker_payload["dispatch_status"] == "explicit_owner",
            f"unexpected dispatch status: {worker_payload['dispatch_status']}",
        )
        _assert(worker_payload["run_id"] is not None, "worker run should create a run id")

        run_logs_response = client.get(f"/runs/{worker_payload['run_id']}/logs")
        _assert(run_logs_response.status_code == 200, "run logs fetch failed")
        run_logs_payload = run_logs_response.json()
        role_handoff_event = next(
            (
                event
                for event in run_logs_payload["events"]
                if event["event"] == "role_handoff"
            ),
            None,
        )
        _assert(role_handoff_event is not None, "role_handoff log event missing")
        _assert(
            role_handoff_event["data"]["owner_role_code"] == "architect",
            "role_handoff event should keep the owner role",
        )
        _assert(
            role_handoff_event["data"]["downstream_role_code"] == "engineer",
            "role_handoff event should keep the downstream role",
        )

        sop_project_response = client.post(
            "/projects",
            json={
                "name": "Day07 SOP Role Flow",
                "summary": "验证项目详情能读出最小角色协作链。",
                "stage": "planning",
            },
        )
        _assert(sop_project_response.status_code == 201, "sop project create failed")
        sop_project_id = sop_project_response.json()["id"]

        template_select_response = client.put(
            f"/projects/{sop_project_id}/sop-template",
            json={"template_code": "std_delivery"},
        )
        _assert(template_select_response.status_code == 200, "sop template select failed")
        template_select_payload = template_select_response.json()
        _assert(
            template_select_payload["created_task_count"] == 2,
            "planning stage should create two SOP tasks",
        )

        project_detail_response = client.get(f"/projects/{sop_project_id}")
        _assert(project_detail_response.status_code == 200, "project detail fetch failed")
        project_detail_payload = project_detail_response.json()
        role_linked_tasks = [
            task
            for task in project_detail_payload["tasks"]
            if task["owner_role_code"] or task["upstream_role_code"] or task["downstream_role_code"]
        ]
        _assert(role_linked_tasks, "project detail should include role-linked tasks")
        _assert(
            any(task["owner_role_code"] == "product_manager" for task in role_linked_tasks),
            "SOP tasks should include a product-manager-owned planning task",
        )
        _assert(
            any(task["downstream_role_code"] == "engineer" for task in role_linked_tasks),
            "SOP tasks should expose engineer as a downstream handoff target",
        )

    report = {
        "manual_task": {
            "project_id": routing_project_id,
            "task_id": manual_task_payload["id"],
            "owner_role_code": manual_task_payload["owner_role_code"],
            "upstream_role_code": manual_task_payload["upstream_role_code"],
            "downstream_role_code": manual_task_payload["downstream_role_code"],
        },
        "worker_result": {
            "run_id": worker_payload["run_id"],
            "dispatch_status": worker_payload["dispatch_status"],
            "owner_role_code": worker_payload["owner_role_code"],
            "handoff_reason": worker_payload["handoff_reason"],
            "route_reason": worker_payload["route_reason"],
        },
        "role_handoff_event": role_handoff_event,
        "sop_project": {
            "project_id": sop_project_id,
            "role_linked_task_count": len(role_linked_tasks),
            "task_role_chains": [
                {
                    "task_id": task["id"],
                    "title": task["title"],
                    "upstream_role_code": task["upstream_role_code"],
                    "owner_role_code": task["owner_role_code"],
                    "downstream_role_code": task["downstream_role_code"],
                }
                for task in role_linked_tasks
            ],
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
