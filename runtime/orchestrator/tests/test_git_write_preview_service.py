from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.domain.git_write import (
    GitWriteBlockReason,
    GitWriteIntent,
    GitWritePreviewStatus,
    GitWritePreview,
    GitWriteRollbackPlan,
    GitWriteSafetyGateName,
)
from app.services.git_write_preview_service import (
    GitWriteChangedFileInput,
    GitWritePreviewRequest,
    GitWritePreviewService,
)


NOW = datetime(2026, 6, 9, 9, 0, tzinfo=timezone.utc)


def make_intent(**overrides: object) -> GitWriteIntent:
    payload = {
        "intent_id": "intent-1",
        "workspace_id": "workspace-1",
        "repository_id": "repo-1",
        "project_id": "project-1",
        "task_id": "task-1",
        "run_id": "run-1",
        "target_branch": "feature/git-write",
        "base_branch": "main",
        "file_paths": ["runtime/orchestrator/app/domain/git_write.py"],
        "commit_message": "Add GitWrite preview service",
        "created_at": NOW,
        "updated_at": NOW,
    }
    payload.update(overrides)
    return GitWriteIntent(**payload)


def make_changed_file(**overrides: object) -> GitWriteChangedFileInput:
    payload = {
        "path": "runtime/orchestrator/app/domain/git_write.py",
        "change_type": "modified",
        "additions": 24,
        "deletions": 2,
        "reviewed": True,
        "safe_summary": "Preview service contract update.",
    }
    payload.update(overrides)
    return GitWriteChangedFileInput(**payload)


def make_request(**overrides: object) -> GitWritePreviewRequest:
    payload = {
        "intent": make_intent(),
        "changed_files": [make_changed_file()],
        "allowed_branches": ["feature/git-write"],
        "feature_flag_enabled": True,
        "diff_summary": "1 file changed with preview service coverage.",
        "audit_event_planned": True,
        "requested_at": NOW,
    }
    payload.update(overrides)
    return GitWritePreviewRequest(**payload)


def build_preview(**overrides: object):
    return GitWritePreviewService().build_preview(make_request(**overrides))


def gate_reason(preview, gate_name: GitWriteSafetyGateName):
    gate = preview.safety_snapshot.get_gate(gate_name)
    return gate.block_reason


def test_feature_flag_off_blocks_preview() -> None:
    preview = build_preview(feature_flag_enabled=False)

    assert preview.status == GitWritePreviewStatus.BLOCKED
    assert gate_reason(preview, GitWriteSafetyGateName.FEATURE_FLAG) == (
        GitWriteBlockReason.FEATURE_FLAG_DISABLED
    )


def test_empty_allowed_branches_blocks_target_branch() -> None:
    preview = build_preview(allowed_branches=[])

    assert preview.status == GitWritePreviewStatus.BLOCKED
    assert gate_reason(preview, GitWriteSafetyGateName.TARGET_BRANCH_ALLOWLIST) == (
        GitWriteBlockReason.TARGET_BRANCH_NOT_ALLOWED
    )


def test_target_branch_not_in_allowlist_blocks_preview() -> None:
    preview = build_preview(allowed_branches=["release/allowed"])

    assert preview.status == GitWritePreviewStatus.BLOCKED
    assert gate_reason(preview, GitWriteSafetyGateName.TARGET_BRANCH_ALLOWLIST) == (
        GitWriteBlockReason.TARGET_BRANCH_NOT_ALLOWED
    )


def test_diff_text_with_suspected_credential_blocks_without_echoing_value() -> None:
    raw_value = "sk-live-123456789"
    preview = build_preview(diff_text=f"+ OPENAI_API_KEY={raw_value}")
    payload = preview.model_dump(mode="json")
    payload_text = str(payload)

    assert preview.status == GitWritePreviewStatus.BLOCKED
    assert gate_reason(preview, GitWriteSafetyGateName.SECRET_SCAN) == (
        GitWriteBlockReason.SECRET_DETECTED
    )
    assert raw_value not in payload_text
    assert "OPENAI_API_KEY" not in payload_text


def test_unreviewed_file_blocks_preview() -> None:
    preview = build_preview(changed_files=[make_changed_file(reviewed=False)])

    assert preview.status == GitWritePreviewStatus.BLOCKED
    assert gate_reason(preview, GitWriteSafetyGateName.REVIEWED_FILES) == (
        GitWriteBlockReason.UNREVIEWED_FILES
    )


def test_force_push_flag_blocks_preview() -> None:
    preview = build_preview(force_push_requested=True)

    assert preview.status == GitWritePreviewStatus.BLOCKED
    assert gate_reason(preview, GitWriteSafetyGateName.FORCE_PUSH_DETECTION) == (
        GitWriteBlockReason.FORCE_PUSH_DETECTED
    )


def test_force_push_operation_marker_blocks_preview() -> None:
    preview = build_preview(operation_kinds=["force_push"])

    assert preview.status == GitWritePreviewStatus.BLOCKED
    assert gate_reason(preview, GitWriteSafetyGateName.FORCE_PUSH_DETECTION) == (
        GitWriteBlockReason.FORCE_PUSH_DETECTED
    )


def test_destructive_operation_flag_blocks_preview() -> None:
    preview = build_preview(destructive_operation_requested=True)

    assert preview.status == GitWritePreviewStatus.BLOCKED
    assert gate_reason(preview, GitWriteSafetyGateName.DESTRUCTIVE_OPERATION_BLOCK) == (
        GitWriteBlockReason.DESTRUCTIVE_OPERATION_DETECTED
    )


def test_destructive_operation_marker_blocks_preview() -> None:
    preview = build_preview(operation_kinds=["reset"])

    assert preview.status == GitWritePreviewStatus.BLOCKED
    assert gate_reason(preview, GitWriteSafetyGateName.DESTRUCTIVE_OPERATION_BLOCK) == (
        GitWriteBlockReason.DESTRUCTIVE_OPERATION_DETECTED
    )


def test_all_gate_inputs_pass_create_ready_preview_only() -> None:
    preview = build_preview()

    assert preview.status == GitWritePreviewStatus.READY
    assert preview.safety_snapshot.all_passed is True
    assert preview.rollback_plan is not None
    assert preview.rollback_plan.summary


def test_ready_preview_does_not_store_raw_diff_field() -> None:
    preview = build_preview(diff_text="+ safe change")
    payload = preview.model_dump()

    assert preview.status == GitWritePreviewStatus.READY
    assert "raw_diff" not in GitWritePreview.model_fields
    assert "raw_diff" not in payload
    assert "+ safe change" not in str(payload)


def test_rollback_plan_is_contract_only_and_does_not_execute() -> None:
    preview = build_preview(rollback_base_commit_hint="abc1234")
    plan = preview.rollback_plan

    assert plan is not None
    assert plan.restore_branch_hint == "main"
    assert plan.restore_commit_hint == "abc1234"
    assert "execute" not in GitWriteRollbackPlan.model_fields


def test_preview_service_file_has_no_forbidden_runtime_imports() -> None:
    source = Path("app/services/git_write_preview_service.py").read_text(encoding="utf-8")

    forbidden_fragments = [
        "subprocess",
        "os.popen",
        "asyncio.subprocess",
        "os.environ",
        "app.api",
        "app.workers",
    ]
    for fragment in forbidden_fragments:
        assert fragment not in source


def test_preview_service_file_has_no_runtime_git_write_command_literals() -> None:
    source = Path("app/services/git_write_preview_service.py").read_text(encoding="utf-8")

    forbidden_literals = [
        "git add ",
        "git commit ",
        "git push ",
        "git merge ",
        "git reset ",
        "git checkout ",
        "git switch ",
        "git rebase ",
        "git stash ",
        "git tag ",
    ]
    for literal in forbidden_literals:
        assert literal not in source


def test_preview_service_file_has_no_reference_project_identifiers() -> None:
    source = Path("app/services/git_write_preview_service.py").read_text(encoding="utf-8")

    forbidden_fragments = [
        "agent-orchestrator",
        "project-explore-one",
        "@aoagents",
        "workspace-worktree",
    ]
    for fragment in forbidden_fragments:
        assert fragment not in source
