"""V3-C Day10 smoke checks for the boss approval gate and decision actions."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v3-day10-approval-gate-smoke"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _prepare_env() -> None:
    if SMOKE_RUNTIME_DATA_DIR.exists():
        shutil.rmtree(SMOKE_RUNTIME_DATA_DIR)
    SMOKE_RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)

    os.environ["RUNTIME_DATA_DIR"] = str(SMOKE_RUNTIME_DATA_DIR)
    os.environ["DAILY_BUDGET_USD"] = "0.20"
    os.environ["SESSION_BUDGET_USD"] = "0.50"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"


def _create_project_task_fixture(
    *,
    name: str,
    summary: str,
):
    from app.core.db import SessionLocal
    from app.domain.project import Project, ProjectStage
    from app.domain.project_role import ProjectRoleCode
    from app.domain.task import Task, TaskPriority, TaskStatus
    from app.repositories.project_repository import ProjectRepository
    from app.repositories.task_repository import TaskRepository

    with SessionLocal() as session:
        project_repository = ProjectRepository(session)
        task_repository = TaskRepository(session)

        project = project_repository.create(
            Project(
                name=name,
                summary=summary,
                stage=ProjectStage.PLANNING,
            )
        )
        task = task_repository.create(
            Task(
                project_id=project.id,
                title=f"{name} 关键规划任务",
                input_summary="整理规划期关键交付件，供老板审批与阶段推进使用。",
                priority=TaskPriority.HIGH,
                owner_role_code=ProjectRoleCode.PRODUCT_MANAGER,
                downstream_role_code=ProjectRoleCode.ARCHITECT,
            )
        )
        task_repository.set_status(task.id, TaskStatus.COMPLETED)
        session.commit()

    return project, task


def main() -> None:
    """Exercise the Day10 approval API surface end to end."""

    _prepare_env()

    from fastapi.testclient import TestClient

    from app.core.db import init_database
    from app.main import app

    init_database()

    gate_project, gate_task = _create_project_task_fixture(
        name="Day10 Approval Gate",
        summary="验证审批闸门会阻塞阶段推进，并在审批通过后释放。",
    )
    queue_project, queue_task = _create_project_task_fixture(
        name="Day10 Approval Inbox",
        summary="验证审批队列、超时项和结构化决策回放。",
    )

    with TestClient(app) as client:
        gate_deliverable_response = client.post(
            "/deliverables",
            json={
                "project_id": str(gate_project.id),
                "type": "prd",
                "title": "审批闸门 PRD",
                "stage": "planning",
                "created_by_role_code": "product_manager",
                "summary": "提交 PRD 初版，等待老板审批后进入执行阶段。",
                "content": "# 目标\n- 验证审批闸门会阻塞阶段推进。\n",
                "content_format": "markdown",
                "source_task_id": str(gate_task.id),
            },
        )
        _assert(
            gate_deliverable_response.status_code == 201,
            f"create gate deliverable failed: {gate_deliverable_response.status_code}",
        )
        gate_deliverable = gate_deliverable_response.json()

        gate_approval_response = client.post(
            "/approvals",
            json={
                "deliverable_id": gate_deliverable["id"],
                "requester_role_code": "product_manager",
                "request_note": "请确认当前 PRD 是否可以进入执行阶段。",
                "due_in_hours": 24,
            },
        )
        _assert(
            gate_approval_response.status_code == 201,
            f"create gate approval failed: {gate_approval_response.status_code}",
        )
        gate_approval = gate_approval_response.json()

        blocked_advance_response = client.post(
            f"/projects/{gate_project.id}/advance-stage",
            json={"note": "审批通过前尝试推进阶段"},
        )
        _assert(
            blocked_advance_response.status_code == 200,
            f"blocked advance request failed: {blocked_advance_response.status_code}",
        )
        blocked_advance = blocked_advance_response.json()

        _assert(blocked_advance["advanced"] is False, "approval gate should block stage advance")
        _assert(
            blocked_advance["stage_guard"]["can_advance"] is False,
            "stage guard should report blocked before approval passes",
        )
        _assert(
            any("审批" in reason or "老板" in reason for reason in blocked_advance["stage_guard"]["blocking_reasons"]),
            "stage guard should contain an approval-related blocking reason",
        )

        gate_decision_response = client.post(
            f"/approvals/{gate_approval['id']}/actions",
            json={
                "action": "approve",
                "actor_name": "老板",
                "summary": "PRD 范围清晰，可以进入执行阶段。",
                "comment": "继续按现有节奏推进。",
                "highlighted_risks": ["注意接口兼容"],
            },
        )
        _assert(
            gate_decision_response.status_code == 200,
            f"approve gate approval failed: {gate_decision_response.status_code}",
        )

        released_advance_response = client.post(
            f"/projects/{gate_project.id}/advance-stage",
            json={"note": "审批通过后再次推进阶段"},
        )
        _assert(
            released_advance_response.status_code == 200,
            f"released advance request failed: {released_advance_response.status_code}",
        )
        released_advance = released_advance_response.json()

        _assert(released_advance["advanced"] is True, "stage should advance after approval")
        _assert(
            released_advance["current_stage"] == "execution",
            "project should advance from planning to execution after approval",
        )

        inbox_deliverables: list[dict] = []
        for deliverable_type, title in [
            ("design", "等待补充的设计稿"),
            ("code_plan", "已驳回的代码计划"),
            ("stage_artifact", "超时待审批产物"),
        ]:
            response = client.post(
                "/deliverables",
                json={
                    "project_id": str(queue_project.id),
                    "type": deliverable_type,
                    "title": title,
                    "stage": "planning",
                    "created_by_role_code": "architect",
                    "summary": f"{title} v1",
                    "content": f"{title} 的最小内容快照。",
                    "content_format": "plain_text",
                    "source_task_id": str(queue_task.id),
                },
            )
            _assert(
                response.status_code == 201,
                f"create inbox deliverable failed: {response.status_code}",
            )
            inbox_deliverables.append(response.json())

        request_changes_response = client.post(
            "/approvals",
            json={
                "deliverable_id": inbox_deliverables[0]["id"],
                "requester_role_code": "architect",
                "request_note": "请确认设计稿边界和交互说明。",
                "due_in_hours": 24,
            },
        )
        reject_response = client.post(
            "/approvals",
            json={
                "deliverable_id": inbox_deliverables[1]["id"],
                "requester_role_code": "architect",
                "request_note": "请确认代码计划的实现顺序。",
                "due_in_hours": 24,
            },
        )
        overdue_response = client.post(
            "/approvals",
            json={
                "deliverable_id": inbox_deliverables[2]["id"],
                "requester_role_code": "architect",
                "request_note": "这个审批项会立即进入超时状态。",
                "due_in_hours": 0,
            },
        )

        _assert(request_changes_response.status_code == 201, "request_changes approval should be created")
        _assert(reject_response.status_code == 201, "reject approval should be created")
        _assert(overdue_response.status_code == 201, "overdue approval should be created")

        request_changes_approval = request_changes_response.json()
        reject_approval = reject_response.json()
        overdue_approval = overdue_response.json()

        request_changes_action_response = client.post(
            f"/approvals/{request_changes_approval['id']}/actions",
            json={
                "action": "request_changes",
                "actor_name": "老板",
                "summary": "请补充交互边界和异常流程说明。",
                "comment": "设计稿主流程已清晰，但补充信息还不够。",
                "highlighted_risks": ["缺少异常流程", "接口状态说明不足"],
                "requested_changes": ["补充异常流程图", "明确接口回退策略"],
            },
        )
        reject_action_response = client.post(
            f"/approvals/{reject_approval['id']}/actions",
            json={
                "action": "reject",
                "actor_name": "老板",
                "summary": "当前代码计划拆分粒度不合适，暂不接受。",
                "comment": "请先重做模块边界和联调顺序。",
                "requested_changes": ["重排实现顺序"],
            },
        )
        _assert(
            request_changes_action_response.status_code == 200,
            f"request_changes action failed: {request_changes_action_response.status_code}",
        )
        _assert(
            reject_action_response.status_code == 200,
            f"reject action failed: {reject_action_response.status_code}",
        )

        inbox_response = client.get(f"/approvals/projects/{queue_project.id}")
        _assert(
            inbox_response.status_code == 200,
            f"project inbox failed: {inbox_response.status_code}",
        )
        inbox_payload = inbox_response.json()

        request_changes_detail_response = client.get(f"/approvals/{request_changes_approval['id']}")
        reject_detail_response = client.get(f"/approvals/{reject_approval['id']}")
        overdue_detail_response = client.get(f"/approvals/{overdue_approval['id']}")

        _assert(request_changes_detail_response.status_code == 200, "request_changes detail should load")
        _assert(reject_detail_response.status_code == 200, "reject detail should load")
        _assert(overdue_detail_response.status_code == 200, "overdue detail should load")

        request_changes_detail = request_changes_detail_response.json()
        reject_detail = reject_detail_response.json()
        overdue_detail = overdue_detail_response.json()

    _assert(
        inbox_payload["total_requests"] == 3,
        "project inbox should contain three approval requests",
    )
    _assert(
        inbox_payload["pending_requests"] == 1,
        "project inbox should keep one pending approval",
    )
    _assert(
        inbox_payload["overdue_requests"] == 1,
        "project inbox should surface one overdue approval",
    )
    _assert(
        inbox_payload["completed_requests"] == 2,
        "project inbox should surface two completed approval decisions",
    )
    _assert(
        request_changes_detail["status"] == "changes_requested",
        "request_changes action should update approval status",
    )
    _assert(
        request_changes_detail["decisions"][0]["requested_changes"] == ["补充异常流程图", "明确接口回退策略"],
        "request_changes detail should keep structured requested changes",
    )
    _assert(
        request_changes_detail["decisions"][0]["highlighted_risks"] == ["缺少异常流程", "接口状态说明不足"],
        "request_changes detail should keep structured highlighted risks",
    )
    _assert(
        reject_detail["status"] == "rejected",
        "reject action should update approval status",
    )
    _assert(
        overdue_detail["status"] == "pending_approval" and overdue_detail["overdue"] is True,
        "pending approval should be surfaced as overdue",
    )

    report = {
        "stage_gate": {
            "project_id": str(gate_project.id),
            "blocked_before_approval": blocked_advance["advanced"],
            "released_after_approval": released_advance["advanced"],
            "current_stage": released_advance["current_stage"],
        },
        "approval_inbox": {
            "project_id": str(queue_project.id),
            "total_requests": inbox_payload["total_requests"],
            "pending_requests": inbox_payload["pending_requests"],
            "overdue_requests": inbox_payload["overdue_requests"],
            "completed_requests": inbox_payload["completed_requests"],
            "statuses": {
                item["deliverable_title"]: item["status"] for item in inbox_payload["approvals"]
            },
        },
        "replay_samples": {
            "request_changes": request_changes_detail["decisions"][0],
            "reject": reject_detail["decisions"][0],
            "overdue": {
                "deliverable_title": overdue_detail["deliverable_title"],
                "status": overdue_detail["status"],
                "overdue": overdue_detail["overdue"],
            },
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
