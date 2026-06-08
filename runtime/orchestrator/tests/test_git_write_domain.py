from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain.git_write import (
    REQUIRED_GIT_WRITE_SAFETY_GATES,
    GitWriteApproval,
    GitWriteApprovalDecision,
    GitWriteAuditEvent,
    GitWriteBlockReason,
    GitWriteIntent,
    GitWriteIntentStatus,
    GitWriteOperationKind,
    GitWritePreview,
    GitWritePreviewFile,
    GitWritePreviewStatus,
    GitWriteRollbackPlan,
    GitWriteSafetyGateCheck,
    GitWriteSafetyGateName,
    GitWriteSafetyGateSnapshot,
    GitWriteSafetyGateStatus,
    GitWriteTokenStatus,
    OneShotApprovalToken,
    sanitize_path_hint,
)


NOW = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(minutes=15)


def passed_snapshot() -> GitWriteSafetyGateSnapshot:
    return GitWriteSafetyGateSnapshot(
        gate_checks=[
            GitWriteSafetyGateCheck(
                gate_name=gate,
                status=GitWriteSafetyGateStatus.PASSED,
                passed=True,
                checked_at=NOW,
            )
            for gate in REQUIRED_GIT_WRITE_SAFETY_GATES
        ],
        all_passed=False,
        evaluated_at=NOW,
    )


def blocked_snapshot(
    gate: GitWriteSafetyGateName = GitWriteSafetyGateName.SECRET_SCAN,
    reason: GitWriteBlockReason = GitWriteBlockReason.SECRET_DETECTED,
) -> GitWriteSafetyGateSnapshot:
    checks = []
    for gate_name in REQUIRED_GIT_WRITE_SAFETY_GATES:
        if gate_name == gate:
            checks.append(
                GitWriteSafetyGateCheck(
                    gate_name=gate_name,
                    status=GitWriteSafetyGateStatus.BLOCKED,
                    passed=False,
                    block_reason=reason,
                    checked_at=NOW,
                )
            )
        else:
            checks.append(
                GitWriteSafetyGateCheck(
                    gate_name=gate_name,
                    status=GitWriteSafetyGateStatus.PASSED,
                    passed=True,
                    checked_at=NOW,
                )
            )
    return GitWriteSafetyGateSnapshot(
        gate_checks=checks,
        all_passed=True,
        evaluated_at=NOW,
    )


def make_intent(**overrides: object) -> GitWriteIntent:
    payload = {
        "intent_id": "intent-1",
        "workspace_id": "workspace-1",
        "repository_id": "repo-1",
        "project_id": "project-1",
        "task_id": "task-1",
        "run_id": "run-1",
        "target_branch": "feature/git-write",
        "file_paths": ["runtime/orchestrator/app/domain/git_write.py"],
        "created_at": NOW,
        "updated_at": NOW,
    }
    payload.update(overrides)
    return GitWriteIntent(**payload)


def make_preview_file(**overrides: object) -> GitWritePreviewFile:
    payload = {
        "path": "runtime/orchestrator/app/domain/git_write.py",
        "change_type": "modified",
        "additions": 10,
        "deletions": 1,
        "reviewed": True,
    }
    payload.update(overrides)
    return GitWritePreviewFile(**payload)


def make_token(**overrides: object) -> OneShotApprovalToken:
    payload = {
        "token_id": "token-1",
        "token_hint": "approval hint redacted",
        "intent_id": "intent-1",
        "preview_id": "preview-1",
        "issued_at": NOW,
        "expires_at": LATER,
    }
    payload.update(overrides)
    return OneShotApprovalToken(**payload)


def test_git_write_intent_defaults_to_draft_not_approved() -> None:
    intent = make_intent()

    assert intent.status == GitWriteIntentStatus.DRAFT
    assert intent.status != GitWriteIntentStatus.APPROVED
    assert intent.requires_preview() is True


def test_git_write_intent_trims_strings_and_rejects_required_blank_values() -> None:
    intent = make_intent(
        intent_id=" intent-1 ",
        workspace_id=" workspace-1 ",
        target_branch=" feature/git-write ",
    )

    assert intent.intent_id == "intent-1"
    assert intent.workspace_id == "workspace-1"
    assert intent.target_branch == "feature/git-write"

    for field in ("intent_id", "workspace_id", "target_branch"):
        with pytest.raises(ValidationError):
            make_intent(**{field: "   "})


def test_operation_kinds_require_values_and_default_to_commit_only() -> None:
    intent = make_intent()

    assert intent.operation_kinds == [GitWriteOperationKind.CREATE_COMMIT]
    assert GitWriteOperationKind.PUSH_BRANCH not in intent.operation_kinds
    assert GitWriteOperationKind.CREATE_PR not in intent.operation_kinds

    with pytest.raises(ValidationError):
        make_intent(operation_kinds=[])


@pytest.mark.parametrize(
    "bad_path",
    [
        "/tmp/real-file.py",
        "~/real-file.py",
        "../outside.py",
        "src/../outside.py",
        "C:\\repo\\file.py",
        "safe\x00name.py",
    ],
)
def test_file_paths_dedupe_and_reject_unsafe_paths(bad_path: str) -> None:
    intent = make_intent(file_paths=[" a.py ", "a.py", "dir/b.py"])

    assert intent.file_paths == ["a.py", "dir/b.py"]

    with pytest.raises(ValidationError):
        make_intent(file_paths=[bad_path])


@pytest.mark.parametrize(
    "bad_branch",
    ["", "feature bad", "feature..bad", "HEAD", "feature~bad", "bad^", "bad:", "bad?", "bad*", "bad[", "bad\\name", "/bad", "bad/"],
)
def test_target_branch_rejects_unsafe_values(bad_branch: str) -> None:
    with pytest.raises(ValidationError):
        make_intent(target_branch=bad_branch)


def test_safe_text_fields_reject_suspected_credentials() -> None:
    with pytest.raises(ValidationError):
        make_intent(commit_message="use api key abc")

    with pytest.raises(ValidationError):
        GitWritePreview(
            preview_id="preview-1",
            intent_id="intent-1",
            status=GitWritePreviewStatus.PENDING,
            target_branch="feature/git-write",
            files=[make_preview_file()],
            diff_summary="contains bearer value",
            safety_snapshot=passed_snapshot(),
            created_at=NOW,
        )

    with pytest.raises(ValidationError):
        GitWriteApproval(
            approval_id="approval-1",
            intent_id="intent-1",
            preview_id="preview-1",
            approval_note="token leaked here",
            safety_snapshot=passed_snapshot(),
        )


def test_safety_gate_check_passed_status_requires_passed_true_without_reason() -> None:
    gate = GitWriteSafetyGateCheck(
        gate_name=GitWriteSafetyGateName.FEATURE_FLAG,
        status=GitWriteSafetyGateStatus.PASSED,
        passed=True,
    )

    assert gate.block_reason is None

    with pytest.raises(ValidationError):
        GitWriteSafetyGateCheck(
            gate_name=GitWriteSafetyGateName.FEATURE_FLAG,
            status=GitWriteSafetyGateStatus.PASSED,
            passed=False,
        )
    with pytest.raises(ValidationError):
        GitWriteSafetyGateCheck(
            gate_name=GitWriteSafetyGateName.FEATURE_FLAG,
            status=GitWriteSafetyGateStatus.PASSED,
            passed=True,
            block_reason=GitWriteBlockReason.FEATURE_FLAG_DISABLED,
        )


def test_safety_gate_check_blocked_status_requires_reason_and_passed_false() -> None:
    gate = GitWriteSafetyGateCheck(
        gate_name=GitWriteSafetyGateName.FEATURE_FLAG,
        status=GitWriteSafetyGateStatus.BLOCKED,
        passed=False,
        block_reason=GitWriteBlockReason.FEATURE_FLAG_DISABLED,
    )

    assert gate.passed is False

    with pytest.raises(ValidationError):
        GitWriteSafetyGateCheck(
            gate_name=GitWriteSafetyGateName.FEATURE_FLAG,
            status=GitWriteSafetyGateStatus.BLOCKED,
            passed=False,
        )
    with pytest.raises(ValidationError):
        GitWriteSafetyGateCheck(
            gate_name=GitWriteSafetyGateName.FEATURE_FLAG,
            status=GitWriteSafetyGateStatus.BLOCKED,
            passed=True,
            block_reason=GitWriteBlockReason.FEATURE_FLAG_DISABLED,
        )


def test_safety_gate_snapshot_requires_all_required_gates() -> None:
    with pytest.raises(ValidationError):
        GitWriteSafetyGateSnapshot(
            gate_checks=[
                GitWriteSafetyGateCheck(
                    gate_name=GitWriteSafetyGateName.FEATURE_FLAG,
                    status=GitWriteSafetyGateStatus.PASSED,
                    passed=True,
                )
            ],
            evaluated_at=NOW,
        )


def test_safety_gate_snapshot_derives_all_passed_and_blocking_reasons() -> None:
    snapshot = blocked_snapshot()

    assert snapshot.all_passed is False
    assert snapshot.blocking_reasons == [GitWriteBlockReason.SECRET_DETECTED]
    assert snapshot.failed_gates()[0].gate_name == GitWriteSafetyGateName.SECRET_SCAN
    assert snapshot.get_gate(GitWriteSafetyGateName.FEATURE_FLAG).passed is True


def test_approved_intent_requires_passing_safety_snapshot() -> None:
    with pytest.raises(ValidationError):
        make_intent(status=GitWriteIntentStatus.APPROVED)

    with pytest.raises(ValidationError):
        make_intent(
            status=GitWriteIntentStatus.APPROVED,
            safety_snapshot=blocked_snapshot(),
        )

    intent = make_intent(
        status=GitWriteIntentStatus.APPROVED,
        safety_snapshot=passed_snapshot(),
    )
    assert intent.status == GitWriteIntentStatus.APPROVED


def test_preview_file_additions_and_deletions_cannot_be_negative() -> None:
    with pytest.raises(ValidationError):
        make_preview_file(additions=-1)
    with pytest.raises(ValidationError):
        make_preview_file(deletions=-1)


def test_preview_with_secret_flagged_file_must_be_blocked() -> None:
    flagged_file = make_preview_file(contains_secret=True)

    with pytest.raises(ValidationError):
        GitWritePreview(
            preview_id="preview-1",
            intent_id="intent-1",
            status=GitWritePreviewStatus.READY,
            target_branch="feature/git-write",
            files=[flagged_file],
            safety_snapshot=passed_snapshot(),
            created_at=NOW,
        )

    preview = GitWritePreview(
        preview_id="preview-1",
        intent_id="intent-1",
        status=GitWritePreviewStatus.BLOCKED,
        target_branch="feature/git-write",
        files=[flagged_file],
        safety_snapshot=blocked_snapshot(),
        created_at=NOW,
    )
    assert preview.status == GitWritePreviewStatus.BLOCKED


def test_ready_preview_requires_reviewed_files_and_passing_snapshot() -> None:
    with pytest.raises(ValidationError):
        GitWritePreview(
            preview_id="preview-1",
            intent_id="intent-1",
            status=GitWritePreviewStatus.READY,
            target_branch="feature/git-write",
            files=[make_preview_file(reviewed=False)],
            safety_snapshot=passed_snapshot(),
            created_at=NOW,
        )

    with pytest.raises(ValidationError):
        GitWritePreview(
            preview_id="preview-1",
            intent_id="intent-1",
            status=GitWritePreviewStatus.READY,
            target_branch="feature/git-write",
            files=[make_preview_file()],
            safety_snapshot=blocked_snapshot(),
            created_at=NOW,
        )

    preview = GitWritePreview(
        preview_id="preview-1",
        intent_id="intent-1",
        status=GitWritePreviewStatus.READY,
        target_branch="feature/git-write",
        files=[make_preview_file()],
        safety_snapshot=passed_snapshot(),
        created_at=NOW,
    )
    assert preview.ready_file_paths() == ["runtime/orchestrator/app/domain/git_write.py"]


def test_preview_contract_stores_summary_not_raw_diff() -> None:
    preview = GitWritePreview(
        preview_id="preview-1",
        intent_id="intent-1",
        status=GitWritePreviewStatus.READY,
        target_branch="feature/git-write",
        files=[make_preview_file()],
        diff_summary="1 file changed with domain contract updates",
        safety_snapshot=passed_snapshot(),
        created_at=NOW,
    )

    assert preview.diff_summary == "1 file changed with domain contract updates"
    assert "raw_diff" not in GitWritePreview.model_fields


def test_rollback_plan_is_contract_only() -> None:
    plan = GitWriteRollbackPlan(
        plan_id="plan-1",
        summary="Restore branch pointer from saved hint.",
        restore_branch_hint="feature/git-write",
        restore_commit_hint="abc1234",
        generated_at=NOW,
    )

    assert plan.plan_id == "plan-1"
    assert "execute" not in GitWriteRollbackPlan.model_fields


def test_one_shot_token_does_not_store_real_token_or_credential_like_hint() -> None:
    token = make_token(token_hint="redacted approval hint")

    assert token.token_hint == "redacted approval hint"
    assert "token" not in token.token_hint.lower()

    for bad_hint in ("bearer abc", "sk-real", "secret value", "password value"):
        with pytest.raises(ValidationError):
            make_token(token_hint=bad_hint)


def test_one_shot_token_expiry_must_be_later_than_issue_time() -> None:
    with pytest.raises(ValidationError):
        make_token(expires_at=NOW)


def test_one_shot_token_consumed_status_requires_consumed_at() -> None:
    with pytest.raises(ValidationError):
        make_token(status=GitWriteTokenStatus.CONSUMED)

    token = make_token(status=GitWriteTokenStatus.CONSUMED, consumed_at=NOW)
    assert token.is_active(NOW + timedelta(minutes=1)) is False


def test_git_write_approval_defaults_to_pending_not_approved() -> None:
    approval = GitWriteApproval(
        approval_id="approval-1",
        intent_id="intent-1",
        preview_id="preview-1",
        safety_snapshot=passed_snapshot(),
    )

    assert approval.decision == GitWriteApprovalDecision.PENDING
    assert approval.is_approved() is False


def test_approved_decision_requires_actor_time_token_and_passing_snapshot() -> None:
    with pytest.raises(ValidationError):
        GitWriteApproval(
            approval_id="approval-1",
            intent_id="intent-1",
            preview_id="preview-1",
            decision=GitWriteApprovalDecision.APPROVED,
            safety_snapshot=passed_snapshot(),
        )

    with pytest.raises(ValidationError):
        GitWriteApproval(
            approval_id="approval-1",
            intent_id="intent-1",
            preview_id="preview-1",
            decision=GitWriteApprovalDecision.APPROVED,
            decided_by="user-1",
            decided_at=NOW,
            one_shot_token=make_token(status=GitWriteTokenStatus.ACTIVE),
            safety_snapshot=blocked_snapshot(),
        )

    approval = GitWriteApproval(
        approval_id="approval-1",
        intent_id="intent-1",
        preview_id="preview-1",
        decision=GitWriteApprovalDecision.APPROVED,
        decided_by="user-1",
        decided_at=NOW,
        one_shot_token=make_token(status=GitWriteTokenStatus.ACTIVE),
        safety_snapshot=passed_snapshot(),
    )
    assert approval.is_approved() is True


def test_audit_event_append_only_defaults_true() -> None:
    event = GitWriteAuditEvent(
        event_id="event-1",
        intent_id="intent-1",
        event_type="git_write.intent_created",
        timestamp=NOW,
        safe_summary="Intent recorded.",
    )

    assert event.append_only is True


def test_audit_event_rejects_raw_execution_fields() -> None:
    forbidden_fields = {
        "raw_command",
        "raw_env",
        "raw_diff",
        "command",
        "env",
        "token",
        "secret",
        "path",
    }

    assert forbidden_fields.isdisjoint(GitWriteAuditEvent.model_fields)
    with pytest.raises(ValidationError):
        GitWriteAuditEvent(
            event_id="event-1",
            intent_id="intent-1",
            event_type="git_write.intent_created",
            timestamp=NOW,
            metadata_count=-1,
        )


def test_path_hints_are_redacted_for_host_specific_shapes() -> None:
    assert sanitize_path_hint("/Users/someone/repo") == "workspace hint provided"
    assert sanitize_path_hint("~/repo") == "workspace hint provided"
    assert sanitize_path_hint("C:\\repo") == "workspace hint provided"
    assert sanitize_path_hint("\\\\server\\repo") == "workspace hint provided"
    assert sanitize_path_hint("repo/worktree") == "repo/worktree"


def test_domain_file_has_no_forbidden_layer_or_execution_imports() -> None:
    source = Path("app/domain/git_write.py").read_text(encoding="utf-8")

    assert "app.services" not in source
    assert "app.api" not in source
    assert "app.workers" not in source
    assert "subprocess" not in source
    assert "os.popen" not in source
    assert "asyncio.subprocess" not in source


def test_domain_file_has_no_git_write_execution_command_literals() -> None:
    source = Path("app/domain/git_write.py").read_text(encoding="utf-8")

    forbidden_literals = [
        "git add ",
        "git commit ",
        "git push ",
        "merge_pr",
    ]
    for literal in forbidden_literals:
        assert literal not in source


def test_domain_models_have_no_forbidden_execution_fields() -> None:
    forbidden_fields = {
        "command",
        "raw_command",
        "raw_args",
        "env",
        "env_vars",
        "api_key",
        "token_value",
        "auth_token",
        "native_config_path",
        "cli_path",
        "process_handle",
        "log_path",
        "raw_output",
        "raw_error",
        "cwd",
    }
    models = [
        GitWriteSafetyGateCheck,
        GitWriteSafetyGateSnapshot,
        GitWriteIntent,
        GitWritePreviewFile,
        GitWriteRollbackPlan,
        GitWritePreview,
        OneShotApprovalToken,
        GitWriteApproval,
        GitWriteAuditEvent,
    ]

    for model in models:
        assert forbidden_fields.isdisjoint(model.model_fields), model.__name__


def test_reference_project_path_does_not_appear_in_domain_file() -> None:
    source = Path("app/domain/git_write.py").read_text(encoding="utf-8")

    assert "agent-orchestrator" not in source
    assert "project-explore-one" not in source
