"""V3-B Day05 smoke checks for the role catalog and project identity config."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
from uuid import uuid4


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v3-day05-role-catalog-smoke"


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
    """Exercise the Day05 role catalog workflow end to end."""

    _prepare_env()

    from fastapi.testclient import TestClient

    from app.core.db import init_database
    from app.main import app

    init_database()

    with TestClient(app) as client:
        project_response = client.post(
            "/projects",
            json={
                "name": "Day05 角色目录 Smoke",
                "summary": "验证系统内置角色目录、项目角色启用配置以及角色身份编辑闭环。",
                "stage": "planning",
            },
        )
        _assert(
            project_response.status_code == 201,
            f"project create failed: {project_response.status_code}",
        )
        project_payload = project_response.json()
        project_id = project_payload["id"]

        catalog_response = client.get("/roles/catalog")
        _assert(catalog_response.status_code == 200, "role catalog request failed")
        catalog_payload = catalog_response.json()
        catalog_codes = [item["code"] for item in catalog_payload]
        _assert(
            catalog_codes
            == [
                "product_manager",
                "architect",
                "engineer",
                "reviewer",
            ],
            f"unexpected role catalog codes: {catalog_codes}",
        )
        _assert(
            all(item["default_skill_slots"] for item in catalog_payload),
            "each built-in role should expose default skill slots",
        )

        initial_project_roles_response = client.get(f"/roles/projects/{project_id}")
        _assert(
            initial_project_roles_response.status_code == 200,
            "project role catalog request failed",
        )
        initial_project_roles_payload = initial_project_roles_response.json()
        _assert(
            initial_project_roles_payload["available_role_count"] == 4,
            "new project should be seeded with four built-in roles",
        )
        _assert(
            initial_project_roles_payload["enabled_role_count"] == 4,
            "new project should enable the built-in roles by default",
        )

        reviewer_before_update = next(
            role
            for role in initial_project_roles_payload["roles"]
            if role["role_code"] == "reviewer"
        )
        _assert(
            reviewer_before_update["name"] == "评审者",
            "reviewer role should expose the built-in default name before editing",
        )

        reviewer_update_response = client.put(
            f"/roles/projects/{project_id}/reviewer",
            json={
                "enabled": False,
                "name": "质量评审",
                "summary": "负责在交付前审查实现结果、风险与回退建议。",
                "responsibilities": [
                    "复核交付结果是否满足验收口径",
                    "整理风险、缺口和返工建议",
                    "形成放行或阻塞结论",
                ],
                "input_boundary": [
                    "待评审代码改动与运行日志",
                    "项目验收标准与阶段守卫要求",
                    "工程实现说明与已知风险列表",
                ],
                "output_boundary": [
                    "评审意见与风险摘要",
                    "返工建议或阻塞结论",
                    "供老板继续决策的审查结论",
                ],
                "default_skill_slots": ["审查清单", "质量闸门", "回归建议"],
                "custom_notes": "Day05 smoke: reviewer is customized for this project only.",
                "sort_order": 40,
            },
        )
        _assert(
            reviewer_update_response.status_code == 200,
            f"reviewer update failed: {reviewer_update_response.status_code}",
        )
        reviewer_update_payload = reviewer_update_response.json()
        _assert(reviewer_update_payload["enabled"] is False, "reviewer should be disabled")
        _assert(reviewer_update_payload["name"] == "质量评审", "reviewer name not updated")
        _assert(
            reviewer_update_payload["custom_notes"]
            == "Day05 smoke: reviewer is customized for this project only.",
            "reviewer custom notes not persisted",
        )

        refreshed_project_roles_response = client.get(f"/roles/projects/{project_id}")
        _assert(
            refreshed_project_roles_response.status_code == 200,
            "refreshed project role catalog request failed",
        )
        refreshed_project_roles_payload = refreshed_project_roles_response.json()
        refreshed_reviewer = next(
            role
            for role in refreshed_project_roles_payload["roles"]
            if role["role_code"] == "reviewer"
        )
        _assert(
            refreshed_project_roles_payload["enabled_role_count"] == 3,
            "enabled role count should drop after disabling reviewer",
        )
        _assert(
            refreshed_reviewer["default_skill_slots"] == ["审查清单", "质量闸门", "回归建议"],
            "reviewer skill slot overrides not persisted",
        )

        catalog_after_update_response = client.get("/roles/catalog")
        _assert(
            catalog_after_update_response.status_code == 200,
            "catalog request after update failed",
        )
        catalog_after_update_payload = catalog_after_update_response.json()
        reviewer_catalog_entry = next(
            item for item in catalog_after_update_payload if item["code"] == "reviewer"
        )
        _assert(
            reviewer_catalog_entry["name"] == "评审者",
            "system catalog should remain immutable after project-level editing",
        )

        second_project_response = client.post(
            "/projects",
            json={
                "name": "Day05 第二项目",
                "summary": "验证项目之间的角色配置相互隔离。",
                "stage": "planning",
            },
        )
        _assert(second_project_response.status_code == 201, "second project create failed")
        second_project_id = second_project_response.json()["id"]
        second_project_roles_response = client.get(f"/roles/projects/{second_project_id}")
        _assert(
            second_project_roles_response.status_code == 200,
            "second project role catalog request failed",
        )
        second_project_roles_payload = second_project_roles_response.json()
        second_project_reviewer = next(
            role
            for role in second_project_roles_payload["roles"]
            if role["role_code"] == "reviewer"
        )
        _assert(
            second_project_reviewer["enabled"] is True
            and second_project_reviewer["name"] == "评审者",
            "project role edits should not leak into another project",
        )

        missing_project_response = client.get(f"/roles/projects/{uuid4()}")
        _assert(
            missing_project_response.status_code == 404,
            "missing project role catalog should return 404",
        )

        project_detail_response = client.get(f"/projects/{project_id}")
        _assert(
            project_detail_response.status_code == 200,
            "project detail should remain available after role config changes",
        )

    report = {
        "project_id": project_id,
        "catalog_codes": catalog_codes,
        "enabled_role_count_before_edit": initial_project_roles_payload["enabled_role_count"],
        "enabled_role_count_after_edit": refreshed_project_roles_payload["enabled_role_count"],
        "customized_reviewer": refreshed_reviewer,
        "second_project_reviewer": second_project_reviewer,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
