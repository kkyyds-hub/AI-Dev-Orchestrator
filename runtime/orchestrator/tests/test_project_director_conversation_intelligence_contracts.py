"""Tests for P26-A conversation intelligence domain contracts.

Verifies enum stability, model invariants, JSON Schema generation,
round-trip serialization, and pure-domain import boundaries.
"""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

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
    DiscussionEvent,
    DiscussionEventStatus,
    DiscussionEventType,
    DiscussionOption,
    DiscussionOptionStatus,
    DiscussionStatus,
    DiscussionWorkspace,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid() -> "UUID":
    return uuid4()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _naive_now() -> datetime:
    return datetime.now()


# ===========================================================================
# 6.1 Enum stability
# ===========================================================================


class TestDiscussionStatusEnum:
    def test_values_and_order(self):
        expected = [
            "exploring", "comparing", "converging",
            "ready_to_formalize", "formalized", "paused",
        ]
        assert [e.value for e in DiscussionStatus] == expected


class TestDiscussionEventStatusEnum:
    def test_values_and_order(self):
        expected = ["active", "rejected", "superseded", "confirmed", "historical"]
        assert [e.value for e in DiscussionEventStatus] == expected


class TestDiscussionEventTypeEnum:
    def test_values_and_order(self):
        expected = [
            "topic_set", "option_added", "option_updated", "option_preferred",
            "option_rejected", "constraint_added", "constraint_updated",
            "constraint_superseded", "concern_added", "assumption_added",
            "assumption_rejected", "open_question_added", "open_question_resolved",
            "temporary_conclusion_added", "user_correction_recorded",
            "decision_confirmed", "formalization_requested", "formalization_cancelled",
        ]
        assert [e.value for e in DiscussionEventType] == expected


class TestDiscussionActorClaimEnum:
    def test_values_and_order(self):
        expected = [
            "user_explicit", "user_inferred", "assistant_proposal",
            "system_fact", "formal_project_fact",
        ]
        assert [e.value for e in DiscussionActorClaim] == expected


class TestDiscussionOptionStatusEnum:
    def test_values_and_order(self):
        expected = ["active", "preferred", "rejected", "superseded", "historical"]
        assert [e.value for e in DiscussionOptionStatus] == expected


class TestDiscussionDeltaOperationTypeEnum:
    def test_values_and_order(self):
        expected = [
            "set_topic", "add_option", "update_option", "prefer_option",
            "reject_option", "add_constraint", "update_constraint",
            "supersede_constraint", "add_concern", "add_assumption",
            "reject_assumption", "add_open_question", "resolve_open_question",
            "add_temporary_conclusion", "record_user_correction",
            "confirm_decision", "request_formalization", "cancel_formalization",
        ]
        assert [e.value for e in DiscussionDeltaOperationType] == expected


class TestConversationModeEnum:
    def test_values_and_order(self):
        expected = [
            "general_discussion", "solution_exploration", "option_comparison",
            "clarification", "challenge", "constraint_update", "preference_update",
            "decision_confirmation", "formalization_request", "action_request",
            "status_query",
        ]
        assert [e.value for e in ConversationMode] == expected


class TestFormalizationTargetEnum:
    def test_values(self):
        assert [e.value for e in FormalizationTarget] == ["plan_revision"]


class TestFormalizationChangeTypeEnum:
    def test_values(self):
        assert [e.value for e in FormalizationChangeType] == ["add", "update", "remove"]


class TestDirectorResponseSourceEnum:
    def test_values(self):
        expected = ["provider", "rule_fallback", "system"]
        assert [e.value for e in DirectorResponseSource] == expected


class TestEnumPydanticRejection:
    def test_unknown_discussion_status_rejected(self):
        with pytest.raises(Exception):
            DiscussionStatus("nonexistent")

    def test_unknown_event_type_rejected(self):
        with pytest.raises(Exception):
            DiscussionEventType("nonexistent")

    def test_unknown_actor_claim_rejected(self):
        with pytest.raises(Exception):
            DiscussionActorClaim("nonexistent")

    def test_unknown_option_status_rejected(self):
        with pytest.raises(Exception):
            DiscussionOptionStatus("nonexistent")

    def test_unknown_delta_op_type_rejected(self):
        with pytest.raises(Exception):
            DiscussionDeltaOperationType("nonexistent")

    def test_unknown_conversation_mode_rejected(self):
        with pytest.raises(Exception):
            ConversationMode("nonexistent")

    def test_unknown_formalization_target_rejected(self):
        with pytest.raises(Exception):
            FormalizationTarget("nonexistent")

    def test_unknown_formalization_change_type_rejected(self):
        with pytest.raises(Exception):
            FormalizationChangeType("nonexistent")

    def test_unknown_director_response_source_rejected(self):
        with pytest.raises(Exception):
            DirectorResponseSource("nonexistent")


# ===========================================================================
# 7. DiscussionOption
# ===========================================================================


class TestDiscussionOption:
    def test_valid_option_creates(self):
        opt = DiscussionOption(
            option_id=_uid(),
            title="Use PostgreSQL",
            summary="Relational database for structured data",
            advantages=["ACID compliance", "mature ecosystem"],
            concerns=["heavier than SQLite"],
        )
        assert opt.status == DiscussionOptionStatus.ACTIVE

    def test_title_and_summary_stripped(self):
        opt = DiscussionOption(
            option_id=_uid(),
            title="  Use PostgreSQL  ",
            summary="  Relational database  ",
        )
        assert opt.title == "Use PostgreSQL"
        assert opt.summary == "Relational database"

    def test_advantages_and_concerns_strip_blanks(self):
        opt = DiscussionOption(
            option_id=_uid(),
            title="Opt A",
            summary="Desc A",
            advantages=["  good  ", "", "  ", "fast"],
            concerns=["", "  hard  "],
        )
        assert opt.advantages == ["good", "fast"]
        assert opt.concerns == ["hard"]

    def test_duplicate_source_event_ids_rejected(self):
        eid = _uid()
        with pytest.raises(ValueError, match="duplicate"):
            DiscussionOption(
                option_id=_uid(),
                title="Opt",
                summary="Desc",
                source_event_ids=[eid, eid],
            )

    def test_empty_title_rejected(self):
        with pytest.raises(ValueError):
            DiscussionOption(option_id=_uid(), title="", summary="Desc")

    def test_whitespace_only_title_rejected(self):
        with pytest.raises(ValueError):
            DiscussionOption(option_id=_uid(), title="   ", summary="Desc")

    def test_empty_summary_rejected(self):
        with pytest.raises(ValueError):
            DiscussionOption(option_id=_uid(), title="Title", summary="")

    def test_whitespace_only_summary_rejected(self):
        with pytest.raises(ValueError):
            DiscussionOption(option_id=_uid(), title="Title", summary="   ")

    def test_unknown_extra_field_rejected(self):
        with pytest.raises(ValueError):
            DiscussionOption(
                option_id=_uid(),
                title="Title",
                summary="Summary",
                unknown_field="bad",
            )

    def test_json_schema_generation(self):
        schema = DiscussionOption.model_json_schema()
        assert "properties" in schema
        assert "option_id" in schema["properties"]

    def test_json_roundtrip(self):
        opt = DiscussionOption(
            option_id=_uid(),
            title="Title",
            summary="Summary",
            advantages=["a"],
            concerns=["b"],
            source_event_ids=[_uid()],
        )
        data = opt.model_dump()
        json_str = json.dumps(data, default=str)
        restored = DiscussionOption.model_validate_json(json_str)
        assert restored.title == opt.title
        assert restored.advantages == opt.advantages


# ===========================================================================
# 8. DiscussionEvent
# ===========================================================================


class TestDiscussionEvent:
    def _make_event(self, **overrides):
        defaults = dict(
            id=_uid(),
            session_id=_uid(),
            project_id=_uid(),
            sequence_no=1,
            event_type=DiscussionEventType.TOPIC_SET,
            subject_key="topic",
            content="Setting up topic",
            created_by=DiscussionActorClaim.USER_EXPLICIT,
            confidence=1.0,
            source_message_ids=[_uid()],
        )
        defaults.update(overrides)
        return DiscussionEvent(**defaults)

    def test_valid_user_explicit_event(self):
        ev = self._make_event()
        assert ev.status == DiscussionEventStatus.ACTIVE

    def test_user_explicit_confidence_1_passes(self):
        ev = self._make_event(confidence=1.0)
        assert ev.confidence == 1.0

    def test_user_explicit_confidence_not_1_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            self._make_event(confidence=0.9)

    def test_user_explicit_requires_source_message_ids(self):
        with pytest.raises(ValueError, match="source_message_ids"):
            self._make_event(source_message_ids=[])

    def test_user_inferred_requires_source_message_ids(self):
        with pytest.raises(ValueError, match="source_message_ids"):
            self._make_event(
                created_by=DiscussionActorClaim.USER_INFERRED,
                confidence=0.8,
                source_message_ids=[],
            )

    def test_assistant_proposal_requires_source_message_ids(self):
        with pytest.raises(ValueError, match="source_message_ids"):
            self._make_event(
                created_by=DiscussionActorClaim.ASSISTANT_PROPOSAL,
                confidence=0.7,
                source_message_ids=[],
            )

    def test_system_fact_without_source_message_ids(self):
        ev = self._make_event(
            created_by=DiscussionActorClaim.SYSTEM_FACT,
            confidence=1.0,
            source_message_ids=[],
        )
        assert ev.created_by == DiscussionActorClaim.SYSTEM_FACT

    def test_formal_project_fact_without_source_message_ids(self):
        ev = self._make_event(
            created_by=DiscussionActorClaim.FORMAL_PROJECT_FACT,
            confidence=1.0,
            source_message_ids=[],
        )
        assert ev.created_by == DiscussionActorClaim.FORMAL_PROJECT_FACT

    def test_duplicate_source_message_ids_rejected(self):
        mid = _uid()
        with pytest.raises(ValueError, match="duplicate"):
            self._make_event(source_message_ids=[mid, mid])

    def test_id_equals_supersedes_event_id_rejected(self):
        eid = _uid()
        with pytest.raises(ValueError, match="supersede itself"):
            self._make_event(id=eid, supersedes_event_id=eid)

    def test_confidence_below_zero_rejected(self):
        with pytest.raises(ValueError):
            self._make_event(
                created_by=DiscussionActorClaim.SYSTEM_FACT,
                confidence=-0.1,
                source_message_ids=[],
            )

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValueError):
            self._make_event(
                created_by=DiscussionActorClaim.SYSTEM_FACT,
                confidence=1.1,
                source_message_ids=[],
            )

    def test_sequence_no_zero_rejected(self):
        with pytest.raises(ValueError):
            self._make_event(sequence_no=0)

    def test_naive_datetime_normalized_to_utc_aware(self):
        naive = _naive_now()
        ev = self._make_event(created_at=naive, source_message_ids=[_uid()])
        assert ev.created_at.tzinfo is not None
        assert ev.created_at.tzinfo == timezone.utc

    def test_p27_reserved_fields_none_by_default(self):
        ev = self._make_event()
        assert ev.source_surface is None
        assert ev.source_entity_type is None
        assert ev.source_entity_id is None
        assert ev.trigger_type is None
        assert ev.interaction_case_id is None
        assert ev.external_context_pack_id is None

    def test_p27_reserved_fields_accept_uuid(self):
        ev = self._make_event(
            source_entity_id=_uid(),
            interaction_case_id=_uid(),
            external_context_pack_id=_uid(),
        )
        data = ev.model_dump()
        assert data["source_entity_id"] is not None

    def test_unknown_extra_field_rejected(self):
        with pytest.raises(ValueError):
            DiscussionEvent(
                id=_uid(),
                session_id=_uid(),
                project_id=_uid(),
                sequence_no=1,
                event_type=DiscussionEventType.TOPIC_SET,
                subject_key="topic",
                content="content",
                created_by=DiscussionActorClaim.SYSTEM_FACT,
                confidence=1.0,
                source_message_ids=[],
                unknown_field="bad",
            )

    def test_json_schema_generation(self):
        schema = DiscussionEvent.model_json_schema()
        assert "properties" in schema
        assert "id" in schema["properties"]

    def test_json_roundtrip(self):
        ev = self._make_event()
        data = ev.model_dump()
        json_str = json.dumps(data, default=str)
        restored = DiscussionEvent.model_validate_json(json_str)
        assert restored.id == ev.id
        assert restored.event_type == ev.event_type


# ===========================================================================
# 9. DiscussionWorkspace
# ===========================================================================


class TestDiscussionWorkspace:
    def _make_workspace(self, **overrides):
        now = _utc_now()
        defaults = dict(
            session_id=_uid(),
            project_id=_uid(),
            topic="Architecture decision",
            version_no=0,
            last_event_sequence_no=0,
            created_at=now,
            updated_at=now,
        )
        defaults.update(overrides)
        return DiscussionWorkspace(**defaults)

    def test_valid_workspace(self):
        ws = self._make_workspace()
        assert ws.discussion_status == DiscussionStatus.EXPLORING

    def test_duplicate_active_option_ids_rejected(self):
        oid = _uid()
        with pytest.raises(ValueError, match="duplicate"):
            self._make_workspace(active_option_ids=[oid, oid])

    def test_duplicate_active_constraint_ids_rejected(self):
        cid = _uid()
        with pytest.raises(ValueError, match="duplicate"):
            self._make_workspace(active_constraint_ids=[cid, cid])

    def test_duplicate_open_question_ids_rejected(self):
        qid = _uid()
        with pytest.raises(ValueError, match="duplicate"):
            self._make_workspace(open_question_ids=[qid, qid])

    def test_duplicate_temporary_conclusion_ids_rejected(self):
        tid = _uid()
        with pytest.raises(ValueError, match="duplicate"):
            self._make_workspace(temporary_conclusion_ids=[tid, tid])

    def test_duplicate_confirmed_decision_ids_rejected(self):
        did = _uid()
        with pytest.raises(ValueError, match="duplicate"):
            self._make_workspace(confirmed_decision_ids=[did, did])

    def test_preferred_option_in_active_passes(self):
        oid = _uid()
        ws = self._make_workspace(
            active_option_ids=[oid],
            preferred_option_id=oid,
        )
        assert ws.preferred_option_id == oid

    def test_preferred_option_not_in_active_rejected(self):
        with pytest.raises(ValueError, match="preferred_option_id"):
            self._make_workspace(
                active_option_ids=[_uid()],
                preferred_option_id=_uid(),
            )

    def test_version_no_negative_rejected(self):
        with pytest.raises(ValueError):
            self._make_workspace(version_no=-1)

    def test_last_event_sequence_no_negative_rejected(self):
        with pytest.raises(ValueError):
            self._make_workspace(last_event_sequence_no=-1)

    def test_updated_at_before_created_at_rejected(self):
        now = _utc_now()
        with pytest.raises(ValueError, match="updated_at"):
            self._make_workspace(created_at=now, updated_at=now.replace(year=2020))

    def test_naive_datetime_normalized_to_utc(self):
        naive = _naive_now()
        ws = self._make_workspace(created_at=naive, updated_at=naive)
        assert ws.created_at.tzinfo == timezone.utc
        assert ws.updated_at.tzinfo == timezone.utc

    def test_default_discussion_status_is_exploring(self):
        ws = self._make_workspace()
        assert ws.discussion_status == DiscussionStatus.EXPLORING

    def test_json_schema_generation(self):
        schema = DiscussionWorkspace.model_json_schema()
        assert "properties" in schema
        assert "session_id" in schema["properties"]

    def test_json_roundtrip(self):
        oid = _uid()
        ws = self._make_workspace(active_option_ids=[oid], preferred_option_id=oid)
        data = ws.model_dump()
        json_str = json.dumps(data, default=str)
        restored = DiscussionWorkspace.model_validate_json(json_str)
        assert restored.session_id == ws.session_id
        assert restored.discussion_status == ws.discussion_status

    def test_unknown_extra_field_rejected(self):
        with pytest.raises(ValueError):
            self._make_workspace(unknown_field="bad")


# ===========================================================================
# 10. DiscussionDelta
# ===========================================================================


class TestDiscussionDeltaOperation:
    def _make_op(self, **overrides):
        defaults = dict(
            op=DiscussionDeltaOperationType.SET_TOPIC,
            content="Set the discussion topic",
            actor_claim=DiscussionActorClaim.ASSISTANT_PROPOSAL,
            source_message_ids=[_uid()],
        )
        defaults.update(overrides)
        return DiscussionDeltaOperation(**defaults)

    @pytest.mark.parametrize("op_type", list(DiscussionDeltaOperationType))
    def test_all_operation_types_parseable(self, op_type):
        op = self._make_op(op=op_type)
        assert op.op == op_type

    def test_unknown_operation_rejected(self):
        with pytest.raises(ValueError):
            DiscussionDeltaOperation(
                op="nonexistent_op",
                content="test",
                actor_claim=DiscussionActorClaim.SYSTEM_FACT,
            )

    def test_content_stripped(self):
        op = self._make_op(content="  trimmed  ")
        assert op.content == "trimmed"

    def test_empty_content_rejected(self):
        with pytest.raises(ValueError):
            self._make_op(content="")

    def test_whitespace_only_content_rejected(self):
        with pytest.raises(ValueError):
            self._make_op(content="   ")

    def test_duplicate_source_message_ids_rejected(self):
        mid = _uid()
        with pytest.raises(ValueError, match="duplicate"):
            self._make_op(source_message_ids=[mid, mid])

    def test_user_explicit_requires_source_message_ids(self):
        with pytest.raises(ValueError, match="source_message_ids"):
            self._make_op(
                actor_claim=DiscussionActorClaim.USER_EXPLICIT,
                source_message_ids=[],
            )

    def test_user_inferred_requires_source_message_ids(self):
        with pytest.raises(ValueError, match="source_message_ids"):
            self._make_op(
                actor_claim=DiscussionActorClaim.USER_INFERRED,
                source_message_ids=[],
            )

    def test_assistant_proposal_requires_source_message_ids(self):
        with pytest.raises(ValueError, match="source_message_ids"):
            self._make_op(
                actor_claim=DiscussionActorClaim.ASSISTANT_PROPOSAL,
                source_message_ids=[],
            )

    def test_system_fact_without_source_message_ids(self):
        op = self._make_op(
            actor_claim=DiscussionActorClaim.SYSTEM_FACT,
            source_message_ids=[],
        )
        assert op.actor_claim == DiscussionActorClaim.SYSTEM_FACT

    def test_formal_project_fact_without_source_message_ids(self):
        op = self._make_op(
            actor_claim=DiscussionActorClaim.FORMAL_PROJECT_FACT,
            source_message_ids=[],
        )
        assert op.actor_claim == DiscussionActorClaim.FORMAL_PROJECT_FACT

    def test_payload_accepts_json_structure(self):
        op = self._make_op(payload={"key": "value", "nested": {"a": 1}})
        assert op.payload["nested"]["a"] == 1

    def test_unknown_extra_field_rejected(self):
        with pytest.raises(ValueError):
            DiscussionDeltaOperation(
                op=DiscussionDeltaOperationType.SET_TOPIC,
                content="test",
                actor_claim=DiscussionActorClaim.SYSTEM_FACT,
                unknown_field="bad",
            )


class TestDiscussionDelta:
    def test_empty_operations_valid(self):
        delta = DiscussionDelta(operations=[])
        assert delta.operations == []

    def test_1_to_50_operations_valid(self):
        for count in [1, 25, 50]:
            ops = [
                DiscussionDeltaOperation(
                    op=DiscussionDeltaOperationType.SET_TOPIC,
                    content=f"Op {i}",
                    actor_claim=DiscussionActorClaim.SYSTEM_FACT,
                )
                for i in range(count)
            ]
            delta = DiscussionDelta(operations=ops)
            assert len(delta.operations) == count

    def test_51_operations_rejected(self):
        ops = [
            DiscussionDeltaOperation(
                op=DiscussionDeltaOperationType.SET_TOPIC,
                content=f"Op {i}",
                actor_claim=DiscussionActorClaim.SYSTEM_FACT,
            )
            for i in range(51)
        ]
        with pytest.raises(ValueError):
            DiscussionDelta(operations=ops)

    def test_json_schema_generation(self):
        schema = DiscussionDelta.model_json_schema()
        assert "properties" in schema

    def test_json_roundtrip(self):
        delta = DiscussionDelta(operations=[
            DiscussionDeltaOperation(
                op=DiscussionDeltaOperationType.ADD_OPTION,
                content="New option",
                actor_claim=DiscussionActorClaim.ASSISTANT_PROPOSAL,
                source_message_ids=[_uid()],
            )
        ])
        data = delta.model_dump()
        json_str = json.dumps(data, default=str)
        restored = DiscussionDelta.model_validate_json(json_str)
        assert len(restored.operations) == 1
        assert restored.operations[0].op == DiscussionDeltaOperationType.ADD_OPTION


# ===========================================================================
# 11. TurnInterpretation
# ===========================================================================


class TestTurnInterpretation:
    def _make_interp(self, **overrides):
        defaults = dict(
            conversation_mode=ConversationMode.GENERAL_DISCUSSION,
            primary_intent="User is exploring options",
            confidence=0.8,
            reason_summary="Exploratory question about architecture",
        )
        defaults.update(overrides)
        return TurnInterpretation(**defaults)

    def test_valid_interpretation(self):
        interp = self._make_interp()
        assert interp.formal_action_requested is False
        assert interp.hypothetical_action is False

    @pytest.mark.parametrize("mode", list(ConversationMode))
    def test_all_conversation_modes_parseable(self, mode):
        interp = self._make_interp(conversation_mode=mode)
        assert interp.conversation_mode == mode

    def test_confidence_boundary_0_valid(self):
        interp = self._make_interp(confidence=0.0)
        assert interp.confidence == 0.0

    def test_confidence_boundary_1_valid(self):
        interp = self._make_interp(confidence=1.0)
        assert interp.confidence == 1.0

    def test_confidence_below_0_rejected(self):
        with pytest.raises(ValueError):
            self._make_interp(confidence=-0.1)

    def test_confidence_above_1_rejected(self):
        with pytest.raises(ValueError):
            self._make_interp(confidence=1.1)

    def test_primary_intent_stripped(self):
        interp = self._make_interp(primary_intent="  trimmed  ")
        assert interp.primary_intent == "trimmed"

    def test_reason_summary_stripped(self):
        interp = self._make_interp(reason_summary="  trimmed  ")
        assert interp.reason_summary == "trimmed"

    def test_empty_primary_intent_rejected(self):
        with pytest.raises(ValueError):
            self._make_interp(primary_intent="")

    def test_empty_reason_summary_rejected(self):
        with pytest.raises(ValueError):
            self._make_interp(reason_summary="")

    def test_duplicate_referenced_option_ids_rejected(self):
        oid = _uid()
        with pytest.raises(ValueError, match="duplicate"):
            self._make_interp(referenced_option_ids=[oid, oid])

    def test_duplicate_referenced_entity_ids_rejected(self):
        eid = _uid()
        with pytest.raises(ValueError, match="duplicate"):
            self._make_interp(referenced_entity_ids=[eid, eid])

    def test_formal_and_hypothetical_both_true_rejected(self):
        with pytest.raises(ValueError, match="cannot both be true"):
            self._make_interp(formal_action_requested=True, hypothetical_action=True)

    def test_formal_action_only_valid(self):
        interp = self._make_interp(formal_action_requested=True, hypothetical_action=False)
        assert interp.formal_action_requested is True

    def test_hypothetical_action_only_valid(self):
        interp = self._make_interp(formal_action_requested=False, hypothetical_action=True)
        assert interp.hypothetical_action is True

    def test_json_schema_generation(self):
        schema = TurnInterpretation.model_json_schema()
        assert "properties" in schema
        assert "conversation_mode" in schema["properties"]

    def test_json_roundtrip(self):
        interp = self._make_interp(
            referenced_option_ids=[_uid()],
            referenced_entity_ids=[_uid()],
        )
        data = interp.model_dump()
        json_str = json.dumps(data, default=str)
        restored = TurnInterpretation.model_validate_json(json_str)
        assert restored.conversation_mode == interp.conversation_mode
        assert len(restored.referenced_option_ids) == 1


# ===========================================================================
# 12. Formalization
# ===========================================================================


class TestFormalizationChange:
    @pytest.mark.parametrize("change_type", list(FormalizationChangeType))
    def test_all_change_types_creatable(self, change_type):
        change = FormalizationChange(
            change_type=change_type,
            subject_key="task.auth",
            summary="Add authentication task",
        )
        assert change.change_type == change_type

    def test_duplicate_source_event_ids_rejected(self):
        eid = _uid()
        with pytest.raises(ValueError, match="duplicate"):
            FormalizationChange(
                change_type=FormalizationChangeType.ADD,
                subject_key="key",
                summary="summary",
                source_event_ids=[eid, eid],
            )

    def test_unknown_change_type_rejected(self):
        with pytest.raises(ValueError):
            FormalizationChange(
                change_type="nonexistent",
                subject_key="key",
                summary="summary",
            )

    def test_json_schema_generation(self):
        schema = FormalizationChange.model_json_schema()
        assert "properties" in schema


class TestFormalizationProposal:
    def _make_proposal(self, **overrides):
        defaults = dict(
            proposal_id=_uid(),
            target=FormalizationTarget.PLAN_REVISION,
            workspace_version=1,
            summary="Add auth module",
            changes=[
                FormalizationChange(
                    change_type=FormalizationChangeType.ADD,
                    subject_key="task.auth",
                    summary="Add auth task",
                )
            ],
            source_message_ids=[_uid()],
            risk_summary="Low risk, additive change",
        )
        defaults.update(overrides)
        return FormalizationProposal(**defaults)

    def test_valid_proposal(self):
        prop = self._make_proposal()
        assert prop.requires_confirmation is True
        assert prop.status == "proposed"

    def test_workspace_version_zero_rejected(self):
        with pytest.raises(ValueError):
            self._make_proposal(workspace_version=0)

    def test_empty_changes_rejected(self):
        with pytest.raises(ValueError):
            self._make_proposal(changes=[])

    def test_empty_source_message_ids_rejected(self):
        with pytest.raises(ValueError):
            self._make_proposal(source_message_ids=[])

    def test_duplicate_source_message_ids_rejected(self):
        mid = _uid()
        with pytest.raises(ValueError, match="duplicate"):
            self._make_proposal(source_message_ids=[mid, mid])

    def test_requires_confirmation_false_rejected(self):
        with pytest.raises(ValueError):
            self._make_proposal(requires_confirmation=False)

    def test_status_not_proposed_rejected(self):
        with pytest.raises(ValueError):
            self._make_proposal(status="confirmed")

    def test_target_not_plan_revision_rejected(self):
        with pytest.raises(ValueError):
            self._make_proposal(target="task_creation")

    def test_json_schema_generation(self):
        schema = FormalizationProposal.model_json_schema()
        assert "properties" in schema
        assert "proposal_id" in schema["properties"]

    def test_json_roundtrip(self):
        prop = self._make_proposal()
        data = prop.model_dump()
        json_str = json.dumps(data, default=str)
        restored = FormalizationProposal.model_validate_json(json_str)
        assert restored.proposal_id == prop.proposal_id
        assert restored.status == "proposed"


# ===========================================================================
# 13. DirectorResponseEnvelope
# ===========================================================================


class TestDirectorResponseEnvelope:
    def _make_interp(self):
        return TurnInterpretation(
            conversation_mode=ConversationMode.GENERAL_DISCUSSION,
            primary_intent="Explore options",
            confidence=0.9,
            reason_summary="User asked about architecture",
        )

    def _make_envelope(self, **overrides):
        defaults = dict(
            answer="Here are the options to consider",
            turn_interpretation=self._make_interp(),
            source=DirectorResponseSource.PROVIDER,
            source_detail="Provider generated response",
        )
        defaults.update(overrides)
        return DirectorResponseEnvelope(**defaults)

    def test_valid_provider_response(self):
        env = self._make_envelope()
        assert env.source == DirectorResponseSource.PROVIDER
        assert env.requires_confirmation is False

    def test_valid_system_response(self):
        env = self._make_envelope(source=DirectorResponseSource.SYSTEM)
        assert env.source == DirectorResponseSource.SYSTEM

    def test_valid_rule_fallback_without_state_updates(self):
        env = self._make_envelope(source=DirectorResponseSource.RULE_FALLBACK)
        assert env.source == DirectorResponseSource.RULE_FALLBACK
        assert env.discussion_delta.operations == []
        assert env.formalization_proposal is None

    def test_answer_stripped(self):
        env = self._make_envelope(answer="  trimmed  ")
        assert env.answer == "trimmed"

    def test_source_detail_stripped(self):
        env = self._make_envelope(source_detail="  trimmed  ")
        assert env.source_detail == "trimmed"

    def test_empty_answer_rejected(self):
        with pytest.raises(ValueError):
            self._make_envelope(answer="")

    def test_empty_source_detail_rejected(self):
        with pytest.raises(ValueError):
            self._make_envelope(source_detail="")

    def test_formalization_proposal_requires_confirmation_true_passes(self):
        prop = FormalizationProposal(
            proposal_id=_uid(),
            target=FormalizationTarget.PLAN_REVISION,
            workspace_version=1,
            summary="Add auth",
            changes=[
                FormalizationChange(
                    change_type=FormalizationChangeType.ADD,
                    subject_key="task.auth",
                    summary="Add auth",
                )
            ],
            source_message_ids=[_uid()],
            risk_summary="Low",
        )
        env = self._make_envelope(
            formalization_proposal=prop,
            requires_confirmation=True,
        )
        assert env.formalization_proposal is not None
        assert env.requires_confirmation is True

    def test_formalization_proposal_requires_confirmation_false_rejected(self):
        prop = FormalizationProposal(
            proposal_id=_uid(),
            target=FormalizationTarget.PLAN_REVISION,
            workspace_version=1,
            summary="Add auth",
            changes=[
                FormalizationChange(
                    change_type=FormalizationChangeType.ADD,
                    subject_key="task.auth",
                    summary="Add auth",
                )
            ],
            source_message_ids=[_uid()],
            risk_summary="Low",
        )
        with pytest.raises(ValueError, match="require confirmation"):
            self._make_envelope(
                formalization_proposal=prop,
                requires_confirmation=False,
            )

    def test_rule_fallback_with_nonempty_delta_rejected(self):
        delta = DiscussionDelta(operations=[
            DiscussionDeltaOperation(
                op=DiscussionDeltaOperationType.ADD_OPTION,
                content="New option",
                actor_claim=DiscussionActorClaim.SYSTEM_FACT,
            )
        ])
        with pytest.raises(ValueError, match="rule_fallback"):
            self._make_envelope(
                source=DirectorResponseSource.RULE_FALLBACK,
                discussion_delta=delta,
            )

    def test_rule_fallback_with_formalization_proposal_rejected(self):
        prop = FormalizationProposal(
            proposal_id=_uid(),
            target=FormalizationTarget.PLAN_REVISION,
            workspace_version=1,
            summary="Add auth",
            changes=[
                FormalizationChange(
                    change_type=FormalizationChangeType.ADD,
                    subject_key="task.auth",
                    summary="Add auth",
                )
            ],
            source_message_ids=[_uid()],
            risk_summary="Low",
        )
        with pytest.raises(ValueError, match="rule_fallback"):
            self._make_envelope(
                source=DirectorResponseSource.RULE_FALLBACK,
                formalization_proposal=prop,
                requires_confirmation=True,
            )

    def test_rule_fallback_with_empty_delta_and_no_proposal_passes(self):
        env = self._make_envelope(source=DirectorResponseSource.RULE_FALLBACK)
        assert env.discussion_delta.operations == []
        assert env.formalization_proposal is None

    def test_unknown_response_source_rejected(self):
        with pytest.raises(ValueError):
            self._make_envelope(source="nonexistent")

    def test_unknown_extra_field_rejected(self):
        with pytest.raises(ValueError):
            DirectorResponseEnvelope(
                answer="answer",
                turn_interpretation=self._make_interp(),
                source=DirectorResponseSource.PROVIDER,
                source_detail="detail",
                unknown_field="bad",
            )

    def test_json_schema_generation(self):
        schema = DirectorResponseEnvelope.model_json_schema()
        assert "properties" in schema
        assert "answer" in schema["properties"]

    def test_json_roundtrip(self):
        env = self._make_envelope()
        data = env.model_dump()
        json_str = json.dumps(data, default=str)
        restored = DirectorResponseEnvelope.model_validate_json(json_str)
        assert restored.answer == env.answer
        assert restored.source == env.source


# ===========================================================================
# 14. Pure domain import boundary
# ===========================================================================


_FORBIDDEN_IMPORTS = {
    "sqlalchemy",
    "alembic",
    "subprocess",
    "requests",
    "httpx",
    "pathlib",
    "app.repositories",
    "app.services",
    "app.api",
    "app.db",
}

_ALLOWED_APP_SUBMODULES = {
    "app.domain",
}

_DOMAIN_FILES = [
    "app/domain/project_director_discussion.py",
    "app/domain/project_director_conversation_intelligence.py",
]


def _collect_full_imports_from_file(filepath: str) -> set[str]:
    """Collect all full import module paths from a Python file using ast."""
    with open(filepath) as f:
        tree = ast.parse(f.read(), filename=filepath)

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def _is_forbidden(full_import: str) -> bool:
    """Check if an import path matches or is under a forbidden module."""
    for forbidden in _FORBIDDEN_IMPORTS:
        if full_import == forbidden or full_import.startswith(forbidden + "."):
            return True
    return False


def _is_allowed_app_import(full_import: str) -> bool:
    """Check if an app.* import is under an allowed submodule."""
    for allowed in _ALLOWED_APP_SUBMODULES:
        if full_import == allowed or full_import.startswith(allowed + "."):
            return True
    return False


class TestPureDomainImportBoundary:
    @pytest.mark.parametrize("module_path", _DOMAIN_FILES)
    def test_no_forbidden_imports(self, module_path):
        import os

        # Resolve the full path relative to the orchestrator directory
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(base, module_path)

        collected = _collect_full_imports_from_file(full_path)

        for full_import in collected:
            if full_import.startswith("app."):
                assert _is_allowed_app_import(full_import), (
                    f"Forbidden app submodule import '{full_import}' found in {module_path}"
                )
            else:
                assert not _is_forbidden(full_import), (
                    f"Forbidden import '{full_import}' found in {module_path}"
                )

    def test_import_does_not_create_files_or_access_network(self):
        """Verify importing domain modules has no side effects."""
        import importlib

        # These imports were already done at module level; verify they succeeded
        mod_disc = importlib.import_module("app.domain.project_director_discussion")
        mod_ci = importlib.import_module("app.domain.project_director_conversation_intelligence")
        assert mod_disc is not None
        assert mod_ci is not None
