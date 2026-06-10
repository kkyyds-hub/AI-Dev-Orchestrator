from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.external_executors.actual_contract import (
    RealExecutorLaunchContext,
    RealExecutorOperationStatus,
    RealExecutorSafetyBoundary,
)
from app.external_executors.actual_preflight import (
    RealExecutorPreflightResult,
    RealExecutorPreflightService,
)
from app.external_executors.actual_preview import (
    RealExecutorLaunchPlanPreview,
    RealExecutorLaunchPlanPreviewBuilder,
    RealExecutorLaunchPlanPreviewInput,
)


PREVIEW_FILE = Path("app/external_executors/actual_preview.py")

FORBIDDEN_RUNTIME_FIELDS = {
    "raw_command",
    "command",
    "args",
    "env",
    "env_vars",
    "api_key",
    "token_value",
    "auth_token",
    "secret",
    "password",
    "native_config_path",
    "cli_path",
    "process_handle",
    "stdout_path",
    "stderr_path",
    "log_path",
}

FORBIDDEN_IMPORT_SNIPPETS = {
    "app.api",
    "app.workers",
    "app.services",
    "app.repositories",
    "import subprocess",
    "from subprocess",
    "import os",
    "from os",
    "import pty",
    "from pty",
    "import shlex",
    "from shlex",
    "import pathlib",
    "from pathlib",
}

FORBIDDEN_EXECUTION_SNIPPETS = {
    "Popen",
    "shell=True",
    "os.popen",
    "asyncio.create_subprocess_exec",
    "asyncio.create_subprocess_shell",
    "tmux",
    "Codex CLI",
    "Claude Code",
    "DeepSeek CLI",
}

FORBIDDEN_ENVIRONMENT_SNIPPETS = {
    "environ",
    "getenv",
    "environment variable",
    "environment variables",
}

FORBIDDEN_DISPLAY_STEP_SNIPPETS = {
    "$ ",
    "&&",
    "||",
    "`",
    "$(",
    "bash ",
    "zsh ",
    "sudo ",
    "curl ",
    "git ",
    "python ",
    "node ",
}


def _source() -> str:
    return PREVIEW_FILE.read_text()


def _module() -> ast.Module:
    return ast.parse(_source())


def _class_field_names(class_name: str) -> set[str]:
    for node in _module().body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            fields: set[str] = set()
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    fields.add(item.target.id)
            return fields
    raise AssertionError(f"{class_name} was not found")


def _passing_boundary() -> RealExecutorSafetyBoundary:
    return RealExecutorSafetyBoundary(
        feature_flag_enabled=True,
        human_confirmation_present=True,
        executor_readiness_available=True,
        workspace_worktree_gate_passed=True,
        budget_cost_gate_passed=True,
        concurrency_gate_passed=True,
        timeout_supported=True,
        cancel_supported=True,
        kill_supported=True,
        audit_events_append_only=True,
        credential_exposure_blocked=True,
        environment_dump_blocked=True,
    )


def _context(boundary: RealExecutorSafetyBoundary) -> RealExecutorLaunchContext:
    return RealExecutorLaunchContext(
        request_id="request-1",
        executor_label="safe executor label",
        command_summary="future launch summary",
        workspace_hint="registered worktree",
        safety_boundary=boundary,
    )


def _preview(
    preflight_result: RealExecutorPreflightResult,
    context: RealExecutorLaunchContext,
) -> RealExecutorLaunchPlanPreview:
    return RealExecutorLaunchPlanPreviewBuilder().build(
        RealExecutorLaunchPlanPreviewInput(
            preview_id="preview-1",
            context=context,
            preflight_result=preflight_result,
        ),
    )


def test_real_executor_launch_preview_file_lives_under_external_executors() -> None:
    assert PREVIEW_FILE.is_file()
    assert PREVIEW_FILE.parts[:2] == ("app", "external_executors")


def test_real_executor_launch_plan_preview_builder_exists() -> None:
    builder = RealExecutorLaunchPlanPreviewBuilder()

    assert hasattr(builder, "build")


def test_preflight_ready_builds_non_executable_accepted_preview() -> None:
    context = _context(_passing_boundary())
    preflight = RealExecutorPreflightService().evaluate_launch(context)
    preview = _preview(preflight, context)

    assert preview.ready is True
    assert preview.status is RealExecutorOperationStatus.ACCEPTED
    assert preview.blocking_reasons == []
    assert preview.executable is False
    assert preview.product_runtime_git_write_allowed is False
    assert preview.redaction_applied is True
    assert preview.display_steps
    assert preview.safe_summary == preflight.safe_summary


def test_preflight_blocked_builds_non_executable_blocked_preview_with_reasons() -> None:
    context = _context(RealExecutorSafetyBoundary())
    preflight = RealExecutorPreflightService().evaluate_launch(context)
    preview = _preview(preflight, context)

    assert preview.ready is False
    assert preview.status is RealExecutorOperationStatus.BLOCKED
    assert preview.blocking_reasons == preflight.blocking_reasons
    assert "feature_flag_disabled" in preview.blocking_reasons
    assert preview.executable is False
    assert preview.product_runtime_git_write_allowed is False
    assert preview.redaction_applied is True


def test_display_steps_are_explanatory_and_not_shell_lines() -> None:
    context = _context(_passing_boundary())
    preflight = RealExecutorPreflightService().evaluate_launch(context)
    preview = _preview(preflight, context)

    for step in preview.display_steps:
        lowered = step.lower()
        for snippet in FORBIDDEN_DISPLAY_STEP_SNIPPETS:
            assert snippet not in lowered


@pytest.mark.parametrize(
    "value",
    [
        "contains api key",
        "contains token",
        "contains secret",
        "contains password",
        "contains bearer value",
        "contains sk-test",
    ],
)
def test_preview_text_rejects_suspected_credential_text(value: str) -> None:
    with pytest.raises(ValidationError):
        RealExecutorLaunchPlanPreview(
            preview_id="preview-1",
            ready=True,
            status=RealExecutorOperationStatus.ACCEPTED,
            executor_label="safe executor",
            safe_summary=value,
            display_steps=["Review safe preview."],
        )

    with pytest.raises(ValidationError):
        RealExecutorLaunchPlanPreview(
            preview_id="preview-1",
            ready=True,
            status=RealExecutorOperationStatus.ACCEPTED,
            executor_label="safe executor",
            display_steps=[value],
        )


@pytest.mark.parametrize(
    "step",
    [
        "$ run future executor",
        "bash launch future executor",
        "git status",
        "python launch.py",
        "first step && second step",
    ],
)
def test_display_steps_reject_shell_execution_traces(step: str) -> None:
    with pytest.raises(ValidationError):
        RealExecutorLaunchPlanPreview(
            preview_id="preview-1",
            ready=True,
            status=RealExecutorOperationStatus.ACCEPTED,
            executor_label="safe executor",
            display_steps=[step],
        )


def test_preview_enforces_non_executable_redacted_and_no_product_runtime_git_write() -> None:
    with pytest.raises(ValidationError):
        RealExecutorLaunchPlanPreview(
            preview_id="preview-1",
            ready=True,
            status=RealExecutorOperationStatus.ACCEPTED,
            executor_label="safe executor",
            display_steps=["Review safe preview."],
            executable=True,
        )

    with pytest.raises(ValidationError):
        RealExecutorLaunchPlanPreview(
            preview_id="preview-1",
            ready=True,
            status=RealExecutorOperationStatus.ACCEPTED,
            executor_label="safe executor",
            display_steps=["Review safe preview."],
            redaction_applied=False,
        )

    with pytest.raises(ValidationError):
        RealExecutorLaunchPlanPreview(
            preview_id="preview-1",
            ready=True,
            status=RealExecutorOperationStatus.ACCEPTED,
            executor_label="safe executor",
            display_steps=["Review safe preview."],
            product_runtime_git_write_allowed=True,
        )


def test_preview_models_forbid_extra_runtime_fields() -> None:
    context = _context(_passing_boundary())
    preflight = RealExecutorPreflightService().evaluate_launch(context)

    with pytest.raises(ValidationError):
        RealExecutorLaunchPlanPreviewInput(
            preview_id="preview-1",
            context=context,
            preflight_result=preflight,
            raw_command="not allowed",
        )

    with pytest.raises(ValidationError):
        RealExecutorLaunchPlanPreview(
            preview_id="preview-1",
            ready=True,
            status=RealExecutorOperationStatus.ACCEPTED,
            executor_label="safe executor",
            display_steps=["Review safe preview."],
            env_vars={"TOKEN": "not allowed"},
        )


def test_preview_field_names_do_not_include_forbidden_runtime_fields() -> None:
    checked_classes = {
        "RealExecutorLaunchPlanPreview",
        "RealExecutorLaunchPlanPreviewInput",
    }

    for class_name in checked_classes:
        assert _class_field_names(class_name).isdisjoint(FORBIDDEN_RUNTIME_FIELDS)


def test_actual_preview_does_not_import_forbidden_layers_or_process_modules() -> None:
    source = _source()

    for snippet in FORBIDDEN_IMPORT_SNIPPETS:
        assert snippet not in source


def test_actual_preview_does_not_contain_execution_traces() -> None:
    source = _source()

    for snippet in FORBIDDEN_EXECUTION_SNIPPETS:
        assert snippet not in source


def test_actual_preview_does_not_read_environment_values() -> None:
    source = _source()

    for snippet in FORBIDDEN_ENVIRONMENT_SNIPPETS:
        assert snippet not in source


def test_actual_preview_does_not_define_real_adapter_implementation() -> None:
    for node in _module().body:
        if isinstance(node, ast.ClassDef):
            assert node.name != "RealExecutorAdapter"


def test_actual_preview_does_not_create_api_frontend_worker_or_migration_entrypoints() -> None:
    assert not Path("app/api/routes/real_executor.py").exists()
    assert not Path("app/api/routes/real_executors.py").exists()
    assert not Path("app/workers/real_executor_worker.py").exists()
    assert not any(Path("migrations").glob("*real_executor*"))
    assert not Path("../../apps/web/real-executors").exists()
