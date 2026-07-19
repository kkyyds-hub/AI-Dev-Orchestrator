"""Contract tests for P26-D1-A governed DiscussionDelta admission.

These tests exercise the public pure-gate boundary only.  They intentionally
use the real C2 reducer and do not involve persistence, routers, or providers.
"""

from __future__ import annotations

import ast
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


class TestPublicContracts:
    def test_public_types_are_exact_frozen_slot_dataclasses(self):
        assert {member.value for member in DiscussionDeltaGateStatus} == {"prepared", "requires_confirmation"}
        for cls, names in (
            (PreparedDiscussionEvent, {"operation_index", "event", "idempotency_key"}),
            (GovernedDiscussionDeltaResult, {"status", "prepared_events", "projected_workspace", "confirmation_reasons"}),
        ):
            assert is_dataclass(cls)
            assert set(cls.__slots__) == names
            assert {item.name for item in fields(cls)} == names
        result = evaluate(make_operation())
        assert isinstance(result.prepared_events, tuple)
        assert isinstance(result.confirmation_reasons, tuple)
        with pytest.raises(FrozenInstanceError):
            result.prepared_events = ()
        with pytest.raises(FrozenInstanceError):
            result.prepared_events[0].idempotency_key = "changed"


class TestMessageCatalogBoundary:
    def test_assistant_session_and_role_are_rejected(self):
        assert_code("discussion_delta_assistant_message_session_mismatch", lambda: evaluate(make_operation(), assistant_message=assistant(session_id=uuid4())))
        for role in (ProjectDirectorMessageRole.USER, ProjectDirectorMessageRole.SYSTEM):
            assert_code("discussion_delta_assistant_message_role_invalid", lambda role=role: evaluate(make_operation(), assistant_message=make_message(message_id=ASSISTANT_ID, role=role)))

    def test_assistant_is_added_once_or_conflict_is_rejected(self):
        op = make_operation(actor_claim=DiscussionActorClaim.ASSISTANT_PROPOSAL)
        assert evaluate(op).status is DiscussionDeltaGateStatus.PREPARED
        assert evaluate(op, available_messages=sources(include_assistant=True)).status is DiscussionDeltaGateStatus.PREPARED
        conflicted = assistant(content="different")
        assert_code("discussion_delta_assistant_message_conflict", lambda: evaluate(op, available_messages=[conflicted]))

    def test_catalog_duplicate_cross_session_and_missing_sources_are_rejected(self):
        user = make_message(message_id=USER_ID)
        assert_code("discussion_delta_source_message_duplicate", lambda: evaluate(make_operation(), available_messages=[user, user]))
        assert_code("discussion_delta_source_message_session_mismatch", lambda: evaluate(make_operation(), available_messages=[make_message(session_id=uuid4())]))
        assert_code("discussion_delta_source_message_not_found", lambda: evaluate(make_operation(source_message_ids=[uuid4()])))


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
def test_actor_source_roles_and_confidence(actor, message_role, confidence):
    source_id = ASSISTANT_ID if message_role is ProjectDirectorMessageRole.ASSISTANT else USER_ID if message_role is ProjectDirectorMessageRole.USER else SYSTEM_ID
    catalog = [make_message(message_id=source_id, role=message_role)] if source_id != ASSISTANT_ID else []
    operation = make_operation(actor_claim=actor, source_message_ids=[] if actor in {DiscussionActorClaim.SYSTEM_FACT, DiscussionActorClaim.FORMAL_PROJECT_FACT} else [source_id])
    result = evaluate(operation, available_messages=catalog)
    assert result.prepared_events[0].event.confidence == confidence
    if actor is DiscussionActorClaim.FORMAL_PROJECT_FACT:
        assert result.prepared_events[0].event.status is DiscussionEventStatus.CONFIRMED


@pytest.mark.parametrize("actor", [DiscussionActorClaim.USER_EXPLICIT, DiscussionActorClaim.USER_INFERRED, DiscussionActorClaim.ASSISTANT_PROPOSAL])
def test_source_role_mismatch_is_rejected(actor):
    wrong = SYSTEM_ID if actor is not DiscussionActorClaim.ASSISTANT_PROPOSAL else USER_ID
    assert_code("discussion_delta_actor_source_role_mismatch", lambda: evaluate(make_operation(actor_claim=actor, source_message_ids=[wrong])))


class TestOperationMapsAndAuthority:
    @pytest.mark.parametrize(
        ("op", "event_type"),
        list(zip(DiscussionDeltaOperationType, DiscussionEventType, strict=True)),
    )
    def test_all_operations_have_mapped_event_types(self, op, event_type):
        # Additive operations are sufficient to assert each public enum mapping;
        # special operations are covered with their valid target below.
        if op not in {DiscussionDeltaOperationType.SET_TOPIC, DiscussionDeltaOperationType.ADD_OPTION, DiscussionDeltaOperationType.ADD_CONSTRAINT, DiscussionDeltaOperationType.ADD_CONCERN, DiscussionDeltaOperationType.ADD_ASSUMPTION, DiscussionDeltaOperationType.ADD_OPEN_QUESTION, DiscussionDeltaOperationType.ADD_TEMPORARY_CONCLUSION}:
            return
        target = uuid4() if op is DiscussionDeltaOperationType.ADD_OPTION else None
        assert evaluate(make_operation(op=op, target_id=target)).prepared_events[0].event.event_type is event_type

    @pytest.mark.parametrize("actor", list(DiscussionActorClaim))
    @pytest.mark.parametrize("op", [DiscussionDeltaOperationType.SET_TOPIC, DiscussionDeltaOperationType.ADD_OPTION, DiscussionDeltaOperationType.ADD_CONSTRAINT, DiscussionDeltaOperationType.ADD_CONCERN, DiscussionDeltaOperationType.ADD_ASSUMPTION, DiscussionDeltaOperationType.ADD_OPEN_QUESTION, DiscussionDeltaOperationType.ADD_TEMPORARY_CONCLUSION])
    def test_additive_operations_allow_each_actor(self, actor, op):
        target = uuid4() if op is DiscussionDeltaOperationType.ADD_OPTION else None
        assert evaluate(make_operation(op=op, actor_claim=actor, target_id=target)).status is DiscussionDeltaGateStatus.PREPARED

    @pytest.mark.parametrize("actor", [DiscussionActorClaim.USER_EXPLICIT, DiscussionActorClaim.USER_INFERRED, DiscussionActorClaim.ASSISTANT_PROPOSAL])
    def test_option_update_allows_only_its_actor_set(self, actor):
        option_id = UUID("11111111-1111-1111-1111-111111111111")
        old = make_event(
            event_id=UUID("22222222-2222-2222-2222-222222222222"),
            event_type=DiscussionEventType.OPTION_ADDED,
            payload={"option_id": option_id},
        )
        result = evaluate(make_operation(op=DiscussionDeltaOperationType.UPDATE_OPTION, actor_claim=actor, target_id=option_id, supersedes_event_id=old.id), current_events=[old])
        if actor is DiscussionActorClaim.USER_EXPLICIT:
            assert result.status is DiscussionDeltaGateStatus.PREPARED
            assert len(result.prepared_events) == 1
            evt = result.prepared_events[0].event
            assert evt.event_type is DiscussionEventType.OPTION_UPDATED
            assert evt.supersedes_event_id == old.id
            assert evt.payload["option_id"] == option_id
            assert option_id in result.projected_workspace.active_option_ids
            assert result.confirmation_reasons == ()
        else:
            assert result.status is DiscussionDeltaGateStatus.REQUIRES_CONFIRMATION
            assert result.prepared_events == ()
            # UPDATE_OPTION is not user-explicit-only; the reason is inferred supersede
            assert any(r.startswith("discussion_delta_inferred_supersede_confirmation_required:") for r in result.confirmation_reasons)
            # projected workspace equals baseline when confirmation is required
            base_ws = workspace([old])
            assert option_id in base_ws.active_option_ids
            assert result.projected_workspace.active_option_ids == base_ws.active_option_ids

    @pytest.mark.parametrize("actor", [DiscussionActorClaim.SYSTEM_FACT, DiscussionActorClaim.FORMAL_PROJECT_FACT])
    def test_option_update_rejects_authoritative_actors(self, actor):
        option_id = uuid4(); old = make_event(event_type=DiscussionEventType.OPTION_ADDED, payload={"option_id": option_id})
        assert_code("discussion_delta_operation_actor_not_authorized", lambda: evaluate(make_operation(op=DiscussionDeltaOperationType.UPDATE_OPTION, actor_claim=actor, target_id=option_id, supersedes_event_id=old.id), current_events=[old]))

    @pytest.mark.parametrize("op,target_type", [(DiscussionDeltaOperationType.UPDATE_CONSTRAINT, DiscussionEventType.CONSTRAINT_ADDED), (DiscussionDeltaOperationType.SUPERSEDE_CONSTRAINT, DiscussionEventType.CONSTRAINT_ADDED), (DiscussionDeltaOperationType.REJECT_ASSUMPTION, DiscussionEventType.ASSUMPTION_ADDED), (DiscussionDeltaOperationType.RESOLVE_OPEN_QUESTION, DiscussionEventType.OPEN_QUESTION_ADDED)])
    @pytest.mark.parametrize("actor", [DiscussionActorClaim.USER_EXPLICIT, DiscussionActorClaim.SYSTEM_FACT, DiscussionActorClaim.FORMAL_PROJECT_FACT])
    def test_authoritative_operations_allow_only_authority_actors(self, op, target_type, actor):
        old = make_event(event_type=target_type)
        assert evaluate(make_operation(op=op, actor_claim=actor, supersedes_event_id=old.id), current_events=[old]).status is DiscussionDeltaGateStatus.PREPARED


class TestConfirmationAndSupersede:
    @pytest.mark.parametrize("op", [DiscussionDeltaOperationType.PREFER_OPTION, DiscussionDeltaOperationType.REJECT_OPTION, DiscussionDeltaOperationType.RECORD_USER_CORRECTION, DiscussionDeltaOperationType.CONFIRM_DECISION, DiscussionDeltaOperationType.REQUEST_FORMALIZATION, DiscussionDeltaOperationType.CANCEL_FORMALIZATION])
    def test_user_explicit_only_operations_are_atomic_for_other_actors(self, op):
        option_id = uuid4(); target = make_event(event_type=DiscussionEventType.OPTION_ADDED, payload={"option_id": option_id})
        kwargs = {"target_id": option_id} if op in {DiscussionDeltaOperationType.PREFER_OPTION, DiscussionDeltaOperationType.REJECT_OPTION} else {}
        if op is DiscussionDeltaOperationType.CANCEL_FORMALIZATION:
            target = make_event(event_type=DiscussionEventType.FORMALIZATION_REQUESTED)
            kwargs["supersedes_event_id"] = target.id
        result = evaluate(make_operation(op=op, actor_claim=DiscussionActorClaim.ASSISTANT_PROPOSAL, **kwargs), current_events=[target])
        assert result.status is DiscussionDeltaGateStatus.REQUIRES_CONFIRMATION
        assert result.prepared_events == ()
        assert result.confirmation_reasons[0] == "discussion_delta_user_confirmation_required:0"

    def test_confirmation_returns_unchanged_baseline_and_stable_reasons(self):
        base = workspace([])
        op0 = make_operation(op=DiscussionDeltaOperationType.ADD_CONCERN, content="a")
        op1 = make_operation(op=DiscussionDeltaOperationType.CONFIRM_DECISION, actor_claim=DiscussionActorClaim.ASSISTANT_PROPOSAL, content="b")
        op2 = make_operation(op=DiscussionDeltaOperationType.ADD_CONCERN, content="c")
        result = evaluate(op0, op1, op2, current_workspace=base)
        assert result.status is DiscussionDeltaGateStatus.REQUIRES_CONFIRMATION
        assert result.prepared_events == () and result.projected_workspace == base
        assert result.confirmation_reasons == ("discussion_delta_user_confirmation_required:1",)

    def test_supersede_not_found_not_effective_inferred_confirmed_and_formal_boundaries(self):
        missing = uuid4()
        assert_code("discussion_delta_supersedes_target_not_found", lambda: evaluate(make_operation(supersedes_event_id=missing)))
        inactive = make_event(status=DiscussionEventStatus.REJECTED)
        assert_code("discussion_delta_supersedes_target_not_effective", lambda: evaluate(make_operation(supersedes_event_id=inactive.id), current_events=[inactive]))
        topic = make_event(created_by=DiscussionActorClaim.USER_EXPLICIT, source_message_ids=[USER_ID])
        inferred = make_operation(actor_claim=DiscussionActorClaim.USER_INFERRED, supersedes_event_id=topic.id)
        result = evaluate(inferred, current_events=[topic])
        assert result.status is DiscussionDeltaGateStatus.REQUIRES_CONFIRMATION
        assert result.confirmation_reasons == ("discussion_delta_inferred_supersede_confirmation_required:0", "discussion_delta_confirmed_fact_confirmation_required:0")
        formal = make_event(created_by=DiscussionActorClaim.FORMAL_PROJECT_FACT)
        assert_code("discussion_delta_formal_project_fact_conflict", lambda: evaluate(make_operation(supersedes_event_id=formal.id), current_events=[formal]))


class TestNormalizationAndDeterminism:
    @pytest.mark.parametrize("op", [DiscussionDeltaOperationType.ADD_OPTION, DiscussionDeltaOperationType.UPDATE_OPTION, DiscussionDeltaOperationType.PREFER_OPTION, DiscussionDeltaOperationType.REJECT_OPTION])
    def test_option_target_payload_is_normalized_without_mutation(self, op):
        option_id = uuid4(); payload = {"option_id": str(option_id), "nested": {"items": ["中文"]}}
        old = make_event(event_type=DiscussionEventType.OPTION_ADDED, payload={"option_id": option_id})
        operation = make_operation(op=op, target_id=option_id, payload=payload, supersedes_event_id=old.id if op is DiscussionDeltaOperationType.UPDATE_OPTION else None)
        result = evaluate(operation, current_events=[old] if op is not DiscussionDeltaOperationType.ADD_OPTION else [])
        assert result.prepared_events[0].event.payload["option_id"] == option_id
        assert payload["option_id"] == str(option_id)

    def test_target_conflicts_subject_default_and_duplicate_canonical_hash_are_enforced(self):
        target = uuid4()
        assert_code("discussion_delta_option_target_required", lambda: evaluate(make_operation(op=DiscussionDeltaOperationType.ADD_OPTION)))
        assert_code("discussion_delta_option_id_conflict", lambda: evaluate(make_operation(op=DiscussionDeltaOperationType.ADD_OPTION, target_id=target, payload={"option_id": uuid4()})))
        result = evaluate(make_operation(subject_key="  custom-key  "))
        assert result.prepared_events[0].event.subject_key == "custom-key"
        default = evaluate(make_operation(op=DiscussionDeltaOperationType.ADD_OPTION, target_id=target)).prepared_events[0].event.subject_key
        assert default == f"option:{target}"
        assert_code("discussion_delta_duplicate_operation", lambda: evaluate(make_operation(payload={"a": 1, "b": 2}), make_operation(payload={"b": 2, "a": 1})))

    def test_ids_keys_times_sequences_and_p27_fields_are_deterministic(self):
        op = make_operation(payload={"source_surface": "not-promoted"})
        first = evaluate(op); second = evaluate(op)
        first_item, second_item = first.prepared_events[0], second.prepared_events[0]
        assert first_item.event.id == second_item.event.id
        assert first_item.idempotency_key == second_item.idempotency_key
        assert first_item.idempotency_key.startswith(f"p26-d1:{ASSISTANT_ID.hex}:0:")
        assert len(first_item.idempotency_key.rsplit(":", 1)[1]) == 64
        assert first_item.event.created_at == FIXED_TIME
        assert all(getattr(first_item.event, name) is None for name in ("source_surface", "source_entity_type", "source_entity_id", "trigger_type", "interaction_case_id", "external_context_pack_id"))
        history = [make_event(sequence_no=9), make_event(sequence_no=2), make_event(sequence_no=4)]
        multi = evaluate(make_operation(content="one"), make_operation(content="two"), current_events=history, start_sequence_no=10)
        assert [item.event.sequence_no for item in multi.prepared_events] == [10, 11]
        assert_code("discussion_delta_start_sequence_mismatch", lambda: evaluate(make_operation(), start_sequence_no=2))


class TestWorkspaceReducerReuseAndPurity:
    def test_projection_matches_real_reducer_and_empty_delta_is_unchanged(self):
        option_id = uuid4()
        operations = (make_operation(op=DiscussionDeltaOperationType.ADD_OPTION, target_id=option_id), make_operation(op=DiscussionDeltaOperationType.PREFER_OPTION, target_id=option_id))
        result = evaluate(*operations)
        direct = ProjectDirectorDiscussionWorkspaceReducerService().rebuild_workspace(session_id=SESSION_ID, project_id=None, events=[item.event for item in result.prepared_events], version_no=0, created_at=FIXED_TIME, updated_at=FIXED_TIME)
        assert result.projected_workspace.active_option_ids == direct.active_option_ids
        assert result.projected_workspace.preferred_option_id == option_id
        base = workspace([])
        empty = evaluate(current_workspace=base)
        assert empty.status is DiscussionDeltaGateStatus.PREPARED
        assert empty.prepared_events == () and empty.projected_workspace == base

    def test_workspace_and_inputs_are_not_mutated(self):
        payload = {"nested": ["中文", {"x": 1}]}
        operation = make_operation(payload=payload)
        delta = DiscussionDelta(operations=[operation])
        message = assistant(); catalog = sources(); events = [make_event()]
        base = workspace(events)
        before = (delta.model_dump(mode="python"), message.model_dump(mode="python"), [item.model_dump(mode="python") for item in catalog], [item.model_dump(mode="python") for item in events], base.model_dump(mode="python"), list(catalog), list(events))
        ProjectDirectorDiscussionDeltaGateService().evaluate_delta(session_id=SESSION_ID, project_id=None, assistant_message=message, available_messages=catalog, current_events=events, current_workspace=base, delta=delta, start_sequence_no=2)
        after = (delta.model_dump(mode="python"), message.model_dump(mode="python"), [item.model_dump(mode="python") for item in catalog], [item.model_dump(mode="python") for item in events], base.model_dump(mode="python"), list(catalog), list(events))
        assert after == before

    def test_gate_module_ast_is_pure_business_boundary(self):
        path = Path(__file__).parents[1] / "app/services/project_director_discussion_delta_gate_service.py"
        tree = ast.parse(path.read_text())
        forbidden_import_roots = {"sqlalchemy", "fastapi", "provider"}
        forbidden_import_prefixes = ("app.repositories", "app.core.db_tables")
        forbidden_names = {"commit", "rollback", "flush", "append_if_absent", "create_if_absent", "update_if_version", "sqlite_immediate_transaction", "PlanVersion", "Task", "Run", "Worker", "Executor"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name.split(".")[0] not in forbidden_import_roots and not alias.name.startswith(forbidden_import_prefixes) for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in forbidden_import_roots
                assert not node.module.startswith(forbidden_import_prefixes)
            if isinstance(node, ast.Name):
                assert node.id not in forbidden_names
