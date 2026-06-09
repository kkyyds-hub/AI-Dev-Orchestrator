from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain.real_git_write_pilot import RealGitWritePilotApprovalDecision
from app.domain.real_git_write_pilot_token import (
    RealGitWritePilotTokenPurpose,
    RealGitWritePilotTokenScope,
    RealGitWritePilotTokenStatus,
)
from app.services.real_git_write_pilot_token_readback_service import (
    RealGitWritePilotTokenReadbackRequest,
    RealGitWritePilotTokenReadbackService,
)


NOW = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(minutes=10)

FORBIDDEN_RESPONSE_TEXT = [
    "raw_token",
    "raw_token_value",
    "token_value",
    "api_key",
    "secret",
]


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


def _request(**overrides: object) -> RealGitWritePilotTokenReadbackRequest:
    payload = {
        "token_id": "token-reference-1",
        "scope": _scope(),
        "purpose": RealGitWritePilotTokenPurpose.AUTHORIZE_SINGLE_DOC_ONLY_PILOT,
        "token_hint": "hint ending 1234",
        "issued_reference_at": NOW,
        "expires_at": LATER,
        "requested_by": "user-1",
        "requested_at": NOW,
    }
    payload.update(overrides)
    return RealGitWritePilotTokenReadbackRequest(**payload)


def _readback(**overrides: object):
    return RealGitWritePilotTokenReadbackService().build_readback(
        _request(**overrides),
    )


def test_token_readback_returns_issuable_reference_for_approved_ready_scope() -> None:
    readback = _readback()

    assert readback.token_reference.status == RealGitWritePilotTokenStatus.ISSUABLE
    assert readback.token_reference.block_reasons == []
    assert readback.audit_readback.append_only is True
    assert readback.token_issue_started is False
    assert readback.token_consume_started is False
    assert readback.ready_for_execution is False
    assert readback.product_runtime_git_write_executed is False
    assert readback.real_executor_started is False


@pytest.mark.parametrize(
    "decision",
    [
        RealGitWritePilotApprovalDecision.PENDING,
        RealGitWritePilotApprovalDecision.REJECTED,
        RealGitWritePilotApprovalDecision.EXPIRED,
        RealGitWritePilotApprovalDecision.CANCELLED,
    ],
)
def test_non_approved_approval_blocks_token_reference(
    decision: RealGitWritePilotApprovalDecision,
) -> None:
    readback = _readback(scope=_scope(approval_decision=decision))

    assert readback.token_reference.status == RealGitWritePilotTokenStatus.BLOCKED
    assert readback.ready_for_execution is False


def test_dry_run_not_ready_blocks_token_reference() -> None:
    readback = _readback(scope=_scope(dry_run_ready=False))

    assert readback.token_reference.status == RealGitWritePilotTokenStatus.BLOCKED
    assert readback.ready_for_execution is False


def test_scope_mismatch_blocks_token_reference() -> None:
    readback = _readback(bound_workspace_id="workspace-other")

    assert readback.token_reference.status == RealGitWritePilotTokenStatus.BLOCKED
    assert readback.ready_for_execution is False


def test_token_readback_response_excludes_raw_token_material() -> None:
    body = json.dumps(_readback().model_dump(mode="json"), sort_keys=True).lower()

    for fragment in FORBIDDEN_RESPONSE_TEXT:
        assert fragment not in body


def test_secret_like_token_hint_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _readback(token_hint="sk-proj-1234567890abcdef")


def test_token_readback_service_static_boundaries() -> None:
    sources = [
        Path("app/services/real_git_write_pilot_token_readback_service.py").read_text(
            encoding="utf-8",
        ),
        Path("app/api/routes/real_git_write_pilot.py").read_text(encoding="utf-8"),
    ]
    forbidden_fragments = [
        "import subprocess",
        "from subprocess",
        "os.popen",
        "asyncio.subprocess",
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

    for source in sources:
        for fragment in forbidden_fragments:
            assert fragment not in source
