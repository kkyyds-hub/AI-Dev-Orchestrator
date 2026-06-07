"""Targeted tests for P6-B agent dispatch decision pure domain model."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

import app.domain.agent_dispatch_decision as agent_dispatch_decision_module
from app.domain.agent_dispatch_decision import (
    P6_AGENT_DISPATCH_DECISION_SOURCE,
    P6_AGENT_DISPATCH_DECISION_VERSION,
    P6B_FORBIDDEN_TRUE_SAFETY_FLAGS,
    AgentDispatchDecision,
    AgentDispatchDecisionSafetyFlags,
    DispatchAgent,
    DispatchStatus,
)
from app.domain.failure_recovery_decision import InstructionKind


EXPECTED_FALSE_SAFETY_FLAGS = {
    "runs_git": False,
    "runs_write_git": False,
    "git_add_triggered": False,
    "git_commit_triggered": False,
    "git_push_triggered": False,
    "pr_opened": False,
    "merge_triggered": False,
    "branch_deleted": False,
    "git_reset_triggered": False,
    "git_checkout_triggered": False,
    "git_switch_triggered": False,
    "git_stash_triggered": False,
    "git_rebase_triggered": False,
    "git_tag_triggered": False,
    "ci_triggered": False,
    "execution_enabled": False,
    "worker_dispatch_triggered": False,
    "api_response_exposed": False,
    "agent_message_written": False,
    "task_created": False,
    "retry_triggered": False,
    "auto_dispatch_triggered": False,
}

FORBIDDEN_USER_VISIBLE_GIT_WRITE_COPY = (
    "git add",
    "git commit",
    "git push",
    "PR",
    "merge",
    "删除 branch",
    "reset",
    "checkout",
    "switch",
    "stash",
    "rebase",
    "tag",
)


def _suggested_decision(**overrides) -> AgentDispatchDecision:
    values = {
        "source_failure_recovery_decision_id": "p5-decision-1",
        "source_run_id": uuid4(),
        "source_task_id": uuid4(),
        "recommended_agent": DispatchAgent.CODEX,
        "dispatch_status": DispatchStatus.SUGGESTED,
        "dispatch_reason_code": "p5_owner_codex",
        "dispatch_reason_cn": "建议由 Codex 继续处理代码或测试修复。",
        "instruction_kind": InstructionKind.CODE_FIX,
        "instruction_draft": (
            "建议交给 Codex：请根据失败证据修复实现，并只运行 targeted tests。"
        ),
        "evidence_refs": ["p5:failure_execution_codex_fix_and_retry"],
        "created_by": "p6-b-test",
    }
    values.update(overrides)
    return AgentDispatchDecision(**values)


def _contains_cjk(value: str) -> bool:
    return any(
        "\u4e00" <= char <= "\u9fff"
        or "\u3400" <= char <= "\u4dbf"
        or "\uf900" <= char <= "\ufaff"
        for char in value
    )


def _assert_pure_contract(decision: AgentDispatchDecision) -> None:
    assert decision.source == P6_AGENT_DISPATCH_DECISION_SOURCE
    assert decision.version == P6_AGENT_DISPATCH_DECISION_VERSION
    assert decision.dispatch_decision_id
    assert decision.safety_flags.model_dump() == EXPECTED_FALSE_SAFETY_FLAGS
    assert decision.api_response_exposed is False
    assert decision.created_at.tzinfo is not None
    assert decision.created_at.utcoffset() == timezone.utc.utcoffset(decision.created_at)
    assert _contains_cjk(decision.dispatch_reason_cn)
    assert not any(
        copy in decision.dispatch_reason_cn
        for copy in FORBIDDEN_USER_VISIBLE_GIT_WRITE_COPY
    )
    if decision.instruction_draft is not None:
        assert _contains_cjk(decision.instruction_draft)
        assert not any(
            copy in decision.instruction_draft
            for copy in FORBIDDEN_USER_VISIBLE_GIT_WRITE_COPY
        )

    payload = decision.model_dump(mode="json")
    assert payload["source"] == P6_AGENT_DISPATCH_DECISION_SOURCE
    assert payload["version"] == P6_AGENT_DISPATCH_DECISION_VERSION
    assert payload["dispatch_decision_id"] == decision.dispatch_decision_id
    assert payload["source_run_id"] == str(decision.source_run_id)
    assert payload["source_task_id"] == str(decision.source_task_id)
    assert payload["recommended_agent"] == decision.recommended_agent.value
    assert payload["dispatch_status"] == decision.dispatch_status.value
    assert payload["instruction_kind"] == decision.instruction_kind.value
    assert payload["safety_flags"] == EXPECTED_FALSE_SAFETY_FLAGS


def test_dispatch_agent_enum_values_are_stable():
    assert {agent.value for agent in DispatchAgent} == {
        "codex",
        "deepseek",
        "user",
        "blocked",
    }


def test_dispatch_status_enum_values_are_stable():
    assert {status.value for status in DispatchStatus} == {
        "suggested",
        "needs_user_decision",
        "blocked",
        "not_applicable",
    }


def test_suggested_codex_dispatch_decision_is_pure_and_serializable():
    decision = _suggested_decision()

    _assert_pure_contract(decision)
    assert decision.source_failure_recovery_decision_id == "p5-decision-1"
    assert decision.recommended_agent == DispatchAgent.CODEX
    assert decision.dispatch_status == DispatchStatus.SUGGESTED
    assert decision.dispatch_reason_code == "p5_owner_codex"
    assert decision.instruction_kind == InstructionKind.CODE_FIX
    assert decision.instruction_draft is not None
    assert "Codex" in decision.instruction_draft
    assert decision.evidence_refs == ["p5:failure_execution_codex_fix_and_retry"]
    assert decision.created_by == "p6-b-test"


def test_suggested_deepseek_dispatch_decision_is_allowed():
    decision = _suggested_decision(
        recommended_agent=DispatchAgent.DEEPSEEK,
        dispatch_reason_code="p5_owner_deepseek",
        dispatch_reason_cn="建议由 DeepSeek 修正文档、配置或证据口径。",
        instruction_kind=InstructionKind.EVIDENCE_FIX,
        instruction_draft=(
            "建议交给 DeepSeek：请核对 ledger、证据链和 Gate 结论是否一致。"
        ),
        evidence_refs=["p5:failure_verification_config_deepseek_config_fix"],
    )

    _assert_pure_contract(decision)
    assert decision.recommended_agent == DispatchAgent.DEEPSEEK
    assert "DeepSeek" in decision.instruction_draft


def test_needs_user_decision_requires_user_agent_and_no_executable_draft():
    decision = _suggested_decision(
        recommended_agent=DispatchAgent.USER,
        dispatch_status=DispatchStatus.NEEDS_USER_DECISION,
        dispatch_reason_code="p5_requires_human_decision",
        dispatch_reason_cn="需要用户确认预算、授权或业务取舍后才能继续。",
        instruction_kind=InstructionKind.HUMAN_QUESTION,
        instruction_draft=None,
        evidence_refs=["p5:failure_budget_user_decision"],
    )

    _assert_pure_contract(decision)
    assert decision.recommended_agent == DispatchAgent.USER
    assert decision.dispatch_status == DispatchStatus.NEEDS_USER_DECISION
    assert decision.instruction_draft is None


def test_blocked_dispatch_requires_blocked_agent_and_no_draft():
    decision = _suggested_decision(
        recommended_agent=DispatchAgent.BLOCKED,
        dispatch_status=DispatchStatus.BLOCKED,
        dispatch_reason_code="dispatch_blocked_by_safety_gate",
        dispatch_reason_cn="安全门或证据链缺失，当前不可调度。",
        instruction_kind=InstructionKind.PAUSE,
        instruction_draft=None,
        evidence_refs=["p5:reason_dependency_blocked_pause"],
    )

    _assert_pure_contract(decision)
    assert decision.recommended_agent == DispatchAgent.BLOCKED
    assert decision.dispatch_status == DispatchStatus.BLOCKED


def test_not_applicable_dispatch_requires_blocked_agent_and_no_draft():
    decision = _suggested_decision(
        recommended_agent=DispatchAgent.BLOCKED,
        dispatch_status=DispatchStatus.NOT_APPLICABLE,
        dispatch_reason_code="dispatch_not_applicable_success_path",
        dispatch_reason_cn="当前成功路径不需要生成调度建议。",
        instruction_kind=InstructionKind.PAUSE,
        instruction_draft=None,
        evidence_refs=[],
    )

    _assert_pure_contract(decision)
    assert decision.evidence_refs == []
    assert decision.dispatch_status == DispatchStatus.NOT_APPLICABLE


@pytest.mark.parametrize("flag_name", P6B_FORBIDDEN_TRUE_SAFETY_FLAGS)
def test_safety_flags_reject_runtime_side_effect_flags(flag_name):
    with pytest.raises(ValueError) as exc_info:
        AgentDispatchDecisionSafetyFlags(**{flag_name: True})

    assert flag_name in str(exc_info.value)
    assert "must not execute Git" in str(exc_info.value)


@pytest.mark.parametrize("flag_name", ("api_response_exposed", "agent_message_written"))
def test_p6_b_rejects_future_stage_read_only_flags(flag_name):
    with pytest.raises(ValidationError) as exc_info:
        _suggested_decision(
            safety_flags=AgentDispatchDecisionSafetyFlags(**{flag_name: True}),
            api_response_exposed=(flag_name == "api_response_exposed"),
        )

    assert flag_name in str(exc_info.value)
    assert "must not execute Git" in str(exc_info.value)


def test_api_response_exposed_must_match_safety_flag():
    with pytest.raises(ValidationError) as exc_info:
        _suggested_decision(
            api_response_exposed=True,
        )

    assert "api_response_exposed must match" in str(exc_info.value)


@pytest.mark.parametrize(
    ("recommended_agent", "expected_error"),
    [
        (DispatchAgent.USER, "suggested decisions must recommend codex or deepseek"),
        (DispatchAgent.BLOCKED, "suggested decisions must recommend codex or deepseek"),
    ],
)
def test_suggested_dispatch_rejects_user_or_blocked_agent(
    recommended_agent,
    expected_error,
):
    with pytest.raises(ValidationError) as exc_info:
        _suggested_decision(recommended_agent=recommended_agent)

    assert expected_error in str(exc_info.value)


def test_suggested_dispatch_requires_instruction_draft():
    with pytest.raises(ValidationError) as exc_info:
        _suggested_decision(instruction_draft=None)

    assert "suggested decisions require instruction_draft" in str(exc_info.value)


def test_needs_user_decision_rejects_non_user_agent():
    with pytest.raises(ValidationError) as exc_info:
        _suggested_decision(
            recommended_agent=DispatchAgent.CODEX,
            dispatch_status=DispatchStatus.NEEDS_USER_DECISION,
            instruction_kind=InstructionKind.HUMAN_QUESTION,
            instruction_draft=None,
        )

    assert "needs_user_decision decisions must recommend user" in str(exc_info.value)


def test_needs_user_decision_rejects_executable_draft():
    with pytest.raises(ValidationError) as exc_info:
        _suggested_decision(
            recommended_agent=DispatchAgent.USER,
            dispatch_status=DispatchStatus.NEEDS_USER_DECISION,
            instruction_kind=InstructionKind.HUMAN_QUESTION,
            instruction_draft="建议用户确认后继续。",
        )

    assert "must not include executable drafts" in str(exc_info.value)


def test_blocked_dispatch_rejects_non_blocked_agent():
    with pytest.raises(ValidationError) as exc_info:
        _suggested_decision(
            recommended_agent=DispatchAgent.CODEX,
            dispatch_status=DispatchStatus.BLOCKED,
            instruction_draft=None,
        )

    assert "blocked decisions must recommend blocked" in str(exc_info.value)


def test_not_applicable_dispatch_rejects_draft():
    with pytest.raises(ValidationError) as exc_info:
        _suggested_decision(
            recommended_agent=DispatchAgent.BLOCKED,
            dispatch_status=DispatchStatus.NOT_APPLICABLE,
            instruction_draft="建议无需处理。",
        )

    assert "not_applicable decisions must not include executable drafts" in str(
        exc_info.value
    )


@pytest.mark.parametrize(
    ("field_name", "field_value", "expected_error"),
    [
        ("source", "wrong", "source must be"),
        ("version", "wrong", "version must be"),
        ("dispatch_reason_cn", "plain english", "must contain Chinese text"),
        ("instruction_draft", "plain english", "must contain Chinese text"),
    ],
)
def test_dispatch_decision_rejects_invalid_contract_text(
    field_name,
    field_value,
    expected_error,
):
    with pytest.raises(ValidationError) as exc_info:
        _suggested_decision(**{field_name: field_value})

    assert expected_error in str(exc_info.value)


@pytest.mark.parametrize(
    "field_name",
    [
        "dispatch_decision_id",
        "dispatch_reason_code",
        "dispatch_reason_cn",
        "created_by",
    ],
)
def test_required_text_fields_reject_blank_values_after_trim(field_name):
    with pytest.raises(ValidationError) as exc_info:
        _suggested_decision(**{field_name: "   "})

    assert "required text fields must not be blank" in str(exc_info.value)
    assert field_name in str(exc_info.value)


def test_text_and_evidence_refs_are_normalized_and_deduplicated():
    decision = _suggested_decision(
        source_failure_recovery_decision_id="  p5-decision-1  ",
        dispatch_reason_code="  p5_owner_codex  ",
        dispatch_reason_cn="  建议由 Codex 继续处理代码修复。  ",
        instruction_draft="  建议交给 Codex：请修复失败并运行 targeted tests。  ",
        evidence_refs=[
            " p5:failure_execution_codex_fix_and_retry ",
            "",
            "p5:failure_execution_codex_fix_and_retry",
            " run:failed ",
        ],
        created_by="  p6-b-test  ",
    )

    assert decision.source_failure_recovery_decision_id == "p5-decision-1"
    assert decision.dispatch_reason_code == "p5_owner_codex"
    assert decision.dispatch_reason_cn == "建议由 Codex 继续处理代码修复。"
    assert decision.instruction_draft == (
        "建议交给 Codex：请修复失败并运行 targeted tests。"
    )
    assert decision.evidence_refs == [
        "p5:failure_execution_codex_fix_and_retry",
        "run:failed",
    ]
    assert decision.created_by == "p6-b-test"


def test_created_at_naive_datetime_is_normalized_to_utc():
    naive_created_at = datetime(2026, 6, 7, 12, 30, 0)

    decision = _suggested_decision(created_at=naive_created_at)

    assert decision.created_at == naive_created_at.replace(tzinfo=timezone.utc)


def test_p6_b_module_does_not_define_builder_or_runtime_entrypoints():
    forbidden_symbols = (
        "AgentDispatchDecisionBuilder",
        "build_from_failure_recovery_decision",
        "dispatch_worker",
        "create_task",
        "write_agent_message",
    )

    for symbol in forbidden_symbols:
        assert not hasattr(agent_dispatch_decision_module, symbol)
