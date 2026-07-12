"""Read-only P23 adapter for the generic execution-authority contract."""

from __future__ import annotations

from typing import Literal, cast
from uuid import UUID

from pydantic import ValidationError

from app.domain.project_director_source_execution_authority import (
    SourceExecutionAuthorityBlockedReason,
    SourceExecutionAuthorityResolution,
    SourceExecutionAuthoritySnapshot,
)
from app.domain.project_director_protected_transition_dispatch_consumption import (
    ProjectDirectorProtectedTransitionDispatchConsumptionResult,
)
from app.domain.project_director_protected_transition_worker_invocation import (
    ProjectDirectorProtectedTransitionWorkerInvocationClaimResult,
    ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult,
)
from app.domain.project_director_protected_transition_worker_start_reservation import (
    ProjectDirectorProtectedTransitionWorkerStartReservationResult,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.services.project_director_protected_transition_dispatch_consumption_service import (
    ProjectDirectorProtectedTransitionDispatchConsumptionService,
)
from app.services.project_director_protected_transition_worker_invocation_service import (
    PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_SCHEMA_VERSION,
    ProjectDirectorProtectedTransitionWorkerInvocationService,
)
from app.services.project_director_protected_transition_worker_start_reservation_service import (
    ProjectDirectorProtectedTransitionWorkerStartReservationService,
)


class P23ProtectedTransitionExecutionAuthorityAdapter:
    """Reconstruct P23 D1/B1/B2 lineage from one durable B2 outcome ID."""

    authority_kind: Literal["p23_protected_transition"] = (
        "p23_protected_transition"
    )

    def __init__(
        self,
        *,
        message_repository: ProjectDirectorMessageRepository,
        dispatch_consumption_service: ProjectDirectorProtectedTransitionDispatchConsumptionService,
        worker_start_reservation_service: (
            ProjectDirectorProtectedTransitionWorkerStartReservationService
        ),
        worker_invocation_service: ProjectDirectorProtectedTransitionWorkerInvocationService,
    ) -> None:
        self._message_repository = message_repository
        self._dispatch_consumption_service = dispatch_consumption_service
        self._worker_start_reservation_service = worker_start_reservation_service
        self._worker_invocation_service = worker_invocation_service
        if (
            dispatch_consumption_service._message_repository
            is not message_repository
            or worker_start_reservation_service._message_repository
            is not message_repository
            or worker_invocation_service._message_repository
            is not message_repository
            or worker_start_reservation_service._dispatch_consumption_service
            is not dispatch_consumption_service
            or worker_invocation_service._worker_start_reservation_service
            is not worker_start_reservation_service
        ):
            raise ValueError("P23 authority adapter dependencies must share lineage readers")

    def resolve(
        self,
        *,
        authority_record_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
    ) -> SourceExecutionAuthorityResolution:
        revalidate_invocation = (
            self._worker_invocation_service
            .revalidate_persisted_protected_transition_worker_invocation
        )
        invocation = revalidate_invocation(
            source_outcome_message_id=authority_record_id,
            source_task_id=source_task_id,
            source_run_id=source_run_id,
        )
        if invocation.blocked_reasons:
            return self._blocked_from_p23(invocation.blocked_reasons)
        claim = invocation.claim
        outcome = invocation.outcome
        claim_message = invocation.claim_message
        outcome_message = invocation.outcome_message
        if (
            claim is None
            or outcome is None
            or claim_message is None
            or outcome_message is None
        ):
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_lineage_invalid"
            )

        revalidate_reservation = (
            self._worker_start_reservation_service
            .revalidate_persisted_protected_transition_worker_start_reservation
        )
        reservation_revalidation = revalidate_reservation(
            session_id=outcome.session_id,
            source_task_id=source_task_id,
            source_reservation_message_id=claim.source_reservation_message_id,
        )
        if reservation_revalidation.blocked_reasons:
            return self._blocked_from_p23(reservation_revalidation.blocked_reasons)
        reservation = reservation_revalidation.result
        reservation_message = reservation_revalidation.message
        if reservation is None or reservation_message is None:
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_missing"
            )

        revalidate_consumption = (
            self._dispatch_consumption_service
            .revalidate_persisted_protected_transition_dispatch_consumption
        )
        consumption_revalidation = revalidate_consumption(
            session_id=outcome.session_id,
            source_task_id=source_task_id,
            source_consumption_message_id=claim.source_consumption_message_id,
        )
        if consumption_revalidation.blocked_reasons:
            return self._blocked_from_p23(consumption_revalidation.blocked_reasons)
        consumption = consumption_revalidation.result
        consumption_message = consumption_revalidation.message
        if consumption is None or consumption_message is None:
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_missing"
            )

        if not self._exact_lineage_matches(
            source_task_id=source_task_id,
            source_run_id=source_run_id,
            consumption=consumption,
            consumption_message_id=consumption_message.id,
            reservation=reservation,
            reservation_message_id=reservation_message.id,
            claim=claim,
            claim_message_id=claim_message.id,
            outcome=outcome,
            outcome_message_id=outcome_message.id,
        ):
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_lineage_invalid"
            )
        if (
            reservation_revalidation.task is None
            or reservation_revalidation.task.id != source_task_id
            or reservation_revalidation.run is None
            or reservation_revalidation.run.id != source_run_id
            or reservation_revalidation.run.task_id != source_task_id
            or consumption_revalidation.task is None
            or consumption_revalidation.task.id != source_task_id
            or consumption_revalidation.run is None
            or consumption_revalidation.run.id != source_run_id
            or consumption_revalidation.run.task_id != source_task_id
        ):
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_task_run_mismatch"
            )

        success_reasons = self._outcome_blocked_reasons(
            source_task_id=source_task_id,
            source_run_id=source_run_id,
            outcome=outcome,
        )
        if success_reasons:
            return SourceExecutionAuthorityResolution(
                resolved=False,
                snapshot=None,
                blocked_reasons=success_reasons,
            )

        optional_evidence_ids = (
            consumption.source_intent_message_id,
            consumption.source_freshness_message_id,
            consumption.source_preflight_message_id,
        )
        if any(evidence_id is None for evidence_id in optional_evidence_ids):
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_lineage_invalid"
            )
        evidence_ids = [
            cast(UUID, consumption.source_intent_message_id),
            cast(UUID, consumption.source_freshness_message_id),
            consumption.source_preflight_message_id,
            consumption_message.id,
            reservation_message.id,
            claim_message.id,
            outcome_message.id,
        ]
        try:
            snapshot = SourceExecutionAuthoritySnapshot(
                authority_kind=self.authority_kind,
                authority_id=consumption_message.id,
                authority_fingerprint=consumption.consumption_fingerprint,
                reservation_id=reservation_message.id,
                reservation_fingerprint=reservation.reservation_fingerprint,
                claim_id=claim_message.id,
                claim_fingerprint=claim.claim_fingerprint,
                outcome_id=outcome_message.id,
                outcome_schema_version=(
                    PROTECTED_TRANSITION_WORKER_INVOCATION_OUTCOME_SCHEMA_VERSION
                ),
                outcome_fingerprint=outcome.outcome_fingerprint,
                session_id=outcome.session_id,
                project_id=outcome.project_id,
                task_id=source_task_id,
                run_id=source_run_id,
                outcome_status="returned",
                worker_result_contract_valid=True,
                recovery_required=False,
                blocked_reasons=[],
                worker_reported_git_write_activity=False,
                product_runtime_git_write_allowed=False,
                source_review_id=consumption.source_review_message_id,
                source_review_outcome=self._source_review_outcome(
                    consumption.source_review_message_id
                ),
                source_transition_evidence_ids=evidence_ids,
            )
        except (TypeError, ValueError, ValidationError):
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_schema_mismatch"
            )
        return SourceExecutionAuthorityResolution.success(snapshot)

    @staticmethod
    def _exact_lineage_matches(
        *,
        source_task_id: UUID,
        source_run_id: UUID,
        consumption: ProjectDirectorProtectedTransitionDispatchConsumptionResult,
        consumption_message_id: UUID,
        reservation: ProjectDirectorProtectedTransitionWorkerStartReservationResult,
        reservation_message_id: UUID,
        claim: ProjectDirectorProtectedTransitionWorkerInvocationClaimResult,
        claim_message_id: UUID,
        outcome: ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult,
        outcome_message_id: UUID,
    ) -> bool:
        return all(
            (
                consumption.consumption_id == consumption_message_id,
                consumption.source_task_id == source_task_id,
                consumption.target_task_id == source_task_id,
                consumption.run_id == source_run_id,
                consumption.target_task_strategy
                in ("source_task_continue", "source_task_rework"),
                not consumption.product_runtime_git_write_allowed,
                reservation.reservation_id == reservation_message_id,
                reservation.session_id == consumption.session_id,
                reservation.project_id == consumption.project_id,
                reservation.source_task_id == source_task_id,
                reservation.target_task_id == source_task_id,
                reservation.run_id == source_run_id,
                reservation.source_consumption_id == consumption_message_id,
                reservation.source_consumption_message_id == consumption_message_id,
                reservation.source_consumption_fingerprint
                == consumption.consumption_fingerprint,
                reservation.target_task_strategy
                == consumption.target_task_strategy,
                not reservation.product_runtime_git_write_allowed,
                claim.claim_id == claim_message_id,
                claim.session_id == consumption.session_id,
                claim.project_id == consumption.project_id,
                claim.source_task_id == source_task_id,
                claim.target_task_id == source_task_id,
                claim.run_id == source_run_id,
                claim.source_reservation_id == reservation_message_id,
                claim.source_reservation_message_id == reservation_message_id,
                claim.source_reservation_fingerprint
                == reservation.reservation_fingerprint,
                claim.source_reservation_token == reservation.reservation_token,
                claim.source_consumption_message_id == consumption_message_id,
                claim.source_consumption_fingerprint
                == consumption.consumption_fingerprint,
                claim.source_preflight_message_id
                == reservation.source_preflight_message_id,
                claim.source_intent_message_id
                == reservation.source_intent_message_id,
                claim.source_freshness_message_id
                == reservation.source_freshness_message_id,
                claim.disposition_type == reservation.disposition_type,
                claim.dispatch_kind == reservation.dispatch_kind,
                claim.target_task_strategy == consumption.target_task_strategy,
                claim.review_result_fingerprint
                == reservation.review_result_fingerprint,
                claim.review_semantic_fingerprint
                == reservation.review_semantic_fingerprint,
                claim.current_freshness_fingerprint
                == reservation.reservation_current_freshness_fingerprint,
                claim.current_diff_sha256 == reservation.current_diff_sha256,
                claim.current_scope_paths == reservation.current_scope_paths,
                claim.workspace_path == reservation.workspace_path,
                claim.workspace_path_within_root
                == reservation.workspace_path_within_root,
                claim.rework_attempt_index == reservation.rework_attempt_index,
                claim.rework_attempt_limit == reservation.rework_attempt_limit,
                claim.budget_guard_allowed,
                not claim.retry_limit_reached,
                not claim.product_runtime_git_write_allowed,
                outcome.outcome_id == outcome_message_id,
                outcome.session_id == consumption.session_id,
                outcome.project_id == consumption.project_id,
                outcome.source_task_id == source_task_id,
                outcome.run_id == source_run_id,
                outcome.source_claim_id == claim_message_id,
                outcome.source_claim_message_id == claim_message_id,
                outcome.source_claim_fingerprint == claim.claim_fingerprint,
                outcome.source_reservation_message_id == reservation_message_id,
                outcome.source_reservation_fingerprint
                == reservation.reservation_fingerprint,
                outcome.source_consumption_message_id == consumption_message_id,
                outcome.target_task_strategy == consumption.target_task_strategy,
                not outcome.product_runtime_git_write_allowed,
            )
        )

    @staticmethod
    def _outcome_blocked_reasons(
        *,
        source_task_id: UUID,
        source_run_id: UUID,
        outcome: ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult,
    ) -> list[SourceExecutionAuthorityBlockedReason]:
        reasons: list[SourceExecutionAuthorityBlockedReason] = []
        if outcome.outcome_status != "returned":
            reasons.append("source_execution_authority_outcome_not_returned")
        if not all(
            (
                outcome.worker_call_attempted,
                outcome.worker_returned,
                not outcome.worker_raised,
                outcome.worker_result_contract_valid,
                outcome.reserved_snapshot_present,
                outcome.reserved_snapshot_exact_task_id == source_task_id,
                outcome.reserved_snapshot_exact_run_id == source_run_id,
                outcome.reserved_snapshot_exact_binding_validated,
                outcome.reserved_snapshot_shared_execution_seam_used,
                not outcome.reserved_snapshot_task_routed,
                not outcome.reserved_snapshot_task_claimed_in_this_cycle,
                not outcome.reserved_snapshot_run_created_in_this_cycle,
                not outcome.reserved_snapshot_blocked_reasons,
            )
        ):
            reasons.append("source_execution_authority_result_contract_invalid")
        if outcome.human_recovery_required:
            reasons.append("source_execution_authority_recovery_required")
        if outcome.blocked_reasons:
            reasons.append("source_execution_authority_blocked")
        if (
            outcome.worker_reported_git_write_activity
            or outcome.product_runtime_git_write_allowed
        ):
            reasons.append("source_execution_authority_git_boundary_violation")
        return list(dict.fromkeys(reasons))

    def _source_review_outcome(self, source_review_id: UUID | None) -> str | None:
        if source_review_id is None:
            return None
        message = self._message_repository.get_by_id(source_review_id)
        if message is None or len(message.suggested_actions) != 1:
            return None
        action = message.suggested_actions[0]
        verdict = action.get("verdict") if isinstance(action, dict) else None
        return verdict if isinstance(verdict, str) and 0 < len(verdict) <= 100 else None

    @staticmethod
    def _blocked_from_p23(reasons: list[str]) -> SourceExecutionAuthorityResolution:
        mapped: list[SourceExecutionAuthorityBlockedReason] = []
        for reason in reasons:
            if "missing" in reason:
                mapped.append("source_execution_authority_missing")
            elif "fingerprint" in reason:
                mapped.append("source_execution_authority_fingerprint_mismatch")
            elif "task" in reason or "run" in reason or "session" in reason:
                mapped.append("source_execution_authority_task_run_mismatch")
            elif "schema" in reason or reason.endswith("_invalid"):
                mapped.append("source_execution_authority_schema_mismatch")
            else:
                mapped.append("source_execution_authority_lineage_invalid")
        return SourceExecutionAuthorityResolution(
            resolved=False,
            snapshot=None,
            blocked_reasons=list(dict.fromkeys(mapped)),
        )


__all__ = ("P23ProtectedTransitionExecutionAuthorityAdapter",)
