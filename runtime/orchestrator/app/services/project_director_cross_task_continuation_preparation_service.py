"""Atomic P24-D2B2 instruction-package and continuation preparation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.domain._base import utc_now
from app.domain.project_director_cross_task_continuation import (
    CROSS_TASK_CONTINUATION_SCHEMA_VERSION,
    CrossTaskContinuationBlockedReason,
    ProjectDirectorCrossTaskContinuationPreparationResult,
    ProjectDirectorCrossTaskContinuationRoot,
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
from app.domain.project_director_next_task_instruction_package_candidate import (
    ProjectDirectorNextTaskInstructionPackageCandidate,
)
from app.domain.project_director_next_task_source_bundle import (
    ProjectDirectorNextTaskSourceBundleResolution,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.services.project_director_next_task_instruction_package_candidate_builder import (
    ProjectDirectorNextTaskInstructionPackageCandidateBuilder,
)
from app.services.project_director_next_task_source_bundle_resolver import (
    ProjectDirectorNextTaskSourceBundleResolver,
)


_PAGE_SIZE = 200

_PACKAGE_INTENT = "cross_task_next_task_instruction_package"
_PACKAGE_SOURCE_DETAIL = "p24_next_task_instruction_package_prepared"
_PACKAGE_ACTION_TYPE = "p24_next_task_instruction_package_record"

_ROOT_INTENT = "cross_task_auto_continue"
_ROOT_SOURCE_DETAIL = "p24_cross_task_continuation_recorded"
_ROOT_ACTION_TYPE = "p24_cross_task_continuation_record"

_FORMAL_FORBIDDEN_ACTIONS = (
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
    "uncontrolled_workspace_write",
    "task_claim",
    "run_creation",
    "worker_invocation",
    "verification_command_execution",
)


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


class _Blocked(Exception):
    def __init__(self, reason: CrossTaskContinuationBlockedReason) -> None:
        self.reason = reason
        super().__init__(reason)


class ProjectDirectorCrossTaskContinuationPreparationService:
    """Prepare or replay one append-only package/continuation root pair."""

    def __init__(
        self,
        *,
        candidate_builder: ProjectDirectorNextTaskInstructionPackageCandidateBuilder,
        source_bundle_resolver: ProjectDirectorNextTaskSourceBundleResolver,
        message_repository: ProjectDirectorMessageRepository,
    ) -> None:
        self._candidate_builder = candidate_builder
        self._source_bundle_resolver = source_bundle_resolver
        self._message_repository = message_repository
        self._require_shared_session()

    def prepare_cross_task_continuation(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        source_completion_evidence_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
    ) -> ProjectDirectorCrossTaskContinuationPreparationResult:
        """Atomically prepare, replay, or record exhausted continuation state."""

        self._require_shared_session()
        try:
            with self._message_repository.sqlite_immediate_transaction():
                history = self._load_history(session_id)
                candidate_result = self._build_candidate_result(
                    session_id=session_id,
                    project_id=project_id,
                    source_completion_evidence_id=source_completion_evidence_id,
                    source_task_id=source_task_id,
                    source_run_id=source_run_id,
                )
                if candidate_result.status == "plan_queue_exhausted":
                    return self._prepare_exhausted(
                        history=history,
                        session_id=session_id,
                        project_id=project_id,
                        source_completion_evidence_id=(
                            source_completion_evidence_id
                        ),
                        source_task_id=source_task_id,
                        source_run_id=source_run_id,
                    )
                if (
                    candidate_result.status != "package_candidate_ready"
                    or candidate_result.candidate is None
                    or candidate_result.blocked_reasons
                ):
                    raise _Blocked("continuation_candidate_invalid")
                return self._prepare_ready(
                    history=history,
                    candidate=candidate_result.candidate,
                    session_id=session_id,
                    project_id=project_id,
                    source_completion_evidence_id=source_completion_evidence_id,
                    source_task_id=source_task_id,
                    source_run_id=source_run_id,
                )
        except _Blocked as exc:
            return self._blocked_result(exc.reason)
        except SQLAlchemyError:
            return self._blocked_result("continuation_persistence_failed")

    def _build_candidate_result(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        source_completion_evidence_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
    ) -> Any:
        try:
            result = (
                self._candidate_builder
                .build_next_task_instruction_package_candidate(
                    session_id=session_id,
                    project_id=project_id,
                    source_completion_evidence_id=source_completion_evidence_id,
                    source_task_id=source_task_id,
                    source_run_id=source_run_id,
                )
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("continuation_candidate_invalid") from exc
        if result.status == "blocked":
            raise _Blocked("continuation_candidate_invalid")
        return result

    def _prepare_ready(
        self,
        *,
        history: _History,
        candidate: ProjectDirectorNextTaskInstructionPackageCandidate,
        session_id: UUID,
        project_id: UUID,
        source_completion_evidence_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
    ) -> ProjectDirectorCrossTaskContinuationPreparationResult:
        if candidate.product_runtime_git_write_allowed is not False:
            raise _Blocked("continuation_git_boundary_violation")
        if (
            candidate.candidate_fingerprint != candidate.compute_fingerprint()
            or candidate.session_id != session_id
            or candidate.project_id != project_id
            or candidate.source_completion_evidence_id
            != source_completion_evidence_id
            or candidate.source_task_id != source_task_id
            or candidate.source_run_id != source_run_id
        ):
            raise _Blocked("continuation_candidate_invalid")

        forbidden_actions = self._formal_forbidden_actions(
            candidate.forbidden_actions
        )
        idempotency_key = (
            ProjectDirectorCrossTaskContinuationRoot.compute_idempotency_key(
                session_id=candidate.session_id,
                project_id=candidate.project_id,
                plan_version_id=candidate.plan_version_id,
                task_creation_record_id=candidate.task_creation_record_id,
                source_task_id=candidate.source_task_id,
                source_run_id=candidate.source_run_id,
                source_completion_evidence_id=(
                    candidate.source_completion_evidence_id
                ),
            )
        )
        root_matches = [
            item for item in history.roots if item[1].idempotency_key == idempotency_key
        ]
        if root_matches:
            _, existing_root = root_matches[0]
            if existing_root.status != "prepared":
                raise _Blocked("continuation_replay_conflict")
            package_matches = [
                item
                for item in history.packages
                if item[1].package_id == existing_root.instruction_package_id
            ]
            if len(package_matches) != 1:
                raise _Blocked("continuation_history_conflict")
            _, existing_package = package_matches[0]
            expected_package = self._build_package(
                candidate=candidate,
                package_id=existing_package.package_id,
                continuation_id=existing_root.continuation_id,
                created_at=existing_root.created_at,
                forbidden_actions=forbidden_actions,
            )
            expected_root = self._build_prepared_root(
                package=expected_package,
                record_id=existing_root.record_id,
                forbidden_actions=forbidden_actions,
            )
            if (
                existing_package != expected_package
                or existing_root != expected_root
            ):
                raise _Blocked("continuation_replay_conflict")
            return ProjectDirectorCrossTaskContinuationPreparationResult(
                status="package_replayed",
                continuation_root=existing_root,
                instruction_package=existing_package,
                blocked_reasons=(),
                product_runtime_git_write_allowed=False,
            )

        candidate_identity = self._candidate_source_identity(candidate)
        if any(
            self._package_source_identity(package) == candidate_identity
            and package.next_task_id == candidate.next_task_id
            for _, package in history.packages
        ):
            raise _Blocked("continuation_history_conflict")

        continuation_id, package_id, record_id = self._new_distinct_ids(3)
        created_at = utc_now()
        package = self._build_package(
            candidate=candidate,
            package_id=package_id,
            continuation_id=continuation_id,
            created_at=created_at,
            forbidden_actions=forbidden_actions,
        )
        root = self._build_prepared_root(
            package=package,
            record_id=record_id,
            forbidden_actions=forbidden_actions,
        )
        next_sequence = self._message_repository.get_next_sequence_no(
            session_id=session_id
        )
        package_message = self._build_package_message(package, next_sequence)
        root_message = self._build_root_message(root, next_sequence + 1)
        self._create_message(package_message)
        self._create_message(root_message)
        return ProjectDirectorCrossTaskContinuationPreparationResult(
            status="package_prepared",
            continuation_root=root,
            instruction_package=package,
            blocked_reasons=(),
            product_runtime_git_write_allowed=False,
        )

    def _prepare_exhausted(
        self,
        *,
        history: _History,
        session_id: UUID,
        project_id: UUID,
        source_completion_evidence_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
    ) -> ProjectDirectorCrossTaskContinuationPreparationResult:
        resolution = self._resolve_exhausted_source_bundle(
            session_id=session_id,
            project_id=project_id,
            source_completion_evidence_id=source_completion_evidence_id,
            source_task_id=source_task_id,
            source_run_id=source_run_id,
        )
        snapshot = resolution.queue_snapshot
        if (
            resolution.status != "plan_queue_exhausted"
            or snapshot is None
            or snapshot.queue_exhausted is not True
            or snapshot.next_task_id is not None
            or snapshot.next_task_index is not None
            or resolution.source_bundle is not None
            or resolution.blocked_reasons
            or snapshot.session_id != session_id
            or snapshot.project_id != project_id
            or snapshot.source_task_id != source_task_id
            or snapshot.source_completion_evidence_id
            != source_completion_evidence_id
        ):
            raise _Blocked("continuation_candidate_invalid")
        if snapshot.product_runtime_git_write_allowed is not False:
            raise _Blocked("continuation_git_boundary_violation")

        idempotency_key = (
            ProjectDirectorCrossTaskContinuationRoot.compute_idempotency_key(
                session_id=snapshot.session_id,
                project_id=snapshot.project_id,
                plan_version_id=snapshot.plan_version_id,
                task_creation_record_id=snapshot.task_creation_record_id,
                source_task_id=snapshot.source_task_id,
                source_run_id=source_run_id,
                source_completion_evidence_id=(
                    snapshot.source_completion_evidence_id
                ),
            )
        )
        root_matches = [
            item for item in history.roots if item[1].idempotency_key == idempotency_key
        ]
        if root_matches:
            _, existing_root = root_matches[0]
            if existing_root.status != "plan_queue_exhausted":
                raise _Blocked("continuation_replay_conflict")
            expected_root = self._build_exhausted_root(
                snapshot=snapshot,
                source_run_id=source_run_id,
                record_id=existing_root.record_id,
                continuation_id=existing_root.continuation_id,
                created_at=existing_root.created_at,
            )
            if existing_root != expected_root:
                raise _Blocked("continuation_replay_conflict")
            return ProjectDirectorCrossTaskContinuationPreparationResult(
                status="plan_queue_exhausted_replayed",
                continuation_root=existing_root,
                instruction_package=None,
                blocked_reasons=(),
                product_runtime_git_write_allowed=False,
            )

        continuation_id, record_id = self._new_distinct_ids(2)
        root = self._build_exhausted_root(
            snapshot=snapshot,
            source_run_id=source_run_id,
            record_id=record_id,
            continuation_id=continuation_id,
            created_at=utc_now(),
        )
        next_sequence = self._message_repository.get_next_sequence_no(
            session_id=session_id
        )
        root_message = self._build_root_message(root, next_sequence)
        self._create_message(root_message)
        return ProjectDirectorCrossTaskContinuationPreparationResult(
            status="plan_queue_exhausted_recorded",
            continuation_root=root,
            instruction_package=None,
            blocked_reasons=(),
            product_runtime_git_write_allowed=False,
        )

    def _resolve_exhausted_source_bundle(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        source_completion_evidence_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
    ) -> ProjectDirectorNextTaskSourceBundleResolution:
        try:
            return self._source_bundle_resolver.resolve_next_task_source_bundle(
                session_id=session_id,
                project_id=project_id,
                source_completion_evidence_id=source_completion_evidence_id,
                source_task_id=source_task_id,
                source_run_id=source_run_id,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("continuation_candidate_invalid") from exc

    def _build_package(
        self,
        *,
        candidate: ProjectDirectorNextTaskInstructionPackageCandidate,
        package_id: UUID,
        continuation_id: UUID,
        created_at: datetime,
        forbidden_actions: tuple[str, ...],
    ) -> ProjectDirectorNextTaskInstructionPackage:
        lineage = candidate.source_authority_lineage
        payload: dict[str, Any] = {
            "schema_version": NEXT_TASK_INSTRUCTION_PACKAGE_SCHEMA_VERSION,
            "package_id": package_id,
            "package_replay_key": (
                ProjectDirectorNextTaskInstructionPackage.compute_package_replay_key(
                    continuation_id=continuation_id,
                    source_completion_evidence_id=(
                        candidate.source_completion_evidence_id
                    ),
                    next_task_id=candidate.next_task_id,
                )
            ),
            "created_at": created_at,
            "continuation_id": continuation_id,
            "supersedes_package_id": None,
            "instruction_candidate_schema_version": candidate.schema_version,
            "instruction_candidate_fingerprint": candidate.candidate_fingerprint,
            "session_id": candidate.session_id,
            "project_id": candidate.project_id,
            "plan_version_id": candidate.plan_version_id,
            "plan_version_no": candidate.plan_version_no,
            "task_creation_record_id": candidate.task_creation_record_id,
            "source_task_id": candidate.source_task_id,
            "source_run_id": candidate.source_run_id,
            "source_completion_evidence_id": (
                candidate.source_completion_evidence_id
            ),
            "source_completion_evidence_fingerprint": (
                lineage.source_completion_evidence_fingerprint
            ),
            "source_execution_authority_kind": (
                lineage.source_execution_authority_kind
            ),
            "source_execution_authority_id": (
                lineage.source_execution_authority_id
            ),
            "source_execution_authority_fingerprint": (
                lineage.source_execution_authority_fingerprint
            ),
            "source_worker_start_reservation_id": lineage.source_reservation_id,
            "source_worker_invocation_claim_id": lineage.source_claim_id,
            "source_worker_invocation_outcome_id": lineage.source_outcome_id,
            "source_worker_outcome_schema_version": (
                lineage.source_outcome_schema_version
            ),
            "source_worker_outcome_fingerprint": (
                lineage.source_outcome_fingerprint
            ),
            "source_review_id": lineage.source_review_id,
            "source_review_outcome": lineage.source_review_outcome,
            "source_transition_evidence_ids": (
                lineage.source_transition_evidence_ids
            ),
            "completion_policy_id": lineage.completion_policy_id,
            "completion_policy_version": lineage.completion_policy_version,
            "completion_policy_fingerprint": (
                lineage.completion_policy_fingerprint
            ),
            "review_requirement": lineage.completion_review_requirement,
            "source_authority_lineage": lineage,
            "next_task_id": candidate.next_task_id,
            "next_task_index": candidate.next_task_index,
            "task_count": candidate.task_count,
            "task_title": candidate.task_title,
            "task_input_summary": candidate.task_input_summary,
            "owner_role_code": candidate.owner_role_code,
            "priority": candidate.priority,
            "risk_level": candidate.risk_level,
            "depends_on_task_ids": candidate.depends_on_task_ids,
            "confirmed_scope": candidate.confirmed_scope,
            "repository_binding": candidate.repository_binding,
            "workspace_binding": candidate.workspace_binding,
            "allowed_paths": candidate.allowed_paths,
            "forbidden_scope_entries": candidate.forbidden_scope_entries,
            "workspace_ignore_rule_summary": (
                candidate.workspace_ignore_rule_summary
            ),
            "forbidden_paths": candidate.forbidden_paths,
            "acceptance_criteria_source": candidate.acceptance_criteria_source,
            "acceptance_criteria": candidate.acceptance_criteria,
            "verification_requirements": candidate.verification_requirements,
            "test_requirements": candidate.test_requirements,
            "evidence_requirements": candidate.evidence_requirements,
            "selected_strategy": candidate.selected_strategy,
            "selected_model": candidate.selected_model,
            "selected_skills": candidate.selected_skills,
            "human_confirmation_required": False,
            "human_confirmation_evidence_id": None,
            "product_runtime_git_write_allowed": False,
            "forbidden_actions": forbidden_actions,
        }
        try:
            fingerprint = compute_p24_contract_sha256(payload)
            return ProjectDirectorNextTaskInstructionPackage(
                **payload,
                package_fingerprint=fingerprint,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("continuation_package_invalid") from exc

    def _build_prepared_root(
        self,
        *,
        package: ProjectDirectorNextTaskInstructionPackage,
        record_id: UUID,
        forbidden_actions: tuple[str, ...],
    ) -> ProjectDirectorCrossTaskContinuationRoot:
        payload: dict[str, Any] = {
            "schema_version": CROSS_TASK_CONTINUATION_SCHEMA_VERSION,
            "record_id": record_id,
            "continuation_id": package.continuation_id,
            "idempotency_key": (
                ProjectDirectorCrossTaskContinuationRoot.compute_idempotency_key(
                    session_id=package.session_id,
                    project_id=package.project_id,
                    plan_version_id=package.plan_version_id,
                    task_creation_record_id=package.task_creation_record_id,
                    source_task_id=package.source_task_id,
                    source_run_id=package.source_run_id,
                    source_completion_evidence_id=(
                        package.source_completion_evidence_id
                    ),
                )
            ),
            "created_at": package.created_at,
            "sequence_no": 1,
            "previous_record_id": None,
            "replay_of_record_id": None,
            "action": "cross_task_auto_continue",
            "status": "prepared",
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
            "instruction_package_id": package.package_id,
            "instruction_package_fingerprint": package.package_fingerprint,
            "instruction_candidate_fingerprint": (
                package.instruction_candidate_fingerprint
            ),
            "exact_run_id": None,
            "worker_reservation_id": None,
            "worker_invocation_claim_id": None,
            "worker_outcome_id": None,
            "new_task_created": False,
            "run_created": False,
            "worker_called": False,
            "blocked_reasons": (),
            "product_runtime_git_write_allowed": False,
            "forbidden_actions": forbidden_actions,
        }
        return self._validate_root_payload(payload)

    def _build_exhausted_root(
        self,
        *,
        snapshot: Any,
        source_run_id: UUID,
        record_id: UUID,
        continuation_id: UUID,
        created_at: datetime,
    ) -> ProjectDirectorCrossTaskContinuationRoot:
        payload: dict[str, Any] = {
            "schema_version": CROSS_TASK_CONTINUATION_SCHEMA_VERSION,
            "record_id": record_id,
            "continuation_id": continuation_id,
            "idempotency_key": (
                ProjectDirectorCrossTaskContinuationRoot.compute_idempotency_key(
                    session_id=snapshot.session_id,
                    project_id=snapshot.project_id,
                    plan_version_id=snapshot.plan_version_id,
                    task_creation_record_id=snapshot.task_creation_record_id,
                    source_task_id=snapshot.source_task_id,
                    source_run_id=source_run_id,
                    source_completion_evidence_id=(
                        snapshot.source_completion_evidence_id
                    ),
                )
            ),
            "created_at": created_at,
            "sequence_no": 1,
            "previous_record_id": None,
            "replay_of_record_id": None,
            "action": "cross_task_auto_continue",
            "status": "plan_queue_exhausted",
            "session_id": snapshot.session_id,
            "project_id": snapshot.project_id,
            "plan_version_id": snapshot.plan_version_id,
            "task_creation_record_id": snapshot.task_creation_record_id,
            "source_task_id": snapshot.source_task_id,
            "source_run_id": source_run_id,
            "source_completion_evidence_id": (
                snapshot.source_completion_evidence_id
            ),
            "source_completion_evidence_fingerprint": (
                snapshot.source_completion_evidence_fingerprint
            ),
            "next_task_id": None,
            "instruction_package_id": None,
            "instruction_package_fingerprint": None,
            "instruction_candidate_fingerprint": None,
            "exact_run_id": None,
            "worker_reservation_id": None,
            "worker_invocation_claim_id": None,
            "worker_outcome_id": None,
            "new_task_created": False,
            "run_created": False,
            "worker_called": False,
            "blocked_reasons": (),
            "product_runtime_git_write_allowed": False,
            "forbidden_actions": _FORMAL_FORBIDDEN_ACTIONS,
        }
        return self._validate_root_payload(payload)

    @staticmethod
    def _validate_root_payload(
        payload: dict[str, Any],
    ) -> ProjectDirectorCrossTaskContinuationRoot:
        try:
            fingerprint = compute_p24_contract_sha256(payload)
            return ProjectDirectorCrossTaskContinuationRoot(
                **payload,
                continuation_fingerprint=fingerprint,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("continuation_root_invalid") from exc

    def _load_history(self, session_id: UUID) -> _History:
        try:
            messages = self._iter_session_messages(session_id)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("continuation_history_invalid") from exc
        packages: list[
            tuple[ProjectDirectorMessage, ProjectDirectorNextTaskInstructionPackage]
        ] = []
        roots: list[
            tuple[ProjectDirectorMessage, ProjectDirectorCrossTaskContinuationRoot]
        ] = []
        for message in messages:
            is_package = self._is_package_family(message)
            is_root = self._is_root_family(message)
            if is_package and is_root:
                raise _Blocked("continuation_history_invalid")
            if is_package:
                packages.append((message, self._parse_package_message(message)))
            elif is_root:
                roots.append((message, self._parse_root_message(message)))
        history = _History(packages=tuple(packages), roots=tuple(roots))
        self._validate_history_graph(history)
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
                raise ValueError("continuation history pagination returned an empty page")
            before_message_id = page[0].id

    @staticmethod
    def _is_package_family(message: ProjectDirectorMessage) -> bool:
        return (
            message.intent == _PACKAGE_INTENT
            or message.source_detail == _PACKAGE_SOURCE_DETAIL
            or any(
                isinstance(action, dict)
                and action.get("type") == _PACKAGE_ACTION_TYPE
                for action in message.suggested_actions
            )
        )

    @staticmethod
    def _is_root_family(message: ProjectDirectorMessage) -> bool:
        return (
            message.intent == _ROOT_INTENT
            or message.source_detail == _ROOT_SOURCE_DETAIL
            or any(
                isinstance(action, dict)
                and action.get("type") == _ROOT_ACTION_TYPE
                for action in message.suggested_actions
            )
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
            raise _Blocked("continuation_history_invalid") from exc
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
            raise _Blocked("continuation_history_invalid")
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
            raise _Blocked("continuation_history_invalid") from exc
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
            raise _Blocked("continuation_history_invalid")
        return root

    @staticmethod
    def _strict_action(
        message: ProjectDirectorMessage,
        *,
        intent: str,
        source_detail: str,
        action_type: str,
        schema_version: str,
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
            raise _Blocked("continuation_history_invalid")
        action = message.suggested_actions[0]
        if (
            action.get("type") != action_type
            or action.get("schema_version") != schema_version
        ):
            raise _Blocked("continuation_history_invalid")
        return action

    def _validate_history_graph(self, history: _History) -> None:
        packages = [item[1] for item in history.packages]
        roots = [item[1] for item in history.roots]
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

        for root_message, root in history.roots:
            if root.status == "prepared":
                matches = [
                    item
                    for item in history.packages
                    if item[1].package_id == root.instruction_package_id
                ]
                if len(matches) != 1:
                    raise _Blocked("continuation_history_conflict")
                package_message, package = matches[0]
                if (
                    root.instruction_package_fingerprint
                    != package.package_fingerprint
                    or root.instruction_candidate_fingerprint
                    != package.instruction_candidate_fingerprint
                    or root.continuation_id != package.continuation_id
                    or root.next_task_id != package.next_task_id
                    or root.forbidden_actions != package.forbidden_actions
                    or root.source_completion_evidence_fingerprint
                    != package.source_completion_evidence_fingerprint
                    or self._root_source_identity(root)
                    != self._package_source_identity(package)
                    or root.created_at != package.created_at
                    or package_message.sequence_no + 1
                    != root_message.sequence_no
                ):
                    raise _Blocked("continuation_history_conflict")
            elif any(
                package.continuation_id == root.continuation_id
                or self._package_source_identity(package)
                == self._root_source_identity(root)
                for package in packages
            ):
                raise _Blocked("continuation_history_conflict")

        for package in packages:
            matches = [
                root
                for root in roots
                if root.status == "prepared"
                and root.instruction_package_id == package.package_id
            ]
            if len(matches) != 1:
                raise _Blocked("continuation_history_conflict")

    @staticmethod
    def _require_unique(*collections: list[Any]) -> None:
        if any(len(values) != len(set(values)) for values in collections):
            raise _Blocked("continuation_history_conflict")

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

    @staticmethod
    def _candidate_source_identity(
        candidate: ProjectDirectorNextTaskInstructionPackageCandidate,
    ) -> tuple[UUID, ...]:
        return (
            candidate.session_id,
            candidate.project_id,
            candidate.plan_version_id,
            candidate.task_creation_record_id,
            candidate.source_task_id,
            candidate.source_run_id,
            candidate.source_completion_evidence_id,
        )

    @staticmethod
    def _formal_forbidden_actions(
        candidate_actions: tuple[str, ...],
    ) -> tuple[str, ...]:
        if (
            not candidate_actions
            or len(candidate_actions) != len(set(candidate_actions))
            or any(
                not isinstance(action, str)
                or not action.strip()
                or action != action.strip()
                for action in candidate_actions
            )
        ):
            raise _Blocked("continuation_candidate_invalid")
        merged = list(candidate_actions)
        seen = set(merged)
        for action in _FORMAL_FORBIDDEN_ACTIONS:
            if action not in seen:
                merged.append(action)
                seen.add(action)
        return tuple(merged)

    @staticmethod
    def _new_distinct_ids(count: int) -> tuple[UUID, ...]:
        values: list[UUID] = []
        while len(values) < count:
            value = uuid4()
            if value not in values:
                values.append(value)
        return tuple(values)

    @staticmethod
    def _build_package_message(
        package: ProjectDirectorNextTaskInstructionPackage,
        sequence_no: int,
    ) -> ProjectDirectorMessage:
        try:
            return ProjectDirectorMessage(
                id=package.package_id,
                session_id=package.session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=f"P24 next Task instruction package: {package.package_id}",
                sequence_no=sequence_no,
                intent=_PACKAGE_INTENT,
                related_plan_version_id=package.plan_version_id,
                related_project_id=package.project_id,
                related_task_id=package.next_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=_PACKAGE_SOURCE_DETAIL,
                suggested_actions=[
                    {
                        "type": _PACKAGE_ACTION_TYPE,
                        **package.model_dump(mode="json"),
                    }
                ],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                forbidden_actions_detected=list(package.forbidden_actions),
                token_count=None,
                estimated_cost=None,
                created_at=package.created_at,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("continuation_persistence_failed") from exc

    @staticmethod
    def _build_root_message(
        root: ProjectDirectorCrossTaskContinuationRoot,
        sequence_no: int,
    ) -> ProjectDirectorMessage:
        related_task_id = (
            root.next_task_id
            if root.status == "prepared"
            else root.source_task_id
        )
        try:
            return ProjectDirectorMessage(
                id=root.record_id,
                session_id=root.session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=f"P24 cross-Task continuation root: {root.record_id}",
                sequence_no=sequence_no,
                intent=_ROOT_INTENT,
                related_plan_version_id=root.plan_version_id,
                related_project_id=root.project_id,
                related_task_id=related_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=_ROOT_SOURCE_DETAIL,
                suggested_actions=[
                    {
                        "type": _ROOT_ACTION_TYPE,
                        **root.model_dump(mode="json"),
                    }
                ],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                forbidden_actions_detected=list(root.forbidden_actions),
                token_count=None,
                estimated_cost=None,
                created_at=root.created_at,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("continuation_persistence_failed") from exc

    def _create_message(self, message: ProjectDirectorMessage) -> None:
        try:
            self._message_repository.create(message)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("continuation_persistence_failed") from exc

    def _require_shared_session(self) -> None:
        session = self._message_repository._session
        if (
            self._candidate_builder._session is not session
            or self._source_bundle_resolver._session is not session
        ):
            raise ValueError(
                "P24-D2B2 dependencies must share one SQLAlchemy session"
            )

    @staticmethod
    def _blocked_result(
        reason: CrossTaskContinuationBlockedReason,
    ) -> ProjectDirectorCrossTaskContinuationPreparationResult:
        return ProjectDirectorCrossTaskContinuationPreparationResult(
            status="blocked",
            continuation_root=None,
            instruction_package=None,
            blocked_reasons=(reason,),
            product_runtime_git_write_allowed=False,
        )


__all__ = ("ProjectDirectorCrossTaskContinuationPreparationService",)
