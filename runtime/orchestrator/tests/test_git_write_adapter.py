from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError
import pytest

from app.domain.git_write import (
    REQUIRED_GIT_WRITE_SAFETY_GATES,
    GitWriteAdapterBlockReason,
    GitWriteAdapterMode,
    GitWriteAdapterResultStatus,
    GitWriteOperationKind,
    GitWritePreviewStatus,
    GitWriteSafetyGateCheck,
    GitWriteSafetyGateName,
    GitWriteSafetyGateSnapshot,
    GitWriteSafetyGateStatus,
)
from app.services.git_write_adapter import (
    DisabledGitWriteAdapter,
    FakeGitWriteAdapter,
    GitWriteAdapterEvidenceRecord,
    GitWriteAdapterOperationPlan,
    GitWriteAdapterRequest,
    GitWriteAdapterResult,
)
from app.services.git_write_preview_service import GitWriteChangedFileInput
from app.services.git_write_readback_service import (
    GitWriteReadbackConflictError,
    GitWriteReadbackService,
)


NOW = datetime(2026, 6, 9, 10, 0, tzinfo=timezone.utc)

FORBIDDEN_RESULT_KEYS = {
    "command",
    "raw_command",
    "raw_args",
    "env",
    "env_vars",
    "token_value",
    "auth_token",
    "cwd",
    "raw_output",
    "raw_error",
    "raw_diff",
}


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
        evaluated_at=NOW,
    )


def preview_ready_snapshot() -> GitWriteSafetyGateSnapshot:
    checks = []
    for gate in REQUIRED_GIT_WRITE_SAFETY_GATES:
        if gate in {
            GitWriteSafetyGateName.HUMAN_APPROVAL,
            GitWriteSafetyGateName.ONE_SHOT_TOKEN,
        }:
            checks.append(
                GitWriteSafetyGateCheck(
                    gate_name=gate,
                    status=GitWriteSafetyGateStatus.PENDING,
                    passed=False,
                    checked_at=NOW,
                )
            )
        else:
            checks.append(
                GitWriteSafetyGateCheck(
                    gate_name=gate,
                    status=GitWriteSafetyGateStatus.PASSED,
                    passed=True,
                    checked_at=NOW,
                )
            )
    return GitWriteSafetyGateSnapshot(gate_checks=checks, evaluated_at=NOW)


def make_request(**overrides: object) -> GitWriteAdapterRequest:
    payload = {
        "intent_id": "intent-1",
        "preview_id": "preview-1",
        "workspace_id": "workspace-1",
        "target_branch": "feature/git-write",
        "file_paths": ["runtime/orchestrator/app/domain/git_write.py"],
        "operation_kinds": [
            GitWriteOperationKind.STAGE_FILES,
            GitWriteOperationKind.CREATE_COMMIT,
        ],
        "approval_id": "approval-1",
        "one_shot_token_id": "token-1",
        "rollback_plan_id": "rollback-1",
        "requested_by": "user-1",
        "requested_at": NOW,
        "product_runtime_write_enabled": True,
        "adapter_mode": GitWriteAdapterMode.DISABLED,
        "preview_status": GitWritePreviewStatus.READY,
        "safety_snapshot": preview_ready_snapshot(),
    }
    payload.update(overrides)
    return GitWriteAdapterRequest(**payload)


def assert_no_forbidden_keys(value: object) -> None:
    if isinstance(value, dict):
        assert FORBIDDEN_RESULT_KEYS.isdisjoint(value.keys())
        for nested in value.values():
            assert_no_forbidden_keys(nested)
    elif isinstance(value, list):
        for item in value:
            assert_no_forbidden_keys(item)


def test_disabled_adapter_returns_disabled_when_product_flag_off() -> None:
    result = DisabledGitWriteAdapter().run(
        make_request(product_runtime_write_enabled=False),
    )

    assert result.status == GitWriteAdapterResultStatus.DISABLED
    assert result.blocking_reason == (
        GitWriteAdapterBlockReason.PRODUCT_RUNTIME_WRITE_DISABLED
    )
    assert result.executed is False
    assert result.product_runtime_git_write_executed is False


def test_disabled_adapter_does_not_run_when_product_flag_on() -> None:
    result = DisabledGitWriteAdapter().run(
        make_request(safety_snapshot=passed_snapshot()),
    )

    assert result.status == GitWriteAdapterResultStatus.DISABLED
    assert result.blocking_reason == GitWriteAdapterBlockReason.REAL_ADAPTER_NOT_STARTED
    assert result.executed is False
    assert result.product_runtime_git_write_executed is False


def test_non_disabled_adapter_mode_is_still_blocked_in_gitwrite_f() -> None:
    result = DisabledGitWriteAdapter().run(
        make_request(
            adapter_mode=GitWriteAdapterMode.REAL_CANDIDATE,
            safety_snapshot=passed_snapshot(),
        ),
    )

    assert result.status == GitWriteAdapterResultStatus.BLOCKED
    assert result.blocking_reason == GitWriteAdapterBlockReason.REAL_ADAPTER_NOT_STARTED
    assert result.executed is False


def test_preview_ready_without_full_write_gate_is_not_enough() -> None:
    request = make_request(safety_snapshot=preview_ready_snapshot())
    result = DisabledGitWriteAdapter().run(request)

    assert request.safety_snapshot.preview_gates_passed() is True
    assert request.safety_snapshot.all_passed is False
    assert result.status == GitWriteAdapterResultStatus.BLOCKED
    assert result.blocking_reason == (
        GitWriteAdapterBlockReason.FULL_WRITE_GATE_NOT_PASSED
    )
    assert "Preview gates alone are insufficient" in result.safe_summary


def test_blocked_preview_cannot_reach_adapter_candidate() -> None:
    result = DisabledGitWriteAdapter().run(
        make_request(
            preview_status=GitWritePreviewStatus.BLOCKED,
            safety_snapshot=preview_ready_snapshot(),
        ),
    )

    assert result.status == GitWriteAdapterResultStatus.BLOCKED
    assert result.blocking_reason == GitWriteAdapterBlockReason.PREVIEW_NOT_READY
    assert result.executed is False


def test_adapter_result_contains_only_safe_contract_fields() -> None:
    result = DisabledGitWriteAdapter().run(make_request())
    payload = result.model_dump(mode="json")

    assert result.executed is False
    assert result.product_runtime_git_write_executed is False
    assert_no_forbidden_keys(payload)

    with pytest.raises(ValidationError):
        GitWriteAdapterResult(
            **{
                **result.model_dump(),
                "executed": True,
            }
        )
    with pytest.raises(ValidationError):
        GitWriteAdapterResult(
            **{
                **result.model_dump(),
                "product_runtime_git_write_executed": True,
            }
        )


def test_operation_plan_is_contract_only_without_command_strings() -> None:
    plan = DisabledGitWriteAdapter().build_operation_plan(make_request())
    payload_text = str(plan.model_dump(mode="json"))

    assert plan.operation_sequence == [
        GitWriteOperationKind.STAGE_FILES,
        GitWriteOperationKind.CREATE_COMMIT,
    ]
    assert "command" not in GitWriteAdapterOperationPlan.model_fields
    assert "cwd" not in GitWriteAdapterOperationPlan.model_fields
    assert "env" not in GitWriteAdapterOperationPlan.model_fields
    assert "raw_args" not in GitWriteAdapterOperationPlan.model_fields
    assert "git add " not in payload_text
    assert "git commit " not in payload_text
    assert "git push " not in payload_text


def test_adapter_file_has_no_forbidden_runtime_imports_or_calls() -> None:
    source = Path("app/services/git_write_adapter.py").read_text(encoding="utf-8")

    forbidden_fragments = [
        "subprocess",
        "os.popen",
        "asyncio.subprocess",
        "os.environ",
        "app.api",
        "app.workers",
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
        "agent-orchestrator",
        "project-explore-one",
        "@aoagents",
        "workspace-worktree",
    ]
    for fragment in forbidden_fragments:
        assert fragment not in source


def test_fake_adapter_returns_ready_evidence_when_full_gates_passed() -> None:
    result = FakeGitWriteAdapter().run(
        make_request(
            adapter_mode=GitWriteAdapterMode.FAKE,
            safety_snapshot=passed_snapshot(),
        ),
    )

    assert result.status == GitWriteAdapterResultStatus.FAKE_EVIDENCE_READY
    assert result.executed is False
    assert result.product_runtime_git_write_executed is False
    assert result.blocking_reason is None
    assert result.fake_evidence is not None
    assert result.fake_evidence.evidence_id == "fake-evidence-intent-1"
    assert result.fake_evidence.adapter_mode == GitWriteAdapterMode.FAKE
    assert result.fake_evidence.fake_evidence_ready is True
    assert result.fake_evidence.fake_execution_recorded is True
    assert result.fake_evidence.product_runtime_git_write_executed is False
    assert "Fake evidence only" in result.fake_evidence.safe_summary
    assert_no_forbidden_keys(result.model_dump(mode="json"))


def test_fake_adapter_blocks_preview_ready_without_full_write_gate() -> None:
    request = make_request(
        adapter_mode=GitWriteAdapterMode.FAKE,
        safety_snapshot=preview_ready_snapshot(),
    )
    evidence = FakeGitWriteAdapter().build_fake_evidence(request)

    assert request.safety_snapshot.preview_gates_passed() is True
    assert request.safety_snapshot.all_passed is False
    assert evidence.status == GitWriteAdapterResultStatus.BLOCKED
    assert evidence.blocking_reason == GitWriteAdapterBlockReason.FULL_WRITE_GATE_NOT_PASSED
    assert evidence.fake_evidence_ready is False
    assert evidence.fake_execution_recorded is False
    assert evidence.product_runtime_git_write_executed is False


def test_fake_adapter_remains_no_write_when_product_flag_off() -> None:
    evidence = FakeGitWriteAdapter().build_fake_evidence(
        make_request(
            adapter_mode=GitWriteAdapterMode.FAKE,
            product_runtime_write_enabled=False,
            safety_snapshot=passed_snapshot(),
        ),
    )

    assert evidence.status == GitWriteAdapterResultStatus.DISABLED
    assert evidence.blocking_reason == (
        GitWriteAdapterBlockReason.PRODUCT_RUNTIME_WRITE_DISABLED
    )
    assert evidence.product_runtime_git_write_executed is False


def test_fake_adapter_blocks_non_fake_adapter_modes() -> None:
    evidence = FakeGitWriteAdapter().build_fake_evidence(
        make_request(
            adapter_mode=GitWriteAdapterMode.REAL_CANDIDATE,
            safety_snapshot=passed_snapshot(),
        ),
    )

    assert evidence.status == GitWriteAdapterResultStatus.BLOCKED
    assert evidence.blocking_reason == GitWriteAdapterBlockReason.REAL_ADAPTER_NOT_STARTED
    assert evidence.product_runtime_git_write_executed is False


def test_fake_evidence_record_rejects_executed_or_unsafe_shapes() -> None:
    evidence = FakeGitWriteAdapter().build_fake_evidence(
        make_request(
            adapter_mode=GitWriteAdapterMode.FAKE,
            safety_snapshot=passed_snapshot(),
        ),
    )

    with pytest.raises(ValidationError):
        GitWriteAdapterEvidenceRecord(
            **{
                **evidence.model_dump(),
                "product_runtime_git_write_executed": True,
            }
        )
    with pytest.raises(ValidationError):
        GitWriteAdapterEvidenceRecord(
            **{
                **evidence.model_dump(),
                "status": GitWriteAdapterResultStatus.EXECUTED,
            }
        )
    assert_no_forbidden_keys(evidence.model_dump(mode="json"))


def test_readback_service_records_fake_adapter_evidence_without_write() -> None:
    service = GitWriteReadbackService()
    record = service.create_intent(
        intent_id="intent-1",
        workspace_id="workspace-1",
        target_branch="feature/git-write",
        file_paths=["runtime/orchestrator/app/domain/git_write.py"],
        changed_files=[
            GitWriteChangedFileInput(
                path="runtime/orchestrator/app/domain/git_write.py",
                change_type="modified",
                additions=5,
                deletions=1,
                reviewed=True,
                safe_summary="Readback route update.",
            )
        ],
        allowed_branches=["feature/git-write"],
        feature_flag_enabled=True,
    )
    request = make_request(
        adapter_mode=GitWriteAdapterMode.FAKE,
        intent_id=record.intent.intent_id,
        preview_id=record.preview.preview_id,
        safety_snapshot=passed_snapshot(),
    )

    updated = service.record_fake_adapter_evidence(record.intent.intent_id, request)

    assert updated.adapter_evidence is not None
    assert updated.adapter_evidence.status == GitWriteAdapterResultStatus.FAKE_EVIDENCE_READY
    assert updated.product_runtime_git_write_executed is False
    assert [event.event_type for event in updated.audit_events][-1] == (
        "git_write.fake_adapter_evidence_recorded"
    )
    assert_no_forbidden_keys(updated.model_dump(mode="json"))


def test_readback_service_rejects_mismatched_fake_adapter_evidence() -> None:
    service = GitWriteReadbackService()
    record = service.create_intent(
        intent_id="intent-1",
        workspace_id="workspace-1",
        target_branch="feature/git-write",
        file_paths=["runtime/orchestrator/app/domain/git_write.py"],
        changed_files=[
            GitWriteChangedFileInput(
                path="runtime/orchestrator/app/domain/git_write.py",
                change_type="modified",
                additions=5,
                deletions=1,
                reviewed=True,
                safe_summary="Readback route update.",
            )
        ],
        allowed_branches=["feature/git-write"],
        feature_flag_enabled=True,
    )

    with pytest.raises(GitWriteReadbackConflictError):
        service.record_fake_adapter_evidence(
            record.intent.intent_id,
            make_request(
                adapter_mode=GitWriteAdapterMode.FAKE,
                intent_id="other-intent",
                preview_id=record.preview.preview_id,
                safety_snapshot=passed_snapshot(),
            ),
        )
