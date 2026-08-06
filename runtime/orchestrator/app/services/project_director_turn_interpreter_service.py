"""Provider-first, side-effect-free semantic turn interpretation for P26-B1.

This module does not persist messages or discussion state, create plans, tasks,
or runs, start workers or executors, mutate repositories, or access a provider
configuration, network, database, or message service.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
import re
from uuid import UUID

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


@dataclass(frozen=True, slots=True)
class VisibleDiscussionOptionReference:
    """A trimmed, read-only option identity available to one interpreted turn."""

    option_id: UUID
    aliases: tuple[str, ...]
    is_active: bool
    is_rejected: bool


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
            "发布这个版本",
            "发布该版本",
            "发布此版本",
            "发布新版本",
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
    _FORMALIZATION_DISCUSSION_LEAD_MARKERS = (
        "讨论",
        "分析",
        "解释",
        "比较",
        "对比",
    )
    _FORMALIZATION_QUERY_MARKERS = (
        "是否",
        "什么意思",
        "会有什么风险",
        "有什么风险",
        "哪个更合适",
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
        "上线",
        "发布",
        "应用",
    )
    _NEGATED_ACTION_MARKERS = ("不要", "不需要", "不用", "无需", "不必", "别")
    _COMPARISON_MARKERS = ("比较", "对比", "哪个方案", "A 和 B", "A/B", "方案一", "方案二")
    _STATUS_MARKERS = ("当前状态", "现在进度", "做到哪", "项目情况", "当前进展")
    _PREFERENCE_MARKERS = ("我更倾向", "我比较喜欢", "优先选", "暂时选")
    _CONSTRAINT_MARKERS = (
        "新增约束",
        "约束",
        "必须",
        "不要",
        "不允许",
        "绝对不能",
        "实施顺序",
        "追溯到原始",
    )
    _PREFERENCE_EXCLUSION_MARKERS = (
        "如果",
        "假如",
        "假设",
        "只要",
        "除非",
        "条件满足",
        "是否",
        "会怎样",
        "有什么风险",
        "请分析",
        "还没有决定",
        "尚未决定",
        "不再选择",
        "不要",
        "不选",
    )

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
        visible_options: tuple[VisibleDiscussionOptionReference, ...] = (),
    ) -> TurnInterpretationOutcome:
        """Interpret a trimmed user turn without persisting or applying any result."""

        normalized_content = content.strip()
        if not normalized_content:
            raise ValueError("content must not be empty or whitespace-only")

        risk_scan = self._risk_scanner.scan(normalized_content)
        resolved_option_id = self._resolve_visible_option_reference(
            content=normalized_content,
            visible_options=visible_options,
        )
        if self._provider_text_generator is None:
            return self._build_fallback_outcome(
                content=normalized_content,
                risk_scan=risk_scan,
                reason="provider_unavailable",
                provider_attempted=False,
                resolved_option_id=resolved_option_id,
            )

        try:
            output_text, receipt_id = self._provider_text_generator(
                model_name,
                self._build_provider_prompt(
                    content=normalized_content,
                    risk_scan=risk_scan,
                    visible_options=visible_options,
                ),
                request_id,
            )
        except Exception:  # noqa: BLE001 - semantic fallback is intentionally safe
            return self._build_fallback_outcome(
                content=normalized_content,
                risk_scan=risk_scan,
                reason="provider_failed",
                provider_attempted=True,
                resolved_option_id=resolved_option_id,
            )

        if not isinstance(output_text, str) or not output_text.strip():
            return self._build_fallback_outcome(
                content=normalized_content,
                risk_scan=risk_scan,
                reason="provider_empty_output",
                provider_attempted=True,
                resolved_option_id=resolved_option_id,
            )

        try:
            interpretation = self._parse_turn_interpretation(output_text)
        except ValueError:
            return self._build_fallback_outcome(
                content=normalized_content,
                risk_scan=risk_scan,
                reason="provider_contract_invalid",
                provider_attempted=True,
                resolved_option_id=resolved_option_id,
            )

        if self._has_provider_semantic_inconsistency(
            content=normalized_content,
            interpretation=interpretation,
        ):
            return self._build_fallback_outcome(
                content=normalized_content,
                risk_scan=risk_scan,
                reason="provider_semantic_inconsistent",
                provider_attempted=True,
                resolved_option_id=resolved_option_id,
            )

        outcome = TurnInterpretationOutcome(
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
        return self._normalize_visible_option_references(
            outcome=outcome,
            content=normalized_content,
            resolved_option_id=resolved_option_id,
            visible_options=visible_options,
        )

    @classmethod
    def _build_provider_prompt(
        cls,
        *,
        content: str,
        risk_scan: ConversationRiskScan,
        visible_options: tuple[VisibleDiscussionOptionReference, ...] = (),
    ) -> str:
        risk_types = [signal.signal_type.value for signal in risk_scan.signals]
        option_catalog = [
            {
                "option_id": str(option.option_id),
                "aliases": list(option.aliases),
                "is_active": option.is_active,
                "is_rejected": option.is_rejected,
            }
            for option in visible_options
        ]
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

For an explicit, current, non-hypothetical request to formalize a plan draft, conversation_mode must be formalization_request, formal_action_requested must be true, and hypothetical_action must be false. Never output general_discussion with formal_action_requested=true for that request.

A formalization request may include secondary requests to explain, assess, compare impacts, or describe risks inside the proposal. Those secondary clauses do not change the primary conversation_mode from formalization_request.

visible_options is the complete catalog of option IDs you may reference. referenced_option_ids must contain only IDs from this catalog. Never generate a UUID or reference an option outside this catalog. When the user makes one explicit, current, non-hypothetical selection or reselection of exactly one visible option, set conversation_mode=preference_update and referenced_option_ids to exactly that option ID. Rejected options remain valid reselection targets. Questions, conditions, comparisons, negations, and undecided language are not current selections.

Examples:
- 假如未来自动启动 Codex，会有什么风险？ => solution_exploration, false, true
- 比较 A 和 B 两个方案，先不要修改计划。 => option_comparison, false, false
- 当前 P26 做到哪了？ => status_query, false, false
- 我确认，按这个结论生成新的计划草案。 => formalization_request, true, false
- 我确认按当前结论生成新的计划草案，先给正式化提案，确认后再创建计划版本。 => formalization_request, true, false
- 我确认按当前结论生成新的计划草案，并在提案中说明主要风险。 => formalization_request, true, false
- 立即创建任务并启动 Codex。 => action_request, true, false
- 新增约束：不要大规模重构。 => constraint_update, false, false
- 未来必须同时支持 Codex 和 Claude Code，但这一轮不要启动任何一个。 => constraint_update, false, false
- 这个方向看起来不错。 => general_discussion, false, false

deterministic_risk_signal_types={json.dumps(risk_types, ensure_ascii=False)}
visible_options={json.dumps(option_catalog, ensure_ascii=False)}
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
        resolved_option_id: UUID | None = None,
    ) -> TurnInterpretationOutcome:
        interpretation = self._build_fallback_interpretation(
            content=content,
            risk_scan=risk_scan,
            resolved_option_id=resolved_option_id,
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
        resolved_option_id: UUID | None = None,
    ) -> TurnInterpretation:
        referenced_option_ids = (
            [resolved_option_id] if resolved_option_id is not None else None
        )
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
                referenced_option_ids=referenced_option_ids,
            )
        if cls._is_explicit_formalization_request(content):
            return cls._interpretation(
                mode=ConversationMode.FORMALIZATION_REQUEST,
                intent="request_plan_formalization",
                confidence=0.6,
                formal_action_requested=True,
                reason="deterministic_fallback_plan_formalization",
                needs_formal_fact_context=True,
                needs_discussion_history=True,
                referenced_option_ids=referenced_option_ids,
            )
        if cls._contains_any(content, cls._CONSTRAINT_MARKERS):
            return cls._interpretation(
                mode=ConversationMode.CONSTRAINT_UPDATE,
                intent="update_explicit_constraint",
                confidence=0.6,
                reason="deterministic_fallback_explicit_constraint",
                needs_discussion_history=True,
                referenced_option_ids=referenced_option_ids,
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
                needs_discussion_history=True,
                referenced_option_ids=referenced_option_ids,
            )
        if (
            resolved_option_id is None
            and cls._contains_any(content, cls._COMPARISON_MARKERS)
        ):
            return cls._interpretation(
                mode=ConversationMode.OPTION_COMPARISON,
                intent="compare_options",
                confidence=0.55,
                reason="deterministic_fallback_option_comparison",
                needs_discussion_history=True,
                referenced_option_ids=referenced_option_ids,
            )
        if cls._contains_any(content, cls._STATUS_MARKERS):
            return cls._interpretation(
                mode=ConversationMode.STATUS_QUERY,
                intent="query_current_status",
                confidence=0.55,
                reason="deterministic_fallback_status_query",
                needs_formal_fact_context=True,
                referenced_option_ids=referenced_option_ids,
            )
        if resolved_option_id is not None:
            return cls._interpretation(
                mode=ConversationMode.PREFERENCE_UPDATE,
                intent="update_preference",
                confidence=0.65,
                reason="deterministic_visible_option_reference",
                needs_discussion_history=True,
                referenced_option_ids=referenced_option_ids,
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
        referenced_option_ids: list[UUID] | None = None,
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
            referenced_option_ids=referenced_option_ids or [],
        )

    @classmethod
    def _resolve_visible_option_reference(
        cls,
        *,
        content: str,
        visible_options: tuple[VisibleDiscussionOptionReference, ...],
    ) -> UUID | None:
        """Resolve one explicit selection only when one visible identity matches."""

        if not cls._is_deterministic_current_preference(content):
            return None

        normalized_content = cls._normalize_option_text(content)
        matched_option_ids = {
            option.option_id
            for option in visible_options
            if any(
                cls._content_mentions_alias(normalized_content, alias)
                for alias in option.aliases
            )
        }
        return next(iter(matched_option_ids)) if len(matched_option_ids) == 1 else None

    @classmethod
    def _is_deterministic_current_preference(cls, content: str) -> bool:
        compact = re.sub(r"\s+", "", content.lower())
        if not compact or "?" in compact or "？" in compact:
            return False
        if cls._contains_any(compact, cls._PREFERENCE_EXCLUSION_MARKERS):
            return False
        if (
            ("还是" in compact and "我最终还是选择" not in compact)
            or "对比" in compact
            or "哪个" in compact
        ):
            return False
        if re.search(r"(?:当|在).+?时", compact):
            return False
        return any(
            re.search(pattern, compact)
            for pattern in (
                r"我(?:当前)?选择(?:方案|选项|组合)?",
                r"我比较喜欢(?:方案|选项|组合)?",
                r"我优先(?:选|选择)(?:方案|选项|组合)?",
                r"我(?:重新选择|重新选)(?:方案|选项|组合)?",
                r"我改变主意了?[，,]?(?:重新选择|重新选)(?:方案|选项|组合)?",
                r"我决定(?:重新选择|重新选)(?:方案|选项|组合)?",
                r"我(?:改选|改回|换回)(?:方案|选项|组合)?",
                r"我最终还是选择(?:方案|选项|组合)?",
            )
        )

    @staticmethod
    def _normalize_option_text(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip()).lower()

    @classmethod
    def _content_mentions_alias(cls, content: str, alias: str) -> bool:
        normalized_alias = cls._normalize_option_text(alias).strip(" :：")
        if not normalized_alias:
            return False
        if re.fullmatch(r"[a-z0-9]+", normalized_alias):
            return re.search(
                rf"(?<![a-z0-9]){re.escape(normalized_alias)}(?![a-z0-9])",
                content,
            ) is not None
        return normalized_alias in content

    @classmethod
    def _normalize_visible_option_references(
        cls,
        *,
        outcome: TurnInterpretationOutcome,
        content: str,
        resolved_option_id: UUID | None,
        visible_options: tuple[VisibleDiscussionOptionReference, ...],
    ) -> TurnInterpretationOutcome:
        interpretation = outcome.interpretation
        visible_option_ids = {option.option_id for option in visible_options}
        updates: dict[str, object] = {}

        if resolved_option_id is not None:
            deterministic_interpretation = cls._build_fallback_interpretation(
                content=content,
                risk_scan=outcome.risk_scan,
                resolved_option_id=resolved_option_id,
            )
            required_values = {
                "conversation_mode": deterministic_interpretation.conversation_mode,
                "primary_intent": deterministic_interpretation.primary_intent,
                "formal_action_requested": (
                    deterministic_interpretation.formal_action_requested
                ),
                "hypothetical_action": deterministic_interpretation.hypothetical_action,
                "referenced_option_ids": [resolved_option_id],
                "needs_discussion_history": True,
            }
            if deterministic_interpretation.needs_formal_fact_context:
                required_values["needs_formal_fact_context"] = True
            updates = {
                field_name: value
                for field_name, value in required_values.items()
                if getattr(interpretation, field_name) != value
            }
        else:
            admitted_option_ids = [
                option_id
                for option_id in interpretation.referenced_option_ids
                if option_id in visible_option_ids
            ]
            if admitted_option_ids != interpretation.referenced_option_ids:
                updates["referenced_option_ids"] = admitted_option_ids

        if not updates:
            return outcome

        normalized_interpretation = interpretation.model_copy(update=updates)
        return outcome.model_copy(
            update={
                "interpretation": normalized_interpretation,
                "source_detail": (
                    f"{outcome.source_detail};normalized=visible_option_reference"
                ),
                "risk_semantic_conflict": cls._has_risk_semantic_conflict(
                    interpretation=normalized_interpretation,
                    risk_scan=outcome.risk_scan,
                ),
            }
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

    @classmethod
    def _is_explicit_formalization_request(cls, content: str) -> bool:
        """Recognize a current request to produce a proposal, not discussion of one."""

        marker = cls._find_formalization_marker(content)
        if marker is None:
            return False

        marker_index, marker_text = marker
        return not (
            cls._is_formalization_hypothetical(
                content=content,
                marker_index=marker_index,
            )
            or cls._is_formalization_negated(
                content=content,
                marker_index=marker_index,
            )
            or cls._is_discussion_only_formalization_reference(
                content=content,
                marker_index=marker_index,
                marker_text=marker_text,
            )
        )

    @classmethod
    def _find_formalization_marker(cls, content: str) -> tuple[int, str] | None:
        normalized = content.lower()
        matches = (
            (normalized.find(marker.lower()), marker)
            for marker in cls._FORMALIZATION_MARKERS
            if normalized.find(marker.lower()) >= 0
        )
        return min(
            matches,
            key=lambda match: (match[0], -len(match[1])),
            default=None,
        )

    @classmethod
    def _is_formalization_hypothetical(
        cls,
        *,
        content: str,
        marker_index: int,
    ) -> bool:
        return cls._contains_any(
            cls._formalization_sentence_prefix(content, marker_index),
            cls._HYPOTHETICAL_MARKERS,
        )

    @classmethod
    def _is_formalization_negated(
        cls,
        *,
        content: str,
        marker_index: int,
    ) -> bool:
        prefix = cls._formalization_sentence_prefix(content, marker_index)
        negation_index = max(
            (prefix.rfind(marker) for marker in cls._NEGATED_ACTION_MARKERS),
            default=-1,
        )
        if negation_index < 0:
            return False

        return "，" not in prefix[negation_index:]

    @classmethod
    def _is_discussion_only_formalization_reference(
        cls,
        *,
        content: str,
        marker_index: int,
        marker_text: str,
    ) -> bool:
        prefix = cls._formalization_sentence_prefix(content, marker_index)
        suffix = cls._formalization_sentence_suffix(
            content,
            marker_index + len(marker_text),
        )
        return cls._contains_any(
            prefix,
            cls._FORMALIZATION_DISCUSSION_LEAD_MARKERS,
        ) or cls._contains_any(suffix, cls._FORMALIZATION_QUERY_MARKERS)

    @staticmethod
    def _formalization_sentence_prefix(content: str, marker_index: int) -> str:
        sentence_start = max(
            content.rfind(boundary, 0, marker_index)
            for boundary in ("。", "！", "？", "\n")
        )
        return content[sentence_start + 1 : marker_index]

    @staticmethod
    def _formalization_sentence_suffix(content: str, marker_end_index: int) -> str:
        suffix = content[marker_end_index:]
        boundary_indexes = (
            suffix.find(boundary) for boundary in ("。", "！", "？", "\n")
        )
        sentence_end = min(
            (index for index in boundary_indexes if index >= 0),
            default=len(suffix),
        )
        return suffix[:sentence_end]

    @classmethod
    def _has_provider_semantic_inconsistency(
        cls,
        *,
        content: str,
        interpretation: TurnInterpretation,
    ) -> bool:
        explicit_formalization = cls._is_explicit_formalization_request(content)
        if explicit_formalization and (
            interpretation.conversation_mode != ConversationMode.FORMALIZATION_REQUEST
            or not interpretation.formal_action_requested
            or interpretation.hypothetical_action
        ):
            return True
        return (
            interpretation.conversation_mode == ConversationMode.FORMALIZATION_REQUEST
            and (
                not interpretation.formal_action_requested
                or interpretation.hypothetical_action
            )
        )

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
