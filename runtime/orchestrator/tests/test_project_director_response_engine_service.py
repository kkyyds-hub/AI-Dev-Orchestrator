"""Contract tests for P26-F1-A provider-first natural response generation."""

from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import fields, is_dataclass, replace
from datetime import datetime, timezone
import inspect
import json
from pathlib import Path
from typing import get_type_hints
from uuid import UUID, uuid4

import pytest

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
)
from app.services.project_director_discussion_context_builder_service import (
    ActiveDiscussionWorkspaceContext,
    DiscussionContextAssembly,
    PinnedDiscussionFormalFacts,
    ResolvedDiscussionContextEvent,
)
from app.services.project_director_discussion_context_planner_service import (
    DiscussionContextPlan,
    DiscussionContextSection,
    DiscussionRetrievalDisposition,
    FormalFactContextScope,
)
from app.services.project_director_response_engine_service import (
    ProviderTextGenerator,
    ProjectDirectorResponseEngineService,
)


SESSION_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_SESSION_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
PROJECT_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
OTHER_PROJECT_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
CURRENT_USER_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
RECENT_USER_ID = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
RECENT_ASSISTANT_ID = UUID("11111111-1111-1111-1111-111111111111")
RESERVED_ASSISTANT_ID = UUID("22222222-2222-2222-2222-222222222222")
ACTIVE_EVENT_ID = UUID("33333333-3333-3333-3333-333333333333")
RELEVANT_EVENT_ID = UUID("44444444-4444-4444-4444-444444444444")
UNKNOWN_ID = UUID("55555555-5555-5555-5555-555555555555")
FIXED_TIME = datetime(2026, 7, 20, 8, 30, tzinfo=timezone.utc)


class RecordingProvider:
    """A deterministic provider spy with configurable output or failure."""

    def __init__(
        self,
        *,
        output: str = "",
        receipt: str | None = "receipt-001",
        error: Exception | None = None,
    ) -> None:
        self.output = output
        self.receipt = receipt
        self.error = error
        self.calls: list[tuple[str, str, str]] = []

    def __call__(self, model_name: str, prompt_text: str, request_id: str) -> tuple[str, str | None]:
        self.calls.append((model_name, prompt_text, request_id))
        if self.error is not None:
            raise self.error
        return self.output, self.receipt


class SequenceRecordingProvider:
    """Deterministic direct/repair Provider spy for the F8 envelope path."""

    def __init__(self, responses: list[tuple[str, str | None]]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str, str, str | None]] = []

    def __call__(self, model_name: str, prompt_text: str, request_id: str) -> tuple[str, str | None]:
        if not self._responses:
            raise AssertionError("unexpected provider call")
        output, receipt = self._responses.pop(0)
        self.calls.append((model_name, prompt_text, request_id, receipt))
        return output, receipt


def make_interpretation(
    mode: ConversationMode = ConversationMode.GENERAL_DISCUSSION,
    **overrides: object,
) -> TurnInterpretation:
    values: dict[str, object] = {
        "conversation_mode": mode,
        "primary_intent": "discuss_current_topic",
        "confidence": 0.8,
        "formal_action_requested": False,
        "hypothetical_action": False,
        "referenced_option_ids": [],
        "referenced_entity_ids": [],
        "needs_formal_fact_context": False,
        "needs_discussion_history": False,
        "needs_retrieval": False,
        "reason_summary": "fixed test interpretation",
    }
    values.update(overrides)
    return TurnInterpretation(**values)


def make_message(
    *,
    message_id: UUID,
    role: ProjectDirectorMessageRole,
    sequence_no: int,
    session_id: UUID = SESSION_ID,
    project_id: UUID | None = PROJECT_ID,
    content: str = "message",
) -> ProjectDirectorMessage:
    return ProjectDirectorMessage(
        id=message_id,
        session_id=session_id,
        role=role,
        content=content,
        sequence_no=sequence_no,
        related_project_id=project_id,
        intent="internal_intent",
        source_detail="internal_source_detail",
        suggested_actions=[{"kind": "internal"}],
        requires_confirmation=True,
        forbidden_actions_detected=["internal_boundary"],
        created_at=FIXED_TIME,
    )


def make_event(
    *,
    event_id: UUID,
    sequence_no: int,
    event_type: DiscussionEventType,
    session_id: UUID = SESSION_ID,
    project_id: UUID | None = PROJECT_ID,
    source_message_ids: list[UUID] | None = None,
    **overrides: object,
) -> DiscussionEvent:
    values: dict[str, object] = {
        "id": event_id,
        "session_id": session_id,
        "project_id": project_id,
        "sequence_no": sequence_no,
        "event_type": event_type,
        "subject_key": "subject",
        "content": "event content",
        "status": DiscussionEventStatus.ACTIVE,
        "payload": {"nested": {"value": "benign"}},
        "source_message_ids": source_message_ids or [],
        "supersedes_event_id": None,
        "created_by": DiscussionActorClaim.SYSTEM_FACT,
        "confidence": 1.0,
        "created_at": FIXED_TIME,
        "source_surface": "reserved_surface",
        "source_entity_type": "reserved_type",
        "source_entity_id": UNKNOWN_ID,
        "trigger_type": "reserved_trigger",
        "interaction_case_id": UNKNOWN_ID,
        "external_context_pack_id": UNKNOWN_ID,
    }
    values.update(overrides)
    return DiscussionEvent(**values)


def make_context(
    interpretation: TurnInterpretation,
    *,
    with_workspace: bool = True,
    project_id: UUID | None = PROJECT_ID,
    recent_messages: tuple[ProjectDirectorMessage, ...] | None = None,
) -> DiscussionContextAssembly:
    selected_sections = (
        DiscussionContextSection.PINNED_FORMAL_FACTS,
        DiscussionContextSection.RECENT_RAW_MESSAGES,
        DiscussionContextSection.ACTIVE_DISCUSSION_WORKSPACE,
        DiscussionContextSection.RELEVANT_DISCUSSION_EVENTS,
        DiscussionContextSection.CURRENT_USER_MESSAGE,
        DiscussionContextSection.SILENT_GOVERNANCE_BOUNDARIES,
    )
    plan = DiscussionContextPlan(
        conversation_mode=interpretation.conversation_mode,
        selected_sections=selected_sections,
        formal_fact_scope=FormalFactContextScope.CORE_AND_PLAN,
        recent_message_limit=12,
        relevant_event_limit=40,
        included_event_statuses=(
            DiscussionEventStatus.ACTIVE,
            DiscussionEventStatus.CONFIRMED,
        ),
        included_event_types=(
            DiscussionEventType.TOPIC_SET,
            DiscussionEventType.CONCERN_ADDED,
        ),
        referenced_option_ids=tuple(interpretation.referenced_option_ids),
        referenced_entity_ids=tuple(interpretation.referenced_entity_ids),
        retrieval_disposition=DiscussionRetrievalDisposition.NOT_REQUIRED,
        reason_codes=("baseline_sections_required",),
    )
    facts = PinnedDiscussionFormalFacts(
        scope=FormalFactContextScope.CORE_AND_PLAN,
        session_id=SESSION_ID,
        project_id=project_id,
        goal_text="fixed goal",
        constraints="fixed constraints",
        session_status="clarifying",
        goal_summary="fixed goal summary",
        confirmed_at=None,
        latest_plan_version={"summary": "plan"},
        task_creation=None,
        project_snapshot=None,
        task_snapshot=None,
    )
    current_user = make_message(
        message_id=CURRENT_USER_ID,
        role=ProjectDirectorMessageRole.USER,
        sequence_no=3,
        project_id=project_id,
        content="current user message",
    )
    recent = recent_messages or (
        make_message(
            message_id=RECENT_USER_ID,
            role=ProjectDirectorMessageRole.USER,
            sequence_no=1,
            project_id=project_id,
            content="recent user message",
        ),
        make_message(
            message_id=RECENT_ASSISTANT_ID,
            role=ProjectDirectorMessageRole.ASSISTANT,
            sequence_no=2,
            project_id=project_id,
            content="recent assistant message",
        ),
    )
    if not with_workspace:
        return DiscussionContextAssembly(
            plan=plan,
            pinned_formal_facts=facts,
            recent_raw_messages=recent,
            active_workspace=None,
            relevant_events=(),
            current_user_message=current_user,
            silent_governance_boundaries=("internal boundary one", "internal boundary two"),
        )

    active_event = make_event(
        event_id=ACTIVE_EVENT_ID,
        sequence_no=1,
        event_type=DiscussionEventType.TOPIC_SET,
        project_id=project_id,
    )
    relevant_event = make_event(
        event_id=RELEVANT_EVENT_ID,
        sequence_no=2,
        event_type=DiscussionEventType.CONCERN_ADDED,
        project_id=project_id,
    )
    workspace = DiscussionWorkspace(
        session_id=SESSION_ID,
        project_id=project_id,
        topic="event content",
        discussion_status=DiscussionStatus.EXPLORING,
        version_no=7,
        last_event_sequence_no=2,
    )
    return DiscussionContextAssembly(
        plan=plan,
        pinned_formal_facts=facts,
        recent_raw_messages=recent,
        active_workspace=ActiveDiscussionWorkspaceContext(
            workspace=workspace, active_events=(active_event,)
        ),
        relevant_events=(
            ResolvedDiscussionContextEvent(
                event=relevant_event, resolved_status=DiscussionEventStatus.ACTIVE
            ),
        ),
        current_user_message=current_user,
        silent_governance_boundaries=("internal boundary one", "internal boundary two"),
    )


def provider_envelope(
    interpretation: TurnInterpretation,
    *,
    answer: str = "natural response",
    operations: list[dict[str, object]] | None = None,
    proposal: dict[str, object] | None = None,
    requires_confirmation: bool = False,
    source: str = "provider",
    source_detail: str = "provider claimed detail",
) -> str:
    return json.dumps(
        {
            "answer": answer,
            "turn_interpretation": interpretation.model_dump(mode="json"),
            "discussion_delta": {"operations": operations or []},
            "formalization_proposal": proposal,
            "requires_confirmation": requires_confirmation,
            "source": source,
            "source_detail": source_detail,
        }
    )


def operation(
    *,
    actor_claim: DiscussionActorClaim,
    source_ids: list[UUID],
    supersedes_event_id: UUID | None = None,
) -> dict[str, object]:
    return {
        "op": "add_concern",
        "content": "candidate concern",
        "payload": {},
        "source_message_ids": [str(item) for item in source_ids],
        "actor_claim": actor_claim.value,
        "supersedes_event_id": (
            str(supersedes_event_id) if supersedes_event_id is not None else None
        ),
    }


def rejected_option_context(interpretation: TurnInterpretation) -> tuple[DiscussionContextAssembly, UUID, UUID]:
    """Expose one visible historical A rejection and active B for provider preflight."""
    option_a, option_b, rejection_id = uuid4(), uuid4(), uuid4()
    added_a = make_event(
        event_id=uuid4(), sequence_no=1, event_type=DiscussionEventType.OPTION_ADDED,
        payload={"option_id": str(option_a)}, subject_key=f"option:{option_a}",
    )
    added_b = make_event(
        event_id=uuid4(), sequence_no=2, event_type=DiscussionEventType.OPTION_ADDED,
        payload={"option_id": str(option_b)}, subject_key=f"option:{option_b}",
    )
    rejected_a = make_event(
        event_id=rejection_id, sequence_no=3, event_type=DiscussionEventType.OPTION_REJECTED,
        payload={"option_id": str(option_a)}, subject_key=f"option:{option_a}",
    )
    preferred_b = make_event(
        event_id=uuid4(), sequence_no=4, event_type=DiscussionEventType.OPTION_PREFERRED,
        payload={"option_id": str(option_b)}, subject_key=f"option:{option_b}",
    )
    context = make_context(interpretation)
    workspace = context.active_workspace.workspace.model_copy(update={
        "active_option_ids": [option_b],
        "preferred_option_id": option_b,
        "last_event_sequence_no": 4,
    })
    return replace(
        context,
        active_workspace=ActiveDiscussionWorkspaceContext(
            workspace=workspace,
            active_events=(added_a, added_b, rejected_a, preferred_b),
        ),
    ), option_a, rejection_id


def assert_fallback(result, interpretation: TurnInterpretation, reason: str) -> None:
    assert result.source.value == "rule_fallback"
    assert result.turn_interpretation.model_dump(mode="python") == interpretation.model_dump(
        mode="python"
    )
    assert result.discussion_delta.operations == []
    assert result.formalization_proposal is None


def assert_direct_fallback(result, interpretation: TurnInterpretation, reason: str) -> None:
    assert_fallback(result, interpretation, reason)
    assert result.source_detail == f"p26_f1_rule_fallback;attempt=direct;reason={reason}"


def assert_repair_fallback(result, interpretation: TurnInterpretation, reason: str) -> None:
    assert_fallback(result, interpretation, reason)
    assert result.source_detail == f"p26_f1_rule_fallback;attempt=repair;reason=provider_repair_failed:{reason}"


def call(
    provider: RecordingProvider | None,
    context: DiscussionContextAssembly,
    interpretation: TurnInterpretation,
    assistant_id: UUID = RESERVED_ASSISTANT_ID,
):
    return ProjectDirectorResponseEngineService(
        provider_text_generator=provider
    ).generate_response(
        context=context,
        interpretation=interpretation,
        assistant_message_id=assistant_id,
        model_name="fixed-model",
        request_id="fixed-request",
    )


class TestPublicContracts:
    def test_provider_type_and_service_signatures(self):
        assert str(ProviderTextGenerator) == "collections.abc.Callable[[str, str, str], tuple[str, str | None]]"
        assert not is_dataclass(ProjectDirectorResponseEngineService)
        assert list(inspect.signature(ProjectDirectorResponseEngineService.__init__).parameters) == [
            "self",
            "provider_text_generator",
        ]
        assert list(inspect.signature(ProjectDirectorResponseEngineService.generate_response).parameters) == [
            "self",
            "context",
            "interpretation",
            "assistant_message_id",
            "model_name",
            "request_id",
        ]
        assert get_type_hints(ProjectDirectorResponseEngineService.generate_response)["return"].__name__ == "DirectorResponseEnvelope"


@pytest.mark.parametrize("model_name", ["", " ", "\n", None, 1])
def test_invalid_model_fails_closed_without_provider(model_name):
    interpretation = make_interpretation()
    context = make_context(interpretation)
    provider = RecordingProvider(output=provider_envelope(interpretation))
    with pytest.raises(ValueError, match="^director_response_model_name_invalid$"):
        ProjectDirectorResponseEngineService(provider_text_generator=provider).generate_response(
            context=context, interpretation=interpretation,
            assistant_message_id=RESERVED_ASSISTANT_ID,
            model_name=model_name, request_id="request",
        )
    assert provider.calls == []


@pytest.mark.parametrize("request_id", ["", " ", "\n", None, 1])
def test_invalid_request_fails_closed_without_provider(request_id):
    interpretation = make_interpretation()
    context = make_context(interpretation)
    provider = RecordingProvider(output=provider_envelope(interpretation))
    with pytest.raises(ValueError, match="^director_response_request_id_invalid$"):
        ProjectDirectorResponseEngineService(provider_text_generator=provider).generate_response(
            context=context, interpretation=interpretation,
            assistant_message_id=RESERVED_ASSISTANT_ID,
            model_name="model", request_id=request_id,
        )
    assert provider.calls == []


@pytest.mark.parametrize(
    ("context_factory", "code"),
    [
        (
            lambda interpretation: replace(
                make_context(interpretation),
                current_user_message=make_message(
                    message_id=CURRENT_USER_ID,
                    role=ProjectDirectorMessageRole.ASSISTANT,
                    sequence_no=3,
                ),
            ),
            "director_response_current_message_role_invalid",
        ),
        (
            lambda interpretation: replace(
                make_context(interpretation),
                pinned_formal_facts=replace(
                    make_context(interpretation).pinned_formal_facts,
                    session_id=OTHER_SESSION_ID,
                ),
            ),
            "director_response_context_session_mismatch",
        ),
        (
            lambda interpretation: replace(
                make_context(interpretation),
                active_workspace=replace(
                    make_context(interpretation).active_workspace,
                    workspace=make_context(interpretation).active_workspace.workspace.model_copy(
                        update={
                            "session_id": OTHER_SESSION_ID,
                        }
                    ),
                ),
            ),
            "director_response_context_session_mismatch",
        ),
        (
            lambda interpretation: replace(
                make_context(interpretation),
                pinned_formal_facts=replace(
                    make_context(interpretation).pinned_formal_facts,
                    project_id=OTHER_PROJECT_ID,
                ),
            ),
            "director_response_context_project_mismatch",
        ),
        (
            lambda interpretation: replace(
                make_context(interpretation),
                active_workspace=replace(
                    make_context(interpretation).active_workspace,
                    workspace=make_context(interpretation).active_workspace.workspace.model_copy(
                        update={
                            "project_id": None,
                        }
                    ),
                ),
            ),
            "director_response_context_project_mismatch",
        ),
        (
            lambda interpretation: replace(
                make_context(interpretation),
                plan=replace(
                    make_context(interpretation).plan,
                    conversation_mode=ConversationMode.STATUS_QUERY,
                ),
            ),
            "director_response_interpretation_mode_mismatch",
        ),
    ],
)
def test_context_contract_errors_fail_closed_without_provider(context_factory, code):
    interpretation = make_interpretation()
    context = context_factory(interpretation)
    provider = RecordingProvider(output=provider_envelope(interpretation))
    with pytest.raises(ValueError, match=f"^{code}$"):
        call(provider, context, interpretation)
    assert provider.calls == []


@pytest.mark.parametrize(
    "plan_option_ids,interpretation_option_ids,plan_entity_ids,interpretation_entity_ids",
    [
        ((ACTIVE_EVENT_ID,), (RELEVANT_EVENT_ID,), (), ()),
        ((ACTIVE_EVENT_ID, RELEVANT_EVENT_ID), (RELEVANT_EVENT_ID, ACTIVE_EVENT_ID), (), ()),
        ((), (), (ACTIVE_EVENT_ID,), (RELEVANT_EVENT_ID,)),
        ((), (), (ACTIVE_EVENT_ID, RELEVANT_EVENT_ID), (RELEVANT_EVENT_ID, ACTIVE_EVENT_ID)),
    ],
)
def test_reference_contract_including_order_fails_closed(
    plan_option_ids, interpretation_option_ids, plan_entity_ids, interpretation_entity_ids
):
    interpretation = make_interpretation(
        referenced_option_ids=list(interpretation_option_ids),
        referenced_entity_ids=list(interpretation_entity_ids),
    )
    context = make_context(interpretation)
    context = replace(
        context,
        plan=replace(
            context.plan,
            referenced_option_ids=plan_option_ids,
            referenced_entity_ids=plan_entity_ids,
        ),
    )
    provider = RecordingProvider(output=provider_envelope(interpretation))
    with pytest.raises(ValueError, match="^director_response_interpretation_references_mismatch$"):
        call(provider, context, interpretation)
    assert provider.calls == []


@pytest.mark.parametrize("assistant_id", [CURRENT_USER_ID, RECENT_USER_ID, RECENT_ASSISTANT_ID])
def test_reserved_assistant_id_conflict_fails_closed(assistant_id):
    interpretation = make_interpretation()
    context = make_context(interpretation)
    provider = RecordingProvider(output=provider_envelope(interpretation))
    with pytest.raises(ValueError, match="^director_response_assistant_message_id_conflict$"):
        call(provider, context, interpretation, assistant_id)
    assert provider.calls == []


def test_prompt_is_deterministic_complete_and_whitelisted():
    interpretation = make_interpretation(needs_discussion_history=True)
    context = make_context(interpretation)
    provider_a = RecordingProvider(output=provider_envelope(interpretation))
    provider_b = RecordingProvider(output=provider_envelope(interpretation))
    call(provider_a, context, interpretation)
    call(provider_a, context, interpretation)
    call(provider_b, context, interpretation)
    assert len(provider_a.calls) == 2
    assert provider_a.calls[0] == provider_a.calls[1]
    assert provider_a.calls[0][1] == provider_b.calls[0][1]

    prompt = json.loads(provider_a.calls[0][1])
    assert set(prompt) == {
        "behavior_instructions", "output_schema", "discussion_delta_operation_contract",
        "source_id_rules", "silent_governance_instruction", "context",
    }
    assert set(prompt["context"]) == {
        "pinned_formal_facts", "recent_raw_messages", "active_workspace",
        "relevant_events", "current_user_message", "silent_governance_boundaries",
        "discussion_context_plan", "caller_interpretation",
        "reserved_assistant_message_id", "expected_workspace_version_after_this_turn",
    }
    assert prompt["context"]["reserved_assistant_message_id"] == str(RESERVED_ASSISTANT_ID)
    assert prompt["context"]["caller_interpretation"] == interpretation.model_dump(mode="json")
    assert prompt["context"]["discussion_context_plan"]["conversation_mode"] == interpretation.conversation_mode.value
    assert "only an explicit formalization request" in " ".join(prompt["behavior_instructions"]).lower()
    assert prompt["source_id_rules"]["forbidden_actor_claims"] == [
        "system_fact", "formal_project_fact"
    ]
    for event in (
        *prompt["context"]["active_workspace"]["active_events"],
        *prompt["context"]["relevant_events"],
    ):
        assert not {
            "source_surface", "source_entity_type", "source_entity_id",
            "trigger_type", "interaction_case_id", "external_context_pack_id",
        } & set(event)
    assert set(prompt["context"]["active_workspace"]["active_events"][0]) == {
        "id", "session_id", "project_id", "sequence_no", "event_type",
        "subject_key", "content", "status", "payload", "source_message_ids",
        "supersedes_event_id", "created_by", "confidence", "created_at",
    }
    assert set(prompt["context"]["relevant_events"][0]) == {
        "id", "session_id", "project_id", "sequence_no", "event_type",
        "subject_key", "content", "resolved_status", "payload", "source_message_ids",
        "supersedes_event_id", "created_by", "confidence", "created_at",
    }
    expected_message_keys = {
        "id", "session_id", "role", "content", "sequence_no",
        "related_project_id", "created_at",
    }
    for message in (
        *prompt["context"]["recent_raw_messages"],
        prompt["context"]["current_user_message"],
    ):
        assert set(message) == expected_message_keys


@pytest.mark.parametrize(
    ("output", "reason"),
    [
        ("not json", "provider_response_not_json"),
        ("[]", "provider_response_not_object"),
        ('"text"', "provider_response_not_object"),
        ('{"answer":"missing fields"}', "provider_envelope_invalid"),
    ],
)
def test_provider_parsing_failures_fallback_once(output, reason):
    interpretation = make_interpretation()
    provider = RecordingProvider(output=output)
    result = call(provider, make_context(interpretation), interpretation)
    # v2025.07-t3: parsing failures trigger one repair attempt before fallback
    assert len(provider.calls) == 2
    assert_repair_fallback(result, interpretation, reason)


def test_fenced_json_success_and_source_detail_receipt_normalization():
    interpretation = make_interpretation()
    raw = provider_envelope(interpretation)
    fence = chr(96) * 3
    provider = RecordingProvider(
        output=f"{fence}json\n{raw}\n{fence}",
        receipt=" " + "r" * 130 + " ",
    )
    result = call(provider, make_context(interpretation), interpretation)
    assert result.source.value == "provider"
    assert result.source_detail == "p26_f1_provider_response;attempt=direct;receipt=" + "r" * 120
    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    ("provider", "reason"),
    [
        (None, "provider_unavailable"),
        (RecordingProvider(error=RuntimeError("provider failed")), "provider_failed"),
        (RecordingProvider(output=""), "provider_empty_output"),
    ],
)
def test_provider_unavailable_and_failures_are_safe(provider, reason):
    interpretation = make_interpretation()
    result = call(provider, make_context(interpretation), interpretation)
    assert_direct_fallback(result, interpretation, reason)
    if provider is not None:
        assert len(provider.calls) == 1


def test_provider_self_claimed_rule_fallback_is_not_accepted_as_success():
    interpretation = make_interpretation()
    provider = RecordingProvider(output=provider_envelope(
        interpretation, source="rule_fallback"
    ))
    result = call(provider, make_context(interpretation), interpretation)
    assert_direct_fallback(result, interpretation, "provider_source_invalid")
    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    "mutate",
    [
        lambda raw: raw.pop("answer"),
        lambda raw: raw.update({"answer": ""}),
        lambda raw: raw.pop("turn_interpretation"),
        lambda raw: raw["turn_interpretation"].update({"conversation_mode": "invalid"}),
        lambda raw: raw["discussion_delta"].update({
            "operations": [{
                "op": "add_concern", "content": "x", "payload": {},
                "source_message_ids": [str(CURRENT_USER_ID)],
                "actor_claim": "invalid",
            }]
        }),
        lambda raw: raw.pop("source"),
        lambda raw: raw.pop("source_detail"),
        lambda raw: raw.update({
            "formalization_proposal": make_proposal(),
            "requires_confirmation": False,
        }),
    ],
)
def test_domain_invalid_provider_outputs_fallback(mutate):
    interpretation = make_interpretation()
    raw = json.loads(provider_envelope(interpretation))
    mutate(raw)
    provider = RecordingProvider(output=json.dumps(raw))
    result = call(provider, make_context(interpretation), interpretation)
    # v2025.07-t3: envelope validation failures trigger one repair attempt
    assert_repair_fallback(result, interpretation, "provider_envelope_invalid")
    assert len(provider.calls) == 2


@pytest.mark.parametrize(
    "change",
    [
        {"conversation_mode": "status_query"},
        {"primary_intent": "other"},
        {"confidence": 0.2},
        {"formal_action_requested": True},
        {"hypothetical_action": True},
        {"referenced_option_ids": [str(ACTIVE_EVENT_ID)]},
        {"referenced_entity_ids": [str(ACTIVE_EVENT_ID)]},
        {"needs_formal_fact_context": True},
        {"needs_discussion_history": True},
        {"needs_retrieval": True},
        {"reason_summary": "other reason"},
    ],
)
def test_any_interpretation_difference_falls_back(change):
    interpretation = make_interpretation()
    returned = interpretation.model_dump(mode="json")
    returned.update(change)
    raw = json.loads(provider_envelope(interpretation))
    raw["turn_interpretation"] = returned
    provider = RecordingProvider(output=json.dumps(raw))
    result = call(provider, make_context(interpretation), interpretation)
    # v2025.07-t3: interpretation mismatch triggers one repair attempt
    assert_repair_fallback(result, interpretation, "provider_interpretation_mismatch")
    assert len(provider.calls) == 2


@pytest.mark.parametrize("claim", [
    "已创建任务", "已经创建任务", "已启动 Worker", "已经启动 Worker",
    "已启动 Codex", "已启动 Claude Code", "已修改正式计划", "已经修改正式计划",
    "已应用计划", "已创建 PlanVersion", "已写入仓库", "已提交代码",
    "已推送代码", "已部署", "已发布",
])
def test_forbidden_completion_claims_fallback(claim):
    interpretation = make_interpretation()
    provider = RecordingProvider(output=provider_envelope(interpretation, answer=f"系统{claim}。"))
    result = call(provider, make_context(interpretation), interpretation)
    assert_direct_fallback(result, interpretation, "provider_forbidden_execution_claim")


@pytest.mark.parametrize(
    "answer",
    ["还没有创建任务", "是否创建任务需要进一步确认", "可以讨论部署方案", "并未写入仓库"],
)
def test_safe_negative_completion_phrases_are_accepted(answer):
    interpretation = make_interpretation()
    provider = RecordingProvider(output=provider_envelope(interpretation, answer=answer))
    result = call(provider, make_context(interpretation), interpretation)
    assert result.source.value == "provider"


@pytest.mark.parametrize(
    ("actor", "sources", "reason"),
    [
        (DiscussionActorClaim.USER_EXPLICIT, [], "provider_envelope_invalid"),
        (DiscussionActorClaim.USER_EXPLICIT, [RESERVED_ASSISTANT_ID], "provider_delta_user_source_invalid"),
        (DiscussionActorClaim.USER_INFERRED, [RECENT_ASSISTANT_ID], "provider_delta_user_source_invalid"),
        (DiscussionActorClaim.USER_EXPLICIT, [UNKNOWN_ID], "provider_delta_user_source_invalid"),
        (DiscussionActorClaim.ASSISTANT_PROPOSAL, [], "provider_envelope_invalid"),
        (DiscussionActorClaim.ASSISTANT_PROPOSAL, [RECENT_ASSISTANT_ID], "provider_delta_assistant_source_invalid"),
        (DiscussionActorClaim.ASSISTANT_PROPOSAL, [RESERVED_ASSISTANT_ID, CURRENT_USER_ID], "provider_delta_assistant_source_invalid"),
    ],
)
def test_delta_source_validation(actor, sources, reason):
    interpretation = make_interpretation()
    provider = RecordingProvider(output=provider_envelope(
        interpretation, operations=[operation(actor_claim=actor, source_ids=sources)]
    ))
    result = call(provider, make_context(interpretation), interpretation)
    # v2025.07-t3: delta source failures trigger one repair attempt
    assert_repair_fallback(result, interpretation, reason)
    assert len(provider.calls) == 2


@pytest.mark.parametrize(
    ("actor", "sources"),
    [
        (DiscussionActorClaim.USER_EXPLICIT, [CURRENT_USER_ID]),
        (DiscussionActorClaim.USER_INFERRED, [RECENT_USER_ID, CURRENT_USER_ID]),
        (DiscussionActorClaim.ASSISTANT_PROPOSAL, [RESERVED_ASSISTANT_ID]),
        (DiscussionActorClaim.ASSISTANT_PROPOSAL, [RESERVED_ASSISTANT_ID, RECENT_ASSISTANT_ID]),
    ],
)
def test_grounded_delta_sources_are_accepted(actor, sources):
    interpretation = make_interpretation()
    provider = RecordingProvider(output=provider_envelope(
        interpretation, operations=[operation(actor_claim=actor, source_ids=sources)]
    ))
    result = call(provider, make_context(interpretation), interpretation)
    assert result.source.value == "provider"


@pytest.mark.parametrize(
    "actor", [DiscussionActorClaim.SYSTEM_FACT, DiscussionActorClaim.FORMAL_PROJECT_FACT]
)
def test_authority_claims_are_rejected(actor):
    interpretation = make_interpretation()
    provider = RecordingProvider(output=provider_envelope(
        interpretation, operations=[operation(actor_claim=actor, source_ids=[])]
    ))
    result = call(provider, make_context(interpretation), interpretation)
    # v2025.07-t3: delta authority claim failures trigger one repair attempt
    assert_repair_fallback(result, interpretation, "provider_delta_authority_claim_invalid")
    assert len(provider.calls) == 2


@pytest.mark.parametrize(
    ("target", "expected_reason"),
    [
        (ACTIVE_EVENT_ID, None),  # TOPIC_SET — compatible with set_topic
        (RELEVANT_EVENT_ID, "provider_delta_supersedes_target_incompatible"),  # CONCERN_ADDED — not compatible
        (UNKNOWN_ID, "provider_delta_supersedes_target_not_visible"),
    ],
)
def test_supersede_target_must_be_visible(target, expected_reason):
    interpretation = make_interpretation()
    # F2: use set_topic (allows_supersedes=True) to test visibility;
    # add_concern now rejects any supersedes with supersedes_forbidden.
    provider = RecordingProvider(output=provider_envelope(
        interpretation,
        operations=[{
            "op": "set_topic",
            "content": "new topic",
            "payload": {},
            "source_message_ids": [str(CURRENT_USER_ID)],
            "actor_claim": DiscussionActorClaim.USER_EXPLICIT.value,
            "supersedes_event_id": str(target) if target is not None else None,
        }],
    ))
    result = call(provider, make_context(interpretation), interpretation)
    if expected_reason is None:
        assert result.source.value == "provider"
    else:
        # v2025.07-t3: delta supersede failures trigger one repair attempt
        assert_repair_fallback(result, interpretation, expected_reason)
        assert len(provider.calls) == 2


def test_provider_accepts_rejected_option_reselection_using_original_identity():
    interpretation = make_interpretation(ConversationMode.PREFERENCE_UPDATE)
    context, option_a, rejection_id = rejected_option_context(interpretation)
    provider = RecordingProvider(output=provider_envelope(
        interpretation,
        operations=[{
            "op": "prefer_option",
            "content": "重新选择方案A",
            "target_id": str(option_a),
            "payload": {"option_id": str(option_a)},
            "source_message_ids": [str(CURRENT_USER_ID)],
            "actor_claim": DiscussionActorClaim.USER_EXPLICIT.value,
            "supersedes_event_id": str(rejection_id),
        }],
    ))
    result = call(provider, context, interpretation)
    assert result.source.value == "provider"
    assert len(provider.calls) == 1
    payload = json.loads(provider.calls[0][1])
    assert payload["context"]["reserved_assistant_message_id"] == str(RESERVED_ASSISTANT_ID)


def test_provider_rejects_historical_option_reintroduction_without_third_call():
    interpretation = make_interpretation(ConversationMode.PREFERENCE_UPDATE)
    context, option_a, _ = rejected_option_context(interpretation)
    provider = RecordingProvider(output=provider_envelope(
        interpretation,
        operations=[{
            "op": "add_option",
            "content": "重复引入方案A",
            "target_id": str(option_a),
            "payload": {"option_id": str(option_a)},
            "source_message_ids": [str(CURRENT_USER_ID)],
            "actor_claim": DiscussionActorClaim.USER_EXPLICIT.value,
            "supersedes_event_id": None,
        }],
    ))
    result = call(provider, context, interpretation)
    assert_repair_fallback(result, interpretation, "provider_delta_option_target_not_new")
    assert len(provider.calls) == 2


def make_proposal(
    *,
    workspace_version: int = 8,
    message_ids: list[UUID] | None = None,
    event_ids: list[UUID] | None = None,
) -> dict[str, object]:
    return {
        "proposal_id": str(UNKNOWN_ID),
        "target": "plan_revision",
        "workspace_version": workspace_version,
        "summary": "proposal summary",
        "changes": [
            {
                "change_type": "add",
                "subject_key": "subject",
                "summary": "change summary",
                "source_event_ids": [
                    str(item) for item in (event_ids or [ACTIVE_EVENT_ID])
                ],
            }
        ],
        "source_message_ids": [
            str(item) for item in (message_ids or [CURRENT_USER_ID])
        ],
        "risk_summary": "proposal risk",
        "requires_confirmation": True,
        "status": "proposed",
    }


def make_formalization_interpretation() -> TurnInterpretation:
    return make_interpretation(
        ConversationMode.FORMALIZATION_REQUEST,
        formal_action_requested=True,
    )


def make_formalization_operation() -> dict[str, object]:
    return {
        "op": "request_formalization",
        "target_id": None,
        "subject_key": "formalization:request",
        "content": "request a formal plan revision",
        "payload": {},
        "source_message_ids": [str(CURRENT_USER_ID)],
        "actor_claim": DiscussionActorClaim.USER_EXPLICIT.value,
        "supersedes_event_id": None,
    }


def make_canonical_formalization_envelope(
    interpretation: TurnInterpretation,
    *,
    answer: str = "formalization response",
    proposal: dict[str, object] | None = None,
    returned_interpretation: TurnInterpretation | None = None,
) -> dict[str, object]:
    context = make_context(interpretation)
    return json.loads(provider_envelope(
        returned_interpretation or interpretation,
        answer=answer,
        operations=[make_formalization_operation()],
        proposal=proposal or make_proposal(
            workspace_version=context.active_workspace.workspace.version_no + 1,
            message_ids=[CURRENT_USER_ID, RECENT_ASSISTANT_ID],
            event_ids=[ACTIVE_EVENT_ID, RELEVANT_EVENT_ID],
        ),
        requires_confirmation=True,
    ))


def call_formalization_sequence(
    responses: list[tuple[str, str | None]],
) -> tuple[object, SequenceRecordingProvider, TurnInterpretation, DiscussionContextAssembly]:
    interpretation = make_formalization_interpretation()
    context = make_context(interpretation)
    provider = SequenceRecordingProvider(responses)
    result = call(provider, context, interpretation)
    return result, provider, interpretation, context


def test_f8_formalization_prompt_exposes_only_canonical_envelope_contract():
    interpretation = make_formalization_interpretation()
    context = make_context(interpretation)
    provider = RecordingProvider(output=json.dumps(
        make_canonical_formalization_envelope(interpretation)
    ))

    result = call(provider, context, interpretation)

    assert result.source.value == "provider"
    prompt = json.loads(provider.calls[0][1])
    contract = prompt["formalization_envelope_contract"]
    assert set(contract["canonical_envelope_schema"]) == {
        "answer", "turn_interpretation", "discussion_delta",
        "formalization_proposal", "requires_confirmation", "source", "source_detail",
    }
    assert set(contract["canonical_envelope_schema"]["formalization_proposal"]) >= {
        "proposal_id", "target", "workspace_version", "summary", "changes",
        "source_message_ids", "risk_summary", "requires_confirmation", "status",
    }
    assert set(contract["canonical_envelope_schema"]["formalization_proposal"]["changes"][0]) == {
        "change_type", "subject_key", "summary", "source_event_ids",
    }
    assert {"proposalId", "workspaceVersion", "proposal_summary", "required_confirmation",
            "proposal", "formalizationProposal", "data"} <= set(
                contract["top_level_field_rule"]["forbidden_aliases_or_wrappers"]
            )

    ordinary = make_interpretation()
    ordinary_provider = RecordingProvider(output=provider_envelope(ordinary))
    call(ordinary_provider, make_context(ordinary), ordinary)
    assert "formalization_envelope_contract" not in json.loads(ordinary_provider.calls[0][1])


def test_f8_pydantic_diagnostics_retain_raw_object_without_sensitive_error_fields():
    interpretation = make_formalization_interpretation()
    malformed = make_canonical_formalization_envelope(interpretation)
    malformed["formalization_proposal"]["proposalId"] = malformed[
        "formalization_proposal"
    ].pop("proposal_id")
    malformed["unrelated_secret"] = "must remain raw only"

    parsed, reason, raw, diagnostics = ProjectDirectorResponseEngineService._parse_envelope(
        json.dumps(malformed)
    )

    assert parsed is None
    assert reason == "provider_envelope_invalid"
    assert raw == malformed
    assert diagnostics
    assert all(set(item) == {"loc", "type", "msg"} for item in diagnostics)
    assert not {"input", "ctx", "url"} & set().union(*(set(item) for item in diagnostics))
    assert all("must remain raw only" not in repr(item) for item in diagnostics)


def test_f8_formalization_repair_returns_canonical_envelope_and_repair_receipt():
    interpretation = make_formalization_interpretation()
    initial = make_canonical_formalization_envelope(interpretation)
    initial["formalization_proposal"]["proposalId"] = initial[
        "formalization_proposal"
    ].pop("proposal_id")
    original_initial = deepcopy(initial)
    repaired = make_canonical_formalization_envelope(interpretation)

    result, provider, _, context = call_formalization_sequence([
        (json.dumps(initial), "receipt-direct"),
        (json.dumps(repaired), "receipt-repair"),
    ])

    assert len(provider.calls) == 2
    assert provider.calls[0][2] == "fixed-request"
    assert provider.calls[1][2] == "fixed-request-repair"
    repair_prompt = json.loads(provider.calls[1][1])
    assert repair_prompt["initial_provider_envelope_json"] == original_initial
    assert all(set(item) == {"loc", "type", "msg"}
               for item in repair_prompt["safe_pydantic_validation_errors"])
    contract = repair_prompt["formalization_envelope_contract"]
    assert contract["identity_context"]["caller_interpretation"] == interpretation.model_dump(mode="json")
    assert contract["identity_context"]["current_user_message_id"] == str(CURRENT_USER_ID)
    assert contract["identity_context"]["reserved_assistant_message_id"] == str(RESERVED_ASSISTANT_ID)
    assert contract["identity_context"]["expected_workspace_version_after_this_turn"] == 8
    assert str(CURRENT_USER_ID) in contract["identity_context"]["visible_user_message_ids"]
    assert str(ACTIVE_EVENT_ID) in contract["identity_context"]["visible_pre_turn_event_ids"]
    assert result.source.value == "provider"
    assert "attempt=repair" in result.source_detail
    assert "receipt=receipt-repair" in result.source_detail
    assert result.formalization_proposal is not None
    assert result.discussion_delta.operations[0].op == "request_formalization"
    assert result.requires_confirmation is True
    assert initial == original_initial
    assert context.active_workspace.workspace.version_no == 7


def test_f8_formalization_repair_rejects_proposal_fragment_without_third_call():
    interpretation = make_formalization_interpretation()
    initial = make_canonical_formalization_envelope(interpretation)
    initial["formalization_proposal"].pop("proposal_id")
    result, provider, _, _ = call_formalization_sequence([
        (json.dumps(initial), "receipt-direct"),
        (json.dumps({"formalization_proposal": make_proposal()}), "receipt-repair"),
    ])

    assert len(provider.calls) == 2
    assert_repair_fallback(
        result, interpretation,
        "provider_formalization_proposal_invalid:provider_envelope_invalid",
    )


def test_f8_formalization_repair_rejects_second_invalid_envelope_without_third_call():
    interpretation = make_formalization_interpretation()
    initial = make_canonical_formalization_envelope(interpretation)
    initial["formalization_proposal"].pop("proposal_id")
    repaired = make_canonical_formalization_envelope(interpretation)
    repaired["formalization_proposal"].pop("workspace_version")
    result, provider, _, _ = call_formalization_sequence([
        (json.dumps(initial), "receipt-direct"),
        (json.dumps(repaired), "receipt-repair"),
    ])

    assert len(provider.calls) == 2
    assert_repair_fallback(
        result, interpretation,
        "provider_formalization_proposal_invalid:provider_envelope_invalid",
    )


def test_f8_formalization_repair_revalidates_visible_lineage():
    interpretation = make_formalization_interpretation()
    initial = make_canonical_formalization_envelope(interpretation)
    initial["formalization_proposal"].pop("proposal_id")
    repaired = make_canonical_formalization_envelope(interpretation)
    repaired["formalization_proposal"]["changes"][0]["source_event_ids"] = [str(UNKNOWN_ID)]
    result, provider, _, _ = call_formalization_sequence([
        (json.dumps(initial), "receipt-direct"),
        (json.dumps(repaired), "receipt-repair"),
    ])

    assert len(provider.calls) == 2
    assert_repair_fallback(result, interpretation, "provider_formalization_source_event_invalid")


def test_f8_formalization_repair_revalidates_caller_interpretation():
    interpretation = make_formalization_interpretation()
    initial = make_canonical_formalization_envelope(interpretation)
    initial["formalization_proposal"].pop("proposal_id")
    mismatched = make_formalization_interpretation()
    repaired = make_canonical_formalization_envelope(
        interpretation, returned_interpretation=mismatched.model_copy(
            update={"primary_intent": "different interpretation"}
        )
    )
    result, provider, _, _ = call_formalization_sequence([
        (json.dumps(initial), "receipt-direct"),
        (json.dumps(repaired), "receipt-repair"),
    ])

    assert len(provider.calls) == 2
    assert_repair_fallback(result, interpretation, "provider_interpretation_mismatch")


def test_f8_formalization_repair_revalidates_execution_claims():
    interpretation = make_formalization_interpretation()
    initial = make_canonical_formalization_envelope(interpretation)
    initial["formalization_proposal"].pop("proposal_id")
    repaired = make_canonical_formalization_envelope(
        interpretation, answer="已创建 PlanVersion，并已写入仓库。"
    )
    result, provider, _, _ = call_formalization_sequence([
        (json.dumps(initial), "receipt-direct"),
        (json.dumps(repaired), "receipt-repair"),
    ])

    assert len(provider.calls) == 2
    assert_repair_fallback(result, interpretation, "provider_forbidden_execution_claim")


def test_f8_non_json_formalization_stays_on_generic_repair_path():
    interpretation = make_formalization_interpretation()
    repaired = make_canonical_formalization_envelope(interpretation)
    result, provider, _, _ = call_formalization_sequence([
        ("not json", "receipt-direct"),
        (json.dumps(repaired), "receipt-repair"),
    ])

    assert len(provider.calls) == 2
    assert provider.calls[0][2] == provider.calls[1][2] == "fixed-request"
    assert "initial_provider_envelope_json" not in json.loads(provider.calls[1][1])
    assert result.source.value == "provider"
    assert "attempt=repair" in result.source_detail


def test_f8_ordinary_response_repair_does_not_use_formalization_contract():
    interpretation = make_interpretation()
    malformed = json.loads(provider_envelope(interpretation))
    malformed.pop("source_detail")
    provider = SequenceRecordingProvider([
        (json.dumps(malformed), "receipt-direct"),
        (provider_envelope(interpretation), "receipt-repair"),
    ])

    result = call(provider, make_context(interpretation), interpretation)

    assert len(provider.calls) == 2
    assert provider.calls[0][2] == provider.calls[1][2] == "fixed-request"
    assert "formalization_envelope_contract" not in json.loads(provider.calls[1][1])
    assert result.source.value == "provider"
    assert "attempt=repair" in result.source_detail


def test_f8_missing_business_lineage_fields_are_never_silently_filled():
    interpretation = make_formalization_interpretation()
    initial = make_canonical_formalization_envelope(interpretation)
    proposal = initial["formalization_proposal"]
    for field in ("proposal_id", "workspace_version", "source_message_ids"):
        proposal.pop(field)
    proposal["changes"][0].pop("source_event_ids")
    original_initial = deepcopy(initial)
    repaired = make_canonical_formalization_envelope(interpretation)

    result, provider, _, _ = call_formalization_sequence([
        (json.dumps(initial), "receipt-direct"),
        (json.dumps(repaired), "receipt-repair"),
    ])

    assert len(provider.calls) == 2
    repair_prompt = json.loads(provider.calls[1][1])
    assert repair_prompt["initial_provider_envelope_json"] == original_initial
    assert result.source.value == "provider"
    assert result.formalization_proposal.proposal_id == UNKNOWN_ID
    assert result.formalization_proposal.workspace_version == 8
    assert result.formalization_proposal.source_message_ids == [CURRENT_USER_ID, RECENT_ASSISTANT_ID]
    assert result.formalization_proposal.changes[0].source_event_ids == [ACTIVE_EVENT_ID, RELEVANT_EVENT_ID]


def test_valid_formalization_proposal_is_preserved():
    interpretation = make_interpretation(
        ConversationMode.FORMALIZATION_REQUEST,
        formal_action_requested=True,
    )
    context = make_context(interpretation)
    form_op = {
        "op": "request_formalization",
        "target_id": None,
        "subject_key": "formalization:request",
        "content": "请求正式化",
        "payload": {},
        "source_message_ids": [str(CURRENT_USER_ID)],
        "actor_claim": DiscussionActorClaim.USER_EXPLICIT.value,
        "supersedes_event_id": None,
    }
    provider = RecordingProvider(output=provider_envelope(
        interpretation,
        operations=[form_op],
        proposal=make_proposal(
            workspace_version=context.active_workspace.workspace.version_no + 1,
            message_ids=[CURRENT_USER_ID, RECENT_ASSISTANT_ID],
            event_ids=[ACTIVE_EVENT_ID, RELEVANT_EVENT_ID],
        ),
        requires_confirmation=True,
    ))
    result = call(provider, context, interpretation)
    assert result.source.value == "provider"
    assert result.formalization_proposal is not None
    assert result.requires_confirmation is True


@pytest.mark.parametrize(
    ("interpretation", "context_modifier", "proposal_modifier", "reason"),
    [
        (
            make_interpretation(),
            lambda context: context,
            lambda proposal: proposal,
            "provider_formalization_not_requested",
        ),
        (
            make_interpretation(
                ConversationMode.FORMALIZATION_REQUEST,
                formal_action_requested=False,
            ),
            lambda context: context,
            lambda proposal: proposal,
            "provider_formalization_not_requested",
        ),
        (
            make_interpretation(
                ConversationMode.FORMALIZATION_REQUEST,
                formal_action_requested=False,
                hypothetical_action=True,
            ),
            lambda context: context,
            lambda proposal: proposal,
            "provider_formalization_not_requested",
        ),
        (
            make_interpretation(
                ConversationMode.FORMALIZATION_REQUEST,
                formal_action_requested=True,
            ),
            lambda context: replace(context, active_workspace=None),
            lambda proposal: proposal,
            "provider_formalization_workspace_missing",
        ),
        (
            make_interpretation(
                ConversationMode.FORMALIZATION_REQUEST,
                formal_action_requested=True,
            ),
            lambda context: context,
            lambda proposal: {**proposal, "workspace_version": 9},
            "provider_formalization_workspace_version_mismatch",
        ),
        (
            make_interpretation(
                ConversationMode.FORMALIZATION_REQUEST,
                formal_action_requested=True,
            ),
            lambda context: context,
            lambda proposal: {**proposal, "source_message_ids": [str(UNKNOWN_ID)]},
            "provider_formalization_source_message_invalid",
        ),
        (
            make_interpretation(
                ConversationMode.FORMALIZATION_REQUEST,
                formal_action_requested=True,
            ),
            lambda context: context,
            lambda proposal: {
                **proposal,
                "changes": [{
                    **proposal["changes"][0],
                    "source_event_ids": [str(UNKNOWN_ID)],
                }],
            },
            "provider_formalization_source_event_invalid",
        ),
    ],
)
def test_formalization_proposal_failures(
    interpretation, context_modifier, proposal_modifier, reason
):
    context = context_modifier(make_context(interpretation))
    proposal = proposal_modifier(make_proposal())
    # v2025.07-t3: formalization proposals require request_formalization delta
    form_op = {
        "op": "request_formalization",
        "target_id": None,
        "subject_key": "formalization:request",
        "content": "请求正式化",
        "payload": {},
        "source_message_ids": [str(CURRENT_USER_ID)],
        "actor_claim": DiscussionActorClaim.USER_EXPLICIT.value,
        "supersedes_event_id": None,
    }
    provider = RecordingProvider(output=provider_envelope(
        interpretation, operations=[form_op], proposal=proposal, requires_confirmation=True
    ))
    result = call(provider, context, interpretation)
    # v2025.07-t3: repairable reasons trigger repair; non-repairable direct
    _REPAIR_REASONS = {
        "provider_formalization_workspace_version_mismatch",
        "provider_formalization_source_message_invalid",
        "provider_formalization_source_event_invalid",
    }
    if reason in _REPAIR_REASONS:
        assert_repair_fallback(result, interpretation, reason)
        assert len(provider.calls) == 2
    else:
        assert_direct_fallback(result, interpretation, reason)
        assert len(provider.calls) == 1


def test_formalization_without_confirmation_is_domain_invalid_first():
    interpretation = make_interpretation(
        ConversationMode.FORMALIZATION_REQUEST,
        formal_action_requested=True,
    )
    form_op = {
        "op": "request_formalization",
        "target_id": None,
        "subject_key": "formalization:request",
        "content": "请求正式化",
        "payload": {},
        "source_message_ids": [str(CURRENT_USER_ID)],
        "actor_claim": DiscussionActorClaim.USER_EXPLICIT.value,
        "supersedes_event_id": None,
    }
    provider = RecordingProvider(output=provider_envelope(
        interpretation, operations=[form_op], proposal=make_proposal(), requires_confirmation=False
    ))
    result = call(provider, make_context(interpretation), interpretation)
    # v2025.07-t3: domain validation catches envelope issue before version check
    # F2: formalization envelope failures are wrapped as proposal_invalid
    assert_repair_fallback(result, interpretation, "provider_formalization_proposal_invalid:provider_envelope_invalid")
    assert len(provider.calls) == 2


@pytest.mark.parametrize(
    ("interpretation", "provider_value", "expected"),
    [
        (make_interpretation(), False, False),
        (make_interpretation(), True, True),
        (
            make_interpretation(
                ConversationMode.ACTION_REQUEST, formal_action_requested=True
            ),
            False,
            True,
        ),
        (
            make_interpretation(
                ConversationMode.ACTION_REQUEST, hypothetical_action=True
            ),
            False,
            False,
        ),
    ],
)
def test_requires_confirmation_policy(interpretation, provider_value, expected):
    provider = RecordingProvider(output=provider_envelope(
        interpretation, requires_confirmation=provider_value
    ))
    result = call(provider, make_context(interpretation), interpretation)
    assert result.source.value == "provider"
    assert result.requires_confirmation is expected


@pytest.mark.parametrize(
    "mode",
    [
        ConversationMode.GENERAL_DISCUSSION,
        ConversationMode.SOLUTION_EXPLORATION,
        ConversationMode.OPTION_COMPARISON,
        ConversationMode.CLARIFICATION,
        ConversationMode.CHALLENGE,
        ConversationMode.CONSTRAINT_UPDATE,
        ConversationMode.PREFERENCE_UPDATE,
        ConversationMode.DECISION_CONFIRMATION,
    ],
)
def test_ordinary_fallback_is_natural_and_not_boundary_dump(mode):
    interpretation = make_interpretation(mode)
    context = make_context(interpretation)
    result = call(None, context, interpretation)
    assert_direct_fallback(result, interpretation, "provider_unavailable")
    assert "讨论上下文仍然保留" in result.answer
    assert "internal boundary one" not in result.answer
    assert "internal boundary two" not in result.answer


def test_status_and_action_fallbacks_are_scoped_to_known_facts():
    status_interpretation = make_interpretation(ConversationMode.STATUS_QUERY)
    status_context = make_context(status_interpretation)
    status = call(None, status_context, status_interpretation)
    assert "clarifying" in status.answer
    assert "fixed goal summary" in status.answer

    action_interpretation = make_interpretation(
        ConversationMode.ACTION_REQUEST, formal_action_requested=True
    )
    action = call(None, make_context(action_interpretation), action_interpretation)
    assert "没有执行正式动作" in action.answer
    assert action.requires_confirmation is True


@pytest.mark.parametrize(
    ("receipt", "expected"),
    [
        ("receipt", "receipt"),
        (None, "missing"),
        ("   ", "missing"),
        (" " + "x" * 121, "x" * 120),
    ],
)
def test_provider_receipt_normalization(receipt, expected):
    interpretation = make_interpretation()
    provider = RecordingProvider(
        output=provider_envelope(interpretation), receipt=receipt
    )
    result = call(provider, make_context(interpretation), interpretation)
    assert result.source_detail == f"p26_f1_provider_response;attempt=direct;receipt={expected}"
    assert len(result.source_detail) <= 300


def test_answer_limit_and_full_original_safety_scan():
    interpretation = make_interpretation()
    answer = "x" * 10_001
    provider = RecordingProvider(output=provider_envelope(interpretation, answer=answer))
    result = call(provider, make_context(interpretation), interpretation)
    assert result.source.value == "provider"
    assert result.answer == "x" * 10_000

    unsafe = "x" * 10_000 + "已创建任务"
    provider = RecordingProvider(output=provider_envelope(interpretation, answer=unsafe))
    result = call(provider, make_context(interpretation), interpretation)
    assert_direct_fallback(result, interpretation, "provider_forbidden_execution_claim")


def test_input_immutability_and_cross_instance_determinism():
    interpretation = make_interpretation(needs_discussion_history=True)
    context = make_context(interpretation)
    before = deepcopy(context)
    interpretation_before = interpretation.model_dump(mode="python")
    output = provider_envelope(interpretation)
    one = call(RecordingProvider(output=output), context, interpretation)
    two = call(RecordingProvider(output=output), context, interpretation)
    assert one == two
    assert context == before
    assert interpretation.model_dump(mode="python") == interpretation_before


def test_static_dependency_and_single_provider_call_boundary():
    path = Path(__file__).parents[1] / "app/services/project_director_response_engine_service.py"
    tree = ast.parse(path.read_text())
    names = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    }
    attributes = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
    }
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    forbidden = {
        "sqlalchemy", "Session", "Repository", "MessageService",
        "ProviderConfigService", "TurnInterpreter", "DeltaGate",
        "create_engine", "sessionmaker", "uuid4", "utc_now",
        "InteractionCase", "ExternalContextPack", "embedding", "vector",
    }
    assert not forbidden & (names | attributes | imports)
    assert "commit" not in attributes
    assert "rollback" not in attributes
    assert "flush" not in attributes
    provider_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_provider_text_generator"
    ]
    # v2025.07-t3: two provider call sites (primary + single repair)
    assert len(provider_calls) == 2


# P26-H3-F2-V2: condition markers govern the entire sentence, not only their
# opening clause. The table also proves that scope resets at sentence end.
@pytest.mark.parametrize(
    "content",
    [
        "如果条件满足，我选择方案A。",
        "如果将来成本下降，我重新选择方案A。",
    ],
)
def test_conditional_preference_scope_rejects_the_original_regressions(content):
    assert ProjectDirectorResponseEngineService._has_explicit_preference_selection(content) is False


@pytest.mark.parametrize(
    "content",
    [
        "如果条件满足，我选择方案A。",
        "如果将来成本下降，我重新选择方案A。",
        "假如预算获批，我选择方案A。",
        "假设延迟降低，我改选方案A。",
        "只要成本下降，我选择方案A。",
        "除非兼容问题解决，我选择方案A。",
        "若预算获批，我选择方案A。",
        "在兼容问题解决的情况下，我选择方案A。",
        "当延迟降低时，我改选方案A。",
        "如果成本下降，并且旧数据兼容，我选择方案A。",
        "如果成本下降，旧数据兼容，并且迁移完成，我重新选择方案A。",
    ],
)
def test_conditional_preference_scope_rejects_all_conditional_forms(content):
    assert ProjectDirectorResponseEngineService._has_explicit_preference_selection(content) is False


@pytest.mark.parametrize(
    "content",
    [
        "条件已经满足。我选择方案A。",
        "经过比较，我最终选择方案A。",
        "我先分析风险。最终我选择方案A。",
        "我先说明风险，我最终选择方案A。",
        "如果条件满足，我选择方案A。现在条件已经满足，我选择方案B。",
    ],
)
def test_conditional_preference_scope_resets_for_later_real_selection(content):
    assert ProjectDirectorResponseEngineService._has_explicit_preference_selection(content) is True


@pytest.mark.parametrize(
    "content",
    [
        "我选择方案A。",
        "我当前选择方案A。",
        "我暂时选择方案A。",
        "我最终选择方案A。",
        "我重新选择方案A。",
        "我改选方案A。",
        "我改回方案A。",
        "我更倾向方案A。",
        "我偏好方案A。",
        "我更偏好方案A。",
        "我比较喜欢方案A。",
        "我优先选方案A。",
        "我优先选择方案A。",
        "我确认选择方案A。",
        "我改变主意，重新选择方案A。",
    ],
)
def test_explicit_preference_selection_recognizes_all_affirmative_forms(content):
    assert ProjectDirectorResponseEngineService._has_explicit_preference_selection(content) is True


@pytest.mark.parametrize(
    "content",
    [
        "如果我重新选择方案A会怎样？",
        "假如我选择方案A会有哪些风险？",
        "我选择方案A吗？",
        "我是否应该选择方案A？",
        "我选择方案A还是方案B更好？",
        "我应该怎么选择？",
        "请比较方案A和方案B。",
        "我想比较方案A和方案B。",
        "请分析我选择方案A后的风险。",
        "不要选择方案A。",
        "我不选择方案A。",
        "我不再选择方案A。",
        "我拒绝方案A。",
        "我还没有决定选择哪个方案。",
        "我尚未决定选择哪个方案。",
        "这个方向看起来不错。",
        "我不想选择方案A。",
        "我选择方案A，还是先比较一下？",
        "我选择方案A，会有什么风险？",
        "请分析风险，我选择方案A会怎样？",
        "我说过‘我选择方案A吗？’，但这不是正式选择。",
        "我是否应该优先选择方案A？",
        "如果我优先选择方案A会怎样？",
        "假如我更偏好方案A，会有哪些风险？",
        "我是否偏好方案A？",
        "请分析偏好方案A可能带来的风险。",
        "偏好设置应该怎么配置？",
        "系统的优先级应该如何配置？",
        "我比较喜欢方案A吗？",
        "如果我比较喜欢方案A，会有什么风险？",
        "我比较喜欢方案A，还是方案B更好？",
    ],
)
def test_explicit_preference_selection_rejects_non_selection_forms(content):
    assert ProjectDirectorResponseEngineService._has_explicit_preference_selection(content) is False


@pytest.mark.parametrize(
    "content",
    [
        "如果条件满足，我选择方案A。",
        "如果我重新选择方案A会怎样？",
        "我是否应该优先选择方案A？",
        "如果我更偏好方案A会怎样？",
        "请分析偏好方案A可能带来的风险。",
        "偏好设置应该怎么配置？",
    ],
)
def test_non_selection_preference_language_does_not_require_an_empty_delta(content):
    interpretation = make_interpretation()
    context = replace(
        make_context(interpretation),
        current_user_message=make_context(interpretation).current_user_message.model_copy(
            update={"content": content}
        ),
    )
    provider = RecordingProvider(output=provider_envelope(interpretation))

    result = call(provider, context, interpretation)

    assert result.source.value == "provider"
    assert len(provider.calls) == 1


def test_explicit_selection_with_no_prefer_option_reports_preference_missing():
    interpretation = make_interpretation(ConversationMode.PREFERENCE_UPDATE)
    context = make_context(interpretation)
    context = replace(
        context,
        current_user_message=context.current_user_message.model_copy(
            update={"content": "我选择方案A。"}
        ),
    )
    provider = RecordingProvider(output=provider_envelope(interpretation))

    result = call(provider, context, interpretation)

    assert_repair_fallback(
        result, interpretation, "provider_delta_preference_operation_missing"
    )
    assert len(provider.calls) == 2


def _explicit_preference_delta_context(
    interpretation: TurnInterpretation,
    *,
    content: str = "我选择方案A。",
) -> tuple[DiscussionContextAssembly, UUID, UUID]:
    option_a, option_b = uuid4(), uuid4()
    context = make_context(interpretation)
    workspace = context.active_workspace.workspace.model_copy(update={
        "active_option_ids": [option_a, option_b],
        "preferred_option_id": option_b,
    })
    return (
        replace(
            context,
            current_user_message=context.current_user_message.model_copy(
                update={"content": content}
            ),
            active_workspace=ActiveDiscussionWorkspaceContext(
                workspace=workspace,
                active_events=(
                    make_event(
                        event_id=uuid4(), sequence_no=1,
                        event_type=DiscussionEventType.OPTION_ADDED,
                        payload={"option_id": str(option_a)},
                        subject_key=f"option:{option_a}",
                    ),
                    make_event(
                        event_id=uuid4(), sequence_no=2,
                        event_type=DiscussionEventType.OPTION_ADDED,
                        payload={"option_id": str(option_b)},
                        subject_key=f"option:{option_b}",
                    ),
                ),
            ),
        ),
        option_a,
        option_b,
    )


def _prefer_option(
    target_id: UUID,
    *,
    actor_claim: DiscussionActorClaim = DiscussionActorClaim.USER_EXPLICIT,
    source_message_ids: list[UUID] | None = None,
) -> DiscussionDeltaOperation:
    return DiscussionDeltaOperation(
        op=DiscussionDeltaOperationType.PREFER_OPTION,
        target_id=target_id,
        content="用户明确选择方案",
        payload={"option_id": str(target_id)},
        source_message_ids=source_message_ids or [CURRENT_USER_ID],
        actor_claim=actor_claim,
    )


def test_helper_local_preference_delta_requires_exactly_one_prefer_operation():
    interpretation = make_interpretation()
    context, option_a, option_b = _explicit_preference_delta_context(interpretation)
    correction = DiscussionDeltaOperation(
        op=DiscussionDeltaOperationType.RECORD_USER_CORRECTION,
        content="记录用户更正",
        source_message_ids=[CURRENT_USER_ID],
        actor_claim=DiscussionActorClaim.USER_EXPLICIT,
    )
    add_option = DiscussionDeltaOperation(
        op=DiscussionDeltaOperationType.ADD_OPTION,
        target_id=uuid4(),
        content="新增无关方案",
        payload={},
        source_message_ids=[CURRENT_USER_ID],
        actor_claim=DiscussionActorClaim.USER_EXPLICIT,
    )
    update_option = DiscussionDeltaOperation(
        op=DiscussionDeltaOperationType.UPDATE_OPTION,
        target_id=option_a,
        content="更新方案A",
        payload={},
        source_message_ids=[CURRENT_USER_ID],
        actor_claim=DiscussionActorClaim.USER_EXPLICIT,
    )

    for operation in (correction, add_option, update_option):
        assert ProjectDirectorResponseEngineService._validate_delta_requirement(
            context=context,
            interpretation=interpretation,
            delta=DiscussionDelta(operations=[operation]),
        ) == "provider_delta_preference_operation_missing"

    assert ProjectDirectorResponseEngineService._validate_delta_requirement(
        context=context,
        interpretation=interpretation,
        delta=DiscussionDelta(
            operations=[_prefer_option(option_a), _prefer_option(option_b)]
        ),
    ) == "provider_delta_preference_operation_ambiguous"


def test_provider_envelope_rejects_inferred_preference_actor_before_helper_validation():
    base_interpretation = make_interpretation(ConversationMode.PREFERENCE_UPDATE)
    context, option_a, _ = _explicit_preference_delta_context(base_interpretation)
    interpretation = base_interpretation.model_copy(
        update={"referenced_option_ids": [option_a]}
    )
    output = provider_envelope(
        interpretation,
        operations=[
            {
                "op": "prefer_option",
                "target_id": str(option_a),
                "content": "用户明确选择方案A。",
                "payload": {"option_id": str(option_a)},
                "source_message_ids": [str(CURRENT_USER_ID)],
                "actor_claim": DiscussionActorClaim.USER_INFERRED.value,
                "supersedes_event_id": None,
            }
        ],
    )

    parsed, reason, _, diagnostics = ProjectDirectorResponseEngineService(
        provider_text_generator=None
    )._validate_provider_envelope(
        context=context,
        interpretation=interpretation,
        assistant_message_id=RESERVED_ASSISTANT_ID,
        output_text=output,
    )

    assert parsed is None
    assert reason == "provider_delta_operation_actor_not_authorized"
    assert diagnostics == []


def test_provider_envelope_rejects_preference_mutation_missing_current_user_source():
    base_interpretation = make_interpretation(ConversationMode.PREFERENCE_UPDATE)
    context, option_a, _ = _explicit_preference_delta_context(base_interpretation)
    interpretation = base_interpretation.model_copy(
        update={"referenced_option_ids": [option_a]}
    )
    output = provider_envelope(
        interpretation,
        operations=[
            {
                "op": "prefer_option",
                "target_id": str(option_a),
                "content": "用户明确选择方案A。",
                "payload": {"option_id": str(option_a)},
                "source_message_ids": [str(RECENT_USER_ID)],
                "actor_claim": DiscussionActorClaim.USER_EXPLICIT.value,
                "supersedes_event_id": None,
            }
        ],
    )

    parsed, reason, _, diagnostics = ProjectDirectorResponseEngineService(
        provider_text_generator=None
    )._validate_provider_envelope(
        context=context,
        interpretation=interpretation,
        assistant_message_id=RESERVED_ASSISTANT_ID,
        output_text=output,
    )

    assert parsed is None
    assert reason == "provider_delta_preference_operation_missing"
    assert diagnostics == []


def test_helper_local_preference_delta_rejects_target_mismatch_for_explicit_reselection():
    base_interpretation = make_interpretation(ConversationMode.PREFERENCE_UPDATE)
    context, option_a, option_b = _explicit_preference_delta_context(
        base_interpretation, content="我改变主意，重新选择方案A。"
    )
    interpretation = base_interpretation.model_copy(
        update={"referenced_option_ids": [option_a]}
    )

    assert ProjectDirectorResponseEngineService._validate_delta_requirement(
        context=context,
        interpretation=interpretation,
        delta=DiscussionDelta(operations=[_prefer_option(option_b)]),
    ) == "provider_delta_preference_target_mismatch"


def test_helper_local_preference_delta_rejects_target_unchanged_old_preferred_on_reversal():
    base_interpretation = make_interpretation(ConversationMode.PREFERENCE_UPDATE)
    context, _, option_b = _explicit_preference_delta_context(
        base_interpretation, content="我改变主意，重新选择方案A。"
    )
    interpretation = base_interpretation.model_copy(
        update={"referenced_option_ids": [option_b]}
    )

    assert ProjectDirectorResponseEngineService._validate_delta_requirement(
        context=context,
        interpretation=interpretation,
        delta=DiscussionDelta(operations=[_prefer_option(option_b)]),
    ) == "provider_delta_preference_target_unchanged"


@pytest.mark.parametrize(
    "content",
    [
        "我选择方案A。",
        "我重新选择方案A。",
        "我重新选方案A。",
        "我改选方案A。",
        "我改回方案A。",
        "我换回方案A。",
        "我决定重新选择方案A。",
        "我改变主意，重新选择方案A。",
        "我改变主意了，重新选择方案A。",
        "我已经改变主意，重新选择方案A。",
        "我最终还是选择方案A。",
        "我最终还是选择 A。",
        "我最终还是选择：方案A。",
        "我最终还是选择，\n方案A。",
    ],
)
def test_preference_mutation_hard_gate_recognizes_current_selection_and_reselection(content):
    assert (
        ProjectDirectorResponseEngineService._has_explicit_preference_selection(content)
        or ProjectDirectorResponseEngineService._has_explicit_preference_reselection(content)
    ) is True


@pytest.mark.parametrize(
    "content",
    [
        "如果我重新选择方案A会怎样？",
        "假如我改回方案A，会有哪些风险？",
        "我是否应该重新选择方案A？",
        "我重新选择方案A吗？",
        "请分析重新选择方案A的后果。",
        "我还没有决定是否改回方案A。",
        "我不再选择方案A。",
        "不要改回方案A。",
        "我重新选择方案A还是方案B更好？",
        "我最终还是选择方案A吗？",
        "我最终还是选择方案A？",
        "我最终还是选择方案A还是方案B更好？",
        "我最终还是选择方案A，还是先比较一下？",
        "如果条件满足，我最终还是选择方案A。",
        "假如我最终还是选择方案A，会有哪些风险？",
        "请分析我最终还是选择方案A的风险。",
        "我还没有决定最终是否选择方案A。",
    ],
)
def test_preference_mutation_hard_gate_rejects_questions_conditions_and_comparisons(content):
    assert ProjectDirectorResponseEngineService._has_explicit_preference_selection(content) is False
    assert ProjectDirectorResponseEngineService._has_explicit_preference_reselection(content) is False


@pytest.mark.parametrize(
    ("content", "mode", "referenced_option_ids", "hypothetical", "expected"),
    [
        ("我选择方案A。", ConversationMode.GENERAL_DISCUSSION, [], False, True),
        ("我重新选择方案A。", ConversationMode.GENERAL_DISCUSSION, [], False, True),
        ("我最终还是选择方案A。", ConversationMode.GENERAL_DISCUSSION, [], False, True),
        ("我比较喜欢方案A。", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], False, True),
        ("如果条件满足，我选择方案A。", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], False, False),
        ("假如我选择方案A会怎样？", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], False, False),
        ("我选择方案A吗？", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], False, False),
        ("我不选择方案A。", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], False, False),
        ("我选择方案A还是方案B更好？", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], False, False),
        ("我还没有决定选择哪个方案。", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], False, False),
        ("请分析我选择方案A后的风险。", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], False, False),
        ("我比较喜欢方案A。", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], True, False),
        ("我比较喜欢方案A。", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], False, True),
        ("我选择方案A。", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], True, False),
        ("我选择方案A。", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], False, True),
        ("我重新选择方案A。", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], True, False),
        ("我重新选择方案A。", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], False, True),
        ("我改变主意，重新选择方案A。", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], True, False),
        ("我改变主意，重新选择方案A。", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], False, True),
        ("我最终还是选择方案A。", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], True, False),
        ("我最终还是选择方案A。", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], False, True),
        ("我改回方案A。", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], True, False),
        ("我改回方案A。", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], False, True),
        ("我优先选择方案A。", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], True, False),
        ("我优先选择方案A。", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], False, True),
        ("这个方向看起来不错。", ConversationMode.PREFERENCE_UPDATE, [UNKNOWN_ID], False, False),
    ],
)
def test_preference_mutation_required_requires_an_affirmative_current_choice(
    content, mode, referenced_option_ids, hypothetical, expected
):
    interpretation = make_interpretation(
        mode,
        referenced_option_ids=referenced_option_ids,
        hypothetical_action=hypothetical,
    )
    context = make_context(interpretation)
    context = replace(
        context,
        current_user_message=context.current_user_message.model_copy(
            update={"content": content}
        ),
    )

    assert ProjectDirectorResponseEngineService._preference_mutation_required(
        context=context, interpretation=interpretation
    ) is expected


def test_preference_mutation_requires_single_referenced_target_without_guessing():
    interpretation = make_interpretation()
    context, option_a, _ = _explicit_preference_delta_context(interpretation)

    assert ProjectDirectorResponseEngineService._validate_delta_requirement(
        context=context,
        interpretation=interpretation,
        delta=DiscussionDelta(operations=[_prefer_option(option_a)]),
    ) == "provider_delta_preference_target_unavailable"
