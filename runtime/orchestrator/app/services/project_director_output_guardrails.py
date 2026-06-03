"""Backend-only guardrails for AI Project Director provider outputs.

These checks run before provider text is persisted or returned to normal users.
They keep technical validation details internal via ``source_detail`` while the
frontend can continue showing a simple business status.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from enum import Enum
from typing import Any


class ProjectDirectorOutputGuardrailError(ValueError):
    """Raised when provider output drifts from the allowed Project Director contract."""


_NEGATION_MARKERS = (
    "不",
    "不会",
    "不得",
    "禁止",
    "不能",
    "不要",
    "no ",
    "not ",
    "never ",
    "do not",
    "does not",
    "without",
)

_UNSAFE_EXECUTION_PHRASES = (
    "自动创建任务",
    "自动生成任务",
    "直接创建任务",
    "立即创建任务",
    "自动启动",
    "启动 worker",
    "调用 worker",
    "运行 worker",
    "worker pool",
    "写仓库",
    "修改仓库",
    "提交代码",
    "git commit",
    "git push",
    "apply-local",
    "planning/apply",
    "automatically create task",
    "automatically create tasks",
    "start worker",
    "run worker",
    "write repository",
    "commit code",
    "push code",
)

_CLARIFICATION_THEMES: dict[str, tuple[str, ...]] = {
    "scope": ("范围", "边界", "不做", "scope", "out of scope"),
    "acceptance": ("验收", "标准", "完成", "验证", "acceptance", "criteria"),
    "constraint": ("约束", "技术栈", "限制", "依赖", "constraint", "dependency"),
    "risk": ("风险", "阻塞", "risk", "blocker"),
    "priority": ("优先级", "时间", "截止", "priority", "deadline"),
}

_PLAN_SAFETY_MARKERS = (
    "不自动创建任务",
    "不自动调用 worker",
    "不调用 worker",
    "不写仓库",
    "不调用 planning/apply",
    "不会自动创建任务",
    "不会自动执行",
    "不得自动执行",
    "manual confirmation",
    "not automatically create tasks",
    "do not automatically create tasks",
    "not run workers",
)


def validate_clarification_output(
    *,
    questions: Sequence[Any],
    goal_text: str,
    constraints: str,
) -> None:
    """Validate provider-generated clarification questions.

    The guardrail checks only backend contract and drift/safety properties. It
    does not add noisy validation fields to the API response.
    """

    if not 3 <= len(questions) <= 6:
        raise ProjectDirectorOutputGuardrailError(
            "clarification_question_count_out_of_range"
        )

    normalized_questions: set[str] = set()
    theme_hits: set[str] = set()
    required_count = 0
    all_text: list[str] = []
    for question in questions:
        question_text = str(getattr(question, "question", "") or "").strip()
        hint_text = str(getattr(question, "hint", "") or "").strip()
        if len(question_text) < 8:
            raise ProjectDirectorOutputGuardrailError(
                "clarification_question_too_short"
            )
        normalized = " ".join(question_text.lower().split())
        if normalized in normalized_questions:
            raise ProjectDirectorOutputGuardrailError(
                "clarification_question_duplicate"
            )
        normalized_questions.add(normalized)
        if bool(getattr(question, "required", True)):
            required_count += 1
        combined = f"{question_text} {hint_text}"
        all_text.append(combined)
        _assert_no_unsafe_execution_intent(
            combined,
            context="clarification",
        )
        for theme, keywords in _CLARIFICATION_THEMES.items():
            if _contains_any(combined, keywords):
                theme_hits.add(theme)

    if required_count < 3:
        raise ProjectDirectorOutputGuardrailError(
            "clarification_required_question_count_too_low"
        )
    if len(theme_hits) < 2:
        raise ProjectDirectorOutputGuardrailError(
            "clarification_theme_coverage_too_low"
        )

    # Lightweight anti-drift: questions should not ignore all user-provided
    # context when the goal/constraints include meaningful terms.
    context_keywords = _significant_context_keywords(goal_text, constraints)
    if context_keywords and not any(
        keyword in " ".join(all_text).lower() for keyword in context_keywords
    ):
        # Do not require exact project names; allow standard planning themes as
        # a safe fallback for short or abstract Chinese goals.
        if not theme_hits.intersection({"scope", "acceptance", "constraint"}):
            raise ProjectDirectorOutputGuardrailError(
                "clarification_context_drift"
            )


def validate_plan_output(
    *,
    goal_text: str,
    constraints: str,
    plan_summary: str,
    phases: Sequence[Any],
    proposed_tasks: Sequence[Any],
    acceptance_criteria: Sequence[str],
    risks: Sequence[str],
    project_scope: Any,
    agent_team_suggestions: Sequence[Any],
    skill_binding_suggestions: Sequence[Any],
    verification_mechanisms: Sequence[Any],
    repository_binding_suggestions: Sequence[Any],
    deliverable_boundaries: Sequence[Any],
    complexity_assessment: Any,
) -> None:
    """Validate provider-generated plan drafts before persistence."""

    if not str(plan_summary).strip():
        raise ProjectDirectorOutputGuardrailError("plan_summary_missing")
    if len(phases) < 1:
        raise ProjectDirectorOutputGuardrailError("plan_phases_missing")
    if len(proposed_tasks) < 1:
        raise ProjectDirectorOutputGuardrailError("plan_proposed_tasks_missing")
    if not [item for item in acceptance_criteria if str(item).strip()]:
        raise ProjectDirectorOutputGuardrailError("plan_acceptance_criteria_missing")
    if not [item for item in risks if str(item).strip()]:
        raise ProjectDirectorOutputGuardrailError("plan_risks_missing")
    if len(agent_team_suggestions) < 1:
        raise ProjectDirectorOutputGuardrailError("plan_agent_team_missing")
    if len(verification_mechanisms) < 1:
        raise ProjectDirectorOutputGuardrailError("plan_verification_missing")
    if len(deliverable_boundaries) < 1:
        raise ProjectDirectorOutputGuardrailError("plan_deliverables_missing")

    in_scope = _model_list_field(project_scope, "in_scope")
    out_of_scope = _model_list_field(project_scope, "out_of_scope")
    assumptions = _model_list_field(project_scope, "assumptions")
    if not in_scope:
        raise ProjectDirectorOutputGuardrailError("plan_in_scope_missing")
    if not out_of_scope and not assumptions:
        raise ProjectDirectorOutputGuardrailError("plan_safety_boundary_missing")

    all_text_values = _collect_text_values(
        [
            goal_text,
            constraints,
            plan_summary,
            phases,
            proposed_tasks,
            acceptance_criteria,
            risks,
            project_scope,
            agent_team_suggestions,
            skill_binding_suggestions,
            verification_mechanisms,
            repository_binding_suggestions,
            deliverable_boundaries,
            complexity_assessment,
        ]
    )
    for text in all_text_values:
        _assert_no_unsafe_execution_intent(text, context="plan")

    safety_text = " ".join(out_of_scope + assumptions).lower()
    if not _contains_any(safety_text, _PLAN_SAFETY_MARKERS):
        raise ProjectDirectorOutputGuardrailError("plan_execution_boundary_missing")

    context_keywords = _significant_context_keywords(goal_text, constraints)
    business_text = " ".join(
        _collect_text_values([plan_summary, phases, proposed_tasks, acceptance_criteria])
    ).lower()
    if context_keywords and not any(keyword in business_text for keyword in context_keywords):
        if not _contains_any(business_text, ("范围", "验收", "阶段", "任务", "验证")):
            raise ProjectDirectorOutputGuardrailError("plan_context_drift")


def _assert_no_unsafe_execution_intent(text: str, *, context: str) -> None:
    normalized = " ".join(str(text).lower().split())
    for phrase in _UNSAFE_EXECUTION_PHRASES:
        index = normalized.find(phrase)
        if index < 0:
            continue
        window = normalized[max(0, index - 18) : index]
        if any(marker in window for marker in _NEGATION_MARKERS):
            continue
        raise ProjectDirectorOutputGuardrailError(
            f"{context}_unsafe_execution_intent:{phrase}"
        )


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    normalized = text.lower()
    return any(keyword.lower() in normalized for keyword in keywords)


def _model_list_field(model: Any, field_name: str) -> list[str]:
    value = getattr(model, field_name, [])
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _collect_text_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Enum):
        return [str(value.value)]
    if isinstance(value, dict):
        collected: list[str] = []
        for item in value.values():
            collected.extend(_collect_text_values(item))
        return collected
    if isinstance(value, (list, tuple, set)):
        collected = []
        for item in value:
            collected.extend(_collect_text_values(item))
        return collected
    if hasattr(value, "model_dump"):
        return _collect_text_values(value.model_dump())
    return [str(value)]


def _significant_context_keywords(*texts: str) -> set[str]:
    keywords: set[str] = set()
    joined = " ".join(text for text in texts if text).lower()
    for token in joined.replace("，", " ").replace("。", " ").replace(",", " ").split():
        stripped = token.strip("：:；;、()（）[]【】")
        if len(stripped) >= 4 and stripped not in {"project", "director"}:
            keywords.add(stripped[:24])
    # Chinese goals are often not whitespace-delimited; keep a few stable domain
    # words when present without attempting full segmentation.
    for token in ("项目", "草案", "验收", "前端", "后端", "任务", "报表", "认证", "工作台"):
        if token in joined:
            keywords.add(token)
    return keywords
