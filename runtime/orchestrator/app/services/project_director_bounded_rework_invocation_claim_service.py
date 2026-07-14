"""Durable P25-E bounded rework invocation Claim preparation."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import secrets
import stat
from typing import Literal
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.domain._base import utc_now
from app.domain.project_director_bounded_rework_attempt_reservation import (
    ProjectDirectorBoundedReworkAttemptReservation,
)
from app.domain.project_director_bounded_rework_contract import (
    BoundedReworkBlockedReason,
    compute_p25_contract_sha256,
    path_is_within_scope,
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
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.services.project_director_bounded_rework_attempt_reservation_service import (
    ProjectDirectorBoundedReworkAttemptReservationService,
    RevalidatedPersistedBoundedReworkAttemptReservation,
)


P25_BOUNDED_REWORK_EXECUTOR_ADAPTER_KIND = (
    "bounded_sandbox_rework_executor.v1"
)
P25_BOUNDED_REWORK_INVOCATION_CLAIM_SOURCE_DETAIL = (
    "p25_bounded_rework_invocation_claimed"
)
P25_BOUNDED_REWORK_INVOCATION_CLAIM_ACTION_TYPE = (
    "p25_bounded_rework_invocation_claim_record"
)
P25_BOUNDED_REWORK_INVOCATION_CLAIM_INTENT = (
    "bounded_rework_invocation_claim"
)

_WORKSPACE_MANIFEST_SCHEMA_VERSION = "p25-e-workspace-manifest.v1"
_WORKSPACE_CONTENT_SCHEMA_VERSION = "p25-e-workspace-content.v1"
_INTERNAL_MANIFEST_PATH = ".ai-project-director/workspace-manifest.json"
_INTERNAL_CONTROL_NAMES = frozenset(
    {
        ".git",
        ".ai-project-director",
        ".ai-dev-orchestrator",
        ".orchestrator",
        "workspace-manifest.json",
        "workspace_manifest.json",
    }
)
_MAX_WORKSPACE_ENTRIES = 256
_MAX_WORKSPACE_FILES = 21
_MAX_WORKSPACE_FILE_BYTES = 256 * 1024
_MAX_WORKSPACE_TOTAL_BYTES = 2 * 1024 * 1024
_READ_CHUNK_BYTES = 64 * 1024

_FORMAL_FALSE_BOUNDARIES = (
    "executor_call_attempted=false",
    "executor_started=false",
    "executor_returned=false",
    "executor_raised=false",
    "executor_success_evidence_present=false",
    "sandbox_file_written_by_claim=false",
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

ClaimPreparationStatus = Literal[
    "claim_claimed",
    "claim_replayed",
    "blocked",
]


@dataclass(frozen=True, slots=True)
class PreparedProjectDirectorBoundedReworkInvocationClaim:
    status: ClaimPreparationStatus
    claim: ProjectDirectorBoundedReworkInvocationClaim | None
    message: ProjectDirectorMessage | None
    blocked_reasons: tuple[BoundedReworkBlockedReason, ...]


@dataclass(frozen=True, slots=True)
class _WorkspaceSnapshot:
    manifest_fingerprint: str
    content_fingerprint: str


class _Blocked(RuntimeError):
    def __init__(self, reason: BoundedReworkBlockedReason) -> None:
        self.reason = reason
        super().__init__(reason)


class ProjectDirectorBoundedReworkInvocationClaimService:
    """Append or safely replay one Claim without calling an executor."""

    def __init__(
        self,
        *,
        message_repository: ProjectDirectorMessageRepository,
        attempt_reservation_service: (
            ProjectDirectorBoundedReworkAttemptReservationService
        ),
    ) -> None:
        self._message_repository = message_repository
        self._attempt_reservation_service = attempt_reservation_service
        if (
            attempt_reservation_service._message_repository
            is not message_repository
        ):
            raise ValueError("P25-E dependencies must share one message repository")

    def claim_bounded_rework_invocation(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_reservation_message_id: UUID,
    ) -> PreparedProjectDirectorBoundedReworkInvocationClaim:
        """Claim from three locators; all semantic values come from persistence."""

        initial = self._attempt_reservation_service.revalidate_persisted_bounded_rework_attempt_reservation(
            session_id=session_id,
            source_task_id=source_task_id,
            source_reservation_message_id=source_reservation_message_id,
        )
        if initial.blocked_reasons:
            self._rollback_read_transaction()
            return self._blocked(initial.blocked_reasons[0])
        try:
            initial_snapshot = self._snapshot_for(initial)
        except _Blocked as exc:
            self._rollback_read_transaction()
            return self._blocked(exc.reason)
        except (OSError, RuntimeError, TypeError, ValueError):
            self._rollback_read_transaction()
            return self._blocked("workspace_invalid")

        self._rollback_read_transaction()
        try:
            with self._message_repository.sqlite_immediate_transaction():
                current = self._attempt_reservation_service.revalidate_persisted_bounded_rework_attempt_reservation(
                    session_id=session_id,
                    source_task_id=source_task_id,
                    source_reservation_message_id=(
                        source_reservation_message_id
                    ),
                )
                if current.blocked_reasons:
                    raise _Blocked(current.blocked_reasons[0])
                if current != initial:
                    raise _Blocked("history_invalid")
                current_snapshot = self._snapshot_for(current)
                if current_snapshot != initial_snapshot:
                    raise _Blocked("workspace_invalid")
                return self._claim_or_replay(
                    current=current,
                    snapshot=current_snapshot,
                )
        except _Blocked as exc:
            return self._blocked(exc.reason)
        except SQLAlchemyError:
            return self._blocked("persistence_failed")
        except (OSError, RuntimeError, TypeError, ValueError, ValidationError):
            return self._blocked("history_invalid")

    def _claim_or_replay(
        self,
        *,
        current: RevalidatedPersistedBoundedReworkAttemptReservation,
        snapshot: _WorkspaceSnapshot,
    ) -> PreparedProjectDirectorBoundedReworkInvocationClaim:
        reservation = current.reservation
        package = current.package
        if reservation is None or package is None:
            raise _Blocked("history_invalid")
        self._validate_claim_history(current)

        replay_key = ProjectDirectorBoundedReworkInvocationClaim.compute_claim_replay_key(
            reservation_id=reservation.reservation_id,
            reservation_token=reservation.reservation_token,
            package_id=reservation.package_id,
            exact_task_id=reservation.exact_task_id,
            exact_run_id=reservation.exact_run_id,
            invocation_ordinal=0,
        )
        exact = [
            item
            for item in current.claims
            if item.reservation_id == reservation.reservation_id
        ]
        conflicts = [
            item
            for item in current.claims
            if (
                item.exact_run_id == reservation.exact_run_id
                or item.package_id == reservation.package_id
                or (
                    item.exact_task_id == reservation.exact_task_id
                    and item.rework_attempt_index
                    == reservation.rework_attempt_index
                )
                or item.claim_replay_key == replay_key
            )
            and item.reservation_id != reservation.reservation_id
        ]
        if len(exact) > 1:
            raise _Blocked("history_invalid")
        if conflicts:
            raise _Blocked("authority_replayed")
        if exact:
            claim = exact[0]
            if (
                claim.claim_replay_key != replay_key
                or not self._claim_binds_current(
                    claim=claim,
                    reservation=reservation,
                    package=package,
                )
            ):
                raise _Blocked("authority_replayed")
            message = self._message_repository.get_by_id(claim.claim_id)
            if message is None or not self._claim_message_valid(
                message=message,
                claim=claim,
            ):
                raise _Blocked("history_invalid")
            outcomes = [
                item for item in current.outcomes if item.claim_id == claim.claim_id
            ]
            if not outcomes:
                return self._blocked(
                    "claim_without_outcome",
                    claim=claim,
                    message=message,
                )
            if len(outcomes) != 1:
                raise _Blocked("history_invalid")
            return PreparedProjectDirectorBoundedReworkInvocationClaim(
                status="claim_replayed",
                claim=claim,
                message=message,
                blocked_reasons=(),
            )

        claim = self._build_claim(
            reservation=reservation,
            package=package,
            snapshot=snapshot,
        )
        message = self._build_claim_message(claim)
        try:
            persisted = self._message_repository.create(message)
        except (TypeError, ValueError, ValidationError, SQLAlchemyError) as exc:
            raise _Blocked("persistence_failed") from exc
        if persisted != message:
            raise _Blocked("persistence_failed")
        return PreparedProjectDirectorBoundedReworkInvocationClaim(
            status="claim_claimed",
            claim=claim,
            message=persisted,
            blocked_reasons=(),
        )

    def _validate_claim_history(
        self,
        current: RevalidatedPersistedBoundedReworkAttemptReservation,
    ) -> None:
        reservations = {
            item.reservation_id: item for item in current.reservations
        }
        claims = {item.claim_id: item for item in current.claims}
        uniqueness_groups = (
            [item.reservation_id for item in current.claims],
            [item.exact_run_id for item in current.claims],
            [
                (item.package_id, item.rework_attempt_index)
                for item in current.claims
            ],
            [item.claim_id for item in current.outcomes],
        )
        if any(len(values) != len(set(values)) for values in uniqueness_groups):
            raise _Blocked("history_invalid")
        for claim in current.claims:
            reservation = reservations.get(claim.reservation_id)
            message = self._message_repository.get_by_id(claim.claim_id)
            package = next(
                (
                    item
                    for item in current.packages
                    if item.package_id == claim.package_id
                ),
                None,
            )
            if (
                reservation is None
                or package is None
                or not self._claim_binds_current(
                    claim=claim,
                    reservation=reservation,
                    package=package,
                )
                or message is None
                or not self._claim_message_valid(message=message, claim=claim)
            ):
                raise _Blocked("history_invalid")
        for outcome in current.outcomes:
            claim = claims.get(outcome.claim_id)
            if (
                claim is None
                or outcome.workspace_before_manifest_fingerprint
                != claim.workspace_before_manifest_fingerprint
                or outcome.workspace_before_content_fingerprint
                != claim.workspace_before_content_fingerprint
            ):
                raise _Blocked("history_invalid")

    @staticmethod
    def _claim_binds_current(
        *,
        claim: ProjectDirectorBoundedReworkInvocationClaim,
        reservation: ProjectDirectorBoundedReworkAttemptReservation,
        package: ProjectDirectorBoundedReworkInstructionPackage,
    ) -> bool:
        return bool(
            package.selected_model is not None
            and package.selected_role is not None
            and claim.reservation_fingerprint
            == reservation.reservation_fingerprint
            and claim.reservation_token == reservation.reservation_token
            and claim.package_id == reservation.package_id == package.package_id
            and claim.package_fingerprint
            == reservation.package_fingerprint
            == package.package_fingerprint
            and claim.authority == reservation.authority == package.authority
            and claim.exact_task_id == reservation.exact_task_id
            and claim.exact_run_id == reservation.exact_run_id
            and claim.rework_attempt_index == reservation.rework_attempt_index
            and claim.rework_attempt_limit == reservation.rework_attempt_limit
            and claim.executor_adapter_kind
            == P25_BOUNDED_REWORK_EXECUTOR_ADAPTER_KIND
            and claim.selected_model == package.selected_model
            and claim.selected_skills == package.selected_skills
            and claim.selected_role == package.selected_role
            and claim.invocation_ordinal == 0
        )

    @staticmethod
    def _build_claim(
        *,
        reservation: ProjectDirectorBoundedReworkAttemptReservation,
        package: ProjectDirectorBoundedReworkInstructionPackage,
        snapshot: _WorkspaceSnapshot,
    ) -> ProjectDirectorBoundedReworkInvocationClaim:
        if package.selected_model is None or package.selected_role is None:
            raise _Blocked("authority_invalid")
        values = {
            "claim_id": uuid4(),
            "claim_replay_key": ProjectDirectorBoundedReworkInvocationClaim.compute_claim_replay_key(
                reservation_id=reservation.reservation_id,
                reservation_token=reservation.reservation_token,
                package_id=reservation.package_id,
                exact_task_id=reservation.exact_task_id,
                exact_run_id=reservation.exact_run_id,
                invocation_ordinal=0,
            ),
            "claim_token": secrets.token_hex(32),
            "created_at": utc_now(),
            "claim_status": "claimed",
            "reservation_id": reservation.reservation_id,
            "reservation_fingerprint": reservation.reservation_fingerprint,
            "reservation_token": reservation.reservation_token,
            "package_id": reservation.package_id,
            "package_fingerprint": reservation.package_fingerprint,
            "authority": reservation.authority,
            "exact_task_id": reservation.exact_task_id,
            "exact_run_id": reservation.exact_run_id,
            "rework_attempt_index": reservation.rework_attempt_index,
            "rework_attempt_limit": reservation.rework_attempt_limit,
            "executor_adapter_kind": P25_BOUNDED_REWORK_EXECUTOR_ADAPTER_KIND,
            "selected_model": package.selected_model,
            "selected_skills": package.selected_skills,
            "selected_role": package.selected_role,
            "workspace_before_manifest_fingerprint": (
                snapshot.manifest_fingerprint
            ),
            "workspace_before_content_fingerprint": (
                snapshot.content_fingerprint
            ),
            "invocation_ordinal": 0,
            "executor_call_attempted": False,
            "executor_started": False,
            "executor_returned": False,
            "executor_raised": False,
            "executor_success_evidence_present": False,
            "sandbox_file_written_by_claim": False,
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
        draft = ProjectDirectorBoundedReworkInvocationClaim.model_construct(
            **values,
            claim_fingerprint="0" * 64,
        )
        return ProjectDirectorBoundedReworkInvocationClaim(
            **values,
            claim_fingerprint=draft.compute_fingerprint(),
        )

    def _build_claim_message(
        self,
        claim: ProjectDirectorBoundedReworkInvocationClaim,
    ) -> ProjectDirectorMessage:
        return ProjectDirectorMessage(
            id=claim.claim_id,
            session_id=claim.authority.session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content=f"P25 bounded rework invocation claimed: {claim.claim_id}",
            sequence_no=self._message_repository.get_next_sequence_no(
                session_id=claim.authority.session_id
            ),
            intent=P25_BOUNDED_REWORK_INVOCATION_CLAIM_INTENT,
            related_project_id=claim.authority.project_id,
            related_task_id=claim.exact_task_id,
            source=ProjectDirectorMessageSource.SYSTEM,
            source_detail=P25_BOUNDED_REWORK_INVOCATION_CLAIM_SOURCE_DETAIL,
            suggested_actions=[
                {
                    "type": P25_BOUNDED_REWORK_INVOCATION_CLAIM_ACTION_TYPE,
                    **claim.model_dump(mode="json"),
                }
            ],
            requires_confirmation=False,
            risk_level=ProjectDirectorMessageRiskLevel.HIGH,
            forbidden_actions_detected=list(_FORMAL_FALSE_BOUNDARIES),
            token_count=None,
            estimated_cost=None,
            created_at=claim.created_at,
        )

    @staticmethod
    def _claim_message_valid(
        *,
        message: ProjectDirectorMessage,
        claim: ProjectDirectorBoundedReworkInvocationClaim,
    ) -> bool:
        expected_action = {
            "type": P25_BOUNDED_REWORK_INVOCATION_CLAIM_ACTION_TYPE,
            **claim.model_dump(mode="json"),
        }
        return bool(
            message.id == claim.claim_id
            and message.created_at == claim.created_at
            and message.session_id == claim.authority.session_id
            and message.related_project_id == claim.authority.project_id
            and message.related_task_id == claim.exact_task_id
            and message.role == ProjectDirectorMessageRole.ASSISTANT
            and message.source == ProjectDirectorMessageSource.SYSTEM
            and message.intent == P25_BOUNDED_REWORK_INVOCATION_CLAIM_INTENT
            and message.source_detail
            == P25_BOUNDED_REWORK_INVOCATION_CLAIM_SOURCE_DETAIL
            and message.content
            == f"P25 bounded rework invocation claimed: {claim.claim_id}"
            and message.suggested_actions == [expected_action]
            and message.requires_confirmation is False
            and message.risk_level == ProjectDirectorMessageRiskLevel.HIGH
            and tuple(message.forbidden_actions_detected)
            == _FORMAL_FALSE_BOUNDARIES
            and message.token_count is None
            and message.estimated_cost is None
            and claim.claim_token not in message.content
            and claim.reservation_token not in message.content
        )

    @classmethod
    def _snapshot_for(
        cls,
        current: RevalidatedPersistedBoundedReworkAttemptReservation,
    ) -> _WorkspaceSnapshot:
        package = current.package
        if package is None or package.workspace_binding is None:
            raise _Blocked("workspace_invalid")
        binding = package.workspace_binding
        root = Path(binding.workspace_root)
        workspace = Path(binding.workspace_path)
        try:
            resolved_root = root.resolve(strict=True)
            resolved_workspace = workspace.resolve(strict=True)
            root_stat = root.lstat()
            workspace_stat = workspace.lstat()
            resolved_workspace.relative_to(resolved_root)
        except (OSError, RuntimeError, ValueError) as exc:
            raise _Blocked("workspace_invalid") from exc
        if (
            root.as_posix() != binding.workspace_root
            or workspace.as_posix() != binding.workspace_path
            or resolved_root != root
            or resolved_workspace != workspace
            or resolved_workspace == resolved_root
            or not stat.S_ISDIR(root_stat.st_mode)
            or not stat.S_ISDIR(workspace_stat.st_mode)
            or stat.S_ISLNK(root_stat.st_mode)
            or stat.S_ISLNK(workspace_stat.st_mode)
        ):
            raise _Blocked("workspace_invalid")

        manifest_entries: list[dict[str, object]] = []
        content_entries: list[dict[str, object]] = []
        counters = {"entries": 0, "files": 0, "bytes": 0}
        cls._walk_workspace(
            directory=workspace,
            workspace=workspace,
            allowed_scope_paths=package.allowed_scope_paths,
            manifest_entries=manifest_entries,
            content_entries=content_entries,
            counters=counters,
        )
        return _WorkspaceSnapshot(
            manifest_fingerprint=compute_p25_contract_sha256(
                {
                    "schema_version": _WORKSPACE_MANIFEST_SCHEMA_VERSION,
                    "entries": manifest_entries,
                }
            ),
            content_fingerprint=compute_p25_contract_sha256(
                {
                    "schema_version": _WORKSPACE_CONTENT_SCHEMA_VERSION,
                    "files": content_entries,
                }
            ),
        )

    @classmethod
    def _walk_workspace(
        cls,
        *,
        directory: Path,
        workspace: Path,
        allowed_scope_paths: tuple[str, ...],
        manifest_entries: list[dict[str, object]],
        content_entries: list[dict[str, object]],
        counters: dict[str, int],
    ) -> None:
        try:
            before = directory.stat(follow_symlinks=False)
            if (
                not stat.S_ISDIR(before.st_mode)
                or stat.S_ISLNK(before.st_mode)
                or directory.resolve(strict=True) != directory
            ):
                raise _Blocked("workspace_invalid")
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda item: item.name)
        except OSError as exc:
            raise _Blocked("workspace_invalid") from exc
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(workspace).as_posix()
            cls._validate_relative_path(relative)
            try:
                entry_stat = entry.stat(follow_symlinks=False)
                if path.resolve(strict=True) != path:
                    raise _Blocked("workspace_invalid")
            except OSError as exc:
                raise _Blocked("workspace_invalid") from exc
            counters["entries"] += 1
            if counters["entries"] > _MAX_WORKSPACE_ENTRIES:
                raise _Blocked("workspace_invalid")
            if stat.S_ISLNK(entry_stat.st_mode):
                raise _Blocked("workspace_invalid")
            if stat.S_ISDIR(entry_stat.st_mode):
                cls._validate_control_path(relative, is_directory=True)
                manifest_entries.append(
                    {"path": relative, "type": "directory"}
                )
                cls._walk_workspace(
                    directory=path,
                    workspace=workspace,
                    allowed_scope_paths=allowed_scope_paths,
                    manifest_entries=manifest_entries,
                    content_entries=content_entries,
                    counters=counters,
                )
                continue
            if not stat.S_ISREG(entry_stat.st_mode):
                raise _Blocked("workspace_invalid")
            if entry_stat.st_nlink != 1:
                raise _Blocked("workspace_invalid")
            cls._validate_control_path(relative, is_directory=False)
            if relative != _INTERNAL_MANIFEST_PATH and not any(
                path_is_within_scope(relative, allowed)
                for allowed in allowed_scope_paths
            ):
                raise _Blocked("scope_invalid")
            size, content_sha256 = cls._hash_regular_file(
                path,
                expected=entry_stat,
            )
            counters["files"] += 1
            counters["bytes"] += size
            if (
                counters["files"] > _MAX_WORKSPACE_FILES
                or counters["bytes"] > _MAX_WORKSPACE_TOTAL_BYTES
            ):
                raise _Blocked("workspace_invalid")
            manifest_entries.append(
                {"path": relative, "type": "file", "size": size}
            )
            content_entries.append(
                {
                    "path": relative,
                    "content_sha256": content_sha256,
                    "size": size,
                }
            )
        try:
            after = directory.stat(follow_symlinks=False)
        except OSError as exc:
            raise _Blocked("workspace_invalid") from exc
        if cls._stat_identity(before) != cls._stat_identity(after):
            raise _Blocked("workspace_invalid")

    @staticmethod
    def _hash_regular_file(
        path: Path,
        *,
        expected: os.stat_result,
    ) -> tuple[int, str]:
        if expected.st_size > _MAX_WORKSPACE_FILE_BYTES:
            raise _Blocked("workspace_invalid")
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags)
        except OSError as exc:
            raise _Blocked("workspace_invalid") from exc
        digest = hashlib.sha256()
        read_bytes = 0
        try:
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_nlink != 1
                or ProjectDirectorBoundedReworkInvocationClaimService._stat_identity(
                    expected
                )
                != ProjectDirectorBoundedReworkInvocationClaimService._stat_identity(
                    opened
                )
            ):
                raise _Blocked("workspace_invalid")
            while True:
                chunk = os.read(descriptor, _READ_CHUNK_BYTES)
                if not chunk:
                    break
                read_bytes += len(chunk)
                if read_bytes > _MAX_WORKSPACE_FILE_BYTES:
                    raise _Blocked("workspace_invalid")
                digest.update(chunk)
            after = os.fstat(descriptor)
        except OSError as exc:
            raise _Blocked("workspace_invalid") from exc
        finally:
            os.close(descriptor)
        if (
            read_bytes != expected.st_size
            or ProjectDirectorBoundedReworkInvocationClaimService._stat_identity(
                expected
            )
            != ProjectDirectorBoundedReworkInvocationClaimService._stat_identity(
                after
            )
        ):
            raise _Blocked("workspace_invalid")
        return read_bytes, digest.hexdigest()

    @staticmethod
    def _stat_identity(value: os.stat_result) -> tuple[int, ...]:
        return (
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_nlink,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )

    @staticmethod
    def _validate_relative_path(value: str) -> None:
        path = PurePosixPath(value)
        if (
            not value
            or value != path.as_posix()
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise _Blocked("workspace_invalid")

    @staticmethod
    def _validate_control_path(value: str, *, is_directory: bool) -> None:
        parts = PurePosixPath(value).parts
        if not parts:
            raise _Blocked("workspace_invalid")
        if parts[0] not in _INTERNAL_CONTROL_NAMES:
            return
        if is_directory and value == ".ai-project-director":
            return
        if not is_directory and value == _INTERNAL_MANIFEST_PATH:
            return
        raise _Blocked("workspace_invalid")

    def _rollback_read_transaction(self) -> None:
        if self._message_repository._session.in_transaction():
            self._message_repository._session.rollback()

    @staticmethod
    def _blocked(
        reason: BoundedReworkBlockedReason,
        *,
        claim: ProjectDirectorBoundedReworkInvocationClaim | None = None,
        message: ProjectDirectorMessage | None = None,
    ) -> PreparedProjectDirectorBoundedReworkInvocationClaim:
        return PreparedProjectDirectorBoundedReworkInvocationClaim(
            status="blocked",
            claim=claim,
            message=message,
            blocked_reasons=(reason,),
        )


__all__ = (
    "ClaimPreparationStatus",
    "P25_BOUNDED_REWORK_EXECUTOR_ADAPTER_KIND",
    "P25_BOUNDED_REWORK_INVOCATION_CLAIM_ACTION_TYPE",
    "P25_BOUNDED_REWORK_INVOCATION_CLAIM_INTENT",
    "P25_BOUNDED_REWORK_INVOCATION_CLAIM_SOURCE_DETAIL",
    "PreparedProjectDirectorBoundedReworkInvocationClaim",
    "ProjectDirectorBoundedReworkInvocationClaimService",
)
