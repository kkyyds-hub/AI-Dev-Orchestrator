"""Provider-first, side-effect-free semantic turn interpretation for P26-B1.

This module does not persist messages or discussion state, create plans, tasks,
or runs, start workers or executors, mutate repositories, or access a provider
configuration, network, database, or message service.
"""

from __future__ import annotations

from collections.abc import Callable
import json
import re

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


ProviderTextGenerator = Callable[[str, str, str], tuple[str, str | None]]


class DeterministicConversationRiskScanner:
    """Detect possible side-effect language without deciding turn semantics."""

    _RISK_PHRASES: dict[ConversationRiskSignalType, tuple[str, ...]] = {
        ConversationRiskSignalType.TASK_CREATION: (
            "创建任务",
            "新建任务",
            "生成任务",
            "派发任务",
        ),
        ConversationRiskSignalType.WORKER_START: (
            "启动 Worker",
            "运行 Worker",
            "派发 Worker",
            "启动工作器",
        ),
        ConversationRiskSignalType.EXECUTOR_START: (
            "启动执行器",
            "运行执行器",
            "启动 Codex",
            "运行 Codex",
            "调用 Codex",
            "启动 Claude Code",
            "运行 Claude Code",
            "调用 Claude Code",
            "开始执行",
            "立即执行",
        ),
        ConversationRiskSignalType.PLAN_MODIFICATION: (
            "修改计划",
            "调整计划",
            "修改草案",
            "调整草案",
            "改验收标准",
            "修改验收标准",
        ),
        ConversationRiskSignalType.PLAN_APPLICATION: (
            "应用草案",
            "应用计划",
            "确认并应用",
            "执行计划",
        ),
        ConversationRiskSignalType.TASK_DELETION: (
            "删除任务",
            "取消任务",
            "移除任务",
        ),
        ConversationRiskSignalType.ACCEPTANCE_CRITERIA_CHANGE: (
            "修改验收标准",
            "调整验收标准",
            "删除验收标准",
        ),
        ConversationRiskSignalType.GIT_WRITE: (
            "git add",
            "git commit",
            "git push",
            "提交代码",
            "推送代码",
            "合并代码",
            "创建 PR",
            "合并 PR",
        ),
        ConversationRiskSignalType.DEPLOYMENT: (
            "部署",
            "上线",
            "发布到服务器",
        ),
        ConversationRiskSignalType.PUBLISH: (
            "正式发布",
            "发布版本",
            "发布应用",
        ),
        ConversationRiskSignalType.DESTRUCTIVE_DATABASE_CHANGE: (
            "删除表",
            "清空数据库",
            "删除数据库",
            "drop table",
            "truncate table",
            "破坏性 migration",
        ),
    }

    def scan(self, content: str) -> ConversationRiskScan:
        """Return all stable, deduplicated risk signals for the supplied text."""

        signals: list[ConversationRiskSignal] = []
        seen: set[tuple[ConversationRiskSignalType, int, int]] = set()
        for signal_type, phrases in self._RISK_PHRASES.items():
            for phrase in phrases:
                for match in re.finditer(re.escape(phrase), content, re.IGNORECASE):
                    key = (signal_type, match.start(), match.end())
                    if key in seen:
                        continue
                    seen.add(key)
                    signals.append(
                        ConversationRiskSignal(
                            signal_type=signal_type,
                            matched_phrase=match.group(),
                            start_index=match.start(),
                            end_index=match.end(),
                        )
                    )
        return ConversationRiskScan(
            signals=signals,
            has_side_effect_signal=bool(signals),
            reason_summary=(
                "deterministic_side_effect_language_detected"
                if signals
                else "no_deterministic_side_effect_language_detected"
            ),
        )


class ProjectDirectorTurnInterpreterService:
    """Interpret one turn with at most one injected provider call and safe fallback."""

    _HYPOTHETICAL_MARKERS = (
        "假如",
        "假设",
        "如果未来",
        "如果以后",
        "未来如果",
        "将来如果",
        "会有什么风险",
        "会发生什么",
        "会怎样",
    )
    _FORMALIZATION_MARKERS = (
        "生成新的计划草案",
        "生成计划草案",
        "按这个结论生成草案",
        "正式化为计划草案",
    )
    _EXPLICIT_REQUEST_CONTEXT_MARKERS = (
        "请",
        "帮我",
        "立即",
        "马上",
        "现在就",
        "直接",
        "开始",
    )
    _DISCUSSION_OR_QUERY_MARKERS = (
        "讨论",
        "分析",
        "解释",
        "说明",
        "比较",
        "对比",
        "评估",
        "风险",
        "优缺点",
        "如何",
        "怎么",
    )
    _EXPLICIT_OPERATION_PHRASES = (
        "创建任务",
        "新建任务",
        "生成任务",
        "派发任务",
        "启动 Worker",
        "运行 Worker",
        "派发 Worker",
        "启动工作器",
        "启动执行器",
        "运行执行器",
        "启动 Codex",
        "运行 Codex",
        "调用 Codex",
        "启动 Claude Code",
        "运行 Claude Code",
        "调用 Claude Code",
        "开始执行",
        "立即执行",
        "修改计划",
        "调整计划",
        "修改草案",
        "调整草案",
        "改验收标准",
        "修改验收标准",
        "应用草案",
        "应用计划",
        "确认并应用",
        "执行计划",
        "删除任务",
        "取消任务",
        "移除任务",
        "git add",
        "git commit",
        "git push",
        "提交代码",
        "推送代码",
        "合并代码",
        "创建 PR",
        "合并 PR",
        "正式发布",
        "发布版本",
        "发布应用",
        "发布到服务器",
        "删除表",
        "清空数据库",
        "删除数据库",
        "drop table",
        "truncate table",
        "破坏性 migration",
    )
    _CONTEXTUAL_OPERATION_MARKERS = (
        "执行",
        "创建",
        "修改",
        "删除",
        "提交",
        "推送",
        "合并",
        "部署",
        "发布",
        "应用",
    )
    _NEGATED_ACTION_MARKERS = ("不要", "不需要", "不用", "无需", "不必", "别")
    _COMPARISON_MARKERS = ("比较", "对比", "哪个方案", "A 和 B", "A/B", "方案一", "方案二")
    _STATUS_MARKERS = ("当前状态", "现在进度", "做到哪", "项目情况", "当前进展")
    _PREFERENCE_MARKERS = ("我更倾向", "我比较喜欢", "这个方向不错", "优先选", "暂时选")

    def __init__(
        self,
        *,
        provider_text_generator: ProviderTextGenerator | None = None,
        risk_scanner: DeterministicConversationRiskScanner | None = None,
    ) -> None:
        self._provider_text_generator = provider_text_generator
        self._risk_scanner = risk_scanner or DeterministicConversationRiskScanner()

    def interpret(
        self,
        *,
        content: str,
        model_name: str,
        request_id: str,
    ) -> TurnInterpretationOutcome:
        """Interpret a trimmed user turn without persisting or applying any result."""

        normalized_content = content.strip()
        if not normalized_content:
            raise ValueError("content must not be empty or whitespace-only")

        risk_scan = self._risk_scanner.scan(normalized_content)
        if self._provider_text_generator is None:
            return self._build_fallback_outcome(
                content=normalized_content,
                risk_scan=risk_scan,
                reason="provider_unavailable",
                provider_attempted=False,
            )

        try:
            output_text, receipt_id = self._provider_text_generator(
                model_name,
                self._build_provider_prompt(
                    content=normalized_content,
                    risk_scan=risk_scan,
                ),
                request_id,
            )
        except Exception:  # noqa: BLE001 - semantic fallback is intentionally safe
            return self._build_fallback_outcome(
                content=normalized_content,
                risk_scan=risk_scan,
                reason="provider_failed",
                provider_attempted=True,
            )

        if not isinstance(output_text, str) or not output_text.strip():
            return self._build_fallback_outcome(
                content=normalized_content,
                risk_scan=risk_scan,
                reason="provider_empty_output",
                provider_attempted=True,
            )

        try:
            interpretation = self._parse_turn_interpretation(output_text)
        except ValueError:
            return self._build_fallback_outcome(
                content=normalized_content,
                risk_scan=risk_scan,
                reason="provider_contract_invalid",
                provider_attempted=True,
            )

        return TurnInterpretationOutcome(
            interpretation=interpretation,
            risk_scan=risk_scan,
            source=DirectorResponseSource.PROVIDER,
            source_detail="p26_b1_provider_turn_interpretation",
            receipt_id=receipt_id,
            provider_attempted=True,
            fallback_reason=None,
            risk_semantic_conflict=self._has_risk_semantic_conflict(
                interpretation=interpretation,
                risk_scan=risk_scan,
            ),
        )

    @classmethod
    def _build_provider_prompt(
        cls,
        *,
        content: str,
        risk_scan: ConversationRiskScan,
    ) -> str:
        risk_types = [signal.signal_type.value for signal in risk_scan.signals]
        return f"""You classify one Project Director user turn. Output only one JSON object, with no Markdown or explanatory text.

Required JSON schema:
{{
  \"conversation_mode\": \"general_discussion\",
  \"primary_intent\": \"discuss_topic\",
  \"confidence\": 0.8,
  \"formal_action_requested\": false,
  \"hypothetical_action\": false,
  \"referenced_option_ids\": [],
  \"referenced_entity_ids\": [],
  \"needs_formal_fact_context\": false,
  \"needs_discussion_history\": true,
  \"needs_retrieval\": false,
  \"reason_summary\": \"brief semantic reason\"
}}

Risk scan is only a side-effect-language hint, never proof of a real action. Do not set formal_action_requested merely because words such as start, execute, deploy, or commit appear. Hypothetical, conditional, and risk-discussion turns must set formal_action_requested=false and hypothetical_action=true. Option comparisons are not plan modifications. \"This direction is good\" is not confirmation of a formal plan. Set formal_action_requested=true only for an explicit real action or formalization request. Do not output answer, delta, proposal, Markdown, or prose outside JSON.

Examples:
- 假如未来自动启动 Codex，会有什么风险？ => solution_exploration, false, true
- 比较 A 和 B 两个方案，先不要修改计划。 => option_comparison, false, false
- 当前 P26 做到哪了？ => status_query, false, false
- 我确认，按这个结论生成新的计划草案。 => formalization_request, true, false
- 立即创建任务并启动 Codex。 => action_request, true, false
- 这个方向不错，但我还要再考虑一下。 => preference_update, false, false

deterministic_risk_signal_types={json.dumps(risk_types, ensure_ascii=False)}
user_turn={json.dumps(content, ensure_ascii=False)}"""

    @staticmethod
    def _parse_turn_interpretation(raw_output: str) -> TurnInterpretation:
        payload = ProjectDirectorTurnInterpreterService._load_provider_json_object(
            raw_output
        )
        if "turn_interpretation" in payload:
            payload = payload["turn_interpretation"]
        if not isinstance(payload, dict):
            raise ValueError("turn_interpretation_not_object")
        try:
            return TurnInterpretation.model_validate(payload)
        except Exception as exc:  # noqa: BLE001 - normalize Pydantic contract failures
            raise ValueError("provider_turn_interpretation_invalid") from exc

    @staticmethod
    def _load_provider_json_object(raw_output: str) -> dict:
        text = raw_output.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("provider_output_not_json") from exc
        if not isinstance(payload, dict):
            raise ValueError("provider_output_not_object")
        return payload

    def _build_fallback_outcome(
        self,
        *,
        content: str,
        risk_scan: ConversationRiskScan,
        reason: str,
        provider_attempted: bool,
    ) -> TurnInterpretationOutcome:
        interpretation = self._build_fallback_interpretation(
            content=content,
            risk_scan=risk_scan,
        )
        return TurnInterpretationOutcome(
            interpretation=interpretation,
            risk_scan=risk_scan,
            source=DirectorResponseSource.RULE_FALLBACK,
            source_detail=f"p26_b1_rule_fallback; reason={reason}",
            receipt_id=None,
            provider_attempted=provider_attempted,
            fallback_reason=reason,
            risk_semantic_conflict=self._has_risk_semantic_conflict(
                interpretation=interpretation,
                risk_scan=risk_scan,
            ),
        )

    @classmethod
    def _build_fallback_interpretation(
        cls,
        *,
        content: str,
        risk_scan: ConversationRiskScan,
    ) -> TurnInterpretation:
        if risk_scan.has_side_effect_signal and cls._contains_any(
            content, cls._HYPOTHETICAL_MARKERS
        ):
            return cls._interpretation(
                mode=ConversationMode.SOLUTION_EXPLORATION,
                intent="discuss_hypothetical_side_effect",
                confidence=0.55,
                hypothetical_action=True,
                reason="deterministic_fallback_hypothetical_side_effect",
                needs_discussion_history=True,
            )
        if cls._contains_any(content, cls._FORMALIZATION_MARKERS):
            return cls._interpretation(
                mode=ConversationMode.FORMALIZATION_REQUEST,
                intent="request_plan_formalization",
                confidence=0.6,
                formal_action_requested=True,
                reason="deterministic_fallback_plan_formalization",
                needs_formal_fact_context=True,
                needs_discussion_history=True,
            )
        if (
            risk_scan.has_side_effect_signal
            and cls._is_explicit_action_request(content)
        ):
            return cls._interpretation(
                mode=ConversationMode.ACTION_REQUEST,
                intent="request_side_effect_action",
                confidence=0.65,
                formal_action_requested=True,
                reason="deterministic_fallback_side_effect_request",
            )
        if cls._contains_any(content, cls._COMPARISON_MARKERS):
            return cls._interpretation(
                mode=ConversationMode.OPTION_COMPARISON,
                intent="compare_options",
                confidence=0.55,
                reason="deterministic_fallback_option_comparison",
                needs_discussion_history=True,
            )
        if cls._contains_any(content, cls._STATUS_MARKERS):
            return cls._interpretation(
                mode=ConversationMode.STATUS_QUERY,
                intent="query_current_status",
                confidence=0.55,
                reason="deterministic_fallback_status_query",
                needs_formal_fact_context=True,
            )
        if cls._contains_any(content, cls._PREFERENCE_MARKERS):
            return cls._interpretation(
                mode=ConversationMode.PREFERENCE_UPDATE,
                intent="update_preference",
                confidence=0.5,
                reason="deterministic_fallback_preference_update",
                needs_discussion_history=True,
            )
        return cls._interpretation(
            mode=ConversationMode.GENERAL_DISCUSSION,
            intent="general_discussion",
            confidence=0.35,
            reason="deterministic_fallback_general_discussion",
        )

    @staticmethod
    def _interpretation(
        *,
        mode: ConversationMode,
        intent: str,
        confidence: float,
        reason: str,
        formal_action_requested: bool = False,
        hypothetical_action: bool = False,
        needs_formal_fact_context: bool = False,
        needs_discussion_history: bool = False,
    ) -> TurnInterpretation:
        return TurnInterpretation(
            conversation_mode=mode,
            primary_intent=intent,
            confidence=confidence,
            formal_action_requested=formal_action_requested,
            hypothetical_action=hypothetical_action,
            reason_summary=reason,
            needs_formal_fact_context=needs_formal_fact_context,
            needs_discussion_history=needs_discussion_history,
        )

    @staticmethod
    def _contains_any(content: str, markers: tuple[str, ...]) -> bool:
        normalized = content.lower()
        return any(marker.lower() in normalized for marker in markers)

    @classmethod
    def _is_explicit_action_request(cls, content: str) -> bool:
        if cls._contains_any(content, cls._NEGATED_ACTION_MARKERS):
            return False
        if cls._contains_any(content, cls._DISCUSSION_OR_QUERY_MARKERS):
            return False
        if cls._contains_any(content, cls._EXPLICIT_OPERATION_PHRASES):
            return True
        return cls._contains_any(
            content, cls._EXPLICIT_REQUEST_CONTEXT_MARKERS
        ) and cls._contains_any(content, cls._CONTEXTUAL_OPERATION_MARKERS)

    @staticmethod
    def _has_risk_semantic_conflict(
        *,
        interpretation: TurnInterpretation,
        risk_scan: ConversationRiskScan,
    ) -> bool:
        if risk_scan.has_side_effect_signal:
            return not (
                interpretation.formal_action_requested
                or interpretation.hypothetical_action
            )
        return interpretation.formal_action_requested
