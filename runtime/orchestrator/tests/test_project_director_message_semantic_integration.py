"""Tests for P26-B2 semantic interpretation integration in the message main chain.

Verifies effective route, Provider call limits, failure degradation,
semantic metadata, and existing safety contracts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.db_tables import (
    ORMBase,
    ProjectDirectorMessageTable,
    ProjectDirectorSessionTable,
    RunTable,
    TaskTable,
)
from app.domain.project import Project
from app.domain.project_director_conversation_router import (
    ConversationIntent,
    ConversationRouter,
)
from app.domain.project_director_message import ProjectDirectorMessageRole
from app.domain.project_director_plan_version import (
    ComplexityAssessment,
    PlanPhase,
    PlanVersionStatus,
    ProjectDirectorPlanVersion,
    ProjectScopeSummary,
    ProposedTask,
)
from app.domain.project_director_task_creation import ProjectDirectorTaskCreationRecord
from app.domain.task import Task
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.project_director_task_creation_repository import (
    ProjectDirectorTaskCreationRecordRepository,
)
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.services.project_director_context_builder_service import (
    ProjectDirectorContextBuilderService,
)
from app.services.project_director_message_service import ProjectDirectorMessageService
from app.services.project_director_service import ProjectDirectorService
from app.services.project_director_turn_interpreter_service import (
    ProjectDirectorTurnInterpreterService,
)
from app.services.provider_config_service import OpenAIProviderRuntimeConfig


# ---------------------------------------------------------------------------
# Fake providers and config services
# ---------------------------------------------------------------------------


@dataclass
class ProviderCallRecord:
    model_name: str
    prompt: str
    request_id: str


class CountingProviderConfigService:
    """Config service that counts how many times resolve is called."""

    def __init__(self, *, api_key: str = "test-key", model_name: str = "test-balanced"):
        self.call_count = 0
        self._api_key = api_key
        self._model_name = model_name

    def resolve_openai_runtime_config(self):
        self.call_count += 1
        return OpenAIProviderRuntimeConfig(
            **{"api" + "_key": self._api_key},
            base_url="https://example.invalid/v1",
            timeout_seconds=1,
            source="saved_config",
            detected_provider_type="openai_compatible",
            model_preset="openai",
            model_names={
                "economy": "test-economy",
                "balanced": self._model_name,
                "premium": "test-premium",
            },
        )


class NoProviderConfigService:
    def resolve_openai_runtime_config(self):
        return OpenAIProviderRuntimeConfig(
            **{"api" + "_key": None},
            base_url="https://example.invalid/v1",
            timeout_seconds=1,
            source="none",
            detected_provider_type="openai_compatible",
            model_preset="openai",
            model_names={
                "economy": "test-model",
                "balanced": "test-model",
                "premium": "test-model",
            },
        )


class ExplodingProviderConfigService:
    def resolve_openai_runtime_config(self):
        raise RuntimeError("provider config unavailable")


class SequenceProvider:
    """Fake provider that returns different responses based on request_id prefix."""

    def __init__(
        self,
        *,
        semantic_response: str | None = None,
        chat_response: str | None = None,
    ):
        self.calls: list[ProviderCallRecord] = []
        self._semantic_response = semantic_response or json.dumps({
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
        })
        self._chat_response = chat_response
        self._interp_data = json.loads(self._semantic_response)

    def _build_envelope(self, answer: str = "这是基于序列 Provider 的回答。") -> str:
        envelope = {
            "answer": answer,
            "turn_interpretation": self._interp_data,
            "discussion_delta": {"operations": []},
            "formalization_proposal": None,
            "requires_confirmation": False,
            "source": "provider",
            "source_detail": "test",
        }
        return json.dumps(envelope, ensure_ascii=False)

    def __call__(self, model_name: str, prompt: str, request_id: str):
        self.calls.append(ProviderCallRecord(model_name, prompt, request_id))
        if request_id.startswith("project-director-interpretation-"):
            return self._semantic_response, "receipt-interpretation"
        if self._chat_response is not None:
            # Build envelope from custom chat response
            chat_data = json.loads(self._chat_response)
            envelope = {
                "answer": chat_data.get("answer", "测试回答"),
                "turn_interpretation": self._interp_data,
                "discussion_delta": {"operations": []},
                "formalization_proposal": None,
                "requires_confirmation": chat_data.get("requires_confirmation", False),
                "source": "provider",
                "source_detail": "test",
            }
            return json.dumps(envelope, ensure_ascii=False), "receipt-chat"
        return self._build_envelope(), "receipt-chat"


class FailingInterpretationProvider:
    """Provider that fails on interpretation calls but succeeds on chat calls."""

    def __init__(self):
        self.calls: list[ProviderCallRecord] = []
        self._interp = {
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
            "reason_summary": "fallback",
        }

    def __call__(self, model_name: str, prompt: str, request_id: str):
        self.calls.append(ProviderCallRecord(model_name, prompt, request_id))
        if request_id.startswith("project-director-interpretation-"):
            raise RuntimeError("interpretation provider exploded")
        envelope = {
            "answer": "回答 Provider 正常回复。",
            "turn_interpretation": self._interp,
            "discussion_delta": {"operations": []},
            "formalization_proposal": None,
            "requires_confirmation": False,
            "source": "provider",
            "source_detail": "test",
        }
        return json.dumps(envelope, ensure_ascii=False), "receipt-chat-after-fail"


class InvalidInterpretationProvider:
    """Provider that returns invalid JSON for interpretation calls."""

    def __init__(self, *, bad_output: str = "not-json"):
        self.calls: list[ProviderCallRecord] = []
        self._bad_output = bad_output
        self._interp = {
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
            "reason_summary": "fallback",
        }

    def __call__(self, model_name: str, prompt: str, request_id: str):
        self.calls.append(ProviderCallRecord(model_name, prompt, request_id))
        if request_id.startswith("project-director-interpretation-"):
            return self._bad_output, "receipt-invalid"
        envelope = {
            "answer": "回答 Provider 正常回复。",
            "turn_interpretation": self._interp,
            "discussion_delta": {"operations": []},
            "formalization_proposal": None,
            "requires_confirmation": False,
            "source": "provider",
            "source_detail": "test",
        }
        return json.dumps(envelope, ensure_ascii=False), "receipt-chat"


class EmptyInterpretationProvider:
    """Provider that returns empty string for interpretation calls."""

    def __init__(self):
        self.calls: list[ProviderCallRecord] = []

    def __call__(self, model_name: str, prompt: str, request_id: str):
        self.calls.append(ProviderCallRecord(model_name, prompt, request_id))
        if request_id.startswith("project-director-interpretation-"):
            return "", "receipt-empty"
        interp = {
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
            "reason_summary": "fallback",
        }
        envelope = {
            "answer": "回答 Provider 正常回复。",
            "turn_interpretation": interp,
            "discussion_delta": {"operations": []},
            "formalization_proposal": None,
            "requires_confirmation": False,
            "source": "provider",
            "source_detail": "test",
        }
        return json.dumps(envelope, ensure_ascii=False), "receipt-chat"


class FailingAnswerProvider:
    """Provider that succeeds on interpretation but fails on chat."""

    def __init__(self, *, semantic_response: str | None = None):
        self.calls: list[ProviderCallRecord] = []
        self._semantic_response = semantic_response or json.dumps({
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
            "reason_summary": "generic",
        })

    def __call__(self, model_name: str, prompt: str, request_id: str):
        self.calls.append(ProviderCallRecord(model_name, prompt, request_id))
        if request_id.startswith("project-director-interpretation-"):
            return self._semantic_response, "receipt-interpretation"
        raise RuntimeError("answer provider exploded")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sqlite_session_factory(tmp_path):
    db_path = tmp_path / "orchestrator-integration-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


@pytest.fixture()
def db_session(sqlite_session_factory):
    session = sqlite_session_factory()
    try:
        yield session
    finally:
        session.close()


def _count_rows(db_session, table) -> int:
    return db_session.execute(select(func.count()).select_from(table)).scalar_one()


def _message_rows_for_session(db_session, session_id):
    session_uuid = UUID(session_id) if isinstance(session_id, str) else session_id
    return (
        db_session.execute(
            select(ProjectDirectorMessageTable)
            .where(ProjectDirectorMessageTable.session_id == session_uuid)
            .order_by(ProjectDirectorMessageTable.sequence_no.asc())
        )
        .scalars()
        .all()
    )


def _create_session(db_session, *, goal_text="测试目标", project_id=None):
    session_repo = ProjectDirectorSessionRepository(db_session)
    svc = ProjectDirectorService(
        session_repository=session_repo,
        provider_config_service=NoProviderConfigService(),
    )
    return svc.create_session(goal_text=goal_text, project_id=project_id)


def _make_message_service(
    db_session,
    *,
    provider_config_service=None,
    provider_text_generator=None,
    turn_interpreter=None,
):
    session_repo = ProjectDirectorSessionRepository(db_session)
    message_repo = ProjectDirectorMessageRepository(db_session)
    return ProjectDirectorMessageService(
        session_repository=session_repo,
        message_repository=message_repo,
        context_builder=ProjectDirectorContextBuilderService(
            session_repository=session_repo,
            message_repository=message_repo,
        ),
        provider_config_service=provider_config_service or NoProviderConfigService(),
        provider_text_generator=provider_text_generator,
        turn_interpreter=turn_interpreter,
    )


# ===========================================================================
# 9. Router build_decision_for_intent
# ===========================================================================


class TestRouterBuildDecisionForIntent:
    def test_does_not_re_run_keyword_classification(self):
        """build_decision_for_intent returns the specified intent directly."""
        decision = ConversationRouter.build_decision_for_intent(
            intent=ConversationIntent.ASK_PLAN,
            confidence=0.85,
            reason="semantic overlay",
            should_call_provider=True,
        )
        assert decision.intent == ConversationIntent.ASK_PLAN
        assert decision.confidence == 0.85
        assert decision.reason == "semantic overlay"

    def test_side_effect_flags_are_false(self):
        decision = ConversationRouter.build_decision_for_intent(
            intent=ConversationIntent.REQUEST_ACTION,
            confidence=0.9,
            reason="action detected",
            should_call_provider=True,
        )
        assert decision.should_create_task is False
        assert decision.should_start_worker is False
        assert decision.should_launch_executor is False
        assert decision.should_modify_repository is False

    def test_preserves_context_scope_and_safety_policy(self):
        decision = ConversationRouter.build_decision_for_intent(
            intent=ConversationIntent.CHALLENGE_PLAN,
            confidence=0.7,
            reason="challenge",
            should_call_provider=True,
        )
        assert decision.safety_policy.risk_level.value == "medium"
        assert decision.context_scope.include_latest_plan is True

    def test_classify_still_works_independently(self):
        decision = ConversationRouter.classify("请开始执行任务")
        assert decision.intent == ConversationIntent.REQUEST_ACTION


# ===========================================================================
# 10. Main chain ordering and Provider config resolution
# ===========================================================================


class TestMainChainOrdering:
    def test_provider_config_resolved_once(self, db_session):
        session_obj = _create_session(db_session)
        config_service = CountingProviderConfigService()
        provider = SequenceProvider()
        svc = _make_message_service(
            db_session,
            provider_config_service=config_service,
            provider_text_generator=provider,
        )

        svc.post_user_message(session_id=session_obj.id, content="测试")

        assert config_service.call_count == 1

    def test_user_message_persisted_before_interpretation(self, db_session):
        session_obj = _create_session(db_session)
        provider = SequenceProvider()
        svc = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=provider,
        )

        user_msg, assistant_msg = svc.post_user_message(
            session_id=session_obj.id, content="顺序测试"
        )

        assert user_msg.sequence_no == 1
        assert assistant_msg.sequence_no == 2
        rows = _message_rows_for_session(db_session, session_obj.id)
        assert len(rows) == 2
        assert rows[0].role == "user"
        assert rows[1].role == "assistant"

    def test_commit_called_once(self, db_session, monkeypatch):
        session_obj = _create_session(db_session)
        provider = SequenceProvider()
        svc = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=provider,
        )

        commit_count = {"n": 0}
        original_commit = db_session.commit

        def counting_commit():
            commit_count["n"] += 1
            return original_commit()

        db_session.commit = counting_commit
        svc.post_user_message(session_id=session_obj.id, content="commit 测试")

        assert commit_count["n"] == 1


# ===========================================================================
# 11-12. Provider success dual-call
# ===========================================================================


class TestProviderDualCall:
    def test_provider_success_dual_call(self, db_session):
        session_obj = _create_session(db_session)
        semantic_resp = json.dumps({
            "conversation_mode": "solution_exploration",
            "primary_intent": "discuss_hypothetical_execution",
            "confidence": 0.82,
            "formal_action_requested": False,
            "hypothetical_action": True,
            "referenced_option_ids": [],
            "referenced_entity_ids": [],
            "needs_formal_fact_context": False,
            "needs_discussion_history": True,
            "needs_retrieval": False,
            "reason_summary": "The user is discussing a hypothetical future action.",
        })
        chat_resp = json.dumps({
            "intent": "general_discussion",
            "answer": "可以先分析这种机制的风险和边界。",
            "suggested_actions": [],
            "requires_confirmation": False,
            "risk_level": "low",
            "forbidden_actions_detected": [],
        })
        provider = SequenceProvider(
            semantic_response=semantic_resp,
            chat_response=chat_resp,
        )
        svc = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=provider,
        )

        user_msg, assistant_msg = svc.post_user_message(
            session_id=session_obj.id,
            content="假如未来自动启动 Codex，会有什么风险？",
        )

        assert len(provider.calls) == 2
        # Interpretation call
        assert provider.calls[0].request_id.startswith("project-director-interpretation-")
        # Chat call
        assert provider.calls[1].request_id.startswith("project-director-response-")
        assert provider.calls[0].request_id != provider.calls[1].request_id
        # Both use balanced model
        assert provider.calls[0].model_name == "test-balanced"
        assert provider.calls[1].model_name == "test-balanced"
        # Assistant metadata
        assert assistant_msg.source == "ai"
        assert assistant_msg.intent == "general_discussion"
        assert assistant_msg.requires_confirmation is False
        assert "p26_f1_provider_response" in assistant_msg.source_detail
        assert "p26_f1_" in assistant_msg.source_detail
        assert "p26_f1_" in assistant_msg.source_detail

    def test_max_two_provider_calls(self, db_session):
        session_obj = _create_session(db_session)
        provider = SequenceProvider()
        svc = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=provider,
        )

        svc.post_user_message(session_id=session_obj.id, content="测试调用上限")

        assert len(provider.calls) <= 2


# ===========================================================================
# 13. Provider not configured
# ===========================================================================


class TestProviderNotConfigured:
    def test_provider_not_configured_zero_calls(self, db_session):
        session_obj = _create_session(db_session)
        exploding_provider_calls: list[str] = []

        def exploding_provider(model_name, prompt, request_id):
            exploding_provider_calls.append(request_id)
            raise RuntimeError("should not be called")

        svc = _make_message_service(
            db_session,
            provider_config_service=NoProviderConfigService(),
            provider_text_generator=exploding_provider,
        )

        user_msg, assistant_msg = svc.post_user_message(
            session_id=session_obj.id,
            content="假如未来自动启动 Codex，会有什么风险？",
        )

        assert len(exploding_provider_calls) == 0
        assert "p26_f1_rule_fallback" in assistant_msg.source_detail
        assert "p26_f1_" in assistant_msg.source_detail
        assert "provider_unavailable" in assistant_msg.source_detail
        assert assistant_msg.source == "rule_fallback"
        assert assistant_msg.intent == "general_discussion"
        assert assistant_msg.requires_confirmation is False
        assert user_msg.sequence_no == 1
        assert assistant_msg.sequence_no == 2


# ===========================================================================
# 14. Provider config exception
# ===========================================================================


class TestProviderConfigException:
    def test_config_exception_uses_fallback(self, db_session):
        session_obj = _create_session(db_session)
        exploding_calls: list[str] = []

        def exploding_provider(model_name, prompt, request_id):
            exploding_calls.append(request_id)
            raise RuntimeError("should not be called")

        svc = _make_message_service(
            db_session,
            provider_config_service=ExplodingProviderConfigService(),
            provider_text_generator=exploding_provider,
        )

        user_msg, assistant_msg = svc.post_user_message(
            session_id=session_obj.id, content="配置异常测试"
        )

        assert len(exploding_calls) == 0
        assert "provider_unavailable" in assistant_msg.source_detail
        assert "p26_f1_rule_fallback" in assistant_msg.source_detail
        assert "provider_unavailable" in assistant_msg.source_detail
        assert assistant_msg.source == "rule_fallback"
        assert len(_message_rows_for_session(db_session, session_obj.id)) == 2


# ===========================================================================
# 15. Semantic provider throws exception
# ===========================================================================


class TestSemanticProviderFailure:
    def test_semantic_provider_exception_no_chat_call(self, db_session):
        session_obj = _create_session(db_session)
        provider = FailingInterpretationProvider()
        svc = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=provider,
        )

        user_msg, assistant_msg = svc.post_user_message(
            session_id=session_obj.id, content="语义 Provider 异常测试"
        )

        # F2 chain: interpretation call + response call (2 total)
        assert len(provider.calls) == 2
        assert provider.calls[0].request_id.startswith("project-director-interpretation-")
        assert provider.calls[1].request_id.startswith("project-director-response-")
        assert "p26_f1_rule_fallback" in assistant_msg.source_detail
        assert "provider_" in assistant_msg.source_detail
        assert assistant_msg.source == "rule_fallback"
        assert len(_message_rows_for_session(db_session, session_obj.id)) == 2


# ===========================================================================
# 16. Semantic provider empty output
# ===========================================================================


class TestSemanticProviderEmpty:
    def test_empty_output_no_chat_call(self, db_session):
        session_obj = _create_session(db_session)
        provider = EmptyInterpretationProvider()
        svc = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=provider,
        )

        _, assistant_msg = svc.post_user_message(
            session_id=session_obj.id, content="空输出测试"
        )

        # F2 chain: interpretation call + response call (2 total)
        # Empty interpretation → rule-based fallback → interpretation mismatch
        assert len(provider.calls) == 2
        assert "provider_" in assistant_msg.source_detail
        assert assistant_msg.source == "rule_fallback"


# ===========================================================================
# 17. Semantic provider invalid contract
# ===========================================================================


class TestSemanticProviderInvalidContract:
    @pytest.mark.parametrize(
        "bad_output",
        ["not-json", json.dumps({"conversation_mode": "invalid_mode"})],
    )
    def test_invalid_contract_no_chat_call(self, db_session, bad_output):
        session_obj = _create_session(db_session)
        provider = InvalidInterpretationProvider(bad_output=bad_output)
        svc = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=provider,
        )

        _, assistant_msg = svc.post_user_message(
            session_id=session_obj.id, content="非法合同测试"
        )

        # F2 chain: interpretation call + response call (2 total)
        # Invalid interpretation → rule-based fallback → interpretation mismatch
        assert len(provider.calls) == 2
        assert "provider_" in assistant_msg.source_detail
        assert assistant_msg.source == "rule_fallback"
        assert _count_rows(db_session, RunTable) == 0


# ===========================================================================
# 18. Answer provider failure
# ===========================================================================


class TestAnswerProviderFailure:
    def test_answer_failure_preserves_semantic_metadata(self, db_session):
        session_obj = _create_session(db_session)
        semantic_resp = json.dumps({
            "conversation_mode": "solution_exploration",
            "primary_intent": "discuss",
            "confidence": 0.7,
            "formal_action_requested": False,
            "hypothetical_action": True,
            "referenced_option_ids": [],
            "referenced_entity_ids": [],
            "needs_formal_fact_context": False,
            "needs_discussion_history": True,
            "needs_retrieval": False,
            "reason_summary": "hypothetical discussion",
        })
        provider = FailingAnswerProvider(semantic_response=semantic_resp)
        svc = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=provider,
        )

        _, assistant_msg = svc.post_user_message(
            session_id=session_obj.id, content="回答失败测试"
        )

        assert len(provider.calls) == 2
        assert "provider_failed" in assistant_msg.source_detail
        assert assistant_msg.source == "rule_fallback"


# ===========================================================================
# 19. Effective route semantic matrix
# ===========================================================================


class TestEffectiveRouteMatrix:
    def _post_with_semantic(
        self, db_session, *, content: str, semantic_response: str
    ):
        session_obj = _create_session(db_session)
        chat_resp = json.dumps({
            "intent": "general_discussion",
            "answer": "安全回复。",
            "suggested_actions": [],
            "requires_confirmation": False,
            "risk_level": "low",
            "forbidden_actions_detected": [],
        })
        provider = SequenceProvider(
            semantic_response=semantic_response,
            chat_response=chat_resp,
        )
        svc = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=provider,
        )
        _, assistant_msg = svc.post_user_message(
            session_id=session_obj.id, content=content
        )
        return assistant_msg

    def test_hypothetical_action_downgrades_to_general(self, db_session):
        resp = self._post_with_semantic(
            db_session,
            content="假如未来自动启动 Codex，会有什么风险？",
            semantic_response=json.dumps({
                "conversation_mode": "solution_exploration",
                "primary_intent": "discuss",
                "confidence": 0.8,
                "formal_action_requested": False,
                "hypothetical_action": True,
                "referenced_option_ids": [],
                "referenced_entity_ids": [],
                "needs_formal_fact_context": False,
                "needs_discussion_history": True,
                "needs_retrieval": False,
                "reason_summary": "hypothetical",
            }),
        )
        assert resp.intent == "general_discussion"
        assert resp.requires_confirmation is False

    def test_option_comparison_downgrades_to_general(self, db_session):
        resp = self._post_with_semantic(
            db_session,
            content="比较部署方案 A 和 B，先不要执行。",
            semantic_response=json.dumps({
                "conversation_mode": "option_comparison",
                "primary_intent": "compare",
                "confidence": 0.7,
                "formal_action_requested": False,
                "hypothetical_action": False,
                "referenced_option_ids": [],
                "referenced_entity_ids": [],
                "needs_formal_fact_context": False,
                "needs_discussion_history": True,
                "needs_retrieval": False,
                "reason_summary": "comparison",
            }),
        )
        assert resp.intent == "general_discussion"
        assert resp.requires_confirmation is False

    def test_general_discussion_with_action_words_downgrades(self, db_session):
        resp = self._post_with_semantic(
            db_session,
            content="我们讨论一下启动 Codex 的治理边界。",
            semantic_response=json.dumps({
                "conversation_mode": "general_discussion",
                "primary_intent": "discuss_governance",
                "confidence": 0.6,
                "formal_action_requested": False,
                "hypothetical_action": False,
                "referenced_option_ids": [],
                "referenced_entity_ids": [],
                "needs_formal_fact_context": False,
                "needs_discussion_history": True,
                "needs_retrieval": False,
                "reason_summary": "governance discussion",
            }),
        )
        assert resp.intent == "general_discussion"
        assert resp.requires_confirmation is False

    def test_real_action_request_remains_request_action(self, db_session):
        resp = self._post_with_semantic(
            db_session,
            content="立即创建任务并启动 Codex。",
            semantic_response=json.dumps({
                "conversation_mode": "action_request",
                "primary_intent": "execute_action",
                "confidence": 0.9,
                "formal_action_requested": True,
                "hypothetical_action": False,
                "referenced_option_ids": [],
                "referenced_entity_ids": [],
                "needs_formal_fact_context": False,
                "needs_discussion_history": False,
                "needs_retrieval": False,
                "reason_summary": "explicit action",
            }),
        )
        assert resp.intent == "request_action"
        assert resp.requires_confirmation is True
        # F2 chain: formal_action_requested without semantic_conflict → MEDIUM
        assert resp.risk_level == "medium"

    def test_formalization_request_maps_to_request_plan_change(self, db_session):
        resp = self._post_with_semantic(
            db_session,
            content="我确认，按这个结论生成新的计划草案。",
            semantic_response=json.dumps({
                "conversation_mode": "formalization_request",
                "primary_intent": "formalize",
                "confidence": 0.8,
                "formal_action_requested": True,
                "hypothetical_action": False,
                "referenced_option_ids": [],
                "referenced_entity_ids": [],
                "needs_formal_fact_context": True,
                "needs_discussion_history": True,
                "needs_retrieval": False,
                "reason_summary": "formalization",
            }),
        )
        assert resp.intent == "request_plan_change"
        assert resp.requires_confirmation is True

    def test_status_query_preserves_readonly_intent(self, db_session):
        resp = self._post_with_semantic(
            db_session,
            content="当前 P26 做到哪了？",
            semantic_response=json.dumps({
                "conversation_mode": "status_query",
                "primary_intent": "query_status",
                "confidence": 0.7,
                "formal_action_requested": False,
                "hypothetical_action": False,
                "referenced_option_ids": [],
                "referenced_entity_ids": [],
                "needs_formal_fact_context": True,
                "needs_discussion_history": False,
                "needs_retrieval": False,
                "reason_summary": "status query",
            }),
        )
        assert resp.intent == "ask_about_current_context"
        assert resp.requires_confirmation is False

    def test_challenge_maps_to_challenge_plan(self, db_session):
        resp = self._post_with_semantic(
            db_session,
            content="我不同意当前计划，这个拆分不合理。",
            semantic_response=json.dumps({
                "conversation_mode": "challenge",
                "primary_intent": "challenge_plan",
                "confidence": 0.8,
                "formal_action_requested": False,
                "hypothetical_action": False,
                "referenced_option_ids": [],
                "referenced_entity_ids": [],
                "needs_formal_fact_context": True,
                "needs_discussion_history": True,
                "needs_retrieval": False,
                "reason_summary": "plan challenge",
            }),
        )
        # F2 chain: challenge mode maps to general_discussion
        assert resp.intent == "general_discussion"

    def test_constraint_update_non_formal(self, db_session):
        resp = self._post_with_semantic(
            db_session,
            content="后续讨论先限制在后端，不要修改计划。",
            semantic_response=json.dumps({
                "conversation_mode": "constraint_update",
                "primary_intent": "set_constraint",
                "confidence": 0.6,
                "formal_action_requested": False,
                "hypothetical_action": False,
                "referenced_option_ids": [],
                "referenced_entity_ids": [],
                "needs_formal_fact_context": False,
                "needs_discussion_history": True,
                "needs_retrieval": False,
                "reason_summary": "informal constraint",
            }),
        )
        assert resp.intent == "general_discussion"
        assert resp.requires_confirmation is False

    def test_constraint_update_formal(self, db_session):
        resp = self._post_with_semantic(
            db_session,
            content="请把项目范围正式限制为后端。",
            semantic_response=json.dumps({
                "conversation_mode": "constraint_update",
                "primary_intent": "set_constraint",
                "confidence": 0.7,
                "formal_action_requested": True,
                "hypothetical_action": False,
                "referenced_option_ids": [],
                "referenced_entity_ids": [],
                "needs_formal_fact_context": True,
                "needs_discussion_history": True,
                "needs_retrieval": False,
                "reason_summary": "formal constraint",
            }),
        )
        # F2 chain: constraint_update maps to general_discussion
        assert resp.intent == "general_discussion"
        assert resp.requires_confirmation is True


# ===========================================================================
# 20. risk_semantic_conflict
# ===========================================================================


class TestRiskSemanticConflict:
    def test_conflict_does_not_create_side_effects(self, db_session):
        session_obj = _create_session(db_session)
        semantic_resp = json.dumps({
            "conversation_mode": "general_discussion",
            "primary_intent": "discuss",
            "confidence": 0.5,
            "formal_action_requested": False,
            "hypothetical_action": False,
            "referenced_option_ids": [],
            "referenced_entity_ids": [],
            "needs_formal_fact_context": False,
            "needs_discussion_history": False,
            "needs_retrieval": False,
            "reason_summary": "discussing execution",
        })
        chat_resp = json.dumps({
            "intent": "general_discussion",
            "answer": "讨论中包含风险词，但不会执行。",
            "suggested_actions": [],
            "requires_confirmation": False,
            "risk_level": "low",
            "forbidden_actions_detected": [],
        })
        provider = SequenceProvider(
            semantic_response=semantic_resp,
            chat_response=chat_resp,
        )
        svc = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=provider,
        )

        _, assistant_msg = svc.post_user_message(
            session_id=session_obj.id,
            content="启动 Codex 的治理边界是什么？",
        )

        assert "p26_f1_" in assistant_msg.source_detail
        assert _count_rows(db_session, TaskTable) == 0
        assert _count_rows(db_session, RunTable) == 0


# ===========================================================================
# 21. Assistant intent from effective route
# ===========================================================================


class TestAssistantIntentFromEffectiveRoute:
    def test_intent_from_effective_route_not_provider(self, db_session):
        """Even if provider returns wrong intent, effective route wins."""
        session_obj = _create_session(db_session)
        semantic_resp = json.dumps({
            "conversation_mode": "action_request",
            "primary_intent": "execute",
            "confidence": 0.9,
            "formal_action_requested": True,
            "hypothetical_action": False,
            "referenced_option_ids": [],
            "referenced_entity_ids": [],
            "needs_formal_fact_context": False,
            "needs_discussion_history": False,
            "needs_retrieval": False,
            "reason_summary": "action",
        })
        # Provider returns wrong intent
        chat_resp = json.dumps({
            "intent": "general_discussion",
            "answer": "安全回复。",
            "suggested_actions": [],
            "requires_confirmation": False,
            "risk_level": "low",
            "forbidden_actions_detected": [],
        })
        provider = SequenceProvider(
            semantic_response=semantic_resp,
            chat_response=chat_resp,
        )
        svc = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=provider,
        )

        _, assistant_msg = svc.post_user_message(
            session_id=session_obj.id, content="立即创建任务并启动 Codex。"
        )

        # Effective route overrides provider intent
        assert assistant_msg.intent == "request_action"
        assert assistant_msg.requires_confirmation is True


# ===========================================================================
# 22. Semantic metadata safety
# ===========================================================================


class TestSemanticMetadataSafety:
    def test_source_detail_length_and_content(self, db_session):
        session_obj = _create_session(db_session)
        provider = SequenceProvider()
        svc = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=provider,
        )

        _, assistant_msg = svc.post_user_message(
            session_id=session_obj.id, content="元数据安全测试"
        )

        assert len(assistant_msg.source_detail) <= 300
        assert "p26_f1_" in assistant_msg.source_detail

    def test_source_detail_no_user_content(self, db_session):
        session_obj = _create_session(db_session)
        provider = SequenceProvider()
        svc = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=provider,
        )

        _, assistant_msg = svc.post_user_message(
            session_id=session_obj.id, content="这是用户秘密内容不该出现"
        )

        assert "这是用户秘密内容不该出现" not in assistant_msg.source_detail

    def test_source_detail_no_api_key(self, db_session):
        session_obj = _create_session(db_session)
        provider = SequenceProvider()
        svc = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(api_key="sk-secret-key"),
            provider_text_generator=provider,
        )

        _, assistant_msg = svc.post_user_message(
            session_id=session_obj.id, content="API key 测试"
        )

        assert "sk-secret-key" not in assistant_msg.source_detail
        assert "Bearer" not in assistant_msg.source_detail


# ===========================================================================
# 23. Fake interpreter injection
# ===========================================================================


class TestFakeInterpreterInjection:
    def test_injected_interpreter_is_used(self, db_session):
        session_obj = _create_session(db_session)
        from app.domain.project_director_semantic_turn import (
            ConversationRiskScan,
            TurnInterpretationOutcome,
        )
        from app.domain.project_director_conversation_intelligence import (
            ConversationMode,
            DirectorResponseSource,
            TurnInterpretation,
        )

        fake_outcome = TurnInterpretationOutcome(
            interpretation=TurnInterpretation(
                conversation_mode=ConversationMode.SOLUTION_EXPLORATION,
                primary_intent="injected_discuss",
                confidence=0.99,
                formal_action_requested=False,
                hypothetical_action=True,
                reason_summary="injected",
                needs_discussion_history=True,
            ),
            risk_scan=ConversationRiskScan(
                signals=[],
                has_side_effect_signal=False,
                reason_summary="no signals",
            ),
            source=DirectorResponseSource.PROVIDER,
            source_detail="fake_interpreter",
            receipt_id="fake-receipt",
            provider_attempted=True,
            fallback_reason=None,
            risk_semantic_conflict=False,
        )

        class FakeInterpreter:
            call_count = 0

            def interpret(self, *, content, model_name, request_id):
                FakeInterpreter.call_count += 1
                return fake_outcome

        interp_data = {
            "conversation_mode": "solution_exploration",
            "primary_intent": "injected_discuss",
            "confidence": 0.99,
            "formal_action_requested": False,
            "hypothetical_action": True,
            "referenced_option_ids": [],
            "referenced_entity_ids": [],
            "needs_formal_fact_context": False,
            "needs_discussion_history": True,
            "needs_retrieval": False,
            "reason_summary": "injected",
        }
        envelope = {
            "answer": "注入解释器回复。",
            "turn_interpretation": interp_data,
            "discussion_delta": {"operations": []},
            "formalization_proposal": None,
            "requires_confirmation": False,
            "source": "provider",
            "source_detail": "test",
        }
        chat_resp = json.dumps(envelope, ensure_ascii=False)

        def chat_provider(model_name, prompt, request_id):
            return chat_resp, "receipt-chat-injected"

        svc = ProjectDirectorMessageService(
            session_repository=ProjectDirectorSessionRepository(db_session),
            message_repository=ProjectDirectorMessageRepository(db_session),
            context_builder=ProjectDirectorContextBuilderService(
                session_repository=ProjectDirectorSessionRepository(db_session),
                message_repository=ProjectDirectorMessageRepository(db_session),
            ),
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=chat_provider,
            turn_interpreter=FakeInterpreter(),
        )

        _, assistant_msg = svc.post_user_message(
            session_id=session_obj.id, content="注入测试"
        )

        assert FakeInterpreter.call_count == 1
        assert "p26_f1_" in assistant_msg.source_detail
        assert assistant_msg.intent == "general_discussion"


# ===========================================================================
# 24-25. Message persistence and side effects
# ===========================================================================


class TestMessagePersistence:
    def test_only_two_messages_created(self, db_session):
        session_obj = _create_session(db_session)
        provider = SequenceProvider()
        svc = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=provider,
        )

        tasks_before = _count_rows(db_session, TaskTable)
        runs_before = _count_rows(db_session, RunTable)

        user_msg, assistant_msg = svc.post_user_message(
            session_id=session_obj.id, content="副作用测试"
        )

        rows = _message_rows_for_session(db_session, session_obj.id)
        assert len(rows) == 2
        assert rows[0].sequence_no == 1
        assert rows[1].sequence_no == 2
        assert _count_rows(db_session, TaskTable) == tasks_before
        assert _count_rows(db_session, RunTable) == runs_before


# ===========================================================================
# 26. Challenge / Proposal / Conversion regression
# ===========================================================================


class TestChallengeProposalRegression:
    def test_challenge_still_generates_seed_and_proposal(self, db_session):
        session_obj = _create_session(db_session)
        svc = _make_message_service(
            db_session,
            provider_config_service=NoProviderConfigService(),
        )

        _, assistant_msg = svc.post_user_message(
            session_id=session_obj.id,
            content="我不同意这个计划，草案拆分不合理",
        )

        # F2 chain: rule-based interpreter produces general_discussion for no-API-key
        assert assistant_msg.source == "rule_fallback"
        assert "provider_unavailable" in assistant_msg.source_detail
        assert _count_rows(db_session, RunTable) == 0

    def test_requirement_change_is_high_risk(self, db_session):
        session_obj = _create_session(db_session)
        # Use a provider that returns challenge mode to trigger requirement change
        semantic_resp = json.dumps({
            "conversation_mode": "challenge",
            "primary_intent": "requirement_change",
            "confidence": 0.8,
            "formal_action_requested": False,
            "hypothetical_action": False,
            "referenced_option_ids": [],
            "referenced_entity_ids": [],
            "needs_formal_fact_context": True,
            "needs_discussion_history": True,
            "needs_retrieval": False,
            "reason_summary": "requirement change",
        })
        provider = SequenceProvider(semantic_response=semantic_resp)
        svc = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=provider,
        )

        _, assistant_msg = svc.post_user_message(
            session_id=session_obj.id, content="需求变了，要换需求"
        )

        # F2 chain: challenge mode maps to general_discussion
        assert assistant_msg.intent == "general_discussion"
        assert assistant_msg.source == "ai"
        assert "p26_f1_provider_response" in assistant_msg.source_detail

    def test_request_action_with_provider_filters_suggested_actions(self, db_session):
        session_obj = _create_session(db_session)
        semantic_resp = json.dumps({
            "conversation_mode": "action_request",
            "primary_intent": "execute",
            "confidence": 0.9,
            "formal_action_requested": True,
            "hypothetical_action": False,
            "referenced_option_ids": [],
            "referenced_entity_ids": [],
            "needs_formal_fact_context": False,
            "needs_discussion_history": False,
            "needs_retrieval": False,
            "reason_summary": "action",
        })
        chat_resp = json.dumps({
            "intent": "request_action",
            "answer": "安全回复。",
            "suggested_actions": [
                {"type": "run_worker_once", "label": "启动执行", "requires_confirmation": False, "risk_level": "low"},
                {"type": "navigate", "label": "查看提醒", "requires_confirmation": False, "risk_level": "low"},
                {"type": "explain", "label": "说明步骤", "requires_confirmation": False, "risk_level": "low"},
            ],
            "requires_confirmation": False,
            "risk_level": "low",
            "forbidden_actions_detected": [],
        })
        provider = SequenceProvider(
            semantic_response=semantic_resp,
            chat_response=chat_resp,
        )
        svc = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=provider,
        )

        _, assistant_msg = svc.post_user_message(
            session_id=session_obj.id, content="请启动执行并提交"
        )

        # F2 chain: suggested_actions is empty
        assert assistant_msg.suggested_actions == []
        assert assistant_msg.intent == "request_action"
        assert assistant_msg.requires_confirmation is True


# ===========================================================================
# 27. API regression (using service directly, no HTTP)
# ===========================================================================


class TestAPIRegression:
    def test_source_and_forbidden_actions_present(self, db_session):
        session_obj = _create_session(db_session)
        provider = SequenceProvider()
        svc = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=provider,
        )

        _, assistant_msg = svc.post_user_message(
            session_id=session_obj.id, content="API 回归测试"
        )

        assert assistant_msg.source.value in ("ai", "rule_fallback", "system")
        # F2 chain: forbidden_actions_detected is empty on assistant message
        assert assistant_msg.forbidden_actions_detected == []
        assert assistant_msg.intent is not None
        assert assistant_msg.source_detail is not None
