"""P26-H2-T3-M6-R1-C: Proposal message transaction atomicity.

One conversation turn that carries a FormalizationProposal must persist, in a
single commit:

1. the USER message;
2. the ASSISTANT message;
3. the ``formalization_requested`` discussion Event;
4. the Workspace version bump;
5. the Proposal row;

with ``assistant_message_id`` bound to the persisted assistant message,
``Proposal.workspace_version`` equal to the persisted workspace version, and
the top-level ``source_event_ids`` lineage intact.

Every injected failure inside the transaction must roll back completely:
USER delta = 0, ASSISTANT delta = 0, Event delta = 0, Workspace version
unchanged, Proposal delta = 0.  No half-written transaction may survive.

Real Message Service, real SQLite, real Gate/Apply; the Provider is a
deterministic fake and no network is touched.
"""

from __future__ import annotations

from contextlib import nullcontext
import json
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.db_tables import (
    ORMBase,
    ProjectDirectorDiscussionEventTable,
    ProjectDirectorDiscussionWorkspaceTable,
    ProjectDirectorFormalizationProposalTable,
    ProjectDirectorMessageTable,
    ProjectDirectorSessionTable,
)
from app.domain.project_director_conversation_intelligence import (
    FormalizationChange,
    FormalizationTarget,
)
from app.domain.project_director_discussion import DiscussionEventType
from app.domain.project_director_formalization_proposal import (
    ProjectDirectorFormalizationProposal,
)
from app.domain.project_director_message import ProjectDirectorMessageRole
from app.repositories.project_director_discussion_event_repository import (
    ProjectDirectorDiscussionEventRepository,
)
from app.repositories.project_director_formalization_proposal_repository import (
    ProjectDirectorFormalizationProposalRepository,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.services.project_director_message_service import (
    ProjectDirectorMessageService,
)
from app.services.provider_config_service import OpenAIProviderRuntimeConfig


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SESSION_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
FIXED_PROPOSAL_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


# ---------------------------------------------------------------------------
# DB fixtures
# ---------------------------------------------------------------------------


def _configure_sqlite(dbapi_conn, connection_record):
    dbapi_conn.isolation_level = None
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _begin_sqlite_transaction(connection):
    connection.exec_driver_sql("BEGIN")


@pytest.fixture()
def db_engine(tmp_path):
    db_path = tmp_path / "p26-h2-m6-atomicity.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    event.listen(engine, "connect", _configure_sqlite)
    event.listen(engine, "begin", _begin_sqlite_transaction)
    ORMBase.metadata.create_all(bind=engine)
    return engine


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


# ---------------------------------------------------------------------------
# Deterministic fake provider (no network)
# ---------------------------------------------------------------------------


class ConfiguredProviderConfigService:
    """Provider config with an API key so the injected fake generator is used."""

    def resolve_openai_runtime_config(self):
        return OpenAIProviderRuntimeConfig(
            **{"api_key": "test-key"},
            base_url="https://example.invalid/v1",
            timeout_seconds=1,
            source="saved_config",
            detected_provider_type="openai_compatible",
            model_preset="openai",
            model_names={
                "economy": "test-model",
                "balanced": "test-chat-model",
                "premium": "test-model",
            },
        )


class DynamicResponseProvider:
    """Routes by request-id prefix; builds the response from the live prompt."""

    def __init__(self, interpretation_text: str, make_envelope) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self._interpretation_text = interpretation_text
        self._make_envelope = make_envelope

    def __call__(
        self, model_name: str, prompt_text: str, request_id: str
    ) -> tuple[str, str | None]:
        self.calls.append((model_name, prompt_text, request_id))
        if request_id.startswith("project-director-interpretation-"):
            return self._interpretation_text, "receipt-interpret"
        if request_id.startswith("project-director-response-"):
            return self._make_envelope(prompt_text), "receipt-response"
        raise AssertionError(f"Unexpected request_id: {request_id}")


def _interpretation_json(mode: str = "general_discussion", *, formal: bool = False) -> str:
    return json.dumps(
        {
            "conversation_mode": mode,
            "primary_intent": "discuss_current_topic",
            "confidence": 0.8,
            "formal_action_requested": formal,
            "hypothetical_action": False,
            "referenced_option_ids": [],
            "referenced_entity_ids": [],
            "needs_formal_fact_context": False,
            "needs_discussion_history": False,
            "needs_retrieval": False,
            "reason_summary": "test interpretation",
        },
        ensure_ascii=False,
    )


def _set_topic_provider() -> DynamicResponseProvider:
    interp = json.loads(_interpretation_json())

    def make_envelope(prompt_text: str) -> str:
        prompt_data = json.loads(prompt_text)
        current_user_id = prompt_data["context"]["current_user_message"]["id"]
        op = {
            "op": "set_topic",
            "target_id": None,
            "subject_key": "topic:test",
            "content": "测试主题",
            "payload": {},
            "source_message_ids": [current_user_id],
            "actor_claim": "user_explicit",
            "supersedes_event_id": None,
        }
        return json.dumps(
            {
                "answer": "已设置主题。",
                "turn_interpretation": interp,
                "discussion_delta": {"operations": [op]},
                "formalization_proposal": None,
                "requires_confirmation": False,
                "source": "provider",
                "source_detail": "test",
            },
            ensure_ascii=False,
        )

    return DynamicResponseProvider(_interpretation_json(), make_envelope)


def _formalization_provider(
    *, topic_event_id: UUID, workspace_version: int, proposal_id: UUID | None = None
) -> DynamicResponseProvider:
    interp = json.loads(_interpretation_json("formalization_request", formal=True))

    def make_envelope(prompt_text: str) -> str:
        prompt_data = json.loads(prompt_text)
        current_user_id = prompt_data["context"]["current_user_message"]["id"]
        proposal = {
            "proposal_id": str(proposal_id or uuid4()),
            "target": "plan_revision",
            "workspace_version": workspace_version + 1,
            "summary": "测试草案修改建议",
            "changes": [
                {
                    "change_type": "add",
                    "subject_key": "subject:test",
                    "summary": "新增测试内容",
                    "source_event_ids": [str(topic_event_id)],
                }
            ],
            "source_message_ids": [current_user_id],
            "risk_summary": "低风险",
            "requires_confirmation": True,
            "status": "proposed",
        }
        delta_op = {
            "op": "request_formalization",
            "target_id": None,
            "subject_key": "formalization:request",
            "content": "请求正式化",
            "payload": {},
            "source_message_ids": [current_user_id],
            "actor_claim": "user_explicit",
            "supersedes_event_id": None,
        }
        return json.dumps(
            {
                "answer": "已生成草案修改建议，需要你确认。",
                "turn_interpretation": interp,
                "discussion_delta": {"operations": [delta_op]},
                "formalization_proposal": proposal,
                "requires_confirmation": True,
                "source": "provider",
                "source_detail": "test",
            },
            ensure_ascii=False,
        )

    return DynamicResponseProvider(
        _interpretation_json("formalization_request", formal=True), make_envelope
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_service(
    db: Session, provider: DynamicResponseProvider
) -> ProjectDirectorMessageService:
    return ProjectDirectorMessageService(
        session_repository=ProjectDirectorSessionRepository(db),
        message_repository=ProjectDirectorMessageRepository(db),
        provider_config_service=ConfiguredProviderConfigService(),
        provider_text_generator=provider,
    )


def _seed_session(db: Session) -> None:
    db.add(
        ProjectDirectorSessionTable(id=SESSION_ID, project_id=None, goal_text="测试目标")
    )
    db.flush()
    db.commit()


def _seed_topic_turn(db: Session) -> dict:
    """Turn 1: set_topic → workspace v1, one topic_set event. Committed."""
    service = _build_service(db, _set_topic_provider())
    result = service.post_user_message_turn(session_id=SESSION_ID, content="设置主题")
    assert result.delta_apply_status.value == "applied"

    topic_event = db.execute(
        select(ProjectDirectorDiscussionEventTable).where(
            ProjectDirectorDiscussionEventTable.session_id == SESSION_ID
        )
    ).scalars().one()
    workspace = db.execute(
        select(ProjectDirectorDiscussionWorkspaceTable).where(
            ProjectDirectorDiscussionWorkspaceTable.session_id == SESSION_ID
        )
    ).scalars().one()
    return {
        "topic_event_id": topic_event.id,
        "workspace_version": workspace.version_no,
        "user_message_id": result.user_message.id,
        "assistant_message_id": result.assistant_message.id,
    }


def _snapshot_counts(db: Session) -> dict:
    """Committed-state snapshot of every entity the turn may touch."""

    def _count(table) -> int:
        return db.execute(select(func.count()).select_from(table)).scalar_one()

    def _count_messages(role) -> int:
        return db.execute(
            select(func.count())
            .select_from(ProjectDirectorMessageTable)
            .where(
                ProjectDirectorMessageTable.session_id == SESSION_ID,
                ProjectDirectorMessageTable.role == role,
            )
        ).scalar_one()

    workspace_version = db.execute(
        select(ProjectDirectorDiscussionWorkspaceTable.version_no).where(
            ProjectDirectorDiscussionWorkspaceTable.session_id == SESSION_ID
        )
    ).scalar_one_or_none()

    return {
        "user_messages": _count_messages(ProjectDirectorMessageRole.USER.value),
        "assistant_messages": _count_messages(ProjectDirectorMessageRole.ASSISTANT.value),
        "events": _count(ProjectDirectorDiscussionEventTable),
        "proposals": _count(ProjectDirectorFormalizationProposalTable),
        "workspace_version": workspace_version,
    }


def _fresh_counts(factory) -> dict:
    """Counts from a brand-new session — only durable, committed state."""
    verify = factory()
    try:
        return _snapshot_counts(verify)
    finally:
        verify.close()


class _TransactionSpy:
    """Instance-scoped commit/rollback counter."""

    def __init__(self, session: Session):
        self._session = session
        self.commit_count = 0
        self.rollback_count = 0
        self._original_commit = session.commit
        self._original_rollback = session.rollback

    def __enter__(self):
        def counting_commit():
            self.commit_count += 1
            return self._original_commit()

        def counting_rollback():
            self.rollback_count += 1
            return self._original_rollback()

        self._session.commit = counting_commit
        self._session.rollback = counting_rollback
        return self

    def __exit__(self, *args):
        self._session.commit = self._original_commit
        self._session.rollback = self._original_rollback


# ---------------------------------------------------------------------------
# Success: one commit persists all five artifacts
# ---------------------------------------------------------------------------


class TestProposalTransactionSuccess:
    def test_single_commit_persists_all_artifacts(self, db_session_factory, db_session):
        db = db_session_factory()
        try:
            _seed_session(db)
            turn1 = _seed_topic_turn(db)
            baseline = _fresh_counts(db_session_factory)

            provider = _formalization_provider(
                topic_event_id=turn1["topic_event_id"],
                workspace_version=turn1["workspace_version"],
            )
            service = _build_service(db, provider)
            with _TransactionSpy(db) as spy:
                result = service.post_user_message_turn(
                    session_id=SESSION_ID, content="请正式修改草案"
                )

            # Exactly one outer commit, no rollback.
            assert spy.commit_count == 1
            assert spy.rollback_count == 0

            after = _fresh_counts(db_session_factory)

            # 1. USER message persisted (+1).
            assert after["user_messages"] == baseline["user_messages"] + 1
            # 2. ASSISTANT message persisted (+1).
            assert after["assistant_messages"] == baseline["assistant_messages"] + 1
            assert result.assistant_message.id is not None
            # 3. formalization_requested Event persisted (+1).
            assert after["events"] == baseline["events"] + 1
            verify = db_session_factory()
            try:
                formalization_event = verify.execute(
                    select(ProjectDirectorDiscussionEventTable).where(
                        ProjectDirectorDiscussionEventTable.session_id == SESSION_ID,
                        ProjectDirectorDiscussionEventTable.event_type
                        == DiscussionEventType.FORMALIZATION_REQUESTED.value,
                    )
                ).scalars().one()
                assert formalization_event.sequence_no > 0
                # 4. Workspace version bumped.
                workspace_version = verify.execute(
                    select(ProjectDirectorDiscussionWorkspaceTable.version_no).where(
                        ProjectDirectorDiscussionWorkspaceTable.session_id == SESSION_ID
                    )
                ).scalar_one()
                assert workspace_version == turn1["workspace_version"] + 1
                assert after["workspace_version"] == workspace_version
                # 5. Proposal persisted (+1).
                assert after["proposals"] == baseline["proposals"] + 1
                proposal = (
                    ProjectDirectorFormalizationProposalRepository(verify)
                    .get_active_for_session(session_id=SESSION_ID)
                )
                assert proposal is not None
                # 6. assistant_message_id bound to the persisted assistant message.
                assert proposal.assistant_message_id == result.assistant_message.id
                # 7. Proposal.workspace_version equals the persisted workspace.
                assert proposal.workspace_version == workspace_version
                # 8. Top-level source_event_ids lineage intact.
                assert tuple(proposal.source_event_ids) == (turn1["topic_event_id"],)
                assert tuple(proposal.source_message_ids) == (result.user_message.id,)
            finally:
                verify.close()

            # The API envelope exposes the persisted proposal.
            envelope_proposal = result.response_envelope.formalization_proposal
            assert envelope_proposal is not None
            assert envelope_proposal.proposal_id == proposal.proposal_id
            assert envelope_proposal.workspace_version == proposal.workspace_version
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Failure injections: every one must roll back with zero durable deltas
# ---------------------------------------------------------------------------


class TestProposalTransactionAtomicity:
    """Each failure is injected after the turn's writes have flushed but before
    the outer commit; the durable state must be byte-identical to the baseline.
    """

    def _run_failing_turn(
        self,
        db_session_factory,
        *,
        patcher,
        expected_error,
        expected_match: str | None = None,
        proposal_id: UUID | None = None,
        pre_turn2=None,
    ) -> dict:
        """Seed turn 1, run turn 2 under the patch, assert full rollback.

        Returns the observed rollback/commit counts for reporting.
        """
        db = db_session_factory()
        try:
            _seed_session(db)
            turn1 = _seed_topic_turn(db)
            if pre_turn2 is not None:
                pre_turn2(db, turn1)
            baseline = _fresh_counts(db_session_factory)

            provider = _formalization_provider(
                topic_event_id=turn1["topic_event_id"],
                workspace_version=turn1["workspace_version"],
                proposal_id=proposal_id,
            )
            service = _build_service(db, provider)
            with _TransactionSpy(db) as spy, patcher:
                with pytest.raises(expected_error, match=expected_match):
                    service.post_user_message_turn(
                        session_id=SESSION_ID, content="请正式修改草案"
                    )

            # The outer transaction must roll back exactly once, never commit.
            assert spy.commit_count == 0
            assert spy.rollback_count == 1

            # Zero durable deltas across all five entity types.
            after = _fresh_counts(db_session_factory)
            assert after["user_messages"] - baseline["user_messages"] == 0
            assert after["assistant_messages"] - baseline["assistant_messages"] == 0
            assert after["events"] - baseline["events"] == 0
            assert after["proposals"] - baseline["proposals"] == 0
            assert after["workspace_version"] == baseline["workspace_version"]
            return {
                "rollback_count": spy.rollback_count,
                "commit_count": spy.commit_count,
            }
        finally:
            db.close()

    def test_f1_proposal_domain_validation_failure(self, db_session_factory):
        """Proposal domain model construction fails inside the transaction."""

        def _exploding_proposal(*args, **kwargs):
            raise ValueError("proposal_domain_validation_failed")

        counts = self._run_failing_turn(
            db_session_factory,
            patcher=patch(
                "app.services.project_director_message_service."
                "ProjectDirectorFormalizationProposal",
                _exploding_proposal,
            ),
            expected_error=ValueError,
            expected_match="proposal_domain_validation_failed",
        )
        assert counts == {"rollback_count": 1, "commit_count": 0}

    def test_f2_repository_create_flush_failure(self, db_session_factory):
        """Proposal repository create/flush fails inside the transaction."""
        counts = self._run_failing_turn(
            db_session_factory,
            patcher=patch.object(
                ProjectDirectorFormalizationProposalRepository,
                "create_no_commit",
                side_effect=RuntimeError("proposal_repository_create_failed"),
            ),
            expected_error=RuntimeError,
            expected_match="proposal_repository_create_failed",
        )
        assert counts == {"rollback_count": 1, "commit_count": 0}

    def test_f3_proposal_id_content_conflict(self, db_session_factory):
        """A persisted proposal with the same proposal_id but different content
        must fail closed and roll the whole turn back."""

        def _seed_conflicting_proposal(db: Session, turn1: dict) -> None:
            conflicting = ProjectDirectorFormalizationProposal(
                proposal_id=FIXED_PROPOSAL_ID,
                session_id=SESSION_ID,
                project_id=None,
                assistant_message_id=turn1["assistant_message_id"],
                workspace_version=turn1["workspace_version"],
                target=FormalizationTarget.PLAN_REVISION,
                summary="旧的冲突摘要",
                changes=[
                    FormalizationChange(
                        change_type="add",
                        subject_key="subject:test",
                        summary="旧变更",
                        source_event_ids=[turn1["topic_event_id"]],
                    )
                ],
                source_message_ids=[turn1["user_message_id"]],
                source_event_ids=[turn1["topic_event_id"]],
                risk_summary="旧风险",
            )
            ProjectDirectorFormalizationProposalRepository(db).create_no_commit(
                conflicting
            )
            db.commit()

        counts = self._run_failing_turn(
            db_session_factory,
            patcher=nullcontext(),  # real conflict path: no patch needed
            expected_error=ValueError,
            expected_match="project_director_formalization_proposal_id_conflict",
            proposal_id=FIXED_PROPOSAL_ID,
            pre_turn2=_seed_conflicting_proposal,
        )
        assert counts == {"rollback_count": 1, "commit_count": 0}

    def test_f4_assistant_message_unique_conflict(self, db_session_factory):
        """A unique-constraint violation on assistant_message_id at flush time
        must propagate and roll the whole turn back."""
        counts = self._run_failing_turn(
            db_session_factory,
            patcher=patch.object(
                ProjectDirectorFormalizationProposalRepository,
                "create_no_commit",
                side_effect=IntegrityError(
                    "INSERT INTO project_director_formalization_proposals",
                    {},
                    Exception(
                        "UNIQUE constraint failed: "
                        "uq_pd_formalization_proposals_assistant_message"
                    ),
                ),
            ),
            expected_error=IntegrityError,
        )
        assert counts == {"rollback_count": 1, "commit_count": 0}

    def test_f5_mark_superseded_failure(self, db_session_factory):
        """mark_superseded_no_commit fails after the new proposal was flushed."""
        counts = self._run_failing_turn(
            db_session_factory,
            patcher=patch.object(
                ProjectDirectorFormalizationProposalRepository,
                "mark_superseded_no_commit",
                side_effect=RuntimeError("mark_superseded_failed"),
            ),
            expected_error=RuntimeError,
            expected_match="mark_superseded_failed",
        )
        assert counts == {"rollback_count": 1, "commit_count": 0}

    def test_f6_lineage_references_missing_event(self, db_session_factory):
        """Proposal lineage cites an event that no longer resolves."""
        counts = self._run_failing_turn(
            db_session_factory,
            patcher=patch.object(
                ProjectDirectorDiscussionEventRepository,
                "get_by_id",
                return_value=None,
            ),
            expected_error=ValueError,
            expected_match="project_director_formalization_proposal_lineage_invalid",
        )
        assert counts == {"rollback_count": 1, "commit_count": 0}

    def test_f7_lineage_references_this_turn_formalization_event(
        self, db_session_factory
    ):
        """Proposal lineage cites this turn's own formalization_requested event,
        which the lineage gate must reject."""

        def _return_formalization_requested_event(self, *, event_id):
            row = self._session.execute(
                select(ProjectDirectorDiscussionEventTable).where(
                    ProjectDirectorDiscussionEventTable.session_id == SESSION_ID,
                    ProjectDirectorDiscussionEventTable.event_type
                    == DiscussionEventType.FORMALIZATION_REQUESTED.value,
                )
            ).scalars().first()
            return self._to_domain(row) if row is not None else None

        counts = self._run_failing_turn(
            db_session_factory,
            patcher=patch.object(
                ProjectDirectorDiscussionEventRepository,
                "get_by_id",
                _return_formalization_requested_event,
            ),
            expected_error=ValueError,
            expected_match="project_director_formalization_proposal_lineage_invalid",
        )
        assert counts == {"rollback_count": 1, "commit_count": 0}
