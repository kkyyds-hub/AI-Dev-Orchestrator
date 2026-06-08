"""Tests for P7-F1 pure Project Director user challenge domain."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.project_director_conversation_router import ConversationIntent
from app.domain.project_director_user_challenge import (
    InterventionTargetType,
    UserChallengeClassifier,
    UserChallengeSeverity,
    UserChallengeStatus,
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
    "Codex",
    "Claude",
    "DeepSeek",
    "Skill",
)

FORBIDDEN_ACTIONS = [
    "不会自动修改草案",
    "不会自动创建任务",
    "不会自动执行任务",
    "不会修改仓库",
    "不会启动外部工具",
]

EXECUTION_ACTION_TEXTS = (
    "启动执行",
    "创建任务",
    "推送",
    "合并",
    "提交代码",
    "重试",
)


@pytest.mark.parametrize(
    ("content", "expected_type", "expected_severity"),
    [
        ("我不同意这个计划，草案拆分不合理", UserChallengeType.PLAN_CHALLENGE, UserChallengeSeverity.MEDIUM),
        ("这个任务范围做多了，验收也不对", UserChallengeType.TASK_SCOPE_CHALLENGE, UserChallengeSeverity.MEDIUM),
        ("优先级和先后顺序不合理，应该先做登录", UserChallengeType.PRIORITY_CHALLENGE, UserChallengeSeverity.LOW),
        ("这个风险判断有问题，安全隐患没有写出来", UserChallengeType.RISK_CHALLENGE, UserChallengeSeverity.MEDIUM),
        ("这个提醒和待处理事项不应该放在收件箱", UserChallengeType.INBOX_ATTENTION_CHALLENGE, UserChallengeSeverity.LOW),
        ("交付物文档和报告产物不合理", UserChallengeType.DELIVERABLE_CHALLENGE, UserChallengeSeverity.LOW),
        ("成本、角色、Skill 和权限治理不合理", UserChallengeType.GOVERNANCE_CHALLENGE, UserChallengeSeverity.HIGH),
        ("需求变了，要换需求并加入新需求", UserChallengeType.REQUIREMENT_CHANGE, UserChallengeSeverity.HIGH),
        ("请解释安排依据，有什么原因", UserChallengeType.CLARIFICATION_REQUEST, UserChallengeSeverity.LOW),
    ],
)

def test_classifier_covers_core_challenge_types(content, expected_type, expected_severity):
    seed = UserChallengeClassifier.classify(user_content=content)

    assert seed.challenge_type == expected_type
    assert seed.severity == expected_severity
    assert seed.target_type == InterventionTargetType.UNKNOWN
    assert seed.requires_response is True
    assert seed.forbidden_actions == FORBIDDEN_ACTIONS


def test_dispatch_challenge_translates_external_tool_names_in_visible_text():
    seed = UserChallengeClassifier.classify(
        user_content="调度给 Codex / Claude / DeepSeek 不合理"
    )

    assert seed.challenge_type == UserChallengeType.DISPATCH_CHALLENGE
    assert seed.severity == UserChallengeSeverity.HIGH
    assert seed.requires_human_confirmation is True
    visible_text = _visible_text(seed)
    assert "外部工具" in visible_text
    assert "Codex" not in visible_text
    assert "Claude" not in visible_text
    assert "DeepSeek" not in visible_text


def test_blocking_severity_requires_review_and_human_confirmation():
    seed = UserChallengeClassifier.classify(
        user_content="这个计划不合理，已经阻塞，不能继续，必须先解决"
    )

    assert seed.challenge_type == UserChallengeType.PLAN_CHALLENGE
    assert seed.severity == UserChallengeSeverity.BLOCKING
    assert seed.status == UserChallengeStatus.NEEDS_REVIEW
    assert seed.requires_human_confirmation is True


def test_conflict_priority_prefers_requirement_change_over_dispatch():
    seed = UserChallengeClassifier.classify(
        user_content="需求变了，而且调度给 Codex 不合理"
    )

    assert seed.challenge_type == UserChallengeType.REQUIREMENT_CHANGE
    assert seed.severity == UserChallengeSeverity.HIGH
    assert seed.requires_plan_revision is True
    assert seed.requires_human_confirmation is True


def test_flags_for_plan_related_challenges_and_unknown():
    plan_seed = UserChallengeClassifier.classify(user_content="任务范围做少了")
    unknown_seed = UserChallengeClassifier.classify(user_content="今天阳光很好")

    assert plan_seed.requires_plan_revision is True
    assert plan_seed.requires_response is True
    assert plan_seed.status == UserChallengeStatus.NEEDS_REVIEW
    assert unknown_seed.challenge_type == UserChallengeType.UNKNOWN
    assert unknown_seed.requires_response is False
    assert unknown_seed.requires_plan_revision is False
    assert unknown_seed.requires_human_confirmation is False
    assert unknown_seed.status == UserChallengeStatus.DRAFT


def test_target_ids_are_preserved_without_side_effects():
    target_id = uuid4()
    conversation_id = uuid4()
    project_id = uuid4()

    seed = UserChallengeClassifier.classify(
        user_content="这个交付物不对",
        target_type=InterventionTargetType.DELIVERABLE,
        target_id=target_id,
        conversation_id=conversation_id,
        project_id=project_id,
    )

    assert seed.target_type == InterventionTargetType.DELIVERABLE
    assert seed.target_id == target_id
    assert seed.conversation_id == conversation_id
    assert seed.project_id == project_id


def test_forbidden_actions_are_always_present():
    seed = UserChallengeClassifier.classify(user_content="请解释原因")

    assert set(FORBIDDEN_ACTIONS).issubset(set(seed.forbidden_actions))


def test_safe_next_actions_do_not_include_execution_actions():
    contents = [
        "我不同意这个计划",
        "任务范围做多了",
        "调度给 Codex 不合理",
        "需求变了",
        "请解释原因",
        "今天阳光很好",
    ]

    for content in contents:
        seed = UserChallengeClassifier.classify(user_content=content)
        safe_actions_text = " ".join(seed.safe_next_actions)
        for action_text in EXECUTION_ACTION_TEXTS:
            assert action_text not in safe_actions_text


def test_user_visible_fields_do_not_include_technical_terms():
    seed = UserChallengeClassifier.classify(
        user_content=(
            "provider worker executor runtime API payload Git dispatch_question "
            "session_id project_id synthetic read model intent source_detail "
            "risk_level suggested_actions Codex Claude DeepSeek Skill 调度不合理"
        )
    )

    visible_text = _visible_text(seed)
    for term in TECHNICAL_USER_VISIBLE_TERMS:
        assert term not in visible_text


@pytest.mark.parametrize(
    ("route_intent", "content", "expected_type"),
    [
        (ConversationIntent.CHALLENGE_PLAN, "请解释安排依据", UserChallengeType.CLARIFICATION_REQUEST),
        (ConversationIntent.CHALLENGE_PLAN, "这个不合理", UserChallengeType.PLAN_CHALLENGE),
        (ConversationIntent.REQUEST_PLAN_CHANGE, "请调整一下", UserChallengeType.PLAN_CHALLENGE),
        (ConversationIntent.REQUEST_PLAN_CHANGE, "新需求来了", UserChallengeType.REQUIREMENT_CHANGE),
        (ConversationIntent.REQUEST_ACTION, "请直接执行", UserChallengeType.CLARIFICATION_REQUEST),
        (ConversationIntent.REQUEST_ACTION, "请调度给 Codex", UserChallengeType.DISPATCH_CHALLENGE),
    ],
)

def test_route_intent_compatibility(route_intent, content, expected_type):
    seed = UserChallengeClassifier.classify(
        user_content=content,
        route_intent=route_intent,
    )

    assert seed.challenge_type == expected_type
    assert seed.requires_plan_revision is (expected_type in {
        UserChallengeType.REQUIREMENT_CHANGE,
        UserChallengeType.PLAN_CHALLENGE,
        UserChallengeType.TASK_SCOPE_CHALLENGE,
        UserChallengeType.PRIORITY_CHALLENGE,
    })
    if route_intent == ConversationIntent.REQUEST_ACTION:
        assert set(FORBIDDEN_ACTIONS).issubset(set(seed.forbidden_actions))


def _visible_text(seed) -> str:
    return " ".join(
        [
            seed.title,
            seed.summary,
            seed.extracted_reason,
            *seed.safe_next_actions,
            *seed.forbidden_actions,
        ]
    )
