"""V3-C Day11 smoke checks for the project timeline and deliverable diff view."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v3-day11-project-timeline-smoke"


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


def main() -> None:
    """Exercise the Day11 API surface end to end."""

    _prepare_env()

    from fastapi.testclient import TestClient

    from app.core.db import SessionLocal, init_database
    from app.domain.project import (
        Project,
        ProjectStage,
        ProjectStageHistoryEntry,
        ProjectStageHistoryOutcome,
    )
    from app.domain.project_role import ProjectRoleCode
    from app.domain.run import RunStatus
    from app.domain.task import Task, TaskPriority, TaskStatus
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
                name="Day11 Project Timeline",
                summary="验证项目级时间线聚合阶段推进、交付件版本、审批动作、角色交接与运行决策。",
                stage=ProjectStage.PLANNING,
            )
        )
        task = task_repository.create(
            Task(
                project_id=project.id,
                title="整理 PRD 与执行计划",
                input_summary="输出 PRD v1 / v2，提交审批，并记录角色交接与执行结果。",
                priority=TaskPriority.HIGH,
                owner_role_code=ProjectRoleCode.PRODUCT_MANAGER,
                downstream_role_code=ProjectRoleCode.ARCHITECT,
            )
        )
        task_repository.set_status(task.id, TaskStatus.COMPLETED)

        run = run_repository.create_running_run(
            task_id=task.id,
            owner_role_code=ProjectRoleCode.PRODUCT_MANAGER,
            downstream_role_code=ProjectRoleCode.ARCHITECT,
            dispatch_status="role_handoff",
            handoff_reason="产品经理先交付 PRD，再由架构师补齐执行计划与技术边界。",
        )
        log_path = run_logging_service.initialize_run_log(task_id=task.id, run_id=run.id)
        run = run_repository.set_log_path(run.id, log_path)

        run_logging_service.append_event(
            log_path=log_path,
            event="task_routed",
            message="任务进入规划阶段，准备生成 PRD 与执行计划。",
            data={"task_id": str(task.id), "project_id": str(project.id)},
        )
        run_logging_service.append_role_handoff_event(
            log_path=log_path,
            project_id=project.id,
            owner_role_code=ProjectRoleCode.PRODUCT_MANAGER,
            upstream_role_code=None,
            downstream_role_code=ProjectRoleCode.ARCHITECT,
            dispatch_status="role_handoff",
            handoff_reason="产品经理提交 PRD 初稿后，交由架构师补齐执行计划。",
        )
        run_logging_service.append_event(
            log_path=log_path,
            event="execution_finished",
            message="产出了 PRD v2，并补齐了执行计划。",
            data={"result_summary": "PRD 与执行计划准备完成。"},
        )
        run_logging_service.append_event(
            log_path=log_path,
            event="verification_finished",
            message="关键交付件通过最小自检，可以进入审批。",
            data={"quality_gate_passed": True},
        )
        run_repository.finish_run(
            run.id,
            status=RunStatus.SUCCEEDED,
            result_summary="PRD v2 与执行计划已提交，等待老板审批。",
            verification_mode="checklist",
            verification_template="timeline-smoke",
            verification_summary="关键交付件已完成自检。",
            quality_gate_passed=True,
        )
        run_logging_service.append_event(
            log_path=log_path,
            event="run_finalized",
            message="本轮运行已收口，准备发起审批。",
            data={"run_status": "succeeded", "task_status": "completed"},
        )
        session.commit()

    with TestClient(app) as client:
        deliverable_v1_response = client.post(
            "/deliverables",
            json={
                "project_id": str(project.id),
                "type": "prd",
                "title": "项目 PRD",
                "stage": "planning",
                "created_by_role_code": "product_manager",
                "summary": "提交 PRD v1，明确目标、范围和关键里程碑。",
                "content": "# 目标\n- 上线新版项目时间线\n\n# 范围\n- 汇总阶段推进\n- 汇总审批与交付件",
                "content_format": "markdown",
                "source_task_id": str(task.id),
                "source_run_id": str(run.id),
            },
        )
        _assert(
            deliverable_v1_response.status_code == 201,
            f"create deliverable failed: {deliverable_v1_response.status_code}",
        )
        deliverable_payload = deliverable_v1_response.json()
        deliverable_id = deliverable_payload["id"]

        deliverable_v2_response = client.post(
            f"/deliverables/{deliverable_id}/versions",
            json={
                "author_role_code": "architect",
                "summary": "提交 PRD v2，补齐技术边界、审批入口和交付件对比说明。",
                "content": "# 目标\n- 上线新版项目时间线\n- 提供交付件版本对比\n\n# 范围\n- 汇总阶段推进\n- 汇总审批与交付件\n- 新增版本 Diff 视图",
                "content_format": "markdown",
                "source_task_id": str(task.id),
                "source_run_id": str(run.id),
            },
        )
        _assert(
            deliverable_v2_response.status_code == 200,
            f"append deliverable version failed: {deliverable_v2_response.status_code}",
        )

        approval_request_response = client.post(
            "/approvals",
            json={
                "deliverable_id": deliverable_id,
                "requester_role_code": "product_manager",
                "request_note": "请确认 PRD v2 与版本对比视图是否可以进入执行阶段。",
                "due_in_hours": 24,
            },
        )
        _assert(
            approval_request_response.status_code == 201,
            f"create approval failed: {approval_request_response.status_code}",
        )
        approval_payload = approval_request_response.json()

        approval_action_response = client.post(
            f"/approvals/{approval_payload['id']}/actions",
            json={
                "action": "approve",
                "actor_name": "老板",
                "summary": "允许进入执行阶段，继续推进实现与联调。",
                "comment": "时间线视角清晰，Diff 视图满足最小可用要求。",
            },
        )
        _assert(
            approval_action_response.status_code == 200,
            f"apply approval action failed: {approval_action_response.status_code}",
        )

    with SessionLocal() as session:
        project_repository = ProjectRepository(session)
        refreshed_project = project_repository.get_by_id(project.id)
        _assert(refreshed_project is not None, "project should still exist")
        updated_project = project_repository.update_stage_state(
            project.id,
            stage=ProjectStage.EXECUTION,
            stage_history=[
                *refreshed_project.stage_history,
                ProjectStageHistoryEntry(
                    from_stage=ProjectStage.PLANNING,
                    to_stage=ProjectStage.EXECUTION,
                    outcome=ProjectStageHistoryOutcome.APPLIED,
                    note="PRD 审批通过后进入执行阶段。",
                ),
            ],
        )
        session.commit()

    with TestClient(app) as client:
        timeline_response = client.get(f"/projects/{project.id}/timeline")
        compare_response = client.get(
            f"/deliverables/{deliverable_id}/compare",
            params={"base_version": 1, "target_version": 2},
        )

    _assert(
        timeline_response.status_code == 200,
        f"project timeline failed: {timeline_response.status_code}",
    )
    _assert(
        compare_response.status_code == 200,
        f"deliverable compare failed: {compare_response.status_code}",
    )

    timeline_payload = timeline_response.json()
    compare_payload = compare_response.json()
    event_type_counts = {
        item["event_type"]: item["count"]
        for item in timeline_payload["event_type_counts"]
    }

    for expected_event_type in [
        "stage",
        "deliverable",
        "approval",
        "role_handoff",
        "decision",
    ]:
        _assert(
            event_type_counts.get(expected_event_type, 0) > 0,
            f"missing timeline events for {expected_event_type}",
        )

    _assert(
        any(
            event["approval_id"] == approval_payload["id"]
            for event in timeline_payload["events"]
        ),
        "timeline should include approval events",
    )
    _assert(
        any(
            event["run_id"] == str(run.id) and event["event_type"] == "role_handoff"
            for event in timeline_payload["events"]
        ),
        "timeline should include role handoff events",
    )
    _assert(
        compare_payload["base_version"]["version_number"] == 1
        and compare_payload["target_version"]["version_number"] == 2,
        "compare endpoint should keep the requested version pair",
    )
    _assert(
        compare_payload["changed_block_count"] >= 1,
        "compare endpoint should detect at least one changed block",
    )

    report = {
        "project": {
            "id": str(project.id),
            "name": project.name,
            "stage_after_update": updated_project.stage.value,
        },
        "timeline": {
            "total_events": timeline_payload["total_events"],
            "event_type_counts": event_type_counts,
            "first_five_titles": [
                item["title"] for item in timeline_payload["events"][:5]
            ],
        },
        "deliverable_compare": {
            "deliverable_id": deliverable_id,
            "base_version": compare_payload["base_version"]["version_number"],
            "target_version": compare_payload["target_version"]["version_number"],
            "added_line_count": compare_payload["added_line_count"],
            "removed_line_count": compare_payload["removed_line_count"],
            "changed_block_count": compare_payload["changed_block_count"],
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
