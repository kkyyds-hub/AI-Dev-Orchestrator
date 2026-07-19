"""Pure governed admission for unpersisted Project Director discussion deltas."""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
import json
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
class GovernedDiscussionDeltaResult:
    """Pure admission result and its derived workspace projection."""

    status: DiscussionDeltaGateStatus
    prepared_events: tuple[PreparedDiscussionEvent, ...]
    projected_workspace: DiscussionWorkspace
    confirmation_reasons: tuple[str, ...]


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
_OPTION_EVENT_TYPES = frozenset(
    {
        DiscussionEventType.OPTION_ADDED,
        DiscussionEventType.OPTION_UPDATED,
        DiscussionEventType.OPTION_PREFERRED,
        DiscussionEventType.OPTION_REJECTED,
    }
)
_CONSTRAINT_EVENT_TYPES = frozenset(
    {
        DiscussionEventType.CONSTRAINT_ADDED,
        DiscussionEventType.CONSTRAINT_UPDATED,
        DiscussionEventType.CONSTRAINT_SUPERSEDED,
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

        for operation_index, operation in enumerate(delta.operations):
            event_type = _OPERATION_EVENT_TYPES.get(operation.op)
            if event_type is None:
                raise ValueError("discussion_delta_operation_not_supported")
            self._validate_operation_sources(
                operation=operation,
                source_messages=source_messages,
                assistant_message_id=assistant_message.id,
            )
            self._validate_operation_authority(operation)
            payload = self._normalized_payload(operation)
            subject_key = self._subject_key(operation)
            operation_hash = self._operation_hash(
                operation=operation, payload=payload, subject_key=subject_key
            )
            if operation_hash in seen_operation_hashes:
                raise ValueError("discussion_delta_duplicate_operation")
            seen_operation_hashes.add(operation_hash)

            target = self._validate_supersedes(
                operation=operation,
                event_by_id=event_by_id,
                effective_event_ids=effective_event_ids,
            )
            self._append_confirmation_reasons(
                operation=operation,
                operation_index=operation_index,
                supersedes_target=target,
                confirmation_reasons=confirmation_reasons,
            )
            event = DiscussionEvent(
                id=uuid5(
                    _EVENT_NAMESPACE,
                    f"{session_id.hex}:{assistant_message.id.hex}:{operation_index}:{operation_hash}",
                ),
                session_id=session_id,
                project_id=project_id,
                sequence_no=start_sequence_no + operation_index,
                event_type=event_type,
                subject_key=subject_key,
                content=operation.content,
                status=(
                    DiscussionEventStatus.CONFIRMED
                    if operation.op == DiscussionDeltaOperationType.CONFIRM_DECISION
                    or operation.actor_claim == DiscussionActorClaim.FORMAL_PROJECT_FACT
                    else DiscussionEventStatus.ACTIVE
                ),
                payload=payload,
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
                    idempotency_key=(
                        f"p26-d1:{assistant_message.id.hex}:{operation_index}:{operation_hash}"
                    ),
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
        return payload

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
        encoded = json.dumps(
            canonical_operation,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        ).encode("utf-8")
        return sha256(encoded).hexdigest()

    @staticmethod
    def _validate_supersedes(
        *,
        operation: DiscussionDeltaOperation,
        event_by_id: dict[UUID, DiscussionEvent],
        effective_event_ids: set[UUID],
    ) -> DiscussionEvent | None:
        if operation.supersedes_event_id is None:
            if operation.op in {
                DiscussionDeltaOperationType.UPDATE_CONSTRAINT,
                DiscussionDeltaOperationType.SUPERSEDE_CONSTRAINT,
                DiscussionDeltaOperationType.REJECT_ASSUMPTION,
                DiscussionDeltaOperationType.RESOLVE_OPEN_QUESTION,
                DiscussionDeltaOperationType.CANCEL_FORMALIZATION,
            }:
                raise ValueError("discussion_delta_supersedes_type_invalid")
            return None
        target = event_by_id.get(operation.supersedes_event_id)
        if target is None:
            raise ValueError("discussion_delta_supersedes_target_not_found")
        if target.id not in effective_event_ids:
            raise ValueError("discussion_delta_supersedes_target_not_effective")

        if operation.op == DiscussionDeltaOperationType.SET_TOPIC:
            valid = target.event_type == DiscussionEventType.TOPIC_SET
        elif operation.op == DiscussionDeltaOperationType.UPDATE_OPTION:
            valid = (
                target.event_type in _OPTION_EVENT_TYPES
                and operation.target_id is not None
                and _payload_uuid_equals(target.payload, "option_id", operation.target_id)
            )
        elif operation.op in {
            DiscussionDeltaOperationType.UPDATE_CONSTRAINT,
            DiscussionDeltaOperationType.SUPERSEDE_CONSTRAINT,
        }:
            valid = target.event_type in _CONSTRAINT_EVENT_TYPES
        elif operation.op == DiscussionDeltaOperationType.REJECT_ASSUMPTION:
            valid = target.event_type == DiscussionEventType.ASSUMPTION_ADDED
        elif operation.op == DiscussionDeltaOperationType.RESOLVE_OPEN_QUESTION:
            valid = target.event_type == DiscussionEventType.OPEN_QUESTION_ADDED
        elif operation.op == DiscussionDeltaOperationType.CANCEL_FORMALIZATION:
            valid = target.event_type == DiscussionEventType.FORMALIZATION_REQUESTED
        elif operation.op == DiscussionDeltaOperationType.RECORD_USER_CORRECTION:
            # A correction may target any effective discussion event.  Formal
            # project facts are rejected by the dedicated governance conflict
            # check below so callers receive its precise error code.
            valid = True
        else:
            valid = False
        if not valid:
            raise ValueError("discussion_delta_supersedes_type_invalid")
        return target

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
