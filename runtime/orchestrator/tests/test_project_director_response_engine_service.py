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
from uuid import UUID

import pytest

from app.domain.project_director_conversation_intelligence import (
    ConversationMode,
    TurnInterpretation,
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


def assert_fallback(result, interpretation: TurnInterpretation, reason: str) -> None:
    assert result.source.value == "rule_fallback"
    assert result.source_detail == f"p26_f1_rule_fallback;reason={reason}"
    assert result.turn_interpretation.model_dump(mode="python") == interpretation.model_dump(
        mode="python"
    )
    assert result.discussion_delta.operations == []
    assert result.formalization_proposal is None


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
        "behavior_instructions", "output_schema", "source_id_rules",
        "silent_governance_instruction", "context",
    }
    assert set(prompt["context"]) == {
        "pinned_formal_facts", "recent_raw_messages", "active_workspace",
        "relevant_events", "current_user_message", "silent_governance_boundaries",
        "discussion_context_plan", "caller_interpretation",
        "reserved_assistant_message_id",
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
    assert len(provider.calls) == 1
    assert_fallback(result, interpretation, reason)


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
    assert result.source_detail == "p26_f1_provider_response;receipt=" + "r" * 120
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
    assert_fallback(result, interpretation, reason)
    if provider is not None:
        assert len(provider.calls) == 1


def test_provider_self_claimed_rule_fallback_is_not_accepted_as_success():
    interpretation = make_interpretation()
    provider = RecordingProvider(output=provider_envelope(
        interpretation, source="rule_fallback"
    ))
    result = call(provider, make_context(interpretation), interpretation)
    assert_fallback(result, interpretation, "provider_source_invalid")
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
    assert_fallback(result, interpretation, "provider_envelope_invalid")
    assert len(provider.calls) == 1


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
    assert_fallback(result, interpretation, "provider_interpretation_mismatch")
    assert len(provider.calls) == 1


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
    assert_fallback(result, interpretation, "provider_forbidden_execution_claim")


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
    assert_fallback(result, interpretation, reason)


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
    assert_fallback(result, interpretation, "provider_delta_authority_claim_invalid")


@pytest.mark.parametrize(
    ("target", "expected_reason"),
    [(ACTIVE_EVENT_ID, None), (RELEVANT_EVENT_ID, None), (UNKNOWN_ID, "provider_delta_supersede_target_not_visible")],
)
def test_supersede_target_must_be_visible(target, expected_reason):
    interpretation = make_interpretation()
    provider = RecordingProvider(output=provider_envelope(
        interpretation,
        operations=[operation(
            actor_claim=DiscussionActorClaim.USER_EXPLICIT,
            source_ids=[CURRENT_USER_ID],
            supersedes_event_id=target,
        )],
    ))
    result = call(provider, make_context(interpretation), interpretation)
    if expected_reason is None:
        assert result.source.value == "provider"
    else:
        assert_fallback(result, interpretation, expected_reason)


def make_proposal(
    *,
    workspace_version: int = 7,
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


def test_valid_formalization_proposal_is_preserved():
    interpretation = make_interpretation(
        ConversationMode.FORMALIZATION_REQUEST,
        formal_action_requested=True,
    )
    context = make_context(interpretation)
    provider = RecordingProvider(output=provider_envelope(
        interpretation,
        proposal=make_proposal(
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
            lambda proposal: {**proposal, "workspace_version": 8},
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
    provider = RecordingProvider(output=provider_envelope(
        interpretation, proposal=proposal, requires_confirmation=True
    ))
    result = call(provider, context, interpretation)
    assert_fallback(result, interpretation, reason)


def test_formalization_without_confirmation_is_domain_invalid_first():
    interpretation = make_interpretation(
        ConversationMode.FORMALIZATION_REQUEST,
        formal_action_requested=True,
    )
    provider = RecordingProvider(output=provider_envelope(
        interpretation, proposal=make_proposal(), requires_confirmation=False
    ))
    result = call(provider, make_context(interpretation), interpretation)
    assert_fallback(result, interpretation, "provider_envelope_invalid")


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
    assert_fallback(result, interpretation, "provider_unavailable")
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
    assert result.source_detail == f"p26_f1_provider_response;receipt={expected}"
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
    assert_fallback(result, interpretation, "provider_forbidden_execution_claim")


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
    assert len(provider_calls) == 1
