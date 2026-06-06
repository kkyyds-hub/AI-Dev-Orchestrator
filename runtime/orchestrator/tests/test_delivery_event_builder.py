"""Targeted tests for P4-B3 delivery diff dry-run event builder."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.domain.delivery_event import (
    DELIVERY_EVENT_CONTENT_DETAIL_MAX_LENGTH,
    DELIVERY_EVENT_SCHEMA_VERSION,
    DeliveryEventBuilder,
    DeliveryEventSchema,
    DeliveryEventState,
    DeliveryEventType,
)
from app.services.git_diff_dry_run_runner import GitDiffDryRunResult


def _ids():
    return {
        "session_id": uuid4(),
        "project_id": uuid4(),
        "task_id": uuid4(),
        "run_id": uuid4(),
    }


def test_build_collected_event_from_ready_dirty_diff_result():
    ids = _ids()
    result = GitDiffDryRunResult(
        ready=True,
        source="agent_session_worktree_diff",
        reason_code=None,
        worktree_path="/tmp/aido-worktree",
        has_changes=True,
        changed_files_count=2,
        changed_files=["README.md", "src/app.py"],
        added_files=["src/app.py"],
        modified_files=["README.md"],
        deleted_files=[],
        renamed_files=[],
        status_summary_cn="1 个文件修改，1 个文件新增",
        branch_name="feature/p4-b3",
        compare_branch="main",
        command="git status --porcelain=v1 --untracked-files=all",
        peek_command="git diff --name-status",
        runs_git=True,
    )

    event = DeliveryEventBuilder.from_diff_dry_run_result(
        **ids,
        result=result,
    )

    assert event.event_type == DeliveryEventType.DIFF_DRY_RUN_COLLECTED
    assert event.previous_delivery_state == DeliveryEventState.NONE
    assert event.next_delivery_state == DeliveryEventState.DIFF_DIRTY
    assert "检测到 2 个文件变更" in event.summary_cn
    assert "尚未被提交或推送" in event.summary_cn
    assert event.safety_flags.model_dump() == {
        "runs_git": True,
        "runs_write_git": False,
        "git_add_triggered": False,
        "git_commit_triggered": False,
        "git_push_triggered": False,
        "pr_opened": False,
        "ci_triggered": False,
        "execution_enabled": False,
    }
    assert event.evidence["status_summary_cn"] == "1 个文件修改，1 个文件新增"

    detail = json.loads(event.to_content_detail_json())
    assert detail["schema_version"] == DELIVERY_EVENT_SCHEMA_VERSION
    assert detail["event_type"] == "delivery_diff_dry_run_collected"
    assert detail["next_delivery_state"] == "diff_dirty"
    assert detail["safety_flags"]["runs_git"] is True
    assert detail["safety_flags"]["git_commit_triggered"] is False


def test_build_collected_event_from_ready_clean_diff_result():
    ids = _ids()
    result = GitDiffDryRunResult(
        ready=True,
        source="agent_session_worktree_diff",
        reason_code=None,
        worktree_path="/tmp/aido-worktree",
        has_changes=False,
        changed_files_count=0,
        status_summary_cn="无代码改动",
        runs_git=True,
    )

    event = DeliveryEventBuilder.from_diff_dry_run_result(
        **ids,
        result=result,
    )

    assert event.event_type == DeliveryEventType.DIFF_DRY_RUN_COLLECTED
    assert event.next_delivery_state == DeliveryEventState.DIFF_CLEAN
    assert event.summary_cn == "本次执行未产生代码改动。"
    assert event.safety_flags.runs_git is True
    assert event.safety_flags.runs_write_git is False


def test_build_skipped_event_without_running_git():
    ids = _ids()

    event = DeliveryEventBuilder.from_diff_dry_run_result(
        **ids,
        result=None,
        skipped_reason_code="worktree_path_unavailable",
        workspace_path=None,
    )

    assert event.event_type == DeliveryEventType.DIFF_DRY_RUN_SKIPPED
    assert event.next_delivery_state == DeliveryEventState.DIFF_SKIPPED
    assert event.reason_code == "worktree_path_unavailable"
    assert event.summary_cn == "代码改动预览已跳过：当前没有可检查的工作区。"
    assert event.safety_flags.model_dump() == {
        "runs_git": False,
        "runs_write_git": False,
        "git_add_triggered": False,
        "git_commit_triggered": False,
        "git_push_triggered": False,
        "pr_opened": False,
        "ci_triggered": False,
        "execution_enabled": False,
    }


@pytest.mark.parametrize(
    ("result", "expected_runs_git", "expected_summary"),
    [
        (
            GitDiffDryRunResult(
                ready=False,
                source="agent_session_worktree_diff",
                reason_code="worktree_path_not_found",
                worktree_path="/tmp/missing-worktree",
                has_changes=None,
                changed_files_count=None,
                runs_git=False,
            ),
            False,
            "未运行 Git 检查",
        ),
        (
            GitDiffDryRunResult(
                ready=False,
                source="agent_session_worktree_diff",
                reason_code="git_status_failed",
                worktree_path="/tmp/aido-worktree",
                has_changes=None,
                changed_files_count=None,
                command="git status --porcelain=v1 --untracked-files=all",
                runs_git=True,
            ),
            True,
            "Git 只读检查未完成",
        ),
    ],
)
def test_build_failed_event_preserves_pre_git_vs_git_command_runs_git(
    result,
    expected_runs_git,
    expected_summary,
):
    ids = _ids()

    event = DeliveryEventBuilder.from_diff_dry_run_result(
        **ids,
        result=result,
    )

    assert event.event_type == DeliveryEventType.DIFF_DRY_RUN_FAILED
    assert event.next_delivery_state == DeliveryEventState.DIFF_FAILED
    assert event.reason_code == result.reason_code
    assert expected_summary in event.summary_cn
    assert event.safety_flags.runs_git is expected_runs_git
    assert event.safety_flags.runs_write_git is False
    assert event.safety_flags.git_add_triggered is False
    assert event.safety_flags.git_commit_triggered is False
    assert event.safety_flags.git_push_triggered is False
    assert event.safety_flags.pr_opened is False
    assert event.safety_flags.ci_triggered is False
    assert event.safety_flags.execution_enabled is False


def test_delivery_event_content_detail_is_bounded_for_agent_message_field():
    ids = _ids()
    event = DeliveryEventBuilder.build(
        **ids,
        event_type=DeliveryEventType.DIFF_DRY_RUN_FAILED,
        technical_detail="x" * 2_000,
        evidence={"large_diff_preview": "y" * 10_000},
    )

    content_detail = event.to_content_detail_json()
    payload = json.loads(content_detail)

    assert len(content_detail) <= DELIVERY_EVENT_CONTENT_DETAIL_MAX_LENGTH
    assert payload["event_type"] == "delivery_diff_dry_run_failed"
    assert payload["evidence"]["truncated"] is True
    assert payload["safety_flags"]["runs_write_git"] is False


def test_delivery_event_schema_rejects_unknown_event_type_and_schema_version():
    ids = _ids()

    with pytest.raises(ValueError) as exc_info:
        DeliveryEventBuilder.build(**ids, event_type="delivery_git_commit_completed")
    assert "delivery_git_commit_completed" in str(exc_info.value)

    event = DeliveryEventBuilder.build(
        **ids,
        event_type=DeliveryEventType.DIFF_DRY_RUN_SKIPPED,
    )
    payload = event.model_dump()
    payload["schema_version"] = "2.0"
    with pytest.raises(ValueError):
        DeliveryEventSchema(**payload)
