"""Contract tests for P26-D2 transactional governed DiscussionDelta apply.

These tests exercise the transactional apply boundary using real SQLite,
real repositories, real Gate, and real Reducer.  No production code is modified.
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
from app.services.project_director_discussion_delta_apply_service import (
    AppliedDiscussionEvent,
    DiscussionDeltaApplyStatus,
    GovernedDiscussionDeltaApplyResult,
    ProjectDirectorDiscussionDeltaApplyService,
)
from app.services.project_director_discussion_delta_gate_service import (
    DiscussionDeltaGateStatus,
    DiscussionDeltaOperationIdentity,
    GovernedDiscussionDeltaResult,
    PreparedDiscussionEvent,
    ProjectDirectorDiscussionDeltaGateService,
)
from app.services.project_director_discussion_workspace_reducer_service import (
    ProjectDirectorDiscussionWorkspaceReducerService,
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
    db_path = tmp_path / "p26d2-test.db"
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
def db_session(db_session_factory):
    session = db_session_factory()
    try:
        yield session
    finally:
        session.close()


def _seed_session(db: Session, *, session_id: UUID = SESSION_ID, project_id: UUID | None = None) -> UUID:
    row = ProjectDirectorSessionTable(id=session_id, project_id=project_id, goal_text="D2 测试")
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
) -> ProjectDirectorMessage:
    return ProjectDirectorMessage(
        id=message_id or uuid4(), session_id=session_id, role=role, content=content,
        sequence_no=sequence_no, source=ProjectDirectorMessageSource.SYSTEM,
        created_at=created_at,
    )


def assistant_msg(**kwargs) -> ProjectDirectorMessage:
    return make_message(message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT, **kwargs)


def user_msg(**kwargs) -> ProjectDirectorMessage:
    return make_message(message_id=USER_ID, **kwargs)


def system_msg(**kwargs) -> ProjectDirectorMessage:
    return make_message(message_id=SYSTEM_ID, role=ProjectDirectorMessageRole.SYSTEM, **kwargs)


def make_operation(
    *,
    op: DiscussionDeltaOperationType = DiscussionDeltaOperationType.ADD_CONCERN,
    actor_claim: DiscussionActorClaim = DiscussionActorClaim.USER_EXPLICIT,
    content: str = "内容",
    target_id: UUID | None = None,
    subject_key: str | None = None,
    payload: dict | None = None,
    source_message_ids: list[UUID] | None = None,
    supersedes_event_id: UUID | None = None,
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
        op=op, actor_claim=actor_claim, content=content, target_id=target_id,
        subject_key=subject_key, payload={} if payload is None else payload,
        source_message_ids=source_message_ids, supersedes_event_id=supersedes_event_id,
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


def _get_workspace(db: Session, session_id: UUID = SESSION_ID) -> ProjectDirectorDiscussionWorkspaceTable | None:
    return db.get(ProjectDirectorDiscussionWorkspaceTable, session_id)


def _new_assistant_round(factory, *, content: str = "第二轮") -> tuple[ProjectDirectorMessage, list[ProjectDirectorMessage]]:
    """Seed a new assistant message in DB and return (assistant_msg, available_messages)."""
    new_id = uuid4()
    with factory() as db:
        _seed_message(db, SESSION_ID, message_id=new_id, role=ProjectDirectorMessageRole.ASSISTANT, content=content, sequence_no=3)
        db.commit()
    asst = make_message(message_id=new_id, role=ProjectDirectorMessageRole.ASSISTANT, content=content, sequence_no=2)
    return asst, [user_msg(), asst]


# ═══════════════════════════════════════════════════════════════════════════
# 1. Public contracts
# ═══════════════════════════════════════════════════════════════════════════


class TestPublicContracts:
    def test_apply_status_members(self):
        assert {m.value for m in DiscussionDeltaApplyStatus} == {
            "applied", "replayed", "requires_confirmation", "no_changes",
        }

    def test_applied_event_frozen_slots(self):
        assert is_dataclass(AppliedDiscussionEvent)
        assert set(AppliedDiscussionEvent.__slots__) == {
            "operation_index", "event", "idempotency_key", "inserted",
        }
        assert {f.name for f in fields(AppliedDiscussionEvent)} == {
            "operation_index", "event", "idempotency_key", "inserted",
        }

    def test_apply_result_frozen_slots(self):
        assert is_dataclass(GovernedDiscussionDeltaApplyResult)
        assert set(GovernedDiscussionDeltaApplyResult.__slots__) == {
            "status", "persisted_events", "workspace",
            "inserted_event_count", "workspace_changed", "confirmation_reasons",
        }
        assert {f.name for f in fields(GovernedDiscussionDeltaApplyResult)} == {
            "status", "persisted_events", "workspace",
            "inserted_event_count", "workspace_changed", "confirmation_reasons",
        }

    def test_identity_frozen_slots(self):
        assert is_dataclass(DiscussionDeltaOperationIdentity)
        assert set(DiscussionDeltaOperationIdentity.__slots__) == {
            "operation_index", "event_id", "idempotency_key",
        }
        assert {f.name for f in fields(DiscussionDeltaOperationIdentity)} == {
            "operation_index", "event_id", "idempotency_key",
        }

    def test_tuple_fields_and_frozen(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            result = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation()),
            )
            assert isinstance(result.persisted_events, tuple)
            assert isinstance(result.confirmation_reasons, tuple)
            with pytest.raises(FrozenInstanceError):
                result.persisted_events = ()
            with pytest.raises(FrozenInstanceError):
                result.confirmation_reasons = ()
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# Helper to get factory from session
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def factory(db_session_factory):
    return db_session_factory


# ═══════════════════════════════════════════════════════════════════════════
# 2. First apply — no workspace, single event
# ═══════════════════════════════════════════════════════════════════════════


class TestFirstApply:
    def test_single_add_concern_applied(self, factory):
        """First apply with no workspace: event inserted, workspace created."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            result = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation()),
            )
            assert result.status is DiscussionDeltaApplyStatus.APPLIED
            assert len(result.persisted_events) == 1
            assert result.inserted_event_count == 1
            assert result.workspace_changed is True

            pe = result.persisted_events[0]
            assert pe.inserted is True
            assert pe.operation_index == 0
            assert pe.event.sequence_no == 1

            # Workspace
            ws = result.workspace
            assert ws.version_no == 1
            assert ws.last_event_sequence_no == 1

            # Service did NOT commit
            db.rollback()

        # After rollback, nothing persisted
        with factory() as db:
            assert _count_events(db) == 0
            assert _count_workspaces(db) == 0

    def test_first_apply_flushed_but_not_committed(self, factory):
        """After apply, data is visible in same session but gone after rollback."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            result = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation()),
            )
            assert result.status is DiscussionDeltaApplyStatus.APPLIED
            # Visible in same session
            assert _count_events(db, SESSION_ID) == 1
            ws_row = _get_workspace(db)
            assert ws_row is not None
            assert ws_row.version_no == 1
            db.rollback()

        # After rollback, gone
        with factory() as db:
            assert _count_events(db) == 0
            assert _count_workspaces(db) == 0

    def test_first_apply_committed_persists(self, factory):
        """After caller commit, data persists in new session."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            result = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation()),
            )
            assert result.status is DiscussionDeltaApplyStatus.APPLIED
            db.commit()

        with factory() as db:
            assert _count_events(db, SESSION_ID) == 1
            ws_row = _get_workspace(db)
            assert ws_row is not None
            assert ws_row.version_no == 1
            assert ws_row.last_event_sequence_no == 1

    def test_p27_fields_none(self, factory):
        """Persisted event has all P27 provenance fields as None."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            result = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation(payload={"source_surface": "not-promoted"})),
            )
            evt = result.persisted_events[0].event
            for name in ("source_surface", "source_entity_type", "source_entity_id",
                          "trigger_type", "interaction_case_id", "external_context_pack_id"):
                assert getattr(evt, name) is None, f"P27 field {name} should be None"
            db.rollback()

    def test_no_message_created(self, factory):
        """Apply does not create any message rows."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        with factory() as db:
            before = _count_messages(db, SESSION_ID)
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation()),
            )
            after = _count_messages(db, SESSION_ID)
            assert after == before
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 3. Existing workspace CAS
# ═══════════════════════════════════════════════════════════════════════════


class TestExistingWorkspaceCAS:
    def test_second_apply_increments_version(self, factory):
        """Second apply with existing workspace uses CAS update."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        # First apply
        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            r1 = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation(content="第一个")),
            )
            assert r1.status is DiscussionDeltaApplyStatus.APPLIED
            assert r1.workspace.version_no == 1
            assert r1.workspace.last_event_sequence_no == 1
            db.commit()

        # Second apply with new assistant message and delta
        assistant2, avail2 = _new_assistant_round(factory)

        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            r2 = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant2,
                available_messages=avail2,
                delta=make_delta(make_operation(content="第二个")),
            )
            assert r2.status is DiscussionDeltaApplyStatus.APPLIED
            assert r2.inserted_event_count == 1
            assert r2.persisted_events[0].event.sequence_no == 2
            assert r2.workspace.version_no == 2
            assert r2.workspace.last_event_sequence_no == 2
            db.commit()

        with factory() as db:
            assert _count_events(db, SESSION_ID) == 2
            ws = _get_workspace(db)
            assert ws is not None
            assert ws.version_no == 2


# ═══════════════════════════════════════════════════════════════════════════
# 4. Multi-operation atomic apply
# ═══════════════════════════════════════════════════════════════════════════


class TestMultiOperationAtomicApply:
    def test_three_operations_atomic(self, factory):
        """Three operations applied atomically: consecutive sequences, one version bump."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            result = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(
                    make_operation(op=DiscussionDeltaOperationType.ADD_CONCERN, content="a"),
                    make_operation(op=DiscussionDeltaOperationType.ADD_CONCERN, content="b"),
                    make_operation(op=DiscussionDeltaOperationType.ADD_CONCERN, content="c"),
                ),
            )
            assert result.status is DiscussionDeltaApplyStatus.APPLIED
            assert len(result.persisted_events) == 3
            assert result.inserted_event_count == 3

            seqs = [pe.event.sequence_no for pe in result.persisted_events]
            assert seqs == [1, 2, 3]
            assert all(pe.inserted for pe in result.persisted_events)

            # Only one version bump
            assert result.workspace.version_no == 1
            assert result.workspace.last_event_sequence_no == 3
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 5. requires_confirmation — zero writes
# ═══════════════════════════════════════════════════════════════════════════


class TestRequiresConfirmationZeroWrites:
    def test_confirmation_no_writes(self, factory):
        """requires_confirmation returns zero writes, no event/workspace changes."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        with factory() as db:
            events_before = _count_events(db, SESSION_ID)
            ws_before = _count_workspaces(db)
            msg_before = _count_messages(db, SESSION_ID)

            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            result = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(
                    make_operation(
                        op=DiscussionDeltaOperationType.CONFIRM_DECISION,
                        actor_claim=DiscussionActorClaim.ASSISTANT_PROPOSAL,
                    ),
                ),
            )
            assert result.status is DiscussionDeltaApplyStatus.REQUIRES_CONFIRMATION
            assert result.persisted_events == ()
            assert result.inserted_event_count == 0
            assert result.workspace_changed is False
            assert len(result.confirmation_reasons) > 0

            assert _count_events(db, SESSION_ID) == events_before
            assert _count_workspaces(db) == ws_before
            assert _count_messages(db, SESSION_ID) == msg_before
            db.rollback()

    def test_confirmation_with_existing_workspace_unchanged(self, factory):
        """With existing workspace, confirmation does not change version/cursor."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        # First apply to create workspace
        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation(content="初始")),
            )
            db.commit()

        assistant2, avail2 = _new_assistant_round(factory)

        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            result = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant2,
                available_messages=avail2,
                delta=make_delta(
                    make_operation(
                        op=DiscussionDeltaOperationType.CONFIRM_DECISION,
                        actor_claim=DiscussionActorClaim.ASSISTANT_PROPOSAL,
                        source_message_ids=[assistant2.id],
                    ),
                ),
            )
            assert result.status is DiscussionDeltaApplyStatus.REQUIRES_CONFIRMATION
            assert result.workspace.version_no == 1
            assert result.workspace.last_event_sequence_no == 1
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 6. Empty delta — zero writes
# ═══════════════════════════════════════════════════════════════════════════


class TestEmptyDeltaZeroWrites:
    def test_empty_delta_no_workspace(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        with factory() as db:
            events_before = _count_events(db, SESSION_ID)
            ws_before = _count_workspaces(db)

            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            result = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=DiscussionDelta(operations=[]),
            )
            assert result.status is DiscussionDeltaApplyStatus.NO_CHANGES
            assert result.persisted_events == ()
            assert result.inserted_event_count == 0
            assert result.workspace_changed is False
            assert result.confirmation_reasons == ()

            assert _count_events(db, SESSION_ID) == events_before
            assert _count_workspaces(db) == ws_before
            db.rollback()

    def test_empty_delta_with_existing_workspace(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        # Create workspace first
        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation(content="初始")),
            )
            db.commit()

        assistant2, avail2 = _new_assistant_round(factory)

        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            result = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant2,
                available_messages=avail2,
                delta=DiscussionDelta(operations=[]),
            )
            assert result.status is DiscussionDeltaApplyStatus.NO_CHANGES
            assert result.workspace.version_no == 1
            assert result.workspace.last_event_sequence_no == 1
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 7. Caller transaction boundaries
# ═══════════════════════════════════════════════════════════════════════════


class TestCallerTransactionBoundary:
    def test_caller_rollback_undoes_apply(self, factory):
        """Caller rollback after APPLIED removes all writes."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            result = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation()),
            )
            assert result.status is DiscussionDeltaApplyStatus.APPLIED
            db.rollback()

        with factory() as db:
            assert _count_events(db, SESSION_ID) == 0
            assert _count_workspaces(db) == 0
            # Seed messages still exist
            assert _count_messages(db, SESSION_ID) == 2

    def test_caller_commit_persists(self, factory):
        """Caller commit makes apply durable."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation()),
            )
            db.commit()

        with factory() as db:
            assert _count_events(db, SESSION_ID) == 1
            assert _count_workspaces(db) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 8. Sequential replay
# ═══════════════════════════════════════════════════════════════════════════


class TestSequentialReplay:
    def test_exact_replay(self, factory):
        """Same assistant_message + same delta → REPLAYED, no additional writes."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        # First apply
        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            r1 = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation()),
            )
            assert r1.status is DiscussionDeltaApplyStatus.APPLIED
            first_event = r1.persisted_events[0].event
            first_key = r1.persisted_events[0].idempotency_key
            first_ws_version = r1.workspace.version_no
            first_ws_cursor = r1.workspace.last_event_sequence_no
            db.commit()

        # Replay
        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            r2 = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation()),
            )
            assert r2.status is DiscussionDeltaApplyStatus.REPLAYED
            assert r2.inserted_event_count == 0
            assert r2.workspace_changed is False
            assert all(not pe.inserted for pe in r2.persisted_events)

            # Event fields identical
            replay_event = r2.persisted_events[0].event
            assert replay_event.id == first_event.id
            assert replay_event.sequence_no == first_event.sequence_no
            assert r2.persisted_events[0].idempotency_key == first_key
            assert replay_event.created_at == first_event.created_at

            # Workspace unchanged
            assert r2.workspace.version_no == first_ws_version
            assert r2.workspace.last_event_sequence_no == first_ws_cursor
            db.rollback()

        # DB unchanged after replay
        with factory() as db:
            assert _count_events(db, SESSION_ID) == 1
            ws = _get_workspace(db)
            assert ws is not None
            assert ws.version_no == 1

    def test_old_delta_replay_in_subsequent_history(self, factory):
        """Replay Delta A after Delta B: returns REPLAYED, workspace stays at B's state."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        delta_a = make_delta(make_operation(content="Delta A"))

        # Apply Delta A
        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            r_a = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=delta_a,
            )
            assert r_a.status is DiscussionDeltaApplyStatus.APPLIED
            db.commit()

        # Apply Delta B with new assistant
        assistant_b, avail_b = _new_assistant_round(factory, content="B")
        delta_b = make_delta(make_operation(content="Delta B"))

        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            r_b = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_b,
                available_messages=avail_b,
                delta=delta_b,
            )
            assert r_b.status is DiscussionDeltaApplyStatus.APPLIED
            assert r_b.workspace.version_no == 2
            assert r_b.workspace.last_event_sequence_no == 2
            db.commit()

        # Replay Delta A
        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            r_replay = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=delta_a,
            )
            assert r_replay.status is DiscussionDeltaApplyStatus.REPLAYED
            assert r_replay.inserted_event_count == 0
            # Workspace stays at Delta B's state
            assert r_replay.workspace.version_no == 2
            assert r_replay.workspace.last_event_sequence_no == 2
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 9. Replay error boundaries
# ═══════════════════════════════════════════════════════════════════════════


class TestReplayErrorBoundaries:
    def test_partial_replay_rejected(self, factory):
        """Only some identities found → partial replay error."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        # Get identities for a 2-op delta
        delta = make_delta(
            make_operation(content="a"),
            make_operation(content="b"),
        )
        gate = ProjectDirectorDiscussionDeltaGateService()
        identities = gate.prepare_replay_identities(
            session_id=SESSION_ID, assistant_message=assistant_msg(), delta=delta,
        )
        assert len(identities) == 2

        # Manually persist only the first event
        with factory() as db:
            event_repo = ProjectDirectorDiscussionEventRepository(db)
            first_event = DiscussionEvent(
                id=identities[0].event_id,
                session_id=SESSION_ID, project_id=None,
                sequence_no=1, event_type=DiscussionEventType.CONCERN_ADDED,
                subject_key="concern", content="a",
                status=DiscussionEventStatus.ACTIVE,
                payload={}, source_message_ids=[USER_ID],
                created_by=DiscussionActorClaim.USER_EXPLICIT,
                confidence=1.0, created_at=FIXED_TIME,
            )
            event_repo.append_if_absent(event=first_event, idempotency_key=identities[0].idempotency_key)
            db.commit()

        # Now apply — partial replay
        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            with pytest.raises(ValueError, match="^discussion_delta_apply_partial_replay$"):
                svc.apply_delta(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),
                    available_messages=[user_msg()],
                    delta=delta,
                )
            db.rollback()

        # Second event was NOT written
        with factory() as db:
            assert _count_events(db, SESSION_ID) == 1

    def test_identity_conflict_rejected(self, factory):
        """Idempotency key exists but with different event ID → conflict."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        delta = make_delta(make_operation())
        gate = ProjectDirectorDiscussionDeltaGateService()
        identities = gate.prepare_replay_identities(
            session_id=SESSION_ID, assistant_message=assistant_msg(), delta=delta,
        )

        # Write event with same key but different ID
        with factory() as db:
            event_repo = ProjectDirectorDiscussionEventRepository(db)
            fake_event = DiscussionEvent(
                id=uuid4(),  # Different ID
                session_id=SESSION_ID, project_id=None,
                sequence_no=1, event_type=DiscussionEventType.CONCERN_ADDED,
                subject_key="concern", content="内容",
                status=DiscussionEventStatus.ACTIVE,
                payload={}, source_message_ids=[USER_ID],
                created_by=DiscussionActorClaim.USER_EXPLICIT,
                confidence=1.0, created_at=FIXED_TIME,
            )
            event_repo.append_if_absent(event=fake_event, idempotency_key=identities[0].idempotency_key)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            with pytest.raises(ValueError, match="^discussion_delta_apply_replay_identity_conflict$"):
                svc.apply_delta(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),
                    available_messages=[user_msg()],
                    delta=delta,
                )
            db.rollback()

    def test_replay_workspace_missing(self, factory):
        """Replay with no workspace row → workspace_missing."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        # Apply and commit
        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation()),
            )
            db.commit()

        # Delete workspace row only
        with factory() as db:
            ws_row = _get_workspace(db)
            assert ws_row is not None
            db.delete(ws_row)
            db.commit()

        # Replay should fail
        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            with pytest.raises(ValueError, match="^discussion_delta_apply_replay_workspace_missing$"):
                svc.apply_delta(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),
                    available_messages=[user_msg()],
                    delta=make_delta(make_operation()),
                )
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 10. Gate identity helper consistency
# ═══════════════════════════════════════════════════════════════════════════


class TestGateIdentityConsistency:
    def test_identity_matches_prepared_events(self):
        """prepare_replay_identities() matches evaluate_delta().prepared_events."""
        gate = ProjectDirectorDiscussionDeltaGateService()
        delta = make_delta(
            make_operation(op=DiscussionDeltaOperationType.SET_TOPIC, content="主题"),
            make_operation(op=DiscussionDeltaOperationType.ADD_OPTION, target_id=uuid4()),
        )
        identities = gate.prepare_replay_identities(
            session_id=SESSION_ID, assistant_message=assistant_msg(), delta=delta,
        )
        result = gate.evaluate_delta(
            session_id=SESSION_ID, project_id=None,
            assistant_message=assistant_msg(),
            available_messages=[user_msg()],
            current_events=[], current_workspace=None,
            delta=delta, start_sequence_no=1,
        )
        assert len(identities) == len(result.prepared_events)
        for ident, prepared in zip(identities, result.prepared_events, strict=True):
            assert ident.operation_index == prepared.operation_index
            assert ident.event_id == prepared.event.id
            assert ident.idempotency_key == prepared.idempotency_key

    def test_identity_with_option_operations(self):
        gate = ProjectDirectorDiscussionDeltaGateService()
        oid = uuid4()
        delta = make_delta(make_operation(
            op=DiscussionDeltaOperationType.ADD_OPTION, target_id=oid,
        ))
        identities = gate.prepare_replay_identities(
            session_id=SESSION_ID, assistant_message=assistant_msg(), delta=delta,
        )
        result = gate.evaluate_delta(
            session_id=SESSION_ID, project_id=None,
            assistant_message=assistant_msg(),
            available_messages=[user_msg()],
            current_events=[], current_workspace=None,
            delta=delta, start_sequence_no=1,
        )
        assert identities[0].event_id == result.prepared_events[0].event.id
        assert identities[0].idempotency_key == result.prepared_events[0].idempotency_key

    def test_identity_with_multi_operation_delta(self):
        gate = ProjectDirectorDiscussionDeltaGateService()
        delta = make_delta(
            make_operation(content="a"),
            make_operation(content="b"),
            make_operation(content="c"),
        )
        identities = gate.prepare_replay_identities(
            session_id=SESSION_ID, assistant_message=assistant_msg(), delta=delta,
        )
        result = gate.evaluate_delta(
            session_id=SESSION_ID, project_id=None,
            assistant_message=assistant_msg(),
            available_messages=[user_msg()],
            current_events=[], current_workspace=None,
            delta=delta, start_sequence_no=1,
        )
        assert len(identities) == 3
        for i, (ident, prepared) in enumerate(zip(identities, result.prepared_events, strict=True)):
            assert ident.operation_index == i
            assert ident.event_id == prepared.event.id
            assert ident.idempotency_key == prepared.idempotency_key

    def test_identity_error_propagation(self):
        """Gate errors propagate through identity helper."""
        gate = ProjectDirectorDiscussionDeltaGateService()
        # Session mismatch
        with pytest.raises(ValueError, match="discussion_delta_assistant_message_session_mismatch"):
            gate.prepare_replay_identities(
                session_id=SESSION_ID,
                assistant_message=assistant_msg(session_id=uuid4()),
                delta=make_delta(),
            )
        # Role invalid
        with pytest.raises(ValueError, match="discussion_delta_assistant_message_role_invalid"):
            gate.prepare_replay_identities(
                session_id=SESSION_ID,
                assistant_message=make_message(message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.USER),
                delta=make_delta(),
            )


# ═══════════════════════════════════════════════════════════════════════════
# 11. Error propagation
# ═══════════════════════════════════════════════════════════════════════════


class TestErrorPropagation:
    def test_assistant_session_mismatch(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            with pytest.raises(ValueError, match="discussion_delta_assistant_message_session_mismatch"):
                svc.apply_delta(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(session_id=uuid4()),
                    available_messages=[user_msg()],
                    delta=make_delta(make_operation()),
                )
            db.rollback()

    def test_assistant_role_invalid(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            with pytest.raises(ValueError, match="discussion_delta_assistant_message_role_invalid"):
                svc.apply_delta(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=make_message(message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.USER),
                    available_messages=[user_msg()],
                    delta=make_delta(make_operation()),
                )
            db.rollback()

    def test_source_message_not_found(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            with pytest.raises(ValueError, match="discussion_delta_source_message_not_found"):
                svc.apply_delta(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),
                    available_messages=[],
                    delta=make_delta(make_operation(source_message_ids=[uuid4()])),
                )
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 12. Savepoint atomicity — event failure
# ═══════════════════════════════════════════════════════════════════════════


class TestSavepointAtomicity:
    def test_second_event_failure_rolls_back_first(self, factory):
        """If second append fails, first event is also rolled back by savepoint."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        # Create a proxy that fails on second append
        call_count = 0

        class FailSecondAppendRepo:
            def __init__(self, real_repo):
                self._real = real_repo

            def list_by_session_id(self, **kw):
                return self._real.list_by_session_id(**kw)

            def get_by_idempotency_key(self, **kw):
                return self._real.get_by_idempotency_key(**kw)

            def get_next_sequence_no(self, **kw):
                return self._real.get_next_sequence_no(**kw)

            def append_if_absent(self, **kw):
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise RuntimeError("simulated second append failure")
                return self._real.append_if_absent(**kw)

        with factory() as db:
            real_repo = ProjectDirectorDiscussionEventRepository(db)
            proxy_repo = FailSecondAppendRepo(real_repo)

            # Monkey-patch the service's event repo
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc._events = proxy_repo

            with pytest.raises(RuntimeError, match="simulated second append failure"):
                svc.apply_delta(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),
                    available_messages=[user_msg()],
                    delta=make_delta(
                        make_operation(content="a"),
                        make_operation(content="b"),
                    ),
                )
            db.rollback()

        # No events persisted
        with factory() as db:
            assert _count_events(db, SESSION_ID) == 0
            assert _count_workspaces(db) == 0


# ═══════════════════════════════════════════════════════════════════════════
# 13. Workspace CAS failure
# ═══════════════════════════════════════════════════════════════════════════


class TestWorkspaceCASFailure:
    def test_stale_version_mapped_to_concurrent_conflict(self, factory):
        """Workspace CAS stale → concurrent_workspace_conflict, events rolled back."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        # First apply to create workspace
        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation(content="初始")),
            )
            db.commit()

        assistant2, avail2 = _new_assistant_round(factory)

        # Use a proxy that makes update_if_version raise stale_version
        class StaleWorkspaceRepo:
            def __init__(self, real):
                self._real = real

            def get_by_session_id(self, **kw):
                return self._real.get_by_session_id(**kw)

            def create_if_absent(self, **kw):
                return self._real.create_if_absent(**kw)

            def update_if_version(self, **kw):
                raise ValueError("discussion_workspace_stale_version")

        with factory() as db:
            real_ws = ProjectDirectorDiscussionWorkspaceRepository(db)
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc._workspaces = StaleWorkspaceRepo(real_ws)

            with pytest.raises(ValueError, match="discussion_delta_apply_concurrent_workspace_conflict"):
                svc.apply_delta(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant2,
                    available_messages=avail2,
                    delta=make_delta(make_operation(content="新")),
                )
            db.rollback()

        # Event count should still be 1 (from first apply)
        with factory() as db:
            assert _count_events(db, SESSION_ID) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 14. Concurrent interleaving
# ═══════════════════════════════════════════════════════════════════════════


class TestConcurrentInterleaving:
    def test_mixed_inserted_state_rejected(self, factory):
        """First append inserted, second returns existing → partial replay error."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        delta = make_delta(
            make_operation(content="a"),
            make_operation(content="b"),
        )
        gate = ProjectDirectorDiscussionDeltaGateService()
        identities = gate.prepare_replay_identities(
            session_id=SESSION_ID, assistant_message=assistant_msg(), delta=delta,
        )

        # Pre-persist the second event
        with factory() as db:
            event_repo = ProjectDirectorDiscussionEventRepository(db)
            # Build the second event from gate
            result = gate.evaluate_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                current_events=[], current_workspace=None,
                delta=delta, start_sequence_no=1,
            )
            second_prepared = result.prepared_events[1]
            event_repo.append_if_absent(
                event=second_prepared.event,
                idempotency_key=second_prepared.idempotency_key,
            )
            db.commit()

        # Now apply — first inserts, second returns existing → mixed
        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            with pytest.raises(ValueError, match="discussion_delta_apply_partial_replay"):
                svc.apply_delta(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),
                    available_messages=[user_msg()],
                    delta=delta,
                )
            db.rollback()

        # First event should be rolled back by savepoint
        with factory() as db:
            assert _count_events(db, SESSION_ID) == 1  # Only the pre-persisted one

    def test_concurrent_event_conflict(self, factory):
        """IntegrityError on append → concurrent_event_conflict."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        from sqlalchemy.exc import IntegrityError

        class ConflictAppendRepo:
            """Proxy that makes second event insert raise IntegrityError."""
            def __init__(self, real_repo):
                self._real = real_repo
                self._call = 0

            def list_by_session_id(self, **kw):
                return self._real.list_by_session_id(**kw)

            def get_by_idempotency_key(self, **kw):
                return self._real.get_by_idempotency_key(**kw)

            def get_next_sequence_no(self, **kw):
                return self._real.get_next_sequence_no(**kw)

            def append_if_absent(self, **kw):
                self._call += 1
                if self._call >= 2:
                    raise IntegrityError("conflict", {}, Exception("duplicate"))
                return self._real.append_if_absent(**kw)

        with factory() as db:
            real_repo = ProjectDirectorDiscussionEventRepository(db)
            proxy = ConflictAppendRepo(real_repo)
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc._events = proxy

            with pytest.raises(ValueError, match="discussion_delta_apply_concurrent_event_conflict"):
                svc.apply_delta(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),
                    available_messages=[user_msg()],
                    delta=make_delta(
                        make_operation(content="a"),
                        make_operation(content="b"),
                    ),
                )
            db.rollback()

        # No partial writes
        with factory() as db:
            assert _count_events(db, SESSION_ID) == 0

    def test_workspace_create_race(self, factory):
        """create_if_absent returns created=False → concurrent_workspace_conflict."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        class RaceWorkspaceRepo:
            """Proxy that makes create_if_absent return (ws, False)."""
            def __init__(self, real_repo, session):
                self._real = real_repo
                self._session = session

            def get_by_session_id(self, **kw):
                return self._real.get_by_session_id(**kw)

            def create_if_absent(self, **kw):
                # Actually create it first (to get a valid workspace), then return False
                ws, created = self._real.create_if_absent(**kw)
                if created:
                    # Simulate race: another transaction already created it
                    # Return the workspace but with created=False
                    return ws, False
                return ws, False

            def update_if_version(self, **kw):
                return self._real.update_if_version(**kw)

        with factory() as db:
            real_ws = ProjectDirectorDiscussionWorkspaceRepository(db)
            proxy = RaceWorkspaceRepo(real_ws, db)
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc._workspaces = proxy

            with pytest.raises(ValueError, match="discussion_delta_apply_concurrent_workspace_conflict"):
                svc.apply_delta(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),
                    available_messages=[user_msg()],
                    delta=make_delta(make_operation()),
                )
            db.rollback()

    def test_exact_concurrent_replay(self, factory):
        """Preflight misses, but append returns existing → REPLAYED."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        delta = make_delta(make_operation())
        gate = ProjectDirectorDiscussionDeltaGateService()
        result = gate.evaluate_delta(
            session_id=SESSION_ID, project_id=None,
            assistant_message=assistant_msg(),
            available_messages=[user_msg()],
            current_events=[], current_workspace=None,
            delta=delta, start_sequence_no=1,
        )

        # Pre-persist the event and workspace
        with factory() as db:
            event_repo = ProjectDirectorDiscussionEventRepository(db)
            ws_repo = ProjectDirectorDiscussionWorkspaceRepository(db)
            prepared = result.prepared_events[0]
            event_repo.append_if_absent(
                event=prepared.event, idempotency_key=prepared.idempotency_key,
            )
            ws = ProjectDirectorDiscussionWorkspaceReducerService().rebuild_workspace(
                session_id=SESSION_ID, project_id=None,
                events=[prepared.event], version_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            ws_repo.create_if_absent(
                workspace=ProjectDirectorDiscussionWorkspaceReducerService().rebuild_workspace(
                    session_id=SESSION_ID, project_id=None, events=[], version_no=0,
                    created_at=FIXED_TIME, updated_at=FIXED_TIME,
                ),
            )
            ws_repo.update_if_version(workspace=ws, expected_version_no=0)
            db.commit()

        # Now apply — preflight won't find via idempotency key check path
        # but the event already exists. Since D2 checks idempotency keys first,
        # and the event IS in the DB with the right key, this should be REPLAYED.
        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            r = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=delta,
            )
            assert r.status is DiscussionDeltaApplyStatus.REPLAYED
            assert r.inserted_event_count == 0
            assert r.workspace_changed is False
            assert r.workspace.version_no == 1
            assert r.workspace.last_event_sequence_no == 1
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 15. Persisted event mismatch
# ═══════════════════════════════════════════════════════════════════════════


class TestPersistedEventMismatch:
    def test_persisted_event_mismatch_rejected(self, factory):
        """append_if_absent returns a different domain event → mismatch error."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        from app.domain.project_director_discussion import DiscussionEvent as DomainEvent

        class MismatchAppendRepo:
            """Returns a domain event with different content."""
            def __init__(self, real_repo):
                self._real = real_repo

            def list_by_session_id(self, **kw):
                return self._real.list_by_session_id(**kw)

            def get_by_idempotency_key(self, **kw):
                return self._real.get_by_idempotency_key(**kw)

            def get_next_sequence_no(self, **kw):
                return self._real.get_next_sequence_no(**kw)

            def append_if_absent(self, *, event, idempotency_key):
                # Insert the real event, then return a modified copy
                real_event, inserted = self._real.append_if_absent(
                    event=event, idempotency_key=idempotency_key,
                )
                # Return a domain event with different content
                return DomainEvent(
                    id=real_event.id,
                    session_id=real_event.session_id,
                    project_id=real_event.project_id,
                    sequence_no=real_event.sequence_no,
                    event_type=real_event.event_type,
                    subject_key=real_event.subject_key,
                    content="TAMPERED",  # Different content
                    status=real_event.status,
                    payload=real_event.payload,
                    source_message_ids=real_event.source_message_ids,
                    supersedes_event_id=real_event.supersedes_event_id,
                    created_by=real_event.created_by,
                    confidence=real_event.confidence,
                    created_at=real_event.created_at,
                ), inserted

        with factory() as db:
            real_repo = ProjectDirectorDiscussionEventRepository(db)
            proxy = MismatchAppendRepo(real_repo)
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc._events = proxy

            with pytest.raises(ValueError, match="discussion_delta_apply_persisted_event_mismatch"):
                svc.apply_delta(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),
                    available_messages=[user_msg()],
                    delta=make_delta(make_operation()),
                )
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 16. Input immutability
# ═══════════════════════════════════════════════════════════════════════════


class TestInputImmutability:
    def test_inputs_unchanged_after_applied(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        with factory() as db:
            msg = assistant_msg()
            delta = make_delta(make_operation(payload={"nested": ["中文", {"x": 1}]}))
            msgs = [user_msg()]
            before = (
                msg.model_dump(mode="python"),
                delta.model_dump(mode="python"),
                [m.model_dump(mode="python") for m in msgs],
            )
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=msg, available_messages=msgs, delta=delta,
            )
            after = (
                msg.model_dump(mode="python"),
                delta.model_dump(mode="python"),
                [m.model_dump(mode="python") for m in msgs],
            )
            assert after == before
            db.rollback()

    def test_inputs_unchanged_after_requires_confirmation(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        with factory() as db:
            msg = assistant_msg()
            delta = make_delta(
                make_operation(
                    op=DiscussionDeltaOperationType.CONFIRM_DECISION,
                    actor_claim=DiscussionActorClaim.ASSISTANT_PROPOSAL,
                ),
            )
            msgs = [user_msg()]
            before = (msg.model_dump(mode="python"), delta.model_dump(mode="python"))
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=msg, available_messages=msgs, delta=delta,
            )
            after = (msg.model_dump(mode="python"), delta.model_dump(mode="python"))
            assert after == before
            db.rollback()

    def test_inputs_unchanged_after_no_changes(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        with factory() as db:
            msg = assistant_msg()
            delta = DiscussionDelta(operations=[])
            before = (msg.model_dump(mode="python"), delta.model_dump(mode="python"))
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=msg, available_messages=[user_msg()], delta=delta,
            )
            after = (msg.model_dump(mode="python"), delta.model_dump(mode="python"))
            assert after == before
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 17. AST boundary
# ═══════════════════════════════════════════════════════════════════════════


class TestASTBoundary:
    @pytest.fixture(scope="class")
    def apply_ast(self):
        path = Path(__file__).parents[1] / "app/services/project_director_discussion_delta_apply_service.py"
        return ast.parse(path.read_text())

    @pytest.fixture(scope="class")
    def gate_ast(self):
        path = Path(__file__).parents[1] / "app/services/project_director_discussion_delta_gate_service.py"
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

    def test_apply_no_commit_rollback(self, apply_ast):
        attrs = self._get_call_attrs(apply_ast)
        assert "commit" not in attrs, "Service must not call .commit()"
        assert "rollback" not in attrs, "Service must not call .rollback()"

    def test_apply_has_begin_nested(self, apply_ast):
        attrs = self._get_call_attrs(apply_ast)
        assert "begin_nested" in attrs, "Service must use begin_nested for savepoint"

    def test_apply_no_message_repository(self, apply_ast):
        imports = self._get_imports(apply_ast)
        for imp in imports:
            assert "message_repository" not in imp.lower(), f"Forbidden import: {imp}"

    def test_apply_no_fastapi_provider(self, apply_ast):
        imports = self._get_imports(apply_ast)
        for imp in imports:
            assert "fastapi" not in imp.lower(), f"Forbidden import: {imp}"
            assert "provider" not in imp.lower(), f"Forbidden import: {imp}"

    def test_gate_identity_helper_pure(self, gate_ast):
        """Gate's prepare_replay_identities has no DB/commit side effects."""
        imports = self._get_imports(gate_ast)
        for imp in imports:
            assert "sqlalchemy" not in imp.lower(), f"Gate import: {imp}"
            assert not imp.startswith("app.repositories"), f"Gate import: {imp}"
            assert not imp.startswith("app.core.db_tables"), f"Gate import: {imp}"
        attrs = self._get_call_attrs(gate_ast)
        for forbidden in ("commit", "rollback", "flush"):
            assert forbidden not in attrs, f"Gate calls .{forbidden}()"

    def test_apply_no_create_engine(self, apply_ast):
        imports = self._get_imports(apply_ast)
        for imp in imports:
            assert "create_engine" not in imp, f"Forbidden: {imp}"
            assert "sessionmaker" not in imp, f"Forbidden: {imp}"


# ═══════════════════════════════════════════════════════════════════════════
# 18. Workspace version increment
# ═══════════════════════════════════════════════════════════════════════════


class TestWorkspaceVersionIncrement:
    def test_version_increments_by_one(self, factory):
        """Each apply increments workspace version by exactly 1."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        for i in range(3):
            if i > 0:
                new_asst, avail = _new_assistant_round(factory, content=f"轮{i}")
            else:
                new_asst = assistant_msg()
                avail = [user_msg()]

            with factory() as db:
                svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
                r = svc.apply_delta(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=new_asst,
                    available_messages=avail,
                    delta=make_delta(make_operation(content=f"op{i}")),
                )
                assert r.status is DiscussionDeltaApplyStatus.APPLIED
                assert r.workspace.version_no == i + 1
                assert r.workspace.last_event_sequence_no == i + 1
                db.commit()

        with factory() as db:
            ws = _get_workspace(db)
            assert ws is not None
            assert ws.version_no == 3
            assert ws.last_event_sequence_no == 3


# ═══════════════════════════════════════════════════════════════════════════
# 19. Mixed inserted — real branch (§8)
# ═══════════════════════════════════════════════════════════════════════════


class TestMixedInsertedRealBranch:
    def test_mixed_true_false_triggers_partial_replay(self, factory):
        """First append returns inserted=True, second returns inserted=False
        within the same apply savepoint → partial_replay, all rolled back."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID,
                          role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        delta = make_delta(
            make_operation(content="a"),
            make_operation(content="b"),
        )
        gate = ProjectDirectorDiscussionDeltaGateService()
        identities = gate.prepare_replay_identities(
            session_id=SESSION_ID, assistant_message=assistant_msg(), delta=delta,
        )

        class MixedInsertRepo:
            """First append: real insert (True). Second: pre-insert then real append (False)."""
            def __init__(self, real, session):
                self._real = real
                self._session = session
                self._call = 0
                self.call_log: list[tuple[int, bool]] = []

            def list_by_session_id(self, **kw):
                return self._real.list_by_session_id(**kw)

            def get_by_idempotency_key(self, **kw):
                return self._real.get_by_idempotency_key(**kw)

            def get_next_sequence_no(self, **kw):
                return self._real.get_next_sequence_no(**kw)

            def append_if_absent(self, *, event, idempotency_key):
                self._call += 1
                if self._call == 1:
                    result = self._real.append_if_absent(
                        event=event, idempotency_key=idempotency_key,
                    )
                    self.call_log.append((1, result[1]))
                    return result
                # Second call: pre-insert via real repo in a nested savepoint,
                # then call real append again → returns (existing, False)
                self._real.append_if_absent(
                    event=event, idempotency_key=idempotency_key,
                )
                result = self._real.append_if_absent(
                    event=event, idempotency_key=idempotency_key,
                )
                self.call_log.append((2, result[1]))
                return result

        with factory() as db:
            real_repo = ProjectDirectorDiscussionEventRepository(db)
            proxy = MixedInsertRepo(real_repo, db)
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc._events = proxy

            with pytest.raises(ValueError, match="discussion_delta_apply_partial_replay"):
                svc.apply_delta(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),
                    available_messages=[user_msg()],
                    delta=delta,
                )
            db.rollback()

        # Verify proxy actually entered mixed branch
        assert len(proxy.call_log) == 2
        assert proxy.call_log[0] == (1, True)   # first: inserted
        assert proxy.call_log[1] == (2, False)  # second: not inserted

        # Savepoint rolled back everything
        with factory() as db:
            assert _count_events(db, SESSION_ID) == 0
            assert _count_workspaces(db) == 0


# ═══════════════════════════════════════════════════════════════════════════
# 20. Exact concurrent replay — real branch (§9)
# ═══════════════════════════════════════════════════════════════════════════


class TestExactConcurrentReplayRealBranch:
    def test_preflight_miss_append_returns_existing(self, factory):
        """Preflight sees nothing, but append returns existing events → REPLAYED."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID,
                          role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        delta = make_delta(make_operation())
        gate = ProjectDirectorDiscussionDeltaGateService()
        result = gate.evaluate_delta(
            session_id=SESSION_ID, project_id=None,
            assistant_message=assistant_msg(),
            available_messages=[user_msg()],
            current_events=[], current_workspace=None,
            delta=delta, start_sequence_no=1,
        )

        # Pre-persist event and workspace
        with factory() as db:
            event_repo = ProjectDirectorDiscussionEventRepository(db)
            ws_repo = ProjectDirectorDiscussionWorkspaceRepository(db)
            prepared = result.prepared_events[0]
            event_repo.append_if_absent(
                event=prepared.event, idempotency_key=prepared.idempotency_key,
            )
            empty_ws = ProjectDirectorDiscussionWorkspaceReducerService().rebuild_workspace(
                session_id=SESSION_ID, project_id=None, events=[], version_no=0,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            ws_repo.create_if_absent(workspace=empty_ws)
            projected_ws = ProjectDirectorDiscussionWorkspaceReducerService().rebuild_workspace(
                session_id=SESSION_ID, project_id=None,
                events=[prepared.event], version_no=1,
                created_at=FIXED_TIME, updated_at=FIXED_TIME,
            )
            ws_repo.update_if_version(workspace=projected_ws, expected_version_no=0)
            db.commit()

        # Proxy: hide from preflight reads, let append see real DB
        preflight_calls = {"list": 0, "idem": 0, "ws": 0}

        class HideFromPreflightEventRepo:
            def __init__(self, real):
                self._real = real

            def list_by_session_id(self, **kw):
                preflight_calls["list"] += 1
                if preflight_calls["list"] == 1:
                    return []  # stale preflight
                return self._real.list_by_session_id(**kw)

            def get_by_idempotency_key(self, **kw):
                preflight_calls["idem"] += 1
                if preflight_calls["idem"] <= len(delta.operations):
                    return None  # stale preflight
                return self._real.get_by_idempotency_key(**kw)

            def get_next_sequence_no(self, **kw):
                return 1  # stale

            def append_if_absent(self, **kw):
                return self._real.append_if_absent(**kw)

        class HideFromPreflightWSRepo:
            def __init__(self, real):
                self._real = real

            def get_by_session_id(self, **kw):
                preflight_calls["ws"] += 1
                if preflight_calls["ws"] == 1:
                    return None  # stale preflight
                return self._real.get_by_session_id(**kw)

            def create_if_absent(self, **kw):
                return self._real.create_if_absent(**kw)

            def update_if_version(self, **kw):
                return self._real.update_if_version(**kw)

        with factory() as db:
            real_event_repo = ProjectDirectorDiscussionEventRepository(db)
            real_ws_repo = ProjectDirectorDiscussionWorkspaceRepository(db)
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc._events = HideFromPreflightEventRepo(real_event_repo)
            svc._workspaces = HideFromPreflightWSRepo(real_ws_repo)

            r = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=delta,
            )
            assert r.status is DiscussionDeltaApplyStatus.REPLAYED
            assert r.inserted_event_count == 0
            assert r.workspace_changed is False
            assert all(not pe.inserted for pe in r.persisted_events)
            assert r.workspace.version_no == 1
            assert r.workspace.last_event_sequence_no == 1
            db.rollback()

        # Verify proxy actually hid preflight
        assert preflight_calls["list"] >= 1
        assert preflight_calls["idem"] >= 1
        assert preflight_calls["ws"] >= 1


# ═══════════════════════════════════════════════════════════════════════════
# 21. Workspace cursor mismatch (§10)
# ═══════════════════════════════════════════════════════════════════════════


class TestReplayWorkspaceCursorMismatch:
    def test_cursor_less_than_event_sequence(self, factory):
        """Workspace cursor < replay event sequence → mismatch error."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID,
                          role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        delta = make_delta(make_operation())
        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=delta,
            )
            db.commit()

        # Tamper workspace cursor to 0
        with factory() as db:
            ws_row = _get_workspace(db)
            assert ws_row is not None
            ws_row.last_event_sequence_no = 0
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            with pytest.raises(ValueError, match="discussion_delta_apply_replay_workspace_mismatch"):
                svc.apply_delta(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),
                    available_messages=[user_msg()],
                    delta=delta,
                )
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 22. Workspace projection mismatch (§11)
# ═══════════════════════════════════════════════════════════════════════════


class TestReplayWorkspaceProjectionMismatch:
    def test_tampered_topic(self, factory):
        """Workspace topic tampered → projection mismatch on replay."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID,
                          role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        delta = make_delta(
            make_operation(op=DiscussionDeltaOperationType.SET_TOPIC, content="正确主题"),
        )
        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=delta,
            )
            db.commit()

        # Tamper topic
        with factory() as db:
            ws_row = _get_workspace(db)
            assert ws_row is not None
            ws_row.topic = "tampered"
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            with pytest.raises(ValueError, match="discussion_delta_apply_replay_workspace_mismatch"):
                svc.apply_delta(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),
                    available_messages=[user_msg()],
                    delta=delta,
                )
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 23. Sequential replay immutability (§12)
# ═══════════════════════════════════════════════════════════════════════════


class TestReplayImmutability:
    def test_replay_preserves_all_db_state(self, factory):
        """Replay must not change any DB state."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID,
                          role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        delta = make_delta(make_operation())
        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=delta,
            )
            db.commit()

        # Snapshot DB state
        with factory() as db:
            event_count_before = _count_events(db, SESSION_ID)
            msg_count_before = _count_messages(db, SESSION_ID)
            ws_row = _get_workspace(db)
            ws_version_before = ws_row.version_no
            ws_cursor_before = ws_row.last_event_sequence_no
            ws_updated_at_before = ws_row.updated_at
            ws_topic_before = ws_row.topic
            ws_state_before = ws_row.state_json
            # Read event details
            event_rows = db.execute(
                select(ProjectDirectorDiscussionEventTable)
                .where(ProjectDirectorDiscussionEventTable.session_id == SESSION_ID)
            ).scalars().all()
            event_payloads_before = [r.payload_json for r in event_rows]
            event_created_ats_before = [r.created_at for r in event_rows]

        # Replay
        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            r = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=delta,
            )
            assert r.status is DiscussionDeltaApplyStatus.REPLAYED
            db.rollback()

        # Verify DB unchanged
        with factory() as db:
            assert _count_events(db, SESSION_ID) == event_count_before
            assert _count_messages(db, SESSION_ID) == msg_count_before
            ws_row = _get_workspace(db)
            assert ws_row.version_no == ws_version_before
            assert ws_row.last_event_sequence_no == ws_cursor_before
            assert ws_row.updated_at == ws_updated_at_before
            assert ws_row.topic == ws_topic_before
            assert ws_row.state_json == ws_state_before
            event_rows = db.execute(
                select(ProjectDirectorDiscussionEventTable)
                .where(ProjectDirectorDiscussionEventTable.session_id == SESSION_ID)
            ).scalars().all()
            assert [r.payload_json for r in event_rows] == event_payloads_before
            assert [r.created_at for r in event_rows] == event_created_ats_before


# ═══════════════════════════════════════════════════════════════════════════
# 24. Gate identity helper — extended (§13)
# ═══════════════════════════════════════════════════════════════════════════


class TestGateIdentityExtended:
    def test_supersede_operation_identity(self):
        """Identity for set_topic supersedes matches evaluate_delta."""
        gate = ProjectDirectorDiscussionDeltaGateService()
        topic_evt = DiscussionEvent(
            id=uuid4(), session_id=SESSION_ID, project_id=None,
            sequence_no=1, event_type=DiscussionEventType.TOPIC_SET,
            subject_key="topic", content="旧", status=DiscussionEventStatus.ACTIVE,
            payload={}, source_message_ids=[SYSTEM_ID],
            created_by=DiscussionActorClaim.SYSTEM_FACT, confidence=1.0,
            created_at=FIXED_TIME,
        )
        delta = make_delta(make_operation(
            op=DiscussionDeltaOperationType.SET_TOPIC,
            supersedes_event_id=topic_evt.id, content="新",
        ))
        identities = gate.prepare_replay_identities(
            session_id=SESSION_ID, assistant_message=assistant_msg(), delta=delta,
        )
        result = gate.evaluate_delta(
            session_id=SESSION_ID, project_id=None,
            assistant_message=assistant_msg(),
            available_messages=[user_msg()],
            current_events=[topic_evt], current_workspace=None,
            delta=delta, start_sequence_no=2,
        )
        assert identities[0].event_id == result.prepared_events[0].event.id
        assert identities[0].idempotency_key == result.prepared_events[0].idempotency_key

    def test_payload_key_ordering_same_identity(self):
        """Payload key order doesn't affect identity."""
        gate = ProjectDirectorDiscussionDeltaGateService()
        d1 = make_delta(make_operation(payload={"a": 1, "b": 2}))
        d2 = make_delta(make_operation(payload={"b": 2, "a": 1}))
        i1 = gate.prepare_replay_identities(
            session_id=SESSION_ID, assistant_message=assistant_msg(), delta=d1,
        )
        i2 = gate.prepare_replay_identities(
            session_id=SESSION_ID, assistant_message=assistant_msg(), delta=d2,
        )
        assert i1[0].event_id == i2[0].event_id
        assert i1[0].idempotency_key == i2[0].idempotency_key

    def test_uuid_string_vs_object_same_identity(self):
        """UUID object and equivalent string produce same identity."""
        gate = ProjectDirectorDiscussionDeltaGateService()
        oid = uuid4()
        d1 = make_delta(make_operation(
            op=DiscussionDeltaOperationType.ADD_OPTION,
            target_id=oid, payload={"option_id": oid},
        ))
        d2 = make_delta(make_operation(
            op=DiscussionDeltaOperationType.ADD_OPTION,
            target_id=oid, payload={"option_id": str(oid)},
        ))
        i1 = gate.prepare_replay_identities(
            session_id=SESSION_ID, assistant_message=assistant_msg(), delta=d1,
        )
        i2 = gate.prepare_replay_identities(
            session_id=SESSION_ID, assistant_message=assistant_msg(), delta=d2,
        )
        assert i1[0].event_id == i2[0].event_id
        assert i1[0].idempotency_key == i2[0].idempotency_key

    def test_subject_key_trim_same_identity(self):
        """Leading/trailing spaces in subject_key are trimmed to same identity."""
        gate = ProjectDirectorDiscussionDeltaGateService()
        d1 = make_delta(make_operation(subject_key="  custom-key  "))
        d2 = make_delta(make_operation(subject_key="custom-key"))
        i1 = gate.prepare_replay_identities(
            session_id=SESSION_ID, assistant_message=assistant_msg(), delta=d1,
        )
        i2 = gate.prepare_replay_identities(
            session_id=SESSION_ID, assistant_message=assistant_msg(), delta=d2,
        )
        assert i1[0].event_id == i2[0].event_id
        assert i1[0].idempotency_key == i2[0].idempotency_key

    def test_unsupported_operation_rejected(self, monkeypatch):
        """Removing an operation from the mapping → not_supported for both paths."""
        from app.services.project_director_discussion_delta_gate_service import (
            _OPERATION_EVENT_TYPES,
        )
        removed = _OPERATION_EVENT_TYPES.pop(DiscussionDeltaOperationType.ADD_CONCERN)
        try:
            gate = ProjectDirectorDiscussionDeltaGateService()
            delta = make_delta(make_operation(op=DiscussionDeltaOperationType.ADD_CONCERN))
            with pytest.raises(ValueError, match="discussion_delta_operation_not_supported"):
                gate.prepare_replay_identities(
                    session_id=SESSION_ID, assistant_message=assistant_msg(), delta=delta,
                )
            with pytest.raises(ValueError, match="discussion_delta_operation_not_supported"):
                gate.evaluate_delta(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),
                    available_messages=[user_msg()],
                    current_events=[], current_workspace=None,
                    delta=delta, start_sequence_no=1,
                )
        finally:
            _OPERATION_EVENT_TYPES[DiscussionDeltaOperationType.ADD_CONCERN] = removed


# ═══════════════════════════════════════════════════════════════════════════
# 25. Error propagation — extended (§14)
# ═══════════════════════════════════════════════════════════════════════════


class TestErrorPropagationExtended:
    def test_source_message_session_mismatch(self, factory):
        """available_messages with wrong session_id → source_message_session_mismatch."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID,
                          role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        other_session = uuid4()
        wrong_msg = make_message(
            message_id=uuid4(), session_id=other_session,
            role=ProjectDirectorMessageRole.USER,
        )
        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            with pytest.raises(ValueError, match="discussion_delta_source_message_session_mismatch"):
                svc.apply_delta(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),
                    available_messages=[wrong_msg],
                    delta=make_delta(make_operation(
                        source_message_ids=[wrong_msg.id],
                    )),
                )
            db.rollback()

    def test_repo_source_message_session_mismatch(self, factory):
        """Repository-level source session mismatch propagates unchanged."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID,
                          role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        class SourceMismatchRepo:
            """Proxy that makes append_if_absent raise source_message_session_mismatch."""
            def __init__(self, real):
                self._real = real

            def list_by_session_id(self, **kw):
                return self._real.list_by_session_id(**kw)

            def get_by_idempotency_key(self, **kw):
                return self._real.get_by_idempotency_key(**kw)

            def get_next_sequence_no(self, **kw):
                return self._real.get_next_sequence_no(**kw)

            def append_if_absent(self, **kw):
                raise ValueError("discussion_event_source_message_session_mismatch")

        with factory() as db:
            real_repo = ProjectDirectorDiscussionEventRepository(db)
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc._events = SourceMismatchRepo(real_repo)

            with pytest.raises(ValueError, match="discussion_event_source_message_session_mismatch"):
                svc.apply_delta(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),
                    available_messages=[user_msg()],
                    delta=make_delta(make_operation()),
                )
            db.rollback()

    def test_workspace_project_session_mismatch_not_mapped(self, factory):
        """workspace_project_session_mismatch is NOT mapped to concurrent_workspace_conflict."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID,
                          role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        class ProjectMismatchWSRepo:
            def __init__(self, real):
                self._real = real

            def get_by_session_id(self, **kw):
                return self._real.get_by_session_id(**kw)

            def create_if_absent(self, **kw):
                raise ValueError("discussion_workspace_project_session_mismatch")

            def update_if_version(self, **kw):
                return self._real.update_if_version(**kw)

        with factory() as db:
            real_ws = ProjectDirectorDiscussionWorkspaceRepository(db)
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc._workspaces = ProjectMismatchWSRepo(real_ws)

            with pytest.raises(ValueError, match="discussion_workspace_project_session_mismatch"):
                svc.apply_delta(
                    session_id=SESSION_ID, project_id=None,
                    assistant_message=assistant_msg(),
                    available_messages=[user_msg()],
                    delta=make_delta(make_operation()),
                )
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 26. REPLAYED input immutability (§15)
# ═══════════════════════════════════════════════════════════════════════════


class TestReplayedInputImmutability:
    def test_inputs_unchanged_after_replayed(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID,
                          role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        # First apply
        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation()),
            )
            db.commit()

        # Replay with input snapshots
        msg = assistant_msg()
        delta = make_delta(make_operation())
        msgs = [user_msg()]
        before = (
            msg.model_dump(mode="python"),
            delta.model_dump(mode="python"),
            [m.model_dump(mode="python") for m in msgs],
        )

        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            r = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=msg, available_messages=msgs, delta=delta,
            )
            assert r.status is DiscussionDeltaApplyStatus.REPLAYED
            after = (
                msg.model_dump(mode="python"),
                delta.model_dump(mode="python"),
                [m.model_dump(mode="python") for m in msgs],
            )
            assert after == before
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 27. Frozen contract — actual field assignment (§16)
# ═══════════════════════════════════════════════════════════════════════════


class TestFrozenContractActual:
    def test_applied_event_field_assignment_raises(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID,
                          role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            result = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation()),
            )
            pe = result.persisted_events[0]
            with pytest.raises(FrozenInstanceError):
                pe.operation_index = 99
            with pytest.raises(FrozenInstanceError):
                pe.inserted = False
            with pytest.raises(FrozenInstanceError):
                pe.idempotency_key = "changed"
            db.rollback()

    def test_identity_field_assignment_raises(self):
        ident = DiscussionDeltaOperationIdentity(
            operation_index=0, event_id=uuid4(), idempotency_key="key",
        )
        with pytest.raises(FrozenInstanceError):
            ident.operation_index = 1
        with pytest.raises(FrozenInstanceError):
            ident.event_id = uuid4()
        with pytest.raises(FrozenInstanceError):
            ident.idempotency_key = "changed"

    def test_apply_result_field_assignment_raises(self, factory):
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID,
                          role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            result = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=make_delta(make_operation()),
            )
            with pytest.raises(FrozenInstanceError):
                result.status = DiscussionDeltaApplyStatus.NO_CHANGES
            with pytest.raises(FrozenInstanceError):
                result.inserted_event_count = 0
            with pytest.raises(FrozenInstanceError):
                result.workspace_changed = False
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 28. Workspace version/cursor unchanged on replay (extra assertion)
# ═══════════════════════════════════════════════════════════════════════════


class TestReplayWorkspaceUnchanged:
    def test_replay_does_not_advance_version_or_cursor(self, factory):
        """Replay must return exact same workspace version/cursor/updated_at."""
        with factory() as db:
            _seed_session(db)
            _seed_message(db, SESSION_ID, message_id=USER_ID)
            _seed_message(db, SESSION_ID, message_id=ASSISTANT_ID,
                          role=ProjectDirectorMessageRole.ASSISTANT)
            db.commit()

        delta = make_delta(make_operation())
        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=delta,
            )
            db.commit()

        with factory() as db:
            ws_row = _get_workspace(db)
            orig_version = ws_row.version_no
            orig_cursor = ws_row.last_event_sequence_no
            orig_updated = ws_row.updated_at

        with factory() as db:
            svc = ProjectDirectorDiscussionDeltaApplyService(session=db)
            r = svc.apply_delta(
                session_id=SESSION_ID, project_id=None,
                assistant_message=assistant_msg(),
                available_messages=[user_msg()],
                delta=delta,
            )
            assert r.status is DiscussionDeltaApplyStatus.REPLAYED
            assert r.workspace.version_no == orig_version
            assert r.workspace.last_event_sequence_no == orig_cursor
            # updated_at must not change
            ws_row = _get_workspace(db)
            assert ws_row.updated_at == orig_updated
            db.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# Helpers for factory fixture reuse
# ═══════════════════════════════════════════════════════════════════════════


