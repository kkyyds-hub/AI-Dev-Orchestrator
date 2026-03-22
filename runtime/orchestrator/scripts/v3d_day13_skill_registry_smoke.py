"""V3-D Day13 smoke checks for the Skill registry and role bindings."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v3-day13-skill-registry-smoke"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _prepare_env() -> None:
    if SMOKE_RUNTIME_DATA_DIR.exists():
        shutil.rmtree(SMOKE_RUNTIME_DATA_DIR)
    SMOKE_RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)

    os.environ["RUNTIME_DATA_DIR"] = str(SMOKE_RUNTIME_DATA_DIR)
    os.environ["DAILY_BUDGET_USD"] = "0.10"
    os.environ["SESSION_BUDGET_USD"] = "0.30"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"


def main() -> None:
    """Exercise the Day13 Skill registry workflow end to end."""

    _prepare_env()

    from fastapi.testclient import TestClient

    from app.core.db import init_database
    from app.main import app

    init_database()

    with TestClient(app) as client:
        project_response = client.post(
            "/projects",
            json={
                "name": "Day13 Skill Registry Smoke",
                "summary": "验证 Skill 注册中心、版本记录与项目角色 Skill 绑定闭环。",
                "stage": "planning",
            },
        )
        _assert(
            project_response.status_code == 201,
            f"project create failed: {project_response.status_code}",
        )
        project_payload = project_response.json()
        project_id = project_payload["id"]

        initial_registry_response = client.get("/skills/registry")
        _assert(
            initial_registry_response.status_code == 200,
            f"initial skill registry failed: {initial_registry_response.status_code}",
        )
        initial_registry_payload = initial_registry_response.json()
        _assert(
            initial_registry_payload["total_skill_count"] == 12,
            "built-in Skill registry should seed twelve Day13 skills",
        )
        quality_gate_initial = next(
            skill
            for skill in initial_registry_payload["skills"]
            if skill["code"] == "quality_gate"
        )
        _assert(
            quality_gate_initial["current_version"] == "1.0.0",
            "quality_gate should start at v1.0.0",
        )

        initial_bindings_response = client.get(
            f"/skills/projects/{project_id}/bindings"
        )
        _assert(
            initial_bindings_response.status_code == 200,
            f"initial project skill bindings failed: {initial_bindings_response.status_code}",
        )
        initial_bindings_payload = initial_bindings_response.json()
        _assert(
            initial_bindings_payload["total_roles"] == 4,
            "new project should expose four role binding groups",
        )
        _assert(
            initial_bindings_payload["total_bound_skills"] == 12,
            "default role bindings should cover the built-in Day05 default skill slots",
        )
        reviewer_initial = next(
            role
            for role in initial_bindings_payload["roles"]
            if role["role_code"] == "reviewer"
        )
        quality_gate_binding_before_upgrade = next(
            skill
            for skill in reviewer_initial["skills"]
            if skill["skill_code"] == "quality_gate"
        )
        _assert(
            quality_gate_binding_before_upgrade["bound_version"] == "1.0.0",
            "reviewer should initially bind quality_gate v1.0.0",
        )

        quality_gate_update_response = client.put(
            "/skills/quality_gate",
            json={
                "name": "质量闸门",
                "summary": "帮助评审角色针对验收标准给出放行、阻塞或返工建议。",
                "purpose": "把 Day10-Day12 的审批判断进一步前移到角色层面，同时补齐更细的老板审批前质量自检口径。",
                "applicable_role_codes": ["reviewer"],
                "enabled": True,
                "version": "1.1.0",
                "change_note": "新增审批前质量自检口径，并保留 Day12 返工链路说明。",
            },
        )
        _assert(
            quality_gate_update_response.status_code == 200,
            f"quality_gate update failed: {quality_gate_update_response.status_code}",
        )
        quality_gate_update_payload = quality_gate_update_response.json()
        _assert(
            quality_gate_update_payload["current_version"] == "1.1.0",
            "quality_gate should be upgraded to v1.1.0",
        )
        _assert(
            [item["version"] for item in quality_gate_update_payload["version_history"]]
            == ["1.0.0", "1.1.0"],
            "quality_gate should keep both v1.0.0 and v1.1.0 in history",
        )

        custom_skill_response = client.put(
            "/skills/approval_traceability",
            json={
                "name": "审批链路回放",
                "summary": "帮助产品和评审角色回看项目内的重要审批判断、返工原因与最新结论。",
                "purpose": "让角色在交接时能够快速回顾关键审批动作，避免 Day10-Day12 的审批语境在角色之间丢失。",
                "applicable_role_codes": ["product_manager", "reviewer"],
                "enabled": True,
                "version": "1.0.0",
                "change_note": "新增跨角色审批链路回放 Skill。",
            },
        )
        _assert(
            custom_skill_response.status_code == 200,
            f"custom skill create failed: {custom_skill_response.status_code}",
        )
        custom_skill_payload = custom_skill_response.json()
        _assert(
            custom_skill_payload["code"] == "approval_traceability",
            "custom skill should be stored under its stable code",
        )

        registry_after_updates_response = client.get("/skills/registry")
        _assert(
            registry_after_updates_response.status_code == 200,
            "registry reload after updates failed",
        )
        registry_after_updates_payload = registry_after_updates_response.json()
        _assert(
            registry_after_updates_payload["total_skill_count"] == 13,
            "registry should include the custom Day13 skill after creation",
        )

        bindings_after_upgrade_response = client.get(
            f"/skills/projects/{project_id}/bindings"
        )
        _assert(
            bindings_after_upgrade_response.status_code == 200,
            "project skill bindings reload after upgrade failed",
        )
        bindings_after_upgrade_payload = bindings_after_upgrade_response.json()
        reviewer_after_upgrade = next(
            role
            for role in bindings_after_upgrade_payload["roles"]
            if role["role_code"] == "reviewer"
        )
        quality_gate_after_upgrade = next(
            skill
            for skill in reviewer_after_upgrade["skills"]
            if skill["skill_code"] == "quality_gate"
        )
        _assert(
            quality_gate_after_upgrade["bound_version"] == "1.0.0",
            "existing project bindings should keep the previously bound quality_gate version",
        )
        _assert(
            quality_gate_after_upgrade["registry_current_version"] == "1.1.0",
            "binding view should surface the newer registry version",
        )
        _assert(
            quality_gate_after_upgrade["upgrade_available"] is True,
            "binding view should mark outdated role bindings",
        )

        reviewer_rebind_response = client.put(
            f"/skills/projects/{project_id}/bindings/reviewer",
            json={
                "skill_codes": [
                    "review_checklist",
                    "quality_gate",
                    "risk_replay",
                    "approval_traceability",
                ]
            },
        )
        _assert(
            reviewer_rebind_response.status_code == 200,
            f"reviewer rebind failed: {reviewer_rebind_response.status_code}",
        )
        reviewer_rebind_payload = reviewer_rebind_response.json()
        _assert(
            reviewer_rebind_payload["bound_skill_count"] == 4,
            "reviewer should bind four skills after adding the custom skill",
        )
        quality_gate_rebound = next(
            skill
            for skill in reviewer_rebind_payload["skills"]
            if skill["skill_code"] == "quality_gate"
        )
        _assert(
            quality_gate_rebound["bound_version"] == "1.1.0",
            "rebinding should pick the latest registry version",
        )
        _assert(
            quality_gate_rebound["upgrade_available"] is False,
            "rebinding should clear the outdated marker",
        )

        final_bindings_response = client.get(f"/skills/projects/{project_id}/bindings")
        _assert(
            final_bindings_response.status_code == 200,
            "final project skill bindings reload failed",
        )
        final_bindings_payload = final_bindings_response.json()
        final_reviewer = next(
            role for role in final_bindings_payload["roles"] if role["role_code"] == "reviewer"
        )
        _assert(
            any(
                skill["skill_code"] == "approval_traceability"
                for skill in final_reviewer["skills"]
            ),
            "reviewer should retain the custom skill after rebinding",
        )

    report = {
        "project": {
            "id": project_id,
            "name": project_payload["name"],
        },
        "registry": {
            "initial_skill_count": initial_registry_payload["total_skill_count"],
            "final_skill_count": registry_after_updates_payload["total_skill_count"],
            "version_record_count": registry_after_updates_payload["version_record_count"],
        },
        "reviewer_binding": {
            "initial_skill_codes": [skill["skill_code"] for skill in reviewer_initial["skills"]],
            "outdated_quality_gate": {
                "bound_version": quality_gate_after_upgrade["bound_version"],
                "registry_current_version": quality_gate_after_upgrade["registry_current_version"],
                "upgrade_available": quality_gate_after_upgrade["upgrade_available"],
            },
            "final_skill_codes": [skill["skill_code"] for skill in final_reviewer["skills"]],
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
