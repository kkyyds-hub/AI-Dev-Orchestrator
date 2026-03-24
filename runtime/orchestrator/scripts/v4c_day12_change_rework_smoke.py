"""V4-C Day12 smoke checks for change rework closure and retrospective linking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_ROOT = RUNTIME_ROOT / "tmp" / "v4-day12-change-rework-smoke"
SMOKE_RUNTIME_DATA_DIR = SMOKE_ROOT / "runtime-data"
SMOKE_ALLOWED_WORKSPACE_ROOT = SMOKE_ROOT / "allowed-workspaces"
SMOKE_REPOSITORY_ROOT = SMOKE_ALLOWED_WORKSPACE_ROOT / "day12-change-rework"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _remove_readonly(func: Any, path: str, _: Any) -> None:
    Path(path).chmod(stat.S_IWRITE)
    func(path)


def _write_file(relative_path: str, content: str) -> None:
    file_path = SMOKE_REPOSITORY_ROOT / Path(relative_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


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

    _write_file("README.md", "# Day12 Smoke Repo\n")
    _write_file(
        ".gitignore",
        "node_modules/\n.tmp/\n",
    )
    _write_file(
        "runtime/orchestrator/app/services/change_rework_service.py",
        '"""day12 smoke placeholder"""\n',
    )
    _write_file(
        "apps/web/src/features/projects/ProjectTimelinePage.tsx",
        "export function ProjectTimelinePage() { return null; }\n",
    )

    _run_git("init")
    _run_git("checkout", "-b", "main")
    _run_git("config", "user.email", "EMAIL_REDACTED")
    _run_git("config", "user.name", "Smoke Bot")
    _run_git("add", ".")
    _run_git("commit", "-m", "init day12 smoke repo")

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
                "name": "Day12 回退重做项目",
                "summary": "验证回退重做链路与仓库复盘收口。",
            },
        )
        _request_json(
            client,
            "PUT",
            f"/repositories/projects/{project['id']}",
            expected_status=200,
            json_body={
                "root_path": str(SMOKE_REPOSITORY_ROOT.resolve()),
                "display_name": "Day12 smoke repo",
                "default_base_branch": "main",
            },
        )

        baseline = _request_json(
            client,
            "GET",
            f"/repositories/projects/{project['id']}/verification-baseline",
            expected_status=200,
        )
        template_ids_by_category = {
            item["category"]: item["id"] for item in baseline["templates"]
        }

        task = _request_json(
            client,
            "POST",
            "/tasks",
            expected_status=201,
            json_body={
                "project_id": project["id"],
                "title": "Day12 重做闭环任务",
                "input_summary": "补齐回退重做闭环与仓库复盘收口。",
                "acceptance_criteria": [
                    "失败可追溯",
                    "保留证据包与驳回原因关联",
                ],
            },
        )
        task_aux = _request_json(
            client,
            "POST",
            "/tasks",
            expected_status=201,
            json_body={
                "project_id": project["id"],
                "title": "Day12 配套前端任务",
                "input_summary": "补齐 Day12 时间线页面入口。",
                "acceptance_criteria": ["保持 Day12 范围收口"],
            },
        )
        deliverable = _request_json(
            client,
            "POST",
            "/deliverables",
            expected_status=201,
            json_body={
                "project_id": project["id"],
                "type": "code_plan",
                "title": "Day12 交付件",
                "stage": "planning",
                "created_by_role_code": "engineer",
                "summary": "初版 Day12 交付件。",
                "content": "# Day12\n\n初版交付件。\n",
                "content_format": "markdown",
                "source_task_id": task["id"],
            },
        )
        deliverable_aux = _request_json(
            client,
            "POST",
            "/deliverables",
            expected_status=201,
            json_body={
                "project_id": project["id"],
                "type": "code_plan",
                "title": "Day12 辅助交付件",
                "stage": "planning",
                "created_by_role_code": "engineer",
                "summary": "辅助计划交付件。",
                "content": "# Day12\n\n辅助交付件。\n",
                "content_format": "markdown",
                "source_task_id": task_aux["id"],
            },
        )
        change_plan = _request_json(
            client,
            "POST",
            f"/planning/projects/{project['id']}/change-plans",
            expected_status=201,
            json_body={
                "task_id": task["id"],
                "title": "Day12 重做计划",
                "primary_deliverable_id": deliverable["id"],
                "related_deliverable_ids": [deliverable["id"]],
                "intent_summary": "构建 Day12 回退重做链路。",
                "source_summary": "来自 Day12 冻结计划。",
                "focus_terms": ["rework", "rollback", "retrospective"],
                "target_files": [
                    {
                        "relative_path": "runtime/orchestrator/app/services/change_rework_service.py",
                        "language": "Python",
                        "file_type": ".py",
                        "rationale": "新增 Day12 回退重做聚合服务",
                        "match_reasons": ["day12", "service"],
                    }
                ],
                "expected_actions": [
                    "汇总计划到重做全链路",
                    "保留证据包关联",
                ],
                "risk_notes": [
                    "不进入 Day13 提交候选与放行",
                ],
                "verification_commands": [
                    "python -m py_compile runtime/orchestrator/app/services/change_rework_service.py",
                ],
                "verification_template_ids": [template_ids_by_category["build"]],
            },
        )
        change_plan_aux = _request_json(
            client,
            "POST",
            f"/planning/projects/{project['id']}/change-plans",
            expected_status=201,
            json_body={
                "task_id": task_aux["id"],
                "title": "Day12 时间线收口计划",
                "primary_deliverable_id": deliverable_aux["id"],
                "related_deliverable_ids": [deliverable_aux["id"]],
                "intent_summary": "补齐 Day12 时间线与重做视图接线。",
                "source_summary": "来自 Day12 UI 收口。",
                "focus_terms": ["timeline", "change-rework"],
                "target_files": [
                    {
                        "relative_path": "apps/web/src/features/projects/ProjectTimelinePage.tsx",
                        "language": "TypeScript",
                        "file_type": ".tsx",
                        "rationale": "接入 Day12 回退重做面板",
                        "match_reasons": ["day12", "ui"],
                    }
                ],
                "expected_actions": ["时间线页面接入重做链路面板"],
                "risk_notes": ["不扩展到 Day13+ 行为"],
                "verification_commands": ["cmd /c echo day12-ui"],
                "verification_template_ids": [template_ids_by_category["typecheck"]],
            },
        )
        change_batch = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project['id']}/change-batches",
            expected_status=200,
            json_body={
                "title": "Day12 重做批次",
                "change_plan_ids": [change_plan["id"], change_plan_aux["id"]],
            },
        )

        _request_json(
            client,
            "POST",
            f"/repositories/change-batches/{change_batch['id']}/preflight",
            expected_status=200,
            json_body={
                "candidate_commands": ["git commit -m day12-smoke"],
            },
        )
        _request_json(
            client,
            "POST",
            f"/approvals/repository-preflight/{change_batch['id']}/actions",
            expected_status=200,
            json_body={
                "action": "reject",
                "actor_name": "老板",
                "summary": "当前批次涉及高风险写操作，先回退重做。",
                "comment": "Day12 只允许显式回退重做，不放行真实 Git 写入。",
                "highlighted_risks": ["命中 git commit 风险命令"],
            },
        )

        _request_json(
            client,
            "POST",
            "/runs/verification",
            expected_status=201,
            json_body={
                "project_id": project["id"],
                "change_plan_id": change_plan["id"],
                "change_batch_id": change_batch["id"],
                "verification_template_id": template_ids_by_category["build"],
                "status": "failed",
                "failure_category": "command_failed",
                "duration_seconds": 8.2,
                "output_summary": "Day12 验证失败：回退策略不完整。",
            },
        )

        approval = _request_json(
            client,
            "POST",
            "/approvals",
            expected_status=201,
            json_body={
                "deliverable_id": deliverable["id"],
                "requester_role_code": "product_manager",
                "request_note": "请审核 Day12 回退重做链路是否完整。",
                "due_in_hours": 8,
            },
        )
        _request_json(
            client,
            "POST",
            f"/approvals/{approval['id']}/actions",
            expected_status=200,
            json_body={
                "action": "request_changes",
                "actor_name": "老板",
                "summary": "回退动作与证据包关联不完整，需要重做。",
                "comment": "请把批次、证据包、驳回原因串成可追溯链路。",
                "highlighted_risks": ["证据包关联缺失"],
                "requested_changes": ["补齐批次-证据包关联", "补齐回退步骤记录"],
            },
        )

        change_rework = _request_json(
            client,
            "GET",
            f"/approvals/projects/{project['id']}/change-rework",
            expected_status=200,
        )
        _assert(
            change_rework["summary"]["total_items"] >= 1,
            "change-rework summary should contain at least one closure item",
        )
        approval_items = [
            item
            for item in change_rework["items"]
            if item["approval_id"] == approval["id"]
        ]
        _assert(approval_items, "approval-based rework item should exist")
        approval_item = approval_items[0]
        _assert(
            approval_item["change_batch_id"] == change_batch["id"],
            "approval rework item should keep original change batch link",
        )
        _assert(
            bool(approval_item["evidence_package_key"]),
            "approval rework item should include Day11 evidence package key",
        )
        _assert(
            "补齐批次-证据包关联" in approval_item["requested_changes"],
            "approval rework item should preserve requested changes",
        )
        _assert(
            {"plan", "verification", "decision", "rework"}.issubset(
                {step["stage"] for step in approval_item["steps"]}
            ),
            "approval rework chain should include plan/verification/decision/rework stages",
        )

        timeline = _request_json(
            client,
            "GET",
            f"/projects/{project['id']}/timeline",
            expected_status=200,
        )
        event_types = {item["event_type"] for item in timeline["events"]}
        _assert("deliverable" in event_types, "timeline should include deliverable events")
        _assert("preflight" in event_types, "timeline should include preflight events")
        _assert("approval" in event_types, "timeline should include approval events")

        retrospective = _request_json(
            client,
            "GET",
            f"/approvals/projects/{project['id']}/retrospective",
            expected_status=200,
        )
        _assert(
            retrospective["summary"]["negative_approval_cycles"] >= 1,
            "retrospective should include at least one negative approval cycle",
        )

    report = {
        "project_id": project["id"],
        "change_batch_id": change_batch["id"],
        "approval_id": approval["id"],
        "change_rework_total_items": change_rework["summary"]["total_items"],
        "change_rework_open_items": change_rework["summary"]["open_items"],
        "approval_item_recommendation": approval_item["recommendation"],
        "approval_item_status": approval_item["status"],
        "approval_item_evidence_package_key": approval_item["evidence_package_key"],
        "timeline_event_types": sorted(event_types),
        "retrospective_negative_cycles": retrospective["summary"][
            "negative_approval_cycles"
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
