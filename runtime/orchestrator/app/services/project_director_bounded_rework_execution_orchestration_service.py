"""Dedicated P25 AUTO_REWORK execution coordinator over existing P25-B to P25-F services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.domain.project_director_bounded_rework_attempt_reservation import (
    ProjectDirectorBoundedReworkAttemptReservation,
)
from app.domain.project_director_bounded_rework_instruction_package import (
    ProjectDirectorBoundedReworkInstructionPackage,
)
from app.domain.project_director_bounded_rework_invocation_claim import (
    ProjectDirectorBoundedReworkInvocationClaim,
)
from app.domain.project_director_bounded_rework_invocation_outcome import (
    ProjectDirectorBoundedReworkInvocationOutcome,
)
from app.domain.project_director_message import ProjectDirectorMessage
from app.services.project_director_bounded_rework_attempt_reservation_service import (
    ProjectDirectorBoundedReworkAttemptReservationService,
)
from app.services.project_director_bounded_rework_invocation_outcome_service import (
    ProjectDirectorBoundedReworkInvocationOutcomeService,
)
from app.services.project_director_bounded_rework_package_preparation_service import (
    ProjectDirectorBoundedReworkPackagePreparationService,
)


BoundedReworkExecutionOrchestrationStatus = Literal[
    "outcome_recorded",
    "outcome_replayed",
    "recovery_required",
    "blocked",
]


@dataclass(frozen=True, slots=True)
class ExecutedProjectDirectorBoundedReworkOrchestration:
    status: BoundedReworkExecutionOrchestrationStatus
    package: ProjectDirectorBoundedReworkInstructionPackage | None
    package_message: ProjectDirectorMessage | None
    reservation: ProjectDirectorBoundedReworkAttemptReservation | None
    reservation_message: ProjectDirectorMessage | None
    claim: ProjectDirectorBoundedReworkInvocationClaim | None
    claim_message: ProjectDirectorMessage | None
    outcome: ProjectDirectorBoundedReworkInvocationOutcome | None
    outcome_message: ProjectDirectorMessage | None
    blocked_reasons: tuple[str, ...]
    recovery_required: bool = False
    human_escalation_required: bool = False
    resumed_from_existing_evidence: bool = False


class ProjectDirectorBoundedReworkExecutionOrchestrationService:
    """Replay-safe coordinator for the exclusive P25 AUTO_REWORK execution path."""

    def __init__(
        self,
        *,
        package_preparation_service: (
            ProjectDirectorBoundedReworkPackagePreparationService
        ),
        attempt_reservation_service: (
            ProjectDirectorBoundedReworkAttemptReservationService
        ),
        invocation_outcome_service: (
            ProjectDirectorBoundedReworkInvocationOutcomeService
        ),
    ) -> None:
        self._package_preparation_service = package_preparation_service
        self._attempt_reservation_service = attempt_reservation_service
        self._invocation_outcome_service = invocation_outcome_service
        self._message_repository = package_preparation_service._message_repository
        self._require_shared_message_repository()

    def execute_bounded_rework_from_consumption(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_p23_dispatch_consumption_message_id: UUID,
    ) -> ExecutedProjectDirectorBoundedReworkOrchestration:
        package_preparation = (
            self._package_preparation_service.prepare_bounded_rework_instruction_package(
                session_id=session_id,
                source_task_id=source_task_id,
                source_p23_dispatch_consumption_message_id=(
                    source_p23_dispatch_consumption_message_id
                ),
            )
        )
        if (
            package_preparation.status == "blocked"
            or package_preparation.message is None
        ):
            return self._result(
                status="blocked",
                package=package_preparation.package,
                package_message=package_preparation.message,
                blocked_reasons=package_preparation.blocked_reasons,
            )

        reservation_preparation = (
            self._attempt_reservation_service.reserve_bounded_rework_attempt(
                session_id=session_id,
                source_task_id=source_task_id,
                source_package_message_id=package_preparation.message.id,
            )
        )
        if (
            reservation_preparation.status == "blocked"
            or reservation_preparation.message is None
        ):
            return self._result(
                status="blocked",
                package=package_preparation.package,
                package_message=package_preparation.message,
                reservation=reservation_preparation.reservation,
                reservation_message=reservation_preparation.message,
                blocked_reasons=reservation_preparation.blocked_reasons,
                resumed_from_existing_evidence=(
                    package_preparation.status == "package_replayed"
                ),
            )

        execution = (
            self._invocation_outcome_service.execute_bounded_rework_from_reservation(
                session_id=session_id,
                source_task_id=source_task_id,
                source_reservation_message_id=reservation_preparation.message.id,
            )
        )
        resumed = (
            package_preparation.status == "package_replayed"
            or reservation_preparation.status == "reservation_replayed"
            or execution.status == "outcome_replayed"
        )
        if execution.status == "blocked":
            return self._result(
                status="recovery_required"
                if execution.recovery_required
                else "blocked",
                package=package_preparation.package,
                package_message=package_preparation.message,
                reservation=reservation_preparation.reservation,
                reservation_message=reservation_preparation.message,
                claim=execution.claim,
                claim_message=execution.claim_message,
                blocked_reasons=execution.blocked_reasons,
                recovery_required=execution.recovery_required,
                human_escalation_required=execution.human_escalation_required,
                resumed_from_existing_evidence=resumed,
            )

        return self._result(
            status=execution.status,
            package=package_preparation.package,
            package_message=package_preparation.message,
            reservation=reservation_preparation.reservation,
            reservation_message=reservation_preparation.message,
            claim=execution.claim,
            claim_message=execution.claim_message,
            outcome=execution.outcome,
            outcome_message=execution.outcome_message,
            blocked_reasons=(),
            recovery_required=execution.recovery_required,
            human_escalation_required=execution.human_escalation_required,
            resumed_from_existing_evidence=resumed,
        )

    @staticmethod
    def _result(
        *,
        status: BoundedReworkExecutionOrchestrationStatus,
        package: ProjectDirectorBoundedReworkInstructionPackage | None = None,
        package_message: ProjectDirectorMessage | None = None,
        reservation: ProjectDirectorBoundedReworkAttemptReservation | None = None,
        reservation_message: ProjectDirectorMessage | None = None,
        claim: ProjectDirectorBoundedReworkInvocationClaim | None = None,
        claim_message: ProjectDirectorMessage | None = None,
        outcome: ProjectDirectorBoundedReworkInvocationOutcome | None = None,
        outcome_message: ProjectDirectorMessage | None = None,
        blocked_reasons: tuple[str, ...] = (),
        recovery_required: bool = False,
        human_escalation_required: bool = False,
        resumed_from_existing_evidence: bool = False,
    ) -> ExecutedProjectDirectorBoundedReworkOrchestration:
        return ExecutedProjectDirectorBoundedReworkOrchestration(
            status=status,
            package=package,
            package_message=package_message,
            reservation=reservation,
            reservation_message=reservation_message,
            claim=claim,
            claim_message=claim_message,
            outcome=outcome,
            outcome_message=outcome_message,
            blocked_reasons=tuple(dict.fromkeys(reason for reason in blocked_reasons if reason)),
            recovery_required=recovery_required,
            human_escalation_required=human_escalation_required,
            resumed_from_existing_evidence=resumed_from_existing_evidence,
        )

    def _require_shared_message_repository(self) -> None:
        repositories = (
            self._package_preparation_service._message_repository,
            self._attempt_reservation_service._message_repository,
            self._invocation_outcome_service._message_repository,
        )
        repository = repositories[0]
        if any(candidate is not repository for candidate in repositories[1:]):
            raise ValueError("P25 execution orchestration dependencies must share one message repository")


__all__ = (
    "BoundedReworkExecutionOrchestrationStatus",
    "ExecutedProjectDirectorBoundedReworkOrchestration",
    "ProjectDirectorBoundedReworkExecutionOrchestrationService",
)
