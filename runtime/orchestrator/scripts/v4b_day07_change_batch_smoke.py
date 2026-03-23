"""V4-B Day07 smoke checks for change-batch execution preparation."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_ROOT = RUNTIME_ROOT / "tmp" / "v4-day07-change-batch-smoke"
SMOKE_RUNTIME_DATA_DIR = SMOKE_ROOT / "runtime-data"
SMOKE_ALLOWED_WORKSPACE_ROOT = SMOKE_ROOT / "allowed-workspaces"
SMOKE_REPOSITORY_ROOT = SMOKE_ALLOWED_WORKSPACE_ROOT / "day07-change-batch"


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

    (
        SMOKE_REPOSITORY_ROOT / "runtime" / "orchestrator" / "app" / "services"
    ).mkdir(parents=True, exist_ok=True)
    (
        SMOKE_REPOSITORY_ROOT / "runtime" / "orchestrator" / "app" / "api" / "routes"
    ).mkdir(parents=True, exist_ok=True)
    (
        SMOKE_REPOSITORY_ROOT / "runtime" / "orchestrator" / "app" / "domain"
    ).mkdir(parents=True, exist_ok=True)
    (
        SMOKE_REPOSITORY_ROOT / "apps" / "web" / "src" / "features" / "repositories"
    ).mkdir(parents=True, exist_ok=True)
    (
        SMOKE_REPOSITORY_ROOT / "apps" / "web" / "src" / "features" / "projects"
    ).mkdir(parents=True, exist_ok=True)
    (SMOKE_REPOSITORY_ROOT / "docs").mkdir(parents=True, exist_ok=True)
    (SMOKE_REPOSITORY_ROOT / "node_modules" / "fake").mkdir(parents=True, exist_ok=True)

    (
        SMOKE_REPOSITORY_ROOT
        / "runtime"
        / "orchestrator"
        / "app"
        / "domain"
        / "change_batch.py"
    ).write_text(
        "\n".join(
            [
                '"""Day07 smoke target domain."""',
                "",
                "class ChangeBatch:",
                "    status = 'preparing'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (
        SMOKE_REPOSITORY_ROOT
        / "runtime"
        / "orchestrator"
        / "app"
        / "services"
        / "change_batch_service.py"
    ).write_text(
        "\n".join(
            [
                '"""Day07 smoke target service."""',
                "",
                "class ChangeBatchService:",
                "    def build_batch(self):",
                "        return {'status': 'preparing'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (
        SMOKE_REPOSITORY_ROOT
        / "runtime"
        / "orchestrator"
        / "app"
        / "api"
        / "routes"
        / "repositories.py"
    ).write_text(
        "\n".join(
            [
                '"""Day07 smoke target route."""',
                "",
                "def register_change_batch_routes(router):",
                "    router.append('/repositories/projects/{project_id}/change-batches')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (
        SMOKE_REPOSITORY_ROOT
        / "apps"
        / "web"
        / "src"
        / "features"
        / "repositories"
        / "ChangeBatchBoard.tsx"
    ).write_text(
        "\n".join(
            [
                "export function ChangeBatchBoard() {",
                "  return <div>Day07 ChangeBatch board</div>;",
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (
        SMOKE_REPOSITORY_ROOT
        / "apps"
        / "web"
        / "src"
        / "features"
        / "projects"
        / "ChangePlanDrawer.tsx"
    ).write_text(
        "export const changePlanDrawer = true;\n",
        encoding="utf-8",
    )
    (SMOKE_REPOSITORY_ROOT / "docs" / "day07-plan.md").write_text(
        "# Day07\n\nChangeBatch execution-preparation smoke repo.\n",
        encoding="utf-8",
    )
    (SMOKE_REPOSITORY_ROOT / "node_modules" / "fake" / "ignored.js").write_text(
        "console.log('ignored');\n",
        encoding="utf-8",
    )

    _run_git("init")
    _run_git("checkout", "-b", "main")
    _run_git("config", "user.email", "EMAIL_REDACTED")
    _run_git("config", "user.name", "Smoke Bot")
    _run_git("add", ".")
    _run_git("commit", "-m", "init day07 smoke repo")
    _run_git("checkout", "-b", "feature/day07-change-batch")

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


def _create_deliverable(
    client: Any,
    *,
    project_id: str,
    task_id: str,
    title: str,
) -> Any:
    return _request_json(
        client,
        "POST",
        "/deliverables",
        expected_status=201,
        json_body={
            "project_id": project_id,
            "type": "code_plan",
            "title": title,
            "stage": "planning",
            "created_by_role_code": "engineer",
            "summary": f"{title} 摘要。",
            "content": f"# {title}\n\nDay07 smoke deliverable.",
            "content_format": "markdown",
            "source_task_id": task_id,
        },
    )


def _create_change_plan(
    client: Any,
    *,
    project_id: str,
    task_id: str,
    deliverable_id: str,
    title: str,
    intent_summary: str,
    target_files: list[dict[str, Any]],
) -> Any:
    return _request_json(
        client,
        "POST",
        f"/planning/projects/{project_id}/change-plans",
        expected_status=201,
        json_body={
            "task_id": task_id,
            "title": title,
            "primary_deliverable_id": deliverable_id,
            "related_deliverable_ids": [deliverable_id],
            "intent_summary": intent_summary,
            "source_summary": "Day07 smoke 将多个 ChangePlan 合并为一份执行准备批次。",
            "focus_terms": ["change batch", "execution prep", "day07"],
            "target_files": target_files,
            "expected_actions": [
                "汇总任务顺序",
                "标记文件重叠风险",
            ],
            "risk_notes": [
                "只做 Day07 批次准备",
                "不进入 Day08 风险预检",
            ],
            "verification_commands": [
                "python -m py_compile runtime/orchestrator/app/services/change_batch_service.py",
                "cmd /c npm run build",
            ],
        },
    )


def main() -> None:
    _prepare_env()

    from fastapi.testclient import TestClient

    from app.main import create_application

    app = create_application()

    with TestClient(app) as client:
        project = _request_json(
            client,
            "POST",
            "/projects",
            expected_status=201,
            json_body={
                "name": "Day07 ChangeBatch Project",
                "summary": "Merge multiple change plans into one execution-preparation batch.",
            },
        )
        _request_json(
            client,
            "PUT",
            f"/repositories/projects/{project['id']}",
            expected_status=200,
            json_body={
                "root_path": str(SMOKE_REPOSITORY_ROOT.resolve()),
                "display_name": "Day07 smoke repo",
                "default_base_branch": "main",
            },
        )

        task_backend = _request_json(
            client,
            "POST",
            "/tasks",
            expected_status=201,
            json_body={
                "project_id": project["id"],
                "title": "整理批次领域模型",
                "input_summary": "为 Day07 新增 ChangeBatch 领域模型与服务骨架。",
                "acceptance_criteria": [
                    "可创建 Day07 变更批次",
                    "批次状态初始为 preparing",
                ],
            },
        )
        task_route = _request_json(
            client,
            "POST",
            "/tasks",
            expected_status=201,
            json_body={
                "project_id": project["id"],
                "title": "接通仓库批次路由",
                "input_summary": "把 Day07 批次接口挂到 repositories 路由中。",
                "acceptance_criteria": [
                    "可列出与查看批次详情",
                    "同项目只保留一个活跃批次",
                ],
                "depends_on_task_ids": [task_backend["id"]],
            },
        )
        task_frontend = _request_json(
            client,
            "POST",
            "/tasks",
            expected_status=201,
            json_body={
                "project_id": project["id"],
                "title": "展示前端批次看板",
                "input_summary": "把批次摘要、任务顺序、依赖和重叠风险展示到仓库页。",
                "acceptance_criteria": [
                    "可展示批次摘要和时间线",
                    "可展示文件重叠风险",
                ],
                "depends_on_task_ids": [task_route["id"]],
            },
        )

        deliverable_backend = _create_deliverable(
            client,
            project_id=project["id"],
            task_id=task_backend["id"],
            title="Day07 批次领域模型交付件",
        )
        deliverable_route = _create_deliverable(
            client,
            project_id=project["id"],
            task_id=task_route["id"],
            title="Day07 批次路由交付件",
        )
        deliverable_frontend = _create_deliverable(
            client,
            project_id=project["id"],
            task_id=task_frontend["id"],
            title="Day07 批次前端交付件",
        )

        backend_plan = _create_change_plan(
            client,
            project_id=project["id"],
            task_id=task_backend["id"],
            deliverable_id=deliverable_backend["id"],
            title="Day07 后端批次准备",
            intent_summary="建立 ChangeBatch 模型与服务，冻结执行准备边界。",
            target_files=[
                {
                    "relative_path": "runtime/orchestrator/app/domain/change_batch.py",
                    "language": "python",
                    "file_type": "py",
                    "rationale": "新增 Day07 领域对象",
                    "match_reasons": ["day07", "domain"],
                },
                {
                    "relative_path": "runtime/orchestrator/app/services/change_batch_service.py",
                    "language": "python",
                    "file_type": "py",
                    "rationale": "汇总批次任务顺序",
                    "match_reasons": ["service", "batch"],
                },
            ],
        )
        route_plan = _create_change_plan(
            client,
            project_id=project["id"],
            task_id=task_route["id"],
            deliverable_id=deliverable_route["id"],
            title="Day07 仓库路由准备",
            intent_summary="把批次列表、详情和创建接口挂到 repositories 路由。",
            target_files=[
                {
                    "relative_path": "runtime/orchestrator/app/services/change_batch_service.py",
                    "language": "python",
                    "file_type": "py",
                    "rationale": "与服务层一起完成批次整理",
                    "match_reasons": ["service overlap"],
                },
                {
                    "relative_path": "runtime/orchestrator/app/api/routes/repositories.py",
                    "language": "python",
                    "file_type": "py",
                    "rationale": "接入 Day07 路由",
                    "match_reasons": ["route", "api"],
                },
            ],
        )
        frontend_plan = _create_change_plan(
            client,
            project_id=project["id"],
            task_id=task_frontend["id"],
            deliverable_id=deliverable_frontend["id"],
            title="Day07 前端看板准备",
            intent_summary="在仓库页展示批次摘要、任务顺序、依赖和时间线。",
            target_files=[
                {
                    "relative_path": "runtime/orchestrator/app/api/routes/repositories.py",
                    "language": "python",
                    "file_type": "py",
                    "rationale": "前端依赖批次详情接口",
                    "match_reasons": ["route overlap"],
                },
                {
                    "relative_path": "apps/web/src/features/repositories/ChangeBatchBoard.tsx",
                    "language": "typescript",
                    "file_type": "tsx",
                    "rationale": "新增 Day07 看板组件",
                    "match_reasons": ["frontend", "board"],
                },
            ],
        )

        created_batch = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project['id']}/change-batches",
            expected_status=200,
            json_body={
                "change_plan_ids": [
                    frontend_plan["id"],
                    route_plan["id"],
                    backend_plan["id"],
                ]
            },
        )
        _assert(
            created_batch["status"] == "preparing",
            "Day07 batches should start in preparing status.",
        )
        _assert(
            created_batch["active"] is True,
            "A newly created Day07 batch should be marked active.",
        )
        _assert(
            [item["task_id"] for item in created_batch["tasks"]]
            == [task_backend["id"], task_route["id"], task_frontend["id"]],
            "Day07 batch task order should respect dependency order, not request order.",
        )
        _assert(
            created_batch["tasks"][1]["dependencies"][0]["order_index"] == 1,
            "The route task should point back to the backend task as an in-batch dependency.",
        )
        _assert(
            created_batch["tasks"][2]["dependencies"][0]["order_index"] == 2,
            "The frontend task should point back to the route task as an in-batch dependency.",
        )

        overlap_paths = [item["relative_path"] for item in created_batch["overlap_files"]]
        _assert(
            "runtime/orchestrator/app/services/change_batch_service.py" in overlap_paths,
            "Day07 overlap detection should highlight shared service files.",
        )
        _assert(
            "runtime/orchestrator/app/api/routes/repositories.py" in overlap_paths,
            "Day07 overlap detection should highlight shared route files.",
        )
        _assert(
            created_batch["timeline"][0]["entry_type"] in {
                "change_batch_created",
                "change_plan_snapshot",
            },
            "Day07 detail should expose a local execution-preparation timeline.",
        )

        listed_batches = _request_json(
            client,
            "GET",
            f"/repositories/projects/{project['id']}/change-batches",
            expected_status=200,
        )
        _assert(
            len(listed_batches) == 1 and listed_batches[0]["id"] == created_batch["id"],
            "Project batch list should surface the created Day07 batch.",
        )
        _assert(
            listed_batches[0]["overlap_file_count"] == len(created_batch["overlap_files"]),
            "Summary overlap counts should match Day07 detail.",
        )

        detail = _request_json(
            client,
            "GET",
            f"/repositories/change-batches/{created_batch['id']}",
            expected_status=200,
        )
        _assert(
            detail["summary"] == created_batch["summary"],
            "Day07 batch detail should preserve the generated summary string.",
        )

        conflict_response = client.post(
            f"/repositories/projects/{project['id']}/change-batches",
            json={"change_plan_ids": [backend_plan["id"], route_plan["id"]]},
        )
        _assert(
            conflict_response.status_code == 409,
            "Day07 should prevent creating a second active change batch for the same project.",
        )

    report = {
        "project_id": project["id"],
        "change_batch_id": detail["id"],
        "status": detail["status"],
        "task_order": [item["task_title"] for item in detail["tasks"]],
        "overlap_files": [item["relative_path"] for item in detail["overlap_files"]],
        "timeline_entries": [item["label"] for item in detail["timeline"]],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
