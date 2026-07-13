"""Atomic P24-E2B exact Worker-start reservation persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.domain._base import utc_now
from app.domain.agent_session import AgentSessionStatus
from app.domain.project_director_cross_task_continuation import (
    CROSS_TASK_CONTINUATION_SCHEMA_VERSION,
    ProjectDirectorCrossTaskContinuationRoot,
)
from app.domain.project_director_cross_task_exact_run_reservation import (
    CROSS_TASK_EXACT_RUN_RESERVATION_ACTION_TYPE,
    CROSS_TASK_EXACT_RUN_RESERVATION_INTENT,
    CROSS_TASK_EXACT_RUN_RESERVATION_SCHEMA_VERSION,
    CROSS_TASK_EXACT_RUN_RESERVATION_SOURCE_DETAIL,
    ProjectDirectorCrossTaskExactRunReservation,
)
from app.domain.project_director_cross_task_exact_worker_start_reservation import (
    CROSS_TASK_EXACT_WORKER_START_RESERVATION_ACTION_TYPE,
    CROSS_TASK_EXACT_WORKER_START_RESERVATION_INTENT,
    CROSS_TASK_EXACT_WORKER_START_RESERVATION_SCHEMA_VERSION,
    CROSS_TASK_EXACT_WORKER_START_RESERVATION_SOURCE_DETAIL,
    CrossTaskExactWorkerStartReservationBlockedReason,
    ProjectDirectorCrossTaskExactWorkerStartReservation,
    ProjectDirectorCrossTaskExactWorkerStartReservationResult,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_next_task_instruction_package import (
    NEXT_TASK_INSTRUCTION_PACKAGE_SCHEMA_VERSION,
    ProjectDirectorNextTaskInstructionPackage,
    compute_p24_contract_sha256,
)
from app.domain.run import (
    Run,
    RunRoutingScoreItem,
    RunStatus,
    RunStrategyDecision,
    RunStrategyReasonItem,
)
from app.domain.task import Task, TaskHumanStatus, TaskStatus
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository


_PAGE_SIZE = 200

_PACKAGE_INTENT = "cross_task_next_task_instruction_package"
_PACKAGE_SOURCE_DETAIL = "p24_next_task_instruction_package_prepared"
_PACKAGE_ACTION_TYPE = "p24_next_task_instruction_package_record"

_ROOT_INTENT = "cross_task_auto_continue"
_ROOT_SOURCE_DETAIL = "p24_cross_task_continuation_recorded"
_ROOT_ACTION_TYPE = "p24_cross_task_continuation_record"

_E1B_CONTENT_PREFIX = "P24 exact next Task Run reservation"
_E2A_CONTENT_PREFIX = "P24 exact Worker-start reservation"

_E1B_REQUIRED_FORBIDDEN_ACTIONS = (
    "product_runtime_git_write",
    "git_add",
    "git_commit",
    "git_push",
    "pull_request_creation",
    "merge",
    "branch_destruction",
    "global_pending_task_scan",
    "next_task_skip",
    "plan_mutation",
    "duplicate_task_creation",
    "duplicate_task_claim",
    "duplicate_run_creation",
    "worker_invocation",
    "worker_invocation_without_reservation",
    "verification_command_execution",
    "uncontrolled_workspace_write",
)
_E1B_COMPLETED_ACTIONS = {"task_claim", "run_creation"}


@dataclass(frozen=True)
class _History:
    packages: tuple[
        tuple[ProjectDirectorMessage, ProjectDirectorNextTaskInstructionPackage],
        ...,
    ]
    roots: tuple[
        tuple[ProjectDirectorMessage, ProjectDirectorCrossTaskContinuationRoot],
        ...,
    ]
    exact_run_reservations: tuple[
        tuple[ProjectDirectorMessage, ProjectDirectorCrossTaskExactRunReservation],
        ...,
    ]
    worker_start_reservations: tuple[
        tuple[
            ProjectDirectorMessage,
            ProjectDirectorCrossTaskExactWorkerStartReservation,
        ],
        ...,
    ]


class _Blocked(Exception):
    def __init__(
        self,
        reason: CrossTaskExactWorkerStartReservationBlockedReason,
    ) -> None:
        self.reason = reason
        super().__init__(reason)


class ProjectDirectorCrossTaskExactWorkerStartReservationService:
    """Persist or replay one exact future Worker-start authority."""

    def __init__(
        self,
        *,
        message_repository: ProjectDirectorMessageRepository,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        agent_session_repository: AgentSessionRepository,
    ) -> None:
        self._message_repository = message_repository
        self._task_repository = task_repository
        self._run_repository = run_repository
        self._agent_session_repository = agent_session_repository
        self._require_shared_session()

    def reserve_exact_worker_start(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        continuation_root_record_id: UUID,
        instruction_package_id: UUID,
        exact_run_reservation_id: UUID,
    ) -> ProjectDirectorCrossTaskExactWorkerStartReservationResult:
        """Reserve, replay, or fail closed for the exact E1B identity."""

        self._require_shared_session()
        try:
            with self._message_repository.sqlite_immediate_transaction():
                result = self._reserve_in_transaction(
                    session_id=session_id,
                    project_id=project_id,
                    continuation_root_record_id=continuation_root_record_id,
                    instruction_package_id=instruction_package_id,
                    exact_run_reservation_id=exact_run_reservation_id,
                )
            return result
        except _Blocked as exc:
            return self._blocked_result(exc.reason)
        except (SQLAlchemyError, ValidationError, TypeError, ValueError):
            return self._blocked_result(
                "exact_worker_start_reservation_persistence_failed"
            )

    def _reserve_in_transaction(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        continuation_root_record_id: UUID,
        instruction_package_id: UUID,
        exact_run_reservation_id: UUID,
    ) -> ProjectDirectorCrossTaskExactWorkerStartReservationResult:
        history = self._load_history(
            session_id=session_id,
            instruction_package_id=instruction_package_id,
            exact_run_reservation_id=exact_run_reservation_id,
        )
        root, package, exact_run_reservation = self._locate_exact_graph(
            history=history,
            session_id=session_id,
            project_id=project_id,
            continuation_root_record_id=continuation_root_record_id,
            instruction_package_id=instruction_package_id,
            exact_run_reservation_id=exact_run_reservation_id,
        )
        replay_key = (
            ProjectDirectorCrossTaskExactWorkerStartReservation
            .compute_worker_start_reservation_replay_key(
                continuation_id=root.continuation_id,
                exact_run_reservation_id=(
                    exact_run_reservation.exact_run_reservation_id
                ),
                instruction_package_id=package.package_id,
                next_task_id=exact_run_reservation.next_task_id,
                exact_run_id=exact_run_reservation.exact_run_id,
            )
        )
        replay_matches = [
            item
            for item in history.worker_start_reservations
            if item[1].worker_start_reservation_replay_key == replay_key
        ]
        if replay_matches:
            message, reservation = replay_matches[0]
            return self._replay_existing_reservation(
                message=message,
                reservation=reservation,
                root=root,
                package=package,
                exact_run_reservation=exact_run_reservation,
            )

        if any(
            reservation.exact_run_reservation_id
            == exact_run_reservation.exact_run_reservation_id
            or reservation.exact_run_id == exact_run_reservation.exact_run_id
            for _, reservation in history.worker_start_reservations
        ):
            raise _Blocked("exact_worker_start_reservation_replay_conflict")

        task = self._load_exact_task(exact_run_reservation.next_task_id)
        self._validate_task(
            task=task,
            package=package,
            exact_run_reservation=exact_run_reservation,
        )
        run = self._load_exact_run(exact_run_reservation.exact_run_id)
        self._validate_run(
            run=run,
            package=package,
            exact_run_reservation=exact_run_reservation,
        )
        self._validate_active_run_set(
            next_task_id=exact_run_reservation.next_task_id,
            exact_run_id=exact_run_reservation.exact_run_id,
        )
        self._validate_no_active_agent_session(
            exact_run_reservation.next_task_id
        )

        reservation = self._build_reservation(
            root=root,
            package=package,
            exact_run_reservation=exact_run_reservation,
            task_human_status=task.human_status.value,
            exact_run_started_at=run.started_at,
            exact_run_created_at=run.created_at,
            exact_worker_start_reservation_id=uuid4(),
            created_at=utc_now(),
        )
        message = self._build_reservation_message(
            reservation=reservation,
            sequence_no=self._message_repository.get_next_sequence_no(
                session_id=session_id
            ),
        )
        persisted_message = self._create_message(message)
        self._post_write_validate(persisted_message, reservation)
        return ProjectDirectorCrossTaskExactWorkerStartReservationResult(
            status="worker_start_reserved",
            reservation=reservation,
            blocked_reasons=(),
            worker_start_reserved=True,
            worker_called=False,
            product_runtime_git_write_allowed=False,
        )

    def _replay_existing_reservation(
        self,
        *,
        message: ProjectDirectorMessage,
        reservation: ProjectDirectorCrossTaskExactWorkerStartReservation,
        root: ProjectDirectorCrossTaskContinuationRoot,
        package: ProjectDirectorNextTaskInstructionPackage,
        exact_run_reservation: ProjectDirectorCrossTaskExactRunReservation,
    ) -> ProjectDirectorCrossTaskExactWorkerStartReservationResult:
        expected = self._build_reservation(
            root=root,
            package=package,
            exact_run_reservation=exact_run_reservation,
            task_human_status=exact_run_reservation.task_human_status,
            exact_run_started_at=exact_run_reservation.exact_run_started_at,
            exact_run_created_at=exact_run_reservation.exact_run_created_at,
            exact_worker_start_reservation_id=(
                reservation.exact_worker_start_reservation_id
            ),
            created_at=reservation.created_at,
            reason="exact_worker_start_reservation_replay_conflict",
        )
        if reservation != expected:
            raise _Blocked("exact_worker_start_reservation_replay_conflict")
        self._validate_worker_start_message_binding(
            message,
            reservation,
            reason="exact_worker_start_reservation_replay_conflict",
        )
        return ProjectDirectorCrossTaskExactWorkerStartReservationResult(
            status="worker_start_replayed",
            reservation=reservation,
            blocked_reasons=(),
            worker_start_reserved=True,
            worker_called=False,
            product_runtime_git_write_allowed=False,
        )

    def _load_history(
        self,
        *,
        session_id: UUID,
        instruction_package_id: UUID,
        exact_run_reservation_id: UUID,
    ) -> _History:
        try:
            messages = self._iter_session_messages(session_id)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(
                "exact_worker_start_reservation_history_invalid"
            ) from exc

        packages: list[
            tuple[ProjectDirectorMessage, ProjectDirectorNextTaskInstructionPackage]
        ] = []
        roots: list[
            tuple[ProjectDirectorMessage, ProjectDirectorCrossTaskContinuationRoot]
        ] = []
        exact_run_reservations: list[
            tuple[ProjectDirectorMessage, ProjectDirectorCrossTaskExactRunReservation]
        ] = []
        worker_start_reservations: list[
            tuple[
                ProjectDirectorMessage,
                ProjectDirectorCrossTaskExactWorkerStartReservation,
            ]
        ] = []
        for message in messages:
            family_flags = (
                self._is_package_family(message),
                self._is_root_family(message),
                self._is_exact_run_reservation_family(message),
                self._is_worker_start_reservation_family(message),
            )
            if sum(family_flags) > 1:
                raise _Blocked(
                    "exact_worker_start_reservation_history_invalid"
                )
            if family_flags[0]:
                reason: CrossTaskExactWorkerStartReservationBlockedReason = (
                    "exact_worker_start_reservation_instruction_package_invalid"
                    if self._raw_action_id_matches(
                        message,
                        "package_id",
                        instruction_package_id,
                    )
                    else "exact_worker_start_reservation_history_invalid"
                )
                packages.append(
                    (message, self._parse_package_message(message, reason=reason))
                )
            elif family_flags[1]:
                roots.append((message, self._parse_root_message(message)))
            elif family_flags[2]:
                reason = (
                    "exact_worker_start_reservation_exact_run_reservation_invalid"
                    if self._raw_action_id_matches(
                        message,
                        "exact_run_reservation_id",
                        exact_run_reservation_id,
                    )
                    else "exact_worker_start_reservation_history_invalid"
                )
                exact_run_reservations.append(
                    (
                        message,
                        self._parse_exact_run_reservation_message(
                            message,
                            reason=reason,
                        ),
                    )
                )
            elif family_flags[3]:
                reason = (
                    "exact_worker_start_reservation_replay_conflict"
                    if self._raw_action_id_matches(
                        message,
                        "exact_run_reservation_id",
                        exact_run_reservation_id,
                    )
                    else "exact_worker_start_reservation_history_invalid"
                )
                worker_start_reservations.append(
                    (
                        message,
                        self._parse_worker_start_reservation_message(
                            message,
                            reason=reason,
                        ),
                    )
                )

        history = _History(
            packages=tuple(packages),
            roots=tuple(roots),
            exact_run_reservations=tuple(exact_run_reservations),
            worker_start_reservations=tuple(worker_start_reservations),
        )
        self._validate_history_graph(
            history,
            exact_run_reservation_id=exact_run_reservation_id,
        )
        return history

    def _iter_session_messages(
        self,
        session_id: UUID,
    ) -> list[ProjectDirectorMessage]:
        messages: list[ProjectDirectorMessage] = []
        before_message_id: UUID | None = None
        seen_cursors: set[UUID] = set()
        while True:
            page, has_more = self._message_repository.list_by_session_id(
                session_id=session_id,
                limit=_PAGE_SIZE,
                before_message_id=before_message_id,
            )
            messages.extend(page)
            if not has_more:
                break
            if not page:
                raise ValueError("Worker-start reservation history page is empty")
            next_cursor = page[0].id
            if next_cursor == before_message_id or next_cursor in seen_cursors:
                raise ValueError("Worker-start reservation history cursor stalled")
            seen_cursors.add(next_cursor)
            before_message_id = next_cursor

        ordered = sorted(messages, key=lambda item: item.sequence_no)
        message_ids = [message.id for message in ordered]
        sequence_numbers = [message.sequence_no for message in ordered]
        if (
            len(message_ids) != len(set(message_ids))
            or len(sequence_numbers) != len(set(sequence_numbers))
        ):
            raise ValueError("Worker-start reservation sequence history is invalid")
        return ordered

    @staticmethod
    def _is_package_family(message: ProjectDirectorMessage) -> bool:
        return (
            message.intent == _PACKAGE_INTENT
            or message.source_detail == _PACKAGE_SOURCE_DETAIL
            or ProjectDirectorCrossTaskExactWorkerStartReservationService
            ._has_action_type(message, _PACKAGE_ACTION_TYPE)
        )

    @staticmethod
    def _is_root_family(message: ProjectDirectorMessage) -> bool:
        return (
            message.intent == _ROOT_INTENT
            or message.source_detail == _ROOT_SOURCE_DETAIL
            or ProjectDirectorCrossTaskExactWorkerStartReservationService
            ._has_action_type(message, _ROOT_ACTION_TYPE)
        )

    @staticmethod
    def _is_exact_run_reservation_family(
        message: ProjectDirectorMessage,
    ) -> bool:
        return (
            message.intent == CROSS_TASK_EXACT_RUN_RESERVATION_INTENT
            or message.source_detail
            == CROSS_TASK_EXACT_RUN_RESERVATION_SOURCE_DETAIL
            or ProjectDirectorCrossTaskExactWorkerStartReservationService
            ._has_action_type(
                message,
                CROSS_TASK_EXACT_RUN_RESERVATION_ACTION_TYPE,
            )
        )

    @staticmethod
    def _is_worker_start_reservation_family(
        message: ProjectDirectorMessage,
    ) -> bool:
        return (
            message.intent == CROSS_TASK_EXACT_WORKER_START_RESERVATION_INTENT
            or message.source_detail
            == CROSS_TASK_EXACT_WORKER_START_RESERVATION_SOURCE_DETAIL
            or ProjectDirectorCrossTaskExactWorkerStartReservationService
            ._has_action_type(
                message,
                CROSS_TASK_EXACT_WORKER_START_RESERVATION_ACTION_TYPE,
            )
        )

    @staticmethod
    def _has_action_type(message: ProjectDirectorMessage, action_type: str) -> bool:
        return any(
            isinstance(action, dict) and action.get("type") == action_type
            for action in message.suggested_actions
        )

    @staticmethod
    def _raw_action_id_matches(
        message: ProjectDirectorMessage,
        field_name: str,
        expected: UUID,
    ) -> bool:
        return (
            len(message.suggested_actions) == 1
            and isinstance(message.suggested_actions[0], dict)
            and str(message.suggested_actions[0].get(field_name))
            == str(expected)
        )

    def _parse_package_message(
        self,
        message: ProjectDirectorMessage,
        *,
        reason: CrossTaskExactWorkerStartReservationBlockedReason = (
            "exact_worker_start_reservation_history_invalid"
        ),
    ) -> ProjectDirectorNextTaskInstructionPackage:
        action = self._strict_action(
            message,
            intent=_PACKAGE_INTENT,
            source_detail=_PACKAGE_SOURCE_DETAIL,
            action_type=_PACKAGE_ACTION_TYPE,
            schema_version=NEXT_TASK_INSTRUCTION_PACKAGE_SCHEMA_VERSION,
            reason=reason,
        )
        payload = dict(action)
        payload.pop("type", None)
        try:
            package = ProjectDirectorNextTaskInstructionPackage.model_validate(
                payload
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(reason) from exc
        if (
            package.package_replay_key
            != package.compute_package_replay_key(
                continuation_id=package.continuation_id,
                source_completion_evidence_id=(
                    package.source_completion_evidence_id
                ),
                next_task_id=package.next_task_id,
            )
            or package.package_fingerprint != package.compute_fingerprint()
        ):
            raise _Blocked(reason)
        self._validate_package_message_binding(
            message,
            package,
            action=action,
            reason=reason,
        )
        return package

    def _parse_root_message(
        self,
        message: ProjectDirectorMessage,
        *,
        reason: CrossTaskExactWorkerStartReservationBlockedReason = (
            "exact_worker_start_reservation_history_invalid"
        ),
    ) -> ProjectDirectorCrossTaskContinuationRoot:
        action = self._strict_action(
            message,
            intent=_ROOT_INTENT,
            source_detail=_ROOT_SOURCE_DETAIL,
            action_type=_ROOT_ACTION_TYPE,
            schema_version=CROSS_TASK_CONTINUATION_SCHEMA_VERSION,
            reason=reason,
        )
        payload = dict(action)
        payload.pop("type", None)
        try:
            root = ProjectDirectorCrossTaskContinuationRoot.model_validate(payload)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(reason) from exc
        if (
            root.idempotency_key
            != root.compute_idempotency_key(
                session_id=root.session_id,
                project_id=root.project_id,
                plan_version_id=root.plan_version_id,
                task_creation_record_id=root.task_creation_record_id,
                source_task_id=root.source_task_id,
                source_run_id=root.source_run_id,
                source_completion_evidence_id=(
                    root.source_completion_evidence_id
                ),
            )
            or root.continuation_fingerprint != root.compute_fingerprint()
        ):
            raise _Blocked(reason)
        self._validate_root_message_binding(
            message,
            root,
            action=action,
            reason=reason,
        )
        return root

    def _parse_exact_run_reservation_message(
        self,
        message: ProjectDirectorMessage,
        *,
        reason: CrossTaskExactWorkerStartReservationBlockedReason,
    ) -> ProjectDirectorCrossTaskExactRunReservation:
        action = self._strict_action(
            message,
            intent=CROSS_TASK_EXACT_RUN_RESERVATION_INTENT,
            source_detail=CROSS_TASK_EXACT_RUN_RESERVATION_SOURCE_DETAIL,
            action_type=CROSS_TASK_EXACT_RUN_RESERVATION_ACTION_TYPE,
            schema_version=CROSS_TASK_EXACT_RUN_RESERVATION_SCHEMA_VERSION,
            reason=reason,
        )
        payload = dict(action)
        payload.pop("type", None)
        try:
            reservation = ProjectDirectorCrossTaskExactRunReservation.model_validate(
                payload
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(reason) from exc
        if (
            reservation.reservation_replay_key
            != reservation.compute_reservation_replay_key(
                continuation_id=reservation.continuation_id,
                continuation_root_record_id=(
                    reservation.continuation_root_record_id
                ),
                instruction_package_id=reservation.instruction_package_id,
                next_task_id=reservation.next_task_id,
            )
            or reservation.reservation_fingerprint
            != reservation.compute_fingerprint()
        ):
            raise _Blocked(reason)
        self._validate_exact_run_message_binding(
            message,
            reservation,
            action=action,
            reason=reason,
        )
        return reservation

    def _parse_worker_start_reservation_message(
        self,
        message: ProjectDirectorMessage,
        *,
        reason: CrossTaskExactWorkerStartReservationBlockedReason,
    ) -> ProjectDirectorCrossTaskExactWorkerStartReservation:
        action = self._strict_action(
            message,
            intent=CROSS_TASK_EXACT_WORKER_START_RESERVATION_INTENT,
            source_detail=CROSS_TASK_EXACT_WORKER_START_RESERVATION_SOURCE_DETAIL,
            action_type=CROSS_TASK_EXACT_WORKER_START_RESERVATION_ACTION_TYPE,
            schema_version=(
                CROSS_TASK_EXACT_WORKER_START_RESERVATION_SCHEMA_VERSION
            ),
            reason=reason,
        )
        payload = dict(action)
        payload.pop("type", None)
        try:
            reservation = (
                ProjectDirectorCrossTaskExactWorkerStartReservation.model_validate(
                    payload
                )
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(reason) from exc
        if (
            reservation.worker_start_reservation_replay_key
            != reservation.compute_worker_start_reservation_replay_key(
                continuation_id=reservation.continuation_id,
                exact_run_reservation_id=reservation.exact_run_reservation_id,
                instruction_package_id=reservation.instruction_package_id,
                next_task_id=reservation.next_task_id,
                exact_run_id=reservation.exact_run_id,
            )
            or reservation.worker_start_reservation_fingerprint
            != reservation.compute_fingerprint()
        ):
            raise _Blocked(reason)
        self._validate_worker_start_message_binding(
            message,
            reservation,
            action=action,
            reason=reason,
        )
        return reservation

    @staticmethod
    def _strict_action(
        message: ProjectDirectorMessage,
        *,
        intent: str,
        source_detail: str,
        action_type: str,
        schema_version: str,
        reason: CrossTaskExactWorkerStartReservationBlockedReason,
    ) -> dict[str, Any]:
        if (
            message.role != ProjectDirectorMessageRole.ASSISTANT
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent != intent
            or message.source_detail != source_detail
            or message.requires_confirmation is not False
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
            or message.token_count is not None
            or message.estimated_cost is not None
            or len(message.suggested_actions) != 1
            or not isinstance(message.suggested_actions[0], dict)
        ):
            raise _Blocked(reason)
        action = message.suggested_actions[0]
        if (
            action.get("type") != action_type
            or action.get("schema_version") != schema_version
        ):
            raise _Blocked(reason)
        return action

    @staticmethod
    def _expected_action(action_type: str, model: Any) -> dict[str, Any]:
        return {
            "type": action_type,
            **model.model_dump(mode="json"),
        }

    @classmethod
    def _validate_package_message_binding(
        cls,
        message: ProjectDirectorMessage,
        package: ProjectDirectorNextTaskInstructionPackage,
        *,
        action: dict[str, Any],
        reason: CrossTaskExactWorkerStartReservationBlockedReason,
    ) -> None:
        if (
            action != cls._expected_action(_PACKAGE_ACTION_TYPE, package)
            or message.id != package.package_id
            or message.content
            != f"P24 next Task instruction package: {package.package_id}"
            or message.session_id != package.session_id
            or message.related_plan_version_id != package.plan_version_id
            or message.related_project_id != package.project_id
            or message.related_task_id != package.next_task_id
            or message.created_at != package.created_at
            or message.forbidden_actions_detected
            != list(package.forbidden_actions)
        ):
            raise _Blocked(reason)

    @classmethod
    def _validate_root_message_binding(
        cls,
        message: ProjectDirectorMessage,
        root: ProjectDirectorCrossTaskContinuationRoot,
        *,
        action: dict[str, Any],
        reason: CrossTaskExactWorkerStartReservationBlockedReason,
    ) -> None:
        related_task_id = (
            root.next_task_id
            if root.status == "prepared"
            else root.source_task_id
        )
        if (
            action != cls._expected_action(_ROOT_ACTION_TYPE, root)
            or message.id != root.record_id
            or message.content
            != f"P24 cross-Task continuation root: {root.record_id}"
            or message.session_id != root.session_id
            or message.related_plan_version_id != root.plan_version_id
            or message.related_project_id != root.project_id
            or message.related_task_id != related_task_id
            or message.created_at != root.created_at
            or message.forbidden_actions_detected != list(root.forbidden_actions)
        ):
            raise _Blocked(reason)

    @classmethod
    def _validate_exact_run_message_binding(
        cls,
        message: ProjectDirectorMessage,
        reservation: ProjectDirectorCrossTaskExactRunReservation,
        *,
        action: dict[str, Any],
        reason: CrossTaskExactWorkerStartReservationBlockedReason,
    ) -> None:
        if (
            action
            != cls._expected_action(
                CROSS_TASK_EXACT_RUN_RESERVATION_ACTION_TYPE,
                reservation,
            )
            or message.id != reservation.exact_run_reservation_id
            or message.content
            != (
                f"{_E1B_CONTENT_PREFIX}: "
                f"{reservation.exact_run_reservation_id}"
            )
            or message.session_id != reservation.session_id
            or message.related_plan_version_id != reservation.plan_version_id
            or message.related_project_id != reservation.project_id
            or message.related_task_id != reservation.next_task_id
            or message.created_at != reservation.created_at
            or message.forbidden_actions_detected
            != list(reservation.forbidden_actions)
        ):
            raise _Blocked(reason)

    @classmethod
    def _validate_worker_start_message_binding(
        cls,
        message: ProjectDirectorMessage,
        reservation: ProjectDirectorCrossTaskExactWorkerStartReservation,
        *,
        action: dict[str, Any] | None = None,
        reason: CrossTaskExactWorkerStartReservationBlockedReason,
    ) -> None:
        expected_action = cls._expected_action(
            CROSS_TASK_EXACT_WORKER_START_RESERVATION_ACTION_TYPE,
            reservation,
        )
        if (
            (action if action is not None else message.suggested_actions[0])
            != expected_action
            or message.id != reservation.exact_worker_start_reservation_id
            or message.content
            != (
                f"{_E2A_CONTENT_PREFIX}: "
                f"{reservation.exact_worker_start_reservation_id}"
            )
            or message.session_id != reservation.session_id
            or message.related_plan_version_id != reservation.plan_version_id
            or message.related_project_id != reservation.project_id
            or message.related_task_id != reservation.next_task_id
            or message.created_at != reservation.created_at
            or message.forbidden_actions_detected
            != list(reservation.forbidden_actions)
        ):
            raise _Blocked(reason)

    def _validate_history_graph(
        self,
        history: _History,
        *,
        exact_run_reservation_id: UUID,
    ) -> None:
        packages = [item[1] for item in history.packages]
        roots = [item[1] for item in history.roots]
        exact_run_reservations = [
            item[1] for item in history.exact_run_reservations
        ]
        worker_start_reservations = [
            item[1] for item in history.worker_start_reservations
        ]
        self._require_unique(
            [package.package_id for package in packages],
            [package.package_replay_key for package in packages],
            [package.continuation_id for package in packages],
        )
        self._require_unique(
            [root.record_id for root in roots],
            [root.continuation_id for root in roots],
            [root.idempotency_key for root in roots],
            [self._root_source_identity(root) for root in roots],
        )
        self._require_unique(
            [item.exact_run_reservation_id for item in exact_run_reservations],
            [item.reservation_replay_key for item in exact_run_reservations],
            [item.exact_run_id for item in exact_run_reservations],
            [
                (
                    item.continuation_root_record_id,
                    item.instruction_package_id,
                    item.next_task_id,
                )
                for item in exact_run_reservations
            ],
        )
        self._require_unique(
            [
                item.exact_worker_start_reservation_id
                for item in worker_start_reservations
            ],
            [
                item.worker_start_reservation_replay_key
                for item in worker_start_reservations
            ],
            [
                item.exact_run_reservation_id
                for item in worker_start_reservations
            ],
            [item.exact_run_id for item in worker_start_reservations],
        )

        for root_message, root in history.roots:
            if root.status == "prepared":
                matches = [
                    item
                    for item in history.packages
                    if item[1].package_id == root.instruction_package_id
                ]
                if len(matches) != 1:
                    raise _Blocked(
                        "exact_worker_start_reservation_history_conflict"
                    )
                package_message, package = matches[0]
                self._validate_root_package_binding(root, package)
                if package_message.sequence_no + 1 != root_message.sequence_no:
                    raise _Blocked(
                        "exact_worker_start_reservation_history_conflict"
                    )
            elif any(
                package.continuation_id == root.continuation_id
                or self._package_source_identity(package)
                == self._root_source_identity(root)
                for package in packages
            ):
                raise _Blocked(
                    "exact_worker_start_reservation_history_conflict"
                )

        for package in packages:
            matches = [
                root
                for root in roots
                if root.status == "prepared"
                and root.instruction_package_id == package.package_id
            ]
            if len(matches) != 1:
                raise _Blocked(
                    "exact_worker_start_reservation_history_conflict"
                )

        for exact_run_reservation in exact_run_reservations:
            root_matches = [
                root
                for root in roots
                if root.record_id
                == exact_run_reservation.continuation_root_record_id
            ]
            package_matches = [
                package
                for package in packages
                if package.package_id
                == exact_run_reservation.instruction_package_id
            ]
            if len(root_matches) != 1 or len(package_matches) != 1:
                raise _Blocked(
                    "exact_worker_start_reservation_history_conflict"
                )
            reason: CrossTaskExactWorkerStartReservationBlockedReason = (
                "exact_worker_start_reservation_exact_run_reservation_invalid"
                if exact_run_reservation.exact_run_reservation_id
                == exact_run_reservation_id
                else "exact_worker_start_reservation_history_conflict"
            )
            self._validate_exact_run_history_binding(
                exact_run_reservation,
                root_matches[0],
                package_matches[0],
                reason=reason,
            )

        for worker_start_reservation in worker_start_reservations:
            root_matches = [
                root
                for root in roots
                if root.record_id
                == worker_start_reservation.continuation_root_record_id
            ]
            package_matches = [
                package
                for package in packages
                if package.package_id
                == worker_start_reservation.instruction_package_id
            ]
            exact_run_matches = [
                item
                for item in exact_run_reservations
                if item.exact_run_reservation_id
                == worker_start_reservation.exact_run_reservation_id
            ]
            if (
                len(root_matches) != 1
                or len(package_matches) != 1
                or len(exact_run_matches) != 1
            ):
                raise _Blocked(
                    "exact_worker_start_reservation_history_conflict"
                )
            reason = (
                "exact_worker_start_reservation_replay_conflict"
                if worker_start_reservation.exact_run_reservation_id
                == exact_run_reservation_id
                else "exact_worker_start_reservation_history_conflict"
            )
            self._validate_worker_start_history_binding(
                worker_start_reservation,
                root_matches[0],
                package_matches[0],
                exact_run_matches[0],
                reason=reason,
            )

    @staticmethod
    def _require_unique(*collections: list[Any]) -> None:
        if any(len(values) != len(set(values)) for values in collections):
            raise _Blocked("exact_worker_start_reservation_history_conflict")

    @staticmethod
    def _validate_root_package_binding(
        root: ProjectDirectorCrossTaskContinuationRoot,
        package: ProjectDirectorNextTaskInstructionPackage,
        *,
        reason: CrossTaskExactWorkerStartReservationBlockedReason = (
            "exact_worker_start_reservation_history_conflict"
        ),
    ) -> None:
        if (
            root.status != "prepared"
            or root.instruction_package_id != package.package_id
            or root.instruction_package_fingerprint
            != package.package_fingerprint
            or root.instruction_candidate_fingerprint
            != package.instruction_candidate_fingerprint
            or root.continuation_id != package.continuation_id
            or root.next_task_id != package.next_task_id
            or root.session_id != package.session_id
            or root.project_id != package.project_id
            or root.plan_version_id != package.plan_version_id
            or root.task_creation_record_id != package.task_creation_record_id
            or root.source_task_id != package.source_task_id
            or root.source_run_id != package.source_run_id
            or root.source_completion_evidence_id
            != package.source_completion_evidence_id
            or root.source_completion_evidence_fingerprint
            != package.source_completion_evidence_fingerprint
            or root.created_at != package.created_at
            or root.forbidden_actions != package.forbidden_actions
        ):
            raise _Blocked(reason)

    @classmethod
    def _validate_exact_run_history_binding(
        cls,
        reservation: ProjectDirectorCrossTaskExactRunReservation,
        root: ProjectDirectorCrossTaskContinuationRoot,
        package: ProjectDirectorNextTaskInstructionPackage,
        *,
        reason: CrossTaskExactWorkerStartReservationBlockedReason,
    ) -> None:
        cls._validate_root_package_binding(root, package, reason=reason)
        strategy = package.selected_strategy
        if (
            reservation.continuation_sequence_no != 2
            or reservation.previous_record_id != root.record_id
            or reservation.replay_of_record_id is not None
            or reservation.continuation_id != root.continuation_id
            or reservation.continuation_root_record_id != root.record_id
            or reservation.continuation_root_fingerprint
            != root.continuation_fingerprint
            or reservation.continuation_idempotency_key != root.idempotency_key
            or reservation.instruction_package_id != package.package_id
            or reservation.instruction_package_fingerprint
            != package.package_fingerprint
            or reservation.instruction_candidate_fingerprint
            != package.instruction_candidate_fingerprint
            or reservation.session_id != package.session_id
            or reservation.project_id != package.project_id
            or reservation.plan_version_id != package.plan_version_id
            or reservation.task_creation_record_id
            != package.task_creation_record_id
            or reservation.source_task_id != package.source_task_id
            or reservation.source_run_id != package.source_run_id
            or reservation.source_completion_evidence_id
            != package.source_completion_evidence_id
            or reservation.source_completion_evidence_fingerprint
            != package.source_completion_evidence_fingerprint
            or reservation.next_task_id != package.next_task_id
            or reservation.next_task_index != package.next_task_index
            or reservation.task_count != package.task_count
            or reservation.task_title != package.task_title
            or reservation.task_input_summary != package.task_input_summary
            or reservation.owner_role_code != package.owner_role_code
            or reservation.priority != package.priority
            or reservation.risk_level != package.risk_level
            or reservation.depends_on_task_ids != package.depends_on_task_ids
            or reservation.run_model_name != package.selected_model.model_name
            or reservation.run_route_reason != strategy.route_reason
            or reservation.run_routing_score != strategy.routing_score
            or reservation.run_routing_score_breakdown
            != strategy.routing_score_breakdown
            or reservation.run_strategy_decision != strategy.strategy_decision
            or reservation.run_owner_role_code != strategy.owner_role_code
            or reservation.run_upstream_role_code != strategy.upstream_role_code
            or reservation.run_downstream_role_code
            != strategy.downstream_role_code
            or reservation.run_handoff_reason != strategy.handoff_reason
            or reservation.run_dispatch_status != strategy.dispatch_status
            or reservation.forbidden_actions
            != cls._exact_run_forbidden_actions(package.forbidden_actions)
        ):
            raise _Blocked(reason)

    @staticmethod
    def _exact_run_forbidden_actions(
        source_actions: tuple[str, ...],
    ) -> tuple[str, ...]:
        retained = [
            action
            for action in source_actions
            if action not in _E1B_COMPLETED_ACTIONS
        ]
        seen = set(retained)
        for action in _E1B_REQUIRED_FORBIDDEN_ACTIONS:
            if action not in seen:
                retained.append(action)
                seen.add(action)
        return tuple(retained)

    @classmethod
    def _validate_worker_start_history_binding(
        cls,
        reservation: ProjectDirectorCrossTaskExactWorkerStartReservation,
        root: ProjectDirectorCrossTaskContinuationRoot,
        package: ProjectDirectorNextTaskInstructionPackage,
        exact_run_reservation: ProjectDirectorCrossTaskExactRunReservation,
        *,
        reason: CrossTaskExactWorkerStartReservationBlockedReason,
    ) -> None:
        cls._validate_exact_run_history_binding(
            exact_run_reservation,
            root,
            package,
            reason=reason,
        )
        if (
            reservation.continuation_sequence_no != 3
            or reservation.previous_record_id
            != exact_run_reservation.exact_run_reservation_id
            or reservation.replay_of_record_id is not None
            or reservation.continuation_id != root.continuation_id
            or reservation.continuation_root_record_id != root.record_id
            or reservation.continuation_root_fingerprint
            != root.continuation_fingerprint
            or reservation.continuation_idempotency_key != root.idempotency_key
            or reservation.instruction_package_id != package.package_id
            or reservation.instruction_package_fingerprint
            != package.package_fingerprint
            or reservation.instruction_candidate_fingerprint
            != package.instruction_candidate_fingerprint
            or reservation.exact_run_reservation_id
            != exact_run_reservation.exact_run_reservation_id
            or reservation.exact_run_reservation_fingerprint
            != exact_run_reservation.reservation_fingerprint
            or reservation.exact_run_reservation_replay_key
            != exact_run_reservation.reservation_replay_key
            or reservation.session_id != package.session_id
            or reservation.project_id != package.project_id
            or reservation.plan_version_id != package.plan_version_id
            or reservation.task_creation_record_id
            != package.task_creation_record_id
            or reservation.source_task_id != package.source_task_id
            or reservation.source_run_id != package.source_run_id
            or reservation.source_completion_evidence_id
            != package.source_completion_evidence_id
            or reservation.source_completion_evidence_fingerprint
            != package.source_completion_evidence_fingerprint
            or reservation.next_task_id != exact_run_reservation.next_task_id
            or reservation.next_task_index
            != exact_run_reservation.next_task_index
            or reservation.task_count != exact_run_reservation.task_count
            or reservation.task_human_status
            != exact_run_reservation.task_human_status
            or reservation.exact_run_id != exact_run_reservation.exact_run_id
            or reservation.exact_run_started_at
            != exact_run_reservation.exact_run_started_at
            or reservation.exact_run_created_at
            != exact_run_reservation.exact_run_created_at
            or reservation.worker_model_name
            != package.selected_model.model_name
            or reservation.worker_model_tier
            != package.selected_model.model_tier
            or reservation.worker_owner_role_code != package.owner_role_code
            or reservation.worker_upstream_role_code
            != package.selected_strategy.upstream_role_code
            or reservation.worker_downstream_role_code
            != package.selected_strategy.downstream_role_code
            or reservation.worker_selected_skills != package.selected_skills
            or reservation.worker_repository_binding
            != package.repository_binding
            or reservation.worker_workspace_binding != package.workspace_binding
            or reservation.worker_allowed_paths != package.allowed_paths
            or reservation.worker_forbidden_paths != package.forbidden_paths
            or reservation.forbidden_actions
            != cls._worker_start_forbidden_actions(reason=reason)
        ):
            raise _Blocked(reason)

    def _locate_exact_graph(
        self,
        *,
        history: _History,
        session_id: UUID,
        project_id: UUID,
        continuation_root_record_id: UUID,
        instruction_package_id: UUID,
        exact_run_reservation_id: UUID,
    ) -> tuple[
        ProjectDirectorCrossTaskContinuationRoot,
        ProjectDirectorNextTaskInstructionPackage,
        ProjectDirectorCrossTaskExactRunReservation,
    ]:
        root_matches = [
            root
            for _, root in history.roots
            if root.record_id == continuation_root_record_id
        ]
        if len(root_matches) != 1:
            raise _Blocked("exact_worker_start_reservation_history_invalid")
        package_matches = [
            package
            for _, package in history.packages
            if package.package_id == instruction_package_id
        ]
        if len(package_matches) != 1:
            raise _Blocked(
                "exact_worker_start_reservation_instruction_package_invalid"
            )
        exact_run_matches = [
            reservation
            for _, reservation in history.exact_run_reservations
            if reservation.exact_run_reservation_id
            == exact_run_reservation_id
        ]
        if len(exact_run_matches) != 1:
            raise _Blocked(
                "exact_worker_start_reservation_exact_run_reservation_invalid"
            )
        root = root_matches[0]
        package = package_matches[0]
        exact_run_reservation = exact_run_matches[0]
        if (
            root.status != "prepared"
            or root.session_id != session_id
            or root.project_id != project_id
        ):
            raise _Blocked("exact_worker_start_reservation_history_invalid")
        if (
            package.session_id != session_id
            or package.project_id != project_id
            or package.human_confirmation_required is not False
        ):
            raise _Blocked(
                "exact_worker_start_reservation_instruction_package_invalid"
            )
        if (
            exact_run_reservation.session_id != session_id
            or exact_run_reservation.project_id != project_id
        ):
            raise _Blocked(
                "exact_worker_start_reservation_exact_run_reservation_invalid"
            )
        if (
            root.product_runtime_git_write_allowed is not False
            or package.product_runtime_git_write_allowed is not False
            or exact_run_reservation.product_runtime_git_write_allowed
            is not False
        ):
            raise _Blocked(
                "exact_worker_start_reservation_git_boundary_violation"
            )
        self._validate_root_package_binding(
            root,
            package,
            reason=(
                "exact_worker_start_reservation_instruction_package_invalid"
            ),
        )
        self._validate_exact_run_history_binding(
            exact_run_reservation,
            root,
            package,
            reason=(
                "exact_worker_start_reservation_exact_run_reservation_invalid"
            ),
        )
        self._validate_package_authority(package)
        return root, package, exact_run_reservation

    @classmethod
    def _validate_package_authority(
        cls,
        package: ProjectDirectorNextTaskInstructionPackage,
    ) -> None:
        strategy = package.selected_strategy
        decision = strategy.strategy_decision
        skill_codes = tuple(item.skill_code for item in package.selected_skills)
        skill_names = tuple(item.skill_name for item in package.selected_skills)
        if (
            not skill_codes
            or len(skill_codes) != len(set(skill_codes))
            or len(skill_names) != len(set(skill_names))
            or package.selected_model.model_name != decision.model_name
            or package.selected_model.model_tier != decision.model_tier
            or package.owner_role_code != strategy.owner_role_code
            or strategy.owner_role_code != decision.owner_role_code
            or skill_codes != decision.selected_skill_codes
            or skill_names != decision.selected_skill_names
            or package.repository_binding.focus_paths != package.allowed_paths
            or package.workspace_binding.project_id != package.project_id
            or package.workspace_binding.ignore_rule_summary
            != package.workspace_ignore_rule_summary
            or not package.allowed_paths
            or len(package.allowed_paths) != len(set(package.allowed_paths))
            or len(package.forbidden_paths) != len(set(package.forbidden_paths))
        ):
            raise _Blocked(
                "exact_worker_start_reservation_worker_authority_conflict"
            )
        cls._routing_inputs(
            package,
            reason="exact_worker_start_reservation_worker_authority_conflict",
        )

    def _load_exact_task(self, task_id: UUID) -> Task:
        try:
            task = self._task_repository.get_by_id(task_id)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(
                "exact_worker_start_reservation_task_identity_conflict"
            ) from exc
        if task is None:
            raise _Blocked("exact_worker_start_reservation_task_missing")
        return task

    @staticmethod
    def _validate_task(
        *,
        task: Task,
        package: ProjectDirectorNextTaskInstructionPackage,
        exact_run_reservation: ProjectDirectorCrossTaskExactRunReservation,
    ) -> None:
        if (
            task.id != package.next_task_id
            or task.id != exact_run_reservation.next_task_id
            or task.project_id != package.project_id
            or task.title != package.task_title
            or task.title != exact_run_reservation.task_title
            or task.input_summary != package.task_input_summary
            or task.input_summary != exact_run_reservation.task_input_summary
            or task.owner_role_code != package.owner_role_code
            or task.owner_role_code != exact_run_reservation.owner_role_code
            or task.priority != package.priority
            or task.priority != exact_run_reservation.priority
            or task.risk_level != package.risk_level
            or task.risk_level != exact_run_reservation.risk_level
            or tuple(task.depends_on_task_ids) != package.depends_on_task_ids
            or tuple(task.depends_on_task_ids)
            != exact_run_reservation.depends_on_task_ids
            or task.source_draft_id
            != f"pdv:{package.plan_version_id}:{package.plan_version_no}"
        ):
            raise _Blocked(
                "exact_worker_start_reservation_task_identity_conflict"
            )
        if (
            task.status != TaskStatus.RUNNING
            or task.human_status
            not in {TaskHumanStatus.NONE, TaskHumanStatus.RESOLVED}
            or task.human_status.value
            != exact_run_reservation.task_human_status
            or task.paused_reason is not None
        ):
            raise _Blocked(
                "exact_worker_start_reservation_task_state_conflict"
            )

    def _load_exact_run(self, run_id: UUID) -> Run:
        try:
            run = self._run_repository.get_by_id(run_id)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(
                "exact_worker_start_reservation_run_identity_conflict"
            ) from exc
        if run is None:
            raise _Blocked("exact_worker_start_reservation_run_missing")
        return run

    @classmethod
    def _validate_run(
        cls,
        *,
        run: Run,
        package: ProjectDirectorNextTaskInstructionPackage,
        exact_run_reservation: ProjectDirectorCrossTaskExactRunReservation,
    ) -> None:
        if (
            run.id != exact_run_reservation.exact_run_id
            or run.task_id != exact_run_reservation.next_task_id
            or run.task_id != package.next_task_id
        ):
            raise _Blocked(
                "exact_worker_start_reservation_run_identity_conflict"
            )
        if (
            run.status != RunStatus.RUNNING
            or run.started_at is None
            or run.started_at != exact_run_reservation.exact_run_started_at
            or run.created_at != exact_run_reservation.exact_run_created_at
            or run.finished_at is not None
            or run.failure_category is not None
            or run.quality_gate_passed is not None
        ):
            raise _Blocked(
                "exact_worker_start_reservation_run_state_conflict"
            )
        routing_breakdown, strategy_decision = cls._routing_inputs(
            package,
            reason="exact_worker_start_reservation_run_routing_conflict",
        )
        strategy = package.selected_strategy
        if (
            run.model_name != package.selected_model.model_name
            or run.model_name != exact_run_reservation.run_model_name
            or run.route_reason != strategy.route_reason
            or run.route_reason != exact_run_reservation.run_route_reason
            or run.routing_score != strategy.routing_score
            or run.routing_score != exact_run_reservation.run_routing_score
            or run.routing_score_breakdown != routing_breakdown
            or run.strategy_decision != strategy_decision
            or run.owner_role_code != strategy.owner_role_code
            or run.owner_role_code != exact_run_reservation.run_owner_role_code
            or run.upstream_role_code != strategy.upstream_role_code
            or run.upstream_role_code
            != exact_run_reservation.run_upstream_role_code
            or run.downstream_role_code != strategy.downstream_role_code
            or run.downstream_role_code
            != exact_run_reservation.run_downstream_role_code
            or run.handoff_reason != strategy.handoff_reason
            or run.handoff_reason != exact_run_reservation.run_handoff_reason
            or run.dispatch_status != strategy.dispatch_status
            or run.dispatch_status
            != exact_run_reservation.run_dispatch_status
        ):
            raise _Blocked(
                "exact_worker_start_reservation_run_routing_conflict"
            )

    @staticmethod
    def _routing_inputs(
        package: ProjectDirectorNextTaskInstructionPackage,
        *,
        reason: CrossTaskExactWorkerStartReservationBlockedReason,
    ) -> tuple[list[RunRoutingScoreItem], RunStrategyDecision]:
        strategy = package.selected_strategy
        decision = strategy.strategy_decision
        if (
            package.selected_model.model_name != decision.model_name
            or package.selected_model.model_tier != decision.model_tier
            or package.owner_role_code != strategy.owner_role_code
            or strategy.owner_role_code != decision.owner_role_code
            or strategy.project_stage != decision.project_stage
            or strategy.budget_pressure_level != decision.budget_pressure_level
            or strategy.budget_action != decision.budget_action
            or strategy.strategy_code != decision.strategy_code
            or strategy.strategy_summary != decision.summary
            or strategy.strategy_reasons != decision.reasons
            or not strategy.route_reason.strip()
            or not strategy.handoff_reason.strip()
            or not strategy.dispatch_status.strip()
        ):
            raise _Blocked(reason)
        try:
            return (
                [
                    RunRoutingScoreItem(
                        code=item.code,
                        label=item.label,
                        score=item.score,
                        detail=item.detail,
                    )
                    for item in strategy.routing_score_breakdown
                ],
                RunStrategyDecision(
                    version=decision.version,
                    project_stage=decision.project_stage,
                    owner_role_code=decision.owner_role_code,
                    model_tier=decision.model_tier,
                    model_name=decision.model_name,
                    selected_skill_codes=list(decision.selected_skill_codes),
                    selected_skill_names=list(decision.selected_skill_names),
                    budget_pressure_level=decision.budget_pressure_level,
                    budget_action=decision.budget_action,
                    strategy_code=decision.strategy_code,
                    summary=decision.summary,
                    role_model_policy_source=decision.role_model_policy_source,
                    role_model_policy_desired_tier=(
                        decision.role_model_policy_desired_tier
                    ),
                    role_model_policy_adjusted_tier=(
                        decision.role_model_policy_adjusted_tier
                    ),
                    role_model_policy_final_tier=(
                        decision.role_model_policy_final_tier
                    ),
                    role_model_policy_stage_override_applied=(
                        decision.role_model_policy_stage_override_applied
                    ),
                    rule_codes=list(decision.rule_codes),
                    reasons=[
                        RunStrategyReasonItem(
                            code=item.code,
                            label=item.label,
                            detail=item.detail,
                            score=item.score,
                        )
                        for item in decision.reasons
                    ],
                ),
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(reason) from exc

    def _validate_active_run_set(
        self,
        *,
        next_task_id: UUID,
        exact_run_id: UUID,
    ) -> None:
        try:
            runs = self._run_repository.list_by_task_id(next_task_id)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(
                "exact_worker_start_reservation_run_state_conflict"
            ) from exc
        active_run_ids = {
            run.id
            for run in runs
            if run.status in {RunStatus.QUEUED, RunStatus.RUNNING}
        }
        if active_run_ids != {exact_run_id}:
            raise _Blocked(
                "exact_worker_start_reservation_run_state_conflict"
            )

    def _validate_no_active_agent_session(self, next_task_id: UUID) -> None:
        try:
            sessions = self._agent_session_repository.list_by_task_id(
                next_task_id
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(
                "exact_worker_start_reservation_agent_session_conflict"
            ) from exc
        if any(
            session.status
            in {AgentSessionStatus.RUNNING, AgentSessionStatus.REVIEW_REWORK}
            for session in sessions
        ):
            raise _Blocked(
                "exact_worker_start_reservation_agent_session_conflict"
            )

    @classmethod
    def _build_reservation(
        cls,
        *,
        root: ProjectDirectorCrossTaskContinuationRoot,
        package: ProjectDirectorNextTaskInstructionPackage,
        exact_run_reservation: ProjectDirectorCrossTaskExactRunReservation,
        task_human_status: Literal["none", "resolved"],
        exact_run_started_at: datetime | None,
        exact_run_created_at: datetime,
        exact_worker_start_reservation_id: UUID,
        created_at: datetime,
        reason: CrossTaskExactWorkerStartReservationBlockedReason = (
            "exact_worker_start_reservation_persistence_failed"
        ),
    ) -> ProjectDirectorCrossTaskExactWorkerStartReservation:
        if exact_run_started_at is None:
            raise _Blocked(reason)
        payload: dict[str, Any] = {
            "schema_version": (
                CROSS_TASK_EXACT_WORKER_START_RESERVATION_SCHEMA_VERSION
            ),
            "exact_worker_start_reservation_id": (
                exact_worker_start_reservation_id
            ),
            "worker_start_reservation_replay_key": (
                ProjectDirectorCrossTaskExactWorkerStartReservation
                .compute_worker_start_reservation_replay_key(
                    continuation_id=root.continuation_id,
                    exact_run_reservation_id=(
                        exact_run_reservation.exact_run_reservation_id
                    ),
                    instruction_package_id=package.package_id,
                    next_task_id=exact_run_reservation.next_task_id,
                    exact_run_id=exact_run_reservation.exact_run_id,
                )
            ),
            "created_at": created_at,
            "continuation_id": root.continuation_id,
            "continuation_root_record_id": root.record_id,
            "continuation_root_fingerprint": root.continuation_fingerprint,
            "continuation_idempotency_key": root.idempotency_key,
            "instruction_package_id": package.package_id,
            "instruction_package_fingerprint": package.package_fingerprint,
            "instruction_candidate_fingerprint": (
                package.instruction_candidate_fingerprint
            ),
            "exact_run_reservation_id": (
                exact_run_reservation.exact_run_reservation_id
            ),
            "exact_run_reservation_fingerprint": (
                exact_run_reservation.reservation_fingerprint
            ),
            "exact_run_reservation_replay_key": (
                exact_run_reservation.reservation_replay_key
            ),
            "continuation_sequence_no": 3,
            "previous_record_id": (
                exact_run_reservation.exact_run_reservation_id
            ),
            "replay_of_record_id": None,
            "action": "reserve_exact_worker_start",
            "status": "worker_start_reserved",
            "session_id": package.session_id,
            "project_id": package.project_id,
            "plan_version_id": package.plan_version_id,
            "task_creation_record_id": package.task_creation_record_id,
            "source_task_id": package.source_task_id,
            "source_run_id": package.source_run_id,
            "source_completion_evidence_id": (
                package.source_completion_evidence_id
            ),
            "source_completion_evidence_fingerprint": (
                package.source_completion_evidence_fingerprint
            ),
            "next_task_id": exact_run_reservation.next_task_id,
            "next_task_index": exact_run_reservation.next_task_index,
            "task_count": exact_run_reservation.task_count,
            "task_status": "running",
            "task_human_status": task_human_status,
            "task_paused_reason_absent": True,
            "exact_run_id": exact_run_reservation.exact_run_id,
            "exact_run_status": "running",
            "exact_run_started_at": exact_run_started_at,
            "exact_run_created_at": exact_run_created_at,
            "exact_run_finished_at": None,
            "exact_run_failure_category": None,
            "exact_run_quality_gate_passed": None,
            "worker_model_name": package.selected_model.model_name,
            "worker_model_tier": package.selected_model.model_tier,
            "worker_owner_role_code": package.owner_role_code,
            "worker_upstream_role_code": (
                package.selected_strategy.upstream_role_code
            ),
            "worker_downstream_role_code": (
                package.selected_strategy.downstream_role_code
            ),
            "worker_selected_skills": package.selected_skills,
            "worker_repository_binding": package.repository_binding,
            "worker_workspace_binding": package.workspace_binding,
            "worker_allowed_paths": package.allowed_paths,
            "worker_forbidden_paths": package.forbidden_paths,
            "task_claimed": True,
            "run_created": True,
            "worker_start_reserved": True,
            "worker_called": False,
            "agent_session_created": False,
            "invocation_claim_created": False,
            "worker_outcome_recorded": False,
            "runtime_started": False,
            "task_status_mutated_by_worker_start": False,
            "run_status_mutated_by_worker_start": False,
            "product_runtime_git_write_allowed": False,
            "active_agent_session_ids_before": (),
            "forbidden_actions": cls._worker_start_forbidden_actions(
                reason=reason
            ),
        }
        try:
            fingerprint = compute_p24_contract_sha256(payload)
            return ProjectDirectorCrossTaskExactWorkerStartReservation(
                **payload,
                worker_start_reservation_fingerprint=fingerprint,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(reason) from exc

    @staticmethod
    def _worker_start_forbidden_actions(
        *,
        reason: CrossTaskExactWorkerStartReservationBlockedReason,
    ) -> tuple[str, ...]:
        default = (
            ProjectDirectorCrossTaskExactWorkerStartReservation
            .model_fields["forbidden_actions"]
            .default
        )
        if not isinstance(default, tuple):
            raise _Blocked(reason)
        return default

    @staticmethod
    def _build_reservation_message(
        *,
        reservation: ProjectDirectorCrossTaskExactWorkerStartReservation,
        sequence_no: int,
    ) -> ProjectDirectorMessage:
        try:
            return ProjectDirectorMessage(
                id=reservation.exact_worker_start_reservation_id,
                session_id=reservation.session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    f"{_E2A_CONTENT_PREFIX}: "
                    f"{reservation.exact_worker_start_reservation_id}"
                ),
                sequence_no=sequence_no,
                intent=CROSS_TASK_EXACT_WORKER_START_RESERVATION_INTENT,
                related_plan_version_id=reservation.plan_version_id,
                related_project_id=reservation.project_id,
                related_task_id=reservation.next_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=(
                    CROSS_TASK_EXACT_WORKER_START_RESERVATION_SOURCE_DETAIL
                ),
                suggested_actions=[
                    {
                        "type": (
                            CROSS_TASK_EXACT_WORKER_START_RESERVATION_ACTION_TYPE
                        ),
                        **reservation.model_dump(mode="json"),
                    }
                ],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                forbidden_actions_detected=list(reservation.forbidden_actions),
                token_count=None,
                estimated_cost=None,
                created_at=reservation.created_at,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(
                "exact_worker_start_reservation_persistence_failed"
            ) from exc

    def _create_message(
        self,
        message: ProjectDirectorMessage,
    ) -> ProjectDirectorMessage:
        try:
            return self._message_repository.create(message)
        except (SQLAlchemyError, TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(
                "exact_worker_start_reservation_persistence_failed"
            ) from exc

    def _post_write_validate(
        self,
        message: ProjectDirectorMessage,
        reservation: ProjectDirectorCrossTaskExactWorkerStartReservation,
    ) -> None:
        reason: CrossTaskExactWorkerStartReservationBlockedReason = (
            "exact_worker_start_reservation_persistence_failed"
        )
        try:
            validated = (
                ProjectDirectorCrossTaskExactWorkerStartReservation
                .model_validate(reservation.model_dump(mode="python"))
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(reason) from exc
        if (
            validated.worker_start_reservation_fingerprint
            != validated.compute_fingerprint()
            or validated.worker_start_reservation_replay_key
            != validated.compute_worker_start_reservation_replay_key(
                continuation_id=validated.continuation_id,
                exact_run_reservation_id=validated.exact_run_reservation_id,
                instruction_package_id=validated.instruction_package_id,
                next_task_id=validated.next_task_id,
                exact_run_id=validated.exact_run_id,
            )
        ):
            raise _Blocked(reason)
        parsed = self._parse_worker_start_reservation_message(
            message,
            reason=reason,
        )
        if parsed != validated:
            raise _Blocked(reason)

    @staticmethod
    def _package_source_identity(
        package: ProjectDirectorNextTaskInstructionPackage,
    ) -> tuple[UUID, ...]:
        return (
            package.session_id,
            package.project_id,
            package.plan_version_id,
            package.task_creation_record_id,
            package.source_task_id,
            package.source_run_id,
            package.source_completion_evidence_id,
        )

    @staticmethod
    def _root_source_identity(
        root: ProjectDirectorCrossTaskContinuationRoot,
    ) -> tuple[UUID, ...]:
        return (
            root.session_id,
            root.project_id,
            root.plan_version_id,
            root.task_creation_record_id,
            root.source_task_id,
            root.source_run_id,
            root.source_completion_evidence_id,
        )

    def _require_shared_session(self) -> None:
        session = self._message_repository._session
        if (
            self._task_repository.session is not session
            or self._run_repository.session is not session
            or self._agent_session_repository.session is not session
        ):
            raise ValueError(
                "P24-E2B repositories must share one SQLAlchemy session"
            )

    @staticmethod
    def _blocked_result(
        reason: CrossTaskExactWorkerStartReservationBlockedReason,
    ) -> ProjectDirectorCrossTaskExactWorkerStartReservationResult:
        return ProjectDirectorCrossTaskExactWorkerStartReservationResult(
            status="blocked",
            reservation=None,
            blocked_reasons=(reason,),
            worker_start_reserved=False,
            worker_called=False,
            product_runtime_git_write_allowed=False,
        )


__all__ = (
    "ProjectDirectorCrossTaskExactWorkerStartReservationService",
)
