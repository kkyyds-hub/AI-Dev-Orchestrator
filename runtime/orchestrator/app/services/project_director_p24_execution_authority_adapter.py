"""P24 execution-authority adapter contract pending P24-E persistence."""

from __future__ import annotations

from typing import Literal, Protocol
from uuid import UUID

from app.domain.project_director_source_execution_authority import (
    SourceExecutionAuthorityResolution,
)


class P24CrossTaskExecutionAuthorityAdapterProtocol(Protocol):
    """Strict read-only adapter to be implemented by the P24-E outcome producer."""

    authority_kind: Literal["p24_cross_task_continuation"]

    def resolve(
        self,
        *,
        authority_record_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
    ) -> SourceExecutionAuthorityResolution:
        """Reconstruct one persisted P24 authority lineage without mutation."""


class UnavailableP24CrossTaskExecutionAuthorityAdapter:
    """Fail closed until P24-E persists a real P24 invocation lineage."""

    authority_kind: Literal["p24_cross_task_continuation"] = (
        "p24_cross_task_continuation"
    )

    def resolve(
        self,
        *,
        authority_record_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
    ) -> SourceExecutionAuthorityResolution:
        del authority_record_id, source_task_id, source_run_id
        return SourceExecutionAuthorityResolution.blocked(
            "source_execution_authority_adapter_unavailable"
        )


__all__ = (
    "P24CrossTaskExecutionAuthorityAdapterProtocol",
    "UnavailableP24CrossTaskExecutionAuthorityAdapter",
)
