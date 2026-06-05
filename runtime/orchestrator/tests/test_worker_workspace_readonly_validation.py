"""P2-B Worker AgentSession.workspace_path read-only validation.

These tests cover the pure validation seam only. They do not invoke the worker
loop, do not start services, do not run git commands, and do not create or
clean real git worktrees.
"""

from __future__ import annotations

from uuid import uuid4

from app.domain.agent_session import AgentSession, WorkspaceType
from app.workers.task_worker import validate_worker_agent_workspace


def _session(
    *,
    workspace_type: WorkspaceType | None = WorkspaceType.WORKTREE,
    workspace_path: str | None = None,
    workspace_clean: bool | None = None,
) -> AgentSession:
    return AgentSession(
        project_id=uuid4(),
        task_id=uuid4(),
        run_id=uuid4(),
        workspace_type=workspace_type,
        workspace_path=workspace_path,
        workspace_clean=workspace_clean,
    )


def test_validate_worker_agent_workspace_skips_non_worktree_sessions():
    result = validate_worker_agent_workspace(
        _session(workspace_type=WorkspaceType.IN_PLACE)
    )

    assert result.ready is True
    assert result.reason_code is None
    assert result.workspace_type == "in_place"
    assert result.resolved_workspace_path is None


def test_validate_worker_agent_workspace_blocks_missing_worktree_path():
    result = validate_worker_agent_workspace(_session(workspace_path=None))

    assert result.ready is False
    assert result.reason_code == "workspace_path_missing"
    assert "requires workspace_path" in result.summary


def test_validate_worker_agent_workspace_blocks_relative_worktree_path():
    result = validate_worker_agent_workspace(
        _session(workspace_path="relative/worktree", workspace_clean=True)
    )

    assert result.ready is False
    assert result.reason_code == "workspace_path_not_absolute"


def test_validate_worker_agent_workspace_blocks_missing_directory(tmp_path):
    missing_path = tmp_path / "missing-worktree"
    result = validate_worker_agent_workspace(
        _session(workspace_path=missing_path.as_posix(), workspace_clean=True)
    )

    assert result.ready is False
    assert result.reason_code == "workspace_path_not_found"
    assert result.resolved_workspace_path == missing_path.as_posix()


def test_validate_worker_agent_workspace_blocks_file_path(tmp_path):
    file_path = tmp_path / "not-a-directory"
    file_path.write_text("not a worktree directory\n")

    result = validate_worker_agent_workspace(
        _session(workspace_path=file_path.as_posix(), workspace_clean=True)
    )

    assert result.ready is False
    assert result.reason_code == "workspace_path_not_directory"


def test_validate_worker_agent_workspace_blocks_unknown_clean_state(tmp_path):
    result = validate_worker_agent_workspace(
        _session(workspace_path=tmp_path.as_posix(), workspace_clean=None)
    )

    assert result.ready is False
    assert result.reason_code == "workspace_clean_unknown"
    assert "does not run git status" in result.summary


def test_validate_worker_agent_workspace_blocks_dirty_metadata(tmp_path):
    result = validate_worker_agent_workspace(
        _session(workspace_path=tmp_path.as_posix(), workspace_clean=False)
    )

    assert result.ready is False
    assert result.reason_code == "workspace_dirty"


def test_validate_worker_agent_workspace_accepts_existing_clean_worktree_metadata(
    tmp_path,
):
    result = validate_worker_agent_workspace(
        _session(workspace_path=tmp_path.as_posix(), workspace_clean=True)
    )

    assert result.ready is True
    assert result.reason_code is None
    assert result.workspace_type == "worktree"
    assert result.workspace_path == tmp_path.as_posix()
    assert result.workspace_clean is True
    assert result.resolved_workspace_path == tmp_path.as_posix()
