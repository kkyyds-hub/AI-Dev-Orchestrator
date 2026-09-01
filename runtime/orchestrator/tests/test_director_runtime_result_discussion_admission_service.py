"""P26-BIG-C2-A pure admission from runtime candidates into the P26 Delta Gate."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.domain.director_runtime_protocol import (
    DIRECTOR_RUNTIME_SCHEMA_VERSION,
    DirectorRuntimeProtocolError,
    parse_director_turn_result,
    validate_director_runtime_request,
)
from app.domain.project_director_discussion import DiscussionEvent, DiscussionEventType
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.services.director_runtime_result_discussion_admission_service import (
    DirectorRuntimeDiscussionAdmissionError,
    DirectorRuntimeResultDiscussionAdmissionService,
)
from app.services.project_director_discussion_delta_gate_service import (
    DiscussionDeltaGateStatus,
)


PROJECT_ID = UUID("11111111-1111-1111-1111-111111111111")
SESSION_ID = UUID("22222222-2222-2222-2222-222222222222")
USER_MESSAGE_ID = UUID("33333333-3333-3333-3333-333333333333")
ASSISTANT_MESSAGE_ID = UUID("44444444-4444-4444-4444-444444444444")
SYSTEM_MESSAGE_ID = UUID("55555555-5555-5555-5555-555555555555")
FIXED_TIME = datetime(2026, 8, 31, 8, 0, tzinfo=timezone.utc)


def _request(*, request_id: str = "c2-a-request"):
    return validate_director_runtime_request(
        {
            "schema_version": DIRECTOR_RUNTIME_SCHEMA_VERSION,
            "request_id": request_id,
            "project_id": str(PROJECT_ID),
            "session_id": str(SESSION_ID),
            "message_id": str(USER_MESSAGE_ID),
            "current_user_message": {
                "content": "请评估这个讨论候选。",
                "occurred_at": "2026-08-31T08:00:00Z",
                "actor_claim": "user",
            },
            "authoritative_facts": {},
            "active_discussion_workspace": None,
            "relevant_discussion_events": [],
            "active_formalization": {"proposal": None, "plan_version": None},
            "governance_boundaries": {
                "authoritative_write": False,
                "director_may_modify_code": False,
                "formalization_requires_explicit_request": True,
                "confirmation_is_separate": True,
                "execution_boundary": "no_task_run_agent_session_before_execution",
            },
            "available_skills": [],
            "available_tools": [],
            "permission_context": {},
            "runtime_config": {
                "model_id": "c2-a-model",
                "provider_profile_id": "c2-a-profile",
                "timeout_ms": 1000.0,
                "max_tool_rounds": 0,
            },
        }
    )


def _result_payload(
    *,
    request_id: str = "c2-a-request",
    candidate: dict | None = None,
    error: dict | None = None,
) -> dict:
    return {
        "schema_version": DIRECTOR_RUNTIME_SCHEMA_VERSION,
        "request_id": request_id,
        "response_text": "运行时回复",
        "turn_semantics": {
            "conversation_mode": "general_discussion",
            "formal_action_requested": False,
            "hypothetical_action": False,
            "confidence": 0.8,
        },
        "discussion_lifecycle": {
            "observed_status": None,
            "suggested_next_status": None,
        },
        "discussion_delta_candidate": candidate,
        "formalization": {"proposal_candidate": None, "readiness": "not_ready"},
        "tool_activity": [],
        "source_references": [],
        "runtime_metadata": {
            "runtime_state": "ready",
            "model_id": "c2-a-model",
            "provider_profile_id": "c2-a-profile",
            "usage": {},
            "duration_ms": 1.0,
            "attempt": 0,
        },
        "error": error,
    }


def _result(**kwargs):
    payload = _result_payload(**kwargs)
    return parse_director_turn_result(
        payload,
        expected_request_id=payload["request_id"],
    )


def _user_message(*, session_id: UUID = SESSION_ID) -> ProjectDirectorMessage:
    return ProjectDirectorMessage(
        id=USER_MESSAGE_ID,
        session_id=session_id,
        role=ProjectDirectorMessageRole.USER,
        content="请评估这个讨论候选。",
        sequence_no=1,
        source=ProjectDirectorMessageSource.SYSTEM,
        created_at=FIXED_TIME,
    )


def _system_message() -> ProjectDirectorMessage:
    return ProjectDirectorMessage(
        id=SYSTEM_MESSAGE_ID,
        session_id=SESSION_ID,
        role=ProjectDirectorMessageRole.SYSTEM,
        content="已确认的平台事实。",
        sequence_no=3,
        source=ProjectDirectorMessageSource.SYSTEM,
        created_at=FIXED_TIME,
    )


def _assistant_delta(
    *,
    op: str = "add_concern",
    actor_claim: str = "assistant_proposal",
    source_message_ids: list[str] | None = None,
    supersedes_event_id: str | None = None,
    content: str = "运行时候选内容",
) -> dict:
    return {
        "operations": [
            {
                "op": op,
                "target_id": None,
                "subject_key": "runtime-candidate",
                "content": content,
                "payload": {},
                "source_message_ids": source_message_ids
                if source_message_ids is not None
                else [str(ASSISTANT_MESSAGE_ID)],
                "actor_claim": actor_claim,
                "supersedes_event_id": supersedes_event_id,
            }
        ]
    }


def _admit(
    result,
    *,
    request=None,
    available_messages: list[ProjectDirectorMessage] | None = None,
    current_events: list[DiscussionEvent] | None = None,
) -> object:
    return DirectorRuntimeResultDiscussionAdmissionService().admit(
        request=_request() if request is None else request,
        result=result,
        assistant_message_id=ASSISTANT_MESSAGE_ID,
        assistant_message_sequence_no=2,
        available_messages=[_user_message()]
        if available_messages is None
        else available_messages,
        current_events=[] if current_events is None else current_events,
        current_workspace=None,
        start_sequence_no=1,
        occurred_at=FIXED_TIME,
    )


def test_no_candidate_returns_explicit_no_delta_admission() -> None:
    admission = _admit(_result(candidate=None))

    assert admission.delta is None
    assert admission.assistant_message_candidate is not None
    assert admission.assistant_message_candidate.id == ASSISTANT_MESSAGE_ID
    assert admission.assistant_message_candidate.session_id == SESSION_ID
    assert admission.assistant_message_candidate.related_project_id == PROJECT_ID
    assert admission.assistant_message_candidate.sequence_no == 2
    assert admission.assistant_message_candidate.content == "运行时回复"
    assert admission.assistant_message_candidate.role == ProjectDirectorMessageRole.ASSISTANT
    assert admission.assistant_message_candidate.source == ProjectDirectorMessageSource.AI
    assert admission.governed_delta is None
    assert admission.no_admission_reason == "no_delta_candidate"


def test_empty_valid_delta_is_prepared_by_the_existing_gate() -> None:
    admission = _admit(_result(candidate={"operations": []}))

    assert admission.delta is not None
    assert admission.governed_delta is not None
    assert admission.governed_delta.status == DiscussionDeltaGateStatus.PREPARED
    assert admission.governed_delta.prepared_events == ()
    assert admission.assistant_message_candidate is not None


def test_legal_assistant_proposal_is_prepared_without_persistence() -> None:
    admission = _admit(_result(candidate=_assistant_delta()))

    assert admission.assistant_message_candidate is not None
    assert admission.assistant_message_candidate.id == ASSISTANT_MESSAGE_ID
    assert admission.assistant_message_candidate.session_id == SESSION_ID
    assert admission.assistant_message_candidate.related_project_id == PROJECT_ID
    assert admission.assistant_message_candidate.role == ProjectDirectorMessageRole.ASSISTANT
    assert admission.assistant_message_candidate.source == ProjectDirectorMessageSource.AI
    assert admission.governed_delta is not None
    assert admission.governed_delta.status == DiscussionDeltaGateStatus.PREPARED
    assert len(admission.governed_delta.prepared_events) == 1


def test_runtime_cannot_forge_user_explicit_from_assistant_message() -> None:
    with pytest.raises(ValueError, match="^discussion_delta_actor_source_role_mismatch$"):
        _admit(
            _result(
                candidate=_assistant_delta(actor_claim="user_explicit"),
            )
        )


@pytest.mark.parametrize("actor_claim", ["system_fact", "formal_project_fact"])
def test_runtime_cannot_mint_trusted_platform_authority(actor_claim: str) -> None:
    with pytest.raises(DirectorRuntimeDiscussionAdmissionError) as exc:
        _admit(
            _result(
                candidate=_assistant_delta(
                    op="add_constraint",
                    actor_claim=actor_claim,
                    source_message_ids=[str(SYSTEM_MESSAGE_ID)],
                )
            ),
            available_messages=[_user_message(), _system_message()],
        )
    assert exc.value.code == "director_runtime_discussion_admission_authority_claim_invalid"


def test_system_context_does_not_reject_a_legal_assistant_proposal() -> None:
    admission = _admit(
        _result(candidate=_assistant_delta()),
        available_messages=[_user_message(), _system_message()],
    )

    assert admission.governed_delta is not None
    assert admission.governed_delta.status == DiscussionDeltaGateStatus.PREPARED


@pytest.mark.parametrize("actor_claim", ["user_explicit", "user_inferred"])
def test_runtime_user_claims_continue_through_the_existing_gate(actor_claim: str) -> None:
    admission = _admit(
        _result(
            candidate=_assistant_delta(
                op="add_constraint",
                actor_claim=actor_claim,
                source_message_ids=[str(USER_MESSAGE_ID)],
            )
        )
    )

    assert admission.governed_delta is not None
    assert admission.governed_delta.status == DiscussionDeltaGateStatus.PREPARED


@pytest.mark.parametrize(
    "candidate",
    [
        _assistant_delta(op="unknown_operation"),
        _assistant_delta(actor_claim="not_an_actor"),
        _assistant_delta(source_message_ids=["not-a-uuid"]),
        _assistant_delta(
            source_message_ids=[str(ASSISTANT_MESSAGE_ID), str(ASSISTANT_MESSAGE_ID)]
        ),
        _assistant_delta(content="   "),
        {"operations": [{"op": "add_concern"}]},
    ],
)
def test_malformed_runtime_candidate_fails_before_the_gate(candidate: dict) -> None:
    with pytest.raises(DirectorRuntimeDiscussionAdmissionError) as exc:
        _admit(_result(candidate=candidate))
    assert exc.value.code == "director_runtime_discussion_admission_delta_invalid"


def test_gate_rejects_a_missing_source_message() -> None:
    with pytest.raises(ValueError, match="^discussion_delta_source_message_not_found$"):
        _admit(_result(candidate=_assistant_delta(source_message_ids=[str(uuid4())])))


def test_gate_rejects_a_cross_session_source_message() -> None:
    with pytest.raises(ValueError, match="^discussion_delta_source_message_session_mismatch$"):
        _admit(
            _result(candidate=_assistant_delta(source_message_ids=[str(USER_MESSAGE_ID)])),
            available_messages=[_user_message(session_id=uuid4())],
        )


def test_gate_rejects_an_illegal_supersede_target() -> None:
    with pytest.raises(ValueError, match="^discussion_delta_supersedes_forbidden$"):
        _admit(
            _result(candidate=_assistant_delta(supersedes_event_id=str(uuid4()))),
        )


def test_high_governance_candidate_preserves_requires_confirmation() -> None:
    admission = _admit(
        _result(candidate=_assistant_delta(op="confirm_decision")),
    )

    assert admission.governed_delta is not None
    assert admission.governed_delta.status == DiscussionDeltaGateStatus.REQUIRES_CONFIRMATION
    assert admission.governed_delta.prepared_events == ()


def test_request_result_identity_mismatch_fails_closed() -> None:
    with pytest.raises(DirectorRuntimeDiscussionAdmissionError) as exc:
        _admit(
            _result(candidate=_assistant_delta(), request_id="different-request"),
            request=_request(request_id="c2-a-request"),
        )
    assert exc.value.code == "director_runtime_discussion_admission_request_id_mismatch"


def test_error_result_returns_explicit_no_admission() -> None:
    admission = _admit(
        _result(
            error={
                "code": "runtime_failed",
                "stage": "runtime",
                "retryable": False,
                "safe_message": "运行时失败",
            }
        )
    )

    assert admission.delta is None
    assert admission.assistant_message_candidate is None
    assert admission.governed_delta is None
    assert admission.no_admission_reason == "runtime_error"


def test_same_inputs_produce_equal_immutable_admission_results() -> None:
    result = _result(candidate=_assistant_delta())

    first = _admit(result)
    second = _admit(result)

    assert first == second
    assert first.governed_delta is not None
    with pytest.raises(AttributeError):
        first.no_admission_reason = "mutated"


def test_protocol_rejects_an_error_result_that_carries_a_candidate() -> None:
    payload = _result_payload(
        candidate=_assistant_delta(),
        error={
            "code": "runtime_failed",
            "stage": "runtime",
            "retryable": False,
            "safe_message": "运行时失败",
        },
    )

    with pytest.raises(DirectorRuntimeProtocolError):
        parse_director_turn_result(payload, expected_request_id="c2-a-request")


def test_admission_service_has_no_persistence_or_runtime_dependencies() -> None:
    source = Path(__file__).parents[1] / (
        "app/services/director_runtime_result_discussion_admission_service.py"
    )
    module = ast.parse(source.read_text())
    imports = {
        alias.name
        for node in ast.walk(module)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    forbidden_imports = (
        "sqlalchemy",
        "app.repositories",
        "app.services.director_runtime_supervisor_service",
        "app.services.director_runtime_transport",
        "provider",
        "worker",
    )
    assert all(
        forbidden not in imported.lower()
        for imported in imports
        for forbidden in forbidden_imports
    )
    forbidden_calls = {"commit", "flush", "rollback", "create", "update", "delete"}
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in forbidden_calls
        for node in ast.walk(module)
    )
