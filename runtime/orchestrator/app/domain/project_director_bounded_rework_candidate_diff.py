"""Immutable P25-G candidate manifest and exact-base diff contracts."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Literal, TypeAlias
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domain._base import DomainModel
from app.domain.project_director_bounded_rework_contract import (
    P25_BOUNDED_REWORK_ATTEMPT_LIMIT,
    ProjectDirectorBoundedReworkAuthorityEnvelope,
    compute_p25_contract_sha256,
    normalize_utc_datetime,
    require_git_commit,
    require_optional_sha256,
    require_sha256,
    validate_repository_relative_path,
    validate_unique_paths,
)


P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_SCHEMA_VERSION = (
    "p25-g-candidate-manifest.v1"
)
P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_REPLAY_SCHEMA_VERSION = (
    "p25-g-candidate-manifest-replay.v1"
)
P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_IDENTITY_SCHEMA_VERSION = (
    "p25-f-candidate-manifest-identity.v1"
)
P25_BOUNDED_REWORK_CANDIDATE_DIFF_SCHEMA_VERSION = "p25-g-candidate-diff.v1"
P25_BOUNDED_REWORK_CANDIDATE_DIFF_REPLAY_SCHEMA_VERSION = (
    "p25-g-candidate-diff-replay.v1"
)
P25_BOUNDED_REWORK_INTERNAL_MANIFEST_PATH = (
    ".ai-project-director/workspace-manifest.json"
)

CandidateFileOperation: TypeAlias = Literal["create", "update", "delete"]
CandidateDiffStatus: TypeAlias = Literal["generated", "non_convergence"]
CandidateDiffNonConvergenceReason: TypeAlias = Literal[
    "empty_diff",
    "unchanged_diff",
]


class ProjectDirectorBoundedReworkCandidateManifestEntry(DomainModel):
    """One exact candidate business-file identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    relative_path: str = Field(min_length=1, max_length=2_000)
    operation: CandidateFileOperation
    content_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    deleted: bool

    @field_validator("relative_path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return validate_repository_relative_path(value)

    @field_validator("content_sha256")
    @classmethod
    def validate_content_hash(cls, value: str | None) -> str | None:
        return require_optional_sha256(value, label="P25-G candidate content hash")

    @model_validator(mode="after")
    def validate_entry(self) -> "ProjectDirectorBoundedReworkCandidateManifestEntry":
        if self.operation == "delete":
            if not self.deleted or self.content_sha256 is not None:
                raise ValueError("deleted candidate entries cannot carry content")
        elif self.deleted or self.content_sha256 is None:
            raise ValueError("created or updated candidate entries require content")
        return self


class ProjectDirectorBoundedReworkCandidateManifest(DomainModel):
    """Materialized manifest for one successful persisted P25-F Outcome."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["p25-g-candidate-manifest.v1"] = (
        P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_SCHEMA_VERSION
    )
    candidate_manifest_id: UUID
    candidate_manifest_fingerprint: str = Field(min_length=64, max_length=64)
    candidate_manifest_replay_key: str = Field(min_length=64, max_length=64)
    created_at: datetime

    source_outcome_id: UUID
    source_outcome_fingerprint: str = Field(min_length=64, max_length=64)
    source_claim_id: UUID
    source_claim_fingerprint: str = Field(min_length=64, max_length=64)
    source_reservation_id: UUID
    source_reservation_fingerprint: str = Field(min_length=64, max_length=64)
    source_package_id: UUID
    source_package_fingerprint: str = Field(min_length=64, max_length=64)

    authority: ProjectDirectorBoundedReworkAuthorityEnvelope
    exact_task_id: UUID
    exact_run_id: UUID
    rework_attempt_index: int = Field(ge=0, lt=3)
    rework_attempt_limit: int

    base_commit_sha: str = Field(min_length=40, max_length=40)
    base_snapshot_fingerprint: str = Field(min_length=64, max_length=64)
    workspace_before_manifest_fingerprint: str = Field(min_length=64, max_length=64)
    workspace_before_content_fingerprint: str = Field(min_length=64, max_length=64)
    workspace_after_manifest_fingerprint: str = Field(min_length=64, max_length=64)
    workspace_after_content_fingerprint: str = Field(min_length=64, max_length=64)

    changed_files: tuple[ProjectDirectorBoundedReworkCandidateManifestEntry, ...]
    internal_manifest_file_path: Literal[
        ".ai-project-director/workspace-manifest.json"
    ] = P25_BOUNDED_REWORK_INTERNAL_MANIFEST_PATH
    internal_manifest_content_sha256: str = Field(min_length=64, max_length=64)

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return normalize_utc_datetime(value, label="P25-G candidate manifest created_at")

    @field_validator(
        "candidate_manifest_fingerprint",
        "candidate_manifest_replay_key",
        "source_outcome_fingerprint",
        "source_claim_fingerprint",
        "source_reservation_fingerprint",
        "source_package_fingerprint",
        "base_snapshot_fingerprint",
        "workspace_before_manifest_fingerprint",
        "workspace_before_content_fingerprint",
        "workspace_after_manifest_fingerprint",
        "workspace_after_content_fingerprint",
        "internal_manifest_content_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return require_sha256(value, label="P25-G candidate manifest hash")

    @field_validator("base_commit_sha")
    @classmethod
    def validate_base_commit(cls, value: str) -> str:
        return require_git_commit(value, label="P25-G candidate manifest base commit")

    @model_validator(mode="after")
    def validate_manifest(self) -> "ProjectDirectorBoundedReworkCandidateManifest":
        if (
            self.exact_task_id != self.authority.source_task_id
            or self.exact_task_id != self.authority.target_task_id
            or self.exact_run_id != self.authority.source_run_id
        ):
            raise ValueError("P25-G manifest must bind the authority's exact Task and Run")
        if self.rework_attempt_limit != P25_BOUNDED_REWORK_ATTEMPT_LIMIT:
            raise ValueError("P25-G manifest attempt limit must equal three")
        paths = tuple(item.relative_path for item in self.changed_files)
        validate_unique_paths(paths, allow_empty=False)
        if paths != tuple(sorted(paths)):
            raise ValueError("P25-G manifest entries must be sorted")
        expected_identity = self.compute_candidate_manifest_identity_fingerprint(
            candidate_manifest_id=self.candidate_manifest_id,
            source_claim_id=self.source_claim_id,
            source_claim_fingerprint=self.source_claim_fingerprint,
            source_reservation_id=self.source_reservation_id,
            source_package_id=self.source_package_id,
            rework_attempt_index=self.rework_attempt_index,
            workspace_after_manifest_fingerprint=(
                self.workspace_after_manifest_fingerprint
            ),
            workspace_after_content_fingerprint=(
                self.workspace_after_content_fingerprint
            ),
            changed_files=self.changed_files,
        )
        if self.candidate_manifest_fingerprint != expected_identity:
            raise ValueError("P25-G candidate manifest identity does not match P25-F")
        expected_replay = self.compute_replay_key(
            source_outcome_id=self.source_outcome_id,
            source_outcome_fingerprint=self.source_outcome_fingerprint,
            candidate_manifest_id=self.candidate_manifest_id,
            candidate_manifest_fingerprint=self.candidate_manifest_fingerprint,
            workspace_after_manifest_fingerprint=(
                self.workspace_after_manifest_fingerprint
            ),
            workspace_after_content_fingerprint=(
                self.workspace_after_content_fingerprint
            ),
            changed_files=self.changed_files,
        )
        if self.candidate_manifest_replay_key != expected_replay:
            raise ValueError("P25-G candidate manifest replay key does not match")
        return self

    @staticmethod
    def compute_candidate_manifest_identity_fingerprint(
        *,
        candidate_manifest_id: UUID,
        source_claim_id: UUID,
        source_claim_fingerprint: str,
        source_reservation_id: UUID,
        source_package_id: UUID,
        rework_attempt_index: int,
        workspace_after_manifest_fingerprint: str,
        workspace_after_content_fingerprint: str,
        changed_files: tuple[ProjectDirectorBoundedReworkCandidateManifestEntry, ...],
    ) -> str:
        """Reproduce the exact candidate identity persisted by P25-F."""

        return compute_p25_contract_sha256(
            {
                "schema_version": (
                    P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_IDENTITY_SCHEMA_VERSION
                ),
                "candidate_manifest_id": candidate_manifest_id,
                "claim_id": source_claim_id,
                "claim_fingerprint": source_claim_fingerprint,
                "reservation_id": source_reservation_id,
                "package_id": source_package_id,
                "rework_attempt_index": rework_attempt_index,
                "workspace_after_manifest_fingerprint": (
                    workspace_after_manifest_fingerprint
                ),
                "workspace_after_content_fingerprint": (
                    workspace_after_content_fingerprint
                ),
                "changed_files": [
                    {
                        "path": entry.relative_path,
                        "content_sha256": entry.content_sha256,
                        "deleted": entry.deleted,
                    }
                    for entry in changed_files
                ],
            }
        )

    @staticmethod
    def compute_replay_key(
        *,
        source_outcome_id: UUID,
        source_outcome_fingerprint: str,
        candidate_manifest_id: UUID,
        candidate_manifest_fingerprint: str,
        workspace_after_manifest_fingerprint: str,
        workspace_after_content_fingerprint: str,
        changed_files: tuple[ProjectDirectorBoundedReworkCandidateManifestEntry, ...],
    ) -> str:
        return compute_p25_contract_sha256(
            {
                "schema_version": (
                    P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_REPLAY_SCHEMA_VERSION
                ),
                "source_outcome_id": source_outcome_id,
                "source_outcome_fingerprint": source_outcome_fingerprint,
                "candidate_manifest_id": candidate_manifest_id,
                "candidate_manifest_fingerprint": candidate_manifest_fingerprint,
                "workspace_after_manifest_fingerprint": (
                    workspace_after_manifest_fingerprint
                ),
                "workspace_after_content_fingerprint": (
                    workspace_after_content_fingerprint
                ),
                "changed_files": changed_files,
            }
        )


class ProjectDirectorBoundedReworkCandidateDiffEntry(DomainModel):
    """One canonical exact-base unified diff entry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    relative_path: str = Field(min_length=1, max_length=2_000)
    operation: CandidateFileOperation
    base_file_existed: bool
    candidate_file_existed: bool
    base_content_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    candidate_content_sha256: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )
    unified_diff: str
    diff_bytes: int = Field(ge=0)

    @field_validator("relative_path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return validate_repository_relative_path(value)

    @field_validator("base_content_sha256", "candidate_content_sha256")
    @classmethod
    def validate_optional_hashes(cls, value: str | None) -> str | None:
        return require_optional_sha256(value, label="P25-G diff content hash")

    @model_validator(mode="after")
    def validate_entry(self) -> "ProjectDirectorBoundedReworkCandidateDiffEntry":
        expected = {
            "create": (False, True),
            "update": (True, True),
            "delete": (True, False),
        }[self.operation]
        if (self.base_file_existed, self.candidate_file_existed) != expected:
            raise ValueError("P25-G diff operation does not match file existence")
        if self.base_file_existed != (self.base_content_sha256 is not None):
            raise ValueError("P25-G diff base content identity is incomplete")
        if self.candidate_file_existed != (
            self.candidate_content_sha256 is not None
        ):
            raise ValueError("P25-G diff candidate content identity is incomplete")
        if self.diff_bytes != len(self.unified_diff.encode("utf-8")):
            raise ValueError("P25-G diff entry byte count does not match")
        return self


class ProjectDirectorBoundedReworkCandidateDiff(DomainModel):
    """Immutable exact-base diff or terminal non-convergence evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["p25-g-candidate-diff.v1"] = (
        P25_BOUNDED_REWORK_CANDIDATE_DIFF_SCHEMA_VERSION
    )
    candidate_diff_id: UUID
    candidate_diff_fingerprint: str = Field(min_length=64, max_length=64)
    candidate_diff_replay_key: str = Field(min_length=64, max_length=64)
    created_at: datetime
    diff_status: CandidateDiffStatus

    source_attempt_id: UUID
    source_outcome_id: UUID
    source_outcome_fingerprint: str = Field(min_length=64, max_length=64)
    source_claim_id: UUID
    source_reservation_id: UUID
    source_package_id: UUID
    candidate_manifest_id: UUID
    candidate_manifest_fingerprint: str = Field(min_length=64, max_length=64)

    authority: ProjectDirectorBoundedReworkAuthorityEnvelope
    exact_task_id: UUID
    exact_run_id: UUID
    rework_attempt_index: int = Field(ge=0, lt=3)
    rework_attempt_limit: int

    previous_diff_message_id: UUID
    previous_diff_sha256: str = Field(min_length=64, max_length=64)
    base_commit_sha: str = Field(min_length=40, max_length=40)
    base_snapshot_fingerprint: str = Field(min_length=64, max_length=64)
    base_content_source: Literal["exact_git_commit_object"] = (
        "exact_git_commit_object"
    )
    readonly_base_snapshot_verified: Literal[True] = True

    workspace_after_manifest_fingerprint: str = Field(min_length=64, max_length=64)
    workspace_after_content_fingerprint: str = Field(min_length=64, max_length=64)
    scope_paths: tuple[str, ...]
    diff_entries: tuple[ProjectDirectorBoundedReworkCandidateDiffEntry, ...]
    unified_diff_text: str
    new_diff_sha256: str = Field(min_length=64, max_length=64)
    diff_bytes: int = Field(ge=0)
    diff_file_count: int = Field(ge=0)
    non_convergence_reason: CandidateDiffNonConvergenceReason | None = None

    product_runtime_git_write_allowed: Literal[False] = False
    main_project_write_allowed: Literal[False] = False
    patch_apply_allowed: Literal[False] = False
    git_add_allowed: Literal[False] = False
    git_commit_allowed: Literal[False] = False
    git_push_allowed: Literal[False] = False
    branch_operation_allowed: Literal[False] = False
    pull_request_allowed: Literal[False] = False
    merge_allowed: Literal[False] = False
    ci_trigger_allowed: Literal[False] = False
    reviewer_called: Literal[False] = False
    task_created: Literal[False] = False
    run_created: Literal[False] = False

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return normalize_utc_datetime(value, label="P25-G candidate diff created_at")

    @field_validator(
        "candidate_diff_fingerprint",
        "candidate_diff_replay_key",
        "source_outcome_fingerprint",
        "candidate_manifest_fingerprint",
        "previous_diff_sha256",
        "base_snapshot_fingerprint",
        "workspace_after_manifest_fingerprint",
        "workspace_after_content_fingerprint",
        "new_diff_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return require_sha256(value, label="P25-G candidate diff hash")

    @field_validator("base_commit_sha")
    @classmethod
    def validate_base_commit(cls, value: str) -> str:
        return require_git_commit(value, label="P25-G candidate diff base commit")

    @field_validator("scope_paths")
    @classmethod
    def validate_scope_paths(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        values = validate_unique_paths(values, allow_empty=False)
        if values != tuple(sorted(values)):
            raise ValueError("P25-G diff scope paths must be sorted")
        return values

    @model_validator(mode="after")
    def validate_diff(self) -> "ProjectDirectorBoundedReworkCandidateDiff":
        if (
            self.exact_task_id != self.authority.source_task_id
            or self.exact_task_id != self.authority.target_task_id
            or self.exact_run_id != self.authority.source_run_id
        ):
            raise ValueError("P25-G diff must bind the authority's exact Task and Run")
        if self.rework_attempt_limit != P25_BOUNDED_REWORK_ATTEMPT_LIMIT:
            raise ValueError("P25-G diff attempt limit must equal three")
        entry_paths = tuple(item.relative_path for item in self.diff_entries)
        validate_unique_paths(entry_paths, allow_empty=False)
        if entry_paths != self.scope_paths:
            raise ValueError("P25-G diff entries must exactly match manifest scope")
        if self.unified_diff_text != "".join(
            item.unified_diff for item in self.diff_entries
        ):
            raise ValueError("P25-G aggregate unified diff does not match entries")
        if self.new_diff_sha256 != hashlib.sha256(
            self.unified_diff_text.encode("utf-8")
        ).hexdigest():
            raise ValueError("P25-G new diff SHA does not match")
        if self.diff_bytes != len(self.unified_diff_text.encode("utf-8")):
            raise ValueError("P25-G aggregate diff byte count does not match")
        if self.diff_file_count != len(self.diff_entries):
            raise ValueError("P25-G diff file count does not match")
        if self.diff_status == "generated":
            if (
                not self.unified_diff_text
                or not self.diff_entries
                or self.new_diff_sha256 == self.previous_diff_sha256
                or self.non_convergence_reason is not None
            ):
                raise ValueError("generated P25-G diff requires new non-empty content")
        elif self.non_convergence_reason == "empty_diff":
            if self.unified_diff_text:
                raise ValueError("empty-diff non-convergence facts are contradictory")
        elif self.non_convergence_reason == "unchanged_diff":
            if (
                not self.unified_diff_text
                or self.new_diff_sha256 != self.previous_diff_sha256
            ):
                raise ValueError("unchanged-diff non-convergence facts are contradictory")
        else:
            raise ValueError("non-convergence requires a stable reason")
        if self.candidate_diff_replay_key != self.compute_replay_key(
            source_outcome_id=self.source_outcome_id,
            source_outcome_fingerprint=self.source_outcome_fingerprint,
            candidate_manifest_fingerprint=self.candidate_manifest_fingerprint,
            base_commit_sha=self.base_commit_sha,
            previous_diff_sha256=self.previous_diff_sha256,
            new_diff_sha256=self.new_diff_sha256,
        ):
            raise ValueError("P25-G candidate diff replay key does not match")
        if self.candidate_diff_fingerprint != self.compute_fingerprint():
            raise ValueError("P25-G candidate diff fingerprint does not match")
        return self

    @staticmethod
    def compute_replay_key(
        *,
        source_outcome_id: UUID,
        source_outcome_fingerprint: str,
        candidate_manifest_fingerprint: str,
        base_commit_sha: str,
        previous_diff_sha256: str,
        new_diff_sha256: str,
    ) -> str:
        return compute_p25_contract_sha256(
            {
                "schema_version": P25_BOUNDED_REWORK_CANDIDATE_DIFF_REPLAY_SCHEMA_VERSION,
                "source_outcome_id": source_outcome_id,
                "source_outcome_fingerprint": source_outcome_fingerprint,
                "candidate_manifest_fingerprint": candidate_manifest_fingerprint,
                "base_commit_sha": base_commit_sha,
                "previous_diff_sha256": previous_diff_sha256,
                "new_diff_sha256": new_diff_sha256,
            }
        )

    def compute_fingerprint(self) -> str:
        return compute_p25_contract_sha256(
            self.model_dump(mode="python", exclude={"candidate_diff_fingerprint"})
        )


__all__ = (
    "CandidateDiffNonConvergenceReason",
    "CandidateDiffStatus",
    "CandidateFileOperation",
    "P25_BOUNDED_REWORK_CANDIDATE_DIFF_REPLAY_SCHEMA_VERSION",
    "P25_BOUNDED_REWORK_CANDIDATE_DIFF_SCHEMA_VERSION",
    "P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_IDENTITY_SCHEMA_VERSION",
    "P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_REPLAY_SCHEMA_VERSION",
    "P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_SCHEMA_VERSION",
    "P25_BOUNDED_REWORK_INTERNAL_MANIFEST_PATH",
    "ProjectDirectorBoundedReworkCandidateDiff",
    "ProjectDirectorBoundedReworkCandidateDiffEntry",
    "ProjectDirectorBoundedReworkCandidateManifest",
    "ProjectDirectorBoundedReworkCandidateManifestEntry",
)
