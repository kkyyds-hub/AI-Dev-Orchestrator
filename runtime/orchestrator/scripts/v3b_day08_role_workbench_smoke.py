"""V3-B Day08 smoke checks for the role workbench and handoff timeline."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import shutil


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v3-day08-role-workbench-smoke"


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


async def _capture_role_handoff_event(run_logging_service, **kwargs):
    from app.services.event_stream_service import event_stream_service

    subscriber_id, queue = event_stream_service.subscribe()
    try:
        run_logging_service.append_role_handoff_event(**kwargs)
        while True:
            event = await asyncio.wait_for(queue.get(), timeout=1.0)
            if event.type == "role_handoff":
                return event
    finally:
        event_stream_service.unsubscribe(subscriber_id)


def main() -> None:
    """Exercise the Day08 role workbench snapshot and SSE handoff chain."""

    _prepare_env()

    from fastapi.testclient import TestClient

    from app.core.db import SessionLocal, init_database
    from app.domain.project import Project, ProjectStage
    from app.domain.project_role import ProjectRoleCode
    from app.domain.run import RunStatus
    from app.domain.task import Task, TaskHumanStatus, TaskPriority, TaskStatus
    from app.main import app
    from app.repositories.project_repository import ProjectRepository
    from app.repositories.run_repository import RunRepository
    from app.repositories.task_repository import TaskRepository
    from app.services.run_logging_service import RunLoggingService

    init_database()

    with SessionLocal() as session:
        project_repository = ProjectRepository(session)
        task_repository = TaskRepository(session)
        run_repository = RunRepository(session)
        run_logging_service = RunLoggingService()

        project = project_repository.create(
            Project(
                name="Day08 Role Workbench",
                summary="验证角色工作台能聚合角色列、运行中项、阻塞项与最近交接。",
                stage=ProjectStage.EXECUTION,
            )
        )

        pm_task = task_repository.create(
            Task(
                project_id=project.id,
                title="澄清角色工作台需求范围",
                input_summary="确认角色列需要展示当前任务、阻塞项、运行中项和最近交接。",
                priority=TaskPriority.HIGH,
                owner_role_code=ProjectRoleCode.PRODUCT_MANAGER,
                downstream_role_code=ProjectRoleCode.ARCHITECT,
            )
        )
        arch_task = task_repository.create(
            Task(
                project_id=project.id,
                title="整理角色工作台技术方案",
                input_summary="规划后端聚合接口、SSE 事件和前端分栏结构。",
                priority=TaskPriority.HIGH,
                owner_role_code=ProjectRoleCode.ARCHITECT,
                upstream_role_code=ProjectRoleCode.PRODUCT_MANAGER,
                downstream_role_code=ProjectRoleCode.ENGINEER,
            )
        )
        engineer_task = task_repository.create(
            Task(
                project_id=project.id,
                title="实现角色工作台页面",
                input_summary="落地角色列看板、交接时间线和任务/运行跳转。",
                priority=TaskPriority.URGENT,
                owner_role_code=ProjectRoleCode.ENGINEER,
                upstream_role_code=ProjectRoleCode.ARCHITECT,
                downstream_role_code=ProjectRoleCode.REVIEWER,
            )
        )
        reviewer_task = task_repository.create(
            Task(
                project_id=project.id,
                title="回归角色工作台链路",
                input_summary="验证角色列、SSE 和任务详情跳转是否联通。",
                priority=TaskPriority.NORMAL,
                owner_role_code=ProjectRoleCode.REVIEWER,
                upstream_role_code=ProjectRoleCode.ENGINEER,
                human_status=TaskHumanStatus.REQUESTED,
            )
        )

        task_repository.set_status(pm_task.id, TaskStatus.COMPLETED)
        task_repository.set_status(arch_task.id, TaskStatus.BLOCKED)
        task_repository.set_status(engineer_task.id, TaskStatus.RUNNING)
        task_repository.update_control_state(
            reviewer_task.id,
            status=TaskStatus.WAITING_HUMAN,
            human_status=TaskHumanStatus.REQUESTED,
        )

        arch_run = run_repository.create_running_run(
            task_id=arch_task.id,
            owner_role_code=ProjectRoleCode.ARCHITECT,
            upstream_role_code=ProjectRoleCode.PRODUCT_MANAGER,
            downstream_role_code=ProjectRoleCode.ENGINEER,
            dispatch_status="explicit_owner",
            handoff_reason="架构任务承接产品范围澄清结果。",
        )
        arch_log_path = run_logging_service.initialize_run_log(task_id=arch_task.id, run_id=arch_run.id)
        run_repository.set_log_path(arch_run.id, arch_log_path)
        run_logging_service.append_role_handoff_event(
            log_path=arch_log_path,
            project_id=project.id,
            owner_role_code=ProjectRoleCode.ARCHITECT,
            upstream_role_code=ProjectRoleCode.PRODUCT_MANAGER,
            downstream_role_code=ProjectRoleCode.ENGINEER,
            dispatch_status="explicit_owner",
            handoff_reason="架构师接力后输出方案，再交给工程实现。",
        )
        run_repository.finish_run(
            arch_run.id,
            status=RunStatus.CANCELLED,
            result_summary="方案已产出，但因依赖缺口暂时阻塞。",
        )

        engineer_run = run_repository.create_running_run(
            task_id=engineer_task.id,
            owner_role_code=ProjectRoleCode.ENGINEER,
            upstream_role_code=ProjectRoleCode.ARCHITECT,
            downstream_role_code=ProjectRoleCode.REVIEWER,
            dispatch_status="explicit_owner",
            handoff_reason="工程任务继续承接架构方案并准备交给评审。",
        )
        engineer_log_path = run_logging_service.initialize_run_log(
            task_id=engineer_task.id,
            run_id=engineer_run.id,
        )
        run_repository.set_log_path(engineer_run.id, engineer_log_path)
        captured_event = asyncio.run(
            _capture_role_handoff_event(
                run_logging_service,
                log_path=engineer_log_path,
                project_id=project.id,
                owner_role_code=ProjectRoleCode.ENGINEER,
                upstream_role_code=ProjectRoleCode.ARCHITECT,
                downstream_role_code=ProjectRoleCode.REVIEWER,
                dispatch_status="explicit_owner",
                handoff_reason="工程实现完成后需要交给评审者复核。",
            )
        )

        session.commit()

    with TestClient(app) as client:
        response = client.get(f"/console/role-workbench?project_id={project.id}")
        _assert(response.status_code == 200, f"role workbench failed: {response.status_code}")
        payload = response.json()

    _assert(captured_event.type == "role_handoff", "expected a role_handoff SSE event")
    _assert(
        captured_event.payload["project_id"] == str(project.id),
        "role_handoff SSE payload should include project_id",
    )
    _assert(
        captured_event.payload["owner_role_code"] == "engineer",
        "role_handoff SSE payload should keep the owner role",
    )

    _assert(payload["project_name"] == "Day08 Role Workbench", "unexpected project name")
    _assert(payload["total_roles"] == 4, f"expected 4 lanes, got {payload['total_roles']}")
    _assert(payload["total_tasks"] == 4, f"expected 4 tasks, got {payload['total_tasks']}")
    _assert(payload["active_tasks"] == 3, f"expected 3 active tasks, got {payload['active_tasks']}")
    _assert(payload["running_tasks"] == 1, f"expected 1 running task, got {payload['running_tasks']}")
    _assert(payload["blocked_tasks"] == 2, f"expected 2 blocked tasks, got {payload['blocked_tasks']}")
    _assert(
        payload["recent_handoff_count"] >= 2,
        f"expected at least 2 handoffs, got {payload['recent_handoff_count']}",
    )

    engineer_lane = next(
        (lane for lane in payload["lanes"] if lane["role_code"] == "engineer"),
        None,
    )
    architect_lane = next(
        (lane for lane in payload["lanes"] if lane["role_code"] == "architect"),
        None,
    )
    _assert(engineer_lane is not None, "engineer lane missing")
    _assert(architect_lane is not None, "architect lane missing")
    _assert(engineer_lane["running_task_count"] == 1, "engineer lane should have 1 running task")
    _assert(architect_lane["blocked_task_count"] == 1, "architect lane should have 1 blocked task")
    _assert(
        payload["recent_handoffs"][0]["owner_role_code"] in {"engineer", "architect"},
        "recent handoffs should surface role ownership",
    )

    report = {
        "project": payload["project_name"],
        "summary": {
            "total_roles": payload["total_roles"],
            "active_tasks": payload["active_tasks"],
            "running_tasks": payload["running_tasks"],
            "blocked_tasks": payload["blocked_tasks"],
            "recent_handoff_count": payload["recent_handoff_count"],
        },
        "lanes": [
            {
                "role_code": lane["role_code"],
                "current_task_count": lane["current_task_count"],
                "running_task_count": lane["running_task_count"],
                "blocked_task_count": lane["blocked_task_count"],
                "recent_handoff_count": lane["recent_handoff_count"],
            }
            for lane in payload["lanes"]
        ],
        "captured_sse": captured_event.payload,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
