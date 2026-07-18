"""Atomic P25-D exact bounded rework attempt reservation service."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.domain._base import utc_now
from app.domain.project_director_bounded_rework_attempt_reservation import (
    BOUNDED_REWORK_ATTEMPT_RESERVATION_SCHEMA_VERSION,
    ProjectDirectorBoundedReworkAttemptReservation,
)
from app.domain.project_director_bounded_rework_contract import (
    BoundedReworkBlockedReason,
    P25_BOUNDED_REWORK_SCHEMA_VERSION,
)
from app.domain.project_director_bounded_rework_instruction_package import (
    ProjectDirectorBoundedReworkInstructionPackage,
)
from app.domain.project_director_bounded_rework_invocation_claim import (
    BOUNDED_REWORK_INVOCATION_CLAIM_SCHEMA_VERSION,
    ProjectDirectorBoundedReworkInvocationClaim,
)
from app.domain.project_director_bounded_rework_invocation_outcome import (
    BOUNDED_REWORK_INVOCATION_OUTCOME_SCHEMA_VERSION,
    ProjectDirectorBoundedReworkInvocationOutcome,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.run import RunStatus
from app.domain.task import TaskHumanStatus, TaskStatus
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.project_director_bounded_rework_package_preparation_service import (
    P25_BOUNDED_REWORK_PACKAGE_INTENT,
    ProjectDirectorBoundedReworkPackagePreparationService,
    RevalidatedPersistedBoundedReworkInstructionPackage,
)

if TYPE_CHECKING:
    from app.services.project_director_protected_transition_worker_invocation_service import (
        ProjectDirectorProtectedTransitionWorkerInvocationService,
    )
    from app.services.project_director_protected_transition_worker_start_reservation_service import (
        ProjectDirectorProtectedTransitionWorkerStartReservationService,
    )


P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_SOURCE_DETAIL = (
    "p25_bounded_rework_attempt_reserved"
)
P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_ACTION_TYPE = (
    "p25_bounded_rework_attempt_reservation_record"
)
P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_INTENT = (
    "bounded_rework_attempt_reservation"
)

_FORMAL_FALSE_BOUNDARIES = (
    "external_call_performed=false",
    "sandbox_file_written=false",
    "product_runtime_git_write_allowed=false",
    "main_project_write_allowed=false",
    "git_add_allowed=false",
    "git_commit_allowed=false",
    "git_push_allowed=false",
    "branch_operation_allowed=false",
    "pull_request_allowed=false",
    "merge_allowed=false",
    "ci_trigger_allowed=false",
)

ReservationPreparationStatus = Literal[
    "reservation_reserved",
    "reservation_replayed",
    "blocked",
]


@dataclass(frozen=True, slots=True)
class PreparedProjectDirectorBoundedReworkAttemptReservation:
    status: ReservationPreparationStatus
    reservation: ProjectDirectorBoundedReworkAttemptReservation | None
    message: ProjectDirectorMessage | None
    blocked_reasons: tuple[BoundedReworkBlockedReason, ...]


@dataclass(frozen=True, slots=True)
class RevalidatedPersistedBoundedReworkAttemptReservation:
    """Pure reconstruction of one exact persisted P25-D reservation."""

    reservation: ProjectDirectorBoundedReworkAttemptReservation | None
    message: ProjectDirectorMessage | None
    package: ProjectDirectorBoundedReworkInstructionPackage | None
    packages: tuple[ProjectDirectorBoundedReworkInstructionPackage, ...]
    reservations: tuple[ProjectDirectorBoundedReworkAttemptReservation, ...]
    claims: tuple[ProjectDirectorBoundedReworkInvocationClaim, ...]
    outcomes: tuple[ProjectDirectorBoundedReworkInvocationOutcome, ...]
    blocked_reasons: tuple[BoundedReworkBlockedReason, ...]


class _Blocked(RuntimeError):
    def __init__(self, reason: BoundedReworkBlockedReason) -> None:
        self.reason = reason
        super().__init__(reason)


class ProjectDirectorBoundedReworkAttemptReservationService:
    """Replay or append one exact P25 reservation without external side effects."""

    def __init__(
        self,
        *,
        message_repository: ProjectDirectorMessageRepository,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        package_preparation_service: (
            ProjectDirectorBoundedReworkPackagePreparationService
        ),
        worker_start_reservation_service: (
            ProjectDirectorProtectedTransitionWorkerStartReservationService
        ),
        worker_invocation_service: (
            ProjectDirectorProtectedTransitionWorkerInvocationService
        ),
    ) -> None:
        self._message_repository = message_repository
        self._task_repository = task_repository
        self._run_repository = run_repository
        self._package_preparation_service = package_preparation_service
        self._worker_start_reservation_service = worker_start_reservation_service
        self._worker_invocation_service = worker_invocation_service
        self._require_shared_repositories()

    def revalidate_persisted_bounded_rework_attempt_reservation(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_reservation_message_id: UUID,
    ) -> RevalidatedPersistedBoundedReworkAttemptReservation:
        """Rebuild an exact reservation and current authority without writes."""

        try:
            history = self._package_preparation_service.revalidate_persisted_bounded_rework_instruction_package_for_execution(
                session_id=session_id,
                source_task_id=source_task_id,
                source_package_message_id=self._reservation_package_message_id(
                    source_reservation_message_id
                ),
            )
            if history.blocked_reasons:
                raise _Blocked(history.blocked_reasons[0])
            package = history.package
            package_message = history.message
            if package is None or package_message is None:
                raise _Blocked("history_invalid")

            message = self._message_repository.get_by_id(
                source_reservation_message_id
            )
            if message is None or len(message.suggested_actions) != 1:
                raise _Blocked("authority_invalid")
            action = message.suggested_actions[0]
            if (
                not isinstance(action, dict)
                or action.get("type")
                != P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_ACTION_TYPE
                or action.get("schema_version")
                != BOUNDED_REWORK_ATTEMPT_RESERVATION_SCHEMA_VERSION
            ):
                raise _Blocked("history_invalid")
            payload = dict(action)
            payload.pop("type", None)
            reservation = (
                ProjectDirectorBoundedReworkAttemptReservation.model_validate(
                    payload
                )
            )
            if (
                message.id != source_reservation_message_id
                or message.session_id != session_id
                or message.related_task_id != source_task_id
                or reservation.reservation_id != source_reservation_message_id
                or reservation.exact_task_id != source_task_id
                or reservation.authority.session_id != session_id
                or reservation.package_id != package.package_id
                or not self._reservation_message_valid(
                    message=message,
                    reservation=reservation,
                )
                or not self._reservation_binds_package(reservation, package)
            ):
                raise _Blocked("authority_invalid")
            exact = [
                item
                for item in history.reservations
                if item.reservation_id == source_reservation_message_id
            ]
            if len(exact) != 1 or exact[0] != reservation:
                raise _Blocked("history_invalid")

            self._validate_exact_task_and_run(package)
            self._validate_p23_generic_history(package)
            self._validate_raw_p25_history_coverage(history)
            self._validate_p25_history(history)
            self._validate_recovery_locks(
                source_task_id=source_task_id,
                outcomes=history.outcomes,
            )
            return RevalidatedPersistedBoundedReworkAttemptReservation(
                reservation=reservation,
                message=message,
                package=package,
                packages=history.packages,
                reservations=history.reservations,
                claims=history.claims,
                outcomes=history.outcomes,
                blocked_reasons=(),
            )
        except _Blocked as exc:
            return self._blocked_revalidation(exc.reason)
        except SQLAlchemyError:
            return self._blocked_revalidation("persistence_failed")
        except (OSError, RuntimeError, TypeError, ValueError, ValidationError):
            return self._blocked_revalidation("history_invalid")

    def _reservation_package_message_id(
        self,
        source_reservation_message_id: UUID,
    ) -> UUID:
        """Read only the persisted reservation locator needed for package revalidation."""

        message = self._message_repository.get_by_id(
            source_reservation_message_id
        )
        if message is None or len(message.suggested_actions) != 1:
            raise _Blocked("authority_invalid")
        action = message.suggested_actions[0]
        if (
            not isinstance(action, dict)
            or action.get("type")
            != P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_ACTION_TYPE
            or action.get("schema_version")
            != BOUNDED_REWORK_ATTEMPT_RESERVATION_SCHEMA_VERSION
        ):
            raise _Blocked("history_invalid")
        try:
            return UUID(str(action.get("package_id")))
        except (TypeError, ValueError) as exc:
            raise _Blocked("history_invalid") from exc

    def reserve_bounded_rework_attempt(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_package_message_id: UUID,
    ) -> PreparedProjectDirectorBoundedReworkAttemptReservation:
        """Reserve from three locators; all semantic values come from persistence."""

        session = self._message_repository._session
        caller_had_transaction = session.in_transaction()
        initial = self._package_preparation_service.revalidate_persisted_bounded_rework_instruction_package(
            session_id=session_id,
            source_task_id=source_task_id,
            source_package_message_id=source_package_message_id,
        )
        # Read-only preflight uses SQLAlchemy autobegin. Release it before the
        # exact reservation phase acquires SQLite's write reservation, without
        # rolling back a transaction owned by the caller.
        if not caller_had_transaction and session.in_transaction():
            session.rollback()
        if initial.blocked_reasons:
            return self._blocked(initial.blocked_reasons[0])
        if initial.package is None or initial.message is None:
            return self._blocked("history_invalid")

        try:
            with self._message_repository.sqlite_immediate_transaction():
                current = self._package_preparation_service.revalidate_persisted_bounded_rework_instruction_package(
                    session_id=session_id,
                    source_task_id=source_task_id,
                    source_package_message_id=source_package_message_id,
                )
                if current.blocked_reasons:
                    raise _Blocked(current.blocked_reasons[0])
                if (
                    current.package is None
                    or current.message is None
                    or current.package != initial.package
                    or current.message != initial.message
                ):
                    raise _Blocked("history_invalid")
                return self._reserve_or_replay(
                    package=current.package,
                    history=current,
                )
        except _Blocked as exc:
            return self._blocked(exc.reason)
        except SQLAlchemyError:
            return self._blocked("persistence_failed")
        except (OSError, RuntimeError, TypeError, ValueError, ValidationError):
            return self._blocked("history_invalid")

    def _reserve_or_replay(
        self,
        *,
        package: ProjectDirectorBoundedReworkInstructionPackage,
        history: RevalidatedPersistedBoundedReworkInstructionPackage,
    ) -> PreparedProjectDirectorBoundedReworkAttemptReservation:
        authority = package.authority
        if (
            authority is None
            or package.package_replay_key is None
            or package.workspace_binding is None
            or package.base_commit_sha is None
            or package.source_candidate_diff_sha256 is None
            or package.rework_attempt_index is None
            or package.rework_attempt_limit is None
        ):
            raise _Blocked("authority_invalid")

        self._validate_exact_task_and_run(package)
        self._validate_p23_generic_history(package)
        self._validate_raw_p25_history_coverage(history)
        self._validate_p25_history(history)
        self._validate_recovery_locks(
            source_task_id=authority.source_task_id,
            outcomes=history.outcomes,
        )

        replay_key = ProjectDirectorBoundedReworkAttemptReservation.compute_reservation_replay_key(
            package_id=package.package_id,
            package_fingerprint=package.package_fingerprint,
            authority=authority,
            exact_task_id=authority.source_task_id,
            exact_run_id=authority.source_run_id,
            rework_attempt_index=package.rework_attempt_index,
        )
        exact_matches = [
            item
            for item in history.reservations
            if item.reservation_replay_key == replay_key
        ]
        if len(exact_matches) > 1:
            raise _Blocked("history_invalid")

        conflicting = [
            item
            for item in history.reservations
            if (
                item.package_id == package.package_id
                or item.authority.source_p23_dispatch_consumption_id
                == authority.source_p23_dispatch_consumption_id
                or item.exact_run_id == authority.source_run_id
                or (
                    item.exact_task_id == authority.source_task_id
                    and item.rework_attempt_index == package.rework_attempt_index
                )
            )
            and item.reservation_replay_key != replay_key
        ]
        if conflicting:
            raise _Blocked("authority_replayed")

        if exact_matches:
            existing = exact_matches[0]
            candidate = self._build_reservation(
                package=package,
                reservation_id=existing.reservation_id,
                reservation_token=existing.reservation_token,
                created_at=existing.created_at,
            )
            if candidate != existing:
                raise _Blocked("history_invalid")
            message = self._message_repository.get_by_id(existing.reservation_id)
            if message is None or not self._reservation_message_valid(
                message=message,
                reservation=existing,
            ):
                raise _Blocked("history_invalid")
            return PreparedProjectDirectorBoundedReworkAttemptReservation(
                status="reservation_replayed",
                reservation=existing,
                message=message,
                blocked_reasons=(),
            )

        reservation = self._build_reservation(
            package=package,
            reservation_id=uuid4(),
            reservation_token=secrets.token_hex(32),
            created_at=utc_now(),
        )
        message = self._build_reservation_message(reservation)
        try:
            persisted = self._message_repository.create(message)
        except (TypeError, ValueError, ValidationError, SQLAlchemyError) as exc:
            raise _Blocked("persistence_failed") from exc
        if persisted != message:
            raise _Blocked("persistence_failed")
        return PreparedProjectDirectorBoundedReworkAttemptReservation(
            status="reservation_reserved",
            reservation=reservation,
            message=persisted,
            blocked_reasons=(),
        )

    def _validate_exact_task_and_run(
        self,
        package: ProjectDirectorBoundedReworkInstructionPackage,
    ) -> None:
        assert package.authority is not None
        authority = package.authority
        task = self._task_repository.get_by_id(authority.source_task_id)
        run = self._run_repository.get_by_id(authority.source_run_id)
        if (
            task is None
            or task.id != authority.source_task_id
            or task.id != authority.target_task_id
            or task.project_id != authority.project_id
        ):
            raise _Blocked("authority_invalid")
        if (
            task.status == TaskStatus.PAUSED
            or task.human_status
            in {TaskHumanStatus.REQUESTED, TaskHumanStatus.IN_PROGRESS}
            or task.paused_reason is not None
        ):
            raise _Blocked("human_escalation_required")
        if task.status != TaskStatus.RUNNING:
            raise _Blocked("authority_invalid")
        if (
            run is None
            or run.id != authority.source_run_id
            or run.task_id != authority.source_task_id
            or run.status != RunStatus.RUNNING
            or run.started_at is None
            or run.finished_at is not None
        ):
            raise _Blocked("authority_invalid")

    def _validate_p23_generic_history(
        self,
        package: ProjectDirectorBoundedReworkInstructionPackage,
    ) -> None:
        assert package.authority is not None
        authority = package.authority
        reservation_history = self._worker_start_reservation_service._scan_reservation_history(
            session_id=authority.session_id,
            source_task_id=authority.source_task_id,
            project_id=authority.project_id,
        )
        invocation_history = self._worker_invocation_service._scan_history(
            session_id=authority.session_id,
            source_task_id=authority.source_task_id,
            project_id=authority.project_id,
        )
        if (
            reservation_history.invalid
            or invocation_history.invalid_claim
            or invocation_history.invalid_outcome
        ):
            raise _Blocked("history_invalid")

        valid_reservation_message_ids = {
            message.id
            for _, message in reservation_history.valid_reservations
        }
        valid_claim_message_ids = {
            message.id for _, message in invocation_history.claims
        }
        valid_outcome_message_ids = {
            message.id for _, message in invocation_history.outcomes
        }
        for message in self._package_preparation_service._iter_session_messages(
            authority.session_id
        ):
            action = (
                message.suggested_actions[0]
                if len(message.suggested_actions) == 1
                and isinstance(message.suggested_actions[0], dict)
                else None
            )
            if action is None:
                continue
            same_consumption = action.get("source_consumption_message_id") == str(
                authority.source_p23_dispatch_consumption_id
            )
            same_run = action.get("run_id") == str(authority.source_run_id)
            if not (same_consumption or same_run):
                continue
            record_kind = {
                "p23_d2_worker_start_reservation_record": "reservation",
                "p23_d2_worker_invocation_claim_record": "claim",
                "p23_d2_worker_invocation_outcome_record": "outcome",
            }.get(action.get("type"))
            if record_kind == "reservation":
                if message.source_detail != "p23_d2_worker_start_reserved":
                    raise _Blocked("history_invalid")
                if message.id not in valid_reservation_message_ids:
                    raise _Blocked("history_invalid")
                if same_consumption != same_run:
                    raise _Blocked("authority_replayed")
            elif record_kind == "claim":
                if message.source_detail != "p23_d2_worker_invocation_claimed":
                    raise _Blocked("history_invalid")
                if message.id not in valid_claim_message_ids:
                    raise _Blocked("history_invalid")
                raise _Blocked("authority_replayed")
            elif record_kind == "outcome":
                if (
                    message.source_detail
                    != "p23_d2_worker_invocation_outcome_recorded"
                ):
                    raise _Blocked("history_invalid")
                if message.id not in valid_outcome_message_ids:
                    raise _Blocked("history_invalid")
                raise _Blocked("authority_replayed")
            elif message.source_detail.startswith("p23_d2_worker_"):
                raise _Blocked("history_invalid")

        for reservation, _ in reservation_history.valid_reservations:
            same_consumption = (
                reservation.source_consumption_message_id
                == authority.source_p23_dispatch_consumption_id
            )
            same_run = reservation.run_id == authority.source_run_id
            if same_consumption != same_run:
                raise _Blocked("authority_replayed")
            if (same_consumption or same_run) and (
                reservation.source_task_id != authority.source_task_id
                or reservation.project_id != authority.project_id
                or reservation.source_consumption_fingerprint
                != authority.source_p23_dispatch_consumption_fingerprint
            ):
                raise _Blocked("authority_replayed")

        for claim, _ in invocation_history.claims:
            if (
                claim.source_consumption_message_id
                == authority.source_p23_dispatch_consumption_id
                or claim.run_id == authority.source_run_id
            ):
                raise _Blocked("authority_replayed")
        for outcome, _ in invocation_history.outcomes:
            if (
                outcome.source_consumption_message_id
                == authority.source_p23_dispatch_consumption_id
                or outcome.run_id == authority.source_run_id
            ):
                raise _Blocked("authority_replayed")

    def _validate_p25_history(
        self,
        history: RevalidatedPersistedBoundedReworkInstructionPackage,
    ) -> None:
        packages = {item.package_id: item for item in history.packages}
        reservations = {item.reservation_id: item for item in history.reservations}
        claims = {item.claim_id: item for item in history.claims}
        if (
            len(packages) != len(history.packages)
            or len(reservations) != len(history.reservations)
            or len(claims) != len(history.claims)
        ):
            raise _Blocked("history_invalid")

        for reservation in history.reservations:
            package = packages.get(reservation.package_id)
            message = self._message_repository.get_by_id(reservation.reservation_id)
            if (
                package is None
                or not self._reservation_binds_package(reservation, package)
                or message is None
                or not self._reservation_message_valid(
                    message=message,
                    reservation=reservation,
                )
            ):
                raise _Blocked("history_invalid")

        for claim in history.claims:
            reservation = reservations.get(claim.reservation_id)
            if reservation is None or not self._claim_binds_reservation(
                claim,
                reservation,
            ):
                raise _Blocked("history_invalid")

        for outcome in history.outcomes:
            claim = claims.get(outcome.claim_id)
            reservation = reservations.get(outcome.reservation_id)
            if (
                claim is None
                or reservation is None
                or not self._outcome_binds_claim(outcome, claim, reservation)
            ):
                raise _Blocked("history_invalid")

        uniqueness_groups = (
            [item.package_id for item in history.reservations],
            [
                item.authority.source_p23_dispatch_consumption_id
                for item in history.reservations
            ],
            [item.exact_run_id for item in history.reservations],
            [
                (item.exact_task_id, item.rework_attempt_index)
                for item in history.reservations
            ],
            [item.reservation_id for item in history.claims],
            [item.claim_id for item in history.outcomes],
        )
        if any(len(values) != len(set(values)) for values in uniqueness_groups):
            raise _Blocked("history_invalid")

    def _validate_raw_p25_history_coverage(
        self,
        history: RevalidatedPersistedBoundedReworkInstructionPackage,
    ) -> None:
        if history.message is None:
            raise _Blocked("history_invalid")
        known_ids_by_schema = {
            P25_BOUNDED_REWORK_SCHEMA_VERSION: {
                item.package_id for item in history.packages
            },
            BOUNDED_REWORK_ATTEMPT_RESERVATION_SCHEMA_VERSION: {
                item.reservation_id for item in history.reservations
            },
            BOUNDED_REWORK_INVOCATION_CLAIM_SCHEMA_VERSION: {
                item.claim_id for item in history.claims
            },
            BOUNDED_REWORK_INVOCATION_OUTCOME_SCHEMA_VERSION: {
                item.outcome_id for item in history.outcomes
            },
        }
        for message in self._package_preparation_service._iter_session_messages(
            history.message.session_id
        ):
            action = (
                message.suggested_actions[0]
                if len(message.suggested_actions) == 1
                and isinstance(message.suggested_actions[0], dict)
                else None
            )
            intent_marks_p25 = message.intent in {
                P25_BOUNDED_REWORK_PACKAGE_INTENT,
                P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_INTENT,
                "bounded_rework_invocation_claim",
                "bounded_rework_invocation_outcome",
            }
            detail_marks_p25 = bool(
                message.source_detail
                and message.source_detail.startswith("p25_bounded_rework_")
            )
            schema_marks_p25 = bool(
                action
                and str(action.get("schema_version", "")).startswith("p25-b")
            )
            if not (intent_marks_p25 or detail_marks_p25 or schema_marks_p25):
                continue
            if action is None:
                raise _Blocked("history_invalid")
            schema_version = action.get("schema_version")
            if (
                schema_version not in known_ids_by_schema
                or message.id not in known_ids_by_schema[schema_version]
            ):
                raise _Blocked("history_invalid")

    @staticmethod
    def _validate_recovery_locks(
        *,
        source_task_id: UUID,
        outcomes: tuple[ProjectDirectorBoundedReworkInvocationOutcome, ...],
    ) -> None:
        relevant = [item for item in outcomes if item.exact_task_id == source_task_id]
        if any(item.git_activity_detected for item in relevant):
            raise _Blocked("git_boundary_violation")
        if any(
            item.recovery_required or item.human_escalation_required
            for item in relevant
        ):
            raise _Blocked("human_escalation_required")

    @staticmethod
    def _reservation_binds_package(
        reservation: ProjectDirectorBoundedReworkAttemptReservation,
        package: ProjectDirectorBoundedReworkInstructionPackage,
    ) -> bool:
        return bool(
            package.authority is not None
            and package.package_replay_key is not None
            and package.workspace_binding is not None
            and package.base_commit_sha is not None
            and package.source_candidate_diff_sha256 is not None
            and package.rework_attempt_index is not None
            and package.rework_attempt_limit is not None
            and reservation.replay_state == "new"
            and reservation.package_fingerprint == package.package_fingerprint
            and reservation.package_replay_key == package.package_replay_key
            and reservation.authority == package.authority
            and reservation.exact_task_id == package.authority.source_task_id
            and reservation.exact_run_id == package.authority.source_run_id
            and reservation.rework_attempt_index == package.rework_attempt_index
            and reservation.rework_attempt_limit == package.rework_attempt_limit
            and reservation.workspace_binding_fingerprint
            == package.workspace_binding.workspace_binding_fingerprint
            and reservation.base_commit_sha == package.base_commit_sha
            and reservation.source_candidate_diff_sha256
            == package.source_candidate_diff_sha256
        )

    @staticmethod
    def _claim_binds_reservation(
        claim: ProjectDirectorBoundedReworkInvocationClaim,
        reservation: ProjectDirectorBoundedReworkAttemptReservation,
    ) -> bool:
        return bool(
            claim.reservation_fingerprint == reservation.reservation_fingerprint
            and claim.reservation_token == reservation.reservation_token
            and claim.package_id == reservation.package_id
            and claim.package_fingerprint == reservation.package_fingerprint
            and claim.authority == reservation.authority
            and claim.exact_task_id == reservation.exact_task_id
            and claim.exact_run_id == reservation.exact_run_id
            and claim.rework_attempt_index == reservation.rework_attempt_index
            and claim.rework_attempt_limit == reservation.rework_attempt_limit
        )

    @staticmethod
    def _outcome_binds_claim(
        outcome: ProjectDirectorBoundedReworkInvocationOutcome,
        claim: ProjectDirectorBoundedReworkInvocationClaim,
        reservation: ProjectDirectorBoundedReworkAttemptReservation,
    ) -> bool:
        return bool(
            outcome.claim_fingerprint == claim.claim_fingerprint
            and outcome.claim_token == claim.claim_token
            and outcome.reservation_id == claim.reservation_id
            and outcome.reservation_fingerprint
            == reservation.reservation_fingerprint
            and outcome.package_id == claim.package_id
            and outcome.package_fingerprint == claim.package_fingerprint
            and outcome.authority == claim.authority
            and outcome.exact_task_id == claim.exact_task_id
            and outcome.exact_run_id == claim.exact_run_id
            and outcome.rework_attempt_index == claim.rework_attempt_index
            and outcome.rework_attempt_limit == claim.rework_attempt_limit
            and outcome.invocation_ordinal == claim.invocation_ordinal
        )

    @staticmethod
    def _build_reservation(
        *,
        package: ProjectDirectorBoundedReworkInstructionPackage,
        reservation_id: UUID,
        reservation_token: str,
        created_at: datetime,
    ) -> ProjectDirectorBoundedReworkAttemptReservation:
        assert package.authority is not None
        assert package.package_replay_key is not None
        assert package.workspace_binding is not None
        assert package.base_commit_sha is not None
        assert package.source_candidate_diff_sha256 is not None
        assert package.rework_attempt_index is not None
        assert package.rework_attempt_limit is not None
        values = {
            "reservation_id": reservation_id,
            "reservation_replay_key": ProjectDirectorBoundedReworkAttemptReservation.compute_reservation_replay_key(
                package_id=package.package_id,
                package_fingerprint=package.package_fingerprint,
                authority=package.authority,
                exact_task_id=package.authority.source_task_id,
                exact_run_id=package.authority.source_run_id,
                rework_attempt_index=package.rework_attempt_index,
            ),
            "reservation_token": reservation_token,
            "created_at": created_at,
            "reservation_status": "reserved",
            "replay_state": "new",
            "package_id": package.package_id,
            "package_fingerprint": package.package_fingerprint,
            "package_replay_key": package.package_replay_key,
            "authority": package.authority,
            "exact_task_id": package.authority.source_task_id,
            "exact_run_id": package.authority.source_run_id,
            "rework_attempt_index": package.rework_attempt_index,
            "rework_attempt_limit": package.rework_attempt_limit,
            "workspace_binding_fingerprint": (
                package.workspace_binding.workspace_binding_fingerprint
            ),
            "base_commit_sha": package.base_commit_sha,
            "source_candidate_diff_sha256": package.source_candidate_diff_sha256,
            "external_call_performed": False,
            "sandbox_file_written": False,
            "product_runtime_git_write_allowed": False,
            "main_project_write_allowed": False,
            "git_add_allowed": False,
            "git_commit_allowed": False,
            "git_push_allowed": False,
            "branch_operation_allowed": False,
            "pull_request_allowed": False,
            "merge_allowed": False,
            "ci_trigger_allowed": False,
        }
        draft = ProjectDirectorBoundedReworkAttemptReservation.model_construct(
            **values,
            reservation_fingerprint="0" * 64,
        )
        return ProjectDirectorBoundedReworkAttemptReservation(
            **values,
            reservation_fingerprint=draft.compute_fingerprint(),
        )

    def _build_reservation_message(
        self,
        reservation: ProjectDirectorBoundedReworkAttemptReservation,
    ) -> ProjectDirectorMessage:
        return ProjectDirectorMessage(
            id=reservation.reservation_id,
            session_id=reservation.authority.session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content=(
                "P25 bounded rework attempt reserved: "
                f"{reservation.reservation_id}"
            ),
            sequence_no=self._message_repository.get_next_sequence_no(
                session_id=reservation.authority.session_id
            ),
            intent=P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_INTENT,
            related_project_id=reservation.authority.project_id,
            related_task_id=reservation.authority.source_task_id,
            source=ProjectDirectorMessageSource.SYSTEM,
            source_detail=P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_SOURCE_DETAIL,
            suggested_actions=[
                {
                    "type": P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_ACTION_TYPE,
                    **reservation.model_dump(mode="json"),
                }
            ],
            requires_confirmation=False,
            risk_level=ProjectDirectorMessageRiskLevel.HIGH,
            forbidden_actions_detected=list(_FORMAL_FALSE_BOUNDARIES),
            token_count=None,
            estimated_cost=None,
            created_at=reservation.created_at,
        )

    @staticmethod
    def _reservation_message_valid(
        *,
        message: ProjectDirectorMessage,
        reservation: ProjectDirectorBoundedReworkAttemptReservation,
    ) -> bool:
        expected_action = {
            "type": P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_ACTION_TYPE,
            **reservation.model_dump(mode="json"),
        }
        return bool(
            message.id == reservation.reservation_id
            and message.created_at == reservation.created_at
            and message.session_id == reservation.authority.session_id
            and message.related_project_id == reservation.authority.project_id
            and message.related_task_id == reservation.authority.source_task_id
            and message.role == ProjectDirectorMessageRole.ASSISTANT
            and message.source == ProjectDirectorMessageSource.SYSTEM
            and message.intent == P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_INTENT
            and message.source_detail
            == P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_SOURCE_DETAIL
            and message.content
            == f"P25 bounded rework attempt reserved: {reservation.reservation_id}"
            and message.suggested_actions == [expected_action]
            and message.requires_confirmation is False
            and message.risk_level == ProjectDirectorMessageRiskLevel.HIGH
            and tuple(message.forbidden_actions_detected)
            == _FORMAL_FALSE_BOUNDARIES
            and message.token_count is None
            and message.estimated_cost is None
            and reservation.reservation_token not in message.content
        )

    def _require_shared_repositories(self) -> None:
        if (
            self._package_preparation_service._message_repository
            is not self._message_repository
            or self._worker_start_reservation_service._message_repository
            is not self._message_repository
            or self._worker_invocation_service._message_repository
            is not self._message_repository
            or self._worker_start_reservation_service._task_repository
            is not self._task_repository
            or self._worker_invocation_service._task_repository
            is not self._task_repository
            or self._worker_start_reservation_service._run_repository
            is not self._run_repository
            or self._worker_invocation_service._run_repository
            is not self._run_repository
            or self._task_repository.session
            is not self._message_repository._session
            or self._run_repository.session
            is not self._message_repository._session
        ):
            raise ValueError("P25-D dependencies must share one repository session")

    @staticmethod
    def _blocked(
        reason: BoundedReworkBlockedReason,
    ) -> PreparedProjectDirectorBoundedReworkAttemptReservation:
        return PreparedProjectDirectorBoundedReworkAttemptReservation(
            status="blocked",
            reservation=None,
            message=None,
            blocked_reasons=(reason,),
        )

    @staticmethod
    def _blocked_revalidation(
        reason: BoundedReworkBlockedReason,
    ) -> RevalidatedPersistedBoundedReworkAttemptReservation:
        return RevalidatedPersistedBoundedReworkAttemptReservation(
            reservation=None,
            message=None,
            package=None,
            packages=(),
            reservations=(),
            claims=(),
            outcomes=(),
            blocked_reasons=(reason,),
        )


__all__ = (
    "P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_ACTION_TYPE",
    "P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_INTENT",
    "P25_BOUNDED_REWORK_ATTEMPT_RESERVATION_SOURCE_DETAIL",
    "PreparedProjectDirectorBoundedReworkAttemptReservation",
    "ProjectDirectorBoundedReworkAttemptReservationService",
    "RevalidatedPersistedBoundedReworkAttemptReservation",
    "ReservationPreparationStatus",
)
