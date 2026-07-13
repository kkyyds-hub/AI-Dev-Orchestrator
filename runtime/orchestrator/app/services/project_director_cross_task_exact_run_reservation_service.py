"""Atomic P24-E1B exact next-Task claim and running Run reservation."""

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
    CrossTaskExactRunReservationBlockedReason,
    ProjectDirectorCrossTaskExactRunReservation,
    ProjectDirectorCrossTaskExactRunReservationResult,
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
    RunBudgetPressureLevel,
    RunBudgetStrategyAction,
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

_RESERVATION_CONTENT_PREFIX = "P24 exact next Task Run reservation"

_RESERVATION_REQUIRED_FORBIDDEN_ACTIONS = (
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
_COMPLETED_ACTIONS = {"task_claim", "run_creation"}


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
    reservations: tuple[
        tuple[ProjectDirectorMessage, ProjectDirectorCrossTaskExactRunReservation],
        ...,
    ]


class _Blocked(Exception):
    def __init__(self, reason: CrossTaskExactRunReservationBlockedReason) -> None:
        self.reason = reason
        super().__init__(reason)


class ProjectDirectorCrossTaskExactRunReservationService:
    """Atomically claim one exact Task and record its running Run fact."""

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

    def reserve_exact_next_task_run(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        continuation_root_record_id: UUID,
        instruction_package_id: UUID,
    ) -> ProjectDirectorCrossTaskExactRunReservationResult:
        """Reserve, replay, or fail closed for one exact continuation pair."""

        self._require_shared_session()
        try:
            with self._message_repository.sqlite_immediate_transaction():
                result = self._reserve_in_transaction(
                    session_id=session_id,
                    project_id=project_id,
                    continuation_root_record_id=continuation_root_record_id,
                    instruction_package_id=instruction_package_id,
                )
            return result
        except _Blocked as exc:
            return self._blocked_result(exc.reason)
        except (SQLAlchemyError, TypeError, ValueError, ValidationError):
            return self._blocked_result(
                "exact_run_reservation_persistence_failed"
            )

    def _reserve_in_transaction(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        continuation_root_record_id: UUID,
        instruction_package_id: UUID,
    ) -> ProjectDirectorCrossTaskExactRunReservationResult:
        history = self._load_history(
            session_id=session_id,
            continuation_root_record_id=continuation_root_record_id,
            instruction_package_id=instruction_package_id,
        )
        root, package = self._locate_exact_root_and_package(
            history=history,
            session_id=session_id,
            project_id=project_id,
            continuation_root_record_id=continuation_root_record_id,
            instruction_package_id=instruction_package_id,
        )
        replay_key = (
            ProjectDirectorCrossTaskExactRunReservation
            .compute_reservation_replay_key(
                continuation_id=root.continuation_id,
                continuation_root_record_id=root.record_id,
                instruction_package_id=package.package_id,
                next_task_id=package.next_task_id,
            )
        )
        replay_matches = [
            item
            for item in history.reservations
            if item[1].reservation_replay_key == replay_key
        ]
        if replay_matches:
            message, reservation = replay_matches[0]
            return self._replay_existing_reservation(
                message=message,
                reservation=reservation,
                root=root,
                package=package,
            )

        exact_identity = (
            root.record_id,
            package.package_id,
            package.next_task_id,
        )
        if any(
            (
                reservation.continuation_root_record_id,
                reservation.instruction_package_id,
                reservation.next_task_id,
            )
            == exact_identity
            for _, reservation in history.reservations
        ):
            raise _Blocked("exact_run_reservation_replay_conflict")

        task_before = self._load_exact_task(package.next_task_id)
        self._validate_task_identity(task_before, package)
        self._validate_pending_task_state(task_before)
        self._validate_dependencies(package)
        self._validate_no_active_run(package.next_task_id)
        self._validate_no_active_agent_session(package.next_task_id)
        routing_breakdown, strategy_decision = self._routing_inputs(package)

        claimed_task = self._claim_exact_task(package.next_task_id)
        self._validate_task_identity(claimed_task, package)
        if (
            claimed_task.status != TaskStatus.RUNNING
            or claimed_task.human_status != task_before.human_status
            or claimed_task.paused_reason is not None
        ):
            raise _Blocked("exact_run_reservation_task_claim_conflict")

        run = self._create_running_run(
            package=package,
            routing_breakdown=routing_breakdown,
            strategy_decision=strategy_decision,
        )
        self._validate_persisted_run(
            run=run,
            package=package,
            routing_breakdown=routing_breakdown,
            strategy_decision=strategy_decision,
            reason="exact_run_reservation_run_creation_failed",
        )

        reservation = self._build_reservation(
            root=root,
            package=package,
            task_human_status=task_before.human_status.value,
            run=run,
            exact_run_reservation_id=uuid4(),
            created_at=utc_now(),
        )
        message = self._build_reservation_message(
            reservation,
            self._message_repository.get_next_sequence_no(
                session_id=package.session_id
            ),
        )
        self._create_message(message)
        return ProjectDirectorCrossTaskExactRunReservationResult(
            status="run_reserved",
            reservation=reservation,
            blocked_reasons=(),
            product_runtime_git_write_allowed=False,
        )

    def _replay_existing_reservation(
        self,
        *,
        message: ProjectDirectorMessage,
        reservation: ProjectDirectorCrossTaskExactRunReservation,
        root: ProjectDirectorCrossTaskContinuationRoot,
        package: ProjectDirectorNextTaskInstructionPackage,
    ) -> ProjectDirectorCrossTaskExactRunReservationResult:
        if (
            reservation.continuation_root_record_id != root.record_id
            or reservation.instruction_package_id != package.package_id
            or reservation.next_task_id != package.next_task_id
        ):
            raise _Blocked("exact_run_reservation_replay_conflict")
        task = self._load_exact_task_for_replay(package.next_task_id)
        if (
            not self._task_identity_matches(task, package)
            or task.status != TaskStatus.RUNNING
            or task.human_status.value != reservation.task_human_status
            or task.paused_reason is not None
        ):
            raise _Blocked("exact_run_reservation_replay_conflict")
        try:
            run = self._run_repository.get_by_id(reservation.exact_run_id)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("exact_run_reservation_replay_conflict") from exc
        if run is None:
            raise _Blocked("exact_run_reservation_replay_conflict")
        routing_breakdown, strategy_decision = self._routing_inputs(
            package,
            conflict_reason="exact_run_reservation_replay_conflict",
        )
        self._validate_persisted_run(
            run=run,
            package=package,
            routing_breakdown=routing_breakdown,
            strategy_decision=strategy_decision,
            reason="exact_run_reservation_replay_conflict",
        )
        expected = self._build_reservation(
            root=root,
            package=package,
            task_human_status=reservation.task_human_status,
            run=run,
            exact_run_reservation_id=reservation.exact_run_reservation_id,
            created_at=reservation.created_at,
            conflict_reason="exact_run_reservation_replay_conflict",
        )
        if reservation != expected:
            raise _Blocked("exact_run_reservation_replay_conflict")
        self._validate_reservation_message_binding(
            message,
            reservation,
            reason="exact_run_reservation_replay_conflict",
        )
        return ProjectDirectorCrossTaskExactRunReservationResult(
            status="run_replayed",
            reservation=reservation,
            blocked_reasons=(),
            product_runtime_git_write_allowed=False,
        )

    def _load_history(
        self,
        *,
        session_id: UUID,
        continuation_root_record_id: UUID,
        instruction_package_id: UUID,
    ) -> _History:
        try:
            messages = self._iter_session_messages(session_id)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("exact_run_reservation_history_invalid") from exc

        packages: list[
            tuple[ProjectDirectorMessage, ProjectDirectorNextTaskInstructionPackage]
        ] = []
        roots: list[
            tuple[ProjectDirectorMessage, ProjectDirectorCrossTaskContinuationRoot]
        ] = []
        reservations: list[
            tuple[
                ProjectDirectorMessage,
                ProjectDirectorCrossTaskExactRunReservation,
            ]
        ] = []
        for message in messages:
            family_flags = (
                self._is_package_family(message),
                self._is_root_family(message),
                self._is_reservation_family(message),
            )
            if sum(family_flags) > 1:
                raise _Blocked("exact_run_reservation_history_invalid")
            if family_flags[0]:
                packages.append((message, self._parse_package_message(message)))
            elif family_flags[1]:
                roots.append((message, self._parse_root_message(message)))
            elif family_flags[2]:
                reservations.append(
                    (
                        message,
                        self._parse_reservation_message(
                            message,
                            continuation_root_record_id=(
                                continuation_root_record_id
                            ),
                            instruction_package_id=instruction_package_id,
                        ),
                    )
                )

        history = _History(
            packages=tuple(packages),
            roots=tuple(roots),
            reservations=tuple(reservations),
        )
        for message, reservation in history.reservations:
            reason: CrossTaskExactRunReservationBlockedReason = (
                "exact_run_reservation_replay_conflict"
                if (
                    reservation.continuation_root_record_id
                    == continuation_root_record_id
                    and reservation.instruction_package_id
                    == instruction_package_id
                )
                else "exact_run_reservation_history_invalid"
            )
            self._validate_reservation_message_binding(
                message,
                reservation,
                reason=reason,
            )
        self._validate_history_graph(
            history,
            continuation_root_record_id=continuation_root_record_id,
            instruction_package_id=instruction_package_id,
        )
        return history

    def _iter_session_messages(
        self,
        session_id: UUID,
    ) -> list[ProjectDirectorMessage]:
        messages: list[ProjectDirectorMessage] = []
        before_message_id: UUID | None = None
        while True:
            page, has_more = self._message_repository.list_by_session_id(
                session_id=session_id,
                limit=_PAGE_SIZE,
                before_message_id=before_message_id,
            )
            messages.extend(page)
            if not has_more:
                return sorted(messages, key=lambda item: item.sequence_no)
            if not page:
                raise ValueError("exact Run reservation history page is empty")
            before_message_id = page[0].id

    @staticmethod
    def _is_package_family(message: ProjectDirectorMessage) -> bool:
        return (
            message.intent == _PACKAGE_INTENT
            or message.source_detail == _PACKAGE_SOURCE_DETAIL
            or ProjectDirectorCrossTaskExactRunReservationService
            ._has_action_type(message, _PACKAGE_ACTION_TYPE)
        )

    @staticmethod
    def _is_root_family(message: ProjectDirectorMessage) -> bool:
        return (
            message.intent == _ROOT_INTENT
            or message.source_detail == _ROOT_SOURCE_DETAIL
            or ProjectDirectorCrossTaskExactRunReservationService
            ._has_action_type(message, _ROOT_ACTION_TYPE)
        )

    @staticmethod
    def _is_reservation_family(message: ProjectDirectorMessage) -> bool:
        return (
            message.intent == CROSS_TASK_EXACT_RUN_RESERVATION_INTENT
            or message.source_detail
            == CROSS_TASK_EXACT_RUN_RESERVATION_SOURCE_DETAIL
            or ProjectDirectorCrossTaskExactRunReservationService
            ._has_action_type(
                message,
                CROSS_TASK_EXACT_RUN_RESERVATION_ACTION_TYPE,
            )
        )

    @staticmethod
    def _has_action_type(message: ProjectDirectorMessage, action_type: str) -> bool:
        return any(
            isinstance(action, dict) and action.get("type") == action_type
            for action in message.suggested_actions
        )

    def _parse_package_message(
        self,
        message: ProjectDirectorMessage,
    ) -> ProjectDirectorNextTaskInstructionPackage:
        action = self._strict_action(
            message,
            intent=_PACKAGE_INTENT,
            source_detail=_PACKAGE_SOURCE_DETAIL,
            action_type=_PACKAGE_ACTION_TYPE,
            schema_version=NEXT_TASK_INSTRUCTION_PACKAGE_SCHEMA_VERSION,
        )
        payload = dict(action)
        payload.pop("type", None)
        try:
            package = ProjectDirectorNextTaskInstructionPackage.model_validate(
                payload
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("exact_run_reservation_history_invalid") from exc
        if (
            message.id != package.package_id
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
            raise _Blocked("exact_run_reservation_history_invalid")
        return package

    def _parse_root_message(
        self,
        message: ProjectDirectorMessage,
    ) -> ProjectDirectorCrossTaskContinuationRoot:
        action = self._strict_action(
            message,
            intent=_ROOT_INTENT,
            source_detail=_ROOT_SOURCE_DETAIL,
            action_type=_ROOT_ACTION_TYPE,
            schema_version=CROSS_TASK_CONTINUATION_SCHEMA_VERSION,
        )
        payload = dict(action)
        payload.pop("type", None)
        try:
            root = ProjectDirectorCrossTaskContinuationRoot.model_validate(payload)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("exact_run_reservation_history_invalid") from exc
        related_task_id = (
            root.next_task_id
            if root.status == "prepared"
            else root.source_task_id
        )
        if (
            message.id != root.record_id
            or message.content
            != f"P24 cross-Task continuation root: {root.record_id}"
            or message.session_id != root.session_id
            or message.related_plan_version_id != root.plan_version_id
            or message.related_project_id != root.project_id
            or message.related_task_id != related_task_id
            or message.created_at != root.created_at
            or message.forbidden_actions_detected != list(root.forbidden_actions)
        ):
            raise _Blocked("exact_run_reservation_history_invalid")
        return root

    def _parse_reservation_message(
        self,
        message: ProjectDirectorMessage,
        *,
        continuation_root_record_id: UUID,
        instruction_package_id: UUID,
    ) -> ProjectDirectorCrossTaskExactRunReservation:
        is_target = (
            len(message.suggested_actions) == 1
            and isinstance(message.suggested_actions[0], dict)
            and str(
                message.suggested_actions[0].get(
                    "continuation_root_record_id"
                )
            )
            == str(continuation_root_record_id)
            and str(
                message.suggested_actions[0].get("instruction_package_id")
            )
            == str(instruction_package_id)
        )
        reason: CrossTaskExactRunReservationBlockedReason = (
            "exact_run_reservation_replay_conflict"
            if is_target
            else "exact_run_reservation_history_invalid"
        )
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
            reservation = (
                ProjectDirectorCrossTaskExactRunReservation.model_validate(
                    payload
                )
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(reason) from exc
        return reservation

    @staticmethod
    def _strict_action(
        message: ProjectDirectorMessage,
        *,
        intent: str,
        source_detail: str,
        action_type: str,
        schema_version: str,
        reason: CrossTaskExactRunReservationBlockedReason = (
            "exact_run_reservation_history_invalid"
        ),
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
    def _validate_reservation_message_binding(
        message: ProjectDirectorMessage,
        reservation: ProjectDirectorCrossTaskExactRunReservation,
        *,
        reason: CrossTaskExactRunReservationBlockedReason = (
            "exact_run_reservation_history_invalid"
        ),
    ) -> None:
        if (
            message.id != reservation.exact_run_reservation_id
            or message.content
            != (
                f"{_RESERVATION_CONTENT_PREFIX}: "
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

    def _validate_history_graph(
        self,
        history: _History,
        *,
        continuation_root_record_id: UUID,
        instruction_package_id: UUID,
    ) -> None:
        packages = [item[1] for item in history.packages]
        roots = [item[1] for item in history.roots]
        reservations = [item[1] for item in history.reservations]
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
            [reservation.exact_run_reservation_id for reservation in reservations],
            [reservation.reservation_replay_key for reservation in reservations],
            [reservation.exact_run_id for reservation in reservations],
            [
                (
                    reservation.continuation_root_record_id,
                    reservation.instruction_package_id,
                    reservation.next_task_id,
                )
                for reservation in reservations
            ],
        )

        for root_message, root in history.roots:
            if root.status == "prepared":
                matches = [
                    item
                    for item in history.packages
                    if item[1].package_id == root.instruction_package_id
                ]
                if len(matches) != 1:
                    raise _Blocked("exact_run_reservation_history_conflict")
                package_message, package = matches[0]
                self._validate_root_package_binding(root, package)
                if package_message.sequence_no + 1 != root_message.sequence_no:
                    raise _Blocked("exact_run_reservation_history_conflict")
            elif any(
                package.continuation_id == root.continuation_id
                or self._package_source_identity(package)
                == self._root_source_identity(root)
                for package in packages
            ):
                raise _Blocked("exact_run_reservation_history_conflict")

        for package in packages:
            matches = [
                root
                for root in roots
                if root.status == "prepared"
                and root.instruction_package_id == package.package_id
            ]
            if len(matches) != 1:
                raise _Blocked("exact_run_reservation_history_conflict")

        for _, reservation in history.reservations:
            root_matches = [
                root
                for root in roots
                if root.record_id == reservation.continuation_root_record_id
            ]
            package_matches = [
                package
                for package in packages
                if package.package_id == reservation.instruction_package_id
            ]
            if len(root_matches) != 1 or len(package_matches) != 1:
                raise _Blocked("exact_run_reservation_history_conflict")
            reason: CrossTaskExactRunReservationBlockedReason = (
                "exact_run_reservation_replay_conflict"
                if (
                    reservation.continuation_root_record_id
                    == continuation_root_record_id
                    and reservation.instruction_package_id
                    == instruction_package_id
                )
                else "exact_run_reservation_history_conflict"
            )
            self._validate_reservation_history_binding(
                reservation,
                root_matches[0],
                package_matches[0],
                reason=reason,
            )

    @staticmethod
    def _require_unique(*collections: list[Any]) -> None:
        if any(len(values) != len(set(values)) for values in collections):
            raise _Blocked("exact_run_reservation_history_conflict")

    @staticmethod
    def _validate_root_package_binding(
        root: ProjectDirectorCrossTaskContinuationRoot,
        package: ProjectDirectorNextTaskInstructionPackage,
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
            raise _Blocked("exact_run_reservation_history_conflict")

    @classmethod
    def _validate_reservation_history_binding(
        cls,
        reservation: ProjectDirectorCrossTaskExactRunReservation,
        root: ProjectDirectorCrossTaskContinuationRoot,
        package: ProjectDirectorNextTaskInstructionPackage,
        *,
        reason: CrossTaskExactRunReservationBlockedReason,
    ) -> None:
        cls._validate_root_package_binding(root, package)
        strategy = package.selected_strategy
        if (
            reservation.continuation_sequence_no != 2
            or reservation.previous_record_id != root.record_id
            or reservation.replay_of_record_id is not None
            or reservation.continuation_id != root.continuation_id
            or reservation.continuation_root_record_id != root.record_id
            or reservation.continuation_root_fingerprint
            != root.continuation_fingerprint
            or reservation.continuation_idempotency_key
            != root.idempotency_key
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
            != cls._reservation_forbidden_actions(package.forbidden_actions)
        ):
            raise _Blocked(reason)

    def _locate_exact_root_and_package(
        self,
        *,
        history: _History,
        session_id: UUID,
        project_id: UUID,
        continuation_root_record_id: UUID,
        instruction_package_id: UUID,
    ) -> tuple[
        ProjectDirectorCrossTaskContinuationRoot,
        ProjectDirectorNextTaskInstructionPackage,
    ]:
        root_matches = [
            root
            for _, root in history.roots
            if root.record_id == continuation_root_record_id
        ]
        if len(root_matches) != 1:
            raise _Blocked("exact_run_reservation_root_invalid")
        package_matches = [
            package
            for _, package in history.packages
            if package.package_id == instruction_package_id
        ]
        if len(package_matches) != 1:
            raise _Blocked("exact_run_reservation_package_invalid")
        root = root_matches[0]
        package = package_matches[0]
        if (
            root.status != "prepared"
            or root.session_id != session_id
            or root.project_id != project_id
        ):
            raise _Blocked("exact_run_reservation_root_invalid")
        if (
            package.session_id != session_id
            or package.project_id != project_id
            or package.human_confirmation_required is not False
        ):
            raise _Blocked("exact_run_reservation_package_invalid")
        if (
            root.product_runtime_git_write_allowed is not False
            or package.product_runtime_git_write_allowed is not False
        ):
            raise _Blocked("exact_run_reservation_git_boundary_violation")
        self._validate_root_package_binding(root, package)
        return root, package

    def _load_exact_task(self, task_id: UUID) -> Task:
        try:
            task = self._task_repository.get_by_id(task_id)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("exact_run_reservation_task_identity_conflict") from exc
        if task is None:
            raise _Blocked("exact_run_reservation_task_missing")
        return task

    def _load_exact_task_for_replay(self, task_id: UUID) -> Task:
        try:
            task = self._task_repository.get_by_id(task_id)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("exact_run_reservation_replay_conflict") from exc
        if task is None:
            raise _Blocked("exact_run_reservation_replay_conflict")
        return task

    @staticmethod
    def _task_identity_matches(
        task: Task,
        package: ProjectDirectorNextTaskInstructionPackage,
    ) -> bool:
        return (
            task.id == package.next_task_id
            and task.project_id == package.project_id
            and task.title == package.task_title
            and task.input_summary == package.task_input_summary
            and task.owner_role_code == package.owner_role_code
            and task.priority == package.priority
            and task.risk_level == package.risk_level
            and tuple(task.depends_on_task_ids) == package.depends_on_task_ids
            and task.source_draft_id
            == f"pdv:{package.plan_version_id}:{package.plan_version_no}"
        )

    @classmethod
    def _validate_task_identity(
        cls,
        task: Task,
        package: ProjectDirectorNextTaskInstructionPackage,
    ) -> None:
        if not cls._task_identity_matches(task, package):
            raise _Blocked("exact_run_reservation_task_identity_conflict")

    @staticmethod
    def _validate_pending_task_state(task: Task) -> None:
        if (
            task.status != TaskStatus.PENDING
            or task.human_status
            not in {TaskHumanStatus.NONE, TaskHumanStatus.RESOLVED}
            or task.paused_reason is not None
        ):
            raise _Blocked("exact_run_reservation_task_state_conflict")

    def _validate_dependencies(
        self,
        package: ProjectDirectorNextTaskInstructionPackage,
    ) -> None:
        dependency_ids = list(package.depends_on_task_ids)
        try:
            dependencies = self._task_repository.get_by_ids(dependency_ids)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("exact_run_reservation_dependency_blocked") from exc
        if (
            set(dependencies) != set(dependency_ids)
            or any(
                dependencies[dependency_id].status != TaskStatus.COMPLETED
                for dependency_id in dependency_ids
            )
        ):
            raise _Blocked("exact_run_reservation_dependency_blocked")

    def _validate_no_active_run(self, task_id: UUID) -> None:
        try:
            runs = self._run_repository.list_by_task_id(task_id)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("exact_run_reservation_active_run_conflict") from exc
        if any(run.status in {RunStatus.QUEUED, RunStatus.RUNNING} for run in runs):
            raise _Blocked("exact_run_reservation_active_run_conflict")

    def _validate_no_active_agent_session(self, task_id: UUID) -> None:
        try:
            sessions = self._agent_session_repository.list_by_task_id(task_id)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(
                "exact_run_reservation_active_agent_session_conflict"
            ) from exc
        if any(
            session.status
            in {AgentSessionStatus.RUNNING, AgentSessionStatus.REVIEW_REWORK}
            for session in sessions
        ):
            raise _Blocked(
                "exact_run_reservation_active_agent_session_conflict"
            )

    def _claim_exact_task(self, task_id: UUID) -> Task:
        try:
            task = self._task_repository.claim_pending_task(task_id)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("exact_run_reservation_task_claim_conflict") from exc
        if task is None:
            raise _Blocked("exact_run_reservation_task_claim_conflict")
        return task

    @staticmethod
    def _routing_inputs(
        package: ProjectDirectorNextTaskInstructionPackage,
        *,
        conflict_reason: CrossTaskExactRunReservationBlockedReason = (
            "exact_run_reservation_routing_conflict"
        ),
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
            raise _Blocked(conflict_reason)
        if (
            strategy.budget_pressure_level == RunBudgetPressureLevel.BLOCKED
            or strategy.budget_action == RunBudgetStrategyAction.BLOCK
        ):
            reason: CrossTaskExactRunReservationBlockedReason = (
                "exact_run_reservation_budget_blocked"
                if conflict_reason == "exact_run_reservation_routing_conflict"
                else conflict_reason
            )
            raise _Blocked(reason)
        try:
            routing_breakdown = [
                RunRoutingScoreItem(
                    code=item.code,
                    label=item.label,
                    score=item.score,
                    detail=item.detail,
                )
                for item in strategy.routing_score_breakdown
            ]
            strategy_decision = RunStrategyDecision(
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
                        code=reason.code,
                        label=reason.label,
                        detail=reason.detail,
                        score=reason.score,
                    )
                    for reason in decision.reasons
                ],
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(conflict_reason) from exc
        return routing_breakdown, strategy_decision

    def _create_running_run(
        self,
        *,
        package: ProjectDirectorNextTaskInstructionPackage,
        routing_breakdown: list[RunRoutingScoreItem],
        strategy_decision: RunStrategyDecision,
    ) -> Run:
        strategy = package.selected_strategy
        try:
            return self._run_repository.add_running_run_no_event(
                task_id=package.next_task_id,
                model_name=package.selected_model.model_name,
                route_reason=strategy.route_reason,
                routing_score=strategy.routing_score,
                routing_score_breakdown=routing_breakdown,
                strategy_decision=strategy_decision,
                owner_role_code=strategy.owner_role_code,
                upstream_role_code=strategy.upstream_role_code,
                downstream_role_code=strategy.downstream_role_code,
                handoff_reason=strategy.handoff_reason,
                dispatch_status=strategy.dispatch_status,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("exact_run_reservation_run_creation_failed") from exc

    @staticmethod
    def _validate_persisted_run(
        *,
        run: Run,
        package: ProjectDirectorNextTaskInstructionPackage,
        routing_breakdown: list[RunRoutingScoreItem],
        strategy_decision: RunStrategyDecision,
        reason: CrossTaskExactRunReservationBlockedReason,
    ) -> None:
        strategy = package.selected_strategy
        if (
            run.task_id != package.next_task_id
            or run.status != RunStatus.RUNNING
            or run.model_name != package.selected_model.model_name
            or run.route_reason != strategy.route_reason
            or run.routing_score != strategy.routing_score
            or run.routing_score_breakdown != routing_breakdown
            or run.strategy_decision != strategy_decision
            or run.owner_role_code != strategy.owner_role_code
            or run.upstream_role_code != strategy.upstream_role_code
            or run.downstream_role_code != strategy.downstream_role_code
            or run.handoff_reason != strategy.handoff_reason
            or run.dispatch_status != strategy.dispatch_status
            or run.started_at is None
            or run.finished_at is not None
            or run.failure_category is not None
            or run.quality_gate_passed is not None
        ):
            raise _Blocked(reason)

    @classmethod
    def _build_reservation(
        cls,
        *,
        root: ProjectDirectorCrossTaskContinuationRoot,
        package: ProjectDirectorNextTaskInstructionPackage,
        task_human_status: Literal["none", "resolved"],
        run: Run,
        exact_run_reservation_id: UUID,
        created_at: datetime,
        conflict_reason: CrossTaskExactRunReservationBlockedReason = (
            "exact_run_reservation_persistence_failed"
        ),
    ) -> ProjectDirectorCrossTaskExactRunReservation:
        if run.started_at is None:
            raise _Blocked(conflict_reason)
        strategy = package.selected_strategy
        payload: dict[str, Any] = {
            "schema_version": CROSS_TASK_EXACT_RUN_RESERVATION_SCHEMA_VERSION,
            "exact_run_reservation_id": exact_run_reservation_id,
            "reservation_replay_key": (
                ProjectDirectorCrossTaskExactRunReservation
                .compute_reservation_replay_key(
                    continuation_id=root.continuation_id,
                    continuation_root_record_id=root.record_id,
                    instruction_package_id=package.package_id,
                    next_task_id=package.next_task_id,
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
            "continuation_sequence_no": 2,
            "previous_record_id": root.record_id,
            "replay_of_record_id": None,
            "action": "reserve_exact_next_task_run",
            "status": "next_task_run_created",
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
            "next_task_id": package.next_task_id,
            "next_task_index": package.next_task_index,
            "task_count": package.task_count,
            "task_title": package.task_title,
            "task_input_summary": package.task_input_summary,
            "owner_role_code": package.owner_role_code,
            "priority": package.priority,
            "risk_level": package.risk_level,
            "depends_on_task_ids": package.depends_on_task_ids,
            "task_status_before": "pending",
            "task_status_after": "running",
            "task_human_status": task_human_status,
            "task_paused_reason_absent": True,
            "new_task_created": False,
            "task_claimed": True,
            "run_created": True,
            "worker_called": False,
            "active_run_ids_before": (),
            "active_agent_session_ids_before": (),
            "exact_run_id": run.id,
            "exact_run_status": "running",
            "exact_run_started_at": run.started_at,
            "exact_run_created_at": run.created_at,
            "exact_run_finished_at": None,
            "exact_run_failure_category": None,
            "exact_run_quality_gate_passed": None,
            "run_model_name": package.selected_model.model_name,
            "run_route_reason": strategy.route_reason,
            "run_routing_score": strategy.routing_score,
            "run_routing_score_breakdown": strategy.routing_score_breakdown,
            "run_strategy_decision": strategy.strategy_decision,
            "run_owner_role_code": strategy.owner_role_code,
            "run_upstream_role_code": strategy.upstream_role_code,
            "run_downstream_role_code": strategy.downstream_role_code,
            "run_handoff_reason": strategy.handoff_reason,
            "run_dispatch_status": strategy.dispatch_status,
            "product_runtime_git_write_allowed": False,
            "forbidden_actions": cls._reservation_forbidden_actions(
                package.forbidden_actions
            ),
        }
        try:
            fingerprint = compute_p24_contract_sha256(payload)
            return ProjectDirectorCrossTaskExactRunReservation(
                **payload,
                reservation_fingerprint=fingerprint,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(conflict_reason) from exc

    @staticmethod
    def _reservation_forbidden_actions(
        source_actions: tuple[str, ...],
    ) -> tuple[str, ...]:
        retained = [
            action for action in source_actions if action not in _COMPLETED_ACTIONS
        ]
        seen = set(retained)
        for action in _RESERVATION_REQUIRED_FORBIDDEN_ACTIONS:
            if action not in seen:
                retained.append(action)
                seen.add(action)
        return tuple(retained)

    @staticmethod
    def _build_reservation_message(
        reservation: ProjectDirectorCrossTaskExactRunReservation,
        sequence_no: int,
    ) -> ProjectDirectorMessage:
        try:
            return ProjectDirectorMessage(
                id=reservation.exact_run_reservation_id,
                session_id=reservation.session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    f"{_RESERVATION_CONTENT_PREFIX}: "
                    f"{reservation.exact_run_reservation_id}"
                ),
                sequence_no=sequence_no,
                intent=CROSS_TASK_EXACT_RUN_RESERVATION_INTENT,
                related_plan_version_id=reservation.plan_version_id,
                related_project_id=reservation.project_id,
                related_task_id=reservation.next_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=CROSS_TASK_EXACT_RUN_RESERVATION_SOURCE_DETAIL,
                suggested_actions=[
                    {
                        "type": CROSS_TASK_EXACT_RUN_RESERVATION_ACTION_TYPE,
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
                "exact_run_reservation_persistence_failed"
            ) from exc

    def _create_message(self, message: ProjectDirectorMessage) -> None:
        try:
            self._message_repository.create(message)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked(
                "exact_run_reservation_persistence_failed"
            ) from exc

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
                "P24-E1B repositories must share one SQLAlchemy session"
            )

    @staticmethod
    def _blocked_result(
        reason: CrossTaskExactRunReservationBlockedReason,
    ) -> ProjectDirectorCrossTaskExactRunReservationResult:
        return ProjectDirectorCrossTaskExactRunReservationResult(
            status="blocked",
            reservation=None,
            blocked_reasons=(reason,),
            product_runtime_git_write_allowed=False,
        )


__all__ = ("ProjectDirectorCrossTaskExactRunReservationService",)
