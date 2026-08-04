"""Pure governed admission for unpersisted Project Director discussion deltas."""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, StrEnum
from hashlib import sha256
import json
import math
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from app.domain._base import ensure_utc_datetime
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
)
from app.services.project_director_discussion_workspace_reducer_service import (
    ProjectDirectorDiscussionWorkspaceReducerService,
)


class DiscussionDeltaGateStatus(StrEnum):
    """The admission outcome for a complete candidate delta."""

    PREPARED = "prepared"
    REQUIRES_CONFIRMATION = "requires_confirmation"


@dataclass(frozen=True, slots=True)
class PreparedDiscussionEvent:
    """One deterministic, not-yet-persisted discussion event."""

    operation_index: int
    event: DiscussionEvent
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class DiscussionDeltaOperationIdentity:
    """Deterministic persistence identity for one candidate operation."""

    operation_index: int
    event_id: UUID
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class _PreparedOperation:
    """Internal canonical operation details shared by Gate and replay lookup."""

    identity: DiscussionDeltaOperationIdentity
    event_type: DiscussionEventType
    payload: dict[str, Any]
    subject_key: str
    operation_hash: str


@dataclass(frozen=True, slots=True)
class GovernedDiscussionDeltaResult:
    """Pure admission result and its derived workspace projection."""

    status: DiscussionDeltaGateStatus
    prepared_events: tuple[PreparedDiscussionEvent, ...]
    projected_workspace: DiscussionWorkspace
    confirmation_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DiscussionDeltaOperationAdmissionRule:
    """Immutable operation-level admission contract shared with provider preflight."""

    target_rule: str
    supersedes_rule: str
    actor_rule: str
    requires_option_target: bool = False
    requires_active_option_target: bool = False
    requires_new_option_target: bool = False
    requires_supersedes: bool = False
    allows_supersedes: bool = False
    supersedes_event_types: frozenset[DiscussionEventType] | None = None
    supersedes_same_option: bool = False


_OPERATION_EVENT_TYPES: dict[DiscussionDeltaOperationType, DiscussionEventType] = {
    DiscussionDeltaOperationType.SET_TOPIC: DiscussionEventType.TOPIC_SET,
    DiscussionDeltaOperationType.ADD_OPTION: DiscussionEventType.OPTION_ADDED,
    DiscussionDeltaOperationType.UPDATE_OPTION: DiscussionEventType.OPTION_UPDATED,
    DiscussionDeltaOperationType.PREFER_OPTION: DiscussionEventType.OPTION_PREFERRED,
    DiscussionDeltaOperationType.REJECT_OPTION: DiscussionEventType.OPTION_REJECTED,
    DiscussionDeltaOperationType.ADD_CONSTRAINT: DiscussionEventType.CONSTRAINT_ADDED,
    DiscussionDeltaOperationType.UPDATE_CONSTRAINT: DiscussionEventType.CONSTRAINT_UPDATED,
    DiscussionDeltaOperationType.SUPERSEDE_CONSTRAINT: DiscussionEventType.CONSTRAINT_SUPERSEDED,
    DiscussionDeltaOperationType.ADD_CONCERN: DiscussionEventType.CONCERN_ADDED,
    DiscussionDeltaOperationType.ADD_ASSUMPTION: DiscussionEventType.ASSUMPTION_ADDED,
    DiscussionDeltaOperationType.REJECT_ASSUMPTION: DiscussionEventType.ASSUMPTION_REJECTED,
    DiscussionDeltaOperationType.ADD_OPEN_QUESTION: DiscussionEventType.OPEN_QUESTION_ADDED,
    DiscussionDeltaOperationType.RESOLVE_OPEN_QUESTION: DiscussionEventType.OPEN_QUESTION_RESOLVED,
    DiscussionDeltaOperationType.ADD_TEMPORARY_CONCLUSION: (
        DiscussionEventType.TEMPORARY_CONCLUSION_ADDED
    ),
    DiscussionDeltaOperationType.RECORD_USER_CORRECTION: (
        DiscussionEventType.USER_CORRECTION_RECORDED
    ),
    DiscussionDeltaOperationType.CONFIRM_DECISION: DiscussionEventType.DECISION_CONFIRMED,
    DiscussionDeltaOperationType.REQUEST_FORMALIZATION: (
        DiscussionEventType.FORMALIZATION_REQUESTED
    ),
    DiscussionDeltaOperationType.CANCEL_FORMALIZATION: (
        DiscussionEventType.FORMALIZATION_CANCELLED
    ),
}

_ADDITIVE_OPERATIONS = frozenset(
    {
        DiscussionDeltaOperationType.SET_TOPIC,
        DiscussionDeltaOperationType.ADD_OPTION,
        DiscussionDeltaOperationType.ADD_CONSTRAINT,
        DiscussionDeltaOperationType.ADD_CONCERN,
        DiscussionDeltaOperationType.ADD_ASSUMPTION,
        DiscussionDeltaOperationType.ADD_OPEN_QUESTION,
        DiscussionDeltaOperationType.ADD_TEMPORARY_CONCLUSION,
    }
)
_OPTION_UPDATE_ACTORS = frozenset(
    {
        DiscussionActorClaim.USER_EXPLICIT,
        DiscussionActorClaim.USER_INFERRED,
        DiscussionActorClaim.ASSISTANT_PROPOSAL,
    }
)
_AUTHORITATIVE_ACTORS = frozenset(
    {
        DiscussionActorClaim.USER_EXPLICIT,
        DiscussionActorClaim.SYSTEM_FACT,
        DiscussionActorClaim.FORMAL_PROJECT_FACT,
    }
)
_AUTHORITATIVE_OPERATIONS = frozenset(
    {
        DiscussionDeltaOperationType.UPDATE_CONSTRAINT,
        DiscussionDeltaOperationType.SUPERSEDE_CONSTRAINT,
        DiscussionDeltaOperationType.REJECT_ASSUMPTION,
        DiscussionDeltaOperationType.RESOLVE_OPEN_QUESTION,
    }
)
_USER_EXPLICIT_OPERATIONS = frozenset(
    {
        DiscussionDeltaOperationType.PREFER_OPTION,
        DiscussionDeltaOperationType.REJECT_OPTION,
        DiscussionDeltaOperationType.RECORD_USER_CORRECTION,
        DiscussionDeltaOperationType.CONFIRM_DECISION,
        DiscussionDeltaOperationType.REQUEST_FORMALIZATION,
        DiscussionDeltaOperationType.CANCEL_FORMALIZATION,
    }
)
_OPTION_OPERATIONS = frozenset(
    {
        DiscussionDeltaOperationType.ADD_OPTION,
        DiscussionDeltaOperationType.UPDATE_OPTION,
        DiscussionDeltaOperationType.PREFER_OPTION,
        DiscussionDeltaOperationType.REJECT_OPTION,
    }
)
_DEFAULT_SUBJECT_KEYS: dict[DiscussionDeltaOperationType, str] = {
    DiscussionDeltaOperationType.SET_TOPIC: "topic",
    DiscussionDeltaOperationType.ADD_OPTION: "option",
    DiscussionDeltaOperationType.UPDATE_OPTION: "option",
    DiscussionDeltaOperationType.PREFER_OPTION: "option",
    DiscussionDeltaOperationType.REJECT_OPTION: "option",
    DiscussionDeltaOperationType.ADD_CONSTRAINT: "constraint",
    DiscussionDeltaOperationType.UPDATE_CONSTRAINT: "constraint",
    DiscussionDeltaOperationType.SUPERSEDE_CONSTRAINT: "constraint",
    DiscussionDeltaOperationType.ADD_CONCERN: "concern",
    DiscussionDeltaOperationType.ADD_ASSUMPTION: "assumption",
    DiscussionDeltaOperationType.REJECT_ASSUMPTION: "assumption",
    DiscussionDeltaOperationType.ADD_OPEN_QUESTION: "open_question",
    DiscussionDeltaOperationType.RESOLVE_OPEN_QUESTION: "open_question",
    DiscussionDeltaOperationType.ADD_TEMPORARY_CONCLUSION: "temporary_conclusion",
    DiscussionDeltaOperationType.RECORD_USER_CORRECTION: "user_correction",
    DiscussionDeltaOperationType.CONFIRM_DECISION: "decision",
    DiscussionDeltaOperationType.REQUEST_FORMALIZATION: "formalization",
    DiscussionDeltaOperationType.CANCEL_FORMALIZATION: "formalization",
}
_EVENT_NAMESPACE = uuid5(NAMESPACE_URL, "p26-d1-governed-discussion-event")

_OPERATION_ADMISSION_RULES: dict[
    DiscussionDeltaOperationType, DiscussionDeltaOperationAdmissionRule
] = {
    DiscussionDeltaOperationType.SET_TOPIC: DiscussionDeltaOperationAdmissionRule(
        target_rule="null",
        supersedes_rule="optional visible effective topic_set event",
        actor_rule="user_explicit, user_inferred, or assistant_proposal",
        allows_supersedes=True,
        supersedes_event_types=frozenset({DiscussionEventType.TOPIC_SET}),
    ),
    DiscussionDeltaOperationType.ADD_OPTION: DiscussionDeltaOperationAdmissionRule(
        target_rule="new stable UUID",
        supersedes_rule="must be null",
        actor_rule="user_explicit, user_inferred, or assistant_proposal",
        requires_option_target=True,
        requires_new_option_target=True,
    ),
    DiscussionDeltaOperationType.UPDATE_OPTION: DiscussionDeltaOperationAdmissionRule(
        target_rule="visible active option_id",
        supersedes_rule=(
            "optional visible effective option_added or option_updated event for "
            "the same option_id"
        ),
        actor_rule="user_explicit, user_inferred, or assistant_proposal",
        requires_option_target=True,
        requires_active_option_target=True,
        allows_supersedes=True,
        supersedes_event_types=frozenset(
            {DiscussionEventType.OPTION_ADDED, DiscussionEventType.OPTION_UPDATED}
        ),
        supersedes_same_option=True,
    ),
    DiscussionDeltaOperationType.PREFER_OPTION: DiscussionDeltaOperationAdmissionRule(
        target_rule=(
            "visible active option_id, or a previously rejected option_id for "
            "explicit reselection"
        ),
        supersedes_rule=(
            "must be null for an active option; an inactive previously rejected "
            "option must supersede its visible effective option_rejected event"
        ),
        actor_rule="user_explicit",
        requires_option_target=True,
    ),
    DiscussionDeltaOperationType.REJECT_OPTION: DiscussionDeltaOperationAdmissionRule(
        target_rule="visible active option_id to reject",
        supersedes_rule="must be null",
        actor_rule="user_explicit",
        requires_option_target=True,
        requires_active_option_target=True,
    ),
    DiscussionDeltaOperationType.ADD_CONSTRAINT: DiscussionDeltaOperationAdmissionRule(
        target_rule="null",
        supersedes_rule="must be null",
        actor_rule="user_explicit, user_inferred, or assistant_proposal",
    ),
    DiscussionDeltaOperationType.UPDATE_CONSTRAINT: DiscussionDeltaOperationAdmissionRule(
        target_rule="null",
        supersedes_rule="required visible effective constraint event",
        actor_rule="user_explicit, system_fact, or formal_project_fact",
        requires_supersedes=True,
        allows_supersedes=True,
        supersedes_event_types=frozenset(
            {
                DiscussionEventType.CONSTRAINT_ADDED,
                DiscussionEventType.CONSTRAINT_UPDATED,
                DiscussionEventType.CONSTRAINT_SUPERSEDED,
            }
        ),
    ),
    DiscussionDeltaOperationType.SUPERSEDE_CONSTRAINT: DiscussionDeltaOperationAdmissionRule(
        target_rule="null",
        supersedes_rule="required visible effective constraint event",
        actor_rule="user_explicit, system_fact, or formal_project_fact",
        requires_supersedes=True,
        allows_supersedes=True,
        supersedes_event_types=frozenset(
            {
                DiscussionEventType.CONSTRAINT_ADDED,
                DiscussionEventType.CONSTRAINT_UPDATED,
                DiscussionEventType.CONSTRAINT_SUPERSEDED,
            }
        ),
    ),
    DiscussionDeltaOperationType.ADD_CONCERN: DiscussionDeltaOperationAdmissionRule(
        target_rule="null",
        supersedes_rule="must be null",
        actor_rule="user_explicit, user_inferred, or assistant_proposal",
    ),
    DiscussionDeltaOperationType.ADD_ASSUMPTION: DiscussionDeltaOperationAdmissionRule(
        target_rule="null",
        supersedes_rule="must be null",
        actor_rule="user_explicit, user_inferred, or assistant_proposal",
    ),
    DiscussionDeltaOperationType.REJECT_ASSUMPTION: DiscussionDeltaOperationAdmissionRule(
        target_rule="null",
        supersedes_rule="required visible effective assumption_added event",
        actor_rule="user_explicit, system_fact, or formal_project_fact",
        requires_supersedes=True,
        allows_supersedes=True,
        supersedes_event_types=frozenset({DiscussionEventType.ASSUMPTION_ADDED}),
    ),
    DiscussionDeltaOperationType.ADD_OPEN_QUESTION: DiscussionDeltaOperationAdmissionRule(
        target_rule="null",
        supersedes_rule="must be null",
        actor_rule="user_explicit, user_inferred, or assistant_proposal",
    ),
    DiscussionDeltaOperationType.RESOLVE_OPEN_QUESTION: DiscussionDeltaOperationAdmissionRule(
        target_rule="null",
        supersedes_rule="required visible effective open_question_added event",
        actor_rule="user_explicit, system_fact, or formal_project_fact",
        requires_supersedes=True,
        allows_supersedes=True,
        supersedes_event_types=frozenset({DiscussionEventType.OPEN_QUESTION_ADDED}),
    ),
    DiscussionDeltaOperationType.ADD_TEMPORARY_CONCLUSION: DiscussionDeltaOperationAdmissionRule(
        target_rule="null",
        supersedes_rule="must be null",
        actor_rule="user_explicit, user_inferred, or assistant_proposal",
    ),
    DiscussionDeltaOperationType.RECORD_USER_CORRECTION: DiscussionDeltaOperationAdmissionRule(
        target_rule="null",
        supersedes_rule="optional visible effective DiscussionEvent",
        actor_rule="user_explicit",
        allows_supersedes=True,
    ),
    DiscussionDeltaOperationType.CONFIRM_DECISION: DiscussionDeltaOperationAdmissionRule(
        target_rule="null",
        supersedes_rule="must be null",
        actor_rule="user_explicit",
    ),
    DiscussionDeltaOperationType.REQUEST_FORMALIZATION: DiscussionDeltaOperationAdmissionRule(
        target_rule="null",
        supersedes_rule="must be null",
        actor_rule="user_explicit",
    ),
    DiscussionDeltaOperationType.CANCEL_FORMALIZATION: DiscussionDeltaOperationAdmissionRule(
        target_rule="null",
        supersedes_rule="required visible effective formalization_requested event",
        actor_rule="user_explicit",
        requires_supersedes=True,
        allows_supersedes=True,
        supersedes_event_types=frozenset(
            {DiscussionEventType.FORMALIZATION_REQUESTED}
        ),
    ),
}


def discussion_delta_operation_contract_rows(
    *, provider_preflight: bool = False
) -> list[dict[str, str]]:
    """Return deterministic provider-facing rows from the governing contract."""

    return [
        {
            "operation": operation.value,
            "target_id_rule": rule.target_rule,
            "supersedes_event_id_rule": rule.supersedes_rule,
            "actor_claim_rule": (
                "user_explicit only; system_fact and formal_project_fact are forbidden "
                "in provider output"
                if provider_preflight
                and rule.actor_rule
                in {
                    "user_explicit, system_fact, or formal_project_fact",
                }
                else rule.actor_rule
            ),
        }
        for operation, rule in _OPERATION_ADMISSION_RULES.items()
    ]


def validate_discussion_operation_admission(
    *,
    operation: DiscussionDeltaOperation,
    event_by_id: dict[UUID, DiscussionEvent],
    effective_event_ids: set[UUID],
    active_option_ids: set[UUID],
) -> str | None:
    """Validate Gate-level option and supersession rules without side effects."""

    rule = _OPERATION_ADMISSION_RULES.get(operation.op)
    if rule is None:
        return "discussion_delta_operation_not_supported"

    if rule.requires_option_target and operation.target_id is None:
        return "discussion_delta_option_target_required"
    if operation.op == DiscussionDeltaOperationType.PREFER_OPTION:
        return _validate_prefer_option_admission(
            operation=operation,
            event_by_id=event_by_id,
            effective_event_ids=effective_event_ids,
            active_option_ids=active_option_ids,
        )
    if (
        rule.requires_new_option_target
        and operation.target_id is not None
        and operation.target_id in active_option_ids
    ):
        return "discussion_delta_option_target_not_new"
    if (
        rule.requires_active_option_target
        and operation.target_id not in active_option_ids
    ):
        return "discussion_delta_option_target_not_active"
    if not rule.requires_option_target and operation.target_id is not None:
        return "discussion_delta_target_id_forbidden"

    supersedes_event_id = operation.supersedes_event_id
    if supersedes_event_id is None:
        if rule.requires_supersedes:
            return "discussion_delta_supersedes_required"
        return None
    if not rule.allows_supersedes:
        return "discussion_delta_supersedes_forbidden"

    target = event_by_id.get(supersedes_event_id)
    if target is None:
        return "discussion_delta_supersedes_target_not_found"
    if target.id not in effective_event_ids:
        return "discussion_delta_supersedes_target_not_effective"
    if (
        rule.supersedes_event_types is not None
        and target.event_type not in rule.supersedes_event_types
    ):
        return "discussion_delta_supersedes_type_invalid"
    if rule.supersedes_same_option and (
        operation.target_id is None
        or not _payload_uuid_equals(target.payload, "option_id", operation.target_id)
    ):
        return "discussion_delta_supersedes_type_invalid"
    return None


def _validate_prefer_option_admission(
    *,
    operation: DiscussionDeltaOperation,
    event_by_id: dict[UUID, DiscussionEvent],
    effective_event_ids: set[UUID],
    active_option_ids: set[UUID],
) -> str | None:
    """Admit ordinary preference or an explicit reselection of a rejected option."""

    target_id = operation.target_id
    if target_id is None:
        return "discussion_delta_option_target_required"
    if target_id in active_option_ids:
        if operation.supersedes_event_id is not None:
            return "discussion_delta_prefer_active_option_supersedes_forbidden"
        return None
    if operation.actor_claim != DiscussionActorClaim.USER_EXPLICIT:
        return "discussion_delta_rejected_option_actor_not_user_explicit"
    supersedes_event_id = operation.supersedes_event_id
    if supersedes_event_id is None:
        return "discussion_delta_rejected_option_supersedes_required"
    target = event_by_id.get(supersedes_event_id)
    if target is None:
        return "discussion_delta_supersedes_target_not_found"
    if target.id not in effective_event_ids:
        return "discussion_delta_supersedes_target_not_effective"
    if target.event_type != DiscussionEventType.OPTION_REJECTED:
        return "discussion_delta_rejected_option_supersedes_type_invalid"
    if not _payload_uuid_equals(target.payload, "option_id", target_id):
        return "discussion_delta_rejected_option_target_mismatch"
    return None


def canonicalize_discussion_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the deterministic JSON-native payload persisted for one event."""

    normalized = _canonicalize_discussion_json_value(payload)
    if not isinstance(normalized, dict):
        raise ValueError("discussion_delta_payload_not_object")
    return normalized


def _canonicalize_discussion_json_value(value: Any) -> Any:
    """Normalize supported JSON-boundary values without changing their meaning."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("discussion_delta_payload_float_not_finite")
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return _canonicalize_discussion_json_value(value.value)
    if isinstance(value, datetime):
        return ensure_utc_datetime(value).isoformat()
    if isinstance(value, (list, tuple)):
        return [_canonicalize_discussion_json_value(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for raw_key, raw_item in sorted(value.items(), key=lambda item: str(item[0])):
            key = str(raw_key)
            if key in normalized:
                raise ValueError("discussion_delta_payload_key_collision")
            normalized[key] = _canonicalize_discussion_json_value(raw_item)
        return normalized
    raise ValueError("discussion_delta_payload_value_not_json_serializable")


def _canonical_json_dump(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


class ProjectDirectorDiscussionDeltaGateService:
    """Validate and prepare a discussion delta without persistence side effects."""

    def __init__(
        self,
        reducer: ProjectDirectorDiscussionWorkspaceReducerService | None = None,
    ) -> None:
        self._reducer = reducer or ProjectDirectorDiscussionWorkspaceReducerService()

    def evaluate_delta(
        self,
        *,
        session_id: UUID,
        project_id: UUID | None,
        assistant_message: ProjectDirectorMessage,
        available_messages: Sequence[ProjectDirectorMessage],
        current_events: Sequence[DiscussionEvent],
        current_workspace: DiscussionWorkspace | None,
        delta: DiscussionDelta,
        start_sequence_no: int,
        occurred_at: datetime | None = None,
    ) -> GovernedDiscussionDeltaResult:
        """Return an all-or-nothing prepared delta and projected workspace."""

        self._validate_assistant_message(assistant_message, session_id)
        source_messages = self._build_source_catalog(
            assistant_message=assistant_message,
            available_messages=available_messages,
            session_id=session_id,
        )
        current_user_message_id = self._current_user_message_id(source_messages)
        resolution = self._reducer.resolve_events(
            session_id=session_id, project_id=project_id, events=current_events
        )
        expected_next_sequence = (
            max(event.sequence_no for event in current_events) + 1
            if current_events
            else 1
        )
        if start_sequence_no != expected_next_sequence:
            raise ValueError("discussion_delta_start_sequence_mismatch")
        normalized_occurred_at = ensure_utc_datetime(
            occurred_at if occurred_at is not None else assistant_message.created_at
        )

        baseline_workspace = self._resolve_baseline_workspace(
            session_id=session_id,
            project_id=project_id,
            current_events=current_events,
            current_workspace=current_workspace,
            current_last_sequence_no=(
                resolution.ordered_events[-1].sequence_no
                if resolution.ordered_events
                else 0
            ),
            empty_history_at=normalized_occurred_at,
        )
        if not delta.operations:
            return GovernedDiscussionDeltaResult(
                status=DiscussionDeltaGateStatus.PREPARED,
                prepared_events=(),
                projected_workspace=baseline_workspace,
                confirmation_reasons=(),
            )

        event_by_id = {event.id: event for event in resolution.ordered_events}
        effective_event_ids = {event.id for event in resolution.effective_events}
        prepared_events: list[PreparedDiscussionEvent] = []
        confirmation_reasons: list[str] = []
        seen_operation_hashes: set[str] = set()
        seen_new_option_ids: set[UUID] = set()

        for operation_index, operation in enumerate(delta.operations):
            event_type = _OPERATION_EVENT_TYPES.get(operation.op)
            if event_type is None:
                raise ValueError("discussion_delta_operation_not_supported")
            self._validate_operation_sources(
                operation=operation,
                source_messages=source_messages,
                assistant_message_id=assistant_message.id,
                current_user_message_id=current_user_message_id,
                active_option_ids=set(baseline_workspace.active_option_ids),
            )
            self._validate_operation_authority(operation)
            prepared_operation = self._prepare_operation(
                session_id=session_id,
                assistant_message_id=assistant_message.id,
                operation_index=operation_index,
                operation=operation,
                event_type=event_type,
            )
            if prepared_operation.operation_hash in seen_operation_hashes:
                raise ValueError("discussion_delta_duplicate_operation")
            seen_operation_hashes.add(prepared_operation.operation_hash)
            if operation.op == DiscussionDeltaOperationType.ADD_OPTION:
                if operation.target_id in seen_new_option_ids:
                    raise ValueError("discussion_delta_option_target_not_new")
                if operation.target_id is not None:
                    seen_new_option_ids.add(operation.target_id)

            target = self._validate_supersedes(
                operation=operation,
                event_by_id=event_by_id,
                effective_event_ids=effective_event_ids,
                active_option_ids=set(baseline_workspace.active_option_ids),
            )
            self._append_confirmation_reasons(
                operation=operation,
                operation_index=operation_index,
                supersedes_target=target,
                confirmation_reasons=confirmation_reasons,
            )
            event = DiscussionEvent(
                id=prepared_operation.identity.event_id,
                session_id=session_id,
                project_id=project_id,
                sequence_no=start_sequence_no + operation_index,
                event_type=prepared_operation.event_type,
                subject_key=prepared_operation.subject_key,
                content=operation.content,
                status=(
                    DiscussionEventStatus.CONFIRMED
                    if operation.op == DiscussionDeltaOperationType.CONFIRM_DECISION
                    or operation.actor_claim == DiscussionActorClaim.FORMAL_PROJECT_FACT
                    else DiscussionEventStatus.ACTIVE
                ),
                payload=prepared_operation.payload,
                source_message_ids=list(operation.source_message_ids),
                supersedes_event_id=operation.supersedes_event_id,
                created_by=operation.actor_claim,
                confidence=(
                    1.0
                    if operation.actor_claim
                    in {
                        DiscussionActorClaim.USER_EXPLICIT,
                        DiscussionActorClaim.SYSTEM_FACT,
                        DiscussionActorClaim.FORMAL_PROJECT_FACT,
                    }
                    else 0.5
                ),
                created_at=normalized_occurred_at,
                source_surface=None,
                source_entity_type=None,
                source_entity_id=None,
                trigger_type=None,
                interaction_case_id=None,
                external_context_pack_id=None,
            )
            prepared_events.append(
                PreparedDiscussionEvent(
                    operation_index=operation_index,
                    event=event,
                    idempotency_key=prepared_operation.identity.idempotency_key,
                )
            )

        if confirmation_reasons:
            return GovernedDiscussionDeltaResult(
                status=DiscussionDeltaGateStatus.REQUIRES_CONFIRMATION,
                prepared_events=(),
                projected_workspace=baseline_workspace,
                confirmation_reasons=tuple(confirmation_reasons),
            )

        projected_workspace, _ = self._reducer.reduce_workspace(
            workspace=baseline_workspace,
            events=tuple(current_events)
            + tuple(item.event for item in prepared_events),
            updated_at=normalized_occurred_at,
        )
        return GovernedDiscussionDeltaResult(
            status=DiscussionDeltaGateStatus.PREPARED,
            prepared_events=tuple(prepared_events),
            projected_workspace=projected_workspace,
            confirmation_reasons=(),
        )

    def prepare_replay_identities(
        self,
        *,
        session_id: UUID,
        assistant_message: ProjectDirectorMessage,
        delta: DiscussionDelta,
    ) -> tuple[DiscussionDeltaOperationIdentity, ...]:
        """Return the identities used by :meth:`evaluate_delta` without writes."""

        self._validate_assistant_message(assistant_message, session_id)
        return tuple(
            item.identity
            for item in self._prepare_operations(
                session_id=session_id,
                assistant_message_id=assistant_message.id,
                delta=delta,
            )
        )

    @staticmethod
    def _prepare_operations(
        *,
        session_id: UUID,
        assistant_message_id: UUID,
        delta: DiscussionDelta,
    ) -> tuple[_PreparedOperation, ...]:
        prepared: list[_PreparedOperation] = []
        for operation_index, operation in enumerate(delta.operations):
            event_type = _OPERATION_EVENT_TYPES.get(operation.op)
            if event_type is None:
                raise ValueError("discussion_delta_operation_not_supported")
            prepared.append(
                ProjectDirectorDiscussionDeltaGateService._prepare_operation(
                    session_id=session_id,
                    assistant_message_id=assistant_message_id,
                    operation_index=operation_index,
                    operation=operation,
                    event_type=event_type,
                )
            )
        return tuple(prepared)

    @staticmethod
    def _prepare_operation(
        *,
        session_id: UUID,
        assistant_message_id: UUID,
        operation_index: int,
        operation: DiscussionDeltaOperation,
        event_type: DiscussionEventType,
    ) -> _PreparedOperation:
        payload = ProjectDirectorDiscussionDeltaGateService._normalized_payload(operation)
        subject_key = ProjectDirectorDiscussionDeltaGateService._subject_key(operation)
        operation_hash = ProjectDirectorDiscussionDeltaGateService._operation_hash(
            operation=operation, payload=payload, subject_key=subject_key
        )
        return _PreparedOperation(
            identity=DiscussionDeltaOperationIdentity(
                operation_index=operation_index,
                event_id=uuid5(
                    _EVENT_NAMESPACE,
                    f"{session_id.hex}:{assistant_message_id.hex}:{operation_index}:"
                    f"{operation_hash}",
                ),
                idempotency_key=(
                    f"p26-d1:{assistant_message_id.hex}:"
                    f"{operation_index}:{operation_hash}"
                ),
            ),
            event_type=event_type,
            payload=payload,
            subject_key=subject_key,
            operation_hash=operation_hash,
        )

    @staticmethod
    def _validate_assistant_message(
        assistant_message: ProjectDirectorMessage, session_id: UUID
    ) -> None:
        if assistant_message.session_id != session_id:
            raise ValueError("discussion_delta_assistant_message_session_mismatch")
        if assistant_message.role != ProjectDirectorMessageRole.ASSISTANT:
            raise ValueError("discussion_delta_assistant_message_role_invalid")

    @staticmethod
    def _build_source_catalog(
        *,
        assistant_message: ProjectDirectorMessage,
        available_messages: Sequence[ProjectDirectorMessage],
        session_id: UUID,
    ) -> dict[UUID, ProjectDirectorMessage]:
        catalog: dict[UUID, ProjectDirectorMessage] = {}
        for message in available_messages:
            if message.session_id != session_id:
                raise ValueError("discussion_delta_source_message_session_mismatch")
            if message.id in catalog:
                raise ValueError("discussion_delta_source_message_duplicate")
            catalog[message.id] = message
        existing_assistant = catalog.get(assistant_message.id)
        if existing_assistant is not None:
            if existing_assistant.model_dump(mode="python") != assistant_message.model_dump(
                mode="python"
            ):
                raise ValueError("discussion_delta_assistant_message_conflict")
        else:
            catalog[assistant_message.id] = assistant_message
        return catalog

    def _resolve_baseline_workspace(
        self,
        *,
        session_id: UUID,
        project_id: UUID | None,
        current_events: Sequence[DiscussionEvent],
        current_workspace: DiscussionWorkspace | None,
        current_last_sequence_no: int,
        empty_history_at: datetime,
    ) -> DiscussionWorkspace:
        if current_workspace is None:
            return self._reducer.rebuild_workspace(
                session_id=session_id,
                project_id=project_id,
                events=current_events,
                version_no=0,
                created_at=empty_history_at if not current_events else None,
                updated_at=empty_history_at if not current_events else None,
            )
        if current_workspace.session_id != session_id:
            raise ValueError("discussion_delta_workspace_session_mismatch")
        if current_workspace.project_id != project_id:
            raise ValueError("discussion_delta_workspace_project_mismatch")
        if current_workspace.last_event_sequence_no != current_last_sequence_no:
            raise ValueError("discussion_delta_workspace_event_cursor_mismatch")
        baseline_workspace, changed = self._reducer.reduce_workspace(
            workspace=current_workspace, events=current_events
        )
        if changed:
            raise ValueError("discussion_delta_workspace_projection_mismatch")
        return baseline_workspace

    @staticmethod
    def _validate_operation_sources(
        *,
        operation: DiscussionDeltaOperation,
        source_messages: dict[UUID, ProjectDirectorMessage],
        assistant_message_id: UUID,
        current_user_message_id: UUID | None,
        active_option_ids: set[UUID],
    ) -> None:
        sources: list[ProjectDirectorMessage] = []
        for source_id in operation.source_message_ids:
            source = source_messages.get(source_id)
            if source is None:
                raise ValueError("discussion_delta_source_message_not_found")
            sources.append(source)

        expected_role: ProjectDirectorMessageRole | None
        if operation.actor_claim in {
            DiscussionActorClaim.USER_EXPLICIT,
            DiscussionActorClaim.USER_INFERRED,
        }:
            expected_role = ProjectDirectorMessageRole.USER
        elif operation.actor_claim == DiscussionActorClaim.ASSISTANT_PROPOSAL:
            expected_role = ProjectDirectorMessageRole.ASSISTANT
            if assistant_message_id not in operation.source_message_ids:
                raise ValueError("discussion_delta_actor_source_role_mismatch")
        else:
            expected_role = ProjectDirectorMessageRole.SYSTEM

        if any(source.role != expected_role for source in sources):
            raise ValueError("discussion_delta_actor_source_role_mismatch")
        if (
            operation.op == DiscussionDeltaOperationType.PREFER_OPTION
            and operation.target_id is not None
            and operation.target_id not in active_option_ids
            and current_user_message_id not in operation.source_message_ids
        ):
            raise ValueError("discussion_delta_rejected_option_source_current_user_required")

    @staticmethod
    def _current_user_message_id(
        source_messages: dict[UUID, ProjectDirectorMessage],
    ) -> UUID | None:
        user_messages = [
            message
            for message in source_messages.values()
            if message.role == ProjectDirectorMessageRole.USER
        ]
        if not user_messages:
            return None
        return max(user_messages, key=lambda message: message.sequence_no).id

    @staticmethod
    def _validate_operation_authority(operation: DiscussionDeltaOperation) -> None:
        if operation.op in _ADDITIVE_OPERATIONS:
            return
        if operation.op == DiscussionDeltaOperationType.UPDATE_OPTION:
            if operation.actor_claim in _OPTION_UPDATE_ACTORS:
                return
        elif operation.op in _AUTHORITATIVE_OPERATIONS:
            if operation.actor_claim in _AUTHORITATIVE_ACTORS:
                return
        elif operation.op in _USER_EXPLICIT_OPERATIONS:
            return
        else:
            raise ValueError("discussion_delta_operation_not_supported")
        raise ValueError("discussion_delta_operation_actor_not_authorized")

    @staticmethod
    def _normalized_payload(operation: DiscussionDeltaOperation) -> dict[str, Any]:
        payload = deepcopy(operation.payload)
        if operation.op in _OPTION_OPERATIONS:
            if operation.target_id is None:
                raise ValueError("discussion_delta_option_target_required")
            if "option_id" in payload and not _uuid_values_equal(
                payload["option_id"], operation.target_id
            ):
                raise ValueError("discussion_delta_option_id_conflict")
            payload["option_id"] = operation.target_id
        elif operation.target_id is not None:
            if "target_id" in payload and not _uuid_values_equal(
                payload["target_id"], operation.target_id
            ):
                raise ValueError("discussion_delta_target_id_conflict")
            payload["target_id"] = operation.target_id
        return canonicalize_discussion_payload(payload)

    @staticmethod
    def _subject_key(operation: DiscussionDeltaOperation) -> str:
        subject_key = (operation.subject_key or "").strip()
        if subject_key:
            return subject_key
        default = _DEFAULT_SUBJECT_KEYS.get(operation.op)
        if default is None:
            raise ValueError("discussion_delta_subject_key_invalid")
        if operation.op in _OPTION_OPERATIONS:
            if operation.target_id is None:
                raise ValueError("discussion_delta_option_target_required")
            return f"{default}:{operation.target_id}"
        return default

    @staticmethod
    def _operation_hash(
        *,
        operation: DiscussionDeltaOperation,
        payload: dict[str, Any],
        subject_key: str,
    ) -> str:
        canonical_operation = {
            "op": operation.op.value,
            "target_id": str(operation.target_id) if operation.target_id else None,
            "subject_key": subject_key,
            "content": operation.content,
            "payload": payload,
            "source_message_ids": [str(item) for item in operation.source_message_ids],
            "actor_claim": operation.actor_claim.value,
            "supersedes_event_id": (
                str(operation.supersedes_event_id)
                if operation.supersedes_event_id is not None
                else None
            ),
        }
        encoded = _canonical_json_dump(canonical_operation).encode("utf-8")
        return sha256(encoded).hexdigest()

    @staticmethod
    def _validate_supersedes(
        *,
        operation: DiscussionDeltaOperation,
        event_by_id: dict[UUID, DiscussionEvent],
        effective_event_ids: set[UUID],
        active_option_ids: set[UUID],
    ) -> DiscussionEvent | None:
        reason = validate_discussion_operation_admission(
            operation=operation,
            event_by_id=event_by_id,
            effective_event_ids=effective_event_ids,
            active_option_ids=active_option_ids,
        )
        if reason is not None:
            raise ValueError(reason)
        if operation.supersedes_event_id is None:
            return None
        return event_by_id[operation.supersedes_event_id]

    @staticmethod
    def _append_confirmation_reasons(
        *,
        operation: DiscussionDeltaOperation,
        operation_index: int,
        supersedes_target: DiscussionEvent | None,
        confirmation_reasons: list[str],
    ) -> None:
        if (
            operation.op in _USER_EXPLICIT_OPERATIONS
            and operation.actor_claim != DiscussionActorClaim.USER_EXPLICIT
        ):
            confirmation_reasons.append(
                f"discussion_delta_user_confirmation_required:{operation_index}"
            )
        if operation.supersedes_event_id is None:
            return
        if operation.actor_claim in {
            DiscussionActorClaim.USER_INFERRED,
            DiscussionActorClaim.ASSISTANT_PROPOSAL,
        }:
            confirmation_reasons.append(
                "discussion_delta_inferred_supersede_confirmation_required:"
                f"{operation_index}"
            )
        if supersedes_target is None:
            return
        if (
            supersedes_target.created_by == DiscussionActorClaim.FORMAL_PROJECT_FACT
            and operation.actor_claim != DiscussionActorClaim.FORMAL_PROJECT_FACT
        ):
            raise ValueError("discussion_delta_formal_project_fact_conflict")
        if (
            supersedes_target.created_by == DiscussionActorClaim.USER_EXPLICIT
            or supersedes_target.status == DiscussionEventStatus.CONFIRMED
            or supersedes_target.event_type == DiscussionEventType.DECISION_CONFIRMED
        ) and operation.actor_claim != DiscussionActorClaim.USER_EXPLICIT:
            confirmation_reasons.append(
                "discussion_delta_confirmed_fact_confirmation_required:"
                f"{operation_index}"
            )


def _uuid_values_equal(value: Any, expected: UUID) -> bool:
    try:
        return (value if isinstance(value, UUID) else UUID(str(value))) == expected
    except (TypeError, ValueError, AttributeError):
        return False


def _payload_uuid_equals(payload: dict[str, Any], key: str, expected: UUID) -> bool:
    return key in payload and _uuid_values_equal(payload[key], expected)
