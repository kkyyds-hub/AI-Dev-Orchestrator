"""Tests for AI Project Director Plan Version endpoints and service.

BCG-02 Phase1: plan version generation, listing, confirmation.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlalchemy import func, select

from app.api.router import api_router
from app.api.routes.project_director import (
    _get_plan_service,
    _get_service,
    PlanVersionResponse,
)
from app.core.db import get_db_session
from app.core.db_tables import ORMBase, TaskTable
from app.domain.project_director_plan_version import PlanVersionStatus
from app.domain.project_director_session import ProjectDirectorSessionStatus
from app.domain.project_role import ProjectRoleCode
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.services.project_director_plan_service import ProjectDirectorPlanService
from app.services.project_director_plan_service import ProjectDirectorPlanGenerationError
from app.services.project_director_service import ProjectDirectorService


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def sqlite_session_factory(tmp_path):
    db_path = tmp_path / "orchestrator-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


@pytest.fixture()
def db_session(sqlite_session_factory):
    session = sqlite_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(sqlite_session_factory):
    app = FastAPI()
    app.include_router(api_router)

    def override_get_db_session():
        session = sqlite_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session

    def override_get_service():
        session = sqlite_session_factory()
        try:
            repo = ProjectDirectorSessionRepository(session)
            yield ProjectDirectorService(
                session_repository=repo,
                provider_config_service=_FakeProviderConfigService(configured=False),
            )
        finally:
            session.close()

    def override_get_plan_service():
        session = sqlite_session_factory()
        try:
            plan_repo = ProjectDirectorPlanVersionRepository(session)
            session_repo = ProjectDirectorSessionRepository(session)
            yield ProjectDirectorPlanService(
                plan_version_repository=plan_repo,
                session_repository=session_repo,
                provider_config_service=_FakeProviderConfigService(configured=False),
            )
        finally:
            session.close()

    app.dependency_overrides[_get_service] = override_get_service
    app.dependency_overrides[_get_plan_service] = override_get_plan_service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def plan_service(db_session):
    plan_repo = ProjectDirectorPlanVersionRepository(db_session)
    session_repo = ProjectDirectorSessionRepository(db_session)
    return ProjectDirectorPlanService(
        plan_version_repository=plan_repo,
        session_repository=session_repo,
        provider_config_service=_FakeProviderConfigService(configured=False),
    )


@pytest.fixture()
def session_service(db_session):
    repo = ProjectDirectorSessionRepository(db_session)
    return ProjectDirectorService(
        session_repository=repo,
        provider_config_service=_FakeProviderConfigService(configured=False),
    )


def _prepare_confirmed_session(client) -> str:
    """Create a session through the full flow and return session_id."""
    # 1. Create session
    resp = client.post(
        "/project-director/sessions",
        json={
            "goal_text": "构建一个用户认证系统，包括登录、注册、密码重置，"
            "范围明确为后端API，技术栈为FastAPI+SQLite，验收标准为所有接口通过测试"
        },
    )
    assert resp.status_code == 201
    session_id = resp.json()["id"]
    questions = resp.json()["clarifying_questions"]

    # 2. Answer all questions
    answers = [
        {"question_id": q["id"], "answer": f"回答内容 {i}"}
        for i, q in enumerate(questions)
    ]
    resp = client.post(
        f"/project-director/sessions/{session_id}/answers",
        json={"answers": answers},
    )
    assert resp.status_code == 200

    # 3. Confirm
    resp = client.post(f"/project-director/sessions/{session_id}/confirm")
    assert resp.status_code == 200
    return session_id


class _FakeProviderConfigService:
    def __init__(self, *, configured: bool) -> None:
        self.configured = configured

    def resolve_openai_runtime_config(self):
        return SimpleNamespace(
            api_key="test-provider-key" if self.configured else None,
            base_url="https://provider.invalid/v1",
            timeout_seconds=1,
            detected_provider_type="openai_compatible",
            model_names={"balanced": "test-plan-model"},
        )


def _provider_plan_payload() -> str:
    """Return one complete provider JSON plan without calling a real provider."""

    return json.dumps(
        {
            "plan_summary": "AI provider 生成的作战计划：围绕目标拆分范围、角色和验收。",
            "phases": [
                {
                    "sequence": 1,
                    "name": "AI 范围收口",
                    "goal": "确认范围、不做范围和验收口径",
                    "task_count_hint": 2,
                },
                {
                    "sequence": 2,
                    "name": "AI 实施准备",
                    "goal": "形成可审阅任务与验证建议",
                    "task_count_hint": 3,
                },
            ],
            "proposed_tasks": [
                {
                    "title": "AI 需求复核",
                    "description": "复核目标、约束和澄清回答",
                    "suggested_role_code": ProjectRoleCode.ARCHITECT.value,
                    "priority_hint": "high",
                },
                {
                    "title": "AI 验证设计",
                    "description": "设计最小验证命令和证据要求",
                    "suggested_role_code": ProjectRoleCode.REVIEWER.value,
                    "priority_hint": "normal",
                },
            ],
            "acceptance_criteria": ["用户确认草案后才允许进入任务创建"],
            "risks": ["草案阶段不得误触发 Worker 或仓库写入"],
            "project_scope": {
                "in_scope": ["生成可审核作战计划草案"],
                "out_of_scope": ["不自动创建任务", "不调用 Worker", "不写仓库"],
                "assumptions": ["后续执行必须由用户单独触发"],
            },
            "agent_team_suggestions": [
                {
                    "role_code": ProjectRoleCode.PRODUCT_MANAGER.value,
                    "role_name": "产品负责人",
                    "responsibility": "确认范围和验收标准",
                    "collaboration_notes": ["先确认目标"],
                },
                {
                    "role_code": ProjectRoleCode.REVIEWER.value,
                    "role_name": "评审者",
                    "responsibility": "确认验证机制和证据完整性",
                    "collaboration_notes": ["后续执行前复核"],
                },
            ],
            "skill_binding_suggestions": [
                {
                    "skill_code": "verify-v5-runtime-and-regression",
                    "owner_role_code": ProjectRoleCode.REVIEWER.value,
                    "usage": "后续实现完成后运行验证",
                    "activation_stage": "验证",
                    "binding_mode": "suggested",
                    "reason": "草案阶段只建议，不创建绑定",
                }
            ],
            "verification_mechanisms": [
                {
                    "name": "草案合同检查",
                    "command_or_method": "pytest tests/test_project_director_plan_versions.py",
                    "evidence_required": "source/source_detail 和安全字段存在",
                    "owner_role_code": ProjectRoleCode.REVIEWER.value,
                    "purpose": "确保 AI 草案合同完整",
                    "risk_level": "high",
                    "requires_user_confirmation": True,
                }
            ],
            "repository_binding_suggestions": [
                {
                    "binding_type": "review_only",
                    "binding_mode": "suggested",
                    "target": "当前项目关联仓库",
                    "branch": "未指定",
                    "focus_paths": ["runtime/orchestrator/app/"],
                    "usage": "只作为后续审阅线索",
                    "safety_note": "草案阶段不写仓库、不提交代码",
                }
            ],
            "deliverable_boundaries": [
                {
                    "name": "AI 草案审阅包",
                    "description": "让用户判断是否批准后续任务创建",
                    "owner_role_code": ProjectRoleCode.PRODUCT_MANAGER.value,
                    "required_contents": ["范围", "不做范围", "验收标准"],
                    "done_definition": "用户能明确是否通过草案",
                    "acceptance_signal": "用户点击通过草案",
                }
            ],
            "complexity_assessment": {
                "level": "medium",
                "label": "中等复杂度",
                "score": 3,
                "recommended_agent_count": 3,
                "drivers": ["AI provider 根据目标评估"],
                "mitigation_suggestions": ["保留人工审核 Gate"],
            },
        },
        ensure_ascii=False,
    )


# ── API Tests: Create Plan Version ──────────────────────────────────


class TestCreatePlanVersion:
    def test_create_from_confirmed_session(self, client):
        session_id = _prepare_confirmed_session(client)

        resp = client.post(
            f"/project-director/sessions/{session_id}/plan-versions"
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["session_id"] == session_id
        assert data["version_no"] == 1
        assert data["status"] == PlanVersionStatus.PENDING_CONFIRMATION.value
        assert len(data["plan_summary"]) > 0
        assert len(data["phases"]) >= 2
        assert len(data["proposed_tasks"]) >= 4
        # All suggested_role_code values must be valid ProjectRoleCode members
        valid_roles = {r.value for r in ProjectRoleCode}
        for task in data["proposed_tasks"]:
            assert task["suggested_role_code"] in valid_roles, (
                f"Invalid role code: {task['suggested_role_code']}"
            )
        assert len(data["forbidden_actions"]) >= 3
        assert "不自动创建任务" in data["forbidden_actions"]
        assert data["project_scope"]["in_scope"]
        assert data["project_scope"]["out_of_scope"]
        assert data["agent_team_suggestions"]
        assert all(item["role_name"] for item in data["agent_team_suggestions"])
        assert data["skill_binding_suggestions"]
        assert all(item["binding_mode"] for item in data["skill_binding_suggestions"])
        assert all(item["reason"] for item in data["skill_binding_suggestions"])
        assert data["verification_mechanisms"]
        assert all(item["purpose"] for item in data["verification_mechanisms"])
        assert all(item["risk_level"] in {"low", "normal", "high"} for item in data["verification_mechanisms"])
        assert all(
            isinstance(item["requires_user_confirmation"], bool)
            for item in data["verification_mechanisms"]
        )
        assert all(
            item["requires_user_confirmation"] is True
            for item in data["verification_mechanisms"]
            if item["risk_level"] == "high"
        )
        assert data["repository_binding_suggestions"]
        assert all(item["binding_mode"] for item in data["repository_binding_suggestions"])
        assert all("branch" in item for item in data["repository_binding_suggestions"])
        assert all(isinstance(item["focus_paths"], list) for item in data["repository_binding_suggestions"])
        assert data["deliverable_boundaries"]
        assert all(item["description"] for item in data["deliverable_boundaries"])
        assert all(item["acceptance_signal"] for item in data["deliverable_boundaries"])
        assert data["complexity_assessment"]["score"] >= 1
        assert data["complexity_assessment"]["level"] in {"simple", "medium", "complex", "large"}
        assert data["complexity_assessment"]["label"]
        assert data["complexity_assessment"]["recommended_agent_count"] >= 1
        assert data["needs_user_confirmation"] is True
        assert data["gate_conclusion"] == "Partial"

    def test_frontend_task_uses_engineer_role(self, client):
        """Frontend tasks must use engineer, not frontend_developer."""
        session_id = _prepare_confirmed_session(client)
        resp = client.post(
            f"/project-director/sessions/{session_id}/plan-versions"
        )
        data = resp.json()
        frontend_tasks = [
            t for t in data["proposed_tasks"] if "前端" in t["title"]
        ]
        if frontend_tasks:
            assert frontend_tasks[0]["suggested_role_code"] == ProjectRoleCode.ENGINEER.value

    def test_testing_task_uses_reviewer_role(self, client):
        """Testing tasks must use reviewer, not tester."""
        session_id = _prepare_confirmed_session(client)
        resp = client.post(
            f"/project-director/sessions/{session_id}/plan-versions"
        )
        data = resp.json()
        test_tasks = [
            t for t in data["proposed_tasks"] if "测试" in t["title"]
        ]
        if test_tasks:
            assert test_tasks[0]["suggested_role_code"] == ProjectRoleCode.REVIEWER.value

    def test_no_developer_or_tester_role_codes(self, client):
        """No proposed task should use invalid role codes like developer or tester."""
        session_id = _prepare_confirmed_session(client)
        resp = client.post(
            f"/project-director/sessions/{session_id}/plan-versions"
        )
        data = resp.json()
        invalid_codes = {"developer", "frontend_developer", "tester"}
        for task in data["proposed_tasks"]:
            assert task["suggested_role_code"] not in invalid_codes, (
                f"Found invalid role code: {task['suggested_role_code']}"
            )

    def test_create_from_unconfirmed_session_returns_409(self, client):
        # Create a session but don't confirm
        resp = client.post(
            "/project-director/sessions",
            json={"goal_text": "构建一个用户认证系统，包括登录、注册"},
        )
        session_id = resp.json()["id"]
        questions = resp.json()["clarifying_questions"]

        # Answer all questions
        answers = [
            {"question_id": q["id"], "answer": f"回答 {i}"}
            for i, q in enumerate(questions)
        ]
        client.post(
            f"/project-director/sessions/{session_id}/answers",
            json={"answers": answers},
        )

        # Session is ready_to_confirm, NOT confirmed → should fail
        resp = client.post(
            f"/project-director/sessions/{session_id}/plan-versions"
        )
        assert resp.status_code == 409
        assert "confirmed" in resp.json()["detail"].lower()

    def test_create_from_nonexistent_session_returns_404(self, client):
        resp = client.post(
            f"/project-director/sessions/{uuid4()}/plan-versions"
        )
        assert resp.status_code == 404

    def test_version_no_increments(self, client):
        session_id = _prepare_confirmed_session(client)

        # First version
        resp1 = client.post(
            f"/project-director/sessions/{session_id}/plan-versions"
        )
        assert resp1.status_code == 201
        assert resp1.json()["version_no"] == 1

        # Second version
        resp2 = client.post(
            f"/project-director/sessions/{session_id}/plan-versions"
        )
        assert resp2.status_code == 201
        assert resp2.json()["version_no"] == 2

        # Third version
        resp3 = client.post(
            f"/project-director/sessions/{session_id}/plan-versions"
        )
        assert resp3.status_code == 201
        assert resp3.json()["version_no"] == 3

    def test_plan_version_has_all_required_fields(self, client):
        session_id = _prepare_confirmed_session(client)

        resp = client.post(
            f"/project-director/sessions/{session_id}/plan-versions"
        )
        data = resp.json()
        assert "id" in data
        assert "session_id" in data
        assert "version_no" in data
        assert "status" in data
        assert "plan_summary" in data
        assert "phases" in data
        assert "proposed_tasks" in data
        assert "acceptance_criteria" in data
        assert "risks" in data
        assert "project_scope" in data
        assert "agent_team_suggestions" in data
        assert "skill_binding_suggestions" in data
        assert "verification_mechanisms" in data
        assert "repository_binding_suggestions" in data
        assert "deliverable_boundaries" in data
        assert "complexity_assessment" in data
        assert "role_name" in data["agent_team_suggestions"][0]
        assert "binding_mode" in data["skill_binding_suggestions"][0]
        assert "reason" in data["skill_binding_suggestions"][0]
        assert "purpose" in data["verification_mechanisms"][0]
        assert "risk_level" in data["verification_mechanisms"][0]
        assert "requires_user_confirmation" in data["verification_mechanisms"][0]
        assert "branch" in data["repository_binding_suggestions"][0]
        assert "focus_paths" in data["repository_binding_suggestions"][0]
        assert "description" in data["deliverable_boundaries"][0]
        assert "acceptance_signal" in data["deliverable_boundaries"][0]
        assert "label" in data["complexity_assessment"]
        assert "recommended_agent_count" in data["complexity_assessment"]
        assert "source" in data
        assert "source_detail" in data
        assert data["source"] in {"ai", "rule_fallback"}
        assert isinstance(data["source_detail"], str)
        assert "forbidden_actions" in data
        assert "confirmed_at" in data
        assert "next_action" in data
        assert "missing_info" in data
        assert "needs_user_confirmation" in data
        assert "gate_conclusion" in data


# ── API Tests: List Plan Versions ───────────────────────────────────


class TestListPlanVersions:
    def test_list_empty(self, client):
        session_id = _prepare_confirmed_session(client)
        resp = client.get(
            f"/project-director/sessions/{session_id}/plan-versions"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == session_id
        assert data["plan_versions"] == []

    def test_list_multiple_versions(self, client):
        session_id = _prepare_confirmed_session(client)

        # Create 3 versions
        for _ in range(3):
            client.post(
                f"/project-director/sessions/{session_id}/plan-versions"
            )

        resp = client.get(
            f"/project-director/sessions/{session_id}/plan-versions"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["plan_versions"]) == 3
        # Newest first
        assert data["plan_versions"][0]["version_no"] == 3
        assert data["plan_versions"][2]["version_no"] == 1

    def test_list_nonexistent_session_returns_404(self, client):
        resp = client.get(
            f"/project-director/sessions/{uuid4()}/plan-versions"
        )
        assert resp.status_code == 404


# ── API Tests: Get Plan Version ─────────────────────────────────────


class TestGetPlanVersion:
    def test_get_existing(self, client):
        session_id = _prepare_confirmed_session(client)
        create_resp = client.post(
            f"/project-director/sessions/{session_id}/plan-versions"
        )
        pv_id = create_resp.json()["id"]

        resp = client.get(f"/project-director/plan-versions/{pv_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == pv_id
        assert data["session_id"] == session_id
        assert data["version_no"] == 1

    def test_get_nonexistent_returns_404(self, client):
        resp = client.get(f"/project-director/plan-versions/{uuid4()}")
        assert resp.status_code == 404


# ── API Tests: Confirm Plan Version ─────────────────────────────────


class TestConfirmPlanVersion:
    def _create_plan_version(self, client) -> tuple[str, str]:
        session_id = _prepare_confirmed_session(client)
        resp = client.post(
            f"/project-director/sessions/{session_id}/plan-versions"
        )
        return session_id, resp.json()["id"]

    def test_confirm_transitions_to_confirmed(self, client):
        _, pv_id = self._create_plan_version(client)

        resp = client.post(
            f"/project-director/plan-versions/{pv_id}/confirm"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == PlanVersionStatus.CONFIRMED.value
        assert data["confirmed_at"] is not None
        assert data["needs_user_confirmation"] is False
        assert "不自动创建任务" in data["forbidden_actions"]

    def test_confirm_twice_is_idempotent(self, client):
        _, pv_id = self._create_plan_version(client)

        resp1 = client.post(
            f"/project-director/plan-versions/{pv_id}/confirm"
        )
        assert resp1.status_code == 200
        assert resp1.json()["status"] == PlanVersionStatus.CONFIRMED.value

        resp2 = client.post(
            f"/project-director/plan-versions/{pv_id}/confirm"
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == PlanVersionStatus.CONFIRMED.value

    def test_confirm_nonexistent_returns_404(self, client):
        resp = client.post(
            f"/project-director/plan-versions/{uuid4()}/confirm"
        )
        assert resp.status_code == 404

    def test_confirm_not_pending_confirmation_returns_409(self, client):
        session_id = _prepare_confirmed_session(client)
        create_resp = client.post(
            f"/project-director/sessions/{session_id}/plan-versions"
        )
        pv_id = create_resp.json()["id"]

        # Confirm first time
        client.post(f"/project-director/plan-versions/{pv_id}/confirm")

        # Now try to confirm a non-pending_confirmation plan version
        # (already confirmed means not in pending_confirmation)
        # But confirmed is idempotent, so this case passes.
        # Instead, test a superseded plan version confirm
        # Create a second plan version and confirm it
        create_resp2 = client.post(
            f"/project-director/sessions/{session_id}/plan-versions"
        )
        pv_id2 = create_resp2.json()["id"]
        client.post(f"/project-director/plan-versions/{pv_id2}/confirm")

        # pv_id1 should now be superseded → confirming should 409
        resp = client.post(f"/project-director/plan-versions/{pv_id}/confirm")
        assert resp.status_code == 409

    def test_new_confirm_supersedes_previous(self, client):
        session_id = _prepare_confirmed_session(client)

        # Create and confirm version 1
        resp1 = client.post(
            f"/project-director/sessions/{session_id}/plan-versions"
        )
        pv1_id = resp1.json()["id"]
        client.post(f"/project-director/plan-versions/{pv1_id}/confirm")

        # Create and confirm version 2
        resp2 = client.post(
            f"/project-director/sessions/{session_id}/plan-versions"
        )
        pv2_id = resp2.json()["id"]
        client.post(f"/project-director/plan-versions/{pv2_id}/confirm")

        # Version 1 should now be superseded
        resp = client.get(f"/project-director/plan-versions/{pv1_id}")
        assert resp.json()["status"] == PlanVersionStatus.SUPERSEDED.value

        # Version 2 should be confirmed
        resp = client.get(f"/project-director/plan-versions/{pv2_id}")
        assert resp.json()["status"] == PlanVersionStatus.CONFIRMED.value

    def test_confirm_has_full_contract_fields(self, client):
        _, pv_id = self._create_plan_version(client)

        resp = client.post(
            f"/project-director/plan-versions/{pv_id}/confirm"
        )
        data = resp.json()
        assert "id" in data
        assert "plan_summary" in data
        assert "phases" in data
        assert "proposed_tasks" in data
        assert "forbidden_actions" in data
        assert "next_action" in data
        assert "needs_user_confirmation" in data
        assert "gate_conclusion" in data
        assert data["needs_user_confirmation"] is False

    def test_confirmed_plan_does_not_create_tasks(self, client, db_session):
        """Verify confirming a plan version does NOT create real tasks."""
        _, pv_id = self._create_plan_version(client)

        # Count tasks before confirming
        task_count_before = db_session.execute(
            select(func.count()).select_from(TaskTable)
        ).scalar_one()

        # Confirm the plan
        resp = client.post(
            f"/project-director/plan-versions/{pv_id}/confirm"
        )
        assert resp.status_code == 200

        # Count tasks after confirming — must be identical
        task_count_after = db_session.execute(
            select(func.count()).select_from(TaskTable)
        ).scalar_one()
        assert task_count_after == task_count_before, (
            f"TaskTable row count changed from {task_count_before} "
            f"to {task_count_after} after plan confirmation"
        )
        assert task_count_after == 0

        # Verify forbidden_actions are present
        data = resp.json()
        assert "不自动创建任务" in data["forbidden_actions"]
        assert "不自动调用 Worker" in data["forbidden_actions"]
        assert "不写仓库" in data["forbidden_actions"]
        assert "不把计划确认等同于执行完成" in data["forbidden_actions"]
        assert "不调用 planning/apply" in data["forbidden_actions"]

        # Verify gate_conclusion is Partial, not Pass
        assert "Partial" in data["gate_conclusion"]


class TestWorkbenchResume:
    def test_resume_empty_workbench_returns_no_active_flow(self, client):
        resp = client.get("/project-director/workbench/resume?mode=new-project")

        assert resp.status_code == 200
        data = resp.json()
        assert data["session"] is None
        assert data["plan_version"] is None
        assert data["source"] == "none"

    def test_resume_new_project_restores_latest_session_and_plan(self, client):
        session_id = _prepare_confirmed_session(client)
        plan_resp = client.post(
            f"/project-director/sessions/{session_id}/plan-versions"
        )
        assert plan_resp.status_code == 201
        plan_id = plan_resp.json()["id"]

        resp = client.get("/project-director/workbench/resume?mode=new-project")

        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "backend_recent_plan"
        assert data["session"]["id"] == session_id
        assert data["session"]["project_id"] is None
        assert data["plan_version"]["id"] == plan_id
        assert (
            data["plan_version"]["status"]
            == PlanVersionStatus.PENDING_CONFIRMATION.value
        )
        assert "恢复" in data["next_action"]

    def test_resume_new_project_restores_formal_project_task_creation(
        self, client
    ):
        session_id = _prepare_confirmed_session(client)
        plan_resp = client.post(
            f"/project-director/sessions/{session_id}/plan-versions"
        )
        assert plan_resp.status_code == 201
        plan_id = plan_resp.json()["id"]

        approve_resp = client.post(
            f"/project-director/plan-versions/{plan_id}/review",
            json={"action": "approve"},
        )
        assert approve_resp.status_code == 200
        assert (
            approve_resp.json()["reviewed_plan_version"]["status"]
            == PlanVersionStatus.CONFIRMED.value
        )

        create_resp = client.post(
            f"/project-director/plan-versions/{plan_id}/create-formal-project"
        )
        assert create_resp.status_code == 200
        created = create_resp.json()
        assert created["project_id"]
        assert created["created_task_ids"]

        resp = client.get("/project-director/workbench/resume?mode=new-project")

        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "backend_recent_task_creation"
        assert data["session"]["id"] == session_id
        assert data["plan_version"]["id"] == plan_id
        assert data["plan_version"]["status"] == PlanVersionStatus.CONFIRMED.value
        assert data["plan_version"]["project_id"] == created["project_id"]
        assert data["task_creation"]["plan_version_id"] == plan_id
        assert data["task_creation"]["project_id"] == created["project_id"]
        assert data["task_creation"]["created_task_ids"] == created["created_task_ids"]
        assert data["task_creation"]["task_count"] == created["task_count"]
        assert data["task_creation"]["status"] == "created"
        assert "正式项目与任务队列" in data["next_action"]


# ── Service Tests ───────────────────────────────────────────────────


class TestReviewPlanVersion:
    def _create_plan_version(self, client) -> tuple[str, str]:
        session_id = _prepare_confirmed_session(client)
        resp = client.post(
            f"/project-director/sessions/{session_id}/plan-versions"
        )
        assert resp.status_code == 201
        return session_id, resp.json()["id"]

    def test_reject_review_transitions_to_rejected(self, client):
        _, pv_id = self._create_plan_version(client)

        resp = client.post(
            f"/project-director/plan-versions/{pv_id}/review",
            json={"action": "reject", "feedback": "scope is still unclear"},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["action"] == "reject"
        assert payload["reviewed_plan_version"]["status"] == PlanVersionStatus.REJECTED.value
        assert payload["replacement_plan_version"] is None
        assert payload["next_action"] == "草案已拒绝，可重新生成或调整目标后再提交。"
        assert "?" not in payload["next_action"]

    def test_approve_review_returns_chinese_next_action(self, client):
        _, pv_id = self._create_plan_version(client)

        resp = client.post(
            f"/project-director/plan-versions/{pv_id}/review",
            json={"action": "approve"},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["action"] == "approve"
        assert payload["reviewed_plan_version"]["status"] == PlanVersionStatus.CONFIRMED.value
        assert payload["next_action"] == "草案已通过，可单独触发任务创建；不会自动执行。"
        assert "?" not in payload["next_action"]

    def test_request_changes_rejects_current_and_generates_new_version(self, client):
        session_id, pv_id = self._create_plan_version(client)

        resp = client.post(
            f"/project-director/plan-versions/{pv_id}/review",
            json={
                "action": "request_changes",
                "feedback": "Please split backend and frontend scope, and add clearer acceptance criteria.",
            },
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["action"] == "request_changes"
        assert payload["reviewed_plan_version"]["status"] == PlanVersionStatus.REJECTED.value
        assert payload["replacement_plan_version"] is not None
        assert payload["replacement_plan_version"]["status"] == PlanVersionStatus.PENDING_CONFIRMATION.value
        assert payload["replacement_plan_version"]["version_no"] == 2
        assert payload["next_action"] == "已生成整改版 v2，请重新审阅后再决定。"
        assert "?" not in payload["next_action"]
        assert "整改说明" in payload["replacement_plan_version"]["plan_summary"]
        assert "?" not in payload["replacement_plan_version"]["plan_summary"]
        assert any(
            risk.startswith("整改反馈需重点处理：")
            for risk in payload["replacement_plan_version"]["risks"]
        )
        assert all("?" not in risk for risk in payload["replacement_plan_version"]["risks"])
        assert "Please split backend and frontend scope" in payload["replacement_plan_version"]["plan_summary"]
        replacement = payload["replacement_plan_version"]
        assert replacement["project_scope"]["out_of_scope"]
        assert any(
            "Please split backend and frontend scope" in item
            for item in replacement["project_scope"]["assumptions"]
        )
        assert replacement["agent_team_suggestions"]
        assert all(item["role_name"] for item in replacement["agent_team_suggestions"])
        assert replacement["skill_binding_suggestions"]
        assert all(item["binding_mode"] == "suggested" for item in replacement["skill_binding_suggestions"])
        assert all(item["reason"] for item in replacement["skill_binding_suggestions"])
        assert replacement["verification_mechanisms"]
        assert all(item["purpose"] for item in replacement["verification_mechanisms"])
        assert all(item["risk_level"] in {"low", "normal", "high"} for item in replacement["verification_mechanisms"])
        assert all(isinstance(item["requires_user_confirmation"], bool) for item in replacement["verification_mechanisms"])
        assert all(
            item["requires_user_confirmation"] is True
            for item in replacement["verification_mechanisms"]
            if item["risk_level"] == "high"
        )
        assert replacement["repository_binding_suggestions"]
        assert all(item["binding_mode"] == "suggested" for item in replacement["repository_binding_suggestions"])
        assert all("branch" in item for item in replacement["repository_binding_suggestions"])
        assert all(isinstance(item["focus_paths"], list) for item in replacement["repository_binding_suggestions"])
        assert replacement["deliverable_boundaries"]
        assert all(item["description"] for item in replacement["deliverable_boundaries"])
        assert all(item["acceptance_signal"] for item in replacement["deliverable_boundaries"])
        assert replacement["complexity_assessment"]["score"] >= 1
        assert replacement["complexity_assessment"]["level"] in {"simple", "medium", "complex", "large"}
        assert replacement["complexity_assessment"]["label"]
        assert replacement["complexity_assessment"]["recommended_agent_count"] >= 1
        assert any(
            "Please split backend and frontend scope" in item
            for item in replacement["complexity_assessment"]["drivers"]
        )

        history = client.get(f"/project-director/sessions/{session_id}/plan-versions")
        assert history.status_code == 200
        versions = history.json()["plan_versions"]
        assert len(versions) == 2
        assert versions[0]["version_no"] == 2
        assert versions[1]["status"] == PlanVersionStatus.REJECTED.value

    def test_request_changes_requires_feedback(self, client):
        _, pv_id = self._create_plan_version(client)

        resp = client.post(
            f"/project-director/plan-versions/{pv_id}/review",
            json={"action": "request_changes", "feedback": "   "},
        )
        assert resp.status_code == 422
        assert "feedback" in resp.json()["detail"].lower()


class TestPlanService:
    def _confirmed_session(self, session_service):
        from app.domain.project_director_session import ClarifyingAnswer

        session_obj = session_service.create_session(
            goal_text="构建一个 AI 项目主管首次创建项目链路，范围包括草案生成和人工确认",
            constraints="不得自动调用 Worker，不得写仓库",
        )
        answers = [
            ClarifyingAnswer(question_id=q.id, answer=f"回答 {i}")
            for i, q in enumerate(session_obj.clarifying_questions)
        ]
        session_obj = session_service.submit_answers(session_obj.id, answers)
        return session_service.confirm_goal(session_obj.id)

    def test_full_plan_flow(self, session_service, plan_service):
        # 1. Create and confirm a session
        session_obj = session_service.create_session(
            goal_text="构建一个用户认证系统，包括登录、注册，范围明确为后端API",
            constraints="FastAPI + SQLite",
        )
        answers = [
            {"question_id": q.id, "answer": f"回答 {i}"}
            for i, q in enumerate(session_obj.clarifying_questions)
        ]
        from app.domain.project_director_session import ClarifyingAnswer

        session_obj = session_service.submit_answers(
            session_obj.id,
            [ClarifyingAnswer(**a) for a in answers],
        )
        session_obj = session_service.confirm_goal(session_obj.id)
        assert session_obj.status == ProjectDirectorSessionStatus.CONFIRMED

        # 2. Create plan version
        pv = plan_service.create_plan_version(session_id=session_obj.id)
        assert pv.status == PlanVersionStatus.PENDING_CONFIRMATION
        assert pv.version_no == 1
        assert len(pv.phases) >= 2
        assert len(pv.proposed_tasks) >= 4
        # All role codes must be valid ProjectRoleCode members
        for task in pv.proposed_tasks:
            assert isinstance(task.suggested_role_code, ProjectRoleCode)
            assert task.suggested_role_code in ProjectRoleCode

        # 3. Read plan version
        retrieved = plan_service.get_plan_version(pv.id)
        assert retrieved is not None
        assert retrieved.version_no == 1

        # 4. List plan versions
        versions = plan_service.list_plan_versions(session_obj.id)
        assert len(versions) == 1

        # 5. Confirm plan version
        confirmed = plan_service.confirm_plan_version(pv.id)
        assert confirmed.status == PlanVersionStatus.CONFIRMED
        assert confirmed.confirmed_at is not None

    def test_create_plan_version_uses_injected_provider_plan(
        self, db_session, session_service
    ):
        session_obj = self._confirmed_session(session_service)
        plan_repo = ProjectDirectorPlanVersionRepository(db_session)
        session_repo = ProjectDirectorSessionRepository(db_session)
        calls: list[tuple[str, str, str]] = []

        def fake_generator(
            model_name: str,
            prompt_text: str,
            request_id: str,
        ) -> tuple[str, str | None]:
            calls.append((model_name, prompt_text, request_id))
            assert model_name == "test-plan-model"
            assert request_id.startswith("project-director-plan-")
            assert "生成一份“可审核的项目作战计划草案”" in prompt_text
            return _provider_plan_payload(), "receipt-plan-test-1"

        service = ProjectDirectorPlanService(
            plan_version_repository=plan_repo,
            session_repository=session_repo,
            provider_config_service=_FakeProviderConfigService(configured=True),
            provider_text_generator=fake_generator,
        )

        pv = service.create_plan_version(session_id=session_obj.id)

        assert len(calls) == 1
        assert pv.source == "ai"
        assert "provider=openai_compatible" in pv.source_detail
        assert "model=test-plan-model" in pv.source_detail
        assert "receipt=receipt-plan-test-1" in pv.source_detail
        assert pv.plan_summary.startswith("AI provider 生成的作战计划")
        assert pv.project_scope.out_of_scope
        assert "不自动创建任务" in pv.forbidden_actions

        retrieved = service.get_plan_version(pv.id)
        assert retrieved is not None
        assert retrieved.source == "ai"
        assert "receipt=receipt-plan-test-1" in retrieved.source_detail

    def test_create_plan_version_normalizes_provider_complexity_score(
        self, db_session, session_service
    ):
        session_obj = self._confirmed_session(session_service)
        plan_repo = ProjectDirectorPlanVersionRepository(db_session)
        session_repo = ProjectDirectorSessionRepository(db_session)

        def score_six_generator(
            model_name: str,
            prompt_text: str,
            request_id: str,
        ) -> tuple[str, str | None]:
            payload = json.loads(_provider_plan_payload())
            payload["complexity_assessment"]["score"] = 6
            return json.dumps(payload, ensure_ascii=False), "receipt-score-six"

        service = ProjectDirectorPlanService(
            plan_version_repository=plan_repo,
            session_repository=session_repo,
            provider_config_service=_FakeProviderConfigService(configured=True),
            provider_text_generator=score_six_generator,
        )

        pv = service.create_plan_version(session_id=session_obj.id)

        assert pv.source == "ai"
        assert pv.complexity_assessment.score == 5
        assert "provider=openai_compatible" in pv.source_detail
        assert "model=test-plan-model" in pv.source_detail
        assert "receipt=receipt-score-six" in pv.source_detail
        assert "normalized_by_backend:complexity_assessment" in pv.source_detail
        assert "deterministic_plan_generation" not in pv.source_detail

    def test_create_plan_version_leniently_fills_missing_non_core_provider_fields(
        self, db_session, session_service
    ):
        session_obj = self._confirmed_session(session_service)
        plan_repo = ProjectDirectorPlanVersionRepository(db_session)
        session_repo = ProjectDirectorSessionRepository(db_session)

        def incomplete_generator(
            model_name: str,
            prompt_text: str,
            request_id: str,
        ) -> tuple[str, str | None]:
            payload = json.loads(_provider_plan_payload())
            payload.pop("acceptance_criteria")
            payload.pop("risks")
            payload["project_scope"] = {"in_scope": ["保留 provider 给出的范围"]}
            payload.pop("agent_team_suggestions")
            payload.pop("skill_binding_suggestions")
            payload.pop("verification_mechanisms")
            payload.pop("repository_binding_suggestions")
            payload.pop("deliverable_boundaries")
            payload.pop("complexity_assessment")
            return json.dumps(payload, ensure_ascii=False), "receipt-incomplete"

        service = ProjectDirectorPlanService(
            plan_version_repository=plan_repo,
            session_repository=session_repo,
            provider_config_service=_FakeProviderConfigService(configured=True),
            provider_text_generator=incomplete_generator,
        )

        pv = service.create_plan_version(session_id=session_obj.id)
        api_payload = PlanVersionResponse.from_domain(pv)

        assert pv.source == "ai"
        assert "receipt=receipt-incomplete" in pv.source_detail
        assert "deterministic_plan_generation" not in pv.source_detail
        assert pv.plan_summary.startswith("AI provider 生成的作战计划")
        assert len(pv.phases) == 2
        assert len(pv.proposed_tasks) == 2
        assert pv.acceptance_criteria
        assert pv.risks
        assert pv.project_scope.in_scope == ["保留 provider 给出的范围"]
        assert pv.project_scope.out_of_scope
        assert pv.agent_team_suggestions
        assert pv.skill_binding_suggestions
        assert pv.verification_mechanisms
        assert pv.repository_binding_suggestions
        assert pv.deliverable_boundaries
        assert pv.complexity_assessment.score >= 1
        assert "normalized_by_backend:plan_draft_schema" in pv.source_detail
        assert "normalization_warnings=" in pv.source_detail
        assert "acceptance_criteria:filled_from_backend_template" in (
            api_payload.normalization_warnings
        )
        assert "project_scope:filled_safety_boundaries" in (
            api_payload.normalization_warnings
        )
        assert "complexity_assessment:normalized_by_backend" in (
            api_payload.normalization_warnings
        )

    def test_request_changes_normalizes_provider_complexity_score(
        self, db_session, session_service
    ):
        session_obj = self._confirmed_session(session_service)
        plan_repo = ProjectDirectorPlanVersionRepository(db_session)
        session_repo = ProjectDirectorSessionRepository(db_session)
        call_count = 0

        def generator(
            model_name: str,
            prompt_text: str,
            request_id: str,
        ) -> tuple[str, str | None]:
            nonlocal call_count
            call_count += 1
            payload = json.loads(_provider_plan_payload())
            if call_count == 2:
                payload["complexity_assessment"]["score"] = 6
            return json.dumps(payload, ensure_ascii=False), f"receipt-change-{call_count}"

        service = ProjectDirectorPlanService(
            plan_version_repository=plan_repo,
            session_repository=session_repo,
            provider_config_service=_FakeProviderConfigService(configured=True),
            provider_text_generator=generator,
        )

        original = service.create_plan_version(session_id=session_obj.id)
        rejected, replacement = service.request_changes(
            plan_version_id=original.id,
            feedback="请把验收标准拆得更清晰，并保持人工确认 Gate。",
        )

        assert call_count == 2
        assert rejected.status == PlanVersionStatus.REJECTED
        assert replacement.source == "ai"
        assert replacement.version_no == 2
        assert replacement.complexity_assessment.score == 5
        assert "receipt=receipt-change-2" in replacement.source_detail
        assert "normalized_by_backend:complexity_assessment" in replacement.source_detail
        assert "deterministic_plan_generation" not in replacement.source_detail

    def test_create_plan_version_fallback_marks_source_without_provider_call(
        self, db_session, session_service
    ):
        session_obj = self._confirmed_session(session_service)
        plan_repo = ProjectDirectorPlanVersionRepository(db_session)
        session_repo = ProjectDirectorSessionRepository(db_session)

        def forbidden_generator(
            model_name: str,
            prompt_text: str,
            request_id: str,
        ) -> tuple[str, str | None]:
            raise AssertionError("provider generator must not be called")

        service = ProjectDirectorPlanService(
            plan_version_repository=plan_repo,
            session_repository=session_repo,
            provider_config_service=_FakeProviderConfigService(configured=False),
            provider_text_generator=forbidden_generator,
        )

        pv = service.create_plan_version(session_id=session_obj.id)

        assert pv.source == "rule_fallback"
        assert "deterministic_plan_generation" in pv.source_detail
        assert "provider_not_configured" in pv.source_detail
        assert "作战计划摘要" in pv.plan_summary
        assert "不自动调用 Worker" in pv.forbidden_actions

    def test_create_plan_version_rejects_unsafe_provider_plan_without_fallback(
        self, db_session, session_service
    ):
        session_obj = self._confirmed_session(session_service)
        plan_repo = ProjectDirectorPlanVersionRepository(db_session)
        session_repo = ProjectDirectorSessionRepository(db_session)

        def unsafe_generator(
            model_name: str,
            prompt_text: str,
            request_id: str,
        ) -> tuple[str, str | None]:
            payload = json.loads(_provider_plan_payload())
            payload["plan_summary"] = "AI 将自动创建任务并启动 Worker，随后 git push。"
            payload["project_scope"]["out_of_scope"] = ["仅口头确认"]
            payload["project_scope"]["assumptions"] = ["系统会自动执行"]
            payload["complexity_assessment"]["score"] = 6
            return json.dumps(payload, ensure_ascii=False), "receipt-unsafe-plan"

        service = ProjectDirectorPlanService(
            plan_version_repository=plan_repo,
            session_repository=session_repo,
            provider_config_service=_FakeProviderConfigService(configured=True),
            provider_text_generator=unsafe_generator,
        )

        with pytest.raises(ProjectDirectorPlanGenerationError) as exc_info:
            service.create_plan_version(session_id=session_obj.id)

        assert "provider_guardrail_blocked" in str(exc_info.value)
        assert "未通过安全边界校验" in str(exc_info.value)
        assert service.list_plan_versions(session_obj.id) == []

    def test_create_plan_version_rejects_invalid_provider_json_without_fallback(
        self, db_session, session_service
    ):
        session_obj = self._confirmed_session(session_service)
        plan_repo = ProjectDirectorPlanVersionRepository(db_session)
        session_repo = ProjectDirectorSessionRepository(db_session)

        def invalid_json_generator(
            model_name: str,
            prompt_text: str,
            request_id: str,
        ) -> tuple[str, str | None]:
            return "AI 说：我会稍后补 JSON", "receipt-invalid-json"

        service = ProjectDirectorPlanService(
            plan_version_repository=plan_repo,
            session_repository=session_repo,
            provider_config_service=_FakeProviderConfigService(configured=True),
            provider_text_generator=invalid_json_generator,
        )

        with pytest.raises(ProjectDirectorPlanGenerationError) as exc_info:
            service.create_plan_version(session_id=session_obj.id)

        assert "provider_generation_failed" in str(exc_info.value)
        assert "未创建系统规则模板草案" in str(exc_info.value)
        assert service.list_plan_versions(session_obj.id) == []

    def test_request_changes_keeps_original_pending_when_provider_output_invalid(
        self, db_session, session_service
    ):
        session_obj = self._confirmed_session(session_service)
        plan_repo = ProjectDirectorPlanVersionRepository(db_session)
        session_repo = ProjectDirectorSessionRepository(db_session)
        call_count = 0

        def generator(
            model_name: str,
            prompt_text: str,
            request_id: str,
        ) -> tuple[str, str | None]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _provider_plan_payload(), "receipt-original"
            return "not-json", "receipt-rework-invalid"

        service = ProjectDirectorPlanService(
            plan_version_repository=plan_repo,
            session_repository=session_repo,
            provider_config_service=_FakeProviderConfigService(configured=True),
            provider_text_generator=generator,
        )

        original = service.create_plan_version(session_id=session_obj.id)

        with pytest.raises(ProjectDirectorPlanGenerationError):
            service.request_changes(
                plan_version_id=original.id,
                feedback="请补充更清晰的验收标准。",
            )

        versions = service.list_plan_versions(session_obj.id)
        assert len(versions) == 1
        assert versions[0].id == original.id
        assert versions[0].status == PlanVersionStatus.PENDING_CONFIRMATION
        assert versions[0].source == "ai"

    def test_version_no_increments(self, session_service, plan_service):
        from app.domain.project_director_session import ClarifyingAnswer

        session_obj = session_service.create_session(
            goal_text="构建一个用户认证系统，范围明确",
            constraints="FastAPI",
        )
        answers = [
            {"question_id": q.id, "answer": f"答 {i}"}
            for i, q in enumerate(session_obj.clarifying_questions)
        ]
        session_obj = session_service.submit_answers(
            session_obj.id,
            [ClarifyingAnswer(**a) for a in answers],
        )
        session_service.confirm_goal(session_obj.id)

        pv1 = plan_service.create_plan_version(session_id=session_obj.id)
        pv2 = plan_service.create_plan_version(session_id=session_obj.id)
        pv3 = plan_service.create_plan_version(session_id=session_obj.id)

        assert pv1.version_no == 1
        assert pv2.version_no == 2
        assert pv3.version_no == 3

    def test_cannot_create_from_unconfirmed(self, session_service, plan_service):
        from app.domain.project_director_session import ClarifyingAnswer

        session_obj = session_service.create_session(
            goal_text="构建一个用户认证系统",
        )
        answers = [
            {"question_id": q.id, "answer": f"答 {i}"}
            for i, q in enumerate(session_obj.clarifying_questions)
        ]
        session_obj = session_service.submit_answers(
            session_obj.id,
            [ClarifyingAnswer(**a) for a in answers],
        )
        # Session is ready_to_confirm but NOT confirmed
        assert session_obj.status == ProjectDirectorSessionStatus.READY_TO_CONFIRM

        with pytest.raises(ValueError, match="Only confirmed sessions"):
            plan_service.create_plan_version(session_id=session_obj.id)

    def test_get_nonexistent_returns_none(self, plan_service):
        assert plan_service.get_plan_version(uuid4()) is None
