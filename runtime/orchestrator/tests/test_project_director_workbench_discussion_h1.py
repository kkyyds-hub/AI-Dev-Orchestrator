"""Tests for P26-H1 workbench discussion and formalization integration.

Covers: workbench resume default contract, workspace readback, historical
formalization versions, core regression scenarios, all resume branches,
new workspace versions, and read-only verification.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.router import api_router
from app.api.routes.project_director import _get_service, get_workbench_resume
from app.core.db import begin_sqlite_transaction, configure_sqlite, get_db_session
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


class _NoProviderConfigService:
    def resolve_openai_runtime_config(self):
        return OpenAIProviderRuntimeConfig(
            **{"api" + "_key": None},
            base_url="https://example.invalid/v1",
            timeout_seconds=1,
            source="none",
            detected_provider_type="openai_compatible",
            model_preset="openai",
            model_names={"economy": "m", "balanced": "m", "premium": "m"},
        )


def _count(session: Session, table) -> int:
    return session.execute(select(func.count()).select_from(table)).scalar_one()


def _seed_project(db_session: Session, *, project_id=PROJECT_ID):
    if db_session.get(ProjectTable, project_id) is not None:
        return
    row = ProjectTable(
        id=project_id,
        name="测试项目",
        summary="测试摘要",
        status="active",
        stage="planning",
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )
    db_session.add(row)
    db_session.flush()


def _seed_session(
    db_session: Session,
    *,
    session_id=SESSION_ID,
    project_id=PROJECT_ID,
    status=ProjectDirectorSessionStatus.CONFIRMED,
):
    if db_session.get(ProjectDirectorSessionTable, session_id) is not None:
        return
    _seed_project(db_session, project_id=project_id)
    row = ProjectDirectorSessionTable(
        id=session_id,
        project_id=project_id,
        goal_text="测试目标",
        constraints="",
        status=status,
        clarifying_questions_json="[]",
        clarifying_answers_json="[]",
        goal_summary="测试摘要",
        confirmed_at=FIXED_TIME if status == ProjectDirectorSessionStatus.CONFIRMED else None,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )
    db_session.add(row)
    db_session.flush()


def _seed_message(db_session: Session, session_id=SESSION_ID, *, sequence_no=1):
    if db_session.get(ProjectDirectorSessionTable, session_id) is None:
        _seed_session(db_session, session_id=session_id)
    mid = uuid4()
    row = ProjectDirectorMessageTable(
        id=mid,
        session_id=session_id,
        role=ProjectDirectorMessageRole.USER,
        content="用户消息",
        sequence_no=sequence_no,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail="test",
        created_at=FIXED_TIME,
    )
    db_session.add(row)
    db_session.flush()
    return mid


def _seed_event(
    db_session: Session,
    session_id=SESSION_ID,
    *,
    project_id=PROJECT_ID,
    sequence_no=1,
    event_type=DiscussionEventType.TOPIC_SET,
    content="主题",
    source_message_ids=None,
    payload=None,
    supersedes_event_id=None,
):
    eid = uuid4()
    if source_message_ids is None:
        source_message_ids = [_seed_message(db_session, session_id=session_id)]
    row = ProjectDirectorDiscussionEventTable(
        id=eid,
        session_id=session_id,
        project_id=project_id,
        sequence_no=sequence_no,
        event_type=event_type,
        subject_key="topic",
        content=content,
        status=DiscussionEventStatus.ACTIVE,
        payload_json=json.dumps(payload or {}, default=str),
        source_message_ids_json=json.dumps([str(m) for m in source_message_ids]),
        supersedes_event_id=supersedes_event_id,
        created_by=DiscussionActorClaim.USER_EXPLICIT,
        confidence=1.0,
        idempotency_key=f"test-{eid}",
        created_at=FIXED_TIME,
    )
    db_session.add(row)
    db_session.flush()
    return eid


def _seed_workspace(
    db_session: Session,
    session_id=SESSION_ID,
    *,
    project_id=PROJECT_ID,
    topic="测试主题",
    discussion_status=DiscussionStatus.EXPLORING,
    version_no=1,
    last_event_sequence_no=1,
    active_option_ids=None,
    preferred_option_id=None,
    active_constraint_ids=None,
    open_question_ids=None,
    temporary_conclusion_ids=None,
    confirmed_decision_ids=None,
    latest_user_correction_event_id=None,
):
    state = {
        "active_option_ids": [str(i) for i in (active_option_ids or [])],
        "preferred_option_id": str(preferred_option_id) if preferred_option_id else None,
        "active_constraint_ids": [str(i) for i in (active_constraint_ids or [])],
        "open_question_ids": [str(i) for i in (open_question_ids or [])],
        "temporary_conclusion_ids": [str(i) for i in (temporary_conclusion_ids or [])],
        "confirmed_decision_ids": [str(i) for i in (confirmed_decision_ids or [])],
        "latest_user_correction_event_id": (
            str(latest_user_correction_event_id) if latest_user_correction_event_id else None
        ),
    }
    existing = db_session.get(ProjectDirectorDiscussionWorkspaceTable, session_id)
    now = datetime.now(timezone.utc)
    if existing is not None:
        existing.topic = topic
        existing.discussion_status = discussion_status
        existing.state_json = json.dumps(state)
        existing.version_no = version_no
        existing.last_event_sequence_no = last_event_sequence_no
        existing.updated_at = now
    else:
        row = ProjectDirectorDiscussionWorkspaceTable(
            session_id=session_id,
            project_id=project_id,
            topic=topic,
            discussion_status=discussion_status,
            state_json=json.dumps(state),
            version_no=version_no,
            last_event_sequence_no=last_event_sequence_no,
            created_at=now,
            updated_at=now,
        )
        db_session.add(row)
    db_session.flush()


def _seed_plan_version(
    db_session: Session,
    session_id=SESSION_ID,
    *,
    version_no=1,
    status=PlanVersionStatus.PENDING_CONFIRMATION,
    formalization_target=None,
    formalization_workspace_version=None,
    formalization_source_message_ids=None,
    formalization_source_event_ids=None,
):
    pv = ProjectDirectorPlanVersion(
        id=uuid4(),
        session_id=session_id,
        version_no=version_no,
        plan_summary="测试计划",
        status=status,
        source="rule_fallback",
        source_detail="test",
        formalization_target=formalization_target,
        formalization_workspace_version=formalization_workspace_version,
        formalization_source_message_ids=formalization_source_message_ids or [],
        formalization_source_event_ids=formalization_source_event_ids or [],
    )
    from app.repositories.project_director_plan_version_repository import (
        ProjectDirectorPlanVersionRepository,
    )
    repo = ProjectDirectorPlanVersionRepository(db_session)
    return repo.create(pv)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_engine(tmp_path):
    db_path = tmp_path / "p26h1-test.db"
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
# §5.1 Default contract
# ===========================================================================


class TestDefaultContract:
    """WorkbenchResumeResponse() defaults."""

    def test_default_response(self):
        from app.api.routes.project_director import WorkbenchResumeResponse

        resp = WorkbenchResumeResponse()
        assert resp.session is None
        assert resp.plan_version is None
        assert resp.task_creation is None
        assert resp.recent_messages == []
        assert resp.discussion_workspace is None
        assert resp.existing_formalization_workspace_versions == []
        assert resp.source == "none"


# ===========================================================================
# §5.2 DiscussionWorkspace readback
# ===========================================================================


class TestWorkspaceReadback:
    """Workspace fields in Resume response."""

    def test_workspace_fields_complete(self, db_session, client):
        _seed_project(db_session)
        _seed_session(db_session, project_id=None)
        _seed_event(db_session, sequence_no=1, project_id=None)
        _seed_workspace(
            db_session,
            project_id=None,
            topic="测试主题",
            discussion_status=DiscussionStatus.READY_TO_FORMALIZE,
            version_no=1,
            last_event_sequence_no=1,
        )
        db_session.commit()

        resp = client.get(
            "/project-director/workbench/resume",
            params={"mode": "new-project", "session_id": str(SESSION_ID)},
        )
        assert resp.status_code == 200
        data = resp.json()
        ws = data["discussion_workspace"]
        assert ws is not None
        assert ws["session_id"] == str(SESSION_ID)
        assert ws["project_id"] is None
        assert ws["topic"] == "测试主题"
        assert ws["discussion_status"] == "ready_to_formalize"
        assert isinstance(ws["active_option_ids"], list)
        assert ws["preferred_option_id"] is None
        assert isinstance(ws["active_constraint_ids"], list)
        assert isinstance(ws["open_question_ids"], list)
        assert isinstance(ws["temporary_conclusion_ids"], list)
        assert isinstance(ws["confirmed_decision_ids"], list)
        assert ws["latest_user_correction_event_id"] is None
        assert ws["version_no"] == 1
        assert ws["last_event_sequence_no"] == 1
        assert "created_at" in ws
        assert "updated_at" in ws

    def test_workspace_no_p27_fields(self, db_session, client):
        _seed_project(db_session)
        _seed_session(db_session, project_id=None)
        _seed_event(db_session, sequence_no=1, project_id=None)
        _seed_workspace(db_session, project_id=None)
        db_session.commit()

        resp = client.get(
            "/project-director/workbench/resume",
            params={"mode": "new-project", "session_id": str(SESSION_ID)},
        )
        ws = resp.json()["discussion_workspace"]
        for forbidden in [
            "source_surface", "source_entity_type", "source_entity_id",
            "trigger_type", "interaction_case_id", "external_context_pack_id",
        ]:
            assert forbidden not in ws, f"P27 field {forbidden!r} leaked into workspace response"

    def test_response_no_secrets(self, db_session, client):
        _seed_project(db_session)
        _seed_session(db_session, project_id=None)
        _seed_event(db_session, sequence_no=1, project_id=None)
        _seed_workspace(db_session, project_id=None)
        db_session.commit()

        resp = client.get(
            "/project-director/workbench/resume",
            params={"mode": "new-project", "session_id": str(SESSION_ID)},
        )
        body = json.dumps(resp.json())
        for forbidden in ["api_key", "Authorization", "Bearer", "prompt", "Event JSON"]:
            assert forbidden not in body


# ===========================================================================
# §5.3 Historical formalization workspace versions
# ===========================================================================


class TestHistoricalFormalizationVersions:
    """_existing_formalization_workspace_versions collects all formalized versions."""

    def test_all_statuses_collected(self, db_session):
        _seed_session(db_session)
        msg_id = _seed_message(db_session)
        for v in [1, 2, 3, 4]:
            _seed_event(db_session, sequence_no=v)
        _seed_workspace(db_session, version_no=4, last_event_sequence_no=4)

        # v1: pending_confirmation
        _seed_plan_version(
            db_session, version_no=1,
            formalization_target=FormalizationTarget.PLAN_REVISION,
            formalization_workspace_version=1,
            formalization_source_message_ids=[msg_id],
            formalization_source_event_ids=[_seed_event(db_session, sequence_no=10 + 1)],
            status=PlanVersionStatus.PENDING_CONFIRMATION,
        )
        # v2: confirmed
        _seed_plan_version(
            db_session, version_no=2,
            formalization_target=FormalizationTarget.PLAN_REVISION,
            formalization_workspace_version=2,
            formalization_source_message_ids=[msg_id],
            formalization_source_event_ids=[_seed_event(db_session, sequence_no=10 + 2)],
            status=PlanVersionStatus.CONFIRMED,
        )
        # v3: rejected
        _seed_plan_version(
            db_session, version_no=3,
            formalization_target=FormalizationTarget.PLAN_REVISION,
            formalization_workspace_version=3,
            formalization_source_message_ids=[msg_id],
            formalization_source_event_ids=[_seed_event(db_session, sequence_no=10 + 3)],
            status=PlanVersionStatus.REJECTED,
        )
        # v4: superseded
        _seed_plan_version(
            db_session, version_no=4,
            formalization_target=FormalizationTarget.PLAN_REVISION,
            formalization_workspace_version=4,
            formalization_source_message_ids=[msg_id],
            formalization_source_event_ids=[_seed_event(db_session, sequence_no=10 + 4)],
            status=PlanVersionStatus.SUPERSEDED,
        )
        # Plain plan version (no formalization)
        _seed_plan_version(db_session, version_no=5)

        db_session.commit()

        from app.api.routes.project_director import _existing_formalization_workspace_versions
        repo = ProjectDirectorPlanVersionRepository(db_session)
        versions = _existing_formalization_workspace_versions(
            plan_repo=repo, session_id=SESSION_ID,
        )
        assert versions == [1, 2, 3, 4]

    def test_rejected_and_superseded_included(self, db_session):
        _seed_session(db_session)
        msg_id = _seed_message(db_session)
        _seed_event(db_session, sequence_no=1)
        _seed_workspace(db_session, version_no=2, last_event_sequence_no=1)

        _seed_plan_version(
            db_session, version_no=1,
            formalization_target=FormalizationTarget.PLAN_REVISION,
            formalization_workspace_version=1,
            formalization_source_message_ids=[msg_id],
            formalization_source_event_ids=[uuid4()],
            status=PlanVersionStatus.REJECTED,
        )
        _seed_plan_version(
            db_session, version_no=2,
            formalization_target=FormalizationTarget.PLAN_REVISION,
            formalization_workspace_version=2,
            formalization_source_message_ids=[msg_id],
            formalization_source_event_ids=[uuid4()],
            status=PlanVersionStatus.SUPERSEDED,
        )
        db_session.commit()

        from app.api.routes.project_director import _existing_formalization_workspace_versions
        repo = ProjectDirectorPlanVersionRepository(db_session)
        versions = _existing_formalization_workspace_versions(
            plan_repo=repo, session_id=SESSION_ID,
        )
        assert 1 in versions
        assert 2 in versions

    def test_plain_plan_excluded(self, db_session):
        _seed_session(db_session)
        _seed_plan_version(db_session, version_no=1)
        db_session.commit()

        from app.api.routes.project_director import _existing_formalization_workspace_versions
        repo = ProjectDirectorPlanVersionRepository(db_session)
        versions = _existing_formalization_workspace_versions(
            plan_repo=repo, session_id=SESSION_ID,
        )
        assert versions == []


# ===========================================================================
# §5.4 Core regression: rejected A + replacement B
# ===========================================================================


class TestCoreRegression:
    """Rejected formalized A + plain replacement B → resume returns B."""

    def test_resume_returns_replacement_not_rejected(self, db_session, client):
        _seed_project(db_session)
        _seed_session(db_session, project_id=None)
        msg_id = _seed_message(db_session)
        _seed_event(db_session, sequence_no=1, project_id=None)
        _seed_workspace(
            db_session,
            project_id=None,
            discussion_status=DiscussionStatus.READY_TO_FORMALIZE,
            version_no=1,
            last_event_sequence_no=1,
        )

        # A: rejected formalized
        _seed_plan_version(
            db_session, version_no=1,
            formalization_target=FormalizationTarget.PLAN_REVISION,
            formalization_workspace_version=1,
            formalization_source_message_ids=[msg_id],
            formalization_source_event_ids=[uuid4()],
            status=PlanVersionStatus.REJECTED,
        )
        # B: plain replacement, higher version_no
        _seed_plan_version(db_session, version_no=2, status=PlanVersionStatus.PENDING_CONFIRMATION)
        db_session.commit()

        resp = client.get(
            "/project-director/workbench/resume",
            params={"mode": "new-project", "session_id": str(SESSION_ID)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_version"]["id"] == str(
            ProjectDirectorPlanVersionRepository(db_session)
            .list_by_session_id(SESSION_ID)[0].id
        )
        assert data["plan_version"]["status"] == "pending_confirmation"
        assert data["plan_version"]["formalization_target"] is None
        assert data["discussion_workspace"]["version_no"] == 1
        assert data["discussion_workspace"]["discussion_status"] == "ready_to_formalize"
        assert data["existing_formalization_workspace_versions"] == [1]


# ===========================================================================
# §5.5 All Resume branches
# ===========================================================================


class TestResumeBranches:
    """Cover all Resume endpoint branches."""

    def test_explicit_session_id(self, db_session, client):
        _seed_project(db_session)
        _seed_session(db_session, project_id=None)
        _seed_event(db_session, sequence_no=1, project_id=None)
        _seed_workspace(db_session, project_id=None)
        db_session.commit()

        resp = client.get(
            "/project-director/workbench/resume",
            params={"mode": "new-project", "session_id": str(SESSION_ID)},
        )
        assert resp.status_code == 200
        assert resp.json()["session"]["id"] == str(SESSION_ID)

    def test_empty_database(self, client):
        resp = client.get("/project-director/workbench/resume")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session"] is None
        assert data["source"] == "none"
        assert data["existing_formalization_workspace_versions"] == []

    def test_project_mode_with_matching_project(self, db_session, client):
        _seed_session(db_session, project_id=PROJECT_ID)
        _seed_event(db_session, sequence_no=1)
        _seed_workspace(db_session)
        db_session.commit()

        resp = client.get(
            "/project-director/workbench/resume",
            params={"mode": "project", "project_id": str(PROJECT_ID)},
        )
        assert resp.status_code == 200
        assert resp.json()["session"] is not None

    def test_project_mode_mismatch_returns_empty(self, db_session, client):
        _seed_session(db_session, project_id=PROJECT_ID)
        db_session.commit()

        other_project = uuid4()
        resp = client.get(
            "/project-director/workbench/resume",
            params={"mode": "project", "project_id": str(other_project)},
        )
        assert resp.status_code == 200
        assert resp.json()["session"] is None

    def test_session_context_mismatch_422(self, db_session, client):
        _seed_session(db_session, project_id=PROJECT_ID)
        db_session.commit()

        resp = client.get(
            "/project-director/workbench/resume",
            params={
                "mode": "new-project",
                "session_id": str(SESSION_ID),
            },
        )
        # Session has project_id but mode=new-project requires project_id=None
        assert resp.status_code == 422

    def test_nonexistent_session_404(self, client):
        resp = client.get(
            "/project-director/workbench/resume",
            params={"mode": "new-project", "session_id": str(uuid4())},
        )
        assert resp.status_code == 404


# ===========================================================================
# §5.6 New workspace version
# ===========================================================================


class TestNewWorkspaceVersion:
    """New workspace version not yet formalized."""

    def test_current_version_not_in_existing(self, db_session, client):
        _seed_project(db_session)
        _seed_session(db_session, project_id=None)
        msg_id = _seed_message(db_session)
        _seed_event(db_session, sequence_no=1, project_id=None)
        _seed_event(db_session, sequence_no=2, project_id=None)
        _seed_workspace(db_session, project_id=None, version_no=2, last_event_sequence_no=2)

        # Only v1 was formalized
        _seed_plan_version(
            db_session, version_no=1,
            formalization_target=FormalizationTarget.PLAN_REVISION,
            formalization_workspace_version=1,
            formalization_source_message_ids=[msg_id],
            formalization_source_event_ids=[uuid4()],
        )
        db_session.commit()

        resp = client.get(
            "/project-director/workbench/resume",
            params={"mode": "new-project", "session_id": str(SESSION_ID)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["existing_formalization_workspace_versions"] == [1]
        assert data["discussion_workspace"]["version_no"] == 2


# ===========================================================================
# §5.7 Resume read-only verification
# ===========================================================================


class TestResumeReadOnly:
    """Resume must not write to any table."""

    def test_resume_no_side_effects(self, db_session_factory, client):
        setup = db_session_factory()
        try:
            _seed_project(setup)
            _seed_session(setup, project_id=None)
            _seed_event(setup, sequence_no=1, project_id=None)
            _seed_workspace(setup, project_id=None)
            setup.commit()

            pre_counts = {
                "project": _count(setup, ProjectTable),
                "session": _count(setup, ProjectDirectorSessionTable),
                "msg": _count(setup, ProjectDirectorMessageTable),
                "evt": _count(setup, ProjectDirectorDiscussionEventTable),
                "ws": _count(setup, ProjectDirectorDiscussionWorkspaceTable),
                "pv": _count(setup, ProjectDirectorPlanVersionTable),
                "task": _count(setup, TaskTable),
                "run": _count(setup, RunTable),
                "agent_session": _count(setup, AgentSessionTable),
            }
        finally:
            setup.close()

        resp = client.get(
            "/project-director/workbench/resume",
            params={"mode": "new-project", "session_id": str(SESSION_ID)},
        )
        assert resp.status_code == 200

        fresh = db_session_factory()
        try:
            post_counts = {
                "project": _count(fresh, ProjectTable),
                "session": _count(fresh, ProjectDirectorSessionTable),
                "msg": _count(fresh, ProjectDirectorMessageTable),
                "evt": _count(fresh, ProjectDirectorDiscussionEventTable),
                "ws": _count(fresh, ProjectDirectorDiscussionWorkspaceTable),
                "pv": _count(fresh, ProjectDirectorPlanVersionTable),
                "task": _count(fresh, TaskTable),
                "run": _count(fresh, RunTable),
                "agent_session": _count(fresh, AgentSessionTable),
            }
            for key in pre_counts:
                assert post_counts[key] == pre_counts[key], f"{key} count changed"
        finally:
            fresh.close()
