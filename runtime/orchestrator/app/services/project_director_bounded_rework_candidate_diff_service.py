"""Materialize P25-G candidate manifests and exact-base readonly diffs."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.domain._base import utc_now
from app.domain.project_director_bounded_rework_attempt_reservation import (
    ProjectDirectorBoundedReworkAttemptReservation,
)
from app.domain.project_director_bounded_rework_candidate_diff import (
    P25_BOUNDED_REWORK_CANDIDATE_DIFF_SCHEMA_VERSION,
    P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_SCHEMA_VERSION,
    P25_BOUNDED_REWORK_INTERNAL_MANIFEST_PATH,
    ProjectDirectorBoundedReworkCandidateDiff,
    ProjectDirectorBoundedReworkCandidateDiffEntry,
    ProjectDirectorBoundedReworkCandidateManifest,
    ProjectDirectorBoundedReworkCandidateManifestEntry,
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
                self._validate_replay_workspace(records=records, lineage=initial)
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
        before_snapshot: BoundedReworkWorkspaceSnapshot | None = None
        before_inventory: tuple[tuple[str, str], ...] | None = None
        expected_business_entries: tuple[tuple[str, str | None], ...] | None = None
        try:
            prepared = self._prepare_filesystem_payloads(initial)
            (
                candidate_manifest,
                candidate_diff,
                manifest_path,
                original_manifest,
                written_manifest_bytes,
                before_snapshot,
                before_inventory,
                expected_business_entries,
            ) = prepared
            self._atomic_replace_manifest(
                path=manifest_path,
                content=written_manifest_bytes,
                mode=stat.S_IMODE(original_manifest.stat_result.st_mode),
            )
            self._validate_post_write_workspace(
                lineage=initial,
                before_snapshot=before_snapshot,
                before_inventory=before_inventory,
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
            )
        except (OSError, RuntimeError, TypeError, ValueError, ValidationError):
            self._rollback_read_transaction()
            return self._rollback_or_block(
                reason="workspace_invalid",
                manifest_path=manifest_path,
                original_manifest=original_manifest,
                written_manifest_bytes=written_manifest_bytes,
            )

        self._rollback_read_transaction()
        try:
            with self._message_repository.sqlite_immediate_transaction():
                final = self._load_lineage(
                    session_id=session_id,
                    source_task_id=source_task_id,
                    source_outcome_message_id=source_outcome_message_id,
                )
                self._validate_outcome_gate(final.outcome)
                if final != initial:
                    raise _Blocked("history_invalid")
                records = self._load_persisted_records(
                    session_id=session_id,
                    source_outcome_id=initial.outcome.outcome_id,
                )
                if records.manifest is not None or records.candidate_diff is not None:
                    if (
                        records.manifest != candidate_manifest
                        or records.candidate_diff != candidate_diff
                    ):
                        raise _Blocked("history_invalid")
                    self._validate_replay_records(records=records, lineage=final)
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
            )
        except (SQLAlchemyError, OSError, RuntimeError, TypeError, ValueError, ValidationError):
            self._message_repository._session.rollback()
            return self._rollback_or_block(
                reason="persistence_failed",
                manifest_path=manifest_path,
                original_manifest=original_manifest,
                written_manifest_bytes=written_manifest_bytes,
            )

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
        tuple[tuple[str, str], ...],
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
        before_inventory = self._workspace_inventory(workspace_path)

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
                changed_files=changed_files,
            )
        )
        manifest_values: dict[str, Any] = {
            "schema_version": P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_SCHEMA_VERSION,
            "candidate_manifest_id": outcome.candidate_manifest_id,
            "candidate_manifest_fingerprint": outcome.candidate_manifest_fingerprint,
            "candidate_manifest_replay_key": manifest_replay_key,
            "created_at": utc_now(),
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
        final_inventory = self._workspace_inventory(workspace_path)
        current_manifest, _ = self._read_and_validate_internal_manifest(
            path=manifest_path,
            lineage=lineage,
        )
        if (
            final_snapshot != snapshot
            or final_inventory != before_inventory
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
            before_inventory,
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
            "candidate_diff_id": uuid4(),
            "candidate_diff_replay_key": replay_key,
            "created_at": utc_now(),
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

    @staticmethod
    def _atomic_replace_manifest(*, path: Path, content: bytes, mode: int) -> None:
        temporary = path.parent / f".{path.name}.p25g-{uuid4().hex}.tmp"
        descriptor: int | None = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(temporary, flags, mode)
            os.fchmod(descriptor, mode)
            written = 0
            while written < len(content):
                chunk_written = os.write(descriptor, content[written:])
                if chunk_written <= 0:
                    raise OSError("internal manifest atomic write made no progress")
                written += chunk_written
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            os.replace(temporary, path)
            directory_descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        finally:
            if descriptor is not None:
                os.close(descriptor)
            temporary.unlink(missing_ok=True)

    def _validate_post_write_workspace(
        self,
        *,
        lineage: _P25GLineage,
        before_snapshot: BoundedReworkWorkspaceSnapshot,
        before_inventory: tuple[tuple[str, str], ...],
        expected_manifest_bytes: bytes,
        expected_business_entries: tuple[tuple[str, str | None], ...],
    ) -> None:
        after_snapshot = self._snapshot_workspace(lineage.current)
        workspace = Path(lineage.package.workspace_binding.workspace_path)
        after_inventory = self._workspace_inventory(workspace)
        state = self._read_manifest_state(
            workspace / P25_BOUNDED_REWORK_INTERNAL_MANIFEST_PATH
        )
        if state.content != expected_manifest_bytes:
            raise _Blocked("workspace_invalid")
        before_business_files = tuple(
            item for item in before_snapshot.file_entries
            if item.path != P25_BOUNDED_REWORK_INTERNAL_MANIFEST_PATH
        )
        after_business_files = tuple(
            item for item in after_snapshot.file_entries
            if item.path != P25_BOUNDED_REWORK_INTERNAL_MANIFEST_PATH
        )
        before_business_inventory = tuple(
            item for item in before_inventory
            if item[0] != P25_BOUNDED_REWORK_INTERNAL_MANIFEST_PATH
        )
        after_business_inventory = tuple(
            item for item in after_inventory
            if item[0] != P25_BOUNDED_REWORK_INTERNAL_MANIFEST_PATH
        )
        if (
            before_business_files != after_business_files
            or before_business_inventory != after_business_inventory
            or self._business_entries_from_outcome(
                lineage.outcome,
                after_snapshot,
            ) != expected_business_entries
        ):
            raise _Blocked("workspace_invalid")

    def _workspace_inventory(self, workspace: Path) -> tuple[tuple[str, str], ...]:
        try:
            if workspace.resolve(strict=True) != workspace:
                raise OSError("workspace path is not canonical")
        except OSError as exc:
            raise _Blocked("workspace_invalid") from exc
        entries: list[tuple[str, str]] = []

        def walk(directory: Path) -> None:
            try:
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
                if stat.S_ISLNK(metadata.st_mode):
                    raise _Blocked("workspace_invalid")
                if stat.S_ISDIR(metadata.st_mode):
                    entries.append((relative, "directory"))
                    walk(path)
                elif stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1:
                    entries.append((relative, "file"))
                else:
                    raise _Blocked("workspace_invalid")

        walk(workspace)
        return tuple(entries)

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
            manifest.candidate_manifest_id != outcome.candidate_manifest_id
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
        self._workspace_inventory(workspace)

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
    ) -> PreparedProjectDirectorBoundedReworkCandidateDiff:
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
            ):
                return self._blocked(reason)
            if current.content != written_manifest_bytes:
                return self._blocked(
                    "human_escalation_required",
                    recovery_required=True,
                    human_escalation_required=True,
                )
            self._atomic_replace_manifest(
                path=manifest_path,
                content=original_manifest.content,
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
            and parts[0]
            in {".git", ".ai-project-director", ".ai-dev-orchestrator", ".orchestrator"}
        )

    def _rollback_read_transaction(self) -> None:
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


__all__ = (
    "CandidateDiffPreparationStatus",
    "P25_BOUNDED_REWORK_CANDIDATE_DIFF_ACTION_TYPE",
    "P25_BOUNDED_REWORK_CANDIDATE_DIFF_INTENT",
    "P25_BOUNDED_REWORK_CANDIDATE_DIFF_SOURCE_DETAIL",
    "P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_ACTION_TYPE",
    "P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_INTENT",
    "P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_SOURCE_DETAIL",
    "PreparedProjectDirectorBoundedReworkCandidateDiff",
    "ProjectDirectorBoundedReworkCandidateDiffService",
)
