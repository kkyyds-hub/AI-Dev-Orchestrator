"""Tests for P7-E3 Project Director context assembler read-only service."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.db_tables import (
    AgentMessageTable,
    ORMBase,
    ProjectDirectorMessageTable,
    ProjectDirectorPlanVersionTable,
    ProjectDirectorSessionTable,
    RunTable,
    TaskTable,
)
from app.domain.agent_dispatch_decision import (
    P6_AGENT_DISPATCH_DECISION_AUDIT_EVENT_TYPE,
)
from app.domain.agent_message import AgentMessageRole, AgentMessageType
from app.domain.project_director_conversation_router import (
    ContextScope,
    ConversationIntent,
    ConversationRouter,
    RouteDecision,
    SafetyPolicy,
    SafetyRiskLevel,
)
from app.domain.project_director_message import (
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_plan_version import PlanVersionStatus
from app.domain.project_director_session import ProjectDirectorSessionStatus
from app.domain.run import RunStatus
from app.domain.task import TaskHumanStatus, TaskPriority, TaskRiskLevel, TaskStatus
from app.services.project_director_context_assembler_service import (
    DirectorContextAssemblerNotFoundError,
    DirectorContextAssemblerService,
)


TECHNICAL_TERMS = (
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
)


@pytest.fixture()
def db_session(tmp_path):
    db_path = tmp_path / "orchestrator-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_assemble_current_context_includes_scope_sections(db_session: Session) -> None:
    now = datetime.now(timezone.utc)
    project_id = uuid4()
    conversation_id = _seed_director_session(
        db_session,
        goal_text="当前状态会话",
        now=now,
        project_id=project_id,
    )
    _seed_director_message(
        db_session,
        session_id=conversation_id,
        role=ProjectDirectorMessageRole.USER,
        content="请看当前状态",
        sequence_no=1,
        created_at=now - timedelta(minutes=2),
    )
    _seed_director_message(
        db_session,
        session_id=conversation_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="请确认草案。",
        sequence_no=2,
        created_at=now - timedelta(minutes=1),
        requires_confirmation=True,
    )
    _seed_plan_version(
        db_session,
        session_id=conversation_id,
        project_id=project_id,
        now=now,
    )

    assembly = DirectorContextAssemblerService(db_session).assemble(
        conversation_id=conversation_id,
        route_decision=ConversationRouter.classify("当前状态和项目情况如何？"),
        recent_message_limit=10,
        inbox_limit=10,
    )
    sections = _sections_by_key(assembly)

    assert assembly.conversation_id == conversation_id
    assert assembly.session_id == conversation_id
    assert assembly.project_id == project_id
    assert assembly.route_intent == ConversationIntent.ASK_CURRENT_CONTEXT
    assert assembly.recent_messages_count == 2
    assert assembly.inbox_attention_count >= 1
    assert assembly.has_plan is True
    assert sections["conversation"].included is True
    assert sections["recent_messages"].included is True
    assert sections["latest_plan"].included is True
    assert sections["inbox_attention"].included is True
    assert sections["conversation_list"].included is False


def test_ask_inbox_scope_does_not_force_latest_plan(db_session: Session) -> None:
    now = datetime.now(timezone.utc)
    project_id = uuid4()
    conversation_id = _seed_director_session(
        db_session,
        goal_text="只看提醒",
        now=now,
        project_id=project_id,
    )
    _seed_plan_version(
        db_session,
        session_id=conversation_id,
        project_id=project_id,
        now=now,
    )
    _seed_director_message(
        db_session,
        session_id=conversation_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="提醒确认",
        sequence_no=1,
        created_at=now,
        requires_confirmation=True,
    )

    assembly = DirectorContextAssemblerService(db_session).assemble(
        conversation_id=conversation_id,
        route_decision=ConversationRouter.classify("有哪些提醒和待处理？"),
    )
    sections = _sections_by_key(assembly)

    assert sections["inbox_attention"].included is True
    assert sections["dispatch_attention"].included is True
    assert sections["safety_boundary"].included is True
    assert sections["latest_plan"].included is False
    assert sections["latest_plan"].item_count == 0
    assert assembly.has_plan is False


def test_ask_conversation_list_includes_other_conversation_section(
    db_session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    project_id = uuid4()
    conversation_id = _seed_director_session(
        db_session,
        goal_text="当前会话",
        now=now,
        project_id=project_id,
    )
    other_id = _seed_director_session(
        db_session,
        goal_text="另一个主管会话",
        now=now - timedelta(minutes=5),
        project_id=project_id,
    )
    _seed_director_message(
        db_session,
        session_id=other_id,
        role=ProjectDirectorMessageRole.USER,
        content="历史讨论",
        sequence_no=1,
        created_at=now - timedelta(minutes=4),
    )

    assembly = DirectorContextAssemblerService(db_session).assemble(
        conversation_id=conversation_id,
        route_decision=ConversationRouter.classify("我想看已有会话和历史讨论"),
    )
    section = _sections_by_key(assembly)["conversation_list"]

    assert section.included is True
    assert section.item_count == 1
    assert "其他主管会话" in section.label


def test_request_action_assembles_safety_without_side_effects(
    db_session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    project_id = uuid4()
    conversation_id = _seed_director_session(
        db_session,
        goal_text="执行请求",
        now=now,
        project_id=project_id,
    )
    route_decision = ConversationRouter.classify("请启动执行并推送")
    counts_before = _row_counts(db_session)

    assembly = DirectorContextAssemblerService(db_session).assemble(
        conversation_id=conversation_id,
        route_decision=route_decision,
    )
    sections = _sections_by_key(assembly)

    assert sections["safety_boundary"].included is True
    assert route_decision.should_create_conversation is False
    assert route_decision.should_create_task is False
    assert route_decision.should_start_worker is False
    assert route_decision.should_launch_executor is False
    assert route_decision.should_modify_repository is False
    assert _row_counts(db_session) == counts_before


def test_dispatch_attention_uses_dispatch_items_without_executing(
    db_session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    project_id = uuid4()
    conversation_id = _seed_director_session(
        db_session,
        goal_text="调度提醒",
        now=now,
        project_id=project_id,
    )
    task_id = _seed_task(
        db_session,
        project_id=project_id,
        title="调度确认任务",
        status=TaskStatus.RUNNING,
        now=now,
    )
    run_id = _seed_run(
        db_session,
        task_id=task_id,
        status=RunStatus.RUNNING,
        result_summary="运行中",
        now=now,
    )
    _seed_agent_dispatch_message(
        db_session,
        project_id=project_id,
        task_id=task_id,
        run_id=run_id,
        recommended_agent="user",
        dispatch_status="needs_user_decision",
        content_summary="P6 调度建议：等待用户决策。当前状态仅建议，未派发。",
        now=now,
    )
    counts_before = _row_counts(db_session)

    assembly = DirectorContextAssemblerService(db_session).assemble(
        conversation_id=conversation_id,
        route_decision=ConversationRouter.classify("下一步接下来继续做什么？"),
    )
    section = _sections_by_key(assembly)["dispatch_attention"]

    assert section.included is True
    assert section.label == "调度建议提醒"
    assert section.item_count == 1
    assert "调度建议需要关注" in section.summary
    assert "dispatch_question" not in section.summary
    assert _row_counts(db_session) == counts_before


def test_project_mismatch_returns_value_error(db_session: Session) -> None:
    now = datetime.now(timezone.utc)
    conversation_id = _seed_director_session(
        db_session,
        goal_text="项目归属",
        now=now,
        project_id=uuid4(),
    )

    with pytest.raises(ValueError, match="does not match"):
        DirectorContextAssemblerService(db_session).assemble(
            conversation_id=conversation_id,
            project_id=uuid4(),
            route_decision=ConversationRouter.classify("当前状态"),
        )


def test_missing_conversation_returns_not_found(db_session: Session) -> None:
    with pytest.raises(DirectorContextAssemblerNotFoundError):
        DirectorContextAssemblerService(db_session).assemble(
            conversation_id=uuid4(),
            route_decision=ConversationRouter.classify("当前状态"),
        )


def test_recent_message_and_inbox_limits_are_clamped(db_session: Session) -> None:
    now = datetime.now(timezone.utc)
    project_id = uuid4()
    conversation_id = _seed_director_session(
        db_session,
        goal_text="限制测试",
        now=now,
        project_id=project_id,
    )
    for index in range(60):
        _seed_director_message(
            db_session,
            session_id=conversation_id,
            role=ProjectDirectorMessageRole.USER,
            content=f"消息 {index:02d}",
            sequence_no=index + 1,
            created_at=now - timedelta(minutes=120 - index),
        )
    for index in range(105):
        inbox_session_id = _seed_director_session(
            db_session,
            goal_text=f"提醒会话 {index:03d}",
            now=now - timedelta(minutes=index),
            project_id=project_id,
        )
        _seed_director_message(
            db_session,
            session_id=inbox_session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content=f"提醒 {index:03d}",
            sequence_no=1,
            created_at=now - timedelta(minutes=index),
            requires_confirmation=True,
        )

    assembly = DirectorContextAssemblerService(db_session).assemble(
        conversation_id=conversation_id,
        route_decision=ConversationRouter.classify("当前状态和项目情况"),
        recent_message_limit=500,
        inbox_limit=500,
    )

    assert assembly.recent_messages_count == 50
    assert assembly.inbox_attention_count == 100


def test_user_visible_text_avoids_technical_terms_and_falls_back(
    db_session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    conversation_id = _seed_director_session(
        db_session,
        goal_text="文案安全",
        now=now,
    )
    route_decision = RouteDecision(
        intent=ConversationIntent.REQUEST_ACTION,
        confidence=1.0,
        reason="test",
        context_scope=ContextScope(include_safety_boundary=True),
        safety_policy=SafetyPolicy(
            risk_level=SafetyRiskLevel.HIGH,
            requires_confirmation=True,
            forbidden_actions=[],
            safe_next_actions=["推送", "provider action"],
            user_visible_warning="provider API payload",
        ),
    )

    assembly = DirectorContextAssemblerService(db_session).assemble(
        conversation_id=conversation_id,
        route_decision=route_decision,
    )
    user_visible_text = " ".join(
        [
            assembly.summary,
            *[section.label for section in assembly.sections],
            *[section.summary for section in assembly.sections],
            *assembly.forbidden_actions,
            *assembly.safe_next_actions,
        ]
    )

    assert assembly.forbidden_actions == [
        "不会自动执行任务",
        "不会自动创建任务",
        "不会修改仓库",
        "不会启动外部工具",
        "不会直接应用草案修改",
    ]
    assert assembly.safe_next_actions == ["继续提问", "要求解释原因"]
    for term in TECHNICAL_TERMS:
        assert term not in user_visible_text


def _seed_director_session(
    db_session: Session,
    *,
    goal_text: str,
    now: datetime,
    project_id: UUID | None = None,
) -> UUID:
    session_id = uuid4()
    db_session.add(
        ProjectDirectorSessionTable(
            id=session_id,
            project_id=project_id,
            goal_text=goal_text,
            constraints="",
            status=ProjectDirectorSessionStatus.CLARIFYING,
            clarifying_questions_json="[]",
            clarifying_answers_json="[]",
            goal_summary="",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()
    return session_id


def _seed_director_message(
    db_session: Session,
    *,
    session_id: UUID,
    role: ProjectDirectorMessageRole,
    content: str,
    sequence_no: int,
    created_at: datetime,
    requires_confirmation: bool = False,
) -> UUID:
    message_id = uuid4()
    db_session.add(
        ProjectDirectorMessageTable(
            id=message_id,
            session_id=session_id,
            role=role,
            content=content,
            sequence_no=sequence_no,
            source=ProjectDirectorMessageSource.RULE_FALLBACK,
            source_detail="test_seed",
            suggested_actions_json="[]",
            requires_confirmation=requires_confirmation,
            forbidden_actions_detected_json="[]",
            created_at=created_at,
        )
    )
    db_session.commit()
    return message_id


def _seed_plan_version(
    db_session: Session,
    *,
    session_id: UUID,
    now: datetime,
    project_id: UUID | None = None,
    status: PlanVersionStatus = PlanVersionStatus.PENDING_CONFIRMATION,
) -> UUID:
    plan_id = uuid4()
    db_session.add(
        ProjectDirectorPlanVersionTable(
            id=plan_id,
            session_id=session_id,
            project_id=project_id,
            version_no=1,
            status=status,
            plan_summary="待确认的测试草案",
            phases_json="[]",
            proposed_tasks_json="[]",
            acceptance_criteria_json="[]",
            risks_json="[]",
            project_scope_json=json.dumps(
                {"in_scope": [], "out_of_scope": [], "assumptions": []}
            ),
            agent_team_suggestions_json="[]",
            skill_binding_suggestions_json="[]",
            verification_mechanisms_json="[]",
            repository_binding_suggestions_json="[]",
            deliverable_boundaries_json="[]",
            complexity_assessment_json=json.dumps(
                {
                    "level": "low",
                    "label": "低复杂度",
                    "score": 1,
                    "recommended_agent_count": 1,
                    "drivers": [],
                    "mitigation_suggestions": [],
                }
            ),
            source="rule_fallback",
            source_detail="test_seed",
            forbidden_actions_json="[]",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()
    return plan_id


def _seed_task(
    db_session: Session,
    *,
    project_id: UUID,
    title: str,
    status: TaskStatus,
    now: datetime,
) -> UUID:
    task_id = uuid4()
    db_session.add(
        TaskTable(
            id=task_id,
            project_id=project_id,
            title=title,
            status=status,
            priority=TaskPriority.NORMAL,
            input_summary=f"{title} 输入摘要",
            acceptance_criteria="[]",
            depends_on_task_ids="[]",
            risk_level=TaskRiskLevel.NORMAL,
            human_status=TaskHumanStatus.NONE,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()
    return task_id


def _seed_run(
    db_session: Session,
    *,
    task_id: UUID,
    status: RunStatus,
    result_summary: str,
    now: datetime,
) -> UUID:
    run_id = uuid4()
    db_session.add(
        RunTable(
            id=run_id,
            task_id=task_id,
            status=status,
            result_summary=result_summary,
            created_at=now,
            finished_at=now if status != RunStatus.RUNNING else None,
        )
    )
    db_session.commit()
    return run_id


def _seed_agent_dispatch_message(
    db_session: Session,
    *,
    project_id: UUID,
    task_id: UUID,
    run_id: UUID,
    recommended_agent: str,
    dispatch_status: str,
    content_summary: str,
    now: datetime,
) -> UUID:
    detail = {
        "p6_stage": "P6-D",
        "event_type": P6_AGENT_DISPATCH_DECISION_AUDIT_EVENT_TYPE,
        "decision": {
            "recommended_agent": recommended_agent,
            "dispatch_status": dispatch_status,
            "instruction_draft": "请主管确认下一步调度建议；本记录不会自动派发。",
            "dispatch_reason_cn": "基于失败回流生成的调度建议。",
        },
        "p6_d_safety": {
            "worker_dispatch_triggered": False,
            "retry_triggered": False,
            "task_created": False,
            "git_push_triggered": False,
        },
    }
    message_id = uuid4()
    db_session.add(
        AgentMessageTable(
            id=message_id,
            session_id=uuid4(),
            project_id=project_id,
            task_id=task_id,
            run_id=run_id,
            sequence_no=1,
            role=AgentMessageRole.SYSTEM,
            message_type=AgentMessageType.TIMELINE,
            event_type=P6_AGENT_DISPATCH_DECISION_AUDIT_EVENT_TYPE,
            phase="executing",
            state_from="failed",
            state_to=dispatch_status,
            content_summary=content_summary,
            content_detail=json.dumps(detail, ensure_ascii=False),
            created_at=now,
        )
    )
    db_session.commit()
    return message_id


def _sections_by_key(assembly) -> dict[str, object]:
    return {section.key: section for section in assembly.sections}


def _row_counts(db_session: Session) -> dict[str, int]:
    return {
        "sessions": _count_rows(db_session, ProjectDirectorSessionTable),
        "messages": _count_rows(db_session, ProjectDirectorMessageTable),
        "plans": _count_rows(db_session, ProjectDirectorPlanVersionTable),
        "tasks": _count_rows(db_session, TaskTable),
        "runs": _count_rows(db_session, RunTable),
        "agent_messages": _count_rows(db_session, AgentMessageTable),
    }


def _count_rows(db_session: Session, table) -> int:
    return db_session.execute(select(func.count()).select_from(table)).scalar_one()
