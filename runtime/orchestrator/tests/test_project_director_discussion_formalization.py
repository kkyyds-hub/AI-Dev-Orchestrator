"""Tests for P26-G1-A discussion formalization gate — end to end.

Covers domain validation, ORM schema, migration, repository, workspace/event
provenance, history/projection gates, formalization gates, success transactions,
idempotency, plan review lifecycle, and API contract.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.api.router import api_router
from app.api.routes.project_director import (
    _get_discussion_formalization_service,
    _get_plan_service,
    _get_service,
)
from app.core.db import (
    begin_sqlite_transaction,
    configure_sqlite,
    get_db_session,
    migrate_database_schema,
)
from app.core.db_tables import (
    AgentSessionTable,
    ORMBase,
    ProjectDirectorDiscussionEventTable,
    ProjectDirectorDiscussionWorkspaceTable,
    ProjectDirectorMessageTable,
    ProjectDirectorPlanVersionTable,
    ProjectDirectorSessionTable,
    ProjectTable,
    RunTable,
    TaskTable,
)
from app.domain.project_director_conversation_intelligence import FormalizationTarget
from app.domain.project_director_discussion import (
    DiscussionActorClaim,
    DiscussionEvent,
    DiscussionEventStatus,
    DiscussionEventType,
    DiscussionStatus,
    DiscussionWorkspace,
)
from app.domain.project_director_message import (
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_plan_version import (
    PlanVersionStatus,
    ProjectDirectorPlanVersion,
)
from app.domain.project_director_session import ProjectDirectorSessionStatus
from app.domain.project_role import ProjectRoleCode
from app.repositories.project_director_discussion_event_repository import (
    ProjectDirectorDiscussionEventRepository,
)
from app.repositories.project_director_discussion_workspace_repository import (
    ProjectDirectorDiscussionWorkspaceRepository,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.services.project_director_discussion_formalization_service import (
    ProjectDirectorDiscussionFormalizationService,
)
from app.services.project_director_plan_service import ProjectDirectorPlanService
from app.services.project_director_service import ProjectDirectorService
from app.services.provider_config_service import OpenAIProviderRuntimeConfig


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SESSION_ID = UUID("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
PROJECT_ID = UUID("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
FIXED_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeProviderConfigService:
    """可控的 Provider 配置服务。"""

    def __init__(self, *, configured: bool, model: str = "test-plan-model") -> None:
        self.configured = configured
        self._model = model
        self.resolve_calls = 0

    def resolve_openai_runtime_config(self):
        self.resolve_calls += 1
        return SimpleNamespace(
            api_key="test-provider-key" if self.configured else None,
            base_url="https://provider.invalid/v1",
            timeout_seconds=1,
            detected_provider_type="openai_compatible",
            model_names={"balanced": self._model},
        )


class _ProviderSpy:
    """记录 provider 调用并返回受控结果。"""

    def __init__(self, response: str | None = None) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self._response = response or _default_plan_payload()

    def __call__(self, model_name: str, prompt: str, request_id: str = "") -> tuple[str, str]:
        self.calls.append((model_name, prompt, request_id))
        return self._response, "test-receipt-id"


def _default_plan_payload() -> str:
    return json.dumps(
        {
            "plan_summary": "测试计划摘要",
            "phases": [
                {"sequence": 1, "name": "阶段1", "goal": "目标1", "task_count_hint": 1}
            ],
            "proposed_tasks": [
                {
                    "title": "任务1",
                    "description": "描述",
                    "suggested_role_code": ProjectRoleCode.ENGINEER.value,
                    "priority_hint": "normal",
                }
            ],
            "acceptance_criteria": ["标准1"],
            "risks": ["风险1"],
            "project_scope": {
                "in_scope": ["范围1"],
                "out_of_scope": [],
                "assumptions": [],
            },
            "agent_team_suggestions": [],
            "skill_binding_suggestions": [],
            "verification_mechanisms": [],
            "repository_binding_suggestions": [],
            "deliverable_boundaries": [],
            "complexity_assessment": {
                "level": "medium",
                "label": "中等",
                "score": 2,
                "recommended_agent_count": 2,
                "drivers": [],
                "mitigation_suggestions": [],
            },
        },
        ensure_ascii=False,
    )


def _seed_project(db_session: Session, *, project_id=PROJECT_ID):
    """Insert a project row if it doesn't exist (needed for FK constraints)."""
    existing = db_session.get(ProjectTable, project_id)
    if existing is not None:
        return
    row = ProjectTable(
        id=project_id,
        name="测试项目",
        summary="测试项目摘要",
        status="active",
        stage="planning",
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )
    db_session.add(row)
    db_session.flush()


def _seed_session(db_session: Session, *, session_id=SESSION_ID, project_id=PROJECT_ID):
    """Insert a CONFIRMED session row directly. Idempotent."""
    existing = db_session.get(ProjectDirectorSessionTable, session_id)
    if existing is not None:
        return existing
    _seed_project(db_session, project_id=project_id)
    row = ProjectDirectorSessionTable(
        id=session_id,
        project_id=project_id,
        goal_text="测试目标：构建一个系统",
        constraints="",
        status=ProjectDirectorSessionStatus.CONFIRMED,
        clarifying_questions_json="[]",
        clarifying_answers_json="[]",
        goal_summary="测试目标摘要",
        confirmed_at=FIXED_TIME,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _seed_message(
    db_session: Session,
    session_id: UUID = SESSION_ID,
    *,
    message_id: UUID | None = None,
    content: str = "用户消息",
    sequence_no: int = 1,
) -> UUID:
    """Insert a USER message row and return its ID. Ensures session exists first."""
    # Ensure the session row exists (FK dependency)
    if db_session.get(ProjectDirectorSessionTable, session_id) is None:
        _seed_session(db_session, session_id=session_id)
    mid = message_id or uuid4()
    row = ProjectDirectorMessageTable(
        id=mid,
        session_id=session_id,
        role=ProjectDirectorMessageRole.USER,
        content=content,
        sequence_no=sequence_no,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail="test",
        created_at=FIXED_TIME,
    )
    db_session.add(row)
    db_session.flush()
    return mid


def _make_event(
    session_id: UUID = SESSION_ID,
    *,
    project_id=PROJECT_ID,
    sequence_no: int = 1,
    event_type: DiscussionEventType = DiscussionEventType.TOPIC_SET,
    content: str = "测试主题",
    subject_key: str = "topic",
    status: DiscussionEventStatus = DiscussionEventStatus.ACTIVE,
    source_message_ids: list[UUID] | None = None,
    payload: dict | None = None,
    supersedes_event_id: UUID | None = None,
    created_by: DiscussionActorClaim = DiscussionActorClaim.USER_EXPLICIT,
    confidence: float = 1.0,
    event_id: UUID | None = None,
) -> DiscussionEvent:
    return DiscussionEvent(
        id=event_id or uuid4(),
        session_id=session_id,
        project_id=project_id,
        sequence_no=sequence_no,
        event_type=event_type,
        subject_key=subject_key,
        content=content,
        status=status,
        payload=payload or {},
        source_message_ids=source_message_ids or [],
        supersedes_event_id=supersedes_event_id,
        created_by=created_by,
        confidence=confidence,
        created_at=FIXED_TIME,
    )


def _make_workspace(
    session_id: UUID = SESSION_ID,
    *,
    project_id=PROJECT_ID,
    topic: str = "测试主题",
    discussion_status: DiscussionStatus = DiscussionStatus.EXPLORING,
    active_option_ids: list[UUID] | None = None,
    preferred_option_id: UUID | None = None,
    active_constraint_ids: list[UUID] | None = None,
    open_question_ids: list[UUID] | None = None,
    temporary_conclusion_ids: list[UUID] | None = None,
    confirmed_decision_ids: list[UUID] | None = None,
    latest_user_correction_event_id: UUID | None = None,
    version_no: int = 1,
    last_event_sequence_no: int = 1,
) -> DiscussionWorkspace:
    now = datetime.now(timezone.utc)
    return DiscussionWorkspace(
        session_id=session_id,
        project_id=project_id,
        topic=topic,
        discussion_status=discussion_status,
        active_option_ids=active_option_ids or [],
        preferred_option_id=preferred_option_id,
        active_constraint_ids=active_constraint_ids or [],
        open_question_ids=open_question_ids or [],
        temporary_conclusion_ids=temporary_conclusion_ids or [],
        confirmed_decision_ids=confirmed_decision_ids or [],
        latest_user_correction_event_id=latest_user_correction_event_id,
        version_no=version_no,
        last_event_sequence_no=last_event_sequence_no,
        created_at=now,
        updated_at=now,
    )


def _persist_event(db_session: Session, event_obj: DiscussionEvent):
    """Insert a DiscussionEvent row directly."""
    row = ProjectDirectorDiscussionEventTable(
        id=event_obj.id,
        session_id=event_obj.session_id,
        project_id=event_obj.project_id,
        sequence_no=event_obj.sequence_no,
        event_type=event_obj.event_type,
        subject_key=event_obj.subject_key,
        content=event_obj.content,
        status=event_obj.status,
        payload_json=json.dumps(event_obj.payload, default=str),
        source_message_ids_json=json.dumps(
            [str(mid) for mid in event_obj.source_message_ids]
        ),
        supersedes_event_id=event_obj.supersedes_event_id,
        created_by=event_obj.created_by,
        confidence=event_obj.confidence,
        idempotency_key=f"test-{event_obj.id}",
        created_at=event_obj.created_at,
    )
    db_session.add(row)
    db_session.flush()


def _persist_workspace(db_session: Session, ws: DiscussionWorkspace):
    """Insert or update a workspace row."""
    state = {
        "active_option_ids": [str(i) for i in ws.active_option_ids],
        "preferred_option_id": (
            str(ws.preferred_option_id) if ws.preferred_option_id else None
        ),
        "active_constraint_ids": [str(i) for i in ws.active_constraint_ids],
        "open_question_ids": [str(i) for i in ws.open_question_ids],
        "temporary_conclusion_ids": [str(i) for i in ws.temporary_conclusion_ids],
        "confirmed_decision_ids": [str(i) for i in ws.confirmed_decision_ids],
        "latest_user_correction_event_id": (
            str(ws.latest_user_correction_event_id)
            if ws.latest_user_correction_event_id
            else None
        ),
    }
    existing = db_session.get(
        ProjectDirectorDiscussionWorkspaceTable, ws.session_id
    )
    if existing is not None:
        existing.topic = ws.topic
        existing.discussion_status = ws.discussion_status
        existing.state_json = json.dumps(state)
        existing.version_no = ws.version_no
        existing.last_event_sequence_no = ws.last_event_sequence_no
        existing.updated_at = ws.updated_at
    else:
        row = ProjectDirectorDiscussionWorkspaceTable(
            session_id=ws.session_id,
            project_id=ws.project_id,
            topic=ws.topic,
            discussion_status=ws.discussion_status,
            state_json=json.dumps(state),
            version_no=ws.version_no,
            last_event_sequence_no=ws.last_event_sequence_no,
            created_at=ws.created_at,
            updated_at=ws.updated_at,
        )
        db_session.add(row)
    db_session.flush()


def _build_formalization_service(
    db_session: Session,
    *,
    provider_configured: bool = False,
    provider_text_generator=None,
) -> ProjectDirectorDiscussionFormalizationService:
    """Build a formalization service with real repositories on the given session."""
    session_repo = ProjectDirectorSessionRepository(db_session)
    workspace_repo = ProjectDirectorDiscussionWorkspaceRepository(db_session)
    event_repo = ProjectDirectorDiscussionEventRepository(db_session)
    message_repo = ProjectDirectorMessageRepository(db_session)
    plan_version_repo = ProjectDirectorPlanVersionRepository(db_session)
    provider_config = _FakeProviderConfigService(configured=provider_configured)
    plan_service = ProjectDirectorPlanService(
        plan_version_repository=plan_version_repo,
        session_repository=session_repo,
        provider_config_service=provider_config,
        provider_text_generator=provider_text_generator,
    )
    return ProjectDirectorDiscussionFormalizationService(
        session_repository=session_repo,
        discussion_workspace_repository=workspace_repo,
        discussion_event_repository=event_repo,
        message_repository=message_repo,
        plan_version_repository=plan_version_repo,
        plan_service=plan_service,
    )


def _count_plan_versions(db_session: Session) -> int:
    return db_session.execute(
        select(func.count()).select_from(ProjectDirectorPlanVersionTable)
    ).scalar_one()


def _count_agent_sessions(session: Session) -> int:
    return session.execute(
        select(func.count()).select_from(AgentSessionTable)
    ).scalar_one()


def _count_table(session: Session, table) -> int:
    return session.execute(select(func.count()).select_from(table)).scalar_one()


class SessionTransactionSpy:
    """Instance-scoped commit/rollback spy — only wraps the given session instance."""

    def __init__(self, session: Session):
        self._session = session
        self.commit_count = 0
        self.rollback_count = 0
        self._original_commit = session.commit
        self._original_rollback = session.rollback

    def _spy_commit(self):
        self.commit_count += 1
        return self._original_commit()

    def _spy_rollback(self):
        self.rollback_count += 1
        return self._original_rollback()

    def __enter__(self):
        self._session.commit = self._spy_commit
        self._session.rollback = self._spy_rollback
        return self

    def __exit__(self, *args):
        self._session.commit = self._original_commit
        self._session.rollback = self._original_rollback


def _rebuild_and_persist_workspace(
    db_session: Session,
    events: list[DiscussionEvent],
    *,
    session_id=SESSION_ID,
    project_id=PROJECT_ID,
    version_no: int = 1,
):
    """Use the reducer to build a workspace from events, then persist it."""
    from app.services.project_director_discussion_workspace_reducer_service import (
        ProjectDirectorDiscussionWorkspaceReducerService,
    )
    reducer = ProjectDirectorDiscussionWorkspaceReducerService()
    ws = reducer.rebuild_workspace(
        session_id=session_id,
        project_id=project_id,
        events=tuple(events),
        version_no=version_no,
    )
    _persist_workspace(db_session, ws)
    return ws


def _seed_ready_to_formalize(
    db_session: Session,
    *,
    session_id=SESSION_ID,
    project_id=PROJECT_ID,
    topic: str = "测试主题",
    workspace_version: int = 1,
    last_sequence: int = 1,
):
    """Seed a complete ready-to-formalize scenario: session, message, event, workspace."""
    _seed_session(db_session, session_id=session_id, project_id=project_id)
    msg_id = _seed_message(db_session, session_id=session_id)
    evt = _make_event(
        session_id=session_id,
        project_id=project_id,
        sequence_no=1,
        event_type=DiscussionEventType.TOPIC_SET,
        content=topic,
        source_message_ids=[msg_id],
    )
    _persist_event(db_session, evt)
    ws = _make_workspace(
        session_id=session_id,
        project_id=project_id,
        topic=topic,
        discussion_status=DiscussionStatus.EXPLORING,
        version_no=workspace_version,
        last_event_sequence_no=last_sequence,
    )
    _persist_workspace(db_session, ws)
    return msg_id, evt


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_engine(tmp_path):
    db_path = tmp_path / "p26g-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    event.listen(engine, "connect", configure_sqlite)
    event.listen(engine, "begin", begin_sqlite_transaction)
    ORMBase.metadata.create_all(bind=engine)
    return engine


@pytest.fixture()
def db_session(db_engine):
    session = sessionmaker(
        bind=db_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def db_session_factory(db_engine):
    return sessionmaker(
        bind=db_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


@pytest.fixture()
def client(db_engine):
    app = FastAPI()
    app.include_router(api_router)

    factory = sessionmaker(
        bind=db_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    def override_get_db_session():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ===========================================================================
# §5 Domain & Schema
# ===========================================================================


class TestDomainFormalizationProvenance:
    """§5.1 PlanVersion formalization provenance all-or-none."""

    def test_plain_plan_version_no_provenance(self):
        pv = ProjectDirectorPlanVersion(
            session_id=uuid4(),
            version_no=1,
            plan_summary="test",
        )
        assert pv.formalization_target is None
        assert pv.formalization_workspace_version is None
        assert pv.formalization_source_message_ids == []
        assert pv.formalization_source_event_ids == []

    def test_formalized_plan_version_requires_all_fields(self):
        pv = ProjectDirectorPlanVersion(
            session_id=uuid4(),
            version_no=1,
            plan_summary="test",
            formalization_target=FormalizationTarget.PLAN_REVISION,
            formalization_workspace_version=1,
            formalization_source_message_ids=[uuid4()],
            formalization_source_event_ids=[uuid4()],
        )
        assert pv.formalization_target == FormalizationTarget.PLAN_REVISION

    def test_target_only_fails(self):
        with pytest.raises(ValueError, match="workspace version|source messages|source events"):
            ProjectDirectorPlanVersion(
                session_id=uuid4(),
                version_no=1,
                plan_summary="test",
                formalization_target=FormalizationTarget.PLAN_REVISION,
            )

    def test_workspace_version_only_fails(self):
        with pytest.raises(ValueError, match="Non-formalized|provenance"):
            ProjectDirectorPlanVersion(
                session_id=uuid4(),
                version_no=1,
                plan_summary="test",
                formalization_workspace_version=1,
            )

    def test_message_ids_only_fails(self):
        with pytest.raises(ValueError, match="Non-formalized|provenance"):
            ProjectDirectorPlanVersion(
                session_id=uuid4(),
                version_no=1,
                plan_summary="test",
                formalization_source_message_ids=[uuid4()],
            )

    def test_event_ids_only_fails(self):
        with pytest.raises(ValueError, match="Non-formalized|provenance"):
            ProjectDirectorPlanVersion(
                session_id=uuid4(),
                version_no=1,
                plan_summary="test",
                formalization_source_event_ids=[uuid4()],
            )

    def test_workspace_version_zero_fails(self):
        with pytest.raises(ValueError, match="at least 1"):
            ProjectDirectorPlanVersion(
                session_id=uuid4(),
                version_no=1,
                plan_summary="test",
                formalization_target=FormalizationTarget.PLAN_REVISION,
                formalization_workspace_version=0,
                formalization_source_message_ids=[uuid4()],
                formalization_source_event_ids=[uuid4()],
            )

    def test_empty_message_ids_fails(self):
        with pytest.raises(ValueError, match="source messages"):
            ProjectDirectorPlanVersion(
                session_id=uuid4(),
                version_no=1,
                plan_summary="test",
                formalization_target=FormalizationTarget.PLAN_REVISION,
                formalization_workspace_version=1,
                formalization_source_message_ids=[],
                formalization_source_event_ids=[uuid4()],
            )

    def test_empty_event_ids_fails(self):
        with pytest.raises(ValueError, match="source events"):
            ProjectDirectorPlanVersion(
                session_id=uuid4(),
                version_no=1,
                plan_summary="test",
                formalization_target=FormalizationTarget.PLAN_REVISION,
                formalization_workspace_version=1,
                formalization_source_message_ids=[uuid4()],
                formalization_source_event_ids=[],
            )

    def test_duplicate_message_ids_fails(self):
        mid = uuid4()
        with pytest.raises(ValueError, match="[Dd]uplicate"):
            ProjectDirectorPlanVersion(
                session_id=uuid4(),
                version_no=1,
                plan_summary="test",
                formalization_target=FormalizationTarget.PLAN_REVISION,
                formalization_workspace_version=1,
                formalization_source_message_ids=[mid, mid],
                formalization_source_event_ids=[uuid4()],
            )

    def test_duplicate_event_ids_fails(self):
        eid = uuid4()
        with pytest.raises(ValueError, match="[Dd]uplicate"):
            ProjectDirectorPlanVersion(
                session_id=uuid4(),
                version_no=1,
                plan_summary="test",
                formalization_target=FormalizationTarget.PLAN_REVISION,
                formalization_workspace_version=1,
                formalization_source_message_ids=[uuid4()],
                formalization_source_event_ids=[eid, eid],
            )


# ===========================================================================
# §5.2 ORM & unique index
# ===========================================================================


class TestOrmSchema:
    """§5.2 Verify ORM table columns and unique index exist."""

    def test_formalization_columns_exist(self, db_engine):
        inspector = inspect(db_engine)
        columns = {
            col["name"]
            for col in inspector.get_columns("project_director_plan_versions")
        }
        assert "formalization_target" in columns
        assert "formalization_workspace_version" in columns
        assert "formalization_source_message_ids_json" in columns
        assert "formalization_source_event_ids_json" in columns

    def test_unique_index_exists(self, db_engine):
        inspector = inspect(db_engine)
        indexes = inspector.get_indexes("project_director_plan_versions")
        idx_names = {idx["name"] for idx in indexes}
        assert "uq_pd_plan_formalization_source" in idx_names

    def test_unique_index_columns(self, db_engine):
        inspector = inspect(db_engine)
        idx = next(
            idx
            for idx in inspector.get_indexes("project_director_plan_versions")
            if idx["name"] == "uq_pd_plan_formalization_source"
        )
        assert "session_id" in idx["column_names"]
        assert "formalization_target" in idx["column_names"]
        assert "formalization_workspace_version" in idx["column_names"]
        assert idx.get("unique", False)


# ===========================================================================
# §5.3 Migration additive upgrade
# ===========================================================================


class TestMigrationUpgrade:
    """§5.3 Old-DB additive upgrade creates formalization columns and index."""

    def test_additive_upgrade_creates_columns(self, tmp_path):
        db_path = tmp_path / "old-db.db"
        engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
        event.listen(engine, "connect", configure_sqlite)
        event.listen(engine, "begin", begin_sqlite_transaction)

        # Create a minimal old schema without formalization columns
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE TABLE project_director_plan_versions ("
                " id CHAR(32) PRIMARY KEY,"
                " session_id CHAR(32) NOT NULL,"
                " version_no INTEGER NOT NULL,"
                " status VARCHAR(32) NOT NULL DEFAULT 'draft',"
                " plan_summary TEXT NOT NULL DEFAULT '',"
                " created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
                ")"
            )

        # Patch the global engine to use our test engine
        import app.core.db as db_mod

        old_engine = db_mod.engine
        db_mod.engine = engine
        try:
            migrate_database_schema()
        finally:
            db_mod.engine = old_engine

        inspector = inspect(engine)
        columns = {
            col["name"]
            for col in inspector.get_columns("project_director_plan_versions")
        }
        assert "formalization_target" in columns
        assert "formalization_workspace_version" in columns
        assert "formalization_source_message_ids_json" in columns
        assert "formalization_source_event_ids_json" in columns

        indexes = inspector.get_indexes("project_director_plan_versions")
        idx_names = {idx["name"] for idx in indexes}
        assert "uq_pd_plan_formalization_source" in idx_names

    def test_second_upgrade_no_error(self, tmp_path):
        db_path = tmp_path / "old-db2.db"
        engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
        event.listen(engine, "connect", configure_sqlite)
        event.listen(engine, "begin", begin_sqlite_transaction)

        with engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE TABLE project_director_plan_versions ("
                " id CHAR(32) PRIMARY KEY,"
                " session_id CHAR(32) NOT NULL,"
                " version_no INTEGER NOT NULL,"
                " status VARCHAR(32) NOT NULL DEFAULT 'draft',"
                " plan_summary TEXT NOT NULL DEFAULT '',"
                " created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
                ")"
            )

        import app.core.db as db_mod

        old_engine = db_mod.engine
        db_mod.engine = engine
        try:
            migrate_database_schema()
            migrate_database_schema()  # second run must not error
        finally:
            db_mod.engine = old_engine

        # No duplicate columns
        inspector = inspect(engine)
        cols = [
            col["name"]
            for col in inspector.get_columns("project_director_plan_versions")
        ]
        assert cols.count("formalization_target") == 1
        assert cols.count("formalization_workspace_version") == 1

    def test_no_alembic_table_created(self, db_engine):
        inspector = inspect(db_engine)
        tables = set(inspector.get_table_names())
        assert "alembic_version" not in tables


# ===========================================================================
# §6 Repository
# ===========================================================================


class TestRepositoryCreateNoCommit:
    """§6.1 create_no_commit does not auto-commit."""

    def test_flushed_but_not_committed(self, db_session):
        _seed_session(db_session)
        repo = ProjectDirectorPlanVersionRepository(db_session)
        pv = ProjectDirectorPlanVersion(
            id=uuid4(),
            session_id=SESSION_ID,
            version_no=1,
            plan_summary="test",
        )
        result = repo.create_no_commit(pv)
        assert result.id == pv.id

        # Visible in current session
        assert repo.get_by_id(pv.id) is not None

        # Not visible in a new session (uncommitted)
        factory = sessionmaker(
            bind=db_session.get_bind(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        new_session = factory()
        try:
            new_repo = ProjectDirectorPlanVersionRepository(new_session)
            assert new_repo.get_by_id(pv.id) is None
        finally:
            new_session.close()


class TestRepositoryCreate:
    """§6.2 create() commits and is visible in new sessions."""

    def test_create_persists(self, db_session):
        _seed_session(db_session)
        repo = ProjectDirectorPlanVersionRepository(db_session)
        pv = ProjectDirectorPlanVersion(
            id=uuid4(),
            session_id=SESSION_ID,
            version_no=1,
            plan_summary="test",
        )
        result = repo.create(pv)

        factory = sessionmaker(
            bind=db_session.get_bind(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        new_session = factory()
        try:
            new_repo = ProjectDirectorPlanVersionRepository(new_session)
            assert new_repo.get_by_id(result.id) is not None
        finally:
            new_session.close()

    def test_plain_plan_version_still_works(self, db_session):
        _seed_session(db_session)
        repo = ProjectDirectorPlanVersionRepository(db_session)
        pv = ProjectDirectorPlanVersion(
            id=uuid4(),
            session_id=SESSION_ID,
            version_no=1,
            plan_summary="plain",
            status=PlanVersionStatus.DRAFT,
        )
        result = repo.create(pv)
        assert result.status == PlanVersionStatus.DRAFT
        assert result.formalization_target is None


class TestRepositoryProvenanceReadback:
    """§6.3 Formalization provenance round-trips correctly."""

    def test_provenance_round_trip(self, db_session):
        _seed_session(db_session)
        repo = ProjectDirectorPlanVersionRepository(db_session)
        msg_ids = [uuid4(), uuid4()]
        evt_ids = [uuid4(), uuid4()]
        pv = ProjectDirectorPlanVersion(
            id=uuid4(),
            session_id=SESSION_ID,
            version_no=1,
            plan_summary="test",
            status=PlanVersionStatus.PENDING_CONFIRMATION,
            source="ai",
            source_detail="provider; formalization_target=plan_revision; formalization_workspace_version=1",
            formalization_target=FormalizationTarget.PLAN_REVISION,
            formalization_workspace_version=1,
            formalization_source_message_ids=msg_ids,
            formalization_source_event_ids=evt_ids,
        )
        repo.create(pv)

        # Read back in new session
        factory = sessionmaker(
            bind=db_session.get_bind(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        new_session = factory()
        try:
            readback = ProjectDirectorPlanVersionRepository(new_session).get_by_id(pv.id)
            assert readback is not None
            assert readback.formalization_target == FormalizationTarget.PLAN_REVISION
            assert readback.formalization_workspace_version == 1
            assert readback.formalization_source_message_ids == msg_ids
            assert readback.formalization_source_event_ids == evt_ids
            assert readback.source == "ai"
            assert "formalization" in readback.source_detail
            assert readback.status == PlanVersionStatus.PENDING_CONFIRMATION
            assert readback.confirmed_at is None
        finally:
            new_session.close()


class TestRepositoryGetByFormalizationSource:
    """§6.4 get_by_formalization_source query."""

    def test_exact_match(self, db_session):
        _seed_session(db_session)
        repo = ProjectDirectorPlanVersionRepository(db_session)
        pv = ProjectDirectorPlanVersion(
            id=uuid4(),
            session_id=SESSION_ID,
            version_no=1,
            plan_summary="test",
            formalization_target=FormalizationTarget.PLAN_REVISION,
            formalization_workspace_version=1,
            formalization_source_message_ids=[uuid4()],
            formalization_source_event_ids=[uuid4()],
        )
        repo.create(pv)

        found = repo.get_by_formalization_source(
            session_id=SESSION_ID,
            target=FormalizationTarget.PLAN_REVISION,
            workspace_version=1,
        )
        assert found is not None
        assert found.id == pv.id

    def test_wrong_session_returns_none(self, db_session):
        _seed_session(db_session)
        repo = ProjectDirectorPlanVersionRepository(db_session)
        pv = ProjectDirectorPlanVersion(
            id=uuid4(),
            session_id=SESSION_ID,
            version_no=1,
            plan_summary="test",
            formalization_target=FormalizationTarget.PLAN_REVISION,
            formalization_workspace_version=1,
            formalization_source_message_ids=[uuid4()],
            formalization_source_event_ids=[uuid4()],
        )
        repo.create(pv)

        found = repo.get_by_formalization_source(
            session_id=uuid4(),
            target=FormalizationTarget.PLAN_REVISION,
            workspace_version=1,
        )
        assert found is None

    def test_wrong_workspace_version_returns_none(self, db_session):
        _seed_session(db_session)
        repo = ProjectDirectorPlanVersionRepository(db_session)
        pv = ProjectDirectorPlanVersion(
            id=uuid4(),
            session_id=SESSION_ID,
            version_no=1,
            plan_summary="test",
            formalization_target=FormalizationTarget.PLAN_REVISION,
            formalization_workspace_version=1,
            formalization_source_message_ids=[uuid4()],
            formalization_source_event_ids=[uuid4()],
        )
        repo.create(pv)

        found = repo.get_by_formalization_source(
            session_id=SESSION_ID,
            target=FormalizationTarget.PLAN_REVISION,
            workspace_version=2,
        )
        assert found is None

    def test_plain_plan_version_not_matched(self, db_session):
        _seed_session(db_session)
        repo = ProjectDirectorPlanVersionRepository(db_session)
        pv = ProjectDirectorPlanVersion(
            id=uuid4(),
            session_id=SESSION_ID,
            version_no=1,
            plan_summary="plain",
        )
        repo.create(pv)

        found = repo.get_by_formalization_source(
            session_id=SESSION_ID,
            target=FormalizationTarget.PLAN_REVISION,
            workspace_version=1,
        )
        assert found is None


class TestRepositoryCorruptJsonFailClosed:
    """§6.5 Corrupt JSON/UUID in DB must not silently pass."""

    def test_message_json_not_array(self, db_session):
        """Invalid JSON in message IDs column raises ValueError (fail closed)."""
        _seed_session(db_session)
        row = ProjectDirectorPlanVersionTable(
            id=uuid4(),
            session_id=SESSION_ID,
            version_no=1,
            status=PlanVersionStatus.PENDING_CONFIRMATION,
            plan_summary="corrupt",
            formalization_target="plan_revision",
            formalization_workspace_version=1,
            formalization_source_message_ids_json="not-an-array",
            formalization_source_event_ids_json=json.dumps([str(uuid4())]),
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
        db_session.add(row)
        db_session.flush()

        repo = ProjectDirectorPlanVersionRepository(db_session)
        # _parse_uuid_list raises ValueError on invalid JSON → fail closed
        with pytest.raises(ValueError, match="invalid_plan_version"):
            repo.get_by_id(row.id)

    def test_event_json_not_array(self, db_session):
        """Invalid JSON in event IDs column raises ValueError (fail closed)."""
        _seed_session(db_session)
        row = ProjectDirectorPlanVersionTable(
            id=uuid4(),
            session_id=SESSION_ID,
            version_no=1,
            status=PlanVersionStatus.PENDING_CONFIRMATION,
            plan_summary="corrupt",
            formalization_target="plan_revision",
            formalization_workspace_version=1,
            formalization_source_message_ids_json=json.dumps([str(uuid4())]),
            formalization_source_event_ids_json="invalid-json",
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
        db_session.add(row)
        db_session.flush()

        repo = ProjectDirectorPlanVersionRepository(db_session)
        with pytest.raises(ValueError, match="invalid_plan_version"):
            repo.get_by_id(row.id)

    def test_invalid_uuid_in_array(self, db_session):
        """Non-UUID string in ID array raises ValueError (fail closed)."""
        _seed_session(db_session)
        row = ProjectDirectorPlanVersionTable(
            id=uuid4(),
            session_id=SESSION_ID,
            version_no=1,
            status=PlanVersionStatus.PENDING_CONFIRMATION,
            plan_summary="corrupt",
            formalization_target="plan_revision",
            formalization_workspace_version=1,
            formalization_source_message_ids_json=json.dumps(["not-a-uuid"]),
            formalization_source_event_ids_json=json.dumps([str(uuid4())]),
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
        db_session.add(row)
        db_session.flush()

        repo = ProjectDirectorPlanVersionRepository(db_session)
        with pytest.raises(ValueError, match="invalid_plan_version"):
            repo.get_by_id(row.id)

    def test_target_present_but_empty_sources_fails_domain_validation(self, db_session):
        """Target=plan_revision with empty source arrays: domain model validation
        rejects during ORM→domain conversion (formalization all-or-none rule)."""
        _seed_session(db_session)
        row = ProjectDirectorPlanVersionTable(
            id=uuid4(),
            session_id=SESSION_ID,
            version_no=1,
            status=PlanVersionStatus.PENDING_CONFIRMATION,
            plan_summary="test",
            formalization_target="plan_revision",
            formalization_workspace_version=1,
            formalization_source_message_ids_json="[]",
            formalization_source_event_ids_json="[]",
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
        db_session.add(row)
        db_session.flush()

        repo = ProjectDirectorPlanVersionRepository(db_session)
        with pytest.raises((ValueError, Exception), match="source messages|source events|validation"):
            repo.get_by_id(row.id)


# ===========================================================================
# §7 Workspace & Event provenance
# ===========================================================================


class TestTopicOnlyProvenance:
    """§7.1 Topic-only workspace extracts TOPIC_SET event."""

    def test_topic_event_in_provenance(self, db_session):
        msg_id = _seed_message(db_session)
        evt = _make_event(
            sequence_no=1,
            event_type=DiscussionEventType.TOPIC_SET,
            content="主题A",
            source_message_ids=[msg_id],
        )
        _persist_event(db_session, evt)
        _seed_session(db_session)
        ws = _make_workspace(
            topic="主题A",
            discussion_status=DiscussionStatus.EXPLORING,
            version_no=1,
            last_event_sequence_no=1,
        )
        _persist_workspace(db_session, ws)

        svc = _build_formalization_service(db_session)
        result = svc.formalize_discussion(
            session_id=SESSION_ID,
            workspace_version=1,
            target=FormalizationTarget.PLAN_REVISION,
            user_confirmed=True,
        )
        assert evt.id in result.source_event_ids
        assert msg_id in result.source_message_ids


class TestOptionIdVsEventId:
    """§7.2 Option payload.option_id vs event.id distinction."""

    def test_event_id_in_provenance_not_option_uuid(self, db_session):
        event_uuid = uuid4()
        option_uuid = uuid4()
        msg_id = _seed_message(db_session)

        evt = _make_event(
            sequence_no=1,
            event_type=DiscussionEventType.OPTION_ADDED,
            content="选项A",
            subject_key="option",
            payload={"option_id": str(option_uuid)},
            source_message_ids=[msg_id],
            event_id=event_uuid,
        )
        _persist_event(db_session, evt)
        _seed_session(db_session)
        ws = _make_workspace(
            topic="",
            discussion_status=DiscussionStatus.EXPLORING,
            active_option_ids=[option_uuid],
            version_no=1,
            last_event_sequence_no=1,
        )
        _persist_workspace(db_session, ws)

        svc = _build_formalization_service(db_session)
        result = svc.formalize_discussion(
            session_id=SESSION_ID,
            workspace_version=1,
            target=FormalizationTarget.PLAN_REVISION,
            user_confirmed=True,
        )
        assert event_uuid in result.source_event_ids
        assert option_uuid not in result.source_event_ids


class TestPreferredOptionProvenance:
    """§7.3 Preferred option: both OPTION_ADDED and OPTION_PREFERRED events."""

    def test_both_events_in_provenance(self, db_session):
        option_id = uuid4()
        msg_id = _seed_message(db_session)

        evt_add = _make_event(
            sequence_no=1,
            event_type=DiscussionEventType.OPTION_ADDED,
            content="选项A",
            subject_key="option",
            payload={"option_id": str(option_id)},
            source_message_ids=[msg_id],
        )
        evt_prefer = _make_event(
            sequence_no=2,
            event_type=DiscussionEventType.OPTION_PREFERRED,
            content="选项A",
            subject_key="option",
            payload={"option_id": str(option_id)},
            source_message_ids=[msg_id],
        )
        _persist_event(db_session, evt_add)
        _persist_event(db_session, evt_prefer)
        _seed_session(db_session)
        _rebuild_and_persist_workspace(
            db_session, [evt_add, evt_prefer], version_no=1,
        )

        svc = _build_formalization_service(db_session)
        result = svc.formalize_discussion(
            session_id=SESSION_ID,
            workspace_version=1,
            target=FormalizationTarget.PLAN_REVISION,
            user_confirmed=True,
        )
        assert evt_add.id in result.source_event_ids
        assert evt_prefer.id in result.source_event_ids
        assert option_id not in result.source_event_ids


class TestOptionUpdateAndHistoricalExclusion:
    """§7.4 Option update supersedes old event; rejected options excluded."""

    def test_superseded_option_excluded(self, db_session):
        option_a = uuid4()
        msg_id = _seed_message(db_session)

        evt_add_a = _make_event(
            sequence_no=1,
            event_type=DiscussionEventType.OPTION_ADDED,
            content="选项A旧",
            subject_key="option",
            payload={"option_id": str(option_a)},
            source_message_ids=[msg_id],
        )
        evt_update_a = _make_event(
            sequence_no=2,
            event_type=DiscussionEventType.OPTION_UPDATED,
            content="选项A新",
            subject_key="option",
            payload={"option_id": str(option_a)},
            supersedes_event_id=evt_add_a.id,
            source_message_ids=[msg_id],
        )
        option_b = uuid4()
        evt_add_b = _make_event(
            sequence_no=3,
            event_type=DiscussionEventType.OPTION_ADDED,
            content="选项B",
            subject_key="option",
            payload={"option_id": str(option_b)},
            source_message_ids=[msg_id],
        )
        evt_reject_b = _make_event(
            sequence_no=4,
            event_type=DiscussionEventType.OPTION_REJECTED,
            content="选项B",
            subject_key="option",
            payload={"option_id": str(option_b)},
            source_message_ids=[msg_id],
        )

        for e in [evt_add_a, evt_update_a, evt_add_b, evt_reject_b]:
            _persist_event(db_session, e)

        _seed_session(db_session)
        # Only option_a is active (update superseded old add, but new update is effective)
        ws = _make_workspace(
            topic="",
            discussion_status=DiscussionStatus.EXPLORING,
            active_option_ids=[option_a],
            version_no=1,
            last_event_sequence_no=4,
        )
        _persist_workspace(db_session, ws)

        svc = _build_formalization_service(db_session)
        result = svc.formalize_discussion(
            session_id=SESSION_ID,
            workspace_version=1,
            target=FormalizationTarget.PLAN_REVISION,
            user_confirmed=True,
        )
        # Superseded add is excluded, update is included
        assert evt_add_a.id not in result.source_event_ids
        assert evt_update_a.id in result.source_event_ids
        # Rejected option events are excluded
        assert evt_add_b.id not in result.source_event_ids
        assert evt_reject_b.id not in result.source_event_ids
        # Option UUIDs never in event provenance
        assert option_a not in result.source_event_ids
        assert option_b not in result.source_event_ids


class TestDirectEventFields:
    """§7.5 Direct workspace event fields: constraint, question, conclusion, decision, correction."""

    def test_constraint_event(self, db_session):
        msg_id = _seed_message(db_session)
        evt = _make_event(
            sequence_no=1,
            event_type=DiscussionEventType.CONSTRAINT_ADDED,
            content="约束1",
            subject_key="constraint",
            source_message_ids=[msg_id],
        )
        _persist_event(db_session, evt)
        _seed_session(db_session)
        ws = _make_workspace(
            topic="",
            discussion_status=DiscussionStatus.EXPLORING,
            active_constraint_ids=[evt.id],
            version_no=1,
            last_event_sequence_no=1,
        )
        _persist_workspace(db_session, ws)

        svc = _build_formalization_service(db_session)
        result = svc.formalize_discussion(
            session_id=SESSION_ID,
            workspace_version=1,
            target=FormalizationTarget.PLAN_REVISION,
            user_confirmed=True,
        )
        assert evt.id in result.source_event_ids

    def test_open_question_event(self, db_session):
        msg_id = _seed_message(db_session)
        evt = _make_event(
            sequence_no=1,
            event_type=DiscussionEventType.OPEN_QUESTION_ADDED,
            content="问题1",
            subject_key="question",
            source_message_ids=[msg_id],
        )
        _persist_event(db_session, evt)
        _seed_session(db_session)
        ws = _make_workspace(
            topic="",
            discussion_status=DiscussionStatus.EXPLORING,
            open_question_ids=[evt.id],
            version_no=1,
            last_event_sequence_no=1,
        )
        _persist_workspace(db_session, ws)

        svc = _build_formalization_service(db_session)
        result = svc.formalize_discussion(
            session_id=SESSION_ID,
            workspace_version=1,
            target=FormalizationTarget.PLAN_REVISION,
            user_confirmed=True,
        )
        assert evt.id in result.source_event_ids

    def test_temporary_conclusion_event(self, db_session):
        msg_id = _seed_message(db_session)
        evt = _make_event(
            sequence_no=1,
            event_type=DiscussionEventType.TEMPORARY_CONCLUSION_ADDED,
            content="结论1",
            subject_key="conclusion",
            source_message_ids=[msg_id],
        )
        _persist_event(db_session, evt)
        _seed_session(db_session)
        ws = _make_workspace(
            topic="",
            discussion_status=DiscussionStatus.EXPLORING,
            temporary_conclusion_ids=[evt.id],
            version_no=1,
            last_event_sequence_no=1,
        )
        _persist_workspace(db_session, ws)

        svc = _build_formalization_service(db_session)
        result = svc.formalize_discussion(
            session_id=SESSION_ID,
            workspace_version=1,
            target=FormalizationTarget.PLAN_REVISION,
            user_confirmed=True,
        )
        assert evt.id in result.source_event_ids

    def test_decision_confirmed_event(self, db_session):
        msg_id = _seed_message(db_session)
        evt = _make_event(
            sequence_no=1,
            event_type=DiscussionEventType.DECISION_CONFIRMED,
            content="决定1",
            subject_key="decision",
            source_message_ids=[msg_id],
        )
        _persist_event(db_session, evt)
        _seed_session(db_session)
        _rebuild_and_persist_workspace(db_session, [evt], version_no=1)

        svc = _build_formalization_service(db_session)
        result = svc.formalize_discussion(
            session_id=SESSION_ID,
            workspace_version=1,
            target=FormalizationTarget.PLAN_REVISION,
            user_confirmed=True,
        )
        assert evt.id in result.source_event_ids

    def test_user_correction_event(self, db_session):
        msg_id = _seed_message(db_session)
        evt = _make_event(
            sequence_no=1,
            event_type=DiscussionEventType.USER_CORRECTION_RECORDED,
            content="纠正1",
            subject_key="correction",
            source_message_ids=[msg_id],
        )
        _persist_event(db_session, evt)
        _seed_session(db_session)
        ws = _make_workspace(
            topic="",
            discussion_status=DiscussionStatus.EXPLORING,
            latest_user_correction_event_id=evt.id,
            version_no=1,
            last_event_sequence_no=1,
        )
        _persist_workspace(db_session, ws)

        svc = _build_formalization_service(db_session)
        result = svc.formalize_discussion(
            session_id=SESSION_ID,
            workspace_version=1,
            target=FormalizationTarget.PLAN_REVISION,
            user_confirmed=True,
        )
        assert evt.id in result.source_event_ids


class TestWorkspaceEventTypeMismatch:
    """§7.6 Type mismatch in workspace event fields must fail."""

    def test_constraint_id_pointing_to_open_question(self, db_session):
        """Workspace active_constraint_ids pointing to an OPEN_QUESTION event
        causes projection mismatch (reducer places it in open_question_ids)."""
        msg_id = _seed_message(db_session)
        evt = _make_event(
            sequence_no=1,
            event_type=DiscussionEventType.OPEN_QUESTION_ADDED,
            content="问题1",
            subject_key="question",
            source_message_ids=[msg_id],
        )
        _persist_event(db_session, evt)
        _seed_session(db_session)
        ws = _make_workspace(
            topic="",
            discussion_status=DiscussionStatus.EXPLORING,
            active_constraint_ids=[evt.id],  # wrong type → projection mismatch
            version_no=1,
            last_event_sequence_no=1,
        )
        _persist_workspace(db_session, ws)

        svc = _build_formalization_service(db_session)
        with pytest.raises(ValueError, match="projection_mismatch|workspace_event_type_mismatch"):
            svc.formalize_discussion(
                session_id=SESSION_ID,
                workspace_version=1,
                target=FormalizationTarget.PLAN_REVISION,
                user_confirmed=True,
            )
        assert _count_plan_versions(db_session) == 0

    def test_open_question_id_pointing_to_constraint(self, db_session):
        """Workspace open_question_ids pointing to a CONSTRAINT event
        causes projection mismatch (reducer places it in active_constraint_ids)."""
        msg_id = _seed_message(db_session)
        evt = _make_event(
            sequence_no=1,
            event_type=DiscussionEventType.CONSTRAINT_ADDED,
            content="约束1",
            subject_key="constraint",
            source_message_ids=[msg_id],
        )
        _persist_event(db_session, evt)
        _seed_session(db_session)
        ws = _make_workspace(
            topic="",
            discussion_status=DiscussionStatus.EXPLORING,
            open_question_ids=[evt.id],  # wrong type → projection mismatch
            version_no=1,
            last_event_sequence_no=1,
        )
        _persist_workspace(db_session, ws)

        svc = _build_formalization_service(db_session)
        with pytest.raises(ValueError, match="projection_mismatch|workspace_event_type_mismatch"):
            svc.formalize_discussion(
                session_id=SESSION_ID,
                workspace_version=1,
                target=FormalizationTarget.PLAN_REVISION,
                user_confirmed=True,
            )
        assert _count_plan_versions(db_session) == 0

    def test_conclusion_id_pointing_to_decision(self, db_session):
        """Workspace temporary_conclusion_ids pointing to a DECISION event
        causes projection mismatch (reducer places it in confirmed_decision_ids)."""
        msg_id = _seed_message(db_session)
        evt = _make_event(
            sequence_no=1,
            event_type=DiscussionEventType.DECISION_CONFIRMED,
            content="决定1",
            subject_key="decision",
            source_message_ids=[msg_id],
        )
        _persist_event(db_session, evt)
        _seed_session(db_session)
        ws = _make_workspace(
            topic="",
            discussion_status=DiscussionStatus.EXPLORING,
            temporary_conclusion_ids=[evt.id],  # wrong type → projection mismatch
            version_no=1,
            last_event_sequence_no=1,
        )
        _persist_workspace(db_session, ws)

        svc = _build_formalization_service(db_session)
        with pytest.raises(ValueError, match="projection_mismatch|workspace_event_type_mismatch"):
            svc.formalize_discussion(
                session_id=SESSION_ID,
                workspace_version=1,
                target=FormalizationTarget.PLAN_REVISION,
                user_confirmed=True,
            )
        assert _count_plan_versions(db_session) == 0


class TestStatusEventProvenance:
    """§7.7 Status event source inclusion."""

    def test_formalization_requested_in_provenance(self, db_session):
        msg_id = _seed_message(db_session)
        evt_topic = _make_event(
            sequence_no=1,
            event_type=DiscussionEventType.TOPIC_SET,
            content="主题",
            source_message_ids=[msg_id],
        )
        evt_status = _make_event(
            sequence_no=2,
            event_type=DiscussionEventType.FORMALIZATION_REQUESTED,
            content="请求正式化",
            source_message_ids=[msg_id],
        )
        _persist_event(db_session, evt_topic)
        _persist_event(db_session, evt_status)
        _seed_session(db_session)
        ws = _make_workspace(
            topic="主题",
            discussion_status=DiscussionStatus.READY_TO_FORMALIZE,
            version_no=1,
            last_event_sequence_no=2,
        )
        _persist_workspace(db_session, ws)

        svc = _build_formalization_service(db_session)
        result = svc.formalize_discussion(
            session_id=SESSION_ID,
            workspace_version=1,
            target=FormalizationTarget.PLAN_REVISION,
            user_confirmed=True,
        )
        assert evt_topic.id in result.source_event_ids
        assert evt_status.id in result.source_event_ids


# ===========================================================================
# §8 History & Projection Gate
# ===========================================================================


class TestEventHistoryAhead:
    """§8.1 Workspace behind event history must fail."""

    def test_history_ahead_fails(self, db_session):
        msg_id = _seed_message(db_session)
        evt1 = _make_event(
            sequence_no=1,
            event_type=DiscussionEventType.TOPIC_SET,
            content="主题",
            source_message_ids=[msg_id],
        )
        evt2 = _make_event(
            sequence_no=2,
            event_type=DiscussionEventType.FORMALIZATION_REQUESTED,
            content="请求",
            source_message_ids=[msg_id],
        )
        _persist_event(db_session, evt1)
        _persist_event(db_session, evt2)
        _seed_session(db_session)
        ws = _make_workspace(
            topic="主题",
            discussion_status=DiscussionStatus.READY_TO_FORMALIZE,
            version_no=1,
            last_event_sequence_no=1,  # behind: only 1, but history has 2
        )
        _persist_workspace(db_session, ws)

        svc = _build_formalization_service(db_session)
        with pytest.raises(ValueError, match="event_history_ahead"):
            svc.formalize_discussion(
                session_id=SESSION_ID,
                workspace_version=1,
                target=FormalizationTarget.PLAN_REVISION,
                user_confirmed=True,
            )
        assert _count_plan_versions(db_session) == 0


class TestEventHistoryMismatch:
    """§8.2 last_event_sequence_no != actual last sequence."""

    def test_history_mismatch_fails(self, db_session):
        msg_id = _seed_message(db_session)
        evt = _make_event(
            sequence_no=1,
            event_type=DiscussionEventType.TOPIC_SET,
            content="主题",
            source_message_ids=[msg_id],
        )
        _persist_event(db_session, evt)
        _seed_session(db_session)
        ws = _make_workspace(
            topic="主题",
            discussion_status=DiscussionStatus.EXPLORING,
            version_no=1,
            last_event_sequence_no=5,  # mismatch: actual is 1
        )
        _persist_workspace(db_session, ws)

        svc = _build_formalization_service(db_session)
        with pytest.raises(ValueError, match="event_history_mismatch"):
            svc.formalize_discussion(
                session_id=SESSION_ID,
                workspace_version=1,
                target=FormalizationTarget.PLAN_REVISION,
                user_confirmed=True,
            )


class TestProjectionMismatch:
    """§8.3 Workspace fields must match rebuilt projection."""

    @pytest.mark.parametrize(
        "field,modify",
        [
            ("topic", lambda ws: setattr(ws, "topic", "WRONG")),
            (
                "discussion_status",
                lambda ws: setattr(ws, "discussion_status", DiscussionStatus.CONVERGING),
            ),
            (
                "active_option_ids",
                lambda ws: setattr(ws, "active_option_ids", [uuid4()]),
            ),
            (
                "preferred_option_id",
                lambda ws: (setattr(ws, "active_option_ids", [uuid4()]),
                            setattr(ws, "preferred_option_id", ws.active_option_ids[0])),
            ),
            (
                "active_constraint_ids",
                lambda ws: setattr(ws, "active_constraint_ids", [uuid4()]),
            ),
            (
                "open_question_ids",
                lambda ws: setattr(ws, "open_question_ids", [uuid4()]),
            ),
            (
                "temporary_conclusion_ids",
                lambda ws: setattr(ws, "temporary_conclusion_ids", [uuid4()]),
            ),
            (
                "confirmed_decision_ids",
                lambda ws: setattr(ws, "confirmed_decision_ids", [uuid4()]),
            ),
            (
                "latest_user_correction_event_id",
                lambda ws: setattr(ws, "latest_user_correction_event_id", uuid4()),
            ),
        ],
    )
    def test_projection_mismatch_fails(self, db_session, field, modify):
        msg_id = _seed_message(db_session)
        evt = _make_event(
            sequence_no=1,
            event_type=DiscussionEventType.TOPIC_SET,
            content="主题",
            source_message_ids=[msg_id],
        )
        _persist_event(db_session, evt)
        _seed_session(db_session)
        ws = _make_workspace(
            topic="主题",
            discussion_status=DiscussionStatus.EXPLORING,
            version_no=1,
            last_event_sequence_no=1,
        )
        modify(ws)
        _persist_workspace(db_session, ws)

        svc = _build_formalization_service(db_session)
        with pytest.raises(ValueError, match="projection_mismatch"):
            svc.formalize_discussion(
                session_id=SESSION_ID,
                workspace_version=1,
                target=FormalizationTarget.PLAN_REVISION,
                user_confirmed=True,
            )
        assert _count_plan_versions(db_session) == 0

    def test_last_event_sequence_no_too_low(self, db_session):
        """last_event_sequence_no < actual → history_ahead."""
        msg_id = _seed_message(db_session)
        evt1 = _make_event(sequence_no=1, event_type=DiscussionEventType.TOPIC_SET,
                           content="主题", source_message_ids=[msg_id])
        evt2 = _make_event(sequence_no=2, event_type=DiscussionEventType.FORMALIZATION_REQUESTED,
                           content="请求", source_message_ids=[msg_id])
        _persist_event(db_session, evt1)
        _persist_event(db_session, evt2)
        _seed_session(db_session)
        ws = _make_workspace(topic="主题", discussion_status=DiscussionStatus.READY_TO_FORMALIZE,
                             version_no=1, last_event_sequence_no=1)
        _persist_workspace(db_session, ws)

        svc = _build_formalization_service(db_session)
        with pytest.raises(ValueError, match="event_history_ahead"):
            svc.formalize_discussion(
                session_id=SESSION_ID, workspace_version=1,
                target=FormalizationTarget.PLAN_REVISION, user_confirmed=True,
            )
        assert _count_plan_versions(db_session) == 0

    def test_last_event_sequence_no_too_high(self, db_session):
        """last_event_sequence_no > actual → history_mismatch."""
        msg_id = _seed_message(db_session)
        evt = _make_event(sequence_no=1, event_type=DiscussionEventType.TOPIC_SET,
                          content="主题", source_message_ids=[msg_id])
        _persist_event(db_session, evt)
        _seed_session(db_session)
        ws = _make_workspace(topic="主题", discussion_status=DiscussionStatus.EXPLORING,
                             version_no=1, last_event_sequence_no=5)
        _persist_workspace(db_session, ws)

        svc = _build_formalization_service(db_session)
        with pytest.raises(ValueError, match="event_history_mismatch"):
            svc.formalize_discussion(
                session_id=SESSION_ID, workspace_version=1,
                target=FormalizationTarget.PLAN_REVISION, user_confirmed=True,
            )


class TestInvalidOptionId:
    """§8.4 Option events with missing/invalid option_id must fail."""

    def test_missing_option_id(self, db_session):
        msg_id = _seed_message(db_session)
        evt = _make_event(
            sequence_no=1,
            event_type=DiscussionEventType.OPTION_ADDED,
            content="选项",
            subject_key="option",
            payload={},  # missing option_id
            source_message_ids=[msg_id],
        )
        _persist_event(db_session, evt)
        _seed_session(db_session)
        # active_option_ids has a dummy id that won't match
        ws = _make_workspace(
            topic="",
            discussion_status=DiscussionStatus.EXPLORING,
            active_option_ids=[uuid4()],
            version_no=1,
            last_event_sequence_no=1,
        )
        _persist_workspace(db_session, ws)

        svc = _build_formalization_service(db_session)
        with pytest.raises(ValueError, match="option_id_invalid"):
            svc.formalize_discussion(
                session_id=SESSION_ID,
                workspace_version=1,
                target=FormalizationTarget.PLAN_REVISION,
                user_confirmed=True,
            )
        assert _count_plan_versions(db_session) == 0

    def test_invalid_option_id_format(self, db_session):
        msg_id = _seed_message(db_session)
        evt = _make_event(
            sequence_no=1,
            event_type=DiscussionEventType.OPTION_ADDED,
            content="选项",
            subject_key="option",
            payload={"option_id": "not-a-uuid"},
            source_message_ids=[msg_id],
        )
        _persist_event(db_session, evt)
        _seed_session(db_session)
        ws = _make_workspace(
            topic="",
            discussion_status=DiscussionStatus.EXPLORING,
            active_option_ids=[uuid4()],
            version_no=1,
            last_event_sequence_no=1,
        )
        _persist_workspace(db_session, ws)

        svc = _build_formalization_service(db_session)
        with pytest.raises(ValueError, match="option_id_invalid"):
            svc.formalize_discussion(
                session_id=SESSION_ID,
                workspace_version=1,
                target=FormalizationTarget.PLAN_REVISION,
                user_confirmed=True,
            )


# ===========================================================================
# §9 Formalization Gate
# ===========================================================================


class TestFormalizationGates:
    """§9 Various gate conditions that must block formalization."""

    def test_user_not_confirmed(self, db_session):
        _seed_ready_to_formalize(db_session)
        svc = _build_formalization_service(db_session)
        with pytest.raises(ValueError, match="user_confirmation_required"):
            svc.formalize_discussion(
                session_id=SESSION_ID,
                workspace_version=1,
                target=FormalizationTarget.PLAN_REVISION,
                user_confirmed=False,
            )
        assert _count_plan_versions(db_session) == 0

    def test_session_not_found(self, db_session):
        svc = _build_formalization_service(db_session)
        with pytest.raises(ValueError, match="not found"):
            svc.formalize_discussion(
                session_id=uuid4(),
                workspace_version=1,
                target=FormalizationTarget.PLAN_REVISION,
                user_confirmed=True,
            )
        assert _count_plan_versions(db_session) == 0

    def test_session_not_confirmed(self, db_session):
        _seed_session(db_session)
        # Override status to CLARIFYING
        row = db_session.get(ProjectDirectorSessionTable, SESSION_ID)
        row.status = ProjectDirectorSessionStatus.CLARIFYING
        db_session.flush()

        svc = _build_formalization_service(db_session)
        with pytest.raises(ValueError, match="session_not_confirmed"):
            svc.formalize_discussion(
                session_id=SESSION_ID,
                workspace_version=1,
                target=FormalizationTarget.PLAN_REVISION,
                user_confirmed=True,
            )
        assert _count_plan_versions(db_session) == 0

    def test_workspace_not_found(self, db_session):
        _seed_session(db_session)
        svc = _build_formalization_service(db_session)
        with pytest.raises(ValueError, match="workspace_not_found"):
            svc.formalize_discussion(
                session_id=SESSION_ID,
                workspace_version=1,
                target=FormalizationTarget.PLAN_REVISION,
                user_confirmed=True,
            )
        assert _count_plan_versions(db_session) == 0

    def test_workspace_version_mismatch(self, db_session):
        _seed_ready_to_formalize(db_session, workspace_version=1)
        svc = _build_formalization_service(db_session)
        with pytest.raises(ValueError, match="workspace_version_mismatch"):
            svc.formalize_discussion(
                session_id=SESSION_ID,
                workspace_version=2,
                target=FormalizationTarget.PLAN_REVISION,
                user_confirmed=True,
            )
        assert _count_plan_versions(db_session) == 0

    def test_workspace_version_zero(self, db_session):
        msg_id = _seed_message(db_session)
        evt = _make_event(
            sequence_no=1,
            event_type=DiscussionEventType.TOPIC_SET,
            content="主题",
            source_message_ids=[msg_id],
        )
        _persist_event(db_session, evt)
        _seed_session(db_session)
        ws = _make_workspace(
            topic="主题",
            discussion_status=DiscussionStatus.EXPLORING,
            version_no=0,
            last_event_sequence_no=1,
        )
        _persist_workspace(db_session, ws)

        svc = _build_formalization_service(db_session)
        with pytest.raises(ValueError, match="workspace_not_ready"):
            svc.formalize_discussion(
                session_id=SESSION_ID,
                workspace_version=0,
                target=FormalizationTarget.PLAN_REVISION,
                user_confirmed=True,
            )
        assert _count_plan_versions(db_session) == 0

    def test_source_message_not_found(self, db_session):
        """Event references a message_id that doesn't exist in messages table."""
        _seed_session(db_session)
        fake_msg_id = uuid4()
        evt = _make_event(
            sequence_no=1,
            event_type=DiscussionEventType.TOPIC_SET,
            content="主题",
            source_message_ids=[fake_msg_id],
        )
        _persist_event(db_session, evt)
        ws = _make_workspace(
            topic="主题",
            discussion_status=DiscussionStatus.EXPLORING,
            version_no=1,
            last_event_sequence_no=1,
        )
        _persist_workspace(db_session, ws)

        svc = _build_formalization_service(db_session)
        with pytest.raises(ValueError, match="source_message_not_found"):
            svc.formalize_discussion(
                session_id=SESSION_ID,
                workspace_version=1,
                target=FormalizationTarget.PLAN_REVISION,
                user_confirmed=True,
            )

    def test_source_message_session_mismatch(self, db_session):
        """Message belongs to a different session."""
        other_session_id = uuid4()
        _seed_session(db_session, session_id=other_session_id)
        msg_id = _seed_message(db_session, session_id=other_session_id)
        _seed_session(db_session)
        evt = _make_event(
            sequence_no=1,
            event_type=DiscussionEventType.TOPIC_SET,
            content="主题",
            source_message_ids=[msg_id],
        )
        _persist_event(db_session, evt)
        ws = _make_workspace(
            topic="主题",
            discussion_status=DiscussionStatus.EXPLORING,
            version_no=1,
            last_event_sequence_no=1,
        )
        _persist_workspace(db_session, ws)

        svc = _build_formalization_service(db_session)
        with pytest.raises(ValueError, match="source_message_session_mismatch"):
            svc.formalize_discussion(
                session_id=SESSION_ID,
                workspace_version=1,
                target=FormalizationTarget.PLAN_REVISION,
                user_confirmed=True,
            )

    def test_shared_session_unavailable(self, db_session):
        """Repository with no _session attribute must fail early."""
        session_repo = ProjectDirectorSessionRepository(db_session)
        workspace_repo = ProjectDirectorDiscussionWorkspaceRepository(db_session)
        event_repo = ProjectDirectorDiscussionEventRepository(db_session)
        message_repo = ProjectDirectorMessageRepository(db_session)
        plan_version_repo = ProjectDirectorPlanVersionRepository(db_session)

        # Create a plan service with no _session_repo/_plan_repo
        plan_service = ProjectDirectorPlanService(
            plan_version_repository=plan_version_repo,
            session_repository=session_repo,
            provider_config_service=_FakeProviderConfigService(configured=False),
        )

        # Create a service with a mock repo that has no _session
        class BadRepo:
            pass

        svc = ProjectDirectorDiscussionFormalizationService(
            session_repository=BadRepo(),
            discussion_workspace_repository=workspace_repo,
            discussion_event_repository=event_repo,
            message_repository=message_repo,
            plan_version_repository=plan_version_repo,
            plan_service=plan_service,
        )
        with pytest.raises(ValueError, match="shared_session_unavailable"):
            svc.formalize_discussion(
                session_id=SESSION_ID,
                workspace_version=1,
                target=FormalizationTarget.PLAN_REVISION,
                user_confirmed=True,
            )

    def test_shared_session_mismatch(self, db_session):
        """Repositories on different sessions must fail early."""
        other_session = sessionmaker(
            bind=db_session.get_bind(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )()
        try:
            session_repo = ProjectDirectorSessionRepository(db_session)
            workspace_repo = ProjectDirectorDiscussionWorkspaceRepository(db_session)
            event_repo = ProjectDirectorDiscussionEventRepository(db_session)
            message_repo = ProjectDirectorMessageRepository(db_session)
            plan_version_repo = ProjectDirectorPlanVersionRepository(other_session)  # different!

            plan_service = ProjectDirectorPlanService(
                plan_version_repository=plan_version_repo,
                session_repository=session_repo,
                provider_config_service=_FakeProviderConfigService(configured=False),
            )
            svc = ProjectDirectorDiscussionFormalizationService(
                session_repository=session_repo,
                discussion_workspace_repository=workspace_repo,
                discussion_event_repository=event_repo,
                message_repository=message_repo,
                plan_version_repository=plan_version_repo,
                plan_service=plan_service,
            )
            with pytest.raises(ValueError, match="shared_session_mismatch"):
                svc.formalize_discussion(
                    session_id=SESSION_ID,
                    workspace_version=1,
                    target=FormalizationTarget.PLAN_REVISION,
                    user_confirmed=True,
                )
        finally:
            other_session.close()


# ===========================================================================
# §10 Success transaction
# ===========================================================================


class TestRuleFallback:
    """§10.1 No API key → rule_fallback source."""

    def test_rule_fallback_creates_plan_version(self, db_session):
        _seed_ready_to_formalize(db_session)
        svc = _build_formalization_service(db_session, provider_configured=False)
        result = svc.formalize_discussion(
            session_id=SESSION_ID,
            workspace_version=1,
            target=FormalizationTarget.PLAN_REVISION,
            user_confirmed=True,
        )
        assert result.plan_version.status == PlanVersionStatus.PENDING_CONFIRMATION
        assert result.plan_version.source == "rule_fallback"
        assert "provider_not_configured" in result.plan_version.source_detail
        assert "formalization_target=plan_revision" in result.plan_version.source_detail
        assert "formalization_workspace_version=1" in result.plan_version.source_detail
        assert result.idempotent_replay is False
        assert _count_plan_versions(db_session) == 1


class TestProviderPath:
    """§10.2 Provider path: balanced model, revision_notes, provenance."""

    def test_provider_generates_plan(self, db_session):
        _seed_ready_to_formalize(db_session)
        provider_spy = _ProviderSpy()
        svc = _build_formalization_service(
            db_session,
            provider_configured=True,
            provider_text_generator=provider_spy,
        )
        result = svc.formalize_discussion(
            session_id=SESSION_ID,
            workspace_version=1,
            target=FormalizationTarget.PLAN_REVISION,
            user_confirmed=True,
        )
        assert result.plan_version.source == "ai"
        assert len(provider_spy.calls) == 1
        model_name, prompt, _request_id = provider_spy.calls[0]
        assert model_name == "test-plan-model"

        # revision_notes must contain workspace/event info
        assert "formalization_target" in prompt
        assert "workspace_version" in prompt
        assert "topic_set" in prompt

        # Must NOT contain sensitive provenance fields
        for forbidden in [
            "source_surface",
            "source_entity_type",
            "source_entity_id",
            "trigger_type",
            "interaction_case_id",
            "external_context_pack_id",
            "api_key",
            "Authorization",
            "Bearer",
        ]:
            assert forbidden not in prompt, f"Sensitive field {forbidden!r} found in prompt"

        assert result.idempotent_replay is False
        assert _count_plan_versions(db_session) == 1


class TestFreshSessionReadback:
    """§10.3 Fresh session readback after success."""

    def test_fresh_session_readback(self, db_session):
        _seed_ready_to_formalize(db_session)
        svc = _build_formalization_service(db_session, provider_configured=False)
        result = svc.formalize_discussion(
            session_id=SESSION_ID,
            workspace_version=1,
            target=FormalizationTarget.PLAN_REVISION,
            user_confirmed=True,
        )
        pv_id = result.plan_version.id
        db_session.commit()

        # Read back in a new session
        factory = sessionmaker(
            bind=db_session.get_bind(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        new_sess = factory()
        try:
            repo = ProjectDirectorPlanVersionRepository(new_sess)
            readback = repo.get_by_id(pv_id)
            assert readback is not None
            assert readback.formalization_target == FormalizationTarget.PLAN_REVISION
            assert readback.formalization_workspace_version == 1
            assert len(readback.formalization_source_message_ids) > 0
            assert len(readback.formalization_source_event_ids) > 0
            assert readback.status == PlanVersionStatus.PENDING_CONFIRMATION
            assert readback.confirmed_at is None

            # Session unchanged
            sess_repo = ProjectDirectorSessionRepository(new_sess)
            sess = sess_repo.get_by_id(SESSION_ID)
            assert sess is not None
            assert sess.status == ProjectDirectorSessionStatus.CONFIRMED

            # Workspace unchanged
            ws_repo = ProjectDirectorDiscussionWorkspaceRepository(new_sess)
            ws = ws_repo.get_by_session_id(session_id=SESSION_ID)
            assert ws is not None
            assert ws.version_no == 1
        finally:
            new_sess.close()


# ===========================================================================
# §11 Idempotency & exception transactions
# ===========================================================================


class TestNormalIdempotency:
    """§11.1 Same session/target/workspace_version returns same PlanVersion."""

    def test_second_call_returns_same_plan(self, db_session):
        _seed_ready_to_formalize(db_session)
        svc = _build_formalization_service(db_session, provider_configured=False)
        result1 = svc.formalize_discussion(
            session_id=SESSION_ID,
            workspace_version=1,
            target=FormalizationTarget.PLAN_REVISION,
            user_confirmed=True,
        )
        result2 = svc.formalize_discussion(
            session_id=SESSION_ID,
            workspace_version=1,
            target=FormalizationTarget.PLAN_REVISION,
            user_confirmed=True,
        )
        assert result2.idempotent_replay is True
        assert result2.plan_version.id == result1.plan_version.id
        assert _count_plan_versions(db_session) == 1


class TestIntegrityErrorRaceReadback:
    """§11.2 Unique index race: IntegrityError → rollback → read existing."""

    def test_real_integrity_error_race_recovery(self, db_session_factory):
        """Three-session race: setup seeds data, winner inserts competing PlanVersion,
        service runs formalization with staged pre-read. Uses controlled Provider spy."""
        # ── Session 1: setup ──────────────────────────────────────────────
        setup = db_session_factory()
        try:
            _seed_ready_to_formalize(setup)
            setup.commit()
        finally:
            setup.close()

        # ── Session 2: winner inserts competing PlanVersion ───────────────
        winner = db_session_factory()
        try:
            evt_repo = ProjectDirectorDiscussionEventRepository(winner)
            events = evt_repo.list_by_session_id(session_id=SESSION_ID)
            msg_ids = []
            for evt in events:
                for mid in evt.source_message_ids:
                    if mid not in msg_ids:
                        msg_ids.append(mid)
            evt_ids = [evt.id for evt in events]

            winner_id = uuid4()
            winner.execute(
                text(
                    "INSERT INTO project_director_plan_versions "
                    "(id, session_id, version_no, status, plan_summary, "
                    "phases_json, proposed_tasks_json, acceptance_criteria_json, "
                    "risks_json, project_scope_json, agent_team_suggestions_json, "
                    "skill_binding_suggestions_json, verification_mechanisms_json, "
                    "repository_binding_suggestions_json, deliverable_boundaries_json, "
                    "complexity_assessment_json, source, source_detail, forbidden_actions_json, "
                    "formalization_target, formalization_workspace_version, "
                    "formalization_source_message_ids_json, formalization_source_event_ids_json, "
                    "created_at, updated_at) VALUES (:id, :sid, 1, 'pending_confirmation', "
                    "'竞争方计划', '[]', '[]', '[]', '[]', '{}', '[]', '[]', '[]', '[]', '[]', '{}', "
                    "'rule_fallback', 'race_winner', '[]', "
                    "'plan_revision', 1, :msg_json, :evt_json, :now, :now)"
                ),
                {
                    "id": str(winner_id).replace("-", ""),
                    "sid": str(SESSION_ID).replace("-", ""),
                    "msg_json": json.dumps([str(mid) for mid in msg_ids]),
                    "evt_json": json.dumps([str(eid) for eid in evt_ids]),
                    "now": datetime.now(timezone.utc).isoformat(),
                },
            )
            winner.commit()
        finally:
            winner.close()

        # ── Session 3: service attempts formalization ─────────────────────
        svc_session = db_session_factory()
        try:
            provider_spy = _ProviderSpy()
            svc = _build_formalization_service(
                svc_session, provider_configured=True, provider_text_generator=provider_spy,
            )
            fake_config = svc._plan_service._provider_config_service
            repo = svc._plan_version_repository

            # Stage the pre-read: first call returns None, subsequent calls use real
            real_get = repo.get_by_formalization_source
            lookup_calls = [0]

            def staged_get(*, session_id, target, workspace_version):
                lookup_calls[0] += 1
                if lookup_calls[0] == 1:
                    return None
                return real_get(session_id=session_id, target=target, workspace_version=workspace_version)

            # Count create_no_commit calls
            real_create = repo.create_no_commit
            create_calls = [0]

            def counted_create(plan_version):
                create_calls[0] += 1
                return real_create(plan_version)

            with (
                patch.object(repo, "get_by_formalization_source", staged_get),
                patch.object(repo, "create_no_commit", counted_create),
                SessionTransactionSpy(svc_session) as txspy,
            ):
                result = svc.formalize_discussion(
                    session_id=SESSION_ID,
                    workspace_version=1,
                    target=FormalizationTarget.PLAN_REVISION,
                    user_confirmed=True,
                )

            # ── Strong assertions ─────────────────────────────────────────
            assert lookup_calls[0] >= 2                    # pre-read + recovery read
            assert create_calls[0] == 1                    # create_no_commit executed once
            assert txspy.commit_count == 0                 # no successful commit
            assert txspy.rollback_count == 1               # IntegrityError triggers rollback
            assert result.idempotent_replay is True
            assert result.plan_version.id == winner_id     # reads back the race winner
            assert fake_config.resolve_calls == 1          # Provider config resolved
            assert len(provider_spy.calls) == 1            # Provider text called once

            # Provenance must match
            assert list(result.source_message_ids) == msg_ids
            assert list(result.source_event_ids) == evt_ids

            # Fresh session: only 1 PlanVersion exists
            fresh = db_session_factory()
            try:
                count = _count_table(fresh, ProjectDirectorPlanVersionTable)
                assert count == 1
            finally:
                fresh.close()
        finally:
            svc_session.close()


class TestProvenanceConflict:
    """§11.3 Idempotency conflict: same source but different provenance."""

    def test_provenance_conflict_raises(self, db_session):
        _seed_ready_to_formalize(db_session)
        svc = _build_formalization_service(db_session, provider_configured=False)

        result1 = svc.formalize_discussion(
            session_id=SESSION_ID,
            workspace_version=1,
            target=FormalizationTarget.PLAN_REVISION,
            user_confirmed=True,
        )

        # Tamper with the existing plan version's provenance
        repo = ProjectDirectorPlanVersionRepository(db_session)
        existing = repo.get_by_id(result1.plan_version.id)
        row = db_session.get(ProjectDirectorPlanVersionTable, existing.id)
        row.formalization_source_event_ids_json = json.dumps([str(uuid4())])
        db_session.flush()

        with pytest.raises(ValueError, match="idempotency_conflict"):
            svc.formalize_discussion(
                session_id=SESSION_ID,
                workspace_version=1,
                target=FormalizationTarget.PLAN_REVISION,
                user_confirmed=True,
            )


class TestUnrelatedIntegrityError:
    """§11.4 Unrelated IntegrityError must propagate as IntegrityError, not ValueError."""

    def test_unrelated_integrity_error_propagates(self, db_session_factory):
        # Setup in one session
        setup = db_session_factory()
        try:
            _seed_ready_to_formalize(setup)
            setup.commit()
        finally:
            setup.close()

        svc_session = db_session_factory()
        try:
            svc = _build_formalization_service(svc_session, provider_configured=False)

            original_create = ProjectDirectorPlanVersionRepository.create_no_commit

            def failing_create(self_repo, plan_version):
                original_create(self_repo, plan_version)
                raise IntegrityError("UNRELATED", {}, Exception("fake"))

            with (
                patch.object(ProjectDirectorPlanVersionRepository, "create_no_commit", failing_create),
                SessionTransactionSpy(svc_session) as txspy,
            ):
                with pytest.raises(IntegrityError):
                    svc.formalize_discussion(
                        session_id=SESSION_ID,
                        workspace_version=1,
                        target=FormalizationTarget.PLAN_REVISION,
                        user_confirmed=True,
                    )

            assert txspy.commit_count == 0
            assert txspy.rollback_count == 1

            # Session still usable — no manual rollback needed
            usable = svc_session.execute(select(func.count()).select_from(ProjectDirectorPlanVersionTable)).scalar_one()
            assert usable == 0

            # Fresh session: no PlanVersion
            fresh = db_session_factory()
            try:
                count = fresh.execute(
                    select(func.count()).select_from(ProjectDirectorPlanVersionTable)
                ).scalar_one()
                assert count == 0
            finally:
                fresh.close()
        finally:
            svc_session.close()


class TestCommitFailure:
    """§11.5 Non-IntegrityError commit failure."""

    def test_commit_failure_rolls_back(self, db_session_factory):
        # Setup in one session
        setup = db_session_factory()
        try:
            _seed_ready_to_formalize(setup)
            setup.commit()
        finally:
            setup.close()

        svc_session = db_session_factory()
        try:
            svc = _build_formalization_service(svc_session, provider_configured=False)

            commit_attempts = [0]
            rollback_count = [0]
            original_commit = svc_session.commit
            original_rollback = svc_session.rollback

            def failing_commit():
                commit_attempts[0] += 1
                raise RuntimeError("commit failed")

            def counting_rollback():
                rollback_count[0] += 1
                return original_rollback()

            svc_session.commit = failing_commit
            svc_session.rollback = counting_rollback

            try:
                with pytest.raises(RuntimeError, match="commit failed"):
                    svc.formalize_discussion(
                        session_id=SESSION_ID,
                        workspace_version=1,
                        target=FormalizationTarget.PLAN_REVISION,
                        user_confirmed=True,
                    )
            finally:
                svc_session.commit = original_commit
                svc_session.rollback = original_rollback

            assert commit_attempts[0] == 1
            assert rollback_count[0] == 1

            # Session still usable — no manual rollback needed
            usable = svc_session.execute(select(func.count()).select_from(ProjectDirectorPlanVersionTable)).scalar_one()
            assert usable == 0

            # Fresh session: no PlanVersion
            fresh = db_session_factory()
            try:
                count = fresh.execute(
                    select(func.count()).select_from(ProjectDirectorPlanVersionTable)
                ).scalar_one()
                assert count == 0
            finally:
                fresh.close()
        finally:
            svc_session.close()


# ===========================================================================
# §11.6 Transaction count matrix
# ===========================================================================


class TestTransactionMatrix:
    """§6 Verify commit/rollback counts for each code path using instance-scoped spy."""

    def test_success_create_commit_rollback(self, db_session):
        _seed_ready_to_formalize(db_session)
        svc = _build_formalization_service(db_session, provider_configured=False)
        with SessionTransactionSpy(db_session) as txspy:
            result = svc.formalize_discussion(
                session_id=SESSION_ID, workspace_version=1,
                target=FormalizationTarget.PLAN_REVISION, user_confirmed=True,
            )
        assert txspy.commit_count == 1
        assert txspy.rollback_count == 0
        assert result.idempotent_replay is False

    def test_idempotent_replay_no_extra_commit(self, db_session):
        _seed_ready_to_formalize(db_session)
        svc = _build_formalization_service(db_session, provider_configured=False)
        svc.formalize_discussion(
            session_id=SESSION_ID, workspace_version=1,
            target=FormalizationTarget.PLAN_REVISION, user_confirmed=True,
        )
        with SessionTransactionSpy(db_session) as txspy:
            svc.formalize_discussion(
                session_id=SESSION_ID, workspace_version=1,
                target=FormalizationTarget.PLAN_REVISION, user_confirmed=True,
            )
        assert txspy.commit_count == 0
        assert txspy.rollback_count == 0

    @pytest.mark.parametrize(
        "label,setup_kwargs",
        [
            ("user_confirmed=False", {"user_confirmed": False}),
            ("workspace_version_mismatch", {"workspace_version": 999}),
        ],
    )
    def test_gate_failure_no_commit_rollback(self, db_session, label, setup_kwargs):
        _seed_ready_to_formalize(db_session)
        svc = _build_formalization_service(db_session, provider_configured=False)
        kwargs = {"session_id": SESSION_ID, "workspace_version": 1,
                  "target": FormalizationTarget.PLAN_REVISION, "user_confirmed": True}
        kwargs.update(setup_kwargs)
        with SessionTransactionSpy(db_session) as txspy:
            with pytest.raises(ValueError):
                svc.formalize_discussion(**kwargs)
        assert txspy.commit_count == 0
        assert txspy.rollback_count == 1
        assert _count_plan_versions(db_session) == 0

    def test_history_ahead_transaction(self, db_session):
        msg_id = _seed_message(db_session)
        evt1 = _make_event(sequence_no=1, event_type=DiscussionEventType.TOPIC_SET,
                           content="主题", source_message_ids=[msg_id])
        evt2 = _make_event(sequence_no=2, event_type=DiscussionEventType.FORMALIZATION_REQUESTED,
                           content="请求", source_message_ids=[msg_id])
        _persist_event(db_session, evt1)
        _persist_event(db_session, evt2)
        _seed_session(db_session)
        ws = _make_workspace(topic="主题", discussion_status=DiscussionStatus.READY_TO_FORMALIZE,
                             version_no=1, last_event_sequence_no=1)
        _persist_workspace(db_session, ws)
        svc = _build_formalization_service(db_session, provider_configured=False)
        with SessionTransactionSpy(db_session) as txspy:
            with pytest.raises(ValueError, match="event_history_ahead"):
                svc.formalize_discussion(
                    session_id=SESSION_ID, workspace_version=1,
                    target=FormalizationTarget.PLAN_REVISION, user_confirmed=True,
                )
        assert txspy.commit_count == 0
        assert txspy.rollback_count == 1

    def test_source_message_not_found_transaction(self, db_session):
        _seed_session(db_session)
        fake_msg_id = uuid4()
        evt = _make_event(sequence_no=1, event_type=DiscussionEventType.TOPIC_SET,
                          content="主题", source_message_ids=[fake_msg_id])
        _persist_event(db_session, evt)
        ws = _make_workspace(topic="主题", discussion_status=DiscussionStatus.EXPLORING,
                             version_no=1, last_event_sequence_no=1)
        _persist_workspace(db_session, ws)
        svc = _build_formalization_service(db_session, provider_configured=False)
        with SessionTransactionSpy(db_session) as txspy:
            with pytest.raises(ValueError, match="source_message_not_found"):
                svc.formalize_discussion(
                    session_id=SESSION_ID, workspace_version=1,
                    target=FormalizationTarget.PLAN_REVISION, user_confirmed=True,
                )
        assert txspy.commit_count == 0
        assert txspy.rollback_count == 1


# ===========================================================================
# §11.7 Expanded fresh session readback — full side-effect verification
# ===========================================================================


class TestFreshSessionFullReadback:
    """§7 Fresh session verifies no side-effects beyond the PlanVersion."""

    def test_fresh_session_no_side_effects(self, db_session_factory):
        """Full before/after snapshot: Project, Session, Message, Event, Workspace, counts."""
        # ── Setup ─────────────────────────────────────────────────────────
        setup = db_session_factory()
        try:
            _seed_ready_to_formalize(setup)
            setup.commit()

            # ── Pre-snapshot: counts ──────────────────────────────────────
            pre_counts = {
                "project": _count_table(setup, ProjectTable),
                "pv": _count_table(setup, ProjectDirectorPlanVersionTable),
                "task": _count_table(setup, TaskTable),
                "run": _count_table(setup, RunTable),
                "agent_session": _count_agent_sessions(setup),
                "msg": _count_table(setup, ProjectDirectorMessageTable),
                "evt": _count_table(setup, ProjectDirectorDiscussionEventTable),
                "ws": _count_table(setup, ProjectDirectorDiscussionWorkspaceTable),
            }

            # ── Pre-snapshot: Project ─────────────────────────────────────
            proj_row = setup.get(ProjectTable, PROJECT_ID)
            pre_proj = {c: getattr(proj_row, c) for c in [
                "id", "name", "summary", "status", "stage",
                "sop_template_code", "stage_history_json", "team_assembly_json",
                "team_policy_json", "budget_policy_json",
            ]} if proj_row else None

            # ── Pre-snapshot: Session ─────────────────────────────────────
            sess_repo = ProjectDirectorSessionRepository(setup)
            pre_sess = sess_repo.get_by_id(SESSION_ID)
            pre_sess_snap = {k: getattr(pre_sess, k) for k in [
                "id", "project_id", "goal_text", "goal_summary", "constraints",
                "status", "confirmed_at", "clarifying_questions", "clarifying_answers",
            ]}

            # ── Pre-snapshot: Messages ────────────────────────────────────
            msg_repo = ProjectDirectorMessageRepository(setup)
            pre_msgs, _ = msg_repo.list_by_session_id(session_id=SESSION_ID)
            pre_msg_snaps = [{k: getattr(m, k) for k in [
                "id", "session_id", "role", "content", "sequence_no",
                "source", "source_detail", "risk_level",
            ]} for m in pre_msgs]

            # ── Pre-snapshot: Events ──────────────────────────────────────
            evt_repo = ProjectDirectorDiscussionEventRepository(setup)
            pre_evts = evt_repo.list_by_session_id(session_id=SESSION_ID)
            pre_evt_snaps = [{k: getattr(e, k) for k in [
                "id", "session_id", "project_id", "sequence_no", "event_type",
                "subject_key", "content", "status", "payload",
                "source_message_ids", "supersedes_event_id", "created_by", "confidence",
            ]} for e in pre_evts]

            # ── Pre-snapshot: Workspace ───────────────────────────────────
            ws_repo = ProjectDirectorDiscussionWorkspaceRepository(setup)
            pre_ws = ws_repo.get_by_session_id(session_id=SESSION_ID)
            pre_ws_dump = pre_ws.model_dump() if pre_ws else None

            # ── Execute formalization ─────────────────────────────────────
            svc = _build_formalization_service(setup, provider_configured=False)
            result = svc.formalize_discussion(
                session_id=SESSION_ID, workspace_version=1,
                target=FormalizationTarget.PLAN_REVISION, user_confirmed=True,
            )
            pv_id = result.plan_version.id
            setup.commit()
        finally:
            setup.close()

        # ── Fresh session post-snapshot ───────────────────────────────────
        fresh = db_session_factory()
        try:
            # Counts
            post_counts = {
                "project": _count_table(fresh, ProjectTable),
                "pv": _count_table(fresh, ProjectDirectorPlanVersionTable),
                "task": _count_table(fresh, TaskTable),
                "run": _count_table(fresh, RunTable),
                "agent_session": _count_agent_sessions(fresh),
                "msg": _count_table(fresh, ProjectDirectorMessageTable),
                "evt": _count_table(fresh, ProjectDirectorDiscussionEventTable),
                "ws": _count_table(fresh, ProjectDirectorDiscussionWorkspaceTable),
            }
            assert post_counts["project"] == pre_counts["project"]
            assert post_counts["pv"] == pre_counts["pv"] + 1
            assert post_counts["task"] == pre_counts["task"]
            assert post_counts["run"] == pre_counts["run"]
            assert post_counts["agent_session"] == pre_counts["agent_session"]
            assert post_counts["msg"] == pre_counts["msg"]
            assert post_counts["evt"] == pre_counts["evt"]
            assert post_counts["ws"] == pre_counts["ws"]

            # PlanVersion content
            repo = ProjectDirectorPlanVersionRepository(fresh)
            readback = repo.get_by_id(pv_id)
            assert readback is not None
            assert readback.formalization_target == FormalizationTarget.PLAN_REVISION
            assert readback.formalization_workspace_version == 1
            assert list(readback.formalization_source_message_ids) == list(result.source_message_ids)
            assert list(readback.formalization_source_event_ids) == list(result.source_event_ids)
            assert readback.status == PlanVersionStatus.PENDING_CONFIRMATION
            assert readback.confirmed_at is None

            # Project unchanged
            proj_row = fresh.get(ProjectTable, PROJECT_ID)
            assert proj_row is not None
            for c in ["id", "name", "summary", "status", "stage",
                       "sop_template_code", "stage_history_json", "team_assembly_json",
                       "team_policy_json", "budget_policy_json"]:
                assert getattr(proj_row, c) == pre_proj[c], f"Project.{c} changed"

            # Session unchanged — full snapshot
            sess_repo = ProjectDirectorSessionRepository(fresh)
            post_sess = sess_repo.get_by_id(SESSION_ID)
            assert post_sess is not None
            for k in ["id", "project_id", "goal_text", "goal_summary", "constraints",
                       "status", "confirmed_at", "clarifying_questions", "clarifying_answers"]:
                assert getattr(post_sess, k) == pre_sess_snap[k], f"Session.{k} changed"

            # Messages unchanged — content snapshot
            msg_repo = ProjectDirectorMessageRepository(fresh)
            post_msgs, _ = msg_repo.list_by_session_id(session_id=SESSION_ID)
            assert len(post_msgs) == len(pre_msg_snaps)
            for post_m, pre_snap in zip(post_msgs, pre_msg_snaps):
                for k, v in pre_snap.items():
                    assert getattr(post_m, k) == v, f"Message.{k} changed"

            # Events unchanged — content snapshot
            evt_repo = ProjectDirectorDiscussionEventRepository(fresh)
            post_evts = evt_repo.list_by_session_id(session_id=SESSION_ID)
            assert len(post_evts) == len(pre_evt_snaps)
            for post_e, pre_snap in zip(post_evts, pre_evt_snaps):
                for k, v in pre_snap.items():
                    actual = getattr(post_e, k)
                    # payload comparison: normalize dicts
                    if k == "payload":
                        assert actual == v, f"Event.{k} changed"
                    else:
                        assert actual == v, f"Event.{k} changed"

            # Workspace unchanged — full model_dump
            ws_repo = ProjectDirectorDiscussionWorkspaceRepository(fresh)
            post_ws = ws_repo.get_by_session_id(session_id=SESSION_ID)
            assert post_ws is not None
            post_ws_dump = post_ws.model_dump()
            for key in ["session_id", "project_id", "topic", "discussion_status",
                        "active_option_ids", "preferred_option_id", "active_constraint_ids",
                        "open_question_ids", "temporary_conclusion_ids", "confirmed_decision_ids",
                        "latest_user_correction_event_id", "version_no", "last_event_sequence_no"]:
                assert post_ws_dump[key] == pre_ws_dump[key], f"Workspace.{key} changed"
        finally:
            fresh.close()

    def test_gate_failure_no_half_persisted_plan_version(self, db_session_factory):
        """After a gate failure, fresh session confirms no PlanVersion was created."""
        setup = db_session_factory()
        try:
            _seed_ready_to_formalize(setup)
            setup.commit()
        finally:
            setup.close()

        svc_session = db_session_factory()
        try:
            svc = _build_formalization_service(svc_session, provider_configured=False)
            with pytest.raises(ValueError, match="workspace_version_mismatch"):
                svc.formalize_discussion(
                    session_id=SESSION_ID, workspace_version=999,
                    target=FormalizationTarget.PLAN_REVISION, user_confirmed=True,
                )
        finally:
            svc_session.close()

        fresh = db_session_factory()
        try:
            assert _count_table(fresh, ProjectDirectorPlanVersionTable) == 0
            assert _count_table(fresh, TaskTable) == 0
            assert _count_table(fresh, RunTable) == 0
            assert _count_agent_sessions(fresh) == 0
        finally:
            fresh.close()


# ===========================================================================
# §11.8 Worker/Executor static boundary
# ===========================================================================


class TestWorkerExecutorBoundary:
    """§8 Static contract: formalization chain must not reference Worker/Executor."""

    def test_formalization_service_no_worker_references(self):
        """Read the formalization service source and verify no Worker/Executor calls."""
        import inspect as stdlib_inspect
        from app.services.project_director_discussion_formalization_service import (
            ProjectDirectorDiscussionFormalizationService,
        )
        source = stdlib_inspect.getsource(ProjectDirectorDiscussionFormalizationService)
        forbidden = [
            "WorkerPool", "worker_pool", "create_task", "create_run",
            "AgentSessionService", "planning/apply", "apply-local",
            "LocalGitWriteService",
        ]
        for term in forbidden:
            assert term not in source, f"Forbidden term {term!r} found in formalization service"

    def test_formalize_route_no_worker_references(self):
        """Read the formalize route source and verify no Worker/Executor calls."""
        import inspect as stdlib_inspect
        from app.api.routes.project_director import formalize_discussion, _get_discussion_formalization_service
        for func in (formalize_discussion, _get_discussion_formalization_service):
            source = stdlib_inspect.getsource(func)
            forbidden = [
                "WorkerPool", "worker_pool", "create_task", "create_run",
                "AgentSessionService", "planning/apply", "apply-local",
                "LocalGitWriteService",
            ]
            for term in forbidden:
                assert term not in source, f"Forbidden term {term!r} found in {func.__name__}"


# ===========================================================================
# §12 Plan review lifecycle with provenance
# ===========================================================================


class TestPlanReviewLifecycle:
    """§12 Confirm, reject, supersede, request_changes on formalized PlanVersions."""

    def _create_formalized_plan(self, db_session) -> ProjectDirectorPlanVersion:
        _seed_ready_to_formalize(db_session)
        svc = _build_formalization_service(db_session, provider_configured=False)
        result = svc.formalize_discussion(
            session_id=SESSION_ID,
            workspace_version=1,
            target=FormalizationTarget.PLAN_REVISION,
            user_confirmed=True,
        )
        return result.plan_version

    def test_reject_preserves_provenance(self, db_session):
        pv = self._create_formalized_plan(db_session)
        original_target = pv.formalization_target
        original_ws_version = pv.formalization_workspace_version
        original_msg_ids = list(pv.formalization_source_message_ids)
        original_evt_ids = list(pv.formalization_source_event_ids)

        repo = ProjectDirectorPlanVersionRepository(db_session)
        plan_svc = ProjectDirectorPlanService(
            plan_version_repository=repo,
            session_repository=ProjectDirectorSessionRepository(db_session),
            provider_config_service=_FakeProviderConfigService(configured=False),
        )
        rejected = plan_svc.reject_plan_version(pv.id)
        assert rejected.status == PlanVersionStatus.REJECTED
        assert rejected.formalization_target == original_target
        assert rejected.formalization_workspace_version == original_ws_version
        assert list(rejected.formalization_source_message_ids) == original_msg_ids
        assert list(rejected.formalization_source_event_ids) == original_evt_ids

    def test_confirm_preserves_provenance(self, db_session):
        pv = self._create_formalized_plan(db_session)
        original_target = pv.formalization_target
        original_ws_version = pv.formalization_workspace_version
        original_msg_ids = list(pv.formalization_source_message_ids)
        original_evt_ids = list(pv.formalization_source_event_ids)

        repo = ProjectDirectorPlanVersionRepository(db_session)
        plan_svc = ProjectDirectorPlanService(
            plan_version_repository=repo,
            session_repository=ProjectDirectorSessionRepository(db_session),
            provider_config_service=_FakeProviderConfigService(configured=False),
        )
        confirmed = plan_svc.confirm_plan_version(pv.id)
        assert confirmed.status == PlanVersionStatus.CONFIRMED
        assert confirmed.formalization_target == original_target
        assert confirmed.formalization_workspace_version == original_ws_version
        assert list(confirmed.formalization_source_message_ids) == original_msg_ids
        assert list(confirmed.formalization_source_event_ids) == original_evt_ids

    def test_supersede_preserves_old_provenance(self, db_session):
        pv = self._create_formalized_plan(db_session)
        original_target = pv.formalization_target
        original_ws_version = pv.formalization_workspace_version
        original_msg_ids = list(pv.formalization_source_message_ids)
        original_evt_ids = list(pv.formalization_source_event_ids)

        repo = ProjectDirectorPlanVersionRepository(db_session)
        plan_svc = ProjectDirectorPlanService(
            plan_version_repository=repo,
            session_repository=ProjectDirectorSessionRepository(db_session),
            provider_config_service=_FakeProviderConfigService(configured=False),
        )
        # Confirm A
        plan_svc.confirm_plan_version(pv.id)

        # Create a plain pending_confirmation B
        pv_b = ProjectDirectorPlanVersion(
            id=uuid4(),
            session_id=SESSION_ID,
            version_no=2,
            plan_summary="新计划",
            status=PlanVersionStatus.PENDING_CONFIRMATION,
        )
        repo.create(pv_b)
        # Confirm B → supersedes A
        confirmed_b = plan_svc.confirm_plan_version(pv_b.id)

        # Read back A
        old_a = repo.get_by_id(pv.id)
        assert old_a is not None
        assert old_a.status == PlanVersionStatus.SUPERSEDED
        # A provenance unchanged
        assert old_a.formalization_target == original_target
        assert old_a.formalization_workspace_version == original_ws_version
        assert list(old_a.formalization_source_message_ids) == original_msg_ids
        assert list(old_a.formalization_source_event_ids) == original_evt_ids

        # B is confirmed, plain plan version
        assert confirmed_b.status == PlanVersionStatus.CONFIRMED
        assert confirmed_b.formalization_target is None
        assert confirmed_b.formalization_workspace_version is None
        assert confirmed_b.formalization_source_message_ids == []
        assert confirmed_b.formalization_source_event_ids == []

    def test_request_changes_creates_replacement_without_provenance(self, db_session):
        pv = self._create_formalized_plan(db_session)
        original_target = pv.formalization_target
        original_ws_version = pv.formalization_workspace_version
        original_msg_ids = list(pv.formalization_source_message_ids)
        original_evt_ids = list(pv.formalization_source_event_ids)

        repo = ProjectDirectorPlanVersionRepository(db_session)
        provider_spy = _ProviderSpy()
        plan_svc = ProjectDirectorPlanService(
            plan_version_repository=repo,
            session_repository=ProjectDirectorSessionRepository(db_session),
            provider_config_service=_FakeProviderConfigService(configured=True),
            provider_text_generator=provider_spy,
        )
        rejected, replacement = plan_svc.request_changes(
            plan_version_id=pv.id, feedback="需要修改"
        )

        # Original should be rejected with provenance unchanged
        original = repo.get_by_id(pv.id)
        assert original.status == PlanVersionStatus.REJECTED
        assert original.formalization_target == original_target
        assert original.formalization_workspace_version == original_ws_version
        assert list(original.formalization_source_message_ids) == original_msg_ids
        assert list(original.formalization_source_event_ids) == original_evt_ids

        # Replacement is a plain plan version — strict empty provenance
        assert replacement.formalization_target is None
        assert replacement.formalization_workspace_version is None
        assert replacement.formalization_source_message_ids == []
        assert replacement.formalization_source_event_ids == []

        # No unique index violation
        assert _count_plan_versions(db_session) == 2


# ===========================================================================
# §13 API tests
# ===========================================================================


class TestApiSuccess:
    """§13.1 Successful API call returns correct response."""

    def test_formalize_api_success(self, db_session, client):
        _seed_ready_to_formalize(db_session)
        db_session.commit()

        resp = client.post(
            f"/project-director/sessions/{SESSION_ID}/discussion/formalize",
            json={
                "workspace_version": 1,
                "target": "plan_revision",
                "user_confirmed": True,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["session_id"] == str(SESSION_ID)
        assert data["workspace_version"] == 1
        assert data["target"] == "plan_revision"
        assert isinstance(data["source_message_ids"], list)
        assert isinstance(data["source_event_ids"], list)
        assert len(data["source_message_ids"]) > 0
        assert len(data["source_event_ids"]) > 0
        assert data["idempotent_replay"] is False

        # Safety guard flags
        assert data["task_created"] is False
        assert data["run_created"] is False
        assert data["worker_started"] is False
        assert data["executor_started"] is False
        assert data["repository_write_performed"] is False
        assert data["gate_conclusion"] == "Partial"

        # PlanVersion provenance in response
        pv = data["plan_version"]
        assert pv["formalization_target"] == "plan_revision"
        assert pv["formalization_workspace_version"] == 1
        assert len(pv["formalization_source_message_ids"]) > 0
        assert len(pv["formalization_source_event_ids"]) > 0


class TestApiIdempotency:
    """§13.2 API idempotent replay."""

    def test_api_idempotent_replay(self, db_session, client):
        _seed_ready_to_formalize(db_session)
        db_session.commit()

        resp1 = client.post(
            f"/project-director/sessions/{SESSION_ID}/discussion/formalize",
            json={
                "workspace_version": 1,
                "target": "plan_revision",
                "user_confirmed": True,
            },
        )
        assert resp1.status_code == 201

        resp2 = client.post(
            f"/project-director/sessions/{SESSION_ID}/discussion/formalize",
            json={
                "workspace_version": 1,
                "target": "plan_revision",
                "user_confirmed": True,
            },
        )
        assert resp2.status_code == 201
        assert resp2.json()["idempotent_replay"] is True
        assert resp2.json()["plan_version"]["id"] == resp1.json()["plan_version"]["id"]


class TestApiErrorMapping:
    """§13.3 API error status code mapping."""

    def test_session_not_found_404(self, client):
        resp = client.post(
            f"/project-director/sessions/{uuid4()}/discussion/formalize",
            json={
                "workspace_version": 1,
                "target": "plan_revision",
                "user_confirmed": True,
            },
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_user_not_confirmed_409(self, db_session, client):
        _seed_ready_to_formalize(db_session)
        db_session.commit()

        resp = client.post(
            f"/project-director/sessions/{SESSION_ID}/discussion/formalize",
            json={
                "workspace_version": 1,
                "target": "plan_revision",
                "user_confirmed": False,
            },
        )
        assert resp.status_code == 409
        assert "user_confirmation_required" in resp.json()["detail"]

    def test_session_not_confirmed_409(self, db_session, client):
        _seed_session(db_session)
        row = db_session.get(ProjectDirectorSessionTable, SESSION_ID)
        row.status = ProjectDirectorSessionStatus.CLARIFYING
        db_session.commit()

        resp = client.post(
            f"/project-director/sessions/{SESSION_ID}/discussion/formalize",
            json={
                "workspace_version": 1,
                "target": "plan_revision",
                "user_confirmed": True,
            },
        )
        assert resp.status_code == 409
        assert "session_not_confirmed" in resp.json()["detail"]

    def test_workspace_not_found_409(self, db_session, client):
        _seed_session(db_session)
        db_session.commit()

        resp = client.post(
            f"/project-director/sessions/{SESSION_ID}/discussion/formalize",
            json={
                "workspace_version": 1,
                "target": "plan_revision",
                "user_confirmed": True,
            },
        )
        assert resp.status_code == 409
        assert "workspace_not_found" in resp.json()["detail"]

    def test_workspace_version_mismatch_409(self, db_session, client):
        _seed_ready_to_formalize(db_session, workspace_version=1)
        db_session.commit()

        resp = client.post(
            f"/project-director/sessions/{SESSION_ID}/discussion/formalize",
            json={
                "workspace_version": 2,
                "target": "plan_revision",
                "user_confirmed": True,
            },
        )
        assert resp.status_code == 409
        assert "workspace_version_mismatch" in resp.json()["detail"]

    def test_workspace_version_zero_422(self, db_session, client):
        _seed_ready_to_formalize(db_session, workspace_version=0)
        db_session.commit()

        resp = client.post(
            f"/project-director/sessions/{SESSION_ID}/discussion/formalize",
            json={
                "workspace_version": 0,
                "target": "plan_revision",
                "user_confirmed": True,
            },
        )
        assert resp.status_code == 422
        # Pydantic catches workspace_version=0 at request validation level
        detail = resp.json()["detail"]
        assert isinstance(detail, list)
        assert any("workspace_version" in str(err.get("loc", [])) for err in detail)

    def test_provider_generation_failure_422(self, db_session_factory, client):
        # Setup in one session
        setup = db_session_factory()
        try:
            _seed_ready_to_formalize(setup)
            setup.commit()
        finally:
            setup.close()

        configured_config = SimpleNamespace(
            api_key="test-key",
            base_url="https://provider.invalid/v1",
            timeout_seconds=1,
            detected_provider_type="openai_compatible",
            model_names={"balanced": "test-model"},
        )

        with (
            patch(
                "app.services.provider_config_service.ProviderConfigService.resolve_openai_runtime_config",
                return_value=configured_config,
            ) as resolve_mock,
            patch(
                "app.services.project_director_plan_service.ProjectDirectorPlanService._call_provider_text",
                side_effect=RuntimeError("provider exploded"),
            ) as provider_mock,
        ):
            resp = client.post(
                f"/project-director/sessions/{SESSION_ID}/discussion/formalize",
                json={
                    "workspace_version": 1,
                    "target": "plan_revision",
                    "user_confirmed": True,
                },
            )

        assert resp.status_code == 422
        assert "provider_generation_failed" in resp.json()["detail"]
        assert resolve_mock.call_count == 1
        assert provider_mock.call_count == 1

        # Fresh session: full no-side-effect verification
        fresh = db_session_factory()
        try:
            assert _count_table(fresh, ProjectDirectorPlanVersionTable) == 0
            assert _count_table(fresh, TaskTable) == 0
            assert _count_table(fresh, RunTable) == 0
            assert _count_agent_sessions(fresh) == 0

            # Session content unchanged
            sess_repo = ProjectDirectorSessionRepository(fresh)
            sess = sess_repo.get_by_id(SESSION_ID)
            assert sess is not None
            assert sess.status == ProjectDirectorSessionStatus.CONFIRMED
            assert sess.goal_text == "测试目标：构建一个系统"

            # Message content unchanged
            msg_repo = ProjectDirectorMessageRepository(fresh)
            msgs, _ = msg_repo.list_by_session_id(session_id=SESSION_ID)
            assert len(msgs) == 1
            assert msgs[0].role == ProjectDirectorMessageRole.USER

            # Event content unchanged
            evt_repo = ProjectDirectorDiscussionEventRepository(fresh)
            evts = evt_repo.list_by_session_id(session_id=SESSION_ID)
            assert len(evts) == 1
            assert evts[0].event_type == DiscussionEventType.TOPIC_SET

            # Workspace content unchanged
            ws_repo = ProjectDirectorDiscussionWorkspaceRepository(fresh)
            ws = ws_repo.get_by_session_id(session_id=SESSION_ID)
            assert ws is not None
            assert ws.topic == "测试主题"
            assert ws.version_no == 1
        finally:
            fresh.close()


class TestApiNormalMessageNoAutoFormalize:
    """§13.4 Normal message API does not auto-formalize."""

    def test_normal_message_no_plan_version_created(self, db_session_factory, client):
        # Setup
        setup = db_session_factory()
        try:
            _seed_session(setup)
            msg_id = _seed_message(setup)
            evt = _make_event(
                sequence_no=1,
                event_type=DiscussionEventType.TOPIC_SET,
                content="主题",
                source_message_ids=[msg_id],
            )
            _persist_event(setup, evt)
            ws = _make_workspace(
                topic="主题",
                discussion_status=DiscussionStatus.EXPLORING,
                version_no=1,
                last_event_sequence_no=1,
            )
            _persist_workspace(setup, ws)
            setup.commit()

            pre_pv_count = setup.execute(
                select(func.count()).select_from(ProjectDirectorPlanVersionTable)
            ).scalar_one()
        finally:
            setup.close()

        # Submit a normal message — expect 201 (existing contract)
        resp = client.post(
            f"/project-director/sessions/{SESSION_ID}/messages",
            json={"content": "请帮我正式化"},
        )
        assert resp.status_code == 201

        # Fresh session: PlanVersion count unchanged, no execution entities
        fresh = db_session_factory()
        try:
            assert _count_table(fresh, ProjectDirectorPlanVersionTable) == pre_pv_count
            assert _count_table(fresh, TaskTable) == 0
            assert _count_table(fresh, RunTable) == 0
            assert _count_agent_sessions(fresh) == 0
        finally:
            fresh.close()


# ===========================================================================
# §14 Existing API compatibility
# ===========================================================================


class TestExistingApiCompatibility:
    """§14 Existing plan version APIs still work with formalization fields."""

    def test_create_plain_plan_version_api(self, db_session, client):
        """POST /sessions/{id}/plan-versions still creates plain plan versions."""
        _seed_session(db_session)
        db_session.commit()

        resp = client.post(
            f"/project-director/sessions/{SESSION_ID}/plan-versions",
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["formalization_target"] is None
        assert data["formalization_workspace_version"] is None
        assert data["formalization_source_message_ids"] == []
        assert data["formalization_source_event_ids"] == []

    def test_list_plan_versions_includes_formalization(self, db_session, client):
        _seed_ready_to_formalize(db_session)
        db_session.commit()

        # Create a formalized plan version
        resp_create = client.post(
            f"/project-director/sessions/{SESSION_ID}/discussion/formalize",
            json={
                "workspace_version": 1,
                "target": "plan_revision",
                "user_confirmed": True,
            },
        )
        assert resp_create.status_code == 201

        # List should include formalization fields
        resp = client.get(f"/project-director/sessions/{SESSION_ID}/plan-versions")
        assert resp.status_code == 200
        versions = resp.json()["plan_versions"]
        assert len(versions) > 0
        formalized = versions[0]
        assert formalized["formalization_target"] == "plan_revision"
        assert formalized["formalization_workspace_version"] == 1
        assert len(formalized["formalization_source_message_ids"]) > 0
        assert len(formalized["formalization_source_event_ids"]) > 0

    def test_get_single_plan_version_has_provenance(self, db_session, client):
        """GET /plan-versions/{id} returns formalization provenance."""
        _seed_ready_to_formalize(db_session)
        db_session.commit()

        resp_create = client.post(
            f"/project-director/sessions/{SESSION_ID}/discussion/formalize",
            json={
                "workspace_version": 1,
                "target": "plan_revision",
                "user_confirmed": True,
            },
        )
        assert resp_create.status_code == 201
        pv_id = resp_create.json()["plan_version"]["id"]

        resp = client.get(f"/project-director/plan-versions/{pv_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["formalization_target"] == "plan_revision"
        assert data["formalization_workspace_version"] == 1
        assert data["formalization_source_message_ids"] == resp_create.json()["source_message_ids"]
        assert data["formalization_source_event_ids"] == resp_create.json()["source_event_ids"]

    def test_confirm_plan_version_preserves_provenance(self, db_session, client):
        """POST /plan-versions/{id}/confirm preserves formalization provenance."""
        _seed_ready_to_formalize(db_session)
        db_session.commit()

        resp_create = client.post(
            f"/project-director/sessions/{SESSION_ID}/discussion/formalize",
            json={
                "workspace_version": 1,
                "target": "plan_revision",
                "user_confirmed": True,
            },
        )
        assert resp_create.status_code == 201
        pv_id = resp_create.json()["plan_version"]["id"]
        original_msg_ids = resp_create.json()["source_message_ids"]
        original_evt_ids = resp_create.json()["source_event_ids"]

        resp = client.post(f"/project-director/plan-versions/{pv_id}/confirm")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "confirmed"
        assert data["formalization_target"] == "plan_revision"
        assert data["formalization_source_message_ids"] == original_msg_ids
        assert data["formalization_source_event_ids"] == original_evt_ids

    def test_reject_plan_version_preserves_provenance(self, db_session, client):
        """POST /plan-versions/{id}/review reject preserves formalization provenance."""
        _seed_ready_to_formalize(db_session)
        db_session.commit()

        resp_create = client.post(
            f"/project-director/sessions/{SESSION_ID}/discussion/formalize",
            json={
                "workspace_version": 1,
                "target": "plan_revision",
                "user_confirmed": True,
            },
        )
        assert resp_create.status_code == 201
        pv_id = resp_create.json()["plan_version"]["id"]
        original_msg_ids = resp_create.json()["source_message_ids"]
        original_evt_ids = resp_create.json()["source_event_ids"]

        resp = client.post(
            f"/project-director/plan-versions/{pv_id}/review",
            json={"action": "reject", "feedback": "需要修改"},
        )
        assert resp.status_code == 200
        data = resp.json()["reviewed_plan_version"]
        assert data["status"] == "rejected"
        assert data["formalization_target"] == "plan_revision"
        assert data["formalization_source_message_ids"] == original_msg_ids
        assert data["formalization_source_event_ids"] == original_evt_ids

    def test_request_changes_api_creates_replacement(self, db_session_factory, client):
        """POST /plan-versions/{id}/review request_changes: original rejected with
        provenance, replacement is a plain plan version with no provenance."""
        # Setup
        setup = db_session_factory()
        try:
            _seed_ready_to_formalize(setup)
            setup.commit()
            pre_pv_count = setup.execute(
                select(func.count()).select_from(ProjectDirectorPlanVersionTable)
            ).scalar_one()
        finally:
            setup.close()

        # Create formalized plan version
        resp_create = client.post(
            f"/project-director/sessions/{SESSION_ID}/discussion/formalize",
            json={
                "workspace_version": 1,
                "target": "plan_revision",
                "user_confirmed": True,
            },
        )
        assert resp_create.status_code == 201
        pv_id = resp_create.json()["plan_version"]["id"]
        original_msg_ids = resp_create.json()["source_message_ids"]
        original_evt_ids = resp_create.json()["source_event_ids"]

        # Request changes
        resp = client.post(
            f"/project-director/plan-versions/{pv_id}/review",
            json={"action": "request_changes", "feedback": "需要调整范围"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "request_changes"

        # Original: rejected, provenance unchanged
        reviewed = data["reviewed_plan_version"]
        assert reviewed["status"] == "rejected"
        assert reviewed["formalization_target"] == "plan_revision"
        assert reviewed["formalization_source_message_ids"] == original_msg_ids
        assert reviewed["formalization_source_event_ids"] == original_evt_ids

        # Replacement: plain plan version, no provenance
        replacement = data["replacement_plan_version"]
        assert replacement is not None
        assert replacement["status"] == "pending_confirmation"
        assert replacement["formalization_target"] is None
        assert replacement["formalization_workspace_version"] is None
        assert replacement["formalization_source_message_ids"] == []
        assert replacement["formalization_source_event_ids"] == []

        # Fresh session: PlanVersion count increased by 2, no execution entities
        fresh = db_session_factory()
        try:
            assert _count_table(fresh, ProjectDirectorPlanVersionTable) == pre_pv_count + 2
            assert _count_table(fresh, TaskTable) == 0
            assert _count_table(fresh, RunTable) == 0
            assert _count_agent_sessions(fresh) == 0
        finally:
            fresh.close()
