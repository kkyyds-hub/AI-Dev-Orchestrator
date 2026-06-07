"""P7-D1 synthetic Project Director Inbox read-only API tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.router import api_router
from app.core.db import get_db_session
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
from app.domain.project_director_message import (
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_plan_version import PlanVersionStatus
from app.domain.project_director_session import ProjectDirectorSessionStatus
from app.domain.run import RunStatus
from app.domain.task import TaskHumanStatus, TaskPriority, TaskRiskLevel, TaskStatus


def _sqlite_session_factory(tmp_path):
    db_path = tmp_path / "orchestrator-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


def _client(sqlite_session_factory):
    app = FastAPI()
    app.include_router(api_router)

    def override_get_db_session():
        session = sqlite_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session
    return app


def test_inbox_returns_item_for_latest_assistant_requires_confirmation(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _client(session_factory)
    db_session = session_factory()
    now = datetime.now(timezone.utc)
    session_id = _seed_director_session(db_session, goal_text="需要确认的会话", now=now)
    _seed_director_message(
        db_session,
        session_id=session_id,
        role=ProjectDirectorMessageRole.USER,
        content="先问一个问题",
        sequence_no=1,
        created_at=now - timedelta(minutes=5),
    )
    message_id = _seed_director_message(
        db_session,
        session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="请确认是否按这个计划继续？",
        sequence_no=2,
        created_at=now,
        requires_confirmation=True,
    )

    with TestClient(app) as client:
        resp = client.get("/project-director/inbox")

    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "synthetic_project_director_inbox_read_model"
    assert data["has_more"] is False
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["kind"] == "plan_question"
    assert item["status"] == "needs_response"
    assert item["priority"] == "normal"
    assert item["requires_user_action"] is True
    assert item["conversation_id"] == str(session_id)
    assert item["session_id"] == str(session_id)
    assert item["related_message_id"] == str(message_id)
    assert item["source_entity_type"] == "message"

    db_session.close()


def test_inbox_pending_plan_version_creates_approval_attention(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _client(session_factory)
    db_session = session_factory()
    now = datetime.now(timezone.utc)
    session_id = _seed_director_session(db_session, goal_text="待审核计划", now=now)
    plan_id = _seed_plan_version(
        db_session,
        session_id=session_id,
        status=PlanVersionStatus.PENDING_CONFIRMATION,
        now=now,
    )

    with TestClient(app) as client:
        resp = client.get("/project-director/inbox")

    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["kind"] == "approval_attention"
    assert item["status"] == "needs_response"
    assert item["priority"] == "high"
    assert item["conversation_id"] == str(session_id)
    assert item["related_plan_version_id"] == str(plan_id)
    assert item["source_entity_type"] == "plan_version"

    db_session.close()


def test_inbox_project_id_filter_only_returns_matching_items(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _client(session_factory)
    db_session = session_factory()
    now = datetime.now(timezone.utc)
    project_id = uuid4()
    other_project_id = uuid4()
    matching_session_id = _seed_director_session(
        db_session,
        goal_text="匹配项目",
        now=now,
        project_id=project_id,
    )
    other_session_id = _seed_director_session(
        db_session,
        goal_text="其他项目",
        now=now,
        project_id=other_project_id,
    )
    _seed_director_message(
        db_session,
        session_id=matching_session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="匹配项目需要确认",
        sequence_no=1,
        created_at=now,
        requires_confirmation=True,
    )
    _seed_director_message(
        db_session,
        session_id=other_session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="其他项目需要确认",
        sequence_no=1,
        created_at=now,
        requires_confirmation=True,
    )

    with TestClient(app) as client:
        resp = client.get(f"/project-director/inbox?project_id={project_id}")

    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["project_id"] == str(project_id)
    assert items[0]["session_id"] == str(matching_session_id)

    db_session.close()


def test_inbox_kind_status_priority_filters_work(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _client(session_factory)
    db_session = session_factory()
    now = datetime.now(timezone.utc)
    session_id = _seed_director_session(db_session, goal_text="过滤测试", now=now)
    _seed_director_message(
        db_session,
        session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="normal plan question",
        sequence_no=1,
        created_at=now,
        requires_confirmation=True,
    )
    _seed_plan_version(
        db_session,
        session_id=session_id,
        status=PlanVersionStatus.PENDING_CONFIRMATION,
        now=now,
    )

    with TestClient(app) as client:
        resp = client.get(
            "/project-director/inbox?kind=approval_attention&status=needs_response&priority=high"
        )

    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["kind"] == "approval_attention"
    assert items[0]["status"] == "needs_response"
    assert items[0]["priority"] == "high"

    db_session.close()


def test_inbox_limit_is_capped_at_100(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _client(session_factory)
    db_session = session_factory()
    now = datetime.now(timezone.utc)
    for index in range(105):
        session_id = _seed_director_session(
            db_session,
            goal_text=f"批量会话 {index}",
            now=now - timedelta(minutes=index),
        )
        _seed_director_message(
            db_session,
            session_id=session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content=f"需要确认 {index}",
            sequence_no=1,
            created_at=now - timedelta(minutes=index),
            requires_confirmation=True,
        )

    with TestClient(app) as client:
        resp = client.get("/project-director/inbox?limit=500")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 100
    assert data["has_more"] is True

    db_session.close()


def test_inbox_read_api_does_not_create_session_message_task_or_run(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _client(session_factory)
    db_session = session_factory()
    now = datetime.now(timezone.utc)
    session_id = _seed_director_session(db_session, goal_text="只读测试", now=now)
    _seed_director_message(
        db_session,
        session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="需要确认",
        sequence_no=1,
        created_at=now,
        requires_confirmation=True,
    )
    counts_before = {
        "sessions": _count_rows(db_session, ProjectDirectorSessionTable),
        "messages": _count_rows(db_session, ProjectDirectorMessageTable),
        "tasks": _count_rows(db_session, TaskTable),
        "runs": _count_rows(db_session, RunTable),
        "agent_messages": _count_rows(db_session, AgentMessageTable),
    }

    with TestClient(app) as client:
        resp = client.get("/project-director/inbox")

    assert resp.status_code == 200
    assert {
        "sessions": _count_rows(db_session, ProjectDirectorSessionTable),
        "messages": _count_rows(db_session, ProjectDirectorMessageTable),
        "tasks": _count_rows(db_session, TaskTable),
        "runs": _count_rows(db_session, RunTable),
        "agent_messages": _count_rows(db_session, AgentMessageTable),
    } == counts_before

    db_session.close()


def test_inbox_task_and_run_blocker_sources(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _client(session_factory)
    db_session = session_factory()
    now = datetime.now(timezone.utc)
    project_id = uuid4()
    blocked_task_id = _seed_task(
        db_session,
        project_id=project_id,
        title="阻塞任务",
        status=TaskStatus.BLOCKED,
        now=now - timedelta(minutes=5),
    )
    failed_task_id = _seed_task(
        db_session,
        project_id=project_id,
        title="失败任务",
        status=TaskStatus.FAILED,
        now=now - timedelta(minutes=4),
    )
    failed_run_id = _seed_run(
        db_session,
        task_id=failed_task_id,
        status=RunStatus.FAILED,
        result_summary="运行失败，需要失败回流",
        now=now,
    )

    with TestClient(app) as client:
        resp = client.get(f"/project-director/inbox?project_id={project_id}")

    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(
        item["kind"] == "run_blocker"
        and item["related_task_id"] == str(blocked_task_id)
        for item in items
    )
    assert any(
        item["kind"] == "failure_recovery_attention"
        and item["related_task_id"] == str(failed_task_id)
        for item in items
    )
    assert any(
        item["kind"] == "failure_recovery_attention"
        and item["related_run_id"] == str(failed_run_id)
        for item in items
    )

    db_session.close()


def test_inbox_dispatch_agent_message_creates_dispatch_question_item(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _client(session_factory)
    db_session = session_factory()
    now = datetime.now(timezone.utc)
    project_id = uuid4()
    task_id = _seed_task(
        db_session,
        project_id=project_id,
        title="需要调度确认的任务",
        status=TaskStatus.RUNNING,
        now=now - timedelta(minutes=2),
    )
    run_id = _seed_run(
        db_session,
        task_id=task_id,
        status=RunStatus.CANCELLED,
        result_summary="运行取消，生成调度建议",
        now=now - timedelta(minutes=1),
    )
    agent_message_id = _seed_agent_dispatch_message(
        db_session,
        project_id=project_id,
        task_id=task_id,
        run_id=run_id,
        recommended_agent="user",
        dispatch_status="needs_user_decision",
        content_summary="P6 调度建议：等待用户决策。当前状态仅建议，未派发。",
        now=now,
    )

    with TestClient(app) as client:
        resp = client.get(f"/project-director/inbox?project_id={project_id}")

    assert resp.status_code == 200
    items = resp.json()["items"]
    dispatch_items = [item for item in items if item["kind"] == "dispatch_question"]
    assert len(dispatch_items) == 1
    item = dispatch_items[0]
    assert item["status"] == "needs_response"
    assert item["priority"] == "high"
    assert item["requires_user_action"] is True
    assert item["source_page"] == "worker_timeline"
    assert item["source_entity_type"] == "agent_message"
    assert item["source_entity_id"] == str(agent_message_id)
    assert item["related_task_id"] == str(task_id)
    assert item["related_run_id"] == str(run_id)
    assert item["project_id"] == str(project_id)
    assert "P6 调度建议" in item["summary"]

    db_session.close()


def test_inbox_dispatch_question_kind_filter_works(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _client(session_factory)
    db_session = session_factory()
    now = datetime.now(timezone.utc)
    project_id = uuid4()
    session_id = _seed_director_session(
        db_session,
        goal_text="同时存在普通主管问题",
        now=now,
        project_id=project_id,
    )
    _seed_director_message(
        db_session,
        session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="普通计划问题",
        sequence_no=1,
        created_at=now,
        requires_confirmation=True,
    )
    task_id = _seed_task(
        db_session,
        project_id=project_id,
        title="调度问题过滤",
        status=TaskStatus.RUNNING,
        now=now,
    )
    run_id = _seed_run(
        db_session,
        task_id=task_id,
        status=RunStatus.FAILED,
        result_summary="失败后调度建议",
        now=now,
    )
    _seed_agent_dispatch_message(
        db_session,
        project_id=project_id,
        task_id=task_id,
        run_id=run_id,
        recommended_agent="codex",
        dispatch_status="suggested",
        content_summary="P6 调度建议：Codex 继续处理。当前状态仅建议，未派发。",
        now=now + timedelta(minutes=1),
    )

    with TestClient(app) as client:
        resp = client.get(
            f"/project-director/inbox?project_id={project_id}&kind=dispatch_question"
        )

    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["kind"] == "dispatch_question"
    assert items[0]["priority"] == "normal"
    assert items[0]["requires_user_action"] is False

    db_session.close()


def test_inbox_read_api_does_not_create_agent_message_for_dispatch_source(
    tmp_path,
) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _client(session_factory)
    db_session = session_factory()
    now = datetime.now(timezone.utc)
    project_id = uuid4()
    task_id = _seed_task(
        db_session,
        project_id=project_id,
        title="只读 dispatch source",
        status=TaskStatus.RUNNING,
        now=now,
    )
    run_id = _seed_run(
        db_session,
        task_id=task_id,
        status=RunStatus.CANCELLED,
        result_summary="调度只读",
        now=now,
    )
    _seed_agent_dispatch_message(
        db_session,
        project_id=project_id,
        task_id=task_id,
        run_id=run_id,
        recommended_agent="blocked",
        dispatch_status="blocked",
        content_summary="P6 调度建议：当前不可调度。当前状态仅建议，未派发。",
        now=now,
    )
    counts_before = {
        "sessions": _count_rows(db_session, ProjectDirectorSessionTable),
        "messages": _count_rows(db_session, ProjectDirectorMessageTable),
        "tasks": _count_rows(db_session, TaskTable),
        "runs": _count_rows(db_session, RunTable),
        "agent_messages": _count_rows(db_session, AgentMessageTable),
    }

    with TestClient(app) as client:
        resp = client.get(f"/project-director/inbox?project_id={project_id}")

    assert resp.status_code == 200
    assert {
        "sessions": _count_rows(db_session, ProjectDirectorSessionTable),
        "messages": _count_rows(db_session, ProjectDirectorMessageTable),
        "tasks": _count_rows(db_session, TaskTable),
        "runs": _count_rows(db_session, RunTable),
        "agent_messages": _count_rows(db_session, AgentMessageTable),
    } == counts_before
    dispatch_item = next(
        item for item in resp.json()["items"] if item["kind"] == "dispatch_question"
    )
    assert dispatch_item["priority"] == "critical"
    assert dispatch_item["requires_user_action"] is True

    db_session.close()


def test_inbox_ignores_malformed_non_p6_agent_message_detail(tmp_path) -> None:
    session_factory = _sqlite_session_factory(tmp_path)
    app = _client(session_factory)
    db_session = session_factory()
    now = datetime.now(timezone.utc)
    project_id = uuid4()
    task_id = _seed_task(
        db_session,
        project_id=project_id,
        title="非 P6 消息",
        status=TaskStatus.RUNNING,
        now=now,
    )
    run_id = _seed_run(
        db_session,
        task_id=task_id,
        status=RunStatus.RUNNING,
        result_summary="仍在运行",
        now=now,
    )
    _seed_agent_message(
        db_session,
        project_id=project_id,
        task_id=task_id,
        run_id=run_id,
        event_type="worker_progress",
        content_summary="普通 worker timeline，不是调度建议。",
        content_detail="{not-json",
        now=now,
    )

    with TestClient(app) as client:
        resp = client.get(
            f"/project-director/inbox?project_id={project_id}&kind=dispatch_question"
        )

    assert resp.status_code == 200
    assert resp.json()["items"] == []

    db_session.close()


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
    status: PlanVersionStatus,
    now: datetime,
    project_id: UUID | None = None,
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
            finished_at=now,
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
    return _seed_agent_message(
        db_session,
        project_id=project_id,
        task_id=task_id,
        run_id=run_id,
        event_type=P6_AGENT_DISPATCH_DECISION_AUDIT_EVENT_TYPE,
        content_summary=content_summary,
        content_detail=json.dumps(detail, ensure_ascii=False),
        now=now,
        state_to=dispatch_status,
    )


def _seed_agent_message(
    db_session: Session,
    *,
    project_id: UUID,
    task_id: UUID,
    run_id: UUID,
    event_type: str,
    content_summary: str,
    content_detail: str,
    now: datetime,
    state_to: str | None = None,
) -> UUID:
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
            event_type=event_type,
            phase="executing",
            state_from="failed",
            state_to=state_to,
            content_summary=content_summary,
            content_detail=content_detail,
            created_at=now,
        )
    )
    db_session.commit()
    return message_id


def _count_rows(db_session: Session, table) -> int:
    return db_session.execute(select(func.count()).select_from(table)).scalar_one()
