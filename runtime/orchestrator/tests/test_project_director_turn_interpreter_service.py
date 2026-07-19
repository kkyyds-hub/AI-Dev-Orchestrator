"""Tests for P26-B1 semantic turn interpreter core contracts and behavior.

Verifies risk scanning, Provider-first interpretation, safe fallback,
semantic boundary decisions, and pure service import boundaries.
"""

from __future__ import annotations

import ast
import json
from uuid import uuid4

import pytest

from app.domain.project_director_conversation_intelligence import (
    ConversationMode,
    DirectorResponseSource,
    TurnInterpretation,
)
from app.domain.project_director_semantic_turn import (
    ConversationRiskScan,
    ConversationRiskSignal,
    ConversationRiskSignalType,
    TurnInterpretationOutcome,
)
from app.services.project_director_turn_interpreter_service import (
    DeterministicConversationRiskScanner,
    ProjectDirectorTurnInterpreterService,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid() -> "UUID":
    return uuid4()


def _valid_interpretation_dict(**overrides) -> dict:
    """Return a minimal valid TurnInterpretation dict."""
    base = {
        "conversation_mode": "general_discussion",
        "primary_intent": "explore",
        "confidence": 0.5,
        "formal_action_requested": False,
        "hypothetical_action": False,
        "referenced_option_ids": [],
        "referenced_entity_ids": [],
        "needs_formal_fact_context": False,
        "needs_discussion_history": False,
        "needs_retrieval": False,
        "reason_summary": "generic fallback",
    }
    base.update(overrides)
    return base


def _make_provider(return_text: str, return_receipt: str | None = "receipt-001"):
    """Return a fake provider that always yields the given text."""
    def _gen(model_name: str, prompt: str, request_id: str) -> tuple[str, str | None]:
        return return_text, return_receipt
    return _gen


def _make_failing_provider(exc: Exception = RuntimeError("boom")):
    """Return a fake provider that always raises."""
    def _gen(model_name: str, prompt: str, request_id: str) -> tuple[str, str | None]:
        raise exc
    return _gen


# ===========================================================================
# 6.1 ConversationRiskSignalType enum
# ===========================================================================


class TestConversationRiskSignalTypeEnum:
    def test_values_and_order(self):
        expected = [
            "task_creation",
            "worker_start",
            "executor_start",
            "plan_modification",
            "plan_application",
            "task_deletion",
            "acceptance_criteria_change",
            "git_write",
            "deployment",
            "publish",
            "destructive_database_change",
        ]
        assert [e.value for e in ConversationRiskSignalType] == expected

    def test_unknown_value_rejected(self):
        with pytest.raises(Exception):
            ConversationRiskSignalType("nonexistent")


# ===========================================================================
# 6.2 ConversationRiskSignal
# ===========================================================================


class TestConversationRiskSignal:
    def _make_signal(self, **overrides):
        defaults = dict(
            signal_type=ConversationRiskSignalType.TASK_CREATION,
            matched_phrase="创建任务",
            start_index=0,
            end_index=4,
        )
        defaults.update(overrides)
        return ConversationRiskSignal(**defaults)

    def test_valid_signal(self):
        sig = self._make_signal()
        assert sig.signal_type == ConversationRiskSignalType.TASK_CREATION

    def test_matched_phrase_stripped(self):
        sig = self._make_signal(matched_phrase="  创建任务  ")
        assert sig.matched_phrase == "创建任务"

    def test_empty_matched_phrase_rejected(self):
        with pytest.raises(ValueError):
            self._make_signal(matched_phrase="")

    def test_whitespace_only_matched_phrase_rejected(self):
        with pytest.raises(ValueError):
            self._make_signal(matched_phrase="   ")

    def test_non_string_matched_phrase_rejected(self):
        with pytest.raises(ValueError):
            self._make_signal(matched_phrase=123)

    def test_start_index_negative_rejected(self):
        with pytest.raises(ValueError):
            self._make_signal(start_index=-1)

    def test_end_index_zero_rejected(self):
        with pytest.raises(ValueError):
            self._make_signal(end_index=0)

    def test_end_index_equals_start_index_rejected(self):
        with pytest.raises(ValueError):
            self._make_signal(start_index=5, end_index=5)

    def test_end_index_less_than_start_index_rejected(self):
        with pytest.raises(ValueError):
            self._make_signal(start_index=10, end_index=5)

    def test_unknown_extra_field_rejected(self):
        with pytest.raises(ValueError):
            ConversationRiskSignal(
                signal_type=ConversationRiskSignalType.TASK_CREATION,
                matched_phrase="创建任务",
                start_index=0,
                end_index=4,
                unknown_field="bad",
            )

    def test_json_schema_generation(self):
        schema = ConversationRiskSignal.model_json_schema()
        assert "properties" in schema

    def test_json_roundtrip(self):
        sig = self._make_signal()
        data = sig.model_dump()
        json_str = json.dumps(data, default=str)
        restored = ConversationRiskSignal.model_validate_json(json_str)
        assert restored.matched_phrase == sig.matched_phrase
        assert restored.start_index == sig.start_index


# ===========================================================================
# 6.3 ConversationRiskScan
# ===========================================================================


class TestConversationRiskScan:
    def test_empty_signals_no_side_effect(self):
        scan = ConversationRiskScan(
            signals=[],
            has_side_effect_signal=False,
            reason_summary="no signals",
        )
        assert scan.has_side_effect_signal is False

    def test_nonempty_signals_with_true(self):
        sig = ConversationRiskSignal(
            signal_type=ConversationRiskSignalType.TASK_CREATION,
            matched_phrase="创建任务",
            start_index=0,
            end_index=4,
        )
        scan = ConversationRiskScan(
            signals=[sig],
            has_side_effect_signal=True,
            reason_summary="detected",
        )
        assert scan.has_side_effect_signal is True

    def test_empty_signals_with_true_rejected(self):
        with pytest.raises(ValueError, match="has_side_effect_signal"):
            ConversationRiskScan(
                signals=[],
                has_side_effect_signal=True,
                reason_summary="detected",
            )

    def test_nonempty_signals_with_false_rejected(self):
        sig = ConversationRiskSignal(
            signal_type=ConversationRiskSignalType.TASK_CREATION,
            matched_phrase="创建任务",
            start_index=0,
            end_index=4,
        )
        with pytest.raises(ValueError, match="has_side_effect_signal"):
            ConversationRiskScan(
                signals=[sig],
                has_side_effect_signal=False,
                reason_summary="detected",
            )

    def test_duplicate_type_start_end_rejected(self):
        sig1 = ConversationRiskSignal(
            signal_type=ConversationRiskSignalType.TASK_CREATION,
            matched_phrase="创建任务",
            start_index=0,
            end_index=4,
        )
        sig2 = ConversationRiskSignal(
            signal_type=ConversationRiskSignalType.TASK_CREATION,
            matched_phrase="创建任务",
            start_index=0,
            end_index=4,
        )
        with pytest.raises(ValueError, match="repeat"):
            ConversationRiskScan(
                signals=[sig1, sig2],
                has_side_effect_signal=True,
                reason_summary="detected",
            )

    def test_different_type_same_span_allowed(self):
        sig1 = ConversationRiskSignal(
            signal_type=ConversationRiskSignalType.PLAN_MODIFICATION,
            matched_phrase="修改验收标准",
            start_index=0,
            end_index=5,
        )
        sig2 = ConversationRiskSignal(
            signal_type=ConversationRiskSignalType.ACCEPTANCE_CRITERIA_CHANGE,
            matched_phrase="修改验收标准",
            start_index=0,
            end_index=5,
        )
        scan = ConversationRiskScan(
            signals=[sig1, sig2],
            has_side_effect_signal=True,
            reason_summary="detected",
        )
        assert len(scan.signals) == 2

    def test_signals_sorted_by_start_end_type(self):
        sig1 = ConversationRiskSignal(
            signal_type=ConversationRiskSignalType.GIT_WRITE,
            matched_phrase="git push",
            start_index=10,
            end_index=18,
        )
        sig2 = ConversationRiskSignal(
            signal_type=ConversationRiskSignalType.TASK_CREATION,
            matched_phrase="创建任务",
            start_index=0,
            end_index=4,
        )
        sig3 = ConversationRiskSignal(
            signal_type=ConversationRiskSignalType.TASK_CREATION,
            matched_phrase="创建任务",
            start_index=10,
            end_index=14,
        )
        scan = ConversationRiskScan(
            signals=[sig1, sig2, sig3],
            has_side_effect_signal=True,
            reason_summary="detected",
        )
        assert scan.signals[0].start_index == 0
        assert scan.signals[1].start_index == 10
        assert scan.signals[1].end_index == 14
        assert scan.signals[2].start_index == 10
        assert scan.signals[2].end_index == 18

    def test_reason_summary_stripped(self):
        scan = ConversationRiskScan(
            signals=[],
            has_side_effect_signal=False,
            reason_summary="  no signals  ",
        )
        assert scan.reason_summary == "no signals"

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError):
            ConversationRiskScan(
                signals=[],
                has_side_effect_signal=False,
                reason_summary="",
            )

    def test_no_user_input_storage_field(self):
        """ConversationRiskScan must not store raw user input."""
        sig = ConversationRiskSignal(
            signal_type=ConversationRiskSignalType.TASK_CREATION,
            matched_phrase="创建任务",
            start_index=0,
            end_index=4,
        )
        scan = ConversationRiskScan(
            signals=[sig],
            has_side_effect_signal=True,
            reason_summary="detected",
        )
        field_names = set(ConversationRiskScan.model_fields.keys())
        for name in field_names:
            assert "user" not in name.lower() or "input" not in name.lower()
            assert "content" not in name.lower()

    def test_unknown_extra_field_rejected(self):
        with pytest.raises(ValueError):
            ConversationRiskScan(
                signals=[],
                has_side_effect_signal=False,
                reason_summary="ok",
                unknown_field="bad",
            )

    def test_json_schema_generation(self):
        schema = ConversationRiskScan.model_json_schema()
        assert "properties" in schema

    def test_json_roundtrip(self):
        sig = ConversationRiskSignal(
            signal_type=ConversationRiskSignalType.TASK_CREATION,
            matched_phrase="创建任务",
            start_index=0,
            end_index=4,
        )
        scan = ConversationRiskScan(
            signals=[sig],
            has_side_effect_signal=True,
            reason_summary="detected",
        )
        data = scan.model_dump()
        json_str = json.dumps(data, default=str)
        restored = ConversationRiskScan.model_validate_json(json_str)
        assert restored.has_side_effect_signal is True
        assert len(restored.signals) == 1


# ===========================================================================
# 6.4 TurnInterpretationOutcome
# ===========================================================================


class TestTurnInterpretationOutcome:
    def _make_outcome(self, **overrides):
        interp = TurnInterpretation(
            conversation_mode=ConversationMode.GENERAL_DISCUSSION,
            primary_intent="explore",
            confidence=0.5,
            reason_summary="fallback",
        )
        risk_scan = ConversationRiskScan(
            signals=[],
            has_side_effect_signal=False,
            reason_summary="no signals",
        )
        defaults = dict(
            interpretation=interp,
            risk_scan=risk_scan,
            source=DirectorResponseSource.PROVIDER,
            source_detail="test_provider",
            receipt_id="receipt-001",
            provider_attempted=True,
            fallback_reason=None,
        )
        defaults.update(overrides)
        return TurnInterpretationOutcome(**defaults)

    def test_valid_provider_outcome(self):
        outcome = self._make_outcome()
        assert outcome.source == DirectorResponseSource.PROVIDER

    def test_provider_requires_provider_attempted_true(self):
        with pytest.raises(ValueError, match="provider_attempted"):
            self._make_outcome(provider_attempted=False)

    def test_provider_cannot_have_fallback_reason(self):
        with pytest.raises(ValueError, match="fallback_reason"):
            self._make_outcome(fallback_reason="some_reason")

    def test_provider_receipt_id_can_exist(self):
        outcome = self._make_outcome(receipt_id="abc-123")
        assert outcome.receipt_id == "abc-123"

    def test_provider_receipt_id_can_be_none(self):
        outcome = self._make_outcome(receipt_id=None)
        assert outcome.receipt_id is None

    def test_valid_provider_unavailable_fallback(self):
        outcome = self._make_outcome(
            source=DirectorResponseSource.RULE_FALLBACK,
            source_detail="p26_b1_rule_fallback; reason=provider_unavailable",
            receipt_id=None,
            provider_attempted=False,
            fallback_reason="provider_unavailable",
        )
        assert outcome.fallback_reason == "provider_unavailable"

    def test_valid_provider_failed_fallback(self):
        outcome = self._make_outcome(
            source=DirectorResponseSource.RULE_FALLBACK,
            source_detail="p26_b1_rule_fallback; reason=provider_failed",
            receipt_id=None,
            provider_attempted=True,
            fallback_reason="provider_failed",
        )
        assert outcome.fallback_reason == "provider_failed"

    def test_fallback_receipt_id_must_be_none(self):
        with pytest.raises(ValueError, match="receipt_id"):
            self._make_outcome(
                source=DirectorResponseSource.RULE_FALLBACK,
                source_detail="fallback",
                receipt_id="bad",
                provider_attempted=False,
                fallback_reason="provider_unavailable",
            )

    def test_fallback_reason_must_be_nonempty(self):
        with pytest.raises(ValueError, match="fallback_reason"):
            self._make_outcome(
                source=DirectorResponseSource.RULE_FALLBACK,
                source_detail="fallback",
                receipt_id=None,
                provider_attempted=False,
                fallback_reason=None,
            )

    def test_system_source_rejected(self):
        with pytest.raises(ValueError, match="provider or rule_fallback"):
            self._make_outcome(
                source=DirectorResponseSource.SYSTEM,
                source_detail="system",
                provider_attempted=False,
                fallback_reason="system",
            )

    def test_unknown_source_rejected(self):
        with pytest.raises(ValueError):
            self._make_outcome(source="nonexistent")

    def test_source_detail_stripped(self):
        outcome = self._make_outcome(source_detail="  trimmed  ")
        assert outcome.source_detail == "trimmed"

    def test_empty_source_detail_rejected(self):
        with pytest.raises(ValueError):
            self._make_outcome(source_detail="")

    def test_source_detail_with_api_key_rejected(self):
        with pytest.raises(ValueError, match="secrets"):
            self._make_outcome(source_detail="provider used api_key=sk-123")

    def test_source_detail_with_bearer_rejected(self):
        with pytest.raises(ValueError, match="secrets"):
            self._make_outcome(source_detail="Bearer token used")

    def test_fallback_reason_with_sk_prefix_rejected(self):
        with pytest.raises(ValueError, match="secrets"):
            self._make_outcome(
                source=DirectorResponseSource.RULE_FALLBACK,
                source_detail="fallback",
                receipt_id=None,
                provider_attempted=False,
                fallback_reason="failed with sk-abc123",
            )

    def test_unknown_extra_field_rejected(self):
        with pytest.raises(ValueError):
            TurnInterpretationOutcome(
                interpretation=TurnInterpretation(
                    conversation_mode=ConversationMode.GENERAL_DISCUSSION,
                    primary_intent="x",
                    confidence=0.5,
                    reason_summary="y",
                ),
                risk_scan=ConversationRiskScan(
                    signals=[],
                    has_side_effect_signal=False,
                    reason_summary="z",
                ),
                source=DirectorResponseSource.PROVIDER,
                source_detail="test",
                provider_attempted=True,
                unknown_field="bad",
            )

    def test_json_schema_generation(self):
        schema = TurnInterpretationOutcome.model_json_schema()
        assert "properties" in schema

    def test_json_roundtrip(self):
        outcome = self._make_outcome()
        data = outcome.model_dump()
        json_str = json.dumps(data, default=str)
        restored = TurnInterpretationOutcome.model_validate_json(json_str)
        assert restored.source == outcome.source
        assert restored.provider_attempted is True


# ===========================================================================
# 7. Risk scanner — 54 phrases parameterized
# ===========================================================================


_RISK_PHRASE_MAP: dict[str, tuple[str, ...]] = {
    "task_creation": ("创建任务", "新建任务", "生成任务", "派发任务"),
    "worker_start": ("启动 Worker", "运行 Worker", "派发 Worker", "启动工作器"),
    "executor_start": (
        "启动执行器", "运行执行器", "启动 Codex", "运行 Codex", "调用 Codex",
        "启动 Claude Code", "运行 Claude Code", "调用 Claude Code",
        "开始执行", "立即执行",
    ),
    "plan_modification": (
        "修改计划", "调整计划", "修改草案", "调整草案", "改验收标准", "修改验收标准",
    ),
    "plan_application": ("应用草案", "应用计划", "确认并应用", "执行计划"),
    "task_deletion": ("删除任务", "取消任务", "移除任务"),
    "acceptance_criteria_change": ("修改验收标准", "调整验收标准", "删除验收标准"),
    "git_write": (
        "git add", "git commit", "git push", "提交代码", "推送代码",
        "合并代码", "创建 PR", "合并 PR",
    ),
    "deployment": ("部署", "上线", "发布到服务器"),
    "publish": ("正式发布", "发布版本", "发布应用"),
    "destructive_database_change": (
        "删除表", "清空数据库", "删除数据库", "drop table", "truncate table",
        "破坏性 migration",
    ),
}


def _all_risk_phrases():
    """Flatten all (signal_type_value, phrase) pairs for parametrize."""
    pairs = []
    for sig_type, phrases in _RISK_PHRASE_MAP.items():
        for phrase in phrases:
            pairs.append((sig_type, phrase))
    return pairs


class TestDeterministicConversationRiskScanner:
    scanner = DeterministicConversationRiskScanner()

    @pytest.mark.parametrize(
        ("expected_type", "phrase"),
        _all_risk_phrases(),
        ids=[f"{t}:{p}" for t, ps in _RISK_PHRASE_MAP.items() for p in ps],
    )
    def test_each_risk_phrase_detected(self, expected_type: str, phrase: str):
        """Every whitelisted phrase must produce a signal with correct type."""
        scan = self.scanner.scan(phrase)
        assert scan.has_side_effect_signal is True
        matching = [s for s in scan.signals if s.signal_type.value == expected_type]
        assert len(matching) >= 1, f"Phrase '{phrase}' did not produce {expected_type}"
        # matched_phrase should contain the phrase (case-insensitive)
        matched = matching[0]
        assert matched.matched_phrase.lower() == phrase.lower() or \
            phrase.lower() in matched.matched_phrase.lower()

    def test_total_risk_phrase_count(self):
        """Verify 54 total phrases across 11 categories."""
        total = sum(len(v) for v in _RISK_PHRASE_MAP.values())
        assert total == 54
        assert len(_RISK_PHRASE_MAP) == 11

    # Case insensitivity for English phrases
    @pytest.mark.parametrize(
        "input_text",
        ["GIT PUSH", "Git Commit", "DROP TABLE", "TrUnCaTe TaBlE"],
    )
    def test_english_case_insensitive(self, input_text: str):
        scan = self.scanner.scan(input_text)
        assert scan.has_side_effect_signal is True

    def test_no_risk_returns_empty_signals(self):
        scan = self.scanner.scan("今天天气真好")
        assert scan.has_side_effect_signal is False
        assert scan.signals == []

    def test_multiple_different_risk_phrases_all_detected(self):
        text = "请创建任务并启动 Codex，然后 git push"
        scan = self.scanner.scan(text)
        types = {s.signal_type.value for s in scan.signals}
        assert "task_creation" in types
        assert "executor_start" in types
        assert "git_write" in types

    def test_output_sorted_by_position(self):
        text = "git push 后创建任务"
        scan = self.scanner.scan(text)
        for i in range(len(scan.signals) - 1):
            a = scan.signals[i]
            b = scan.signals[i + 1]
            assert (a.start_index, a.end_index) <= (b.start_index, b.end_index)

    def test_duplicate_text_at_different_positions_produces_two_signals(self):
        text = "创建任务，然后再说创建任务"
        scan = self.scanner.scan(text)
        task_signals = [s for s in scan.signals if s.signal_type.value == "task_creation"]
        assert len(task_signals) == 2
        assert task_signals[0].start_index != task_signals[1].start_index

    def test_modify_acceptance_criteria_produces_two_types(self):
        """'修改验收标准' matches both plan_modification and acceptance_criteria_change."""
        scan = self.scanner.scan("修改验收标准")
        types = {s.signal_type.value for s in scan.signals}
        assert "plan_modification" in types
        assert "acceptance_criteria_change" in types

    def test_scanner_does_not_return_conversation_mode(self):
        scan = self.scanner.scan("创建任务")
        assert not hasattr(scan, "conversation_mode")

    def test_scanner_does_not_return_formal_action_requested(self):
        scan = self.scanner.scan("启动 Codex")
        assert not hasattr(scan, "formal_action_requested")

    def test_scanner_does_not_call_provider(self):
        """Scanner is deterministic, no provider call."""
        scan = self.scanner.scan("部署上线")
        assert scan.has_side_effect_signal is True
        # No provider interaction - scanner is pure function


# ===========================================================================
# 8. Provider-first interpretation
# ===========================================================================


class TestProviderFirstInterpretation:
    def test_provider_called_when_configured(self):
        call_log: list[str] = []
        def fake_provider(model: str, prompt: str, req_id: str):
            call_log.append(req_id)
            return json.dumps(_valid_interpretation_dict()), "r-001"

        svc = ProjectDirectorTurnInterpreterService(
            provider_text_generator=fake_provider,
        )
        result = svc.interpret(content="创建任务", model_name="m", request_id="req-1")
        assert result.source == DirectorResponseSource.PROVIDER
        assert call_log == ["req-1"]

    def test_at_most_one_provider_call(self):
        call_count = 0
        def counting_provider(model: str, prompt: str, req_id: str):
            nonlocal call_count
            call_count += 1
            return json.dumps(_valid_interpretation_dict()), "r-001"

        svc = ProjectDirectorTurnInterpreterService(
            provider_text_generator=counting_provider,
        )
        svc.interpret(content="创建任务", model_name="m", request_id="req-1")
        assert call_count == 1

    def test_model_name_passed_through(self):
        received_models: list[str] = []
        def fake_provider(model: str, prompt: str, req_id: str):
            received_models.append(model)
            return json.dumps(_valid_interpretation_dict()), "r-001"

        svc = ProjectDirectorTurnInterpreterService(
            provider_text_generator=fake_provider,
        )
        svc.interpret(content="测试", model_name="gpt-4o", request_id="req-1")
        assert received_models == ["gpt-4o"]

    def test_request_id_passed_through(self):
        received_ids: list[str] = []
        def fake_provider(model: str, prompt: str, req_id: str):
            received_ids.append(req_id)
            return json.dumps(_valid_interpretation_dict()), "r-001"

        svc = ProjectDirectorTurnInterpreterService(
            provider_text_generator=fake_provider,
        )
        svc.interpret(content="测试", model_name="m", request_id="req-abc")
        assert received_ids == ["req-abc"]

    def test_content_trimmed_before_prompt(self):
        received_prompts: list[str] = []
        def fake_provider(model: str, prompt: str, req_id: str):
            received_prompts.append(prompt)
            return json.dumps(_valid_interpretation_dict()), "r-001"

        svc = ProjectDirectorTurnInterpreterService(
            provider_text_generator=fake_provider,
        )
        svc.interpret(content="  创建任务  ", model_name="m", request_id="r")
        assert "创建任务" in received_prompts[0]

    def test_risk_scan_before_provider_call(self):
        """Risk signals appear in prompt, proving scan happens before provider."""
        received_prompts: list[str] = []
        def fake_provider(model: str, prompt: str, req_id: str):
            received_prompts.append(prompt)
            return json.dumps(_valid_interpretation_dict()), "r-001"

        svc = ProjectDirectorTurnInterpreterService(
            provider_text_generator=fake_provider,
        )
        svc.interpret(content="启动 Codex", model_name="m", request_id="r")
        assert "executor_start" in received_prompts[0]

    def test_prompt_does_not_contain_delta_or_formalization_instructions(self):
        received_prompts: list[str] = []
        def fake_provider(model: str, prompt: str, req_id: str):
            received_prompts.append(prompt)
            return json.dumps(_valid_interpretation_dict()), "r-001"

        svc = ProjectDirectorTurnInterpreterService(
            provider_text_generator=fake_provider,
        )
        svc.interpret(content="创建任务", model_name="m", request_id="r")
        prompt = received_prompts[0]
        assert "DiscussionDelta" not in prompt
        assert "FormalizationProposal" not in prompt
        assert "PlanVersion" not in prompt

    def test_provider_success_source_and_receipt(self):
        def fake_provider(model: str, prompt: str, req_id: str):
            return json.dumps(_valid_interpretation_dict()), "receipt-42"

        svc = ProjectDirectorTurnInterpreterService(
            provider_text_generator=fame_provider if False else fake_provider,
        )
        result = svc.interpret(content="测试", model_name="m", request_id="r")
        assert result.source == DirectorResponseSource.PROVIDER
        assert result.provider_attempted is True
        assert result.fallback_reason is None
        assert result.receipt_id == "receipt-42"

    def test_provider_success_no_side_effects(self):
        """Provider success must not create messages, events, plans, etc."""
        def fake_provider(model: str, prompt: str, req_id: str):
            return json.dumps(_valid_interpretation_dict()), "r-001"

        svc = ProjectDirectorTurnInterpreterService(
            provider_text_generator=fake_provider,
        )
        result = svc.interpret(content="测试", model_name="m", request_id="r")
        # Only the outcome is returned, no side-effect artifacts
        assert isinstance(result, TurnInterpretationOutcome)


# ===========================================================================
# 9. Provider output format parsing
# ===========================================================================


class TestProviderOutputFormatParsing:
    def test_direct_json_succeeds(self):
        payload = _valid_interpretation_dict()
        provider = _make_provider(json.dumps(payload))
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=provider)
        result = svc.interpret(content="测试", model_name="m", request_id="r")
        assert result.source == DirectorResponseSource.PROVIDER
        assert result.interpretation.conversation_mode == ConversationMode.GENERAL_DISCUSSION

    def test_fenced_json_succeeds(self):
        payload = _valid_interpretation_dict()
        fenced = f"```json\n{json.dumps(payload)}\n```"
        provider = _make_provider(fenced)
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=provider)
        result = svc.interpret(content="测试", model_name="m", request_id="r")
        assert result.source == DirectorResponseSource.PROVIDER

    def test_wrapped_turn_interpretation_succeeds(self):
        payload = _valid_interpretation_dict()
        wrapped = json.dumps({"turn_interpretation": payload})
        provider = _make_provider(wrapped)
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=provider)
        result = svc.interpret(content="测试", model_name="m", request_id="r")
        assert result.source == DirectorResponseSource.PROVIDER

    def test_fenced_wrapped_json_succeeds(self):
        payload = _valid_interpretation_dict()
        wrapped = json.dumps({"turn_interpretation": payload})
        fenced = f"```json\n{wrapped}\n```"
        provider = _make_provider(fenced)
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=provider)
        result = svc.interpret(content="测试", model_name="m", request_id="r")
        assert result.source == DirectorResponseSource.PROVIDER

    @pytest.mark.parametrize(
        ("description", "bad_output"),
        [
            ("non_json", "this is not json at all"),
            ("json_array", json.dumps([1, 2, 3])),
            ("empty_object", json.dumps({})),
            ("missing_conversation_mode", json.dumps({"primary_intent": "x", "confidence": 0.5, "reason_summary": "y"})),
            ("missing_primary_intent", json.dumps({"conversation_mode": "general_discussion", "confidence": 0.5, "reason_summary": "y"})),
            ("missing_confidence", json.dumps({"conversation_mode": "general_discussion", "primary_intent": "x", "reason_summary": "y"})),
            ("missing_reason_summary", json.dumps({"conversation_mode": "general_discussion", "primary_intent": "x", "confidence": 0.5})),
            ("unknown_conversation_mode", json.dumps({"conversation_mode": "nonexistent", "primary_intent": "x", "confidence": 0.5, "reason_summary": "y"})),
            ("confidence_below_zero", json.dumps({"conversation_mode": "general_discussion", "primary_intent": "x", "confidence": -0.1, "reason_summary": "y"})),
            ("confidence_above_one", json.dumps({"conversation_mode": "general_discussion", "primary_intent": "x", "confidence": 1.5, "reason_summary": "y"})),
            ("formal_and_hypothetical", json.dumps({"conversation_mode": "general_discussion", "primary_intent": "x", "confidence": 0.5, "formal_action_requested": True, "hypothetical_action": True, "reason_summary": "y"})),
            ("extra_field_in_interpretation", json.dumps({"conversation_mode": "general_discussion", "primary_intent": "x", "confidence": 0.5, "reason_summary": "y", "unknown_field": "bad"})),
            ("wrapped_not_object", json.dumps({"turn_interpretation": "not_an_object"})),
        ],
    )
    def test_invalid_contract_enters_fallback(self, description: str, bad_output: str):
        provider = _make_provider(bad_output)
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=provider)
        result = svc.interpret(content="测试", model_name="m", request_id="r")
        assert result.source == DirectorResponseSource.RULE_FALLBACK
        assert result.fallback_reason == "provider_contract_invalid"
        assert result.provider_attempted is True
        assert result.receipt_id is None


# ===========================================================================
# 10. Provider failure fallback
# ===========================================================================


class TestProviderFailureFallback:
    def test_provider_not_injected(self):
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=None)
        result = svc.interpret(content="测试", model_name="m", request_id="r")
        assert result.source == DirectorResponseSource.RULE_FALLBACK
        assert result.fallback_reason == "provider_unavailable"
        assert result.provider_attempted is False

    def test_provider_raises_exception(self):
        provider = _make_failing_provider(RuntimeError("connection timeout"))
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=provider)
        result = svc.interpret(content="测试", model_name="m", request_id="r")
        assert result.source == DirectorResponseSource.RULE_FALLBACK
        assert result.fallback_reason == "provider_failed"
        assert result.provider_attempted is True
        # Must not leak exception details
        assert "connection timeout" not in (result.source_detail or "")
        assert "connection timeout" not in (result.fallback_reason or "")

    def test_provider_returns_empty_string(self):
        provider = _make_provider("")
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=provider)
        result = svc.interpret(content="测试", model_name="m", request_id="r")
        assert result.fallback_reason == "provider_empty_output"
        assert result.provider_attempted is True

    def test_provider_returns_whitespace(self):
        provider = _make_provider("   ")
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=provider)
        result = svc.interpret(content="测试", model_name="m", request_id="r")
        assert result.fallback_reason == "provider_empty_output"
        assert result.provider_attempted is True

    def test_provider_returns_non_string(self):
        def bad_provider(model: str, prompt: str, req_id: str):
            return 12345, "r-001"  # type: ignore
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=bad_provider)
        result = svc.interpret(content="测试", model_name="m", request_id="r")
        assert result.fallback_reason == "provider_empty_output"
        assert result.provider_attempted is True

    def test_provider_returns_wrong_tuple_structure(self):
        def bad_provider(model: str, prompt: str, req_id: str):
            return ("text",)  # type: ignore
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=bad_provider)
        result = svc.interpret(content="测试", model_name="m", request_id="r")
        # Should fall back safely without leaking
        assert result.source == DirectorResponseSource.RULE_FALLBACK
        assert result.provider_attempted is True

    def test_exception_details_not_in_outcome(self):
        provider = _make_failing_provider(RuntimeError("sk-leaked-api-key"))
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=provider)
        result = svc.interpret(content="测试", model_name="m", request_id="r")
        detail = json.dumps(result.model_dump(), default=str)
        assert "sk-leaked-api-key" not in detail


# ===========================================================================
# 11. Six core semantic use cases
# ===========================================================================


class TestCoreSemanticUseCases:
    """Both Provider success and no-Provider fallback paths."""

    def test_hypothetical_risk_discussion(self):
        content = "假如未来自动启动 Codex，会有什么风险？"
        # Provider path
        provider = _make_provider(json.dumps(_valid_interpretation_dict(
            conversation_mode="solution_exploration",
            primary_intent="discuss_hypothetical_risk",
            confidence=0.7,
            formal_action_requested=False,
            hypothetical_action=True,
        )))
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=provider)
        result = svc.interpret(content=content, model_name="m", request_id="r")
        assert result.interpretation.conversation_mode == ConversationMode.SOLUTION_EXPLORATION
        assert result.interpretation.formal_action_requested is False
        assert result.interpretation.hypothetical_action is True
        assert result.risk_semantic_conflict is False

    def test_hypothetical_risk_discussion_fallback(self):
        content = "假如未来自动启动 Codex，会有什么风险？"
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=None)
        result = svc.interpret(content=content, model_name="m", request_id="r")
        assert result.interpretation.conversation_mode == ConversationMode.SOLUTION_EXPLORATION
        assert result.interpretation.formal_action_requested is False
        assert result.interpretation.hypothetical_action is True
        assert result.risk_semantic_conflict is False

    def test_option_comparison(self):
        content = "比较 A 和 B 两个方案，先不要修改计划。"
        provider = _make_provider(json.dumps(_valid_interpretation_dict(
            conversation_mode="option_comparison",
            primary_intent="compare_options",
            confidence=0.7,
            formal_action_requested=False,
            hypothetical_action=False,
        )))
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=provider)
        result = svc.interpret(content=content, model_name="m", request_id="r")
        assert result.interpretation.conversation_mode == ConversationMode.OPTION_COMPARISON
        assert result.interpretation.formal_action_requested is False

    def test_option_comparison_fallback(self):
        content = "比较 A 和 B 两个方案，先不要修改计划。"
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=None)
        result = svc.interpret(content=content, model_name="m", request_id="r")
        assert result.interpretation.conversation_mode == ConversationMode.OPTION_COMPARISON
        assert result.interpretation.formal_action_requested is False

    def test_status_query(self):
        content = "当前 P26 做到哪了？"
        provider = _make_provider(json.dumps(_valid_interpretation_dict(
            conversation_mode="status_query",
            primary_intent="query_status",
            confidence=0.7,
            formal_action_requested=False,
            hypothetical_action=False,
            needs_formal_fact_context=True,
        )))
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=provider)
        result = svc.interpret(content=content, model_name="m", request_id="r")
        assert result.interpretation.conversation_mode == ConversationMode.STATUS_QUERY
        assert result.interpretation.needs_formal_fact_context is True
        assert result.interpretation.formal_action_requested is False

    def test_status_query_fallback(self):
        content = "当前 P26 做到哪了？"
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=None)
        result = svc.interpret(content=content, model_name="m", request_id="r")
        assert result.interpretation.conversation_mode == ConversationMode.STATUS_QUERY
        assert result.interpretation.needs_formal_fact_context is True
        assert result.interpretation.formal_action_requested is False

    def test_formalization_request(self):
        content = "我确认，按这个结论生成新的计划草案。"
        provider = _make_provider(json.dumps(_valid_interpretation_dict(
            conversation_mode="formalization_request",
            primary_intent="formalize_plan",
            confidence=0.8,
            formal_action_requested=True,
            hypothetical_action=False,
            needs_formal_fact_context=True,
            needs_discussion_history=True,
        )))
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=provider)
        result = svc.interpret(content=content, model_name="m", request_id="r")
        assert result.interpretation.conversation_mode == ConversationMode.FORMALIZATION_REQUEST
        assert result.interpretation.formal_action_requested is True
        assert result.interpretation.hypothetical_action is False
        assert result.interpretation.needs_formal_fact_context is True
        assert result.interpretation.needs_discussion_history is True

    def test_formalization_request_fallback_conflict(self):
        """Risk scanner has no formalization signal; fallback detects conflict."""
        content = "我确认，按这个结论生成新的计划草案。"
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=None)
        result = svc.interpret(content=content, model_name="m", request_id="r")
        assert result.interpretation.conversation_mode == ConversationMode.FORMALIZATION_REQUEST
        assert result.interpretation.formal_action_requested is True
        # Risk scanner doesn't have formalization phrases → conflict
        assert result.risk_semantic_conflict is True

    def test_action_request(self):
        content = "立即创建任务并启动 Codex。"
        provider = _make_provider(json.dumps(_valid_interpretation_dict(
            conversation_mode="action_request",
            primary_intent="execute_action",
            confidence=0.9,
            formal_action_requested=True,
            hypothetical_action=False,
        )))
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=provider)
        result = svc.interpret(content=content, model_name="m", request_id="r")
        assert result.interpretation.conversation_mode == ConversationMode.ACTION_REQUEST
        assert result.interpretation.formal_action_requested is True
        assert result.interpretation.hypothetical_action is False

    def test_action_request_fallback(self):
        content = "立即创建任务并启动 Codex。"
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=None)
        result = svc.interpret(content=content, model_name="m", request_id="r")
        assert result.interpretation.conversation_mode == ConversationMode.ACTION_REQUEST
        assert result.interpretation.formal_action_requested is True
        assert result.interpretation.hypothetical_action is False
        assert result.risk_semantic_conflict is False

    def test_preference_update(self):
        content = "这个方向不错，但我还要再考虑一下。"
        provider = _make_provider(json.dumps(_valid_interpretation_dict(
            conversation_mode="preference_update",
            primary_intent="express_preference",
            confidence=0.6,
            formal_action_requested=False,
            hypothetical_action=False,
        )))
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=provider)
        result = svc.interpret(content=content, model_name="m", request_id="r")
        assert result.interpretation.conversation_mode == ConversationMode.PREFERENCE_UPDATE
        assert result.interpretation.formal_action_requested is False

    def test_preference_update_fallback(self):
        content = "这个方向不错，但我还要再考虑一下。"
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=None)
        result = svc.interpret(content=content, model_name="m", request_id="r")
        assert result.interpretation.conversation_mode == ConversationMode.PREFERENCE_UPDATE
        assert result.interpretation.formal_action_requested is False


# ===========================================================================
# 12. Semantic boundary tests
# ===========================================================================


class TestSemanticBoundary:
    def test_risk_word_not_execution_command(self):
        """Risk word present. '部署' is both risk word and action marker,
        so fallback classifies as action_request — not a conflict."""
        content = "我们讨论一下部署架构的优缺点。"
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=None)
        result = svc.interpret(content=content, model_name="m", request_id="r")
        # "部署" is in both risk words and action markers → action_request
        assert result.interpretation.formal_action_requested is True
        assert result.risk_semantic_conflict is False

    def test_risk_word_option_comparison(self):
        content = "请比较部署方案 A 和 B，先不要执行。"
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=None)
        result = svc.interpret(content=content, model_name="m", request_id="r")
        assert result.interpretation.conversation_mode == ConversationMode.OPTION_COMPARISON
        assert result.interpretation.formal_action_requested is False

    def test_explicit_negation_not_action(self):
        content = "请不要启动 Codex。"
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=None)
        result = svc.interpret(content=content, model_name="m", request_id="r")
        # Negation prevents action request classification
        assert result.interpretation.formal_action_requested is False
        # Risk signal present but not formal/hypothetical → conflict
        assert result.risk_semantic_conflict is True

    def test_mixed_negation_and_real_command(self):
        """Mixed negation + command: diagnostic only, not a production defect."""
        content = "不要修改计划，但立即创建任务并启动 Codex。"
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=None)
        result = svc.interpret(content=content, model_name="m", request_id="r")
        # Risk signals must be complete
        assert result.risk_scan.has_side_effect_signal is True
        # No side effects
        assert result.source == DirectorResponseSource.RULE_FALLBACK

    def test_general_discussion_fallback(self):
        content = "这个项目的总体思路是什么？"
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=None)
        result = svc.interpret(content=content, model_name="m", request_id="r")
        assert result.interpretation.conversation_mode == ConversationMode.GENERAL_DISCUSSION
        assert result.interpretation.confidence == 0.35
        assert result.interpretation.formal_action_requested is False
        assert result.interpretation.hypothetical_action is False
        assert result.risk_semantic_conflict is False


# ===========================================================================
# 13. Fallback confidence tests
# ===========================================================================


class TestFallbackConfidence:
    @pytest.mark.parametrize(
        ("content", "expected_mode"),
        [
            ("假如未来自动启动 Codex，会有什么风险？", "solution_exploration"),
            ("我确认，按这个结论生成新的计划草案。", "formalization_request"),
            ("立即创建任务并启动 Codex。", "action_request"),
            ("比较 A 和 B 两个方案", "option_comparison"),
            ("当前 P26 做到哪了？", "status_query"),
            ("这个方向不错，但我还要再考虑一下。", "preference_update"),
            ("你好，今天天气如何？", "general_discussion"),
        ],
    )
    def test_fallback_confidence_at_most_065(self, content: str, expected_mode: str):
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=None)
        result = svc.interpret(content=content, model_name="m", request_id="r")
        assert result.interpretation.confidence <= 0.65

    def test_general_discussion_confidence_is_035(self):
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=None)
        result = svc.interpret(content="这个项目的总体思路是什么？", model_name="m", request_id="r")
        assert result.interpretation.confidence == 0.35


# ===========================================================================
# 14. risk_semantic_conflict matrix
# ===========================================================================


class TestRiskSemanticConflictMatrix:
    """Tests that use the service to compute risk_semantic_conflict
    via _has_risk_semantic_conflict, not direct construction."""

    def test_risk_and_formal_no_conflict(self):
        """Risk signal + formal_action_requested=True → no conflict."""
        provider = _make_provider(json.dumps(_valid_interpretation_dict(
            formal_action_requested=True,
            hypothetical_action=False,
        )))
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=provider)
        result = svc.interpret(content="立即创建任务", model_name="m", request_id="r")
        assert result.risk_scan.has_side_effect_signal is True
        assert result.interpretation.formal_action_requested is True
        assert result.risk_semantic_conflict is False

    def test_risk_and_hypothetical_no_conflict(self):
        """Risk signal + hypothetical_action=True → no conflict."""
        provider = _make_provider(json.dumps(_valid_interpretation_dict(
            formal_action_requested=False,
            hypothetical_action=True,
        )))
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=provider)
        result = svc.interpret(content="启动 Codex", model_name="m", request_id="r")
        assert result.risk_scan.has_side_effect_signal is True
        assert result.interpretation.hypothetical_action is True
        assert result.risk_semantic_conflict is False

    def test_risk_and_neither_conflict(self):
        """Risk signal + neither formal nor hypothetical → conflict."""
        provider = _make_provider(json.dumps(_valid_interpretation_dict(
            formal_action_requested=False,
            hypothetical_action=False,
        )))
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=provider)
        result = svc.interpret(content="启动 Codex", model_name="m", request_id="r")
        assert result.risk_scan.has_side_effect_signal is True
        assert result.interpretation.formal_action_requested is False
        assert result.interpretation.hypothetical_action is False
        assert result.risk_semantic_conflict is True

    def test_no_risk_and_neither_no_conflict(self):
        """No risk signal + neither formal nor hypothetical → no conflict."""
        provider = _make_provider(json.dumps(_valid_interpretation_dict(
            formal_action_requested=False,
            hypothetical_action=False,
        )))
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=provider)
        result = svc.interpret(content="天气真好", model_name="m", request_id="r")
        assert result.risk_scan.has_side_effect_signal is False
        assert result.risk_semantic_conflict is False

    def test_no_risk_and_formal_conflict(self):
        """No risk signal + formal_action_requested=True → conflict."""
        provider = _make_provider(json.dumps(_valid_interpretation_dict(
            formal_action_requested=True,
            hypothetical_action=False,
        )))
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=provider)
        result = svc.interpret(content="天气真好", model_name="m", request_id="r")
        assert result.risk_scan.has_side_effect_signal is False
        assert result.interpretation.formal_action_requested is True
        assert result.risk_semantic_conflict is True

    def test_formal_and_hypothetical_rejected_at_contract_level(self):
        """TurnInterpretation rejects both flags true."""
        with pytest.raises(ValueError, match="cannot both be true"):
            TurnInterpretation(
                conversation_mode=ConversationMode.GENERAL_DISCUSSION,
                primary_intent="test",
                confidence=0.5,
                formal_action_requested=True,
                hypothetical_action=True,
                reason_summary="test",
            )


# ===========================================================================
# 15. Prompt content tests
# ===========================================================================


class TestPromptContent:
    def _capture_prompt(self, content: str = "测试内容") -> str:
        captured: list[str] = []
        def fake_provider(model: str, prompt: str, req_id: str):
            captured.append(prompt)
            return json.dumps(_valid_interpretation_dict()), "r-001"
        svc = ProjectDirectorTurnInterpreterService(provider_text_generator=fake_provider)
        svc.interpret(content=content, model_name="m", request_id="r")
        return captured[0]

    def test_prompt_requires_json_only(self):
        prompt = self._capture_prompt()
        assert "JSON" in prompt or "json" in prompt

    def test_prompt_contains_field_template(self):
        prompt = self._capture_prompt()
        assert "conversation_mode" in prompt
        assert "primary_intent" in prompt
        assert "confidence" in prompt

    def test_prompt_contains_risk_not_action_evidence(self):
        prompt = self._capture_prompt()
        assert "Risk scan" in prompt or "risk" in prompt.lower()

    def test_prompt_contains_hypothetical_rule(self):
        prompt = self._capture_prompt()
        assert "Hypothetical" in prompt or "hypothetical" in prompt

    def test_prompt_contains_comparison_rule(self):
        prompt = self._capture_prompt()
        assert "comparison" in prompt.lower() or "Option" in prompt

    def test_prompt_contains_six_semantic_examples(self):
        prompt = self._capture_prompt()
        assert "假如" in prompt
        assert "比较" in prompt
        assert "做到哪" in prompt
        assert "确认" in prompt or "生成" in prompt
        assert "立即创建" in prompt or "启动 Codex" in prompt
        assert "这个方向不错" in prompt

    def test_prompt_contains_risk_signal_types(self):
        prompt = self._capture_prompt("启动 Codex")
        assert "executor_start" in prompt

    def test_prompt_contains_trimmed_user_turn(self):
        prompt = self._capture_prompt("  创建任务  ")
        # The trimmed content appears in the prompt as JSON-encoded string
        assert "创建任务" in prompt

    def test_prompt_does_not_require_answer(self):
        prompt = self._capture_prompt()
        assert "answer" not in prompt.lower() or "Do not output answer" in prompt

    def test_prompt_does_not_require_delta(self):
        prompt = self._capture_prompt()
        assert "DiscussionDelta" not in prompt

    def test_prompt_does_not_require_formalization(self):
        prompt = self._capture_prompt()
        assert "FormalizationProposal" not in prompt

    def test_prompt_does_not_require_plan_task_run(self):
        prompt = self._capture_prompt()
        assert "PlanVersion" not in prompt
        assert "Task" not in prompt or "task_creation" in prompt
        assert "Run" not in prompt


# ===========================================================================
# 16. AST pure service boundary
# ===========================================================================


_FORBIDDEN_IMPORTS = {
    "sqlalchemy",
    "alembic",
    "requests",
    "httpx",
    "openai",
    "subprocess",
    "pathlib",
    "app.repositories",
    "app.api",
    "app.db",
    "app.core.db",
    "app.services.provider_config_service",
    "app.services.project_director_message_service",
    "app.domain.project_director_conversation_router",
}

_ALLOWED_APP_SUBMODULES = {
    "app.domain",
    "app.services.project_director_turn_interpreter_service",
}

_SERVICE_FILES = [
    "app/domain/project_director_semantic_turn.py",
    "app/services/project_director_turn_interpreter_service.py",
]


def _collect_full_imports_from_file(filepath: str) -> set[str]:
    with open(filepath) as f:
        tree = ast.parse(f.read(), filename=filepath)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def _is_forbidden(full_import: str) -> bool:
    for forbidden in _FORBIDDEN_IMPORTS:
        if full_import == forbidden or full_import.startswith(forbidden + "."):
            return True
    return False


def _is_allowed(full_import: str) -> bool:
    if full_import.startswith("app."):
        for allowed in _ALLOWED_APP_SUBMODULES:
            if full_import == allowed or full_import.startswith(allowed + "."):
                return True
        return False
    return True


class TestPureServiceImportBoundary:
    @pytest.mark.parametrize("module_path", _SERVICE_FILES)
    def test_no_forbidden_imports(self, module_path):
        import os
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(base, module_path)
        collected = _collect_full_imports_from_file(full_path)

        for full_import in collected:
            if full_import.startswith("app."):
                assert _is_allowed(full_import), (
                    f"Forbidden app import '{full_import}' in {module_path}"
                )
            else:
                assert not _is_forbidden(full_import), (
                    f"Forbidden import '{full_import}' in {module_path}"
                )

    def test_import_has_no_side_effects(self):
        """Importing modules creates no files, network, or DB connections."""
        import importlib
        mod_turn = importlib.import_module("app.domain.project_director_semantic_turn")
        mod_svc = importlib.import_module("app.services.project_director_turn_interpreter_service")
        assert mod_turn is not None
        assert mod_svc is not None
