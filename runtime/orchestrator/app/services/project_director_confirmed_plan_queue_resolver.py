"""Readonly P24-C resolver for one exact confirmed-plan successor Task."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.core.db_tables import TaskTable
from app.domain.project_director_confirmed_plan_queue import (
    CONFIRMED_PLAN_QUEUE_SCHEMA_VERSION,
    ConfirmedPlanQueueBlockedReason,
    ProjectDirectorConfirmedPlanQueueResolution,
    ProjectDirectorConfirmedPlanQueueSnapshot,
)
from app.domain.project_director_plan_version import PlanVersionStatus
from app.domain.project_director_source_task_completion_evidence import (
    ProjectDirectorSourceTaskCompletionEvidence,
)
from app.domain.task import Task
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.repositories.project_director_task_creation_repository import (
    ProjectDirectorTaskCreationRecordRepository,
    TaskCreationRecordConflictError,
    TaskCreationRecordInvalidError,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_source_task_completion_evidence_service import (
    ProjectDirectorSourceTaskCompletionEvidenceService,
)


_SOURCE_DRAFT_PATTERN = re.compile(r"^pdv:([0-9a-fA-F-]{36}):([1-9][0-9]*)$")
_SIGNED_64_BIT_MAX = (1 << 63) - 1

_FORBIDDEN_ACTIONS = [
    "no_task_router_or_global_pending_queue",
    "no_task_creation_or_mutation",
    "no_readiness_evaluation",
    "no_instruction_package_or_continuation_creation",
    "no_run_reservation_claim_or_outcome_creation",
    "no_worker_provider_or_runtime_call",
    "no_workspace_or_product_runtime_git_write",
]


@dataclass(frozen=True)
class _LocatedPlanVersion:
    plan_version_id: UUID
    plan_version_no: int


class _Blocked(Exception):
    def __init__(self, *reasons: ConfirmedPlanQueueBlockedReason) -> None:
        self.reasons = tuple(dict.fromkeys(reasons))
        super().__init__(self.reasons[0] if self.reasons else "plan_lineage_invalid")


class ProjectDirectorConfirmedPlanQueueResolver:
    """Resolve only the immediate successor in one authoritative plan queue."""

    def __init__(
        self,
        *,
        completion_evidence_service: (
            ProjectDirectorSourceTaskCompletionEvidenceService
        ),
        plan_version_repository: ProjectDirectorPlanVersionRepository,
        task_creation_record_repository: (
            ProjectDirectorTaskCreationRecordRepository
        ),
        task_repository: TaskRepository,
    ) -> None:
        self._completion_evidence_service = completion_evidence_service
        self._plan_version_repository = plan_version_repository
        self._task_creation_record_repository = task_creation_record_repository
        self._task_repository = task_repository
        self._require_shared_session()

    def resolve_exact_next_task(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        source_completion_evidence_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
    ) -> ProjectDirectorConfirmedPlanQueueResolution:
        """Revalidate completion and resolve `task_ids[source_index + 1]`."""

        try:
            with self._task_repository.session.no_autoflush:
                evidence = self._revalidate_completion_evidence(
                    session_id=session_id,
                    project_id=project_id,
                    source_completion_evidence_id=source_completion_evidence_id,
                    source_task_id=source_task_id,
                    source_run_id=source_run_id,
                )
                source_task = self._load_task(source_task_id)
                if source_task is None:
                    raise _Blocked("plan_lineage_invalid")
                raw_source_draft_id = self._raw_source_draft_id(source_task_id)
                located_plan = self._parse_source_draft_id(raw_source_draft_id)

                try:
                    plan = self._plan_version_repository.get_by_id(
                        located_plan.plan_version_id
                    )
                except (TypeError, ValueError, ValidationError) as exc:
                    raise _Blocked("plan_lineage_invalid") from exc
                if (
                    plan is None
                    or plan.status != PlanVersionStatus.CONFIRMED
                    or plan.id != evidence.plan_version_id
                    or plan.id != located_plan.plan_version_id
                    or plan.version_no != located_plan.plan_version_no
                    or plan.version_no != evidence.plan_version_no
                    or plan.session_id != session_id
                    or plan.session_id != evidence.session_id
                    or plan.project_id is None
                    or plan.project_id != project_id
                    or plan.project_id != evidence.project_id
                    or not plan.proposed_tasks
                ):
                    raise _Blocked("plan_lineage_invalid")

                try:
                    record = (
                        self._task_creation_record_repository
                        .get_strict_by_plan_version_id(plan.id)
                    )
                except TaskCreationRecordConflictError as exc:
                    raise _Blocked("plan_creation_record_conflict") from exc
                except TaskCreationRecordInvalidError as exc:
                    raise _Blocked("plan_lineage_invalid") from exc
                if record is None:
                    raise _Blocked("plan_creation_record_missing")
                if (
                    record.id != evidence.task_creation_record_id
                    or record.plan_version_id != plan.id
                    or record.version_no != plan.version_no
                    or record.session_id != session_id
                    or record.session_id != evidence.session_id
                    or record.project_id != project_id
                    or record.project_id != evidence.project_id
                    or record.source_type != "project_director_plan_version"
                    or record.task_count != len(record.task_ids)
                    or record.task_count != len(plan.proposed_tasks)
                    or record.task_count <= 0
                ):
                    raise _Blocked("plan_lineage_invalid")

                source_occurrences = record.task_ids.count(source_task_id)
                if source_occurrences != 1:
                    raise _Blocked("source_task_not_in_plan_queue")
                source_index = record.task_ids.index(source_task_id)
                next_index = source_index + 1
                queue_exhausted = next_index == len(record.task_ids)
                next_task_id = (
                    None if queue_exhausted else record.task_ids[next_index]
                )

                expected_locator = f"pdv:{plan.id}:{plan.version_no}"
                queue_tasks = self._validate_complete_queue(
                    task_ids=record.task_ids,
                    project_id=project_id,
                    expected_locator=expected_locator,
                    next_task_id=next_task_id,
                )
                if queue_tasks[source_index] != source_task:
                    raise _Blocked("plan_lineage_invalid")

                if next_task_id is not None:
                    next_task = self._load_task(next_task_id)
                    if next_task is None:
                        raise _Blocked("next_task_missing")
                    if (
                        next_task != queue_tasks[next_index]
                        or next_task.project_id != project_id
                        or next_task.source_draft_id != expected_locator
                        or self._raw_source_draft_id(next_task_id)
                        != expected_locator
                    ):
                        raise _Blocked("plan_lineage_invalid")

                snapshot = self._build_snapshot(
                    evidence=evidence,
                    task_ids=record.task_ids,
                    source_task_id=source_task_id,
                    source_task_index=source_index,
                    next_task_id=next_task_id,
                    next_task_index=None if queue_exhausted else next_index,
                    queue_exhausted=queue_exhausted,
                )
                return ProjectDirectorConfirmedPlanQueueResolution(
                    status=(
                        "plan_queue_exhausted"
                        if queue_exhausted
                        else "next_task_resolved"
                    ),
                    snapshot=snapshot,
                    blocked_reasons=[],
                )
        except _Blocked as exc:
            return ProjectDirectorConfirmedPlanQueueResolution.blocked(*exc.reasons)

    def _revalidate_completion_evidence(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        source_completion_evidence_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
    ) -> ProjectDirectorSourceTaskCompletionEvidence:
        try:
            result = (
                self._completion_evidence_service
                .revalidate_persisted_source_task_completion_evidence(
                    source_completion_evidence_id=source_completion_evidence_id,
                    source_task_id=source_task_id,
                    source_run_id=source_run_id,
                )
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("source_completion_evidence_invalid") from exc
        if result.evidence is None:
            reason: ConfirmedPlanQueueBlockedReason = (
                "source_completion_evidence_missing"
                if "source_completion_evidence_missing" in result.blocked_reasons
                else "source_completion_evidence_invalid"
            )
            raise _Blocked(reason)
        evidence = result.evidence
        if (
            result.status != "evidence_revalidated"
            or result.blocked_reasons
            or evidence.completion_status != "completed"
            or evidence.source_completion_evidence_id
            != source_completion_evidence_id
            or evidence.source_task_id != source_task_id
            or evidence.source_success_run_id != source_run_id
            or evidence.product_runtime_git_write_allowed
        ):
            raise _Blocked("source_completion_evidence_invalid")
        if evidence.session_id != session_id or evidence.project_id != project_id:
            raise _Blocked("source_completion_evidence_scope_mismatch")
        return evidence

    def _validate_complete_queue(
        self,
        *,
        task_ids: list[UUID],
        project_id: UUID,
        expected_locator: str,
        next_task_id: UUID | None,
    ) -> list[Task]:
        tasks: list[Task] = []
        for task_id in task_ids:
            task = self._load_task(task_id)
            if task is None:
                if task_id == next_task_id:
                    raise _Blocked("next_task_missing")
                raise _Blocked("plan_lineage_invalid")
            if (
                task.project_id != project_id
                or task.source_draft_id != expected_locator
                or self._raw_source_draft_id(task_id) != expected_locator
            ):
                raise _Blocked("plan_lineage_invalid")
            tasks.append(task)
        return tasks

    def _load_task(self, task_id: UUID) -> Task | None:
        try:
            return self._task_repository.get_by_id(task_id)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("plan_lineage_invalid") from exc

    def _raw_source_draft_id(self, task_id: UUID) -> str | None:
        task_row = self._task_repository.session.get(TaskTable, task_id)
        if task_row is None:
            return None
        return task_row.source_draft_id

    @staticmethod
    def _parse_source_draft_id(value: str | None) -> _LocatedPlanVersion:
        if value is None:
            raise _Blocked("plan_lineage_invalid")
        match = _SOURCE_DRAFT_PATTERN.fullmatch(value)
        if match is None:
            raise _Blocked("plan_lineage_invalid")
        raw_plan_version_id, raw_version_no = match.groups()
        try:
            plan_version_id = UUID(raw_plan_version_id)
            version_no = int(raw_version_no, 10)
        except (TypeError, ValueError) as exc:
            raise _Blocked("plan_lineage_invalid") from exc
        if (
            str(plan_version_id).casefold() != raw_plan_version_id.casefold()
            or version_no <= 0
            or version_no > _SIGNED_64_BIT_MAX
        ):
            raise _Blocked("plan_lineage_invalid")
        return _LocatedPlanVersion(
            plan_version_id=plan_version_id,
            plan_version_no=version_no,
        )

    def _build_snapshot(
        self,
        *,
        evidence: ProjectDirectorSourceTaskCompletionEvidence,
        task_ids: list[UUID],
        source_task_id: UUID,
        source_task_index: int,
        next_task_id: UUID | None,
        next_task_index: int | None,
        queue_exhausted: bool,
    ) -> ProjectDirectorConfirmedPlanQueueSnapshot:
        payload = {
            "schema_version": CONFIRMED_PLAN_QUEUE_SCHEMA_VERSION,
            "source_completion_evidence_id": (
                evidence.source_completion_evidence_id
            ),
            "source_completion_evidence_fingerprint": (
                evidence.source_completion_evidence_fingerprint
            ),
            "session_id": evidence.session_id,
            "project_id": evidence.project_id,
            "plan_version_id": evidence.plan_version_id,
            "plan_version_no": evidence.plan_version_no,
            "task_creation_record_id": evidence.task_creation_record_id,
            "queue_task_ids": list(task_ids),
            "task_count": len(task_ids),
            "source_task_id": source_task_id,
            "source_task_index": source_task_index,
            "next_task_id": next_task_id,
            "next_task_index": next_task_index,
            "queue_exhausted": queue_exhausted,
        }
        queue_fingerprint = self._fingerprint(payload)
        try:
            return ProjectDirectorConfirmedPlanQueueSnapshot(
                **payload,
                queue_fingerprint=queue_fingerprint,
                product_runtime_git_write_allowed=False,
                forbidden_actions=list(_FORBIDDEN_ACTIONS),
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("plan_lineage_invalid") from exc

    def _require_shared_session(self) -> None:
        session = self._task_repository.session
        sessions = (
            self._completion_evidence_service._message_repository._session,
            self._plan_version_repository._session,
            self._task_creation_record_repository._session,
            self._task_repository.session,
        )
        if any(item is not session for item in sessions):
            raise ValueError("confirmed plan queue dependencies must share one session")

    @classmethod
    def _fingerprint(cls, payload: Any) -> str:
        canonical = json.dumps(
            cls._canonicalize(payload),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def _canonicalize(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): cls._canonicalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._canonicalize(item) for item in value]
        if isinstance(value, UUID):
            return str(value).lower()
        return value


__all__ = ("ProjectDirectorConfirmedPlanQueueResolver",)
