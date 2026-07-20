"""Contract tests for P26-E2-A deterministic discussion context assembly.

Verifies that current user message + TurnInterpretation + real E1 Planner +
formal facts, messages, workspace, and events produce a read-only, deterministic
DiscussionContextAssembly with correct filtering, ordering, and error handling.
"""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import begin_sqlite_transaction, configure_sqlite
from app.core.db_tables import (
    ORMBase,
    ProjectDirectorDiscussionEventTable,
    ProjectDirectorDiscussionWorkspaceTable,
    ProjectDirectorMessageTable,
    ProjectDirectorSessionTable,
)
from app.domain.project_director_conversation_intelligence import (
    ConversationMode,
    TurnInterpretation,
)
from app.domain.project_director_discussion import (
    DiscussionActorClaim,
    DiscussionDelta,
    DiscussionDeltaOperation,
    DiscussionDeltaOperationType,
    DiscussionEvent,
    DiscussionEventStatus,
    DiscussionEventType,
    DiscussionStatus,
    DiscussionWorkspace,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.repositories.project_director_discussion_event_repository import (
    ProjectDirectorDiscussionEventRepository,
)
from app.repositories.project_director_discussion_workspace_repository import (
    ProjectDirectorDiscussionWorkspaceRepository,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.services.project_director_discussion_context_builder_service import (
    ActiveDiscussionWorkspaceContext,
    DiscussionContextAssembly,
    PinnedDiscussionFormalFacts,
    ProjectDirectorDiscussionContextBuilderService,
    ResolvedDiscussionContextEvent,
)
from app.services.project_director_discussion_context_planner_service import (
    DiscussionContextPlan,
    DiscussionContextSection,
    DiscussionRetrievalDisposition,
    FormalFactContextScope,
    ProjectDirectorDiscussionContextPlannerService,
)
from app.services.project_director_discussion_workspace_reducer_service import (
    ProjectDirectorDiscussionWorkspaceReducerService,
)


# ── Constants ────────────────────────────────────────────────────────────────

SESSION_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PROJECT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
USER_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
FIXED_TIME = datetime(2026, 7, 19, 8, 30, tzinfo=timezone.utc)


# ── DB fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def db_engine(tmp_path):
    db_path = tmp_path / "p26e2a-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    event.listen(engine, "connect", configure_sqlite)
    event.listen(engine, "begin", begin_sqlite_transaction)
    ORMBase.metadata.create_all(bind=engine)
    return engine


@pytest.fixture()
def db_session_factory(db_engine):
    return sessionmaker(
        bind=db_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


@pytest.fixture()
def factory(db_session_factory):
    return db_session_factory


# ── Helpers ──────────────────────────────────────────────────────────────────


def _seed_session(db: Session, *, session_id: UUID = SESSION_ID, project_id: UUID | None = None):
    row = ProjectDirectorSessionTable(id=session_id, project_id=project_id, goal_text="E2-A 测试")
    db.add(row)
    db.flush()


def _seed_message(
    db: Session,
    session_id: UUID,
    *,
    message_id: UUID | None = None,
    role: ProjectDirectorMessageRole = ProjectDirectorMessageRole.USER,
    content: str = "消息",
    sequence_no: int = 1,
    source: ProjectDirectorMessageSource = ProjectDirectorMessageSource.SYSTEM,
    source_detail: str = "test",
    created_at: datetime = FIXED_TIME,
    related_project_id: UUID | None = None,
    requires_confirmation: bool = False,
    intent: str | None = None,
) -> UUID:
    mid = message_id or uuid4()
    row = ProjectDirectorMessageTable(
        id=mid, session_id=session_id, role=role, content=content,
        sequence_no=sequence_no, source=source, source_detail=source_detail,
        created_at=created_at, related_project_id=related_project_id,
        requires_confirmation=requires_confirmation, intent=intent,
    )
    db.add(row)
    db.flush()
    return mid


def _make_event(
    *,
    event_id: UUID | None = None,
    session_id: UUID = SESSION_ID,
    sequence_no: int = 1,
    event_type: DiscussionEventType = DiscussionEventType.TOPIC_SET,
    subject_key: str = "topic",
    content: str = "内容",
    status: DiscussionEventStatus = DiscussionEventStatus.ACTIVE,
    payload: dict | None = None,
    source_message_ids: list[UUID] | None = None,
    supersedes_event_id: UUID | None = None,
    created_by: DiscussionActorClaim = DiscussionActorClaim.USER_EXPLICIT,
) -> DiscussionEvent:
    return DiscussionEvent(
        id=event_id or uuid4(), session_id=session_id, project_id=None,
        sequence_no=sequence_no, event_type=event_type,
        subject_key=subject_key, content=content, status=status,
        payload=payload or {}, source_message_ids=source_message_ids or [USER_ID],
        supersedes_event_id=supersedes_event_id,
        created_by=created_by, confidence=1.0, created_at=FIXED_TIME,
    )


def _seed_event(db: Session, event: DiscussionEvent, *, idempotency_key: str | None = None):
    from app.core.db_tables import ProjectDirectorDiscussionEventTable as EvtTable
    import json
    row = EvtTable(
        id=event.id, session_id=event.session_id, project_id=event.project_id,
        sequence_no=event.sequence_no, event_type=event.event_type,
        subject_key=event.subject_key, content=event.content, status=event.status,
        payload_json=json.dumps(event.payload, default=str),
        source_message_ids_json=json.dumps([str(i) for i in event.source_message_ids]),
        supersedes_event_id=event.supersedes_event_id,
        created_by=event.created_by, confidence=event.confidence,
        idempotency_key=idempotency_key or f"key-{event.id}",
        created_at=event.created_at,
    )
    db.add(row)
    db.flush()


def _seed_workspace_row(db: Session, ws: DiscussionWorkspace):
    from app.core.db_tables import ProjectDirectorDiscussionWorkspaceTable as WsTable
    import json
    row = WsTable(
        session_id=ws.session_id, project_id=ws.project_id,
        topic=ws.topic, discussion_status=ws.discussion_status,
        state_json=json.dumps({
            "active_option_ids": [str(i) for i in ws.active_option_ids],
            "preferred_option_id": str(ws.preferred_option_id) if ws.preferred_option_id else None,
            "active_constraint_ids": [str(i) for i in ws.active_constraint_ids],
            "open_question_ids": [str(i) for i in ws.open_question_ids],
            "temporary_conclusion_ids": [str(i) for i in ws.temporary_conclusion_ids],
            "confirmed_decision_ids": [str(i) for i in ws.confirmed_decision_ids],
            "latest_user_correction_event_id": str(ws.latest_user_correction_event_id) if ws.latest_user_correction_event_id else None,
        }),
        version_no=ws.version_no, last_event_sequence_no=ws.last_event_sequence_no,
        created_at=ws.created_at, updated_at=ws.updated_at,
    )
    db.add(row)
    db.flush()


def _make_interpretation(
    mode: ConversationMode,
    *,
    needs_discussion_history: bool = False,
    needs_formal_fact_context: bool = False,
    needs_retrieval: bool = False,
    referenced_option_ids: list[UUID] | None = None,
    referenced_entity_ids: list[UUID] | None = None,
) -> TurnInterpretation:
    return TurnInterpretation(
        conversation_mode=mode, primary_intent="test", confidence=0.8,
        needs_discussion_history=needs_discussion_history,
        needs_formal_fact_context=needs_formal_fact_context,
        needs_retrieval=needs_retrieval,
        referenced_option_ids=referenced_option_ids or [],
        referenced_entity_ids=referenced_entity_ids or [],
        reason_summary="test reason",
    )


def _count_events(db: Session, session_id: UUID = SESSION_ID) -> int:
    return len(db.execute(
        select(ProjectDirectorDiscussionEventTable)
        .where(ProjectDirectorDiscussionEventTable.session_id == session_id)
    ).scalars().all())


def _count_messages(db: Session, session_id: UUID = SESSION_ID) -> int:
    return len(db.execute(
        select(ProjectDirectorMessageTable)
        .where(ProjectDirectorMessageTable.session_id == session_id)
    ).scalars().all())


def _count_workspaces(db: Session) -> int:
    return len(db.execute(select(ProjectDirectorDiscussionWorkspaceTable)).scalars().all())


# ═══════════════════════════════════════════════════════════════════════════
# 1. Public contracts
# ═══════════════════════════════════════════════════════════════════════════


class TestPublicContracts:
    def test_pinned_formal_facts_frozen_slots(self):
        assert is_dataclass(PinnedDiscussionFormalFacts)
        assert set(PinnedDiscussionFormalFacts.__slots__) == {
            "scope", "session_id", "project_id",
            "goal_text", "constraints", "session_status", "goal_summary", "confirmed_at",
            "latest_plan_version", "task_creation", "project_snapshot", "task_snapshot",
        }

    def test_resolved_event_frozen_slots(self):
        assert is_dataclass(ResolvedDiscussionContextEvent)
        assert set(ResolvedDiscussionContextEvent.__slots__) == {"event", "resolved_status"}

    def test_active_workspace_frozen_slots(self):
        assert is_dataclass(ActiveDiscussionWorkspaceContext)
        assert set(ActiveDiscussionWorkspaceContext.__slots__) == {"workspace", "active_events"}

    def test_assembly_frozen_slots(self):
        assert is_dataclass(DiscussionContextAssembly)
        expected = {
            "plan", "pinned_formal_facts", "recent_raw_messages",
            "active_workspace", "relevant_events", "current_user_message",
            "silent_governance_boundaries",
        }
        assert set(DiscussionContextAssembly.__slots__) == expected

    def test_service_not_dataclass(self):
        assert not is_dataclass(ProjectDirectorDiscussionContextBuilderService)

    def test_frozen_raises(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
            )
            with pytest.raises(FrozenInstanceError):
                assembly.relevant_events = ()
            db.rollback()


def _user_msg(
    *,
    message_id: UUID = USER_ID,
    content: str = "消息",
    sequence_no: int = 1,
    session_id: UUID = SESSION_ID,
    related_project_id: UUID | None = None,
    source_detail: str = "test",
    requires_confirmation: bool = False,
    created_at: datetime = FIXED_TIME,
    suggested_actions: list | None = None,
    role: ProjectDirectorMessageRole = ProjectDirectorMessageRole.USER,
) -> ProjectDirectorMessage:
    return ProjectDirectorMessage(
        id=message_id, session_id=session_id, role=role,
        content=content, sequence_no=sequence_no,
        source=ProjectDirectorMessageSource.SYSTEM, source_detail=source_detail,
        created_at=created_at, related_project_id=related_project_id,
        requires_confirmation=requires_confirmation,
        suggested_actions=suggested_actions or [],
    )


# ═══════════════════════════════════════════════════════════════════════════
# 2. Current user message validation
# ═══════════════════════════════════════════════════════════════════════════


class TestCurrentMessageValidation:
    def test_non_user_role_rejected(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            msg = ProjectDirectorMessage(
                id=USER_ID, session_id=SESSION_ID, role=ProjectDirectorMessageRole.ASSISTANT,
                content="msg", sequence_no=1, source=ProjectDirectorMessageSource.AI,
                source_detail="ai", created_at=FIXED_TIME,
            )
            with pytest.raises(ValueError, match="discussion_context_current_message_role_invalid"):
                svc.build_context(
                    session_id=SESSION_ID, project_id=None,
                    current_user_message=msg,
                    interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
                )
            db.rollback()

    def test_session_mismatch_rejected(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        other_session = uuid4()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            with pytest.raises(ValueError, match="discussion_context_current_message_session_mismatch"):
                svc.build_context(
                    session_id=SESSION_ID, project_id=None,
                    current_user_message=_user_msg(session_id=other_session),
                    interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
                )
            db.rollback()

    def test_session_not_found(self, factory):
        """Session row deleted after message seeded → session_not_found."""
        missing_session = uuid4()
        with factory() as db:
            _seed_session(db, session_id=missing_session)
            _seed_message(db, missing_session, message_id=USER_ID)
            # Delete session row but keep message
            db.execute(
                __import__("sqlalchemy").delete(ProjectDirectorSessionTable)
                .where(ProjectDirectorSessionTable.id == missing_session)
            )
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            with pytest.raises(ValueError, match="discussion_context_session_not_found"):
                svc.build_context(
                    session_id=missing_session, project_id=None,
                    current_user_message=_user_msg(session_id=missing_session),
                    interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
                )
            db.rollback()

    def test_message_not_found(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            with pytest.raises(ValueError, match="discussion_context_current_message_not_found"):
                svc.build_context(
                    session_id=SESSION_ID, project_id=None,
                    current_user_message=_user_msg(message_id=uuid4()),
                    interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
                )
            db.rollback()

    @pytest.mark.parametrize("field,value", [
        ("content", "不同内容"),
        ("sequence_no", 99),
        ("source_detail", "不同详情"),
        ("requires_confirmation", True),
    ])
    def test_message_conflict_rejected(self, factory, field, value):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID, content="用户消息", sequence_no=1)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            kwargs = {"message_id": USER_ID, "content": "用户消息", "sequence_no": 1}
            kwargs[field] = value
            msg = _user_msg(**kwargs)
            with pytest.raises(ValueError, match="discussion_context_current_message_conflict"):
                svc.build_context(
                    session_id=SESSION_ID, project_id=None,
                    current_user_message=msg,
                    interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
                )
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 3. Recent raw messages
# ═══════════════════════════════════════════════════════════════════════════


class TestRecentRawMessages:
    def test_current_message_excluded(self, factory):
        """Current message must not appear in recent_raw_messages."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=uuid4(), content="msg1", sequence_no=1)
            _seed_message(db, SESSION_ID, message_id=uuid4(), content="msg2", sequence_no=2)
            _seed_message(db, SESSION_ID, message_id=USER_ID, content="current", sequence_no=3)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(content="current", sequence_no=3),
                interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
            )
            contents = [m.content for m in assembly.recent_raw_messages]
            assert "current" not in contents
            assert "msg1" in contents
            assert "msg2" in contents
            db.rollback()

    def test_messages_after_current_excluded(self, factory):
        """Messages after current message cursor must not appear."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=uuid4(), content="before1", sequence_no=1)
            _seed_message(db, SESSION_ID, message_id=uuid4(), content="before2", sequence_no=2)
            _seed_message(db, SESSION_ID, message_id=USER_ID, content="current", sequence_no=3)
            _seed_message(db, SESSION_ID, message_id=uuid4(), content="after1", sequence_no=4)
            _seed_message(db, SESSION_ID, message_id=uuid4(), content="after2", sequence_no=5)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(content="current", sequence_no=3),
                interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
            )
            contents = [m.content for m in assembly.recent_raw_messages]
            assert contents == ["before1", "before2"]
            db.rollback()

    def test_limit_8_for_general_discussion(self, factory):
        with factory() as db:
            _seed_session(db)
            for i in range(15):
                _seed_message(db, SESSION_ID, message_id=uuid4(), content=f"msg{i}", sequence_no=i + 1)
            _seed_message(db, SESSION_ID, message_id=USER_ID, content="current", sequence_no=16)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(content="current", sequence_no=16),
                interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
            )
            assert len(assembly.recent_raw_messages) == 8
            assert assembly.plan.recent_message_limit == 8
            db.rollback()

    def test_limit_12_for_option_comparison(self, factory):
        with factory() as db:
            _seed_session(db)
            for i in range(15):
                _seed_message(db, SESSION_ID, message_id=uuid4(), content=f"msg{i}", sequence_no=i + 1)
            _seed_message(db, SESSION_ID, message_id=USER_ID, content="current", sequence_no=16)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(content="current", sequence_no=16),
                interpretation=_make_interpretation(ConversationMode.OPTION_COMPARISON),
            )
            assert len(assembly.recent_raw_messages) == 12
            assert assembly.plan.recent_message_limit == 12
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 4. Event stream guard
# ═══════════════════════════════════════════════════════════════════════════


class TestEventStreamGuard:
    def test_no_event_read_when_not_needed(self, factory):
        """GENERAL_DISCUSSION + no workspace + no history → no event read."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        class SpyEventRepo:
            def __init__(self, real):
                self._real = real
                self.list_called = False

            def list_by_session_id(self, **kw):
                self.list_called = True
                return self._real.list_by_session_id(**kw)

            def get_by_id(self, **kw):
                return self._real.get_by_id(**kw)

        with factory() as db:
            real_repo = ProjectDirectorDiscussionEventRepository(db)
            spy = SpyEventRepo(real_repo)
            svc = ProjectDirectorDiscussionContextBuilderService(
                session=db, event_repository=spy,
            )
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
            )
            assert not spy.list_called
            assert assembly.active_workspace is None
            assert assembly.relevant_events == ()
            db.rollback()

    def test_event_read_when_workspace_selected(self, factory):
        """GENERAL_DISCUSSION + workspace → event read happens."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            evt = _make_event(sequence_no=1, content="主题")
            _seed_event(db, evt)
            ws = DiscussionWorkspace(
                session_id=SESSION_ID, project_id=None, topic="主题",
                version_no=1, last_event_sequence_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()

        class SpyEventRepo:
            def __init__(self, real):
                self._real = real
                self.list_called = False

            def list_by_session_id(self, **kw):
                self.list_called = True
                return self._real.list_by_session_id(**kw)

            def get_by_id(self, **kw):
                return self._real.get_by_id(**kw)

        with factory() as db:
            real_repo = ProjectDirectorDiscussionEventRepository(db)
            spy = SpyEventRepo(real_repo)
            svc = ProjectDirectorDiscussionContextBuilderService(
                session=db, event_repository=spy,
            )
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
            )
            assert spy.list_called
            assert assembly.active_workspace is not None
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 5. Workspace/Event consistency
# ═══════════════════════════════════════════════════════════════════════════


class TestWorkspaceEventConsistency:
    def test_events_without_workspace_raises(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_event(db, _make_event(sequence_no=1))
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            with pytest.raises(ValueError, match="discussion_context_workspace_missing_for_events"):
                svc.build_context(
                    session_id=SESSION_ID, project_id=None,
                    current_user_message=_user_msg(),
                    interpretation=_make_interpretation(ConversationMode.OPTION_COMPARISON),
                )
            db.rollback()

    def test_cursor_mismatch_raises(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            evt = _make_event(sequence_no=1)
            _seed_event(db, evt)
            ws = DiscussionWorkspace(
                session_id=SESSION_ID, project_id=None, topic="",
                version_no=1, last_event_sequence_no=99,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            with pytest.raises(ValueError, match="discussion_context_workspace_event_cursor_mismatch"):
                svc.build_context(
                    session_id=SESSION_ID, project_id=None,
                    current_user_message=_user_msg(),
                    interpretation=_make_interpretation(ConversationMode.OPTION_COMPARISON),
                )
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 6. Active workspace restoration
# ═══════════════════════════════════════════════════════════════════════════


class TestActiveWorkspaceRestoration:
    def test_topic_and_options_restored(self, factory):
        oid = uuid4()
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            e1 = _make_event(sequence_no=1, content="测试主题")
            e2 = _make_event(
                sequence_no=2, event_type=DiscussionEventType.OPTION_ADDED,
                subject_key=f"option:{oid}", content="选项内容",
                payload={"option_id": oid},
            )
            _seed_event(db, e1)
            _seed_event(db, e2)
            ws = DiscussionWorkspace(
                session_id=SESSION_ID, project_id=None, topic="测试主题",
                active_option_ids=[oid], version_no=1, last_event_sequence_no=2,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
            )
            assert assembly.active_workspace is not None
            ws_ctx = assembly.active_workspace
            assert ws_ctx.workspace.topic == "测试主题"
            active_types = {e.event_type for e in ws_ctx.active_events}
            assert DiscussionEventType.TOPIC_SET in active_types
            assert DiscussionEventType.OPTION_ADDED in active_types
            db.rollback()

    def test_option_update_chain_latest_content(self, factory):
        """OPTION_ADDED → OPTION_UPDATED → OPTION_UPDATED: only latest content event."""
        oid = uuid4()
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            e1 = _make_event(
                event_id=uuid4(), sequence_no=1,
                event_type=DiscussionEventType.OPTION_ADDED,
                subject_key=f"option:{oid}", content="初始",
                payload={"option_id": oid},
            )
            e2 = _make_event(
                event_id=uuid4(), sequence_no=2,
                event_type=DiscussionEventType.OPTION_UPDATED,
                subject_key=f"option:{oid}", content="更新1",
                payload={"option_id": oid}, supersedes_event_id=e1.id,
            )
            e3 = _make_event(
                sequence_no=3,
                event_type=DiscussionEventType.OPTION_UPDATED,
                subject_key=f"option:{oid}", content="更新2",
                payload={"option_id": oid}, supersedes_event_id=e2.id,
            )
            _seed_event(db, e1)
            _seed_event(db, e2)
            _seed_event(db, e3)
            ws = DiscussionWorkspace(
                session_id=SESSION_ID, project_id=None, topic="",
                active_option_ids=[oid], version_no=1, last_event_sequence_no=3,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
            )
            ws_ctx = assembly.active_workspace
            option_events = [
                e for e in ws_ctx.active_events
                if e.event_type in (DiscussionEventType.OPTION_ADDED, DiscussionEventType.OPTION_UPDATED)
            ]
            assert len(option_events) == 1
            assert option_events[0].content == "更新2"
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 7. Resolved status
# ═══════════════════════════════════════════════════════════════════════════


class TestResolvedStatus:
    def test_superseded_event_resolved_status(self, factory):
        """An ACTIVE event that is superseded should resolve to SUPERSEDED.
        Uses OPTION_COMPARISON which includes all historical statuses."""
        e1_id = uuid4()
        e2_id = uuid4()
        oid = uuid4()
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            # e1: OPTION_ADDED (will be superseded)
            e1 = _make_event(
                event_id=e1_id, sequence_no=1,
                event_type=DiscussionEventType.OPTION_ADDED,
                subject_key=f"option:{oid}", content="旧选项",
                payload={"option_id": oid},
            )
            # e2: OPTION_UPDATED supersedes e1
            e2 = _make_event(
                event_id=e2_id, sequence_no=2,
                event_type=DiscussionEventType.OPTION_UPDATED,
                subject_key=f"option:{oid}", content="新选项",
                payload={"option_id": oid}, supersedes_event_id=e1_id,
            )
            _seed_event(db, e1)
            _seed_event(db, e2)
            # Build workspace via reducer to ensure consistency
            reducer = ProjectDirectorDiscussionWorkspaceReducerService()
            ws = reducer.rebuild_workspace(
                session_id=SESSION_ID, project_id=None,
                events=[e1, e2], version_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.OPTION_COMPARISON),
            )
            statuses = {re.event.id: re.resolved_status for re in assembly.relevant_events}
            assert statuses[e1_id] == DiscussionEventStatus.SUPERSEDED
            assert statuses[e2_id] == DiscussionEventStatus.ACTIVE
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 8. Relevant events type/status filtering
# ═══════════════════════════════════════════════════════════════════════════


class TestRelevantEventsFiltering:
    def test_type_filter(self, factory):
        """Only events matching included_event_types appear."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            # OPTION_COMPARISON includes OPTION_ADDED but not TOPIC_SET
            e1 = _make_event(sequence_no=1, content="主题")
            oid = uuid4()
            e2 = _make_event(
                sequence_no=2, event_type=DiscussionEventType.OPTION_ADDED,
                subject_key=f"option:{oid}", content="选项", payload={"option_id": oid},
            )
            _seed_event(db, e1)
            _seed_event(db, e2)
            ws = DiscussionWorkspace(
                session_id=SESSION_ID, project_id=None, topic="主题",
                active_option_ids=[oid], version_no=1, last_event_sequence_no=2,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.OPTION_COMPARISON),
            )
            types = {re.event.event_type for re in assembly.relevant_events}
            assert DiscussionEventType.OPTION_ADDED in types
            assert DiscussionEventType.TOPIC_SET not in types
            db.rollback()

    def test_no_match_returns_empty(self, factory):
        """When no events match type/status filter, returns empty."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            # Only TOPIC_SET events, but OPTION_COMPARISON doesn't include TOPIC_SET
            e1 = _make_event(sequence_no=1, content="主题")
            _seed_event(db, e1)
            ws = DiscussionWorkspace(
                session_id=SESSION_ID, project_id=None, topic="主题",
                version_no=1, last_event_sequence_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.OPTION_COMPARISON),
            )
            assert assembly.relevant_events == ()
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 9. Option reference matching
# ═══════════════════════════════════════════════════════════════════════════


class TestOptionReference:
    def test_payload_uuid_match(self, factory):
        oid = uuid4()
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            e = _make_event(
                sequence_no=1, event_type=DiscussionEventType.OPTION_ADDED,
                subject_key=f"option:{oid}", content="选项", payload={"option_id": oid},
            )
            _seed_event(db, e)
            ws = DiscussionWorkspace(
                session_id=SESSION_ID, project_id=None, topic="",
                active_option_ids=[oid], version_no=1, last_event_sequence_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(
                    ConversationMode.GENERAL_DISCUSSION,
                    referenced_option_ids=[oid],
                ),
            )
            assert len(assembly.relevant_events) > 0
            db.rollback()

    def test_subject_key_match(self, factory):
        oid = uuid4()
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            e = _make_event(
                sequence_no=1, event_type=DiscussionEventType.CONCERN_ADDED,
                subject_key=f"option:{oid}", content="关注", payload={},
            )
            _seed_event(db, e)
            ws = DiscussionWorkspace(
                session_id=SESSION_ID, project_id=None, topic="",
                version_no=1, last_event_sequence_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(
                    ConversationMode.GENERAL_DISCUSSION,
                    referenced_option_ids=[oid],
                ),
            )
            assert len(assembly.relevant_events) > 0
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 10. Entity reference deep matching
# ═══════════════════════════════════════════════════════════════════════════


class TestEntityReference:
    def test_event_id_match(self, factory):
        """Entity ID matches event.id when events are selected via needs_discussion_history."""
        eid = uuid4()
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            e = _make_event(event_id=eid, sequence_no=1, content="内容")
            _seed_event(db, e)
            reducer = ProjectDirectorDiscussionWorkspaceReducerService()
            ws = reducer.rebuild_workspace(
                session_id=SESSION_ID, project_id=None,
                events=[e], version_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(
                    ConversationMode.GENERAL_DISCUSSION,
                    needs_discussion_history=True,
                    referenced_entity_ids=[eid],
                ),
            )
            matched = [re for re in assembly.relevant_events if re.event.id == eid]
            assert len(matched) == 1
            db.rollback()

    def test_nested_payload_uuid_match(self, factory):
        """Entity ID matches UUID nested in payload when events are selected."""
        eid = uuid4()
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            e = _make_event(
                sequence_no=1, content="内容",
                payload={"nested": {"ref": eid}},
            )
            _seed_event(db, e)
            reducer = ProjectDirectorDiscussionWorkspaceReducerService()
            ws = reducer.rebuild_workspace(
                session_id=SESSION_ID, project_id=None,
                events=[e], version_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(
                    ConversationMode.GENERAL_DISCUSSION,
                    needs_discussion_history=True,
                    referenced_entity_ids=[eid],
                ),
            )
            matched = [re for re in assembly.relevant_events if re.event.id == e.id]
            assert len(matched) == 1
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 11. Input immutability and determinism
# ═══════════════════════════════════════════════════════════════════════════


class TestImmutabilityAndDeterminism:
    def test_inputs_not_mutated(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            msg = _user_msg()
            interp = _make_interpretation(ConversationMode.GENERAL_DISCUSSION)
            msg_before = msg.model_dump(mode="python")
            interp_before = interp.model_dump(mode="python")
            svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=msg, interpretation=interp,
            )
            assert msg.model_dump(mode="python") == msg_before
            assert interp.model_dump(mode="python") == interp_before
            db.rollback()

    def test_deterministic(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            msg = _user_msg()
            interp = _make_interpretation(ConversationMode.GENERAL_DISCUSSION)
            a1 = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=msg, interpretation=interp,
            )
            a2 = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=msg, interpretation=interp,
            )
            assert a1.plan == a2.plan
            assert a1.recent_raw_messages == a2.recent_raw_messages
            assert a1.relevant_events == a2.relevant_events
            db.rollback()

    def test_no_db_writes(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
            )
            assert not db.new
            assert not db.dirty
            assert not db.deleted
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 12. Formal facts scope
# ═══════════════════════════════════════════════════════════════════════════


class TestFormalFactsScope:
    def test_core_scope(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
            )
            facts = assembly.pinned_formal_facts
            assert facts.scope is FormalFactContextScope.CORE
            assert facts.latest_plan_version is None
            assert facts.task_creation is None
            db.rollback()

    def test_plan_scope(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.OPTION_COMPARISON),
            )
            assert assembly.pinned_formal_facts.scope is FormalFactContextScope.CORE_AND_PLAN
            db.rollback()

    def test_status_scope(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.STATUS_QUERY),
            )
            assert assembly.pinned_formal_facts.scope is FormalFactContextScope.CORE_AND_STATUS
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 13. Limit and ordering
# ═══════════════════════════════════════════════════════════════════════════


class TestLimitAndOrdering:
    def test_relevant_events_ordered_ascending(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            events = []
            for i in range(5):
                oid = uuid4()
                e = _make_event(
                    sequence_no=i + 1,
                    event_type=DiscussionEventType.OPTION_ADDED,
                    subject_key=f"option:{oid}", content=f"opt{i}",
                    payload={"option_id": oid},
                )
                _seed_event(db, e)
                events.append(e)
            reducer = ProjectDirectorDiscussionWorkspaceReducerService()
            ws = reducer.rebuild_workspace(
                session_id=SESSION_ID, project_id=None,
                events=events, version_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.OPTION_COMPARISON),
            )
            seqs = [re.event.sequence_no for re in assembly.relevant_events]
            assert seqs == sorted(seqs)
            db.rollback()

    def test_limit_respected(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            events = []
            for i in range(50):
                oid = uuid4()
                e = _make_event(
                    sequence_no=i + 1,
                    event_type=DiscussionEventType.OPTION_ADDED,
                    subject_key=f"option:{oid}", content=f"opt{i}",
                    payload={"option_id": oid},
                )
                _seed_event(db, e)
                events.append(e)
            reducer = ProjectDirectorDiscussionWorkspaceReducerService()
            ws = reducer.rebuild_workspace(
                session_id=SESSION_ID, project_id=None,
                events=events, version_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.OPTION_COMPARISON),
            )
            # OPTION_COMPARISON limit is 40
            assert len(assembly.relevant_events) <= 40
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 14. AST boundary
# ═══════════════════════════════════════════════════════════════════════════


class TestASTBoundary:
    @pytest.fixture(scope="class")
    def builder_ast(self):
        path = Path(__file__).parents[1] / "app/services/project_director_discussion_context_builder_service.py"
        return ast.parse(path.read_text())

    def _get_call_attrs(self, node: ast.Module) -> set[str]:
        attrs: set[str] = set()
        for n in ast.walk(node):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                attrs.add(n.func.attr)
        return attrs

    def _get_names(self, node: ast.Module) -> set[str]:
        names: set[str] = set()
        for n in ast.walk(node):
            if isinstance(n, ast.Name):
                names.add(n.id)
            elif isinstance(n, ast.Attribute):
                names.add(n.attr)
        return names

    def test_no_commit_rollback(self, builder_ast):
        attrs = self._get_call_attrs(builder_ast)
        assert "commit" not in attrs
        assert "rollback" not in attrs

    def test_no_write_operations(self, builder_ast):
        attrs = self._get_call_attrs(builder_ast)
        for forbidden in ("append_if_absent", "create_if_absent", "update_if_version"):
            assert forbidden not in attrs

    def test_no_p27_fields(self, builder_ast):
        names = self._get_names(builder_ast)
        for p27 in ("source_surface", "source_entity_type", "source_entity_id",
                     "trigger_type", "interaction_case_id", "external_context_pack_id"):
            assert p27 not in names

    def test_no_embedding_vector(self, builder_ast):
        names = self._get_names(builder_ast)
        assert "embedding" not in names
        assert "vector" not in names

    def test_no_flush_add(self, builder_ast):
        attrs = self._get_call_attrs(builder_ast)
        assert "flush" not in attrs
        assert "add" not in attrs  # session.add not used

    def test_no_create_engine_sessionmaker(self, builder_ast):
        names = self._get_names(builder_ast)
        assert "create_engine" not in names
        assert "sessionmaker" not in names

    def test_no_provider_message_service(self, builder_ast):
        names = self._get_names(builder_ast)
        assert "Provider" not in names
        assert "MessageService" not in names
        assert "DirectorResponseEnvelope" not in names
        assert "DiscussionDelta" not in names


# ═══════════════════════════════════════════════════════════════════════════
# R1: Project mismatch (§6)
# ═══════════════════════════════════════════════════════════════════════════


class TestProjectMismatch:
    def test_current_message_project_mismatch(self, factory):
        """Message.related_project_id != project_id → project_mismatch."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            # Message has related_project_id=None, but we pass project_id=PROJECT_ID
            msg = _user_msg(related_project_id=None)
            with pytest.raises(ValueError, match="discussion_context_current_message_project_mismatch"):
                svc.build_context(
                    session_id=SESSION_ID, project_id=PROJECT_ID,
                    current_user_message=msg,
                    interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
                )
            assert _count_events(db, SESSION_ID) == 0
            db.execute(select(ProjectDirectorMessageTable).limit(1))
            db.rollback()

    def test_session_project_mismatch(self, factory):
        """Session.project_id != project_id → session_project_mismatch."""
        with factory() as db:
            _seed_session(db)  # project_id=None
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            with pytest.raises(ValueError, match="discussion_context_session_project_mismatch"):
                svc.build_context(
                    session_id=SESSION_ID, project_id=PROJECT_ID,
                    current_user_message=_user_msg(related_project_id=PROJECT_ID),
                    interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
                )
            assert _count_events(db, SESSION_ID) == 0
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# R1: Message conflict extended (§7)
# ═══════════════════════════════════════════════════════════════════════════


class TestMessageConflictExtended:
    @pytest.mark.parametrize("field,value", [
        ("created_at", datetime(2027, 1, 1, tzinfo=timezone.utc)),
        ("suggested_actions", [{"action": "test"}]),
    ])
    def test_conflict_extended_fields(self, factory, field, value):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            kwargs = {"message_id": USER_ID}
            kwargs[field] = value
            msg = _user_msg(**kwargs)
            with pytest.raises(ValueError, match="discussion_context_current_message_conflict"):
                svc.build_context(
                    session_id=SESSION_ID, project_id=None,
                    current_user_message=msg,
                    interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
                )
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# R1: Pre-failure zero side effects (§8)
# ═══════════════════════════════════════════════════════════════════════════


class TestPreFailureZeroSideEffects:
    """All validation failures must have zero event reads and zero writes."""

    class SpyEventRepo:
        def __init__(self, real):
            self._real = real
            self.list_called = False

        def list_by_session_id(self, **kw):
            self.list_called = True
            return self._real.list_by_session_id(**kw)

        def get_by_id(self, **kw):
            return self._real.get_by_id(**kw)

    @pytest.mark.parametrize("error_code,kwargs", [
        ("discussion_context_current_message_role_invalid", {"msg_kwargs": {"role": ProjectDirectorMessageRole.ASSISTANT}}),
        ("discussion_context_current_message_session_mismatch", {"msg_kwargs": {"session_id": uuid4()}}),
        ("discussion_context_current_message_project_mismatch", {"build_kwargs": {"project_id": PROJECT_ID}, "msg_kwargs": {"related_project_id": None}}),
        ("discussion_context_current_message_not_found", {"msg_kwargs": {"message_id": uuid4()}}),
        ("discussion_context_current_message_conflict", {"msg_kwargs": {"content": "不同"}}),
    ])
    def test_validation_failure_zero_event_read(self, factory, error_code, kwargs):
        with factory() as db:
            _seed_session(db, **kwargs.get("session_kwargs", {}))
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        with factory() as db:
            real_repo = ProjectDirectorDiscussionEventRepository(db)
            spy = self.SpyEventRepo(real_repo)
            svc = ProjectDirectorDiscussionContextBuilderService(
                session=db, event_repository=spy,
            )
            build_kw = {"session_id": SESSION_ID, "project_id": None}
            build_kw.update(kwargs.get("build_kwargs", {}))
            msg_kw = {}
            msg_kw.update(kwargs.get("msg_kwargs", {}))
            msg = _user_msg(**msg_kw)

            events_before = _count_events(db, SESSION_ID)
            msgs_before = _count_messages(db, SESSION_ID)

            with pytest.raises(ValueError, match=error_code):
                svc.build_context(
                    **build_kw,
                    current_user_message=msg,
                    interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
                )

            assert not spy.list_called
            assert _count_events(db, SESSION_ID) == events_before
            assert _count_messages(db, SESSION_ID) == msgs_before
            assert not db.new
            assert not db.dirty
            assert not db.deleted
            db.execute(select(ProjectDirectorMessageTable).limit(1))
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# R1: STATUS_QUERY event guard (§9)
# ═══════════════════════════════════════════════════════════════════════════


class TestStatusQueryEventGuard:
    class SpyEventRepo:
        def __init__(self, real):
            self._real = real
            self.list_called = False

        def list_by_session_id(self, **kw):
            self.list_called = True
            return self._real.list_by_session_id(**kw)

        def get_by_id(self, **kw):
            return self._real.get_by_id(**kw)

    def _setup_with_workspace(self, factory, *, status=DiscussionStatus.EXPLORING):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            ws = DiscussionWorkspace(
                session_id=SESSION_ID, project_id=None, topic="",
                discussion_status=status, version_no=0, last_event_sequence_no=0,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()

    def test_status_query_default_no_event_read(self, factory):
        self._setup_with_workspace(factory)
        with factory() as db:
            real_repo = ProjectDirectorDiscussionEventRepository(db)
            spy = self.SpyEventRepo(real_repo)
            svc = ProjectDirectorDiscussionContextBuilderService(
                session=db, event_repository=spy,
            )
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.STATUS_QUERY),
            )
            assert not spy.list_called
            assert assembly.active_workspace is None
            assert assembly.relevant_events == ()
            db.rollback()

    def test_status_query_triggered_by_history(self, factory):
        self._setup_with_workspace(factory)
        with factory() as db:
            real_repo = ProjectDirectorDiscussionEventRepository(db)
            spy = self.SpyEventRepo(real_repo)
            svc = ProjectDirectorDiscussionContextBuilderService(
                session=db, event_repository=spy,
            )
            svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(
                    ConversationMode.STATUS_QUERY, needs_discussion_history=True,
                ),
            )
            assert spy.list_called
            db.rollback()

    def test_status_query_triggered_by_option_refs(self, factory):
        self._setup_with_workspace(factory)
        with factory() as db:
            real_repo = ProjectDirectorDiscussionEventRepository(db)
            spy = self.SpyEventRepo(real_repo)
            svc = ProjectDirectorDiscussionContextBuilderService(
                session=db, event_repository=spy,
            )
            svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(
                    ConversationMode.STATUS_QUERY, referenced_option_ids=[uuid4()],
                ),
            )
            assert spy.list_called
            db.rollback()

    def test_status_query_triggered_by_ready_to_formalize(self, factory):
        """READY_TO_FORMALIZE workspace triggers event read for STATUS_QUERY."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            e = _make_event(
                sequence_no=1, event_type=DiscussionEventType.FORMALIZATION_REQUESTED,
                subject_key="formalization", content="请正式化",
            )
            _seed_event(db, e)
            reducer = ProjectDirectorDiscussionWorkspaceReducerService()
            ws = reducer.rebuild_workspace(
                session_id=SESSION_ID, project_id=None,
                events=[e], version_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()
        with factory() as db:
            real_repo = ProjectDirectorDiscussionEventRepository(db)
            spy = self.SpyEventRepo(real_repo)
            svc = ProjectDirectorDiscussionContextBuilderService(
                session=db, event_repository=spy,
            )
            svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.STATUS_QUERY),
            )
            assert spy.list_called
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# R1: Workspace/Event consistency (§10)
# ═══════════════════════════════════════════════════════════════════════════


class TestWorkspaceConsistencyExtended:
    def test_workspace_session_mismatch(self, factory):
        """Stub workspace repo returns workspace with wrong session_id."""
        other_session = uuid4()
        wrong_ws = DiscussionWorkspace(
            session_id=other_session, project_id=None, topic="",
            version_no=0, last_event_sequence_no=0,
            created_at=FIXED_TIME, updated_at=FIXED_TIME,
        )

        class StubWSRepo:
            def get_by_session_id(self, **kw):
                return wrong_ws

        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(
                session=db, workspace_repository=StubWSRepo(),
            )
            with pytest.raises(ValueError, match="discussion_context_workspace_session_mismatch"):
                svc.build_context(
                    session_id=SESSION_ID, project_id=None,
                    current_user_message=_user_msg(),
                    interpretation=_make_interpretation(ConversationMode.OPTION_COMPARISON),
                )
            db.rollback()

    def test_workspace_project_mismatch(self, factory):
        """Stub workspace repo returns workspace with wrong project_id."""
        wrong_ws = DiscussionWorkspace(
            session_id=SESSION_ID, project_id=PROJECT_ID, topic="",
            version_no=0, last_event_sequence_no=0,
            created_at=FIXED_TIME, updated_at=FIXED_TIME,
        )

        class StubWSRepo:
            def get_by_session_id(self, **kw):
                return wrong_ws

        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(
                session=db, workspace_repository=StubWSRepo(),
            )
            with pytest.raises(ValueError, match="discussion_context_workspace_project_mismatch"):
                svc.build_context(
                    session_id=SESSION_ID, project_id=None,
                    current_user_message=_user_msg(),
                    interpretation=_make_interpretation(ConversationMode.OPTION_COMPARISON),
                )
            db.rollback()

    def test_projection_mismatch_topic(self, factory):
        """Workspace topic doesn't match latest effective TOPIC_SET."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            evt = _make_event(sequence_no=1, content="正确主题")
            _seed_event(db, evt)
            ws = DiscussionWorkspace(
                session_id=SESSION_ID, project_id=None, topic="错误主题",
                version_no=1, last_event_sequence_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            with pytest.raises(ValueError, match="discussion_context_workspace_projection_mismatch"):
                svc.build_context(
                    session_id=SESSION_ID, project_id=None,
                    current_user_message=_user_msg(),
                    interpretation=_make_interpretation(ConversationMode.OPTION_COMPARISON),
                )
            db.rollback()

    def test_empty_stream_version_0_workspace(self, factory):
        """Empty event stream + version 0 workspace → builds successfully."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            ws = DiscussionWorkspace(
                session_id=SESSION_ID, project_id=None, topic="",
                version_no=0, last_event_sequence_no=0,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
            )
            assert assembly.active_workspace is not None
            assert assembly.active_workspace.active_events == ()
            db.rollback()

    def test_reducer_error_passthrough(self, factory):
        """Reducer errors (duplicate event id) are not swallowed."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        dup_id = uuid4()
        e1 = _make_event(event_id=dup_id, sequence_no=1, content="a")
        e2 = _make_event(event_id=dup_id, sequence_no=2, content="b")
        ws = DiscussionWorkspace(
            session_id=SESSION_ID, project_id=None, topic="",
            version_no=1, last_event_sequence_no=2,
            created_at=FIXED_TIME, updated_at=FIXED_TIME,
        )

        class DupEventRepo:
            def list_by_session_id(self, **kw):
                return [e1, e2]
            def get_by_id(self, **kw):
                return None

        class StubWSRepo:
            def get_by_session_id(self, **kw):
                return ws

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(
                session=db, event_repository=DupEventRepo(),
                workspace_repository=StubWSRepo(),
            )
            with pytest.raises(ValueError, match="discussion_event_stream_duplicate_event_id"):
                svc.build_context(
                    session_id=SESSION_ID, project_id=None,
                    current_user_message=_user_msg(),
                    interpretation=_make_interpretation(ConversationMode.OPTION_COMPARISON),
                )
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# R1: Active workspace complete semantics (§11)
# ═══════════════════════════════════════════════════════════════════════════


class TestActiveWorkspaceComplete:
    def test_full_workspace_restoration(self, factory):
        """Complete workspace with topic, options, constraints, questions, etc."""
        oid1 = uuid4()
        oid2 = uuid4()

        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)

            e1 = _make_event(event_id=uuid4(), sequence_no=1, content="完整主题")
            e2 = _make_event(
                event_id=uuid4(), sequence_no=2,
                event_type=DiscussionEventType.OPTION_ADDED,
                subject_key=f"option:{oid1}", content="选项1初始",
                payload={"option_id": oid1},
            )
            e3 = _make_event(
                event_id=uuid4(), sequence_no=3,
                event_type=DiscussionEventType.OPTION_UPDATED,
                subject_key=f"option:{oid1}", content="选项1更新",
                payload={"option_id": oid1}, supersedes_event_id=e2.id,
            )
            e4 = _make_event(
                sequence_no=4,
                event_type=DiscussionEventType.OPTION_ADDED,
                subject_key=f"option:{oid2}", content="选项2",
                payload={"option_id": oid2},
            )
            e5 = _make_event(
                sequence_no=5,
                event_type=DiscussionEventType.OPTION_PREFERRED,
                subject_key=f"option:{oid1}", content="偏好",
                payload={"option_id": oid1},
            )
            e6 = _make_event(
                sequence_no=6,
                event_type=DiscussionEventType.CONSTRAINT_ADDED,
                subject_key="constraint", content="约束",
            )
            e7 = _make_event(
                sequence_no=7,
                event_type=DiscussionEventType.OPEN_QUESTION_ADDED,
                subject_key="open_question", content="问题",
            )
            e8 = _make_event(
                sequence_no=8,
                event_type=DiscussionEventType.TEMPORARY_CONCLUSION_ADDED,
                subject_key="temporary_conclusion", content="结论",
            )
            e9 = _make_event(
                sequence_no=9,
                event_type=DiscussionEventType.DECISION_CONFIRMED,
                subject_key="decision", content="决策",
            )
            e10 = _make_event(
                sequence_no=10,
                event_type=DiscussionEventType.USER_CORRECTION_RECORDED,
                subject_key="user_correction", content="纠正",
            )

            events = [e1, e2, e3, e4, e5, e6, e7, e8, e9, e10]
            for e in events:
                _seed_event(db, e)

            reducer = ProjectDirectorDiscussionWorkspaceReducerService()
            ws = reducer.rebuild_workspace(
                session_id=SESSION_ID, project_id=None,
                events=events, version_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
            )
            ws_ctx = assembly.active_workspace
            assert ws_ctx is not None

            active_types = {e.event_type for e in ws_ctx.active_events}

            # Topic
            assert DiscussionEventType.TOPIC_SET in active_types

            # Options: only latest content events (e3 supersedes e2)
            opt_events = [e for e in ws_ctx.active_events
                          if e.event_type in (DiscussionEventType.OPTION_ADDED, DiscussionEventType.OPTION_UPDATED)]
            # option_id in payload may be string after DB round-trip
            opt1_events = [e for e in opt_events
                           if str(e.payload.get("option_id")) == str(oid1)]
            assert len(opt1_events) == 1
            assert opt1_events[0].content == "选项1更新"

            # Preferred
            assert DiscussionEventType.OPTION_PREFERRED in active_types

            # Constraint, question, conclusion, decision, correction
            assert DiscussionEventType.CONSTRAINT_ADDED in active_types
            assert DiscussionEventType.OPEN_QUESTION_ADDED in active_types
            assert DiscussionEventType.TEMPORARY_CONCLUSION_ADDED in active_types
            assert DiscussionEventType.DECISION_CONFIRMED in active_types
            assert DiscussionEventType.USER_CORRECTION_RECORDED in active_types

            # No duplicates
            assert len(ws_ctx.active_events) == len(set(e.id for e in ws_ctx.active_events))

            # Sorted ascending
            keys = [e.sequence_no for e in ws_ctx.active_events]
            assert keys == sorted(keys)

            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# R1: Active workspace error branches (§12)
# ═══════════════════════════════════════════════════════════════════════════


class TestActiveWorkspaceErrors:
    def _build_ws_context(self, ws, events):
        """Helper to call _build_active_workspace_context directly."""
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        resolution = reducer.resolve_events(
            session_id=SESSION_ID, project_id=None, events=events,
        )
        svc = ProjectDirectorDiscussionContextBuilderService.__new__(
            ProjectDirectorDiscussionContextBuilderService
        )
        return svc._build_active_workspace_context(workspace=ws, resolution=resolution)

    def test_topic_no_effective_topic_set(self, factory):
        """Workspace has topic but no effective TOPIC_SET event exists."""
        e = _make_event(
            sequence_no=1, event_type=DiscussionEventType.CONCERN_ADDED,
            subject_key="concern", content="关注",
        )
        ws = DiscussionWorkspace(
            session_id=SESSION_ID, project_id=None, topic="某主题",
            version_no=1, last_event_sequence_no=1,
            created_at=FIXED_TIME, updated_at=FIXED_TIME,
        )
        with pytest.raises(ValueError, match="discussion_context_workspace_topic_mismatch"):
            self._build_ws_context(ws, [e])

    def test_option_missing(self, factory):
        oid = uuid4()
        e = _make_event(sequence_no=1, content="主题")
        ws = DiscussionWorkspace(
            session_id=SESSION_ID, project_id=None, topic="主题",
            active_option_ids=[oid], version_no=1, last_event_sequence_no=1,
            created_at=FIXED_TIME, updated_at=FIXED_TIME,
        )
        with pytest.raises(ValueError, match="discussion_context_workspace_option_missing"):
            self._build_ws_context(ws, [e])

    def test_preferred_reference_invalid(self, factory):
        oid = uuid4()
        e_opt = _make_event(
            sequence_no=1, event_type=DiscussionEventType.OPTION_ADDED,
            subject_key=f"option:{oid}", content="选项", payload={"option_id": oid},
        )
        ws = DiscussionWorkspace(
            session_id=SESSION_ID, project_id=None, topic="",
            active_option_ids=[oid], preferred_option_id=oid,
            version_no=1, last_event_sequence_no=1,
            created_at=FIXED_TIME, updated_at=FIXED_TIME,
        )
        with pytest.raises(ValueError, match="discussion_context_workspace_reference_invalid"):
            self._build_ws_context(ws, [e_opt])

    def test_constraint_reference_missing(self, factory):
        missing_cid = uuid4()
        e = _make_event(sequence_no=1, content="主题")
        ws = DiscussionWorkspace(
            session_id=SESSION_ID, project_id=None, topic="主题",
            active_constraint_ids=[missing_cid],
            version_no=1, last_event_sequence_no=1,
            created_at=FIXED_TIME, updated_at=FIXED_TIME,
        )
        with pytest.raises(ValueError, match="discussion_context_workspace_reference_invalid"):
            self._build_ws_context(ws, [e])

    def test_decision_reference_historical(self, factory):
        """Decision pointing to superseded event → reference invalid."""
        did = uuid4()
        e1 = _make_event(
            event_id=did, sequence_no=1,
            event_type=DiscussionEventType.DECISION_CONFIRMED,
            subject_key="decision", content="决策",
        )
        e2 = _make_event(
            sequence_no=2, event_type=DiscussionEventType.TOPIC_SET,
            content="覆盖", supersedes_event_id=did,
        )
        ws = DiscussionWorkspace(
            session_id=SESSION_ID, project_id=None, topic="覆盖",
            confirmed_decision_ids=[did],
            version_no=1, last_event_sequence_no=2,
            created_at=FIXED_TIME, updated_at=FIXED_TIME,
        )
        with pytest.raises(ValueError, match="discussion_context_workspace_reference_invalid"):
            self._build_ws_context(ws, [e1, e2])


# ═══════════════════════════════════════════════════════════════════════════
# R1: Resolved status matrix (§13)
# ═══════════════════════════════════════════════════════════════════════════


class TestResolvedStatusMatrix:
    def _resolve(self, events):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        return reducer.resolve_events(
            session_id=SESSION_ID, project_id=None, events=events,
        )

    def test_effective_active(self):
        e = _make_event(sequence_no=1, status=DiscussionEventStatus.ACTIVE)
        res = self._resolve([e])
        svc = ProjectDirectorDiscussionContextBuilderService.__new__(
            ProjectDirectorDiscussionContextBuilderService
        )
        assert svc._resolved_status(event=e, resolution=res) == DiscussionEventStatus.ACTIVE

    def test_effective_confirmed(self):
        e = _make_event(sequence_no=1, status=DiscussionEventStatus.CONFIRMED)
        res = self._resolve([e])
        svc = ProjectDirectorDiscussionContextBuilderService.__new__(
            ProjectDirectorDiscussionContextBuilderService
        )
        assert svc._resolved_status(event=e, resolution=res) == DiscussionEventStatus.CONFIRMED

    def test_rejected_not_effective(self):
        e = _make_event(sequence_no=1, status=DiscussionEventStatus.REJECTED)
        res = self._resolve([e])
        svc = ProjectDirectorDiscussionContextBuilderService.__new__(
            ProjectDirectorDiscussionContextBuilderService
        )
        assert svc._resolved_status(event=e, resolution=res) == DiscussionEventStatus.REJECTED

    def test_superseded_raw(self):
        e = _make_event(sequence_no=1, status=DiscussionEventStatus.SUPERSEDED)
        res = self._resolve([e])
        svc = ProjectDirectorDiscussionContextBuilderService.__new__(
            ProjectDirectorDiscussionContextBuilderService
        )
        assert svc._resolved_status(event=e, resolution=res) == DiscussionEventStatus.SUPERSEDED

    def test_active_superseded_by_later(self):
        e1 = _make_event(event_id=uuid4(), sequence_no=1, content="旧")
        e2 = _make_event(sequence_no=2, content="新", supersedes_event_id=e1.id)
        res = self._resolve([e1, e2])
        svc = ProjectDirectorDiscussionContextBuilderService.__new__(
            ProjectDirectorDiscussionContextBuilderService
        )
        assert svc._resolved_status(event=e1, resolution=res) == DiscussionEventStatus.SUPERSEDED
        assert svc._resolved_status(event=e2, resolution=res) == DiscussionEventStatus.ACTIVE

    def test_other_non_effective_is_historical(self):
        e = _make_event(sequence_no=1, status=DiscussionEventStatus.HISTORICAL)
        res = self._resolve([e])
        svc = ProjectDirectorDiscussionContextBuilderService.__new__(
            ProjectDirectorDiscussionContextBuilderService
        )
        assert svc._resolved_status(event=e, resolution=res) == DiscussionEventStatus.HISTORICAL

    def test_raw_status_unchanged(self):
        e = _make_event(
            sequence_no=1, status=DiscussionEventStatus.ACTIVE,
            event_id=uuid4(),
        )
        e2 = _make_event(sequence_no=2, content="新", supersedes_event_id=e.id)
        res = self._resolve([e, e2])
        svc = ProjectDirectorDiscussionContextBuilderService.__new__(
            ProjectDirectorDiscussionContextBuilderService
        )
        svc._resolved_status(event=e, resolution=res)
        assert e.status == DiscussionEventStatus.ACTIVE  # unchanged


# ═══════════════════════════════════════════════════════════════════════════
# R1: Relevant event status filtering (§14)
# ═══════════════════════════════════════════════════════════════════════════


class TestRelevantEventStatusFiltering:
    def test_general_discussion_excludes_rejected_superseded(self, factory):
        """GENERAL_DISCUSSION + history: only ACTIVE and CONFIRMED."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            e_active = _make_event(sequence_no=1, content="active")
            e_confirmed = _make_event(
                sequence_no=2, status=DiscussionEventStatus.CONFIRMED,
                content="confirmed",
            )
            e_rejected = _make_event(
                event_id=uuid4(), sequence_no=3,
                status=DiscussionEventStatus.REJECTED, content="rejected",
            )
            e_superseded_target = _make_event(
                event_id=uuid4(), sequence_no=4, content="to-be-superseded",
            )
            e_superseder = _make_event(
                sequence_no=5, content="superseder",
                supersedes_event_id=e_superseded_target.id,
            )
            events = [e_active, e_confirmed, e_rejected, e_superseded_target, e_superseder]
            for e in events:
                _seed_event(db, e)
            reducer = ProjectDirectorDiscussionWorkspaceReducerService()
            ws = reducer.rebuild_workspace(
                session_id=SESSION_ID, project_id=None,
                events=events, version_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(
                    ConversationMode.GENERAL_DISCUSSION, needs_discussion_history=True,
                ),
            )
            statuses = {re.resolved_status for re in assembly.relevant_events}
            assert DiscussionEventStatus.ACTIVE in statuses
            assert DiscussionEventStatus.CONFIRMED in statuses
            assert DiscussionEventStatus.REJECTED not in statuses
            assert DiscussionEventStatus.SUPERSEDED not in statuses
            db.rollback()

    def test_option_comparison_includes_all_statuses(self, factory):
        """OPTION_COMPARISON: ACTIVE, CONFIRMED, REJECTED, SUPERSEDED."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            # Use concern/assumption events which don't require active options
            e_active = _make_event(
                sequence_no=1, event_type=DiscussionEventType.CONCERN_ADDED,
                subject_key="concern", content="active concern",
            )
            e_confirmed = _make_event(
                event_id=uuid4(), sequence_no=2,
                event_type=DiscussionEventType.CONCERN_ADDED,
                subject_key="concern", content="confirmed concern",
                status=DiscussionEventStatus.CONFIRMED,
            )
            e_rejected = _make_event(
                event_id=uuid4(), sequence_no=3,
                event_type=DiscussionEventType.CONCERN_ADDED,
                subject_key="concern", content="rejected concern",
                status=DiscussionEventStatus.REJECTED,
            )
            e_target = _make_event(
                event_id=uuid4(), sequence_no=4,
                event_type=DiscussionEventType.CONCERN_ADDED,
                subject_key="concern", content="to-supersede",
            )
            e_superseder = _make_event(
                sequence_no=5, event_type=DiscussionEventType.CONCERN_ADDED,
                subject_key="concern", content="superseder",
                supersedes_event_id=e_target.id,
            )
            events = [e_active, e_confirmed, e_rejected, e_target, e_superseder]
            for e in events:
                _seed_event(db, e)
            reducer = ProjectDirectorDiscussionWorkspaceReducerService()
            ws = reducer.rebuild_workspace(
                session_id=SESSION_ID, project_id=None,
                events=events, version_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.OPTION_COMPARISON),
            )
            statuses = {re.resolved_status for re in assembly.relevant_events}
            assert DiscussionEventStatus.ACTIVE in statuses
            assert DiscussionEventStatus.CONFIRMED in statuses
            assert DiscussionEventStatus.REJECTED in statuses
            assert DiscussionEventStatus.SUPERSEDED in statuses
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# R1: Option reference negative cases (§15)
# ═══════════════════════════════════════════════════════════════════════════


class TestOptionReferenceNegative:
    def test_other_option_id_not_matched(self, factory):
        """Event for option A should not match reference to option B."""
        oid_a = uuid4()
        oid_b = uuid4()
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            e = _make_event(
                sequence_no=1, event_type=DiscussionEventType.OPTION_ADDED,
                subject_key=f"option:{oid_a}", content="选项A",
                payload={"option_id": oid_a},
            )
            _seed_event(db, e)
            reducer = ProjectDirectorDiscussionWorkspaceReducerService()
            ws = reducer.rebuild_workspace(
                session_id=SESSION_ID, project_id=None,
                events=[e], version_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(
                    ConversationMode.GENERAL_DISCUSSION,
                    needs_discussion_history=True,
                    referenced_option_ids=[oid_b],
                ),
            )
            assert len(assembly.relevant_events) == 0
            db.rollback()

    def test_uuid_in_content_not_option_match(self, factory):
        """UUID in content text should not match option reference."""
        oid = uuid4()
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            e = _make_event(
                sequence_no=1, event_type=DiscussionEventType.CONCERN_ADDED,
                subject_key="concern", content=f"提到 {oid} 但不是选项",
            )
            _seed_event(db, e)
            reducer = ProjectDirectorDiscussionWorkspaceReducerService()
            ws = reducer.rebuild_workspace(
                session_id=SESSION_ID, project_id=None,
                events=[e], version_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(
                    ConversationMode.GENERAL_DISCUSSION,
                    needs_discussion_history=True,
                    referenced_option_ids=[oid],
                ),
            )
            # Should NOT match via option reference (content is not a reference source)
            assert len(assembly.relevant_events) == 0
            db.rollback()

    def test_option_id_not_from_event_id(self, factory):
        """Option reference should match payload option_id, not event.id."""
        oid = uuid4()
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            # Event ID happens to equal the option ID we're looking for
            e = _make_event(
                event_id=oid, sequence_no=1,
                event_type=DiscussionEventType.CONCERN_ADDED,
                subject_key="concern", content="关注",
            )
            _seed_event(db, e)
            reducer = ProjectDirectorDiscussionWorkspaceReducerService()
            ws = reducer.rebuild_workspace(
                session_id=SESSION_ID, project_id=None,
                events=[e], version_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(
                    ConversationMode.GENERAL_DISCUSSION,
                    needs_discussion_history=True,
                    referenced_option_ids=[oid],
                ),
            )
            # Option reference should NOT match via event.id
            assert len(assembly.relevant_events) == 0
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# R1: Entity reference full coverage (§16)
# ═══════════════════════════════════════════════════════════════════════════


class TestEntityReferenceFull:
    def _build_with_entity(self, factory, e, entity_ids):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_event(db, e)
            reducer = ProjectDirectorDiscussionWorkspaceReducerService()
            ws = reducer.rebuild_workspace(
                session_id=SESSION_ID, project_id=None,
                events=[e], version_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(
                    ConversationMode.GENERAL_DISCUSSION,
                    needs_discussion_history=True,
                    referenced_entity_ids=entity_ids,
                ),
            )
            return assembly

    def test_match_via_supersedes_event_id(self, factory):
        target_id = uuid4()
        e_target = _make_event(event_id=target_id, sequence_no=1, content="被覆盖")
        e = _make_event(
            sequence_no=2, content="内容",
            supersedes_event_id=target_id,
        )
        # Need both events for DB consistency
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_event(db, e_target)
            _seed_event(db, e)
            reducer = ProjectDirectorDiscussionWorkspaceReducerService()
            ws = reducer.rebuild_workspace(
                session_id=SESSION_ID, project_id=None,
                events=[e_target, e], version_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(
                    ConversationMode.GENERAL_DISCUSSION,
                    needs_discussion_history=True,
                    referenced_entity_ids=[target_id],
                ),
            )
            assert len(assembly.relevant_events) > 0
            db.rollback()

    def test_match_via_source_message_ids(self, factory):
        mid = uuid4()
        e = _make_event(sequence_no=1, content="内容", source_message_ids=[mid])
        assembly = self._build_with_entity(factory, e, [mid])
        assert len(assembly.relevant_events) > 0

    def test_match_via_subject_key_uuid(self, factory):
        eid = uuid4()
        e = _make_event(sequence_no=1, subject_key=f"ref:{eid}", content="内容")
        assembly = self._build_with_entity(factory, e, [eid])
        assert len(assembly.relevant_events) > 0

    def test_match_via_payload_top_level(self, factory):
        eid = uuid4()
        e = _make_event(sequence_no=1, content="内容", payload={"ref": eid})
        assembly = self._build_with_entity(factory, e, [eid])
        assert len(assembly.relevant_events) > 0

    def test_match_via_payload_list(self, factory):
        eid = uuid4()
        e = _make_event(sequence_no=1, content="内容", payload={"refs": [eid]})
        assembly = self._build_with_entity(factory, e, [eid])
        assert len(assembly.relevant_events) > 0

    def test_match_via_payload_tuple(self, factory):
        eid = uuid4()
        e = _make_event(sequence_no=1, content="内容", payload={"refs": (eid,)})
        assembly = self._build_with_entity(factory, e, [eid])
        assert len(assembly.relevant_events) > 0

    def test_match_via_payload_uuid_string(self, factory):
        eid = uuid4()
        e = _make_event(sequence_no=1, content="内容", payload={"ref": str(eid)})
        assembly = self._build_with_entity(factory, e, [eid])
        assert len(assembly.relevant_events) > 0

    def test_no_match_payload_key_only(self, factory):
        eid = uuid4()
        e = _make_event(sequence_no=1, content="内容", payload={str(eid): "value"})
        assembly = self._build_with_entity(factory, e, [eid])
        assert len(assembly.relevant_events) == 0

    def test_no_match_partial_uuid_in_subject(self, factory):
        eid = uuid4()
        partial = str(eid)[:8]
        e = _make_event(sequence_no=1, subject_key=f"ref:{partial}", content="内容")
        assembly = self._build_with_entity(factory, e, [eid])
        assert len(assembly.relevant_events) == 0

    def test_option_and_entity_or_semantics(self, factory):
        """When both option_ids and entity_ids, matching either (OR) is sufficient."""
        oid = uuid4()
        eid = uuid4()
        e = _make_event(
            sequence_no=1, event_type=DiscussionEventType.OPTION_ADDED,
            subject_key=f"option:{oid}", content="选项", payload={"option_id": oid},
        )

        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_event(db, e)
            reducer = ProjectDirectorDiscussionWorkspaceReducerService()
            ws = reducer.rebuild_workspace(
                session_id=SESSION_ID, project_id=None,
                events=[e], version_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()

        # Only entity_ids (eid doesn't match) → no match
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(
                    ConversationMode.GENERAL_DISCUSSION,
                    needs_discussion_history=True,
                    referenced_entity_ids=[eid],
                ),
            )
            assert len(assembly.relevant_events) == 0
            db.rollback()

        # Both option_ids and entity_ids — oid matches via option reference
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(
                    ConversationMode.GENERAL_DISCUSSION,
                    needs_discussion_history=True,
                    referenced_option_ids=[oid],
                    referenced_entity_ids=[eid],
                ),
            )
            assert len(assembly.relevant_events) > 0
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# R1: Limit exact semantics (§17)
# ═══════════════════════════════════════════════════════════════════════════


class TestLimitExactSemantics:
    def test_limit_40_keeps_latest(self, factory):
        """50 events, limit 40 → keeps seq 11..50."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            events = []
            for i in range(50):
                oid = uuid4()
                e = _make_event(
                    sequence_no=i + 1,
                    event_type=DiscussionEventType.OPTION_ADDED,
                    subject_key=f"option:{oid}", content=f"opt{i}",
                    payload={"option_id": oid},
                )
                _seed_event(db, e)
                events.append(e)
            reducer = ProjectDirectorDiscussionWorkspaceReducerService()
            ws = reducer.rebuild_workspace(
                session_id=SESSION_ID, project_id=None,
                events=events, version_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.OPTION_COMPARISON),
            )
            assert len(assembly.relevant_events) == 40
            seqs = [re.event.sequence_no for re in assembly.relevant_events]
            assert seqs == list(range(11, 51))
            assert seqs == sorted(seqs)
            db.rollback()

    def test_limit_30_keeps_latest(self, factory):
        """40 events, CONSTRAINT_UPDATE limit 30 → keeps seq 11..40."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            events = []
            for i in range(40):
                e = _make_event(
                    sequence_no=i + 1,
                    event_type=DiscussionEventType.CONSTRAINT_ADDED,
                    subject_key="constraint", content=f"c{i}",
                )
                _seed_event(db, e)
                events.append(e)
            reducer = ProjectDirectorDiscussionWorkspaceReducerService()
            ws = reducer.rebuild_workspace(
                session_id=SESSION_ID, project_id=None,
                events=events, version_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.CONSTRAINT_UPDATE),
            )
            assert len(assembly.relevant_events) == 30
            seqs = [re.event.sequence_no for re in assembly.relevant_events]
            assert seqs == list(range(11, 41))
            db.rollback()

    def test_limit_20_keeps_latest(self, factory):
        """30 events, GENERAL_DISCUSSION + history limit 20 → keeps seq 11..30."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            events = []
            for i in range(30):
                e = _make_event(sequence_no=i + 1, content=f"msg{i}")
                _seed_event(db, e)
                events.append(e)
            reducer = ProjectDirectorDiscussionWorkspaceReducerService()
            ws = reducer.rebuild_workspace(
                session_id=SESSION_ID, project_id=None,
                events=events, version_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(
                    ConversationMode.GENERAL_DISCUSSION, needs_discussion_history=True,
                ),
            )
            assert len(assembly.relevant_events) == 20
            seqs = [re.event.sequence_no for re in assembly.relevant_events]
            assert seqs == list(range(11, 31))
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# R1: DEFERRED_TO_P28 (§18)
# ═══════════════════════════════════════════════════════════════════════════


class TestDeferredToP28:
    def test_deferred_with_history(self, factory):
        """needs_retrieval=True + needs_discussion_history=True → deferred but events still assembled."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            e = _make_event(sequence_no=1, content="主题")
            _seed_event(db, e)
            reducer = ProjectDirectorDiscussionWorkspaceReducerService()
            ws = reducer.rebuild_workspace(
                session_id=SESSION_ID, project_id=None,
                events=[e], version_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(
                    ConversationMode.GENERAL_DISCUSSION,
                    needs_discussion_history=True,
                    needs_retrieval=True,
                ),
            )
            assert assembly.plan.retrieval_disposition is DiscussionRetrievalDisposition.DEFERRED_TO_P28
            assert DiscussionContextSection.RELEVANT_DISCUSSION_EVENTS in assembly.plan.selected_sections
            assert len(assembly.relevant_events) > 0
            db.rollback()

    def test_deferred_without_history(self, factory):
        """needs_retrieval=True but no history trigger → no events read."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        class SpyEventRepo:
            def __init__(self, real):
                self._real = real
                self.list_called = False

            def list_by_session_id(self, **kw):
                self.list_called = True
                return self._real.list_by_session_id(**kw)

            def get_by_id(self, **kw):
                return self._real.get_by_id(**kw)

        with factory() as db:
            real_repo = ProjectDirectorDiscussionEventRepository(db)
            spy = SpyEventRepo(real_repo)
            svc = ProjectDirectorDiscussionContextBuilderService(
                session=db, event_repository=spy,
            )
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(
                    ConversationMode.GENERAL_DISCUSSION,
                    needs_retrieval=True,
                ),
            )
            assert assembly.plan.retrieval_disposition is DiscussionRetrievalDisposition.DEFERRED_TO_P28
            assert assembly.relevant_events == ()
            assert not spy.list_called
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# R1: Formal facts deepcopy (§19)
# ═══════════════════════════════════════════════════════════════════════════


class TestFormalFactsDeepcopy:
    def test_core_all_extended_none(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
            )
            facts = assembly.pinned_formal_facts
            assert facts.scope is FormalFactContextScope.CORE
            assert facts.latest_plan_version is None
            assert facts.task_creation is None
            assert facts.project_snapshot is None
            assert facts.task_snapshot is None
            db.rollback()

    def test_plan_scope_only_latest_plan_version(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.OPTION_COMPARISON),
            )
            facts = assembly.pinned_formal_facts
            assert facts.scope is FormalFactContextScope.CORE_AND_PLAN
            # latest_plan_version may be None (no plan exists) but field is present
            assert facts.task_creation is None
            assert facts.project_snapshot is None
            assert facts.task_snapshot is None
            db.rollback()

    def test_status_scope_all_fields(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.STATUS_QUERY),
            )
            facts = assembly.pinned_formal_facts
            assert facts.scope is FormalFactContextScope.CORE_AND_STATUS
            # All four fields present (may be None if no data)
            assert hasattr(facts, "latest_plan_version")
            assert hasattr(facts, "task_creation")
            assert hasattr(facts, "project_snapshot")
            assert hasattr(facts, "task_snapshot")
            db.rollback()

    def test_deepcopy_isolation(self, factory):
        """Modify source dict after build → assembly unchanged."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        class SpyFormalBuilder:
            def __init__(self):
                self.nested = {"key": ["original"]}
                self.call_count = 0

            def build_context(self, session_id):
                self.call_count += 1

                class Ctx:
                    pass

                ctx = Ctx()
                ctx.session_id = session_id
                ctx.project_id = None
                ctx.goal_text = "goal"
                ctx.constraints = ""
                ctx.session_status = "draft"
                ctx.goal_summary = ""
                ctx.confirmed_at = None
                ctx.latest_plan_version = self.nested
                ctx.task_creation = self.nested
                ctx.project_snapshot = self.nested
                ctx.task_snapshot = self.nested
                ctx.safety_boundary = ["boundary"]
                return ctx

        spy_builder = SpyFormalBuilder()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(
                session=db, formal_context_builder=spy_builder,
            )
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.STATUS_QUERY),
            )
            # Modify source
            spy_builder.nested["key"].append("modified")
            spy_builder.nested["new_key"] = "new"

            facts = assembly.pinned_formal_facts
            # Assembly should have original copy
            assert facts.latest_plan_version == {"key": ["original"]}
            assert "new_key" not in facts.latest_plan_version
            db.rollback()

    def test_no_clarifying_fields_leaked(self, factory):
        """Assembly field names must not include clarifying_questions/answers."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            assembly = svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
            )
            field_names = {f.name for f in fields(assembly)}
            assert "clarifying_questions" not in field_names
            assert "clarifying_answers" not in field_names
            assert "recent_messages" not in field_names
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# R1: Read-only and caller transaction (§20)
# ═══════════════════════════════════════════════════════════════════════════


class TestReadOnlyAndCallerTransaction:
    def test_no_writes_on_success(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        with factory() as db:
            msgs_before = _count_messages(db, SESSION_ID)
            evts_before = _count_events(db, SESSION_ID)
            wss_before = _count_workspaces(db)

            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
            )

            assert _count_messages(db, SESSION_ID) == msgs_before
            assert _count_events(db, SESSION_ID) == evts_before
            assert _count_workspaces(db) == wss_before
            assert not db.new
            assert not db.dirty
            assert not db.deleted
            db.rollback()

    def test_no_writes_with_workspace_events(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            e = _make_event(sequence_no=1, content="主题")
            _seed_event(db, e)
            reducer = ProjectDirectorDiscussionWorkspaceReducerService()
            ws = reducer.rebuild_workspace(
                session_id=SESSION_ID, project_id=None,
                events=[e], version_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()
        with factory() as db:
            msgs_before = _count_messages(db, SESSION_ID)
            evts_before = _count_events(db, SESSION_ID)
            wss_before = _count_workspaces(db)

            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            svc.build_context(
                session_id=SESSION_ID, project_id=None,
                current_user_message=_user_msg(),
                interpretation=_make_interpretation(ConversationMode.GENERAL_DISCUSSION),
            )

            assert _count_messages(db, SESSION_ID) == msgs_before
            assert _count_events(db, SESSION_ID) == evts_before
            assert _count_workspaces(db) == wss_before
            assert not db.new
            assert not db.dirty
            assert not db.deleted
            db.rollback()

    def test_no_writes_on_consistency_failure(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            evt = _make_event(sequence_no=1)
            _seed_event(db, evt)
            ws = DiscussionWorkspace(
                session_id=SESSION_ID, project_id=None, topic="错误",
                version_no=1, last_event_sequence_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            _seed_workspace_row(db, ws)
            db.commit()
        with factory() as db:
            msgs_before = _count_messages(db, SESSION_ID)
            evts_before = _count_events(db, SESSION_ID)

            svc = ProjectDirectorDiscussionContextBuilderService(session=db)
            with pytest.raises(ValueError, match="discussion_context_workspace_projection_mismatch"):
                svc.build_context(
                    session_id=SESSION_ID, project_id=None,
                    current_user_message=_user_msg(),
                    interpretation=_make_interpretation(ConversationMode.OPTION_COMPARISON),
                )

            assert _count_messages(db, SESSION_ID) == msgs_before
            assert _count_events(db, SESSION_ID) == evts_before
            assert not db.new
            assert not db.dirty
            assert not db.deleted
            db.execute(select(ProjectDirectorMessageTable).limit(1))
            db.rollback()
