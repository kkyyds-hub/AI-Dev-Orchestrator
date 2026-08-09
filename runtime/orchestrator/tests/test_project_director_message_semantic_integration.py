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
    AgentSessionTable,
    ORMBase,
    ProjectDirectorDiscussionEventTable,
    ProjectDirectorDiscussionWorkspaceTable,
    ProjectDirectorFormalizationProposalTable,
    ProjectDirectorMessageTable,
    ProjectDirectorPlanVersionTable,
    ProjectDirectorSessionTable,
    RunTable,
    TaskTable,
)
from app.domain.project import Project
from app.domain.project_director_conversation_router import (
    ConversationIntent,
    ConversationRouter,
)
from app.domain.project_director_discussion import (
    DiscussionActorClaim,
    DiscussionEventStatus,
    DiscussionEventType,
)
from app.domain.project_director_message import (
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
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


class ReselectionSequenceProvider:
    """Deterministic provider for the persisted rejected-option reselection path."""

    def __init__(self, *, option_id: UUID, rejection_event_id: UUID) -> None:
        self.option_id = option_id
        self.rejection_event_id = rejection_event_id
        self.calls: list[ProviderCallRecord] = []
        self.interpretation = {
            "conversation_mode": "preference_update",
            "primary_intent": "discuss_current_topic",
            "confidence": 0.9,
            "formal_action_requested": False,
            "hypothetical_action": False,
            "referenced_option_ids": [str(option_id)],
            "referenced_entity_ids": [],
            "needs_formal_fact_context": False,
            "needs_discussion_history": True,
            "needs_retrieval": False,
            "reason_summary": "user explicitly reselected the rejected option",
        }

    def __call__(self, model_name: str, prompt: str, request_id: str):
        self.calls.append(ProviderCallRecord(model_name, prompt, request_id))
        if request_id.startswith("project-director-interpretation-"):
            return json.dumps(self.interpretation), "receipt-interpretation"
        response_context = json.loads(prompt)["context"]
        current_user_id = response_context["current_user_message"]["id"]
        return json.dumps({
            "answer": "已按你的明确选择恢复方案A为当前偏好。",
            "turn_interpretation": response_context["caller_interpretation"],
            "discussion_delta": {"operations": [{
                "op": "prefer_option",
                "content": "用户重新选择方案A",
                "target_id": str(self.option_id),
                "payload": {"option_id": str(self.option_id)},
                "source_message_ids": [current_user_id],
                "actor_claim": "user_explicit",
                "supersedes_event_id": str(self.rejection_event_id),
            }]},
            "formalization_proposal": None,
            "requires_confirmation": False,
            "source": "provider",
            "source_detail": "test reselection provider",
        }, ensure_ascii=False), "receipt-response"


@dataclass
class FormalizationRepairProviderCall:
    model_name: str
    prompt: str
    request_id: str
    receipt: str


class FormalizationRepairSequenceProvider:
    """Local sequence Provider for F8 Message Service repair integration."""

    def __init__(self, *, repair_succeeds: bool) -> None:
        self.repair_succeeds = repair_succeeds
        self.calls: list[FormalizationRepairProviderCall] = []

    @staticmethod
    def _interpretation() -> dict[str, object]:
        return {
            "conversation_mode": "formalization_request",
            "primary_intent": "formalize_plan_revision",
            "confidence": 0.9,
            "formal_action_requested": True,
            "hypothetical_action": False,
            "referenced_option_ids": [],
            "referenced_entity_ids": [],
            "needs_formal_fact_context": True,
            "needs_discussion_history": True,
            "needs_retrieval": False,
            "reason_summary": "explicit formalization request",
        }

    def __call__(self, model_name: str, prompt: str, request_id: str):
        receipt = f"receipt-{len(self.calls) + 1}"
        self.calls.append(FormalizationRepairProviderCall(
            model_name=model_name,
            prompt=prompt,
            request_id=request_id,
            receipt=receipt,
        ))
        if request_id.startswith("project-director-interpretation-"):
            return json.dumps(self._interpretation()), receipt

        prompt_data = json.loads(prompt)
        contract = prompt_data["formalization_envelope_contract"]
        identity = contract["identity_context"]
        proposal = {
            "proposal_id": str(uuid4()),
            "target": "plan_revision",
            "workspace_version": identity["expected_workspace_version_after_this_turn"],
            "summary": "测试正式化草案",
            "changes": [{
                "change_type": "update",
                "subject_key": "topic",
                "summary": "更新主题草案",
                "source_event_ids": [identity["visible_pre_turn_event_ids"][0]],
            }],
            "source_message_ids": [identity["current_user_message_id"]],
            "risk_summary": "需要确认后才能应用",
            "requires_confirmation": True,
            "status": "proposed",
        }
        envelope = {
            "answer": "已准备正式化草案，等待确认。",
            "turn_interpretation": identity["caller_interpretation"],
            "discussion_delta": {"operations": [{
                "op": "request_formalization",
                "target_id": None,
                "subject_key": "formalization:request",
                "content": "用户请求正式化",
                "payload": {},
                "source_message_ids": [identity["current_user_message_id"]],
                "actor_claim": "user_explicit",
                "supersedes_event_id": None,
            }]},
            "formalization_proposal": proposal,
            "requires_confirmation": True,
            "source": "provider",
            "source_detail": "test provider",
        }
        if "initial_provider_envelope_json" not in prompt_data:
            proposal.pop("proposal_id")
        elif not self.repair_succeeds:
            proposal.pop("workspace_version")
        return json.dumps(envelope, ensure_ascii=False), receipt


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


def _assert_single_repair_fallback(provider, assistant_msg, db_session) -> None:
    interpretation_calls = [
        call
        for call in provider.calls
        if call.request_id.startswith("project-director-interpretation-")
    ]
    response_calls = [
        call
        for call in provider.calls
        if call.request_id.startswith("project-director-response-")
    ]

    assert len(provider.calls) == 3
    assert len(interpretation_calls) == 1
    assert len(response_calls) == 2
    assert provider.calls[0] is interpretation_calls[0]
    assert provider.calls[1] is response_calls[0]
    assert provider.calls[2] is response_calls[1]
    assert assistant_msg.source == "rule_fallback"
    assert "provider_repair_failed:provider_interpretation_mismatch" in assistant_msg.source_detail
    assert _count_rows(db_session, ProjectDirectorDiscussionEventTable) == 0
    assert _count_rows(db_session, ProjectDirectorDiscussionWorkspaceTable) == 0
    assert _count_rows(db_session, TaskTable) == 0
    assert _count_rows(db_session, RunTable) == 0
    assert _count_rows(db_session, AgentSessionTable) == 0


def _seed_visible_pre_turn_event(db_session, session_id):
    """Provide the existing workspace/event lineage required by formalization."""

    prior_message_id = uuid4()
    event_id = uuid4()
    db_session.add(ProjectDirectorMessageTable(
        id=prior_message_id,
        session_id=session_id,
        role=ProjectDirectorMessageRole.USER,
        content="先前已确认的讨论主题",
        sequence_no=1,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail="test seed",
    ))
    db_session.add(ProjectDirectorDiscussionEventTable(
        id=event_id,
        session_id=session_id,
        project_id=None,
        sequence_no=1,
        event_type=DiscussionEventType.TOPIC_SET,
        subject_key="topic",
        content="先前主题",
        status=DiscussionEventStatus.ACTIVE,
        payload_json="{}",
        source_message_ids_json=json.dumps([str(prior_message_id)]),
        supersedes_event_id=None,
        created_by=DiscussionActorClaim.USER_EXPLICIT,
        confidence=1.0,
        idempotency_key=f"f8-seed-{event_id}",
    ))
    db_session.add(ProjectDirectorDiscussionWorkspaceTable(
        session_id=session_id,
        project_id=None,
        topic="先前主题",
        discussion_status="exploring",
        state_json=json.dumps({
            "active_option_ids": [], "preferred_option_id": None,
            "active_constraint_ids": [], "open_question_ids": [],
            "temporary_conclusion_ids": [], "confirmed_decision_ids": [],
            "latest_user_correction_event_id": None,
        }),
        version_no=1,
        last_event_sequence_no=1,
    ))
    db_session.flush()
    return event_id


def _seed_rejected_option_history(db_session, session_id):
    """Seed A/B and an effective rejection of A before the reselection turn."""
    prior_message_id, option_a, option_b, rejection_id = uuid4(), uuid4(), uuid4(), uuid4()
    db_session.add(ProjectDirectorMessageTable(
        id=prior_message_id,
        session_id=session_id,
        role=ProjectDirectorMessageRole.USER,
        content="先建立方案A和方案B，随后拒绝A并偏好B。",
        sequence_no=1,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail="test seed",
    ))
    for sequence_no, event_type, option_id, event_id in (
        (1, DiscussionEventType.OPTION_ADDED, option_a, uuid4()),
        (2, DiscussionEventType.OPTION_ADDED, option_b, uuid4()),
        (3, DiscussionEventType.OPTION_PREFERRED, option_b, uuid4()),
        (4, DiscussionEventType.OPTION_REJECTED, option_a, rejection_id),
    ):
        payload = {"option_id": str(option_id)}
        if event_type is DiscussionEventType.OPTION_ADDED:
            content = (
                "添加选项A：只保留最近聊天记录"
                if option_id == option_a
                else "添加选项B：使用结构化DiscussionEvent和DiscussionWorkspace"
            )
        else:
            content = "测试历史选项"
        db_session.add(ProjectDirectorDiscussionEventTable(
            id=event_id,
            session_id=session_id,
            project_id=None,
            sequence_no=sequence_no,
            event_type=event_type,
            subject_key=f"option:{option_id}",
            content=content,
            status=DiscussionEventStatus.ACTIVE,
            payload_json=json.dumps(payload),
            source_message_ids_json=json.dumps([str(prior_message_id)]),
            supersedes_event_id=None,
            created_by=DiscussionActorClaim.USER_EXPLICIT,
            confidence=1.0,
            idempotency_key=f"reselection-history-{event_id}",
        ))
    db_session.add(ProjectDirectorDiscussionWorkspaceTable(
        session_id=session_id,
        project_id=None,
        topic="",
        discussion_status="converging",
        state_json=json.dumps({
            "active_option_ids": [str(option_b)],
            "preferred_option_id": str(option_b),
            "active_constraint_ids": [],
            "open_question_ids": [],
            "temporary_conclusion_ids": [],
            "confirmed_decision_ids": [],
            "latest_user_correction_event_id": None,
        }),
        version_no=4,
        last_event_sequence_no=4,
    ))
    db_session.flush()
    return option_a, option_b, rejection_id


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

    def test_direct_success_has_two_provider_calls(self, db_session):
        session_obj = _create_session(db_session)
        provider = SequenceProvider()
        svc = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=provider,
        )

        svc.post_user_message(session_id=session_obj.id, content="测试调用上限")

        assert len(provider.calls) == 2
        assert sum(
            call.request_id.startswith("project-director-interpretation-")
            for call in provider.calls
        ) == 1
        assert sum(
            call.request_id.startswith("project-director-response-")
            for call in provider.calls
        ) == 1


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

        _assert_single_repair_fallback(provider, assistant_msg, db_session)
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

        _assert_single_repair_fallback(provider, assistant_msg, db_session)


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

        _assert_single_repair_fallback(provider, assistant_msg, db_session)


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

            def interpret(
                self, *, content, model_name, request_id, visible_options=()
            ):
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


class TestRejectedOptionReselectionMessageIntegration:
    def test_reselection_persists_only_original_option_preference(self, db_session):
        session_obj = _create_session(db_session)
        option_a, option_b, rejection_id = _seed_rejected_option_history(
            db_session, session_obj.id
        )
        provider = ReselectionSequenceProvider(
            option_id=option_a, rejection_event_id=rejection_id
        )
        svc = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=provider,
        )
        visible_options = svc._build_visible_option_references(
            session_id=session_obj.id,
            project_id=None,
            session=db_session,
        )
        visible_by_id = {option.option_id: option for option in visible_options}
        assert set(visible_by_id) == {option_a, option_b}
        assert "方案A" in visible_by_id[option_a].aliases
        assert "方案B" in visible_by_id[option_b].aliases
        assert visible_by_id[option_a].is_rejected is True
        assert visible_by_id[option_b].is_active is True
        assert visible_by_id[option_b].is_rejected is False
        before = {
            table: _count_rows(db_session, table)
            for table in (
                ProjectDirectorFormalizationProposalTable,
                ProjectDirectorPlanVersionTable,
                TaskTable,
                RunTable,
                AgentSessionTable,
            )
        }

        _, assistant = svc.post_user_message(
            session_id=session_obj.id,
            content="我改变主意，重新选择方案A。",
        )

        response_prompt = json.loads(provider.calls[-1].prompt)
        caller_interpretation = response_prompt["context"]["caller_interpretation"]
        assert caller_interpretation["conversation_mode"] == "preference_update"
        assert caller_interpretation["referenced_option_ids"] == [str(option_a)]
        assert caller_interpretation["needs_discussion_history"] is True
        assert response_prompt["required_preference_target_id"] == str(option_a)
        assert (
            response_prompt["required_preference_supersedes_event_id"]
            == str(rejection_id)
        )

        events = db_session.execute(
            select(ProjectDirectorDiscussionEventTable)
            .where(ProjectDirectorDiscussionEventTable.session_id == session_obj.id)
            .order_by(ProjectDirectorDiscussionEventTable.sequence_no)
        ).scalars().all()
        workspace = db_session.get(ProjectDirectorDiscussionWorkspaceTable, session_obj.id)
        reselection = events[-1]
        state = json.loads(workspace.state_json)
        assert assistant.source == "ai"
        assert len(events) == 5
        assert reselection.event_type is DiscussionEventType.OPTION_PREFERRED
        assert json.loads(reselection.payload_json)["option_id"] == str(option_a)
        assert reselection.supersedes_event_id == rejection_id
        assert state["active_option_ids"] == [str(option_a), str(option_b)]
        assert state["preferred_option_id"] == str(option_a)
        assert workspace.version_no == 5
        assert sum(
            event.event_type is DiscussionEventType.OPTION_ADDED
            and json.loads(event.payload_json)["option_id"] == str(option_a)
            for event in events
        ) == 1
        for table, count in before.items():
            assert _count_rows(db_session, table) == count


class TestAddEventOptionAliasDerivation:
    @pytest.mark.parametrize(
        ("content", "base_label"),
        [
            ("添加选项A：只保留最近聊天记录", "A"),
            ("添加选项B：使用结构化DiscussionEvent和DiscussionWorkspace", "B"),
            ("新增方案A：只保留最近聊天记录", "A"),
            ("已添加选项A：只保留最近聊天记录", "A"),
            ("方案A：只保留最近聊天记录", "A"),
            ("A", "A"),
        ],
    )
    def test_explicit_add_and_legacy_labels_derive_one_option_family(
        self, content, base_label
    ):
        aliases: list[str] = []

        ProjectDirectorMessageService._append_visible_option_aliases(aliases, content)

        assert {base_label, f"方案{base_label}", f"选项{base_label}", f"组合{base_label}"} <= set(aliases)

    @pytest.mark.parametrize(
        "content",
        [
            "讨论添加选项A的风险。",
            "请分析添加选项A是否合理。",
            "如果添加选项A会怎样？",
            "不要添加选项A。",
            "未决定是否添加选项A。",
            "记录了用户曾说“添加选项A”。",
            "添加选项A和选项B。",
            "新增方案A、方案B两个方案。",
            "创建组合A/B。",
        ],
    )
    def test_contextual_or_multiple_additions_do_not_derive_short_alias_a(self, content):
        aliases: list[str] = []

        ProjectDirectorMessageService._append_visible_option_aliases(aliases, content)

        assert "A" not in aliases
        assert "方案A" not in aliases
        assert "选项A" not in aliases
        assert "组合A" not in aliases


class TestAddEventOptionReselectionFiveTurnIntegration:
    def test_real_add_event_content_reselects_the_original_rejected_option(
        self, db_session
    ):
        session_obj = _create_session(db_session)
        option_a, option_b = uuid4(), uuid4()

        class FiveTurnProvider:
            def __init__(self) -> None:
                self.turn_index = 0
                self.calls: list[ProviderCallRecord] = []
                self.rejection_event_id: UUID | None = None

            def __call__(self, model_name: str, prompt: str, request_id: str):
                self.calls.append(ProviderCallRecord(model_name, prompt, request_id))
                if request_id.startswith("project-director-interpretation-"):
                    references = (
                        [str(option_b)] if self.turn_index == 3
                        else [str(option_a)] if self.turn_index == 4
                        else []
                    )
                    return json.dumps({
                        "conversation_mode": (
                            "preference_update" if self.turn_index in {3, 4}
                            else "general_discussion"
                        ),
                        "primary_intent": "discuss",
                        "confidence": 0.9,
                        "formal_action_requested": False,
                        "hypothetical_action": False,
                        "referenced_option_ids": references,
                        "referenced_entity_ids": [],
                        "needs_formal_fact_context": False,
                        "needs_discussion_history": self.turn_index in {3, 4},
                        "needs_retrieval": False,
                        "reason_summary": "deterministic five-turn test",
                    }), "receipt-interpretation"

                prompt_data = json.loads(prompt)
                current_user_id = prompt_data["context"]["current_user_message"]["id"]
                operation: dict[str, object]
                if self.turn_index == 0:
                    operation = {
                        "op": "set_topic", "target_id": None,
                        "subject_key": "topic:p26-alias", "content": "P26选项讨论",
                        "payload": {}, "source_message_ids": [current_user_id],
                        "actor_claim": "user_explicit", "supersedes_event_id": None,
                    }
                elif self.turn_index == 1:
                    operation = {
                        "op": "add_option", "target_id": str(option_a),
                        "subject_key": f"option:{option_a}",
                        "content": "添加选项A：只保留最近聊天记录",
                        "payload": {"option_id": str(option_a)},
                        "source_message_ids": [current_user_id],
                        "actor_claim": "user_explicit", "supersedes_event_id": None,
                    }
                    operation_b = {
                        "op": "add_option", "target_id": str(option_b),
                        "subject_key": f"option:{option_b}",
                        "content": "添加选项B：使用结构化DiscussionEvent和DiscussionWorkspace",
                        "payload": {"option_id": str(option_b)},
                        "source_message_ids": [current_user_id],
                        "actor_claim": "user_explicit", "supersedes_event_id": None,
                    }
                elif self.turn_index == 2:
                    operation = {
                        "op": "reject_option", "target_id": str(option_a),
                        "subject_key": f"option:{option_a}", "content": "用户拒绝方案A",
                        "payload": {"option_id": str(option_a)},
                        "source_message_ids": [current_user_id],
                        "actor_claim": "user_explicit", "supersedes_event_id": None,
                    }
                elif self.turn_index == 3:
                    operation = {
                        "op": "prefer_option", "target_id": str(option_b),
                        "subject_key": f"option:{option_b}", "content": "用户当前选择方案B",
                        "payload": {"option_id": str(option_b)},
                        "source_message_ids": [current_user_id],
                        "actor_claim": "user_explicit", "supersedes_event_id": None,
                    }
                else:
                    required_rejection = prompt_data["required_preference_supersedes_event_id"]
                    self.rejection_event_id = UUID(required_rejection)
                    operation = {
                        "op": "prefer_option", "target_id": str(option_a),
                        "subject_key": f"option:{option_a}", "content": "用户重新选择方案A",
                        "payload": {"option_id": str(option_a)},
                        "source_message_ids": [current_user_id],
                        "actor_claim": "user_explicit",
                        "supersedes_event_id": required_rejection,
                    }

                operations = [operation]
                if self.turn_index == 1:
                    operations.append(operation_b)
                envelope = {
                    "answer": "已记录本轮讨论。",
                    "turn_interpretation": prompt_data["context"]["caller_interpretation"],
                    "discussion_delta": {"operations": operations},
                    "formalization_proposal": None,
                    "requires_confirmation": False,
                    "source": "provider",
                    "source_detail": "deterministic five-turn provider",
                }
                self.turn_index += 1
                return json.dumps(envelope, ensure_ascii=False), "receipt-response"

        provider = FiveTurnProvider()
        service = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=provider,
        )
        before = {
            table: _count_rows(db_session, table)
            for table in (
                ProjectDirectorFormalizationProposalTable,
                ProjectDirectorPlanVersionTable,
                TaskTable,
                RunTable,
                AgentSessionTable,
            )
        }

        for content in (
            "设置讨论主题。",
            "添加：A：只保留最近聊天记录；B：使用结构化DiscussionEvent和DiscussionWorkspace。",
            "明确拒绝A并保存理由。",
            "当前选择B。",
        ):
            _, assistant = service.post_user_message(session_id=session_obj.id, content=content)
            assert assistant.source == "ai"

        visible_options = service._build_visible_option_references(
            session_id=session_obj.id, project_id=None, session=db_session
        )
        visible_by_id = {option.option_id: option for option in visible_options}
        assert set(visible_by_id) == {option_a, option_b}
        assert "方案A" in visible_by_id[option_a].aliases
        assert "方案B" in visible_by_id[option_b].aliases
        assert visible_by_id[option_a].is_rejected is True
        assert visible_by_id[option_b].is_active is True

        _, assistant = service.post_user_message(
            session_id=session_obj.id, content="我改变主意，重新选择方案A。"
        )

        response_prompt = json.loads(provider.calls[-1].prompt)
        interpretation = response_prompt["context"]["caller_interpretation"]
        assert assistant.source == "ai"
        assert interpretation["conversation_mode"] == "preference_update"
        assert interpretation["referenced_option_ids"] == [str(option_a)]
        assert interpretation["needs_discussion_history"] is True
        assert response_prompt["required_preference_target_id"] == str(option_a)
        assert response_prompt["required_preference_supersedes_event_id"] == str(provider.rejection_event_id)

        events = db_session.execute(
            select(ProjectDirectorDiscussionEventTable)
            .where(ProjectDirectorDiscussionEventTable.session_id == session_obj.id)
            .order_by(ProjectDirectorDiscussionEventTable.sequence_no)
        ).scalars().all()
        workspace = db_session.get(ProjectDirectorDiscussionWorkspaceTable, session_obj.id)
        state = json.loads(workspace.state_json)
        assert sum(
            event.event_type is DiscussionEventType.OPTION_PREFERRED
            and json.loads(event.payload_json)["option_id"] == str(option_a)
            for event in events
        ) == 1
        assert sum(
            event.event_type is DiscussionEventType.OPTION_ADDED
            and json.loads(event.payload_json)["option_id"] == str(option_a)
            for event in events
        ) == 1
        assert events[-1].event_type is DiscussionEventType.OPTION_PREFERRED
        assert events[-1].supersedes_event_id == provider.rejection_event_id
        assert state["active_option_ids"] == [str(option_a), str(option_b)]
        assert state["preferred_option_id"] == str(option_a)
        for table, count in before.items():
            assert _count_rows(db_session, table) == count


class TestFormalizationEnvelopeRepairMessageIntegration:
    def test_f8_invalid_direct_and_repair_are_atomic_for_message_service(self, db_session):
        session_obj = _create_session(db_session)
        _seed_visible_pre_turn_event(db_session, session_obj.id)
        provider = FormalizationRepairSequenceProvider(repair_succeeds=False)
        svc = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=provider,
        )
        before = {
            table: _count_rows(db_session, table)
            for table in (
                ProjectDirectorDiscussionEventTable,
                ProjectDirectorDiscussionWorkspaceTable,
                ProjectDirectorFormalizationProposalTable,
                ProjectDirectorPlanVersionTable,
                TaskTable,
                RunTable,
                AgentSessionTable,
            )
        }

        _, assistant_msg = svc.post_user_message(
            session_id=session_obj.id,
            content="请基于当前讨论生成正式计划草案",
        )

        response_calls = [
            call for call in provider.calls
            if call.request_id.startswith("project-director-response-")
        ]
        assert len(provider.calls) == 3
        assert len(response_calls) == 2
        assert response_calls[1].request_id == f"{response_calls[0].request_id}-repair"
        assert assistant_msg.source == "rule_fallback"
        assert "provider_repair_failed:provider_formalization_proposal_invalid" in assistant_msg.source_detail
        for table, count in before.items():
            assert _count_rows(db_session, table) == count

    def test_f8_repair_success_persists_only_proposed_formalization(self, db_session):
        session_obj = _create_session(db_session)
        visible_event_id = _seed_visible_pre_turn_event(db_session, session_obj.id)
        provider = FormalizationRepairSequenceProvider(repair_succeeds=True)
        svc = _make_message_service(
            db_session,
            provider_config_service=CountingProviderConfigService(),
            provider_text_generator=provider,
        )
        before_events = _count_rows(db_session, ProjectDirectorDiscussionEventTable)
        before_proposals = _count_rows(db_session, ProjectDirectorFormalizationProposalTable)
        before_plan_versions = _count_rows(db_session, ProjectDirectorPlanVersionTable)
        before_tasks = _count_rows(db_session, TaskTable)
        before_runs = _count_rows(db_session, RunTable)
        before_agent_sessions = _count_rows(db_session, AgentSessionTable)

        _, assistant_msg = svc.post_user_message(
            session_id=session_obj.id,
            content="请基于当前讨论生成正式计划草案",
        )

        response_calls = [
            call for call in provider.calls
            if call.request_id.startswith("project-director-response-")
        ]
        proposal = db_session.execute(
            select(ProjectDirectorFormalizationProposalTable)
        ).scalar_one()
        workspace = db_session.get(ProjectDirectorDiscussionWorkspaceTable, session_obj.id)
        assert len(provider.calls) == 3
        assert len(response_calls) == 2
        assert response_calls[1].request_id == f"{response_calls[0].request_id}-repair"
        assert assistant_msg.source == "ai"
        assert "attempt=repair" in assistant_msg.source_detail
        assert proposal.status == "proposed"
        assert json.loads(proposal.source_event_ids_json) == [str(visible_event_id)]
        assert workspace.version_no == 2
        assert _count_rows(db_session, ProjectDirectorDiscussionEventTable) == before_events + 1
        assert _count_rows(db_session, ProjectDirectorFormalizationProposalTable) == before_proposals + 1
        assert _count_rows(db_session, ProjectDirectorPlanVersionTable) == before_plan_versions
        assert _count_rows(db_session, TaskTable) == before_tasks
        assert _count_rows(db_session, RunTable) == before_runs
        assert _count_rows(db_session, AgentSessionTable) == before_agent_sessions


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
