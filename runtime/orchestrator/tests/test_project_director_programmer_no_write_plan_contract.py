"""Contract tests for P16 programmer no-write planning domain model."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.project_director_programmer_no_write_plan import (
    ProjectDirectorProgrammerNoWritePlannedStep,
    ProjectDirectorProgrammerNoWritePlanResult,
)


FORBIDDEN_SENSITIVE_TERMS = {
    "api_key",
    "token",
    "secret",
    "pid",
    "raw command",
    "raw stdout",
    "raw stderr",
    "已执行提交",
    "已推送",
    "PR 已创建",
    "代码已写入",
    "已授权 Git 写",
    "已启动 Codex",
    "已启动 Claude",
}


def _default_result(**overrides) -> ProjectDirectorProgrammerNoWritePlanResult:
    base = dict(
        plan_status="planned",
        session_id=uuid4(),
        source_task_id=uuid4(),
        source_message_id=uuid4(),
    )
    base.update(overrides)
    return ProjectDirectorProgrammerNoWritePlanResult(**base)


# ── 1. Default safety fields ─────────────────────────────────────────


def test_result_default_safety_fields() -> None:
    result = _default_result()

    assert result.programmer_agent is True
    assert result.controlled_programmer_planning is True
    assert result.no_write_plan is True
    assert result.executor_backed_programmer_allowed is True
    assert result.product_runtime_git_write_allowed is False
    assert result.worktree_write_allowed is False
    assert result.file_write_allowed is False
    assert result.real_code_modified is False
    assert result.git_write_performed is False
    assert result.native_executor_started is False
    assert result.codex_started is False
    assert result.claude_code_started is False
    assert result.worker_started is False
    assert result.task_created is False
    assert result.run_created is False
    assert result.ai_project_director_total_loop == "Partial"


# ── 2. Validator rejects true for forbidden flags ─────────────────────


@pytest.mark.parametrize(
    "field_name",
    [
        "product_runtime_git_write_allowed",
        "worktree_write_allowed",
        "file_write_allowed",
        "real_code_modified",
        "git_write_performed",
        "native_executor_started",
        "codex_started",
        "claude_code_started",
        "worker_started",
        "task_created",
        "run_created",
    ],
)
def test_result_validator_rejects_true_forbidden_flags(field_name: str) -> None:
    with pytest.raises(ValidationError, match="must remain false"):
        _default_result(**{field_name: True})


# ── 3. PlannedStep structure completeness ─────────────────────────────


def test_planned_step_has_all_required_fields() -> None:
    step = ProjectDirectorProgrammerNoWritePlannedStep(
        step_id="step-1",
        title="Test step",
        summary="A test step summary.",
        evidence_refs=["ref-1"],
        affected_files_preview=["src/foo.py"],
        required_targeted_tests=["test_foo.py"],
        risk_notes=["low risk"],
    )

    assert step.step_id == "step-1"
    assert step.title == "Test step"
    assert step.summary == "A test step summary."
    assert step.evidence_refs == ["ref-1"]
    assert step.affected_files_preview == ["src/foo.py"]
    assert step.required_targeted_tests == ["test_foo.py"]
    assert step.risk_notes == ["low risk"]


def test_planned_step_fields_have_length_constraints() -> None:
    with pytest.raises(ValidationError):
        ProjectDirectorProgrammerNoWritePlannedStep(
            step_id="", title="t", summary="s"
        )

    with pytest.raises(ValidationError):
        ProjectDirectorProgrammerNoWritePlannedStep(
            step_id="x", title="", summary="s"
        )

    with pytest.raises(ValidationError):
        ProjectDirectorProgrammerNoWritePlannedStep(
            step_id="x", title="t", summary=""
        )


# ── 4. Output does not contain sensitive/misleading terms ─────────────


def test_result_output_excludes_sensitive_terms() -> None:
    result = _default_result()
    serialized = result.model_dump_json().lower()

    for term in FORBIDDEN_SENSITIVE_TERMS:
        assert term.lower() not in serialized, f"Found forbidden term: {term}"


def test_result_with_steps_excludes_sensitive_terms() -> None:
    result = _default_result(
        planned_steps=[
            ProjectDirectorProgrammerNoWritePlannedStep(
                step_id="p16-plan-1",
                title="Inspect readonly reviewer feedback",
                summary="Use the P15 readonly reviewer message as planning evidence.",
            )
        ],
        implementation_summary="Programmer no-write plan prepared.",
        recommended_next_step="Run safety tests.",
    )
    serialized = result.model_dump_json().lower()

    for term in FORBIDDEN_SENSITIVE_TERMS:
        assert term.lower() not in serialized, f"Found forbidden term: {term}"
