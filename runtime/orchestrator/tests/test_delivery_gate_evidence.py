"""Targeted tests for P4-D delivery gate evidence builder."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domain.agent_session import AgentSession, WorkspaceType
from app.domain.delivery_gate_evidence import (
    DELIVERY_AUDIT_COLLECTED_EVENT_TYPE,
    DELIVERY_GATE_EVIDENCE_SOURCE,
    DeliveryGateEvidenceBuilder,
    DeliveryGateEvidenceResult,
    DeliveryGateEvidenceSafetyFlags,
    DeliveryGateNextRequiredAction,
    P4D_FORBIDDEN_TRUE_SAFETY_FLAGS,
)
from app.domain.git_operation_dry_run import (
    GitOperationDryRunBuilder,
    GitOperationDryRunOperation,
)
from app.services.git_diff_dry_run_runner import GitDiffDryRunResult


FORBIDDEN_USER_VISIBLE_COPY = (
    "代码已" + "提交",
    "代码已" + "推送",
    "合并请求" + "已创建",
    "自动提交" + "成功",
    "AI 已完成" + "交付",
    "交付" + "完成",
    "PR 已" + "准备",
    "提交" + "成功",
    "推送" + "成功",
    "可" + "合并",
)


def _session(**overrides) -> AgentSession:
    values = {
        "id": uuid4(),
        "project_id": uuid4(),
        "task_id": uuid4(),
        "run_id": uuid4(),
        "branch_name": "feature/p4-d",
        "workspace_type": WorkspaceType.WORKTREE,
        "workspace_path": "/tmp/aido-worktree",
        "workspace_clean": True,
    }
    values.update(overrides)
    return AgentSession(**values)


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
        "branch_name": "feature/p4-d",
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


def _operation(session=None, diff=None, **overrides):
    result = GitOperationDryRunBuilder.build_from_diff_evidence(
        agent_session=session or _session(),
        diff_evidence=diff or _dirty_diff(),
    )
    if not overrides:
        return result
    payload = result.model_dump()
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _evaluate(**overrides):
    session = overrides.pop("agent_session", _session())
    diff = overrides.pop("diff_evidence", _dirty_diff())
    operation = overrides.pop("operation_dry_run", _operation(session, diff))
    values = {
        "agent_session": session,
        "diff_evidence": diff,
        "operation_dry_run": operation,
        "delivery_audit_event_present": True,
        "delivery_audit_event_type": DELIVERY_AUDIT_COLLECTED_EVENT_TYPE,
        "delivery_audit_event_ready": True,
        "delivery_git_write_enabled": False,
    }
    values.update(overrides)
    return DeliveryGateEvidenceBuilder.evaluate(**values)


def test_evaluate_ready_delivery_gate_evidence_covers_g1_to_g21():
    session = _session()
    diff = _dirty_diff()
    operation = _operation(session, diff)

    result = _evaluate(
        agent_session=session,
        diff_evidence=diff,
        operation_dry_run=operation,
    )

    assert result.ready is True
    assert result.source == DELIVERY_GATE_EVIDENCE_SOURCE
    assert result.reason_code is None
    assert result.session_id == str(session.id)
    assert result.project_id == str(session.project_id)
    assert result.task_id == str(session.task_id)
    assert result.run_id == str(session.run_id)
    assert result.worktree_path == "/tmp/aido-worktree"
    assert result.branch_name == "feature/p4-d"
    assert result.proposed_operation == "git_add_commit"
    assert result.changed_files_count == 2
    assert result.changed_files == ["README.md", "src/app.py"]
    assert result.next_required_action == (
        DeliveryGateNextRequiredAction.AWAIT_USER_CONFIRMATION
    )
    assert result.user_confirmation_required is True
    assert result.human_approval_required is True
    assert result.summary_cn == "交付前检查已通过，可以进入用户确认。仍未执行提交或推送。"
    assert result.satisfied_conditions == [f"G{index}" for index in range(1, 22)]
    assert result.blocking_reasons == []
    assert result.safety_flags.gate_allows_write is False
    assert result.safety_flags.gate_allows_user_confirmation is True
    assert not any(copy in result.summary_cn for copy in FORBIDDEN_USER_VISIBLE_COPY)


def test_evaluate_blocks_when_audit_evidence_missing():
    result = _evaluate(
        delivery_audit_event_present=None,
        delivery_audit_event_type=None,
        delivery_audit_event_ready=None,
    )

    assert result.ready is False
    assert result.reason_code == "audit_evidence_missing"
    assert result.summary_cn == "缺少交付审计记录，无法进行交付前检查。"
    assert result.next_required_action == (
        DeliveryGateNextRequiredAction.RESOLVE_BLOCKING_CONDITIONS
    )
    assert "G21:audit_evidence_missing" in result.blocking_reasons
    assert result.proposed_operation == "none"
    assert result.safety_flags.gate_allows_write is False
    assert result.safety_flags.gate_allows_user_confirmation is False
    assert not any(copy in result.summary_cn for copy in FORBIDDEN_USER_VISIBLE_COPY)


def test_evaluate_blocked_reason_code_coverage():
    cases = [
        (
            {"agent_session": None},
            "agent_session_missing",
            "G1:agent_session_missing",
        ),
        (
            {"agent_session": _session(workspace_type=WorkspaceType.IN_PLACE)},
            "worktree_unavailable",
            "G2:worktree_unavailable",
        ),
        (
            {"agent_session": _session(branch_name=None)},
            "branch_missing",
            "G4:branch_missing",
        ),
        (
            {"agent_session": _session(workspace_clean=False)},
            "workspace_not_clean",
            "G5:workspace_not_clean",
        ),
        (
            {"diff_evidence": None},
            "diff_evidence_not_ready",
            "G6:diff_evidence_not_ready",
        ),
        (
            {"diff_evidence": _dirty_diff(has_changes=False, changed_files_count=0)},
            "no_changes",
            "G8:no_changes",
        ),
        (
            {"diff_evidence": _dirty_diff(git_add_triggered=True)},
            "diff_write_flag_triggered",
            "G10:diff_write_flag_triggered",
        ),
        (
            {"operation_dry_run": None},
            "operation_dry_run_not_ready",
            "G11:operation_dry_run_not_ready",
        ),
        (
            {
                "operation_dry_run": SimpleNamespace(
                    ready=True,
                    proposed_operation=GitOperationDryRunOperation.NONE,
                    user_confirmation_required=True,
                    human_approval_required=True,
                    changed_files_count=2,
                    changed_files=["README.md", "src/app.py"],
                    safety_flags=SimpleNamespace(),
                )
            },
            "unsupported_operation",
            "G13:unsupported_operation",
        ),
        (
            {
                "operation_dry_run": SimpleNamespace(
                    ready=True,
                    proposed_operation=GitOperationDryRunOperation.GIT_ADD_COMMIT,
                    user_confirmation_required=True,
                    human_approval_required=True,
                    changed_files_count=2,
                    changed_files=["README.md", "src/app.py"],
                    safety_flags=SimpleNamespace(git_commit_triggered=True),
                )
            },
            "operation_write_flag_triggered",
            "G16:operation_write_flag_triggered",
        ),
        (
            {
                "operation_dry_run": SimpleNamespace(
                    ready=True,
                    proposed_operation=GitOperationDryRunOperation.GIT_ADD_COMMIT,
                    user_confirmation_required=True,
                    human_approval_required=True,
                    changed_files_count=2,
                    changed_files=["README.md", "src/app.py"],
                    safety_flags=SimpleNamespace(operation_applied=True),
                )
            },
            "operation_already_applied",
            "G17:operation_already_applied",
        ),
        (
            {
                "operation_dry_run": SimpleNamespace(
                    ready=True,
                    proposed_operation=GitOperationDryRunOperation.GIT_ADD_COMMIT,
                    user_confirmation_required=True,
                    human_approval_required=True,
                    changed_files_count=2,
                    changed_files=["README.md", "src/app.py"],
                    safety_flags=SimpleNamespace(approval_granted=True),
                )
            },
            "approval_already_granted",
            "G18:approval_already_granted",
        ),
        (
            {"delivery_git_write_enabled": True},
            "feature_flag_enabled",
            "G19:feature_flag_enabled",
        ),
        (
            {
                "operation_dry_run": SimpleNamespace(
                    ready=True,
                    proposed_operation=GitOperationDryRunOperation.GIT_ADD_COMMIT,
                    user_confirmation_required=True,
                    human_approval_required=True,
                    changed_files_count=1,
                    changed_files=["README.md"],
                    safety_flags=SimpleNamespace(),
                )
            },
            "evidence_mismatch",
            "G20:evidence_mismatch",
        ),
    ]

    for overrides, expected_reason, expected_blocking_reason in cases:
        result = _evaluate(**overrides)

        assert result.ready is False
        assert result.reason_code == expected_reason
        assert expected_blocking_reason in result.blocking_reasons
        assert result.next_required_action == (
            DeliveryGateNextRequiredAction.RESOLVE_BLOCKING_CONDITIONS
        )
        assert result.proposed_operation == "none"
        assert result.user_confirmation_required is False
        assert result.safety_flags.gate_allows_write is False
        assert result.safety_flags.gate_allows_user_confirmation is False
        assert not any(copy in result.summary_cn for copy in FORBIDDEN_USER_VISIBLE_COPY)


def test_delivery_gate_evidence_safety_flags_reject_forbidden_true_flags():
    for flag_name in P4D_FORBIDDEN_TRUE_SAFETY_FLAGS:
        with pytest.raises(ValueError) as exc_info:
            DeliveryGateEvidenceSafetyFlags(**{flag_name: True})

        assert flag_name in str(exc_info.value)
        assert "must not execute Git" in str(exc_info.value)

    allowed = DeliveryGateEvidenceSafetyFlags(gate_allows_user_confirmation=True)
    assert allowed.gate_allows_user_confirmation is True
    assert allowed.gate_allows_write is False


def test_delivery_gate_evidence_result_rejects_inconsistent_ready_contract():
    with pytest.raises(ValueError) as exc_info:
        DeliveryGateEvidenceResult(
            ready=True,
            reason_code="audit_evidence_missing",
            session_id=str(uuid4()),
            project_id=str(uuid4()),
            task_id=str(uuid4()),
            run_id=str(uuid4()),
            proposed_operation="git_add_commit",
            changed_files_count=1,
            changed_files=["README.md"],
            next_required_action=DeliveryGateNextRequiredAction.AWAIT_USER_CONFIRMATION,
            user_confirmation_required=True,
            human_approval_required=True,
            summary_cn="交付前检查已通过，可以进入用户确认。仍未执行提交或推送。",
            satisfied_conditions=[f"G{index}" for index in range(1, 22)],
            safety_flags=DeliveryGateEvidenceSafetyFlags(
                gate_allows_user_confirmation=True
            ),
        )

    assert "must not include reason_code" in str(exc_info.value)
