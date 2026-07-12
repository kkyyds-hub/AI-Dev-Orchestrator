"""P23-D2-B2 unique exact Worker invocation and durable outcome evidence."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.domain.agent_session import AgentSession
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_protected_transition_worker_invocation import (
    ProjectDirectorProtectedTransitionWorkerInvocationClaimResult,
    ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult,
)
from app.domain.project_director_protected_transition_worker_start_reservation import (
    ProjectDirectorProtectedTransitionWorkerStartReservationResult,
)
from app.domain.run import Run
from app.domain.task import Task
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.project_director_protected_transition_evidence_freshness_service import (
    ProjectDirectorProtectedTransitionEvidenceFreshnessService,
)
from app.services.project_director_protected_transition_worker_start_reservation_service import (
    ProjectDirectorProtectedTransitionWorkerStartReservationService,
    RevalidatedCurrentProtectedTransitionWorkerStartReservation,
)
from app.workers.task_worker import TaskWorker, WorkerRunResult


P23_PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL = (
    "p23_d2_worker_invocation_claimed"
)
P23_PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_ACTION_TYPE = (
    "p23_d2_worker_invocation_claim_record"
)
PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_SCHEMA_VERSION = (
    "p23-d2-b2-claim.v1"
)

P23_PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL = (
    "p23_d2_worker_invocation_outcome_recorded"
)
P23_PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_ACTION_TYPE = (
    "p23_d2_worker_invocation_outcome_record"
)
PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_SCHEMA_VERSION = (
    "p23-d2-b2-outcome.v1"
)

_CLAIM_INTENT = "protected_transition_worker_invocation_claim"
_OUTCOME_INTENT = "protected_transition_worker_invocation_outcome"
_PAGE_SIZE = 100
_SECRET_PATTERN = re.compile(
    r"(?i)(authorization|api[_-]?key|token|secret|password|prompt|environment|env)"
    r"\s*[:=]\s*[^\s,;]+"
)


@dataclass(frozen=True, slots=True)
class InvokedProjectDirectorProtectedTransitionWorker:
    """Claim and optional durable outcome for one exact B1 reservation."""

    claim: ProjectDirectorProtectedTransitionWorkerInvocationClaimResult | None
    claim_message: ProjectDirectorMessage | None
    outcome: ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult | None
    outcome_message: ProjectDirectorMessage | None
    blocked_reasons: list[str]
    resumed_from_existing_outcome: bool = False


@dataclass(frozen=True, slots=True)
class _InvocationHistory:
    claims: list[
        tuple[
            ProjectDirectorProtectedTransitionWorkerInvocationClaimResult,
            ProjectDirectorMessage,
        ]
    ]
    outcomes: list[
        tuple[
            ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult,
            ProjectDirectorMessage,
        ]
    ]
    invalid_claim: bool
    invalid_outcome: bool


class ProjectDirectorProtectedTransitionWorkerInvocationService:
    """Consume one B1 reservation, call its exact Worker once, record outcome."""

    def __init__(
        self,
        *,
        session_repository: ProjectDirectorSessionRepository,
        message_repository: ProjectDirectorMessageRepository,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        agent_session_repository: AgentSessionRepository,
        worker_start_reservation_service: ProjectDirectorProtectedTransitionWorkerStartReservationService,
        freshness_service: ProjectDirectorProtectedTransitionEvidenceFreshnessService,
        task_worker: TaskWorker,
    ) -> None:
        self._session_repository = session_repository
        self._message_repository = message_repository
        self._task_repository = task_repository
        self._run_repository = run_repository
        self._agent_session_repository = agent_session_repository
        self._worker_start_reservation_service = worker_start_reservation_service
        self._freshness_service = freshness_service
        self._task_worker = task_worker
        self._require_shared_sqlalchemy_session()

    def invoke_reserved_protected_transition_worker(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
    ) -> InvokedProjectDirectorProtectedTransitionWorker:
        """Invoke the exact B1 Task/Run once across three transaction phases."""

        # Phase 1: consume invocation authority. No Worker/provider/runtime call.
        with self._message_repository.sqlite_immediate_transaction():
            phase_one = self._claim_or_replay(
                session_id=session_id,
                source_task_id=source_task_id,
                source_reservation_message_id=source_message_id,
            )
        if phase_one.outcome is not None or phase_one.blocked_reasons:
            return phase_one
        claim = phase_one.claim
        claim_message = phase_one.claim_message
        if claim is None or claim_message is None:
            return self._blocked(["worker_invocation_claim_replay_conflict"])

        # Phase 2: there is deliberately no SQLite write transaction here.
        final_current = self._worker_start_reservation_service.revalidate_current_protected_transition_worker_start_reservation(
            session_id=session_id,
            source_task_id=source_task_id,
            source_reservation_message_id=source_message_id,
        )
        # SQLAlchemy autobegins for the read-only revalidation. End that read
        # transaction before crossing the exact Worker call boundary.
        self._message_repository._session.rollback()
        worker_result: WorkerRunResult | None = None
        worker_exception: Exception | None = None
        if not final_current.blocked_reasons and final_current.result is not None:
            try:
                worker_result = self._task_worker.run_reserved_once(
                    task_id=source_task_id,
                    run_id=claim.run_id,
                )
            except Exception as exc:
                worker_exception = exc
                self._message_repository._session.rollback()
        if self._message_repository._session.in_transaction():
            self._message_repository._session.rollback()

        # Phase 3: immutable revalidation and one append-only outcome record.
        try:
            with self._message_repository.sqlite_immediate_transaction():
                return self._record_outcome(
                    claim=claim,
                    claim_message=claim_message,
                    final_current=final_current,
                    worker_result=worker_result,
                    worker_exception=worker_exception,
                )
        except Exception:
            self._message_repository._session.rollback()
            return InvokedProjectDirectorProtectedTransitionWorker(
                claim=claim,
                claim_message=claim_message,
                outcome=None,
                outcome_message=None,
                blocked_reasons=[
                    "worker_outcome_persistence_failed_recovery_required"
                ],
            )

    def _claim_or_replay(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_reservation_message_id: UUID,
    ) -> InvokedProjectDirectorProtectedTransitionWorker:
        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None or session_obj.project_id is None:
            return self._blocked(["source_reservation_project_mismatch"])
        persisted = self._worker_start_reservation_service.revalidate_persisted_protected_transition_worker_start_reservation(
            session_id=session_id,
            source_task_id=source_task_id,
            source_reservation_message_id=source_reservation_message_id,
        )
        reservation = persisted.result
        if persisted.blocked_reasons or reservation is None:
            return self._blocked(
                persisted.blocked_reasons or ["source_reservation_invalid"]
            )

        history = self._scan_history(
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=session_obj.project_id,
        )
        claims = [
            item
            for item in history.claims
            if item[0].source_reservation_message_id
            == source_reservation_message_id
        ]
        outcomes = [
            item
            for item in history.outcomes
            if item[0].source_reservation_message_id
            == source_reservation_message_id
        ]
        cross_claim_conflict = any(
            item[0].run_id == reservation.run_id
            and item[0].source_reservation_message_id
            != source_reservation_message_id
            for item in history.claims
        )
        claim_ids = {item[0].claim_id for item in claims}
        cross_outcome_conflict = any(
            item[0].source_claim_id in claim_ids
            and (
                item[0].source_reservation_message_id
                != source_reservation_message_id
                or item[0].run_id != reservation.run_id
            )
            for item in history.outcomes
        )
        if history.invalid_claim or len(claims) > 1 or cross_claim_conflict:
            return self._blocked(["worker_invocation_claim_replay_conflict"])
        if history.invalid_outcome or len(outcomes) > 1 or cross_outcome_conflict:
            return self._blocked(["worker_invocation_outcome_replay_conflict"])
        if outcomes:
            if len(claims) != 1:
                return self._blocked(["worker_invocation_outcome_replay_conflict"])
            claim, claim_message = claims[0]
            outcome, outcome_message = outcomes[0]
            if not self._outcome_binds_claim(outcome=outcome, claim=claim):
                return self._blocked(["worker_invocation_outcome_replay_conflict"])
            replayed = ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult.model_validate(
                {**outcome.model_dump(), "resumed_from_existing_outcome": True}
            )
            return InvokedProjectDirectorProtectedTransitionWorker(
                claim=claim,
                claim_message=claim_message,
                outcome=replayed,
                outcome_message=outcome_message,
                blocked_reasons=[],
                resumed_from_existing_outcome=True,
            )
        if claims:
            claim, claim_message = claims[0]
            if (
                claim.source_reservation_message_id
                != source_reservation_message_id
                or claim.run_id != reservation.run_id
            ):
                return self._blocked(["worker_invocation_claim_replay_conflict"])
            return InvokedProjectDirectorProtectedTransitionWorker(
                claim=claim,
                claim_message=claim_message,
                outcome=None,
                outcome_message=None,
                blocked_reasons=[
                    "worker_invocation_in_progress_or_recovery_required"
                ],
            )

        current = self._worker_start_reservation_service.revalidate_current_protected_transition_worker_start_reservation(
            session_id=session_id,
            source_task_id=source_task_id,
            source_reservation_message_id=source_reservation_message_id,
        )
        if current.blocked_reasons or current.result is None:
            return self._blocked(current.blocked_reasons)
        claim = self._build_claim(reservation=reservation, current=current)
        message = self._message_repository.create(self._claim_message(claim))
        return InvokedProjectDirectorProtectedTransitionWorker(
            claim=claim,
            claim_message=message,
            outcome=None,
            outcome_message=None,
            blocked_reasons=[],
        )

    def _record_outcome(
        self,
        *,
        claim: ProjectDirectorProtectedTransitionWorkerInvocationClaimResult,
        claim_message: ProjectDirectorMessage,
        final_current: RevalidatedCurrentProtectedTransitionWorkerStartReservation,
        worker_result: WorkerRunResult | None,
        worker_exception: Exception | None,
    ) -> InvokedProjectDirectorProtectedTransitionWorker:
        persisted = self._worker_start_reservation_service.revalidate_persisted_protected_transition_worker_start_reservation(
            session_id=claim.session_id,
            source_task_id=claim.source_task_id,
            source_reservation_message_id=claim.source_reservation_message_id,
        )
        if persisted.blocked_reasons or persisted.result is None:
            return InvokedProjectDirectorProtectedTransitionWorker(
                claim=claim,
                claim_message=claim_message,
                outcome=None,
                outcome_message=None,
                blocked_reasons=["source_reservation_invalid"],
            )
        trusted_claim = self._trusted_claim(
            message=self._message_repository.get_by_id(claim.claim_id),
            session_id=claim.session_id,
            source_task_id=claim.source_task_id,
            project_id=claim.project_id,
        )
        if trusted_claim is None or trusted_claim != claim:
            return self._blocked(["worker_invocation_claim_replay_conflict"])

        history = self._scan_history(
            session_id=claim.session_id,
            source_task_id=claim.source_task_id,
            project_id=claim.project_id,
        )
        matching_claims = [item for item in history.claims if item[0].claim_id == claim.claim_id]
        matching_outcomes = [
            item for item in history.outcomes if item[0].source_claim_id == claim.claim_id
        ]
        if history.invalid_claim or len(matching_claims) != 1:
            return self._blocked(["worker_invocation_claim_replay_conflict"])
        if history.invalid_outcome or len(matching_outcomes) > 1:
            return self._blocked(["worker_invocation_outcome_replay_conflict"])
        if matching_outcomes:
            outcome, outcome_message = matching_outcomes[0]
            if not self._outcome_binds_claim(outcome=outcome, claim=claim):
                return self._blocked(["worker_invocation_outcome_replay_conflict"])
            replayed = ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult.model_validate(
                {**outcome.model_dump(), "resumed_from_existing_outcome": True}
            )
            return InvokedProjectDirectorProtectedTransitionWorker(
                claim=claim,
                claim_message=claim_message,
                outcome=replayed,
                outcome_message=outcome_message,
                blocked_reasons=[],
                resumed_from_existing_outcome=True,
            )

        task = self._task_repository.get_by_id(claim.source_task_id)
        run = self._run_repository.get_by_id(claim.run_id)
        agent_session = self._agent_session_repository.get_by_run_id(claim.run_id)
        outcome = self._build_outcome(
            claim=claim,
            final_current=final_current,
            worker_result=worker_result,
            worker_exception=worker_exception,
            task=task,
            run=run,
            agent_session=agent_session,
        )
        message = self._message_repository.create(self._outcome_message(outcome))
        return InvokedProjectDirectorProtectedTransitionWorker(
            claim=claim,
            claim_message=claim_message,
            outcome=outcome,
            outcome_message=message,
            blocked_reasons=[],
        )

    def _build_claim(
        self,
        *,
        reservation: ProjectDirectorProtectedTransitionWorkerStartReservationResult,
        current: RevalidatedCurrentProtectedTransitionWorkerStartReservation,
    ) -> ProjectDirectorProtectedTransitionWorkerInvocationClaimResult:
        freshness = current.current_freshness
        budget = current.budget_decision
        if freshness is None or budget is None or current.task is None or current.run is None:
            raise ValueError("current B1 revalidation is incomplete")
        values = {
            "claim_status": "claimed",
            "claim_id": uuid4(),
            "claim_fingerprint": "0" * 64,
            "claim_token": uuid4().hex,
            "session_id": reservation.session_id,
            "project_id": reservation.project_id,
            "source_task_id": reservation.source_task_id,
            "target_task_id": reservation.target_task_id,
            "run_id": reservation.run_id,
            "source_reservation_message_id": reservation.reservation_id,
            "source_reservation_id": reservation.reservation_id,
            "source_reservation_fingerprint": reservation.reservation_fingerprint,
            "source_reservation_token": reservation.reservation_token,
            "source_consumption_message_id": reservation.source_consumption_message_id,
            "source_consumption_fingerprint": reservation.source_consumption_fingerprint,
            "source_preflight_message_id": reservation.source_preflight_message_id,
            "source_intent_message_id": reservation.source_intent_message_id,
            "source_freshness_message_id": reservation.source_freshness_message_id,
            "disposition_type": reservation.disposition_type,
            "dispatch_kind": reservation.dispatch_kind,
            "target_task_strategy": reservation.target_task_strategy,
            "review_result_fingerprint": reservation.review_result_fingerprint,
            "review_semantic_fingerprint": reservation.review_semantic_fingerprint,
            "current_freshness_fingerprint": freshness.current_freshness_fingerprint,
            "current_diff_sha256": freshness.current_diff_sha256,
            "current_scope_paths": list(freshness.current_scope_paths),
            "workspace_path": freshness.workspace_path,
            "workspace_path_within_root": freshness.workspace_path_within_root,
            "task_status_before": current.task.status.value,
            "run_status_before": current.run.status.value,
            "agent_session_absent": True,
            "budget_guard_allowed": budget.allowed,
            "budget_pressure_level": budget.pressure_level.value,
            "budget_strategy_action": budget.suggested_action.value,
            "budget_strategy_code": budget.strategy_code,
            "budget_policy_source": budget.budget_policy_source,
            "retry_limit_reached": budget.retry_status.retry_limit_reached,
            "rework_attempt_index": reservation.rework_attempt_index,
            "rework_attempt_limit": reservation.rework_attempt_limit,
            "worker_invocation_claimed": True,
        }
        result = ProjectDirectorProtectedTransitionWorkerInvocationClaimResult(**values)
        return ProjectDirectorProtectedTransitionWorkerInvocationClaimResult.model_validate(
            {**result.model_dump(), "claim_fingerprint": self._claim_fingerprint(result)}
        )

    def _build_outcome(
        self,
        *,
        claim: ProjectDirectorProtectedTransitionWorkerInvocationClaimResult,
        final_current: RevalidatedCurrentProtectedTransitionWorkerStartReservation,
        worker_result: WorkerRunResult | None,
        worker_exception: Exception | None,
        task: Task | None,
        run: Run | None,
        agent_session: AgentSession | None,
    ) -> ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult:
        reasons: list[str] = []
        status = "returned"
        attempted = worker_result is not None or worker_exception is not None
        if final_current.blocked_reasons:
            status = "not_invoked"
            attempted = False
            reasons.extend(["final_worker_revalidation_failed", *final_current.blocked_reasons])
        elif worker_exception is not None:
            status = "raised"
            reasons.append("worker_execution_side_effects_indeterminate")

        snapshot = worker_result.reserved_run_execution_snapshot if worker_result else None
        contract_valid = bool(
            snapshot is not None
            and snapshot.source == "p23_d2_exact_reserved_run"
            and snapshot.exact_task_id == claim.source_task_id
            and snapshot.exact_run_id == claim.run_id
            and snapshot.reserved_run_execution_requested
            and not snapshot.task_routed
            and not snapshot.task_claimed_in_this_cycle
            and not snapshot.run_created_in_this_cycle
            and not snapshot.product_runtime_git_write_allowed
        )
        if status == "returned" and not contract_valid:
            reasons.append("worker_result_contract_invalid")

        git_activity = bool(
            worker_result
            and any(
                getattr(worker_result, field_name, False) is True
                for field_name in self._git_activity_fields()
            )
        )
        if git_activity:
            reasons.append("worker_result_git_boundary_violation")

        execution_started = bool(snapshot and snapshot.shared_execution_seam_used)
        continuation_started = claim.disposition_type == "AUTO_CONTINUE" and execution_started
        rework_started = claim.disposition_type == "AUTO_REWORK" and execution_started
        external = worker_result.external_executor_snapshot if worker_result else None
        native_process_started = bool(external and external.native_process_started)
        if status == "not_invoked" and agent_session is not None:
            reasons.append("worker_execution_side_effects_indeterminate")
        if agent_session is not None and (
            agent_session.task_id != claim.source_task_id
            or agent_session.run_id != claim.run_id
        ):
            reasons.append("worker_execution_side_effects_indeterminate")
        if status == "returned" and (
            task is None
            or run is None
            or task.status.value == "running"
            or run.status.value == "running"
        ):
            reasons.append("worker_returned_with_running_state")
        if status == "raised" and (
            task is None
            or run is None
            or task.status.value == "running"
            or run.status.value == "running"
        ):
            reasons.append("worker_exception_left_running_state")

        reasons = list(dict.fromkeys(reasons))
        human_recovery = bool(
            status == "raised"
            or not contract_valid and status == "returned"
            or git_activity
            or "worker_execution_side_effects_indeterminate" in reasons
            or reasons
            and status != "not_invoked"
        )
        exception_type = type(worker_exception).__name__ if worker_exception else None
        exception_summary = (
            self._safe_exception_summary(worker_exception)
            if worker_exception is not None
            else None
        )
        result_values = {
            "outcome_status": status,
            "outcome_id": uuid4(),
            "outcome_fingerprint": "0" * 64,
            "session_id": claim.session_id,
            "project_id": claim.project_id,
            "source_task_id": claim.source_task_id,
            "run_id": claim.run_id,
            "source_claim_message_id": claim.claim_id,
            "source_claim_id": claim.claim_id,
            "source_claim_fingerprint": claim.claim_fingerprint,
            "source_claim_token": claim.claim_token,
            "source_reservation_message_id": claim.source_reservation_message_id,
            "source_reservation_fingerprint": claim.source_reservation_fingerprint,
            "source_consumption_message_id": claim.source_consumption_message_id,
            "disposition_type": claim.disposition_type,
            "dispatch_kind": claim.dispatch_kind,
            "target_task_strategy": claim.target_task_strategy,
            "worker_call_attempted": attempted,
            "worker_returned": status == "returned",
            "worker_raised": status == "raised",
            "worker_result_contract_valid": contract_valid,
            "worker_result_claimed": worker_result.claimed if worker_result else None,
            "worker_result_message": (
                worker_result.message[:2_000] if worker_result else None
            ),
            "worker_execution_mode": (
                worker_result.execution_mode[:100]
                if worker_result and worker_result.execution_mode
                else None
            ),
            "worker_failure_category": (
                worker_result.failure_category.value
                if worker_result and worker_result.failure_category
                else None
            ),
            "worker_quality_gate_passed": worker_result.quality_gate_passed if worker_result else None,
            "worker_result_summary": (
                worker_result.result_summary[:2_000]
                if worker_result and worker_result.result_summary
                else None
            ),
            "reserved_snapshot_present": snapshot is not None,
            "reserved_snapshot_exact_task_id": snapshot.exact_task_id if snapshot else None,
            "reserved_snapshot_exact_run_id": snapshot.exact_run_id if snapshot else None,
            "reserved_snapshot_exact_binding_validated": bool(snapshot and snapshot.exact_binding_validated),
            "reserved_snapshot_task_routed": bool(snapshot and snapshot.task_routed),
            "reserved_snapshot_task_claimed_in_this_cycle": bool(snapshot and snapshot.task_claimed_in_this_cycle),
            "reserved_snapshot_run_created_in_this_cycle": bool(snapshot and snapshot.run_created_in_this_cycle),
            "reserved_snapshot_budget_rechecked": bool(snapshot and snapshot.budget_rechecked),
            "reserved_snapshot_existing_run_reused": bool(snapshot and snapshot.existing_run_reused),
            "reserved_snapshot_shared_execution_seam_used": bool(snapshot and snapshot.shared_execution_seam_used),
            "reserved_snapshot_blocked_reasons": list(snapshot.blocked_reasons) if snapshot else [],
            "task_status_after": task.status.value if task else None,
            "run_status_after": run.status.value if run else None,
            "agent_session_id": agent_session.id if agent_session else None,
            "agent_session_status": agent_session.status.value if agent_session else None,
            "runtime_handle_id": agent_session.runtime_handle_id if agent_session else None,
            "continuation_started": continuation_started,
            "rework_started": rework_started,
            "native_process_started": native_process_started,
            "human_recovery_required": human_recovery,
            "exception_type": exception_type,
            "exception_summary": exception_summary,
            "worker_reported_git_write_activity": git_activity,
            "product_runtime_git_write_allowed": False,
            "replay_check_completed": True,
            "blocked_reasons": reasons,
        }
        result = ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult(
            **result_values
        )
        return ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult.model_validate(
            {**result.model_dump(), "outcome_fingerprint": self._outcome_fingerprint(result)}
        )

    def _scan_history(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        project_id: UUID,
    ) -> _InvocationHistory:
        claims = []
        outcomes = []
        invalid_claim = False
        invalid_outcome = False
        for message in self._iter_session_messages(session_id):
            if message.source_detail == P23_PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL:
                action = self._single_action(message)
                claims_task = bool(action and action.get("source_task_id") == str(source_task_id))
                if message.related_task_id != source_task_id and not claims_task:
                    continue
                claim = self._trusted_claim(
                    message=message,
                    session_id=session_id,
                    source_task_id=source_task_id,
                    project_id=project_id,
                )
                if claim is None:
                    invalid_claim = True
                else:
                    claims.append((claim, message))
            elif message.source_detail == P23_PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL:
                action = self._single_action(message)
                claims_task = bool(action and action.get("source_task_id") == str(source_task_id))
                if message.related_task_id != source_task_id and not claims_task:
                    continue
                outcome = self._trusted_outcome(
                    message=message,
                    session_id=session_id,
                    source_task_id=source_task_id,
                    project_id=project_id,
                )
                if outcome is None:
                    invalid_outcome = True
                else:
                    outcomes.append((outcome, message))
        return _InvocationHistory(claims, outcomes, invalid_claim, invalid_outcome)

    def _trusted_claim(
        self,
        *,
        message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        project_id: UUID,
    ) -> ProjectDirectorProtectedTransitionWorkerInvocationClaimResult | None:
        if message is None or not self._message_metadata_valid(
            message=message,
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=project_id,
            intent=_CLAIM_INTENT,
            source_detail=P23_PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL,
        ):
            return None
        action = self._single_action(message)
        if not action or action.get("type") != P23_PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_ACTION_TYPE or action.get("schema_version") != PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_SCHEMA_VERSION:
            return None
        try:
            result = ProjectDirectorProtectedTransitionWorkerInvocationClaimResult.model_validate(
                {name: action.get(name) for name in ProjectDirectorProtectedTransitionWorkerInvocationClaimResult.model_fields}
            )
        except ValidationError:
            return None
        if (
            result.claim_id != message.id
            or result.created_at != message.created_at
            or result.claim_fingerprint != self._claim_fingerprint(result)
            or not set(self._claim_forbidden_actions()).issubset(message.forbidden_actions_detected)
        ):
            return None
        return result

    def _trusted_outcome(
        self,
        *,
        message: ProjectDirectorMessage,
        session_id: UUID,
        source_task_id: UUID,
        project_id: UUID,
    ) -> ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult | None:
        if not self._message_metadata_valid(
            message=message,
            session_id=session_id,
            source_task_id=source_task_id,
            project_id=project_id,
            intent=_OUTCOME_INTENT,
            source_detail=P23_PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL,
        ):
            return None
        action = self._single_action(message)
        if not action or action.get("type") != P23_PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_ACTION_TYPE or action.get("schema_version") != PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_SCHEMA_VERSION:
            return None
        try:
            result = ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult.model_validate(
                {name: action.get(name) for name in ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult.model_fields}
            )
        except ValidationError:
            return None
        if (
            result.outcome_id != message.id
            or result.created_at != message.created_at
            or result.resumed_from_existing_outcome
            or result.outcome_fingerprint != self._outcome_fingerprint(result)
            or not set(self._outcome_forbidden_actions()).issubset(message.forbidden_actions_detected)
        ):
            return None
        return result

    def _claim_message(
        self,
        result: ProjectDirectorProtectedTransitionWorkerInvocationClaimResult,
    ) -> ProjectDirectorMessage:
        return self._evidence_message(
            result=result,
            message_id=result.claim_id,
            intent=_CLAIM_INTENT,
            source_detail=P23_PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL,
            action_type=P23_PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_ACTION_TYPE,
            schema_version=PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_SCHEMA_VERSION,
            content=(
                "The exact protected-transition Worker invocation was uniquely claimed. "
                "The Worker has not been called yet. No AgentSession, runtime, provider, "
                "continuation, or rework execution has started in this claim phase. "
                "No Task or Run was created, rerouted, or reclaimed, and no product "
                "runtime Git write was authorized."
            ),
            forbidden_actions=self._claim_forbidden_actions(),
        )

    def _outcome_message(
        self,
        result: ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult,
    ) -> ProjectDirectorMessage:
        content = {
            "not_invoked": (
                "A unique invocation claim was recorded, but the final current "
                "revalidation failed before the Worker call. The Worker was not called."
            ),
            "returned": (
                "The exact reserved Worker entry returned and its normalized outcome "
                "was recorded."
            ),
            "raised": (
                "The exact reserved Worker entry raised an exception. The invocation "
                "claim remains consumed and automatic reinvocation is forbidden. "
                "Recovery review is required."
            ),
        }[result.outcome_status]
        return self._evidence_message(
            result=result,
            message_id=result.outcome_id,
            intent=_OUTCOME_INTENT,
            source_detail=P23_PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL,
            action_type=P23_PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_ACTION_TYPE,
            schema_version=PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_SCHEMA_VERSION,
            content=content,
            forbidden_actions=self._outcome_forbidden_actions(),
        )

    def _evidence_message(
        self,
        *,
        result: Any,
        message_id: UUID,
        intent: str,
        source_detail: str,
        action_type: str,
        schema_version: str,
        content: str,
        forbidden_actions: list[str],
    ) -> ProjectDirectorMessage:
        action = result.model_dump(mode="json")
        action.update(type=action_type, schema_version=schema_version)
        return ProjectDirectorMessage(
            id=message_id,
            session_id=result.session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content=content,
            sequence_no=self._message_repository.get_next_sequence_no(session_id=result.session_id),
            intent=intent,
            related_project_id=result.project_id,
            related_task_id=result.source_task_id,
            source=ProjectDirectorMessageSource.SYSTEM,
            source_detail=source_detail,
            suggested_actions=[action],
            requires_confirmation=False,
            risk_level=ProjectDirectorMessageRiskLevel.HIGH,
            forbidden_actions_detected=forbidden_actions,
            created_at=result.created_at,
        )

    @classmethod
    def _claim_fingerprint(
        cls,
        result: ProjectDirectorProtectedTransitionWorkerInvocationClaimResult,
    ) -> str:
        excluded = {"claim_id", "claim_fingerprint", "claim_token", "created_at"}
        payload = {
            "schema_version": PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_SCHEMA_VERSION,
            **{key: value for key, value in result.model_dump(mode="json").items() if key not in excluded},
        }
        return cls._canonical_fingerprint(payload)

    @classmethod
    def _outcome_fingerprint(
        cls,
        result: ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult,
    ) -> str:
        excluded = {"outcome_id", "outcome_fingerprint", "created_at", "resumed_from_existing_outcome"}
        payload = {
            "schema_version": PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_SCHEMA_VERSION,
            **{key: value for key, value in result.model_dump(mode="json").items() if key not in excluded},
        }
        return cls._canonical_fingerprint(payload)

    @staticmethod
    def _outcome_binds_claim(
        *,
        outcome: ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult,
        claim: ProjectDirectorProtectedTransitionWorkerInvocationClaimResult,
    ) -> bool:
        return all(
            (
                outcome.source_claim_id == claim.claim_id,
                outcome.source_claim_fingerprint == claim.claim_fingerprint,
                outcome.source_claim_token == claim.claim_token,
                outcome.source_reservation_message_id == claim.source_reservation_message_id,
                outcome.source_reservation_fingerprint == claim.source_reservation_fingerprint,
                outcome.run_id == claim.run_id,
            )
        )

    @staticmethod
    def _message_metadata_valid(
        *,
        message: ProjectDirectorMessage,
        session_id: UUID,
        source_task_id: UUID,
        project_id: UUID,
        intent: str,
        source_detail: str,
    ) -> bool:
        return bool(
            message.session_id == session_id
            and message.related_project_id == project_id
            and message.related_task_id == source_task_id
            and message.role == ProjectDirectorMessageRole.ASSISTANT
            and message.source == ProjectDirectorMessageSource.SYSTEM
            and message.intent == intent
            and message.source_detail == source_detail
            and message.requires_confirmation is False
            and message.risk_level == ProjectDirectorMessageRiskLevel.HIGH
        )

    def _iter_session_messages(self, session_id: UUID) -> list[ProjectDirectorMessage]:
        result: list[ProjectDirectorMessage] = []
        before: UUID | None = None
        while True:
            messages, has_more = self._message_repository.list_by_session_id(
                session_id=session_id,
                limit=_PAGE_SIZE,
                before_message_id=before,
            )
            result.extend(messages)
            if not has_more or not messages:
                return result
            before = messages[0].id

    @staticmethod
    def _single_action(message: ProjectDirectorMessage) -> dict[str, Any] | None:
        if len(message.suggested_actions) != 1 or not isinstance(message.suggested_actions[0], dict):
            return None
        return message.suggested_actions[0]

    @staticmethod
    def _canonical_fingerprint(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _safe_exception_summary(exc: Exception) -> str:
        summary = str(exc).replace("\r", " ").replace("\n", " ")
        summary = _SECRET_PATTERN.sub(r"\1=[REDACTED]", summary)
        return summary[:500] or type(exc).__name__

    @staticmethod
    def _git_activity_fields() -> tuple[str, ...]:
        return (
            "workspace_context_runs_write_git",
            "runtime_launch_dry_run_runs_write_git",
            "runtime_launch_gate_runs_write_git",
            "worktree_safe_command_proof_runs_write_git",
            "git_diff_dry_run_runs_write_git",
            "git_operation_dry_run_runs_write_git",
            "git_diff_dry_run_git_add_triggered",
            "git_diff_dry_run_git_commit_triggered",
            "git_diff_dry_run_git_push_triggered",
            "git_operation_dry_run_git_add_triggered",
            "git_operation_dry_run_git_commit_triggered",
            "git_operation_dry_run_git_push_triggered",
            "git_operation_dry_run_operation_applied",
        )

    @staticmethod
    def _claim_forbidden_actions() -> list[str]:
        return [
            "no_worker_call_in_claim_transaction",
            "no_agent_session_creation_in_claim_transaction",
            "no_runtime_start_in_claim_transaction",
            "no_provider_call_in_claim_transaction",
            "no_task_creation",
            "no_run_creation",
            "no_task_reroute",
            "no_task_reclaim",
            "no_product_runtime_git_write",
            "no_pr_creation",
            "no_merge",
            "no_ci_trigger",
        ]

    @staticmethod
    def _outcome_forbidden_actions() -> list[str]:
        return [
            "no_task_creation_by_p23_d2_b2",
            "no_run_creation_by_p23_d2_b2",
            "no_task_reroute",
            "no_task_reclaim",
            "no_second_worker_invocation",
            "no_product_runtime_git_write_authority",
            "no_pr_creation",
            "no_merge",
            "no_ci_trigger",
        ]

    @staticmethod
    def _blocked(reasons: list[str]) -> InvokedProjectDirectorProtectedTransitionWorker:
        return InvokedProjectDirectorProtectedTransitionWorker(
            claim=None,
            claim_message=None,
            outcome=None,
            outcome_message=None,
            blocked_reasons=list(dict.fromkeys(reasons)),
        )

    def _require_shared_sqlalchemy_session(self) -> None:
        session = self._message_repository._session
        dependencies = (
            self._session_repository._session,
            self._task_repository.session,
            self._run_repository.session,
            self._agent_session_repository.session,
            self._task_worker.session,
        )
        if any(candidate is not session for candidate in dependencies):
            raise ValueError("B2 dependencies must share one SQLAlchemy Session")
        if (
            self._worker_start_reservation_service._message_repository
            is not self._message_repository
            or self._worker_start_reservation_service._task_repository
            is not self._task_repository
            or self._worker_start_reservation_service._run_repository
            is not self._run_repository
            or self._worker_start_reservation_service._agent_session_repository
            is not self._agent_session_repository
            or self._freshness_service is not self._worker_start_reservation_service._freshness_service
        ):
            raise ValueError("B2 revalidation dependencies must share instances")


__all__ = (
    "InvokedProjectDirectorProtectedTransitionWorker",
    "P23_PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_ACTION_TYPE",
    "P23_PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL",
    "P23_PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_ACTION_TYPE",
    "P23_PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL",
    "PROTECTED_TRANSITION_WORKER_INVOCATION_CLAIM_SCHEMA_VERSION",
    "PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_SCHEMA_VERSION",
    "ProjectDirectorProtectedTransitionWorkerInvocationService",
)
