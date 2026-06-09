from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain.real_git_write_pilot import RealGitWritePilotApprovalDecision
from app.domain.real_git_write_pilot_token import (
    RealGitWritePilotOneShotTokenReference,
    RealGitWritePilotTokenAuditReadback,
    RealGitWritePilotTokenBlockReason,
    RealGitWritePilotTokenPurpose,
    RealGitWritePilotTokenScope,
    RealGitWritePilotTokenStatus,
    build_real_git_write_pilot_token_reference,
)


NOW = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(minutes=10)


def _scope(**overrides: object) -> RealGitWritePilotTokenScope:
    payload = {
        "pilot_id": "pilot-token-1",
        "approval_id": "approval-readback-1",
        "executor_id": "codex",
        "workspace_id": "workspace-1",
        "target_branch": "ai/gitwrite-pilot/2026-06-09-doc-only",
        "file_paths": ["docs/product/pilot.md"],
        "dry_run_ready": True,
        "approval_decision": RealGitWritePilotApprovalDecision.APPROVED,
        "approval_phrase_matched": True,
        "approved_scope_summary": "approval covers the doc-only pilot scope",
    }
    payload.update(overrides)
    return RealGitWritePilotTokenScope(**payload)


def _reference(
    *,
    scope: RealGitWritePilotTokenScope | None = None,
    token_hint: str = "hint ending 1234",
    **overrides: object,
) -> RealGitWritePilotOneShotTokenReference:
    payload = {
        "token_id": "token-reference-1",
        "scope": scope or _scope(),
        "purpose": RealGitWritePilotTokenPurpose.AUTHORIZE_SINGLE_DOC_ONLY_PILOT,
        "token_hint": token_hint,
        "issued_reference_at": NOW,
        "expires_at": LATER,
    }
    payload.update(overrides)
    return build_real_git_write_pilot_token_reference(**payload)


def test_approved_ready_and_scope_matched_reference_can_be_issuable() -> None:
    reference = _reference()

    assert reference.status == RealGitWritePilotTokenStatus.ISSUABLE
    assert reference.block_reasons == []
    assert reference.ready_for_execution is False
    assert reference.product_runtime_git_write_executed is False
    assert reference.real_executor_started is False


@pytest.mark.parametrize(
    "decision",
    [
        RealGitWritePilotApprovalDecision.PENDING,
        RealGitWritePilotApprovalDecision.REJECTED,
        RealGitWritePilotApprovalDecision.EXPIRED,
        RealGitWritePilotApprovalDecision.CANCELLED,
    ],
)
def test_non_approved_decision_blocks_reference(
    decision: RealGitWritePilotApprovalDecision,
) -> None:
    reference = _reference(scope=_scope(approval_decision=decision))

    assert reference.status == RealGitWritePilotTokenStatus.BLOCKED
    assert reference.block_reasons == [
        RealGitWritePilotTokenBlockReason.APPROVAL_MISSING,
    ]


def test_unmatched_approval_phrase_blocks_reference() -> None:
    reference = _reference(scope=_scope(approval_phrase_matched=False))

    assert reference.status == RealGitWritePilotTokenStatus.BLOCKED
    assert reference.block_reasons == [
        RealGitWritePilotTokenBlockReason.APPROVAL_MISSING,
    ]


def test_dry_run_not_ready_blocks_reference() -> None:
    reference = _reference(scope=_scope(dry_run_ready=False))

    assert reference.status == RealGitWritePilotTokenStatus.BLOCKED
    assert reference.block_reasons == [
        RealGitWritePilotTokenBlockReason.DRY_RUN_NOT_READY,
    ]


def test_scope_mismatch_blocks_reference() -> None:
    reference = _reference(bound_workspace_id="workspace-other")

    assert reference.status == RealGitWritePilotTokenStatus.BLOCKED
    assert reference.block_reasons == [
        RealGitWritePilotTokenBlockReason.SCOPE_MISMATCH,
    ]


def test_raw_token_value_field_does_not_exist() -> None:
    fields = set(RealGitWritePilotOneShotTokenReference.model_fields)

    assert "raw_token" not in fields
    assert "raw_token_value" not in fields
    assert "token_value" not in fields
    assert "secret" not in fields


@pytest.mark.parametrize(
    "token_hint",
    [
        "sk-proj-1234567890abcdef",
        "token=abc123456789",
        "bearer abcdefghijklmnop",
        "github_pat_1234567890abcdef",
        "abcdefghijklmnopqrstuvwxyz123456",
    ],
)
def test_token_hint_rejects_secret_like_values(token_hint: str) -> None:
    with pytest.raises(ValidationError):
        _reference(token_hint=token_hint)


def test_expires_at_must_be_later_than_issued_reference_at() -> None:
    with pytest.raises(ValidationError):
        _reference(expires_at=NOW)

    with pytest.raises(ValidationError):
        RealGitWritePilotOneShotTokenReference(
            token_id="token-reference-2",
            pilot_id="pilot-token-1",
            approval_id="approval-readback-1",
            purpose=RealGitWritePilotTokenPurpose.AUTHORIZE_SINGLE_DOC_ONLY_PILOT,
            status=RealGitWritePilotTokenStatus.ISSUED_REFERENCE,
            token_hint="hint ending 5678",
            issued_reference_at=NOW,
            expires_at=NOW,
            bound_executor_id="codex",
            bound_workspace_id="workspace-1",
            bound_target_branch="ai/gitwrite-pilot/2026-06-09-doc-only",
            bound_file_paths=["docs/product/pilot.md"],
        )


def test_consumed_reference_does_not_mean_execution_ready() -> None:
    reference = RealGitWritePilotOneShotTokenReference(
        token_id="token-reference-3",
        pilot_id="pilot-token-1",
        approval_id="approval-readback-1",
        purpose=RealGitWritePilotTokenPurpose.AUTHORIZE_SINGLE_DOC_ONLY_PILOT,
        status=RealGitWritePilotTokenStatus.CONSUMED_REFERENCE,
        token_hint="hint ending 3456",
        issued_reference_at=NOW,
        expires_at=LATER,
        consumed_reference_at=NOW + timedelta(minutes=1),
        bound_executor_id="codex",
        bound_workspace_id="workspace-1",
        bound_target_branch="ai/gitwrite-pilot/2026-06-09-doc-only",
        bound_file_paths=["docs/product/pilot.md"],
    )

    assert reference.ready_for_execution is False
    assert reference.product_runtime_git_write_executed is False
    assert reference.real_executor_started is False


def test_revoked_reference_does_not_mean_execution_ready() -> None:
    reference = RealGitWritePilotOneShotTokenReference(
        token_id="token-reference-4",
        pilot_id="pilot-token-1",
        approval_id="approval-readback-1",
        purpose=RealGitWritePilotTokenPurpose.VERIFY_MANUAL_APPROVAL_SCOPE,
        status=RealGitWritePilotTokenStatus.REVOKED,
        token_hint="hint ending 4567",
        issued_reference_at=NOW,
        expires_at=LATER,
        revoked_at=NOW + timedelta(minutes=1),
        bound_executor_id="codex",
        bound_workspace_id="workspace-1",
        bound_target_branch="ai/gitwrite-pilot/2026-06-09-doc-only",
        bound_file_paths=["docs/product/pilot.md"],
    )

    assert reference.ready_for_execution is False
    assert reference.product_runtime_git_write_executed is False
    assert reference.real_executor_started is False


@pytest.mark.parametrize(
    "field_name",
    [
        "ready_for_execution",
        "product_runtime_git_write_executed",
        "real_executor_started",
    ],
)
def test_execution_flags_must_remain_false(field_name: str) -> None:
    payload = _reference().model_dump()
    payload[field_name] = True

    with pytest.raises(ValidationError):
        RealGitWritePilotOneShotTokenReference(**payload)


def test_audit_readback_append_only_is_always_true() -> None:
    readback = RealGitWritePilotTokenAuditReadback(
        event_id="token-audit-1",
        pilot_id="pilot-token-1",
        token_id="token-reference-1",
        event_type="token_reference_readback",
        safe_summary="token reference recorded without issuing a token value",
        append_only=True,
        created_at=NOW,
        metadata_count=2,
    )

    assert readback.append_only is True

    with pytest.raises(ValidationError):
        RealGitWritePilotTokenAuditReadback(
            event_id="token-audit-2",
            pilot_id="pilot-token-1",
            token_id="token-reference-1",
            event_type="token_reference_readback",
            safe_summary="token reference recorded without issuing a token value",
            append_only=False,
            created_at=NOW,
        )


def test_audit_readback_safe_summary_rejects_secret_like_values() -> None:
    with pytest.raises(ValidationError):
        RealGitWritePilotTokenAuditReadback(
            event_id="token-audit-3",
            pilot_id="pilot-token-1",
            token_id="token-reference-1",
            event_type="token_reference_readback",
            safe_summary="secret sk-proj-1234567890abcdef",
            created_at=NOW,
        )


def test_reference_payload_excludes_raw_token_material() -> None:
    body = json.dumps(_reference().model_dump(mode="json"), sort_keys=True).lower()

    for fragment in ["raw_token", "raw token", "token_value", "api_key", "secret"]:
        assert fragment not in body


def test_domain_file_static_boundaries() -> None:
    source = Path("app/domain/real_git_write_pilot_token.py").read_text(encoding="utf-8")

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
    ]

    for fragment in forbidden_fragments:
        assert fragment not in source
