"""Targeted tests for P4-C git operation dry-run builder."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.agent_session import AgentSession, WorkspaceType
from app.domain.git_operation_dry_run import (
    GIT_OPERATION_DRY_RUN_SOURCE,
    GitOperationDryRunBuilder,
    GitOperationDryRunOperation,
    GitOperationDryRunResult,
    GitOperationDryRunSafetyFlags,
    P4C_FORBIDDEN_TRUE_SAFETY_FLAGS,
)
from app.services.git_diff_dry_run_runner import GitDiffDryRunResult


def _session(
    *,
    workspace_type: WorkspaceType | None = WorkspaceType.WORKTREE,
    workspace_path: str | None = "/tmp/aido-worktree",
) -> AgentSession:
    return AgentSession(
        id=uuid4(),
        project_id=uuid4(),
        task_id=uuid4(),
        run_id=uuid4(),
        branch_name="feature/p4-c",
        workspace_type=workspace_type,
        workspace_path=workspace_path,
    )


def _dirty_diff(**overrides) -> GitDiffDryRunResult:
    values = {
        "ready": True,
        "source": "agent_session_worktree_diff",
        "reason_code": None,
        "worktree_path": "/tmp/aido-worktree",
        "has_changes": True,
        "changed_files_count": 2,
        "changed_files": ["README.md", "src/app.py"],
        "added_files": ["src/app.py"],
        "modified_files": ["README.md"],
        "deleted_files": [],
        "renamed_files": [],
        "status_summary_cn": "1 个文件修改，1 个文件新增",
        "branch_name": "feature/p4-c",
        "runs_git": True,
        "runs_write_git": False,
        "git_add_triggered": False,
        "git_commit_triggered": False,
        "git_push_triggered": False,
        "pr_opened": False,
        "ci_triggered": False,
        "execution_enabled": False,
    }
    values.update(overrides)
    return GitDiffDryRunResult(**values)


def test_build_ready_operation_preview_from_dirty_diff_evidence():
    session = _session()
    result = GitOperationDryRunBuilder.build_from_diff_evidence(
        agent_session=session,
        diff_evidence=_dirty_diff(),
    )

    assert result.ready is True
    assert result.source == GIT_OPERATION_DRY_RUN_SOURCE
    assert result.reason_code is None
    assert result.session_id == str(session.id)
    assert result.project_id == str(session.project_id)
    assert result.task_id == str(session.task_id)
    assert result.run_id == str(session.run_id)
    assert result.worktree_path == "/tmp/aido-worktree"
    assert result.branch_name == "feature/p4-c"
    assert result.changed_files_count == 2
    assert result.changed_files == ["README.md", "src/app.py"]
    assert result.added_files == ["src/app.py"]
    assert result.modified_files == ["README.md"]
    assert result.proposed_operation == GitOperationDryRunOperation.GIT_ADD_COMMIT
    assert result.proposed_steps == [
        "准备加入待提交区（git add，预览不执行）",
        "准备生成本地提交（git commit，预览不执行）：chore: update 2 files from agent work",
    ]
    assert result.proposed_commit_message == "chore: update 2 files from agent work"
    assert result.proposed_pr_title is None
    assert result.proposed_pr_body is None
    assert result.user_confirmation_required is True
    assert result.human_approval_required is True
    assert result.feature_flag_required is True
    assert "已生成提交预览" in result.summary_cn
    assert "尚未加入待提交区" in result.summary_cn
    assert "尚未生成本地提交" in result.summary_cn
    assert "尚未推送" in result.summary_cn
    assert result.safety_flags.model_dump() == {
        "runs_git": False,
        "runs_write_git": False,
        "git_add_triggered": False,
        "git_commit_triggered": False,
        "git_push_triggered": False,
        "pr_opened": False,
        "ci_triggered": False,
        "execution_enabled": False,
        "operation_applied": False,
        "approval_granted": False,
    }


@pytest.mark.parametrize(
    ("session", "diff_evidence", "expected_reason", "expected_summary"),
    [
        (
            _session(workspace_type=WorkspaceType.IN_PLACE),
            _dirty_diff(),
            "worktree_unavailable",
            "当前工作区不可用，无法生成提交预览。",
        ),
        (
            _session(workspace_path=None),
            _dirty_diff(),
            "worktree_unavailable",
            "当前工作区不可用，无法生成提交预览。",
        ),
        (
            _session(),
            GitDiffDryRunResult(
                ready=False,
                source="agent_session_worktree_diff",
                reason_code="git_diff_dry_run_failed",
                worktree_path="/tmp/aido-worktree",
                has_changes=None,
                changed_files_count=None,
                runs_git=False,
            ),
            "diff_evidence_not_ready",
            "代码改动预览未就绪，无法生成提交预览。",
        ),
        (
            _session(),
            _dirty_diff(has_changes=False, changed_files_count=0, changed_files=[]),
            "no_changes",
            "当前没有可提交的代码改动。",
        ),
        (
            _session(),
            _dirty_diff(git_commit_triggered=True),
            "write_already_triggered",
            "检测到写操作已触发，无法再次生成提交预览。",
        ),
    ],
)
def test_build_blocked_operation_preview_reason_codes(
    session,
    diff_evidence,
    expected_reason,
    expected_summary,
):
    result = GitOperationDryRunBuilder.build_from_diff_evidence(
        agent_session=session,
        diff_evidence=diff_evidence,
    )

    assert result.ready is False
    assert result.reason_code == expected_reason
    assert result.summary_cn == expected_summary
    assert result.proposed_operation == GitOperationDryRunOperation.NONE
    assert result.proposed_steps == []
    assert result.proposed_commit_message is None
    assert result.safety_flags.runs_git is False
    assert result.safety_flags.runs_write_git is False
    assert result.safety_flags.git_add_triggered is False
    assert result.safety_flags.git_commit_triggered is False
    assert result.safety_flags.operation_applied is False
    assert result.safety_flags.approval_granted is False


def test_build_blocked_when_operation_preview_feature_flag_disabled():
    result = GitOperationDryRunBuilder.build_from_diff_evidence(
        agent_session=_session(),
        diff_evidence=_dirty_diff(),
        delivery_operation_dry_run_enabled=False,
    )

    assert result.ready is False
    assert result.reason_code == "feature_flag_disabled"
    assert result.summary_cn == "提交功能尚未开启。"
    assert result.proposed_operation == GitOperationDryRunOperation.NONE


def test_build_blocked_when_session_missing():
    result = GitOperationDryRunBuilder.build_from_diff_evidence(
        agent_session=None,
        diff_evidence=_dirty_diff(),
    )

    assert result.ready is False
    assert result.reason_code == "session_missing"
    assert result.summary_cn == "会话信息缺失，无法生成提交预览。"
    assert result.session_id == "missing"
    assert result.project_id == "missing"
    assert result.task_id == "missing"
    assert result.run_id == "missing"
    assert result.proposed_operation == GitOperationDryRunOperation.NONE
    assert result.proposed_steps == []


def test_build_blocks_if_delivery_git_write_feature_flag_is_enabled():
    result = GitOperationDryRunBuilder.build_from_diff_evidence(
        agent_session=_session(),
        diff_evidence=_dirty_diff(),
        delivery_git_write_enabled=True,
    )

    assert result.ready is False
    assert result.reason_code == "feature_flag_enabled"
    assert result.summary_cn == "真实写入开关已开启，无法生成提交预览。"
    assert result.safety_flags.execution_enabled is False
    assert result.safety_flags.operation_applied is False


def test_git_operation_dry_run_operation_does_not_include_push_or_pr_preview():
    operation_values = {operation.value for operation in GitOperationDryRunOperation}

    assert "git_" + "push_pr" not in operation_values
    assert operation_values == {"git_add_commit", "none"}


def test_git_operation_dry_run_safety_flags_reject_any_true_flag():
    for flag_name in P4C_FORBIDDEN_TRUE_SAFETY_FLAGS:
        with pytest.raises(ValueError) as exc_info:
            GitOperationDryRunSafetyFlags(**{flag_name: True})

        assert flag_name in str(exc_info.value)
        assert "must not execute Git" in str(exc_info.value)


def test_git_operation_dry_run_result_rejects_inconsistent_ready_contract():
    with pytest.raises(ValueError) as exc_info:
        GitOperationDryRunResult(
            ready=True,
            reason_code="no_changes",
            session_id=str(uuid4()),
            project_id=str(uuid4()),
            task_id=str(uuid4()),
            run_id=str(uuid4()),
            proposed_operation=GitOperationDryRunOperation.GIT_ADD_COMMIT,
            proposed_steps=["准备加入待提交区（git add，预览不执行）"],
            summary_cn="已生成提交预览。",
        )

    assert "must not include reason_code" in str(exc_info.value)
