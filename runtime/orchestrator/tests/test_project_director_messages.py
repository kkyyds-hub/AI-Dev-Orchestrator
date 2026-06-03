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
from app.core.db_tables import ORMBase, ProjectDirectorMessageTable, RunTable
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
from app.services.project_director_message_service import ProjectDirectorMessageService
from app.services.project_director_service import ProjectDirectorService
from app.services.provider_config_service import OpenAIProviderRuntimeConfig


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
    assert data["assistant_message"]["source_detail"].startswith("stage_7_b2_rule_fallback")
    assert data["assistant_message"]["sequence_no"] == 2
    assert data["assistant_message"]["requires_confirmation"] is False
    assert data["assistant_message"]["suggested_actions"] == []
    assert "不创建 Run" in data["assistant_message"]["forbidden_actions_detected"]
    assert "不执行 suggested_actions" in data["assistant_message"]["forbidden_actions_detected"]


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
    assert assistant_message.source_detail.startswith("stage_7_b2_rule_fallback")
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
    assert "不创建 Run" in assistant_message.forbidden_actions_detected


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
    assert rows[1].source_detail.startswith("stage_7_b2_rule_fallback")
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
        captured["model_name"] = model_name
        captured["prompt_text"] = prompt_text
        captured["request_id"] = request_id
        return (
            '{"intent":"ask_about_next_step","answer":"这是 Provider 生成的 Project Director 对话回复",'
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
    assert assistant_message.content == "这是 Provider 生成的 Project Director 对话回复"
    assert assistant_message.intent == "ask_about_next_step"
    assert assistant_message.suggested_actions == [
        {
            "type": "navigate",
            "label": "查看项目页",
            "requires_confirmation": False,
            "risk_level": "low",
        }
    ]
    assert "stage_7_b2_provider_chat" in assistant_message.source_detail
    assert "receipt-chat-1" in assistant_message.source_detail
    assert captured["model_name"] == "test-chat-model"
    assert "基于现有项目回答用户问题" in captured["prompt_text"]
    assert "只读回答，不执行任何动作" in captured["prompt_text"]
    assert "Project Director 对话项目" in captured["prompt_text"]
    assert "上下文任务" in captured["prompt_text"]
    assert "请说明当前项目下一步" in captured["prompt_text"]
    assert "不得声称已经启动 Worker" in captured["prompt_text"]
    assert captured["request_id"].startswith("project-director-chat-")
    assert assistant_message.requires_confirmation is False
    assert "不写仓库" in assistant_message.forbidden_actions_detected
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
    assert "不执行 suggested_actions" in assistant_message.forbidden_actions_detected
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
    assert "provider_generation_failed" in assistant_message.source_detail
    assert "provider exploded" in assistant_message.source_detail
    assert "本回复不会启动 Worker" in assistant_message.content
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
    assert "非法 Provider 输出降级" in assistant_message.content
    assert "不会启动 Worker" in assistant_message.content
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
    assert "Provider 合同不稳定" in assistant_message.content
    assert "用户可能误以为已执行" in assistant_message.content
    assert "分析与设计" in assistant_message.content
    assert "梳理上下文字段" in assistant_message.content
    assert "fallback 上下文项目" in assistant_message.content
    assert "任务数 1" in assistant_message.content
    assert "不会启动 Worker" in assistant_message.content
    assert _count_rows(db_session, RunTable) == 0


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
