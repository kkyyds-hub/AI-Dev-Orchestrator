"""Transactional persistence for governed Project Director discussion deltas.

``APPLIED`` means writes have flushed into the caller's transaction.  This
service never commits or rolls back that transaction, so the caller can still
roll back the complete apply operation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.project_director_discussion import (
    DiscussionDelta,
    DiscussionEvent,
    DiscussionWorkspace,
)
from app.domain.project_director_message import ProjectDirectorMessage
from app.repositories.project_director_discussion_event_repository import (
    ProjectDirectorDiscussionEventRepository,
)
from app.repositories.project_director_discussion_workspace_repository import (
    ProjectDirectorDiscussionWorkspaceRepository,
)
from app.services.project_director_discussion_delta_gate_service import (
    DiscussionDeltaGateStatus,
    PreparedDiscussionEvent,
    ProjectDirectorDiscussionDeltaGateService,
)
from app.services.project_director_discussion_workspace_reducer_service import (
    ProjectDirectorDiscussionWorkspaceReducerService,
)


class DiscussionDeltaApplyStatus(StrEnum):
    """The durable outcome of a governed discussion delta apply attempt."""

    APPLIED = "applied"
    REPLAYED = "replayed"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    NO_CHANGES = "no_changes"


@dataclass(frozen=True, slots=True)
class AppliedDiscussionEvent:
    """One prepared event and the result of its idempotent append."""

    operation_index: int
    event: DiscussionEvent
    idempotency_key: str
    inserted: bool


@dataclass(frozen=True, slots=True)
class GovernedDiscussionDeltaApplyResult:
    """The outcome visible inside the caller-owned transaction."""

    status: DiscussionDeltaApplyStatus
    persisted_events: tuple[AppliedDiscussionEvent, ...]
    workspace: DiscussionWorkspace
    inserted_event_count: int
    workspace_changed: bool
    confirmation_reasons: tuple[str, ...]


class ProjectDirectorDiscussionDeltaApplyService:
    """Apply a D1-approved delta without owning the Session transaction.

    All append and workspace writes run in an apply-level savepoint.  The
    caller remains responsible for committing or rolling back the surrounding
    SQLAlchemy ``Session`` transaction.
    """

    def __init__(
        self,
        session: Session,
        gate: ProjectDirectorDiscussionDeltaGateService | None = None,
        reducer: ProjectDirectorDiscussionWorkspaceReducerService | None = None,
    ) -> None:
        self._session = session
        self._events = ProjectDirectorDiscussionEventRepository(session)
        self._workspaces = ProjectDirectorDiscussionWorkspaceRepository(session)
        self._reducer = reducer or ProjectDirectorDiscussionWorkspaceReducerService()
        self._gate = gate or ProjectDirectorDiscussionDeltaGateService(
            reducer=self._reducer
        )

    def apply_delta(
        self,
        *,
        session_id: UUID,
        project_id: UUID | None,
        assistant_message: ProjectDirectorMessage,
        available_messages: Sequence[ProjectDirectorMessage],
        delta: DiscussionDelta,
        occurred_at: datetime | None = None,
    ) -> GovernedDiscussionDeltaApplyResult:
        """Flush one governed delta into the caller transaction, never committing it."""

        current_events = self._events.list_by_session_id(session_id=session_id)
        current_workspace = self._workspaces.get_by_session_id(session_id=session_id)
        next_sequence_no = self._events.get_next_sequence_no(session_id=session_id)
        identities = self._gate.prepare_replay_identities(
            session_id=session_id, assistant_message=assistant_message, delta=delta
        )

        if not identities:
            gate_result = self._gate.evaluate_delta(
                session_id=session_id,
                project_id=project_id,
                assistant_message=assistant_message,
                available_messages=available_messages,
                current_events=current_events,
                current_workspace=current_workspace,
                delta=delta,
                start_sequence_no=next_sequence_no,
                occurred_at=occurred_at,
            )
            return GovernedDiscussionDeltaApplyResult(
                status=DiscussionDeltaApplyStatus.NO_CHANGES,
                persisted_events=(),
                workspace=gate_result.projected_workspace,
                inserted_event_count=0,
                workspace_changed=False,
                confirmation_reasons=(),
            )

        replay_events = tuple(
            self._events.get_by_idempotency_key(
                session_id=session_id, idempotency_key=identity.idempotency_key
            )
            for identity in identities
        )
        replay_count = sum(event is not None for event in replay_events)
        if replay_count:
            if replay_count != len(identities):
                raise ValueError("discussion_delta_apply_partial_replay")
            if any(
                event is None
                or event.id != identity.event_id
                or event.project_id != project_id
                for identity, event in zip(identities, replay_events, strict=True)
            ):
                raise ValueError("discussion_delta_apply_replay_identity_conflict")
            workspace = self._validated_replay_workspace(
                session_id=session_id,
                project_id=project_id,
                current_events=current_events,
                current_workspace=current_workspace,
                replay_event_ids=frozenset(identity.event_id for identity in identities),
            )
            return self._replayed_result(
                workspace,
                tuple(
                    AppliedDiscussionEvent(
                        operation_index=identity.operation_index,
                        event=event,
                        idempotency_key=identity.idempotency_key,
                        inserted=False,
                    )
                    for identity, event in zip(
                        identities, replay_events, strict=True
                    )
                    if event is not None
                ),
            )

        gate_result = self._gate.evaluate_delta(
            session_id=session_id,
            project_id=project_id,
            assistant_message=assistant_message,
            available_messages=available_messages,
            current_events=current_events,
            current_workspace=current_workspace,
            delta=delta,
            start_sequence_no=next_sequence_no,
            occurred_at=occurred_at,
        )
        if gate_result.status is DiscussionDeltaGateStatus.REQUIRES_CONFIRMATION:
            return GovernedDiscussionDeltaApplyResult(
                status=DiscussionDeltaApplyStatus.REQUIRES_CONFIRMATION,
                persisted_events=(),
                workspace=gate_result.projected_workspace,
                inserted_event_count=0,
                workspace_changed=False,
                confirmation_reasons=gate_result.confirmation_reasons,
            )
        if not gate_result.prepared_events:
            return GovernedDiscussionDeltaApplyResult(
                status=DiscussionDeltaApplyStatus.NO_CHANGES,
                persisted_events=(),
                workspace=gate_result.projected_workspace,
                inserted_event_count=0,
                workspace_changed=False,
                confirmation_reasons=(),
            )

        try:
            with self._session.begin_nested():
                persisted = self._append_prepared_events(gate_result.prepared_events)
                inserted_count = sum(item.inserted for item in persisted)
                if inserted_count not in {0, len(persisted)}:
                    raise ValueError("discussion_delta_apply_partial_replay")
                if inserted_count == 0:
                    replay_workspace = self._validated_replay_workspace(
                        session_id=session_id,
                        project_id=project_id,
                        current_events=self._events.list_by_session_id(session_id=session_id),
                        current_workspace=self._workspaces.get_by_session_id(
                            session_id=session_id
                        ),
                        replay_event_ids=frozenset(item.event.id for item in persisted),
                    )
                    if not self._workspace_matches(
                        replay_workspace, gate_result.projected_workspace
                    ):
                        raise ValueError(
                            "discussion_delta_apply_concurrent_workspace_conflict"
                        )
                    return self._replayed_result(replay_workspace, persisted)

                workspace = self._persist_workspace(
                    session_id=session_id,
                    project_id=project_id,
                    current_workspace=current_workspace,
                    projected_workspace=gate_result.projected_workspace,
                )
        except IntegrityError as exc:
            raise ValueError("discussion_delta_apply_concurrent_event_conflict") from exc
        except ValueError as exc:
            if str(exc) == "discussion_workspace_stale_version":
                raise ValueError(
                    "discussion_delta_apply_concurrent_workspace_conflict"
                ) from exc
            raise

        return GovernedDiscussionDeltaApplyResult(
            status=DiscussionDeltaApplyStatus.APPLIED,
            persisted_events=persisted,
            workspace=workspace,
            inserted_event_count=len(persisted),
            workspace_changed=True,
            confirmation_reasons=(),
        )

    def _append_prepared_events(
        self, prepared_events: Sequence[PreparedDiscussionEvent]
    ) -> tuple[AppliedDiscussionEvent, ...]:
        persisted: list[AppliedDiscussionEvent] = []
        for prepared in sorted(prepared_events, key=lambda item: item.operation_index):
            event, inserted = self._events.append_if_absent(
                event=prepared.event, idempotency_key=prepared.idempotency_key
            )
            if event.model_dump(mode="python") != prepared.event.model_dump(mode="python"):
                raise ValueError("discussion_delta_apply_persisted_event_mismatch")
            persisted.append(
                AppliedDiscussionEvent(
                    operation_index=prepared.operation_index,
                    event=event,
                    idempotency_key=prepared.idempotency_key,
                    inserted=inserted,
                )
            )
        return tuple(persisted)

    def _persist_workspace(
        self,
        *,
        session_id: UUID,
        project_id: UUID | None,
        current_workspace: DiscussionWorkspace | None,
        projected_workspace: DiscussionWorkspace,
    ) -> DiscussionWorkspace:
        if current_workspace is None:
            empty_workspace = self._reducer.rebuild_workspace(
                session_id=session_id,
                project_id=project_id,
                events=(),
                version_no=0,
                created_at=projected_workspace.created_at,
                updated_at=projected_workspace.created_at,
            )
            _, created = self._workspaces.create_if_absent(
                workspace=empty_workspace
            )
            if not created:
                raise ValueError("discussion_delta_apply_concurrent_workspace_conflict")
            expected_version_no = 0
        else:
            expected_version_no = current_workspace.version_no

        if projected_workspace.version_no != expected_version_no + 1:
            raise ValueError("discussion_delta_apply_concurrent_workspace_conflict")
        return self._workspaces.update_if_version(
            workspace=projected_workspace, expected_version_no=expected_version_no
        )

    def _validated_replay_workspace(
        self,
        *,
        session_id: UUID,
        project_id: UUID | None,
        current_events: Sequence[DiscussionEvent],
        current_workspace: DiscussionWorkspace | None,
        replay_event_ids: frozenset[UUID],
    ) -> DiscussionWorkspace:
        if current_workspace is None:
            raise ValueError("discussion_delta_apply_replay_workspace_missing")
        if (
            current_workspace.session_id != session_id
            or current_workspace.project_id != project_id
        ):
            raise ValueError("discussion_delta_apply_replay_workspace_mismatch")
        event_ids = {event.id for event in current_events}
        if not replay_event_ids <= event_ids:
            raise ValueError("discussion_delta_apply_replay_identity_conflict")
        if current_workspace.last_event_sequence_no < max(
            event.sequence_no
            for event in current_events
            if event.id in replay_event_ids
        ):
            raise ValueError("discussion_delta_apply_replay_workspace_mismatch")
        rebuilt, changed = self._reducer.reduce_workspace(
            workspace=current_workspace, events=current_events
        )
        if changed or rebuilt != current_workspace:
            raise ValueError("discussion_delta_apply_replay_workspace_mismatch")
        return current_workspace

    @staticmethod
    def _workspace_matches(
        left: DiscussionWorkspace, right: DiscussionWorkspace
    ) -> bool:
        fields = (
            "session_id",
            "project_id",
            "topic",
            "discussion_status",
            "active_option_ids",
            "preferred_option_id",
            "active_constraint_ids",
            "open_question_ids",
            "temporary_conclusion_ids",
            "confirmed_decision_ids",
            "latest_user_correction_event_id",
            "version_no",
            "last_event_sequence_no",
        )
        return all(getattr(left, field) == getattr(right, field) for field in fields)

    @staticmethod
    def _replayed_result(
        workspace: DiscussionWorkspace,
        persisted_events: tuple[AppliedDiscussionEvent, ...] = (),
    ) -> GovernedDiscussionDeltaApplyResult:
        return GovernedDiscussionDeltaApplyResult(
            status=DiscussionDeltaApplyStatus.REPLAYED,
            persisted_events=persisted_events,
            workspace=workspace,
            inserted_event_count=0,
            workspace_changed=False,
            confirmation_reasons=(),
        )
