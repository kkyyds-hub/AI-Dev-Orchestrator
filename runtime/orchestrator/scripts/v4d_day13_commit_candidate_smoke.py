"""V4-D Day13 smoke checks for commit-candidate draft generation and revision history."""

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
SMOKE_ROOT = RUNTIME_ROOT / "tmp" / "v4-day13-commit-candidate-smoke"
SMOKE_RUNTIME_DATA_DIR = SMOKE_ROOT / "runtime-data"
SMOKE_ALLOWED_WORKSPACE_ROOT = SMOKE_ROOT / "allowed-workspaces"
SMOKE_REPOSITORY_ROOT = SMOKE_ALLOWED_WORKSPACE_ROOT / "day13-commit-candidate"


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
                "name": "day13-smoke-web",
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
        "runtime/orchestrator/app/services/commit_candidate_service.py",
        '"""Day13 smoke placeholder service."""\n\nSERVICE_READY = True\n',
    )
    _write_file(
        "runtime/orchestrator/app/api/routes/repositories.py",
        '"""Day13 smoke placeholder route."""\n\nROUTES = ["/repositories"]\n',
    )
    _write_file(
        "apps/web/src/features/repositories/RepositoryOverviewPage.tsx",
        "export function RepositoryOverviewPage() { return <div>Day13</div>; }\n",
    )
    _write_file("README.md", "# Day13 Smoke Repo\n")
    _write_file(".gitignore", "node_modules/\n.tmp/\n")

    _run_git("init")
    _run_git("checkout", "-b", "main")
    _run_git("config", "user.email", "EMAIL_REDACTED")
    _run_git("config", "user.name", "Smoke Bot")
    _run_git("add", ".")
    _run_git("commit", "-m", "init day13 smoke repo")

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
            "name": "Day13 提交草案项目",
            "summary": "验证 Day13 CommitCandidate 草案与修订历史。",
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
            "display_name": "Day13 smoke repo",
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
                "可生成提交草案并包含证据摘要",
                "可追加修订版本且保留历史",
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
            "summary": "Day13 烟测交付件摘要。",
            "content": "# Day13\n\nSmoke deliverable.",
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
            "intent_summary": f"{title} 的 Day13 烟测计划。",
            "source_summary": "Day13 smoke 来源摘要。",
            "focus_terms": ["commit", "candidate", "day13"],
            "target_files": target_files,
            "expected_actions": [
                "生成提交草案",
                "沉淀版本修订历史",
            ],
            "risk_notes": [
                "Day13 仅形成草案，不执行真实 Git 提交。",
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
            "title": "Day13 提交草案批次",
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
            "duration_seconds": 8.6,
            "output_summary": output_summary,
        },
    )


def _apply_workspace_changes() -> None:
    _write_file(
        "runtime/orchestrator/app/services/commit_candidate_service.py",
        (
            '"""Day13 smoke placeholder service."""\n\n'
            "SERVICE_READY = True\n"
            "DAY13_COMMIT_CANDIDATE_READY = True\n"
        ),
    )
    _write_file(
        "apps/web/src/features/repositories/CommitDraftPanel.tsx",
        "export function CommitDraftPanel() { return <div>Day13 Commit Draft</div>; }\n",
    )


def main() -> None:
    _prepare_env()

    from fastapi.testclient import TestClient

    from app.main import create_application

    app = create_application()

    with TestClient(app) as client:
        project = _create_project(client)
        _bind_repository(client, project_id=project["id"])

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
            "Day13 smoke requires the Day09 verification baseline categories.",
        )

        task_backend = _create_task(
            client,
            project_id=project["id"],
            title="沉淀提交草案后端能力",
            input_summary="补齐 CommitCandidate 领域、仓储、服务与接口。",
        )
        task_frontend = _create_task(
            client,
            project_id=project["id"],
            title="展示提交草案面板",
            input_summary="补齐仓库页 CommitDraftPanel。",
        )

        deliverable_backend = _create_deliverable(
            client,
            project_id=project["id"],
            task_id=task_backend["id"],
            title="Day13 后端方案",
        )
        deliverable_frontend = _create_deliverable(
            client,
            project_id=project["id"],
            task_id=task_frontend["id"],
            title="Day13 前端方案",
        )

        change_plan_backend = _create_change_plan(
            client,
            project_id=project["id"],
            task_id=task_backend["id"],
            deliverable_id=deliverable_backend["id"],
            title="Day13 后端草案计划",
            target_files=[
                {
                    "relative_path": "runtime/orchestrator/app/services/commit_candidate_service.py",
                    "language": "Python",
                    "file_type": ".py",
                    "rationale": "补齐提交草案服务",
                    "match_reasons": ["service", "day13"],
                },
                {
                    "relative_path": "runtime/orchestrator/app/api/routes/repositories.py",
                    "language": "Python",
                    "file_type": ".py",
                    "rationale": "补齐提交草案接口",
                    "match_reasons": ["api", "day13"],
                },
            ],
            verification_commands=[
                "python -m py_compile runtime/orchestrator/app/services/commit_candidate_service.py",
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
            title="Day13 前端草案计划",
            target_files=[
                {
                    "relative_path": "apps/web/src/features/repositories/CommitDraftPanel.tsx",
                    "language": "TypeScript",
                    "file_type": ".tsx",
                    "rationale": "补齐提交草案面板",
                    "match_reasons": ["ui", "day13"],
                },
                {
                    "relative_path": "apps/web/src/features/repositories/RepositoryOverviewPage.tsx",
                    "language": "TypeScript",
                    "file_type": ".tsx",
                    "rationale": "接入提交草案面板",
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
            "Day13 smoke requires a preflight-ready change batch.",
        )

        _record_verification_run(
            client,
            project_id=project["id"],
            change_plan_id=change_plan_backend["id"],
            change_batch_id=change_batch["id"],
            verification_template_id=template_ids_by_category["build"],
            output_summary="Day13 后端验证通过。",
        )
        time.sleep(0.02)
        _record_verification_run(
            client,
            project_id=project["id"],
            change_plan_id=change_plan_frontend["id"],
            change_batch_id=change_batch["id"],
            verification_template_id=template_ids_by_category["test"],
            output_summary="Day13 前端验证通过。",
        )

        _apply_workspace_changes()
        head_before = _run_git("rev-parse", "HEAD")

        first_revision = _request_json(
            client,
            "POST",
            f"/repositories/change-batches/{change_batch['id']}/commit-candidate",
            expected_status=200,
            json_body={},
        )
        _assert(
            first_revision["current_version_number"] == 1,
            "The first Day13 draft should start at version 1.",
        )
        _assert(
            first_revision["latest_version"]["verification_summary"]["failed_runs"] == 0,
            "Day13 draft should require zero failed verification runs.",
        )
        _assert(
            first_revision["latest_version"]["impact_scope"],
            "Day13 draft must include non-empty impact scope.",
        )
        _assert(
            first_revision["latest_version"]["related_files"],
            "Day13 draft must include related file references.",
        )
        _assert(
            first_revision["latest_version"]["related_deliverables"],
            "Day13 draft must include linked deliverables.",
        )

        second_revision = _request_json(
            client,
            "POST",
            f"/repositories/change-batches/{change_batch['id']}/commit-candidate",
            expected_status=200,
            json_body={
                "revision_note": "补充老板审阅意见后的草案修订。",
                "message_title": "chore: Day13 提交草案（修订版）",
            },
        )
        _assert(
            second_revision["current_version_number"] == 2,
            "The second Day13 generation should append revision version 2.",
        )
        _assert(
            len(second_revision["versions"]) == 2,
            "Day13 revision history should preserve both v1 and v2.",
        )
        _assert(
            second_revision["versions"][0]["version_number"] == 1
            and second_revision["versions"][1]["version_number"] == 2,
            "Day13 revisions should keep historical versions instead of overwriting.",
        )
        _assert(
            second_revision["versions"][1]["revision_note"] == "补充老板审阅意见后的草案修订。",
            "Day13 revision note should persist on the new version.",
        )

        detail = _request_json(
            client,
            "GET",
            f"/repositories/change-batches/{change_batch['id']}/commit-candidate",
            expected_status=200,
        )
        project_candidates = _request_json(
            client,
            "GET",
            f"/repositories/projects/{project['id']}/commit-candidates",
            expected_status=200,
        )

        head_after = _run_git("rev-parse", "HEAD")
        _assert(
            head_before == head_after,
            "Day13 draft generation must not create real Git commits.",
        )
        _assert(
            detail["latest_version"]["message_title"] == "chore: Day13 提交草案（修订版）",
            "Day13 detail should return the latest revision message title.",
        )
        _assert(
            len(project_candidates) == 1
            and project_candidates[0]["change_batch_id"] == change_batch["id"],
            "Day13 project list should expose the change-batch candidate summary.",
        )

    report = {
        "project_id": project["id"],
        "change_batch_id": change_batch["id"],
        "candidate_id": detail["id"],
        "current_version_number": detail["current_version_number"],
        "revision_count": detail["revision_count"],
        "verification_total_runs": detail["latest_version"]["verification_summary"][
            "total_runs"
        ],
        "related_file_count": len(detail["latest_version"]["related_files"]),
        "deliverable_count": len(detail["latest_version"]["related_deliverables"]),
        "head_unchanged": head_before == head_after,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
