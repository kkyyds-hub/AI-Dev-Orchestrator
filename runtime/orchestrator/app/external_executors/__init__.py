"""External executor boundary package for P9 guarded runtime work."""

from app.external_executors.actual_contract import (
    RealExecutorAdapterProtocol,
    RealExecutorCapability,
    RealExecutorLaunchContext,
    RealExecutorLifecycleIntent,
    RealExecutorOperationResult,
    RealExecutorOperationStatus,
    RealExecutorPollSnapshot,
    RealExecutorPollState,
    RealExecutorSafetyBoundary,
)

__all__ = (
    "RealExecutorAdapterProtocol",
    "RealExecutorCapability",
    "RealExecutorLaunchContext",
    "RealExecutorLifecycleIntent",
    "RealExecutorOperationResult",
    "RealExecutorOperationStatus",
    "RealExecutorPollSnapshot",
    "RealExecutorPollState",
    "RealExecutorSafetyBoundary",
)
