from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain.real_git_write_pilot import (
    PREFLIGHT_REAL_GIT_WRITE_PILOT_GATES,
    REQUIRED_REAL_GIT_WRITE_PILOT_GATES,
    RealGitWritePilotApproval,
    RealGitWritePilotApprovalDecision,
    RealGitWritePilotAuditEvent,
    RealGitWritePilotBlockReason,
    RealGitWritePilotGateCheck,
    RealGitWritePilotGateName,
    RealGitWritePilotGateSnapshot,
    RealGitWritePilotGateStatus,
    RealGitWritePilotOperationKind,
    RealGitWritePilotRequest,
    RealGitWritePilotRollbackPlan,
    RealGitWritePilotStatus,
)


NOW = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(minutes=5)
BASE_COMMIT = "29d5ac233032c704f862968993b661abe79feef1"


def _passed_check(gate_name: RealGitWritePilotGateName) -> RealGitWritePilotGateCheck:
    return RealGitWritePilotGateCheck(
        gate_name=gate_name,
        status=RealGitWritePilotGateStatus.PASSED,
        passed=True,
        checked_at=NOW,
    )


def _pending_check(gate_name: RealGitWritePilotGateName) -> RealGitWritePilotGateCheck:
    return RealGitWritePilotGateCheck(
        gate_name=gate_name,
        status=RealGitWritePilotGateStatus.PENDING,
        passed=False,
        checked_at=NOW,
    )


def _blocked_check(
    gate_name: RealGitWritePilotGateName,
    reason: RealGitWritePilotBlockReason,
) -> RealGitWritePilotGateCheck:
    return RealGitWritePilotGateCheck(
        gate_name=gate_name,
        status=RealGitWritePilotGateStatus.BLOCKED,
        passed=False,
        block_reason=reason,
        checked_at=NOW,
    )


def _all_passed_snapshot() -> RealGitWritePilotGateSnapshot:
    return RealGitWritePilotGateSnapshot(
        gate_checks=[_passed_check(gate) for gate in REQUIRED_REAL_GIT_WRITE_PILOT_GATES],
        evaluated_at=NOW,
    )


def _preflight_only_snapshot() -> RealGitWritePilotGateSnapshot:
    checks = []
    for gate in REQUIRED_REAL_GIT_WRITE_PILOT_GATES:
        if gate in PREFLIGHT_REAL_GIT_WRITE_PILOT_GATES:
            checks.append(_passed_check(gate))
        else:
            checks.append(_pending_check(gate))
    return RealGitWritePilotGateSnapshot(gate_checks=checks, evaluated_at=NOW)


def _early_gates_snapshot() -> RealGitWritePilotGateSnapshot:
    pending_gates = {
        RealGitWritePilotGateName.HUMAN_APPROVAL,
        RealGitWritePilotGateName.ONE_SHOT_TOKEN,
        RealGitWritePilotGateName.MANUAL_FINAL_CONFIRMATION,
    }
    checks = [
        _pending_check(gate) if gate in pending_gates else _passed_check(gate)
        for gate in REQUIRED_REAL_GIT_WRITE_PILOT_GATES
    ]
    return RealGitWritePilotGateSnapshot(gate_checks=checks, evaluated_at=NOW)


def _request(**overrides: object) -> RealGitWritePilotRequest:
    payload = {
        "pilot_id": "pilot-1",
        "project_id": "project-1",
        "run_id": "run-1",
        "executor_id": "codex",
        "workspace_id": "workspace-1",
        "repository_id": "repo-1",
        "base_commit": BASE_COMMIT,
        "target_branch": "ai/gitwrite-pilot/2026-06-09-doc-only",
        "file_paths": ["docs/product/pilot.md"],
        "requested_by": "user-1",
        "requested_at": NOW,
        "expires_at": LATER,
        "gate_snapshot": _all_passed_snapshot(),
    }
    payload.update(overrides)
    return RealGitWritePilotRequest(**payload)


def test_required_gates_must_all_be_present() -> None:
    missing_manual_confirmation = [
        _passed_check(gate)
        for gate in REQUIRED_REAL_GIT_WRITE_PILOT_GATES
        if gate != RealGitWritePilotGateName.MANUAL_FINAL_CONFIRMATION
    ]

    with pytest.raises(ValidationError):
        RealGitWritePilotGateSnapshot(
            gate_checks=missing_manual_confirmation,
            evaluated_at=NOW,
        )


def test_all_passed_is_derived_and_cannot_be_forged() -> None:
    blocked_gate = _blocked_check(
        RealGitWritePilotGateName.SECRET_SCAN,
        RealGitWritePilotBlockReason.SECRET_DETECTED,
    )
    checks = [
        blocked_gate if gate == RealGitWritePilotGateName.SECRET_SCAN else _passed_check(gate)
        for gate in REQUIRED_REAL_GIT_WRITE_PILOT_GATES
    ]

    snapshot = RealGitWritePilotGateSnapshot(
        gate_checks=checks,
        all_required_gates_present=False,
        all_passed=True,
        blocking_reasons=[],
        evaluated_at=NOW,
    )

    assert snapshot.all_required_gates_present is True
    assert snapshot.all_passed is False
    assert snapshot.blocking_reasons == [RealGitWritePilotBlockReason.SECRET_DETECTED]
    assert snapshot.failed_gates() == [blocked_gate]
    assert snapshot.get_gate(RealGitWritePilotGateName.SECRET_SCAN) == blocked_gate


def test_early_gates_without_approval_token_and_final_confirmation_are_not_all_passed() -> None:
    snapshot = _early_gates_snapshot()

    assert snapshot.all_passed is False
    assert snapshot.pilot_preflight_gates_passed() is False
    assert snapshot.get_gate(RealGitWritePilotGateName.HUMAN_APPROVAL).passed is False
    assert snapshot.get_gate(RealGitWritePilotGateName.ONE_SHOT_TOKEN).passed is False
    assert snapshot.get_gate(RealGitWritePilotGateName.MANUAL_FINAL_CONFIRMATION).passed is False


@pytest.mark.parametrize(
    "target_branch",
    [
        "main",
        "master",
        "release",
        "release/2026-06-09",
        "production",
        "production/hotfix",
        "staging",
        "staging/check",
        "gh-pages",
        "gh-pages/docs",
    ],
)
def test_target_branch_blocks_protected_branches(target_branch: str) -> None:
    with pytest.raises(ValidationError):
        _request(target_branch=target_branch)


@pytest.mark.parametrize(
    "target_branch",
    [
        "ai/gitwrite-pilot/2026-06-09",
        "ai/gitwrite-pilot/20260609-doc-only",
        "feature/gitwrite-pilot/2026-06-09-doc-only",
        "ai/gitwrite-pilot/2026-06-09-code",
        "ai/gitwrite-pilot/2026-6-9-doc-only",
    ],
)
def test_target_branch_must_match_doc_only_pilot_pattern(target_branch: str) -> None:
    with pytest.raises(ValidationError):
        _request(target_branch=target_branch)


@pytest.mark.parametrize(
    "file_paths",
    [
        ["runtime/orchestrator/app/domain/real_git_write_pilot.py"],
        ["docs/pilot.txt"],
        ["README.md"],
        ["../docs/pilot.md"],
        ["/tmp/docs/pilot.md"],
        ["docs/pilot.yaml"],
    ],
)
def test_file_paths_must_be_docs_markdown_only(file_paths: list[str]) -> None:
    with pytest.raises(ValidationError):
        _request(file_paths=file_paths)


def test_file_paths_are_trimmed_and_deduped() -> None:
    request = _request(file_paths=[" docs/pilot.md ", "docs/pilot.md", "docs/sub/pilot.md"])

    assert request.file_paths == ["docs/pilot.md", "docs/sub/pilot.md"]


def test_product_runtime_write_flag_must_remain_false() -> None:
    with pytest.raises(ValidationError):
        _request(product_runtime_git_write_executed=True)


def test_real_executor_started_flag_must_remain_false() -> None:
    with pytest.raises(ValidationError):
        _request(real_executor_started=True)


def test_approved_and_preflight_statuses_depend_on_gate_snapshot() -> None:
    no_human_approval = RealGitWritePilotGateSnapshot(
        gate_checks=[
            _pending_check(gate)
            if gate == RealGitWritePilotGateName.HUMAN_APPROVAL
            else _passed_check(gate)
            for gate in REQUIRED_REAL_GIT_WRITE_PILOT_GATES
        ],
        evaluated_at=NOW,
    )

    with pytest.raises(ValidationError):
        _request(status=RealGitWritePilotStatus.APPROVED, gate_snapshot=no_human_approval)

    assert _request(
        status=RealGitWritePilotStatus.PREFLIGHT_READY,
        gate_snapshot=_preflight_only_snapshot(),
    ).gate_snapshot.pilot_preflight_gates_passed() is True


def test_operation_kinds_default_to_doc_local_commit_candidates_only() -> None:
    request = _request()

    assert request.operation_kinds == [
        RealGitWritePilotOperationKind.CREATE_DOC_FILE,
        RealGitWritePilotOperationKind.CREATE_COMMIT_CANDIDATE,
        RealGitWritePilotOperationKind.LOCAL_BRANCH_CANDIDATE,
    ]
    assert "push" not in {kind.value for kind in request.operation_kinds}
    assert "pr" not in {kind.value for kind in request.operation_kinds}
    assert "merge" not in {kind.value for kind in request.operation_kinds}


def test_approval_stores_token_id_and_safe_hint_not_token_value() -> None:
    approval = RealGitWritePilotApproval(
        approval_id="approval-1",
        pilot_id="pilot-1",
        approved_by="user-1",
        approved_at=NOW,
        one_shot_token_id="token-id-1",
        token_hint="approval hint ending 1234",
        expires_at=LATER,
        approved_scope_summary="single doc-only branch candidate",
        decision=RealGitWritePilotApprovalDecision.APPROVED,
    )

    assert approval.one_shot_token_id == "token-id-1"
    assert approval.token_hint == "approval hint ending 1234"

    with pytest.raises(ValidationError):
        RealGitWritePilotApproval(
            approval_id="approval-2",
            pilot_id="pilot-1",
            approved_by="user-1",
            approved_at=NOW,
            one_shot_token_id="token-id-2",
            token_hint="sk-proj-1234567890abcdef",
            expires_at=LATER,
            approved_scope_summary="single doc-only branch candidate",
            decision=RealGitWritePilotApprovalDecision.APPROVED,
        )


def test_approval_expiry_must_be_later_than_approval_time() -> None:
    with pytest.raises(ValidationError):
        RealGitWritePilotApproval(
            approval_id="approval-1",
            pilot_id="pilot-1",
            approved_by="user-1",
            approved_at=NOW,
            one_shot_token_id="token-id-1",
            token_hint="approval hint ending 1234",
            expires_at=NOW,
            approved_scope_summary="single doc-only branch candidate",
            decision=RealGitWritePilotApprovalDecision.APPROVED,
        )


@pytest.mark.parametrize(
    "bad_action",
    [
        "reset --hard to base commit",
        "force push pilot branch",
        "run automatic rollback script",
    ],
)
def test_rollback_plan_rejects_forbidden_allowed_actions(bad_action: str) -> None:
    with pytest.raises(ValidationError):
        RealGitWritePilotRollbackPlan(
            rollback_plan_id="rollback-1",
            pilot_id="pilot-1",
            base_commit=BASE_COMMIT,
            target_branch="ai/gitwrite-pilot/2026-06-09-doc-only",
            allowed_rollback_actions=[bad_action],
            forbidden_rollback_actions=[
                "reset --hard is forbidden",
                "force push is forbidden",
                "automatic rollback script is forbidden",
            ],
            safe_summary="rollback contract only",
        )


def test_rollback_plan_requires_forbidden_dangerous_actions() -> None:
    plan = RealGitWritePilotRollbackPlan(
        rollback_plan_id="rollback-1",
        pilot_id="pilot-1",
        base_commit=BASE_COMMIT,
        target_branch="ai/gitwrite-pilot/2026-06-09-doc-only",
        pilot_commit_id=None,
        allowed_rollback_actions=[
            "create revert commit for the pilot commit",
            "delete unmerged pilot branch manually",
        ],
        forbidden_rollback_actions=[
            "reset --hard is forbidden",
            "force push is forbidden",
            "automatic rollback script is forbidden",
        ],
        safe_summary="rollback contract only",
    )

    assert plan.pilot_commit_id is None

    with pytest.raises(ValidationError):
        RealGitWritePilotRollbackPlan(
            rollback_plan_id="rollback-2",
            pilot_id="pilot-1",
            base_commit=BASE_COMMIT,
            target_branch="ai/gitwrite-pilot/2026-06-09-doc-only",
            allowed_rollback_actions=["create revert commit for the pilot commit"],
            forbidden_rollback_actions=["force push is forbidden"],
            safe_summary="rollback contract only",
        )


def test_audit_event_rejects_suspected_secret_text_and_requires_append_only() -> None:
    with pytest.raises(ValidationError):
        RealGitWritePilotAuditEvent(
            event_id="event-1",
            pilot_id="pilot-1",
            event_type="pilot.audit",
            safe_summary="contains bearer abcdefghijk",
            timestamp=NOW,
        )

    with pytest.raises(ValidationError):
        RealGitWritePilotAuditEvent(
            event_id="event-1",
            pilot_id="pilot-1",
            event_type="pilot.audit",
            safe_summary="safe pilot audit event",
            timestamp=NOW,
            append_only=False,
        )


def test_domain_file_static_boundaries() -> None:
    domain_file = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "domain"
        / "real_git_write_pilot.py"
    )
    source = domain_file.read_text(encoding="utf-8")

    forbidden_fragments = [
        "import subprocess",
        "from subprocess",
        "os.popen",
        "asyncio.subprocess",
        "app.api",
        "app.services",
        "app.workers",
        "os.environ",
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
        "/Users/kk/project explore/agent-orchestrator",
        "@aoagents/ao-core",
        "workspace-worktree",
        "CleanupStack",
        "Zod",
        "tmux",
    ]

    for fragment in forbidden_fragments:
        assert fragment not in source
