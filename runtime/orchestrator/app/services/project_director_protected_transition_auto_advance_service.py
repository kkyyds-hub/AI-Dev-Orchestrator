"""P23-D3 coordinator over the existing protected-transition public services."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.domain.project_director_protected_transition_auto_advance import (
    ProjectDirectorProtectedTransitionAutoAdvanceResult,
)
from app.services.project_director_post_review_automation_service import (
    ProjectDirectorPostReviewAutomationService,
)
from app.services.project_director_protected_transition_dispatch_consumption_preflight_service import (
    ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService,
)
from app.services.project_director_protected_transition_dispatch_consumption_service import (
    ProjectDirectorProtectedTransitionDispatchConsumptionService,
)
from app.services.project_director_protected_transition_dispatch_intent_service import (
    ProjectDirectorProtectedTransitionDispatchIntentService,
)
from app.services.project_director_protected_transition_worker_invocation_service import (
    ProjectDirectorProtectedTransitionWorkerInvocationService,
)
from app.services.project_director_protected_transition_worker_start_reservation_service import (
    ProjectDirectorProtectedTransitionWorkerStartReservationService,
)


class ProjectDirectorProtectedTransitionAutoAdvanceService:
    """Advance one exact review through existing P22/P23 authorities."""

    def __init__(
        self,
        *,
        post_review_automation_service: ProjectDirectorPostReviewAutomationService,
        dispatch_intent_service: ProjectDirectorProtectedTransitionDispatchIntentService,
        dispatch_consumption_preflight_service: ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService,
        dispatch_consumption_service: ProjectDirectorProtectedTransitionDispatchConsumptionService,
        worker_start_reservation_service: ProjectDirectorProtectedTransitionWorkerStartReservationService,
        worker_invocation_service: ProjectDirectorProtectedTransitionWorkerInvocationService,
    ) -> None:
        self._post_review_automation_service = post_review_automation_service
        self._dispatch_intent_service = dispatch_intent_service
        self._dispatch_consumption_preflight_service = (
            dispatch_consumption_preflight_service
        )
        self._dispatch_consumption_service = dispatch_consumption_service
        self._worker_start_reservation_service = worker_start_reservation_service
        self._worker_invocation_service = worker_invocation_service
        self._require_shared_sqlalchemy_session()

    def advance_post_review_protected_transition(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_review_message_id: UUID,
    ) -> ProjectDirectorProtectedTransitionAutoAdvanceResult:
        """Advance an exact review without duplicating downstream business rules."""

        state: dict[str, Any] = {
            "session_id": session_id,
            "source_task_id": source_task_id,
            "source_review_message_id": source_review_message_id,
            "current_step": "p22_post_review_automation",
            "resumed_from_existing_evidence": False,
        }
        d1_completed = False
        b2_invocation_started = False

        try:
            p22 = self._post_review_automation_service.orchestrate_post_review(
                session_id=session_id,
                source_task_id=source_task_id,
                source_review_message_id=source_review_message_id,
            )
            p22_result = p22.result
            self._merge_identity_from_message(state, p22.message)
            state.update(
                route=p22_result.route,
                disposition_type=p22_result.disposition_type,
                resumed_from_existing_evidence=(
                    p22_result.resumed_from_existing_evidence
                ),
            )
            if p22.message is not None:
                state["source_p22_summary_message_id"] = p22.message.id

            # P22 already revalidated this summary. Its orchestration identity is
            # not the persisted message ID; downstream lineage uses p22.message.id.
            if p22_result.orchestration_status == "waiting_for_human":
                if (
                    p22.message is None
                    or p22_result.route != "human_escalation"
                ):
                    return self._blocked(
                        state,
                        current_step="p22_blocked",
                        reasons=["p22_waiting_summary_invalid"],
                    )
                return self._result(
                    state,
                    auto_advance_status="waiting_for_human",
                    current_step="p22_waiting_for_human",
                    blocked_reasons=[],
                )
            if p22_result.orchestration_status != "ready_for_future_transition":
                return self._blocked(
                    state,
                    current_step="p22_blocked",
                    reasons=p22_result.blocked_reasons
                    or ["p22_post_review_automation_blocked"],
                )
            if (
                p22.message is None
                or p22_result.route
                not in ("automatic_continuation", "bounded_automatic_rework")
            ):
                return self._blocked(
                    state,
                    current_step="p22_blocked",
                    reasons=["p22_ready_summary_invalid"],
                )

            state["current_step"] = "dispatch_intent"
            intent = self._dispatch_intent_service.prepare_protected_transition_dispatch_intent(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=p22.message.id,
            )
            self._merge_common_result(state, intent.result)
            self._merge_replay(state, intent.result, "resumed_from_existing_intent")
            if intent.result.intent_status != "prepared" or intent.message is None:
                return self._blocked(
                    state,
                    current_step="dispatch_intent",
                    reasons=intent.result.blocked_reasons
                    or ["dispatch_intent_not_prepared"],
                )
            state["source_dispatch_intent_message_id"] = intent.message.id

            state["current_step"] = "dispatch_consumption_preflight"
            preflight = self._dispatch_consumption_preflight_service.find_persisted_only_protected_transition_dispatch_consumption_preflight(
                session_id=session_id,
                source_task_id=source_task_id,
                source_intent_message_id=intent.message.id,
            )
            if preflight.blocked_reasons:
                return self._blocked(
                    state,
                    current_step="dispatch_consumption_preflight",
                    reasons=preflight.blocked_reasons,
                )
            if preflight.result is None and preflight.message is None:
                preflight = self._dispatch_consumption_preflight_service.prepare_protected_transition_dispatch_consumption_preflight(
                    session_id=session_id,
                    source_task_id=source_task_id,
                    source_message_id=intent.message.id,
                )
            else:
                self._merge_replay_from_value(state, True)
            self._merge_common_result(state, preflight.result)
            self._merge_replay(
                state, preflight.result, "resumed_from_existing_preflight"
            )
            if preflight.result.preflight_status != "ready" or preflight.message is None:
                return self._blocked(
                    state,
                    current_step="dispatch_consumption_preflight",
                    reasons=preflight.result.blocked_reasons
                    or ["dispatch_consumption_preflight_not_ready"],
                )
            state["source_dispatch_consumption_preflight_message_id"] = (
                preflight.message.id
            )

            state["current_step"] = "dispatch_consumption"
            consumption = self._dispatch_consumption_service.find_persisted_protected_transition_dispatch_consumption(
                session_id=session_id,
                source_task_id=source_task_id,
                source_preflight_message_id=preflight.message.id,
            )
            if consumption.blocked_reasons:
                return self._blocked(
                    state,
                    current_step="dispatch_consumption",
                    reasons=consumption.blocked_reasons,
                )
            if consumption.result is None and consumption.message is None:
                consumption = self._dispatch_consumption_service.consume_protected_transition_dispatch_preflight(
                    session_id=session_id,
                    source_task_id=source_task_id,
                    source_message_id=preflight.message.id,
                )
            else:
                self._merge_replay_from_value(state, True)
            self._merge_common_result(state, consumption.result)
            self._merge_replay(
                state, consumption.result, "resumed_from_existing_consumption"
            )
            if (
                consumption.result.consumption_status
                != "reserved_for_worker_start"
                or consumption.message is None
            ):
                return self._blocked(
                    state,
                    current_step="dispatch_consumption",
                    reasons=consumption.result.blocked_reasons
                    or ["dispatch_consumption_not_reserved"],
                )
            state.update(
                source_dispatch_consumption_message_id=consumption.message.id,
                d1_task_claimed=consumption.result.task_claimed,
                d1_run_created=consumption.result.run_created,
                run_id=consumption.result.run_id,
            )
            d1_completed = True

            state["current_step"] = "worker_start_reservation"
            reservation = self._worker_start_reservation_service.find_persisted_protected_transition_worker_start_reservation(
                session_id=session_id,
                source_task_id=source_task_id,
                source_consumption_message_id=consumption.message.id,
            )
            if reservation.blocked_reasons:
                return self._blocked(
                    state,
                    current_step="worker_start_reservation",
                    reasons=reservation.blocked_reasons,
                )
            if reservation.result is None and reservation.message is None:
                reservation = self._worker_start_reservation_service.prepare_protected_transition_worker_start_reservation(
                    session_id=session_id,
                    source_task_id=source_task_id,
                    source_message_id=consumption.message.id,
                )
            else:
                self._merge_replay_from_value(state, True)
            self._merge_common_result(state, reservation.result)
            self._merge_replay(
                state, reservation.result, "resumed_from_existing_reservation"
            )
            if (
                reservation.result.reservation_status != "reserved"
                or reservation.message is None
            ):
                return self._blocked(
                    state,
                    current_step="worker_start_reservation",
                    reasons=reservation.result.blocked_reasons
                    or ["worker_start_reservation_not_reserved"],
                )
            state["source_worker_start_reservation_message_id"] = (
                reservation.message.id
            )

            state["current_step"] = "worker_invocation"
            b2_invocation_started = True
            invocation = self._worker_invocation_service.invoke_reserved_protected_transition_worker(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=reservation.message.id,
            )
            self._merge_replay_from_value(
                state, invocation.resumed_from_existing_outcome
            )
            if invocation.claim_message is not None:
                state["source_worker_invocation_claim_message_id"] = (
                    invocation.claim_message.id
                )
                state["worker_invocation_claimed"] = True
            if invocation.claim is not None:
                self._merge_common_result(state, invocation.claim)

            if invocation.outcome is None:
                if invocation.claim is not None or invocation.claim_message is not None:
                    return self._result(
                        state,
                        auto_advance_status="recovery_required",
                        current_step="worker_invocation_outcome",
                        human_recovery_required=True,
                        blocked_reasons=self._reasons(
                            invocation.blocked_reasons,
                            "worker_invocation_in_progress_or_recovery_required",
                        ),
                    )
                return self._blocked(
                    state,
                    current_step="worker_invocation",
                    reasons=invocation.blocked_reasons
                    or ["worker_invocation_not_claimed"],
                )

            outcome = invocation.outcome
            self._merge_common_result(state, outcome)
            self._merge_replay_from_value(
                state, outcome.resumed_from_existing_outcome
            )
            if invocation.outcome_message is None:
                return self._result(
                    state,
                    auto_advance_status="recovery_required",
                    current_step="worker_invocation_outcome",
                    human_recovery_required=True,
                    blocked_reasons=self._reasons(
                        invocation.blocked_reasons,
                        "worker_outcome_message_missing_recovery_required",
                    ),
                )
            state["source_worker_invocation_outcome_message_id"] = (
                invocation.outcome_message.id
            )
            status_map = {
                "not_invoked": "worker_not_invoked",
                "returned": "worker_returned",
                "raised": "worker_raised",
            }
            return self._result(
                state,
                auto_advance_status=status_map[outcome.outcome_status],
                current_step="worker_invocation_outcome",
                worker_outcome_status=outcome.outcome_status,
                worker_call_attempted=outcome.worker_call_attempted,
                worker_returned=outcome.worker_returned,
                worker_raised=outcome.worker_raised,
                continuation_started=outcome.continuation_started,
                rework_started=outcome.rework_started,
                human_recovery_required=outcome.human_recovery_required,
                worker_reported_git_write_activity=(
                    outcome.worker_reported_git_write_activity
                ),
                blocked_reasons=list(outcome.blocked_reasons),
            )
        except Exception as exc:
            if b2_invocation_started:
                reason = "worker_invocation_in_progress_or_recovery_required"
                status = "recovery_required"
            elif d1_completed:
                reason = "coordinator_exception_after_atomic_consumption"
                status = "recovery_required"
            else:
                reason = "coordinator_step_exception"
                status = "blocked"
            return self._result(
                state,
                auto_advance_status=status,
                current_step=state["current_step"],
                human_recovery_required=status == "recovery_required",
                blocked_reasons=[reason],
                exception_summary=(
                    f"{type(exc).__name__} during {state['current_step']}"
                )[:500],
            )

    @staticmethod
    def _result(
        state: dict[str, Any],
        *,
        auto_advance_status: str,
        current_step: str,
        **updates: Any,
    ) -> ProjectDirectorProtectedTransitionAutoAdvanceResult:
        values = {
            key: value
            for key, value in state.items()
            if key in ProjectDirectorProtectedTransitionAutoAdvanceResult.model_fields
        }
        values.update(
            auto_advance_status=auto_advance_status,
            current_step=current_step,
            **updates,
        )
        return ProjectDirectorProtectedTransitionAutoAdvanceResult(**values)

    def _blocked(
        self,
        state: dict[str, Any],
        *,
        current_step: str,
        reasons: list[str],
    ) -> ProjectDirectorProtectedTransitionAutoAdvanceResult:
        return self._result(
            state,
            auto_advance_status="blocked",
            current_step=current_step,
            blocked_reasons=self._reasons(reasons, "coordinator_step_blocked"),
        )

    @staticmethod
    def _merge_identity_from_message(state: dict[str, Any], message: Any) -> None:
        if message is not None and message.related_project_id is not None:
            state["project_id"] = message.related_project_id

    @staticmethod
    def _merge_common_result(state: dict[str, Any], result: Any) -> None:
        for name in (
            "project_id",
            "disposition_type",
            "dispatch_kind",
            "target_task_strategy",
            "run_id",
        ):
            value = getattr(result, name, None)
            if value is not None:
                state[name] = value

    @staticmethod
    def _merge_replay(state: dict[str, Any], result: Any, name: str) -> None:
        ProjectDirectorProtectedTransitionAutoAdvanceService._merge_replay_from_value(
            state, bool(getattr(result, name, False))
        )

    @staticmethod
    def _merge_replay_from_value(state: dict[str, Any], resumed: bool) -> None:
        state["resumed_from_existing_evidence"] = bool(
            state.get("resumed_from_existing_evidence") or resumed
        )

    @staticmethod
    def _reasons(values: list[str], fallback: str) -> list[str]:
        return list(dict.fromkeys([*(value for value in values if value), fallback]))

    def _require_shared_sqlalchemy_session(self) -> None:
        services = (
            self._post_review_automation_service,
            self._dispatch_intent_service,
            self._dispatch_consumption_preflight_service,
            self._dispatch_consumption_service,
            self._worker_start_reservation_service,
            self._worker_invocation_service,
        )
        repositories = tuple(service._message_repository for service in services)
        repository = repositories[0]
        if any(candidate is not repository for candidate in repositories[1:]):
            raise ValueError("D3 services must share one ProjectDirectorMessageRepository")
        sqlalchemy_session = repository._session
        if any(
            candidate._session is not sqlalchemy_session
            for candidate in repositories[1:]
        ):
            raise ValueError("D3 services must share one SQLAlchemy Session")


__all__ = ("ProjectDirectorProtectedTransitionAutoAdvanceService",)
