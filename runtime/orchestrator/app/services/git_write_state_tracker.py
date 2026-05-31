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


def _jsonl_log_has_entry(change_batch_id: UUID, file_name: str) -> bool:
    """Return whether one git-write JSONL log contains this change batch."""

    log_path = settings.runtime_data_dir / _GIT_WRITE_LOG_DIR_NAME / file_name
    if not log_path.exists():
        return False

    expected_id = str(change_batch_id)
    try:
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(entry.get("change_batch_id", "")) == expected_id:
                return True
    except OSError:
        return False

    return False


def has_git_write_actions_triggered(change_batch_id: UUID) -> bool:
    """Check whether git write has been triggered for a change batch.

    Used by RepositoryReleaseGateService to report git_write_actions_triggered.
    """
    state = _load_git_write_state(change_batch_id)
    if state is None:
        return False
    return bool(state.get("git_write_actions_triggered", False))


def get_git_write_action_summary(change_batch_id: UUID) -> dict[str, bool]:
    """Return a read-only summary of local git-write side effects for one batch.

    This is intentionally small and safe: it only reads the runtime tracking file
    written by apply-local/git-commit, and never attempts to mutate the workspace
    or inspect git state directly.
    """

    state = _load_git_write_state(change_batch_id)
    state_payload = state if isinstance(state, dict) else {}

    apply_local_triggered = isinstance(
        state_payload.get("apply_local"), dict
    ) or _jsonl_log_has_entry(change_batch_id, "apply-local.jsonl")
    git_commit_triggered = isinstance(
        state_payload.get("git_commit"), dict
    ) or _jsonl_log_has_entry(change_batch_id, "git-commit.jsonl")

    return {
        "apply_local_triggered": apply_local_triggered,
        "git_commit_triggered": git_commit_triggered,
        "git_write_actions_triggered": bool(
            state_payload.get("git_write_actions_triggered", False)
            or apply_local_triggered
            or git_commit_triggered
        ),
    }
