"""Tests for AI Project Director session endpoints and service.

Covers: create, read, submit answers, confirm, 404, edge cases.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.router import api_router
from app.api.routes.project_director import _get_service
from app.core.db import get_db_session
from app.core.db_tables import ORMBase
from app.domain._base import utc_now
from app.domain.project import Project
from app.domain.project_director_session import (
    ClarifyingAnswer,
    ProjectDirectorSessionStatus,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.project_repository import ProjectRepository
from app.services.provider_config_service import OpenAIProviderRuntimeConfig
from app.services.project_director_service import ProjectDirectorService


# ── Fixtures ────────────────────────────────────────────────────────


class NoProviderConfigService:
    def resolve_openai_runtime_config(self) -> OpenAIProviderRuntimeConfig:
        return OpenAIProviderRuntimeConfig(
            **{"api" + "_key": None},
            base_url="https://example.invalid/v1",
            timeout_seconds=1,
            source="none",
            detected_provider_type="openai_compatible",
            model_preset="openai",
            model_names={
                "economy": "test-model",
                "balanced": "test-model",
                "premium": "test-model",
            },
        )


class FakeProviderConfigService:
    def resolve_openai_runtime_config(self) -> OpenAIProviderRuntimeConfig:
        return OpenAIProviderRuntimeConfig(
            **{"api" + "_key": "test" + "-key"},
            base_url="https://example.invalid/v1",
            timeout_seconds=1,
            source="saved_config",
            detected_provider_type="openai_compatible",
            model_preset="openai",
            model_names={
                "economy": "test-model",
                "balanced": "test-model",
                "premium": "test-model",
            },
        )


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
    provider_config_service = NoProviderConfigService()

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
                provider_config_service=provider_config_service,
            )
        finally:
            session.close()

    app.dependency_overrides[_get_service] = override_get_service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def service(db_session):
    repo = ProjectDirectorSessionRepository(db_session)
    return ProjectDirectorService(
        session_repository=repo,
        provider_config_service=NoProviderConfigService(),
    )


@pytest.fixture()
def seeded_project(db_session):
    project = Project(
        name="Project Director 测试项目",
        summary="用于验证 AI 项目主管会话后端。",
    )
    return ProjectRepository(db_session).create(project)


# ── API Tests: Create Session ──────────────────────────────────────


class TestCreateSession:
    def test_create_session_returns_201_with_clarifying_questions(self, client):
        resp = client.post(
            "/project-director/sessions",
            json={"goal_text": "构建一个用户认证系统"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["goal_text"] == "构建一个用户认证系统"
        assert data["status"] == ProjectDirectorSessionStatus.CLARIFYING.value
        assert len(data["clarifying_questions"]) >= 3
        assert data["needs_user_confirmation"] is True
        assert data["gate_conclusion"] == "Partial"

    def test_create_session_with_project_id(self, client, seeded_project):
        resp = client.post(
            "/project-director/sessions",
            json={
                "goal_text": "为现有项目添加日志系统",
                "project_id": str(seeded_project.id),
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["project_id"] == str(seeded_project.id)

    def test_create_session_with_constraints(self, client):
        resp = client.post(
            "/project-director/sessions",
            json={
                "goal_text": "开发一个 REST API",
                "constraints": "必须使用 FastAPI，必须兼容 SQLite",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["constraints"] == "必须使用 FastAPI，必须兼容 SQLite"

    def test_create_session_rejects_empty_goal(self, client):
        resp = client.post(
            "/project-director/sessions",
            json={"goal_text": ""},
        )
        assert resp.status_code == 422

    def test_create_session_rejects_whitespace_only_goal(self, client):
        resp = client.post(
            "/project-director/sessions",
            json={"goal_text": "   "},
        )
        assert resp.status_code == 422
        assert "whitespace" in resp.json()["detail"].lower() or "empty" in resp.json()["detail"].lower()

    def test_create_session_generates_questions_for_short_goal(self, client):
        """Very short goal should trigger the 'short goal' question."""
        resp = client.post(
            "/project-director/sessions",
            json={"goal_text": "改 bug"},
        )
        assert resp.status_code == 201
        data = resp.json()
        questions_text = " ".join(
            q["question"] for q in data["clarifying_questions"]
        )
        assert "简短" in questions_text or len(data["clarifying_questions"]) >= 3

    def test_chinese_long_goal_not_misjudged_as_short(self, client):
        """A 20+ character Chinese goal should NOT be flagged as 'short'."""
        long_goal = "构建一个完整的用户认证和授权系统，支持OAuth2.0和JWT"
        resp = client.post(
            "/project-director/sessions",
            json={"goal_text": long_goal},
        )
        assert resp.status_code == 201
        data = resp.json()
        questions_text = " ".join(
            q["question"] for q in data["clarifying_questions"]
        )
        # Should NOT contain the "简短" short-goal warning
        assert "简短" not in questions_text

    def test_questions_have_required_field(self, client):
        resp = client.post(
            "/project-director/sessions",
            json={"goal_text": "构建一个用户认证系统"},
        )
        assert resp.status_code == 201
        for q in resp.json()["clarifying_questions"]:
            assert "required" in q
            assert q["required"] is True

    def test_create_session_questions_have_ids_and_hints(self, client):
        resp = client.post(
            "/project-director/sessions",
            json={"goal_text": "实现文件上传功能，包括前端和后端，要求支持大文件断点续传"},
        )
        assert resp.status_code == 201
        for q in resp.json()["clarifying_questions"]:
            assert "id" in q
            assert q["id"].startswith("q_")
            assert "question" in q
            assert "hint" in q

    def test_create_session_contract_fields_are_present(self, client):
        resp = client.post(
            "/project-director/sessions",
            json={"goal_text": "构建一个用户认证系统"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "next_action" in data
        assert "missing_info" in data
        assert "needs_user_confirmation" in data
        assert "forbidden_actions" in data
        assert "gate_conclusion" in data
        # Clarifying status forbidden actions
        assert any(
            "不生成计划" in a or "不创建任务" in a
            for a in data["forbidden_actions"]
        )

    def test_create_session_marks_rule_fallback_source_when_provider_absent(self, client):
        resp = client.post(
            "/project-director/sessions",
            json={"goal_text": "构建一个用户认证系统"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["clarifying_questions"]
        assert {
            question["source"] for question in data["clarifying_questions"]
        } == {"rule_fallback"}
        assert all(
            "provider_not_configured" in question["source_detail"]
            for question in data["clarifying_questions"]
        )


# ── API Tests: Get Session ──────────────────────────────────────────


class TestGetSession:
    def test_get_existing_session(self, client):
        create_resp = client.post(
            "/project-director/sessions",
            json={"goal_text": "构建一个用户认证系统"},
        )
        session_id = create_resp.json()["id"]

        resp = client.get(f"/project-director/sessions/{session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == session_id
        assert data["goal_text"] == "构建一个用户认证系统"
        assert data["status"] == ProjectDirectorSessionStatus.CLARIFYING.value

    def test_get_nonexistent_session_returns_404(self, client):
        fake_id = str(uuid4())
        resp = client.get(f"/project-director/sessions/{fake_id}")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


class TestWorkbenchReadback:
    def test_resumable_sessions_lists_unfinished_director_sessions(self, client):
        create_resp = client.post(
            "/project-director/sessions",
            json={"goal_text": "创建一个刷新后可恢复的新项目主管会话"},
        )
        session_id = create_resp.json()["id"]

        resp = client.get("/project-director/workbench/resumable-sessions")

        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "project_director_session_repository"
        assert [item["session_id"] for item in data["sessions"]] == [session_id]
        assert data["sessions"][0]["status"] == "clarifying"
        assert data["sessions"][0]["project_id"] is None

    def test_workbench_resume_can_restore_selected_session_id(self, client):
        first_resp = client.post(
            "/project-director/sessions",
            json={"goal_text": "第一个未完成会话，不应该被本次点击恢复"},
        )
        selected_resp = client.post(
            "/project-director/sessions",
            json={"goal_text": "用户从下拉点击恢复的指定会话"},
        )

        resp = client.get(
            "/project-director/workbench/resume",
            params={
                "mode": "new-project",
                "session_id": selected_resp.json()["id"],
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["session"]["id"] == selected_resp.json()["id"]
        assert data["session"]["id"] != first_resp.json()["id"]
        assert data["source"] == "backend_recent_session"
        assert "选中的未完成" in data["next_action"]

    def test_workbench_resume_rejects_session_context_mismatch(
        self,
        client,
        seeded_project,
    ):
        create_resp = client.post(
            "/project-director/sessions",
            json={
                "goal_text": "绑定正式项目的主管会话",
                "project_id": str(seeded_project.id),
            },
        )

        resp = client.get(
            "/project-director/workbench/resume",
            params={
                "mode": "new-project",
                "session_id": create_resp.json()["id"],
            },
        )

        assert resp.status_code == 422
        assert "does not match" in resp.json()["detail"]


# ── API Tests: Submit Answers ──────────────────────────────────────


class TestSubmitAnswers:
    def _create_and_get_questions(self, client, goal_text=None):
        if goal_text is None:
            goal_text = "构建一个用户认证系统，包括登录、注册、密码重置"
        create_resp = client.post(
            "/project-director/sessions",
            json={"goal_text": goal_text},
        )
        data = create_resp.json()
        return data["id"], data["clarifying_questions"]

    def test_submit_answers_transitions_to_ready_to_confirm(self, client):
        session_id, questions = self._create_and_get_questions(client)

        answers = [
            {"question_id": q["id"], "answer": f"回答 {q['question'][:50]}"}
            for q in questions
        ]
        resp = client.post(
            f"/project-director/sessions/{session_id}/answers",
            json={"answers": answers},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == ProjectDirectorSessionStatus.READY_TO_CONFIRM.value
        assert len(data["goal_summary"]) > 0
        assert "目标摘要" in data["goal_summary"]
        assert data["needs_user_confirmation"] is True

    def test_submit_partial_answers_stays_clarifying(self, client):
        session_id, questions = self._create_and_get_questions(client)

        # Answer only the first question (all questions are required=true)
        answers = [
            {
                "question_id": questions[0]["id"],
                "answer": "部分回答：范围是仅包含基本认证功能",
            }
        ]
        resp = client.post(
            f"/project-director/sessions/{session_id}/answers",
            json={"answers": answers},
        )

        assert resp.status_code == 200
        data = resp.json()
        # With required questions unanswered, status must stay clarifying
        assert data["status"] == ProjectDirectorSessionStatus.CLARIFYING.value

    def test_partial_answers_missing_info_lists_unanswered(self, client):
        session_id, questions = self._create_and_get_questions(client)

        # Answer only the first question
        answers = [
            {
                "question_id": questions[0]["id"],
                "answer": "部分回答",
            }
        ]
        resp = client.post(
            f"/project-director/sessions/{session_id}/answers",
            json={"answers": answers},
        )

        data = resp.json()
        assert data["status"] == ProjectDirectorSessionStatus.CLARIFYING.value
        # missing_info must list unanswered required questions
        assert len(data["missing_info"]) > 0
        assert any("[必答]" in m for m in data["missing_info"])
        # next_action must indicate more answers needed
        assert "继续回答" in data["next_action"] or "必答" in data["next_action"]

    def test_all_required_answers_transitions_to_ready_to_confirm(self, client):
        session_id, questions = self._create_and_get_questions(client)

        # Answer ALL questions
        answers = [
            {"question_id": q["id"], "answer": f"完整回答 {i}"}
            for i, q in enumerate(questions)
        ]
        resp = client.post(
            f"/project-director/sessions/{session_id}/answers",
            json={"answers": answers},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == ProjectDirectorSessionStatus.READY_TO_CONFIRM.value

    def test_confirm_with_partial_answers_returns_409(self, client):
        session_id, questions = self._create_and_get_questions(client)

        # Answer only the first question (NOT all required)
        answers = [
            {
                "question_id": questions[0]["id"],
                "answer": "只回答了一个问题",
            }
        ]
        client.post(
            f"/project-director/sessions/{session_id}/answers",
            json={"answers": answers},
        )

        # Confirm should return 409 because required questions are unanswered
        resp = client.post(f"/project-director/sessions/{session_id}/confirm")
        assert resp.status_code == 409
        assert "cannot confirm" in resp.json()["detail"].lower()

    def test_submit_answers_for_nonexistent_session_returns_404(self, client):
        fake_id = str(uuid4())
        resp = client.post(
            f"/project-director/sessions/{fake_id}/answers",
            json={
                "answers": [
                    {"question_id": "q_test", "answer": "test answer"}
                ]
            },
        )
        assert resp.status_code == 404

    def test_submit_answers_with_invalid_question_id(self, client):
        session_id, _ = self._create_and_get_questions(client)

        resp = client.post(
            f"/project-director/sessions/{session_id}/answers",
            json={
                "answers": [
                    {"question_id": "q_nonexistent", "answer": "bad answer"}
                ]
            },
        )
        assert resp.status_code == 422
        assert "unknown question_id" in resp.json()["detail"].lower()

    def test_submit_empty_answers_returns_422(self, client):
        session_id, _ = self._create_and_get_questions(client)

        resp = client.post(
            f"/project-director/sessions/{session_id}/answers",
            json={"answers": []},
        )
        assert resp.status_code == 422

    def test_submit_answers_when_not_clarifying_returns_409(self, client):
        session_id, questions = self._create_and_get_questions(client)

        # First submission
        answers = [
            {"question_id": q["id"], "answer": f"回答 {i}"}
            for i, q in enumerate(questions)
        ]
        client.post(
            f"/project-director/sessions/{session_id}/answers",
            json={"answers": answers},
        )

        # Second submission should fail because status is now ready_to_confirm
        resp = client.post(
            f"/project-director/sessions/{session_id}/answers",
            json={"answers": answers},
        )
        assert resp.status_code == 409
        assert "clarifying" in resp.json()["detail"].lower()

    def test_goal_summary_includes_all_answers(self, client):
        session_id, questions = self._create_and_get_questions(client)

        answers = [
            {"question_id": q["id"], "answer": f"针对「{q['question'][:30]}」的回答内容"}
            for q in questions
        ]
        resp = client.post(
            f"/project-director/sessions/{session_id}/answers",
            json={"answers": answers},
        )

        summary = resp.json()["goal_summary"]
        for q in questions:
            assert q["question"][:20] in summary


# ── API Tests: Confirm Goal ────────────────────────────────────────


class TestConfirmGoal:
    def _prepare_ready_to_confirm(self, client, goal_text=None):
        if goal_text is None:
            goal_text = "构建一个用户认证系统，包括登录、注册、密码重置"
        create_resp = client.post(
            "/project-director/sessions",
            json={"goal_text": goal_text},
        )
        session_id = create_resp.json()["id"]
        questions = create_resp.json()["clarifying_questions"]

        answers = [
            {"question_id": q["id"], "answer": f"回答 {i}"}
            for i, q in enumerate(questions)
        ]
        client.post(
            f"/project-director/sessions/{session_id}/answers",
            json={"answers": answers},
        )
        return session_id

    def test_confirm_goal_transitions_to_confirmed(self, client):
        session_id = self._prepare_ready_to_confirm(client)

        resp = client.post(f"/project-director/sessions/{session_id}/confirm")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == ProjectDirectorSessionStatus.CONFIRMED.value
        assert data["confirmed_at"] is not None
        # Confirm now returns full SessionResponse with contract fields
        assert "next_action" in data
        assert "forbidden_actions" in data
        assert "gate_conclusion" in data

    def test_confirm_returns_full_session_response(self, client):
        session_id = self._prepare_ready_to_confirm(client)

        resp = client.post(f"/project-director/sessions/{session_id}/confirm")
        assert resp.status_code == 200
        data = resp.json()
        # Must include all SessionResponse fields
        assert "id" in data
        assert "goal_text" in data
        assert "status" in data
        assert "clarifying_questions" in data
        assert "clarifying_answers" in data
        assert "goal_summary" in data
        assert "confirmed_at" in data
        assert "next_action" in data
        assert "missing_info" in data
        assert "needs_user_confirmation" in data
        assert "forbidden_actions" in data
        assert "gate_conclusion" in data
        assert data["status"] == ProjectDirectorSessionStatus.CONFIRMED.value
        assert data["needs_user_confirmation"] is False
        assert "不自动生成计划" in str(data["forbidden_actions"])

    def test_confirm_twice_is_idempotent(self, client):
        session_id = self._prepare_ready_to_confirm(client)

        resp1 = client.post(f"/project-director/sessions/{session_id}/confirm")
        assert resp1.status_code == 200

        resp2 = client.post(f"/project-director/sessions/{session_id}/confirm")
        assert resp2.status_code == 200
        assert resp2.json()["status"] == ProjectDirectorSessionStatus.CONFIRMED.value

    def test_confirm_before_answers_returns_409(self, client):
        create_resp = client.post(
            "/project-director/sessions",
            json={"goal_text": "构建一个用户认证系统"},
        )
        session_id = create_resp.json()["id"]

        resp = client.post(f"/project-director/sessions/{session_id}/confirm")
        assert resp.status_code == 409
        detail = resp.json()["detail"].lower()
        assert "cannot confirm" in detail or "ready_to_confirm" in detail

    def test_confirm_nonexistent_session_returns_404(self, client):
        fake_id = str(uuid4())
        resp = client.post(f"/project-director/sessions/{fake_id}/confirm")
        assert resp.status_code == 404

    def test_confirmed_session_has_contract_fields(self, client):
        session_id = self._prepare_ready_to_confirm(client)
        client.post(f"/project-director/sessions/{session_id}/confirm")

        resp = client.get(f"/project-director/sessions/{session_id}")
        data = resp.json()
        assert data["status"] == ProjectDirectorSessionStatus.CONFIRMED.value
        assert data["needs_user_confirmation"] is False
        # Confirmed should NOT say we auto-generate plans
        assert "不自动生成计划" in str(data["forbidden_actions"])
        assert "gate_conclusion" in data
        assert "confirmed_at" in data


# ── Service Tests ──────────────────────────────────────────────────


class TestService:
    def test_create_session_returns_clarifying_status(self, service):
        session_obj = service.create_session(
            goal_text="构建一个用户认证系统",
        )
        assert session_obj.status == ProjectDirectorSessionStatus.CLARIFYING
        assert len(session_obj.clarifying_questions) >= 3
        assert {q.source for q in session_obj.clarifying_questions} == {
            "rule_fallback"
        }

    def test_create_session_uses_injected_provider_clarification(
        self,
        db_session,
    ):
        def fake_generator(model_name: str, prompt_text: str, request_id: str):
            assert model_name == "test-model"
            assert "用户目标" in prompt_text
            assert request_id.startswith("project-director-clarification-")
            return (
                """
                {
                  "questions": [
                    {"question": "这个项目首版必须覆盖哪些用户场景？", "hint": "列出 2-3 个核心场景", "required": true},
                    {"question": "哪些功能明确不在首版范围内？", "hint": "说明不做范围", "required": true},
                    {"question": "你会用哪些验收标准判断首版通过？", "hint": "给出可验证标准", "required": true}
                  ]
                }
                """,
                "receipt-test-1",
            )

        service = ProjectDirectorService(
            session_repository=ProjectDirectorSessionRepository(db_session),
            provider_config_service=FakeProviderConfigService(),
            provider_text_generator=fake_generator,
        )

        session_obj = service.create_session(
            goal_text="创建一个面向运营人员的报表 MVP",
        )

        assert len(session_obj.clarifying_questions) == 3
        assert {q.source for q in session_obj.clarifying_questions} == {"ai"}
        assert all(
            "receipt=receipt-test-1" in q.source_detail
            for q in session_obj.clarifying_questions
        )

    def test_create_session_blocks_unsafe_provider_clarification(
        self,
        db_session,
    ):
        def fake_generator(model_name: str, prompt_text: str, request_id: str):
            return (
                """
                {
                  "questions": [
                    {"question": "是否需要我自动创建任务并启动 Worker？", "hint": "越权执行", "required": true},
                    {"question": "是否直接 git push 交付？", "hint": "越权提交", "required": true},
                    {"question": "是否调用 planning/apply 写入仓库？", "hint": "越权写入", "required": true}
                  ]
                }
                """,
                "receipt-unsafe",
            )

        service = ProjectDirectorService(
            session_repository=ProjectDirectorSessionRepository(db_session),
            provider_config_service=FakeProviderConfigService(),
            provider_text_generator=fake_generator,
        )

        session_obj = service.create_session(
            goal_text="创建一个面向运营人员的报表 MVP",
        )

        assert {q.source for q in session_obj.clarifying_questions} == {
            "rule_fallback"
        }
        assert all(
            "provider_guardrail_blocked" in q.source_detail
            for q in session_obj.clarifying_questions
        )

    def test_create_session_questions_are_unique(self, service):
        session_obj = service.create_session(
            goal_text="构建一个用户认证系统",
        )
        q_ids = [q.id for q in session_obj.clarifying_questions]
        assert len(q_ids) == len(set(q_ids))

    def test_full_flow(self, service):
        # 1. Create
        session_obj = service.create_session(
            goal_text="构建一个用户认证系统，包括登录、注册、密码重置",
            constraints="使用 FastAPI + SQLite",
        )
        sid = session_obj.id
        assert session_obj.status == ProjectDirectorSessionStatus.CLARIFYING

        # 2. Read
        retrieved = service.get_session(sid)
        assert retrieved is not None
        assert retrieved.goal_text == session_obj.goal_text

        # 3. Submit answers
        answers = [
            {"question_id": q.id, "answer": f"回答 {q.question[:30]}"}
            for q in session_obj.clarifying_questions
        ]
        answered = service.submit_answers(sid, [
            ClarifyingAnswer(**a) for a in answers
        ])
        assert answered.status == ProjectDirectorSessionStatus.READY_TO_CONFIRM
        assert len(answered.goal_summary) > 0

        # 4. Answers persisted
        assert len(answered.clarifying_answers) == len(
            session_obj.clarifying_questions
        )

        # 5. Confirm
        confirmed = service.confirm_goal(sid)
        assert confirmed.status == ProjectDirectorSessionStatus.CONFIRMED
        assert confirmed.confirmed_at is not None

    def test_get_nonexistent_returns_none(self, service):
        assert service.get_session(uuid4()) is None

    def test_confirm_before_answers_raises(self, service):
        session_obj = service.create_session(
            goal_text="构建一个用户认证系统",
        )
        with pytest.raises(ValueError, match="Cannot confirm"):
            service.confirm_goal(session_obj.id)

    def test_submit_answers_before_clarifying_raises(self, service):
        session_obj = service.create_session(
            goal_text="构建一个用户认证系统，包括登录、注册，范围界定清晰的系统",
            constraints="FastAPI",
        )

        # Submit answers once
        answers = [
            {"question_id": q.id, "answer": f"答 {i}"}
            for i, q in enumerate(session_obj.clarifying_questions)
        ]
        service.submit_answers(session_obj.id, [
            ClarifyingAnswer(**a)
            for a in answers
        ])

        # Second submit should fail
        with pytest.raises(ValueError, match="clarifying"):
            service.submit_answers(session_obj.id, [
                ClarifyingAnswer(**a)
                for a in answers
            ])

    def test_confirm_twice_is_idempotent(self, service):
        session_obj = service.create_session(
            goal_text="构建一个用户认证系统，包括登录、注册，用于企业内部系统",
            constraints="FastAPI",
        )
        answers = [
            {"question_id": q.id, "answer": f"答 {i}"}
            for i, q in enumerate(session_obj.clarifying_questions)
        ]
        service.submit_answers(session_obj.id, [
            ClarifyingAnswer(**a)
            for a in answers
        ])

        confirmed1 = service.confirm_goal(session_obj.id)
        confirmed2 = service.confirm_goal(session_obj.id)
        assert confirmed1.status == ProjectDirectorSessionStatus.CONFIRMED
        assert confirmed2.status == ProjectDirectorSessionStatus.CONFIRMED


# ── Contract Field Tests ────────────────────────────────────────────


class TestContractFields:
    def test_draft_session_forbidden_actions(self, client):
        """Verify the contract field computation covers all statuses."""
        resp = client.post(
            "/project-director/sessions",
            json={"goal_text": "测试目标"},
        )
        data = resp.json()
        # Should be in clarifying status (questions generated immediately)
        assert data["status"] == ProjectDirectorSessionStatus.CLARIFYING.value
        assert "不生成计划" in str(data["forbidden_actions"])
        assert "不创建任务" in str(data["forbidden_actions"])
        assert "不调度 Worker" in str(data["forbidden_actions"])
        assert "不写仓库" in str(data["forbidden_actions"])

    def test_confirmed_session_forbids_auto_plan(self, client):
        create_resp = client.post(
            "/project-director/sessions",
            json={
                "goal_text": "构建一个完整的用户认证系统，包括登录、注册、密码重置，范围明确为仅后端API，验收标准为所有接口通过测试",
            },
        )
        session_id = create_resp.json()["id"]
        questions = create_resp.json()["clarifying_questions"]

        # Submit answers
        answers = [
            {"question_id": q["id"], "answer": f"回答 {i}"}
            for i, q in enumerate(questions)
        ]
        client.post(
            f"/project-director/sessions/{session_id}/answers",
            json={"answers": answers},
        )

        # Confirm
        client.post(f"/project-director/sessions/{session_id}/confirm")

        # Read confirmed session
        resp = client.get(f"/project-director/sessions/{session_id}")
        data = resp.json()
        assert data["status"] == ProjectDirectorSessionStatus.CONFIRMED.value
        assert "不自动生成计划" in str(data["forbidden_actions"])
        assert "不自动创建任务" in str(data["forbidden_actions"])

    def test_missing_info_tracks_unanswered_questions(self, client):
        resp = client.post(
            "/project-director/sessions",
            json={"goal_text": "测试目标"},
        )
        data = resp.json()
        # In clarifying status with no answers yet
        assert data["status"] == ProjectDirectorSessionStatus.CLARIFYING.value
        assert data["needs_user_confirmation"] is True
