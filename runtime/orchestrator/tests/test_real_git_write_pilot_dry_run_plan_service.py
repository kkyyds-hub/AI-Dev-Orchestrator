from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.real_git_write_pilot_dry_run_plan_service import (
    DRY_RUN_FORBIDDEN_OPERATIONS,
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
LATER = NOW + timedelta(minutes=5)
BASE_COMMIT = "00c356700f2682ef3495e9eb43bd388fae4fec06"

FORBIDDEN_PLAN_TEXT = [
    "raw command",
    "raw_command",
    "raw args",
    "raw_args",
    "cwd",
    "env",
    "token",
    "raw diff",
    "raw_diff",
    "subprocess output",
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


def _preview_request(**overrides: object) -> RealGitWritePilotPreviewRequest:
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
        "feature_flags": _safe_feature_flags(),
        "gate_inputs": _safe_gate_inputs(),
        "diff_summary": "single doc-only markdown file candidate",
        "rollback_summary": "rollback remains a manual contract",
    }
    payload.update(overrides)
    return RealGitWritePilotPreviewRequest(**payload)


def _readiness_request(**overrides: object) -> RealGitWritePilotReadinessRequest:
    payload = {
        "pilot_id": "pilot-1",
        "executor": {
            "executor_id": "codex",
            "executor_kind": "codex",
            "configured": True,
            "authenticated": True,
            "available": True,
            "model_or_profile": "gpt-5-codex",
            "safe_summary": "executor profile is ready",
            "checked_at": NOW,
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
            "checked_at": NOW,
        },
        "requested_by": "user-1",
        "requested_at": NOW,
    }
    payload.update(overrides)
    return RealGitWritePilotReadinessRequest(**payload)


def _plan_request(
    *,
    preview_overrides: dict[str, object] | None = None,
    readiness_overrides: dict[str, object] | None = None,
) -> RealGitWritePilotDryRunPlanRequest:
    preview = RealGitWritePilotPreviewService().build_preview(
        _preview_request(**(preview_overrides or {})),
    )
    readiness = RealGitWritePilotReadinessService().build_readiness(
        _readiness_request(**(readiness_overrides or {})),
    )
    return RealGitWritePilotDryRunPlanRequest(
        pilot_id="pilot-1",
        preview=preview,
        readiness=readiness,
        requested_by="user-1",
        requested_at=NOW,
    )


def _semantic_text(plan) -> str:
    return " | ".join(
        f"{step.step_id} {step.step_kind} {step.safe_summary}"
        for step in plan.semantic_steps
    ).lower()


def test_dry_run_plan_ready_when_readiness_ready_and_preview_approval_required() -> None:
    plan = RealGitWritePilotDryRunPlanService().build_plan(_plan_request())

    assert plan.pilot_id == "pilot-1"
    assert plan.readiness_ready_for_preview is True
    assert plan.preview_status.value == "approval_required"
    assert plan.dry_run_ready is True
    assert len(plan.semantic_steps) == 11
    assert plan.gate_snapshot_summary.total_gates == 17
    assert plan.rollback_plan_summary == "rollback remains a manual contract"


def test_dry_run_plan_never_marks_execution_or_runtime_writes_started() -> None:
    plan = RealGitWritePilotDryRunPlanService().build_plan(_plan_request())

    assert plan.ready_for_execution is False
    assert plan.product_runtime_git_write_executed is False
    assert plan.real_executor_started is False
    assert all(step.produces_repository_side_effect is False for step in plan.semantic_steps)


def test_readiness_not_ready_keeps_dry_run_not_ready() -> None:
    readiness = _readiness_request().model_dump()
    readiness["executor"] = {
        **readiness["executor"],
        "available": False,
    }

    plan = RealGitWritePilotDryRunPlanService().build_plan(
        _plan_request(readiness_overrides=readiness),
    )

    assert plan.readiness_ready_for_preview is False
    assert plan.dry_run_ready is False
    assert plan.ready_for_execution is False


def test_preview_blocked_keeps_dry_run_not_ready() -> None:
    plan = RealGitWritePilotDryRunPlanService().build_plan(
        _plan_request(
            preview_overrides={
                "feature_flags": RealGitWritePilotPreviewFeatureFlags(),
            },
        ),
    )

    assert plan.preview_status.value == "blocked"
    assert plan.dry_run_ready is False
    assert plan.ready_for_execution is False


def test_pending_approval_and_one_shot_grant_do_not_mark_execution_ready() -> None:
    plan = RealGitWritePilotDryRunPlanService().build_plan(_plan_request())
    steps_requiring_human = [
        step.step_kind
        for step in plan.semantic_steps
        if step.requires_human_confirmation
    ]

    assert steps_requiring_human == [
        "wait_for_manual_approval",
        "wait_for_one_shot_approval_grant",
    ]
    assert plan.ready_for_execution is False


def test_semantic_steps_exclude_raw_execution_material() -> None:
    plan = RealGitWritePilotDryRunPlanService().build_plan(_plan_request())
    semantic_text = _semantic_text(plan)
    body = json.dumps(
        {
            "semantic_steps": [
                step.model_dump(mode="json")
                for step in plan.semantic_steps
            ],
        },
        sort_keys=True,
    ).lower()

    for fragment in FORBIDDEN_PLAN_TEXT:
        assert fragment not in semantic_text
        assert fragment not in body


def test_forbidden_operations_cover_required_write_boundaries() -> None:
    plan = RealGitWritePilotDryRunPlanService().build_plan(_plan_request())

    assert plan.forbidden_operations == list(DRY_RUN_FORBIDDEN_OPERATIONS)
    assert plan.forbidden_operations == [
        "raw shell execution",
        "direct main write",
        "git force push",
        "automatic PR creation",
        "automatic merge",
        "branch delete",
        "reset hard",
        "tag creation",
        "stash operation",
    ]


def test_full_plan_payload_excludes_command_like_text() -> None:
    plan = RealGitWritePilotDryRunPlanService().build_plan(_plan_request())
    body = json.dumps(plan.model_dump(mode="json"), sort_keys=True).lower()

    for fragment in [
        "raw_command",
        "raw_args",
        "cwd",
        "env",
        "token_value",
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
    ]:
        assert fragment not in body


def test_dry_run_plan_service_and_route_static_boundaries() -> None:
    sources = [
        Path("app/services/real_git_write_pilot_dry_run_plan_service.py").read_text(
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
    ]

    for source in sources:
        for fragment in forbidden_fragments:
            assert fragment not in source
