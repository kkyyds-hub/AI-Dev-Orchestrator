"""Materialize P25-G candidate manifests and exact-base readonly diffs."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import stat
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal
from uuid import UUID, uuid4, uuid5

try:
    import fcntl
except ImportError:  # pragma: no cover - unsupported platforms fail closed.
    fcntl = None  # type: ignore[assignment]

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.domain.project_director_bounded_rework_attempt_reservation import (
    ProjectDirectorBoundedReworkAttemptReservation,
)
from app.domain.project_director_bounded_rework_candidate_diff import (
    P25_BOUNDED_REWORK_CANDIDATE_DIFF_NAMESPACE,
    P25_BOUNDED_REWORK_CANDIDATE_DIFF_SCHEMA_VERSION,
    P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_SCHEMA_VERSION,
    P25_BOUNDED_REWORK_INTERNAL_MANIFEST_PATH,
    ProjectDirectorBoundedReworkCandidateDiff,
    ProjectDirectorBoundedReworkCandidateDiffEntry,
    ProjectDirectorBoundedReworkCandidateManifest,
    ProjectDirectorBoundedReworkCandidateManifestEntry,
    ProjectDirectorBoundedReworkWorkspaceBusinessEntry,
)
from app.domain.project_director_bounded_rework_contract import (
    BoundedReworkBlockedReason,
    path_is_within_scope,
)
from app.domain.project_director_bounded_rework_instruction_package import (
    ProjectDirectorBoundedReworkInstructionPackage,
)
from app.domain.project_director_bounded_rework_invocation_claim import (
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
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.services.project_director_bounded_rework_invocation_claim_service import (
    BoundedReworkWorkspaceInspectionError,
    BoundedReworkWorkspaceSnapshot,
    ProjectDirectorBoundedReworkInvocationClaimService,
    RevalidatedPersistedBoundedReworkInvocationClaim,
)
from app.services.project_director_bounded_rework_invocation_outcome_service import (
    P25_BOUNDED_REWORK_INVOCATION_OUTCOME_ACTION_TYPE,
)
from app.services.project_director_sandbox_candidate_diff_service import (
    ExactBaseCandidateDiffError,
    ExactBaseCandidateDiffInputEntry,
    ExactBaseCandidateDiffProjection,
    ProjectDirectorSandboxCandidateDiffService,
)


P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_SOURCE_DETAIL = (
    "p25_g_candidate_manifest_materialized"
)
P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_ACTION_TYPE = (
    "p25_bounded_rework_candidate_manifest_record"
)
P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_INTENT = (
    "bounded_rework_candidate_manifest"
)
P25_BOUNDED_REWORK_CANDIDATE_DIFF_SOURCE_DETAIL = (
    "p25_g_candidate_diff_generated"
)
P25_BOUNDED_REWORK_CANDIDATE_DIFF_ACTION_TYPE = (
    "p25_bounded_rework_candidate_diff_record"
)
P25_BOUNDED_REWORK_CANDIDATE_DIFF_INTENT = "bounded_rework_candidate_diff"

_INTERNAL_MANIFEST_TOP_LEVEL_FIELD = "p25_bounded_rework_candidate"
_P21_INTERNAL_MANIFEST_SCHEMA_VERSION = "p21-c-d.v1"
_MAX_INTERNAL_MANIFEST_BYTES = 256 * 1024
_MAX_DIFF_BYTES = 2 * 1024 * 1024
_MESSAGE_PAGE_SIZE = 200
_READ_CHUNK_BYTES = 64 * 1024
_MAX_WORKSPACE_ENTRIES = 256
_MAX_WORKSPACE_FILES = 21
_MAX_WORKSPACE_DIRECTORIES = 256
_MAX_WORKSPACE_FILE_BYTES = 256 * 1024
_MAX_WORKSPACE_TOTAL_BYTES = 2 * 1024 * 1024
_WORKSPACE_LOCK_TIMEOUT_SECONDS = 5.0
_WORKSPACE_LOCK_POLL_SECONDS = 0.05

_P25_G_FALSE_BOUNDARIES = (
    "product_runtime_git_write_allowed=false",
    "main_project_write_allowed=false",
    "patch_apply_allowed=false",
    "git_add_allowed=false",
    "git_commit_allowed=false",
    "git_push_allowed=false",
    "branch_operation_allowed=false",
    "pull_request_allowed=false",
    "merge_allowed=false",
    "ci_trigger_allowed=false",
    "reviewer_called=false",
    "task_created=false",
    "run_created=false",
)

CandidateDiffPreparationStatus = Literal[
    "candidate_diff_generated",
    "candidate_diff_non_convergence",
    "candidate_diff_replayed",
    "blocked",
]


@dataclass(frozen=True, slots=True)
class PreparedProjectDirectorBoundedReworkCandidateDiff:
    status: CandidateDiffPreparationStatus
    candidate_manifest: ProjectDirectorBoundedReworkCandidateManifest | None
    candidate_diff: ProjectDirectorBoundedReworkCandidateDiff | None
    manifest_message: ProjectDirectorMessage | None
    diff_message: ProjectDirectorMessage | None
    blocked_reasons: tuple[BoundedReworkBlockedReason, ...]
    recovery_required: bool = False
    human_escalation_required: bool = False


@dataclass(frozen=True, slots=True)
class RevalidatedProjectDirectorBoundedReworkCandidateDiff:
    package: ProjectDirectorBoundedReworkInstructionPackage | None
    reservation: ProjectDirectorBoundedReworkAttemptReservation | None
    invocation_claim: ProjectDirectorBoundedReworkInvocationClaim | None
    invocation_outcome: ProjectDirectorBoundedReworkInvocationOutcome | None
    outcome_message: ProjectDirectorMessage | None
    candidate_manifest: ProjectDirectorBoundedReworkCandidateManifest | None
    candidate_manifest_message: ProjectDirectorMessage | None
    candidate_diff: ProjectDirectorBoundedReworkCandidateDiff | None
    candidate_diff_message: ProjectDirectorMessage | None
    blocked_reasons: tuple[BoundedReworkBlockedReason, ...]


@dataclass(frozen=True, slots=True)
class _P25GLineage:
    current: RevalidatedPersistedBoundedReworkInvocationClaim
    outcome: ProjectDirectorBoundedReworkInvocationOutcome
    outcome_message: ProjectDirectorMessage
    claim: ProjectDirectorBoundedReworkInvocationClaim
    reservation: ProjectDirectorBoundedReworkAttemptReservation
    package: ProjectDirectorBoundedReworkInstructionPackage


@dataclass(frozen=True, slots=True)
class _PersistedP25GRecords:
    manifest: ProjectDirectorBoundedReworkCandidateManifest | None
    candidate_diff: ProjectDirectorBoundedReworkCandidateDiff | None
    manifest_message: ProjectDirectorMessage | None
    diff_message: ProjectDirectorMessage | None


@dataclass(frozen=True, slots=True)
class _ManifestFileState:
    content: bytes
    content_sha256: str
    stat_result: os.stat_result


@dataclass(frozen=True, slots=True)
class _WorkspaceBusinessIdentity:
    manifest_fingerprint: str
    content_fingerprint: str
    inventory: tuple[ProjectDirectorBoundedReworkWorkspaceBusinessEntry, ...]


@dataclass(frozen=True, slots=True)
class _ManifestWriteReceipt:
    state: _ManifestFileState
    replaced_by_call: bool


class _Blocked(RuntimeError):
    def __init__(self, reason: BoundedReworkBlockedReason) -> None:
        self.reason = reason
        super().__init__(reason)


class ProjectDirectorBoundedReworkCandidateDiffService:
    """Regenerate one immutable manifest/diff pair from three locators."""

    def __init__(
        self,
        *,
        message_repository: ProjectDirectorMessageRepository,
        claim_service: ProjectDirectorBoundedReworkInvocationClaimService,
        candidate_diff_service: ProjectDirectorSandboxCandidateDiffService | None = None,
    ) -> None:
        self._message_repository = message_repository
        self._claim_service = claim_service
        self._candidate_diff_service = (
            candidate_diff_service or ProjectDirectorSandboxCandidateDiffService()
        )
        if claim_service._message_repository is not message_repository:
            raise ValueError("P25-G dependencies must share one message repository")

    def regenerate_candidate_manifest_and_diff(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_outcome_message_id: UUID,
    ) -> PreparedProjectDirectorBoundedReworkCandidateDiff:
        """Regenerate from persisted lineage without invoking an executor or reviewer."""

        try:
            initial = self._load_lineage(
                session_id=session_id,
                source_task_id=source_task_id,
                source_outcome_message_id=source_outcome_message_id,
            )
            self._validate_outcome_gate(initial.outcome)
            records = self._load_persisted_records(
                session_id=session_id,
                source_outcome_id=initial.outcome.outcome_id,
            )
            if records.manifest is not None or records.candidate_diff is not None:
                self._validate_replay_records(records=records, lineage=initial)
        except _Blocked as exc:
            self._rollback_read_transaction()
            return self._blocked(exc.reason)
        except SQLAlchemyError:
            self._rollback_read_transaction()
            return self._blocked("persistence_failed")
        except (OSError, RuntimeError, TypeError, ValueError, ValidationError):
            self._rollback_read_transaction()
            return self._blocked("history_invalid")

        self._rollback_read_transaction()
        try:
            lock_descriptor = self._acquire_workspace_lock(initial)
        except (OSError, RuntimeError, TypeError, ValueError, _Blocked):
            self._rollback_read_transaction()
            return self._blocked("workspace_invalid")
        try:
            return self._regenerate_under_workspace_lock(
                initial=initial,
                lock_descriptor=lock_descriptor,
                session_id=session_id,
                source_task_id=source_task_id,
                source_outcome_message_id=source_outcome_message_id,
            )
        finally:
            self._release_workspace_lock(lock_descriptor)

    def revalidate_persisted_candidate_diff_for_review_reentry(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_candidate_diff_message_id: UUID,
    ) -> RevalidatedProjectDirectorBoundedReworkCandidateDiff:
        """Rebuild one persisted generated diff and revalidate current workspace state."""

        return self._revalidate_persisted_candidate_diff(
            session_id=session_id,
            source_task_id=source_task_id,
            source_candidate_diff_message_id=source_candidate_diff_message_id,
            validate_workspace=True,
            transaction_cleanup_mode="cleanup_local_read_transaction",
        )

    def revalidate_persisted_candidate_diff_lineage_for_review_persistence(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_candidate_diff_message_id: UUID,
    ) -> RevalidatedProjectDirectorBoundedReworkCandidateDiff:
        """Rebuild only immutable P25-G lineage for atomic P25-H persistence."""

        return self._revalidate_persisted_candidate_diff(
            session_id=session_id,
            source_task_id=source_task_id,
            source_candidate_diff_message_id=source_candidate_diff_message_id,
            validate_workspace=False,
            transaction_cleanup_mode="preserve_caller_transaction",
        )

    def _revalidate_persisted_candidate_diff(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_candidate_diff_message_id: UUID,
        validate_workspace: bool,
        transaction_cleanup_mode: Literal[
            "cleanup_local_read_transaction",
            "preserve_caller_transaction",
        ],
    ) -> RevalidatedProjectDirectorBoundedReworkCandidateDiff:
        transaction_active_on_entry = self._message_repository._session.in_transaction()
        if (
            transaction_cleanup_mode == "preserve_caller_transaction"
            and not transaction_active_on_entry
        ):
            return self._blocked_revalidation("persistence_failed")
        try:
            diff_message = self._message_repository.get_by_id(
                source_candidate_diff_message_id
            )
            if diff_message is None or len(diff_message.suggested_actions) != 1:
                raise _Blocked("authority_invalid")
            action = diff_message.suggested_actions[0]
            if (
                not isinstance(action, dict)
                or action.get("type") != P25_BOUNDED_REWORK_CANDIDATE_DIFF_ACTION_TYPE
                or action.get("schema_version")
                != P25_BOUNDED_REWORK_CANDIDATE_DIFF_SCHEMA_VERSION
            ):
                raise _Blocked("history_invalid")
            payload = dict(action)
            payload.pop("type", None)
            candidate_diff = ProjectDirectorBoundedReworkCandidateDiff.model_validate(
                payload
            )
            if (
                diff_message.id != source_candidate_diff_message_id
                or diff_message.session_id != session_id
                or diff_message.related_task_id != source_task_id
                or candidate_diff.candidate_diff_id
                != source_candidate_diff_message_id
                or candidate_diff.authority.session_id != session_id
                or candidate_diff.exact_task_id != source_task_id
                or not self._diff_message_valid(diff_message, candidate_diff)
            ):
                raise _Blocked("authority_invalid")

            lineage = self._load_lineage(
                session_id=session_id,
                source_task_id=source_task_id,
                source_outcome_message_id=candidate_diff.source_outcome_id,
            )
            self._validate_outcome_gate(lineage.outcome)
            records = self._load_persisted_records(
                session_id=session_id,
                source_outcome_id=candidate_diff.source_outcome_id,
            )
            if (
                records.manifest is None
                or records.candidate_diff is None
                or records.manifest_message is None
                or records.diff_message is None
                or records.candidate_diff != candidate_diff
                or records.diff_message != diff_message
            ):
                raise _Blocked("history_invalid")
            self._validate_replay_records(records=records, lineage=lineage)
            self._validate_review_reentry_candidate_diff(
                candidate_diff=records.candidate_diff,
                candidate_diff_message=records.diff_message,
                candidate_manifest=records.manifest,
                lineage=lineage,
                source_candidate_diff_message_id=source_candidate_diff_message_id,
            )
            if validate_workspace:
                self._validate_replay_workspace(records=records, lineage=lineage)
            return RevalidatedProjectDirectorBoundedReworkCandidateDiff(
                package=lineage.package,
                reservation=lineage.reservation,
                invocation_claim=lineage.claim,
                invocation_outcome=lineage.outcome,
                outcome_message=lineage.outcome_message,
                candidate_manifest=records.manifest,
                candidate_manifest_message=records.manifest_message,
                candidate_diff=records.candidate_diff,
                candidate_diff_message=records.diff_message,
                blocked_reasons=(),
            )
        except _Blocked as exc:
            return self._blocked_revalidation(exc.reason)
        except SQLAlchemyError:
            return self._blocked_revalidation("persistence_failed")
        except (OSError, RuntimeError, TypeError, ValueError, ValidationError):
            return self._blocked_revalidation(
                "workspace_invalid" if validate_workspace else "history_invalid"
            )
        finally:
            self._cleanup_revalidation_transaction(
                transaction_active_on_entry=transaction_active_on_entry,
                transaction_cleanup_mode=transaction_cleanup_mode,
            )

    def _regenerate_under_workspace_lock(
        self,
        *,
        initial: _P25GLineage,
        lock_descriptor: int,
        session_id: UUID,
        source_task_id: UUID,
        source_outcome_message_id: UUID,
    ) -> PreparedProjectDirectorBoundedReworkCandidateDiff:
        try:
            locked = self._load_lineage(
                session_id=session_id,
                source_task_id=source_task_id,
                source_outcome_message_id=source_outcome_message_id,
            )
            self._validate_outcome_gate(locked.outcome)
            if locked != initial:
                raise _Blocked("history_invalid")
            self._validate_workspace_lock_identity(lock_descriptor, locked)
            records = self._load_persisted_records(
                session_id=session_id,
                source_outcome_id=locked.outcome.outcome_id,
            )
            if records.manifest is not None or records.candidate_diff is not None:
                self._validate_replay_records(records=records, lineage=locked)
                self._validate_replay_workspace(records=records, lineage=locked)
                self._rollback_read_transaction()
                return self._replayed(records)
        except _Blocked as exc:
            self._rollback_read_transaction()
            return self._blocked(exc.reason)
        except SQLAlchemyError:
            self._rollback_read_transaction()
            return self._blocked("persistence_failed")
        except (OSError, RuntimeError, TypeError, ValueError, ValidationError):
            self._rollback_read_transaction()
            return self._blocked("history_invalid")

        self._rollback_read_transaction()
        manifest_path: Path | None = None
        original_manifest: _ManifestFileState | None = None
        written_manifest_bytes: bytes | None = None
        write_receipt: _ManifestWriteReceipt | None = None
        candidate_manifest: ProjectDirectorBoundedReworkCandidateManifest | None = None
        candidate_diff: ProjectDirectorBoundedReworkCandidateDiff | None = None
        before_snapshot: BoundedReworkWorkspaceSnapshot | None = None
        before_business_identity: _WorkspaceBusinessIdentity | None = None
        expected_business_entries: tuple[tuple[str, str | None], ...] | None = None
        try:
            prepared = self._prepare_filesystem_payloads(locked)
            (
                candidate_manifest,
                candidate_diff,
                manifest_path,
                original_manifest,
                written_manifest_bytes,
                before_snapshot,
                before_business_identity,
                expected_business_entries,
            ) = prepared
            self._validate_workspace_lock_identity(lock_descriptor, locked)
            write_receipt = self._compare_and_replace_manifest(
                path=manifest_path,
                expected=original_manifest,
                desired=written_manifest_bytes,
                mode=stat.S_IMODE(original_manifest.stat_result.st_mode),
            )
            self._validate_post_write_workspace(
                lineage=locked,
                before_snapshot=before_snapshot,
                before_business_identity=before_business_identity,
                expected_manifest_bytes=written_manifest_bytes,
                expected_business_entries=expected_business_entries,
            )
        except _Blocked as exc:
            self._rollback_read_transaction()
            return self._rollback_or_block(
                reason=exc.reason,
                manifest_path=manifest_path,
                original_manifest=original_manifest,
                written_manifest_bytes=written_manifest_bytes,
                write_receipt=write_receipt,
                lineage=locked,
                lock_descriptor=lock_descriptor,
                candidate_manifest=candidate_manifest,
                candidate_diff=candidate_diff,
            )
        except ExactBaseCandidateDiffError as exc:
            self._rollback_read_transaction()
            reason = exc.reason if exc.reason in {
                "scope_invalid",
                "workspace_invalid",
                "source_diff_mismatch",
            } else "source_diff_mismatch"
            return self._rollback_or_block(
                reason=reason,
                manifest_path=manifest_path,
                original_manifest=original_manifest,
                written_manifest_bytes=written_manifest_bytes,
                write_receipt=write_receipt,
                lineage=locked,
                lock_descriptor=lock_descriptor,
                candidate_manifest=candidate_manifest,
                candidate_diff=candidate_diff,
            )
        except (OSError, RuntimeError, TypeError, ValueError, ValidationError):
            self._rollback_read_transaction()
            return self._rollback_or_block(
                reason="workspace_invalid",
                manifest_path=manifest_path,
                original_manifest=original_manifest,
                written_manifest_bytes=written_manifest_bytes,
                write_receipt=write_receipt,
                lineage=locked,
                lock_descriptor=lock_descriptor,
                candidate_manifest=candidate_manifest,
                candidate_diff=candidate_diff,
            )

        self._rollback_read_transaction()
        assert candidate_manifest is not None
        assert candidate_diff is not None
        try:
            self._validate_workspace_lock_identity(lock_descriptor, locked)
            with self._message_repository.sqlite_immediate_transaction():
                final = self._load_lineage(
                    session_id=session_id,
                    source_task_id=source_task_id,
                    source_outcome_message_id=source_outcome_message_id,
                )
                self._validate_outcome_gate(final.outcome)
                if final != locked:
                    raise _Blocked("history_invalid")
                records = self._load_persisted_records(
                    session_id=session_id,
                    source_outcome_id=locked.outcome.outcome_id,
                )
                if records.manifest is not None or records.candidate_diff is not None:
                    if (
                        records.manifest != candidate_manifest
                        or records.candidate_diff != candidate_diff
                    ):
                        raise _Blocked("history_invalid")
                    self._validate_replay_records(records=records, lineage=final)
                    self._validate_replay_workspace(records=records, lineage=final)
                    result = self._replayed(records)
                else:
                    manifest_message = self._build_manifest_message(candidate_manifest)
                    persisted_manifest = self._message_repository.create(
                        manifest_message
                    )
                    if persisted_manifest != manifest_message:
                        raise _Blocked("persistence_failed")
                    diff_message = self._build_diff_message(candidate_diff)
                    persisted_diff = self._message_repository.create(diff_message)
                    if persisted_diff != diff_message:
                        raise _Blocked("persistence_failed")
                    result = PreparedProjectDirectorBoundedReworkCandidateDiff(
                        status=(
                            "candidate_diff_generated"
                            if candidate_diff.diff_status == "generated"
                            else "candidate_diff_non_convergence"
                        ),
                        candidate_manifest=candidate_manifest,
                        candidate_diff=candidate_diff,
                        manifest_message=persisted_manifest,
                        diff_message=persisted_diff,
                        blocked_reasons=(),
                    )
            return result
        except _Blocked as exc:
            self._message_repository._session.rollback()
            return self._rollback_or_block(
                reason=exc.reason,
                manifest_path=manifest_path,
                original_manifest=original_manifest,
                written_manifest_bytes=written_manifest_bytes,
                write_receipt=write_receipt,
                lineage=locked,
                lock_descriptor=lock_descriptor,
                candidate_manifest=candidate_manifest,
                candidate_diff=candidate_diff,
            )
        except (SQLAlchemyError, OSError, RuntimeError, TypeError, ValueError, ValidationError):
            self._message_repository._session.rollback()
            return self._rollback_or_block(
                reason="persistence_failed",
                manifest_path=manifest_path,
                original_manifest=original_manifest,
                written_manifest_bytes=written_manifest_bytes,
                write_receipt=write_receipt,
                lineage=locked,
                lock_descriptor=lock_descriptor,
                candidate_manifest=candidate_manifest,
                candidate_diff=candidate_diff,
            )

    def _acquire_workspace_lock(self, lineage: _P25GLineage) -> int:
        if (
            fcntl is None
            or not hasattr(fcntl, "flock")
            or not hasattr(os, "O_DIRECTORY")
            or not hasattr(os, "O_NOFOLLOW")
            or lineage.package.workspace_binding is None
        ):
            raise OSError("POSIX workspace locking is unavailable")
        if self._message_repository._session.in_transaction():
            raise OSError("workspace lock wait cannot hold a database transaction")
        workspace = Path(lineage.package.workspace_binding.workspace_path)
        lock_path = workspace / ".ai-project-director"
        try:
            if workspace.resolve(strict=True) != workspace:
                raise OSError("workspace path is not canonical")
            expected = lock_path.lstat()
            if (
                lock_path.resolve(strict=True) != lock_path
                or not stat.S_ISDIR(expected.st_mode)
                or stat.S_ISLNK(expected.st_mode)
            ):
                raise OSError("workspace lock directory identity is invalid")
            descriptor = os.open(
                lock_path,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            )
        except OSError:
            raise

        deadline = time.monotonic() + _WORKSPACE_LOCK_TIMEOUT_SECONDS
        try:
            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError as exc:
                    if exc.errno not in {errno.EACCES, errno.EAGAIN}:
                        raise
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise OSError(
                            errno.ETIMEDOUT,
                            "workspace materialization lock timed out",
                        ) from exc
                    time.sleep(min(_WORKSPACE_LOCK_POLL_SECONDS, remaining))
            opened = os.fstat(descriptor)
            current = lock_path.lstat()
            if (
                not stat.S_ISDIR(opened.st_mode)
                or stat.S_ISLNK(current.st_mode)
                or ProjectDirectorBoundedReworkCandidateDiffService._stat_identity(
                    opened
                )
                != ProjectDirectorBoundedReworkCandidateDiffService._stat_identity(
                    current
                )
                or lock_path.resolve(strict=True) != lock_path
            ):
                raise OSError("workspace lock directory changed during acquisition")
            return descriptor
        except BaseException:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(descriptor)
            raise

    @staticmethod
    def _release_workspace_lock(descriptor: int) -> None:
        try:
            if fcntl is not None:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                except OSError:
                    pass
        finally:
            os.close(descriptor)

    @staticmethod
    def _validate_workspace_lock_identity(
        descriptor: int,
        lineage: _P25GLineage,
    ) -> None:
        if lineage.package.workspace_binding is None:
            raise _Blocked("workspace_invalid")
        lock_path = (
            Path(lineage.package.workspace_binding.workspace_path)
            / ".ai-project-director"
        )
        try:
            opened = os.fstat(descriptor)
            current = lock_path.lstat()
            if (
                lock_path.resolve(strict=True) != lock_path
                or not stat.S_ISDIR(opened.st_mode)
                or not stat.S_ISDIR(current.st_mode)
                or stat.S_ISLNK(current.st_mode)
                or (opened.st_dev, opened.st_ino, stat.S_IFMT(opened.st_mode))
                != (current.st_dev, current.st_ino, stat.S_IFMT(current.st_mode))
            ):
                raise OSError("workspace lock directory identity changed")
        except OSError as exc:
            raise _Blocked("workspace_invalid") from exc

    def _prepare_filesystem_payloads(
        self,
        lineage: _P25GLineage,
    ) -> tuple[
        ProjectDirectorBoundedReworkCandidateManifest,
        ProjectDirectorBoundedReworkCandidateDiff,
        Path,
        _ManifestFileState,
        bytes,
        BoundedReworkWorkspaceSnapshot,
        _WorkspaceBusinessIdentity,
        tuple[tuple[str, str | None], ...],
    ]:
        package = lineage.package
        outcome = lineage.outcome
        if (
            package.repository_binding is None
            or package.workspace_binding is None
            or package.base_commit_sha is None
            or package.base_snapshot_fingerprint is None
            or package.source_candidate_diff_message_id is None
            or package.source_candidate_diff_sha256 is None
            or outcome.candidate_manifest_id is None
            or outcome.candidate_manifest_fingerprint is None
        ):
            raise _Blocked("history_invalid")
        repository_root = Path(package.repository_binding.repository_root)
        workspace_path = Path(package.workspace_binding.workspace_path)
        before_business_identity = self._workspace_business_identity(workspace_path)
        snapshot = self._snapshot_workspace(lineage.current)
        if (
            snapshot.manifest_fingerprint
            != outcome.workspace_after_manifest_fingerprint
            or snapshot.content_fingerprint
            != outcome.workspace_after_content_fingerprint
        ):
            raise _Blocked("workspace_invalid")
        business_entries = self._business_entries_from_outcome(outcome, snapshot)
        for path, _ in business_entries:
            if not any(
                path_is_within_scope(path, allowed)
                for allowed in package.allowed_scope_paths
            ) or any(
                path_is_within_scope(path, forbidden)
                for forbidden in package.forbidden_scope_paths
            ):
                raise _Blocked("scope_invalid")
        candidate_inputs = tuple(
            ExactBaseCandidateDiffInputEntry(
                relative_path=path,
                operation=None,
                content_sha256=content_sha256,
                deleted=content_sha256 is None,
            )
            for path, content_sha256 in business_entries
        )
        identity_projection = (
            self._candidate_diff_service.build_readonly_diff_from_exact_base(
                repository_root=repository_root,
                workspace_path=workspace_path,
                base_commit_sha=package.base_commit_sha,
                candidate_entries=candidate_inputs,
                max_diff_bytes=_MAX_DIFF_BYTES,
                render_unified_diff=False,
            )
        )
        changed_files = tuple(
            ProjectDirectorBoundedReworkCandidateManifestEntry(
                relative_path=item.relative_path,
                operation=item.operation,
                content_sha256=item.candidate_content_sha256,
                deleted=not item.candidate_file_existed,
            )
            for item in identity_projection.diff_entries
        )
        recomputed_manifest_fingerprint = (
            ProjectDirectorBoundedReworkCandidateManifest.compute_candidate_manifest_identity_fingerprint(
                candidate_manifest_id=outcome.candidate_manifest_id,
                source_claim_id=lineage.claim.claim_id,
                source_claim_fingerprint=lineage.claim.claim_fingerprint,
                source_reservation_id=lineage.reservation.reservation_id,
                source_package_id=package.package_id,
                rework_attempt_index=lineage.claim.rework_attempt_index,
                workspace_after_manifest_fingerprint=(
                    outcome.workspace_after_manifest_fingerprint
                ),
                workspace_after_content_fingerprint=(
                    outcome.workspace_after_content_fingerprint
                ),
                changed_files=changed_files,
            )
        )
        if recomputed_manifest_fingerprint != outcome.candidate_manifest_fingerprint:
            raise _Blocked("source_diff_mismatch")
        manifest_replay_key = (
            ProjectDirectorBoundedReworkCandidateManifest.compute_replay_key(
                source_outcome_id=outcome.outcome_id,
                source_outcome_fingerprint=outcome.outcome_fingerprint,
                candidate_manifest_id=outcome.candidate_manifest_id,
                candidate_manifest_fingerprint=outcome.candidate_manifest_fingerprint,
                workspace_after_manifest_fingerprint=(
                    outcome.workspace_after_manifest_fingerprint
                ),
                workspace_after_content_fingerprint=(
                    outcome.workspace_after_content_fingerprint
                ),
                workspace_business_manifest_fingerprint=(
                    before_business_identity.manifest_fingerprint
                ),
                workspace_business_content_fingerprint=(
                    before_business_identity.content_fingerprint
                ),
                workspace_business_inventory=before_business_identity.inventory,
                changed_files=changed_files,
            )
        )
        manifest_values: dict[str, Any] = {
            "schema_version": P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_SCHEMA_VERSION,
            "candidate_manifest_id": outcome.candidate_manifest_id,
            "candidate_manifest_fingerprint": outcome.candidate_manifest_fingerprint,
            "candidate_manifest_replay_key": manifest_replay_key,
            "created_at": outcome.created_at,
            "source_outcome_id": outcome.outcome_id,
            "source_outcome_fingerprint": outcome.outcome_fingerprint,
            "source_claim_id": lineage.claim.claim_id,
            "source_claim_fingerprint": lineage.claim.claim_fingerprint,
            "source_reservation_id": lineage.reservation.reservation_id,
            "source_reservation_fingerprint": (
                lineage.reservation.reservation_fingerprint
            ),
            "source_package_id": package.package_id,
            "source_package_fingerprint": package.package_fingerprint,
            "authority": package.authority,
            "exact_task_id": lineage.claim.exact_task_id,
            "exact_run_id": lineage.claim.exact_run_id,
            "rework_attempt_index": lineage.claim.rework_attempt_index,
            "rework_attempt_limit": lineage.claim.rework_attempt_limit,
            "base_commit_sha": package.base_commit_sha,
            "base_snapshot_fingerprint": package.base_snapshot_fingerprint,
            "workspace_before_manifest_fingerprint": (
                lineage.claim.workspace_before_manifest_fingerprint
            ),
            "workspace_before_content_fingerprint": (
                lineage.claim.workspace_before_content_fingerprint
            ),
            "workspace_after_manifest_fingerprint": (
                outcome.workspace_after_manifest_fingerprint
            ),
            "workspace_after_content_fingerprint": (
                outcome.workspace_after_content_fingerprint
            ),
            "workspace_business_manifest_fingerprint": (
                before_business_identity.manifest_fingerprint
            ),
            "workspace_business_content_fingerprint": (
                before_business_identity.content_fingerprint
            ),
            "workspace_business_inventory": before_business_identity.inventory,
            "changed_files": changed_files,
            "internal_manifest_file_path": P25_BOUNDED_REWORK_INTERNAL_MANIFEST_PATH,
        }
        manifest_path = workspace_path / P25_BOUNDED_REWORK_INTERNAL_MANIFEST_PATH
        original_manifest, original_payload = self._read_and_validate_internal_manifest(
            path=manifest_path,
            lineage=lineage,
        )
        projection_model = ProjectDirectorBoundedReworkCandidateManifest.model_construct(
            **manifest_values,
            internal_manifest_content_sha256="0" * 64,
        )
        projected_payload = projection_model.model_dump(
            mode="json",
            exclude={"internal_manifest_content_sha256"},
        )
        updated_payload = dict(original_payload)
        updated_payload[_INTERNAL_MANIFEST_TOP_LEVEL_FIELD] = projected_payload
        manifest_bytes = (
            json.dumps(
                updated_payload,
                sort_keys=True,
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
        if len(manifest_bytes) > _MAX_INTERNAL_MANIFEST_BYTES:
            raise _Blocked("workspace_invalid")
        candidate_manifest = ProjectDirectorBoundedReworkCandidateManifest(
            **manifest_values,
            internal_manifest_content_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        )
        projection = self._candidate_diff_service.build_readonly_diff_from_exact_base(
            repository_root=repository_root,
            workspace_path=workspace_path,
            base_commit_sha=package.base_commit_sha,
            candidate_entries=candidate_inputs,
            max_diff_bytes=_MAX_DIFF_BYTES,
            render_unified_diff=True,
        )
        identity_entries = tuple(
            (
                item.relative_path,
                item.operation,
                item.base_file_existed,
                item.candidate_file_existed,
                item.base_content_sha256,
                item.candidate_content_sha256,
            )
            for item in identity_projection.diff_entries
        )
        diff_entries = tuple(
            (
                item.relative_path,
                item.operation,
                item.base_file_existed,
                item.candidate_file_existed,
                item.base_content_sha256,
                item.candidate_content_sha256,
            )
            for item in projection.diff_entries
        )
        if identity_entries != diff_entries:
            raise _Blocked("workspace_invalid")
        candidate_diff = self._build_candidate_diff(
            lineage=lineage,
            candidate_manifest=candidate_manifest,
            projection=projection,
        )

        final_snapshot = self._snapshot_workspace(lineage.current)
        final_business_identity = self._workspace_business_identity(workspace_path)
        current_manifest, _ = self._read_and_validate_internal_manifest(
            path=manifest_path,
            lineage=lineage,
        )
        if (
            final_snapshot != snapshot
            or final_business_identity != before_business_identity
            or current_manifest.content != original_manifest.content
            or self._stat_identity(current_manifest.stat_result)
            != self._stat_identity(original_manifest.stat_result)
        ):
            raise _Blocked("workspace_invalid")
        return (
            candidate_manifest,
            candidate_diff,
            manifest_path,
            original_manifest,
            manifest_bytes,
            snapshot,
            before_business_identity,
            business_entries,
        )

    def _build_candidate_diff(
        self,
        *,
        lineage: _P25GLineage,
        candidate_manifest: ProjectDirectorBoundedReworkCandidateManifest,
        projection: ExactBaseCandidateDiffProjection,
    ) -> ProjectDirectorBoundedReworkCandidateDiff:
        package = lineage.package
        outcome = lineage.outcome
        assert package.source_candidate_diff_message_id is not None
        assert package.source_candidate_diff_sha256 is not None
        assert package.base_commit_sha is not None
        assert package.base_snapshot_fingerprint is not None
        entries = tuple(
            ProjectDirectorBoundedReworkCandidateDiffEntry(
                relative_path=item.relative_path,
                operation=item.operation,
                base_file_existed=item.base_file_existed,
                candidate_file_existed=item.candidate_file_existed,
                base_content_sha256=item.base_content_sha256,
                candidate_content_sha256=item.candidate_content_sha256,
                unified_diff=item.unified_diff,
                diff_bytes=item.diff_bytes,
            )
            for item in projection.diff_entries
        )
        new_diff_sha256 = hashlib.sha256(
            projection.unified_diff_text.encode("utf-8")
        ).hexdigest()
        if not projection.unified_diff_text:
            diff_status = "non_convergence"
            non_convergence_reason = "empty_diff"
        elif new_diff_sha256 == package.source_candidate_diff_sha256:
            diff_status = "non_convergence"
            non_convergence_reason = "unchanged_diff"
        else:
            diff_status = "generated"
            non_convergence_reason = None
        replay_key = ProjectDirectorBoundedReworkCandidateDiff.compute_replay_key(
            source_outcome_id=outcome.outcome_id,
            source_outcome_fingerprint=outcome.outcome_fingerprint,
            candidate_manifest_fingerprint=(
                candidate_manifest.candidate_manifest_fingerprint
            ),
            base_commit_sha=package.base_commit_sha,
            previous_diff_sha256=package.source_candidate_diff_sha256,
            new_diff_sha256=new_diff_sha256,
        )
        values = {
            "schema_version": P25_BOUNDED_REWORK_CANDIDATE_DIFF_SCHEMA_VERSION,
            "candidate_diff_id": uuid5(
                P25_BOUNDED_REWORK_CANDIDATE_DIFF_NAMESPACE,
                replay_key,
            ),
            "candidate_diff_replay_key": replay_key,
            "created_at": outcome.created_at,
            "diff_status": diff_status,
            "source_attempt_id": lineage.reservation.reservation_id,
            "source_outcome_id": outcome.outcome_id,
            "source_outcome_fingerprint": outcome.outcome_fingerprint,
            "source_claim_id": lineage.claim.claim_id,
            "source_reservation_id": lineage.reservation.reservation_id,
            "source_package_id": package.package_id,
            "candidate_manifest_id": candidate_manifest.candidate_manifest_id,
            "candidate_manifest_fingerprint": (
                candidate_manifest.candidate_manifest_fingerprint
            ),
            "authority": package.authority,
            "exact_task_id": lineage.claim.exact_task_id,
            "exact_run_id": lineage.claim.exact_run_id,
            "rework_attempt_index": lineage.claim.rework_attempt_index,
            "rework_attempt_limit": lineage.claim.rework_attempt_limit,
            "previous_diff_message_id": package.source_candidate_diff_message_id,
            "previous_diff_sha256": package.source_candidate_diff_sha256,
            "base_commit_sha": package.base_commit_sha,
            "base_snapshot_fingerprint": package.base_snapshot_fingerprint,
            "base_content_source": projection.base_content_source,
            "readonly_base_snapshot_verified": (
                projection.readonly_base_snapshot_verified
            ),
            "workspace_after_manifest_fingerprint": (
                outcome.workspace_after_manifest_fingerprint
            ),
            "workspace_after_content_fingerprint": (
                outcome.workspace_after_content_fingerprint
            ),
            "scope_paths": tuple(item.relative_path for item in entries),
            "diff_entries": entries,
            "unified_diff_text": projection.unified_diff_text,
            "new_diff_sha256": new_diff_sha256,
            "diff_bytes": projection.diff_bytes,
            "diff_file_count": projection.diff_file_count,
            "non_convergence_reason": non_convergence_reason,
        }
        draft = ProjectDirectorBoundedReworkCandidateDiff.model_construct(
            **values,
            candidate_diff_fingerprint="0" * 64,
        )
        return ProjectDirectorBoundedReworkCandidateDiff(
            **values,
            candidate_diff_fingerprint=draft.compute_fingerprint(),
        )

    def _load_lineage(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_outcome_message_id: UUID,
    ) -> _P25GLineage:
        message = self._message_repository.get_by_id(source_outcome_message_id)
        if message is None or len(message.suggested_actions) != 1:
            raise _Blocked("authority_invalid")
        action = message.suggested_actions[0]
        if (
            not isinstance(action, dict)
            or action.get("type")
            != P25_BOUNDED_REWORK_INVOCATION_OUTCOME_ACTION_TYPE
            or action.get("schema_version")
            != BOUNDED_REWORK_INVOCATION_OUTCOME_SCHEMA_VERSION
        ):
            raise _Blocked("history_invalid")
        payload = dict(action)
        payload.pop("type", None)
        outcome = ProjectDirectorBoundedReworkInvocationOutcome.model_validate(payload)
        if (
            outcome.outcome_id != source_outcome_message_id
            or message.id != outcome.outcome_id
            or message.session_id != session_id
            or message.related_task_id != source_task_id
            or outcome.authority.session_id != session_id
            or outcome.exact_task_id != source_task_id
        ):
            raise _Blocked("authority_invalid")
        current = self._claim_service.revalidate_persisted_bounded_rework_invocation_claim_for_outcome_persistence(
            session_id=session_id,
            source_task_id=source_task_id,
            source_claim_message_id=outcome.claim_id,
        )
        if current.blocked_reasons:
            raise _Blocked(current.blocked_reasons[0])
        if (
            current.outcome != outcome
            or current.outcome_message != message
            or current.claim is None
            or current.reservation is None
            or current.package is None
        ):
            raise _Blocked("history_invalid")
        return _P25GLineage(
            current=current,
            outcome=outcome,
            outcome_message=message,
            claim=current.claim,
            reservation=current.reservation,
            package=current.package,
        )

    @staticmethod
    def _validate_outcome_gate(outcome: ProjectDirectorBoundedReworkInvocationOutcome) -> None:
        if outcome.git_activity_detected or outcome.git_activity_kinds:
            raise _Blocked("git_boundary_violation")
        if outcome.human_escalation_required:
            raise _Blocked("human_escalation_required")
        if outcome.scope_validation_status != "valid":
            raise _Blocked("scope_invalid")
        if outcome.side_effect_state != "observed":
            raise _Blocked("workspace_invalid")
        required = (
            outcome.outcome_status == "returned",
            outcome.executor_attempted,
            outcome.executor_started,
            outcome.executor_returned,
            not outcome.executor_raised,
            outcome.executor_result_valid,
            not outcome.recovery_required,
            outcome.candidate_files_changed,
            outcome.candidate_manifest_id is not None,
            outcome.candidate_manifest_fingerprint is not None,
            bool(outcome.declared_changed_paths),
            bool(outcome.observed_changed_paths),
            outcome.declared_changed_paths == outcome.observed_changed_paths,
            outcome.workspace_after_manifest_fingerprint is not None,
            outcome.workspace_after_content_fingerprint is not None,
        )
        if not all(required):
            raise _Blocked("history_invalid")

    def _snapshot_workspace(
        self,
        current: RevalidatedPersistedBoundedReworkInvocationClaim,
    ) -> BoundedReworkWorkspaceSnapshot:
        try:
            return self._claim_service.inspect_revalidated_bounded_rework_workspace(
                current,
                observe_out_of_scope_files=True,
            )
        except BoundedReworkWorkspaceInspectionError as exc:
            raise _Blocked(exc.reason) from exc

    def _business_entries_from_outcome(
        self,
        outcome: ProjectDirectorBoundedReworkInvocationOutcome,
        snapshot: BoundedReworkWorkspaceSnapshot,
    ) -> tuple[tuple[str, str | None], ...]:
        by_path = {item.path: item for item in snapshot.file_entries}
        entries: list[tuple[str, str | None]] = []
        for path in outcome.observed_changed_paths:
            if self._is_internal_path(path):
                raise _Blocked("scope_invalid")
            current = by_path.get(path)
            entries.append((path, current.content_sha256 if current else None))
        return tuple(entries)

    def _read_and_validate_internal_manifest(
        self,
        *,
        path: Path,
        lineage: _P25GLineage,
    ) -> tuple[_ManifestFileState, dict[str, Any]]:
        expected_workspace = Path(lineage.package.workspace_binding.workspace_path)
        expected_path = expected_workspace / P25_BOUNDED_REWORK_INTERNAL_MANIFEST_PATH
        if path != expected_path:
            raise _Blocked("workspace_invalid")
        state = self._read_manifest_state(path)
        try:
            payload = json.loads(state.content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise _Blocked("workspace_invalid") from exc
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != _P21_INTERNAL_MANIFEST_SCHEMA_VERSION
            or payload.get("internal_manifest_only") is not True
            or payload.get("session_id") != str(lineage.outcome.authority.session_id)
            or payload.get("source_task_id") != str(lineage.outcome.exact_task_id)
            or payload.get("workspace_path") != expected_workspace.as_posix()
            or payload.get("manifest_file_path") != expected_path.as_posix()
        ):
            raise _Blocked("workspace_invalid")
        return state, payload

    @staticmethod
    def _read_manifest_state(path: Path) -> _ManifestFileState:
        try:
            expected = path.lstat()
            if (
                not stat.S_ISREG(expected.st_mode)
                or stat.S_ISLNK(expected.st_mode)
                or expected.st_nlink != 1
                or expected.st_size > _MAX_INTERNAL_MANIFEST_BYTES
                or path.resolve(strict=True) != path
            ):
                raise OSError("invalid internal manifest identity")
            flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(path, flags)
            chunks: list[bytes] = []
            total = 0
            try:
                opened = os.fstat(descriptor)
                if ProjectDirectorBoundedReworkCandidateDiffService._stat_identity(
                    expected
                ) != ProjectDirectorBoundedReworkCandidateDiffService._stat_identity(
                    opened
                ):
                    raise OSError("internal manifest changed before read")
                while True:
                    chunk = os.read(descriptor, _READ_CHUNK_BYTES)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > _MAX_INTERNAL_MANIFEST_BYTES:
                        raise OSError("internal manifest exceeded read limit")
                    chunks.append(chunk)
                after = os.fstat(descriptor)
            finally:
                os.close(descriptor)
            if (
                total != expected.st_size
                or ProjectDirectorBoundedReworkCandidateDiffService._stat_identity(
                    expected
                )
                != ProjectDirectorBoundedReworkCandidateDiffService._stat_identity(after)
            ):
                raise OSError("internal manifest changed during read")
        except OSError as exc:
            raise _Blocked("workspace_invalid") from exc
        content = b"".join(chunks)
        return _ManifestFileState(
            content=content,
            content_sha256=hashlib.sha256(content).hexdigest(),
            stat_result=expected,
        )

    @classmethod
    def _compare_and_replace_manifest(
        cls,
        *,
        path: Path,
        expected: _ManifestFileState,
        desired: bytes,
        mode: int,
    ) -> _ManifestWriteReceipt:
        temporary = path.parent / f".{path.name}.p25g-{uuid4().hex}.tmp"
        descriptor: int | None = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(temporary, flags, mode)
            os.fchmod(descriptor, mode)
            written = 0
            while written < len(desired):
                chunk_written = os.write(descriptor, desired[written:])
                if chunk_written <= 0:
                    raise OSError("internal manifest atomic write made no progress")
                written += chunk_written
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            current = cls._read_manifest_state(path)
            desired_sha256 = hashlib.sha256(desired).hexdigest()
            if (
                current.content == desired
                and current.content_sha256 == desired_sha256
            ):
                return _ManifestWriteReceipt(
                    state=current,
                    replaced_by_call=False,
                )
            if (
                current.content != expected.content
                or current.content_sha256 != expected.content_sha256
                or cls._stat_identity(current.stat_result)
                != cls._stat_identity(expected.stat_result)
            ):
                raise _Blocked("human_escalation_required")
            os.replace(temporary, path)
            directory_descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
            replaced = cls._read_manifest_state(path)
            if (
                replaced.content != desired
                or replaced.content_sha256 != desired_sha256
                or stat.S_IMODE(replaced.stat_result.st_mode) != mode
                or replaced.stat_result.st_nlink != 1
            ):
                raise OSError("internal manifest replace verification failed")
            return _ManifestWriteReceipt(
                state=replaced,
                replaced_by_call=True,
            )
        finally:
            if descriptor is not None:
                os.close(descriptor)
            temporary.unlink(missing_ok=True)

    def _validate_post_write_workspace(
        self,
        *,
        lineage: _P25GLineage,
        before_snapshot: BoundedReworkWorkspaceSnapshot,
        before_business_identity: _WorkspaceBusinessIdentity,
        expected_manifest_bytes: bytes,
        expected_business_entries: tuple[tuple[str, str | None], ...],
    ) -> None:
        after_snapshot = self._snapshot_workspace(lineage.current)
        workspace = Path(lineage.package.workspace_binding.workspace_path)
        after_business_identity = self._workspace_business_identity(workspace)
        state = self._read_manifest_state(
            workspace / P25_BOUNDED_REWORK_INTERNAL_MANIFEST_PATH
        )
        if state.content != expected_manifest_bytes:
            raise _Blocked("workspace_invalid")
        before_business_files = tuple(
            item
            for item in before_snapshot.file_entries
            if not self._is_internal_path(item.path)
        )
        after_business_files = tuple(
            item
            for item in after_snapshot.file_entries
            if not self._is_internal_path(item.path)
        )
        if (
            before_business_files != after_business_files
            or before_business_identity != after_business_identity
            or self._business_entries_from_outcome(
                lineage.outcome,
                after_snapshot,
            ) != expected_business_entries
        ):
            raise _Blocked("workspace_invalid")

    def _workspace_business_identity(
        self,
        workspace: Path,
    ) -> _WorkspaceBusinessIdentity:
        try:
            workspace_stat = workspace.lstat()
            if (
                workspace.resolve(strict=True) != workspace
                or not stat.S_ISDIR(workspace_stat.st_mode)
                or stat.S_ISLNK(workspace_stat.st_mode)
            ):
                raise OSError("workspace path is not a canonical directory")
        except OSError as exc:
            raise _Blocked("workspace_invalid") from exc
        entries: list[ProjectDirectorBoundedReworkWorkspaceBusinessEntry] = []
        counters = {"entries": 0, "files": 0, "directories": 0, "bytes": 0}

        def walk(directory: Path) -> None:
            try:
                before = directory.stat(follow_symlinks=False)
                if (
                    not stat.S_ISDIR(before.st_mode)
                    or stat.S_ISLNK(before.st_mode)
                    or directory.resolve(strict=True) != directory
                ):
                    raise OSError("business directory identity is invalid")
                with os.scandir(directory) as iterator:
                    children = sorted(iterator, key=lambda item: item.name)
            except OSError as exc:
                raise _Blocked("workspace_invalid") from exc
            for child in children:
                path = Path(child.path)
                relative = path.relative_to(workspace).as_posix()
                try:
                    metadata = child.stat(follow_symlinks=False)
                    if path.resolve(strict=True) != path:
                        raise OSError("workspace entry is not canonical")
                except OSError as exc:
                    raise _Blocked("workspace_invalid") from exc
                if relative == ".ai-project-director":
                    if not stat.S_ISDIR(metadata.st_mode):
                        raise _Blocked("workspace_invalid")
                    self._validate_internal_control_tree(path)
                    continue
                if self._is_internal_path(relative):
                    raise _Blocked("workspace_invalid")
                counters["entries"] += 1
                if counters["entries"] > _MAX_WORKSPACE_ENTRIES:
                    raise _Blocked("workspace_invalid")
                if stat.S_ISLNK(metadata.st_mode):
                    raise _Blocked("workspace_invalid")
                if stat.S_ISDIR(metadata.st_mode):
                    counters["directories"] += 1
                    if counters["directories"] > _MAX_WORKSPACE_DIRECTORIES:
                        raise _Blocked("workspace_invalid")
                    entries.append(
                        ProjectDirectorBoundedReworkWorkspaceBusinessEntry(
                            relative_path=relative,
                            entry_type="directory",
                        )
                    )
                    walk(path)
                elif stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1:
                    file_size, content_sha256 = self._hash_business_regular_file(
                        path,
                        expected=metadata,
                    )
                    counters["files"] += 1
                    counters["bytes"] += file_size
                    if (
                        counters["files"] > _MAX_WORKSPACE_FILES
                        or counters["bytes"] > _MAX_WORKSPACE_TOTAL_BYTES
                    ):
                        raise _Blocked("workspace_invalid")
                    entries.append(
                        ProjectDirectorBoundedReworkWorkspaceBusinessEntry(
                            relative_path=relative,
                            entry_type="file",
                            file_size=file_size,
                            content_sha256=content_sha256,
                        )
                    )
                else:
                    raise _Blocked("workspace_invalid")
            try:
                after = directory.stat(follow_symlinks=False)
            except OSError as exc:
                raise _Blocked("workspace_invalid") from exc
            if self._stat_identity(before) != self._stat_identity(after):
                raise _Blocked("workspace_invalid")

        try:
            walk(workspace)
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("workspace_invalid") from exc
        inventory = tuple(sorted(entries, key=lambda item: item.relative_path))
        return _WorkspaceBusinessIdentity(
            manifest_fingerprint=(
                ProjectDirectorBoundedReworkCandidateManifest.compute_workspace_business_manifest_fingerprint(
                    inventory
                )
            ),
            content_fingerprint=(
                ProjectDirectorBoundedReworkCandidateManifest.compute_workspace_business_content_fingerprint(
                    inventory
                )
            ),
            inventory=inventory,
        )

    @staticmethod
    def _validate_internal_control_tree(path: Path) -> None:
        try:
            before = path.stat(follow_symlinks=False)
            if (
                not stat.S_ISDIR(before.st_mode)
                or stat.S_ISLNK(before.st_mode)
                or path.resolve(strict=True) != path
            ):
                raise OSError("internal control directory identity is invalid")
            with os.scandir(path) as iterator:
                children = list(iterator)
            if len(children) != 1 or children[0].name != "workspace-manifest.json":
                raise OSError("internal control directory has unexpected entries")
            manifest_path = Path(children[0].path)
            manifest_stat = children[0].stat(follow_symlinks=False)
            if (
                not stat.S_ISREG(manifest_stat.st_mode)
                or stat.S_ISLNK(manifest_stat.st_mode)
                or manifest_stat.st_nlink != 1
                or manifest_stat.st_size > _MAX_INTERNAL_MANIFEST_BYTES
                or manifest_path.resolve(strict=True) != manifest_path
            ):
                raise OSError("internal manifest identity is invalid")
            after = path.stat(follow_symlinks=False)
            if ProjectDirectorBoundedReworkCandidateDiffService._stat_identity(
                before
            ) != ProjectDirectorBoundedReworkCandidateDiffService._stat_identity(after):
                raise OSError("internal control directory changed during inspection")
        except OSError as exc:
            raise _Blocked("workspace_invalid") from exc

    @staticmethod
    def _hash_business_regular_file(
        path: Path,
        *,
        expected: os.stat_result,
    ) -> tuple[int, str]:
        if expected.st_size > _MAX_WORKSPACE_FILE_BYTES:
            raise _Blocked("workspace_invalid")
        flags = os.O_RDONLY
        if not hasattr(os, "O_NOFOLLOW"):
            raise _Blocked("workspace_invalid")
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
                or ProjectDirectorBoundedReworkCandidateDiffService._stat_identity(
                    expected
                )
                != ProjectDirectorBoundedReworkCandidateDiffService._stat_identity(
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
            or ProjectDirectorBoundedReworkCandidateDiffService._stat_identity(
                expected
            )
            != ProjectDirectorBoundedReworkCandidateDiffService._stat_identity(after)
        ):
            raise _Blocked("workspace_invalid")
        return read_bytes, digest.hexdigest()

    def _load_persisted_records(
        self,
        *,
        session_id: UUID,
        source_outcome_id: UUID,
    ) -> _PersistedP25GRecords:
        manifests: list[
            tuple[ProjectDirectorBoundedReworkCandidateManifest, ProjectDirectorMessage]
        ] = []
        diffs: list[
            tuple[ProjectDirectorBoundedReworkCandidateDiff, ProjectDirectorMessage]
        ] = []
        for message in self._iter_session_messages(session_id):
            action = (
                message.suggested_actions[0]
                if len(message.suggested_actions) == 1
                and isinstance(message.suggested_actions[0], dict)
                else None
            )
            marker = bool(
                message.intent
                in {
                    P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_INTENT,
                    P25_BOUNDED_REWORK_CANDIDATE_DIFF_INTENT,
                }
                or message.source_detail
                in {
                    P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_SOURCE_DETAIL,
                    P25_BOUNDED_REWORK_CANDIDATE_DIFF_SOURCE_DETAIL,
                }
                or (
                    action
                    and (
                        action.get("type")
                        in {
                            P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_ACTION_TYPE,
                            P25_BOUNDED_REWORK_CANDIDATE_DIFF_ACTION_TYPE,
                        }
                        or str(action.get("schema_version", "")).startswith(
                            "p25-g-"
                        )
                    )
                )
            )
            if not marker:
                continue
            if action is None:
                raise _Blocked("history_invalid")
            payload = dict(action)
            action_type = payload.pop("type", None)
            if action_type == P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_ACTION_TYPE:
                manifest = ProjectDirectorBoundedReworkCandidateManifest.model_validate(
                    payload
                )
                if not self._manifest_message_valid(message, manifest):
                    raise _Blocked("history_invalid")
                if manifest.source_outcome_id == source_outcome_id:
                    manifests.append((manifest, message))
            elif action_type == P25_BOUNDED_REWORK_CANDIDATE_DIFF_ACTION_TYPE:
                candidate_diff = ProjectDirectorBoundedReworkCandidateDiff.model_validate(
                    payload
                )
                if not self._diff_message_valid(message, candidate_diff):
                    raise _Blocked("history_invalid")
                if candidate_diff.source_outcome_id == source_outcome_id:
                    diffs.append((candidate_diff, message))
            else:
                raise _Blocked("history_invalid")
        if len(manifests) > 1 or len(diffs) > 1:
            raise _Blocked("history_invalid")
        if bool(manifests) != bool(diffs):
            raise _Blocked("history_invalid")
        return _PersistedP25GRecords(
            manifest=manifests[0][0] if manifests else None,
            candidate_diff=diffs[0][0] if diffs else None,
            manifest_message=manifests[0][1] if manifests else None,
            diff_message=diffs[0][1] if diffs else None,
        )

    def _validate_replay_records(
        self,
        *,
        records: _PersistedP25GRecords,
        lineage: _P25GLineage,
    ) -> None:
        manifest = records.manifest
        candidate_diff = records.candidate_diff
        if manifest is None or candidate_diff is None:
            raise _Blocked("history_invalid")
        outcome = lineage.outcome
        package = lineage.package
        if (
            manifest.source_outcome_id != outcome.outcome_id
            or manifest.created_at != outcome.created_at
            or manifest.candidate_manifest_id != outcome.candidate_manifest_id
            or manifest.candidate_manifest_fingerprint
            != outcome.candidate_manifest_fingerprint
            or manifest.source_outcome_fingerprint != outcome.outcome_fingerprint
            or manifest.source_claim_id != lineage.claim.claim_id
            or manifest.source_claim_fingerprint
            != lineage.claim.claim_fingerprint
            or manifest.source_reservation_id != lineage.reservation.reservation_id
            or manifest.source_reservation_fingerprint
            != lineage.reservation.reservation_fingerprint
            or manifest.source_package_id != package.package_id
            or manifest.source_package_fingerprint != package.package_fingerprint
            or manifest.authority != outcome.authority
            or manifest.exact_task_id != lineage.claim.exact_task_id
            or manifest.exact_run_id != lineage.claim.exact_run_id
            or manifest.rework_attempt_index != lineage.claim.rework_attempt_index
            or manifest.rework_attempt_limit != lineage.claim.rework_attempt_limit
            or manifest.base_commit_sha != package.base_commit_sha
            or manifest.base_snapshot_fingerprint
            != package.base_snapshot_fingerprint
            or manifest.workspace_before_manifest_fingerprint
            != lineage.claim.workspace_before_manifest_fingerprint
            or manifest.workspace_before_content_fingerprint
            != lineage.claim.workspace_before_content_fingerprint
            or manifest.workspace_after_manifest_fingerprint
            != outcome.workspace_after_manifest_fingerprint
            or manifest.workspace_after_content_fingerprint
            != outcome.workspace_after_content_fingerprint
            or candidate_diff.source_outcome_fingerprint
            != outcome.outcome_fingerprint
            or candidate_diff.source_outcome_id != outcome.outcome_id
            or candidate_diff.created_at != outcome.created_at
            or candidate_diff.candidate_manifest_id
            != manifest.candidate_manifest_id
            or candidate_diff.candidate_manifest_fingerprint
            != manifest.candidate_manifest_fingerprint
            or candidate_diff.source_claim_id != lineage.claim.claim_id
            or candidate_diff.source_attempt_id
            != lineage.reservation.reservation_id
            or candidate_diff.source_reservation_id
            != lineage.reservation.reservation_id
            or candidate_diff.source_package_id != package.package_id
            or candidate_diff.authority != outcome.authority
            or candidate_diff.exact_task_id != lineage.claim.exact_task_id
            or candidate_diff.exact_run_id != lineage.claim.exact_run_id
            or candidate_diff.rework_attempt_index
            != lineage.claim.rework_attempt_index
            or candidate_diff.rework_attempt_limit
            != lineage.claim.rework_attempt_limit
            or candidate_diff.base_commit_sha != package.base_commit_sha
            or candidate_diff.base_snapshot_fingerprint
            != package.base_snapshot_fingerprint
            or candidate_diff.previous_diff_message_id
            != package.source_candidate_diff_message_id
            or candidate_diff.previous_diff_sha256
            != package.source_candidate_diff_sha256
            or candidate_diff.workspace_after_manifest_fingerprint
            != outcome.workspace_after_manifest_fingerprint
            or candidate_diff.workspace_after_content_fingerprint
            != outcome.workspace_after_content_fingerprint
            or tuple(item.relative_path for item in manifest.changed_files)
            != candidate_diff.scope_paths
        ):
            raise _Blocked("history_invalid")

    @staticmethod
    def _validate_review_reentry_candidate_diff(
        *,
        candidate_diff: ProjectDirectorBoundedReworkCandidateDiff,
        candidate_diff_message: ProjectDirectorMessage,
        candidate_manifest: ProjectDirectorBoundedReworkCandidateManifest,
        lineage: _P25GLineage,
        source_candidate_diff_message_id: UUID,
    ) -> None:
        if candidate_diff_message.id != source_candidate_diff_message_id:
            raise _Blocked("authority_invalid")
        if (
            candidate_diff.diff_status != "generated"
            or candidate_diff.non_convergence_reason is not None
            or not candidate_diff.unified_diff_text
            or not candidate_diff.diff_entries
            or candidate_diff.new_diff_sha256 == candidate_diff.previous_diff_sha256
        ):
            raise _Blocked("non_convergence")
        if (
            candidate_diff.source_outcome_id != lineage.outcome.outcome_id
            or candidate_diff.source_claim_id != lineage.claim.claim_id
            or candidate_diff.source_reservation_id
            != lineage.reservation.reservation_id
            or candidate_diff.source_package_id != lineage.package.package_id
            or candidate_diff.source_attempt_id != lineage.reservation.reservation_id
            or candidate_diff.candidate_manifest_id
            != candidate_manifest.candidate_manifest_id
            or candidate_diff.candidate_manifest_fingerprint
            != candidate_manifest.candidate_manifest_fingerprint
            or candidate_diff.base_commit_sha != lineage.package.base_commit_sha
            or candidate_diff.base_snapshot_fingerprint
            != lineage.package.base_snapshot_fingerprint
            or candidate_diff.exact_task_id != lineage.claim.exact_task_id
        ):
            raise _Blocked("history_invalid")
        if (
            candidate_diff.exact_run_id != lineage.claim.exact_run_id
            or candidate_diff.rework_attempt_index
            != lineage.package.rework_attempt_index
            or candidate_diff.rework_attempt_limit
            != lineage.package.rework_attempt_limit
        ):
            raise _Blocked("history_invalid")
        if candidate_diff.new_diff_sha256 != hashlib.sha256(
            candidate_diff.unified_diff_text.encode("utf-8")
        ).hexdigest():
            raise _Blocked("source_diff_mismatch")
        manifest_scope = tuple(
            entry.relative_path for entry in candidate_manifest.changed_files
        )
        diff_scope = tuple(
            entry.relative_path for entry in candidate_diff.diff_entries
        )
        if (
            candidate_diff.scope_paths != diff_scope
            or candidate_diff.scope_paths != manifest_scope
        ):
            raise _Blocked("source_diff_mismatch")
        if (
            candidate_diff.base_content_source != "exact_git_commit_object"
            or candidate_diff.readonly_base_snapshot_verified is not True
        ):
            raise _Blocked("source_diff_mismatch")

    def _validate_replay_workspace(
        self,
        *,
        records: _PersistedP25GRecords,
        lineage: _P25GLineage,
    ) -> None:
        manifest = records.manifest
        if manifest is None or lineage.package.workspace_binding is None:
            raise _Blocked("history_invalid")
        workspace = Path(lineage.package.workspace_binding.workspace_path)
        manifest_path = workspace / P25_BOUNDED_REWORK_INTERNAL_MANIFEST_PATH
        state = self._read_manifest_state(manifest_path)
        if state.content_sha256 != manifest.internal_manifest_content_sha256:
            raise _Blocked("workspace_invalid")
        try:
            payload = json.loads(state.content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise _Blocked("workspace_invalid") from exc
        expected_projection = manifest.model_dump(
            mode="json",
            exclude={"internal_manifest_content_sha256"},
        )
        if (
            not isinstance(payload, dict)
            or payload.get(_INTERNAL_MANIFEST_TOP_LEVEL_FIELD)
            != expected_projection
        ):
            raise _Blocked("workspace_invalid")
        snapshot = self._snapshot_workspace(lineage.current)
        by_path = {item.path: item for item in snapshot.file_entries}
        for entry in manifest.changed_files:
            current = by_path.get(entry.relative_path)
            if entry.deleted:
                if current is not None:
                    raise _Blocked("workspace_invalid")
            elif current is None or current.content_sha256 != entry.content_sha256:
                raise _Blocked("workspace_invalid")
        business_identity = self._workspace_business_identity(workspace)
        if (
            business_identity.inventory != manifest.workspace_business_inventory
            or business_identity.manifest_fingerprint
            != manifest.workspace_business_manifest_fingerprint
            or business_identity.content_fingerprint
            != manifest.workspace_business_content_fingerprint
        ):
            raise _Blocked("workspace_invalid")

    def _iter_session_messages(self, session_id: UUID) -> list[ProjectDirectorMessage]:
        messages: list[ProjectDirectorMessage] = []
        before_message_id: UUID | None = None
        while True:
            page, has_more = self._message_repository.list_by_session_id(
                session_id=session_id,
                limit=_MESSAGE_PAGE_SIZE,
                before_message_id=before_message_id,
            )
            messages.extend(page)
            if not has_more:
                return sorted(messages, key=lambda item: item.sequence_no)
            if not page:
                raise _Blocked("history_invalid")
            before_message_id = page[0].id

    def _build_manifest_message(
        self,
        manifest: ProjectDirectorBoundedReworkCandidateManifest,
    ) -> ProjectDirectorMessage:
        return ProjectDirectorMessage(
            id=manifest.candidate_manifest_id,
            session_id=manifest.authority.session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content=(
                "P25 bounded rework candidate manifest: "
                f"{manifest.candidate_manifest_id} ({len(manifest.changed_files)} files)"
            ),
            sequence_no=self._message_repository.get_next_sequence_no(
                session_id=manifest.authority.session_id
            ),
            intent=P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_INTENT,
            related_project_id=manifest.authority.project_id,
            related_task_id=manifest.exact_task_id,
            source=ProjectDirectorMessageSource.SYSTEM,
            source_detail=P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_SOURCE_DETAIL,
            suggested_actions=[
                {
                    "type": P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_ACTION_TYPE,
                    **manifest.model_dump(mode="json"),
                }
            ],
            requires_confirmation=False,
            risk_level=ProjectDirectorMessageRiskLevel.HIGH,
            forbidden_actions_detected=list(_P25_G_FALSE_BOUNDARIES),
            token_count=None,
            estimated_cost=None,
            created_at=manifest.created_at,
        )

    def _build_diff_message(
        self,
        candidate_diff: ProjectDirectorBoundedReworkCandidateDiff,
    ) -> ProjectDirectorMessage:
        return ProjectDirectorMessage(
            id=candidate_diff.candidate_diff_id,
            session_id=candidate_diff.authority.session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content=(
                "P25 bounded rework candidate diff: "
                f"{candidate_diff.candidate_diff_id} ({candidate_diff.diff_status})"
            ),
            sequence_no=self._message_repository.get_next_sequence_no(
                session_id=candidate_diff.authority.session_id
            ),
            intent=P25_BOUNDED_REWORK_CANDIDATE_DIFF_INTENT,
            related_project_id=candidate_diff.authority.project_id,
            related_task_id=candidate_diff.exact_task_id,
            source=ProjectDirectorMessageSource.SYSTEM,
            source_detail=P25_BOUNDED_REWORK_CANDIDATE_DIFF_SOURCE_DETAIL,
            suggested_actions=[
                {
                    "type": P25_BOUNDED_REWORK_CANDIDATE_DIFF_ACTION_TYPE,
                    **candidate_diff.model_dump(mode="json"),
                }
            ],
            requires_confirmation=False,
            risk_level=ProjectDirectorMessageRiskLevel.HIGH,
            forbidden_actions_detected=list(_P25_G_FALSE_BOUNDARIES),
            token_count=None,
            estimated_cost=None,
            created_at=candidate_diff.created_at,
        )

    @staticmethod
    def _manifest_message_valid(
        message: ProjectDirectorMessage,
        manifest: ProjectDirectorBoundedReworkCandidateManifest,
    ) -> bool:
        return bool(
            message.id == manifest.candidate_manifest_id
            and message.session_id == manifest.authority.session_id
            and message.related_project_id == manifest.authority.project_id
            and message.related_task_id == manifest.exact_task_id
            and message.created_at == manifest.created_at
            and message.role == ProjectDirectorMessageRole.ASSISTANT
            and message.source == ProjectDirectorMessageSource.SYSTEM
            and message.intent == P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_INTENT
            and message.source_detail
            == P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_SOURCE_DETAIL
            and message.content
            == (
                "P25 bounded rework candidate manifest: "
                f"{manifest.candidate_manifest_id} ({len(manifest.changed_files)} files)"
            )
            and message.suggested_actions
            == [
                {
                    "type": P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_ACTION_TYPE,
                    **manifest.model_dump(mode="json"),
                }
            ]
            and message.requires_confirmation is False
            and message.risk_level == ProjectDirectorMessageRiskLevel.HIGH
            and tuple(message.forbidden_actions_detected) == _P25_G_FALSE_BOUNDARIES
            and message.token_count is None
            and message.estimated_cost is None
        )

    @staticmethod
    def _diff_message_valid(
        message: ProjectDirectorMessage,
        candidate_diff: ProjectDirectorBoundedReworkCandidateDiff,
    ) -> bool:
        return bool(
            message.id == candidate_diff.candidate_diff_id
            and message.session_id == candidate_diff.authority.session_id
            and message.related_project_id == candidate_diff.authority.project_id
            and message.related_task_id == candidate_diff.exact_task_id
            and message.created_at == candidate_diff.created_at
            and message.role == ProjectDirectorMessageRole.ASSISTANT
            and message.source == ProjectDirectorMessageSource.SYSTEM
            and message.intent == P25_BOUNDED_REWORK_CANDIDATE_DIFF_INTENT
            and message.source_detail
            == P25_BOUNDED_REWORK_CANDIDATE_DIFF_SOURCE_DETAIL
            and message.content
            == (
                "P25 bounded rework candidate diff: "
                f"{candidate_diff.candidate_diff_id} ({candidate_diff.diff_status})"
            )
            and message.suggested_actions
            == [
                {
                    "type": P25_BOUNDED_REWORK_CANDIDATE_DIFF_ACTION_TYPE,
                    **candidate_diff.model_dump(mode="json"),
                }
            ]
            and message.requires_confirmation is False
            and message.risk_level == ProjectDirectorMessageRiskLevel.HIGH
            and tuple(message.forbidden_actions_detected) == _P25_G_FALSE_BOUNDARIES
            and message.token_count is None
            and message.estimated_cost is None
        )

    def _rollback_or_block(
        self,
        *,
        reason: BoundedReworkBlockedReason,
        manifest_path: Path | None,
        original_manifest: _ManifestFileState | None,
        written_manifest_bytes: bytes | None,
        write_receipt: _ManifestWriteReceipt | None,
        lineage: _P25GLineage,
        lock_descriptor: int,
        candidate_manifest: ProjectDirectorBoundedReworkCandidateManifest | None,
        candidate_diff: ProjectDirectorBoundedReworkCandidateDiff | None,
    ) -> PreparedProjectDirectorBoundedReworkCandidateDiff:
        try:
            self._validate_workspace_lock_identity(lock_descriptor, lineage)
            records = self._load_persisted_records(
                session_id=lineage.outcome.authority.session_id,
                source_outcome_id=lineage.outcome.outcome_id,
            )
            if records.manifest is not None or records.candidate_diff is not None:
                if (
                    candidate_manifest is not None
                    and candidate_diff is not None
                    and (
                        records.manifest != candidate_manifest
                        or records.candidate_diff != candidate_diff
                    )
                ):
                    raise _Blocked("history_invalid")
                self._validate_replay_records(records=records, lineage=lineage)
                self._validate_replay_workspace(records=records, lineage=lineage)
                self._rollback_read_transaction()
                return self._replayed(records)
            self._rollback_read_transaction()
        except (
            SQLAlchemyError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
            ValidationError,
        ):
            self._rollback_read_transaction()
            return self._blocked(
                "human_escalation_required",
                recovery_required=True,
                human_escalation_required=True,
            )
        if (
            manifest_path is None
            or original_manifest is None
            or written_manifest_bytes is None
        ):
            return self._blocked(reason)
        try:
            current = self._read_manifest_state(manifest_path)
            if (
                current.content_sha256 == original_manifest.content_sha256
                and current.content == original_manifest.content
                and self._stat_identity(current.stat_result)
                == self._stat_identity(original_manifest.stat_result)
            ):
                return self._blocked(reason)
            written_sha256 = hashlib.sha256(written_manifest_bytes).hexdigest()
            if (
                write_receipt is None
                or not write_receipt.replaced_by_call
                or current.content != written_manifest_bytes
                or current.content_sha256 != written_sha256
                or self._stat_identity(current.stat_result)
                != self._stat_identity(write_receipt.state.stat_result)
            ):
                raise OSError("internal manifest rollback ownership is absent")
            self._validate_workspace_lock_identity(lock_descriptor, lineage)
            self._compare_and_replace_manifest(
                path=manifest_path,
                expected=write_receipt.state,
                desired=original_manifest.content,
                mode=stat.S_IMODE(original_manifest.stat_result.st_mode),
            )
            restored = self._read_manifest_state(manifest_path)
            if (
                restored.content_sha256 != original_manifest.content_sha256
                or restored.content != original_manifest.content
                or stat.S_IMODE(restored.stat_result.st_mode)
                != stat.S_IMODE(original_manifest.stat_result.st_mode)
                or restored.stat_result.st_nlink != 1
            ):
                raise OSError("internal manifest rollback verification failed")
        except (OSError, RuntimeError, ValueError):
            return self._blocked(
                "human_escalation_required",
                recovery_required=True,
                human_escalation_required=True,
            )
        return self._blocked(reason)

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
    def _is_internal_path(path: str) -> bool:
        parts = PurePosixPath(path).parts
        return bool(
            parts
            and any(
                part
                in {
                    ".git",
                    ".ai-project-director",
                    ".ai-dev-orchestrator",
                    ".orchestrator",
                    "workspace-manifest.json",
                    "workspace_manifest.json",
                }
                for part in parts
            )
        )

    def _rollback_read_transaction(self) -> None:
        if self._message_repository._session.in_transaction():
            self._message_repository._session.rollback()

    def _cleanup_revalidation_transaction(
        self,
        *,
        transaction_active_on_entry: bool,
        transaction_cleanup_mode: Literal[
            "cleanup_local_read_transaction",
            "preserve_caller_transaction",
        ],
    ) -> None:
        if transaction_cleanup_mode != "cleanup_local_read_transaction":
            return
        if transaction_active_on_entry:
            return
        if self._message_repository._session.in_transaction():
            self._message_repository._session.rollback()

    @staticmethod
    def _replayed(
        records: _PersistedP25GRecords,
    ) -> PreparedProjectDirectorBoundedReworkCandidateDiff:
        return PreparedProjectDirectorBoundedReworkCandidateDiff(
            status="candidate_diff_replayed",
            candidate_manifest=records.manifest,
            candidate_diff=records.candidate_diff,
            manifest_message=records.manifest_message,
            diff_message=records.diff_message,
            blocked_reasons=(),
        )

    @staticmethod
    def _blocked(
        reason: BoundedReworkBlockedReason,
        *,
        recovery_required: bool = False,
        human_escalation_required: bool = False,
    ) -> PreparedProjectDirectorBoundedReworkCandidateDiff:
        return PreparedProjectDirectorBoundedReworkCandidateDiff(
            status="blocked",
            candidate_manifest=None,
            candidate_diff=None,
            manifest_message=None,
            diff_message=None,
            blocked_reasons=(reason,),
            recovery_required=recovery_required,
            human_escalation_required=human_escalation_required,
        )

    @staticmethod
    def _blocked_revalidation(
        reason: BoundedReworkBlockedReason,
    ) -> RevalidatedProjectDirectorBoundedReworkCandidateDiff:
        return RevalidatedProjectDirectorBoundedReworkCandidateDiff(
            package=None,
            reservation=None,
            invocation_claim=None,
            invocation_outcome=None,
            outcome_message=None,
            candidate_manifest=None,
            candidate_manifest_message=None,
            candidate_diff=None,
            candidate_diff_message=None,
            blocked_reasons=(reason,),
        )


__all__ = (
    "CandidateDiffPreparationStatus",
    "P25_BOUNDED_REWORK_CANDIDATE_DIFF_ACTION_TYPE",
    "P25_BOUNDED_REWORK_CANDIDATE_DIFF_INTENT",
    "P25_BOUNDED_REWORK_CANDIDATE_DIFF_SOURCE_DETAIL",
    "P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_ACTION_TYPE",
    "P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_INTENT",
    "P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_SOURCE_DETAIL",
    "PreparedProjectDirectorBoundedReworkCandidateDiff",
    "RevalidatedProjectDirectorBoundedReworkCandidateDiff",
    "ProjectDirectorBoundedReworkCandidateDiffService",
)
