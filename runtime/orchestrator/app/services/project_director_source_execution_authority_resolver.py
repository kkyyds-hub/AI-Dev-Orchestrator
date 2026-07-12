"""Authority-neutral resolver for persisted Project Director execution lineage."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Protocol, cast
from uuid import UUID

from pydantic import ValidationError

from app.domain.project_director_source_execution_authority import (
    SourceExecutionAuthorityKind,
    SourceExecutionAuthorityResolution,
    SourceExecutionAuthoritySnapshot,
)


_AUTHORITY_KINDS = {
    "p23_protected_transition",
    "p24_cross_task_continuation",
}
_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class SourceExecutionAuthorityAdapterProtocol(Protocol):
    """Read-only adapter boundary shared by P23 and P24 authorities."""

    authority_kind: SourceExecutionAuthorityKind

    def resolve(
        self,
        *,
        authority_record_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
    ) -> SourceExecutionAuthorityResolution:
        """Resolve one persisted authority for an exact Task and Run."""


class ProjectDirectorSourceExecutionAuthorityResolver:
    """Select an injected adapter and defensively validate its unified snapshot."""

    def __init__(
        self,
        *,
        adapters: Mapping[
            SourceExecutionAuthorityKind,
            SourceExecutionAuthorityAdapterProtocol,
        ],
    ) -> None:
        self._adapters = dict(adapters)

    def resolve(
        self,
        *,
        authority_kind: str,
        authority_record_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
    ) -> SourceExecutionAuthorityResolution:
        if authority_kind not in _AUTHORITY_KINDS:
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_kind_unsupported"
            )
        typed_kind = cast(SourceExecutionAuthorityKind, authority_kind)
        adapter = self._adapters.get(typed_kind)
        if adapter is None:
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_adapter_unavailable"
            )
        if adapter.authority_kind != typed_kind:
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_schema_mismatch"
            )
        try:
            raw_resolution = adapter.resolve(
                authority_record_id=authority_record_id,
                source_task_id=source_task_id,
                source_run_id=source_run_id,
            )
        except Exception:
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_adapter_unavailable"
            )
        try:
            raw_resolved = raw_resolution.resolved
            raw_snapshot = raw_resolution.snapshot
            raw_blocked_reasons = raw_resolution.blocked_reasons
        except AttributeError:
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_schema_mismatch"
            )
        if raw_resolved and (raw_snapshot is None or raw_blocked_reasons):
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_schema_mismatch"
            )
        if not raw_resolved:
            try:
                return SourceExecutionAuthorityResolution.model_validate(
                    raw_resolution.model_dump()
                )
            except (AttributeError, TypeError, ValueError, ValidationError):
                return SourceExecutionAuthorityResolution.blocked(
                    "source_execution_authority_schema_mismatch"
                )
        snapshot = raw_snapshot
        try:
            snapshot_kind = snapshot.authority_kind
            snapshot_task_id = snapshot.task_id
            snapshot_run_id = snapshot.run_id
            fingerprints = (
                snapshot.authority_fingerprint,
                snapshot.reservation_fingerprint,
                snapshot.claim_fingerprint,
                snapshot.outcome_fingerprint,
            )
            outcome_status = snapshot.outcome_status
            worker_result_contract_valid = snapshot.worker_result_contract_valid
            recovery_required = snapshot.recovery_required
            snapshot_blocked_reasons = snapshot.blocked_reasons
            worker_reported_git_write_activity = (
                snapshot.worker_reported_git_write_activity
            )
            product_runtime_git_write_allowed = (
                snapshot.product_runtime_git_write_allowed
            )
        except AttributeError:
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_schema_mismatch"
            )
        if snapshot_kind != typed_kind:
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_schema_mismatch"
            )
        if snapshot_task_id != source_task_id or snapshot_run_id != source_run_id:
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_task_run_mismatch"
            )
        if not all(
            isinstance(value, str) and _LOWER_HEX_SHA256.fullmatch(value)
            for value in fingerprints
        ):
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_fingerprint_mismatch"
            )
        if outcome_status != "returned":
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_outcome_not_returned"
            )
        if not worker_result_contract_valid:
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_result_contract_invalid"
            )
        if recovery_required:
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_recovery_required"
            )
        if snapshot_blocked_reasons:
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_blocked"
            )
        if (
            worker_reported_git_write_activity
            or product_runtime_git_write_allowed
        ):
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_git_boundary_violation"
            )
        try:
            validated_snapshot = SourceExecutionAuthoritySnapshot.model_validate(
                snapshot.model_dump()
            )
        except (AttributeError, TypeError, ValueError, ValidationError):
            return SourceExecutionAuthorityResolution.blocked(
                "source_execution_authority_schema_mismatch"
            )
        return SourceExecutionAuthorityResolution.success(validated_snapshot)


__all__ = (
    "ProjectDirectorSourceExecutionAuthorityResolver",
    "SourceExecutionAuthorityAdapterProtocol",
)
