"""Tests for P26-C1 discussion event store and workspace persistence.

Verifies ORM schema, Event Repository, Workspace Repository,
payload idempotency, strict JSON, foreign keys, and message chain isolation.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db_tables import (
    ORMBase,
    ProjectDirectorDiscussionEventTable,
    ProjectDirectorDiscussionWorkspaceTable,
    ProjectDirectorMessageTable,
    ProjectDirectorSessionTable,
    ProjectTable,
    RunTable,
    TaskTable,
)
from app.domain.project import Project
from app.domain.project_director_discussion import (
    DiscussionActorClaim,
    DiscussionDeltaOperationType,
    DiscussionEvent,
    DiscussionEventStatus,
    DiscussionEventType,
    DiscussionOptionStatus,
    DiscussionStatus,
    DiscussionWorkspace,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_session import ProjectDirectorSession
from app.repositories.project_director_discussion_event_repository import (
    ProjectDirectorDiscussionEventRepository,
)
from app.repositories.project_director_discussion_workspace_repository import (
    ProjectDirectorDiscussionWorkspaceRepository,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.project_repository import ProjectRepository
from app.services.project_director_message_service import ProjectDirectorMessageService
from app.services.project_director_service import ProjectDirectorService
from app.services.provider_config_service import OpenAIProviderRuntimeConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_engine(tmp_path):
    db_path = tmp_path / "p26c1-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.commit()
    ORMBase.metadata.create_all(bind=engine)
    return engine


@pytest.fixture()
def db_session(db_engine):
    session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def db_session_factory(db_engine):
    return sessionmaker(bind=db_engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _count(session: Session, table) -> int:
    return session.execute(select(table)).scalars().all().__len__()


def _create_session_row(db_session: Session, *, project_id=None) -> ProjectDirectorSession:
    from app.services.project_director_service import ProjectDirectorService
    svc = ProjectDirectorService(
        session_repository=ProjectDirectorSessionRepository(db_session),
        provider_config_service=NoProviderConfigService(),
    )
    return svc.create_session(goal_text="P26-C1 测试", project_id=project_id)


def _create_message_row(db_session: Session, session_id: UUID, *, content="消息") -> ProjectDirectorMessageTable:
    msg = ProjectDirectorMessageTable(
        session_id=session_id,
        role=ProjectDirectorMessageRole.USER,
        content=content,
        sequence_no=1,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail="test",
    )
    db_session.add(msg)
    db_session.flush()
    return msg


def _make_event(
    session_id: UUID,
    *,
    project_id=None,
    sequence_no: int = 1,
    content: str = "事件内容",
    status: DiscussionEventStatus = DiscussionEventStatus.ACTIVE,
    source_message_ids: list[UUID] | None = None,
    payload: dict | None = None,
    supersedes_event_id: UUID | None = None,
    created_by: DiscussionActorClaim = DiscussionActorClaim.SYSTEM_FACT,
    confidence: float = 1.0,
    source_surface: str | None = None,
    source_entity_type: str | None = None,
    source_entity_id: UUID | None = None,
    trigger_type: str | None = None,
    interaction_case_id: UUID | None = None,
    external_context_pack_id: UUID | None = None,
    event_id: UUID | None = None,
) -> DiscussionEvent:
    return DiscussionEvent(
        id=event_id or uuid4(),
        session_id=session_id,
        project_id=project_id,
        sequence_no=sequence_no,
        event_type=DiscussionEventType.TOPIC_SET,
        subject_key="topic",
        content=content,
        status=status,
        payload=payload or {},
        source_message_ids=source_message_ids or [],
        supersedes_event_id=supersedes_event_id,
        created_by=created_by,
        confidence=confidence,
        created_at=datetime.now(timezone.utc),
        source_surface=source_surface,
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        trigger_type=trigger_type,
        interaction_case_id=interaction_case_id,
        external_context_pack_id=external_context_pack_id,
    )


def _make_workspace(
    session_id: UUID,
    *,
    project_id=None,
    topic: str = "测试主题",
    version_no: int = 0,
    last_event_sequence_no: int = 0,
) -> DiscussionWorkspace:
    now = datetime.now(timezone.utc)
    return DiscussionWorkspace(
        session_id=session_id,
        project_id=project_id,
        topic=topic,
        discussion_status=DiscussionStatus.EXPLORING,
        active_option_ids=[],
        preferred_option_id=None,
        active_constraint_ids=[],
        open_question_ids=[],
        temporary_conclusion_ids=[],
        confirmed_decision_ids=[],
        latest_user_correction_event_id=None,
        version_no=version_no,
        last_event_sequence_no=last_event_sequence_no,
        created_at=now,
        updated_at=now,
    )


class NoProviderConfigService:
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


# ===========================================================================
# 8. ORM Schema Verification
# ===========================================================================


class TestEventTableSchema:
    def test_table_exists(self, db_engine):
        inspector = inspect(db_engine)
        assert "project_director_discussion_events" in inspector.get_table_names()

    def test_columns_present(self, db_engine):
        inspector = inspect(db_engine)
        cols = {c["name"] for c in inspector.get_columns("project_director_discussion_events")}
        expected = {
            "id", "session_id", "project_id", "sequence_no", "event_type",
            "subject_key", "content", "status", "payload_json",
            "source_message_ids_json", "supersedes_event_id", "created_by",
            "confidence", "idempotency_key", "created_at",
            "source_surface", "source_entity_type", "source_entity_id",
            "trigger_type", "interaction_case_id", "external_context_pack_id",
        }
        assert expected.issubset(cols)

    def test_project_id_nullable(self, db_engine):
        inspector = inspect(db_engine)
        cols = {c["name"]: c for c in inspector.get_columns("project_director_discussion_events")}
        assert cols["project_id"]["nullable"] is True

    def test_session_id_not_nullable(self, db_engine):
        inspector = inspect(db_engine)
        cols = {c["name"]: c for c in inspector.get_columns("project_director_discussion_events")}
        assert cols["session_id"]["nullable"] is False

    def test_idempotency_key_max_length(self, db_engine):
        inspector = inspect(db_engine)
        cols = {c["name"]: c for c in inspector.get_columns("project_director_discussion_events")}
        assert cols["idempotency_key"]["type"].length == 256

    def test_unique_constraints(self, db_engine):
        inspector = inspect(db_engine)
        uqs = {u["name"] for u in inspector.get_unique_constraints("project_director_discussion_events")}
        assert "uq_pd_discussion_events_session_sequence" in uqs
        assert "uq_pd_discussion_events_session_idempotency" in uqs

    def test_indexes(self, db_engine):
        inspector = inspect(db_engine)
        idx_names = {idx["name"] for idx in inspector.get_indexes("project_director_discussion_events")}
        assert "ix_pd_discussion_events_session_event_type" in idx_names
        assert "ix_pd_discussion_events_session_status" in idx_names
        assert "ix_pd_discussion_events_supersedes" in idx_names
        assert "ix_pd_discussion_events_created_at" in idx_names

    def test_check_constraints_reject_sequence_zero(self, db_session):
        session_obj = _create_session_row(db_session)
        row = ProjectDirectorDiscussionEventTable(
            id=uuid4(), session_id=session_obj.id, project_id=None,
            sequence_no=0, event_type="topic_set", subject_key="t",
            content="c", status="active", payload_json="{}",
            source_message_ids_json="[]", created_by="system_fact",
            confidence=1.0, idempotency_key="k1",
        )
        db_session.add(row)
        with pytest.raises(Exception):
            db_session.flush()
        db_session.rollback()

    def test_check_constraints_reject_confidence_below_zero(self, db_session):
        session_obj = _create_session_row(db_session)
        row = ProjectDirectorDiscussionEventTable(
            id=uuid4(), session_id=session_obj.id, project_id=None,
            sequence_no=1, event_type="topic_set", subject_key="t",
            content="c", status="active", payload_json="{}",
            source_message_ids_json="[]", created_by="system_fact",
            confidence=-0.1, idempotency_key="k2",
        )
        db_session.add(row)
        with pytest.raises(Exception):
            db_session.flush()
        db_session.rollback()

    def test_check_constraints_reject_confidence_above_one(self, db_session):
        session_obj = _create_session_row(db_session)
        row = ProjectDirectorDiscussionEventTable(
            id=uuid4(), session_id=session_obj.id, project_id=None,
            sequence_no=1, event_type="topic_set", subject_key="t",
            content="c", status="active", payload_json="{}",
            source_message_ids_json="[]", created_by="system_fact",
            confidence=1.1, idempotency_key="k3",
        )
        db_session.add(row)
        with pytest.raises(Exception):
            db_session.flush()
        db_session.rollback()

    def test_check_constraints_reject_empty_idempotency_key(self, db_session):
        session_obj = _create_session_row(db_session)
        row = ProjectDirectorDiscussionEventTable(
            id=uuid4(), session_id=session_obj.id, project_id=None,
            sequence_no=1, event_type="topic_set", subject_key="t",
            content="c", status="active", payload_json="{}",
            source_message_ids_json="[]", created_by="system_fact",
            confidence=1.0, idempotency_key="",
        )
        db_session.add(row)
        with pytest.raises(Exception):
            db_session.flush()
        db_session.rollback()


class TestWorkspaceTableSchema:
    def test_table_exists(self, db_engine):
        inspector = inspect(db_engine)
        assert "project_director_discussion_workspaces" in inspector.get_table_names()

    def test_session_id_is_primary_key(self, db_engine):
        inspector = inspect(db_engine)
        pk = inspector.get_pk_constraint("project_director_discussion_workspaces")
        assert pk["constrained_columns"] == ["session_id"]

    def test_project_id_nullable(self, db_engine):
        inspector = inspect(db_engine)
        cols = {c["name"]: c for c in inspector.get_columns("project_director_discussion_workspaces")}
        assert cols["project_id"]["nullable"] is True

    def test_check_version_no_non_negative(self, db_session):
        session_obj = _create_session_row(db_session)
        row = ProjectDirectorDiscussionWorkspaceTable(
            session_id=session_obj.id, project_id=None,
            topic="t", discussion_status="exploring",
            state_json="{}", version_no=-1, last_event_sequence_no=0,
        )
        db_session.add(row)
        with pytest.raises(Exception):
            db_session.flush()
        db_session.rollback()

    def test_check_last_event_sequence_no_non_negative(self, db_session):
        session_obj = _create_session_row(db_session)
        row = ProjectDirectorDiscussionWorkspaceTable(
            session_id=session_obj.id, project_id=None,
            topic="t", discussion_status="exploring",
            state_json="{}", version_no=0, last_event_sequence_no=-1,
        )
        db_session.add(row)
        with pytest.raises(Exception):
            db_session.flush()
        db_session.rollback()

    def test_duplicate_session_rejected(self, db_session):
        session_obj = _create_session_row(db_session)
        row1 = ProjectDirectorDiscussionWorkspaceTable(
            session_id=session_obj.id, project_id=None,
            topic="t1", state_json="{}", version_no=0, last_event_sequence_no=0,
        )
        row2 = ProjectDirectorDiscussionWorkspaceTable(
            session_id=session_obj.id, project_id=None,
            topic="t2", state_json="{}", version_no=0, last_event_sequence_no=0,
        )
        db_session.add(row1)
        db_session.flush()
        db_session.add(row2)
        with pytest.raises(Exception):
            db_session.flush()
        db_session.rollback()


# ===========================================================================
# 9. Unbound project session
# ===========================================================================


class TestUnboundProjectSession:
    def test_create_workspace_with_null_project(self, db_session):
        session_obj = _create_session_row(db_session, project_id=None)
        repo = ProjectDirectorDiscussionWorkspaceRepository(db_session)
        ws = _make_workspace(session_obj.id)
        created, is_new = repo.create_if_absent(workspace=ws)
        assert is_new is True
        assert created.project_id is None

    def test_append_event_with_null_project(self, db_session):
        session_obj = _create_session_row(db_session, project_id=None)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        event = _make_event(session_obj.id)
        created, is_new = repo.append_if_absent(event=event, idempotency_key="k-null")
        assert is_new is True
        assert created.project_id is None

    def test_get_and_list_work_with_null_project(self, db_session):
        session_obj = _create_session_row(db_session, project_id=None)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        repo.append_if_absent(event=_make_event(session_obj.id, sequence_no=1), idempotency_key="k1")
        repo.append_if_absent(event=_make_event(session_obj.id, sequence_no=2), idempotency_key="k2")
        events = repo.list_by_session_id(session_id=session_obj.id)
        assert len(events) == 2

    def test_fake_project_id_rejected_for_event(self, db_session):
        session_obj = _create_session_row(db_session, project_id=None)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        event = _make_event(session_obj.id, project_id=uuid4())
        with pytest.raises(ValueError, match="discussion_event_project_session_mismatch"):
            repo.append_if_absent(event=event, idempotency_key="k-fake")

    def test_fake_project_id_rejected_for_workspace(self, db_session):
        session_obj = _create_session_row(db_session, project_id=None)
        repo = ProjectDirectorDiscussionWorkspaceRepository(db_session)
        ws = _make_workspace(session_obj.id, project_id=uuid4())
        with pytest.raises(ValueError, match="discussion_workspace_project_session_mismatch"):
            repo.create_if_absent(workspace=ws)


# ===========================================================================
# 10. Bound project session
# ===========================================================================


class TestBoundProjectSession:
    def test_event_project_id_persisted(self, db_session):
        project = ProjectRepository(db_session).create(Project(name="P", summary="S"))
        session_obj = _create_session_row(db_session, project_id=project.id)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        event = _make_event(session_obj.id, project_id=project.id)
        created, _ = repo.append_if_absent(event=event, idempotency_key="k-proj")
        assert created.project_id == project.id

    def test_workspace_project_id_persisted(self, db_session):
        project = ProjectRepository(db_session).create(Project(name="P", summary="S"))
        session_obj = _create_session_row(db_session, project_id=project.id)
        repo = ProjectDirectorDiscussionWorkspaceRepository(db_session)
        ws = _make_workspace(session_obj.id, project_id=project.id)
        created, _ = repo.create_if_absent(workspace=ws)
        assert created.project_id == project.id

    def test_wrong_project_id_rejected(self, db_session):
        project = ProjectRepository(db_session).create(Project(name="P", summary="S"))
        session_obj = _create_session_row(db_session, project_id=project.id)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        event = _make_event(session_obj.id, project_id=uuid4())
        with pytest.raises(ValueError, match="discussion_event_project_session_mismatch"):
            repo.append_if_absent(event=event, idempotency_key="k-wrong")


# ===========================================================================
# 11. Event Repository basic capabilities
# ===========================================================================


class TestEventRepositoryBasic:
    def test_append_two_events_sequential(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e1, created1 = repo.append_if_absent(
            event=_make_event(session_obj.id, sequence_no=1), idempotency_key="k1",
        )
        e2, created2 = repo.append_if_absent(
            event=_make_event(session_obj.id, sequence_no=2), idempotency_key="k2",
        )
        assert created1 is True
        assert created2 is True
        assert repo.get_next_sequence_no(session_id=session_obj.id) == 3

    def test_list_order(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        repo.append_if_absent(event=_make_event(session_obj.id, sequence_no=1), idempotency_key="k1")
        repo.append_if_absent(event=_make_event(session_obj.id, sequence_no=2), idempotency_key="k2")
        events = repo.list_by_session_id(session_id=session_obj.id)
        assert [e.sequence_no for e in events] == [1, 2]

    def test_get_by_id(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        event = _make_event(session_obj.id)
        repo.append_if_absent(event=event, idempotency_key="k-id")
        found = repo.get_by_id(event_id=event.id)
        assert found is not None
        assert found.id == event.id

    def test_get_by_id_not_found(self, db_session):
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        assert repo.get_by_id(event_id=uuid4()) is None

    def test_get_by_idempotency_key(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        event = _make_event(session_obj.id)
        repo.append_if_absent(event=event, idempotency_key="k-ik")
        found = repo.get_by_idempotency_key(session_id=session_obj.id, idempotency_key="k-ik")
        assert found is not None
        assert found.id == event.id

    def test_get_by_idempotency_key_not_found(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        assert repo.get_by_idempotency_key(session_id=session_obj.id, idempotency_key="none") is None

    def test_next_sequence_starts_at_one(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        assert repo.get_next_sequence_no(session_id=session_obj.id) == 1

    def test_sequence_unique_constraint(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        repo.append_if_absent(event=_make_event(session_obj.id, sequence_no=1), idempotency_key="k1")
        with pytest.raises(Exception):
            db_session.begin_nested()
            repo.append_if_absent(
                event=_make_event(session_obj.id, sequence_no=1, content="different", event_id=uuid4()),
                idempotency_key="k-dup-seq",
            )
            db_session.commit()
        db_session.rollback()


# ===========================================================================
# 12. Payload idempotency
# ===========================================================================


class TestPayloadIdempotency:
    def test_simple_payload_replay(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        payload = {"name": "方案A", "count": 2}
        e1, c1 = repo.append_if_absent(
            event=_make_event(session_obj.id, payload=payload), idempotency_key="k-p1",
        )
        e2, c2 = repo.append_if_absent(
            event=_make_event(session_obj.id, payload=payload, event_id=uuid4(), sequence_no=2),
            idempotency_key="k-p1",
        )
        assert c1 is True
        assert c2 is False
        assert e2.id == e1.id
        assert _count(db_session, ProjectDirectorDiscussionEventTable) == 1

    def test_top_level_uuid_payload_replay(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        option_id = uuid4()
        payload = {"option_id": str(option_id)}
        e1, c1 = repo.append_if_absent(
            event=_make_event(session_obj.id, payload=payload), idempotency_key="k-uuid",
        )
        e2, c2 = repo.append_if_absent(
            event=_make_event(session_obj.id, payload=payload, event_id=uuid4()), idempotency_key="k-uuid",
        )
        assert c1 is True
        assert c2 is False

    def test_nested_uuid_payload_replay(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        oid = uuid4()
        rid = uuid4()
        payload = {"options": [{"option_id": str(oid), "related_ids": [str(rid)]}]}
        e1, c1 = repo.append_if_absent(
            event=_make_event(session_obj.id, payload=payload), idempotency_key="k-nested",
        )
        e2, c2 = repo.append_if_absent(
            event=_make_event(session_obj.id, payload=payload, event_id=uuid4()), idempotency_key="k-nested",
        )
        assert c1 is True
        assert c2 is False

    def test_dict_key_order_equivalence(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e1, c1 = repo.append_if_absent(
            event=_make_event(session_obj.id, payload={"a": 1, "b": 2}), idempotency_key="k-order",
        )
        e2, c2 = repo.append_if_absent(
            event=_make_event(session_obj.id, payload={"b": 2, "a": 1}, event_id=uuid4()),
            idempotency_key="k-order",
        )
        assert c1 is True
        assert c2 is False

    def test_tuple_list_json_equivalence(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e1, c1 = repo.append_if_absent(
            event=_make_event(session_obj.id, payload={"items": [1, 2, 3]}), idempotency_key="k-tuple",
        )
        e2, c2 = repo.append_if_absent(
            event=_make_event(session_obj.id, payload={"items": [1, 2, 3]}, event_id=uuid4()),
            idempotency_key="k-tuple",
        )
        assert c1 is True
        assert c2 is False

    def test_chinese_payload_roundtrip(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        payload = {"label": "方案甲", "说明": "后端优先"}
        e1, c1 = repo.append_if_absent(
            event=_make_event(session_obj.id, payload=payload), idempotency_key="k-cn",
        )
        assert c1 is True
        assert e1.payload == payload

    @pytest.mark.parametrize(
        "field,value",
        [
            ("content", "不同的内容"),
            ("status", DiscussionEventStatus.REJECTED),
            ("payload", {"different": True}),
            ("source_message_ids", [uuid4()]),
            ("supersedes_event_id", uuid4()),
            ("created_by", DiscussionActorClaim.USER_EXPLICIT),
            ("confidence", 0.5),
            ("source_surface", "different_surface"),
            ("source_entity_type", "different_type"),
            ("source_entity_id", uuid4()),
            ("trigger_type", "different_trigger"),
            ("interaction_case_id", uuid4()),
            ("external_context_pack_id", uuid4()),
        ],
    )
    def test_real_change_produces_conflict(self, db_session, field, value):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        msg = _create_message_row(db_session, session_obj.id)
        e1 = _make_event(session_obj.id, source_message_ids=[msg.id])
        repo.append_if_absent(event=e1, idempotency_key="k-change")

        kwargs = dict(
            session_id=session_obj.id, sequence_no=2, event_id=uuid4(),
            source_message_ids=[msg.id],
        )
        kwargs[field] = value
        if field == "source_message_ids":
            kwargs["source_message_ids"] = value
        if field == "created_by" and value == DiscussionActorClaim.USER_EXPLICIT:
            kwargs["confidence"] = 1.0
            kwargs["source_message_ids"] = [msg.id]
        e2 = _make_event(**kwargs)
        with pytest.raises(ValueError, match="discussion_event_idempotency_conflict"):
            repo.append_if_absent(event=e2, idempotency_key="k-change")
        assert _count(db_session, ProjectDirectorDiscussionEventTable) == 1


# ===========================================================================
# 13. Idempotency priority
# ===========================================================================


class TestIdempotencyPriority:
    def test_same_key_invalid_source_message_gives_conflict_not_source_error(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        msg = _create_message_row(db_session, session_obj.id)
        e1 = _make_event(session_obj.id, source_message_ids=[msg.id])
        repo.append_if_absent(event=e1, idempotency_key="k-pri")

        e2 = _make_event(session_obj.id, source_message_ids=[uuid4()], event_id=uuid4(), sequence_no=2)
        with pytest.raises(ValueError, match="discussion_event_idempotency_conflict"):
            repo.append_if_absent(event=e2, idempotency_key="k-pri")

    def test_same_key_invalid_supersedes_gives_conflict(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e1 = _make_event(session_obj.id)
        repo.append_if_absent(event=e1, idempotency_key="k-sup")

        e2 = _make_event(session_obj.id, supersedes_event_id=uuid4(), event_id=uuid4(), sequence_no=2)
        with pytest.raises(ValueError, match="discussion_event_idempotency_conflict"):
            repo.append_if_absent(event=e2, idempotency_key="k-sup")

    def test_new_key_invalid_source_message_gives_source_error(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e = _make_event(session_obj.id, source_message_ids=[uuid4()])
        with pytest.raises(ValueError, match="discussion_event_source_message_not_found"):
            repo.append_if_absent(event=e, idempotency_key="k-new-src")

    def test_new_key_invalid_supersedes_gives_supersedes_error(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e = _make_event(session_obj.id, supersedes_event_id=uuid4())
        with pytest.raises(ValueError, match="discussion_event_supersedes_not_found"):
            repo.append_if_absent(event=e, idempotency_key="k-new-sup")


# ===========================================================================
# 14. Idempotency key validation
# ===========================================================================


class TestIdempotencyKeyValidation:
    @pytest.mark.parametrize("bad_key", ["", "   ", "a" * 257])
    def test_empty_or_too_long_key_rejected(self, db_session, bad_key):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e = _make_event(session_obj.id)
        with pytest.raises(ValueError, match="discussion_event_idempotency_key_invalid"):
            repo.append_if_absent(event=e, idempotency_key=bad_key)

    @pytest.mark.parametrize(
        "bad_key",
        ["has api_key inside", "has API KEY inside", "has authorization inside",
         "has Bearer token", "has sk-abc123"],
    )
    def test_sensitive_key_rejected(self, db_session, bad_key):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e = _make_event(session_obj.id)
        with pytest.raises(ValueError, match="discussion_event_idempotency_key_invalid"):
            repo.append_if_absent(event=e, idempotency_key=bad_key)

    def test_length_1_key_accepted(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e = _make_event(session_obj.id)
        _, created = repo.append_if_absent(event=e, idempotency_key="x")
        assert created is True

    def test_length_256_key_accepted(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e = _make_event(session_obj.id)
        _, created = repo.append_if_absent(event=e, idempotency_key="k" * 256)
        assert created is True


# ===========================================================================
# 15. Source message validation
# ===========================================================================


class TestSourceMessageValidation:
    def test_same_session_message_accepted(self, db_session):
        session_obj = _create_session_row(db_session)
        msg = _create_message_row(db_session, session_obj.id)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e = _make_event(session_obj.id, source_message_ids=[msg.id])
        _, created = repo.append_if_absent(event=e, idempotency_key="k-sm1")
        assert created is True

    def test_message_not_found(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e = _make_event(session_obj.id, source_message_ids=[uuid4()])
        with pytest.raises(ValueError, match="discussion_event_source_message_not_found"):
            repo.append_if_absent(event=e, idempotency_key="k-sm-nf")

    def test_message_wrong_session(self, db_session):
        s1 = _create_session_row(db_session)
        s2 = _create_session_row(db_session)
        msg = _create_message_row(db_session, s2.id)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e = _make_event(s1.id, source_message_ids=[msg.id])
        with pytest.raises(ValueError, match="discussion_event_source_message_session_mismatch"):
            repo.append_if_absent(event=e, idempotency_key="k-sm-ws")


# ===========================================================================
# 16. Supersedes validation
# ===========================================================================


class TestSupersedesValidation:
    def test_supersede_same_session_event(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e1 = _make_event(session_obj.id, sequence_no=1)
        repo.append_if_absent(event=e1, idempotency_key="k-s1")
        e2 = _make_event(session_obj.id, sequence_no=2, supersedes_event_id=e1.id)
        _, created = repo.append_if_absent(event=e2, idempotency_key="k-s2")
        assert created is True

    def test_supersede_not_found(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e = _make_event(session_obj.id, supersedes_event_id=uuid4())
        with pytest.raises(ValueError, match="discussion_event_supersedes_not_found"):
            repo.append_if_absent(event=e, idempotency_key="k-sup-nf")

    def test_supersede_wrong_session(self, db_session):
        s1 = _create_session_row(db_session)
        s2 = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e1 = _make_event(s2.id, sequence_no=1)
        repo.append_if_absent(event=e1, idempotency_key="k-sw1")
        e2 = _make_event(s1.id, sequence_no=1, supersedes_event_id=e1.id)
        with pytest.raises(ValueError, match="discussion_event_supersedes_session_mismatch"):
            repo.append_if_absent(event=e2, idempotency_key="k-sw2")

    def test_old_event_not_modified_by_supersede(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e1 = _make_event(session_obj.id, sequence_no=1, content="原始内容")
        repo.append_if_absent(event=e1, idempotency_key="k-orig")
        e2 = _make_event(session_obj.id, sequence_no=2, supersedes_event_id=e1.id)
        repo.append_if_absent(event=e2, idempotency_key="k-sup-new")
        original = repo.get_by_id(event_id=e1.id)
        assert original.content == "原始内容"
        assert original.status == DiscussionEventStatus.ACTIVE

    def test_no_update_delete_methods(self):
        repo = ProjectDirectorDiscussionEventRepository.__new__(ProjectDirectorDiscussionEventRepository)
        assert not hasattr(repo, "update_event")
        assert not hasattr(repo, "delete_event")
        assert not hasattr(repo, "replace_event")


# ===========================================================================
# 17. Race recovery
# ===========================================================================


class TestRaceRecovery:
    def test_equivalent_race_recovery(self, db_session, monkeypatch):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e1 = _make_event(session_obj.id, sequence_no=1)
        repo.append_if_absent(event=e1, idempotency_key="k-race")

        call_count = {"n": 0}
        original = ProjectDirectorDiscussionEventRepository.get_by_idempotency_key

        def patched(self, *, session_id, idempotency_key):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return None
            return original(self, session_id=session_id, idempotency_key=idempotency_key)

        monkeypatch.setattr(ProjectDirectorDiscussionEventRepository, "get_by_idempotency_key", patched)

        e2 = _make_event(session_obj.id, sequence_no=2, event_id=uuid4())
        result, created = repo.append_if_absent(event=e2, idempotency_key="k-race")
        assert created is False
        assert result.id == e1.id
        assert _count(db_session, ProjectDirectorDiscussionEventTable) == 1

    def test_conflict_race_preserves_error(self, db_session, monkeypatch):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e1 = _make_event(session_obj.id, sequence_no=1, content="原始")
        repo.append_if_absent(event=e1, idempotency_key="k-crace")

        call_count = {"n": 0}
        original = ProjectDirectorDiscussionEventRepository.get_by_idempotency_key

        def patched(self, *, session_id, idempotency_key):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return None
            return original(self, session_id=session_id, idempotency_key=idempotency_key)

        monkeypatch.setattr(ProjectDirectorDiscussionEventRepository, "get_by_idempotency_key", patched)

        e2 = _make_event(session_obj.id, sequence_no=2, content="不同内容", event_id=uuid4())
        with pytest.raises(ValueError, match="discussion_event_idempotency_conflict"):
            repo.append_if_absent(event=e2, idempotency_key="k-crace")
        assert _count(db_session, ProjectDirectorDiscussionEventTable) == 1

    def test_sequence_conflict_not_disguised_as_idempotent(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e1 = _make_event(session_obj.id, sequence_no=1)
        repo.append_if_absent(event=e1, idempotency_key="k-seq1")
        e2 = _make_event(session_obj.id, sequence_no=1, content="different", event_id=uuid4())
        with pytest.raises(Exception):
            repo.append_if_absent(event=e2, idempotency_key="k-seq2")


# ===========================================================================
# 18. Strict JSON readback
# ===========================================================================


class TestStrictJsonReadback:
    def test_invalid_payload_json(self, db_session):
        session_obj = _create_session_row(db_session)
        row = ProjectDirectorDiscussionEventTable(
            id=uuid4(), session_id=session_obj.id, project_id=None,
            sequence_no=1, event_type="topic_set", subject_key="t",
            content="c", status="active", payload_json="not-json",
            source_message_ids_json="[]", created_by="system_fact",
            confidence=1.0, idempotency_key="k-bad-payload",
        )
        db_session.add(row)
        db_session.flush()
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        with pytest.raises(ValueError, match="invalid_discussion_event_payload_json"):
            repo.get_by_id(event_id=row.id)

    def test_array_payload_json(self, db_session):
        session_obj = _create_session_row(db_session)
        row = ProjectDirectorDiscussionEventTable(
            id=uuid4(), session_id=session_obj.id, project_id=None,
            sequence_no=1, event_type="topic_set", subject_key="t",
            content="c", status="active", payload_json="[1,2,3]",
            source_message_ids_json="[]", created_by="system_fact",
            confidence=1.0, idempotency_key="k-arr-payload",
        )
        db_session.add(row)
        db_session.flush()
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        with pytest.raises(ValueError, match="invalid_discussion_event_payload_json"):
            repo.get_by_id(event_id=row.id)

    def test_invalid_source_message_ids_json(self, db_session):
        session_obj = _create_session_row(db_session)
        row = ProjectDirectorDiscussionEventTable(
            id=uuid4(), session_id=session_obj.id, project_id=None,
            sequence_no=1, event_type="topic_set", subject_key="t",
            content="c", status="active", payload_json="{}",
            source_message_ids_json="not-json", created_by="system_fact",
            confidence=1.0, idempotency_key="k-bad-sm",
        )
        db_session.add(row)
        db_session.flush()
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        with pytest.raises(ValueError, match="invalid_discussion_event_source_message_ids_json"):
            repo.get_by_id(event_id=row.id)

    def test_object_source_message_ids_json(self, db_session):
        session_obj = _create_session_row(db_session)
        row = ProjectDirectorDiscussionEventTable(
            id=uuid4(), session_id=session_obj.id, project_id=None,
            sequence_no=1, event_type="topic_set", subject_key="t",
            content="c", status="active", payload_json="{}",
            source_message_ids_json='{"a":1}', created_by="system_fact",
            confidence=1.0, idempotency_key="k-obj-sm",
        )
        db_session.add(row)
        db_session.flush()
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        with pytest.raises(ValueError, match="invalid_discussion_event_source_message_ids_json"):
            repo.get_by_id(event_id=row.id)


# ===========================================================================
# 19. P27 six fields round-trip
# ===========================================================================


class TestP27FieldsRoundTrip:
    def test_all_six_fields_persisted(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        se_id = uuid4()
        ic_id = uuid4()
        ec_id = uuid4()
        e = _make_event(
            session_obj.id,
            source_surface="test_surface",
            source_entity_type="test_entity",
            source_entity_id=se_id,
            trigger_type="test_trigger",
            interaction_case_id=ic_id,
            external_context_pack_id=ec_id,
        )
        created, _ = repo.append_if_absent(event=e, idempotency_key="k-p27")
        assert created.source_surface == "test_surface"
        assert created.source_entity_type == "test_entity"
        assert created.source_entity_id == se_id
        assert created.trigger_type == "test_trigger"
        assert created.interaction_case_id == ic_id
        assert created.external_context_pack_id == ec_id

    def test_p27_fields_roundtrip_via_list(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e = _make_event(session_obj.id, source_surface="surf", trigger_type="trig")
        repo.append_if_absent(event=e, idempotency_key="k-p27-list")
        events = repo.list_by_session_id(session_id=session_obj.id)
        assert events[0].source_surface == "surf"
        assert events[0].trigger_type == "trig"

    def test_p27_same_values_idempotent(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e1 = _make_event(session_obj.id, source_surface="surf", trigger_type="trig")
        repo.append_if_absent(event=e1, idempotency_key="k-p27-idem")
        e2 = _make_event(session_obj.id, source_surface="surf", trigger_type="trig", event_id=uuid4(), sequence_no=2)
        _, created = repo.append_if_absent(event=e2, idempotency_key="k-p27-idem")
        assert created is False

    def test_p27_field_change_conflict(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e1 = _make_event(session_obj.id, source_surface="surf1")
        repo.append_if_absent(event=e1, idempotency_key="k-p27-chg")
        e2 = _make_event(session_obj.id, source_surface="surf2", event_id=uuid4(), sequence_no=2)
        with pytest.raises(ValueError, match="discussion_event_idempotency_conflict"):
            repo.append_if_absent(event=e2, idempotency_key="k-p27-chg")


# ===========================================================================
# 20. Workspace create_if_absent
# ===========================================================================


class TestWorkspaceCreate:
    def test_first_create(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionWorkspaceRepository(db_session)
        ws = _make_workspace(session_obj.id)
        created, is_new = repo.create_if_absent(workspace=ws)
        assert is_new is True
        assert created.version_no == 0
        assert created.last_event_sequence_no == 0

    def test_duplicate_create(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionWorkspaceRepository(db_session)
        ws = _make_workspace(session_obj.id)
        repo.create_if_absent(workspace=ws)
        _, is_new = repo.create_if_absent(workspace=_make_workspace(session_obj.id))
        assert is_new is False
        assert _count(db_session, ProjectDirectorDiscussionWorkspaceTable) == 1

    def test_initial_version_invalid(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionWorkspaceRepository(db_session)
        ws = _make_workspace(session_obj.id, version_no=1)
        with pytest.raises(ValueError, match="discussion_workspace_initial_version_invalid"):
            repo.create_if_absent(workspace=ws)

    def test_initial_last_event_invalid(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionWorkspaceRepository(db_session)
        ws = _make_workspace(session_obj.id, last_event_sequence_no=1)
        with pytest.raises(ValueError, match="discussion_workspace_initial_version_invalid"):
            repo.create_if_absent(workspace=ws)

    def test_project_mismatch(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionWorkspaceRepository(db_session)
        ws = _make_workspace(session_obj.id, project_id=uuid4())
        with pytest.raises(ValueError, match="discussion_workspace_project_session_mismatch"):
            repo.create_if_absent(workspace=ws)

    def test_session_not_found(self, db_session):
        repo = ProjectDirectorDiscussionWorkspaceRepository(db_session)
        ws = _make_workspace(uuid4())
        with pytest.raises(ValueError, match="discussion_workspace_session_not_found"):
            repo.create_if_absent(workspace=ws)


# ===========================================================================
# 21. Workspace state round-trip
# ===========================================================================


class TestWorkspaceStateRoundTrip:
    def test_full_state_roundtrip(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionWorkspaceRepository(db_session)
        opt1 = uuid4()
        opt2 = uuid4()
        constr = uuid4()
        oq = uuid4()
        tc = uuid4()
        cd = uuid4()
        corr = uuid4()
        ws = _make_workspace(session_obj.id)
        ws_full = DiscussionWorkspace(
            session_id=session_obj.id,
            project_id=None,
            topic="中文主题：后端优先",
            discussion_status=DiscussionStatus.COMPARING,
            active_option_ids=[opt1, opt2],
            preferred_option_id=opt1,
            active_constraint_ids=[constr],
            open_question_ids=[oq],
            temporary_conclusion_ids=[tc],
            confirmed_decision_ids=[cd],
            latest_user_correction_event_id=corr,
            version_no=0,
            last_event_sequence_no=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        created, _ = repo.create_if_absent(workspace=ws_full)
        read = repo.get_by_session_id(session_id=session_obj.id)
        assert read.topic == "中文主题：后端优先"
        assert read.discussion_status == DiscussionStatus.COMPARING
        assert read.active_option_ids == [opt1, opt2]
        assert read.preferred_option_id == opt1
        assert read.active_constraint_ids == [constr]
        assert read.open_question_ids == [oq]
        assert read.temporary_conclusion_ids == [tc]
        assert read.confirmed_decision_ids == [cd]
        assert read.latest_user_correction_event_id == corr

    def test_preferred_must_be_in_active(self):
        with pytest.raises(ValueError, match="preferred_option_id"):
            DiscussionWorkspace(
                session_id=uuid4(), project_id=None, topic="t",
                active_option_ids=[uuid4()],
                preferred_option_id=uuid4(),
                version_no=0, last_event_sequence_no=0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

    def test_duplicate_active_option_ids_rejected(self):
        oid = uuid4()
        with pytest.raises(ValueError, match="duplicate"):
            DiscussionWorkspace(
                session_id=uuid4(), project_id=None, topic="t",
                active_option_ids=[oid, oid],
                version_no=0, last_event_sequence_no=0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )


# ===========================================================================
# 22. Workspace update_if_version
# ===========================================================================


class TestWorkspaceUpdate:
    def test_normal_update_0_to_1(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionWorkspaceRepository(db_session)
        ws = _make_workspace(session_obj.id)
        repo.create_if_absent(workspace=ws)

        updated = DiscussionWorkspace(
            session_id=session_obj.id, project_id=None,
            topic="更新主题",
            discussion_status=DiscussionStatus.CONVERGING,
            active_option_ids=[uuid4()],
            version_no=1, last_event_sequence_no=5,
            created_at=ws.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        result = repo.update_if_version(workspace=updated, expected_version_no=0)
        assert result.version_no == 1
        assert result.last_event_sequence_no == 5
        assert result.discussion_status == DiscussionStatus.CONVERGING

    def test_non_incremental_version_rejected(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionWorkspaceRepository(db_session)
        repo.create_if_absent(workspace=_make_workspace(session_obj.id))
        ws = _make_workspace(session_obj.id, version_no=2)
        with pytest.raises(ValueError, match="discussion_workspace_version_increment_invalid"):
            repo.update_if_version(workspace=ws, expected_version_no=0)

    def test_stale_version_rejected(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionWorkspaceRepository(db_session)
        repo.create_if_absent(workspace=_make_workspace(session_obj.id))
        ws1 = _make_workspace(session_obj.id, version_no=1)
        repo.update_if_version(workspace=ws1, expected_version_no=0)

        ws_stale = _make_workspace(session_obj.id, version_no=1)
        with pytest.raises(ValueError, match="discussion_workspace_stale_version"):
            repo.update_if_version(workspace=ws_stale, expected_version_no=0)

    def test_two_session_cas(self, db_session_factory):
        s1 = db_session_factory()
        s2 = db_session_factory()
        try:
            from app.services.project_director_service import ProjectDirectorService
            svc1 = ProjectDirectorService(
                session_repository=ProjectDirectorSessionRepository(s1),
                provider_config_service=NoProviderConfigService(),
            )
            session_obj = svc1.create_session(goal_text="CAS")
            s1.commit()

            repo1 = ProjectDirectorDiscussionWorkspaceRepository(s1)
            repo2 = ProjectDirectorDiscussionWorkspaceRepository(s2)

            repo1.create_if_absent(workspace=_make_workspace(session_obj.id))
            s1.commit()
            repo2.create_if_absent(workspace=_make_workspace(session_obj.id))
            s2.commit()

            ws1 = _make_workspace(session_obj.id, version_no=1, topic="A更新")
            repo1.update_if_version(workspace=ws1, expected_version_no=0)
            s1.commit()

            ws2 = _make_workspace(session_obj.id, version_no=1, topic="B更新")
            with pytest.raises(ValueError, match="discussion_workspace_stale_version"):
                repo2.update_if_version(workspace=ws2, expected_version_no=0)
        finally:
            s1.close()
            s2.close()

    def test_nonexistent_workspace_stale(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionWorkspaceRepository(db_session)
        ws = _make_workspace(session_obj.id, version_no=1)
        with pytest.raises(ValueError, match="discussion_workspace_stale_version"):
            repo.update_if_version(workspace=ws, expected_version_no=0)


# ===========================================================================
# 23. Workspace strict JSON
# ===========================================================================


class TestWorkspaceStrictJson:
    def test_invalid_state_json(self, db_session):
        session_obj = _create_session_row(db_session)
        row = ProjectDirectorDiscussionWorkspaceTable(
            session_id=session_obj.id, project_id=None,
            topic="t", state_json="not-json",
            version_no=0, last_event_sequence_no=0,
        )
        db_session.add(row)
        db_session.flush()
        repo = ProjectDirectorDiscussionWorkspaceRepository(db_session)
        with pytest.raises(ValueError, match="invalid_discussion_workspace_state_json"):
            repo.get_by_session_id(session_id=session_obj.id)

    def test_array_state_json(self, db_session):
        session_obj = _create_session_row(db_session)
        row = ProjectDirectorDiscussionWorkspaceTable(
            session_id=session_obj.id, project_id=None,
            topic="t", state_json="[1,2,3]",
            version_no=0, last_event_sequence_no=0,
        )
        db_session.add(row)
        db_session.flush()
        repo = ProjectDirectorDiscussionWorkspaceRepository(db_session)
        with pytest.raises(ValueError, match="invalid_discussion_workspace_state_json"):
            repo.get_by_session_id(session_id=session_obj.id)

    def test_invalid_uuid_in_state(self, db_session):
        session_obj = _create_session_row(db_session)
        row = ProjectDirectorDiscussionWorkspaceTable(
            session_id=session_obj.id, project_id=None,
            topic="t",
            state_json='{"active_option_ids": ["not-a-uuid"]}',
            version_no=0, last_event_sequence_no=0,
        )
        db_session.add(row)
        db_session.flush()
        repo = ProjectDirectorDiscussionWorkspaceRepository(db_session)
        with pytest.raises(ValueError, match="invalid_discussion_workspace_state_json"):
            repo.get_by_session_id(session_id=session_obj.id)


# ===========================================================================
# 24. Repository no auto-commit
# ===========================================================================


class TestRepositoryNoAutoCommit:
    def test_event_repository_no_commit_method(self):
        """Event Repository must not have a commit method."""
        import ast
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "app/repositories/project_director_discussion_event_repository.py",
        )
        with open(path) as f:
            source = f.read()
        assert ".commit(" not in source

    def test_workspace_repository_no_commit_method(self):
        """Workspace Repository must not have a commit method."""
        import ast
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "app/repositories/project_director_discussion_workspace_repository.py",
        )
        with open(path) as f:
            source = f.read()
        assert ".commit(" not in source

    def test_event_data_flushed_not_committed(self, db_session):
        """Repository flushes data but caller must commit."""
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e = _make_event(session_obj.id)
        _, created = repo.append_if_absent(event=e, idempotency_key="k-flush")
        assert created is True
        # Data is accessible via same session (flushed)
        found = repo.get_by_id(event_id=e.id)
        assert found is not None
        # But not committed yet - commit manually
        db_session.commit()

    def test_workspace_data_flushed_not_committed(self, db_session):
        """Repository flushes data but caller must commit."""
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionWorkspaceRepository(db_session)
        ws = _make_workspace(session_obj.id)
        _, created = repo.create_if_absent(workspace=ws)
        assert created is True
        found = repo.get_by_session_id(session_id=session_obj.id)
        assert found is not None
        db_session.commit()


# ===========================================================================
# 25. Foreign key lifecycle
# ===========================================================================


class TestForeignKeyLifecycle:
    def test_session_cascade_deletes_events(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        repo.append_if_absent(event=_make_event(session_obj.id), idempotency_key="k-cascade")
        assert _count(db_session, ProjectDirectorDiscussionEventTable) == 1
        db_session.delete(db_session.get(ProjectDirectorSessionTable, session_obj.id))
        db_session.flush()
        assert _count(db_session, ProjectDirectorDiscussionEventTable) == 0

    def test_session_cascade_deletes_workspace(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionWorkspaceRepository(db_session)
        repo.create_if_absent(workspace=_make_workspace(session_obj.id))
        assert _count(db_session, ProjectDirectorDiscussionWorkspaceTable) == 1
        db_session.delete(db_session.get(ProjectDirectorSessionTable, session_obj.id))
        db_session.flush()
        assert _count(db_session, ProjectDirectorDiscussionWorkspaceTable) == 0

    def test_superseded_event_restrict_prevents_delete(self, db_session):
        session_obj = _create_session_row(db_session)
        repo = ProjectDirectorDiscussionEventRepository(db_session)
        e1 = _make_event(session_obj.id, sequence_no=1)
        repo.append_if_absent(event=e1, idempotency_key="k-old")
        e2 = _make_event(session_obj.id, sequence_no=2, supersedes_event_id=e1.id)
        repo.append_if_absent(event=e2, idempotency_key="k-new")
        with pytest.raises(Exception):
            db_session.delete(db_session.get(ProjectDirectorDiscussionEventTable, e1.id))
            db_session.flush()
        db_session.rollback()


# ===========================================================================
# 26. Message chain isolation
# ===========================================================================


class TestMessageChainIsolation:
    def test_message_service_does_not_write_events_or_workspaces(self, db_session):
        from app.services.project_director_context_builder_service import (
            ProjectDirectorContextBuilderService,
        )
        session_obj = _create_session_row(db_session)
        msg_repo = ProjectDirectorMessageRepository(db_session)
        svc = ProjectDirectorMessageService(
            session_repository=ProjectDirectorSessionRepository(db_session),
            message_repository=msg_repo,
            context_builder=ProjectDirectorContextBuilderService(
                session_repository=ProjectDirectorSessionRepository(db_session),
                message_repository=msg_repo,
            ),
            provider_config_service=NoProviderConfigService(),
        )
        svc.post_user_message(session_id=session_obj.id, content="测试消息")
        assert _count(db_session, ProjectDirectorDiscussionEventTable) == 0
        assert _count(db_session, ProjectDirectorDiscussionWorkspaceTable) == 0
        assert _count(db_session, TaskTable) == 0
        assert _count(db_session, RunTable) == 0

    def test_message_service_does_not_import_event_repo(self):
        import ast
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "app/services/project_director_message_service.py",
        )
        with open(path) as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert "discussion_event" not in node.module
                    assert "discussion_workspace" not in node.module
