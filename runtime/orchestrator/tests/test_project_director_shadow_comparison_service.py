"""Regression locks for the non-writing Director shadow comparison seam."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.domain.director_runtime_protocol import (
    DIRECTOR_RUNTIME_SCHEMA_VERSION,
    DirectorRuntimeFailure,
    parse_director_turn_result,
)
from app.domain.project_director_conversation_intelligence import (
    ConversationMode,
    DirectorResponseEnvelope,
    DirectorResponseSource,
    FormalizationChange,
    FormalizationChangeType,
    FormalizationProposal,
    FormalizationTarget,
    TurnInterpretation,
)
from app.domain.project_director_discussion import (
    DiscussionActorClaim,
    DiscussionDelta,
    DiscussionDeltaOperation,
    DiscussionDeltaOperationType,
)
from app.domain.project_director_shadow_comparison import (
    LegacyShadowObservationMetadata,
    ShadowComparisonError,
)
from app.services.director_runtime_supervisor_service import (
    DirectorRuntimeAttemptState,
    DirectorRuntimeSupervisionOutcome,
)
from app.services.project_director_shadow_comparison_service import (
    ProjectDirectorShadowComparisonService,
)


REQUEST_ID = "shadow-request-1"


def _interpretation(**overrides: object) -> TurnInterpretation:
    values: dict[str, object] = {
        "conversation_mode": ConversationMode.GENERAL_DISCUSSION,
        "primary_intent": "compare this turn",
        "confidence": 0.8,
        "reason_summary": "synthetic verification only",
    }
    values.update(overrides)
    return TurnInterpretation(**values)


def _operation(
    *,
    op: DiscussionDeltaOperationType = DiscussionDeltaOperationType.PREFER_OPTION,
    message_ids: list[UUID] | None = None,
    actor: DiscussionActorClaim = DiscussionActorClaim.USER_EXPLICIT,
    supersedes_event_id: UUID | None = None,
) -> DiscussionDeltaOperation:
    return DiscussionDeltaOperation(
        op=op,
        content="bounded legacy operation",
        actor_claim=actor,
        source_message_ids=message_ids or [uuid4()],
        supersedes_event_id=supersedes_event_id,
    )


def _proposal(message_id: UUID, event_id: UUID) -> FormalizationProposal:
    return FormalizationProposal(
        proposal_id=uuid4(),
        target=FormalizationTarget.PLAN_REVISION,
        workspace_version=1,
        summary="bounded proposal",
        changes=[
            FormalizationChange(
                change_type=FormalizationChangeType.ADD,
                subject_key="scope",
                summary="bounded change",
                source_event_ids=[event_id],
            )
        ],
        source_message_ids=[message_id],
        source_event_ids=[event_id],
        risk_summary="bounded risk",
    )


def _legacy(
    *,
    interpretation: TurnInterpretation | None = None,
    operations: list[DiscussionDeltaOperation] | None = None,
    proposal: FormalizationProposal | None = None,
    answer: str = "legacy response",
) -> DirectorResponseEnvelope:
    return DirectorResponseEnvelope(
        answer=answer,
        turn_interpretation=interpretation or _interpretation(),
        discussion_delta=DiscussionDelta(operations=operations or []),
        formalization_proposal=proposal,
        requires_confirmation=proposal is not None,
        source=DirectorResponseSource.PROVIDER,
        source_detail="synthetic provider envelope",
    )


def _runtime_payload(
    *,
    request_id: str = REQUEST_ID,
    mode: str = "general_discussion",
    formal_action_requested: bool = False,
    hypothetical_action: bool = False,
    delta: dict[str, object] | None = None,
    readiness: str = "not_ready",
    proposal_candidate: dict[str, object] | None = None,
    refs: list[dict[str, str]] | None = None,
    response: str = "runtime response",
    duration_ms: float = 1.0,
    usage: dict[str, float | None] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": DIRECTOR_RUNTIME_SCHEMA_VERSION,
        "request_id": request_id,
        "response_text": response,
        "turn_semantics": {
            "conversation_mode": mode,
            "formal_action_requested": formal_action_requested,
            "hypothetical_action": hypothetical_action,
            "confidence": 0.8,
        },
        "discussion_lifecycle": {
            "observed_status": "exploring",
            "suggested_next_status": "exploring",
        },
        "discussion_delta_candidate": delta,
        "formalization": {
            "proposal_candidate": proposal_candidate,
            "readiness": readiness,
        },
        "tool_activity": [],
        "source_references": refs or [],
        "runtime_metadata": {
            "runtime_state": "ready",
            "model_id": "synthetic-model",
            "provider_profile_id": "synthetic-profile",
            "usage": usage or {},
            "duration_ms": duration_ms,
            "attempt": 0,
        },
        "error": None,
    }


def _outcome(**overrides: object) -> DirectorRuntimeSupervisionOutcome:
    candidate = parse_director_turn_result(
        _runtime_payload(**overrides), expected_request_id=overrides.get("request_id", REQUEST_ID), authorized_tools=[]
    )
    return DirectorRuntimeSupervisionOutcome(
        request_id=candidate.request_id,
        attempt_state=DirectorRuntimeAttemptState.SUCCEEDED,
        candidate=candidate,
        error=None,
    )


def _compare(
    legacy: DirectorResponseEnvelope | None = None,
    outcome: DirectorRuntimeSupervisionOutcome | None = None,
    metadata: LegacyShadowObservationMetadata | None = None,
):
    return ProjectDirectorShadowComparisonService().compare(
        expected_request_id=REQUEST_ID,
        legacy_envelope=legacy or _legacy(),
        runtime_outcome=outcome or _outcome(),
        legacy_observation=metadata,
    )


def _assert_non_writing(result: object) -> None:
    assert result.authoritative is False
    assert result.write_allowed is False
    assert result.candidate_admitted is False


def _difference(result: object, dimension: str):
    return next(item for item in result.differences if item.dimension == dimension)


def test_matching_case_compares_all_available_dimensions_and_is_non_writing() -> None:
    metadata = LegacyShadowObservationMetadata(
        discussion_observed_status="exploring",
        discussion_suggested_next_status="exploring",
        attempt_state="succeeded",
        duration_ms=1.0,
        usage_keys=("input_tokens",),
    )
    result = _compare(_legacy(), _outcome(usage={"input_tokens": 1.0}), metadata)
    assert result.runtime_failed is False
    assert result.semantic_match is True
    assert result.differences == ()
    assert "source_references" in result.compared_dimensions
    _assert_non_writing(result)


@pytest.mark.parametrize(
    ("legacy", "outcome", "dimension"),
    [
        (_legacy(interpretation=_interpretation(conversation_mode=ConversationMode.CLARIFICATION)), _outcome(), "conversation_mode"),
        (_legacy(interpretation=_interpretation(formal_action_requested=True)), _outcome(), "formal_action_requested"),
        (_legacy(interpretation=_interpretation(hypothetical_action=True)), _outcome(), "hypothetical_action"),
    ],
)
def test_basic_semantic_mismatches_are_bounded(legacy, outcome, dimension) -> None:
    result = _compare(legacy, outcome)
    assert result.semantic_match is False
    diff = _difference(result, dimension)
    assert len(diff.legacy_summary) <= 256
    assert len(diff.runtime_summary) <= 256
    _assert_non_writing(result)


def test_delta_match_type_mismatch_and_unknown_shape() -> None:
    message_id = uuid4()
    legacy = _legacy(operations=[_operation(message_ids=[message_id])])
    refs = [{"message_id": str(message_id), "kind": "user_message"}]
    matched = _compare(
        legacy,
        _outcome(delta={"operations": [{"op": "prefer_option"}]}, refs=refs),
    )
    assert matched.semantic_match is True
    mismatched = _compare(
        legacy,
        _outcome(delta={"operations": [{"op": "reject_option"}]}, refs=refs),
    )
    assert _difference(mismatched, "discussion_delta").status == "mismatch"
    unknown = _compare(
        legacy,
        _outcome(delta={"operations": "shadow-delta-secret"}, refs=refs),
    )
    assert "discussion_delta" in unknown.unavailable_dimensions
    assert "discussion_delta" not in unknown.compared_dimensions
    assert "shadow-delta-secret" not in unknown.model_dump_json()


@pytest.mark.parametrize(
    ("readiness", "candidate", "expected"),
    [
        ("not_ready", None, "no_proposal"),
        ("candidate", {"proposal": "shadow-proposal-secret"}, "candidate_only"),
        ("requires_confirmation", {"proposal": "safe"}, "proposal_requires_confirmation"),
        ("not_ready", {"proposal": "safe"}, "inconsistent_shape"),
    ],
)
def test_formalization_states_are_compared_without_gate_execution(readiness, candidate, expected) -> None:
    event_id, message_id = uuid4(), uuid4()
    legacy = _legacy(proposal=_proposal(message_id, event_id)) if expected == "proposal_requires_confirmation" else _legacy()
    refs = [{"message_id": str(message_id), "kind": "user_message"}] if expected == "proposal_requires_confirmation" else []
    result = _compare(legacy, _outcome(readiness=readiness, proposal_candidate=candidate, refs=refs))
    if expected == "no_proposal" or expected == "proposal_requires_confirmation":
        assert result.semantic_match is True
    else:
        assert _difference(result, "formalization").runtime_summary == expected
    assert "shadow-proposal-secret" not in result.model_dump_json()
    _assert_non_writing(result)


def test_source_provenance_set_equality_privacy_and_event_lineage_boundary() -> None:
    message_a, message_b, event = uuid4(), uuid4(), uuid4()
    legacy = _legacy(operations=[_operation(message_ids=[message_a], supersedes_event_id=event)])
    same = _compare(
        legacy,
        _outcome(
            refs=[{"message_id": str(message_a).upper(), "kind": "user_message"}],
            delta={"operations": [{"op": "prefer_option"}]},
        ),
    )
    assert same.semantic_match is True
    assert "not_comparable" not in same.model_dump_json()  # only emitted in the zero-ref summary
    wrong = _compare(legacy, _outcome(refs=[{"message_id": str(message_b), "kind": "assistant_message"}]))
    diff = _difference(wrong, "source_references")
    assert message_a.hex not in wrong.model_dump_json() and message_b.hex not in wrong.model_dump_json()
    assert "message_refs=1" in diff.legacy_summary
    assert "actors=user_explicit" in diff.legacy_summary
    assert "kinds=assistant_message" in diff.runtime_summary
    missing = _compare(legacy, _outcome())
    assert _difference(missing, "source_references").status == "mismatch"
    extra = _compare(legacy, _outcome(refs=[{"message_id": str(message_a), "kind": "user_message"}, {"message_id": str(message_b), "kind": "user_message"}]))
    assert _difference(extra, "source_references").status == "mismatch"


def test_empty_provenance_and_event_lineage_do_not_hide_wrong_message_reference() -> None:
    assert _compare().semantic_match is True
    message_a, message_b, event = uuid4(), uuid4(), uuid4()
    legacy = _legacy(operations=[_operation(message_ids=[message_a], supersedes_event_id=event)])
    result = _compare(legacy, _outcome(refs=[{"message_id": str(message_b), "kind": "grounding"}]))
    assert _difference(result, "source_references").status == "mismatch"


def test_response_and_raw_source_privacy() -> None:
    message_id, event_id = uuid4(), uuid4()
    legacy = _legacy(
        operations=[_operation(message_ids=[message_id], supersedes_event_id=event_id)],
        answer="secret-legacy-response-unique",
    )
    result = _compare(
        legacy,
        _outcome(
            refs=[{"message_id": str(message_id), "kind": "user_message"}],
            delta={"operations": [{"op": "prefer_option", "note": "shadow-delta-secret-unique"}]},
            response="secret-runtime-response-unique" * 30,
        ),
    )
    dumped = result.model_dump_json()
    for secret in ("secret-legacy-response-unique", "secret-runtime-response-unique", "shadow-delta-secret-unique", str(message_id), str(event_id), "DirectorTurnResult", "DirectorResponseEnvelope"):
        assert secret not in dumped
    assert "length_bucket" in dumped


@pytest.mark.parametrize("state", [DirectorRuntimeAttemptState.TIMED_OUT, DirectorRuntimeAttemptState.FAILED, DirectorRuntimeAttemptState.REJECTED, DirectorRuntimeAttemptState.CANCELLED])
def test_runtime_failures_are_all_unavailable_and_non_writing(state) -> None:
    outcome = DirectorRuntimeSupervisionOutcome(
        request_id=REQUEST_ID,
        attempt_state=state,
        candidate=None,
        error=DirectorRuntimeFailure(code="safe-code", stage="runtime", retryable=False, safe_message="raw stack must not leak"),
    )
    result = _compare(outcome=outcome)
    assert result.runtime_failed is True
    assert result.semantic_match is False
    assert result.compared_dimensions == ()
    assert len(result.unavailable_dimensions) == 11
    assert result.differences == ()
    assert "raw stack must not leak" not in result.model_dump_json()
    _assert_non_writing(result)


def test_request_correlation_fails_closed_and_optional_metadata_is_unavailable() -> None:
    with pytest.raises(ShadowComparisonError, match="shadow_comparison_request_id_mismatch"):
        _compare(outcome=_outcome(request_id="different-request"))
    with pytest.raises(ShadowComparisonError, match="shadow_comparison_request_id_invalid"):
        ProjectDirectorShadowComparisonService().compare(expected_request_id=" ", legacy_envelope=_legacy(), runtime_outcome=_outcome())
    result = _compare()
    assert {"discussion_lifecycle", "runtime_attempt_state", "duration", "usage"}.issubset(result.unavailable_dimensions)
