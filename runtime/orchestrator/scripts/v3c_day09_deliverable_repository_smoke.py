"""V3-C Day09 smoke checks for the deliverable repository and version snapshots."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v3-day09-deliverable-repository-smoke"


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
    """Exercise the Day09 API surface end to end."""

    _prepare_env()

    from fastapi.testclient import TestClient

    from app.core.db import SessionLocal, init_database
    from app.domain.project import Project, ProjectStage
    from app.domain.project_role import ProjectRoleCode
    from app.domain.run import RunStatus
    from app.domain.task import Task, TaskPriority, TaskStatus
    from app.main import app
    from app.repositories.project_repository import ProjectRepository
    from app.repositories.run_repository import RunRepository
    from app.repositories.task_repository import TaskRepository

    init_database()

    with SessionLocal() as session:
        project_repository = ProjectRepository(session)
        task_repository = TaskRepository(session)
        run_repository = RunRepository(session)

        project = project_repository.create(
            Project(
                name="Day09 Deliverable Repository",
                summary="验证 PRD / 代码计划交付件、版本快照和任务运行回链。",
                stage=ProjectStage.PLANNING,
            )
        )
        task = task_repository.create(
            Task(
                project_id=project.id,
                title="整理项目 PRD 与代码计划",
                input_summary="产出项目 PRD、技术约束与代码计划，供老板查看交付件版本。",
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
            dispatch_status="explicit_owner",
            handoff_reason="先产出 PRD，再继续补技术拆分。",
        )
        run_repository.finish_run(
            run.id,
            status=RunStatus.SUCCEEDED,
            result_summary="PRD 初稿与技术约束整理完成。",
        )
        session.commit()

    with TestClient(app) as client:
        prd_response = client.post(
            "/deliverables",
            json={
                "project_id": str(project.id),
                "type": "prd",
                "title": "移动端改版 PRD",
                "stage": "planning",
                "created_by_role_code": "product_manager",
                "summary": "提交 PRD v1，明确业务目标、范围与验收口径。",
                "content": "# 背景\n- 统一改版首页与消息流入口。\n\n# 范围\n- 首页改版\n- 消息中心改版",
                "content_format": "markdown",
                "source_task_id": str(task.id),
                "source_run_id": str(run.id),
            },
        )
        _assert(prd_response.status_code == 201, f"create PRD failed: {prd_response.status_code}")
        prd_payload = prd_response.json()
        deliverable_id = prd_payload["id"]

        prd_v2_response = client.post(
            f"/deliverables/{deliverable_id}/versions",
            json={
                "author_role_code": "architect",
                "summary": "提交 PRD v2，补充架构边界、接口责任和风险说明。",
                "content": "## 架构补充\n- BFF 负责聚合消息流接口\n- 需要兼容旧版埋点\n- 风险：消息中心接口限流",
                "content_format": "markdown",
                "source_task_id": str(task.id),
            },
        )
        _assert(
            prd_v2_response.status_code == 200,
            f"append PRD version failed: {prd_v2_response.status_code}",
        )

        code_plan_response = client.post(
            "/deliverables",
            json={
                "project_id": str(project.id),
                "type": "code_plan",
                "title": "首轮代码计划",
                "stage": "planning",
                "created_by_role_code": "architect",
                "summary": "提交代码计划 v1，说明模块拆分、实现顺序与联调策略。",
                "content": "1. 搭建首页容器\n2. 抽离消息流数据层\n3. 回归埋点与权限",
                "content_format": "plain_text",
                "source_task_id": str(task.id),
            },
        )
        _assert(
            code_plan_response.status_code == 201,
            f"create code plan failed: {code_plan_response.status_code}",
        )

        snapshot_response = client.get(f"/deliverables/projects/{project.id}")
        _assert(
            snapshot_response.status_code == 200,
            f"project snapshot failed: {snapshot_response.status_code}",
        )
        snapshot_payload = snapshot_response.json()

        detail_response = client.get(f"/deliverables/{deliverable_id}")
        _assert(
            detail_response.status_code == 200,
            f"deliverable detail failed: {detail_response.status_code}",
        )
        detail_payload = detail_response.json()

        related_response = client.get(f"/deliverables/tasks/{task.id}")
        _assert(
            related_response.status_code == 200,
            f"task-related deliverables failed: {related_response.status_code}",
        )
        related_payload = related_response.json()

    _assert(snapshot_payload["total_deliverables"] == 2, "expected 2 deliverables")
    _assert(snapshot_payload["total_versions"] == 3, "expected 3 total versions")
    _assert(
        detail_payload["current_version_number"] == 2,
        "expected deliverable current version to be v2",
    )
    _assert(
        len(detail_payload["versions"]) == 2,
        "expected two versions in deliverable detail",
    )
    _assert(
        detail_payload["versions"][0]["version_number"] == 2,
        "deliverable detail should sort latest version first",
    )
    _assert(
        detail_payload["versions"][1]["source_run_id"] == str(run.id),
        "initial PRD version should keep the source run link",
    )
    _assert(
        len(related_payload) == 3,
        "task reverse lookup should include both PRD versions and the code plan",
    )

    report = {
        "project": {
            "id": str(project.id),
            "name": project.name,
        },
        "snapshot": {
            "total_deliverables": snapshot_payload["total_deliverables"],
            "total_versions": snapshot_payload["total_versions"],
            "titles": [item["title"] for item in snapshot_payload["deliverables"]],
        },
        "deliverable_detail": {
            "id": detail_payload["id"],
            "current_version_number": detail_payload["current_version_number"],
            "version_numbers": [item["version_number"] for item in detail_payload["versions"]],
        },
        "task_related_titles": [item["title"] for item in related_payload],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
