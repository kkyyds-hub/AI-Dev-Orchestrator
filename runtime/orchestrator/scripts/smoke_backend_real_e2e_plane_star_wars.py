"""Backend real closed-loop E2E for the "Plane Star Wars" console game theme.

This smoke intentionally stays inside the existing backend/API surface:

- no project rebuild
- no tech-stack switch
- no frontend/UI change
- no API path change

It drives a real TestClient chain from planning -> tasks -> repository binding
-> file locator -> context pack -> change plan -> change batch -> preflight
-> verification records -> release gate -> apply-local -> git-commit -> rollup
evidence files.

The only external side effect is an isolated temporary git repository under
``runtime/orchestrator/tmp/backend-real-e2e-plane-star-wars``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = RUNTIME_ROOT.parents[1]
SMOKE_ROOT = RUNTIME_ROOT / "tmp" / "backend-real-e2e-plane-star-wars"
if os.environ.get("PLANE_STAR_WARS_SMOKE_ROOT"):
    SMOKE_ROOT = Path(os.environ["PLANE_STAR_WARS_SMOKE_ROOT"])
SMOKE_RUNTIME_DATA_DIR = SMOKE_ROOT / "runtime-data"
SMOKE_ALLOWED_WORKSPACE_ROOT = SMOKE_ROOT / "allowed-workspaces"
SMOKE_REPOSITORY_ROOT = SMOKE_ALLOWED_WORKSPACE_ROOT / "plane-star-wars-game"
SMOKE_REPORT_PATH = SMOKE_ROOT / "plane-star-wars-e2e-report.json"

if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


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
            f"git {' '.join(args)} failed: "
            f"{completed_process.stderr or completed_process.stdout}"
        )
    return (completed_process.stdout or "").strip()


def _run_repo_command(command: str) -> dict[str, object]:
    completed_process = subprocess.run(
        command,
        cwd=SMOKE_REPOSITORY_ROOT,
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=120,
    )
    output = "\n".join(
        part for part in [completed_process.stdout, completed_process.stderr] if part
    ).strip()
    return {
        "command": command,
        "exit_code": completed_process.returncode,
        "output": output[:4_000],
    }


def _write_file(relative_path: str, content: str) -> None:
    file_path = SMOKE_REPOSITORY_ROOT / Path(relative_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def _prepare_env() -> None:
    if SMOKE_ROOT.exists():
        shutil.rmtree(SMOKE_ROOT, onerror=_remove_readonly)

    _write_file(
        "README.md",
        "# Plane Star Wars Console Game\n\n"
        "A tiny Python console-game repository used by backend E2E smoke tests.\n",
    )
    _write_file(
        "pyproject.toml",
        "[project]\n"
        'name = "plane-star-wars-game"\n'
        'version = "0.1.0"\n'
        'description = "Tiny Plane Star Wars console game"\n'
        'requires-python = ">=3.11"\n',
    )
    _write_file("plane_star_wars/__init__.py", '"""Plane Star Wars package."""\n')
    _write_file(
        "plane_star_wars/game.py",
        '"""Minimal seed module before orchestrated E2E changes."""\n\n'
        "def title() -> str:\n"
        '    return "飞机星球大战"\n',
    )
    _write_file(
        "tests/test_game.py",
        "from plane_star_wars.game import title\n\n\n"
        "def test_title() -> None:\n"
        '    assert title() == "飞机星球大战"\n',
    )
    _write_file(".gitignore", "__pycache__/\n*.py[cod]\n.pytest_cache/\n")

    _run_git("init")
    _run_git("checkout", "-b", "main")
    _run_git("config", "user.email", "EMAIL_REDACTED")
    _run_git("config", "user.name", "Plane Star Wars E2E")
    _run_git("add", ".")
    _run_git("commit", "-m", "init plane star wars game")

    os.environ["RUNTIME_DATA_DIR"] = str(SMOKE_RUNTIME_DATA_DIR)
    os.environ["REPOSITORY_WORKSPACE_ROOT_DIR"] = str(SMOKE_ALLOWED_WORKSPACE_ROOT)
    os.environ["DAILY_BUDGET_USD"] = "8.00"
    os.environ["SESSION_BUDGET_USD"] = "8.00"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"
    (SMOKE_RUNTIME_DATA_DIR / "db").mkdir(parents=True, exist_ok=True)


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
            f"{method} {path} expected {expected_status}, "
            f"got {response.status_code}: {response.text}"
        )
    return response.json()


def _target_files_from_context_pack(context_pack: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "relative_path": entry["relative_path"],
            "language": entry["language"],
            "file_type": entry["file_type"],
            "rationale": f"Plane Star Wars E2E target: {entry['relative_path']}",
            "match_reasons": entry["match_reasons"],
        }
        for entry in context_pack["entries"]
    ]


def _planned_game_content() -> str:
    return '''"""A tiny deterministic Python console game: 飞机星球大战."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Fighter:
    name: str
    hp: int
    laser: int

    def attack(self, enemy: "Fighter") -> str:
        enemy.hp = max(0, enemy.hp - self.laser)
        return f"{self.name} fires {self.laser} laser damage at {enemy.name}!"


def title() -> str:
    return "飞机星球大战"


def build_opening_scene() -> str:
    return (
        "飞机星球大战：银河跑道遭遇帝国陨石机群。"
        "驾驶星翼飞机，发射激光，守住蓝色星球。"
    )


def play_demo_round() -> list[str]:
    hero = Fighter(name="星翼飞机", hp=30, laser=9)
    enemy = Fighter(name="陨石战机", hp=18, laser=5)
    log = [build_opening_scene()]
    round_no = 1
    while hero.hp > 0 and enemy.hp > 0:
        log.append(f"Round {round_no}")
        log.append(hero.attack(enemy))
        if enemy.hp <= 0:
            break
        log.append(enemy.attack(hero))
        round_no += 1
    winner = hero.name if hero.hp > 0 else enemy.name
    log.append(f"Winner: {winner}")
    return log


def main() -> None:
    demo_log = play_demo_round()
    for line in [title(), demo_log[1], demo_log[-1]]:
        # Keep the console command deterministic on Windows runners whose parent
        # process may decode captured subprocess output with a non-UTF-8 locale.
        print(line.encode("unicode_escape").decode("ascii"))


if __name__ == "__main__":
    main()
'''


def _planned_test_content() -> str:
    return '''from plane_star_wars.game import build_opening_scene, play_demo_round, title


def test_title() -> None:
    assert title() == "飞机星球大战"


def test_opening_scene_mentions_theme() -> None:
    scene = build_opening_scene()
    assert "飞机星球大战" in scene
    assert "星球" in scene


def test_demo_round_has_winner() -> None:
    log = play_demo_round()
    assert log[-1] == "Winner: 星翼飞机"
    assert any("laser" in line for line in log)
'''


def _create_deliverable(
    client: Any,
    *,
    project_id: str,
    task_id: str,
    title: str,
    summary: str,
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
            "summary": summary,
            "content": f"# {title}\n\n{summary}\n",
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
    source_summary: str,
    focus_terms: list[str],
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
            "intent_summary": "Build a simple Python console mini-game themed 飞机星球大战.",
            "source_summary": source_summary,
            "focus_terms": focus_terms,
            "target_files": target_files,
            "expected_actions": [
                "Implement deterministic console-game logic.",
                "Keep Python package layout and existing API routes unchanged.",
                "Verify compile and scripted demo output.",
            ],
            "risk_notes": [
                "Low-risk isolated game repository fixture.",
                "No frontend changes and no backend route changes.",
            ],
            "verification_commands": verification_commands,
            "verification_template_ids": verification_template_ids,
        },
    )


def main() -> None:
    _prepare_env()

    from fastapi.testclient import TestClient

    from app.core.db import init_database
    from app.main import create_application

    init_database()
    app = create_application()
    commands_run: list[dict[str, object]] = []

    with TestClient(app) as client:
        provider_summary = _request_json(
            client,
            "PUT",
            "/provider-settings/openai",
            expected_status=200,
            json_body={
                "api_key": os.environ.get(
                    "PLANE_STAR_WARS_PROVIDER_API_KEY",
                    "sk-KEY_REDACTED-plane-star-wars-e2e",
                ),
                "base_url": os.environ.get(
                    "PLANE_STAR_WARS_PROVIDER_BASE_URL",
                    "https://api.openai.com/v1",
                ),
                "timeout_seconds": int(
                    os.environ.get(
                        "PLANE_STAR_WARS_PROVIDER_TIMEOUT_SECONDS", "5"
                    )
                ),
            },
        )

        plan_draft = _request_json(
            client,
            "POST",
            "/planning/drafts",
            expected_status=200,
            json_body={
                "brief": (
                    "做一个简单的 Python 控制台小游戏，主题叫“飞机星球大战”。\n"
                    "- 项目规划、任务、仓库绑定、文件定位、上下文包、变更计划要形成链路。\n"
                    "- 新增星翼飞机对战陨石战机的确定性 demo 回合。\n"
                    "- 用 compileall 和 python -m plane_star_wars.game 验证。"
                ),
                "max_tasks": 5,
            },
        )
        apply_payload = {
            "project_summary": plan_draft["project_summary"],
            "project": {
                **plan_draft["project"],
                "name": "飞机星球大战 backend real E2E",
                "summary": "Backend real E2E for a simple Python console mini-game.",
                "stage": "execution",
            },
            "tasks": plan_draft["tasks"],
        }
        applied_plan = _request_json(
            client,
            "POST",
            "/planning/apply",
            expected_status=201,
            json_body=apply_payload,
        )
        project_id = applied_plan["project"]["id"]
        created_tasks = applied_plan["tasks"]
        implementation_task = next(
            (
                task
                for task in created_tasks
                if "飞机" in task["title"] or "demo" in task["input_summary"].lower()
            ),
            created_tasks[min(1, len(created_tasks) - 1)],
        )
        verification_task = created_tasks[-1]

        team_control = _request_json(
            client,
            "PUT",
            f"/projects/{project_id}/team-control-center",
            expected_status=200,
            json_body={
                "team_name": "Plane Star Wars Backend E2E Team",
                "team_mission": "Deliver a real backend closed-loop acceptance for 飞机星球大战.",
                "assembly": [
                    {
                        "role_code": "engineer",
                        "display_name": "Runtime Engineer",
                        "enabled": True,
                        "allocation_percent": 70,
                        "notes": "Owns local git write and verification.",
                    },
                    {
                        "role_code": "reviewer",
                        "display_name": "Release Reviewer",
                        "enabled": True,
                        "allocation_percent": 30,
                        "notes": "Owns release-gate evidence.",
                    },
                ],
                "team_policy": {
                    "collaboration_mode": "role-led",
                    "intervention_mode": "boss-review",
                    "escalation_enabled": True,
                    "handoff_required": True,
                    "review_gate": "required",
                },
                "budget_policy": {
                    "daily_budget_usd": 8.0,
                    "per_run_budget_usd": 2.0,
                    "hard_stop_enabled": False,
                    "pressure_mode": "balanced",
                },
                "role_model_policy": {
                    "role_preferences": [
                        {"role_code": "engineer", "model_tier": "balanced"},
                        {"role_code": "reviewer", "model_tier": "premium"},
                    ],
                    "stage_overrides": [
                        {
                            "stage": "execution",
                            "role_code": "engineer",
                            "model_tier": "balanced",
                        },
                        {
                            "stage": "verification",
                            "role_code": "reviewer",
                            "model_tier": "premium",
                        },
                    ],
                },
            },
        )

        worker_result = _request_json(
            client,
            "POST",
            f"/workers/run-once?project_id={project_id}",
            expected_status=200,
        )
        _assert(worker_result["claimed"] is True, "Worker must claim one planned task.")
        _assert(
            worker_result["run_status"] == "succeeded",
            f"Worker run should succeed, got {worker_result['run_status']}",
        )
        _assert(
            worker_result["token_accounting_mode"] == "provider_reported",
            "Worker run should persist provider_reported token accounting via mock/fallback receipt.",
        )
        _assert(
            worker_result["provider_receipt_id"],
            "Worker run should persist a provider receipt id.",
        )

        repository_binding = _request_json(
            client,
            "PUT",
            f"/repositories/projects/{project_id}",
            expected_status=200,
            json_body={
                "root_path": str(SMOKE_REPOSITORY_ROOT.resolve()),
                "display_name": "plane-star-wars-e2e-repo",
                "access_mode": "read_only",
                "default_base_branch": "main",
                "ignore_rule_summary": [".git", "__pycache__", ".pytest_cache"],
            },
        )
        snapshot_refresh = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project_id}/snapshot/refresh",
            expected_status=200,
        )
        _assert(snapshot_refresh["status"] == "success", "Snapshot refresh must pass.")

        clean_change_session = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project_id}/change-session",
            expected_status=200,
        )
        _assert(
            clean_change_session["workspace_status"] == "clean",
            "Change session must start clean before apply-local.",
        )

        baseline = _request_json(
            client,
            "PUT",
            f"/repositories/projects/{project_id}/verification-baseline",
            expected_status=200,
            json_body={
                "templates": [
                    {
                        "category": "build",
                        "name": "Python package compile",
                        "command": "python -m compileall plane_star_wars",
                        "working_directory": ".",
                        "timeout_seconds": 120,
                        "enabled_by_default": True,
                        "description": "Compile the Plane Star Wars package.",
                    },
                    {
                        "category": "test",
                        "name": "Python tests compile",
                        "command": "python -m compileall tests",
                        "working_directory": ".",
                        "timeout_seconds": 120,
                        "enabled_by_default": True,
                        "description": "Compile the Plane Star Wars tests.",
                    },
                    {
                        "category": "lint",
                        "name": "Python source lint substitute",
                        "command": "python -m compileall plane_star_wars tests",
                        "working_directory": ".",
                        "timeout_seconds": 120,
                        "enabled_by_default": True,
                        "description": "Use Python compilation as the minimal lint baseline.",
                    },
                    {
                        "category": "typecheck",
                        "name": "Console demo execution",
                        "command": "python -m plane_star_wars.game",
                        "working_directory": ".",
                        "timeout_seconds": 120,
                        "enabled_by_default": True,
                        "description": "Run the deterministic console demo.",
                    },
                ],
            },
        )
        template_ids_by_category = {
            template["category"]: template["id"] for template in baseline["templates"]
        }
        _assert(
            {"build", "test", "lint", "typecheck"} == set(template_ids_by_category),
            "Verification baseline must expose build/test/lint/typecheck templates.",
        )

        locator_result = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project_id}/file-locator/search",
            expected_status=200,
            json_body={
                "task_id": implementation_task["id"],
                "path_prefixes": ["plane_star_wars", "tests"],
                "module_names": ["plane_star_wars", "game"],
                "file_types": ["py"],
                "limit": 10,
            },
        )
        locator_paths = {candidate["relative_path"] for candidate in locator_result["candidates"]}
        _assert(
            "plane_star_wars/game.py" in locator_paths,
            "File locator must find the existing game module.",
        )
        _assert(
            "tests/test_game.py" in locator_paths,
            "File locator must find the existing test file.",
        )

        context_pack = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project_id}/context-pack",
            expected_status=200,
            json_body={
                "task_id": implementation_task["id"],
                "selected_paths": ["plane_star_wars/game.py", "tests/test_game.py"],
                "max_total_bytes": 12_000,
                "max_bytes_per_file": 6_000,
            },
        )
        _assert(
            context_pack["included_file_count"] == 2,
            "Context pack should include game module and tests.",
        )

        deliverable = _create_deliverable(
            client,
            project_id=project_id,
            task_id=implementation_task["id"],
            title="飞机星球大战 implementation plan",
            summary="Implement deterministic console gameplay and tests.",
        )
        verification_deliverable = _create_deliverable(
            client,
            project_id=project_id,
            task_id=verification_task["id"],
            title="飞机星球大战 verification plan",
            summary="Compile and execute the console demo through repository verification.",
        )

        implementation_plan = _create_change_plan(
            client,
            project_id=project_id,
            task_id=implementation_task["id"],
            deliverable_id=deliverable["id"],
            title="Implement Plane Star Wars game loop",
            source_summary=context_pack["source_summary"],
            focus_terms=context_pack["focus_terms"],
            target_files=_target_files_from_context_pack(context_pack),
            verification_commands=[
                "python -m compileall plane_star_wars",
                "python -m plane_star_wars.game",
            ],
            verification_template_ids=[
                template_ids_by_category["build"],
                template_ids_by_category["test"],
            ],
        )
        verification_plan = _create_change_plan(
            client,
            project_id=project_id,
            task_id=verification_task["id"],
            deliverable_id=verification_deliverable["id"],
            title="Verify Plane Star Wars game loop",
            source_summary="Verify compileall and demo execution for the console game.",
            focus_terms=["飞机星球大战", "compileall", "demo"],
            target_files=[
                {
                    "relative_path": "plane_star_wars/game.py",
                    "language": "Python",
                    "file_type": ".py",
                    "rationale": "Runtime entry point for the console game.",
                    "match_reasons": ["game", "demo", "python"],
                },
                {
                    "relative_path": "tests/test_game.py",
                    "language": "Python",
                    "file_type": ".py",
                    "rationale": "Regression coverage for the game loop.",
                    "match_reasons": ["test", "game", "python"],
                },
            ],
            verification_commands=[
                "python -m compileall plane_star_wars tests",
                "python -m plane_star_wars.game",
            ],
            verification_template_ids=[
                template_ids_by_category["build"],
                template_ids_by_category["test"],
            ],
        )

        change_batch = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project_id}/change-batches",
            expected_status=200,
            json_body={
                "title": "Plane Star Wars backend real E2E batch",
                "change_plan_ids": [implementation_plan["id"], verification_plan["id"]],
            },
        )

        preflight_result = _request_json(
            client,
            "POST",
            f"/repositories/change-batches/{change_batch['id']}/preflight",
            expected_status=200,
            json_body={},
        )
        preflight_status = preflight_result["preflight"]["status"]
        if preflight_status == "blocked_requires_confirmation":
            preflight_result = _request_json(
                client,
                "POST",
                f"/approvals/repository-preflight/{change_batch['id']}/actions",
                expected_status=200,
                json_body={
                    "action": "approve",
                    "actor_name": "boss",
                    "summary": "Plane Star Wars E2E accepts preflight findings.",
                    "comment": "Isolated smoke repository; proceed for backend E2E.",
                    "highlighted_risks": [],
                },
            )
            preflight_status = preflight_result["preflight"]["status"]
        _assert(
            preflight_status in {"ready_for_execution", "manual_confirmed"},
            f"Preflight must be ready, got {preflight_status}.",
        )

        planned_files = [
            {
                "relative_path": "plane_star_wars/game.py",
                "content": _planned_game_content(),
            },
            {
                "relative_path": "tests/test_game.py",
                "content": _planned_test_content(),
            },
        ]
        for entry in planned_files:
            _write_file(entry["relative_path"], entry["content"])

        commands_run.append(_run_repo_command("python -m compileall plane_star_wars tests"))
        commands_run.append(_run_repo_command("python -m plane_star_wars.game"))
        for command_result in commands_run:
            _assert(
                command_result["exit_code"] == 0,
                f"Repository command failed: {command_result}",
            )

        for plan, command_result, template_category in [
            (implementation_plan, commands_run[0], "build"),
            (verification_plan, commands_run[1], "test"),
        ]:
            _request_json(
                client,
                "POST",
                "/runs/verification",
                expected_status=201,
                json_body={
                    "project_id": project_id,
                    "change_plan_id": plan["id"],
                    "change_batch_id": change_batch["id"],
                    "verification_template_id": template_ids_by_category[template_category],
                    "command": command_result["command"],
                    "working_directory": ".",
                    "status": "passed",
                    "duration_seconds": 1.0,
                    "output_summary": str(command_result["output"])[:2_000]
                    or f"{command_result['command']} passed.",
                },
            )

        blocked_gate = _request_json(
            client,
            "GET",
            f"/approvals/repository-release-gate/{change_batch['id']}",
            expected_status=200,
        )
        _assert(
            blocked_gate["blocked"] is True
            and "commit_draft" in blocked_gate["missing_item_keys"],
            "Release gate must be blocked before commit-candidate generation.",
        )
        approve_while_blocked = client.post(
            f"/approvals/repository-release-gate/{change_batch['id']}/actions",
            json={
                "action": "approve",
                "actor_name": "boss",
                "summary": "try approve while blocked",
            },
        )
        _assert(
            approve_while_blocked.status_code == 409,
            "Release gate approval must fail while checklist is blocked.",
        )

        evidence_package = _request_json(
            client,
            "GET",
            (
                f"/deliverables/projects/{project_id}/change-evidence"
                f"?change_batch_id={change_batch['id']}"
            ),
            expected_status=200,
        )
        _assert(
            evidence_package["diff_summary"]["metrics"]["changed_file_count"] >= 2,
            "Diff evidence must see the planned file changes.",
        )

        commit_candidate = _request_json(
            client,
            "POST",
            f"/repositories/change-batches/{change_batch['id']}/commit-candidate",
            expected_status=200,
            json_body={
                "message_title": "chore: implement plane star wars console game",
                "message_body": (
                    "Implement the deterministic Plane Star Wars Python console game.\n\n"
                    "- update plane_star_wars/game.py\n"
                    "- update tests/test_game.py\n"
                    "- evidence: compileall and demo execution passed"
                ),
                "revision_note": "backend real E2E ASCII-safe commit candidate",
            },
        )
        _assert(
            commit_candidate["current_version_number"] == 1,
            "Commit candidate version should be created.",
        )
        time.sleep(0.02)

        pending_gate = _request_json(
            client,
            "GET",
            f"/approvals/repository-release-gate/{change_batch['id']}",
            expected_status=200,
        )
        _assert(
            pending_gate["blocked"] is False
            and pending_gate["status"] == "pending_approval",
            "Release gate should become pending approval after commit candidate.",
        )

        gate_after_approve = _request_json(
            client,
            "POST",
            f"/approvals/repository-release-gate/{change_batch['id']}/actions",
            expected_status=200,
            json_body={
                "action": "approve",
                "actor_name": "boss",
                "summary": "Plane Star Wars backend E2E release gate approved.",
                "comment": "All repository evidence is present; allow local git write.",
                "highlighted_risks": ["local smoke repository only"],
                "requested_changes": [],
            },
        )
        _assert(
            gate_after_approve["release_qualification_established"] is True,
            "Release qualification must be established before apply-local.",
        )

        # Reset manual writes so apply-local is the operation that mutates files.
        _run_git("checkout", "--", "plane_star_wars/game.py", "tests/test_game.py")
        _assert(_run_git("status", "--short") == "", "Repo should be clean before apply-local.")

        apply_local = _request_json(
            client,
            "POST",
            f"/repositories/change-batches/{change_batch['id']}/apply-local",
            expected_status=200,
            json_body={"files": planned_files},
        )
        _assert(
            apply_local["status"] == "applied"
            and apply_local["verification_passed"] is True,
            f"apply-local should pass verification, got {apply_local}",
        )

        git_commit = _request_json(
            client,
            "POST",
            f"/repositories/change-batches/{change_batch['id']}/git-commit",
            expected_status=200,
        )
        _assert(
            git_commit["status"] == "committed" and git_commit["commit_sha"],
            f"git-commit should create a local commit, got {git_commit}",
        )

        gate_after_git_commit = _request_json(
            client,
            "GET",
            f"/approvals/repository-release-gate/{change_batch['id']}",
            expected_status=200,
        )
        _assert(
            gate_after_git_commit["git_write_actions_triggered"] is True,
            "Release gate must expose git_write_actions_triggered after local commit.",
        )

        repository_day15_flow = _request_json(
            client,
            "GET",
            f"/repositories/projects/{project_id}/day15-flow",
            expected_status=200,
        )
        _assert(
            repository_day15_flow["overall_status"] == "ready_for_review",
            "Repository Day15 flow should be ready_for_review.",
        )
        project_day15_flow = _request_json(
            client,
            "GET",
            f"/projects/{project_id}/day15-repository-flow",
            expected_status=200,
        )
        approvals_day15_judgement = _request_json(
            client,
            "GET",
            (
                f"/approvals/projects/{project_id}/day15-release-judgement"
                f"?change_batch_id={change_batch['id']}"
            ),
            expected_status=200,
        )
        release_checklist = _request_json(
            client,
            "GET",
            f"/repositories/change-batches/{change_batch['id']}/release-checklist",
            expected_status=200,
        )
        cost_dashboard = _request_json(
            client,
            "GET",
            f"/projects/{project_id}/cost-dashboard",
            expected_status=200,
        )
        closure_diagnostics = _request_json(
            client,
            "GET",
            f"/projects/{project_id}/closure-diagnostics",
            expected_status=200,
        )

    committed_files = _run_git(
        "diff-tree",
        "--no-commit-id",
        "-r",
        "--name-only",
        git_commit["commit_sha"],
    ).splitlines()
    demo_output = _run_repo_command("python -m plane_star_wars.game")
    _assert(demo_output["exit_code"] == 0, "Committed game demo must run.")

    report: dict[str, Any] = {
        "theme": "飞机星球大战",
        "runtime_data_dir": str(SMOKE_RUNTIME_DATA_DIR),
        "repository_root": str(SMOKE_REPOSITORY_ROOT),
        "project_id": project_id,
        "project_name": applied_plan["project"]["name"],
        "created_task_count": len(created_tasks),
        "worker": {
            "claimed": worker_result["claimed"],
            "run_status": worker_result["run_status"],
            "execution_mode": worker_result["execution_mode"],
            "token_accounting_mode": worker_result["token_accounting_mode"],
            "provider_receipt_id": worker_result["provider_receipt_id"],
            "fallback_note": "provider_mock/fallback is expected when no real OPENAI_API_KEY is available.",
        },
        "provider_configured": provider_summary["configured"],
        "team_control_budget_policy": team_control["budget_policy"],
        "repository_binding": {
            "root_path": repository_binding["root_path"],
            "default_base_branch": repository_binding["default_base_branch"],
        },
        "snapshot_file_count": snapshot_refresh["file_count"],
        "change_session_guard_status": clean_change_session["guard_status"],
        "locator_candidate_count": locator_result["candidate_count"],
        "context_pack_file_count": context_pack["included_file_count"],
        "change_batch_id": change_batch["id"],
        "preflight_status": preflight_status,
        "commands_run": commands_run,
        "blocked_before": blocked_gate["blocked"],
        "approve_blocked_status_code": approve_while_blocked.status_code,
        "evidence_package_key": evidence_package["package_key"],
        "evidence_changed_file_count": evidence_package["diff_summary"]["metrics"][
            "changed_file_count"
        ],
        "commit_candidate_version": commit_candidate["current_version_number"],
        "release_checklist_status": release_checklist["status"],
        "release_gate_status": gate_after_git_commit["status"],
        "release_qualification_established": gate_after_git_commit[
            "release_qualification_established"
        ],
        "apply_local_status": apply_local["status"],
        "apply_local_changed_files": apply_local["changed_files"],
        "apply_local_verification_passed": apply_local["verification_passed"],
        "git_commit_status": git_commit["status"],
        "git_commit_sha": git_commit["commit_sha"],
        "git_write_actions_triggered": gate_after_git_commit[
            "git_write_actions_triggered"
        ],
        "committed_files": committed_files,
        "demo_output": demo_output["output"],
        "repository_day15_status": repository_day15_flow["overall_status"],
        "project_day15_status": project_day15_flow["overall_status"],
        "approvals_day15_selected_status": approvals_day15_judgement["selected_status"],
        "cost_dashboard": {
            "run_count": cost_dashboard["run_count"],
            "provider_reported_run_count": cost_dashboard["fallback_contract"][
                "provider_reported_run_count"
            ],
            "provider_cache_reported_run_count": cost_dashboard["provider_cache"][
                "reported_run_count"
            ],
            "budget_policy_source": cost_dashboard["budget_policy_source"],
        },
        "closure_diagnostics": {
            "overall_status": closure_diagnostics["overall_status"],
            "blocking_reason_codes": closure_diagnostics["blocking_reason_codes"],
            "run_count": closure_diagnostics["task_runtime"]["run_count"],
            "change_batch_count": closure_diagnostics["governance"]["change_batch_count"],
            "commit_candidate_count": closure_diagnostics["governance"][
                "commit_candidate_count"
            ],
        },
    }
    SMOKE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SMOKE_REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report["report_path"] = str(SMOKE_REPORT_PATH)
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
