"""BCL-03: Git-write state tracking shared between release gate and local git write.

This module is deliberately independent to avoid circular imports between
repository_release_gate_service and local_git_write_service.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from app.core.config import settings

_GIT_WRITE_LOG_DIR_NAME = "repository-git-writes"


def _resolve_git_write_state_path(change_batch_id: UUID) -> Path:
    """Resolve the git-write tracking file for one change batch."""
    return (
        settings.runtime_data_dir
        / _GIT_WRITE_LOG_DIR_NAME
        / f"{change_batch_id}.json"
    )


def _load_git_write_state(change_batch_id: UUID) -> dict | None:
    """Load git-write tracking state, or None if it doesn't exist."""
    path = _resolve_git_write_state_path(change_batch_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def has_git_write_actions_triggered(change_batch_id: UUID) -> bool:
    """Check whether git write has been triggered for a change batch.

    Used by RepositoryReleaseGateService to report git_write_actions_triggered.
    """
    state = _load_git_write_state(change_batch_id)
    if state is None:
        return False
    return bool(state.get("git_write_actions_triggered", False))
