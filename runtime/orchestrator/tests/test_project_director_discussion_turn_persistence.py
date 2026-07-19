"""Contract tests for P26-D3-A transactional assistant turn persistence.

Verifies that assistant message, discussion events, and workspace are
persisted in one caller-owned savepoint, with correct replay, conflict,
rollback, and error propagation semantics.
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
from app.domain.project_director_discussion import (
    DiscussionActorClaim,
    DiscussionDelta,
    DiscussionDeltaOperation,
    DiscussionDeltaOperationType,
    DiscussionEvent,
    DiscussionEventStatus,
    DiscussionEventType,
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
from app.services.project_director_discussion_delta_apply_service import (
    DiscussionDeltaApplyStatus,
    GovernedDiscussionDeltaApplyResult,
    ProjectDirectorDiscussionDeltaApplyService,
)
from app.services.project_director_discussion_turn_persistence_service import (
    PersistedDiscussionTurnResult,
    ProjectDirectorDiscussionTurnPersistenceService,
)


# ── Constants ────────────────────────────────────────────────────────────────

SESSION_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PROJECT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
ASSISTANT_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
USER_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
SYSTEM_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
FIXED_TIME = datetime(2026, 7, 19, 8, 30, tzinfo=timezone.utc)


# ── DB fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def db_engine(tmp_path):
    db_path = tmp_path / "p26d3a-test.db"
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


def _seed_session(db: Session, *, session_id: UUID = SESSION_ID, project_id: UUID | None = None) -> UUID:
    row = ProjectDirectorSessionTable(id=session_id, project_id=project_id, goal_text="D3-A 测试")
    db.add(row)
    db.flush()
    return session_id


def _seed_message(
    db: Session,
    session_id: UUID,
    *,
    message_id: UUID | None = None,
    role: ProjectDirectorMessageRole = ProjectDirectorMessageRole.USER,
    content: str = "消息",
    sequence_no: int = 1,
) -> UUID:
    mid = message_id or uuid4()
    row = ProjectDirectorMessageTable(
        id=mid, session_id=session_id, role=role, content=content,
        sequence_no=sequence_no, source=ProjectDirectorMessageSource.SYSTEM, source_detail="test",
    )
    db.add(row)
    db.flush()
    return mid


# ── Domain helpers ───────────────────────────────────────────────────────────


def make_message(
    *,
    message_id: UUID | None = None,
    session_id: UUID = SESSION_ID,
    role: ProjectDirectorMessageRole = ProjectDirectorMessageRole.USER,
    content: str = "消息",
    sequence_no: int = 1,
    created_at: datetime = FIXED_TIME,
    related_project_id: UUID | None = None,
    source: ProjectDirectorMessageSource = ProjectDirectorMessageSource.AI,
    source_detail: str = "detail",
    intent: str | None = None,
    requires_confirmation: bool = False,
    suggested_actions: list | None = None,
) -> ProjectDirectorMessage:
    return ProjectDirectorMessage(
        id=message_id or uuid4(), session_id=session_id, role=role, content=content,
        sequence_no=sequence_no, source=source, source_detail=source_detail,
        created_at=created_at, related_project_id=related_project_id,
        intent=intent, requires_confirmation=requires_confirmation,
        suggested_actions=suggested_actions or [],
    )


def assistant_msg(**kwargs) -> ProjectDirectorMessage:
    defaults = dict(
        message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT,
        content="助手回复", sequence_no=2, source=ProjectDirectorMessageSource.AI,
        source_detail="ai",
    )
    defaults.update(kwargs)
    return make_message(**defaults)


def user_msg(**kwargs) -> ProjectDirectorMessage:
    return make_message(message_id=USER_ID, **kwargs)


def make_operation(
    *,
    op: DiscussionDeltaOperationType = DiscussionDeltaOperationType.ADD_CONCERN,
    actor_claim: DiscussionActorClaim = DiscussionActorClaim.USER_EXPLICIT,
    content: str = "内容",
    source_message_ids: list[UUID] | None = None,
) -> DiscussionDeltaOperation:
    if source_message_ids is None:
        source_message_ids = {
            DiscussionActorClaim.USER_EXPLICIT: [USER_ID],
            DiscussionActorClaim.USER_INFERRED: [USER_ID],
            DiscussionActorClaim.ASSISTANT_PROPOSAL: [ASSISTANT_ID],
            DiscussionActorClaim.SYSTEM_FACT: [],
            DiscussionActorClaim.FORMAL_PROJECT_FACT: [],
        }[actor_claim]
    return DiscussionDeltaOperation(
        op=op, actor_claim=actor_claim, content=content,
        source_message_ids=source_message_ids,
    )


def make_delta(*operations: DiscussionDeltaOperation) -> DiscussionDelta:
    return DiscussionDelta(operations=list(operations))


def _count_events(db: Session, session_id: UUID = SESSION_ID) -> int:
    return len(
        db.execute(
            select(ProjectDirectorDiscussionEventTable)
            .where(ProjectDirectorDiscussionEventTable.session_id == session_id)
        ).scalars().all()
    )


def _count_workspaces(db: Session) -> int:
    return len(db.execute(select(ProjectDirectorDiscussionWorkspaceTable)).scalars().all())


def _count_messages(db: Session, session_id: UUID = SESSION_ID) -> int:
    return len(
        db.execute(
            select(ProjectDirectorMessageTable)
            .where(ProjectDirectorMessageTable.session_id == session_id)
        ).scalars().all()
    )


def _get_workspace(db: Session, session_id: UUID = SESSION_ID):
    return db.get(ProjectDirectorDiscussionWorkspaceTable, session_id)


def _get_message(db: Session, message_id: UUID):
    return db.get(ProjectDirectorMessageTable, message_id)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Public contracts
# ═══════════════════════════════════════════════════════════════════════════


class TestPublicContracts:
    def test_result_frozen_slots(self):
        assert is_dataclass(PersistedDiscussionTurnResult)
        assert set(PersistedDiscussionTurnResult.__slots__) == {
            "assistant_message", "assistant_message_inserted", "delta_apply_result",
        }
        assert {f.name for f in fields(PersistedDiscussionTurnResult)} == {
            "assistant_message", "assistant_message_inserted", "delta_apply_result",
        }

    def test_result_field_assignment_raises(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            result = svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(),
            )
            with pytest.raises(FrozenInstanceError):
                result.assistant_message_inserted = False
            with pytest.raises(FrozenInstanceError):
                result.assistant_message = user_msg()
            db.rollback()

    def test_constructor_signature(self, factory):
        """Service accepts session, optional message_repo, optional delta_apply."""
        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            assert svc is not None
            # With explicit repos
            svc2 = ProjectDirectorDiscussionTurnPersistenceService(
                session=db,
                message_repository=ProjectDirectorMessageRepository(db),
                delta_apply_service=ProjectDirectorDiscussionDeltaApplyService(db),
            )
            assert svc2 is not None


# ═══════════════════════════════════════════════════════════════════════════
# 2. Input validation
# ═══════════════════════════════════════════════════════════════════════════


class TestInputValidation:
    def test_non_assistant_role_rejected(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        with factory() as db:
            events_before = _count_events(db, SESSION_ID)
            ws_before = _count_workspaces(db)
            msg_before = _count_messages(db, SESSION_ID)
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            with pytest.raises(ValueError, match="discussion_turn_assistant_message_role_invalid"):
                svc.persist_assistant_turn(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=make_message(
                        message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.USER,
                        sequence_no=2,
                    ),
                    available_messages=[user_msg()],
                    delta=make_delta(),
                )
            assert _count_events(db, SESSION_ID) == events_before
            assert _count_workspaces(db) == ws_before
            assert _count_messages(db, SESSION_ID) == msg_before
            db.rollback()

    def test_session_mismatch_rejected(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            with pytest.raises(ValueError, match="discussion_turn_assistant_message_session_mismatch"):
                svc.persist_assistant_turn(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(session_id=uuid4()),
                    available_messages=[user_msg()],
                    delta=make_delta(),
                )
            assert _count_messages(db, SESSION_ID) == 1
            db.rollback()

    def test_project_mismatch_rejected(self, factory):
        with factory() as db:
            _seed_session(db)  # project_id=None
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            with pytest.raises(ValueError, match="discussion_turn_assistant_message_project_mismatch"):
                svc.persist_assistant_turn(
                    session_id=SESSION_ID, project_id=PROJECT_ID,
                    assistant_message=assistant_msg(related_project_id=None),
                    available_messages=[user_msg()],
                    delta=make_delta(),
                )
            db.rollback()

    def test_sequence_mismatch_rejected(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            with pytest.raises(ValueError, match="discussion_turn_assistant_message_sequence_mismatch"):
                svc.persist_assistant_turn(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(sequence_no=99),
                    available_messages=[user_msg()],
                    delta=make_delta(),
                )
            assert _count_messages(db, SESSION_ID) == 1
            assert _count_events(db, SESSION_ID) == 0
            assert _count_workspaces(db) == 0
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 3. First APPLIED turn
# ═══════════════════════════════════════════════════════════════════════════


class TestFirstAppliedTurn:
    def test_applied_turn_visible_in_session(self, factory):
        """Message + Event + Workspace visible in same caller session."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            result = svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation()),
            )
            assert result.assistant_message_inserted is True
            assert result.delta_apply_result.status is DiscussionDeltaApplyStatus.APPLIED

            # Visible in same session
            assert _count_messages(db, SESSION_ID) == 2
            assert _count_events(db, SESSION_ID) == 1
            ws = _get_workspace(db)
            assert ws is not None
            assert ws.version_no == 1
            assert ws.last_event_sequence_no == 1
            db.rollback()

    def test_applied_turn_committed_persists(self, factory):
        """After caller commit, all three persist in new session."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            result = svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation()),
            )
            assert result.assistant_message_inserted is True
            db.commit()

        with factory() as db:
            assert _count_messages(db, SESSION_ID) == 2
            assert _count_events(db, SESSION_ID) == 1
            ws = _get_workspace(db)
            assert ws is not None
            assert ws.version_no == 1

    def test_p27_fields_none(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            result = svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation()),
            )
            evt = result.delta_apply_result.persisted_events[0].event
            for name in ("source_surface", "source_entity_type", "source_entity_id",
                          "trigger_type", "interaction_case_id", "external_context_pack_id"):
                assert getattr(evt, name) is None
            db.rollback()

    def test_message_fields_preserved(self, factory):
        """Assistant message fields survive persistence."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        asst = assistant_msg(
            source_detail="custom_detail", intent="test_intent",
            requires_confirmation=True, suggested_actions=[{"action": "test"}],
        )
        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            result = svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=asst,
                available_messages=[user_msg()],
                delta=make_delta(make_operation()),
            )
            persisted = result.assistant_message
            assert persisted.content == "助手回复"
            assert persisted.source_detail == "custom_detail"
            assert persisted.intent == "test_intent"
            assert persisted.requires_confirmation is True
            assert persisted.suggested_actions == [{"action": "test"}]
            db.rollback()

    def test_occurred_at_propagated(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            result = svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation()),
            )
            # Default occurred_at = assistant_message.created_at = FIXED_TIME
            evt = result.delta_apply_result.persisted_events[0].event
            assert evt.created_at == FIXED_TIME
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 4. Caller rollback
# ═══════════════════════════════════════════════════════════════════════════


class TestCallerRollback:
    def test_rollback_undoes_all_writes(self, factory):
        """Caller rollback removes message, event, workspace; seed data survives."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            result = svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation()),
            )
            assert result.assistant_message_inserted is True
            db.rollback()

        with factory() as db:
            assert _count_messages(db, SESSION_ID) == 1  # only seed user
            assert _count_events(db, SESSION_ID) == 0
            assert _count_workspaces(db) == 0
            # Seed session and user message still exist
            assert _get_message(db, USER_ID) is not None


# ═══════════════════════════════════════════════════════════════════════════
# 5. Sequential replay
# ═══════════════════════════════════════════════════════════════════════════


class TestSequentialReplay:
    def test_exact_replay(self, factory):
        """Same inputs → assistant_message_inserted=False, D2 REPLAYED."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        asst = assistant_msg()
        delta = make_delta(make_operation())
        avail = [user_msg()]

        # First turn
        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            r1 = svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=asst, available_messages=avail, delta=delta,
            )
            assert r1.assistant_message_inserted is True
            assert r1.delta_apply_result.status is DiscussionDeltaApplyStatus.APPLIED
            db.commit()

        # Replay
        with factory() as db:
            msg_before = _count_messages(db, SESSION_ID)
            evt_before = _count_events(db, SESSION_ID)
            ws_row = _get_workspace(db)
            ws_version = ws_row.version_no
            ws_cursor = ws_row.last_event_sequence_no
            ws_updated = ws_row.updated_at

            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            r2 = svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=asst, available_messages=avail, delta=delta,
            )
            assert r2.assistant_message_inserted is False
            assert r2.delta_apply_result.status is DiscussionDeltaApplyStatus.REPLAYED
            assert all(not pe.inserted for pe in r2.delta_apply_result.persisted_events)

            assert _count_messages(db, SESSION_ID) == msg_before
            assert _count_events(db, SESSION_ID) == evt_before
            ws_row2 = _get_workspace(db)
            assert ws_row2.version_no == ws_version
            assert ws_row2.last_event_sequence_no == ws_cursor
            assert ws_row2.updated_at == ws_updated
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 6. Message equivalence and conflict
# ═══════════════════════════════════════════════════════════════════════════


class TestMessageEquivalenceAndConflict:
    def test_equivalent_message_is_replay(self, factory):
        """Same ID, same fields → replay, no duplicate create."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        asst = assistant_msg()
        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=asst, available_messages=[user_msg()],
                delta=make_delta(),
            )
            db.commit()

        with factory() as db:
            before = _count_messages(db, SESSION_ID)
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            r = svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=asst, available_messages=[user_msg()],
                delta=make_delta(),
            )
            assert r.assistant_message_inserted is False
            assert _count_messages(db, SESSION_ID) == before
            db.rollback()

    @pytest.mark.parametrize("field,value", [
        ("content", "不同内容"),
        ("source_detail", "不同详情"),
        ("requires_confirmation", True),
        ("suggested_actions", [{"x": 1}]),
        ("created_at", datetime(2027, 1, 1, tzinfo=timezone.utc)),
    ])
    def test_same_id_different_field_rejected(self, factory, field, value):
        """Same ID but different field → conflict, no DB changes."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        asst = assistant_msg()
        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=asst, available_messages=[user_msg()],
                delta=make_delta(),
            )
            db.commit()

        # Create a conflicting version
        conflict_kwargs = {
            "message_id": ASSISTANT_ID, "role": ProjectDirectorMessageRole.ASSISTANT,
            "content": "助手回复", "sequence_no": 2,
            "source": ProjectDirectorMessageSource.AI, "source_detail": "ai",
        }
        conflict_kwargs[field] = value
        conflict_msg = make_message(**conflict_kwargs)

        with factory() as db:
            msg_before = _count_messages(db, SESSION_ID)
            evt_before = _count_events(db, SESSION_ID)
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            with pytest.raises(ValueError, match="discussion_turn_assistant_message_conflict"):
                svc.persist_assistant_turn(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=conflict_msg, available_messages=[user_msg()],
                    delta=make_delta(make_operation()),
                )
            assert _count_messages(db, SESSION_ID) == msg_before
            assert _count_events(db, SESSION_ID) == evt_before
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 7. available_messages normalization
# ═══════════════════════════════════════════════════════════════════════════


class TestAvailableMessagesNormalization:
    def test_assistant_appended_when_missing(self, factory):
        """If assistant not in available_messages, D2 receives it appended."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        captured_delta = {}

        class SpyD2:
            def __init__(self, real):
                self._real = real

            def apply_delta(self, *, available_messages, **kw):
                captured_delta["msg_ids"] = [m.id for m in available_messages]
                return self._real.apply_delta(available_messages=available_messages, **kw)

        with factory() as db:
            real_d2 = ProjectDirectorDiscussionDeltaApplyService(db)
            svc = ProjectDirectorDiscussionTurnPersistenceService(
                session=db, delta_apply_service=SpyD2(real_d2),
            )
            svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(),
            )
            assert USER_ID in captured_delta["msg_ids"]
            assert ASSISTANT_ID in captured_delta["msg_ids"]
            db.rollback()

    def test_assistant_not_duplicated_when_present(self, factory):
        """If assistant already in available_messages, not duplicated."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        captured_delta = {}

        class SpyD2:
            def __init__(self, real):
                self._real = real

            def apply_delta(self, *, available_messages, **kw):
                captured_delta["msg_ids"] = [m.id for m in available_messages]
                return self._real.apply_delta(available_messages=available_messages, **kw)

        asst = assistant_msg()
        with factory() as db:
            real_d2 = ProjectDirectorDiscussionDeltaApplyService(db)
            svc = ProjectDirectorDiscussionTurnPersistenceService(
                session=db, delta_apply_service=SpyD2(real_d2),
            )
            svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=asst,
                available_messages=[user_msg(), asst],
                delta=make_delta(),
            )
            ids = captured_delta["msg_ids"]
            assert ids.count(ASSISTANT_ID) == 1
            db.rollback()

    def test_duplicate_same_content_deduplicated(self, factory):
        """Same ID, same content → keeps first occurrence."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        captured_delta = {}

        class SpyD2:
            def __init__(self, real):
                self._real = real

            def apply_delta(self, *, available_messages, **kw):
                captured_delta["msg_ids"] = [m.id for m in available_messages]
                return self._real.apply_delta(available_messages=available_messages, **kw)

        user_copy = user_msg()  # same ID, same content
        with factory() as db:
            real_d2 = ProjectDirectorDiscussionDeltaApplyService(db)
            svc = ProjectDirectorDiscussionTurnPersistenceService(
                session=db, delta_apply_service=SpyD2(real_d2),
            )
            svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg(), user_copy],
                delta=make_delta(),
            )
            ids = captured_delta["msg_ids"]
            assert ids.count(USER_ID) == 1
            db.rollback()

    def test_duplicate_same_id_different_content_rejected(self, factory):
        """Same ID, different content in available_messages → conflict."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        user2 = make_message(
            message_id=USER_ID, content="不同内容", sequence_no=1,
        )
        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            with pytest.raises(ValueError, match="discussion_turn_available_message_conflict"):
                svc.persist_assistant_turn(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),
                    available_messages=[user_msg(), user2],
                    delta=make_delta(),
                )
            db.rollback()

    def test_available_conflict_rolls_back_new_message(self, factory):
        """available_messages conflict after message create → savepoint rolls back message."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        # First, create the assistant message so it exists in DB
        asst = assistant_msg()
        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=asst, available_messages=[user_msg()],
                delta=make_delta(),
            )
            db.commit()

        # New assistant with different content but same ID in available_messages
        conflict_asst = assistant_msg(content="冲突内容")
        with factory() as db:
            msg_before = _count_messages(db, SESSION_ID)
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            with pytest.raises(ValueError, match="discussion_turn_available_message_conflict"):
                svc.persist_assistant_turn(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),  # equivalent to existing
                    available_messages=[user_msg(), conflict_asst],
                    delta=make_delta(),
                )
            # No new messages created
            assert _count_messages(db, SESSION_ID) == msg_before
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 8. requires_confirmation
# ═══════════════════════════════════════════════════════════════════════════


class TestRequiresConfirmation:
    def test_confirmation_turn(self, factory):
        """assistant_proposal + confirm_decision → message inserted, no events."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        asst = assistant_msg()
        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            result = svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=asst,
                available_messages=[user_msg()],
                delta=make_delta(
                    make_operation(
                        op=DiscussionDeltaOperationType.CONFIRM_DECISION,
                        actor_claim=DiscussionActorClaim.ASSISTANT_PROPOSAL,
                    ),
                ),
            )
            assert result.assistant_message_inserted is True
            assert result.delta_apply_result.status is DiscussionDeltaApplyStatus.REQUIRES_CONFIRMATION
            assert result.delta_apply_result.persisted_events == ()
            assert result.delta_apply_result.inserted_event_count == 0
            assert len(result.delta_apply_result.confirmation_reasons) > 0

            # Message committed, no events/workspace
            assert _count_messages(db, SESSION_ID) == 2
            assert _count_events(db, SESSION_ID) == 0
            assert _count_workspaces(db) == 0
            db.commit()

        # Replay confirmation
        with factory() as db:
            msg_before = _count_messages(db, SESSION_ID)
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            r2 = svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=asst,
                available_messages=[user_msg()],
                delta=make_delta(
                    make_operation(
                        op=DiscussionDeltaOperationType.CONFIRM_DECISION,
                        actor_claim=DiscussionActorClaim.ASSISTANT_PROPOSAL,
                    ),
                ),
            )
            assert r2.assistant_message_inserted is False
            assert r2.delta_apply_result.status is DiscussionDeltaApplyStatus.REQUIRES_CONFIRMATION
            assert _count_messages(db, SESSION_ID) == msg_before
            assert _count_events(db, SESSION_ID) == 0
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 9. NO_CHANGES
# ═══════════════════════════════════════════════════════════════════════════


class TestNoChanges:
    def test_no_changes_first_turn(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            result = svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=DiscussionDelta(operations=[]),
            )
            assert result.assistant_message_inserted is True
            assert result.delta_apply_result.status is DiscussionDeltaApplyStatus.NO_CHANGES
            assert _count_messages(db, SESSION_ID) == 2
            assert _count_events(db, SESSION_ID) == 0
            assert _count_workspaces(db) == 0
            db.commit()

    def test_no_changes_replay(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        asst = assistant_msg()
        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=asst, available_messages=[user_msg()],
                delta=DiscussionDelta(operations=[]),
            )
            db.commit()

        with factory() as db:
            msg_before = _count_messages(db, SESSION_ID)
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            r2 = svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=asst, available_messages=[user_msg()],
                delta=DiscussionDelta(operations=[]),
            )
            assert r2.assistant_message_inserted is False
            assert r2.delta_apply_result.status is DiscussionDeltaApplyStatus.NO_CHANGES
            assert _count_messages(db, SESSION_ID) == msg_before
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 10. D2 failure rolls back new message
# ═══════════════════════════════════════════════════════════════════════════


class TestD2FailureRollback:
    def test_source_message_not_found_rolls_back_message(self, factory):
        """D2 error after message create → savepoint rolls back message."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        with factory() as db:
            msg_before = _count_messages(db, SESSION_ID)
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            with pytest.raises(ValueError, match="discussion_delta_source_message_not_found"):
                svc.persist_assistant_turn(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),
                    available_messages=[user_msg()],
                    delta=make_delta(make_operation(source_message_ids=[uuid4()])),
                )
            # New message rolled back
            assert _count_messages(db, SESSION_ID) == msg_before
            assert _count_events(db, SESSION_ID) == 0
            db.rollback()

    def test_d2_partial_replay_rolls_back_message(self, factory):
        """D2 partial_replay error → message rolled back."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        class FailD2:
            def apply_delta(self, **kw):
                raise ValueError("discussion_delta_apply_partial_replay")

        with factory() as db:
            msg_before = _count_messages(db, SESSION_ID)
            svc = ProjectDirectorDiscussionTurnPersistenceService(
                session=db, delta_apply_service=FailD2(),
            )
            with pytest.raises(ValueError, match="discussion_delta_apply_partial_replay"):
                svc.persist_assistant_turn(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),
                    available_messages=[user_msg()],
                    delta=make_delta(make_operation()),
                )
            assert _count_messages(db, SESSION_ID) == msg_before
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 11. Replay state mismatch
# ═══════════════════════════════════════════════════════════════════════════


class TestReplayStateMismatch:
    def test_new_message_with_d2_replayed_raises(self, factory):
        """New message but injected D2 returns REPLAYED → mismatch, message rolled back."""
        from app.services.project_director_discussion_workspace_reducer_service import (
            ProjectDirectorDiscussionWorkspaceReducerService,
        )
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        ws = reducer.rebuild_workspace(
            session_id=SESSION_ID, project_id=None, events=[], version_no=0,
            created_at=FIXED_TIME, updated_at=FIXED_TIME,
        )

        class ReplayD2:
            def apply_delta(self, **kw):
                return GovernedDiscussionDeltaApplyResult(
                    status=DiscussionDeltaApplyStatus.REPLAYED,
                    persisted_events=(), workspace=ws,
                    inserted_event_count=0, workspace_changed=False,
                    confirmation_reasons=(),
                )

        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        with factory() as db:
            msg_before = _count_messages(db, SESSION_ID)
            svc = ProjectDirectorDiscussionTurnPersistenceService(
                session=db, delta_apply_service=ReplayD2(),
            )
            with pytest.raises(ValueError, match="discussion_turn_replay_state_mismatch"):
                svc.persist_assistant_turn(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),
                    available_messages=[user_msg()],
                    delta=make_delta(make_operation()),
                )
            assert _count_messages(db, SESSION_ID) == msg_before
            db.rollback()

    def test_existing_message_with_d2_applied_raises(self, factory):
        """Existing message but D2 returns APPLIED → mismatch."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        class FakeAppliedD2:
            """Returns APPLIED regardless of inputs."""
            def apply_delta(self, **kw):
                from app.services.project_director_discussion_workspace_reducer_service import (
                    ProjectDirectorDiscussionWorkspaceReducerService,
                )
                reducer = ProjectDirectorDiscussionWorkspaceReducerService()
                ws = reducer.rebuild_workspace(
                    session_id=SESSION_ID, project_id=None, events=[], version_no=1,
                    created_at=FIXED_TIME, updated_at=FIXED_TIME,
                )
                return GovernedDiscussionDeltaApplyResult(
                    status=DiscussionDeltaApplyStatus.APPLIED,
                    persisted_events=(),
                    workspace=ws,
                    inserted_event_count=0,
                    workspace_changed=True,
                    confirmation_reasons=(),
                )

        asst = assistant_msg()
        # First: create the message
        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(
                session=db, delta_apply_service=FakeAppliedD2(),
            )
            # This will succeed because message is new + APPLIED is valid
            svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=asst, available_messages=[user_msg()],
                delta=make_delta(),
            )
            db.commit()

        # Second: message exists, D2 returns APPLIED → mismatch
        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(
                session=db, delta_apply_service=FakeAppliedD2(),
            )
            with pytest.raises(ValueError, match="discussion_turn_replay_state_mismatch"):
                svc.persist_assistant_turn(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=asst, available_messages=[user_msg()],
                    delta=make_delta(make_operation()),
                )
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 12. State combination matrix (injected)
# ═══════════════════════════════════════════════════════════════════════════


class TestStateCombinationMatrix:
    """Verify valid/invalid combinations of message_inserted × D2 status."""

    def _make_d2_spy(self, status: DiscussionDeltaApplyStatus, *, has_ops: bool = True):
        from app.services.project_director_discussion_workspace_reducer_service import (
            ProjectDirectorDiscussionWorkspaceReducerService,
        )
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        ws = reducer.rebuild_workspace(
            session_id=SESSION_ID, project_id=None, events=[], version_no=0,
            created_at=FIXED_TIME, updated_at=FIXED_TIME,
        )

        class StaticD2:
            def apply_delta(self, **kw):
                return GovernedDiscussionDeltaApplyResult(
                    status=status,
                    persisted_events=(),
                    workspace=ws,
                    inserted_event_count=0,
                    workspace_changed=(status is DiscussionDeltaApplyStatus.APPLIED),
                    confirmation_reasons=(
                        ("reason",) if status is DiscussionDeltaApplyStatus.REQUIRES_CONFIRMATION else ()
                    ),
                )

        return StaticD2()

    def test_new_message_applied_succeeds(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(
                session=db,
                delta_apply_service=self._make_d2_spy(DiscussionDeltaApplyStatus.APPLIED),
            )
            r = svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(), available_messages=[user_msg()],
                delta=make_delta(),
            )
            assert r.assistant_message_inserted is True
            db.rollback()

    def test_new_message_requires_confirmation_succeeds(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(
                session=db,
                delta_apply_service=self._make_d2_spy(DiscussionDeltaApplyStatus.REQUIRES_CONFIRMATION),
            )
            r = svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(), available_messages=[user_msg()],
                delta=make_delta(),
            )
            assert r.assistant_message_inserted is True
            db.rollback()

    def test_new_message_no_changes_succeeds(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(
                session=db,
                delta_apply_service=self._make_d2_spy(DiscussionDeltaApplyStatus.NO_CHANGES),
            )
            r = svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(), available_messages=[user_msg()],
                delta=DiscussionDelta(operations=[]),
            )
            assert r.assistant_message_inserted is True
            db.rollback()

    def test_new_message_replayed_raises(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(
                session=db,
                delta_apply_service=self._make_d2_spy(DiscussionDeltaApplyStatus.REPLAYED),
            )
            with pytest.raises(ValueError, match="discussion_turn_replay_state_mismatch"):
                svc.persist_assistant_turn(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(), available_messages=[user_msg()],
                    delta=make_delta(),
                )
            db.rollback()

    def test_existing_message_replayed_succeeds(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        asst = assistant_msg()
        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(
                session=db,
                delta_apply_service=self._make_d2_spy(DiscussionDeltaApplyStatus.APPLIED),
            )
            svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=asst, available_messages=[user_msg()],
                delta=make_delta(),
            )
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(
                session=db,
                delta_apply_service=self._make_d2_spy(DiscussionDeltaApplyStatus.REPLAYED),
            )
            r = svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=asst, available_messages=[user_msg()],
                delta=make_delta(),
            )
            assert r.assistant_message_inserted is False
            db.rollback()

    def test_existing_message_requires_confirmation_succeeds(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        asst = assistant_msg()
        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(
                session=db,
                delta_apply_service=self._make_d2_spy(DiscussionDeltaApplyStatus.APPLIED),
            )
            svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=asst, available_messages=[user_msg()],
                delta=make_delta(),
            )
            db.commit()
        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(
                session=db,
                delta_apply_service=self._make_d2_spy(DiscussionDeltaApplyStatus.REQUIRES_CONFIRMATION),
            )
            r = svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=asst, available_messages=[user_msg()],
                delta=make_delta(),
            )
            assert r.assistant_message_inserted is False
            db.rollback()

    def test_existing_message_applied_raises(self, factory):
        """Existing message + D2 APPLIED → replay_state_mismatch."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()
        asst = assistant_msg()
        # First: create message with APPLIED (valid: new + APPLIED)
        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(
                session=db,
                delta_apply_service=self._make_d2_spy(DiscussionDeltaApplyStatus.APPLIED),
            )
            svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=asst, available_messages=[user_msg()],
                delta=make_delta(),
            )
            db.commit()
        # Second: existing message + APPLIED = mismatch
        with factory() as db:
            svc = ProjectDirectorDiscussionTurnPersistenceService(
                session=db,
                delta_apply_service=self._make_d2_spy(DiscussionDeltaApplyStatus.APPLIED),
            )
            with pytest.raises(ValueError, match="discussion_turn_replay_state_mismatch"):
                svc.persist_assistant_turn(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=asst, available_messages=[user_msg()],
                    delta=make_delta(make_operation()),
                )
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 13. Real IntegrityError
# ═══════════════════════════════════════════════════════════════════════════


class TestRealIntegrityError:
    def test_concurrent_message_conflict(self, factory):
        """Proxy causes real IntegrityError → concurrent_conflict, savepoint rolls back."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        class RaceMessageRepo:
            """get_by_id returns None; create inserts conflict first, then real create."""
            def __init__(self, real, session):
                self._real = real
                self._session = session

            def get_by_id(self, message_id):
                return None  # Simulate: message doesn't exist yet

            def get_next_sequence_no(self, **kw):
                return self._real.get_next_sequence_no(**kw)

            def create(self, message):
                # Insert a conflicting row with same ID first
                conflict = ProjectDirectorMessageTable(
                    id=message.id, session_id=message.session_id,
                    role=message.role, content="抢先插入",
                    sequence_no=message.sequence_no,
                    source=ProjectDirectorMessageSource.SYSTEM,
                    source_detail="race",
                )
                self._session.add(conflict)
                self._session.flush()
                # Now try to create the real message → IntegrityError
                return self._real.create(message)

        with factory() as db:
            real_repo = ProjectDirectorMessageRepository(db)
            proxy = RaceMessageRepo(real_repo, db)
            svc = ProjectDirectorDiscussionTurnPersistenceService(
                session=db, message_repository=proxy,
            )
            with pytest.raises(ValueError, match="discussion_turn_assistant_message_concurrent_conflict"):
                svc.persist_assistant_turn(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),
                    available_messages=[user_msg()],
                    delta=make_delta(),
                )
            # Savepoint rolled back both conflict and target
            assert _count_messages(db, SESSION_ID) == 1  # only seed user
            # Session still usable
            db.execute(select(ProjectDirectorMessageTable).limit(1))
            db.rollback()

    def test_session_usable_after_conflict(self, factory):
        """After IntegrityError, caller session can still SELECT and rollback."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        class RaceMessageRepo:
            def __init__(self, real, session):
                self._real = real
                self._session = session

            def get_by_id(self, message_id):
                return None

            def get_next_sequence_no(self, **kw):
                return self._real.get_next_sequence_no(**kw)

            def create(self, message):
                conflict = ProjectDirectorMessageTable(
                    id=message.id, session_id=message.session_id,
                    role=message.role, content="抢先",
                    sequence_no=message.sequence_no,
                    source=ProjectDirectorMessageSource.SYSTEM,
                    source_detail="race",
                )
                self._session.add(conflict)
                self._session.flush()
                return self._real.create(message)

        with factory() as db:
            real_repo = ProjectDirectorMessageRepository(db)
            proxy = RaceMessageRepo(real_repo, db)
            svc = ProjectDirectorDiscussionTurnPersistenceService(
                session=db, message_repository=proxy,
            )
            with pytest.raises(ValueError, match="discussion_turn_assistant_message_concurrent_conflict"):
                svc.persist_assistant_turn(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),
                    available_messages=[user_msg()],
                    delta=make_delta(),
                )
            # Session still functional
            result = db.execute(
                select(ProjectDirectorMessageTable)
                .where(ProjectDirectorMessageTable.session_id == SESSION_ID)
            ).scalars().all()
            assert len(result) >= 1
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 14. Input immutability
# ═══════════════════════════════════════════════════════════════════════════


class TestInputImmutability:
    @pytest.mark.parametrize("status", [
        DiscussionDeltaApplyStatus.APPLIED,
        DiscussionDeltaApplyStatus.REPLAYED,
        DiscussionDeltaApplyStatus.REQUIRES_CONFIRMATION,
        DiscussionDeltaApplyStatus.NO_CHANGES,
    ])
    def test_inputs_unchanged(self, factory, status):
        from app.services.project_director_discussion_workspace_reducer_service import (
            ProjectDirectorDiscussionWorkspaceReducerService,
        )
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        ws = reducer.rebuild_workspace(
            session_id=SESSION_ID, project_id=None, events=[], version_no=0,
            created_at=FIXED_TIME, updated_at=FIXED_TIME,
        )

        class StaticD2:
            def apply_delta(self, **kw):
                return GovernedDiscussionDeltaApplyResult(
                    status=status, persisted_events=(), workspace=ws,
                    inserted_event_count=0,
                    workspace_changed=(status is DiscussionDeltaApplyStatus.APPLIED),
                    confirmation_reasons=(
                        ("reason",) if status is DiscussionDeltaApplyStatus.REQUIRES_CONFIRMATION else ()
                    ),
                )

        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        # For REPLAYED, need to pre-create the message with matching fields
        if status is DiscussionDeltaApplyStatus.REPLAYED:
            with factory() as db:
                repo = ProjectDirectorMessageRepository(db)
                repo.create(assistant_msg())
                db.commit()

        with factory() as db:
            asst = assistant_msg()
            delta = make_delta(make_operation())
            msgs = [user_msg()]
            before = (
                asst.model_dump(mode="python"),
                delta.model_dump(mode="python"),
                [m.model_dump(mode="python") for m in msgs],
                list(msgs),
            )
            svc = ProjectDirectorDiscussionTurnPersistenceService(
                session=db, delta_apply_service=StaticD2(),
            )
            svc.persist_assistant_turn(
                session_id=SESSION_ID, project_id=None,
                assistant_message=asst, available_messages=msgs, delta=delta,
            )
            after = (
                asst.model_dump(mode="python"),
                delta.model_dump(mode="python"),
                [m.model_dump(mode="python") for m in msgs],
                list(msgs),
            )
            assert after == before
            db.rollback()

    def test_inputs_unchanged_on_error(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            db.commit()

        with factory() as db:
            asst = assistant_msg()
            delta = make_delta(make_operation(source_message_ids=[uuid4()]))
            msgs = [user_msg()]
            before = (
                asst.model_dump(mode="python"),
                delta.model_dump(mode="python"),
                [m.model_dump(mode="python") for m in msgs],
            )
            svc = ProjectDirectorDiscussionTurnPersistenceService(session=db)
            with pytest.raises(ValueError):
                svc.persist_assistant_turn(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=asst, available_messages=msgs, delta=delta,
                )
            after = (
                asst.model_dump(mode="python"),
                delta.model_dump(mode="python"),
                [m.model_dump(mode="python") for m in msgs],
            )
            assert after == before
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 15. AST boundary
# ═══════════════════════════════════════════════════════════════════════════


class TestASTBoundary:
    @pytest.fixture(scope="class")
    def turn_ast(self):
        path = Path(__file__).parents[1] / "app/services/project_director_discussion_turn_persistence_service.py"
        return ast.parse(path.read_text())

    def _get_imports(self, node: ast.Module) -> set[str]:
        imports: set[str] = set()
        for n in ast.walk(node):
            if isinstance(n, ast.Import):
                for alias in n.names:
                    imports.add(alias.name)
            elif isinstance(n, ast.ImportFrom):
                if n.module:
                    imports.add(n.module)
        return imports

    def _get_call_attrs(self, node: ast.Module) -> set[str]:
        attrs: set[str] = set()
        for n in ast.walk(node):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                attrs.add(n.func.attr)
        return attrs

    def test_no_commit_rollback(self, turn_ast):
        attrs = self._get_call_attrs(turn_ast)
        assert "commit" not in attrs
        assert "rollback" not in attrs

    def test_has_begin_nested(self, turn_ast):
        attrs = self._get_call_attrs(turn_ast)
        assert "begin_nested" in attrs

    def test_has_message_repository(self, turn_ast):
        imports = self._get_imports(turn_ast)
        assert any("message_repository" in imp for imp in imports)

    def test_has_delta_apply_service(self, turn_ast):
        imports = self._get_imports(turn_ast)
        assert any("delta_apply_service" in imp for imp in imports)

    def test_no_fastapi_provider(self, turn_ast):
        imports = self._get_imports(turn_ast)
        for imp in imports:
            assert "fastapi" not in imp.lower()
            assert "provider" not in imp.lower()

    def test_no_plan_task_run(self, turn_ast):
        imports = self._get_imports(turn_ast)
        for imp in imports:
            for forbidden in ("PlanVersion", "Task", "Run", "Worker", "Executor", "Formalization"):
                assert forbidden not in imp

    def test_no_create_engine(self, turn_ast):
        imports = self._get_imports(turn_ast)
        for imp in imports:
            assert "create_engine" not in imp
            assert "sessionmaker" not in imp
