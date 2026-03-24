"""V4-D Day14 smoke checks for repository release-gate checklist and approval decisions."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_ROOT = RUNTIME_ROOT / "tmp" / "v4-day14-release-gate-smoke"
SMOKE_RUNTIME_DATA_DIR = SMOKE_ROOT / "runtime-data"
SMOKE_ALLOWED_WORKSPACE_ROOT = SMOKE_ROOT / "allowed-workspaces"
SMOKE_REPOSITORY_ROOT = SMOKE_ALLOWED_WORKSPACE_ROOT / "day14-release-gate"


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


def _write_file(relative_path: str, content: str) -> None:
    file_path = SMOKE_REPOSITORY_ROOT / Path(relative_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def _prepare_env() -> None:
    if SMOKE_ROOT.exists():
        shutil.rmtree(SMOKE_ROOT, onerror=_remove_readonly)

    _write_file(
        "apps/web/package.json",
        json.dumps(
            {
                "name": "day14-smoke-web",
                "private": True,
                "scripts": {"build": "echo build", "typecheck": "echo typecheck"},
                "devDependencies": {"typescript": "^5.8.2"},
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    _write_file(
        "runtime/orchestrator/app/services/repository_release_gate_service.py",
        '"""Day14 smoke placeholder service."""\n\nDAY14_RELEASE_GATE_READY = True\n',
    )
    _write_file(
        "runtime/orchestrator/app/api/routes/approvals.py",
        '"""Day14 smoke placeholder approvals route."""\n\nROUTES = ["/approvals"]\n',
    )
    _write_file(
        "runtime/orchestrator/app/api/routes/repositories.py",
        '"""Day14 smoke placeholder repositories route."""\n\nROUTES = ["/repositories"]\n',
    )
    _write_file(
        "apps/web/src/features/approvals/ApprovalGatePage.tsx",
        "export function ApprovalGatePage() { return <div>Day14</div>; }\n",
    )
    _write_file(".gitignore", "node_modules/\n.tmp/\n")
    _write_file("README.md", "# Day14 Smoke Repo\n")

    _run_git("init")
    _run_git("checkout", "-b", "main")
    _run_git("config", "user.email", "EMAIL_REDACTED")
    _run_git("config", "user.name", "Smoke Bot")
    _run_git("add", ".")
    _run_git("commit", "-m", "init day14 smoke repo")

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


def _create_project(client: Any) -> Any:
    return _request_json(
        client,
        "POST",
        "/projects",
        expected_status=201,
        json_body={
            "name": "Day14 审批闸门项目",
            "summary": "验证 Day14 放行检查单、阻断逻辑与审批记录。",
        },
    )


def _bind_repository(client: Any, *, project_id: str) -> Any:
    return _request_json(
        client,
        "PUT",
        f"/repositories/projects/{project_id}",
        expected_status=200,
        json_body={
            "root_path": str(SMOKE_REPOSITORY_ROOT.resolve()),
            "display_name": "Day14 smoke repo",
            "default_base_branch": "main",
        },
    )


def _create_task(
    client: Any,
    *,
    project_id: str,
    title: str,
    input_summary: str,
) -> Any:
    return _request_json(
        client,
        "POST",
        "/tasks",
        expected_status=201,
        json_body={
            "project_id": project_id,
            "title": title,
            "input_summary": input_summary,
            "acceptance_criteria": [
                "放行检查单关键项完整",
                "审批动作可记录并可回放",
            ],
        },
    )


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
            "summary": "Day14 烟测交付件摘要。",
            "content": "# Day14\n\nSmoke deliverable.",
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
    target_files: list[dict[str, Any]],
    verification_commands: list[str],
    verification_template_ids: list[str],
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
            "intent_summary": f"{title} 的 Day14 烟测计划。",
            "source_summary": "Day14 smoke 来源摘要。",
            "focus_terms": ["release", "gate", "day14"],
            "target_files": target_files,
            "expected_actions": [
                "汇总放行检查单",
                "记录审批动作",
            ],
            "risk_notes": [
                "Day14 审批通过仅代表放行资格成立，不自动写 Git。",
            ],
            "verification_commands": verification_commands,
            "verification_template_ids": verification_template_ids,
        },
    )


def _create_change_batch(
    client: Any,
    *,
    project_id: str,
    change_plan_ids: list[str],
) -> Any:
    return _request_json(
        client,
        "POST",
        f"/repositories/projects/{project_id}/change-batches",
        expected_status=200,
        json_body={
            "title": "Day14 放行审批批次",
            "change_plan_ids": change_plan_ids,
        },
    )


def _record_verification_run(
    client: Any,
    *,
    project_id: str,
    change_plan_id: str,
    change_batch_id: str,
    verification_template_id: str,
    output_summary: str,
) -> Any:
    return _request_json(
        client,
        "POST",
        "/runs/verification",
        expected_status=201,
        json_body={
            "project_id": project_id,
            "change_plan_id": change_plan_id,
            "change_batch_id": change_batch_id,
            "verification_template_id": verification_template_id,
            "status": "passed",
            "duration_seconds": 6.8,
            "output_summary": output_summary,
        },
    )


def _apply_workspace_changes() -> None:
    _write_file(
        "runtime/orchestrator/app/services/repository_release_gate_service.py",
        (
            '"""Day14 smoke placeholder service."""\n\n'
            "DAY14_RELEASE_GATE_READY = True\n"
            "DAY14_CHECKLIST_READY = True\n"
        ),
    )
    _write_file(
        "apps/web/src/features/approvals/RepositoryReleaseChecklist.tsx",
        "export function RepositoryReleaseChecklist() { return <div>Day14 Checklist</div>; }\n",
    )


def main() -> None:
    _prepare_env()

    from fastapi.testclient import TestClient

    from app.main import create_application

    app = create_application()

    with TestClient(app) as client:
        project = _create_project(client)
        _bind_repository(client, project_id=project["id"])
        snapshot = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project['id']}/snapshot/refresh",
            expected_status=200,
        )
        _assert(snapshot["status"] == "success", "Day14 smoke requires snapshot success.")

        baseline = _request_json(
            client,
            "GET",
            f"/repositories/projects/{project['id']}/verification-baseline",
            expected_status=200,
        )
        template_ids_by_category = {
            template["category"]: template["id"]
            for template in baseline["templates"]
        }
        _assert(
            {"build", "test", "lint", "typecheck"} == set(template_ids_by_category),
            "Day14 smoke requires the Day09 verification baseline categories.",
        )

        task_backend = _create_task(
            client,
            project_id=project["id"],
            title="沉淀 Day14 放行闸门后端能力",
            input_summary="补齐检查单汇总、阻断与审批记录接口。",
        )
        task_frontend = _create_task(
            client,
            project_id=project["id"],
            title="展示 Day14 放行检查单面板",
            input_summary="补齐审批页检查单展示与审批动作表单。",
        )
        deliverable_backend = _create_deliverable(
            client,
            project_id=project["id"],
            task_id=task_backend["id"],
            title="Day14 后端方案",
        )
        deliverable_frontend = _create_deliverable(
            client,
            project_id=project["id"],
            task_id=task_frontend["id"],
            title="Day14 前端方案",
        )
        change_plan_backend = _create_change_plan(
            client,
            project_id=project["id"],
            task_id=task_backend["id"],
            deliverable_id=deliverable_backend["id"],
            title="Day14 放行检查单后端计划",
            target_files=[
                {
                    "relative_path": "runtime/orchestrator/app/services/repository_release_gate_service.py",
                    "language": "Python",
                    "file_type": ".py",
                    "rationale": "补齐 Day14 核心服务",
                    "match_reasons": ["service", "day14"],
                },
                {
                    "relative_path": "apps/web/src/features/approvals/RepositoryReleaseChecklist.tsx",
                    "language": "TypeScript",
                    "file_type": ".tsx",
                    "rationale": "展示 Day14 检查单",
                    "match_reasons": ["ui", "day14"],
                },
            ],
            verification_commands=[
                "python -m py_compile runtime/orchestrator/app/services/repository_release_gate_service.py",
            ],
            verification_template_ids=[
                template_ids_by_category["build"],
                template_ids_by_category["lint"],
            ],
        )
        change_plan_frontend = _create_change_plan(
            client,
            project_id=project["id"],
            task_id=task_frontend["id"],
            deliverable_id=deliverable_frontend["id"],
            title="Day14 放行检查单前端计划",
            target_files=[
                {
                    "relative_path": "apps/web/src/features/approvals/RepositoryReleaseChecklist.tsx",
                    "language": "TypeScript",
                    "file_type": ".tsx",
                    "rationale": "展示 Day14 检查单",
                    "match_reasons": ["ui", "day14"],
                },
                {
                    "relative_path": "apps/web/src/features/approvals/RepositoryReleaseGatePanel.tsx",
                    "language": "TypeScript",
                    "file_type": ".tsx",
                    "rationale": "接入审批动作表单",
                    "match_reasons": ["ui", "integration"],
                },
            ],
            verification_commands=[
                "cmd /c npm run build",
            ],
            verification_template_ids=[
                template_ids_by_category["test"],
                template_ids_by_category["typecheck"],
            ],
        )
        change_batch = _create_change_batch(
            client,
            project_id=project["id"],
            change_plan_ids=[change_plan_backend["id"], change_plan_frontend["id"]],
        )

        preflight_ready = _request_json(
            client,
            "POST",
            f"/repositories/change-batches/{change_batch['id']}/preflight",
            expected_status=200,
            json_body={},
        )
        _assert(
            preflight_ready["preflight"]["status"] in {"ready_for_execution", "manual_confirmed"},
            "Day14 smoke requires a preflight-ready change batch.",
        )

        _record_verification_run(
            client,
            project_id=project["id"],
            change_plan_id=change_plan_backend["id"],
            change_batch_id=change_batch["id"],
            verification_template_id=template_ids_by_category["build"],
            output_summary="Day14 验证通过。",
        )
        _apply_workspace_changes()
        head_before = _run_git("rev-parse", "HEAD")

        blocked_gate = _request_json(
            client,
            "GET",
            f"/approvals/repository-release-gate/{change_batch['id']}",
            expected_status=200,
        )
        required_item_keys = {
            "repository_binding",
            "snapshot_freshness",
            "change_plan",
            "risk_preflight",
            "verification_results",
            "diff_evidence",
            "commit_draft",
        }
        _assert(
            required_item_keys == {item["key"] for item in blocked_gate["checklist_items"]},
            "Day14 checklist must expose the seven required items.",
        )
        _assert(
            blocked_gate["blocked"] is True
            and "commit_draft" in blocked_gate["missing_item_keys"],
            "Before Day13 draft generation, Day14 gate must be blocked by missing commit draft.",
        )

        approve_while_blocked = client.post(
            f"/approvals/repository-release-gate/{change_batch['id']}/actions",
            json={
                "action": "approve",
                "actor_name": "老板",
                "summary": "尝试在阻断状态直接通过",
            },
        )
        _assert(
            approve_while_blocked.status_code == 409,
            "Day14 must explicitly block approve actions while checklist has gaps.",
        )

        commit_candidate = _request_json(
            client,
            "POST",
            f"/repositories/change-batches/{change_batch['id']}/commit-candidate",
            expected_status=200,
            json_body={},
        )
        _assert(
            commit_candidate["current_version_number"] == 1,
            "Day14 smoke requires Day13 commit draft to unblock the gate.",
        )
        time.sleep(0.02)

        ready_gate = _request_json(
            client,
            "GET",
            f"/approvals/repository-release-gate/{change_batch['id']}",
            expected_status=200,
        )
        _assert(
            ready_gate["blocked"] is False
            and ready_gate["status"] == "pending_approval"
            and not ready_gate["missing_item_keys"],
            "After commit draft generation, Day14 gate should move to pending approval.",
        )

        gate_after_request_changes = _request_json(
            client,
            "POST",
            f"/approvals/repository-release-gate/{change_batch['id']}/actions",
            expected_status=200,
            json_body={
                "action": "request_changes",
                "actor_name": "老板",
                "summary": "需要补充失败回滚验证说明。",
                "comment": "请追加失败场景回滚证据。",
                "highlighted_risks": ["失败回滚证据不足"],
                "requested_changes": ["补充失败回滚验证日志"],
            },
        )
        _assert(
            gate_after_request_changes["status"] == "changes_requested"
            and gate_after_request_changes["decision_count"] == 1,
            "Day14 should persist request_changes decisions.",
        )

        gate_after_reject = _request_json(
            client,
            "POST",
            f"/approvals/repository-release-gate/{change_batch['id']}/actions",
            expected_status=200,
            json_body={
                "action": "reject",
                "actor_name": "老板",
                "summary": "当前说明不足，驳回本轮放行。",
                "comment": "证据链条还不完整。",
                "highlighted_risks": ["证据链不完整"],
                "requested_changes": ["补齐证据后重提"],
            },
        )
        _assert(
            gate_after_reject["status"] == "rejected"
            and gate_after_reject["decision_count"] == 2,
            "Day14 should persist reject decisions.",
        )

        gate_after_approve = _request_json(
            client,
            "POST",
            f"/approvals/repository-release-gate/{change_batch['id']}/actions",
            expected_status=200,
            json_body={
                "action": "approve",
                "actor_name": "老板",
                "summary": "缺口已补齐，同意放行。",
                "comment": "仅确认放行资格，不触发真实 Git 写入。",
                "highlighted_risks": ["后续人工提交需二次复核"],
                "requested_changes": [],
            },
        )
        _assert(
            gate_after_approve["status"] == "approved"
            and gate_after_approve["release_qualification_established"] is True
            and gate_after_approve["git_write_actions_triggered"] is False
            and gate_after_approve["decision_count"] == 3,
            "Day14 approval should establish release qualification without triggering Git writes.",
        )

        approval_actions = [item["action"] for item in gate_after_approve["decisions"]]
        _assert(
            approval_actions == ["request_changes", "reject", "approve"],
            "Day14 decision history should preserve request_changes/reject/approve order.",
        )

        approvals_inbox = _request_json(
            client,
            "GET",
            f"/approvals/projects/{project['id']}/repository-release-gate",
            expected_status=200,
        )
        _assert(
            approvals_inbox["total_batches"] == 1
            and approvals_inbox["approved_batches"] == 1,
            "Approvals Day14 inbox should expose final approved counters.",
        )

        repositories_inbox = _request_json(
            client,
            "GET",
            f"/repositories/projects/{project['id']}/release-gates",
            expected_status=200,
        )
        repositories_detail = _request_json(
            client,
            "GET",
            f"/repositories/change-batches/{change_batch['id']}/release-checklist",
            expected_status=200,
        )
        _assert(
            repositories_inbox["total_batches"] == approvals_inbox["total_batches"],
            "Repositories and approvals Day14 inbox counters should stay compatible.",
        )
        _assert(
            repositories_detail["status"] == "approved"
            and repositories_detail["release_qualification_established"] is True,
            "Repositories Day14 detail should match approvals-side release status.",
        )

        head_after = _run_git("rev-parse", "HEAD")
        _assert(
            head_before == head_after,
            "Day14 release gate decisions must not create real Git commits.",
        )

    decision_file = (
        SMOKE_RUNTIME_DATA_DIR
        / "repository-release-gates"
        / f"{change_batch['id']}.json"
    )
    _assert(
        decision_file.exists(),
        "Day14 smoke should persist decision records under runtime data.",
    )
    decision_payload = json.loads(decision_file.read_text(encoding="utf-8"))

    report = {
        "project_id": project["id"],
        "change_batch_id": change_batch["id"],
        "checklist_item_count": len(ready_gate["checklist_items"]),
        "blocked_before": blocked_gate["blocked"],
        "blocked_reason_keys": blocked_gate["missing_item_keys"],
        "approve_blocked_status_code": approve_while_blocked.status_code,
        "final_status": gate_after_approve["status"],
        "release_qualification_established": gate_after_approve[
            "release_qualification_established"
        ],
        "decision_count": gate_after_approve["decision_count"],
        "decision_actions": [item["action"] for item in gate_after_approve["decisions"]],
        "head_unchanged": head_before == head_after,
        "git_write_actions_triggered": gate_after_approve["git_write_actions_triggered"],
        "decision_file": str(decision_file),
        "persisted_decision_count": len(decision_payload.get("decisions", [])),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
