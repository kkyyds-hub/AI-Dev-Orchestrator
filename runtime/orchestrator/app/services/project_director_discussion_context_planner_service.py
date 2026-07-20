"""Pure deterministic planning for Project Director discussion context."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

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


class DiscussionContextSection(StrEnum):
    """A read-only section that a later stage may assemble."""

    PINNED_FORMAL_FACTS = "pinned_formal_facts"
    RECENT_RAW_MESSAGES = "recent_raw_messages"
    ACTIVE_DISCUSSION_WORKSPACE = "active_discussion_workspace"
    RELEVANT_DISCUSSION_EVENTS = "relevant_discussion_events"
    CURRENT_USER_MESSAGE = "current_user_message"
    SILENT_GOVERNANCE_BOUNDARIES = "silent_governance_boundaries"


class FormalFactContextScope(StrEnum):
    """The formal-fact read scope requested by a plan."""

    CORE = "core"
    CORE_AND_PLAN = "core_and_plan"
    CORE_AND_STATUS = "core_and_status"


class DiscussionRetrievalDisposition(StrEnum):
    """How a later stage should obtain historical discussion evidence."""

    NOT_REQUIRED = "not_required"
    DETERMINISTIC_EVENT_LOOKUP = "deterministic_event_lookup"
    DEFERRED_TO_P28 = "deferred_to_p28"


@dataclass(frozen=True, slots=True)
class DiscussionContextPlan:
    """Stable, side-effect-free read plan for one interpreted turn."""

    conversation_mode: ConversationMode
    selected_sections: tuple[DiscussionContextSection, ...]
    formal_fact_scope: FormalFactContextScope

    recent_message_limit: int
    relevant_event_limit: int

    included_event_statuses: tuple[DiscussionEventStatus, ...]
    included_event_types: tuple[DiscussionEventType, ...]

    referenced_option_ids: tuple[UUID, ...]
    referenced_entity_ids: tuple[UUID, ...]

    retrieval_disposition: DiscussionRetrievalDisposition
    reason_codes: tuple[str, ...]


_EXTENDED_RECENT_MESSAGE_MODES = (
    ConversationMode.SOLUTION_EXPLORATION,
    ConversationMode.OPTION_COMPARISON,
    ConversationMode.CHALLENGE,
    ConversationMode.CONSTRAINT_UPDATE,
    ConversationMode.PREFERENCE_UPDATE,
    ConversationMode.DECISION_CONFIRMATION,
    ConversationMode.FORMALIZATION_REQUEST,
)

_WORKSPACE_REQUIRED_MODES = (
    ConversationMode.GENERAL_DISCUSSION,
    ConversationMode.SOLUTION_EXPLORATION,
    ConversationMode.OPTION_COMPARISON,
    ConversationMode.CLARIFICATION,
    ConversationMode.CHALLENGE,
    ConversationMode.CONSTRAINT_UPDATE,
    ConversationMode.PREFERENCE_UPDATE,
    ConversationMode.DECISION_CONFIRMATION,
    ConversationMode.FORMALIZATION_REQUEST,
)

_MODE_REQUIRING_HISTORY = (
    ConversationMode.OPTION_COMPARISON,
    ConversationMode.CHALLENGE,
    ConversationMode.CONSTRAINT_UPDATE,
    ConversationMode.PREFERENCE_UPDATE,
    ConversationMode.DECISION_CONFIRMATION,
    ConversationMode.FORMALIZATION_REQUEST,
)

_PLAN_CONTEXT_MODES = _EXTENDED_RECENT_MESSAGE_MODES

_STATUS_CONTEXT_MODES = (
    ConversationMode.STATUS_QUERY,
    ConversationMode.ACTION_REQUEST,
)

_HISTORICAL_EVENT_STATUS_MODES = _MODE_REQUIRING_HISTORY

_ACTIVE_EVENT_STATUSES = (
    DiscussionEventStatus.ACTIVE,
    DiscussionEventStatus.CONFIRMED,
)

_HISTORICAL_EVENT_STATUSES = (
    *_ACTIVE_EVENT_STATUSES,
    DiscussionEventStatus.REJECTED,
    DiscussionEventStatus.SUPERSEDED,
    DiscussionEventStatus.HISTORICAL,
)

_OPTION_COMPARISON_EVENT_TYPES = (
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

_CHALLENGE_EVENT_TYPES = (
    DiscussionEventType.CONCERN_ADDED,
    DiscussionEventType.OPTION_REJECTED,
    DiscussionEventType.ASSUMPTION_REJECTED,
    DiscussionEventType.CONSTRAINT_ADDED,
    DiscussionEventType.CONSTRAINT_UPDATED,
    DiscussionEventType.USER_CORRECTION_RECORDED,
    DiscussionEventType.TEMPORARY_CONCLUSION_ADDED,
    DiscussionEventType.DECISION_CONFIRMED,
)

_CONSTRAINT_UPDATE_EVENT_TYPES = (
    DiscussionEventType.CONSTRAINT_ADDED,
    DiscussionEventType.CONSTRAINT_UPDATED,
    DiscussionEventType.CONSTRAINT_SUPERSEDED,
    DiscussionEventType.USER_CORRECTION_RECORDED,
    DiscussionEventType.DECISION_CONFIRMED,
)

_PREFERENCE_UPDATE_EVENT_TYPES = (
    DiscussionEventType.OPTION_ADDED,
    DiscussionEventType.OPTION_UPDATED,
    DiscussionEventType.OPTION_PREFERRED,
    DiscussionEventType.OPTION_REJECTED,
    DiscussionEventType.USER_CORRECTION_RECORDED,
)

_DECISION_CONFIRMATION_EVENT_TYPES = (
    DiscussionEventType.OPTION_PREFERRED,
    DiscussionEventType.CONSTRAINT_ADDED,
    DiscussionEventType.CONSTRAINT_UPDATED,
    DiscussionEventType.OPEN_QUESTION_ADDED,
    DiscussionEventType.OPEN_QUESTION_RESOLVED,
    DiscussionEventType.TEMPORARY_CONCLUSION_ADDED,
    DiscussionEventType.USER_CORRECTION_RECORDED,
    DiscussionEventType.DECISION_CONFIRMED,
)

_FORMALIZATION_REQUEST_EVENT_TYPES = (
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

_GENERIC_HISTORY_EVENT_TYPES = (
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


class ProjectDirectorDiscussionContextPlannerService:
    """Choose a stable discussion-context plan without reading any state."""

    def plan_context(
        self,
        *,
        interpretation: TurnInterpretation,
        workspace: DiscussionWorkspace | None,
    ) -> DiscussionContextPlan:
        """Return the deterministic context plan for ``interpretation``."""

        mode = interpretation.conversation_mode
        reason_codes: list[str] = ["baseline_sections_required"]
        selected_sections: list[DiscussionContextSection] = [
            DiscussionContextSection.PINNED_FORMAL_FACTS,
            DiscussionContextSection.RECENT_RAW_MESSAGES,
        ]

        recent_message_limit = self._recent_message_limit(mode)
        reason_codes.append(
            "extended_recent_messages_for_discussion"
            if recent_message_limit == 12
            else "standard_recent_messages"
        )

        workspace_selected = self._should_include_workspace(
            interpretation=interpretation, workspace=workspace
        )
        if workspace_selected:
            selected_sections.append(DiscussionContextSection.ACTIVE_DISCUSSION_WORKSPACE)
            reason_codes.append("workspace_available")
        elif workspace is None:
            reason_codes.append("workspace_not_available")
        else:
            reason_codes.append("workspace_not_required_for_mode")

        relevant_events_selected = self._should_include_relevant_events(interpretation)
        if relevant_events_selected:
            selected_sections.append(DiscussionContextSection.RELEVANT_DISCUSSION_EVENTS)

        self._append_history_reason_codes(
            reason_codes=reason_codes, interpretation=interpretation
        )

        formal_fact_scope = self._formal_fact_scope(interpretation)
        self._append_formal_fact_reason_codes(
            reason_codes=reason_codes, interpretation=interpretation
        )

        retrieval_disposition = self._retrieval_disposition(
            needs_retrieval=interpretation.needs_retrieval,
            relevant_events_selected=relevant_events_selected,
        )
        reason_codes.append(
            self._retrieval_reason_code(retrieval_disposition)
        )

        selected_sections.extend(
            (
                DiscussionContextSection.CURRENT_USER_MESSAGE,
                DiscussionContextSection.SILENT_GOVERNANCE_BOUNDARIES,
            )
        )

        return DiscussionContextPlan(
            conversation_mode=mode,
            selected_sections=tuple(selected_sections),
            formal_fact_scope=formal_fact_scope,
            recent_message_limit=recent_message_limit,
            relevant_event_limit=self._relevant_event_limit(
                mode=mode, relevant_events_selected=relevant_events_selected
            ),
            included_event_statuses=self._included_event_statuses(
                mode=mode, relevant_events_selected=relevant_events_selected
            ),
            included_event_types=self._included_event_types(
                mode=mode, relevant_events_selected=relevant_events_selected
            ),
            referenced_option_ids=tuple(interpretation.referenced_option_ids),
            referenced_entity_ids=tuple(interpretation.referenced_entity_ids),
            retrieval_disposition=retrieval_disposition,
            reason_codes=tuple(reason_codes),
        )

    @staticmethod
    def _recent_message_limit(mode: ConversationMode) -> int:
        return 12 if mode in _EXTENDED_RECENT_MESSAGE_MODES else 8

    @staticmethod
    def _should_include_workspace(
        *,
        interpretation: TurnInterpretation,
        workspace: DiscussionWorkspace | None,
    ) -> bool:
        if workspace is None:
            return False
        if interpretation.conversation_mode in _WORKSPACE_REQUIRED_MODES:
            return True
        return (
            interpretation.needs_discussion_history
            or bool(interpretation.referenced_option_ids)
            or workspace.discussion_status == DiscussionStatus.READY_TO_FORMALIZE
        )

    @staticmethod
    def _should_include_relevant_events(interpretation: TurnInterpretation) -> bool:
        return (
            interpretation.needs_discussion_history
            or bool(interpretation.referenced_option_ids)
            or interpretation.conversation_mode in _MODE_REQUIRING_HISTORY
        )

    @staticmethod
    def _append_history_reason_codes(
        *,
        reason_codes: list[str],
        interpretation: TurnInterpretation,
    ) -> None:
        if interpretation.needs_discussion_history:
            reason_codes.append("discussion_history_requested")
        if interpretation.conversation_mode in _MODE_REQUIRING_HISTORY:
            reason_codes.append("mode_requires_discussion_history")
        if interpretation.referenced_option_ids:
            reason_codes.append("referenced_options_require_history")

    @staticmethod
    def _formal_fact_scope(
        interpretation: TurnInterpretation,
    ) -> FormalFactContextScope:
        mode = interpretation.conversation_mode
        if mode in _STATUS_CONTEXT_MODES:
            return FormalFactContextScope.CORE_AND_STATUS
        if (
            interpretation.needs_formal_fact_context
            or mode in _PLAN_CONTEXT_MODES
        ):
            return FormalFactContextScope.CORE_AND_PLAN
        return FormalFactContextScope.CORE

    @staticmethod
    def _append_formal_fact_reason_codes(
        *,
        reason_codes: list[str],
        interpretation: TurnInterpretation,
    ) -> None:
        if interpretation.needs_formal_fact_context:
            reason_codes.append("formal_fact_context_requested")
        if interpretation.conversation_mode in _PLAN_CONTEXT_MODES:
            reason_codes.append("mode_requires_plan_context")
        if interpretation.conversation_mode in _STATUS_CONTEXT_MODES:
            reason_codes.append("mode_requires_status_context")

    @staticmethod
    def _relevant_event_limit(
        *,
        mode: ConversationMode,
        relevant_events_selected: bool,
    ) -> int:
        if not relevant_events_selected:
            return 0
        if mode in (
            ConversationMode.OPTION_COMPARISON,
            ConversationMode.CHALLENGE,
            ConversationMode.FORMALIZATION_REQUEST,
        ):
            return 40
        if mode in (
            ConversationMode.CONSTRAINT_UPDATE,
            ConversationMode.PREFERENCE_UPDATE,
            ConversationMode.DECISION_CONFIRMATION,
        ):
            return 30
        return 20

    @staticmethod
    def _included_event_statuses(
        *,
        mode: ConversationMode,
        relevant_events_selected: bool,
    ) -> tuple[DiscussionEventStatus, ...]:
        if not relevant_events_selected:
            return ()
        if mode in _HISTORICAL_EVENT_STATUS_MODES:
            return _HISTORICAL_EVENT_STATUSES
        return _ACTIVE_EVENT_STATUSES

    @staticmethod
    def _included_event_types(
        *,
        mode: ConversationMode,
        relevant_events_selected: bool,
    ) -> tuple[DiscussionEventType, ...]:
        if not relevant_events_selected:
            return ()
        if mode == ConversationMode.OPTION_COMPARISON:
            return _OPTION_COMPARISON_EVENT_TYPES
        if mode == ConversationMode.CHALLENGE:
            return _CHALLENGE_EVENT_TYPES
        if mode == ConversationMode.CONSTRAINT_UPDATE:
            return _CONSTRAINT_UPDATE_EVENT_TYPES
        if mode == ConversationMode.PREFERENCE_UPDATE:
            return _PREFERENCE_UPDATE_EVENT_TYPES
        if mode == ConversationMode.DECISION_CONFIRMATION:
            return _DECISION_CONFIRMATION_EVENT_TYPES
        if mode == ConversationMode.FORMALIZATION_REQUEST:
            return _FORMALIZATION_REQUEST_EVENT_TYPES
        return _GENERIC_HISTORY_EVENT_TYPES

    @staticmethod
    def _retrieval_disposition(
        *,
        needs_retrieval: bool,
        relevant_events_selected: bool,
    ) -> DiscussionRetrievalDisposition:
        if needs_retrieval:
            return DiscussionRetrievalDisposition.DEFERRED_TO_P28
        if relevant_events_selected:
            return DiscussionRetrievalDisposition.DETERMINISTIC_EVENT_LOOKUP
        return DiscussionRetrievalDisposition.NOT_REQUIRED

    @staticmethod
    def _retrieval_reason_code(
        disposition: DiscussionRetrievalDisposition,
    ) -> str:
        if disposition == DiscussionRetrievalDisposition.DEFERRED_TO_P28:
            return "retrieval_requested_but_deferred_to_p28"
        if disposition == DiscussionRetrievalDisposition.DETERMINISTIC_EVENT_LOOKUP:
            return "deterministic_event_lookup_selected"
        return "retrieval_not_required"
