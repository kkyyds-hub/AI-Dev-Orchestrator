"""Tests for Stage 7-B2 Project Director message context + chat response."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.api.router import api_router
from app.api.routes import project_director as project_director_route
from app.core.db import get_db_session
from app.core.db_tables import (
    ORMBase,
    ProjectDirectorMessageTable,
    ProjectDirectorSessionTable,
    RunTable,
    TaskTable,
)
from app.domain.project import Project
from app.domain.project_director_message import ProjectDirectorMessageRole
from app.domain.project_director_plan_version import (
    ComplexityAssessment,
    PlanPhase,
    PlanVersionStatus,
    ProjectDirectorPlanVersion,
    ProjectScopeSummary,
    ProposedTask,
)
from app.domain.project_director_task_creation import (
    ProjectDirectorTaskCreationRecord,
)
from app.domain.task import Task
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.project_director_task_creation_repository import (
    ProjectDirectorTaskCreationRecordRepository,
)
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.services.project_director_context_builder_service import (
    ProjectDirectorContextBuilderService,
)
from app.services.project_director_context_assembler_service import (
    DirectorContextAssemblerService,
)
from app.services.project_director_message_service import ProjectDirectorMessageService
from app.services.project_director_service import ProjectDirectorService
from app.services.provider_config_service import OpenAIProviderRuntimeConfig


TECHNICAL_USER_VISIBLE_TERMS = (
    "provider",
    "worker",
    "executor",
    "runtime",
    "API",
    "payload",
    "Git",
    "dispatch_question",
    "session_id",
    "project_id",
    "synthetic",
    "read model",
    "intent",
    "source_detail",
    "risk_level",
    "suggested_actions",
    "Codex",
    "Claude",
    "DeepSeek",
    "Skill",
    "challenge_type",
    "challenge_severity",
    "challenge_status",
    "proposal_type",
    "proposal_status",
    "approval_requirement",
    "plan_revision",
    "conversion_target",
    "conversion_status",
    "conversion_risk",
    "task_draft",
    "plan_draft",
)


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


class ConfiguredProviderConfigService:
    def resolve_openai_runtime_config(self) -> OpenAIProviderRuntimeConfig:
        return OpenAIProviderRuntimeConfig(
            **{"api" + "_key": "test-key"},
            base_url="https://example.invalid/v1",
            timeout_seconds=1,
            source="saved_config",
            detected_provider_type="openai_compatible",
            model_preset="openai",
            model_names={
                "economy": "test-model",
                "balanced": "test-chat-model",
                "premium": "test-model",
            },
        )


class ExplodingProviderConfigService:
    def resolve_openai_runtime_config(self) -> OpenAIProviderRuntimeConfig:
        raise AssertionError("provider config unavailable")


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

    def override_get_project_director_service():
        session = sqlite_session_factory()
        try:
            yield ProjectDirectorService(
                session_repository=ProjectDirectorSessionRepository(session),
                provider_config_service=NoProviderConfigService(),
            )
        finally:
            session.close()

    def override_get_message_service():
        session = sqlite_session_factory()
        try:
            session_repo = ProjectDirectorSessionRepository(session)
            message_repo = ProjectDirectorMessageRepository(session)
            yield ProjectDirectorMessageService(
                session_repository=session_repo,
                message_repository=message_repo,
                context_builder=ProjectDirectorContextBuilderService(
                    session_repository=session_repo,
                    message_repository=message_repo,
                    project_repository=ProjectRepository(session),
                    task_repository=TaskRepository(session),
                ),
                provider_config_service=NoProviderConfigService(),
            )
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[project_director_route._get_service] = (
        override_get_project_director_service
    )
    app.dependency_overrides[project_director_route._get_message_service] = (
        override_get_message_service
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _create_session(client: TestClient) -> str:
    resp = client.post(
        "/project-director/sessions",
        json={"goal_text": "为工作台增加 Project Director 对话历史"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _count_rows(db_session, table) -> int:
    return db_session.execute(select(func.count()).select_from(table)).scalar_one()


def _message_rows_for_session(db_session, session_id: str):
    session_uuid = UUID(session_id) if isinstance(session_id, str) else session_id
    return (
        db_session.execute(
            select(ProjectDirectorMessageTable)
            .where(ProjectDirectorMessageTable.session_id == session_uuid)
            .order_by(ProjectDirectorMessageTable.sequence_no.asc())
        )
        .scalars()
        .all()
    )


def _assert_no_user_visible_technical_terms(*values: object) -> None:
    text = " ".join(str(value) for value in values)
    for term in TECHNICAL_USER_VISIBLE_TERMS:
        assert term not in text


def _create_plan_version(
    db_session,
    *,
    session_id,
    project_id=None,
    version_no: int = 1,
    status: PlanVersionStatus = PlanVersionStatus.PENDING_CONFIRMATION,
    plan_summary: str = "## 作战计划摘要\n当前草案覆盖设计、实现与验证。",
    risks: list[str] | None = None,
) -> ProjectDirectorPlanVersion:
    return ProjectDirectorPlanVersionRepository(db_session).create(
        ProjectDirectorPlanVersion(
            session_id=session_id,
            project_id=project_id,
            version_no=version_no,
            status=status,
            plan_summary=plan_summary,
            phases=[
                PlanPhase(
                    sequence=1,
                    name="分析与设计",
                    goal="确认范围、设计接口与验收口径",
                    task_count_hint=2,
                ),
                PlanPhase(
                    sequence=2,
                    name="实现与验证",
                    goal="完成实现并补齐测试",
                    task_count_hint=3,
                ),
            ],
            proposed_tasks=[
                ProposedTask(
                    title="梳理上下文字段",
                    description="补齐对话上下文读取字段",
                ),
                ProposedTask(
                    title="验证 fallback 回复",
                    description="确保 Provider 不可用时仍能总结草案",
                ),
            ],
            acceptance_criteria=["上下文字段可 readback", "fallback 不冒充 AI"],
            risks=risks or ["范围蔓延风险", "Provider 输出不符合合同"],
            project_scope=ProjectScopeSummary(
                in_scope=["会话上下文", "草案摘要", "任务创建记录"],
                out_of_scope=["自动执行 Worker", "写仓库"],
                assumptions=["用户会单独确认高风险动作"],
            ),
            complexity_assessment=ComplexityAssessment(
                level="medium",
                label="中等复杂度",
                score=3,
                drivers=["涉及 Provider 输出合同", "涉及上下文 readback"],
                mitigation_suggestions=["使用规则 fallback"],
            ),
            source="rule_fallback",
            source_detail="test_plan",
        )
    )


def test_post_message_persists_user_and_rule_fallback_assistant(client):
    session_id = _create_session(client)

    resp = client.post(
        f"/project-director/sessions/{session_id}/messages",
        json={"content": "请总结当前草案风险"},
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["session_id"] == session_id
    assert data["source"] == "rule_fallback"
    assert data["gate_conclusion"] == "Partial"
    assert "不启动 Worker" in data["forbidden_actions"]
    assert data["user_message"]["role"] == ProjectDirectorMessageRole.USER.value
    assert data["user_message"]["content"] == "请总结当前草案风险"
    assert data["user_message"]["source"] == "system"
    assert data["user_message"]["source_detail"] == "user_submitted_message"
    assert data["user_message"]["sequence_no"] == 1
    assert data["assistant_message"]["role"] == "assistant"
    assert data["assistant_message"]["source"] == "rule_fallback"
    assert data["assistant_message"]["source_detail"].startswith("stage_7_e4_rule_fallback")
    assert data["assistant_message"]["sequence_no"] == 2
    assert data["assistant_message"]["requires_confirmation"] is False
    assert data["assistant_message"]["suggested_actions"] == []
    assert "不会自动创建任务" in data["assistant_message"]["forbidden_actions_detected"]
    assert "不会修改仓库" in data["assistant_message"]["forbidden_actions_detected"]
    _assert_no_user_visible_technical_terms(
        data["assistant_message"]["content"],
        data["assistant_message"]["forbidden_actions_detected"],
    )


def test_list_messages_returns_session_timeline_in_sequence_order(client):
    session_id = _create_session(client)
    client.post(
        f"/project-director/sessions/{session_id}/messages",
        json={"content": "第一条"},
    )
    client.post(
        f"/project-director/sessions/{session_id}/messages",
        json={"content": "第二条"},
    )

    resp = client.get(f"/project-director/sessions/{session_id}/messages")

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_more"] is False
    messages = data["messages"]
    assert [m["sequence_no"] for m in messages] == [1, 2, 3, 4]
    assert [m["role"] for m in messages] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert messages[0]["content"] == "第一条"
    assert messages[2]["content"] == "第二条"



def test_list_messages_for_empty_session_matches_contract(client):
    session_id = _create_session(client)

    resp = client.get(f"/project-director/sessions/{session_id}/messages")

    assert resp.status_code == 200
    data = resp.json()
    assert data == {"session_id": session_id, "messages": [], "has_more": False}


def test_list_messages_defaults_to_latest_50_and_supports_before_cursor(client):
    session_id = _create_session(client)
    for index in range(26):
        resp = client.post(
            f"/project-director/sessions/{session_id}/messages",
            json={"content": f"消息 {index:02d}"},
        )
        assert resp.status_code == 201

    first_page_resp = client.get(f"/project-director/sessions/{session_id}/messages")

    assert first_page_resp.status_code == 200
    first_page = first_page_resp.json()
    assert first_page["has_more"] is True
    assert len(first_page["messages"]) == 50
    assert [m["sequence_no"] for m in first_page["messages"]] == list(range(3, 53))

    before_id = first_page["messages"][0]["id"]
    previous_page_resp = client.get(
        f"/project-director/sessions/{session_id}/messages",
        params={"before": before_id},
    )

    assert previous_page_resp.status_code == 200
    previous_page = previous_page_resp.json()
    assert previous_page["has_more"] is False
    assert [m["sequence_no"] for m in previous_page["messages"]] == [1, 2]


def test_list_messages_before_cursor_must_belong_to_same_session(client):
    session_id = _create_session(client)
    other_session_id = _create_session(client)
    other_post = client.post(
        f"/project-director/sessions/{other_session_id}/messages",
        json={"content": "另一个 session 的消息"},
    )
    other_message_id = other_post.json()["user_message"]["id"]

    resp = client.get(
        f"/project-director/sessions/{session_id}/messages",
        params={"before": other_message_id},
    )

    assert resp.status_code == 404
    assert "cursor" in resp.json()["detail"].lower()


def test_post_message_rejects_blank_content_without_persisting_messages(client, db_session):
    session_id = _create_session(client)

    resp = client.post(
        f"/project-director/sessions/{session_id}/messages",
        json={"content": "   \n\t  "},
    )

    assert resp.status_code == 422
    assert "empty" in resp.json()["detail"].lower() or "whitespace" in resp.json()["detail"].lower()
    assert _message_rows_for_session(db_session, session_id) == []


def test_messages_service_with_unconfigured_provider_falls_back_and_creates_no_run(db_session):
    session_repo = ProjectDirectorSessionRepository(db_session)
    director_service = ProjectDirectorService(
        session_repository=session_repo,
        provider_config_service=NoProviderConfigService(),
    )
    session_obj = director_service.create_session(
        goal_text="验证消息 API 不触发 Provider 或 Run",
    )
    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    )

    assert _count_rows(db_session, RunTable) == 0
    user_message, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="只记录消息，不允许触发执行链路",
    )

    assert user_message.source == "system"
    assert assistant_message.source == "rule_fallback"
    assert assistant_message.source_detail.startswith("stage_7_e4_rule_fallback")
    assert "provider_not_configured" in assistant_message.source_detail
    assert _count_rows(db_session, RunTable) == 0


def test_messages_service_provider_config_failure_uses_rule_fallback(db_session):
    session_repo = ProjectDirectorSessionRepository(db_session)
    director_service = ProjectDirectorService(
        session_repository=session_repo,
        provider_config_service=NoProviderConfigService(),
    )
    session_obj = director_service.create_session(
        goal_text="验证消息服务与 Provider 配置隔离",
    )
    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
        provider_config_service=ExplodingProviderConfigService(),
    )

    user_message, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="Provider 配置读取失败时必须降级规则回复",
    )

    assert user_message.source_detail == "user_submitted_message"
    assert assistant_message.source == "rule_fallback"
    assert "provider_config_unavailable" in assistant_message.source_detail
    assert "不会自动创建任务" in assistant_message.forbidden_actions_detected


def test_messages_are_fully_isolated_between_sessions(client, db_session):
    first_session_id = _create_session(client)
    second_session_id = _create_session(client)

    client.post(
        f"/project-director/sessions/{first_session_id}/messages",
        json={"content": "第一会话消息"},
    )
    client.post(
        f"/project-director/sessions/{second_session_id}/messages",
        json={"content": "第二会话消息"},
    )

    first_resp = client.get(f"/project-director/sessions/{first_session_id}/messages")
    second_resp = client.get(f"/project-director/sessions/{second_session_id}/messages")

    first_messages = first_resp.json()["messages"]
    second_messages = second_resp.json()["messages"]
    assert {m["session_id"] for m in first_messages} == {first_session_id}
    assert {m["session_id"] for m in second_messages} == {second_session_id}
    assert [m["content"] for m in first_messages if m["role"] == "user"] == ["第一会话消息"]
    assert [m["content"] for m in second_messages if m["role"] == "user"] == ["第二会话消息"]
    assert len(_message_rows_for_session(db_session, first_session_id)) == 2
    assert len(_message_rows_for_session(db_session, second_session_id)) == 2


def test_source_detail_readback_matches_persisted_rows(client, db_session):
    session_id = _create_session(client)

    post_resp = client.post(
        f"/project-director/sessions/{session_id}/messages",
        json={"content": "验证 source_detail 可追溯"},
    )
    list_resp = client.get(f"/project-director/sessions/{session_id}/messages")

    assert post_resp.status_code == 201
    assert list_resp.status_code == 200
    post_data = post_resp.json()
    messages = list_resp.json()["messages"]
    rows = _message_rows_for_session(db_session, session_id)

    assert rows[0].source_detail == "user_submitted_message"
    assert rows[1].source_detail.startswith("stage_7_e4_rule_fallback")
    assert [m["source_detail"] for m in messages] == [row.source_detail for row in rows]
    assert post_data["user_message"]["source_detail"] == rows[0].source_detail
    assert post_data["assistant_message"]["source_detail"] == rows[1].source_detail


def test_provider_chat_response_uses_read_only_context_and_creates_no_run(db_session):
    project = ProjectRepository(db_session).create(
        Project(name="Project Director 对话项目", summary="验证上下文读取")
    )
    TaskRepository(db_session).create(
        Task(project_id=project.id, title="上下文任务", input_summary="验证 provider prompt")
    )
    session_repo = ProjectDirectorSessionRepository(db_session)
    director_service = ProjectDirectorService(
        session_repository=session_repo,
        provider_config_service=NoProviderConfigService(),
    )
    session_obj = director_service.create_session(
        goal_text="基于现有项目回答用户问题",
        project_id=project.id,
        constraints="只读回答，不执行任何动作",
    )
    captured = {}

    def fake_provider(model_name: str, prompt_text: str, request_id: str):
        if request_id.startswith("project-director-interpretation-"):
            return (
                '{"conversation_mode":"general_discussion","primary_intent":"explore",'
                '"confidence":0.5,"formal_action_requested":false,"hypothetical_action":false,'
                '"referenced_option_ids":[],"referenced_entity_ids":[],'
                '"needs_formal_fact_context":false,"needs_discussion_history":false,'
                '"needs_retrieval":false,"reason_summary":"fallback"}',
                "receipt-interpretation",
            )
        captured["model_name"] = model_name
        captured["prompt_text"] = prompt_text
        captured["request_id"] = request_id
        return (
            '{"intent":"ask_about_next_step","answer":"这是基于上下文生成的 Project Director 对话回复",'
            '"suggested_actions":[{"type":"navigate","label":"查看项目页","requires_confirmation":false,"risk_level":"low"}],'
            '"requires_confirmation":false,"risk_level":"low","forbidden_actions_detected":[]}',
            "receipt-chat-1",
        )

    message_repo = ProjectDirectorMessageRepository(db_session)
    context_builder = ProjectDirectorContextBuilderService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=message_repo,
        project_repository=ProjectRepository(db_session),
        task_repository=TaskRepository(db_session),
    )
    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=message_repo,
        context_builder=context_builder,
        provider_config_service=ConfiguredProviderConfigService(),
        provider_text_generator=fake_provider,
    )

    assert _count_rows(db_session, RunTable) == 0
    user_message, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="请说明当前项目下一步",
    )

    assert user_message.source == "system"
    assert assistant_message.source == "ai"
    assert assistant_message.content == "这是基于上下文生成的 Project Director 对话回复"
    assert assistant_message.intent == "ask_about_next_step"
    assert assistant_message.suggested_actions == [
        {
            "type": "navigate",
            "label": "查看项目页",
            "requires_confirmation": False,
            "risk_level": "low",
        }
    ]
    assert "stage_7_e4_provider_chat" in assistant_message.source_detail
    assert "receipt-chat-1" in assistant_message.source_detail
    assert "semantic_source=provider" in assistant_message.source_detail
    assert captured["model_name"] == "test-chat-model"
    assert "基于现有项目回答用户问题" in captured["prompt_text"]
    assert "只读回答，不执行任何动作" in captured["prompt_text"]
    assert "Project Director 对话项目" in captured["prompt_text"]
    assert "上下文任务" in captured["prompt_text"]
    assert "请说明当前项目下一步" in captured["prompt_text"]
    assert "不能声称已执行任务" in captured["prompt_text"]
    assert "用户输入意图：询问下一步" in captured["prompt_text"]
    assert "已选上下文摘要" in captured["prompt_text"]
    assert captured["request_id"].startswith("project-director-chat-")
    assert assistant_message.requires_confirmation is False
    assert "不会修改仓库" in assistant_message.forbidden_actions_detected
    _assert_no_user_visible_technical_terms(
        assistant_message.content,
        assistant_message.forbidden_actions_detected,
        [action["label"] for action in assistant_message.suggested_actions],
    )
    assert _count_rows(db_session, RunTable) == 0


def test_provider_json_contract_persists_plan_trace_and_suggested_actions(db_session):
    project = ProjectRepository(db_session).create(
        Project(name="Provider 合同项目", summary="验证结构化输出")
    )
    session_obj = ProjectDirectorService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    ).create_session(
        goal_text="讨论草案合同",
        project_id=project.id,
    )
    plan = _create_plan_version(
        db_session,
        session_id=session_obj.id,
        project_id=project.id,
        plan_summary="Provider 合同测试草案",
    )

    def fake_provider(model_name: str, prompt_text: str, request_id: str):
        if request_id.startswith("project-director-interpretation-"):
            return (
                '{"conversation_mode":"general_discussion","primary_intent":"explore",'
                '"confidence":0.5,"formal_action_requested":false,"hypothetical_action":false,'
                '"referenced_option_ids":[],"referenced_entity_ids":[],'
                '"needs_formal_fact_context":false,"needs_discussion_history":false,'
                '"needs_retrieval":false,"reason_summary":"fallback"}',
                "receipt-interpretation",
            )
        return (
            "{"
            '"intent":"ask_about_plan",'
            f'"related_plan_version_id":"{plan.id}",'
            '"answer":"当前草案分为分析与设计、实现与验证两个阶段。",'
            '"suggested_actions":[{"type":"create_formal_project","label":"创建正式项目","requires_confirmation":false,"risk_level":"low"}],'
            '"requires_confirmation":false,'
            '"risk_level":"low",'
            '"forbidden_actions_detected":[]'
            "}",
            "receipt-contract-1",
        )

    message_repo = ProjectDirectorMessageRepository(db_session)
    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=message_repo,
        context_builder=ProjectDirectorContextBuilderService(
            session_repository=ProjectDirectorSessionRepository(db_session),
            message_repository=message_repo,
            plan_version_repository=ProjectDirectorPlanVersionRepository(db_session),
        ),
        provider_config_service=ConfiguredProviderConfigService(),
        provider_text_generator=fake_provider,
    )

    _, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="总结这个草案",
    )

    assert assistant_message.source == "ai"
    assert assistant_message.intent == "ask_about_plan"
    assert assistant_message.related_plan_version_id == plan.id
    assert assistant_message.content == "当前草案分为分析与设计、实现与验证两个阶段。"
    assert assistant_message.requires_confirmation is True
    assert assistant_message.risk_level == "low"
    assert assistant_message.suggested_actions == [
        {
            "type": "create_formal_project",
            "label": "创建正式项目",
            "requires_confirmation": True,
            "risk_level": "medium",
        }
    ]
    assert "receipt-contract-1" in assistant_message.source_detail
    assert "不会修改仓库" in assistant_message.forbidden_actions_detected
    assert _count_rows(db_session, RunTable) == 0


def test_provider_chat_failure_falls_back_without_run(db_session):
    session_repo = ProjectDirectorSessionRepository(db_session)
    director_service = ProjectDirectorService(
        session_repository=session_repo,
        provider_config_service=NoProviderConfigService(),
    )
    session_obj = director_service.create_session(goal_text="Provider 失败降级")

    def failing_provider(model_name: str, prompt_text: str, request_id: str):
        raise RuntimeError("provider exploded")

    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
        provider_config_service=ConfiguredProviderConfigService(),
        provider_text_generator=failing_provider,
    )

    user_message, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="请回复",
    )

    assert user_message.source == "system"
    assert assistant_message.source == "rule_fallback"
    # Interpretation fails first, so fallback_reason is provider_failed
    assert "semantic_fallback_reason=provider_failed" in assistant_message.source_detail
    assert "本回复不会自动执行任务" in assistant_message.content
    assert _count_rows(db_session, RunTable) == 0


@pytest.mark.parametrize(
    ("provider_output", "expected_reason"),
    [
        ("这是非 JSON 的 Provider 输出", "response_not_json"),
        ('{"intent":"ask_about_plan","answer":"   "}', "missing_non_empty_answer"),
        (
            '{"intent":"ask_about_plan","answer":"我已创建 Run 并启动 Worker。"}',
            "forbidden_execution_claim",
        ),
    ],
)
def test_invalid_provider_contract_falls_back_without_persisting_provider_text(
    db_session,
    provider_output,
    expected_reason,
):
    session_obj = ProjectDirectorService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    ).create_session(goal_text="非法 Provider 输出降级")

    def invalid_provider(model_name: str, prompt_text: str, request_id: str):
        if request_id.startswith("project-director-interpretation-"):
            return (
                '{"conversation_mode":"general_discussion","primary_intent":"explore",'
                '"confidence":0.5,"formal_action_requested":false,"hypothetical_action":false,'
                '"referenced_option_ids":[],"referenced_entity_ids":[],'
                '"needs_formal_fact_context":false,"needs_discussion_history":false,'
                '"needs_retrieval":false,"reason_summary":"fallback"}',
                "receipt-interpretation",
            )
        return provider_output, "receipt-invalid"

    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
        provider_config_service=ConfiguredProviderConfigService(),
        provider_text_generator=invalid_provider,
    )

    _, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="请总结",
    )

    assert assistant_message.source == "rule_fallback"
    assert "provider_contract_invalid" in assistant_message.source_detail
    assert expected_reason in assistant_message.source_detail
    assert provider_output not in assistant_message.content
    assert "非法 回答服务 输出降级" in assistant_message.content
    assert "不会启动外部工具" in assistant_message.content
    assert _count_rows(db_session, RunTable) == 0


def test_rule_fallback_uses_plan_risks_and_task_creation_context(db_session):
    project = ProjectRepository(db_session).create(
        Project(name="fallback 上下文项目", summary="验证规则回复读取事实")
    )
    task = TaskRepository(db_session).create(
        Task(project_id=project.id, title="已创建任务", input_summary="任务创建 readback")
    )
    session_obj = ProjectDirectorService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    ).create_session(
        goal_text="总结当前草案和风险",
        project_id=project.id,
        constraints="必须说明不执行动作",
    )
    plan = _create_plan_version(
        db_session,
        session_id=session_obj.id,
        project_id=project.id,
        plan_summary="草案包含上下文补齐、fallback 增强和测试收口。",
        risks=["Provider 合同不稳定", "用户可能误以为已执行"],
    )
    ProjectDirectorTaskCreationRecordRepository(db_session).create(
        ProjectDirectorTaskCreationRecord(
            plan_version_id=plan.id,
            session_id=session_obj.id,
            project_id=project.id,
            version_no=plan.version_no,
            task_ids=[task.id],
            task_count=1,
        )
    )
    message_repo = ProjectDirectorMessageRepository(db_session)
    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=message_repo,
        context_builder=ProjectDirectorContextBuilderService(
            session_repository=ProjectDirectorSessionRepository(db_session),
            message_repository=message_repo,
            plan_version_repository=ProjectDirectorPlanVersionRepository(db_session),
            task_creation_repository=ProjectDirectorTaskCreationRecordRepository(
                db_session
            ),
            project_repository=ProjectRepository(db_session),
            task_repository=TaskRepository(db_session),
        ),
        provider_config_service=NoProviderConfigService(),
    )

    _, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="总结当前草案风险",
    )

    assert assistant_message.source == "rule_fallback"
    assert "草案包含上下文补齐、fallback 增强和测试收口" in assistant_message.content
    assert "回答服务 合同不稳定" in assistant_message.content
    assert "用户可能误以为已执行" in assistant_message.content
    assert "分析与设计" in assistant_message.content
    assert "梳理上下文字段" in assistant_message.content
    assert "fallback 上下文项目" in assistant_message.content
    assert "任务数 1" in assistant_message.content
    assert "不会启动外部工具" in assistant_message.content
    assert _count_rows(db_session, RunTable) == 0


def test_request_action_route_is_high_risk_and_requires_confirmation(db_session):
    session_obj = ProjectDirectorService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    ).create_session(goal_text="验证执行请求只做安全回复")
    session_row_before = db_session.get(ProjectDirectorSessionTable, session_obj.id)
    status_before = session_row_before.status
    counts_before = {
        "sessions": _count_rows(db_session, ProjectDirectorSessionTable),
        "tasks": _count_rows(db_session, TaskTable),
        "runs": _count_rows(db_session, RunTable),
    }
    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    )

    _, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="请开始执行任务并提交推送",
    )

    assert assistant_message.intent == "request_action"
    assert assistant_message.risk_level == "high"
    assert assistant_message.requires_confirmation is True
    assert assistant_message.suggested_actions == []
    assert "不会自动执行任务" in assistant_message.forbidden_actions_detected
    assert "不会修改仓库" in assistant_message.forbidden_actions_detected
    assert "不会启动外部工具" in assistant_message.forbidden_actions_detected
    assert "我不能自动执行任务，也不会修改仓库" in assistant_message.content
    assert _count_rows(db_session, ProjectDirectorSessionTable) == counts_before["sessions"]
    assert _count_rows(db_session, TaskTable) == counts_before["tasks"]
    assert _count_rows(db_session, RunTable) == counts_before["runs"]
    assert db_session.get(ProjectDirectorSessionTable, session_obj.id).status == status_before
    _assert_no_user_visible_technical_terms(
        assistant_message.content,
        assistant_message.forbidden_actions_detected,
    )


def test_request_action_filters_provider_suggested_actions_over_route_safety(db_session):
    session_obj = ProjectDirectorService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    ).create_session(goal_text="过滤越界建议")

    def unsafe_provider(model_name: str, prompt_text: str, request_id: str):
        if request_id.startswith("project-director-interpretation-"):
            return (
                '{"conversation_mode":"action_request","primary_intent":"execute",'
                '"confidence":0.9,"formal_action_requested":true,"hypothetical_action":false,'
                '"referenced_option_ids":[],"referenced_entity_ids":[],'
                '"needs_formal_fact_context":false,"needs_discussion_history":false,'
                '"needs_retrieval":false,"reason_summary":"action request"}',
                "receipt-interpretation",
            )
        return (
            "{"
            '"intent":"request_action",'
            '"answer":"我可以先说明需要确认的步骤。",'
            '"suggested_actions":['
            '{"type":"run_worker_once","label":"启动执行","requires_confirmation":false,"risk_level":"low"},'
            '{"type":"create_formal_project","label":"创建正式项目","requires_confirmation":false,"risk_level":"low"},'
            '{"type":"navigate","label":"查看提醒","requires_confirmation":false,"risk_level":"low"},'
            '{"type":"explain","label":"说明确认步骤","requires_confirmation":false,"risk_level":"low"}'
            "],"
            '"requires_confirmation":false,'
            '"risk_level":"low",'
            '"forbidden_actions_detected":[]'
            "}",
            "receipt-route-safety",
        )

    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
        provider_config_service=ConfiguredProviderConfigService(),
        provider_text_generator=unsafe_provider,
    )

    _, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="请启动执行并提交",
    )

    action_types = [action["type"] for action in assistant_message.suggested_actions]
    assert "run_worker_once" not in action_types
    assert "create_formal_project" not in action_types
    assert action_types == ["navigate", "explain"]
    assert all(action["requires_confirmation"] is True for action in assistant_message.suggested_actions)
    assert {action["risk_level"] for action in assistant_message.suggested_actions} == {"high"}
    assert assistant_message.intent == "request_action"
    assert assistant_message.risk_level == "high"
    assert assistant_message.requires_confirmation is True
    assert _count_rows(db_session, RunTable) == 0


def test_ask_inbox_route_maps_to_existing_current_context_intent(db_session):
    session_obj = ProjectDirectorService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    ).create_session(goal_text="查看提醒")
    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    )

    _, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="有哪些提醒和待处理？",
    )

    assert assistant_message.intent == "ask_about_current_context"
    assert assistant_message.risk_level == "low"
    assert "可以查看提醒并解释含义，但不会替你执行任何操作" in assistant_message.content
    _assert_no_user_visible_technical_terms(
        assistant_message.content,
        assistant_message.forbidden_actions_detected,
    )


def test_challenge_plan_route_is_medium_risk_without_modification(db_session):
    session_obj = ProjectDirectorService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    ).create_session(goal_text="质疑草案")
    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    )

    _, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="我不同意，这样不合理",
    )

    assert assistant_message.intent == "request_plan_change"
    assert assistant_message.risk_level == "medium"
    assert assistant_message.requires_confirmation is True
    assert assistant_message.suggested_actions == []
    assert "不会直接应用草案修改" in assistant_message.forbidden_actions_detected
    assert "不会直接修改草案" in assistant_message.content
    assert _count_rows(db_session, RunTable) == 0


def test_challenge_readback_fallback_handles_plan_challenge_without_raw_statement(
    db_session,
):
    session_obj = ProjectDirectorService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    ).create_session(goal_text="质疑草案 readback")
    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    )

    _, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="我不同意这个草案",
    )

    assert assistant_message.intent == "request_plan_change"
    assert assistant_message.risk_level == "medium"
    assert assistant_message.requires_confirmation is True
    assert "我会先把这当作一个需要复核的问题处理" in assistant_message.content
    assert "我会先把它整理成一个可审查的建议" in assistant_message.content
    assert "我会先把它整理成一个可查看的草稿" in assistant_message.content
    assert "这只是计划修改草稿，不会直接改草案" in assistant_message.content
    assert "这只是修改建议，不会直接改草案" in assistant_message.content
    assert "继续处理前需要你确认" in assistant_message.content
    assert "继续处理前需要你确认或复核" in assistant_message.content
    assert "不会直接修改草案，会先解释原因或准备修改建议" in assistant_message.content
    assert "我不同意这个草案" not in assistant_message.content
    assert "proposal_type=plan_revision" in assistant_message.source_detail
    assert "approval_requirement=user_confirmation_required" in assistant_message.source_detail
    assert "has_plan_revision=true" in assistant_message.source_detail
    # Semantic metadata extends source_detail; conversion fields may be truncated
    assert "semantic_source=rule_fallback" in assistant_message.source_detail
    assert "challenge_type" not in assistant_message.content
    assert "proposal_type" not in assistant_message.content
    assert "approval_requirement" not in assistant_message.content
    assert "plan_revision" not in assistant_message.content
    assert "conversion_target" not in assistant_message.content
    assert "conversion_status" not in assistant_message.content
    assert "plan_draft" not in assistant_message.content
    assert "task_draft" not in assistant_message.content
    assert "不会自动修改草案" in assistant_message.forbidden_actions_detected
    _assert_no_user_visible_technical_terms(
        assistant_message.content,
        assistant_message.forbidden_actions_detected,
        [action["label"] for action in assistant_message.suggested_actions],
    )
    assert _count_rows(db_session, RunTable) == 0


def test_challenge_readback_requirement_change_is_high_risk_without_mutation(
    db_session,
):
    session_obj = ProjectDirectorService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    ).create_session(goal_text="需求变更 readback")
    session_row_before = db_session.get(ProjectDirectorSessionTable, session_obj.id)
    status_before = session_row_before.status
    counts_before = {
        "sessions": _count_rows(db_session, ProjectDirectorSessionTable),
        "tasks": _count_rows(db_session, TaskTable),
        "runs": _count_rows(db_session, RunTable),
    }
    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    )

    _, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="需求变了，要换需求",
    )

    # With NoProviderConfigService, semantic rule-fallback returns general_discussion
    # which downgrades the legacy request_plan_change to general_discussion
    assert assistant_message.intent == "general_discussion"
    assert assistant_message.risk_level == "high"
    assert assistant_message.requires_confirmation is True
    assert "需求变更" in assistant_message.content
    assert "我会先把它整理成一个可审查的建议" in assistant_message.content
    assert "我会先把它整理成一个可查看的草稿" in assistant_message.content
    assert "这只是计划修改草稿，不会直接改草案" in assistant_message.content
    assert "继续处理前需要你确认" in assistant_message.content
    assert "继续处理前需要你确认或复核" in assistant_message.content
    assert "不会直接修改草案，会先解释原因或准备修改建议" in assistant_message.content
    assert "proposal_type=requirement_change_review" in assistant_message.source_detail
    assert "approval_requirement=human_review_required" in assistant_message.source_detail
    assert "has_plan_revision=true" in assistant_message.source_detail
    assert "semantic_source=rule_fallback" in assistant_message.source_detail
    assert _count_rows(db_session, ProjectDirectorSessionTable) == counts_before["sessions"]
    assert _count_rows(db_session, TaskTable) == counts_before["tasks"]
    assert _count_rows(db_session, RunTable) == counts_before["runs"]
    assert db_session.get(ProjectDirectorSessionTable, session_obj.id).status == status_before
    _assert_no_user_visible_technical_terms(
        assistant_message.content,
        assistant_message.forbidden_actions_detected,
    )


def test_conversion_task_scope_fallback_uses_task_draft_without_task_creation(
    db_session,
):
    session_obj = ProjectDirectorService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    ).create_session(goal_text="任务范围草稿 readback")
    status_before = db_session.get(ProjectDirectorSessionTable, session_obj.id).status
    counts_before = {
        "sessions": _count_rows(db_session, ProjectDirectorSessionTable),
        "tasks": _count_rows(db_session, TaskTable),
        "runs": _count_rows(db_session, RunTable),
    }
    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    )

    _, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="这个任务范围做多了，验收也不对",
    )

    # Legacy route is ASK_TASK_OR_RUN (via "任务"), maps to ask_about_current_context.
    # Semantic overlay doesn't downgrade readonly intents.
    assert assistant_message.intent == "ask_about_current_context"
    assert assistant_message.risk_level == "medium"
    assert assistant_message.requires_confirmation is True
    assert "我会先把它整理成一个可查看的草稿" in assistant_message.content
    assert "这只是任务草稿，不会自动创建任务" in assistant_message.content
    assert "任务草稿标题：调整任务范围" in assistant_message.content
    assert "任务草稿摘要：这条反馈适合整理为任务范围调整草稿" in assistant_message.content
    assert "proposal_type=task_scope_revision" in assistant_message.source_detail
    assert "semantic_source=rule_fallback" in assistant_message.source_detail
    assert _count_rows(db_session, ProjectDirectorSessionTable) == counts_before["sessions"]
    assert _count_rows(db_session, TaskTable) == counts_before["tasks"]
    assert _count_rows(db_session, RunTable) == counts_before["runs"]
    assert db_session.get(ProjectDirectorSessionTable, session_obj.id).status == status_before
    _assert_no_user_visible_technical_terms(
        assistant_message.content,
        assistant_message.forbidden_actions_detected,
    )


def test_challenge_readback_dispatch_fallback_translates_external_tool_names(
    db_session,
):
    session_obj = ProjectDirectorService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    ).create_session(goal_text="调度质疑 readback")
    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    )

    _, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="调度给 Codex 不合理",
    )

    # With NoProviderConfigService, semantic rule-fallback returns general_discussion.
    # Legacy route is REQUEST_ACTION (via "调度"), but semantic challenge mode
    # maps to CHALLENGE_PLAN → request_plan_change via effective route.
    assert assistant_message.intent == "request_plan_change"
    assert assistant_message.risk_level == "high"
    assert assistant_message.requires_confirmation is True
    assert "外部工具" in assistant_message.content
    assert "不会启动外部工具，会先解释调度依据并等待你确认" in assistant_message.content
    assert "不会启动外部工具，会先复核调度安排" in assistant_message.content
    assert "我会先把它整理成一个可查看的草稿" in assistant_message.content
    assert "这类反馈更适合先解释原因，不会执行后续动作" in assistant_message.content
    assert "proposal_type=dispatch_review" in assistant_message.source_detail
    assert "approval_requirement=human_review_required" in assistant_message.source_detail
    assert "has_plan_revision=false" in assistant_message.source_detail
    assert "semantic_source=rule_fallback" in assistant_message.source_detail
    assert "不会启动外部工具" in assistant_message.forbidden_actions_detected
    _assert_no_user_visible_technical_terms(
        assistant_message.content,
        assistant_message.forbidden_actions_detected,
    )
    assert _count_rows(db_session, RunTable) == 0


def test_challenge_readback_provider_prompt_and_suggested_actions_are_safe(
    db_session,
):
    session_obj = ProjectDirectorService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    ).create_session(goal_text="调度建议 readback")
    captured = {}

    def unsafe_provider(model_name: str, prompt_text: str, request_id: str):
        if request_id.startswith("project-director-interpretation-"):
            return (
                '{"conversation_mode":"challenge","primary_intent":"challenge",'
                '"confidence":0.8,"formal_action_requested":false,"hypothetical_action":false,'
                '"referenced_option_ids":[],"referenced_entity_ids":[],'
                '"needs_formal_fact_context":true,"needs_discussion_history":true,'
                '"needs_retrieval":false,"reason_summary":"dispatch challenge"}',
                "receipt-interpretation",
            )
        captured["prompt_text"] = prompt_text
        return (
            "{"
            '"intent":"request_action",'
            '"answer":"可以先说明外部工具的调度依据，等待你确认。",'
            '"suggested_actions":['
            '{"type":"run_worker_once","label":"启动执行","requires_confirmation":false,"risk_level":"low"},'
            '{"type":"create_formal_project","label":"创建任务","requires_confirmation":false,"risk_level":"low"},'
            '{"type":"navigate","label":"启动执行","requires_confirmation":false,"risk_level":"low"},'
            '{"type":"request_changes","label":"准备修改建议","requires_confirmation":false,"risk_level":"low"},'
            '{"type":"explain","label":"解释调度依据","requires_confirmation":false,"risk_level":"low"}'
            "],"
            '"requires_confirmation":false,'
            '"risk_level":"low",'
            '"forbidden_actions_detected":[]'
            "}",
            "receipt-challenge-readback",
        )

    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
        provider_config_service=ConfiguredProviderConfigService(),
        provider_text_generator=unsafe_provider,
    )

    _, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="调度给 Codex 不合理",
    )

    assert "复核问题回看" in captured["prompt_text"]
    assert "可审查建议回看" in captured["prompt_text"]
    assert "可查看草稿回看" in captured["prompt_text"]
    assert "反馈类型：质疑调度建议" in captured["prompt_text"]
    assert "严重程度：高" in captured["prompt_text"]
    assert "摘要：收到用户反馈，需要处理“质疑调度建议”" in captured["prompt_text"]
    assert "提取原因：用户认为调度建议需要人工确认" in captured["prompt_text"]
    assert "建议类型：建议复核调度安排" in captured["prompt_text"]
    assert "建议摘要：这条反馈涉及调度安排，需要人工复核后再决定" in captured["prompt_text"]
    assert "审查要求：需要人工复核" in captured["prompt_text"]
    assert "这只是建议，不是已应用" in captured["prompt_text"]
    assert "不能声称已执行审批" in captured["prompt_text"]
    assert "不能把建议写成已处理完成" in captured["prompt_text"]
    assert "草稿类型：仅解释说明" in captured["prompt_text"]
    assert "草稿摘要：这条建议只适合先解释原因，不生成执行草稿" in captured["prompt_text"]
    assert "审查状态：草稿" in captured["prompt_text"]
    assert "这只是草稿，不是已应用" in captured["prompt_text"]
    assert "不能把草稿写成已处理完成" in captured["prompt_text"]
    assert "安全边界：不会自动修改草案" in captured["prompt_text"]
    assert "可做下一步：解释调度依据" in captured["prompt_text"]
    assert "不能把复核问题写成已处理完成" in captured["prompt_text"]
    assert assistant_message.source == "ai"
    # Challenge semantic mode maps to CHALLENGE_PLAN → request_plan_change
    assert assistant_message.intent == "request_plan_change"
    assert assistant_message.risk_level == "high"
    assert assistant_message.requires_confirmation is True
    action_types = [action["type"] for action in assistant_message.suggested_actions]
    action_labels = [action["label"] for action in assistant_message.suggested_actions]
    assert action_types == ["request_changes", "explain"]
    assert action_labels == ["准备修改建议", "解释调度依据"]
    assert all(action["requires_confirmation"] is True for action in assistant_message.suggested_actions)
    assert {action["risk_level"] for action in assistant_message.suggested_actions} == {"high"}
    assert "proposal_type=dispatch_review" in assistant_message.source_detail
    assert "approval_requirement=human_review_required" in assistant_message.source_detail
    assert "conversion_target=explanation_only" in assistant_message.source_detail
    assert "semantic_source=provider" in assistant_message.source_detail
    assert "semantic_mode=challenge" in assistant_message.source_detail
    _assert_no_user_visible_technical_terms(
        assistant_message.content,
        assistant_message.forbidden_actions_detected,
        action_labels,
    )
    assert _count_rows(db_session, RunTable) == 0


def test_proposal_plan_revision_prompt_readback_is_not_applied(
    db_session,
):
    session_obj = ProjectDirectorService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    ).create_session(goal_text="草案建议 readback")
    status_before = db_session.get(ProjectDirectorSessionTable, session_obj.id).status
    counts_before = {
        "sessions": _count_rows(db_session, ProjectDirectorSessionTable),
        "tasks": _count_rows(db_session, TaskTable),
        "runs": _count_rows(db_session, RunTable),
    }
    captured = {}

    def safe_provider(model_name: str, prompt_text: str, request_id: str):
        if request_id.startswith("project-director-interpretation-"):
            return (
                '{"conversation_mode":"challenge","primary_intent":"challenge_plan",'
                '"confidence":0.8,"formal_action_requested":false,"hypothetical_action":false,'
                '"referenced_option_ids":[],"referenced_entity_ids":[],'
                '"needs_formal_fact_context":true,"needs_discussion_history":true,'
                '"needs_retrieval":false,"reason_summary":"plan challenge"}',
                "receipt-interpretation",
            )
        captured["prompt_text"] = prompt_text
        return (
            "{"
            '"intent":"request_plan_change",'
            '"answer":"我会先整理建议，等待你确认，不会直接改草案。",'
            '"suggested_actions":[{"type":"request_changes","label":"准备草案修改建议","requires_confirmation":false,"risk_level":"low"}],'
            '"requires_confirmation":false,'
            '"risk_level":"low",'
            '"forbidden_actions_detected":[]'
            "}",
            "receipt-plan-proposal",
        )

    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
        provider_config_service=ConfiguredProviderConfigService(),
        provider_text_generator=safe_provider,
    )

    _, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="我不同意这个计划，草案拆分不合理",
    )

    assert "可审查建议回看" in captured["prompt_text"]
    assert "可查看草稿回看" in captured["prompt_text"]
    assert "建议类型：建议调整项目草案" in captured["prompt_text"]
    assert "修改建议标题：调整草案摘要" in captured["prompt_text"]
    assert "修改建议摘要：建议复核项目草案摘要" in captured["prompt_text"]
    assert "受影响内容：项目草案、范围说明" in captured["prompt_text"]
    assert "建议改动：重新梳理草案摘要、补充受影响范围" in captured["prompt_text"]
    assert "这只是建议，不是已应用" in captured["prompt_text"]
    assert "不能声称已修改草案" in captured["prompt_text"]
    assert "不能声称已创建任务" in captured["prompt_text"]
    assert "不能声称已执行审批" in captured["prompt_text"]
    assert "草稿类型：计划修改草稿" in captured["prompt_text"]
    assert "计划草稿标题：调整草案摘要" in captured["prompt_text"]
    assert "计划草稿摘要：建议复核项目草案摘要" in captured["prompt_text"]
    assert "这只是草稿，不是已应用" in captured["prompt_text"]
    assert "不能声称已创建任务" in captured["prompt_text"]
    assert assistant_message.intent == "request_plan_change"
    assert assistant_message.risk_level == "medium"
    assert assistant_message.requires_confirmation is True
    assert assistant_message.suggested_actions == [
        {
            "type": "request_changes",
            "label": "准备草案修改建议",
            "requires_confirmation": True,
            "risk_level": "medium",
        }
    ]
    assert "proposal_type=plan_revision" in assistant_message.source_detail
    assert "approval_requirement=user_confirmation_required" in assistant_message.source_detail
    assert "has_plan_revision=true" in assistant_message.source_detail
    assert "semantic_source=provider" in assistant_message.source_detail
    assert "semantic_mode=challenge" in assistant_message.source_detail
    assert _count_rows(db_session, ProjectDirectorSessionTable) == counts_before["sessions"]
    assert _count_rows(db_session, TaskTable) == counts_before["tasks"]
    assert _count_rows(db_session, RunTable) == counts_before["runs"]
    assert db_session.get(ProjectDirectorSessionTable, session_obj.id).status == status_before
    _assert_no_user_visible_technical_terms(
        assistant_message.content,
        assistant_message.forbidden_actions_detected,
        [action["label"] for action in assistant_message.suggested_actions],
    )


def test_challenge_readback_provider_contract_fallback_uses_seed_boundaries(
    db_session,
):
    session_obj = ProjectDirectorService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    ).create_session(goal_text="非法回答降级 readback")

    def invalid_provider(model_name: str, prompt_text: str, request_id: str):
        if request_id.startswith("project-director-interpretation-"):
            return (
                '{"conversation_mode":"challenge","primary_intent":"challenge",'
                '"confidence":0.8,"formal_action_requested":false,"hypothetical_action":false,'
                '"referenced_option_ids":[],"referenced_entity_ids":[],'
                '"needs_formal_fact_context":true,"needs_discussion_history":true,'
                '"needs_retrieval":false,"reason_summary":"governance challenge"}',
                "receipt-interpretation",
            )
        return "不是 JSON", "receipt-invalid-challenge"

    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
        provider_config_service=ConfiguredProviderConfigService(),
        provider_text_generator=invalid_provider,
    )

    _, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="成本和 Skill 权限治理不合理",
    )

    assert assistant_message.source == "rule_fallback"
    assert assistant_message.risk_level == "high"
    assert assistant_message.requires_confirmation is True
    assert "我会先把这当作一个需要复核的问题处理" in assistant_message.content
    assert "质疑治理设置" in assistant_message.content
    assert "不会修改治理配置，会先说明风险和建议" in assistant_message.content
    assert "不会修改治理配置，会先复核风险" in assistant_message.content
    assert "这类反馈更适合先解释原因，不会执行后续动作" in assistant_message.content
    assert "继续处理前需要你确认或复核" in assistant_message.content
    assert "不会自动修改草案" in assistant_message.forbidden_actions_detected
    assert "proposal_type=governance_review" in assistant_message.source_detail
    assert "approval_requirement=human_review_required" in assistant_message.source_detail
    assert "has_plan_revision=false" in assistant_message.source_detail
    assert "conversion_target=explanation_only" in assistant_message.source_detail
    assert "semantic_source=provider" in assistant_message.source_detail
    assert "semantic_mode=challenge" in assistant_message.source_detail
    assert "challenge_type" not in assistant_message.content
    assert "proposal_type" not in assistant_message.content
    assert "approval_requirement" not in assistant_message.content
    _assert_no_user_visible_technical_terms(
        assistant_message.content,
        assistant_message.forbidden_actions_detected,
    )
    assert _count_rows(db_session, RunTable) == 0


def test_provider_unavailable_request_action_uses_router_chinese_safety(db_session):
    session_obj = ProjectDirectorService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    ).create_session(goal_text="执行请求降级")
    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    )

    _, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="请创建任务并执行",
    )

    assert assistant_message.source == "rule_fallback"
    assert assistant_message.intent == "request_action"
    assert assistant_message.risk_level == "high"
    assert assistant_message.requires_confirmation is True
    assert "我不能自动执行任务，也不会修改仓库" in assistant_message.content
    assert "不会自动执行任务" in assistant_message.forbidden_actions_detected
    _assert_no_user_visible_technical_terms(
        assistant_message.content,
        assistant_message.forbidden_actions_detected,
    )


def test_assembler_exception_falls_back_to_base_context_without_interrupting(
    db_session,
    monkeypatch,
):
    session_obj = ProjectDirectorService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    ).create_session(goal_text="上下文异常降级")

    def explode(self, **kwargs):
        raise RuntimeError("assembler exploded")

    monkeypatch.setattr(DirectorContextAssemblerService, "assemble", explode)
    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    )

    user_message, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="当前状态如何？",
    )

    assert user_message.sequence_no == 1
    assert assistant_message.sequence_no == 2
    assert assistant_message.source == "rule_fallback"
    assert "上下文回看失败，已使用基础上下文" in assistant_message.content
    assert "context_note=上下文回看失败，已使用基础上下文" in assistant_message.source_detail
    assert len(_message_rows_for_session(db_session, session_obj.id)) == 2
    assert _count_rows(db_session, RunTable) == 0


def test_assistant_user_visible_text_avoids_technical_terms(db_session):
    session_obj = ProjectDirectorService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    ).create_session(goal_text="检查用户可见文案")
    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    )

    _, assistant_message = message_service.post_user_message(
        session_id=session_obj.id,
        content="请问 API payload 和 Git 相关状态？",
    )

    _assert_no_user_visible_technical_terms(
        assistant_message.content,
        assistant_message.forbidden_actions_detected,
        [action["label"] for action in assistant_message.suggested_actions],
    )


def test_context_builder_reads_recent_messages_project_and_tasks(db_session):
    project = ProjectRepository(db_session).create(
        Project(name="上下文读取项目", summary="只读 snapshot")
    )
    task = TaskRepository(db_session).create(
        Task(project_id=project.id, title="第一任务", input_summary="读取任务")
    )
    session_obj = ProjectDirectorService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    ).create_session(
        goal_text="验证 context builder",
        project_id=project.id,
        constraints="读取但不写入",
    )
    older_plan = _create_plan_version(
        db_session,
        session_id=session_obj.id,
        project_id=project.id,
        version_no=1,
        plan_summary="旧版草案摘要",
    )
    latest_plan = _create_plan_version(
        db_session,
        session_id=session_obj.id,
        project_id=project.id,
        version_no=2,
        plan_summary="最新版草案摘要：请优先读取这一版。",
        risks=["最新版风险 A", "最新版风险 B"],
    )
    ProjectDirectorTaskCreationRecordRepository(db_session).create(
        ProjectDirectorTaskCreationRecord(
            plan_version_id=latest_plan.id,
            session_id=session_obj.id,
            project_id=project.id,
            version_no=latest_plan.version_no,
            task_ids=[task.id],
            task_count=1,
        )
    )
    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    )
    message_service.post_user_message(session_id=session_obj.id, content="第一轮")

    context = ProjectDirectorContextBuilderService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
        plan_version_repository=ProjectDirectorPlanVersionRepository(db_session),
        task_creation_repository=ProjectDirectorTaskCreationRecordRepository(
            db_session
        ),
        project_repository=ProjectRepository(db_session),
        task_repository=TaskRepository(db_session),
    ).build_context(session_id=session_obj.id)

    assert context.session_id == session_obj.id
    assert context.project_id == project.id
    assert context.goal_text == "验证 context builder"
    assert context.constraints == "读取但不写入"
    assert context.session_status == "clarifying"
    assert context.clarifying_questions
    assert context.clarifying_questions[0]["id"]
    assert context.clarifying_questions[0]["question"]
    assert [message.content for message in context.recent_messages] == [
        "第一轮",
        context.recent_messages[1].content,
    ]
    assert context.latest_plan_version is not None
    assert context.latest_plan_version["id"] == str(latest_plan.id)
    assert context.latest_plan_version["version_no"] == 2
    assert context.latest_plan_version["plan_summary"] == "最新版草案摘要：请优先读取这一版。"
    assert context.latest_plan_version["phases"][0]["name"] == "分析与设计"
    assert context.latest_plan_version["proposed_tasks"][0]["title"] == "梳理上下文字段"
    assert context.latest_plan_version["risks"] == ["最新版风险 A", "最新版风险 B"]
    assert context.latest_plan_version["complexity_assessment"]["score"] == 3
    assert context.task_creation is not None
    assert context.task_creation["plan_version_id"] == str(latest_plan.id)
    assert context.task_creation["project_name"] == "上下文读取项目"
    assert context.task_creation["created_task_ids"] == [str(task.id)]
    assert context.task_creation["task_count"] == 1
    assert context.project_snapshot is not None
    assert context.project_snapshot["name"] == "上下文读取项目"
    assert context.task_snapshot is not None
    assert context.task_snapshot["total"] == 1
    assert context.task_snapshot["recent_tasks"][0]["title"] == "第一任务"
    assert "不写仓库" in context.safety_boundary
    assert older_plan.id != latest_plan.id


def test_context_builder_defaults_to_latest_20_recent_messages(db_session):
    session_obj = ProjectDirectorService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    ).create_session(goal_text="验证最近消息默认窗口")
    message_service = ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    )
    for index in range(11):
        message_service.post_user_message(
            session_id=session_obj.id,
            content=f"窗口消息 {index:02d}",
        )

    context = ProjectDirectorContextBuilderService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        message_repository=ProjectDirectorMessageRepository(db_session),
    ).build_context(session_id=session_obj.id)

    assert len(context.recent_messages) == 20
    assert [message.sequence_no for message in context.recent_messages] == list(
        range(3, 23)
    )
    assert context.recent_messages[0].role == "user"
    assert context.recent_messages[-1].role == "assistant"
    assert context.recent_messages[-2].content == "窗口消息 10"


def test_message_endpoints_return_404_for_missing_session(client):
    missing_session_id = uuid4()

    get_resp = client.get(f"/project-director/sessions/{missing_session_id}/messages")
    post_resp = client.post(
        f"/project-director/sessions/{missing_session_id}/messages",
        json={"content": "hello"},
    )

    assert get_resp.status_code == 404
    assert post_resp.status_code == 404
