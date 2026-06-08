"""Tests for P7-E2 pure Project Director conversation router."""

from __future__ import annotations

import pytest

from app.domain.project_director_conversation_router import (
    ConversationIntent,
    ConversationRouter,
    SafetyRiskLevel,
)


TECHNICAL_TERMS = (
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
)

EXECUTION_ACTION_TEXTS = (
    "启动执行",
    "提交代码",
    "推送",
    "合并",
    "派发 Codex",
)


def test_empty_input_routes_to_unknown_without_provider_call():
    decision = ConversationRouter.classify("   ")

    assert decision.intent == ConversationIntent.UNKNOWN
    assert decision.confidence < 0.2
    assert decision.should_call_provider is False
    assert decision.should_persist_user_message is True
    assert decision.should_create_conversation is False
    assert decision.should_create_task is False
    assert decision.should_start_worker is False
    assert decision.should_launch_executor is False
    assert decision.should_modify_repository is False


@pytest.mark.parametrize(
    ("content", "expected_intent"),
    [
        ("现在进度做到哪了？", ConversationIntent.ASK_CURRENT_CONTEXT),
        ("有哪些提醒和待处理？", ConversationIntent.ASK_INBOX),
        ("我想看历史讨论和已有会话", ConversationIntent.ASK_CONVERSATION_LIST),
        ("任务运行失败了吗？有没有阻塞？", ConversationIntent.ASK_TASK_OR_RUN),
        ("我不同意，这样不合理", ConversationIntent.CHALLENGE_PLAN),
        ("请修改草案，调整计划", ConversationIntent.REQUEST_PLAN_CHANGE),
    ],
)
def test_router_classifies_supported_non_execution_intents(content, expected_intent):
    decision = ConversationRouter.classify(content)

    assert decision.intent == expected_intent
    assert decision.should_call_provider is True
    assert decision.should_create_task is False
    assert decision.should_start_worker is False
    assert decision.should_launch_executor is False
    assert decision.should_modify_repository is False


def test_ask_current_context_scope_includes_current_state_sources():
    decision = ConversationRouter.classify("请总结当前状态和项目情况")

    assert decision.intent == ConversationIntent.ASK_CURRENT_CONTEXT
    assert decision.context_scope.include_session is True
    assert decision.context_scope.include_recent_messages is True
    assert decision.context_scope.include_latest_plan is True
    assert decision.context_scope.include_task_creation is True
    assert decision.context_scope.include_project_snapshot is True
    assert decision.context_scope.include_task_snapshot is True
    assert decision.context_scope.include_inbox is True


def test_request_action_is_high_risk_requires_confirmation_and_no_execution_flags():
    decision = ConversationRouter.classify("请开始跑并提交推送")

    assert decision.intent == ConversationIntent.REQUEST_ACTION
    assert decision.safety_policy.risk_level == SafetyRiskLevel.HIGH
    assert decision.safety_policy.requires_confirmation is True
    assert decision.safety_policy.user_visible_warning == (
        "这听起来像要执行操作。系统不会自动执行任务，也不会修改仓库。"
    )
    assert decision.should_call_provider is False
    assert decision.should_create_conversation is False
    assert decision.should_create_task is False
    assert decision.should_start_worker is False
    assert decision.should_launch_executor is False
    assert decision.should_modify_repository is False


def test_restart_or_new_goal_requires_confirmation_without_creating_conversation():
    decision = ConversationRouter.classify("换一个需求，新建主管会话")

    assert decision.intent == ConversationIntent.RESTART_OR_NEW_GOAL
    assert decision.safety_policy.risk_level == SafetyRiskLevel.MEDIUM
    assert decision.safety_policy.requires_confirmation is True
    assert decision.should_call_provider is False
    assert decision.should_create_conversation is False
    assert decision.should_create_task is False
    assert decision.should_start_worker is False
    assert decision.should_launch_executor is False
    assert decision.should_modify_repository is False


def test_conflict_priority_prefers_request_action_over_plan_change():
    decision = ConversationRouter.classify("请修改计划并启动执行")

    assert decision.intent == ConversationIntent.REQUEST_ACTION
    assert decision.safety_policy.risk_level == SafetyRiskLevel.HIGH
    assert decision.safety_policy.requires_confirmation is True


def test_user_visible_safety_text_does_not_include_technical_terms():
    contents = [
        "",
        "项目情况如何？",
        "请修改草案",
        "我不同意这个计划",
        "请执行并推送",
        "重新开始一个新目标",
    ]

    for content in contents:
        decision = ConversationRouter.classify(content)
        user_visible_text = " ".join(
            [
                decision.safety_policy.user_visible_warning,
                *decision.safety_policy.forbidden_actions,
            ]
        )
        for term in TECHNICAL_TERMS:
            assert term not in user_visible_text


def test_forbidden_actions_are_always_simple_chinese_boundary_items():
    decision = ConversationRouter.classify("请创建任务并执行")

    assert decision.safety_policy.forbidden_actions == [
        "不会自动执行任务",
        "不会自动创建任务",
        "不会修改仓库",
        "不会启动外部工具",
        "不会直接应用草案修改",
    ]


def test_safe_next_actions_do_not_include_execution_actions():
    contents = [
        "看一下计划",
        "请修改草案",
        "有哪些提醒",
        "任务是否阻塞",
        "下一步做什么",
        "请启动执行",
    ]

    for content in contents:
        decision = ConversationRouter.classify(content)
        safe_actions_text = " ".join(decision.safety_policy.safe_next_actions)
        for action_text in EXECUTION_ACTION_TEXTS:
            assert action_text not in safe_actions_text
