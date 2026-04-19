"""Day11 agent-thread backend service for session/message/review-rework contracts."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.agent_message import AgentMessage, AgentMessageRole, AgentMessageType
from app.domain.agent_session import (
    AgentSession,
    AgentSessionPhase,
    AgentSessionReviewStatus,
    AgentSessionStatus,
)
from app.domain.project_role import ProjectRoleCode
from app.domain.run import RunFailureCategory, RunStatus
from app.repositories.agent_message_repository import AgentMessageRepository
from app.repositories.agent_session_repository import AgentSessionRepository
from app.services.context_builder_service import AgentThreadContextSeed


@dataclass(slots=True, frozen=True)
class AgentThreadRecordResult:
    """Result returned when the Day11 worker records one thread cycle."""

    session: AgentSession
    timeline_messages: list[AgentMessage]


class AgentConversationService:
    """Persist and query the Day11 minimal agent-thread conversation chain."""

    def __init__(
        self,
        *,
        agent_session_repository: AgentSessionRepository,
        agent_message_repository: AgentMessageRepository,
    ) -> None:
        self.agent_session_repository = agent_session_repository
        self.agent_message_repository = agent_message_repository

    def start_session(
        self,
        *,
        project_id: UUID,
        task_id: UUID,
        run_id: UUID,
        owner_role_code: ProjectRoleCode | None,
        context_seed: AgentThreadContextSeed,
    ) -> AgentSession:
        """Create the Day11 session row and seed context-recovery timeline messages."""

        session = self.agent_session_repository.create(
            project_id=project_id,
            task_id=task_id,
            run_id=run_id,
            status=AgentSessionStatus.RUNNING,
            review_status=AgentSessionReviewStatus.NONE,
            current_phase=AgentSessionPhase.CONTEXT_READY,
            owner_role_code=owner_role_code,
            context_checkpoint_id=context_seed.context_checkpoint_id,
            context_rehydrated=context_seed.context_rehydrated,
            summary="Day11 session started from worker main chain.",
        )
        self._append_message(
            session=session,
            role=AgentMessageRole.SYSTEM,
            message_type=AgentMessageType.TIMELINE,
            event_type="session_started",
            phase=AgentSessionPhase.CONTEXT_READY.value,
            state_from=None,
            state_to=AgentSessionPhase.CONTEXT_READY.value,
            context_checkpoint_id=context_seed.context_checkpoint_id,
            context_rehydrated=context_seed.context_rehydrated,
            content_summary="Agent session started and bound to the current run.",
            content_detail=context_seed.context_contract_summary,
        )
        if context_seed.context_checkpoint_id is not None:
            self._append_message(
                session=session,
                role=AgentMessageRole.SYSTEM,
                message_type=AgentMessageType.TIMELINE,
                event_type="context_recovery_ready",
                phase=AgentSessionPhase.CONTEXT_READY.value,
                state_from=AgentSessionPhase.CONTEXT_READY.value,
                state_to=AgentSessionPhase.CONTEXT_READY.value,
                context_checkpoint_id=context_seed.context_checkpoint_id,
                context_rehydrated=context_seed.context_rehydrated,
                content_summary=(
                    "Day10 context recoverability precondition is available for Day11."
                ),
                content_detail=context_seed.context_contract_summary,
            )
        return session

    def record_execution_started(self, *, session_id: UUID) -> AgentSession:
        """Move one session into executing phase and append a timeline event."""

        session = self._require_session(session_id)
        session = self.agent_session_repository.update_status(
            session.id,
            current_phase=AgentSessionPhase.EXECUTING,
            summary="Execution has started in the worker chain.",
        )
        self._append_message(
            session=session,
            role=AgentMessageRole.AGENT,
            message_type=AgentMessageType.TIMELINE,
            event_type="execution_started",
            phase=AgentSessionPhase.EXECUTING.value,
            state_from=AgentSessionPhase.CONTEXT_READY.value,
            state_to=AgentSessionPhase.EXECUTING.value,
            context_checkpoint_id=session.context_checkpoint_id,
            context_rehydrated=session.context_rehydrated,
            content_summary="Agent execution started.",
            content_detail=None,
        )
        return session

    def record_execution_outcome(
        self,
        *,
        session_id: UUID,
        execution_success: bool,
        execution_summary: str,
        verification_present: bool,
        verification_success: bool,
        verification_summary: str | None,
        run_failure_category: RunFailureCategory | None,
    ) -> AgentSession:
        """Persist Day11 review/rework and boss note-event contracts."""

        session = self._require_session(session_id)
        self._append_message(
            session=session,
            role=AgentMessageRole.AGENT,
            message_type=AgentMessageType.TIMELINE,
            event_type="execution_finished",
            phase=AgentSessionPhase.EXECUTING.value,
            state_from=AgentSessionPhase.EXECUTING.value,
            state_to=AgentSessionPhase.EXECUTING.value,
            context_checkpoint_id=session.context_checkpoint_id,
            context_rehydrated=session.context_rehydrated,
            content_summary=execution_summary,
            content_detail=None,
        )

        if execution_success and (not verification_present or verification_success):
            session = self.agent_session_repository.update_status(
                session.id,
                review_status=AgentSessionReviewStatus.REVIEW_PASSED,
                summary="Execution completed with review gate passed.",
            )
            self._append_message(
                session=session,
                role=AgentMessageRole.REVIEWER,
                message_type=AgentMessageType.REVIEW,
                event_type="review_passed",
                phase=AgentSessionPhase.REVIEWING.value,
                state_from=AgentSessionReviewStatus.NONE.value,
                state_to=AgentSessionReviewStatus.REVIEW_PASSED.value,
                context_checkpoint_id=session.context_checkpoint_id,
                context_rehydrated=session.context_rehydrated,
                content_summary=(
                    verification_summary
                    or "Verification passed. No rework requested."
                ),
                content_detail=None,
            )
            return session

        # Day11 minimal review/rework chain: review required -> rework required.
        session = self.agent_session_repository.update_status(
            session.id,
            status=AgentSessionStatus.REVIEW_REWORK,
            review_status=AgentSessionReviewStatus.REVIEW_REQUIRED,
            current_phase=AgentSessionPhase.REVIEWING,
            summary="Review gate requires rework before completion.",
        )
        self._append_message(
            session=session,
            role=AgentMessageRole.REVIEWER,
            message_type=AgentMessageType.REVIEW,
            event_type="review_required",
            phase=AgentSessionPhase.REVIEWING.value,
            state_from=AgentSessionReviewStatus.NONE.value,
            state_to=AgentSessionReviewStatus.REVIEW_REQUIRED.value,
            context_checkpoint_id=session.context_checkpoint_id,
            context_rehydrated=session.context_rehydrated,
            content_summary=(
                verification_summary
                or "Verification failed. Review requires a rework round."
            ),
            content_detail=(
                f"run_failure_category={run_failure_category.value}"
                if run_failure_category is not None
                else None
            ),
        )

        session = self.agent_session_repository.update_status(
            session.id,
            review_status=AgentSessionReviewStatus.REWORK_REQUIRED,
            current_phase=AgentSessionPhase.REWORKING,
            latest_intervention_type="request_rework",
            summary="Rework has been requested after review.",
        )
        self._append_message(
            session=session,
            role=AgentMessageRole.AGENT,
            message_type=AgentMessageType.REWORK,
            event_type="rework_requested",
            phase=AgentSessionPhase.REWORKING.value,
            state_from=AgentSessionReviewStatus.REVIEW_REQUIRED.value,
            state_to=AgentSessionReviewStatus.REWORK_REQUIRED.value,
            intervention_type="request_rework",
            context_checkpoint_id=session.context_checkpoint_id,
            context_rehydrated=session.context_rehydrated,
            content_summary="Rework requested by review gate.",
            content_detail=verification_summary,
        )

        session = self.record_boss_note_event(
            session_id=session.id,
            note_event_type="quality_gate_blocked",
            note_summary="Boss note-event: quality gate blocked completion and requested rework.",
            note_detail=verification_summary,
        )
        return session

    def record_boss_note_event(
        self,
        *,
        session_id: UUID,
        note_event_type: str,
        note_summary: str,
        note_detail: str | None,
    ) -> AgentSession:
        """Persist one boss note-event for Day12 intervention consumption."""

        session = self._require_session(session_id)
        session = self.agent_session_repository.update_status(
            session.id,
            latest_note_event_type=note_event_type,
            latest_intervention_type="boss_note",
            summary=note_summary,
        )
        self._append_message(
            session=session,
            role=AgentMessageRole.BOSS,
            message_type=AgentMessageType.NOTE_EVENT,
            event_type="boss_note_event",
            phase=session.current_phase.value,
            state_from=session.review_status.value,
            state_to=session.review_status.value,
            intervention_type="boss_note",
            note_event_type=note_event_type,
            context_checkpoint_id=session.context_checkpoint_id,
            context_rehydrated=session.context_rehydrated,
            content_summary=note_summary,
            content_detail=note_detail,
        )
        return session

    def record_boss_intervention(
        self,
        *,
        project_id: UUID,
        session_id: UUID,
        intervention_type: str,
        note_event_type: str | None,
        intervention_summary: str,
        intervention_detail: str | None,
    ) -> tuple[AgentSession, AgentMessage]:
        """Persist one formal Day12 session-level boss intervention command."""

        session = self._require_session(session_id)
        if session.project_id != project_id:
            raise ValueError(
                "Agent session does not belong to project: "
                f"project_id={project_id}, session_id={session_id}"
            )
        self._ensure_boss_intervention_writable(session)

        normalized_intervention_type = intervention_type.strip()
        if not normalized_intervention_type:
            raise ValueError("intervention_type must not be blank")

        normalized_summary = intervention_summary.strip()
        if not normalized_summary:
            raise ValueError("intervention_summary must not be blank")

        normalized_note_event_type = (
            note_event_type.strip() if note_event_type is not None else None
        )
        normalized_intervention_detail = (
            intervention_detail.strip() if intervention_detail is not None else None
        )

        if normalized_note_event_type is None:
            session = self.agent_session_repository.update_status(
                session.id,
                latest_intervention_type=normalized_intervention_type,
                summary=normalized_summary,
            )
        else:
            session = self.agent_session_repository.update_status(
                session.id,
                latest_intervention_type=normalized_intervention_type,
                latest_note_event_type=normalized_note_event_type,
                summary=normalized_summary,
            )

        message = self._append_message(
            session=session,
            role=AgentMessageRole.BOSS,
            message_type=AgentMessageType.INTERVENTION,
            event_type="boss_intervention_submitted",
            phase=session.current_phase.value,
            state_from=session.review_status.value,
            state_to=session.review_status.value,
            intervention_type=normalized_intervention_type,
            note_event_type=normalized_note_event_type,
            context_checkpoint_id=session.context_checkpoint_id,
            context_rehydrated=session.context_rehydrated,
            content_summary=normalized_summary,
            content_detail=normalized_intervention_detail,
        )
        return session, message

    def finalize_session(
        self,
        *,
        session_id: UUID,
        run_status: RunStatus,
        run_failure_category: RunFailureCategory | None,
        final_summary: str,
    ) -> AgentSession:
        """Finalize one session according to run outcome."""

        session = self._require_session(session_id)
        next_status = AgentSessionStatus.COMPLETED
        if run_status == RunStatus.CANCELLED:
            next_status = AgentSessionStatus.BLOCKED
        elif run_status == RunStatus.FAILED:
            next_status = AgentSessionStatus.FAILED

        session = self.agent_session_repository.update_status(
            session.id,
            status=next_status,
            current_phase=AgentSessionPhase.FINALIZED,
            summary=final_summary,
            finished=True,
        )
        self._append_message(
            session=session,
            role=AgentMessageRole.SYSTEM,
            message_type=AgentMessageType.TIMELINE,
            event_type="session_finalized",
            phase=AgentSessionPhase.FINALIZED.value,
            state_from=session.review_status.value,
            state_to=next_status.value,
            context_checkpoint_id=session.context_checkpoint_id,
            context_rehydrated=session.context_rehydrated,
            content_summary=final_summary,
            content_detail=(
                f"run_status={run_status.value}; failure={run_failure_category.value}"
                if run_failure_category is not None
                else f"run_status={run_status.value}"
            ),
        )
        return session

    def list_project_sessions(
        self,
        *,
        project_id: UUID,
        limit: int = 20,
    ) -> list[AgentSession]:
        """Return project session snapshots for Day12 session panel."""

        return self.agent_session_repository.list_by_project_id(
            project_id=project_id,
            limit=limit,
        )

    def list_project_timeline(
        self,
        *,
        project_id: UUID,
        session_id: UUID | None = None,
        limit: int = 200,
    ) -> list[AgentMessage]:
        """Return Day12 timeline messages."""

        if session_id is not None:
            return self.agent_message_repository.list_by_session_id(
                session_id=session_id,
                limit=limit,
            )

        messages = self.agent_message_repository.list_by_project_id(
            project_id=project_id,
            session_id=None,
            limit=limit,
        )
        return sorted(messages, key=lambda item: (item.created_at, item.sequence_no))

    def list_project_interventions(
        self,
        *,
        project_id: UUID,
        session_id: UUID | None = None,
        limit: int = 100,
    ) -> list[AgentMessage]:
        """Return Day12 intervention/note/review-rework messages."""

        return self.agent_message_repository.list_by_project_id(
            project_id=project_id,
            session_id=session_id,
            message_types=[
                AgentMessageType.INTERVENTION,
                AgentMessageType.NOTE_EVENT,
                AgentMessageType.REVIEW,
                AgentMessageType.REWORK,
            ],
            limit=limit,
        )

    def _append_message(
        self,
        *,
        session: AgentSession,
        role: AgentMessageRole,
        message_type: AgentMessageType,
        event_type: str,
        phase: str | None,
        state_from: str | None,
        state_to: str | None,
        intervention_type: str | None = None,
        note_event_type: str | None = None,
        context_checkpoint_id: str | None,
        context_rehydrated: bool | None,
        content_summary: str,
        content_detail: str | None,
    ) -> AgentMessage:
        """Persist one timeline message with auto-incremented per-session sequence."""

        sequence_no = self.agent_message_repository.get_next_sequence_no(
            session_id=session.id
        )
        return self.agent_message_repository.create(
            session_id=session.id,
            project_id=session.project_id,
            task_id=session.task_id,
            run_id=session.run_id,
            sequence_no=sequence_no,
            role=role,
            message_type=message_type,
            event_type=event_type,
            phase=phase,
            state_from=state_from,
            state_to=state_to,
            intervention_type=intervention_type,
            note_event_type=note_event_type,
            context_checkpoint_id=context_checkpoint_id,
            context_rehydrated=context_rehydrated,
            content_summary=content_summary,
            content_detail=content_detail,
        )

    def _require_session(self, session_id: UUID) -> AgentSession:
        """Load one session or raise a stable not-found error."""

        session = self.agent_session_repository.get_by_id(session_id)
        if session is None:
            raise ValueError(f"Agent session not found: {session_id}")
        return session

    @staticmethod
    def _ensure_boss_intervention_writable(session: AgentSession) -> None:
        """Freeze intervention writes once one session has entered a terminal state."""

        if (
            session.current_phase == AgentSessionPhase.FINALIZED
            or session.status
            in {
                AgentSessionStatus.COMPLETED,
                AgentSessionStatus.FAILED,
                AgentSessionStatus.BLOCKED,
            }
            or session.finished_at is not None
        ):
            raise ValueError(
                "Agent session is finalized and does not accept boss interventions: "
                f"session_id={session.id}, "
                f"status={session.status.value}, "
                f"phase={session.current_phase.value}"
            )
