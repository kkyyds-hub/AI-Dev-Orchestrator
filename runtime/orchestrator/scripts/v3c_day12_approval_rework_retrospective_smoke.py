"""V3-C Day12 smoke checks for approval redo history and project retrospective."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v3-day12-approval-retrospective-smoke"


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


def _create_project_task_fixture(*, name: str, summary: str):
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
                title=f"{name} 核心交付任务",
                input_summary="围绕审批驳回重做链路，补齐 PRD 与复盘收口所需信息。",
                priority=TaskPriority.HIGH,
                owner_role_code=ProjectRoleCode.PRODUCT_MANAGER,
                downstream_role_code=ProjectRoleCode.ARCHITECT,
            )
        )
        task_repository.set_status(task.id, TaskStatus.COMPLETED)
        session.commit()

    return project, task


def _create_failed_run_review(task_id):
    from app.core.db import SessionLocal
    from app.domain.project_role import ProjectRoleCode
    from app.domain.run import RunFailureCategory, RunStatus
    from app.domain.task import TaskStatus
    from app.repositories.failure_review_repository import FailureReviewRepository
    from app.repositories.run_repository import RunRepository
    from app.repositories.task_repository import TaskRepository
    from app.services.failure_review_service import FailureReviewService
    from app.services.run_logging_service import RunLoggingService

    with SessionLocal() as session:
        task_repository = TaskRepository(session)
        run_repository = RunRepository(session)
        run_logging_service = RunLoggingService()
        failure_review_service = FailureReviewService(
            failure_review_repository=FailureReviewRepository(),
            run_logging_service=run_logging_service,
        )

        task_repository.set_status(task_id, TaskStatus.FAILED)
        run = run_repository.create_running_run(
            task_id=task_id,
            route_reason="Approval rework uncovered execution-side gaps that still need fixing.",
            owner_role_code=ProjectRoleCode.ARCHITECT,
            upstream_role_code=ProjectRoleCode.PRODUCT_MANAGER,
            downstream_role_code=ProjectRoleCode.ENGINEER,
            handoff_reason="Rework version still lacked implementation details.",
            dispatch_status="handoff_pending",
        )
        log_path = run_logging_service.initialize_run_log(task_id=task_id, run_id=run.id)
        run_repository.set_log_path(run.id, log_path)
        run_logging_service.append_event(
            log_path=log_path,
            event="task_routed",
            message="Task was routed back for one more execution attempt.",
            data={"reason": "approval_rework"},
        )
        run_logging_service.append_event(
            log_path=log_path,
            event="execution_finished",
            level="error",
            message="Execution failed while implementing the latest approval feedback.",
            data={"exit_code": 1},
        )
        run_logging_service.append_event(
            log_path=log_path,
            event="run_finalized",
            level="error",
            message="Run finalized as failed after the approval-driven rework attempt.",
            data={"status": "failed"},
        )
        failed_run = run_repository.finish_run(
            run.id,
            status=RunStatus.FAILED,
            result_summary="Execution failed after the deliverable was sent back for rework.",
            failure_category=RunFailureCategory.EXECUTION_FAILED,
            quality_gate_passed=False,
        )
        task = task_repository.get_by_id(task_id)
        _assert(task is not None, "task should exist when creating a failure review")
        review = failure_review_service.ensure_review(task=task, run=failed_run)
        session.commit()

    _assert(review is not None, "failure review should be created for failed run")
    return failed_run, review


def main() -> None:
    """Exercise the Day12 redo / retrospective API surface end to end."""

    _prepare_env()

    from fastapi.testclient import TestClient

    from app.core.db import init_database
    from app.main import app

    init_database()

    project, task = _create_project_task_fixture(
        name="Day12 Approval Retrospective",
        summary="验证审批驳回后的重做链路，以及项目复盘如何收口审批与失败运行。",
    )

    with TestClient(app) as client:
        deliverable_response = client.post(
            "/deliverables",
            json={
                "project_id": str(project.id),
                "type": "prd",
                "title": "Day12 PRD",
                "stage": "planning",
                "created_by_role_code": "product_manager",
                "summary": "提交初版 PRD，准备进入老板审批。",
                "content": "# 背景\n- 需要验证审批驳回后的重做链路。\n",
                "content_format": "markdown",
                "source_task_id": str(task.id),
            },
        )
        _assert(
            deliverable_response.status_code == 201,
            f"create deliverable failed: {deliverable_response.status_code}",
        )
        deliverable = deliverable_response.json()

        approval_v1_response = client.post(
            "/approvals",
            json={
                "deliverable_id": deliverable["id"],
                "requester_role_code": "product_manager",
                "request_note": "请确认 PRD v1 是否可进入执行阶段。",
                "due_in_hours": 24,
            },
        )
        _assert(
            approval_v1_response.status_code == 201,
            f"create approval v1 failed: {approval_v1_response.status_code}",
        )
        approval_v1 = approval_v1_response.json()

        reject_response = client.post(
            f"/approvals/{approval_v1['id']}/actions",
            json={
                "action": "reject",
                "actor_name": "老板",
                "summary": "当前版本缺少执行边界与验收标准，先退回重做。",
                "comment": "先补齐里程碑、风险与通过标准，再重新提交。",
                "highlighted_risks": ["验收标准不完整"],
                "requested_changes": ["补齐验收标准", "补齐执行阶段边界"],
            },
        )
        _assert(
            reject_response.status_code == 200,
            f"reject approval failed: {reject_response.status_code}",
        )

        history_after_reject = client.get(f"/approvals/{approval_v1['id']}/history")
        _assert(
            history_after_reject.status_code == 200,
            f"history after reject failed: {history_after_reject.status_code}",
        )
        history_payload = history_after_reject.json()
        _assert(
            history_payload["rework_status"] == "rework_required",
            "history should mark the deliverable as requiring rework after rejection",
        )

        version_v2_response = client.post(
            f"/deliverables/{deliverable['id']}/versions",
            json={
                "author_role_code": "product_manager",
                "summary": "补齐执行边界、验收标准与里程碑后的重做版本。",
                "content": "# 目标\n- 补齐验收标准\n- 补齐执行边界\n",
                "content_format": "markdown",
                "source_task_id": str(task.id),
            },
        )
        _assert(
            version_v2_response.status_code == 200,
            f"submit v2 failed: {version_v2_response.status_code}",
        )

        history_after_rework = client.get(f"/approvals/{approval_v1['id']}/history")
        _assert(
            history_after_rework.status_code == 200,
            f"history after rework failed: {history_after_rework.status_code}",
        )
        history_after_rework_payload = history_after_rework.json()
        _assert(
            history_after_rework_payload["rework_status"] == "reworking",
            "history should mark the deliverable as reworking after a new version is submitted",
        )
        _assert(
            any(
                step["event_kind"] == "rework_version_submitted"
                for step in history_after_rework_payload["steps"]
            ),
            "history should contain a rework version step",
        )

        approval_v2_response = client.post(
            "/approvals",
            json={
                "deliverable_id": deliverable["id"],
                "requester_role_code": "product_manager",
                "request_note": "PRD v2 已按意见补齐，请重新审批。",
                "due_in_hours": 24,
            },
        )
        _assert(
            approval_v2_response.status_code == 201,
            f"create approval v2 failed: {approval_v2_response.status_code}",
        )
        approval_v2 = approval_v2_response.json()

        history_after_resubmission = client.get(f"/approvals/{approval_v2['id']}/history")
        _assert(
            history_after_resubmission.status_code == 200,
            f"history after resubmission failed: {history_after_resubmission.status_code}",
        )
        history_after_resubmission_payload = history_after_resubmission.json()
        _assert(
            history_after_resubmission_payload["rework_status"] == "resubmitted",
            "history should mark the deliverable as resubmitted while approval is pending",
        )

        approve_response = client.post(
            f"/approvals/{approval_v2['id']}/actions",
            json={
                "action": "approve",
                "actor_name": "老板",
                "summary": "返工后的版本已经补齐关键信息，可以进入执行阶段。",
                "comment": "批准进入下一阶段，并在复盘页保留这次返工链路。",
            },
        )
        _assert(
            approve_response.status_code == 200,
            f"approve approval v2 failed: {approve_response.status_code}",
        )

        history_after_approval = client.get(f"/approvals/{approval_v2['id']}/history")
        _assert(
            history_after_approval.status_code == 200,
            f"history after approval failed: {history_after_approval.status_code}",
        )
        final_history_payload = history_after_approval.json()
        _assert(
            final_history_payload["rework_status"] == "approved_after_rework",
            "history should mark the deliverable as approved after rework",
        )
        _assert(
            final_history_payload["negative_decision_count"] == 1,
            "history should preserve the rejected decision count",
        )

    failed_run, review = _create_failed_run_review(task.id)

    with TestClient(app) as client:
        retrospective_response = client.get(
            f"/approvals/projects/{project.id}/retrospective"
        )

    _assert(
        retrospective_response.status_code == 200,
        f"project retrospective failed: {retrospective_response.status_code}",
    )

    retrospective_payload = retrospective_response.json()
    _assert(
        retrospective_payload["summary"]["negative_approval_cycles"] >= 1,
        "retrospective should include at least one approval rework cycle",
    )
    _assert(
        retrospective_payload["summary"]["open_rework_cycles"] == 0,
        "retrospective should treat the approved rework cycle as closed",
    )
    _assert(
        retrospective_payload["summary"]["total_failure_reviews"] >= 1,
        "retrospective should include the stored failure review",
    )
    _assert(
        len(retrospective_payload["recent_failures"]) >= 1,
        "retrospective should surface recent failed runs",
    )

    report = {
        "project": {
            "id": str(project.id),
            "name": project.name,
        },
        "history": {
            "rework_status": final_history_payload["rework_status"],
            "negative_decision_count": final_history_payload["negative_decision_count"],
            "step_kinds": [step["event_kind"] for step in final_history_payload["steps"]],
        },
        "retrospective": {
            "summary": retrospective_payload["summary"],
            "approval_cycle_statuses": [
                item["status"] for item in retrospective_payload["approval_cycles"]
            ],
            "failure_cluster_keys": [
                item["cluster_key"] for item in retrospective_payload["failure_clusters"]
            ],
        },
        "failure_review": {
            "run_id": str(failed_run.id),
            "review_id": review.review_id,
            "conclusion": review.conclusion,
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
