from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.services.real_git_write_pilot_preview_service import (
    RealGitWritePilotPreviewFeatureFlags,
    RealGitWritePilotPreviewGateInputs,
    RealGitWritePilotPreviewRequest,
    RealGitWritePilotPreviewService,
)


NOW = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(minutes=5)
BASE_COMMIT = "60193910875933d8582737a7d8991cd3bf4c38e1"

FORBIDDEN_PLAN_TEXT = [
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


def _request(**overrides: object) -> RealGitWritePilotPreviewRequest:
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


def _plan_text(preview) -> str:
    return " | ".join(
        [
            *preview.command_plan.safe_steps,
            *preview.command_plan.forbidden_operations,
        ],
    )


def test_preview_service_generates_preview_for_doc_only_branch_and_docs_file() -> None:
    preview = RealGitWritePilotPreviewService().build_preview(_request())

    assert preview.pilot_id == "pilot-1"
    assert preview.status == "approval_required"
    assert preview.command_plan.target_branch == "ai/gitwrite-pilot/2026-06-09-doc-only"
    assert preview.command_plan.file_paths == ["docs/product/pilot.md"]
    assert preview.rollback_plan.rollback_plan_id == "pilot-rollback-pilot-1"
    assert preview.gate_snapshot.all_passed is False


def test_preview_never_marks_product_runtime_write_or_real_executor_started() -> None:
    preview = RealGitWritePilotPreviewService().build_preview(_request())

    assert preview.product_runtime_git_write_executed is False
    assert preview.real_executor_started is False


def test_default_feature_flags_do_not_pass_full_gate() -> None:
    preview = RealGitWritePilotPreviewService().build_preview(
        _request(feature_flags=RealGitWritePilotPreviewFeatureFlags()),
    )

    assert preview.status == "blocked"
    assert preview.gate_snapshot.all_passed is False
    assert "feature_flag_disabled" in [
        reason.value for reason in preview.gate_snapshot.blocking_reasons
    ]


def test_approval_token_and_final_confirmation_pending_keep_all_passed_false() -> None:
    preview = RealGitWritePilotPreviewService().build_preview(_request())

    checks = {
        check.gate_name.value: check
        for check in preview.gate_snapshot.gate_checks
    }
    assert checks["human_approval"].status.value == "pending"
    assert checks["one_shot_token"].status.value == "pending"
    assert checks["manual_final_confirmation"].status.value == "pending"
    assert preview.gate_snapshot.all_passed is False


@pytest.mark.parametrize(
    "target_branch",
    [
        "main",
        "master",
        "release",
        "production",
        "staging",
        "gh-pages",
    ],
)
def test_protected_target_branches_fail_validation(target_branch: str) -> None:
    with pytest.raises(ValidationError):
        RealGitWritePilotPreviewService().build_preview(
            _request(target_branch=target_branch),
        )


@pytest.mark.parametrize(
    "file_paths",
    [
        ["runtime/orchestrator/app/domain/real_git_write_pilot.py"],
        ["docs/pilot.txt"],
        ["README.md"],
    ],
)
def test_non_docs_markdown_files_fail_validation(file_paths: list[str]) -> None:
    with pytest.raises(ValidationError):
        RealGitWritePilotPreviewService().build_preview(
            _request(file_paths=file_paths),
        )


def test_command_plan_has_only_semantic_steps_and_required_forbidden_operations() -> None:
    preview = RealGitWritePilotPreviewService().build_preview(_request())
    plan = preview.command_plan.model_dump()

    assert "raw_command" not in plan
    assert "raw_args" not in plan
    assert "cwd" not in plan
    assert "env" not in plan
    assert preview.command_plan.safe_steps == [
        "validate pilot branch",
        "prepare doc-only file candidate",
        "prepare local commit candidate",
        "prepare rollback plan",
    ]
    assert preview.command_plan.forbidden_operations == [
        "main write",
        "force push",
        "auto PR",
        "auto merge",
        "raw shell execution",
    ]
    for fragment in FORBIDDEN_PLAN_TEXT:
        assert fragment not in _plan_text(preview)


def test_preview_service_and_route_static_boundaries() -> None:
    sources = [
        Path("app/services/real_git_write_pilot_preview_service.py").read_text(
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
