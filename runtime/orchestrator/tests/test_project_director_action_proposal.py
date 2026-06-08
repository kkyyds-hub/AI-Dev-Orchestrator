"""Tests for P7-G1 pure Project Director action proposal domain."""

from __future__ import annotations

import inspect
from uuid import uuid4

import app.domain.project_director_action_proposal as proposal_module
from app.domain.project_director_action_proposal import (
    DirectorActionProposalBuilder,
    DirectorActionProposalStatus,
    DirectorActionProposalType,
    DirectorActionRisk,
    PlanRevisionKind,
    ProposalApprovalRequirement,
)
from app.domain.project_director_user_challenge import (
    InterventionTargetType,
    UserChallengeClassifier,
    UserChallengeType,
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
]


def test_plan_challenge_builds_plan_revision_proposal():
    proposal = _build("我不同意这个计划，草案拆分不合理")

    assert proposal.proposal_type == DirectorActionProposalType.PLAN_REVISION
    assert proposal.risk == DirectorActionRisk.MEDIUM
    assert proposal.plan_revision is not None
    assert proposal.plan_revision.revision_kind == PlanRevisionKind.SUMMARY_UPDATE
    assert proposal.approval_requirement == (
        ProposalApprovalRequirement.USER_CONFIRMATION_REQUIRED
    )
    assert proposal.status == DirectorActionProposalStatus.PENDING_USER_REVIEW


def test_task_scope_challenge_builds_task_revision_proposal():
    proposal = _build("这个任务范围做多了，验收也不对")

    assert proposal.proposal_type == DirectorActionProposalType.TASK_SCOPE_REVISION
    assert proposal.risk == DirectorActionRisk.MEDIUM
    assert proposal.plan_revision is not None
    assert proposal.plan_revision.revision_kind == PlanRevisionKind.TASK_UPDATE
    assert proposal.approval_requirement == (
        ProposalApprovalRequirement.USER_CONFIRMATION_REQUIRED
    )


def test_priority_challenge_builds_priority_revision_proposal():
    proposal = _build("优先级和先后顺序不合理，应该先做登录")

    assert proposal.proposal_type == DirectorActionProposalType.PRIORITY_REVISION
    assert proposal.risk == DirectorActionRisk.MEDIUM
    assert proposal.plan_revision is not None
    assert proposal.plan_revision.revision_kind == PlanRevisionKind.PRIORITY_UPDATE


def test_risk_challenge_builds_risk_revision_proposal():
    proposal = _build("这个风险判断有问题，安全隐患没有写出来")

    assert proposal.proposal_type == DirectorActionProposalType.RISK_REVISION
    assert proposal.risk == DirectorActionRisk.MEDIUM
    assert proposal.plan_revision is not None
    assert proposal.plan_revision.revision_kind == PlanRevisionKind.RISK_UPDATE


def test_dispatch_challenge_builds_dispatch_review_with_high_risk():
    proposal = _build("调度给 Codex 不合理，需要先确认")

    assert proposal.proposal_type == DirectorActionProposalType.DISPATCH_REVIEW
    assert proposal.risk == DirectorActionRisk.HIGH
    assert proposal.plan_revision is None
    assert proposal.approval_requirement == (
        ProposalApprovalRequirement.HUMAN_REVIEW_REQUIRED
    )
    assert proposal.status == DirectorActionProposalStatus.PENDING_USER_REVIEW


def test_governance_challenge_builds_governance_review_with_high_risk():
    proposal = _build("成本、角色、Skill 和权限治理不合理")

    assert proposal.proposal_type == DirectorActionProposalType.GOVERNANCE_REVIEW
    assert proposal.risk == DirectorActionRisk.HIGH
    assert proposal.plan_revision is None
    assert proposal.approval_requirement == (
        ProposalApprovalRequirement.HUMAN_REVIEW_REQUIRED
    )


def test_requirement_change_builds_requirement_change_review_and_human_review():
    proposal = _build("需求变了，要换需求并加入新需求")

    assert proposal.proposal_type == (
        DirectorActionProposalType.REQUIREMENT_CHANGE_REVIEW
    )
    assert proposal.risk == DirectorActionRisk.HIGH
    assert proposal.plan_revision is not None
    assert proposal.plan_revision.revision_kind == PlanRevisionKind.REQUIREMENT_CHANGE
    assert proposal.approval_requirement == (
        ProposalApprovalRequirement.HUMAN_REVIEW_REQUIRED
    )


def test_clarification_request_builds_explain_only():
    proposal = _build("请解释安排依据，有什么原因")

    assert proposal.proposal_type == DirectorActionProposalType.EXPLAIN_ONLY
    assert proposal.risk == DirectorActionRisk.LOW
    assert proposal.plan_revision is None
    assert proposal.approval_requirement == ProposalApprovalRequirement.NONE
    assert proposal.status == DirectorActionProposalStatus.DRAFT


def test_unknown_builds_no_action():
    proposal = _build("今天阳光很好")

    assert proposal.proposal_type == DirectorActionProposalType.NO_ACTION
    assert proposal.risk == DirectorActionRisk.LOW
    assert proposal.plan_revision is None
    assert proposal.approval_requirement == ProposalApprovalRequirement.NONE
    assert proposal.status == DirectorActionProposalStatus.DRAFT


def test_inbox_attention_can_build_explain_only_without_plan_revision():
    proposal = _build("这个提醒和待处理事项不应该放在收件箱")

    assert proposal.proposal_type == DirectorActionProposalType.EXPLAIN_ONLY
    assert proposal.risk == DirectorActionRisk.LOW
    assert proposal.plan_revision is None
    assert proposal.approval_requirement == ProposalApprovalRequirement.NONE


def test_deliverable_challenge_builds_deliverable_review_without_plan_revision():
    proposal = _build("交付物文档和报告产物不合理")

    assert proposal.proposal_type == DirectorActionProposalType.DELIVERABLE_REVIEW
    assert proposal.risk == DirectorActionRisk.MEDIUM
    assert proposal.plan_revision is None
    assert proposal.status == DirectorActionProposalStatus.PENDING_USER_REVIEW


def test_high_risk_never_returns_approved_or_applied():
    contents = [
        "调度给 Codex 不合理",
        "成本、角色和权限治理不合理",
        "需求变了，要换需求",
    ]

    for content in contents:
        proposal = _build(content)
        assert proposal.risk == DirectorActionRisk.HIGH
        assert proposal.status not in {
            DirectorActionProposalStatus.APPROVED,
            DirectorActionProposalStatus.APPLIED,
        }


def test_proposal_with_plan_revision_requires_user_or_human_review():
    contents = [
        "我不同意这个计划",
        "任务范围做少了",
        "优先级不合理",
        "这个风险判断有问题",
        "需求变了",
    ]

    for content in contents:
        proposal = _build(content)
        assert proposal.plan_revision is not None
        assert proposal.approval_requirement in {
            ProposalApprovalRequirement.USER_CONFIRMATION_REQUIRED,
            ProposalApprovalRequirement.HUMAN_REVIEW_REQUIRED,
        }
        assert proposal.status == DirectorActionProposalStatus.PENDING_USER_REVIEW


def test_safe_next_actions_do_not_contain_execution_words():
    for content in _all_sample_contents():
        proposal = _build(content)
        safe_actions_text = " ".join(proposal.safe_next_actions)
        for action_text in EXECUTION_ACTION_TEXTS:
            assert action_text not in safe_actions_text


def test_forbidden_actions_include_all_required_boundaries():
    proposal = _build("我不同意这个计划")

    assert set(FORBIDDEN_ACTIONS).issubset(set(proposal.forbidden_actions))


def test_user_visible_fields_do_not_contain_technical_words():
    for content in _all_sample_contents():
        proposal = _build(content)
        visible_text = _visible_text(proposal)
        for term in TECHNICAL_USER_VISIBLE_TERMS:
            assert term not in visible_text


def test_source_fields_may_keep_internal_values_but_visible_text_does_not():
    proposal = _build("我不同意这个计划")

    assert proposal.source_challenge_type == UserChallengeType.PLAN_CHALLENGE.value
    assert proposal.source_challenge_severity == "medium"
    assert "plan_challenge" not in proposal.title
    assert "plan_challenge" not in proposal.summary
    assert "plan_challenge" not in proposal.reason


def test_builder_preserves_ids_without_side_effects():
    target_id = uuid4()
    conversation_id = uuid4()
    project_id = uuid4()
    seed = UserChallengeClassifier.classify(
        user_content="这个任务范围做多了",
        target_type=InterventionTargetType.TASK,
        target_id=target_id,
        conversation_id=conversation_id,
        project_id=project_id,
    )

    proposal = DirectorActionProposalBuilder.build_from_challenge(seed)

    assert proposal.target_id == target_id
    assert proposal.conversation_id == conversation_id
    assert proposal.project_id == project_id


def test_builder_has_no_service_repository_or_database_dependency():
    source = inspect.getsource(proposal_module)

    assert "app.repositories" not in source
    assert "app.services" not in source
    assert "sqlalchemy" not in source
    assert "Session" not in source
    assert "ProjectDirectorMessageService" not in source


def _build(content: str):
    seed = UserChallengeClassifier.classify(user_content=content)
    return DirectorActionProposalBuilder.build_from_challenge(seed)


def _all_sample_contents() -> list[str]:
    return [
        "我不同意这个计划，草案拆分不合理",
        "这个任务范围做多了，验收也不对",
        "优先级和先后顺序不合理，应该先做登录",
        "这个风险判断有问题，安全隐患没有写出来",
        "调度给 Codex 不合理，需要先确认",
        "这个提醒和待处理事项不应该放在收件箱",
        "交付物文档和报告产物不合理",
        "成本、角色、Skill 和权限治理不合理",
        "需求变了，要换需求并加入新需求",
        "请解释安排依据，有什么原因",
        "今天阳光很好",
    ]


def _visible_text(proposal) -> str:
    text_parts = [
        proposal.title,
        proposal.summary,
        proposal.reason,
        *proposal.safe_next_actions,
        *proposal.forbidden_actions,
    ]
    if proposal.plan_revision is not None:
        text_parts.extend(
            [
                proposal.plan_revision.title,
                proposal.plan_revision.summary,
                proposal.plan_revision.reason,
                *proposal.plan_revision.affected_sections,
                *proposal.plan_revision.proposed_changes,
            ]
        )
    return " ".join(text_parts)
