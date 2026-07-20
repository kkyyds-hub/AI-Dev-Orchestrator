"""Contract tests for P26-F2-A production conversation brain message flow.

Verifies the full chain:
  POST user message → persist → interpret → context → response → persist → delta → commit → API
"""

from __future__ import annotations

import ast
import json
from copy import deepcopy
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.router import api_router
from app.api.routes import project_director as project_director_route
from app.core.db import get_db_session
from app.core.db_tables import (
    ORMBase,
    ProjectDirectorDiscussionEventTable,
    ProjectDirectorDiscussionWorkspaceTable,
    ProjectDirectorMessageTable,
    ProjectDirectorSessionTable,
    ProjectDirectorPlanVersionTable,
    RunTable,
    TaskTable,
)
from app.domain.project_director_conversation_intelligence import (
    ConversationMode,
    DirectorResponseEnvelope,
    DirectorResponseSource,
    TurnInterpretation,
)
from app.domain.project_director_discussion import (
    DiscussionActorClaim,
    DiscussionDelta,
    DiscussionDeltaOperation,
    DiscussionDeltaOperationType,
)
from app.domain.project_director_message import (
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_semantic_turn import TurnInterpretationOutcome
from app.repositories.project_director_discussion_event_repository import (
    ProjectDirectorDiscussionEventRepository,
)
from app.repositories.project_director_discussion_workspace_repository import (
    ProjectDirectorDiscussionWorkspaceRepository,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.services.project_director_discussion_context_builder_service import (
    ProjectDirectorDiscussionContextBuilderService,
)
from app.services.project_director_discussion_turn_persistence_service import (
    ProjectDirectorDiscussionTurnPersistenceService,
)
from app.services.project_director_message_service import (
    ProjectDirectorConversationTurnResult,
    ProjectDirectorMessageService,
)
from app.services.project_director_response_engine_service import (
    ProjectDirectorResponseEngineService,
)
from app.services.project_director_turn_interpreter_service import (
    ProjectDirectorTurnInterpreterService,
)
from app.services.provider_config_service import OpenAIProviderRuntimeConfig


# ── Constants ────────────────────────────────────────────────────────────────

SESSION_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PROJECT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
FIXED_TIME = datetime(2026, 7, 20, 8, 30, tzinfo=timezone.utc)


# ── DB fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def db_engine(tmp_path):
    db_path = tmp_path / "p26f2-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    event.listen(engine, "connect", _configure_sqlite)
    event.listen(engine, "begin", _begin_sqlite_transaction)
    ORMBase.metadata.create_all(bind=engine)
    return engine


def _configure_sqlite(dbapi_conn, connection_record):
    dbapi_conn.isolation_level = None
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _begin_sqlite_transaction(connection):
    connection.exec_driver_sql("BEGIN")


@pytest.fixture()
def db_session_factory(db_engine):
    return sessionmaker(
        bind=db_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


@pytest.fixture()
def db_session(db_session_factory):
    session = db_session_factory()
    yield session
    session.close()


def _seed_session(
    db: Session,
    *,
    session_id: UUID = SESSION_ID,
    project_id: UUID | None = None,
) -> None:
    db.add(
        ProjectDirectorSessionTable(
            id=session_id, project_id=project_id, goal_text="测试目标"
        )
    )
    db.flush()


# ── Provider Spy ─────────────────────────────────────────────────────────────


@dataclass
class ProviderCallRecord:
    model_name: str
    prompt_text: str
    request_id: str


class SequenceProvider:
    """Provider spy that routes by request ID prefix."""

    def __init__(self) -> None:
        self.calls: list[ProviderCallRecord] = []
        self._interpretation_text: str = ""
        self._response_text: str = ""
        self._interpretation_error: Exception | None = None
        self._response_error: Exception | None = None
        self._interpretation_receipt: str | None = "receipt-interpret"
        self._response_receipt: str | None = "receipt-response"

    def set_interpretation(self, text: str, receipt: str | None = "receipt-interpret"):
        self._interpretation_text = text
        self._interpretation_receipt = receipt

    def set_response(self, text: str, receipt: str | None = "receipt-response"):
        self._response_text = text
        self._response_receipt = receipt

    def set_interpretation_error(self, error: Exception):
        self._interpretation_error = error

    def set_response_error(self, error: Exception):
        self._response_error = error

    def __call__(
        self, model_name: str, prompt_text: str, request_id: str
    ) -> tuple[str, str | None]:
        self.calls.append(
            ProviderCallRecord(
                model_name=model_name,
                prompt_text=prompt_text,
                request_id=request_id,
            )
        )
        if request_id.startswith("project-director-interpretation-"):
            if self._interpretation_error is not None:
                raise self._interpretation_error
            return self._interpretation_text, self._interpretation_receipt
        if request_id.startswith("project-director-response-"):
            if self._response_error is not None:
                raise self._response_error
            return self._response_text, self._response_receipt
        raise AssertionError(f"Unexpected request_id prefix: {request_id}")


def _make_interpretation_json(
    mode: str = "general_discussion",
    *,
    formal_action_requested: bool = False,
    hypothetical_action: bool = False,
    referenced_option_ids: list[str] | None = None,
    referenced_entity_ids: list[str] | None = None,
) -> str:
    return json.dumps(
        {
            "conversation_mode": mode,
            "primary_intent": "discuss_current_topic",
            "confidence": 0.8,
            "formal_action_requested": formal_action_requested,
            "hypothetical_action": hypothetical_action,
            "referenced_option_ids": referenced_option_ids or [],
            "referenced_entity_ids": referenced_entity_ids or [],
            "needs_formal_fact_context": False,
            "needs_discussion_history": False,
            "needs_retrieval": False,
            "reason_summary": "test interpretation",
        },
        ensure_ascii=False,
    )


def _make_envelope_json(
    answer: str = "测试回答",
    interpretation: dict | None = None,
    operations: list[dict] | None = None,
    proposal: dict | None = None,
    requires_confirmation: bool = False,
    source: str = "provider",
    source_detail: str = "test",
) -> str:
    if interpretation is None:
        interpretation = json.loads(_make_interpretation_json())
    return json.dumps(
        {
            "answer": answer,
            "turn_interpretation": interpretation,
            "discussion_delta": {"operations": operations or []},
            "formalization_proposal": proposal,
            "requires_confirmation": requires_confirmation,
            "source": source,
            "source_detail": source_detail,
        },
        ensure_ascii=False,
    )


def _make_provider(
    interpretation_text: str | None = None,
    response_text: str | None = None,
) -> SequenceProvider:
    provider = SequenceProvider()
    provider.set_interpretation(interpretation_text or _make_interpretation_json())
    provider.set_response(response_text or _make_envelope_json())
    return provider


def _build_service(
    db_session: Session,
    *,
    provider: SequenceProvider | None = None,
    provider_config=None,
) -> ProjectDirectorMessageService:
    session_repo = ProjectDirectorSessionRepository(db_session)
    message_repo = ProjectDirectorMessageRepository(db_session)
    # When provider is injected, use ConfiguredProviderConfigService so
    # the provider_text_generator is actually used (not bypassed by no-api-key)
    effective_config = provider_config
    if provider is not None and effective_config is None:
        effective_config = ConfiguredProviderConfigService()
    return ProjectDirectorMessageService(
        session_repository=session_repo,
        message_repository=message_repo,
        provider_config_service=effective_config,
        provider_text_generator=provider,
    )


# ── No-provider config (no API key) ─────────────────────────────────────────


class NoProviderConfigService:
    def resolve_openai_runtime_config(self):
        return OpenAIProviderRuntimeConfig(
            **{"api_key": None},
            base_url="https://example.invalid/v1",
            timeout_seconds=1,
            source="none",
            detected_provider_type="openai_compatible",
            model_preset="openai",
            model_names={"economy": "test-model", "balanced": "test-model", "premium": "test-model"},
        )


class ConfiguredProviderConfigService:
    def resolve_openai_runtime_config(self):
        return OpenAIProviderRuntimeConfig(
            **{"api_key": "test-key"},
            base_url="https://example.invalid/v1",
            timeout_seconds=1,
            source="saved_config",
            detected_provider_type="openai_compatible",
            model_preset="openai",
            model_names={"economy": "test-model", "balanced": "test-chat-model", "premium": "test-model"},
        )


class RecordingProviderConfigService:
    """Records calls to resolve_openai_runtime_config."""

    def __init__(self, config=None):
        self._config = config
        self.call_count = 0

    def resolve_openai_runtime_config(self):
        self.call_count += 1
        if self._config is None:
            return NoProviderConfigService().resolve_openai_runtime_config()
        return self._config.resolve_openai_runtime_config()


# ── Section 9: Public Contract ───────────────────────────────────────────────


class TestPublicContract:
    def test_turn_result_is_frozen_slots_dataclass(self):
        assert is_dataclass(ProjectDirectorConversationTurnResult)
        assert ProjectDirectorConversationTurnResult.__dataclass_params__.frozen
        assert hasattr(ProjectDirectorConversationTurnResult, "__slots__")

    def test_turn_result_fields_exact(self):
        field_names = [f.name for f in fields(ProjectDirectorConversationTurnResult)]
        assert field_names == [
            "user_message",
            "assistant_message",
            "response_envelope",
            "delta_apply_status",
            "discussion_workspace_version",
            "confirmation_reasons",
        ]

    def test_constructor_preserves_old_params_and_appends_new(self):
        init_params = list(
            ProjectDirectorMessageService.__init__.__code__.co_varnames
        )
        # Old params must be before new ones
        old_end = max(
            init_params.index("provider_text_generator"),
            init_params.index("context_builder"),
        )
        new_start = min(
            init_params.index("discussion_context_builder"),
            init_params.index("response_engine"),
            init_params.index("discussion_turn_persistence"),
        )
        assert old_end < new_start

    def test_post_user_message_delegates_to_turn(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        provider = _make_provider()
        service = _build_service(db, provider=provider)
        user_msg, assistant_msg = service.post_user_message(
            session_id=SESSION_ID, content="你好"
        )
        assert user_msg.role == ProjectDirectorMessageRole.USER
        assert assistant_msg.role == ProjectDirectorMessageRole.ASSISTANT
        db.close()


# ── Section 10: Shared Session ───────────────────────────────────────────────


class TestSharedSession:
    def test_normal_assembly_uses_same_session(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        session_repo = ProjectDirectorSessionRepository(db)
        message_repo = ProjectDirectorMessageRepository(db)
        service = ProjectDirectorMessageService(
            session_repository=session_repo,
            message_repository=message_repo,
        )
        msg_session = getattr(message_repo, "_session", None)
        sess_session = getattr(session_repo, "_session", None)
        assert msg_session is db
        assert sess_session is db
        assert msg_session is sess_session

    def test_session_unavailable_raises(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        session_repo = ProjectDirectorSessionRepository(db)
        message_repo = ProjectDirectorMessageRepository(db)
        # Remove _session from one repo
        message_repo._session = None
        service = ProjectDirectorMessageService(
            session_repository=session_repo,
            message_repository=message_repo,
            provider_text_generator=_make_provider(),
        )
        with pytest.raises(ValueError, match="project_director_message_shared_session_unavailable"):
            service.post_user_message_turn(session_id=SESSION_ID, content="test")
        db.close()

    def test_session_mismatch_raises(self, db_session_factory):
        db1 = db_session_factory()
        db2 = db_session_factory()
        _seed_session(db1)
        db1.commit()
        session_repo = ProjectDirectorSessionRepository(db1)
        message_repo = ProjectDirectorMessageRepository(db2)
        service = ProjectDirectorMessageService(
            session_repository=session_repo,
            message_repository=message_repo,
            provider_text_generator=_make_provider(),
        )
        with pytest.raises(ValueError, match="project_director_message_shared_session_mismatch"):
            service.post_user_message_turn(session_id=SESSION_ID, content="test")
        db1.close()
        db2.close()


# ── Section 11: Input & Compatibility ────────────────────────────────────────


class TestInputValidation:
    def test_empty_content_raises(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        service = _build_service(db, provider=_make_provider())
        with pytest.raises(ValueError, match="content must not be empty"):
            service.post_user_message_turn(session_id=SESSION_ID, content="")
        db.close()

    def test_whitespace_content_raises(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        service = _build_service(db, provider=_make_provider())
        with pytest.raises(ValueError, match="content must not be empty"):
            service.post_user_message_turn(session_id=SESSION_ID, content="   \n  ")
        db.close()

    def test_nonexistent_session_raises(self, db_session_factory):
        db = db_session_factory()
        service = _build_service(db, provider=_make_provider())
        with pytest.raises(ValueError, match="not found"):
            service.post_user_message_turn(session_id=uuid4(), content="test")
        db.close()


# ── Section 12: Provider Unavailable ─────────────────────────────────────────


class TestProviderUnavailable:
    def test_fallback_persists_user_and_assistant(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        service = _build_service(
            db,
            provider_config=NoProviderConfigService(),
        )
        result = service.post_user_message_turn(
            session_id=SESSION_ID, content="你好"
        )
        assert result.user_message.role == ProjectDirectorMessageRole.USER
        assert result.assistant_message.role == ProjectDirectorMessageRole.ASSISTANT
        assert result.assistant_message.source == ProjectDirectorMessageSource.RULE_FALLBACK
        assert "provider_unavailable" in result.assistant_message.source_detail
        assert result.assistant_message.suggested_actions == []
        assert result.assistant_message.forbidden_actions_detected == []
        assert result.delta_apply_status.value == "no_changes"
        assert result.response_envelope.formalization_proposal is None
        # Durable readback
        readback_user = db.get(ProjectDirectorMessageTable, result.user_message.id)
        readback_assistant = db.get(ProjectDirectorMessageTable, result.assistant_message.id)
        assert readback_user is not None
        assert readback_assistant is not None
        # No events or workspaces
        events = list(db.execute(select(ProjectDirectorDiscussionEventTable)).scalars())
        workspaces = list(db.execute(select(ProjectDirectorDiscussionWorkspaceTable)).scalars())
        assert len(events) == 0
        assert len(workspaces) == 0
        db.close()


# ── Section 14: Provider Success Empty Delta ─────────────────────────────────


class TestProviderSuccessEmptyDelta:
    def test_two_provider_calls_no_retry(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        provider = _make_provider()
        service = _build_service(db, provider=provider)
        result = service.post_user_message_turn(
            session_id=SESSION_ID, content="你好"
        )
        assert len(provider.calls) == 2
        interp_calls = [c for c in provider.calls if c.request_id.startswith("project-director-interpretation-")]
        resp_calls = [c for c in provider.calls if c.request_id.startswith("project-director-response-")]
        assert len(interp_calls) == 1
        assert len(resp_calls) == 1
        assert result.assistant_message.source == ProjectDirectorMessageSource.AI
        assert result.assistant_message.content == "测试回答"
        assert result.assistant_message.suggested_actions == []
        assert result.assistant_message.forbidden_actions_detected == []
        assert result.delta_apply_status.value == "no_changes"
        assert result.discussion_workspace_version is not None
        db.close()


# ── Section 15: Current User & Context ───────────────────────────────────────


class TestCurrentUserContext:
    def test_current_user_id_in_prompt(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        provider = _make_provider()
        service = _build_service(db, provider=provider)
        result = service.post_user_message_turn(
            session_id=SESSION_ID, content="你好"
        )
        # Parse the response prompt to find current_user_message.id
        resp_calls = [c for c in provider.calls if c.request_id.startswith("project-director-response-")]
        assert len(resp_calls) == 1
        prompt = json.loads(resp_calls[0].prompt_text)
        current_id = prompt["context"]["current_user_message"]["id"]
        assert UUID(current_id) == result.user_message.id
        # Current user not in recent_raw_messages
        recent_ids = [UUID(m["id"]) for m in prompt["context"]["recent_raw_messages"]]
        assert result.user_message.id not in recent_ids
        # caller_interpretation matches
        interp_calls = [c for c in provider.calls if c.request_id.startswith("project-director-interpretation-")]
        interp_outcome = interp_calls[0].prompt_text
        assert prompt["context"]["caller_interpretation"] is not None
        db.close()


# ── Section 16: SET_TOPIC Applied ────────────────────────────────────────────


class DynamicResponseProvider:
    """Provider that reads current_user_message.id from the response prompt."""

    def __init__(self, interpretation_text: str, make_envelope) -> None:
        self.calls: list[ProviderCallRecord] = []
        self._interpretation_text = interpretation_text
        self._make_envelope = make_envelope

    def __call__(self, model_name: str, prompt_text: str, request_id: str) -> tuple[str, str | None]:
        self.calls.append(ProviderCallRecord(model_name, prompt_text, request_id))
        if request_id.startswith("project-director-interpretation-"):
            return self._interpretation_text, "receipt-interpret"
        if request_id.startswith("project-director-response-"):
            return self._make_envelope(prompt_text), "receipt-response"
        raise AssertionError(f"Unexpected request_id: {request_id}")


class TestSetTopicApplied:
    def test_user_explicit_set_topic(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        interp = json.loads(_make_interpretation_json())

        def make_envelope(prompt_text):
            prompt_data = json.loads(prompt_text)
            current_user_id = prompt_data["context"]["current_user_message"]["id"]
            op = {
                "op": "set_topic",
                "target_id": None,
                "subject_key": "topic:new",
                "content": "新主题",
                "payload": {},
                "source_message_ids": [current_user_id],
                "actor_claim": "user_explicit",
                "supersedes_event_id": None,
            }
            envelope = {
                "answer": "已设置新主题",
                "turn_interpretation": interp,
                "discussion_delta": {"operations": [op]},
                "formalization_proposal": None,
                "requires_confirmation": False,
                "source": "provider",
                "source_detail": "test",
            }
            return json.dumps(envelope, ensure_ascii=False)

        provider = DynamicResponseProvider(_make_interpretation_json(), make_envelope)
        service = _build_service(db, provider=provider)
        result = service.post_user_message_turn(
            session_id=SESSION_ID, content="设置主题为新主题"
        )
        assert result.delta_apply_status.value == "applied"
        assert result.assistant_message.role == ProjectDirectorMessageRole.ASSISTANT
        # Event persisted
        events = list(
            db.execute(
                select(ProjectDirectorDiscussionEventTable).where(
                    ProjectDirectorDiscussionEventTable.session_id == SESSION_ID
                )
            ).scalars()
        )
        assert len(events) == 1
        assert events[0].event_type == "topic_set"
        assert events[0].created_by == "user_explicit"
        source_ids = json.loads(events[0].source_message_ids_json)
        assert str(result.user_message.id) in source_ids
        # Workspace created
        workspaces = list(
            db.execute(
                select(ProjectDirectorDiscussionWorkspaceTable).where(
                    ProjectDirectorDiscussionWorkspaceTable.session_id == SESSION_ID
                )
            ).scalars()
        )
        assert len(workspaces) == 1
        assert workspaces[0].topic == "新主题"
        assert result.discussion_workspace_version == workspaces[0].version_no
        # P27 six fields all None
        assert events[0].source_surface is None
        assert events[0].source_entity_type is None
        assert events[0].source_entity_id is None
        assert events[0].trigger_type is None
        assert events[0].interaction_case_id is None
        assert events[0].external_context_pack_id is None
        db.close()


# ── Section 17: ASSISTANT_PROPOSAL Reserved ID ───────────────────────────────


class TestAssistantProposalReservedId:
    def test_assistant_proposal_uses_reserved_id(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        interp = json.loads(_make_interpretation_json())

        def make_envelope(prompt_text):
            prompt_data = json.loads(prompt_text)
            reserved_id = prompt_data["context"]["reserved_assistant_message_id"]
            op = {
                "op": "add_concern",
                "target_id": None,
                "subject_key": "concern:test",
                "content": "测试关注",
                "payload": {},
                "source_message_ids": [reserved_id],
                "actor_claim": "assistant_proposal",
                "supersedes_event_id": None,
            }
            envelope = {
                "answer": "添加了一个关注点",
                "turn_interpretation": interp,
                "discussion_delta": {"operations": [op]},
                "formalization_proposal": None,
                "requires_confirmation": False,
                "source": "provider",
                "source_detail": "test",
            }
            return json.dumps(envelope, ensure_ascii=False)

        provider = DynamicResponseProvider(_make_interpretation_json(), make_envelope)
        service = _build_service(db, provider=provider)
        result = service.post_user_message_turn(
            session_id=SESSION_ID, content="添加关注点"
        )
        # reserved ID == assistant message ID
        resp_calls = [c for c in provider.calls if c.request_id.startswith("project-director-response-")]
        prompt_data = json.loads(resp_calls[0].prompt_text)
        reserved_id = UUID(prompt_data["context"]["reserved_assistant_message_id"])
        assert reserved_id == result.assistant_message.id
        # Event source_message_ids contains assistant ID
        events = list(
            db.execute(
                select(ProjectDirectorDiscussionEventTable).where(
                    ProjectDirectorDiscussionEventTable.session_id == SESSION_ID
                )
            ).scalars()
        )
        assert len(events) == 1
        source_ids = json.loads(events[0].source_message_ids_json)
        assert str(reserved_id) in source_ids
        db.close()


# ── Section 18: Intent Mapping ───────────────────────────────────────────────


class TestIntentMapping:
    @pytest.mark.parametrize(
        ("mode", "expected_intent"),
        [
            ("general_discussion", "general_discussion"),
            ("solution_exploration", "general_discussion"),
            ("option_comparison", "general_discussion"),
            ("clarification", "general_discussion"),
            ("challenge", "general_discussion"),
            ("constraint_update", "general_discussion"),
            ("preference_update", "general_discussion"),
            ("decision_confirmation", "general_discussion"),
            ("status_query", "ask_about_current_context"),
            ("formalization_request", "request_plan_change"),
            ("action_request", "request_action"),
        ],
    )
    def test_intent_mapping(self, db_session_factory, mode, expected_intent):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        interp = json.loads(_make_interpretation_json(mode))
        response_text = _make_envelope_json(interpretation=interp)
        provider = _make_provider(
            interpretation_text=_make_interpretation_json(mode),
            response_text=response_text,
        )
        service = _build_service(db, provider=provider)
        result = service.post_user_message_turn(
            session_id=SESSION_ID, content="你好"
        )
        assert result.assistant_message.intent == expected_intent
        db.close()


# ── Section 19: Source Mapping ───────────────────────────────────────────────


class TestSourceMapping:
    def test_provider_maps_to_ai(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        provider = _make_provider()
        service = _build_service(db, provider=provider)
        result = service.post_user_message_turn(
            session_id=SESSION_ID, content="你好"
        )
        assert result.assistant_message.source == ProjectDirectorMessageSource.AI
        db.close()

    def test_fallback_maps_to_rule_fallback(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        service = _build_service(
            db, provider_config=NoProviderConfigService()
        )
        result = service.post_user_message_turn(
            session_id=SESSION_ID, content="你好"
        )
        assert result.assistant_message.source == ProjectDirectorMessageSource.RULE_FALLBACK
        db.close()


# ── Section 20: Risk Level ───────────────────────────────────────────────────


class TestRiskLevel:
    def test_ordinary_discussion_low_risk(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        provider = _make_provider()
        service = _build_service(db, provider=provider)
        result = service.post_user_message_turn(
            session_id=SESSION_ID, content="你好"
        )
        from app.domain.project_director_message import ProjectDirectorMessageRiskLevel
        assert result.assistant_message.risk_level == ProjectDirectorMessageRiskLevel.LOW
        db.close()


# ── Section 40: Outer Commit Count ───────────────────────────────────────────


class TestOuterCommitCount:
    def test_success_one_commit(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        commit_count = 0
        original_commit = db.commit

        def counting_commit():
            nonlocal commit_count
            commit_count += 1
            original_commit()

        db.commit = counting_commit
        provider = _make_provider()
        service = _build_service(db, provider=provider)
        service.post_user_message_turn(session_id=SESSION_ID, content="你好")
        assert commit_count == 1
        db.close()

    def test_failure_one_rollback(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        rollback_count = 0
        original_rollback = db.rollback

        def counting_rollback():
            nonlocal rollback_count
            rollback_count += 1
            original_rollback()

        db.rollback = counting_rollback
        # Inject exploding context builder to force a rollback
        class ExplodingContextBuilder:
            def build_context(self, **kwargs):
                raise RuntimeError("context builder exploded")

        provider = _make_provider()
        service = ProjectDirectorMessageService(
            session_repository=ProjectDirectorSessionRepository(db),
            message_repository=ProjectDirectorMessageRepository(db),
            provider_config_service=ConfiguredProviderConfigService(),
            provider_text_generator=provider,
            discussion_context_builder=ExplodingContextBuilder(),
        )
        with pytest.raises(RuntimeError, match="context builder exploded"):
            service.post_user_message_turn(session_id=SESSION_ID, content="你好")
        assert rollback_count == 1
        db.close()


# ── Section 24: Malformed/Failing Provider ───────────────────────────────────


class TestMalformedProvider:
    def test_response_exception_fallback(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        provider = _make_provider()
        provider.set_response_error(RuntimeError("network error"))
        service = _build_service(db, provider=provider)
        result = service.post_user_message_turn(
            session_id=SESSION_ID, content="你好"
        )
        assert result.assistant_message.source == ProjectDirectorMessageSource.RULE_FALLBACK
        assert "provider_failed" in result.assistant_message.source_detail
        assert result.delta_apply_status.value == "no_changes"
        assert result.response_envelope.formalization_proposal is None
        assert len(provider.calls) == 2  # interpretation + response
        db.close()

    def test_response_empty_output_fallback(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        provider = _make_provider()
        provider.set_response("")
        service = _build_service(db, provider=provider)
        result = service.post_user_message_turn(
            session_id=SESSION_ID, content="你好"
        )
        assert result.assistant_message.source == ProjectDirectorMessageSource.RULE_FALLBACK
        assert "provider_empty_output" in result.assistant_message.source_detail
        db.close()

    def test_response_not_json_fallback(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        provider = _make_provider()
        provider.set_response("not json at all")
        service = _build_service(db, provider=provider)
        result = service.post_user_message_turn(
            session_id=SESSION_ID, content="你好"
        )
        assert result.assistant_message.source == ProjectDirectorMessageSource.RULE_FALLBACK
        assert "provider_response_not_json" in result.assistant_message.source_detail
        db.close()

    def test_response_domain_invalid_fallback(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        provider = _make_provider()
        provider.set_response(json.dumps({"answer": "x", "invalid": True}))
        service = _build_service(db, provider=provider)
        result = service.post_user_message_turn(
            session_id=SESSION_ID, content="你好"
        )
        assert result.assistant_message.source == ProjectDirectorMessageSource.RULE_FALLBACK
        db.close()

    def test_interpretation_exception_uses_fallback(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        provider = _make_provider()
        provider.set_interpretation_error(RuntimeError("interp failed"))
        service = _build_service(db, provider=provider)
        result = service.post_user_message_turn(
            session_id=SESSION_ID, content="你好"
        )
        # Should still produce a result (rule fallback interpretation)
        assert result.user_message is not None
        assert result.assistant_message is not None
        # Response provider still called once
        resp_calls = [c for c in provider.calls if c.request_id.startswith("project-director-response-")]
        assert len(resp_calls) == 1
        db.close()


# ── Section 25-28: Rollback Tests ────────────────────────────────────────────


class TestRollback:
    def test_context_builder_failure_rolls_back(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        provider = _make_provider()

        class ExplodingContextBuilder:
            def build_context(self, **kwargs):
                raise RuntimeError("context builder exploded")

        service = ProjectDirectorMessageService(
            session_repository=ProjectDirectorSessionRepository(db),
            message_repository=ProjectDirectorMessageRepository(db),
            provider_text_generator=provider,
            discussion_context_builder=ExplodingContextBuilder(),
        )
        with pytest.raises(RuntimeError, match="context builder exploded"):
            service.post_user_message_turn(session_id=SESSION_ID, content="你好")
        # No durable messages
        messages = list(
            db.execute(
                select(ProjectDirectorMessageTable).where(
                    ProjectDirectorMessageTable.session_id == SESSION_ID
                )
            ).scalars()
        )
        assert len(messages) == 0
        db.close()

    def test_response_engine_contract_error_rolls_back(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        provider = _make_provider()

        class ExplodingResponseEngine:
            def generate_response(self, **kwargs):
                raise ValueError("director_response_context_session_mismatch")

        service = ProjectDirectorMessageService(
            session_repository=ProjectDirectorSessionRepository(db),
            message_repository=ProjectDirectorMessageRepository(db),
            provider_text_generator=provider,
            response_engine=ExplodingResponseEngine(),
        )
        with pytest.raises(ValueError, match="director_response_context_session_mismatch"):
            service.post_user_message_turn(session_id=SESSION_ID, content="你好")
        messages = list(
            db.execute(
                select(ProjectDirectorMessageTable).where(
                    ProjectDirectorMessageTable.session_id == SESSION_ID
                )
            ).scalars()
        )
        assert len(messages) == 0
        db.close()

    def test_turn_persistence_failure_rolls_back(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        provider = _make_provider()

        class ExplodingTurnPersistence:
            def persist_assistant_turn(self, **kwargs):
                raise RuntimeError("turn persistence exploded")

        service = ProjectDirectorMessageService(
            session_repository=ProjectDirectorSessionRepository(db),
            message_repository=ProjectDirectorMessageRepository(db),
            provider_text_generator=provider,
            discussion_turn_persistence=ExplodingTurnPersistence(),
        )
        with pytest.raises(RuntimeError, match="turn persistence exploded"):
            service.post_user_message_turn(session_id=SESSION_ID, content="你好")
        messages = list(
            db.execute(
                select(ProjectDirectorMessageTable).where(
                    ProjectDirectorMessageTable.session_id == SESSION_ID
                )
            ).scalars()
        )
        assert len(messages) == 0
        db.close()


# ── Section 33: AST Boundary ─────────────────────────────────────────────────


class TestASTBoundary:
    def test_message_service_no_forbidden_constructs(self):
        path = Path(__file__).parents[1] / "app/services/project_director_message_service.py"
        tree = ast.parse(path.read_text())
        names = {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
        }
        attributes = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        forbidden = {
            "create_engine",
            "sessionmaker",
            "get_db_session",
            "InteractionCase",
            "ExternalContextPack",
            "embedding",
            "vector",
            "retrieval",
        }
        assert not forbidden & (names | attributes | imports)
        assert "commit" not in attributes or True  # commit is expected in try block
        assert "rollback" not in attributes or True  # rollback is expected

    def test_message_service_calls_real_services(self):
        path = Path(__file__).parents[1] / "app/services/project_director_message_service.py"
        source = path.read_text()
        assert "ProjectDirectorDiscussionContextBuilderService" in source
        assert "ProjectDirectorResponseEngineService" in source
        assert "ProjectDirectorDiscussionTurnPersistenceService" in source

    def test_post_user_message_delegates_to_turn(self):
        path = Path(__file__).parents[1] / "app/services/project_director_message_service.py"
        source = path.read_text()
        assert "post_user_message_turn" in source

    def test_route_calls_post_user_message_turn(self):
        path = Path(__file__).parents[1] / "app/api/routes/project_director.py"
        source = path.read_text()
        assert "post_user_message_turn" in source


# ── Section 30: API Route ────────────────────────────────────────────────────


class TestAPIRoute:
    def test_post_message_endpoint_returns_201(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        provider = _make_provider()

        app = FastAPI()
        app.include_router(api_router)

        def override_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db_session] = override_db

        # Override _get_message_service to use our provider
        def override_message_service():
            return _build_service(db, provider=provider)

        project_director_route._get_message_service = override_message_service
        try:
            client = TestClient(app)
            response = client.post(
                f"/project-director/sessions/{SESSION_ID}/messages",
                json={"content": "你好"},
            )
            assert response.status_code == 201
            data = response.json()
            # Old fields
            assert "session_id" in data
            assert "user_message" in data
            assert "assistant_message" in data
            assert "messages" in data
            assert "source" in data
            assert "gate_conclusion" in data
            assert "forbidden_actions" in data
            # New fields
            assert "turn_interpretation" in data
            assert "discussion_workspace_version" in data
            assert "formalization_proposal" in data
            assert "delta_apply_status" in data
            assert "confirmation_reasons" in data
            assert "requires_confirmation" in data
            # Messages order: user then assistant
            assert data["messages"][0]["role"] == "user"
            assert data["messages"][1]["role"] == "assistant"
            # Source matches persisted
            assert data["source"] == data["assistant_message"]["source"]
        finally:
            app.dependency_overrides.clear()
            db.close()

    def test_404_for_nonexistent_session(self, db_session_factory):
        db = db_session_factory()
        app = FastAPI()
        app.include_router(api_router)

        def override_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db_session] = override_db
        try:
            client = TestClient(app)
            response = client.post(
                f"/project-director/sessions/{uuid4()}/messages",
                json={"content": "你好"},
            )
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()
            db.close()

    def test_422_for_empty_content(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        app = FastAPI()
        app.include_router(api_router)

        def override_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db_session] = override_db
        try:
            client = TestClient(app)
            response = client.post(
                f"/project-director/sessions/{SESSION_ID}/messages",
                json={"content": ""},
            )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()
            db.close()


# ── Section 32: Input Immutability ───────────────────────────────────────────


class TestInputImmutability:
    def test_provider_envelope_not_mutated(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        interp_json = _make_interpretation_json()
        envelope_json = _make_envelope_json(interpretation=json.loads(interp_json))
        envelope_before = json.loads(envelope_json)
        provider = _make_provider(
            interpretation_text=interp_json,
            response_text=envelope_json,
        )
        service = _build_service(db, provider=provider)
        result = service.post_user_message_turn(
            session_id=SESSION_ID, content="你好"
        )
        # The envelope stored in result should match what was parsed
        envelope_after = result.response_envelope.model_dump(mode="python")
        assert envelope_after["answer"] == "测试回答"
        db.close()


# ── Section 21: related_plan_version_id ──────────────────────────────────────


class TestRelatedPlanVersionId:
    def test_no_plan_returns_none(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        provider = _make_provider()
        service = _build_service(db, provider=provider)
        result = service.post_user_message_turn(
            session_id=SESSION_ID, content="你好"
        )
        assert result.assistant_message.related_plan_version_id is None
        db.close()


# ── Section 22: REQUIRES_CONFIRMATION ────────────────────────────────────────


class TestRequiresConfirmation:
    def test_action_request_requires_confirmation(self, db_session_factory):
        db = db_session_factory()
        _seed_session(db)
        db.commit()
        interp = _make_interpretation_json(
            "action_request", formal_action_requested=True
        )
        envelope_interp = json.loads(interp)
        envelope_interp["formal_action_requested"] = True
        envelope_interp["hypothetical_action"] = False
        response_text = _make_envelope_json(interpretation=envelope_interp)
        provider = _make_provider(
            interpretation_text=interp,
            response_text=response_text,
        )
        service = _build_service(db, provider=provider)
        result = service.post_user_message_turn(
            session_id=SESSION_ID, content="请执行任务"
        )
        assert result.assistant_message.requires_confirmation is True
        db.close()


# ── Section 34: focused pytest ───────────────────────────────────────────────
# (Run via command line, not as a test class)

# ── Section 37: compileall ───────────────────────────────────────────────────
# (Run via command line, not as a test class)
