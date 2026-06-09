"""Static boundary rules for future external executor modules.

This module is intentionally declarative. It does not provide an adapter,
start a process, invoke a terminal, or perform a real executor launch.
"""

from __future__ import annotations


EXTERNAL_EXECUTOR_MODULE_BOUNDARY = (
    "External executor code must live under app.external_executors. "
    "fake, preview, and actual executor capabilities must use separate "
    "module names. Future actual executor code may not be embedded in "
    "task_worker.py, executor_service.py, route files, or "
    "controlled_runtime_service.py. ControlledRuntimeService owns orchestration "
    "and the repository seam only; concrete CLI behavior belongs behind this "
    "package boundary in a later approved phase. P9-PEG-B does not define "
    "RealExecutorAdapter, does not use subprocess, and does not launch a "
    "real executor."
)

ALLOWED_EXTERNAL_EXECUTOR_MODULE_KINDS = ("fake", "preview", "actual")

FORBIDDEN_LEGACY_INTEGRATION_TARGETS = (
    "task_worker.py",
    "executor_service.py",
    "routes/runtime.py",
    "controlled_runtime_service.py",
)

BOUNDARY_RULES = (
    "fake modules, preview modules, and actual modules must remain separate",
    "future actual executor code can only be placed under external_executors",
    "real executor launch logic must not be added to task_worker.py",
    "real executor launch logic must not be added to executor_service.py",
    "real executor launch logic must not be added to route files",
    "ControlledRuntimeService only orchestrates runtime state and repositories",
    "P9-PEG-B has no RealExecutorAdapter",
    "P9-PEG-B has no subprocess integration",
    "P9-PEG-B has no real executor launch",
)
