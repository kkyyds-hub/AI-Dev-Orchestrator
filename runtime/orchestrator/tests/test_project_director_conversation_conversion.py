"""Tests for P7-H1 pure Project Director conversation conversion domain."""

from __future__ import annotations

import inspect
from uuid import uuid4

import app.domain.project_director_conversation_conversion as conversion_module
from app.domain.project_director_action_proposal import (
    DirectorActionProposalBuilder,
    DirectorActionProposalType,
    ProposalApprovalRequirement,
)
from app.domain.project_director_conversation_conversion import (
    ConversationConversionBuilder,
    ConversationConversionStatus,
    ConversationConversionTarget,
)
from app.domain.project_director_user_challenge import (
    InterventionTargetType,
    UserChallengeClassifier,
)


TECHNICAL_USER_VISIBLE_TERMS = (
    "provider",
    "worker",
    "executor",
    "runtime",
    "API",
    "payload",
    "Git",
    "dispatch_question",
    "session_id",
    "project_id",
    "synthetic",
    "read model",
    "intent",
    "source_detail",
    "risk_level",
    "suggested_actions",
    "challenge_type",
    "challenge_severity",
    "challenge_status",
    "proposal_type",
    "proposal_status",
    "approval_requirement",
    "plan_revision",
    "Codex",
    "Claude",
    "DeepSeek",
    "Skill",
)

EXECUTION_ACTION_TEXTS = (
    "启动执行",
    "创建任务",
    "推送",
    "合并",
    "提交代码",
    "重试",
    "应用修改",
    "执行审批",
)

FORBIDDEN_ACTIONS = [
    "不会自动修改草案",
    "不会自动创建任务",
    "不会自动执行任务",
    "不会修改仓库",
    "不会启动外部工具",
    "不会自动应用建议",
    "不会自动执行审批",
]


def test_plan_revision_proposal_builds_plan_revision_draft_with_plan_draft():
    draft = _convert("我不同意这个计划，草案拆分不合理")

    assert draft.target == ConversationConversionTarget.PLAN_REVISION_DRAFT
    assert draft.plan_draft is not None
    assert draft.task_draft is None
    assert draft.status == ConversationConversionStatus.NEEDS_USER_REVIEW


def test_task_scope_revision_builds_task_scope_update_draft_with_task_draft():
    draft = _convert("这个任务范围做多了，验收也不对")

    assert draft.target == ConversationConversionTarget.TASK_SCOPE_UPDATE_DRAFT
    assert draft.task_draft is not None
    assert draft.plan_draft is None
    assert draft.task_draft.requires_user_confirmation is True


def test_priority_revision_builds_priority_update_draft():
    draft = _convert("优先级和先后顺序不合理，应该先做登录")

    assert draft.target == ConversationConversionTarget.PRIORITY_UPDATE_DRAFT
    assert draft.task_draft is not None
    assert draft.task_draft.title == "调整任务优先级"


def test_risk_revision_builds_risk_update_draft():
    draft = _convert("这个风险判断有问题，安全隐患没有写出来")

    assert draft.target == ConversationConversionTarget.RISK_UPDATE_DRAFT
    assert draft.plan_draft is not None
    assert draft.task_draft is None


def test_requirement_change_review_builds_plan_revision_draft_and_needs_review():
    draft = _convert("需求变了，要换需求并加入新需求")

    assert draft.target == ConversationConversionTarget.PLAN_REVISION_DRAFT
    assert draft.plan_draft is not None
    assert draft.status == ConversationConversionStatus.NEEDS_USER_REVIEW
    assert (
        draft.source_approval_requirement
        == ProposalApprovalRequirement.HUMAN_REVIEW_REQUIRED.value
    )


def test_dispatch_review_builds_explanation_only_without_task_draft():
    draft = _convert("调度给 Codex 不合理，需要先确认")

    assert draft.target == ConversationConversionTarget.EXPLANATION_ONLY
    assert draft.status == ConversationConversionStatus.DRAFT
    assert draft.task_draft is None
    assert draft.plan_draft is None
    assert "外部工具" in draft.reason


def test_governance_review_builds_explanation_only():
    draft = _convert("成本、角色、Skill 和权限治理不合理")

    assert draft.target == ConversationConversionTarget.EXPLANATION_ONLY
    assert draft.status == ConversationConversionStatus.DRAFT
    assert draft.task_draft is None
    assert draft.plan_draft is None
    assert "不会修改配置" in draft.reason


def test_no_action_builds_no_conversion():
    draft = _convert("今天阳光很好")

    assert draft.target == ConversationConversionTarget.NO_CONVERSION
    assert draft.status == ConversationConversionStatus.DRAFT
    assert draft.task_draft is None
    assert draft.plan_draft is None


def test_high_risk_or_approval_requirement_creates_needs_user_review_for_drafts():
    contents = [
        "我不同意这个计划，草案拆分不合理",
        "需求变了，要换需求并加入新需求",
    ]

    for content in contents:
        draft = _convert(content)
        assert draft.status == ConversationConversionStatus.NEEDS_USER_REVIEW


def test_conversion_never_returns_applied_created_or_executed_status():
    forbidden_status_values = {"applied", "created", "executed"}

    for content in _all_sample_contents():
        draft = _convert(content)
        assert draft.status.value not in forbidden_status_values
    assert not hasattr(ConversationConversionStatus, "APPLIED")
    assert not hasattr(ConversationConversionStatus, "CREATED")
    assert not hasattr(ConversationConversionStatus, "EXECUTED")


def test_safe_next_actions_do_not_contain_execution_words():
    for content in _all_sample_contents():
        draft = _convert(content)
        safe_actions_text = " ".join(draft.safe_next_actions)
        for action_text in EXECUTION_ACTION_TEXTS:
            assert action_text not in safe_actions_text


def test_forbidden_actions_include_all_required_boundaries():
    draft = _convert("我不同意这个计划，草案拆分不合理")

    assert set(FORBIDDEN_ACTIONS).issubset(set(draft.forbidden_actions))


def test_user_visible_fields_do_not_contain_technical_words():
    for content in _all_sample_contents():
        draft = _convert(content)
        visible_text = _visible_text(draft)
        for term in TECHNICAL_USER_VISIBLE_TERMS:
            assert term not in visible_text


def test_source_trace_fields_may_keep_internal_values_but_visible_text_does_not():
    draft = _convert("我不同意这个计划，草案拆分不合理")

    assert draft.source_proposal_type == DirectorActionProposalType.PLAN_REVISION.value
    assert (
        draft.source_approval_requirement
        == ProposalApprovalRequirement.USER_CONFIRMATION_REQUIRED.value
    )
    visible_text = _visible_text(draft)
    assert "plan_revision" not in visible_text
    assert "approval_requirement" not in visible_text


def test_builder_preserves_ids_without_side_effects():
    target_id = uuid4()
    conversation_id = uuid4()
    project_id = uuid4()
    proposal = _proposal(
        "这个任务范围做多了，验收也不对",
        target_type=InterventionTargetType.TASK,
        target_id=target_id,
        conversation_id=conversation_id,
        project_id=project_id,
    )

    draft = ConversationConversionBuilder.build_from_proposal(proposal)

    assert draft.target_id == target_id
    assert draft.conversation_id == conversation_id
    assert draft.project_id == project_id


def test_builder_has_no_service_repository_database_or_provider_dependency():
    source = inspect.getsource(conversion_module)

    assert "app.repositories" not in source
    assert "app.services" not in source
    assert "sqlalchemy" not in source
    assert "Session" not in source
    assert "ProjectDirectorMessageService" not in source
    assert "requestJson" not in source


def _proposal(content: str, **kwargs):
    seed = UserChallengeClassifier.classify(user_content=content, **kwargs)
    return DirectorActionProposalBuilder.build_from_challenge(seed)


def _convert(content: str):
    return ConversationConversionBuilder.build_from_proposal(_proposal(content))


def _all_sample_contents() -> list[str]:
    return [
        "我不同意这个计划，草案拆分不合理",
        "这个任务范围做多了，验收也不对",
        "优先级和先后顺序不合理，应该先做登录",
        "这个风险判断有问题，安全隐患没有写出来",
        "调度给 Codex 不合理，需要先确认",
        "交付物文档和报告产物不合理",
        "成本、角色、Skill 和权限治理不合理",
        "需求变了，要换需求并加入新需求",
        "请解释安排依据，有什么原因",
        "今天阳光很好",
    ]


def _visible_text(draft) -> str:
    text_parts = [
        draft.title,
        draft.summary,
        draft.reason,
        *draft.safe_next_actions,
        *draft.forbidden_actions,
    ]
    if draft.plan_draft is not None:
        text_parts.extend(
            [
                draft.plan_draft.title,
                draft.plan_draft.summary,
                draft.plan_draft.reason,
                *draft.plan_draft.affected_sections,
                *draft.plan_draft.proposed_changes,
            ]
        )
    if draft.task_draft is not None:
        text_parts.extend(
            [
                draft.task_draft.title,
                draft.task_draft.summary,
                draft.task_draft.input_summary,
                *draft.task_draft.acceptance_criteria,
                draft.task_draft.suggested_priority,
                draft.task_draft.blocked_reason or "",
            ]
        )
    return " ".join(text_parts)
