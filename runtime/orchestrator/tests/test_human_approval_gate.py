"""Targeted tests for P4-F human approval gate evidence builder."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domain.agent_session import AgentSession, WorkspaceType
from app.domain.delivery_gate_evidence import (
    DELIVERY_AUDIT_COLLECTED_EVENT_TYPE,
    DeliveryGateEvidenceBuilder,
    DeliveryGateEvidenceSafetyFlags,
    DeliveryGateNextRequiredAction,
)
from app.domain.git_operation_dry_run import (
    GitOperationDryRunBuilder,
    GitOperationDryRunOperation,
)
from app.domain.human_approval_gate import (
    DELIVERY_HUMAN_APPROVAL_SOURCE,
    HUMAN_APPROVAL_ACTION_APPROVE_GIT_ADD_COMMIT_PREVIEW,
    HUMAN_APPROVAL_SCOPE_GIT_ADD_COMMIT_PREVIEW,
    DeliveryHumanApprovalResult,
    HumanApprovalGateAction,
    HumanApprovalGateBuilder,
    HumanApprovalGateSafetyFlags,
    HumanApprovalRecord,
    HumanApprovalGateScope,
    P4F_FORBIDDEN_TRUE_SAFETY_FLAGS,
)
from app.services.git_diff_dry_run_runner import GitDiffDryRunResult


NOW = datetime(2026, 6, 6, 8, 0, tzinfo=timezone.utc)
CREATED_AT = NOW
EXPIRES_AT = NOW + timedelta(minutes=30)

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
        "branch_name": "feature/p4-f",
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
        "branch_name": "feature/p4-f",
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


def _delivery_gate(session=None, diff=None, operation=None, **overrides):
    result = DeliveryGateEvidenceBuilder.evaluate(
        agent_session=session or _session(),
        diff_evidence=diff or _dirty_diff(),
        operation_dry_run=operation or _operation(),
        delivery_audit_event_present=True,
        delivery_audit_event_type=DELIVERY_AUDIT_COLLECTED_EVENT_TYPE,
        delivery_audit_event_ready=True,
        delivery_git_write_enabled=False,
    )
    if not overrides:
        return result
    payload = result.model_dump()
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _evaluate(**overrides):
    session = overrides.pop("agent_session", _session())
    diff = overrides.pop("diff_evidence", _dirty_diff())
    base_operation = _operation(session, diff)
    operation = overrides.pop("operation_dry_run", base_operation)
    delivery_gate = overrides.pop(
        "delivery_gate_evidence", _delivery_gate(session, diff, base_operation)
    )
    values = {
        "agent_session": session,
        "operation_dry_run": operation,
        "delivery_gate_evidence": delivery_gate,
        "approval_id": "approval-001",
        "approval_requested_action": (
            HUMAN_APPROVAL_ACTION_APPROVE_GIT_ADD_COMMIT_PREVIEW
        ),
        "approval_confirmation_text": "确认提交预览：CONFIRM_GIT_ADD_COMMIT_PREVIEW",
        "approval_actor_id": "user-123",
        "approval_actor_display_name": "Owner",
        "approval_client_request_id": "client-request-001",
        "approval_created_at": CREATED_AT,
        "approval_scope": HUMAN_APPROVAL_SCOPE_GIT_ADD_COMMIT_PREVIEW,
        "approval_expires_at": EXPIRES_AT,
        "approval_applied": False,
        "approval_revoked": False,
        "delivery_git_write_enabled": False,
        "expected_changed_files": ["README.md", "src/app.py"],
        "expected_proposed_commit_message": (
            "chore: update 2 files from agent work"
        ),
        "current_time": NOW,
    }
    values.update(overrides)
    return HumanApprovalGateBuilder.evaluate(**values)


def test_evaluate_ready_human_approval_gate_outputs_auditable_record():
    session = _session()
    diff = _dirty_diff()
    operation = _operation(session, diff)
    delivery_gate = _delivery_gate(session, diff, operation)

    result = _evaluate(
        agent_session=session,
        operation_dry_run=operation,
        delivery_gate_evidence=delivery_gate,
    )

    assert result.ready is True
    assert result.source == DELIVERY_HUMAN_APPROVAL_SOURCE
    assert result.reason_code is None
    assert result.session_id == str(session.id)
    assert result.project_id == str(session.project_id)
    assert result.task_id == str(session.task_id)
    assert result.run_id == str(session.run_id)
    assert result.approval_required is True
    assert result.approval_granted is True
    assert result.approval_record is not None
    assert result.approval_id == "approval-001"
    assert result.approved_by == "user-123"
    assert result.approved_by_display_name == "Owner"
    assert result.approval_scope == HumanApprovalGateScope.GIT_ADD_COMMIT_PREVIEW
    assert result.approval_requested_action == (
        HumanApprovalGateAction.APPROVE_GIT_ADD_COMMIT_PREVIEW
    )
    assert result.approval_client_request_id == "client-request-001"
    assert result.approval_created_at == CREATED_AT
    assert result.approval_expires_at == EXPIRES_AT
    assert result.approval_applied is False
    assert result.approval_revoked is False
    assert result.approval_confirmation_fingerprint is not None
    assert len(result.approval_confirmation_fingerprint) == 64
    assert result.operation_dry_run_ready is True
    assert result.delivery_gate_evidence_ready is True
    assert result.delivery_gate_allows_user_confirmation is True
    assert result.delivery_gate_allows_write is False
    assert result.proposed_operation == "git_add_commit"
    assert result.proposed_commit_message == "chore: update 2 files from agent work"
    assert result.changed_files_count == 2
    assert result.changed_files == ["README.md", "src/app.py"]
    assert result.summary_cn == (
        "用户已确认提交预览，可进入下一阶段写入前安全检查。当前仍未写入仓库。"
    )
    assert result.blocking_reasons == []
    assert result.safety_flags.approval_granted is True
    assert result.safety_flags.approval_applied is False
    assert result.safety_flags.approval_revoked is False
    assert result.safety_flags.approval_expired is False
    assert result.safety_flags.gate_allows_write is False
    assert result.safety_flags.gate_allows_next_guardrail is True
    assert result.safety_flags.runs_write_git is False
    assert result.safety_flags.git_add_triggered is False
    assert result.safety_flags.git_commit_triggered is False
    assert not any(copy in result.summary_cn for copy in FORBIDDEN_USER_VISIBLE_COPY)


def test_evaluate_ready_generates_approval_id_without_persistence_or_git_writes():
    result = _evaluate(approval_id=None)

    assert result.ready is True
    assert result.approval_id is not None
    assert result.approval_id.startswith("hap_")
    assert result.approval_record is not None
    assert result.approval_record.approval_id == result.approval_id
    assert result.safety_flags.runs_git is False
    assert result.safety_flags.runs_write_git is False
    assert result.safety_flags.gate_allows_write is False


@pytest.mark.parametrize(
    ("overrides", "expected_reason", "expected_blocking_reason"),
    [
        ({"agent_session": None}, "agent_session_missing", "H1:agent_session_missing"),
        (
            {"operation_dry_run": None},
            "operation_dry_run_missing",
            "H2:operation_dry_run_missing",
        ),
        (
            {"operation_dry_run": SimpleNamespace(ready=False)},
            "operation_dry_run_not_ready",
            "H3:operation_dry_run_not_ready",
        ),
        (
            {"delivery_gate_evidence": None},
            "delivery_gate_evidence_missing",
            "H4:delivery_gate_evidence_missing",
        ),
        (
            {
                "delivery_gate_evidence": SimpleNamespace(
                    ready=False,
                    safety_flags=SimpleNamespace(
                        gate_allows_user_confirmation=False,
                        gate_allows_write=False,
                    ),
                    changed_files=[],
                    changed_files_count=0,
                )
            },
            "delivery_gate_not_ready",
            "H5:delivery_gate_not_ready",
        ),
        (
            {
                "delivery_gate_evidence": SimpleNamespace(
                    ready=True,
                    safety_flags=SimpleNamespace(
                        gate_allows_user_confirmation=False,
                        gate_allows_write=False,
                    ),
                    changed_files=["README.md", "src/app.py"],
                    changed_files_count=2,
                )
            },
            "user_confirmation_not_allowed",
            "H6:user_confirmation_not_allowed",
        ),
        (
            {"delivery_git_write_enabled": True},
            "write_gate_unexpectedly_enabled",
            "H7:write_gate_unexpectedly_enabled",
        ),
        (
            {"approval_requested_action": "approve_push_preview"},
            "unsupported_approval_action",
            "H8:unsupported_approval_action",
        ),
        (
            {"approval_actor_id": None},
            "approval_actor_missing",
            "H9:approval_actor_missing",
        ),
        (
            {"approval_scope": None},
            "approval_scope_missing",
            "H10:approval_scope_missing",
        ),
        (
            {"approval_scope": "git_push_preview"},
            "approval_scope_unsupported",
            "H11:approval_scope_unsupported",
        ),
        (
            {
                "operation_dry_run": SimpleNamespace(
                    ready=True,
                    proposed_operation=GitOperationDryRunOperation.NONE,
                    proposed_commit_message="chore: update 2 files from agent work",
                    changed_files_count=2,
                    changed_files=["README.md", "src/app.py"],
                    safety_flags=SimpleNamespace(),
                )
            },
            "approval_scope_mismatch",
            "H12:approval_scope_mismatch",
        ),
        (
            {"approval_client_request_id": None},
            "approval_request_id_missing",
            "H13:approval_request_id_missing",
        ),
        (
            {"approval_created_at": None},
            "approval_timestamp_missing",
            "H14:approval_timestamp_missing",
        ),
        (
            {"approval_expires_at": None},
            "approval_expiry_missing",
            "H15:approval_expiry_missing",
        ),
        (
            {"approval_expires_at": NOW - timedelta(minutes=1)},
            "approval_expired",
            "H16:approval_expired",
        ),
        (
            {"approval_applied": True},
            "approval_already_applied",
            "H17:approval_already_applied",
        ),
        (
            {"approval_revoked": True},
            "approval_revoked",
            "H18:approval_revoked",
        ),
        (
            {"approval_confirmation_text": "looks fine"},
            "approval_confirmation_missing",
            "H19:approval_confirmation_missing",
        ),
        (
            {"expected_changed_files": ["README.md"]},
            "changed_files_mismatch",
            "H20:changed_files_mismatch",
        ),
        (
            {"expected_proposed_commit_message": "chore: wrong message"},
            "commit_message_mismatch",
            "H21:commit_message_mismatch",
        ),
        (
            {
                "operation_dry_run": SimpleNamespace(
                    ready=True,
                    proposed_operation=GitOperationDryRunOperation.GIT_ADD_COMMIT,
                    proposed_commit_message="chore: update 2 files from agent work",
                    changed_files_count=2,
                    changed_files=["README.md", "src/app.py"],
                    safety_flags=SimpleNamespace(git_commit_triggered=True),
                )
            },
            "write_already_triggered",
            "H22:write_already_triggered",
        ),
    ],
)
def test_evaluate_blocked_reason_code_coverage(
    overrides, expected_reason, expected_blocking_reason
):
    result = _evaluate(**overrides)

    assert result.ready is False
    assert result.reason_code == expected_reason
    assert expected_blocking_reason in result.blocking_reasons
    assert result.approval_required is True
    assert result.approval_granted is False
    assert result.approval_record is None
    assert result.safety_flags.gate_allows_write is False
    assert result.safety_flags.gate_allows_next_guardrail is False
    assert result.safety_flags.runs_git is False
    assert result.safety_flags.runs_write_git is False
    assert result.safety_flags.git_add_triggered is False
    assert result.safety_flags.git_commit_triggered is False
    assert not any(copy in result.summary_cn for copy in FORBIDDEN_USER_VISIBLE_COPY)


def test_evaluate_blocks_when_delivery_gate_unexpectedly_allows_write():
    session = _session()
    diff = _dirty_diff()
    operation = _operation(session, diff)
    delivery_gate = SimpleNamespace(
        ready=True,
        proposed_operation="git_add_commit",
        changed_files_count=2,
        changed_files=["README.md", "src/app.py"],
        satisfied_conditions=[f"G{index}" for index in range(1, 22)],
        blocking_reasons=[],
        safety_flags=SimpleNamespace(
            gate_allows_user_confirmation=True,
            gate_allows_write=True,
        ),
    )

    result = _evaluate(
        agent_session=session,
        operation_dry_run=operation,
        delivery_gate_evidence=delivery_gate,
    )

    assert result.ready is False
    assert result.reason_code == "write_gate_unexpectedly_enabled"
    assert "H7:write_gate_unexpectedly_enabled" in result.blocking_reasons
    assert result.delivery_gate_allows_write is True
    assert result.safety_flags.gate_allows_write is False
    assert result.safety_flags.gate_allows_next_guardrail is False


def test_human_approval_record_rejects_applied_or_revoked_ready_record():
    base_values = {
        "approval_id": "approval-001",
        "approved_by": "user-123",
        "approval_scope": HumanApprovalGateScope.GIT_ADD_COMMIT_PREVIEW,
        "approval_requested_action": (
            HumanApprovalGateAction.APPROVE_GIT_ADD_COMMIT_PREVIEW
        ),
        "approval_client_request_id": "client-request-001",
        "approval_created_at": CREATED_AT,
        "approval_expires_at": EXPIRES_AT,
        "approval_confirmation_fingerprint": "a" * 64,
    }

    with pytest.raises(ValueError) as applied_exc:
        HumanApprovalRecord(**base_values, approval_applied=True)

    assert "must not be applied" in str(applied_exc.value)

    with pytest.raises(ValueError) as revoked_exc:
        HumanApprovalRecord(**base_values, approval_revoked=True)

    assert "must not be revoked" in str(revoked_exc.value)


def test_human_approval_gate_safety_flags_reject_forbidden_true_flags():
    for flag_name in P4F_FORBIDDEN_TRUE_SAFETY_FLAGS:
        with pytest.raises(ValueError) as exc_info:
            HumanApprovalGateSafetyFlags(**{flag_name: True})

        assert flag_name in str(exc_info.value)
        assert "must not execute Git" in str(exc_info.value)

    allowed = HumanApprovalGateSafetyFlags(
        approval_granted=True,
        gate_allows_next_guardrail=True,
    )
    assert allowed.approval_granted is True
    assert allowed.gate_allows_next_guardrail is True
    assert allowed.gate_allows_write is False


def test_human_approval_gate_safety_flags_reject_next_guardrail_without_approval():
    with pytest.raises(ValueError) as exc_info:
        HumanApprovalGateSafetyFlags(gate_allows_next_guardrail=True)

    assert "requires approval_granted" in str(exc_info.value)


def test_delivery_human_approval_result_rejects_inconsistent_ready_contract():
    with pytest.raises(ValueError) as exc_info:
        DeliveryHumanApprovalResult(
            ready=True,
            reason_code="approval_expired",
            summary_cn="用户已确认提交预览，可进入下一阶段写入前安全检查。当前仍未写入仓库。",
            session_id=str(uuid4()),
            project_id=str(uuid4()),
            task_id=str(uuid4()),
            run_id=str(uuid4()),
            approval_granted=True,
            approval_record=HumanApprovalRecord(
                approval_id="approval-001",
                approved_by="user-123",
                approval_scope=HumanApprovalGateScope.GIT_ADD_COMMIT_PREVIEW,
                approval_requested_action=(
                    HumanApprovalGateAction.APPROVE_GIT_ADD_COMMIT_PREVIEW
                ),
                approval_client_request_id="client-request-001",
                approval_created_at=CREATED_AT,
                approval_expires_at=EXPIRES_AT,
                approval_confirmation_fingerprint="a" * 64,
            ),
            operation_dry_run_ready=True,
            delivery_gate_evidence_ready=True,
            delivery_gate_allows_user_confirmation=True,
            delivery_gate_allows_write=False,
            proposed_operation="git_add_commit",
            proposed_commit_message="chore: update 2 files from agent work",
            changed_files_count=2,
            changed_files=["README.md", "src/app.py"],
            safety_flags=HumanApprovalGateSafetyFlags(
                approval_granted=True,
                gate_allows_next_guardrail=True,
            ),
        )

    assert "must not include reason_code" in str(exc_info.value)


def test_p4f_does_not_reuse_p4d_safety_flag_type_for_ready_approval():
    with pytest.raises(ValueError):
        DeliveryGateEvidenceSafetyFlags(approval_granted=True)

    result = _evaluate()
    assert result.ready is True
    assert isinstance(result.safety_flags, HumanApprovalGateSafetyFlags)
    assert result.safety_flags.approval_granted is True
    assert result.safety_flags.gate_allows_write is False
    assert result.safety_flags.gate_allows_next_guardrail is True
    assert (
        DeliveryGateNextRequiredAction.AWAIT_USER_CONFIRMATION.value
        == "await_user_confirmation"
    )
