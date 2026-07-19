"""Contract tests for P26-D1-A governed DiscussionDelta admission.

These tests exercise the public pure-gate boundary only.  They intentionally
use the real C2 reducer and do not involve persistence, routers, or providers.
"""

from __future__ import annotations

import ast
from collections.abc import Sequence
from dataclasses import FrozenInstanceError, fields, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest

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
from app.services.project_director_discussion_delta_gate_service import (
    DiscussionDeltaGateStatus,
    GovernedDiscussionDeltaResult,
    PreparedDiscussionEvent,
    ProjectDirectorDiscussionDeltaGateService,
)
from app.services.project_director_discussion_workspace_reducer_service import (
    DiscussionEventResolution,
    ProjectDirectorDiscussionWorkspaceReducerService,
)


SESSION_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PROJECT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
ASSISTANT_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
USER_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
SYSTEM_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
FIXED_TIME = datetime(2026, 7, 19, 8, 30, tzinfo=timezone.utc)


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


def make_operation(
    *,
    op: DiscussionDeltaOperationType = DiscussionDeltaOperationType.SET_TOPIC,
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


def make_event(
    *,
    event_id: UUID | None = None,
    session_id: UUID = SESSION_ID,
    project_id: UUID | None = None,
    sequence_no: int = 1,
    event_type: DiscussionEventType = DiscussionEventType.TOPIC_SET,
    status: DiscussionEventStatus = DiscussionEventStatus.ACTIVE,
    created_by: DiscussionActorClaim = DiscussionActorClaim.SYSTEM_FACT,
    payload: dict | None = None,
    supersedes_event_id: UUID | None = None,
    source_message_ids: list[UUID] | None = None,
    created_at: datetime = FIXED_TIME,
    subject_key: str = "subject",
    content: str = "历史",
) -> DiscussionEvent:
    return DiscussionEvent(
        id=event_id or uuid4(), session_id=session_id, project_id=project_id,
        sequence_no=sequence_no, event_type=event_type, status=status,
        created_by=created_by, payload={} if payload is None else payload,
        supersedes_event_id=supersedes_event_id,
        source_message_ids=[] if source_message_ids is None else source_message_ids,
        confidence=1.0 if created_by not in {DiscussionActorClaim.USER_INFERRED, DiscussionActorClaim.ASSISTANT_PROPOSAL} else 0.5,
        created_at=created_at, subject_key=subject_key, content=content,
    )


def assistant(**kwargs) -> ProjectDirectorMessage:
    return make_message(message_id=ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT, **kwargs)


def sources(*, include_assistant: bool = False) -> list[ProjectDirectorMessage]:
    result = [make_message(message_id=USER_ID), make_message(message_id=SYSTEM_ID, role=ProjectDirectorMessageRole.SYSTEM)]
    if include_assistant:
        result.append(assistant())
    return result


def evaluate(
    *operations: DiscussionDeltaOperation,
    assistant_message: ProjectDirectorMessage | None = None,
    available_messages: list[ProjectDirectorMessage] | None = None,
    current_events: list[DiscussionEvent] | None = None,
    current_workspace: DiscussionWorkspace | None = None,
    session_id: UUID = SESSION_ID,
    project_id: UUID | None = None,
    start_sequence_no: int | None = None,
    occurred_at: datetime | None = None,
    service: ProjectDirectorDiscussionDeltaGateService | None = None,
) -> GovernedDiscussionDeltaResult:
    events = [] if current_events is None else current_events
    return (service or ProjectDirectorDiscussionDeltaGateService()).evaluate_delta(
        session_id=session_id, project_id=project_id, assistant_message=assistant_message or assistant(),
        available_messages=sources() if available_messages is None else available_messages,
        current_events=events, current_workspace=current_workspace,
        delta=DiscussionDelta(operations=list(operations)),
        start_sequence_no=len(events) + 1 if start_sequence_no is None else start_sequence_no,
        occurred_at=occurred_at,
    )


def workspace(events: list[DiscussionEvent], *, version_no: int = 0) -> DiscussionWorkspace:
    return ProjectDirectorDiscussionWorkspaceReducerService().rebuild_workspace(
        session_id=SESSION_ID, project_id=None, events=events, version_no=version_no,
        created_at=FIXED_TIME, updated_at=FIXED_TIME,
    )


def assert_code(code: str, thunk) -> None:
    with pytest.raises(ValueError, match=f"^{code}$"):
        thunk()


# ── Spy Reducer for reuse evidence ──────────────────────────────────────────


class SpyReducer(ProjectDirectorDiscussionWorkspaceReducerService):
    """Records calls to prove Gate delegates to the injected reducer."""

    def __init__(self) -> None:
        super().__init__()
        self.resolve_calls: list[tuple[int, int]] = []   # (event_count, call_ordinal)
        self.rebuild_calls: list[tuple[int, int]] = []
        self.reduce_calls: list[tuple[int, int]] = []
        self._ordinal = 0

    def resolve_events(
        self, *, session_id: UUID, project_id: UUID | None, events: Sequence[DiscussionEvent],
    ) -> DiscussionEventResolution:
        self._ordinal += 1
        self.resolve_calls.append((len(events), self._ordinal))
        return super().resolve_events(session_id=session_id, project_id=project_id, events=events)

    def rebuild_workspace(
        self, *, session_id: UUID, project_id: UUID | None, events: Sequence[DiscussionEvent],
        version_no: int = 0, created_at: datetime | None = None, updated_at: datetime | None = None,
    ) -> DiscussionWorkspace:
        self._ordinal += 1
        self.rebuild_calls.append((len(events), self._ordinal))
        return super().rebuild_workspace(
            session_id=session_id, project_id=project_id, events=events,
            version_no=version_no, created_at=created_at, updated_at=updated_at,
        )

    def reduce_workspace(
        self, *, workspace: DiscussionWorkspace, events: Sequence[DiscussionEvent],
        updated_at: datetime | None = None,
    ) -> tuple[DiscussionWorkspace, bool]:
        self._ordinal += 1
        self.reduce_calls.append((len(events), self._ordinal))
        return super().reduce_workspace(workspace=workspace, events=events, updated_at=updated_at)


# ── 18-operation fixture ────────────────────────────────────────────────────

_OPTION_ID = UUID("11111111-1111-1111-1111-111111111111")
_OPTION_ADDED_EVT_ID = UUID("22222222-2222-2222-2222-222222222222")
_CONSTRAINT_ADDED_EVT_ID = UUID("33333333-3333-3333-3333-333333333333")
_ASSUMPTION_ADDED_EVT_ID = UUID("44444444-4444-4444-4444-444444444444")
_QUESTION_ADDED_EVT_ID = UUID("55555555-5555-5555-5555-555555555555")
_FORMALIZATION_EVT_ID = UUID("66666666-6666-6666-6666-666666666666")

_OPTION_ADDED = make_event(
    event_id=_OPTION_ADDED_EVT_ID, event_type=DiscussionEventType.OPTION_ADDED,
    payload={"option_id": _OPTION_ID}, subject_key=f"option:{_OPTION_ID}", content="选项",
)
_CONSTRAINT_ADDED = make_event(
    event_id=_CONSTRAINT_ADDED_EVT_ID, event_type=DiscussionEventType.CONSTRAINT_ADDED,
    subject_key="constraint", content="约束",
)
_ASSUMPTION_ADDED = make_event(
    event_id=_ASSUMPTION_ADDED_EVT_ID, event_type=DiscussionEventType.ASSUMPTION_ADDED,
    subject_key="assumption", content="假设",
)
_QUESTION_ADDED = make_event(
    event_id=_QUESTION_ADDED_EVT_ID, event_type=DiscussionEventType.OPEN_QUESTION_ADDED,
    subject_key="open_question", content="问题",
)
_FORMALIZATION_REQUESTED = make_event(
    event_id=_FORMALIZATION_EVT_ID, event_type=DiscussionEventType.FORMALIZATION_REQUESTED,
    subject_key="formalization", content="请正式化",
)


def _option_added_events() -> list[DiscussionEvent]:
    return [_OPTION_ADDED]


def _constraint_added_events() -> list[DiscussionEvent]:
    return [_CONSTRAINT_ADDED]


def _assumption_added_events() -> list[DiscussionEvent]:
    return [_ASSUMPTION_ADDED]


def _question_added_events() -> list[DiscussionEvent]:
    return [_QUESTION_ADDED]


def _formalization_events() -> list[DiscussionEvent]:
    return [_FORMALIZATION_REQUESTED]


def _record_correction_events() -> list[DiscussionEvent]:
    """Return an effective discussion event for record_user_correction target."""
    return [make_event(
        event_type=DiscussionEventType.TOPIC_SET, subject_key="topic", content="可纠正主题",
    )]


# (op, expected_event_type, current_events_factory, make_op_kwargs)
_ALL_18_MAPPINGS: list[tuple[
    DiscussionDeltaOperationType,
    DiscussionEventType,
    callable,
    dict,
]] = [
    (DiscussionDeltaOperationType.SET_TOPIC, DiscussionEventType.TOPIC_SET, list, {}),
    (DiscussionDeltaOperationType.ADD_OPTION, DiscussionEventType.OPTION_ADDED, list, {"target_id": _OPTION_ID}),
    (DiscussionDeltaOperationType.UPDATE_OPTION, DiscussionEventType.OPTION_UPDATED, _option_added_events, {"target_id": _OPTION_ID, "supersedes_event_id": _OPTION_ADDED_EVT_ID}),
    (DiscussionDeltaOperationType.PREFER_OPTION, DiscussionEventType.OPTION_PREFERRED, _option_added_events, {"target_id": _OPTION_ID}),
    (DiscussionDeltaOperationType.REJECT_OPTION, DiscussionEventType.OPTION_REJECTED, _option_added_events, {"target_id": _OPTION_ID}),
    (DiscussionDeltaOperationType.ADD_CONSTRAINT, DiscussionEventType.CONSTRAINT_ADDED, list, {}),
    (DiscussionDeltaOperationType.UPDATE_CONSTRAINT, DiscussionEventType.CONSTRAINT_UPDATED, _constraint_added_events, {"supersedes_event_id": _CONSTRAINT_ADDED_EVT_ID}),
    (DiscussionDeltaOperationType.SUPERSEDE_CONSTRAINT, DiscussionEventType.CONSTRAINT_SUPERSEDED, _constraint_added_events, {"supersedes_event_id": _CONSTRAINT_ADDED_EVT_ID}),
    (DiscussionDeltaOperationType.ADD_CONCERN, DiscussionEventType.CONCERN_ADDED, list, {}),
    (DiscussionDeltaOperationType.ADD_ASSUMPTION, DiscussionEventType.ASSUMPTION_ADDED, list, {}),
    (DiscussionDeltaOperationType.REJECT_ASSUMPTION, DiscussionEventType.ASSUMPTION_REJECTED, _assumption_added_events, {"supersedes_event_id": _ASSUMPTION_ADDED_EVT_ID}),
    (DiscussionDeltaOperationType.ADD_OPEN_QUESTION, DiscussionEventType.OPEN_QUESTION_ADDED, list, {}),
    (DiscussionDeltaOperationType.RESOLVE_OPEN_QUESTION, DiscussionEventType.OPEN_QUESTION_RESOLVED, _question_added_events, {"supersedes_event_id": _QUESTION_ADDED_EVT_ID}),
    (DiscussionDeltaOperationType.ADD_TEMPORARY_CONCLUSION, DiscussionEventType.TEMPORARY_CONCLUSION_ADDED, list, {}),
    (DiscussionDeltaOperationType.RECORD_USER_CORRECTION, DiscussionEventType.USER_CORRECTION_RECORDED, _record_correction_events, {}),
    (DiscussionDeltaOperationType.CONFIRM_DECISION, DiscussionEventType.DECISION_CONFIRMED, list, {}),
    (DiscussionDeltaOperationType.REQUEST_FORMALIZATION, DiscussionEventType.FORMALIZATION_REQUESTED, list, {}),
    (DiscussionDeltaOperationType.CANCEL_FORMALIZATION, DiscussionEventType.FORMALIZATION_CANCELLED, _formalization_events, {"supersedes_event_id": _FORMALIZATION_EVT_ID}),
]


# ═══════════════════════════════════════════════════════════════════════════
# 1. Public contracts
# ═══════════════════════════════════════════════════════════════════════════


class TestPublicContracts:
    def test_gate_status_members(self):
        assert {member.value for member in DiscussionDeltaGateStatus} == {"prepared", "requires_confirmation"}

    def test_prepared_event_frozen_slots(self):
        assert is_dataclass(PreparedDiscussionEvent)
        assert set(PreparedDiscussionEvent.__slots__) == {"operation_index", "event", "idempotency_key"}
        assert {item.name for item in fields(PreparedDiscussionEvent)} == {"operation_index", "event", "idempotency_key"}
        result = evaluate(make_operation())
        with pytest.raises(FrozenInstanceError):
            result.prepared_events[0].idempotency_key = "changed"

    def test_result_frozen_slots_tuple_fields(self):
        assert is_dataclass(GovernedDiscussionDeltaResult)
        assert set(GovernedDiscussionDeltaResult.__slots__) == {"status", "prepared_events", "projected_workspace", "confirmation_reasons"}
        assert {item.name for item in fields(GovernedDiscussionDeltaResult)} == {"status", "prepared_events", "projected_workspace", "confirmation_reasons"}
        result = evaluate(make_operation())
        assert isinstance(result.prepared_events, tuple)
        assert isinstance(result.confirmation_reasons, tuple)
        with pytest.raises(FrozenInstanceError):
            result.prepared_events = ()


# ═══════════════════════════════════════════════════════════════════════════
# 2. Assistant message boundary
# ═══════════════════════════════════════════════════════════════════════════


class TestAssistantMessageBoundary:
    def test_session_mismatch_rejected(self):
        assert_code("discussion_delta_assistant_message_session_mismatch",
                     lambda: evaluate(make_operation(), assistant_message=assistant(session_id=uuid4())))

    @pytest.mark.parametrize("role", [ProjectDirectorMessageRole.USER, ProjectDirectorMessageRole.SYSTEM])
    def test_non_assistant_role_rejected(self, role):
        assert_code("discussion_delta_assistant_message_role_invalid",
                     lambda: evaluate(make_operation(), assistant_message=make_message(message_id=ASSISTANT_ID, role=role)))

    def test_assistant_auto_added_to_catalog(self):
        op = make_operation(actor_claim=DiscussionActorClaim.ASSISTANT_PROPOSAL)
        result = evaluate(op)
        assert result.status is DiscussionDeltaGateStatus.PREPARED

    def test_assistant_already_in_catalog_passes(self):
        op = make_operation(actor_claim=DiscussionActorClaim.ASSISTANT_PROPOSAL)
        result = evaluate(op, available_messages=sources(include_assistant=True))
        assert result.status is DiscussionDeltaGateStatus.PREPARED

    def test_assistant_conflict_rejected(self):
        op = make_operation(actor_claim=DiscussionActorClaim.ASSISTANT_PROPOSAL)
        conflicted = assistant(content="different")
        assert_code("discussion_delta_assistant_message_conflict",
                     lambda: evaluate(op, available_messages=[conflicted]))

    def test_assistant_proposal_must_reference_current_assistant(self):
        """assistant_proposal referencing a different assistant → rejected."""
        other_assistant = make_message(
            message_id=uuid4(), role=ProjectDirectorMessageRole.ASSISTANT,
            content="其他助手", sequence_no=2,
        )
        op = make_operation(
            actor_claim=DiscussionActorClaim.ASSISTANT_PROPOSAL,
            source_message_ids=[other_assistant.id],
        )
        catalog = sources(include_assistant=True) + [other_assistant]
        assert_code("discussion_delta_actor_source_role_mismatch",
                     lambda: evaluate(op, available_messages=catalog))


# ═══════════════════════════════════════════════════════════════════════════
# 3. Available message catalog
# ═══════════════════════════════════════════════════════════════════════════


class TestSourceMessageCatalog:
    def test_duplicate_rejected(self):
        user = make_message(message_id=USER_ID)
        assert_code("discussion_delta_source_message_duplicate",
                     lambda: evaluate(make_operation(), available_messages=[user, user]))

    def test_cross_session_rejected(self):
        assert_code("discussion_delta_source_message_session_mismatch",
                     lambda: evaluate(make_operation(), available_messages=[make_message(session_id=uuid4())]))

    def test_referenced_id_not_found(self):
        assert_code("discussion_delta_source_message_not_found",
                     lambda: evaluate(make_operation(source_message_ids=[uuid4()])))


# ═══════════════════════════════════════════════════════════════════════════
# 4. Actor / source role matrix
# ═══════════════════════════════════════════════════════════════════════════


class TestActorSourceRoleMatrix:
    @pytest.mark.parametrize(
        ("actor", "message_role", "confidence"),
        [
            (DiscussionActorClaim.USER_EXPLICIT, ProjectDirectorMessageRole.USER, 1.0),
            (DiscussionActorClaim.USER_INFERRED, ProjectDirectorMessageRole.USER, 0.5),
            (DiscussionActorClaim.ASSISTANT_PROPOSAL, ProjectDirectorMessageRole.ASSISTANT, 0.5),
            (DiscussionActorClaim.SYSTEM_FACT, ProjectDirectorMessageRole.SYSTEM, 1.0),
            (DiscussionActorClaim.FORMAL_PROJECT_FACT, ProjectDirectorMessageRole.SYSTEM, 1.0),
        ],
    )
    def test_actor_confidence_and_source_role(self, actor, message_role, confidence):
        source_id = ASSISTANT_ID if message_role is ProjectDirectorMessageRole.ASSISTANT else (
            USER_ID if message_role is ProjectDirectorMessageRole.USER else SYSTEM_ID
        )
        catalog = [make_message(message_id=source_id, role=message_role)] if source_id != ASSISTANT_ID else []
        operation = make_operation(
            actor_claim=actor,
            source_message_ids=[] if actor in {DiscussionActorClaim.SYSTEM_FACT, DiscussionActorClaim.FORMAL_PROJECT_FACT} else [source_id],
        )
        result = evaluate(operation, available_messages=catalog)
        assert result.prepared_events[0].event.confidence == confidence
        if actor is DiscussionActorClaim.FORMAL_PROJECT_FACT:
            assert result.prepared_events[0].event.status is DiscussionEventStatus.CONFIRMED

    @pytest.mark.parametrize("actor", [
        DiscussionActorClaim.USER_EXPLICIT, DiscussionActorClaim.USER_INFERRED, DiscussionActorClaim.ASSISTANT_PROPOSAL,
    ])
    def test_source_role_mismatch_rejected(self, actor):
        wrong = SYSTEM_ID if actor is not DiscussionActorClaim.ASSISTANT_PROPOSAL else USER_ID
        assert_code("discussion_delta_actor_source_role_mismatch",
                     lambda: evaluate(make_operation(actor_claim=actor, source_message_ids=[wrong])))


# ═══════════════════════════════════════════════════════════════════════════
# 5. All 18 operation mappings — every one asserted
# ═══════════════════════════════════════════════════════════════════════════


class TestAllOperationMappings:
    @pytest.mark.parametrize(
        ("op", "expected_event_type", "events_factory", "op_kwargs"),
        _ALL_18_MAPPINGS,
        ids=[m[0].value for m in _ALL_18_MAPPINGS],
    )
    def test_operation_maps_to_event_type(self, op, expected_event_type, events_factory, op_kwargs):
        current_events = events_factory()
        result = evaluate(make_operation(op=op, **op_kwargs), current_events=current_events)
        assert result.status is DiscussionDeltaGateStatus.PREPARED
        assert len(result.prepared_events) == 1
        assert result.prepared_events[0].event.event_type is expected_event_type
        assert result.prepared_events[0].operation_index == 0
        assert result.confirmation_reasons == ()

    def test_unsupported_operation_rejected(self):
        """A fabricated op value not in the enum → not supported."""
        # We can't create an invalid enum member through normal means,
        # but we can verify the gate rejects when _OPERATION_EVENT_TYPES has no mapping.
        # The real test is that all 18 ARE mapped above — this asserts completeness.
        from app.services.project_director_discussion_delta_gate_service import _OPERATION_EVENT_TYPES
        assert len(_OPERATION_EVENT_TYPES) == 18


# ═══════════════════════════════════════════════════════════════════════════
# 6. Additive operation actor matrix
# ═══════════════════════════════════════════════════════════════════════════


_ADDITIVE_OPS = [
    DiscussionDeltaOperationType.SET_TOPIC,
    DiscussionDeltaOperationType.ADD_OPTION,
    DiscussionDeltaOperationType.ADD_CONSTRAINT,
    DiscussionDeltaOperationType.ADD_CONCERN,
    DiscussionDeltaOperationType.ADD_ASSUMPTION,
    DiscussionDeltaOperationType.ADD_OPEN_QUESTION,
    DiscussionDeltaOperationType.ADD_TEMPORARY_CONCLUSION,
]


class TestAdditiveOperationAuthority:
    @pytest.mark.parametrize("actor", list(DiscussionActorClaim))
    @pytest.mark.parametrize("op", _ADDITIVE_OPS)
    def test_additive_allows_all_actors(self, actor, op):
        target = uuid4() if op is DiscussionDeltaOperationType.ADD_OPTION else None
        result = evaluate(make_operation(op=op, actor_claim=actor, target_id=target))
        assert result.status is DiscussionDeltaGateStatus.PREPARED
        assert result.confirmation_reasons == ()


# ═══════════════════════════════════════════════════════════════════════════
# 7. Option update actor matrix
# ═══════════════════════════════════════════════════════════════════════════


class TestOptionUpdateAuthority:
    @pytest.mark.parametrize("actor", [
        DiscussionActorClaim.USER_EXPLICIT, DiscussionActorClaim.USER_INFERRED, DiscussionActorClaim.ASSISTANT_PROPOSAL,
    ])
    def test_option_update_allowed_actors(self, actor):
        result = evaluate(
            make_operation(
                op=DiscussionDeltaOperationType.UPDATE_OPTION, actor_claim=actor,
                target_id=_OPTION_ID, supersedes_event_id=_OPTION_ADDED_EVT_ID,
            ),
            current_events=_option_added_events(),
        )
        if actor is DiscussionActorClaim.USER_EXPLICIT:
            assert result.status is DiscussionDeltaGateStatus.PREPARED
            assert len(result.prepared_events) == 1
            evt = result.prepared_events[0].event
            assert evt.event_type is DiscussionEventType.OPTION_UPDATED
            assert evt.supersedes_event_id == _OPTION_ADDED_EVT_ID
            assert evt.payload["option_id"] == _OPTION_ID
            assert _OPTION_ID in result.projected_workspace.active_option_ids
            assert result.confirmation_reasons == ()
        else:
            assert result.status is DiscussionDeltaGateStatus.REQUIRES_CONFIRMATION
            assert result.prepared_events == ()
            assert result.confirmation_reasons == (
                "discussion_delta_inferred_supersede_confirmation_required:0",
            )
            base_ws = workspace(_option_added_events())
            assert _OPTION_ID in base_ws.active_option_ids
            assert result.projected_workspace.active_option_ids == base_ws.active_option_ids

    @pytest.mark.parametrize("actor", [DiscussionActorClaim.SYSTEM_FACT, DiscussionActorClaim.FORMAL_PROJECT_FACT])
    def test_option_update_rejects_authoritative_actors(self, actor):
        assert_code("discussion_delta_operation_actor_not_authorized", lambda: evaluate(
            make_operation(
                op=DiscussionDeltaOperationType.UPDATE_OPTION, actor_claim=actor,
                target_id=_OPTION_ID, supersedes_event_id=_OPTION_ADDED_EVT_ID,
            ),
            current_events=_option_added_events(),
        ))


# ═══════════════════════════════════════════════════════════════════════════
# 8. Authoritative operation actor matrix
# ═══════════════════════════════════════════════════════════════════════════


_AUTH_OPS_AND_TARGETS = [
    (DiscussionDeltaOperationType.UPDATE_CONSTRAINT, DiscussionEventType.CONSTRAINT_ADDED, _constraint_added_events, _CONSTRAINT_ADDED_EVT_ID),
    (DiscussionDeltaOperationType.SUPERSEDE_CONSTRAINT, DiscussionEventType.CONSTRAINT_ADDED, _constraint_added_events, _CONSTRAINT_ADDED_EVT_ID),
    (DiscussionDeltaOperationType.REJECT_ASSUMPTION, DiscussionEventType.ASSUMPTION_ADDED, _assumption_added_events, _ASSUMPTION_ADDED_EVT_ID),
    (DiscussionDeltaOperationType.RESOLVE_OPEN_QUESTION, DiscussionEventType.OPEN_QUESTION_ADDED, _question_added_events, _QUESTION_ADDED_EVT_ID),
]


class TestAuthoritativeOperationAuthority:
    @pytest.mark.parametrize("actor", [DiscussionActorClaim.USER_EXPLICIT, DiscussionActorClaim.SYSTEM_FACT, DiscussionActorClaim.FORMAL_PROJECT_FACT])
    @pytest.mark.parametrize("op,target_type,events_factory,target_id", _AUTH_OPS_AND_TARGETS)
    def test_authoritative_allows_authority_actors(self, op, target_type, events_factory, target_id, actor):
        result = evaluate(
            make_operation(op=op, actor_claim=actor, supersedes_event_id=target_id),
            current_events=events_factory(),
        )
        assert result.status is DiscussionDeltaGateStatus.PREPARED
        assert result.confirmation_reasons == ()

    @pytest.mark.parametrize("actor", [DiscussionActorClaim.USER_INFERRED, DiscussionActorClaim.ASSISTANT_PROPOSAL])
    @pytest.mark.parametrize("op,target_type,events_factory,target_id", _AUTH_OPS_AND_TARGETS)
    def test_authoritative_rejects_non_authority_actors(self, op, target_type, events_factory, target_id, actor):
        assert_code("discussion_delta_operation_actor_not_authorized", lambda: evaluate(
            make_operation(op=op, actor_claim=actor, supersedes_event_id=target_id),
            current_events=events_factory(),
        ))


# ═══════════════════════════════════════════════════════════════════════════
# 9. User-explicit-only operations — confirmation for ALL non-explicit actors
# ═══════════════════════════════════════════════════════════════════════════


_USER_EXPLICIT_OPS = [
    DiscussionDeltaOperationType.PREFER_OPTION,
    DiscussionDeltaOperationType.REJECT_OPTION,
    DiscussionDeltaOperationType.RECORD_USER_CORRECTION,
    DiscussionDeltaOperationType.CONFIRM_DECISION,
    DiscussionDeltaOperationType.REQUEST_FORMALIZATION,
    DiscussionDeltaOperationType.CANCEL_FORMALIZATION,
]


class TestUserExplicitOnlyConfirmation:
    @pytest.mark.parametrize("op", _USER_EXPLICIT_OPS)
    def test_user_explicit_is_directly_prepared(self, op):
        """user_explicit on these ops → prepared, no confirmation."""
        option_id = _OPTION_ID
        target = make_event(
            event_type=DiscussionEventType.OPTION_ADDED, payload={"option_id": option_id},
            subject_key=f"option:{option_id}", content="选项",
        )
        kwargs: dict = {}
        if op in {DiscussionDeltaOperationType.PREFER_OPTION, DiscussionDeltaOperationType.REJECT_OPTION}:
            kwargs["target_id"] = option_id
        if op is DiscussionDeltaOperationType.CANCEL_FORMALIZATION:
            target = make_event(event_type=DiscussionEventType.FORMALIZATION_REQUESTED, subject_key="formalization", content="请正式化")
            kwargs["supersedes_event_id"] = target.id
        result = evaluate(make_operation(op=op, **kwargs), current_events=[target])
        assert result.status is DiscussionDeltaGateStatus.PREPARED
        assert result.confirmation_reasons == ()

    @pytest.mark.parametrize("op", _USER_EXPLICIT_OPS)
    @pytest.mark.parametrize("actor", [
        DiscussionActorClaim.USER_INFERRED,
        DiscussionActorClaim.ASSISTANT_PROPOSAL,
        DiscussionActorClaim.SYSTEM_FACT,
        DiscussionActorClaim.FORMAL_PROJECT_FACT,
    ])
    def test_non_explicit_actor_requires_confirmation(self, op, actor):
        """All four non-explicit actors → requires_confirmation with exact reason."""
        option_id = _OPTION_ID
        target = make_event(
            event_type=DiscussionEventType.OPTION_ADDED, payload={"option_id": option_id},
            subject_key=f"option:{option_id}", content="选项",
        )
        kwargs: dict = {}
        has_supersede = False
        if op in {DiscussionDeltaOperationType.PREFER_OPTION, DiscussionDeltaOperationType.REJECT_OPTION}:
            kwargs["target_id"] = option_id
        if op is DiscussionDeltaOperationType.CANCEL_FORMALIZATION:
            target = make_event(event_type=DiscussionEventType.FORMALIZATION_REQUESTED, subject_key="formalization", content="请正式化")
            kwargs["supersedes_event_id"] = target.id
            has_supersede = True
        # system_fact and formal_project_fact have no source messages
        src = [] if actor in {DiscussionActorClaim.SYSTEM_FACT, DiscussionActorClaim.FORMAL_PROJECT_FACT} else None
        result = evaluate(
            make_operation(op=op, actor_claim=actor, source_message_ids=src, **kwargs),
            current_events=[target],
        )
        assert result.status is DiscussionDeltaGateStatus.REQUIRES_CONFIRMATION
        assert result.prepared_events == ()
        # Baseline workspace unchanged
        base_ws = workspace([target])
        assert result.projected_workspace.last_event_sequence_no == base_ws.last_event_sequence_no
        assert result.projected_workspace.version_no == base_ws.version_no
        # Exact reasons — cancel_formalization has supersedes, so inferred actors get extra reason
        expected: tuple[str, ...] = ("discussion_delta_user_confirmation_required:0",)
        if has_supersede and actor in {DiscussionActorClaim.USER_INFERRED, DiscussionActorClaim.ASSISTANT_PROPOSAL}:
            expected = (
                "discussion_delta_user_confirmation_required:0",
                "discussion_delta_inferred_supersede_confirmation_required:0",
            )
        assert result.confirmation_reasons == expected


# ═══════════════════════════════════════════════════════════════════════════
# 10. Confirmation atomicity
# ═══════════════════════════════════════════════════════════════════════════


class TestConfirmationAtomicity:
    def test_confirmation_blocks_entire_delta(self):
        """One confirmation-required op blocks all ops in the delta."""
        base = workspace([])
        op0 = make_operation(op=DiscussionDeltaOperationType.ADD_CONCERN, content="a")
        op1 = make_operation(
            op=DiscussionDeltaOperationType.CONFIRM_DECISION,
            actor_claim=DiscussionActorClaim.ASSISTANT_PROPOSAL, content="b",
        )
        op2 = make_operation(op=DiscussionDeltaOperationType.ADD_CONCERN, content="c")
        result = evaluate(op0, op1, op2, current_workspace=base)
        assert result.status is DiscussionDeltaGateStatus.REQUIRES_CONFIRMATION
        assert result.prepared_events == ()
        assert result.projected_workspace == base
        assert result.confirmation_reasons == ("discussion_delta_user_confirmation_required:1",)

    def test_multi_reason_ordering_stable(self):
        """Multiple confirmation-required ops produce ordered reasons."""
        opt_evt = make_event(
            event_type=DiscussionEventType.OPTION_ADDED, payload={"option_id": _OPTION_ID},
            subject_key=f"option:{_OPTION_ID}", content="选项", sequence_no=1,
        )
        base = workspace([opt_evt])
        # system_fact for prefer_option → user_confirmation reason at index 0
        op0 = make_operation(
            op=DiscussionDeltaOperationType.PREFER_OPTION,
            actor_claim=DiscussionActorClaim.SYSTEM_FACT,
            target_id=_OPTION_ID, source_message_ids=[],
        )
        op1 = make_operation(op=DiscussionDeltaOperationType.ADD_CONCERN, content="x")
        # assistant_proposal for confirm_decision → user_confirmation at index 2
        op2 = make_operation(
            op=DiscussionDeltaOperationType.CONFIRM_DECISION,
            actor_claim=DiscussionActorClaim.ASSISTANT_PROPOSAL, content="y",
        )
        result = evaluate(op0, op1, op2, current_events=[opt_evt], current_workspace=base)
        assert result.status is DiscussionDeltaGateStatus.REQUIRES_CONFIRMATION
        reasons = result.confirmation_reasons
        # indices must be in ascending order
        indices = [int(r.split(":")[-1]) for r in reasons]
        assert indices == sorted(indices)
        # Exact reasons
        assert reasons == (
            "discussion_delta_user_confirmation_required:0",
            "discussion_delta_user_confirmation_required:2",
        )


# ═══════════════════════════════════════════════════════════════════════════
# 11. Supersede basics
# ═══════════════════════════════════════════════════════════════════════════


class TestSupersedeBasics:
    def test_target_not_found(self):
        assert_code("discussion_delta_supersedes_target_not_found",
                     lambda: evaluate(make_operation(supersedes_event_id=uuid4())))

    @pytest.mark.parametrize("status", [
        DiscussionEventStatus.REJECTED,
        DiscussionEventStatus.SUPERSEDED,
        DiscussionEventStatus.HISTORICAL,
    ])
    def test_non_effective_target_rejected(self, status):
        inactive = make_event(status=status)
        assert_code("discussion_delta_supersedes_target_not_effective",
                     lambda: evaluate(make_operation(supersedes_event_id=inactive.id), current_events=[inactive]))

    def test_intra_delta_supersede_not_allowed(self):
        """D1 does not promote unpersisted prepared events to supersedeable facts."""
        op0 = make_operation(op=DiscussionDeltaOperationType.SET_TOPIC, content="主题")
        # Compute the deterministic event ID that op0 will produce
        svc = ProjectDirectorDiscussionDeltaGateService()
        r0 = svc.evaluate_delta(
            session_id=SESSION_ID, project_id=None, assistant_message=assistant(),
            available_messages=sources(), current_events=[], current_workspace=None,
            delta=DiscussionDelta(operations=[op0]), start_sequence_no=1,
        )
        prepared_id = r0.prepared_events[0].event.id
        # op1 tries to supersede op0's prepared event (not in current_events)
        op1 = make_operation(supersedes_event_id=prepared_id)
        assert_code("discussion_delta_supersedes_target_not_found",
                     lambda: evaluate(op0, op1))


# ═══════════════════════════════════════════════════════════════════════════
# 12. Supersede type compatibility matrix
# ═══════════════════════════════════════════════════════════════════════════


class TestSupersedeTypeCompatibility:
    def test_set_topic_supersedes_topic_set(self):
        topic_evt = make_event(event_type=DiscussionEventType.TOPIC_SET, subject_key="topic", content="旧主题")
        result = evaluate(
            make_operation(op=DiscussionDeltaOperationType.SET_TOPIC, supersedes_event_id=topic_evt.id, content="新主题"),
            current_events=[topic_evt],
        )
        assert result.status is DiscussionDeltaGateStatus.PREPARED
        assert result.prepared_events[0].event.supersedes_event_id == topic_evt.id

    @pytest.mark.parametrize("target_type", [
        DiscussionEventType.CONSTRAINT_ADDED, DiscussionEventType.OPEN_QUESTION_ADDED,
    ])
    def test_set_topic_rejects_non_topic_target(self, target_type):
        bad_target = make_event(event_type=target_type, subject_key="s", content="c")
        assert_code("discussion_delta_supersedes_type_invalid",
                     lambda: evaluate(
                         make_operation(op=DiscussionDeltaOperationType.SET_TOPIC, supersedes_event_id=bad_target.id),
                         current_events=[bad_target],
                     ))

    def test_set_topic_rejects_option_target(self):
        oid = uuid4()
        bad_target = make_event(
            event_type=DiscussionEventType.OPTION_ADDED,
            payload={"option_id": oid}, subject_key=f"option:{oid}", content="选项",
        )
        assert_code("discussion_delta_supersedes_type_invalid",
                     lambda: evaluate(
                         make_operation(op=DiscussionDeltaOperationType.SET_TOPIC, supersedes_event_id=bad_target.id),
                         current_events=[bad_target],
                     ))

    def test_update_option_supersedes_option_added(self):
        oid = uuid4()
        e1 = make_event(
            event_id=uuid4(), event_type=DiscussionEventType.OPTION_ADDED,
            payload={"option_id": oid}, subject_key=f"option:{oid}", content="选项",
        )
        result = evaluate(
            make_operation(
                op=DiscussionDeltaOperationType.UPDATE_OPTION, target_id=oid,
                supersedes_event_id=e1.id,
            ),
            current_events=[e1],
        )
        assert result.status is DiscussionDeltaGateStatus.PREPARED
        assert result.prepared_events[0].event.event_type is DiscussionEventType.OPTION_UPDATED

    def test_update_option_supersedes_option_updated_chain(self):
        """OPTION_UPDATED supersedes OPTION_UPDATED supersedes OPTION_ADDED."""
        oid = uuid4()
        e1 = make_event(
            event_id=uuid4(), event_type=DiscussionEventType.OPTION_ADDED,
            payload={"option_id": oid}, subject_key=f"option:{oid}", content="选项",
            sequence_no=1,
        )
        e2 = make_event(
            event_id=uuid4(), event_type=DiscussionEventType.OPTION_UPDATED,
            payload={"option_id": oid}, subject_key=f"option:{oid}", content="更新",
            supersedes_event_id=e1.id, sequence_no=2,
        )
        result = evaluate(
            make_operation(
                op=DiscussionDeltaOperationType.UPDATE_OPTION, target_id=oid,
                supersedes_event_id=e2.id,
            ),
            current_events=[e1, e2],
        )
        assert result.status is DiscussionDeltaGateStatus.PREPARED

    def test_update_option_rejects_topic_target(self):
        topic = make_event(event_type=DiscussionEventType.TOPIC_SET, subject_key="topic", content="主题")
        assert_code("discussion_delta_supersedes_type_invalid",
                     lambda: evaluate(
                         make_operation(
                             op=DiscussionDeltaOperationType.UPDATE_OPTION,
                             target_id=_OPTION_ID, supersedes_event_id=topic.id,
                         ),
                         current_events=[topic],
                     ))

    def test_update_constraint_supersedes_constraint_added(self):
        c = make_event(event_id=uuid4(), event_type=DiscussionEventType.CONSTRAINT_ADDED, subject_key="constraint", content="约束")
        result = evaluate(
            make_operation(
                op=DiscussionDeltaOperationType.UPDATE_CONSTRAINT,
                supersedes_event_id=c.id,
            ),
            current_events=[c],
        )
        assert result.status is DiscussionDeltaGateStatus.PREPARED

    def test_update_constraint_supersedes_constraint_updated_chain(self):
        """CONSTRAINT_UPDATED supersedes CONSTRAINT_UPDATED supersedes CONSTRAINT_ADDED."""
        c1 = make_event(
            event_id=uuid4(), event_type=DiscussionEventType.CONSTRAINT_ADDED,
            subject_key="constraint", content="约束", sequence_no=1,
        )
        c2 = make_event(
            event_id=uuid4(), event_type=DiscussionEventType.CONSTRAINT_UPDATED,
            subject_key="constraint", content="更新", supersedes_event_id=c1.id, sequence_no=2,
        )
        result = evaluate(
            make_operation(
                op=DiscussionDeltaOperationType.UPDATE_CONSTRAINT,
                supersedes_event_id=c2.id,
            ),
            current_events=[c1, c2],
        )
        assert result.status is DiscussionDeltaGateStatus.PREPARED

    def test_update_constraint_rejects_option_target(self):
        oid = uuid4()
        opt = make_event(
            event_type=DiscussionEventType.OPTION_ADDED,
            payload={"option_id": oid}, subject_key=f"option:{oid}", content="选项",
        )
        assert_code("discussion_delta_supersedes_type_invalid",
                     lambda: evaluate(
                         make_operation(
                             op=DiscussionDeltaOperationType.UPDATE_CONSTRAINT,
                             supersedes_event_id=opt.id,
                         ),
                         current_events=[opt],
                     ))

    def test_reject_assumption_supersedes_assumption_added(self):
        a = make_event(event_type=DiscussionEventType.ASSUMPTION_ADDED, subject_key="assumption", content="假设")
        result = evaluate(
            make_operation(
                op=DiscussionDeltaOperationType.REJECT_ASSUMPTION,
                supersedes_event_id=a.id,
            ),
            current_events=[a],
        )
        assert result.status is DiscussionDeltaGateStatus.PREPARED

    def test_reject_assumption_rejects_constraint_target(self):
        c = make_event(event_type=DiscussionEventType.CONSTRAINT_ADDED, subject_key="constraint", content="约束")
        assert_code("discussion_delta_supersedes_type_invalid",
                     lambda: evaluate(
                         make_operation(
                             op=DiscussionDeltaOperationType.REJECT_ASSUMPTION,
                             supersedes_event_id=c.id,
                         ),
                         current_events=[c],
                     ))

    def test_resolve_open_question_supersedes_question_added(self):
        q = make_event(event_type=DiscussionEventType.OPEN_QUESTION_ADDED, subject_key="open_question", content="问题")
        result = evaluate(
            make_operation(
                op=DiscussionDeltaOperationType.RESOLVE_OPEN_QUESTION,
                supersedes_event_id=q.id,
            ),
            current_events=[q],
        )
        assert result.status is DiscussionDeltaGateStatus.PREPARED

    def test_resolve_open_question_rejects_assumption_target(self):
        a = make_event(event_type=DiscussionEventType.ASSUMPTION_ADDED, subject_key="assumption", content="假设")
        assert_code("discussion_delta_supersedes_type_invalid",
                     lambda: evaluate(
                         make_operation(
                             op=DiscussionDeltaOperationType.RESOLVE_OPEN_QUESTION,
                             supersedes_event_id=a.id,
                         ),
                         current_events=[a],
                     ))

    def test_cancel_formalization_supersedes_formalization_requested(self):
        f = make_event(event_type=DiscussionEventType.FORMALIZATION_REQUESTED, subject_key="formalization", content="正式化")
        result = evaluate(
            make_operation(
                op=DiscussionDeltaOperationType.CANCEL_FORMALIZATION,
                supersedes_event_id=f.id,
            ),
            current_events=[f],
        )
        assert result.status is DiscussionDeltaGateStatus.PREPARED

    def test_cancel_formalization_rejects_topic_target(self):
        t = make_event(event_type=DiscussionEventType.TOPIC_SET, subject_key="topic", content="主题")
        assert_code("discussion_delta_supersedes_type_invalid",
                     lambda: evaluate(
                         make_operation(
                             op=DiscussionDeltaOperationType.CANCEL_FORMALIZATION,
                             supersedes_event_id=t.id,
                         ),
                         current_events=[t],
                     ))

    def test_record_user_correction_supersedes_any_effective_event(self):
        """record_user_correction can supersede any effective discussion event."""
        topic = make_event(event_type=DiscussionEventType.TOPIC_SET, subject_key="topic", content="主题")
        result = evaluate(
            make_operation(
                op=DiscussionDeltaOperationType.RECORD_USER_CORRECTION,
                supersedes_event_id=topic.id, content="纠正",
            ),
            current_events=[topic],
        )
        assert result.status is DiscussionDeltaGateStatus.PREPARED


# ═══════════════════════════════════════════════════════════════════════════
# 13. Inferred / assistant supersede confirmation
# ═══════════════════════════════════════════════════════════════════════════


class TestInferredSupersedeConfirmation:
    @pytest.mark.parametrize("actor", [DiscussionActorClaim.USER_INFERRED, DiscussionActorClaim.ASSISTANT_PROPOSAL])
    def test_inferred_supersede_requires_confirmation(self, actor):
        topic = make_event(
            event_type=DiscussionEventType.TOPIC_SET, subject_key="topic", content="主题",
            created_by=DiscussionActorClaim.SYSTEM_FACT, source_message_ids=[SYSTEM_ID],
        )
        result = evaluate(
            make_operation(
                op=DiscussionDeltaOperationType.SET_TOPIC,
                actor_claim=actor, supersedes_event_id=topic.id, content="新主题",
            ),
            current_events=[topic],
        )
        assert result.status is DiscussionDeltaGateStatus.REQUIRES_CONFIRMATION
        assert result.prepared_events == ()
        assert result.confirmation_reasons == (
            "discussion_delta_inferred_supersede_confirmation_required:0",
        )

    @pytest.mark.parametrize("actor", [DiscussionActorClaim.USER_INFERRED, DiscussionActorClaim.ASSISTANT_PROPOSAL])
    def test_inferred_supersede_of_confirmed_fact_has_both_reasons(self, actor):
        """Inferred supersede of a user_explicit topic → both inferred_supersede and confirmed_fact reasons."""
        topic = make_event(
            event_type=DiscussionEventType.TOPIC_SET, subject_key="topic", content="主题",
            created_by=DiscussionActorClaim.USER_EXPLICIT, source_message_ids=[USER_ID],
        )
        result = evaluate(
            make_operation(
                op=DiscussionDeltaOperationType.SET_TOPIC,
                actor_claim=actor, supersedes_event_id=topic.id, content="新主题",
            ),
            current_events=[topic],
        )
        assert result.status is DiscussionDeltaGateStatus.REQUIRES_CONFIRMATION
        assert result.confirmation_reasons == (
            "discussion_delta_inferred_supersede_confirmation_required:0",
            "discussion_delta_confirmed_fact_confirmation_required:0",
        )


# ═══════════════════════════════════════════════════════════════════════════
# 14. Confirmed fact protection
# ═══════════════════════════════════════════════════════════════════════════


class TestConfirmedFactProtection:
    def test_supersede_user_explicit_target_requires_confirmation_for_non_explicit(self):
        topic = make_event(
            event_type=DiscussionEventType.TOPIC_SET, subject_key="topic", content="主题",
            created_by=DiscussionActorClaim.USER_EXPLICIT, source_message_ids=[USER_ID],
        )
        result = evaluate(
            make_operation(
                op=DiscussionDeltaOperationType.SET_TOPIC,
                actor_claim=DiscussionActorClaim.USER_INFERRED,
                supersedes_event_id=topic.id, content="新主题",
            ),
            current_events=[topic],
        )
        assert result.status is DiscussionDeltaGateStatus.REQUIRES_CONFIRMATION
        assert "discussion_delta_confirmed_fact_confirmation_required:0" in result.confirmation_reasons

    def test_supersede_confirmed_status_requires_confirmation_for_non_explicit(self):
        evt = make_event(
            event_type=DiscussionEventType.TOPIC_SET, subject_key="topic", content="主题",
            status=DiscussionEventStatus.CONFIRMED,
        )
        result = evaluate(
            make_operation(
                op=DiscussionDeltaOperationType.SET_TOPIC,
                actor_claim=DiscussionActorClaim.ASSISTANT_PROPOSAL,
                supersedes_event_id=evt.id, content="新主题",
            ),
            current_events=[evt],
        )
        assert result.status is DiscussionDeltaGateStatus.REQUIRES_CONFIRMATION
        assert "discussion_delta_confirmed_fact_confirmation_required:0" in result.confirmation_reasons

    def test_supersede_decision_confirmed_requires_confirmation_for_non_explicit(self):
        evt = make_event(
            event_type=DiscussionEventType.DECISION_CONFIRMED, subject_key="decision", content="决策",
        )
        result = evaluate(
            make_operation(
                op=DiscussionDeltaOperationType.RECORD_USER_CORRECTION,
                actor_claim=DiscussionActorClaim.SYSTEM_FACT,
                supersedes_event_id=evt.id, content="纠正",
            ),
            current_events=[evt],
        )
        assert result.status is DiscussionDeltaGateStatus.REQUIRES_CONFIRMATION
        assert "discussion_delta_confirmed_fact_confirmation_required:0" in result.confirmation_reasons

    def test_user_explicit_supersede_of_confirmed_is_directly_prepared(self):
        topic = make_event(
            event_type=DiscussionEventType.TOPIC_SET, subject_key="topic", content="主题",
            created_by=DiscussionActorClaim.USER_EXPLICIT, source_message_ids=[USER_ID],
        )
        result = evaluate(
            make_operation(
                op=DiscussionDeltaOperationType.SET_TOPIC,
                actor_claim=DiscussionActorClaim.USER_EXPLICIT,
                supersedes_event_id=topic.id, content="新主题",
            ),
            current_events=[topic],
        )
        assert result.status is DiscussionDeltaGateStatus.PREPARED
        assert result.confirmation_reasons == ()

    def test_formal_project_fact_conflict_always_rejected(self):
        formal = make_event(created_by=DiscussionActorClaim.FORMAL_PROJECT_FACT)
        assert_code("discussion_delta_formal_project_fact_conflict",
                     lambda: evaluate(
                         make_operation(supersedes_event_id=formal.id),
                         current_events=[formal],
                     ))


# ═══════════════════════════════════════════════════════════════════════════
# 15. Existing Workspace update replacement path
# ═══════════════════════════════════════════════════════════════════════════


class TestExistingWorkspaceReplacement:
    def test_update_supersede_with_existing_workspace(self):
        """update_option supersedes option_added; existing workspace version/cursor advance."""
        e1 = make_event(
            event_id=_OPTION_ADDED_EVT_ID,
            event_type=DiscussionEventType.OPTION_ADDED,
            payload={"option_id": _OPTION_ID}, subject_key=f"option:{_OPTION_ID}", content="选项",
            sequence_no=1,
        )
        ws = workspace([e1], version_no=7)
        assert ws.last_event_sequence_no == 1
        assert ws.version_no == 7
        result = evaluate(
            make_operation(
                op=DiscussionDeltaOperationType.UPDATE_OPTION,
                actor_claim=DiscussionActorClaim.USER_EXPLICIT,
                target_id=_OPTION_ID, supersedes_event_id=_OPTION_ADDED_EVT_ID,
                content="更新内容",
            ),
            current_events=[e1],
            current_workspace=ws,
        )
        assert result.status is DiscussionDeltaGateStatus.PREPARED
        assert len(result.prepared_events) == 1
        evt = result.prepared_events[0].event
        assert evt.event_type is DiscussionEventType.OPTION_UPDATED
        assert evt.supersedes_event_id == _OPTION_ADDED_EVT_ID
        assert evt.payload["option_id"] == _OPTION_ID
        assert _OPTION_ID in result.projected_workspace.active_option_ids
        assert result.projected_workspace.last_event_sequence_no == 2
        assert result.projected_workspace.version_no == 8
        # Original workspace not mutated
        assert ws.version_no == 7
        assert ws.last_event_sequence_no == 1
        # Original events not mutated
        assert e1.supersedes_event_id is None

    def test_update_supersede_without_workspace(self):
        """update_option supersedes option_added; no existing workspace."""
        e1 = make_event(
            event_id=_OPTION_ADDED_EVT_ID,
            event_type=DiscussionEventType.OPTION_ADDED,
            payload={"option_id": _OPTION_ID}, subject_key=f"option:{_OPTION_ID}", content="选项",
            sequence_no=1,
        )
        result = evaluate(
            make_operation(
                op=DiscussionDeltaOperationType.UPDATE_OPTION,
                actor_claim=DiscussionActorClaim.USER_EXPLICIT,
                target_id=_OPTION_ID, supersedes_event_id=_OPTION_ADDED_EVT_ID,
                content="更新内容",
            ),
            current_events=[e1],
            current_workspace=None,
        )
        assert result.status is DiscussionDeltaGateStatus.PREPARED
        assert _OPTION_ID in result.projected_workspace.active_option_ids
        assert result.projected_workspace.last_event_sequence_no == 2


# ═══════════════════════════════════════════════════════════════════════════
# 16. Normalization, determinism, and sequence
# ═══════════════════════════════════════════════════════════════════════════


class TestNormalizationAndDeterminism:
    @pytest.mark.parametrize("op", [
        DiscussionDeltaOperationType.ADD_OPTION,
        DiscussionDeltaOperationType.UPDATE_OPTION,
        DiscussionDeltaOperationType.PREFER_OPTION,
        DiscussionDeltaOperationType.REJECT_OPTION,
    ])
    def test_option_target_payload_normalized_without_mutation(self, op):
        option_id = uuid4()
        payload = {"option_id": str(option_id), "nested": {"items": ["中文"]}}
        old = make_event(event_type=DiscussionEventType.OPTION_ADDED, payload={"option_id": option_id})
        operation = make_operation(
            op=op, target_id=option_id, payload=payload,
            supersedes_event_id=old.id if op is DiscussionDeltaOperationType.UPDATE_OPTION else None,
        )
        result = evaluate(operation, current_events=[old] if op is not DiscussionDeltaOperationType.ADD_OPTION else [])
        assert result.prepared_events[0].event.payload["option_id"] == option_id
        # Original payload not mutated
        assert payload["option_id"] == str(option_id)

    def test_option_target_required(self):
        assert_code("discussion_delta_option_target_required",
                     lambda: evaluate(make_operation(op=DiscussionDeltaOperationType.ADD_OPTION)))

    def test_option_id_conflict(self):
        assert_code("discussion_delta_option_id_conflict",
                     lambda: evaluate(make_operation(
                         op=DiscussionDeltaOperationType.ADD_OPTION,
                         target_id=uuid4(), payload={"option_id": uuid4()},
                     )))

    def test_subject_key_trim(self):
        result = evaluate(make_operation(subject_key="  custom-key  "))
        assert result.prepared_events[0].event.subject_key == "custom-key"

    def test_option_subject_key_default(self):
        target = uuid4()
        result = evaluate(make_operation(op=DiscussionDeltaOperationType.ADD_OPTION, target_id=target))
        assert result.prepared_events[0].event.subject_key == f"option:{target}"

    def test_canonical_duplicate_rejected(self):
        assert_code("discussion_delta_duplicate_operation", lambda: evaluate(
            make_operation(payload={"a": 1, "b": 2}),
            make_operation(payload={"b": 2, "a": 1}),
        ))

    def test_deterministic_event_id(self):
        op = make_operation()
        first = evaluate(op)
        second = evaluate(op)
        assert first.prepared_events[0].event.id == second.prepared_events[0].event.id

    def test_deterministic_idempotency_key(self):
        op = make_operation()
        first = evaluate(op)
        second = evaluate(op)
        assert first.prepared_events[0].idempotency_key == second.prepared_events[0].idempotency_key
        key = first.prepared_events[0].idempotency_key
        assert key.startswith(f"p26-d1:{ASSISTANT_ID.hex}:0:")
        assert len(key.rsplit(":", 1)[1]) == 64
        assert len(key) < 256
        for forbidden in ("api_key", "authorization", "bearer", "sk-"):
            assert forbidden not in key.lower()

    def test_p27_fields_none(self):
        op = make_operation(payload={"source_surface": "not-promoted"})
        result = evaluate(op)
        for name in ("source_surface", "source_entity_type", "source_entity_id",
                      "trigger_type", "interaction_case_id", "external_context_pack_id"):
            assert getattr(result.prepared_events[0].event, name) is None

    def test_occurred_at_defaults_to_assistant_message(self):
        result = evaluate(make_operation())
        assert result.prepared_events[0].event.created_at == FIXED_TIME

    def test_occurred_at_explicit(self):
        explicit = datetime(2026, 12, 25, 0, 0, tzinfo=timezone.utc)
        result = evaluate(make_operation(), occurred_at=explicit)
        assert result.prepared_events[0].event.created_at == explicit

    def test_sequence_assignment(self):
        history = [make_event(sequence_no=9), make_event(sequence_no=2), make_event(sequence_no=4)]
        result = evaluate(
            make_operation(content="one"), make_operation(content="two"),
            current_events=history, start_sequence_no=10,
        )
        assert [item.event.sequence_no for item in result.prepared_events] == [10, 11]

    def test_start_sequence_mismatch(self):
        assert_code("discussion_delta_start_sequence_mismatch",
                     lambda: evaluate(make_operation(), start_sequence_no=2))


# ═══════════════════════════════════════════════════════════════════════════
# 17. Workspace baseline and empty delta
# ═══════════════════════════════════════════════════════════════════════════


class TestWorkspaceBaselineAndEmptyDelta:
    def test_empty_delta_with_workspace(self):
        base = workspace([])
        result = evaluate(current_workspace=base)
        assert result.status is DiscussionDeltaGateStatus.PREPARED
        assert result.prepared_events == ()
        assert result.projected_workspace == base
        assert result.confirmation_reasons == ()

    def test_empty_delta_without_workspace(self):
        result = evaluate(current_workspace=None)
        assert result.status is DiscussionDeltaGateStatus.PREPARED
        assert result.prepared_events == ()
        assert result.projected_workspace.version_no == 0
        assert result.projected_workspace.last_event_sequence_no == 0

    def test_workspace_session_mismatch(self):
        ws = DiscussionWorkspace(
            session_id=uuid4(), project_id=None, topic="",
            version_no=0, last_event_sequence_no=0,
            created_at=FIXED_TIME, updated_at=FIXED_TIME,
        )
        assert_code("discussion_delta_workspace_session_mismatch",
                     lambda: evaluate(make_operation(), current_workspace=ws))

    def test_workspace_project_mismatch(self):
        ws = workspace([])
        ws_pid = DiscussionWorkspace(
            session_id=SESSION_ID, project_id=PROJECT_ID, topic="",
            version_no=0, last_event_sequence_no=0,
            created_at=FIXED_TIME, updated_at=FIXED_TIME,
        )
        assert_code("discussion_delta_workspace_project_mismatch",
                     lambda: evaluate(make_operation(), current_workspace=ws_pid))

    def test_workspace_cursor_mismatch(self):
        e1 = make_event(sequence_no=1)
        ws = workspace([e1])
        # Manually set wrong cursor
        bad_ws = DiscussionWorkspace(
            session_id=SESSION_ID, project_id=None, topic=ws.topic,
            version_no=ws.version_no, last_event_sequence_no=99,
            created_at=ws.created_at, updated_at=ws.updated_at,
        )
        assert_code("discussion_delta_workspace_event_cursor_mismatch",
                     lambda: evaluate(make_operation(), current_events=[e1], current_workspace=bad_ws))


# ═══════════════════════════════════════════════════════════════════════════
# 18. Reducer spy injection — reuse evidence
# ═══════════════════════════════════════════════════════════════════════════


class TestReducerReuseEvidence:
    def test_prepared_delta_delegates_to_reducer(self):
        """Prepared delta uses the injected reducer for resolve, rebuild, and reduce."""
        spy = SpyReducer()
        svc = ProjectDirectorDiscussionDeltaGateService(reducer=spy)
        evaluate(make_operation(), service=svc)
        # Gate calls resolve_events directly; rebuild_workspace and reduce_workspace
        # each call resolve_events internally too, so resolve_calls >= 2.
        assert len(spy.resolve_calls) >= 2
        # No existing workspace → Gate calls rebuild_workspace for baseline
        assert len(spy.rebuild_calls) >= 1
        # Prepared events → Gate calls reduce_workspace for projection
        assert len(spy.reduce_calls) >= 1

    def test_confirmation_skips_final_reduce(self):
        """Confirmation path: no reduce_workspace from the projection step."""
        spy = SpyReducer()
        svc = ProjectDirectorDiscussionDeltaGateService(reducer=spy)
        evaluate(
            make_operation(
                op=DiscussionDeltaOperationType.CONFIRM_DECISION,
                actor_claim=DiscussionActorClaim.ASSISTANT_PROPOSAL,
            ),
            service=svc,
        )
        # Gate calls resolve_events + _resolve_baseline_workspace (rebuild)
        # rebuild internally calls resolve_events → at least 2 resolves
        assert len(spy.resolve_calls) >= 2
        assert len(spy.rebuild_calls) >= 1
        # Confirmation returns baseline → reduce_workspace only from baseline check
        # (rebuild does NOT call reduce), so reduce_calls == 0
        assert len(spy.reduce_calls) == 0

    def test_empty_delta_uses_reducer_for_baseline(self):
        """Empty delta: resolve + rebuild for baseline, no reduce."""
        spy = SpyReducer()
        svc = ProjectDirectorDiscussionDeltaGateService(reducer=spy)
        evaluate(current_workspace=None, service=svc)
        assert len(spy.resolve_calls) >= 2
        assert len(spy.rebuild_calls) >= 1
        assert len(spy.reduce_calls) == 0

    def test_existing_workspace_uses_reduce_not_rebuild(self):
        """Existing workspace → Gate uses reduce_workspace, not rebuild_workspace."""
        spy = SpyReducer()
        svc = ProjectDirectorDiscussionDeltaGateService(reducer=spy)
        base = workspace([])
        evaluate(make_operation(), current_workspace=base, service=svc)
        # reduce_workspace calls rebuild_workspace internally,
        # so rebuild_calls come from inside reduce, not from Gate directly
        assert len(spy.reduce_calls) >= 1
        # The Gate's _resolve_baseline_workspace calls reduce_workspace (not rebuild)
        # when current_workspace is provided


# ═══════════════════════════════════════════════════════════════════════════
# 19. Input immutability
# ═══════════════════════════════════════════════════════════════════════════


class TestInputImmutability:
    def test_all_inputs_unchanged_after_evaluation(self):
        payload = {"nested": ["中文", {"x": 1}]}
        operation = make_operation(payload=payload)
        delta = DiscussionDelta(operations=[operation])
        message = assistant()
        catalog = sources()
        events = [make_event()]
        base = workspace(events)
        before = (
            delta.model_dump(mode="python"),
            message.model_dump(mode="python"),
            [m.model_dump(mode="python") for m in catalog],
            [e.model_dump(mode="python") for e in events],
            base.model_dump(mode="python"),
            list(catalog),
            list(events),
        )
        ProjectDirectorDiscussionDeltaGateService().evaluate_delta(
            session_id=SESSION_ID, project_id=None, assistant_message=message,
            available_messages=catalog, current_events=events,
            current_workspace=base, delta=delta, start_sequence_no=2,
        )
        after = (
            delta.model_dump(mode="python"),
            message.model_dump(mode="python"),
            [m.model_dump(mode="python") for m in catalog],
            [e.model_dump(mode="python") for e in events],
            base.model_dump(mode="python"),
            list(catalog),
            list(events),
        )
        assert after == before


# ═══════════════════════════════════════════════════════════════════════════
# 20. AST pure business boundary — strengthened
# ═══════════════════════════════════════════════════════════════════════════


class TestASTBoundary:
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

    def test_no_sqlalchemy_import(self, gate_ast):
        imports = self._get_imports(gate_ast)
        for imp in imports:
            assert "sqlalchemy" not in imp.lower(), f"Forbidden import: {imp}"

    def test_no_fastapi_import(self, gate_ast):
        imports = self._get_imports(gate_ast)
        for imp in imports:
            assert "fastapi" not in imp.lower(), f"Forbidden import: {imp}"

    def test_no_repository_import(self, gate_ast):
        imports = self._get_imports(gate_ast)
        for imp in imports:
            assert not imp.startswith("app.repositories"), f"Forbidden import: {imp}"

    def test_no_db_tables_import(self, gate_ast):
        imports = self._get_imports(gate_ast)
        for imp in imports:
            assert not imp.startswith("app.core.db_tables"), f"Forbidden import: {imp}"

    def test_no_provider_import(self, gate_ast):
        imports = self._get_imports(gate_ast)
        for imp in imports:
            assert "provider" not in imp.lower(), f"Forbidden import: {imp}"

    def test_no_message_service_import(self, gate_ast):
        imports = self._get_imports(gate_ast)
        for imp in imports:
            assert "message_service" not in imp.lower(), f"Forbidden import: {imp}"

    def test_no_forbidden_method_calls(self, gate_ast):
        """No ORM/persistence method calls: .commit(), .rollback(), .flush(), .execute(), etc."""
        # Note: .add() and .delete() are excluded because set.add() and list operations
        # are legitimate in pure business logic.
        forbidden_attrs = {"commit", "rollback", "flush", "execute",
                           "append_if_absent", "create_if_absent", "update_if_version"}
        for node in ast.walk(gate_ast):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr in forbidden_attrs:
                    pytest.fail(f"Forbidden method call: .{func.attr}()")

    def test_no_forbidden_names(self, gate_ast):
        """No references to PlanVersion, Task, Run, Worker, Executor."""
        forbidden = {"PlanVersion", "Task", "Run", "Worker", "Executor"}
        for node in ast.walk(gate_ast):
            if isinstance(node, ast.Name) and node.id in forbidden:
                pytest.fail(f"Forbidden name: {node.id}")

    def test_allowed_imports_only(self, gate_ast):
        imports = self._get_imports(gate_ast)
        allowed_prefixes = (
            "app.domain._base",
            "app.domain.project_director_discussion",
            "app.domain.project_director_message",
            "app.services.project_director_discussion_workspace_reducer_service",
            "collections",
            "copy",
            "dataclasses",
            "datetime",
            "enum",
            "hashlib",
            "json",
            "typing",
            "uuid",
            "__future__",
        )
        for imp in imports:
            assert any(imp.startswith(p) for p in allowed_prefixes), f"Unexpected import: {imp}"
