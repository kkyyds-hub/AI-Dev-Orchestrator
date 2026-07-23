"""Tests for P26-H1 workbench discussion and formalization integration.

Covers: workbench resume default contract, workspace readback with non-empty
fields, historical formalization versions, core regression scenarios, all
resume branches (explicit session, recent-plan, recent-session, empty, project
mode, new-project mode), dual-project isolation, workspace v2 lifecycle,
and full read-only content snapshots.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.router import api_router
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
    DiscussionEventStatus,
    DiscussionEventType,
    DiscussionStatus,
)
from app.domain.project_director_message import (
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_plan_version import PlanVersionStatus
from app.domain.project_director_session import ProjectDirectorSessionStatus
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.services.provider_config_service import OpenAIProviderRuntimeConfig


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SESSION_ID = UUID("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
PROJECT_ID = UUID("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
SESSION_B_ID = UUID("cccccccccccccccccccccccccccccccc")
PROJECT_B_ID = UUID("dddddddddddddddddddddddddddddddd")
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


def _seed_project(db_session, *, project_id=PROJECT_ID, name="测试项目"):
    if db_session.get(ProjectTable, project_id) is not None:
        return
    db_session.add(ProjectTable(
        id=project_id, name=name, summary=f"{name}摘要",
        status="active", stage="planning",
        created_at=FIXED_TIME, updated_at=FIXED_TIME,
    ))
    db_session.flush()


def _seed_session(db_session, *, session_id=SESSION_ID, project_id=PROJECT_ID,
                  status=ProjectDirectorSessionStatus.CONFIRMED, goal_text="测试目标"):
    if db_session.get(ProjectDirectorSessionTable, session_id) is not None:
        return
    if project_id is not None:
        _seed_project(db_session, project_id=project_id)
    db_session.add(ProjectDirectorSessionTable(
        id=session_id, project_id=project_id, goal_text=goal_text,
        constraints="约束条件", status=status,
        clarifying_questions_json="[]", clarifying_answers_json="[]",
        goal_summary=f"{goal_text}摘要",
        confirmed_at=FIXED_TIME if status == ProjectDirectorSessionStatus.CONFIRMED else None,
        created_at=FIXED_TIME, updated_at=FIXED_TIME,
    ))
    db_session.flush()


def _seed_message(db_session, session_id=SESSION_ID, *, sequence_no=1, content="用户消息"):
    if db_session.get(ProjectDirectorSessionTable, session_id) is None:
        _seed_session(db_session, session_id=session_id)
    mid = uuid4()
    db_session.add(ProjectDirectorMessageTable(
        id=mid, session_id=session_id, role=ProjectDirectorMessageRole.USER,
        content=content, sequence_no=sequence_no,
        source=ProjectDirectorMessageSource.SYSTEM, source_detail="test",
        risk_level="low", created_at=FIXED_TIME,
    ))
    db_session.flush()
    return mid


def _seed_event(db_session, session_id=SESSION_ID, *, project_id=PROJECT_ID,
                sequence_no=1, event_type=DiscussionEventType.TOPIC_SET,
                content="主题", source_message_ids=None, payload=None):
    eid = uuid4()
    if source_message_ids is None:
        source_message_ids = [_seed_message(db_session, session_id=session_id)]
    db_session.add(ProjectDirectorDiscussionEventTable(
        id=eid, session_id=session_id, project_id=project_id,
        sequence_no=sequence_no, event_type=event_type,
        subject_key="topic", content=content,
        status=DiscussionEventStatus.ACTIVE,
        payload_json=json.dumps(payload or {}, default=str),
        source_message_ids_json=json.dumps([str(m) for m in source_message_ids]),
        supersedes_event_id=None, created_by=DiscussionActorClaim.USER_EXPLICIT,
        confidence=1.0, idempotency_key=f"test-{eid}", created_at=FIXED_TIME,
    ))
    db_session.flush()
    return eid


def _seed_workspace(db_session, session_id=SESSION_ID, *, project_id=PROJECT_ID,
                    topic="测试主题", discussion_status=DiscussionStatus.EXPLORING,
                    version_no=1, last_event_sequence_no=1,
                    active_option_ids=None, preferred_option_id=None,
                    active_constraint_ids=None, open_question_ids=None,
                    temporary_conclusion_ids=None, confirmed_decision_ids=None,
                    latest_user_correction_event_id=None):
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
        db_session.add(ProjectDirectorDiscussionWorkspaceTable(
            session_id=session_id, project_id=project_id,
            topic=topic, discussion_status=discussion_status,
            state_json=json.dumps(state), version_no=version_no,
            last_event_sequence_no=last_event_sequence_no,
            created_at=now, updated_at=now,
        ))
    db_session.flush()


def _seed_plan_version(db_session, session_id=SESSION_ID, *, version_no=1,
                       project_id=None,
                       status=PlanVersionStatus.PENDING_CONFIRMATION,
                       formalization_target=None, formalization_workspace_version=None,
                       formalization_source_message_ids=None,
                       formalization_source_event_ids=None):
    from app.domain.project_director_plan_version import ProjectDirectorPlanVersion
    pv = ProjectDirectorPlanVersion(
        id=uuid4(), session_id=session_id, project_id=project_id,
        version_no=version_no, plan_summary="测试计划", status=status,
        source="rule_fallback", source_detail="test",
        formalization_target=formalization_target,
        formalization_workspace_version=formalization_workspace_version,
        formalization_source_message_ids=formalization_source_message_ids or [],
        formalization_source_event_ids=formalization_source_event_ids or [],
    )
    return ProjectDirectorPlanVersionRepository(db_session).create(pv)


def _snapshot_state(session: Session, session_id: UUID, project_id: UUID | None) -> dict:
    """Capture all business state as stable primitive values before closing session."""
    proj = None
    if project_id is not None:
        row = session.execute(select(ProjectTable).where(ProjectTable.id == project_id)).scalar_one_or_none()
        if row:
            proj = {c: getattr(row, c) for c in [
                "id", "name", "summary", "status", "stage",
                "sop_template_code", "stage_history_json", "team_assembly_json",
                "team_policy_json", "budget_policy_json",
            ]}

    sess_row = session.execute(select(ProjectDirectorSessionTable).where(
        ProjectDirectorSessionTable.id == session_id)).scalar_one_or_none()
    sess = {c: getattr(sess_row, c) for c in [
        "id", "project_id", "goal_text", "goal_summary", "constraints",
        "status", "clarifying_questions_json", "clarifying_answers_json", "confirmed_at",
    ]} if sess_row else None

    msgs = [{c: getattr(r, c) for c in [
        "id", "session_id", "role", "content", "sequence_no",
        "source", "source_detail", "risk_level",
    ]} for r in session.execute(select(ProjectDirectorMessageTable).where(
        ProjectDirectorMessageTable.session_id == session_id
    ).order_by(ProjectDirectorMessageTable.sequence_no, ProjectDirectorMessageTable.id)).scalars().all()]

    evts = [{c: getattr(r, c) for c in [
        "id", "session_id", "project_id", "sequence_no", "event_type",
        "subject_key", "content", "status", "payload_json",
        "source_message_ids_json", "supersedes_event_id", "created_by", "confidence",
    ]} for r in session.execute(select(ProjectDirectorDiscussionEventTable).where(
        ProjectDirectorDiscussionEventTable.session_id == session_id
    ).order_by(ProjectDirectorDiscussionEventTable.sequence_no, ProjectDirectorDiscussionEventTable.id)).scalars().all()]

    ws_row = session.execute(select(ProjectDirectorDiscussionWorkspaceTable).where(
        ProjectDirectorDiscussionWorkspaceTable.session_id == session_id)).scalar_one_or_none()
    ws = {c: getattr(ws_row, c) for c in [
        "session_id", "project_id", "topic", "discussion_status",
        "state_json", "version_no", "last_event_sequence_no",
    ]} if ws_row else None

    pvs = [{c: getattr(r, c) for c in [
        "id", "session_id", "project_id", "version_no", "status",
        "formalization_target", "formalization_workspace_version",
        "formalization_source_message_ids_json", "formalization_source_event_ids_json",
    ]} for r in session.execute(select(ProjectDirectorPlanVersionTable).where(
        ProjectDirectorPlanVersionTable.session_id == session_id
    ).order_by(ProjectDirectorPlanVersionTable.version_no, ProjectDirectorPlanVersionTable.id)).scalars().all()]

    counts = {
        "project": _count(session, ProjectTable),
        "session": _count(session, ProjectDirectorSessionTable),
        "msg": _count(session, ProjectDirectorMessageTable),
        "evt": _count(session, ProjectDirectorDiscussionEventTable),
        "ws": _count(session, ProjectDirectorDiscussionWorkspaceTable),
        "pv": _count(session, ProjectDirectorPlanVersionTable),
        "task": _count(session, TaskTable),
        "run": _count(session, RunTable),
        "agent_session": _count(session, AgentSessionTable),
    }

    return {"project": proj, "session": sess, "messages": msgs, "events": evts,
            "workspace": ws, "plan_versions": pvs, "counts": counts}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_engine(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'p26h1.db').as_posix()}")
    event.listen(engine, "connect", configure_sqlite)
    event.listen(engine, "begin", begin_sqlite_transaction)
    ORMBase.metadata.create_all(bind=engine)
    return engine


@pytest.fixture()
def db_session(db_engine):
    s = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, expire_on_commit=False)()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def db_session_factory(db_engine):
    return sessionmaker(bind=db_engine, autoflush=False, autocommit=False, expire_on_commit=False)


@pytest.fixture()
def client(db_engine):
    app = FastAPI()
    app.include_router(api_router)
    factory = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db_session] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ===========================================================================
# §5.1 Default contract
# ===========================================================================


class TestDefaultContract:

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
# §5.2 Workspace readback with non-empty fields
# ===========================================================================


class TestWorkspaceReadback:

    def test_workspace_non_empty_fields(self, db_session, client):
        opt_id = uuid4()
        pref_id = opt_id
        con_id = uuid4()
        oq_id = uuid4()
        tc_id = uuid4()
        cd_id = uuid4()
        corr_id = uuid4()

        _seed_session(db_session, project_id=None)
        _seed_event(db_session, sequence_no=1, project_id=None)
        _seed_workspace(
            db_session, project_id=None,
            topic="讨论主题", discussion_status=DiscussionStatus.READY_TO_FORMALIZE,
            version_no=1, last_event_sequence_no=1,
            active_option_ids=[opt_id], preferred_option_id=pref_id,
            active_constraint_ids=[con_id], open_question_ids=[oq_id],
            temporary_conclusion_ids=[tc_id], confirmed_decision_ids=[cd_id],
            latest_user_correction_event_id=corr_id,
        )
        db_session.commit()

        resp = client.get("/project-director/workbench/resume",
                          params={"mode": "new-project", "session_id": str(SESSION_ID)})
        assert resp.status_code == 200
        ws = resp.json()["discussion_workspace"]
        assert ws["session_id"] == str(SESSION_ID)
        assert ws["project_id"] is None
        assert ws["topic"] == "讨论主题"
        assert ws["discussion_status"] == "ready_to_formalize"
        assert ws["active_option_ids"] == [str(opt_id)]
        assert ws["preferred_option_id"] == str(pref_id)
        assert ws["active_constraint_ids"] == [str(con_id)]
        assert ws["open_question_ids"] == [str(oq_id)]
        assert ws["temporary_conclusion_ids"] == [str(tc_id)]
        assert ws["confirmed_decision_ids"] == [str(cd_id)]
        assert ws["latest_user_correction_event_id"] == str(corr_id)
        assert ws["version_no"] == 1
        assert ws["last_event_sequence_no"] == 1

    def test_workspace_no_p27_fields(self, db_session, client):
        _seed_session(db_session, project_id=None)
        _seed_event(db_session, sequence_no=1, project_id=None)
        _seed_workspace(db_session, project_id=None)
        db_session.commit()

        resp = client.get("/project-director/workbench/resume",
                          params={"mode": "new-project", "session_id": str(SESSION_ID)})
        ws = resp.json()["discussion_workspace"]
        for f in ["source_surface", "source_entity_type", "source_entity_id",
                   "trigger_type", "interaction_case_id", "external_context_pack_id"]:
            assert f not in ws

    def test_response_no_secrets(self, db_session, client):
        _seed_session(db_session, project_id=None)
        _seed_event(db_session, sequence_no=1, project_id=None)
        _seed_workspace(db_session, project_id=None)
        db_session.commit()

        resp = client.get("/project-director/workbench/resume",
                          params={"mode": "new-project", "session_id": str(SESSION_ID)})
        body = json.dumps(resp.json())
        for f in ["api_key", "Authorization", "Bearer", "prompt", "Event JSON"]:
            assert f not in body


# ===========================================================================
# §5.3 Historical formalization workspace versions
# ===========================================================================


class TestHistoricalFormalizationVersions:

    def test_all_statuses_collected_sorted(self, db_session):
        _seed_session(db_session)
        msg_id = _seed_message(db_session)
        for v in range(1, 5):
            _seed_event(db_session, sequence_no=v)
        _seed_workspace(db_session, version_no=4, last_event_sequence_no=4)

        for v, st in [(1, PlanVersionStatus.PENDING_CONFIRMATION),
                       (2, PlanVersionStatus.CONFIRMED),
                       (3, PlanVersionStatus.REJECTED),
                       (4, PlanVersionStatus.SUPERSEDED)]:
            _seed_plan_version(
                db_session, version_no=v,
                formalization_target=FormalizationTarget.PLAN_REVISION,
                formalization_workspace_version=v,
                formalization_source_message_ids=[msg_id],
                formalization_source_event_ids=[uuid4()], status=st,
            )
        _seed_plan_version(db_session, version_no=5)  # plain
        db_session.commit()

        from app.api.routes.project_director import _existing_formalization_workspace_versions
        versions = _existing_formalization_workspace_versions(
            plan_repo=ProjectDirectorPlanVersionRepository(db_session), session_id=SESSION_ID,
        )
        assert versions == [1, 2, 3, 4]
        assert versions == sorted(versions)

    def test_plain_plan_excluded(self, db_session):
        _seed_session(db_session)
        _seed_plan_version(db_session, version_no=1)
        db_session.commit()

        from app.api.routes.project_director import _existing_formalization_workspace_versions
        versions = _existing_formalization_workspace_versions(
            plan_repo=ProjectDirectorPlanVersionRepository(db_session), session_id=SESSION_ID,
        )
        assert versions == []


# ===========================================================================
# §5.4 Core regression: rejected A + replacement B
# ===========================================================================


class TestCoreRegression:

    def test_resume_returns_b_not_a(self, db_session, client):
        _seed_session(db_session, project_id=None)
        msg_id = _seed_message(db_session)
        _seed_event(db_session, sequence_no=1, project_id=None)
        _seed_workspace(db_session, project_id=None,
                        discussion_status=DiscussionStatus.READY_TO_FORMALIZE,
                        version_no=1, last_event_sequence_no=1)

        plan_a = _seed_plan_version(
            db_session, version_no=1,
            formalization_target=FormalizationTarget.PLAN_REVISION,
            formalization_workspace_version=1,
            formalization_source_message_ids=[msg_id],
            formalization_source_event_ids=[uuid4()],
            status=PlanVersionStatus.REJECTED,
        )
        plan_b = _seed_plan_version(
            db_session, version_no=2, status=PlanVersionStatus.PENDING_CONFIRMATION,
        )
        db_session.commit()

        resp = client.get("/project-director/workbench/resume",
                          params={"mode": "new-project", "session_id": str(SESSION_ID)})
        assert resp.status_code == 200
        data = resp.json()

        assert data["plan_version"]["id"] == str(plan_b.id)
        assert data["plan_version"]["id"] != str(plan_a.id)
        assert data["plan_version"]["status"] == "pending_confirmation"
        assert data["plan_version"]["formalization_target"] is None
        assert data["plan_version"]["formalization_workspace_version"] is None
        assert data["discussion_workspace"]["version_no"] == 1
        assert data["discussion_workspace"]["discussion_status"] == "ready_to_formalize"
        assert data["existing_formalization_workspace_versions"] == [1]


# ===========================================================================
# §5.5 All Resume branches
# ===========================================================================


class TestResumeBranches:

    def test_explicit_session_branch(self, db_session, client):
        """Explicit session_id → returns that session's workspace and existing versions."""
        _seed_session(db_session, project_id=None)
        _seed_event(db_session, sequence_no=1, project_id=None)
        _seed_workspace(db_session, project_id=None, topic="显式主题", version_no=2)
        _seed_plan_version(
            db_session, version_no=1,
            formalization_target=FormalizationTarget.PLAN_REVISION,
            formalization_workspace_version=1,
            formalization_source_message_ids=[uuid4()],
            formalization_source_event_ids=[uuid4()],
        )
        db_session.commit()

        resp = client.get("/project-director/workbench/resume",
                          params={"mode": "new-project", "session_id": str(SESSION_ID)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["session"]["id"] == str(SESSION_ID)
        assert data["session"]["project_id"] is None
        assert data["discussion_workspace"]["session_id"] == str(SESSION_ID)
        assert data["discussion_workspace"]["topic"] == "显式主题"
        assert data["discussion_workspace"]["version_no"] == 2
        assert data["existing_formalization_workspace_versions"] == [1]

    def test_recent_plan_branch(self, db_session, client):
        """No session_id, has pending formalized plan → source=backend_recent_plan."""
        _seed_session(db_session, project_id=None)
        msg_id = _seed_message(db_session)
        _seed_event(db_session, sequence_no=1, project_id=None)
        _seed_workspace(db_session, project_id=None, topic="最近计划主题", version_no=1)
        plan = _seed_plan_version(
            db_session, version_no=1,
            formalization_target=FormalizationTarget.PLAN_REVISION,
            formalization_workspace_version=1,
            formalization_source_message_ids=[msg_id],
            formalization_source_event_ids=[uuid4()],
            status=PlanVersionStatus.PENDING_CONFIRMATION,
        )
        db_session.commit()

        resp = client.get("/project-director/workbench/resume", params={"mode": "new-project"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "backend_recent_plan"
        assert data["session"]["id"] == str(SESSION_ID)
        assert data["plan_version"]["id"] == str(plan.id)
        assert data["plan_version"]["status"] == "pending_confirmation"
        assert data["plan_version"]["formalization_target"] == "plan_revision"
        assert data["plan_version"]["formalization_workspace_version"] == 1
        assert data["discussion_workspace"]["topic"] == "最近计划主题"
        assert data["discussion_workspace"]["version_no"] == 1
        assert data["existing_formalization_workspace_versions"] == [1]

    def test_recent_session_branch(self, db_session, client):
        """No session_id, no resumable plan, only superseded → source=backend_recent_session."""
        _seed_session(db_session, project_id=None)
        msg_id = _seed_message(db_session)
        _seed_event(db_session, sequence_no=1, project_id=None)
        _seed_workspace(db_session, project_id=None, topic="最近会话主题", version_no=1)
        superseded = _seed_plan_version(
            db_session, version_no=1,
            formalization_target=FormalizationTarget.PLAN_REVISION,
            formalization_workspace_version=1,
            formalization_source_message_ids=[msg_id],
            formalization_source_event_ids=[uuid4()],
            status=PlanVersionStatus.SUPERSEDED,
        )
        db_session.commit()

        resp = client.get("/project-director/workbench/resume", params={"mode": "new-project"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "backend_recent_session"
        assert data["session"]["id"] == str(SESSION_ID)
        assert data["plan_version"] is None
        assert data["discussion_workspace"]["session_id"] == str(SESSION_ID)
        assert data["discussion_workspace"]["topic"] == "最近会话主题"
        assert data["discussion_workspace"]["version_no"] == 1
        assert data["existing_formalization_workspace_versions"] == [1]

    def test_empty_database_branch(self, client):
        resp = client.get("/project-director/workbench/resume")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session"] is None
        assert data["plan_version"] is None
        assert data["discussion_workspace"] is None
        assert data["existing_formalization_workspace_versions"] == []
        assert data["source"] == "none"

    def test_project_mode(self, db_session, client):
        _seed_session(db_session, project_id=PROJECT_ID)
        _seed_event(db_session, sequence_no=1)
        _seed_workspace(db_session)
        db_session.commit()

        resp = client.get("/project-director/workbench/resume",
                          params={"mode": "project", "project_id": str(PROJECT_ID)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["session"]["id"] == str(SESSION_ID)
        assert data["session"]["project_id"] == str(PROJECT_ID)
        assert data["discussion_workspace"]["project_id"] == str(PROJECT_ID)

    def test_new_project_mode_no_project_row(self, db_session, client):
        """new-project mode with unbound session → Project count stays 0."""
        _seed_session(db_session, project_id=None)
        _seed_event(db_session, sequence_no=1, project_id=None)
        _seed_workspace(db_session, project_id=None)
        db_session.commit()

        assert _count(db_session, ProjectTable) == 0

        resp = client.get("/project-director/workbench/resume", params={"mode": "new-project"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["session"]["id"] == str(SESSION_ID)
        assert data["session"]["project_id"] is None
        assert data["discussion_workspace"]["project_id"] is None

    def test_context_mismatch_422(self, db_session, client):
        _seed_session(db_session, project_id=PROJECT_ID)
        db_session.commit()
        resp = client.get("/project-director/workbench/resume",
                          params={"mode": "new-project", "session_id": str(SESSION_ID)})
        assert resp.status_code == 422

    def test_nonexistent_session_404(self, client):
        resp = client.get("/project-director/workbench/resume",
                          params={"mode": "new-project", "session_id": str(uuid4())})
        assert resp.status_code == 404


# ===========================================================================
# §5.6 Dual-project isolation
# ===========================================================================


class TestDualProjectIsolation:

    def test_projects_do_not_cross(self, db_session, client):
        """Project A and B with different data must not cross."""
        # Project A: version=1, formalization=[1], pending plan
        _seed_session(db_session, session_id=SESSION_ID, project_id=PROJECT_ID, goal_text="目标A")
        msg_a = _seed_message(db_session, session_id=SESSION_ID, content="消息A")
        _seed_event(db_session, session_id=SESSION_ID, project_id=PROJECT_ID, sequence_no=1, content="主题A")
        _seed_workspace(db_session, session_id=SESSION_ID, project_id=PROJECT_ID,
                        topic="主题A", version_no=1, last_event_sequence_no=1)
        plan_a = _seed_plan_version(
            db_session, session_id=SESSION_ID, version_no=1, project_id=PROJECT_ID,
            formalization_target=FormalizationTarget.PLAN_REVISION,
            formalization_workspace_version=1,
            formalization_source_message_ids=[msg_a],
            formalization_source_event_ids=[uuid4()],
            status=PlanVersionStatus.PENDING_CONFIRMATION,
        )

        # Project B: version=3, formalization=[2,3], confirmed plan
        _seed_session(db_session, session_id=SESSION_B_ID, project_id=PROJECT_B_ID, goal_text="目标B")
        msg_b = _seed_message(db_session, session_id=SESSION_B_ID, content="消息B")
        for sn in range(1, 4):
            _seed_event(db_session, session_id=SESSION_B_ID, project_id=PROJECT_B_ID,
                        sequence_no=sn, content=f"主题B{sn}")
        _seed_workspace(db_session, session_id=SESSION_B_ID, project_id=PROJECT_B_ID,
                        topic="主题B", version_no=3, last_event_sequence_no=3)
        _seed_plan_version(
            db_session, session_id=SESSION_B_ID, version_no=1, project_id=PROJECT_B_ID,
            formalization_target=FormalizationTarget.PLAN_REVISION,
            formalization_workspace_version=2,
            formalization_source_message_ids=[msg_b],
            formalization_source_event_ids=[uuid4()],
        )
        plan_b = _seed_plan_version(
            db_session, session_id=SESSION_B_ID, version_no=2, project_id=PROJECT_B_ID,
            formalization_target=FormalizationTarget.PLAN_REVISION,
            formalization_workspace_version=3,
            formalization_source_message_ids=[msg_b],
            formalization_source_event_ids=[uuid4()],
            status=PlanVersionStatus.CONFIRMED,
        )
        db_session.commit()

        # Resume A
        resp_a = client.get("/project-director/workbench/resume",
                            params={"mode": "project", "project_id": str(PROJECT_ID)})
        assert resp_a.status_code == 200
        da = resp_a.json()

        # Resume B
        resp_b = client.get("/project-director/workbench/resume",
                            params={"mode": "project", "project_id": str(PROJECT_B_ID)})
        assert resp_b.status_code == 200
        db_ = resp_b.json()

        # A assertions
        assert da["session"]["id"] == str(SESSION_ID)
        assert da["session"]["project_id"] == str(PROJECT_ID)
        assert da["discussion_workspace"]["session_id"] == str(SESSION_ID)
        assert da["discussion_workspace"]["project_id"] == str(PROJECT_ID)
        assert da["discussion_workspace"]["topic"] == "主题A"
        assert da["discussion_workspace"]["version_no"] == 1
        assert da["plan_version"]["id"] == str(plan_a.id)
        assert da["plan_version"]["project_id"] == str(PROJECT_ID)
        assert da["existing_formalization_workspace_versions"] == [1]

        # B assertions
        assert db_["session"]["id"] == str(SESSION_B_ID)
        assert db_["session"]["project_id"] == str(PROJECT_B_ID)
        assert db_["discussion_workspace"]["session_id"] == str(SESSION_B_ID)
        assert db_["discussion_workspace"]["project_id"] == str(PROJECT_B_ID)
        assert db_["discussion_workspace"]["topic"] == "主题B"
        assert db_["discussion_workspace"]["version_no"] == 3
        assert db_["plan_version"]["id"] == str(plan_b.id)
        assert db_["plan_version"]["project_id"] == str(PROJECT_B_ID)
        assert db_["existing_formalization_workspace_versions"] == [2, 3]

        # No cross
        assert da["session"]["id"] != db_["session"]["id"]
        assert da["plan_version"]["id"] != db_["plan_version"]["id"]
        assert da["discussion_workspace"]["session_id"] != db_["discussion_workspace"]["session_id"]
        assert da["existing_formalization_workspace_versions"] != db_["existing_formalization_workspace_versions"]


# ===========================================================================
# §5.6 Workspace v2 lifecycle
# ===========================================================================


class TestWorkspaceV2Lifecycle:

    def test_v1_formalized_then_v2_resumable(self, db_session, client):
        _seed_session(db_session, project_id=None)
        msg_id = _seed_message(db_session)
        _seed_event(db_session, sequence_no=1, project_id=None)
        _seed_event(db_session, sequence_no=2, project_id=None)
        _seed_workspace(db_session, project_id=None, version_no=2, last_event_sequence_no=2)

        _seed_plan_version(
            db_session, version_no=1,
            formalization_target=FormalizationTarget.PLAN_REVISION,
            formalization_workspace_version=1,
            formalization_source_message_ids=[msg_id],
            formalization_source_event_ids=[uuid4()],
        )
        db_session.commit()

        # Phase 1
        resp1 = client.get("/project-director/workbench/resume",
                           params={"mode": "new-project", "session_id": str(SESSION_ID)})
        assert resp1.status_code == 200
        d1 = resp1.json()
        assert d1["existing_formalization_workspace_versions"] == [1]
        assert d1["discussion_workspace"]["version_no"] == 2

        # Phase 2: create v2 formalization
        _seed_plan_version(
            db_session, version_no=2,
            formalization_target=FormalizationTarget.PLAN_REVISION,
            formalization_workspace_version=2,
            formalization_source_message_ids=[msg_id],
            formalization_source_event_ids=[uuid4()],
        )
        db_session.commit()

        resp2 = client.get("/project-director/workbench/resume",
                           params={"mode": "new-project", "session_id": str(SESSION_ID)})
        assert resp2.status_code == 200
        d2 = resp2.json()
        assert d2["existing_formalization_workspace_versions"] == [1, 2]
        assert len(d2["existing_formalization_workspace_versions"]) == 2
        assert len(set(d2["existing_formalization_workspace_versions"])) == 2
        assert d2["discussion_workspace"]["version_no"] == 2


# ===========================================================================
# §5.7 Resume read-only — full content snapshots
# ===========================================================================


class TestResumeReadOnly:
    """Resume must not write to any table. Full content comparison via fresh session."""

    def test_resume_no_side_effects_full_snapshot(self, db_session_factory, client):
        setup = db_session_factory()
        try:
            _seed_session(setup, project_id=None, goal_text="快照目标")
            msg_id = _seed_message(setup, content="快照消息")
            evt_id = _seed_event(setup, sequence_no=1, project_id=None, content="快照事件")
            _seed_workspace(setup, project_id=None, topic="快照主题",
                            discussion_status=DiscussionStatus.READY_TO_FORMALIZE)
            # Create 2 plan versions: 1 formalized rejected + 1 plain pending
            _seed_plan_version(
                setup, version_no=1,
                formalization_target=FormalizationTarget.PLAN_REVISION,
                formalization_workspace_version=1,
                formalization_source_message_ids=[msg_id],
                formalization_source_event_ids=[evt_id],
                status=PlanVersionStatus.REJECTED,
            )
            _seed_plan_version(setup, version_no=2, status=PlanVersionStatus.PENDING_CONFIRMATION)
            setup.commit()

            assert _count(setup, ProjectDirectorPlanVersionTable) == 2

            pre = _snapshot_state(setup, SESSION_ID, None)
        finally:
            setup.close()

        # Call Resume
        resp = client.get("/project-director/workbench/resume",
                          params={"mode": "new-project", "session_id": str(SESSION_ID)})
        assert resp.status_code == 200

        # Fresh session readback
        fresh = db_session_factory()
        try:
            post = _snapshot_state(fresh, SESSION_ID, None)

            # Full snapshot equality
            assert post["project"] == pre["project"]
            assert post["session"] == pre["session"]
            assert post["messages"] == pre["messages"]
            assert post["events"] == pre["events"]
            assert post["workspace"] == pre["workspace"]
            assert post["plan_versions"] == pre["plan_versions"]
            assert post["counts"] == pre["counts"]

            # Explicit minimum counts
            assert post["counts"]["session"] >= 1
            assert post["counts"]["msg"] >= 1
            assert post["counts"]["evt"] >= 1
            assert post["counts"]["ws"] >= 1
            assert post["counts"]["pv"] == 2
            assert post["counts"]["task"] == 0
            assert post["counts"]["run"] == 0
            assert post["counts"]["agent_session"] == 0
        finally:
            fresh.close()
