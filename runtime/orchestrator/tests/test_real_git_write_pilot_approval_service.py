from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.services.real_git_write_pilot_approval_service import (
    EXPLICIT_APPROVAL_PHRASES,
    RealGitWritePilotApprovalReadbackRequest,
    RealGitWritePilotApprovalReadbackService,
)
from app.services.real_git_write_pilot_dry_run_plan_service import (
    RealGitWritePilotDryRunPlan,
    RealGitWritePilotDryRunPlanRequest,
    RealGitWritePilotDryRunPlanService,
)
from app.services.real_git_write_pilot_preview_service import (
    RealGitWritePilotPreviewFeatureFlags,
    RealGitWritePilotPreviewGateInputs,
    RealGitWritePilotPreviewRequest,
    RealGitWritePilotPreviewService,
)
from app.services.real_git_write_pilot_readiness_service import (
    RealGitWritePilotReadinessRequest,
    RealGitWritePilotReadinessService,
)


NOW = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)
BASE_COMMIT = "3ce00cd8014361ba1571a836d981ff6509183c86"

FORBIDDEN_READBACK_TEXT = [
    "raw_command",
    "raw args",
    "raw_args",
    "cwd",
    "env",
    "token_value",
    "api_key",
    "secret",
    "raw_diff",
    "subprocess_output",
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


def _requested_at() -> datetime:
    return datetime.now(timezone.utc)


def _expires_at(requested_at: datetime) -> datetime:
    return requested_at + timedelta(minutes=30)


def _safe_feature_flags() -> RealGitWritePilotPreviewFeatureFlags:
    return RealGitWritePilotPreviewFeatureFlags(
        p9_real_executor_launch_enabled=True,
        product_runtime_git_write_enabled=True,
        real_git_write_pilot_enabled=True,
    )


def _safe_gate_inputs(**overrides: object) -> RealGitWritePilotPreviewGateInputs:
    values = {
        "executor_ready": True,
        "workspace_bound": True,
        "target_branch_allowed": True,
        "diff_preview_ready": True,
        "secret_scan_passed": True,
        "human_approved": False,
        "one_shot_token_issued": False,
        "budget_within_limit": True,
        "timeout_configured": True,
        "rollback_plan_ready": True,
        "append_only_audit_ready": True,
        "force_push_requested": False,
        "auto_pr_requested": False,
        "auto_merge_requested": False,
    }
    values.update(overrides)
    return RealGitWritePilotPreviewGateInputs(**values)


def _preview_request(
    *,
    requested_at: datetime,
    expires_at: datetime,
    **overrides: object,
) -> RealGitWritePilotPreviewRequest:
    payload = {
        "pilot_id": "pilot-approval-1",
        "project_id": "project-1",
        "run_id": "run-1",
        "executor_id": "codex",
        "workspace_id": "workspace-1",
        "repository_id": "repo-1",
        "base_commit": BASE_COMMIT,
        "target_branch": "ai/gitwrite-pilot/2026-06-09-doc-only",
        "file_paths": ["docs/product/pilot.md"],
        "requested_by": "user-1",
        "requested_at": requested_at,
        "expires_at": expires_at,
        "feature_flags": _safe_feature_flags(),
        "gate_inputs": _safe_gate_inputs(),
        "diff_summary": "single doc-only markdown file candidate",
        "rollback_summary": "rollback remains a manual contract",
    }
    payload.update(overrides)
    return RealGitWritePilotPreviewRequest(**payload)


def _readiness_request(
    *,
    requested_at: datetime,
    **overrides: object,
) -> RealGitWritePilotReadinessRequest:
    payload = {
        "pilot_id": "pilot-approval-1",
        "executor": {
            "executor_id": "codex",
            "executor_kind": "codex",
            "configured": True,
            "authenticated": True,
            "available": True,
            "model_or_profile": "gpt-5-codex",
            "safe_summary": "executor profile is ready",
            "checked_at": requested_at,
        },
        "workspace": {
            "workspace_id": "workspace-1",
            "repository_id": "repo-1",
            "base_commit": BASE_COMMIT,
            "target_branch": "ai/gitwrite-pilot/2026-06-09-doc-only",
            "file_paths": ["docs/product/pilot.md"],
            "workspace_bound": True,
            "worktree_registered": True,
            "stale_workspace_detected": False,
            "safe_path_confirmed": True,
            "safe_summary": "workspace binding is ready",
            "checked_at": requested_at,
        },
        "requested_by": "user-1",
        "requested_at": requested_at,
    }
    payload.update(overrides)
    return RealGitWritePilotReadinessRequest(**payload)


def _dry_run_plan(
    *,
    readiness_overrides: dict[str, object] | None = None,
) -> RealGitWritePilotDryRunPlan:
    requested_at = _requested_at()
    expires_at = _expires_at(requested_at)
    preview = RealGitWritePilotPreviewService().build_preview(
        _preview_request(requested_at=requested_at, expires_at=expires_at),
    )
    readiness = RealGitWritePilotReadinessService().build_readiness(
        _readiness_request(
            requested_at=requested_at,
            **(readiness_overrides or {}),
        ),
    )
    return RealGitWritePilotDryRunPlanService().build_plan(
        RealGitWritePilotDryRunPlanRequest(
            pilot_id="pilot-approval-1",
            preview=preview,
            readiness=readiness,
            requested_by="user-1",
            requested_at=requested_at,
        ),
    )


def _approval_request(
    *,
    dry_run_plan: RealGitWritePilotDryRunPlan | None = None,
    approval_phrase: str = "我确认此次试点写入",
) -> RealGitWritePilotApprovalReadbackRequest:
    requested_at = _requested_at()
    return RealGitWritePilotApprovalReadbackRequest(
        pilot_id="pilot-approval-1",
        dry_run_plan=dry_run_plan or _dry_run_plan(),
        approved_by="user-1",
        approval_phrase=approval_phrase,
        approved_scope_summary="approval covers the dry-run doc-only pilot scope",
        requested_at=requested_at,
        expires_at=_expires_at(requested_at),
    )


def test_approval_readback_approves_explicit_phrase_when_dry_run_ready() -> None:
    readback = RealGitWritePilotApprovalReadbackService().build_readback(
        _approval_request(),
    )

    assert readback.approval_id == "pilot-approval-readback-pilot-approval-1"
    assert readback.pilot_id == "pilot-approval-1"
    assert readback.decision == "approved"
    assert readback.approved_by == "user-1"
    assert readback.approval_phrase_matched is True
    assert readback.dry_run_ready is True
    assert readback.ready_for_execution is False
    assert readback.one_shot_token_issued is False
    assert readback.product_runtime_git_write_executed is False
    assert readback.real_executor_started is False


def test_english_explicit_approval_phrase_is_accepted() -> None:
    readback = RealGitWritePilotApprovalReadbackService().build_readback(
        _approval_request(approval_phrase="I confirm this pilot write"),
    )

    assert readback.decision == "approved"
    assert readback.approval_phrase_matched is True


@pytest.mark.parametrize("phrase", ["approve", "ok", "yes", "同意", "确认"])
def test_broad_approval_phrases_do_not_match(phrase: str) -> None:
    readback = RealGitWritePilotApprovalReadbackService().build_readback(
        _approval_request(approval_phrase=phrase),
    )

    assert phrase not in EXPLICIT_APPROVAL_PHRASES
    assert readback.decision == "pending"
    assert readback.approval_phrase_matched is False
    assert readback.ready_for_execution is False


def test_dry_run_not_ready_blocks_approval_readback() -> None:
    readiness_payload = _readiness_request(requested_at=NOW).model_dump()
    executor_payload = {
        **readiness_payload["executor"],
        "available": False,
    }
    plan = _dry_run_plan(readiness_overrides={"executor": executor_payload})

    readback = RealGitWritePilotApprovalReadbackService().build_readback(
        _approval_request(dry_run_plan=plan),
    )

    assert plan.dry_run_ready is False
    assert readback.decision == "blocked"
    assert readback.approval_phrase_matched is True
    assert readback.dry_run_ready is False
    assert readback.ready_for_execution is False


def test_expires_at_is_later_than_requested_and_created_at() -> None:
    request = _approval_request()
    readback = RealGitWritePilotApprovalReadbackService().build_readback(request)

    assert readback.expires_at > request.requested_at
    assert readback.expires_at > readback.created_at


def test_approval_readback_payload_excludes_raw_execution_material() -> None:
    readback = RealGitWritePilotApprovalReadbackService().build_readback(
        _approval_request(),
    )
    body = json.dumps(readback.model_dump(mode="json"), sort_keys=True).lower()

    for fragment in FORBIDDEN_READBACK_TEXT:
        assert fragment not in body


def test_approval_service_and_route_static_boundaries() -> None:
    sources = [
        Path("app/services/real_git_write_pilot_approval_service.py").read_text(
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
        "/Users/kk/project explore/agent-orchestrator",
        "@aoagents/ao-core",
        "workspace-worktree",
        "CleanupStack",
        "Zod",
        "tmux",
    ]

    for source in sources:
        for fragment in forbidden_fragments:
            assert fragment not in source
