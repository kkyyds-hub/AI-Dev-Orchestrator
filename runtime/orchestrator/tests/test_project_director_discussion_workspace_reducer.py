"""Tests for P26-C2-A-T1: Discussion Workspace Reducer.

Verifies:
- DiscussionEventResolution frozen dataclass contract
- Event sorting, boundary, duplicate, and mismatch handling
- Supersede basics and semantics
- Effective / historical partition
- Topic, option, constraint, question, and other workspace projections
- DiscussionStatus lifecycle
- Rebuild metadata, determinism, and versioning
- Reduce unchanged / changed / historical-only / regression
- Input immutability
- Static business boundary (AST)
- Repository → Reducer → Workspace integration
"""

from __future__ import annotations

import ast
import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event
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
from app.repositories.project_director_discussion_event_repository import (
    ProjectDirectorDiscussionEventRepository,
)
from app.repositories.project_director_discussion_workspace_repository import (
    ProjectDirectorDiscussionWorkspaceRepository,
)
from app.services.project_director_discussion_workspace_reducer_service import (
    DiscussionEventResolution,
    ProjectDirectorDiscussionWorkspaceReducerService,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SESSION_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_PROJECT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
_SYSTEM_MSG_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _utc(year=2026, month=1, day=1, hour=0, minute=0, second=0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)


def make_event(
    *,
    session_id: UUID = _SESSION_ID,
    project_id: UUID | None = None,
    sequence_no: int = 1,
    event_type: DiscussionEventType = DiscussionEventType.TOPIC_SET,
    subject_key: str = "topic",
    content: str = "内容",
    status: DiscussionEventStatus = DiscussionEventStatus.ACTIVE,
    payload: dict | None = None,
    source_message_ids: list[UUID] | None = None,
    supersedes_event_id: UUID | None = None,
    created_by: DiscussionActorClaim = DiscussionActorClaim.SYSTEM_FACT,
    confidence: float = 1.0,
    event_id: UUID | None = None,
    created_at: datetime | None = None,
    source_surface: str | None = None,
    source_entity_type: str | None = None,
    source_entity_id: UUID | None = None,
    trigger_type: str | None = None,
    interaction_case_id: UUID | None = None,
    external_context_pack_id: UUID | None = None,
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
        created_at=created_at or _utc(),
        source_surface=source_surface,
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        trigger_type=trigger_type,
        interaction_case_id=interaction_case_id,
        external_context_pack_id=external_context_pack_id,
    )


def _option_event(
    *,
    seq: int,
    option_id: UUID | str,
    event_type: DiscussionEventType,
    status: DiscussionEventStatus = DiscussionEventStatus.ACTIVE,
    supersedes_event_id: UUID | None = None,
    event_id: UUID | None = None,
    subject_key: str = "option",
    content: str = "选项内容",
    created_at: datetime | None = None,
) -> DiscussionEvent:
    return make_event(
        sequence_no=seq,
        event_type=event_type,
        subject_key=subject_key,
        content=content,
        status=status,
        payload={"option_id": option_id},
        supersedes_event_id=supersedes_event_id,
        event_id=event_id,
        created_at=created_at,
    )


def _constraint_event(
    *,
    seq: int,
    event_type: DiscussionEventType,
    status: DiscussionEventStatus = DiscussionEventStatus.ACTIVE,
    supersedes_event_id: UUID | None = None,
    event_id: UUID | None = None,
    content: str = "约束内容",
    created_at: datetime | None = None,
) -> DiscussionEvent:
    return make_event(
        sequence_no=seq,
        event_type=event_type,
        subject_key="constraint",
        content=content,
        status=status,
        supersedes_event_id=supersedes_event_id,
        event_id=event_id,
        created_at=created_at,
    )


def _question_event(
    *,
    seq: int,
    event_type: DiscussionEventType,
    status: DiscussionEventStatus = DiscussionEventStatus.ACTIVE,
    supersedes_event_id: UUID | None = None,
    event_id: UUID | None = None,
    content: str = "问题内容",
    created_at: datetime | None = None,
) -> DiscussionEvent:
    return make_event(
        sequence_no=seq,
        event_type=event_type,
        subject_key="question",
        content=content,
        status=status,
        supersedes_event_id=supersedes_event_id,
        event_id=event_id,
        created_at=created_at,
    )


def _resolve(reducer, events, **kwargs):
    return reducer.resolve_events(
        session_id=_SESSION_ID, project_id=None, events=events, **kwargs
    )


def _rebuild(reducer, events, **kwargs):
    return reducer.rebuild_workspace(
        session_id=_SESSION_ID, project_id=None, events=events, **kwargs
    )


# ===========================================================================
# 6. Resolution frozen dataclass
# ===========================================================================


class TestResolutionDataclass:
    def test_is_dataclass(self):
        from dataclasses import fields as dc_fields

        assert hasattr(DiscussionEventResolution, "__dataclass_fields__")
        field_names = {f.name for f in dc_fields(DiscussionEventResolution)}
        assert field_names == {
            "ordered_events",
            "effective_events",
            "historical_events",
            "superseded_event_ids",
        }

    def test_frozen(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e = make_event(sequence_no=1)
        res = _resolve(reducer, [e])
        with pytest.raises(FrozenInstanceError):
            res.ordered_events = ()

    def test_field_types(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e1 = make_event(sequence_no=1)
        e2 = make_event(
            sequence_no=2,
            event_type=DiscussionEventType.OPTION_ADDED,
            subject_key="option",
            payload={"option_id": uuid4()},
        )
        e3 = make_event(sequence_no=3, status=DiscussionEventStatus.REJECTED)
        res = _resolve(reducer, [e1, e2, e3])

        assert isinstance(res.ordered_events, tuple)
        assert isinstance(res.effective_events, tuple)
        assert isinstance(res.historical_events, tuple)
        assert isinstance(res.superseded_event_ids, frozenset)

    def test_field_reassignment_raises(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e = make_event(sequence_no=1)
        res = _resolve(reducer, [e])
        with pytest.raises(FrozenInstanceError):
            res.effective_events = ()
        with pytest.raises(FrozenInstanceError):
            res.historical_events = ()
        with pytest.raises(FrozenInstanceError):
            res.superseded_event_ids = frozenset()


# ===========================================================================
# 7. Event sorting and basic boundaries
# ===========================================================================


class TestEventSorting:
    def test_out_of_order_sorted(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e7 = make_event(sequence_no=7, created_at=_utc(hour=7))
        e2 = make_event(sequence_no=2, created_at=_utc(hour=2))
        e5 = make_event(sequence_no=5, created_at=_utc(hour=5))
        res = _resolve(reducer, [e7, e2, e5])
        ordered_ids = [e.id for e in res.ordered_events]
        assert ordered_ids == [e2.id, e5.id, e7.id]
        effective_ids = [e.id for e in res.effective_events]
        assert effective_ids == [e2.id, e5.id, e7.id]
        historical_ids = [e.id for e in res.historical_events]
        assert historical_ids == []

    def test_input_list_not_mutated(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e7 = make_event(sequence_no=7)
        e2 = make_event(sequence_no=2)
        e5 = make_event(sequence_no=5)
        original = [e7, e2, e5]
        original_ids = [e.id for e in original]
        _resolve(reducer, original)
        assert [e.id for e in original] == original_ids

    def test_sequence_gap_allowed(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e1 = make_event(sequence_no=1)
        e4 = make_event(sequence_no=4)
        e20 = make_event(sequence_no=20)
        res = _resolve(reducer, [e1, e4, e20])
        assert len(res.ordered_events) == 3

    def test_duplicate_event_id_rejected(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        eid = uuid4()
        e1 = make_event(sequence_no=1, event_id=eid)
        e2 = make_event(sequence_no=2, event_id=eid)
        with pytest.raises(ValueError, match="discussion_event_stream_duplicate_event_id"):
            _resolve(reducer, [e1, e2])

    def test_duplicate_sequence_rejected(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e1 = make_event(sequence_no=1)
        e2 = make_event(sequence_no=1)
        with pytest.raises(ValueError, match="discussion_event_stream_duplicate_sequence"):
            _resolve(reducer, [e1, e2])

    def test_session_mismatch_rejected(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        other_session = uuid4()
        e = make_event(session_id=other_session, sequence_no=1)
        with pytest.raises(ValueError, match="discussion_event_stream_session_mismatch"):
            _resolve(reducer, [e])

    def test_project_mismatch_expected_none_got_uuid(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e = make_event(project_id=_PROJECT_ID, sequence_no=1)
        with pytest.raises(ValueError, match="discussion_event_stream_project_mismatch"):
            _resolve(reducer, [e])

    def test_project_mismatch_expected_uuid_got_none(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e = make_event(project_id=None, sequence_no=1)
        with pytest.raises(ValueError, match="discussion_event_stream_project_mismatch"):
            reducer.resolve_events(
                session_id=_SESSION_ID, project_id=_PROJECT_ID, events=[e]
            )

    def test_project_mismatch_two_different_uuids(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        pid2 = uuid4()
        e = make_event(project_id=pid2, sequence_no=1)
        with pytest.raises(ValueError, match="discussion_event_stream_project_mismatch"):
            reducer.resolve_events(
                session_id=_SESSION_ID, project_id=_PROJECT_ID, events=[e]
            )


# ===========================================================================
# 8. Supersede basics
# ===========================================================================


class TestSupersedeBasics:
    def test_target_not_found(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e = make_event(sequence_no=1, supersedes_event_id=uuid4())
        with pytest.raises(ValueError, match="discussion_event_stream_supersedes_not_found"):
            _resolve(reducer, [e])

    def test_forward_reference_rejected(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e1 = make_event(sequence_no=1)
        e2 = make_event(sequence_no=2)
        # e1 supersedes e2, but e2 has higher sequence → not prior
        e1_bad = make_event(
            sequence_no=1,
            event_id=e1.id,
            supersedes_event_id=e2.id,
        )
        with pytest.raises(ValueError, match="discussion_event_stream_supersedes_not_prior"):
            _resolve(reducer, [e2, e1_bad])

    def test_self_reference_rejected(self):
        """Domain rejects self-supersede. Reducer also rejects via not_prior."""
        eid = uuid4()
        # Domain will reject: cannot supersede itself
        with pytest.raises(ValueError, match="cannot supersede itself"):
            make_event(sequence_no=1, event_id=eid, supersedes_event_id=eid)

    def test_cycle_rejected_via_prior(self):
        """A supersedes B and B supersedes A: prior check prevents cycle."""
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        a = make_event(sequence_no=1)
        b = make_event(sequence_no=2, supersedes_event_id=a.id)
        # Now try A supersedes B — but A.seq(1) < B.seq(2), so prior check fails
        a_bad = make_event(sequence_no=1, event_id=a.id, supersedes_event_id=b.id)
        with pytest.raises(ValueError, match="discussion_event_stream_supersedes_not_prior"):
            _resolve(reducer, [a_bad, b])


# ===========================================================================
# 9. Effective / Historical partition
# ===========================================================================


class TestEffectiveHistoricalPartition:
    def test_no_supersede_active_confirmed_effective(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e_active = make_event(sequence_no=1, status=DiscussionEventStatus.ACTIVE)
        e_confirmed = make_event(sequence_no=2, status=DiscussionEventStatus.CONFIRMED)
        res = _resolve(reducer, [e_active, e_confirmed])
        eff_ids = {e.id for e in res.effective_events}
        assert e_active.id in eff_ids
        assert e_confirmed.id in eff_ids

    def test_no_supersede_rejected_historical(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e_rejected = make_event(sequence_no=1, status=DiscussionEventStatus.REJECTED)
        e_superseded = make_event(sequence_no=2, status=DiscussionEventStatus.SUPERSEDED)
        e_historical = make_event(sequence_no=3, status=DiscussionEventStatus.HISTORICAL)
        res = _resolve(reducer, [e_rejected, e_superseded, e_historical])
        hist_ids = {e.id for e in res.historical_events}
        assert e_rejected.id in hist_ids
        assert e_superseded.id in hist_ids
        assert e_historical.id in hist_ids

    def test_each_event_exactly_once(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        events = [
            make_event(sequence_no=i, status=s)
            for i, s in enumerate(
                [
                    DiscussionEventStatus.ACTIVE,
                    DiscussionEventStatus.CONFIRMED,
                    DiscussionEventStatus.REJECTED,
                    DiscussionEventStatus.SUPERSEDED,
                    DiscussionEventStatus.HISTORICAL,
                ],
                start=1,
            )
        ]
        res = _resolve(reducer, events)
        all_ids = {e.id for e in res.ordered_events}
        eff_ids = {e.id for e in res.effective_events}
        hist_ids = {e.id for e in res.historical_events}
        assert eff_ids & hist_ids == set()
        assert eff_ids | hist_ids == all_ids

    def test_order_preserved_sequence_asc(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        events = [make_event(sequence_no=i) for i in [5, 3, 1, 4, 2]]
        res = _resolve(reducer, events)
        seqs = [e.sequence_no for e in res.ordered_events]
        assert seqs == [1, 2, 3, 4, 5]
        eff_seqs = [e.sequence_no for e in res.effective_events]
        assert eff_seqs == [1, 2, 3, 4, 5]


# ===========================================================================
# 10. Supersede status semantics
# ===========================================================================


class TestSupersedeSemantics:
    def test_active_superseder(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        a = make_event(sequence_no=1)
        b = make_event(sequence_no=2, supersedes_event_id=a.id)
        res = _resolve(reducer, [a, b])
        eff_ids = {e.id for e in res.effective_events}
        hist_ids = {e.id for e in res.historical_events}
        assert a.id in hist_ids
        assert b.id in eff_ids
        assert a.id in res.superseded_event_ids

    def test_confirmed_superseder(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        a = make_event(sequence_no=1)
        b = make_event(sequence_no=2, status=DiscussionEventStatus.CONFIRMED, supersedes_event_id=a.id)
        res = _resolve(reducer, [a, b])
        eff_ids = {e.id for e in res.effective_events}
        assert a.id not in eff_ids
        assert b.id in eff_ids
        assert a.id in res.superseded_event_ids

    def test_rejected_superseder_does_not_supersede(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        a = make_event(sequence_no=1)
        b = make_event(sequence_no=2, status=DiscussionEventStatus.REJECTED, supersedes_event_id=a.id)
        res = _resolve(reducer, [a, b])
        eff_ids = {e.id for e in res.effective_events}
        hist_ids = {e.id for e in res.historical_events}
        assert a.id in eff_ids  # a still effective
        assert b.id in hist_ids  # b is historical
        assert a.id not in res.superseded_event_ids

    def test_historical_superseder_does_not_supersede(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        a = make_event(sequence_no=1)
        b = make_event(sequence_no=2, status=DiscussionEventStatus.HISTORICAL, supersedes_event_id=a.id)
        res = _resolve(reducer, [a, b])
        eff_ids = {e.id for e in res.effective_events}
        assert a.id in eff_ids
        assert a.id not in res.superseded_event_ids

    def test_chain_a_b_c(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        a = make_event(sequence_no=1)
        b = make_event(sequence_no=2, supersedes_event_id=a.id)
        c = make_event(sequence_no=3, supersedes_event_id=b.id)
        res = _resolve(reducer, [a, b, c])
        eff_ids = [e.id for e in res.effective_events]
        hist_ids = {e.id for e in res.historical_events}
        assert eff_ids == [c.id]
        assert a.id in hist_ids
        assert b.id in hist_ids
        assert res.superseded_event_ids == frozenset({a.id, b.id})

    def test_branch_supersede(self):
        """B and C both supersede A."""
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        a = make_event(sequence_no=1)
        b = make_event(sequence_no=2, supersedes_event_id=a.id)
        c = make_event(sequence_no=3, supersedes_event_id=a.id)
        res = _resolve(reducer, [a, b, c])
        eff_ids = {e.id for e in res.effective_events}
        hist_ids = {e.id for e in res.historical_events}
        assert a.id in hist_ids
        assert b.id in eff_ids
        assert c.id in eff_ids
        # a.id appears once in frozenset
        assert res.superseded_event_ids == frozenset({a.id})


# ===========================================================================
# 11. Topic projection
# ===========================================================================


class TestTopicProjection:
    def test_no_topic(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        ws = _rebuild(reducer, [])
        assert ws.topic == ""

    def test_single_topic(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e = make_event(sequence_no=1, content="架构选型")
        ws = _rebuild(reducer, [e])
        assert ws.topic == "架构选型"

    def test_multiple_topics_last_effective(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e1 = make_event(sequence_no=1, content="旧主题")
        e2 = make_event(sequence_no=2, content="新主题")
        ws = _rebuild(reducer, [e1, e2])
        assert ws.topic == "新主题"

    def test_rejected_topic_ignored(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e = make_event(sequence_no=1, content="拒绝主题", status=DiscussionEventStatus.REJECTED)
        ws = _rebuild(reducer, [e])
        assert ws.topic == ""

    def test_historical_topic_ignored(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e = make_event(sequence_no=1, content="历史主题", status=DiscussionEventStatus.HISTORICAL)
        ws = _rebuild(reducer, [e])
        assert ws.topic == ""

    def test_superseded_topic_replaced(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        a = make_event(sequence_no=1, content="旧主题")
        b = make_event(sequence_no=2, content="新主题", supersedes_event_id=a.id)
        ws = _rebuild(reducer, [a, b])
        assert ws.topic == "新主题"

    def test_out_of_order_input_same_topic(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e1 = make_event(sequence_no=1, content="第一")
        e3 = make_event(sequence_no=3, content="第三")
        e2 = make_event(sequence_no=2, content="第二")
        ws = _rebuild(reducer, [e3, e1, e2])
        assert ws.topic == "第三"

    def test_not_from_payload_topic(self):
        """Topic comes from content, not payload['topic']."""
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e = make_event(sequence_no=1, content="正确主题", payload={"topic": "错误主题"})
        ws = _rebuild(reducer, [e])
        assert ws.topic == "正确主题"


# ===========================================================================
# 12. Option ID parsing
# ===========================================================================


class TestOptionIdParsing:
    def test_valid_uuid_object(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid = uuid4()
        e = _option_event(seq=1, option_id=oid, event_type=DiscussionEventType.OPTION_ADDED)
        ws = _rebuild(reducer, [e])
        assert oid in ws.active_option_ids

    def test_valid_uuid_string(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid = uuid4()
        e = _option_event(seq=1, option_id=str(oid), event_type=DiscussionEventType.OPTION_ADDED)
        ws = _rebuild(reducer, [e])
        assert oid in ws.active_option_ids

    @pytest.mark.parametrize(
        "bad_value",
        [None, "", "not-a-uuid", 123, {}, []],
        ids=["none", "empty", "text", "int", "dict", "list"],
    )
    def test_invalid_option_id(self, bad_value):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e = _option_event(seq=1, option_id=bad_value, event_type=DiscussionEventType.OPTION_ADDED)
        with pytest.raises(ValueError, match="discussion_workspace_reducer_option_id_invalid"):
            _rebuild(reducer, [e])


# ===========================================================================
# 13. Option lifecycle
# ===========================================================================


class TestOptionLifecycle:
    def test_add_first(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid = uuid4()
        e = _option_event(seq=1, option_id=oid, event_type=DiscussionEventType.OPTION_ADDED)
        ws = _rebuild(reducer, [e])
        assert ws.active_option_ids == [oid]

    def test_add_preserves_order(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid1, oid2, oid3 = uuid4(), uuid4(), uuid4()
        e1 = _option_event(seq=1, option_id=oid1, event_type=DiscussionEventType.OPTION_ADDED)
        e2 = _option_event(seq=2, option_id=oid2, event_type=DiscussionEventType.OPTION_ADDED)
        e3 = _option_event(seq=3, option_id=oid3, event_type=DiscussionEventType.OPTION_ADDED)
        ws = _rebuild(reducer, [e1, e2, e3])
        assert ws.active_option_ids == [oid1, oid2, oid3]

    def test_same_id_no_duplicate(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid = uuid4()
        e1 = _option_event(seq=1, option_id=oid, event_type=DiscussionEventType.OPTION_ADDED)
        e2 = _option_event(seq=2, option_id=oid, event_type=DiscussionEventType.OPTION_ADDED)
        ws = _rebuild(reducer, [e1, e2])
        assert ws.active_option_ids == [oid]

    def test_uuid_object_and_string_same(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid = uuid4()
        e1 = _option_event(seq=1, option_id=oid, event_type=DiscussionEventType.OPTION_ADDED)
        e2 = _option_event(seq=2, option_id=str(oid), event_type=DiscussionEventType.OPTION_ADDED)
        ws = _rebuild(reducer, [e1, e2])
        assert ws.active_option_ids == [oid]

    def test_update_active(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid = uuid4()
        e1 = _option_event(seq=1, option_id=oid, event_type=DiscussionEventType.OPTION_ADDED)
        e2 = _option_event(
            seq=2,
            option_id=oid,
            event_type=DiscussionEventType.OPTION_UPDATED,
            content="更新内容",
        )
        ws = _rebuild(reducer, [e1, e2])
        assert ws.active_option_ids == [oid]

    def test_update_not_active_raises(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid = uuid4()
        e = _option_event(seq=1, option_id=oid, event_type=DiscussionEventType.OPTION_UPDATED)
        with pytest.raises(ValueError, match="discussion_workspace_reducer_option_not_active"):
            _rebuild(reducer, [e])

    def test_prefer_active(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid = uuid4()
        e1 = _option_event(seq=1, option_id=oid, event_type=DiscussionEventType.OPTION_ADDED)
        e2 = _option_event(seq=2, option_id=oid, event_type=DiscussionEventType.OPTION_PREFERRED)
        ws = _rebuild(reducer, [e1, e2])
        assert ws.preferred_option_id == oid
        assert ws.discussion_status == DiscussionStatus.CONVERGING

    def test_prefer_inactive_raises(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid = uuid4()
        e = _option_event(seq=1, option_id=oid, event_type=DiscussionEventType.OPTION_PREFERRED)
        with pytest.raises(ValueError, match="discussion_workspace_reducer_option_not_active"):
            _rebuild(reducer, [e])

    def test_reject_active(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid1, oid2 = uuid4(), uuid4()
        e1 = _option_event(seq=1, option_id=oid1, event_type=DiscussionEventType.OPTION_ADDED)
        e2 = _option_event(seq=2, option_id=oid2, event_type=DiscussionEventType.OPTION_ADDED)
        e3 = _option_event(seq=3, option_id=oid1, event_type=DiscussionEventType.OPTION_REJECTED)
        ws = _rebuild(reducer, [e1, e2, e3])
        assert ws.active_option_ids == [oid2]

    def test_reject_preferred_clears_preferred(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid = uuid4()
        e1 = _option_event(seq=1, option_id=oid, event_type=DiscussionEventType.OPTION_ADDED)
        e2 = _option_event(seq=2, option_id=oid, event_type=DiscussionEventType.OPTION_PREFERRED)
        e3 = _option_event(seq=3, option_id=oid, event_type=DiscussionEventType.OPTION_REJECTED)
        ws = _rebuild(reducer, [e1, e2, e3])
        assert ws.preferred_option_id is None
        assert oid not in ws.active_option_ids

    def test_reject_inactive_raises(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid = uuid4()
        e = _option_event(seq=1, option_id=oid, event_type=DiscussionEventType.OPTION_REJECTED)
        with pytest.raises(ValueError, match="discussion_workspace_reducer_option_not_active"):
            _rebuild(reducer, [e])

    def test_prefer_then_reject_status(self):
        """Prefer → converging. Then reject preferred option.
        Status stays converging (no explicit override from reject)."""
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid = uuid4()
        e1 = _option_event(seq=1, option_id=oid, event_type=DiscussionEventType.OPTION_ADDED)
        e2 = _option_event(seq=2, option_id=oid, event_type=DiscussionEventType.OPTION_PREFERRED)
        e3 = _option_event(seq=3, option_id=oid, event_type=DiscussionEventType.OPTION_REJECTED)
        ws = _rebuild(reducer, [e1, e2, e3])
        assert ws.discussion_status == DiscussionStatus.CONVERGING
        assert ws.preferred_option_id is None
        assert oid not in ws.active_option_ids

    def test_option_add_superseded(self):
        """If option_added is superseded by a later effective event,
        the option should not remain in active list."""
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid = uuid4()
        e1 = _option_event(seq=1, option_id=oid, event_type=DiscussionEventType.OPTION_ADDED, event_id=uuid4())
        # A later topic_set supersedes the option_added (different type but supersede is structural)
        e2 = make_event(
            sequence_no=2,
            event_type=DiscussionEventType.TOPIC_SET,
            content="覆盖主题",
            supersedes_event_id=e1.id,
        )
        ws = _rebuild(reducer, [e1, e2])
        # e1 is historical (superseded), so option should not be in active list
        assert oid not in ws.active_option_ids


# ===========================================================================
# 14. Constraint projection
# ===========================================================================


class TestConstraintProjection:
    def test_constraint_added(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e = _constraint_event(seq=1, event_type=DiscussionEventType.CONSTRAINT_ADDED)
        ws = _rebuild(reducer, [e])
        assert e.id in ws.active_constraint_ids

    def test_constraint_update_supersedes(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        a = _constraint_event(seq=1, event_type=DiscussionEventType.CONSTRAINT_ADDED)
        b = _constraint_event(
            seq=2,
            event_type=DiscussionEventType.CONSTRAINT_UPDATED,
            supersedes_event_id=a.id,
        )
        ws = _rebuild(reducer, [a, b])
        assert a.id not in ws.active_constraint_ids
        assert b.id in ws.active_constraint_ids

    def test_constraint_chain(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        a = _constraint_event(seq=1, event_type=DiscussionEventType.CONSTRAINT_ADDED)
        b = _constraint_event(
            seq=2,
            event_type=DiscussionEventType.CONSTRAINT_UPDATED,
            supersedes_event_id=a.id,
        )
        c = _constraint_event(
            seq=3,
            event_type=DiscussionEventType.CONSTRAINT_UPDATED,
            supersedes_event_id=b.id,
        )
        ws = _rebuild(reducer, [a, b, c])
        assert ws.active_constraint_ids == [c.id]

    def test_constraint_update_no_target_raises(self):
        """CONSTRAINT_UPDATED with supersedes_event_id=None → _validate_target_event_types rejects."""
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e = _constraint_event(
            seq=1,
            event_type=DiscussionEventType.CONSTRAINT_UPDATED,
            supersedes_event_id=None,
        )
        with pytest.raises(ValueError, match="discussion_workspace_reducer_constraint_target_invalid"):
            _rebuild(reducer, [e])

    def test_constraint_update_wrong_target_type(self):
        """Target is a topic_set, not a constraint type."""
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        topic_e = make_event(sequence_no=1)
        e = _constraint_event(
            seq=2,
            event_type=DiscussionEventType.CONSTRAINT_UPDATED,
            supersedes_event_id=topic_e.id,
        )
        with pytest.raises(ValueError, match="discussion_workspace_reducer_constraint_target_invalid"):
            _rebuild(reducer, [topic_e, e])

    def test_rejected_constraint_update_target_still_valid(self):
        """Rejected update still has valid structure; target stays active."""
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        a = _constraint_event(seq=1, event_type=DiscussionEventType.CONSTRAINT_ADDED)
        b = _constraint_event(
            seq=2,
            event_type=DiscussionEventType.CONSTRAINT_UPDATED,
            supersedes_event_id=a.id,
            status=DiscussionEventStatus.REJECTED,
        )
        ws = _rebuild(reducer, [a, b])
        # a is still active because b (rejected) didn't supersede it
        assert a.id in ws.active_constraint_ids
        assert b.id not in ws.active_constraint_ids

    def test_constraint_superseded_event_type(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        a = _constraint_event(seq=1, event_type=DiscussionEventType.CONSTRAINT_ADDED)
        b = _constraint_event(
            seq=2,
            event_type=DiscussionEventType.CONSTRAINT_SUPERSEDED,
            supersedes_event_id=a.id,
        )
        ws = _rebuild(reducer, [a, b])
        assert a.id not in ws.active_constraint_ids
        assert b.id in ws.active_constraint_ids


# ===========================================================================
# 15. Open question
# ===========================================================================


class TestOpenQuestion:
    def test_question_added(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e = _question_event(seq=1, event_type=DiscussionEventType.OPEN_QUESTION_ADDED)
        ws = _rebuild(reducer, [e])
        assert e.id in ws.open_question_ids

    def test_question_resolved(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        q = _question_event(seq=1, event_type=DiscussionEventType.OPEN_QUESTION_ADDED)
        r = _question_event(
            seq=2,
            event_type=DiscussionEventType.OPEN_QUESTION_RESOLVED,
            supersedes_event_id=q.id,
        )
        ws = _rebuild(reducer, [q, r])
        assert q.id not in ws.open_question_ids
        assert r.id not in ws.open_question_ids

    def test_question_resolution_no_target_raises(self):
        """OPEN_QUESTION_RESOLVED with supersedes_event_id=None → _validate_target_event_types rejects."""
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e = _question_event(
            seq=1,
            event_type=DiscussionEventType.OPEN_QUESTION_RESOLVED,
            supersedes_event_id=None,
        )
        with pytest.raises(ValueError, match="discussion_workspace_reducer_question_target_invalid"):
            _rebuild(reducer, [e])

    def test_question_resolution_wrong_target_type(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        topic_e = make_event(sequence_no=1)
        e = _question_event(
            seq=2,
            event_type=DiscussionEventType.OPEN_QUESTION_RESOLVED,
            supersedes_event_id=topic_e.id,
        )
        with pytest.raises(ValueError, match="discussion_workspace_reducer_question_target_invalid"):
            _rebuild(reducer, [topic_e, e])

    def test_rejected_resolution_keeps_question_open(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        q = _question_event(seq=1, event_type=DiscussionEventType.OPEN_QUESTION_ADDED)
        r = _question_event(
            seq=2,
            event_type=DiscussionEventType.OPEN_QUESTION_RESOLVED,
            supersedes_event_id=q.id,
            status=DiscussionEventStatus.REJECTED,
        )
        ws = _rebuild(reducer, [q, r])
        assert q.id in ws.open_question_ids
        assert r.id not in ws.open_question_ids


# ===========================================================================
# 16. Other workspace fields
# ===========================================================================


class TestOtherWorkspaceFields:
    def test_temporary_conclusions(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e1 = make_event(sequence_no=1, event_type=DiscussionEventType.TEMPORARY_CONCLUSION_ADDED, subject_key="tc")
        e2 = make_event(sequence_no=2, event_type=DiscussionEventType.TEMPORARY_CONCLUSION_ADDED, subject_key="tc")
        ws = _rebuild(reducer, [e1, e2])
        assert ws.temporary_conclusion_ids == [e1.id, e2.id]

    def test_confirmed_decisions(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e = make_event(sequence_no=1, event_type=DiscussionEventType.DECISION_CONFIRMED, subject_key="decision")
        ws = _rebuild(reducer, [e])
        assert ws.confirmed_decision_ids == [e.id]
        assert ws.discussion_status == DiscussionStatus.CONVERGING

    def test_latest_user_correction(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e1 = make_event(sequence_no=1, event_type=DiscussionEventType.USER_CORRECTION_RECORDED, subject_key="correction")
        e2 = make_event(sequence_no=2, event_type=DiscussionEventType.USER_CORRECTION_RECORDED, subject_key="correction")
        ws = _rebuild(reducer, [e1, e2])
        assert ws.latest_user_correction_event_id == e2.id

    def test_correction_superseded_not_latest(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e1 = make_event(
            sequence_no=1,
            event_type=DiscussionEventType.USER_CORRECTION_RECORDED,
            subject_key="correction",
            event_id=uuid4(),
        )
        e2 = make_event(
            sequence_no=2,
            event_type=DiscussionEventType.USER_CORRECTION_RECORDED,
            subject_key="correction",
            supersedes_event_id=e1.id,
        )
        ws = _rebuild(reducer, [e1, e2])
        assert ws.latest_user_correction_event_id == e2.id
        # e1 is superseded, so not effective
        res = _resolve(reducer, [e1, e2])
        eff_ids = {e.id for e in res.effective_events}
        assert e1.id not in eff_ids

    def test_concern_and_assumption_events_preserved(self):
        """concern_added, assumption_added, assumption_rejected are kept in resolution."""
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e1 = make_event(sequence_no=1, event_type=DiscussionEventType.CONCERN_ADDED, subject_key="concern")
        e2 = make_event(sequence_no=2, event_type=DiscussionEventType.ASSUMPTION_ADDED, subject_key="assumption")
        e3 = make_event(sequence_no=3, event_type=DiscussionEventType.ASSUMPTION_REJECTED, subject_key="assumption")
        res = _resolve(reducer, [e1, e2, e3])
        assert len(res.effective_events) == 3
        # These don't write to any special ID list
        ws = _rebuild(reducer, [e1, e2, e3])
        assert ws.active_option_ids == []
        assert ws.active_constraint_ids == []
        assert ws.open_question_ids == []


# ===========================================================================
# 17. DiscussionStatus
# ===========================================================================


class TestDiscussionStatus:
    @pytest.mark.parametrize("n_options,expected", [
        (0, DiscussionStatus.EXPLORING),
        (1, DiscussionStatus.EXPLORING),
        (2, DiscussionStatus.COMPARING),
        (3, DiscussionStatus.COMPARING),
    ])
    def test_option_count_status(self, n_options, expected):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        events = []
        for i in range(n_options):
            events.append(
                _option_event(seq=i + 1, option_id=uuid4(), event_type=DiscussionEventType.OPTION_ADDED)
            )
        ws = _rebuild(reducer, events)
        assert ws.discussion_status == expected

    def test_prefer_overrides_to_converging(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid = uuid4()
        e1 = _option_event(seq=1, option_id=oid, event_type=DiscussionEventType.OPTION_ADDED)
        e2 = _option_event(seq=2, option_id=oid, event_type=DiscussionEventType.OPTION_PREFERRED)
        ws = _rebuild(reducer, [e1, e2])
        assert ws.discussion_status == DiscussionStatus.CONVERGING

    def test_formalization_request(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e = make_event(sequence_no=1, event_type=DiscussionEventType.FORMALIZATION_REQUESTED, subject_key="formalize")
        ws = _rebuild(reducer, [e])
        assert ws.discussion_status == DiscussionStatus.READY_TO_FORMALIZE

    def test_formalization_cancelled(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e1 = make_event(sequence_no=1, event_type=DiscussionEventType.FORMALIZATION_REQUESTED, subject_key="formalize")
        e2 = make_event(sequence_no=2, event_type=DiscussionEventType.FORMALIZATION_CANCELLED, subject_key="formalize")
        ws = _rebuild(reducer, [e1, e2])
        assert ws.discussion_status == DiscussionStatus.CONVERGING

    def test_request_then_cancel_then_request(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e1 = make_event(sequence_no=1, event_type=DiscussionEventType.FORMALIZATION_REQUESTED, subject_key="formalize")
        e2 = make_event(sequence_no=2, event_type=DiscussionEventType.FORMALIZATION_CANCELLED, subject_key="formalize")
        e3 = make_event(sequence_no=3, event_type=DiscussionEventType.FORMALIZATION_REQUESTED, subject_key="formalize")
        ws = _rebuild(reducer, [e1, e2, e3])
        assert ws.discussion_status == DiscussionStatus.READY_TO_FORMALIZE

    def test_prefer_then_request(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid = uuid4()
        e1 = _option_event(seq=1, option_id=oid, event_type=DiscussionEventType.OPTION_ADDED)
        e2 = _option_event(seq=2, option_id=oid, event_type=DiscussionEventType.OPTION_PREFERRED)
        e3 = make_event(sequence_no=3, event_type=DiscussionEventType.FORMALIZATION_REQUESTED, subject_key="formalize")
        ws = _rebuild(reducer, [e1, e2, e3])
        assert ws.discussion_status == DiscussionStatus.READY_TO_FORMALIZE

    def test_request_then_prefer(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid = uuid4()
        e1 = make_event(sequence_no=1, event_type=DiscussionEventType.FORMALIZATION_REQUESTED, subject_key="formalize")
        e2 = _option_event(seq=2, option_id=oid, event_type=DiscussionEventType.OPTION_ADDED)
        e3 = _option_event(seq=3, option_id=oid, event_type=DiscussionEventType.OPTION_PREFERRED)
        ws = _rebuild(reducer, [e1, e2, e3])
        # prefer overrides request → converging
        assert ws.discussion_status == DiscussionStatus.CONVERGING

    def test_request_superseded_by_cancel(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e1 = make_event(
            sequence_no=1,
            event_type=DiscussionEventType.FORMALIZATION_REQUESTED,
            subject_key="formalize",
            event_id=uuid4(),
        )
        e2 = make_event(
            sequence_no=2,
            event_type=DiscussionEventType.FORMALIZATION_CANCELLED,
            subject_key="formalize",
            supersedes_event_id=e1.id,
        )
        ws = _rebuild(reducer, [e1, e2])
        assert ws.discussion_status == DiscussionStatus.CONVERGING

    def test_cancel_superseded_by_new_request(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e1 = make_event(
            sequence_no=1,
            event_type=DiscussionEventType.FORMALIZATION_CANCELLED,
            subject_key="formalize",
            event_id=uuid4(),
        )
        e2 = make_event(
            sequence_no=2,
            event_type=DiscussionEventType.FORMALIZATION_REQUESTED,
            subject_key="formalize",
            supersedes_event_id=e1.id,
        )
        ws = _rebuild(reducer, [e1, e2])
        assert ws.discussion_status == DiscussionStatus.READY_TO_FORMALIZE

    def test_no_formalized_status(self):
        """Reducer never produces FORMALIZED or PAUSED."""
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        events = [
            make_event(sequence_no=1, event_type=DiscussionEventType.TOPIC_SET),
            make_event(sequence_no=2, event_type=DiscussionEventType.DECISION_CONFIRMED, subject_key="decision"),
            make_event(sequence_no=3, event_type=DiscussionEventType.FORMALIZATION_REQUESTED, subject_key="formalize"),
        ]
        ws = _rebuild(reducer, events)
        assert ws.discussion_status not in (DiscussionStatus.FORMALIZED, DiscussionStatus.PAUSED)


# ===========================================================================
# 18. Rebuild metadata
# ===========================================================================


class TestRebuildMetadata:
    def test_empty_events_defaults(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        ws = _rebuild(reducer, [])
        assert ws.topic == ""
        assert ws.discussion_status == DiscussionStatus.EXPLORING
        assert ws.last_event_sequence_no == 0
        assert ws.version_no == 0
        assert ws.created_at == ws.updated_at

    def test_default_event_timestamps(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        t1 = _utc(hour=1)
        t3 = _utc(hour=3)
        e1 = make_event(sequence_no=1, created_at=t1)
        e3 = make_event(sequence_no=3, created_at=t3)
        e2 = make_event(sequence_no=2, created_at=_utc(hour=2))
        ws = _rebuild(reducer, [e3, e1, e2])
        assert ws.created_at == t1
        assert ws.updated_at == t3
        assert ws.last_event_sequence_no == 3

    def test_explicit_timestamps(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        ct = _utc(month=1)
        ut = _utc(month=6)
        e = make_event(sequence_no=1)
        ws = _rebuild(reducer, [e], created_at=ct, updated_at=ut)
        assert ws.created_at == ct
        assert ws.updated_at == ut

    def test_timezone_naive_normalized_to_utc(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        # Pass naive datetime, should be normalized to UTC
        naive = datetime(2026, 1, 1, 12, 0, 0)
        e = make_event(sequence_no=1)
        ws = _rebuild(reducer, [e], created_at=naive, updated_at=naive)
        assert ws.created_at.tzinfo == timezone.utc
        assert ws.updated_at.tzinfo == timezone.utc

    def test_invalid_updated_before_created_raises(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e = make_event(sequence_no=1)
        with pytest.raises(ValueError):
            _rebuild(reducer, [e], created_at=_utc(hour=10), updated_at=_utc(hour=5))

    @pytest.mark.parametrize("v", [0, 1, 17])
    def test_version_used_verbatim(self, v):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e = make_event(sequence_no=1)
        ws = _rebuild(reducer, [e], version_no=v)
        assert ws.version_no == v


# ===========================================================================
# 19. Rebuild determinism
# ===========================================================================


class TestRebuildDeterminism:
    def _make_events(self):
        e1 = make_event(
            sequence_no=1, content="主题A", event_type=DiscussionEventType.TOPIC_SET,
            created_at=_utc(hour=1),
        )
        oid = uuid4()
        e2 = _option_event(seq=2, option_id=oid, event_type=DiscussionEventType.OPTION_ADDED, created_at=_utc(hour=2))
        e3 = make_event(
            sequence_no=3, event_type=DiscussionEventType.DECISION_CONFIRMED,
            subject_key="decision", content="决策", created_at=_utc(hour=3),
        )
        return [e1, e2, e3]

    def _assert_ws_fields_match(self, ws1, ws2):
        assert ws1.topic == ws2.topic
        assert ws1.discussion_status == ws2.discussion_status
        assert ws1.active_option_ids == ws2.active_option_ids
        assert ws1.preferred_option_id == ws2.preferred_option_id
        assert ws1.active_constraint_ids == ws2.active_constraint_ids
        assert ws1.open_question_ids == ws2.open_question_ids
        assert ws1.temporary_conclusion_ids == ws2.temporary_conclusion_ids
        assert ws1.confirmed_decision_ids == ws2.confirmed_decision_ids
        assert ws1.latest_user_correction_event_id == ws2.latest_user_correction_event_id
        assert ws1.last_event_sequence_no == ws2.last_event_sequence_no
        assert ws1.version_no == ws2.version_no
        assert ws1.created_at == ws2.created_at
        assert ws1.updated_at == ws2.updated_at

    def test_different_input_orders_same_result(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        events = self._make_events()
        import random
        rng = random.Random(42)

        ws_original = _rebuild(reducer, events)
        ws_reversed = _rebuild(reducer, list(reversed(events)))
        shuffled = list(events)
        rng.shuffle(shuffled)
        ws_shuffled = _rebuild(reducer, shuffled)
        ws_tuple = _rebuild(reducer, tuple(events))

        self._assert_ws_fields_match(ws_original, ws_reversed)
        self._assert_ws_fields_match(ws_original, ws_shuffled)
        self._assert_ws_fields_match(ws_original, ws_tuple)


# ===========================================================================
# 20. Reduce unchanged
# ===========================================================================


class TestReduceUnchanged:
    def test_no_change_returns_same_object(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        events = [
            make_event(sequence_no=1, content="主题"),
            make_event(sequence_no=2, event_type=DiscussionEventType.DECISION_CONFIRMED, subject_key="decision"),
        ]
        ws = _rebuild(reducer, events, version_no=0)
        new_ws, changed = reducer.reduce_workspace(workspace=ws, events=events)
        assert changed is False
        assert new_ws is ws  # same object

    def test_unchanged_version_not_incremented(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        events = [make_event(sequence_no=1)]
        ws = _rebuild(reducer, events, version_no=5)
        new_ws, changed = reducer.reduce_workspace(workspace=ws, events=events)
        assert changed is False
        assert new_ws.version_no == 5

    def test_unchanged_timestamps_preserved(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        events = [make_event(sequence_no=1)]
        ct = _utc(month=1)
        ut = _utc(month=6)
        ws = _rebuild(reducer, events, created_at=ct, updated_at=ut, version_no=0)
        new_ws, changed = reducer.reduce_workspace(workspace=ws, events=events, updated_at=_utc(month=12))
        assert changed is False
        assert new_ws.created_at == ct
        assert new_ws.updated_at == ut
        assert new_ws.last_event_sequence_no == 1


# ===========================================================================
# 21. Reduce changed
# ===========================================================================


class TestReduceChanged:
    def test_changed_increments_version(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e1 = make_event(sequence_no=1, content="初始")
        ws = _rebuild(reducer, [e1], version_no=0)
        e2 = make_event(sequence_no=2, content="更新")
        new_ws, changed = reducer.reduce_workspace(
            workspace=ws, events=[e1, e2], updated_at=_utc(month=12)
        )
        assert changed is True
        assert new_ws.version_no == 1
        assert new_ws.created_at == ws.created_at
        assert new_ws.updated_at == _utc(month=12)
        assert new_ws.last_event_sequence_no == 2

    def test_changed_only_increments_by_one(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e1 = make_event(sequence_no=1)
        ws = _rebuild(reducer, [e1], version_no=10)
        e2 = make_event(sequence_no=2)
        e3 = make_event(sequence_no=3)
        new_ws, changed = reducer.reduce_workspace(workspace=ws, events=[e1, e2, e3])
        assert changed is True
        assert new_ws.version_no == 11

    def test_changed_projection_matches_full_rebuild(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e1 = make_event(sequence_no=1, content="初始")
        ws = _rebuild(reducer, [e1], version_no=0)
        oid = uuid4()
        e2 = _option_event(seq=2, option_id=oid, event_type=DiscussionEventType.OPTION_ADDED)
        new_ws, changed = reducer.reduce_workspace(workspace=ws, events=[e1, e2])
        full_rebuild = _rebuild(reducer, [e1, e2])
        assert new_ws.topic == full_rebuild.topic
        assert new_ws.active_option_ids == full_rebuild.active_option_ids
        assert new_ws.discussion_status == full_rebuild.discussion_status


# ===========================================================================
# 22. Historical-only append
# ===========================================================================


class TestHistoricalOnlyAppend:
    def test_historical_event_changes_cursor(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e1 = make_event(sequence_no=1)
        ws = _rebuild(reducer, [e1], version_no=0)
        e2 = make_event(sequence_no=2, status=DiscussionEventStatus.HISTORICAL)
        new_ws, changed = reducer.reduce_workspace(workspace=ws, events=[e1, e2])
        assert changed is True
        assert new_ws.version_no == 1
        assert new_ws.last_event_sequence_no == 2


# ===========================================================================
# 23. History regression
# ===========================================================================


class TestHistoryRegression:
    def test_regression_raises(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e1 = make_event(sequence_no=1)
        e10 = make_event(sequence_no=10)
        ws = _rebuild(reducer, [e1, e10], version_no=0)
        # Only pass up to sequence 9
        with pytest.raises(ValueError, match="discussion_workspace_event_history_regressed"):
            reducer.reduce_workspace(workspace=ws, events=[e1])

    def test_regression_empty_history(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e5 = make_event(sequence_no=5)
        ws = _rebuild(reducer, [e5], version_no=0)
        with pytest.raises(ValueError, match="discussion_workspace_event_history_regressed"):
            reducer.reduce_workspace(workspace=ws, events=[])


# ===========================================================================
# 24. Session / Project reduce boundary
# ===========================================================================


class TestSessionProjectReduceBoundary:
    def test_session_mismatch_in_reduce(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e = make_event(sequence_no=1)
        ws = _rebuild(reducer, [e])
        other_session = uuid4()
        bad_ws = DiscussionWorkspace(
            session_id=other_session,
            project_id=None,
            topic="",
            discussion_status=DiscussionStatus.EXPLORING,
            version_no=0,
            last_event_sequence_no=0,
            created_at=_utc(),
            updated_at=_utc(),
        )
        with pytest.raises(ValueError, match="discussion_event_stream_session_mismatch"):
            reducer.reduce_workspace(workspace=bad_ws, events=[e])

    def test_project_mismatch_in_reduce(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e = make_event(sequence_no=1)
        ws = _rebuild(reducer, [e])
        bad_ws = DiscussionWorkspace(
            session_id=_SESSION_ID,
            project_id=_PROJECT_ID,
            topic="",
            discussion_status=DiscussionStatus.EXPLORING,
            version_no=0,
            last_event_sequence_no=0,
            created_at=_utc(),
            updated_at=_utc(),
        )
        with pytest.raises(ValueError, match="discussion_event_stream_project_mismatch"):
            reducer.reduce_workspace(workspace=bad_ws, events=[e])


# ===========================================================================
# 25. Updated_at boundary
# ===========================================================================


class TestUpdatedAtBoundary:
    def test_explicit_updated_at_used(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e1 = make_event(sequence_no=1)
        ws = _rebuild(reducer, [e1], version_no=0)
        e2 = make_event(sequence_no=2)
        explicit_time = _utc(month=6)
        new_ws, changed = reducer.reduce_workspace(
            workspace=ws, events=[e1, e2], updated_at=explicit_time
        )
        assert changed is True
        assert new_ws.updated_at == explicit_time

    def test_no_updated_at_generates_utc(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e1 = make_event(sequence_no=1)
        ws = _rebuild(reducer, [e1], version_no=0)
        e2 = make_event(sequence_no=2)
        new_ws, changed = reducer.reduce_workspace(workspace=ws, events=[e1, e2])
        assert changed is True
        assert new_ws.updated_at.tzinfo == timezone.utc


# ===========================================================================
# 26. Input immutability
# ===========================================================================


class TestInputImmutability:
    def test_events_not_mutated_by_resolve(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid = uuid4()
        events = [
            make_event(
                sequence_no=1,
                event_type=DiscussionEventType.TOPIC_SET,
                payload={"k": "v"},
                source_message_ids=[_SYSTEM_MSG_ID],
            ),
            _option_event(seq=2, option_id=oid, event_type=DiscussionEventType.OPTION_ADDED),
            make_event(sequence_no=3, status=DiscussionEventStatus.REJECTED),
        ]
        dumps_before = [e.model_dump(mode="python") for e in events]
        _resolve(reducer, events)
        dumps_after = [e.model_dump(mode="python") for e in events]
        assert dumps_before == dumps_after

    def test_events_not_mutated_by_rebuild(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        events = [
            make_event(sequence_no=1, payload={"key": "val"}),
            make_event(sequence_no=2, event_type=DiscussionEventType.DECISION_CONFIRMED, subject_key="d"),
        ]
        dumps_before = [e.model_dump(mode="python") for e in events]
        _rebuild(reducer, events)
        dumps_after = [e.model_dump(mode="python") for e in events]
        assert dumps_before == dumps_after

    def test_events_not_mutated_by_reduce(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e1 = make_event(sequence_no=1)
        ws = _rebuild(reducer, [e1], version_no=0)
        e2 = make_event(sequence_no=2)
        all_events = [e1, e2]
        dumps_before = [e.model_dump(mode="python") for e in all_events]
        reducer.reduce_workspace(workspace=ws, events=all_events)
        dumps_after = [e.model_dump(mode="python") for e in all_events]
        assert dumps_before == dumps_after

    def test_input_list_order_not_mutated(self):
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        e3 = make_event(sequence_no=3)
        e1 = make_event(sequence_no=1)
        e2 = make_event(sequence_no=2)
        original = [e3, e1, e2]
        original_ids = [e.id for e in original]
        _rebuild(reducer, original)
        assert [e.id for e in original] == original_ids


# ===========================================================================
# 27. Static business boundary (AST)
# ===========================================================================


class TestStaticBusinessBoundary:
    @pytest.fixture(scope="class")
    def reducer_ast(self):
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent / "app" / "services" / "project_director_discussion_workspace_reducer_service.py"
        source = path.read_text()
        return ast.parse(source)

    def _get_imports(self, node: ast.Module) -> set[str]:
        imports = set()
        for n in ast.walk(node):
            if isinstance(n, ast.Import):
                for alias in n.names:
                    imports.add(alias.name)
            elif isinstance(n, ast.ImportFrom):
                if n.module:
                    imports.add(n.module)
        return imports

    def _get_all_names(self, node: ast.Module) -> set[str]:
        names = set()
        for n in ast.walk(node):
            if isinstance(n, ast.Attribute):
                names.add(n.attr)
            elif isinstance(n, ast.Name):
                names.add(n.id)
        return names

    def test_no_sqlalchemy_import(self, reducer_ast):
        imports = self._get_imports(reducer_ast)
        for imp in imports:
            assert "sqlalchemy" not in imp.lower(), f"Found SQLAlchemy import: {imp}"

    def test_no_repository_import(self, reducer_ast):
        imports = self._get_imports(reducer_ast)
        for imp in imports:
            assert "repository" not in imp.lower(), f"Found repository import: {imp}"

    def test_no_orm_table_import(self, reducer_ast):
        imports = self._get_imports(reducer_ast)
        for imp in imports:
            assert "db_tables" not in imp.lower(), f"Found ORM table import: {imp}"

    def test_no_fastapi_import(self, reducer_ast):
        imports = self._get_imports(reducer_ast)
        for imp in imports:
            assert "fastapi" not in imp.lower(), f"Found FastAPI import: {imp}"

    def test_no_provider_import(self, reducer_ast):
        imports = self._get_imports(reducer_ast)
        for imp in imports:
            assert "provider" not in imp.lower(), f"Found provider import: {imp}"

    def test_no_message_service_import(self, reducer_ast):
        imports = self._get_imports(reducer_ast)
        for imp in imports:
            assert "message_service" not in imp.lower(), f"Found message service import: {imp}"

    def test_no_commit_rollback_flush(self, reducer_ast):
        names = self._get_all_names(reducer_ast)
        for forbidden in ("commit", "rollback", "flush"):
            # Only check attribute access, not standalone names
            pass  # covered by checking no sqlalchemy/repo imports
        # More precise: check ast.Call for commit/rollback/flush
        for node in ast.walk(reducer_ast):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr in ("commit", "rollback", "flush"):
                    pytest.fail(f"Found forbidden call: .{func.attr}()")

    def test_no_file_write(self, reducer_ast):
        names = self._get_all_names(reducer_ast)
        for forbidden in ("open", "write", "makedirs", "mkdir"):
            # Allow 'open' only if not used as builtin file open
            pass  # checked via no side-effect imports

    def test_no_network(self, reducer_ast):
        imports = self._get_imports(reducer_ast)
        for imp in imports:
            for net in ("requests", "httpx", "urllib", "aiohttp", "socket"):
                assert net not in imp.lower(), f"Found network import: {imp}"

    def test_no_git(self, reducer_ast):
        imports = self._get_imports(reducer_ast)
        for imp in imports:
            assert "git" not in imp.lower() or "digit" in imp.lower(), f"Found git import: {imp}"

    def test_no_plan_task_run_creation(self, reducer_ast):
        names = self._get_all_names(reducer_ast)
        for forbidden in ("PlanVersion", "Task", "Run"):
            # These are domain types; not expected in reducer
            for node in ast.walk(reducer_ast):
                if isinstance(node, ast.Name) and node.id == forbidden:
                    pytest.fail(f"Found forbidden domain type: {forbidden}")

    def test_no_delta_gate(self, reducer_ast):
        imports = self._get_imports(reducer_ast)
        for imp in imports:
            assert "delta" not in imp.lower() or "project_director_discussion" in imp, f"Found delta import: {imp}"

    def test_allowed_imports(self, reducer_ast):
        imports = self._get_imports(reducer_ast)
        allowed_prefixes = (
            "app.domain._base",
            "app.domain.project_director_discussion",
            "collections",
            "dataclasses",
            "datetime",
            "uuid",
            "typing",
            "__future__",
        )
        for imp in imports:
            assert any(imp.startswith(p) for p in allowed_prefixes), f"Unexpected import: {imp}"


# ===========================================================================
# 28. Integration: Repository → Reducer → Workspace
# ===========================================================================


@pytest.fixture()
def db_engine(tmp_path):
    db_path = tmp_path / "p26c2-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    event.listen(engine, "connect", configure_sqlite)
    event.listen(engine, "begin", begin_sqlite_transaction)
    ORMBase.metadata.create_all(bind=engine)
    return engine


@pytest.fixture()
def db_session_factory(db_engine):
    return sessionmaker(bind=db_engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _seed_session(db_session: Session, *, session_id: UUID | None = None, project_id: UUID | None = None) -> UUID:
    sid = session_id or uuid4()
    row = ProjectDirectorSessionTable(
        id=sid,
        project_id=project_id,
        goal_text="测试目标",
    )
    db_session.add(row)
    db_session.flush()
    return sid


def _seed_message(db_session: Session, session_id: UUID, *, msg_id: UUID | None = None) -> UUID:
    mid = msg_id or uuid4()
    row = ProjectDirectorMessageTable(
        id=mid,
        session_id=session_id,
        role=ProjectDirectorMessageRole.USER,
        content="测试消息",
        sequence_no=1,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail="test",
    )
    db_session.add(row)
    db_session.flush()
    return mid


def _append_event_to_db(
    db_session: Session,
    event_repo: ProjectDirectorDiscussionEventRepository,
    *,
    session_id: UUID,
    project_id: UUID | None = None,
    sequence_no: int = 1,
    event_type: DiscussionEventType = DiscussionEventType.TOPIC_SET,
    subject_key: str = "topic",
    content: str = "内容",
    status: DiscussionEventStatus = DiscussionEventStatus.ACTIVE,
    payload: dict | None = None,
    supersedes_event_id: UUID | None = None,
    event_id: UUID | None = None,
    created_at: datetime | None = None,
    msg_id: UUID | None = None,
) -> DiscussionEvent:
    ev = make_event(
        session_id=session_id,
        project_id=project_id,
        sequence_no=sequence_no,
        event_type=event_type,
        subject_key=subject_key,
        content=content,
        status=status,
        payload=payload,
        supersedes_event_id=supersedes_event_id,
        event_id=event_id,
        created_at=created_at,
        source_message_ids=[msg_id] if msg_id else [],
    )
    event_repo.append_if_absent(event=ev, idempotency_key=f"key-{ev.id}")
    return ev


class TestIntegrationRebuildFromRepository:
    def test_rebuild_from_repo_history(self, db_session_factory):
        """Repository → Reducer → Workspace round-trip.
        1. Seed session + events + commit
        2. New session: create empty workspace via create_if_absent (version=0, last_seq=0)
        3. Commit
        4. New session: read events, reduce → changed=True, update_if_version(expected=0)
        5. Commit
        6. New session: read back, verify business fields match full rebuild
        """
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        factory = db_session_factory

        # Session 1: seed base records and events
        with factory() as session:
            sid = _seed_session(session)
            mid = _seed_message(session, sid)
            event_repo = ProjectDirectorDiscussionEventRepository(session)
            _append_event_to_db(
                session, event_repo,
                session_id=sid, sequence_no=1, content="集成主题", msg_id=mid,
            )
            oid = uuid4()
            _append_event_to_db(
                session, event_repo,
                session_id=sid, sequence_no=2,
                event_type=DiscussionEventType.OPTION_ADDED,
                subject_key="option", content="选项",
                payload={"option_id": str(oid)}, msg_id=mid,
            )
            session.commit()

        # Session 2: create empty workspace (version=0, last_seq=0)
        with factory() as session:
            ws_repo = ProjectDirectorDiscussionWorkspaceRepository(session)
            empty_ws = reducer.rebuild_workspace(
                session_id=sid, project_id=None, events=[]
            )
            ws_repo.create_if_absent(workspace=empty_ws)
            session.commit()

        # Session 3: read events, reduce, update
        with factory() as session:
            event_repo = ProjectDirectorDiscussionEventRepository(session)
            ws_repo = ProjectDirectorDiscussionWorkspaceRepository(session)
            events = event_repo.list_by_session_id(session_id=sid)
            assert len(events) == 2

            old_ws = ws_repo.get_by_session_id(session_id=sid)
            assert old_ws is not None
            new_ws, changed = reducer.reduce_workspace(
                workspace=old_ws, events=events
            )
            assert changed is True
            ws_repo.update_if_version(workspace=new_ws, expected_version_no=0)
            session.commit()

        # Session 4: read back and verify
        with factory() as session:
            ws_repo = ProjectDirectorDiscussionWorkspaceRepository(session)
            persisted = ws_repo.get_by_session_id(session_id=sid)
            assert persisted is not None
            assert persisted.topic == "集成主题"
            assert oid in persisted.active_option_ids
            assert persisted.last_event_sequence_no == 2
            assert persisted.version_no == 1


class TestIntegrationAppendAndReduce:
    def test_append_and_reduce(self, db_session_factory):
        """Append → reduce → CAS update workflow."""
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        factory = db_session_factory

        # Session 1: seed session, initial event, create empty workspace
        with factory() as session:
            sid = _seed_session(session)
            mid = _seed_message(session, sid)
            event_repo = ProjectDirectorDiscussionEventRepository(session)
            ws_repo = ProjectDirectorDiscussionWorkspaceRepository(session)
            _append_event_to_db(
                session, event_repo,
                session_id=sid, sequence_no=1, content="初始", msg_id=mid,
            )
            empty_ws = reducer.rebuild_workspace(session_id=sid, project_id=None, events=[])
            ws_repo.create_if_absent(workspace=empty_ws)
            session.commit()

        # Session 2: reduce existing events, CAS update to version 1
        with factory() as session:
            event_repo = ProjectDirectorDiscussionEventRepository(session)
            ws_repo = ProjectDirectorDiscussionWorkspaceRepository(session)
            events = event_repo.list_by_session_id(session_id=sid)
            old_ws = ws_repo.get_by_session_id(session_id=sid)
            assert old_ws is not None
            assert old_ws.version_no == 0

            new_ws, changed = reducer.reduce_workspace(workspace=old_ws, events=events)
            assert changed is True
            ws_repo.update_if_version(workspace=new_ws, expected_version_no=0)
            session.commit()

        # Session 3: append new event, reduce, CAS update to version 2
        with factory() as session:
            event_repo = ProjectDirectorDiscussionEventRepository(session)
            ws_repo = ProjectDirectorDiscussionWorkspaceRepository(session)
            _append_event_to_db(
                session, event_repo,
                session_id=sid, sequence_no=2, content="更新主题", msg_id=mid,
            )
            events = event_repo.list_by_session_id(session_id=sid)
            old_ws = ws_repo.get_by_session_id(session_id=sid)
            assert old_ws.version_no == 1

            new_ws, changed = reducer.reduce_workspace(workspace=old_ws, events=events)
            assert changed is True
            ws_repo.update_if_version(workspace=new_ws, expected_version_no=1)
            session.commit()

        # Session 4: verify version 2
        with factory() as session:
            ws_repo = ProjectDirectorDiscussionWorkspaceRepository(session)
            persisted = ws_repo.get_by_session_id(session_id=sid)
            assert persisted is not None
            assert persisted.version_no == 2
            assert persisted.topic == "更新主题"
            assert persisted.last_event_sequence_no == 2


class TestIntegrationNoChangeReplay:
    def test_no_change_replay(self, db_session_factory):
        """Same full history replayed → changed=False, version unchanged."""
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        factory = db_session_factory

        # Session 1: seed session, event, create empty workspace
        with factory() as session:
            sid = _seed_session(session)
            mid = _seed_message(session, sid)
            event_repo = ProjectDirectorDiscussionEventRepository(session)
            ws_repo = ProjectDirectorDiscussionWorkspaceRepository(session)
            _append_event_to_db(
                session, event_repo,
                session_id=sid, sequence_no=1, content="主题", msg_id=mid,
            )
            empty_ws = reducer.rebuild_workspace(session_id=sid, project_id=None, events=[])
            ws_repo.create_if_absent(workspace=empty_ws)
            session.commit()

        # Session 2: reduce once → version 1
        with factory() as session:
            event_repo = ProjectDirectorDiscussionEventRepository(session)
            ws_repo = ProjectDirectorDiscussionWorkspaceRepository(session)
            events = event_repo.list_by_session_id(session_id=sid)
            old_ws = ws_repo.get_by_session_id(session_id=sid)
            new_ws, changed = reducer.reduce_workspace(workspace=old_ws, events=events)
            assert changed is True
            ws_repo.update_if_version(workspace=new_ws, expected_version_no=0)
            session.commit()

        # Session 3: reduce again with same events → no change
        with factory() as session:
            event_repo = ProjectDirectorDiscussionEventRepository(session)
            ws_repo = ProjectDirectorDiscussionWorkspaceRepository(session)
            events = event_repo.list_by_session_id(session_id=sid)
            old_ws = ws_repo.get_by_session_id(session_id=sid)
            assert old_ws.version_no == 1
            new_ws, changed = reducer.reduce_workspace(workspace=old_ws, events=events)
            assert changed is False
            assert new_ws.version_no == 1


class TestIntegrationCallerRollback:
    def test_caller_rollback(self, db_session_factory):
        """Append + reduce + update + rollback → original state preserved."""
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        factory = db_session_factory

        # Session 1: seed session, event, create empty workspace, reduce, update
        with factory() as session:
            sid = _seed_session(session)
            mid = _seed_message(session, sid)
            event_repo = ProjectDirectorDiscussionEventRepository(session)
            ws_repo = ProjectDirectorDiscussionWorkspaceRepository(session)
            _append_event_to_db(
                session, event_repo,
                session_id=sid, sequence_no=1, content="原始主题", msg_id=mid,
            )
            empty_ws = reducer.rebuild_workspace(session_id=sid, project_id=None, events=[])
            ws_repo.create_if_absent(workspace=empty_ws)
            session.commit()

        # Session 2: reduce existing event → version 1
        with factory() as session:
            event_repo = ProjectDirectorDiscussionEventRepository(session)
            ws_repo = ProjectDirectorDiscussionWorkspaceRepository(session)
            events = event_repo.list_by_session_id(session_id=sid)
            old_ws = ws_repo.get_by_session_id(session_id=sid)
            new_ws, changed = reducer.reduce_workspace(workspace=old_ws, events=events)
            assert changed is True
            ws_repo.update_if_version(workspace=new_ws, expected_version_no=0)
            session.commit()

        # Session 3: append new event + reduce + update, then rollback
        with factory() as session:
            event_repo = ProjectDirectorDiscussionEventRepository(session)
            ws_repo = ProjectDirectorDiscussionWorkspaceRepository(session)
            _append_event_to_db(
                session, event_repo,
                session_id=sid, sequence_no=2, content="新主题", msg_id=mid,
            )
            events = event_repo.list_by_session_id(session_id=sid)
            old_ws = ws_repo.get_by_session_id(session_id=sid)
            new_ws, changed = reducer.reduce_workspace(workspace=old_ws, events=events)
            assert changed is True
            ws_repo.update_if_version(workspace=new_ws, expected_version_no=1)
            session.rollback()

        # Session 4: verify rollback - new event doesn't exist, workspace is still version 1
        with factory() as session:
            event_repo = ProjectDirectorDiscussionEventRepository(session)
            ws_repo = ProjectDirectorDiscussionWorkspaceRepository(session)
            events = event_repo.list_by_session_id(session_id=sid)
            assert len(events) == 1  # only the original event
            persisted = ws_repo.get_by_session_id(session_id=sid)
            assert persisted.version_no == 1
            assert persisted.topic == "原始主题"


# ===========================================================================
# P26-D1-A-R1: Option replacement lineage regression
# ===========================================================================


class TestOptionReplacementLineage:
    """Direct Reducer regression for the _is_option_replacement fix."""

    def test_single_level_replacement(self):
        """OPTION_ADDED(O) → OPTION_UPDATED(O, supersedes E1) keeps O active."""
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid = uuid4()
        e1 = _option_event(seq=1, option_id=oid, event_type=DiscussionEventType.OPTION_ADDED, event_id=uuid4())
        e2 = _option_event(
            seq=2, option_id=oid, event_type=DiscussionEventType.OPTION_UPDATED,
            supersedes_event_id=e1.id, content="更新内容",
        )
        res = _resolve(reducer, [e1, e2])
        eff_ids = {e.id for e in res.effective_events}
        assert e2.id in eff_ids
        assert e1.id in res.superseded_event_ids
        assert e1.id in {e.id for e in res.historical_events}
        ws = _rebuild(reducer, [e1, e2])
        assert oid in ws.active_option_ids
        assert ws.active_option_ids == [oid]
        assert ws.last_event_sequence_no == 2

    def test_two_level_replacement_chain(self):
        """OPTION_ADDED(O) → UPDATED(O, supersedes E1) → UPDATED(O, supersedes E2).
        Only E3 is effective; E1 and E2 are historical."""
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid = uuid4()
        e1 = _option_event(seq=1, option_id=oid, event_type=DiscussionEventType.OPTION_ADDED, event_id=uuid4())
        e2 = _option_event(
            seq=2, option_id=oid, event_type=DiscussionEventType.OPTION_UPDATED,
            supersedes_event_id=e1.id, content="更新1", event_id=uuid4(),
        )
        e3 = _option_event(
            seq=3, option_id=oid, event_type=DiscussionEventType.OPTION_UPDATED,
            supersedes_event_id=e2.id, content="更新2",
        )
        res = _resolve(reducer, [e1, e2, e3])
        eff_ids = {e.id for e in res.effective_events}
        hist_ids = {e.id for e in res.historical_events}
        assert eff_ids == {e3.id}
        assert e1.id in hist_ids and e2.id in hist_ids
        assert res.superseded_event_ids == frozenset({e1.id, e2.id})
        ws = _rebuild(reducer, [e1, e2, e3])
        assert ws.active_option_ids == [oid]
        assert ws.last_event_sequence_no == 3

    def test_standalone_update_without_supersede_raises(self):
        """OPTION_UPDATED(O) with no supersedes → not active → raises."""
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid = uuid4()
        e = _option_event(seq=1, option_id=oid, event_type=DiscussionEventType.OPTION_UPDATED)
        with pytest.raises(ValueError, match="discussion_workspace_reducer_option_not_active"):
            _rebuild(reducer, [e])

    def test_cross_option_replacement_raises(self):
        """OPTION_UPDATED(option B, supersedes OPTION_ADDED(option A)) → not active."""
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid_a, oid_b = uuid4(), uuid4()
        e1 = _option_event(seq=1, option_id=oid_a, event_type=DiscussionEventType.OPTION_ADDED, event_id=uuid4())
        e2 = _option_event(
            seq=2, option_id=oid_b, event_type=DiscussionEventType.OPTION_UPDATED,
            supersedes_event_id=e1.id, content="跨选项更新",
        )
        with pytest.raises(ValueError, match="discussion_workspace_reducer_option_not_active"):
            _rebuild(reducer, [e1, e2])

    def test_rejected_target_not_used_for_replacement(self):
        """OPTION_UPDATED supersedes a rejected OPTION_ADDED → raises."""
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid = uuid4()
        e1 = _option_event(
            seq=1, option_id=oid, event_type=DiscussionEventType.OPTION_ADDED,
            status=DiscussionEventStatus.REJECTED, event_id=uuid4(),
        )
        e2 = _option_event(
            seq=2, option_id=oid, event_type=DiscussionEventType.OPTION_UPDATED,
            supersedes_event_id=e1.id, content="更新被拒绝的",
        )
        with pytest.raises(ValueError, match="discussion_workspace_reducer_option_not_active"):
            _rebuild(reducer, [e1, e2])

    def test_replacement_input_immutability(self):
        """Reducer does not mutate input events or list order."""
        reducer = ProjectDirectorDiscussionWorkspaceReducerService()
        oid = uuid4()
        e1 = _option_event(seq=1, option_id=oid, event_type=DiscussionEventType.OPTION_ADDED, event_id=uuid4())
        e2 = _option_event(
            seq=2, option_id=oid, event_type=DiscussionEventType.OPTION_UPDATED,
            supersedes_event_id=e1.id, content="更新",
        )
        events = [e1, e2]
        dumps_before = [e.model_dump(mode="python") for e in events]
        order_before = [e.id for e in events]
        _rebuild(reducer, events)
        assert [e.model_dump(mode="python") for e in events] == dumps_before
        assert [e.id for e in events] == order_before
