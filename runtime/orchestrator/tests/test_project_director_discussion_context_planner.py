"""Contract tests for P26-E1-A deterministic discussion context planner.

Verifies that TurnInterpretation + optional DiscussionWorkspace produces a
deterministic DiscussionContextPlan with correct sections, limits, statuses,
types, scopes, dispositions, reason codes, and ID ordering.
"""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, is_dataclass
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.domain.project_director_conversation_intelligence import (
    ConversationMode,
    TurnInterpretation,
)
from app.domain.project_director_discussion import (
    DiscussionEventStatus,
    DiscussionEventType,
    DiscussionStatus,
    DiscussionWorkspace,
)
from app.services.project_director_discussion_context_planner_service import (
    DiscussionContextPlan,
    DiscussionContextSection,
    DiscussionRetrievalDisposition,
    FormalFactContextScope,
    ProjectDirectorDiscussionContextPlannerService,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def make_interpretation(
    mode: ConversationMode,
    *,
    needs_formal_fact_context: bool = False,
    needs_discussion_history: bool = False,
    needs_retrieval: bool = False,
    referenced_option_ids: list[UUID] | None = None,
    referenced_entity_ids: list[UUID] | None = None,
) -> TurnInterpretation:
    return TurnInterpretation(
        conversation_mode=mode,
        primary_intent=f"intent for {mode.value}",
        confidence=0.8,
        needs_formal_fact_context=needs_formal_fact_context,
        needs_discussion_history=needs_discussion_history,
        needs_retrieval=needs_retrieval,
        referenced_option_ids=referenced_option_ids or [],
        referenced_entity_ids=referenced_entity_ids or [],
        reason_summary=f"reason for {mode.value}",
    )


def make_workspace(
    *,
    discussion_status: DiscussionStatus = DiscussionStatus.EXPLORING,
) -> DiscussionWorkspace:
    return DiscussionWorkspace(
        session_id=uuid4(),
        project_id=None,
        topic="测试主题",
        discussion_status=discussion_status,
        version_no=1,
        last_event_sequence_no=1,
    )


SVC = ProjectDirectorDiscussionContextPlannerService()


# ═══════════════════════════════════════════════════════════════════════════
# 1. Public enum contracts
# ═══════════════════════════════════════════════════════════════════════════


class TestEnumContracts:
    def test_context_section_members(self):
        assert {m.value for m in DiscussionContextSection} == {
            "pinned_formal_facts", "recent_raw_messages",
            "active_discussion_workspace", "relevant_discussion_events",
            "current_user_message", "silent_governance_boundaries",
        }
        assert len(DiscussionContextSection) == 6

    def test_formal_fact_scope_members(self):
        assert {m.value for m in FormalFactContextScope} == {
            "core", "core_and_plan", "core_and_status",
        }
        assert len(FormalFactContextScope) == 3

    def test_retrieval_disposition_members(self):
        assert {m.value for m in DiscussionRetrievalDisposition} == {
            "not_required", "deterministic_event_lookup", "deferred_to_p28",
        }
        assert len(DiscussionRetrievalDisposition) == 3


# ═══════════════════════════════════════════════════════════════════════════
# 2. DiscussionContextPlan contract
# ═══════════════════════════════════════════════════════════════════════════


class TestPlanContract:
    def test_frozen_slots_fields(self):
        assert is_dataclass(DiscussionContextPlan)
        expected = {
            "conversation_mode", "selected_sections", "formal_fact_scope",
            "recent_message_limit", "relevant_event_limit",
            "included_event_statuses", "included_event_types",
            "referenced_option_ids", "referenced_entity_ids",
            "retrieval_disposition", "reason_codes",
        }
        assert set(DiscussionContextPlan.__slots__) == expected
        assert {f.name for f in fields(DiscussionContextPlan)} == expected

    def test_frozen_raises_on_assignment(self):
        plan = SVC.plan_context(
            interpretation=make_interpretation(ConversationMode.GENERAL_DISCUSSION),
            workspace=None,
        )
        with pytest.raises(FrozenInstanceError):
            plan.recent_message_limit = 99

    def test_output_collections_are_tuples(self):
        plan = SVC.plan_context(
            interpretation=make_interpretation(ConversationMode.GENERAL_DISCUSSION),
            workspace=None,
        )
        assert isinstance(plan.selected_sections, tuple)
        assert isinstance(plan.included_event_statuses, tuple)
        assert isinstance(plan.included_event_types, tuple)
        assert isinstance(plan.referenced_option_ids, tuple)
        assert isinstance(plan.referenced_entity_ids, tuple)
        assert isinstance(plan.reason_codes, tuple)

    def test_no_duplicate_sections(self):
        for mode in ConversationMode:
            plan = SVC.plan_context(
                interpretation=make_interpretation(mode),
                workspace=None,
            )
            assert len(plan.selected_sections) == len(set(plan.selected_sections))

    def test_no_duplicate_reason_codes(self):
        for mode in ConversationMode:
            plan = SVC.plan_context(
                interpretation=make_interpretation(mode),
                workspace=None,
            )
            assert len(plan.reason_codes) == len(set(plan.reason_codes))

    def test_no_duplicate_statuses(self):
        for mode in ConversationMode:
            plan = SVC.plan_context(
                interpretation=make_interpretation(mode),
                workspace=None,
            )
            assert len(plan.included_event_statuses) == len(set(plan.included_event_statuses))

    def test_no_duplicate_event_types(self):
        for mode in ConversationMode:
            plan = SVC.plan_context(
                interpretation=make_interpretation(mode),
                workspace=None,
            )
            assert len(plan.included_event_types) == len(set(plan.included_event_types))


# ═══════════════════════════════════════════════════════════════════════════
# 3. All modes coverage guard
# ═══════════════════════════════════════════════════════════════════════════


class TestModeCoverage:
    def test_all_modes_tested(self):
        """Dynamic check: every ConversationMode must appear in tested_modes."""
        tested_modes: set[ConversationMode] = set()
        for mode in ConversationMode:
            plan = SVC.plan_context(
                interpretation=make_interpretation(mode),
                workspace=None,
            )
            tested_modes.add(plan.conversation_mode)
        assert tested_modes == set(ConversationMode)

    def test_mode_count_matches_enum(self):
        assert len(ConversationMode) == 11


# ═══════════════════════════════════════════════════════════════════════════
# 4. Base sections for all modes
# ═══════════════════════════════════════════════════════════════════════════


class TestBaseSections:
    @pytest.mark.parametrize("mode", list(ConversationMode))
    def test_base_sections_present(self, mode):
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode),
            workspace=None,
        )
        sections = plan.selected_sections
        assert DiscussionContextSection.PINNED_FORMAL_FACTS in sections
        assert DiscussionContextSection.RECENT_RAW_MESSAGES in sections
        assert DiscussionContextSection.CURRENT_USER_MESSAGE in sections
        assert DiscussionContextSection.SILENT_GOVERNANCE_BOUNDARIES in sections

    @pytest.mark.parametrize("mode", list(ConversationMode))
    def test_base_section_order(self, mode):
        """Base sections must appear in fixed order."""
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode),
            workspace=None,
        )
        sections = plan.selected_sections
        pinned_idx = sections.index(DiscussionContextSection.PINNED_FORMAL_FACTS)
        recent_idx = sections.index(DiscussionContextSection.RECENT_RAW_MESSAGES)
        current_idx = sections.index(DiscussionContextSection.CURRENT_USER_MESSAGE)
        silent_idx = sections.index(DiscussionContextSection.SILENT_GOVERNANCE_BOUNDARIES)
        assert pinned_idx < recent_idx < current_idx < silent_idx

    @pytest.mark.parametrize("mode", list(ConversationMode))
    def test_workspace_between_recent_and_current(self, mode):
        """When workspace is selected, it goes between RECENT and CURRENT."""
        ws = make_workspace()
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode),
            workspace=ws,
        )
        sections = plan.selected_sections
        recent_idx = sections.index(DiscussionContextSection.RECENT_RAW_MESSAGES)
        current_idx = sections.index(DiscussionContextSection.CURRENT_USER_MESSAGE)
        if DiscussionContextSection.ACTIVE_DISCUSSION_WORKSPACE in sections:
            ws_idx = sections.index(DiscussionContextSection.ACTIVE_DISCUSSION_WORKSPACE)
            assert recent_idx < ws_idx < current_idx

    @pytest.mark.parametrize("mode", list(ConversationMode))
    def test_events_between_workspace_and_current(self, mode):
        """When events are selected, they go between workspace (or recent) and current."""
        ws = make_workspace()
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode, needs_discussion_history=True),
            workspace=ws,
        )
        sections = plan.selected_sections
        current_idx = sections.index(DiscussionContextSection.CURRENT_USER_MESSAGE)
        if DiscussionContextSection.RELEVANT_DISCUSSION_EVENTS in sections:
            evt_idx = sections.index(DiscussionContextSection.RELEVANT_DISCUSSION_EVENTS)
            assert evt_idx < current_idx


# ═══════════════════════════════════════════════════════════════════════════
# 5. Recent message limit
# ═══════════════════════════════════════════════════════════════════════════


_EXTENDED_MODES = [
    ConversationMode.SOLUTION_EXPLORATION,
    ConversationMode.OPTION_COMPARISON,
    ConversationMode.CHALLENGE,
    ConversationMode.CONSTRAINT_UPDATE,
    ConversationMode.PREFERENCE_UPDATE,
    ConversationMode.DECISION_CONFIRMATION,
    ConversationMode.FORMALIZATION_REQUEST,
]

_STANDARD_MODES = [
    ConversationMode.GENERAL_DISCUSSION,
    ConversationMode.CLARIFICATION,
    ConversationMode.ACTION_REQUEST,
    ConversationMode.STATUS_QUERY,
]


class TestRecentMessageLimit:
    @pytest.mark.parametrize("mode", _EXTENDED_MODES)
    def test_extended_modes_limit_12(self, mode):
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode),
            workspace=None,
        )
        assert plan.recent_message_limit == 12
        assert "extended_recent_messages_for_discussion" in plan.reason_codes
        assert "standard_recent_messages" not in plan.reason_codes

    @pytest.mark.parametrize("mode", _STANDARD_MODES)
    def test_standard_modes_limit_8(self, mode):
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode),
            workspace=None,
        )
        assert plan.recent_message_limit == 8
        assert "standard_recent_messages" in plan.reason_codes
        assert "extended_recent_messages_for_discussion" not in plan.reason_codes

    def test_limits_only_8_or_12(self):
        for mode in ConversationMode:
            plan = SVC.plan_context(
                interpretation=make_interpretation(mode),
                workspace=None,
            )
            assert plan.recent_message_limit in (8, 12)


# ═══════════════════════════════════════════════════════════════════════════
# 6. Workspace selection matrix
# ═══════════════════════════════════════════════════════════════════════════


class TestWorkspaceSelection:
    @pytest.mark.parametrize("mode", list(ConversationMode))
    def test_no_workspace_not_selected(self, mode):
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode),
            workspace=None,
        )
        assert DiscussionContextSection.ACTIVE_DISCUSSION_WORKSPACE not in plan.selected_sections
        assert "workspace_not_available" in plan.reason_codes
        assert "workspace_available" not in plan.reason_codes

    @pytest.mark.parametrize("mode", [
        ConversationMode.GENERAL_DISCUSSION,
        ConversationMode.SOLUTION_EXPLORATION,
        ConversationMode.OPTION_COMPARISON,
        ConversationMode.CLARIFICATION,
        ConversationMode.CHALLENGE,
        ConversationMode.CONSTRAINT_UPDATE,
        ConversationMode.PREFERENCE_UPDATE,
        ConversationMode.DECISION_CONFIRMATION,
        ConversationMode.FORMALIZATION_REQUEST,
    ])
    def test_nine_modes_workspace_selected(self, mode):
        ws = make_workspace()
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode),
            workspace=ws,
        )
        assert DiscussionContextSection.ACTIVE_DISCUSSION_WORKSPACE in plan.selected_sections
        assert "workspace_available" in plan.reason_codes

    @pytest.mark.parametrize("mode", [
        ConversationMode.ACTION_REQUEST,
        ConversationMode.STATUS_QUERY,
    ])
    def test_action_status_default_no_workspace(self, mode):
        ws = make_workspace()
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode),
            workspace=ws,
        )
        assert DiscussionContextSection.ACTIVE_DISCUSSION_WORKSPACE not in plan.selected_sections
        assert "workspace_not_required_for_mode" in plan.reason_codes

    @pytest.mark.parametrize("mode", [
        ConversationMode.ACTION_REQUEST,
        ConversationMode.STATUS_QUERY,
    ])
    def test_action_status_triggered_by_history(self, mode):
        ws = make_workspace()
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode, needs_discussion_history=True),
            workspace=ws,
        )
        assert DiscussionContextSection.ACTIVE_DISCUSSION_WORKSPACE in plan.selected_sections
        assert "workspace_available" in plan.reason_codes

    @pytest.mark.parametrize("mode", [
        ConversationMode.ACTION_REQUEST,
        ConversationMode.STATUS_QUERY,
    ])
    def test_action_status_triggered_by_option_refs(self, mode):
        ws = make_workspace()
        oid = uuid4()
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode, referenced_option_ids=[oid]),
            workspace=ws,
        )
        assert DiscussionContextSection.ACTIVE_DISCUSSION_WORKSPACE in plan.selected_sections

    @pytest.mark.parametrize("mode", [
        ConversationMode.ACTION_REQUEST,
        ConversationMode.STATUS_QUERY,
    ])
    def test_action_status_triggered_by_ready_to_formalize(self, mode):
        ws = make_workspace(discussion_status=DiscussionStatus.READY_TO_FORMALIZE)
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode),
            workspace=ws,
        )
        assert DiscussionContextSection.ACTIVE_DISCUSSION_WORKSPACE in plan.selected_sections


# ═══════════════════════════════════════════════════════════════════════════
# 7. Relevant events selection matrix
# ═══════════════════════════════════════════════════════════════════════════


_FORCED_HISTORY_MODES = [
    ConversationMode.OPTION_COMPARISON,
    ConversationMode.CHALLENGE,
    ConversationMode.CONSTRAINT_UPDATE,
    ConversationMode.PREFERENCE_UPDATE,
    ConversationMode.DECISION_CONFIRMATION,
    ConversationMode.FORMALIZATION_REQUEST,
]

_OPTIONAL_HISTORY_MODES = [
    ConversationMode.GENERAL_DISCUSSION,
    ConversationMode.SOLUTION_EXPLORATION,
    ConversationMode.CLARIFICATION,
    ConversationMode.ACTION_REQUEST,
    ConversationMode.STATUS_QUERY,
]


class TestRelevantEventsSelection:
    @pytest.mark.parametrize("mode", _FORCED_HISTORY_MODES)
    def test_forced_modes_always_select(self, mode):
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode),
            workspace=None,
        )
        assert DiscussionContextSection.RELEVANT_DISCUSSION_EVENTS in plan.selected_sections
        assert plan.relevant_event_limit > 0
        assert len(plan.included_event_statuses) > 0
        assert len(plan.included_event_types) > 0

    @pytest.mark.parametrize("mode", _OPTIONAL_HISTORY_MODES)
    def test_optional_modes_default_no_events(self, mode):
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode),
            workspace=None,
        )
        assert DiscussionContextSection.RELEVANT_DISCUSSION_EVENTS not in plan.selected_sections
        assert plan.relevant_event_limit == 0
        assert plan.included_event_statuses == ()
        assert plan.included_event_types == ()

    @pytest.mark.parametrize("mode", _OPTIONAL_HISTORY_MODES)
    def test_optional_triggered_by_history_flag(self, mode):
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode, needs_discussion_history=True),
            workspace=None,
        )
        assert DiscussionContextSection.RELEVANT_DISCUSSION_EVENTS in plan.selected_sections
        assert plan.relevant_event_limit > 0

    @pytest.mark.parametrize("mode", _OPTIONAL_HISTORY_MODES)
    def test_optional_triggered_by_option_refs(self, mode):
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode, referenced_option_ids=[uuid4()]),
            workspace=None,
        )
        assert DiscussionContextSection.RELEVANT_DISCUSSION_EVENTS in plan.selected_sections


# ═══════════════════════════════════════════════════════════════════════════
# 8. Event limit matrix
# ═══════════════════════════════════════════════════════════════════════════


class TestEventLimit:
    @pytest.mark.parametrize("mode", [
        ConversationMode.OPTION_COMPARISON,
        ConversationMode.CHALLENGE,
        ConversationMode.FORMALIZATION_REQUEST,
    ])
    def test_limit_40(self, mode):
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode),
            workspace=None,
        )
        assert plan.relevant_event_limit == 40

    @pytest.mark.parametrize("mode", [
        ConversationMode.CONSTRAINT_UPDATE,
        ConversationMode.PREFERENCE_UPDATE,
        ConversationMode.DECISION_CONFIRMATION,
    ])
    def test_limit_30(self, mode):
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode),
            workspace=None,
        )
        assert plan.relevant_event_limit == 30

    @pytest.mark.parametrize("mode", _OPTIONAL_HISTORY_MODES)
    def test_limit_20_when_triggered(self, mode):
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode, needs_discussion_history=True),
            workspace=None,
        )
        assert plan.relevant_event_limit == 20

    @pytest.mark.parametrize("mode", list(ConversationMode))
    def test_limit_0_when_no_events(self, mode):
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode),
            workspace=None,
        )
        if DiscussionContextSection.RELEVANT_DISCUSSION_EVENTS not in plan.selected_sections:
            assert plan.relevant_event_limit == 0


# ═══════════════════════════════════════════════════════════════════════════
# 9. Event status matrix
# ═══════════════════════════════════════════════════════════════════════════


class TestEventStatus:
    @pytest.mark.parametrize("mode", _FORCED_HISTORY_MODES)
    def test_historical_modes_include_all_statuses(self, mode):
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode),
            workspace=None,
        )
        assert plan.included_event_statuses == (
            DiscussionEventStatus.ACTIVE,
            DiscussionEventStatus.CONFIRMED,
            DiscussionEventStatus.REJECTED,
            DiscussionEventStatus.SUPERSEDED,
            DiscussionEventStatus.HISTORICAL,
        )

    @pytest.mark.parametrize("mode", _OPTIONAL_HISTORY_MODES)
    def test_optional_triggered_uses_active_only(self, mode):
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode, needs_discussion_history=True),
            workspace=None,
        )
        assert plan.included_event_statuses == (
            DiscussionEventStatus.ACTIVE,
            DiscussionEventStatus.CONFIRMED,
        )

    @pytest.mark.parametrize("mode", list(ConversationMode))
    def test_no_events_empty_statuses(self, mode):
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode),
            workspace=None,
        )
        if DiscussionContextSection.RELEVANT_DISCUSSION_EVENTS not in plan.selected_sections:
            assert plan.included_event_statuses == ()


# ═══════════════════════════════════════════════════════════════════════════
# 10. Event type matrix
# ═══════════════════════════════════════════════════════════════════════════


class TestEventType:
    def test_option_comparison_types(self):
        plan = SVC.plan_context(
            interpretation=make_interpretation(ConversationMode.OPTION_COMPARISON),
            workspace=None,
        )
        assert plan.included_event_types == (
            DiscussionEventType.OPTION_ADDED,
            DiscussionEventType.OPTION_UPDATED,
            DiscussionEventType.OPTION_PREFERRED,
            DiscussionEventType.OPTION_REJECTED,
            DiscussionEventType.CONCERN_ADDED,
            DiscussionEventType.ASSUMPTION_ADDED,
            DiscussionEventType.ASSUMPTION_REJECTED,
            DiscussionEventType.CONSTRAINT_ADDED,
            DiscussionEventType.CONSTRAINT_UPDATED,
            DiscussionEventType.CONSTRAINT_SUPERSEDED,
            DiscussionEventType.USER_CORRECTION_RECORDED,
        )

    def test_challenge_types(self):
        plan = SVC.plan_context(
            interpretation=make_interpretation(ConversationMode.CHALLENGE),
            workspace=None,
        )
        assert plan.included_event_types == (
            DiscussionEventType.CONCERN_ADDED,
            DiscussionEventType.OPTION_REJECTED,
            DiscussionEventType.ASSUMPTION_REJECTED,
            DiscussionEventType.CONSTRAINT_ADDED,
            DiscussionEventType.CONSTRAINT_UPDATED,
            DiscussionEventType.USER_CORRECTION_RECORDED,
            DiscussionEventType.TEMPORARY_CONCLUSION_ADDED,
            DiscussionEventType.DECISION_CONFIRMED,
        )

    def test_constraint_update_types(self):
        plan = SVC.plan_context(
            interpretation=make_interpretation(ConversationMode.CONSTRAINT_UPDATE),
            workspace=None,
        )
        assert plan.included_event_types == (
            DiscussionEventType.CONSTRAINT_ADDED,
            DiscussionEventType.CONSTRAINT_UPDATED,
            DiscussionEventType.CONSTRAINT_SUPERSEDED,
            DiscussionEventType.USER_CORRECTION_RECORDED,
            DiscussionEventType.DECISION_CONFIRMED,
        )

    def test_preference_update_types(self):
        plan = SVC.plan_context(
            interpretation=make_interpretation(ConversationMode.PREFERENCE_UPDATE),
            workspace=None,
        )
        assert plan.included_event_types == (
            DiscussionEventType.OPTION_ADDED,
            DiscussionEventType.OPTION_UPDATED,
            DiscussionEventType.OPTION_PREFERRED,
            DiscussionEventType.OPTION_REJECTED,
            DiscussionEventType.USER_CORRECTION_RECORDED,
        )

    def test_decision_confirmation_types(self):
        plan = SVC.plan_context(
            interpretation=make_interpretation(ConversationMode.DECISION_CONFIRMATION),
            workspace=None,
        )
        assert plan.included_event_types == (
            DiscussionEventType.OPTION_PREFERRED,
            DiscussionEventType.CONSTRAINT_ADDED,
            DiscussionEventType.CONSTRAINT_UPDATED,
            DiscussionEventType.OPEN_QUESTION_ADDED,
            DiscussionEventType.OPEN_QUESTION_RESOLVED,
            DiscussionEventType.TEMPORARY_CONCLUSION_ADDED,
            DiscussionEventType.USER_CORRECTION_RECORDED,
            DiscussionEventType.DECISION_CONFIRMED,
        )

    def test_formalization_request_types(self):
        plan = SVC.plan_context(
            interpretation=make_interpretation(ConversationMode.FORMALIZATION_REQUEST),
            workspace=None,
        )
        assert plan.included_event_types == (
            DiscussionEventType.TOPIC_SET,
            DiscussionEventType.OPTION_PREFERRED,
            DiscussionEventType.CONSTRAINT_ADDED,
            DiscussionEventType.CONSTRAINT_UPDATED,
            DiscussionEventType.CONSTRAINT_SUPERSEDED,
            DiscussionEventType.CONCERN_ADDED,
            DiscussionEventType.OPEN_QUESTION_ADDED,
            DiscussionEventType.OPEN_QUESTION_RESOLVED,
            DiscussionEventType.TEMPORARY_CONCLUSION_ADDED,
            DiscussionEventType.USER_CORRECTION_RECORDED,
            DiscussionEventType.DECISION_CONFIRMED,
            DiscussionEventType.FORMALIZATION_REQUESTED,
            DiscussionEventType.FORMALIZATION_CANCELLED,
        )

    _EXPECTED_GENERIC = (
        DiscussionEventType.TOPIC_SET,
        DiscussionEventType.OPTION_ADDED,
        DiscussionEventType.OPTION_UPDATED,
        DiscussionEventType.OPTION_PREFERRED,
        DiscussionEventType.OPTION_REJECTED,
        DiscussionEventType.CONSTRAINT_ADDED,
        DiscussionEventType.CONSTRAINT_UPDATED,
        DiscussionEventType.CONSTRAINT_SUPERSEDED,
        DiscussionEventType.CONCERN_ADDED,
        DiscussionEventType.ASSUMPTION_ADDED,
        DiscussionEventType.ASSUMPTION_REJECTED,
        DiscussionEventType.OPEN_QUESTION_ADDED,
        DiscussionEventType.OPEN_QUESTION_RESOLVED,
        DiscussionEventType.TEMPORARY_CONCLUSION_ADDED,
        DiscussionEventType.USER_CORRECTION_RECORDED,
        DiscussionEventType.DECISION_CONFIRMED,
    )

    @pytest.mark.parametrize("mode,kwargs", [
        (ConversationMode.GENERAL_DISCUSSION, {"needs_discussion_history": True}),
        (ConversationMode.SOLUTION_EXPLORATION, {"needs_discussion_history": True}),
        (ConversationMode.CLARIFICATION, {"referenced_option_ids": [uuid4()]}),
        (ConversationMode.ACTION_REQUEST, {"needs_discussion_history": True}),
        (ConversationMode.STATUS_QUERY, {"referenced_option_ids": [uuid4()]}),
    ])
    def test_generic_history_types(self, mode, kwargs):
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode, **kwargs),
            workspace=None,
        )
        assert plan.included_event_types == self._EXPECTED_GENERIC

    def test_no_events_empty_types(self):
        for mode in ConversationMode:
            plan = SVC.plan_context(
                interpretation=make_interpretation(mode),
                workspace=None,
            )
            if DiscussionContextSection.RELEVANT_DISCUSSION_EVENTS not in plan.selected_sections:
                assert plan.included_event_types == ()


# ═══════════════════════════════════════════════════════════════════════════
# 11. Formal fact scope
# ═══════════════════════════════════════════════════════════════════════════


class TestFormalFactScope:
    @pytest.mark.parametrize("mode", [
        ConversationMode.GENERAL_DISCUSSION,
        ConversationMode.CLARIFICATION,
    ])
    def test_core_default(self, mode):
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode),
            workspace=None,
        )
        assert plan.formal_fact_scope is FormalFactContextScope.CORE

    @pytest.mark.parametrize("mode", [
        ConversationMode.GENERAL_DISCUSSION,
        ConversationMode.CLARIFICATION,
    ])
    def test_core_to_plan_with_flag(self, mode):
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode, needs_formal_fact_context=True),
            workspace=None,
        )
        assert plan.formal_fact_scope is FormalFactContextScope.CORE_AND_PLAN

    @pytest.mark.parametrize("mode", _EXTENDED_MODES)
    def test_plan_context_modes(self, mode):
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode),
            workspace=None,
        )
        assert plan.formal_fact_scope is FormalFactContextScope.CORE_AND_PLAN
        assert "mode_requires_plan_context" in plan.reason_codes

    @pytest.mark.parametrize("mode", [
        ConversationMode.ACTION_REQUEST,
        ConversationMode.STATUS_QUERY,
    ])
    def test_status_context_modes(self, mode):
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode),
            workspace=None,
        )
        assert plan.formal_fact_scope is FormalFactContextScope.CORE_AND_STATUS
        assert "mode_requires_status_context" in plan.reason_codes

    @pytest.mark.parametrize("mode", [
        ConversationMode.ACTION_REQUEST,
        ConversationMode.STATUS_QUERY,
    ])
    def test_status_scope_not_overridden_by_flag(self, mode):
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode, needs_formal_fact_context=True),
            workspace=None,
        )
        assert plan.formal_fact_scope is FormalFactContextScope.CORE_AND_STATUS


# ═══════════════════════════════════════════════════════════════════════════
# 12. Retrieval disposition
# ═══════════════════════════════════════════════════════════════════════════


class TestRetrievalDisposition:
    def test_not_required_when_no_events(self):
        plan = SVC.plan_context(
            interpretation=make_interpretation(ConversationMode.GENERAL_DISCUSSION),
            workspace=None,
        )
        assert plan.retrieval_disposition is DiscussionRetrievalDisposition.NOT_REQUIRED
        assert "retrieval_not_required" in plan.reason_codes

    def test_deterministic_when_events_selected(self):
        plan = SVC.plan_context(
            interpretation=make_interpretation(
                ConversationMode.GENERAL_DISCUSSION, needs_discussion_history=True,
            ),
            workspace=None,
        )
        assert plan.retrieval_disposition is DiscussionRetrievalDisposition.DETERMINISTIC_EVENT_LOOKUP
        assert "deterministic_event_lookup_selected" in plan.reason_codes

    def test_deferred_no_events(self):
        plan = SVC.plan_context(
            interpretation=make_interpretation(
                ConversationMode.GENERAL_DISCUSSION, needs_retrieval=True,
            ),
            workspace=None,
        )
        assert plan.retrieval_disposition is DiscussionRetrievalDisposition.DEFERRED_TO_P28
        assert DiscussionContextSection.RELEVANT_DISCUSSION_EVENTS not in plan.selected_sections
        assert "retrieval_requested_but_deferred_to_p28" in plan.reason_codes
        assert "deterministic_event_lookup_selected" not in plan.reason_codes

    @pytest.mark.parametrize("mode,kwargs", [
        (ConversationMode.OPTION_COMPARISON, {}),
        (ConversationMode.GENERAL_DISCUSSION, {"needs_discussion_history": True}),
        (ConversationMode.STATUS_QUERY, {"referenced_option_ids": [uuid4()]}),
    ])
    def test_deferred_preserves_deterministic_events(self, mode, kwargs):
        plan = SVC.plan_context(
            interpretation=make_interpretation(mode, needs_retrieval=True, **kwargs),
            workspace=None,
        )
        assert plan.retrieval_disposition is DiscussionRetrievalDisposition.DEFERRED_TO_P28
        assert DiscussionContextSection.RELEVANT_DISCUSSION_EVENTS in plan.selected_sections
        assert plan.relevant_event_limit > 0
        assert len(plan.included_event_statuses) > 0
        assert len(plan.included_event_types) > 0
        assert "retrieval_requested_but_deferred_to_p28" in plan.reason_codes
        assert "deterministic_event_lookup_selected" not in plan.reason_codes


# ═══════════════════════════════════════════════════════════════════════════
# 13. Reason code order and completeness
# ═══════════════════════════════════════════════════════════════════════════


_ALLOWED_CODES = frozenset({
    "baseline_sections_required",
    "extended_recent_messages_for_discussion",
    "standard_recent_messages",
    "workspace_available",
    "workspace_not_available",
    "workspace_not_required_for_mode",
    "discussion_history_requested",
    "mode_requires_discussion_history",
    "referenced_options_require_history",
    "formal_fact_context_requested",
    "mode_requires_plan_context",
    "mode_requires_status_context",
    "deterministic_event_lookup_selected",
    "retrieval_not_required",
    "retrieval_requested_but_deferred_to_p28",
})


class TestReasonCodes:
    def test_all_codes_in_whitelist(self):
        for mode in ConversationMode:
            for ws in [None, make_workspace()]:
                for hist in [False, True]:
                    for ret in [False, True]:
                        plan = SVC.plan_context(
                            interpretation=make_interpretation(
                                mode, needs_discussion_history=hist,
                                needs_retrieval=ret,
                            ),
                            workspace=ws,
                        )
                        for code in plan.reason_codes:
                            assert code in _ALLOWED_CODES, f"Unknown code: {code}"

    def test_high_combination_exact_reasons(self):
        """OPTION_COMPARISON + workspace + history + formal_fact + retrieval + option refs."""
        oid = uuid4()
        ws = make_workspace()
        plan = SVC.plan_context(
            interpretation=make_interpretation(
                ConversationMode.OPTION_COMPARISON,
                needs_discussion_history=True,
                needs_formal_fact_context=True,
                needs_retrieval=True,
                referenced_option_ids=[oid],
            ),
            workspace=ws,
        )
        assert plan.reason_codes == (
            "baseline_sections_required",
            "extended_recent_messages_for_discussion",
            "workspace_available",
            "discussion_history_requested",
            "mode_requires_discussion_history",
            "referenced_options_require_history",
            "formal_fact_context_requested",
            "mode_requires_plan_context",
            "retrieval_requested_but_deferred_to_p28",
        )

    def test_status_query_exact_reasons(self):
        ws = make_workspace()
        plan = SVC.plan_context(
            interpretation=make_interpretation(
                ConversationMode.STATUS_QUERY,
                needs_formal_fact_context=True,
            ),
            workspace=ws,
        )
        assert plan.reason_codes == (
            "baseline_sections_required",
            "standard_recent_messages",
            "workspace_not_required_for_mode",
            "formal_fact_context_requested",
            "mode_requires_status_context",
            "retrieval_not_required",
        )


# ═══════════════════════════════════════════════════════════════════════════
# 14. Referenced ID order
# ═══════════════════════════════════════════════════════════════════════════


class TestReferencedIDs:
    def test_ids_preserve_order(self):
        ids = [uuid4(), uuid4(), uuid4()]
        plan = SVC.plan_context(
            interpretation=make_interpretation(
                ConversationMode.GENERAL_DISCUSSION,
                referenced_option_ids=ids,
            ),
            workspace=None,
        )
        assert plan.referenced_option_ids == tuple(ids)

    def test_entity_ids_preserve_order(self):
        ids = [uuid4(), uuid4(), uuid4()]
        plan = SVC.plan_context(
            interpretation=make_interpretation(
                ConversationMode.GENERAL_DISCUSSION,
                referenced_entity_ids=ids,
            ),
            workspace=None,
        )
        assert plan.referenced_entity_ids == tuple(ids)

    def test_input_list_not_sorted(self):
        ids = [uuid4(), uuid4(), uuid4()]
        interp = make_interpretation(
            ConversationMode.GENERAL_DISCUSSION,
            referenced_option_ids=list(ids),
        )
        SVC.plan_context(interpretation=interp, workspace=None)
        assert interp.referenced_option_ids == list(ids)


# ═══════════════════════════════════════════════════════════════════════════
# 15. Input immutability
# ═══════════════════════════════════════════════════════════════════════════


class TestInputImmutability:
    def test_interpretation_not_mutated(self):
        interp = make_interpretation(
            ConversationMode.OPTION_COMPARISON,
            needs_discussion_history=True,
            needs_retrieval=True,
            referenced_option_ids=[uuid4()],
            referenced_entity_ids=[uuid4()],
        )
        before = interp.model_dump(mode="python")
        SVC.plan_context(interpretation=interp, workspace=None)
        assert interp.model_dump(mode="python") == before

    def test_workspace_not_mutated(self):
        ws = make_workspace()
        before = ws.model_dump(mode="python")
        SVC.plan_context(
            interpretation=make_interpretation(ConversationMode.GENERAL_DISCUSSION),
            workspace=ws,
        )
        assert ws.model_dump(mode="python") == before

    def test_no_workspace_scenario(self):
        interp = make_interpretation(ConversationMode.GENERAL_DISCUSSION)
        before = interp.model_dump(mode="python")
        SVC.plan_context(interpretation=interp, workspace=None)
        assert interp.model_dump(mode="python") == before


# ═══════════════════════════════════════════════════════════════════════════
# 16. Determinism
# ═══════════════════════════════════════════════════════════════════════════


class TestDeterminism:
    @pytest.mark.parametrize("mode", list(ConversationMode))
    def test_same_instance_deterministic(self, mode):
        interp = make_interpretation(mode)
        p1 = SVC.plan_context(interpretation=interp, workspace=None)
        p2 = SVC.plan_context(interpretation=interp, workspace=None)
        assert p1 == p2

    @pytest.mark.parametrize("mode", list(ConversationMode))
    def test_different_instances_deterministic(self, mode):
        interp1 = make_interpretation(mode)
        interp2 = make_interpretation(mode)
        svc1 = ProjectDirectorDiscussionContextPlannerService()
        svc2 = ProjectDirectorDiscussionContextPlannerService()
        p1 = svc1.plan_context(interpretation=interp1, workspace=None)
        p2 = svc2.plan_context(interpretation=interp2, workspace=None)
        assert p1 == p2

    def test_complex_scenario_deterministic(self):
        interp = make_interpretation(
            ConversationMode.OPTION_COMPARISON,
            needs_discussion_history=True,
            needs_formal_fact_context=True,
            needs_retrieval=True,
            referenced_option_ids=[uuid4()],
        )
        ws = make_workspace()
        plans = [SVC.plan_context(interpretation=interp, workspace=ws) for _ in range(5)]
        for p in plans[1:]:
            assert p == plans[0]


# ═══════════════════════════════════════════════════════════════════════════
# 17. AST boundary
# ═══════════════════════════════════════════════════════════════════════════


class TestASTBoundary:
    @pytest.fixture(scope="class")
    def planner_ast(self):
        path = Path(__file__).parents[1] / "app/services/project_director_discussion_context_planner_service.py"
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

    def _get_names(self, node: ast.Module) -> set[str]:
        names: set[str] = set()
        for n in ast.walk(node):
            if isinstance(n, ast.Name):
                names.add(n.id)
            elif isinstance(n, ast.Attribute):
                names.add(n.attr)
        return names

    def test_no_sqlalchemy(self, planner_ast):
        imports = self._get_imports(planner_ast)
        for imp in imports:
            assert "sqlalchemy" not in imp.lower()

    def test_no_repository(self, planner_ast):
        imports = self._get_imports(planner_ast)
        for imp in imports:
            assert not imp.startswith("app.repositories")

    def test_no_session_create_engine(self, planner_ast):
        imports = self._get_imports(planner_ast)
        for imp in imports:
            assert "create_engine" not in imp
            assert "sessionmaker" not in imp

    def test_no_provider_message_service(self, planner_ast):
        imports = self._get_imports(planner_ast)
        for imp in imports:
            assert "provider" not in imp.lower()
            assert "message_service" not in imp.lower()

    def test_no_uuid4_datetime_now(self, planner_ast):
        names = self._get_names(planner_ast)
        assert "uuid4" not in names
        assert "now" not in names or "utc_now" not in names

    def test_no_commit_rollback(self, planner_ast):
        imports = self._get_imports(planner_ast)
        for imp in imports:
            assert "commit" not in imp.lower()
            assert "rollback" not in imp.lower()

    def test_allowed_imports(self, planner_ast):
        imports = self._get_imports(planner_ast)
        allowed = {
            "__future__", "dataclasses", "enum", "uuid",
            "app.domain._base",
            "app.domain.project_director_conversation_intelligence",
            "app.domain.project_director_discussion",
        }
        for imp in imports:
            assert imp in allowed, f"Unexpected import: {imp}"
