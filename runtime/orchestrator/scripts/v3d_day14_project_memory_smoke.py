"""V3-D Day14 smoke checks for project memory and retrievable experience."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v3-day14-project-memory-smoke"


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


def _create_task_fixture(*, project_id):
    from app.core.db import SessionLocal
    from app.domain.project_role import ProjectRoleCode
    from app.domain.task import Task, TaskPriority
    from app.repositories.task_repository import TaskRepository

    with SessionLocal() as session:
        task_repository = TaskRepository(session)
        approval_task = task_repository.create(
            Task(
                project_id=project_id,
                title="整理 PRD 审批结论",
                input_summary="把审批意见整理成下一轮执行入口，并沉淀 PRD 摘要。",
                priority=TaskPriority.HIGH,
                acceptance_criteria=[
                    "记录审批意见的核心结论",
                    "给出下一轮执行输入",
                ],
                owner_role_code=ProjectRoleCode.PRODUCT_MANAGER,
                downstream_role_code=ProjectRoleCode.ARCHITECT,
            )
        )
        failure_task = task_repository.create(
            Task(
                project_id=project_id,
                title="修复验证失败回路",
                input_summary="定位验证失败原因并形成可复用失败模式。",
                priority=TaskPriority.HIGH,
                acceptance_criteria=[
                    "明确失败模式",
                    "留下后续修复建议",
                ],
                owner_role_code=ProjectRoleCode.ENGINEER,
                upstream_role_code=ProjectRoleCode.ARCHITECT,
            )
        )

    return approval_task, failure_task


def _create_run_fixture(*, success_task, failure_task):
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

        success_run = run_repository.create_running_run(
            task_id=success_task.id,
            route_reason="审批结论已经明确，可以整理成下一轮执行输入。",
            owner_role_code=ProjectRoleCode.PRODUCT_MANAGER,
            downstream_role_code=ProjectRoleCode.ARCHITECT,
            dispatch_status="completed",
        )
        success_log_path = run_logging_service.initialize_run_log(
            task_id=success_task.id,
            run_id=success_run.id,
        )
        run_repository.set_log_path(success_run.id, success_log_path)
        run_logging_service.append_event(
            log_path=success_log_path,
            event="execution_finished",
            message="Execution summarized the approved PRD direction for downstream roles.",
        )
        run_logging_service.append_event(
            log_path=success_log_path,
            event="verification_finished",
            message="Verification confirmed the PRD summary can be reused as project memory.",
        )
        success_run = run_repository.finish_run(
            success_run.id,
            status=RunStatus.SUCCEEDED,
            result_summary="梳理出审批后的 PRD 关键结论，并补齐下一轮执行输入。",
            verification_summary="验证确认该结论可直接供架构和工程角色继续使用。",
            quality_gate_passed=True,
        )
        task_repository.set_status(success_task.id, TaskStatus.COMPLETED)

        failure_run = run_repository.create_running_run(
            task_id=failure_task.id,
            route_reason="验证失败后需要沉淀失败模式并指导下次修复。",
            owner_role_code=ProjectRoleCode.ENGINEER,
            upstream_role_code=ProjectRoleCode.ARCHITECT,
            dispatch_status="rework_pending",
        )
        failure_log_path = run_logging_service.initialize_run_log(
            task_id=failure_task.id,
            run_id=failure_run.id,
        )
        run_repository.set_log_path(failure_run.id, failure_log_path)
        run_logging_service.append_event(
            log_path=failure_log_path,
            event="execution_finished",
            level="error",
            message="Execution completed but the implementation still missed verification details.",
        )
        run_logging_service.append_event(
            log_path=failure_log_path,
            event="verification_finished",
            level="error",
            message="Verification failed because acceptance evidence was incomplete.",
        )
        failure_run = run_repository.finish_run(
            failure_run.id,
            status=RunStatus.FAILED,
            result_summary="实现已提交，但缺少验证证据，无法进入交付阶段。",
            verification_summary="验收证据不完整，导致验证失败并需要返工。",
            failure_category=RunFailureCategory.VERIFICATION_FAILED,
            quality_gate_passed=False,
        )
        failed_task = task_repository.set_status(failure_task.id, TaskStatus.FAILED)
        review = failure_review_service.ensure_review(task=failed_task, run=failure_run)
        session.commit()

    _assert(review is not None, "failed run should generate a Day12 review")
    return success_run, failure_run, review


def main() -> None:
    """Exercise the Day14 project-memory snapshot, search and context recall."""

    _prepare_env()

    from fastapi.testclient import TestClient

    from app.core.db import SessionLocal, init_database
    from app.main import app

    init_database()

    with TestClient(app) as client:
        project_response = client.post(
            "/projects",
            json={
                "name": "Day14 Project Memory Smoke",
                "summary": "验证项目记忆沉淀、最小检索和任务上下文召回能力。",
                "stage": "planning",
            },
        )
        _assert(
            project_response.status_code == 201,
            f"project create failed: {project_response.status_code}",
        )
        project = project_response.json()

    approval_task, failure_task = _create_task_fixture(project_id=project["id"])
    success_run, failure_run, review = _create_run_fixture(
        success_task=approval_task,
        failure_task=failure_task,
    )

    with TestClient(app) as client:
        deliverable_response = client.post(
            "/deliverables",
            json={
                "project_id": project["id"],
                "type": "prd",
                "title": "PRD 审批纪要",
                "stage": "planning",
                "created_by_role_code": "product_manager",
                "summary": "汇总审批后的关键结论与后续修改方向。",
                "content": "## 审批纪要\n- 结论：进入下一轮执行准备\n- 风险：验收证据还需要补齐",
                "source_task_id": str(approval_task.id),
                "source_run_id": str(success_run.id),
            },
        )
        _assert(
            deliverable_response.status_code == 201,
            f"deliverable create failed: {deliverable_response.status_code}",
        )
        deliverable = deliverable_response.json()

        approval_request_response = client.post(
            "/approvals",
            json={
                "deliverable_id": deliverable["id"],
                "requester_role_code": "product_manager",
                "request_note": "请确认 PRD 摘要和后续执行方向是否满足继续推进条件。",
                "due_in_hours": 24,
            },
        )
        _assert(
            approval_request_response.status_code == 201,
            f"create approval failed: {approval_request_response.status_code}",
        )
        approval = approval_request_response.json()

        approval_action_response = client.post(
            f"/approvals/{approval['id']}/actions",
            json={
                "action": "request_changes",
                "actor_name": "老板",
                "summary": "结论可用，但需要把验收证据补齐后再进入执行。",
                "comment": "请补充验证证据与风险说明，再重新提交审批。",
                "highlighted_risks": ["验收证据缺失"],
                "requested_changes": ["补充验证证据", "说明失败回路的修复计划"],
            },
        )
        _assert(
            approval_action_response.status_code == 200,
            f"apply approval action failed: {approval_action_response.status_code}",
        )

        snapshot_response = client.get(f"/projects/{project['id']}/memory")
        search_response = client.get(
            f"/projects/{project['id']}/memory/search",
            params={"q": "审批 证据", "limit": 6},
        )
        context_response = client.get(
            f"/projects/{project['id']}/memory/context",
            params={"task_id": str(approval_task.id), "limit": 3},
        )

    _assert(snapshot_response.status_code == 200, "project memory snapshot should succeed")
    _assert(search_response.status_code == 200, "project memory search should succeed")
    _assert(context_response.status_code == 200, "project memory context preview should succeed")

    snapshot_payload = snapshot_response.json()
    counts_by_type = {
        item["memory_type"]: item["count"] for item in snapshot_payload["counts"]
    }
    for expected_type in [
        "conclusion",
        "failure_pattern",
        "approval_feedback",
        "deliverable_summary",
    ]:
        _assert(
            counts_by_type.get(expected_type, 0) >= 1,
            f"snapshot should include at least one {expected_type} memory",
        )

    search_payload = search_response.json()
    _assert(
        search_payload["total_matches"] >= 1,
        "memory search should return at least one hit",
    )
    _assert(
        any(hit["item"]["approval_id"] == approval["id"] for hit in search_payload["hits"]),
        "search should expose approval-derived memories",
    )

    context_payload = context_response.json()
    _assert(
        context_payload["memory_count"] >= 1,
        "context preview should recall at least one memory item",
    )

    from app.repositories.approval_repository import ApprovalRepository
    from app.repositories.deliverable_repository import DeliverableRepository
    from app.repositories.failure_review_repository import FailureReviewRepository
    from app.repositories.project_repository import ProjectRepository
    from app.repositories.run_repository import RunRepository
    from app.repositories.task_repository import TaskRepository
    from app.services.context_builder_service import ContextBuilderService
    from app.services.project_memory_service import ProjectMemoryService
    from app.services.task_readiness_service import TaskReadinessService
    from app.services.failure_review_service import FailureReviewService
    from app.services.run_logging_service import RunLoggingService

    with SessionLocal() as session:
        task_repository = TaskRepository(session)
        run_repository = RunRepository(session)
        project_memory_service = ProjectMemoryService(
            project_repository=ProjectRepository(session),
            task_repository=task_repository,
            run_repository=run_repository,
            deliverable_repository=DeliverableRepository(session),
            approval_repository=ApprovalRepository(session),
            failure_review_service=FailureReviewService(
                failure_review_repository=FailureReviewRepository(),
                run_logging_service=RunLoggingService(),
            ),
        )
        context_builder_service = ContextBuilderService(
            run_repository=run_repository,
            task_readiness_service=TaskReadinessService(
                task_repository=task_repository,
                run_repository=run_repository,
            ),
            project_memory_service=project_memory_service,
        )
        approval_task_fresh = task_repository.get_by_id(approval_task.id)
        _assert(approval_task_fresh is not None, "approval task should still exist")
        context_package = context_builder_service.build_context_package(
            task=approval_task_fresh,
            include_project_memory=True,
            project_memory_limit=3,
        )
        snapshot = project_memory_service.get_project_memory_snapshot(
            project_id=approval_task_fresh.project_id,
        )

    _assert(snapshot is not None, "project memory snapshot should be available in service")
    _assert(snapshot.storage_path is not None, "project memory snapshot should be persisted")
    _assert(
        (SMOKE_RUNTIME_DATA_DIR / snapshot.storage_path).exists(),
        "project memory snapshot file should be persisted under runtime data",
    )
    _assert(
        "Project memory:" in context_package.context_summary,
        "context summary should include recalled project memory when explicitly enabled",
    )

    report = {
        "project": {
            "id": project["id"],
            "name": project["name"],
        },
        "memory_snapshot": {
            "total_memories": snapshot_payload["total_memories"],
            "counts": counts_by_type,
            "latest_titles": [item["title"] for item in snapshot_payload["latest_items"][:4]],
        },
        "search": {
            "query": search_payload["query"],
            "total_matches": search_payload["total_matches"],
            "matched_titles": [hit["item"]["title"] for hit in search_payload["hits"][:3]],
        },
        "context": {
            "memory_count": context_payload["memory_count"],
            "context_summary": context_payload["context_summary"],
        },
        "review": {
            "run_id": str(failure_run.id),
            "review_id": review.review_id,
            "conclusion": review.conclusion,
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
