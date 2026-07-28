"""P26-H2-T3-M6-R1-E — Proposal confirmation idempotency and concurrency.

Scope (verification only — this file never mutates production code):

1. Repeat confirmation:
   - the same confirmation request executed twice returns the same PlanVersion;
   - the second call reports ``idempotent_replay=True``;
   - exactly one PlanVersion exists;
   - the Proposal is bound to that single PlanVersion;
   - ``confirmed_at`` is not wrongly reset on replay.

2. Concurrency (two independent SQLAlchemy Sessions):
   - the same Proposal confirmed concurrently yields exactly one PlanVersion;
   - both results converge on the same PlanVersion (one commits, the other
     hits the unique index, rolls back, and reads the same row back);
   - no unhandled error escapes the service for the intended race;
   - no uncommitted transaction is left behind.

3. Conflicting concurrent requests (same proposal_id but a different
   workspace / target / session) must be rejected, never silently honored.

4. Plan Service spy: the plan-generation input must carry the persisted
   Proposal lineage (proposal_id, summary, risk_summary, changes,
   source_message_ids, source_event_ids, workspace_version) and must not be
   re-derived from the Workspace alone.
"""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.router import api_router
from app.core.db import begin_sqlite_transaction, configure_sqlite, get_db_session
from app.core.db_tables import (
    ORMBase,
    ProjectDirectorDiscussionEventTable,
    ProjectDirectorDiscussionWorkspaceTable,
    ProjectDirectorFormalizationProposalTable,
    ProjectDirectorMessageTable,
    ProjectDirectorPlanVersionTable,
    ProjectDirectorSessionTable,
    ProjectTable,
)
from app.domain.project_director_conversation_intelligence import (
    FormalizationChange,
    FormalizationChangeType,
    FormalizationTarget,
)
from app.domain.project_director_discussion import (
    DiscussionActorClaim,
    DiscussionEvent,
    DiscussionEventStatus,
    DiscussionEventType,
)
from app.domain.project_director_formalization_proposal import (
    FormalizationProposalStatus,
    ProjectDirectorFormalizationProposal,
)
from app.domain.project_director_message import (
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_session import ProjectDirectorSessionStatus
from app.repositories.project_director_discussion_event_repository import (
    ProjectDirectorDiscussionEventRepository,
)
from app.repositories.project_director_discussion_workspace_repository import (
    ProjectDirectorDiscussionWorkspaceRepository,
)
from app.repositories.project_director_formalization_proposal_repository import (
    ProjectDirectorFormalizationProposalRepository,
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
from app.services.project_director_discussion_formalization_service import (
    ProjectDirectorDiscussionFormalizationService,
)
from app.services.project_director_discussion_workspace_reducer_service import (
    ProjectDirectorDiscussionWorkspaceReducerService,
)
from app.services.project_director_plan_service import ProjectDirectorPlanService


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SESSION_ID = UUID("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
PROJECT_ID = UUID("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Provider / plan-service spies
# ---------------------------------------------------------------------------


class _UnconfiguredProviderConfig:
    """Forces the deterministic rule_fallback plan path (no network)."""

    def resolve_openai_runtime_config(self):
        return SimpleNamespace(
            api_key=None,
            base_url="https://provider.invalid/v1",
            timeout_seconds=1,
            detected_provider_type="openai_compatible",
            model_names={"balanced": "test-plan-model"},
        )


class _GenerateDraftSpy:
    """Wraps a real ProjectDirectorPlanService and records generation inputs.

    The formalization service drives plan generation exclusively through
    ``generate_plan_draft(session_id=..., revision_notes=...)``. Capturing the
    ``revision_notes`` proves what the plan generator was actually fed.
    """

    def __init__(self, plan_service: ProjectDirectorPlanService | None = None) -> None:
        self._plan_service = plan_service
        self.calls: list[dict] = []
        self._real_generate = (
            plan_service.generate_plan_draft if plan_service is not None else None
        )
        if plan_service is not None:
            plan_service.generate_plan_draft = self._spy  # type: ignore[method-assign]

    def _spy(self, *, session_id: UUID, revision_notes: str = ""):
        record = {"session_id": session_id, "revision_notes": revision_notes}
        try:
            record["parsed"] = json.loads(revision_notes)
        except (TypeError, json.JSONDecodeError):
            record["parsed"] = None
        self.calls.append(record)
        return self._real_generate(
            session_id=session_id, revision_notes=revision_notes
        )


# ---------------------------------------------------------------------------
# Transaction spy (instance scoped)
# ---------------------------------------------------------------------------


class SessionTransactionSpy:
    """Counts commit/rollback on one specific Session instance only."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self.commit_count = 0
        self.rollback_count = 0
        self._original_commit = session.commit
        self._original_rollback = session.rollback

    def _spy_commit(self):
        self.commit_count += 1
        return self._original_commit()

    def _spy_rollback(self):
        self.rollback_count += 1
        return self._original_rollback()

    def __enter__(self) -> "SessionTransactionSpy":
        self._session.commit = self._spy_commit  # type: ignore[method-assign]
        self._session.rollback = self._spy_rollback  # type: ignore[method-assign]
        return self

    def __exit__(self, *args) -> None:
        self._session.commit = self._original_commit  # type: ignore[method-assign]
        self._session.rollback = self._original_rollback  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------


def _seed_project_and_session(db: Session) -> None:
    db.add(
        ProjectTable(
            id=PROJECT_ID,
            name="测试项目",
            summary="摘要",
            status="active",
            stage="planning",
            created_at=T0,
            updated_at=T0,
        )
    )
    db.flush()
    db.add(
        ProjectDirectorSessionTable(
            id=SESSION_ID,
            project_id=PROJECT_ID,
            goal_text="测试目标：构建一个系统",
            constraints="",
            status=ProjectDirectorSessionStatus.CONFIRMED,
            clarifying_questions_json="[]",
            clarifying_answers_json="[]",
            goal_summary="测试目标摘要",
            confirmed_at=T0,
            created_at=T0,
            updated_at=T0,
        )
    )
    db.flush()


def _seed_message(
    db: Session,
    *,
    message_id: UUID,
    role: ProjectDirectorMessageRole,
    content: str,
    sequence_no: int,
    created_at: datetime,
) -> None:
    db.add(
        ProjectDirectorMessageTable(
            id=message_id,
            session_id=SESSION_ID,
            role=role,
            content=content,
            sequence_no=sequence_no,
            source=(
                ProjectDirectorMessageSource.AI
                if role == ProjectDirectorMessageRole.ASSISTANT
                else ProjectDirectorMessageSource.SYSTEM
            ),
            source_detail="test",
            created_at=created_at,
        )
    )
    db.flush()


def _seed_topic_event(db: Session, *, event: DiscussionEvent) -> None:
    db.add(
        ProjectDirectorDiscussionEventTable(
            id=event.id,
            session_id=event.session_id,
            project_id=event.project_id,
            sequence_no=event.sequence_no,
            event_type=event.event_type,
            subject_key=event.subject_key,
            content=event.content,
            status=event.status,
            payload_json=json.dumps(event.payload, default=str),
            source_message_ids_json=json.dumps(
                [str(mid) for mid in event.source_message_ids]
            ),
            supersedes_event_id=event.supersedes_event_id,
            created_by=event.created_by,
            confidence=event.confidence,
            idempotency_key=f"test-{event.id}",
            created_at=event.created_at,
        )
    )
    db.flush()


def _persist_workspace_from_events(
    db: Session, *, events: tuple[DiscussionEvent, ...], version_no: int
) -> None:
    reducer = ProjectDirectorDiscussionWorkspaceReducerService()
    workspace = reducer.rebuild_workspace(
        session_id=SESSION_ID,
        project_id=PROJECT_ID,
        events=events,
        version_no=version_no,
    )
    state = {
        "active_option_ids": [str(i) for i in workspace.active_option_ids],
        "preferred_option_id": (
            str(workspace.preferred_option_id)
            if workspace.preferred_option_id
            else None
        ),
        "active_constraint_ids": [str(i) for i in workspace.active_constraint_ids],
        "open_question_ids": [str(i) for i in workspace.open_question_ids],
        "temporary_conclusion_ids": [
            str(i) for i in workspace.temporary_conclusion_ids
        ],
        "confirmed_decision_ids": [
            str(i) for i in workspace.confirmed_decision_ids
        ],
        "latest_user_correction_event_id": (
            str(workspace.latest_user_correction_event_id)
            if workspace.latest_user_correction_event_id
            else None
        ),
    }
    db.add(
        ProjectDirectorDiscussionWorkspaceTable(
            session_id=SESSION_ID,
            project_id=PROJECT_ID,
            topic=workspace.topic,
            discussion_status=workspace.discussion_status,
            state_json=json.dumps(state),
            version_no=workspace.version_no,
            last_event_sequence_no=workspace.last_event_sequence_no,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
        )
    )
    db.flush()


def _make_proposal(
    *,
    proposal_id: UUID,
    assistant_message_id: UUID,
    source_message_ids: list[UUID],
    source_event_ids: list[UUID],
    workspace_version: int = 1,
    target: FormalizationTarget = FormalizationTarget.PLAN_REVISION,
    summary: str = "提案摘要",
    risk_summary: str = "风险摘要",
    created_at: datetime | None = None,
) -> ProjectDirectorFormalizationProposal:
    changes = [
        FormalizationChange(
            change_type=FormalizationChangeType.ADD,
            subject_key="topic",
            summary="新增主题",
            source_event_ids=list(source_event_ids),
        )
    ]
    stamp = created_at or (T0 + timedelta(seconds=3))
    return ProjectDirectorFormalizationProposal(
        proposal_id=proposal_id,
        session_id=SESSION_ID,
        project_id=PROJECT_ID,
        assistant_message_id=assistant_message_id,
        workspace_version=workspace_version,
        target=target,
        summary=summary,
        changes=changes,
        source_message_ids=list(source_message_ids),
        source_event_ids=list(source_event_ids),
        risk_summary=risk_summary,
        requires_confirmation=True,
        status=FormalizationProposalStatus.PROPOSED,
        created_at=stamp,
        updated_at=stamp,
    )


class SeededScenario:
    """Everything a confirmation needs, plus the ids used to build it."""

    def __init__(
        self,
        *,
        proposal_id: UUID,
        user_message_id: UUID,
        assistant_message_id: UUID,
        topic_event_id: UUID,
        workspace_version: int = 1,
    ) -> None:
        self.proposal_id = proposal_id
        self.user_message_id = user_message_id
        self.assistant_message_id = assistant_message_id
        self.topic_event_id = topic_event_id
        self.workspace_version = workspace_version


def _seed_scenario(db: Session, *, workspace_version: int = 1) -> SeededScenario:
    """Seed project/session/messages/event/workspace/proposal and commit.

    The proposal is created through the real repository so its JSON lineage is
    stored exactly as production stores it.
    """

    _seed_project_and_session(db)

    user_message_id = uuid4()
    assistant_message_id = uuid4()
    _seed_message(
        db,
        message_id=user_message_id,
        role=ProjectDirectorMessageRole.USER,
        content="用户消息",
        sequence_no=1,
        created_at=T0,
    )
    _seed_message(
        db,
        message_id=assistant_message_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="助手消息",
        sequence_no=2,
        created_at=T0 + timedelta(seconds=2),
    )

    topic_event = DiscussionEvent(
        id=uuid4(),
        session_id=SESSION_ID,
        project_id=PROJECT_ID,
        sequence_no=1,
        event_type=DiscussionEventType.TOPIC_SET,
        subject_key="topic",
        content="测试主题",
        status=DiscussionEventStatus.ACTIVE,
        payload={},
        source_message_ids=[user_message_id],
        supersedes_event_id=None,
        created_by=DiscussionActorClaim.USER_EXPLICIT,
        confidence=1.0,
        created_at=T0,
    )
    _seed_topic_event(db, event=topic_event)
    _persist_workspace_from_events(
        db, events=(topic_event,), version_no=workspace_version
    )

    proposal_id = uuid4()
    proposal = _make_proposal(
        proposal_id=proposal_id,
        assistant_message_id=assistant_message_id,
        source_message_ids=[user_message_id],
        source_event_ids=[topic_event.id],
        workspace_version=workspace_version,
    )
    ProjectDirectorFormalizationProposalRepository(db).create_no_commit(proposal)
    db.commit()

    return SeededScenario(
        proposal_id=proposal_id,
        user_message_id=user_message_id,
        assistant_message_id=assistant_message_id,
        topic_event_id=topic_event.id,
        workspace_version=workspace_version,
    )


# ---------------------------------------------------------------------------
# Service construction
# ---------------------------------------------------------------------------


def _build_service(
    db: Session, *, plan_spy: _GenerateDraftSpy | None = None
) -> ProjectDirectorDiscussionFormalizationService:
    plan_version_repo = ProjectDirectorPlanVersionRepository(db)
    session_repo = ProjectDirectorSessionRepository(db)
    plan_service = ProjectDirectorPlanService(
        plan_version_repository=plan_version_repo,
        session_repository=session_repo,
        provider_config_service=_UnconfiguredProviderConfig(),
    )
    if plan_spy is not None:
        # Attach the spy to this exact plan service instance.
        plan_spy._plan_service = plan_service
        plan_spy._real_generate = plan_service.generate_plan_draft
        plan_service.generate_plan_draft = plan_spy._spy  # type: ignore[method-assign]
    return ProjectDirectorDiscussionFormalizationService(
        session_repository=session_repo,
        discussion_workspace_repository=ProjectDirectorDiscussionWorkspaceRepository(db),
        discussion_event_repository=ProjectDirectorDiscussionEventRepository(db),
        message_repository=ProjectDirectorMessageRepository(db),
        formalization_proposal_repository=(
            ProjectDirectorFormalizationProposalRepository(db)
        ),
        plan_version_repository=plan_version_repo,
        plan_service=plan_service,
    )


def _count_plan_versions(db: Session) -> int:
    return db.execute(
        select(func.count()).select_from(ProjectDirectorPlanVersionTable)
    ).scalar_one()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_engine(tmp_path):
    db_path = tmp_path / "p26-m6-idempotency.db"
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    event.listen(engine, "connect", configure_sqlite)
    event.listen(engine, "begin", begin_sqlite_transaction)

    @event.listens_for(engine, "connect")
    def _busy_timeout(connection, _):  # give concurrent writers a chance to queue
        connection.execute("PRAGMA busy_timeout = 30000")

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
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_engine):
    app = FastAPI()
    app.include_router(api_router)
    factory = sessionmaker(
        bind=db_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    def override_get_db_session():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _confirm_kwargs(scenario: SeededScenario, *, workspace_version: int | None = None):
    return {
        "session_id": SESSION_ID,
        "proposal_id": scenario.proposal_id,
        "workspace_version": workspace_version or scenario.workspace_version,
        "target": FormalizationTarget.PLAN_REVISION,
        "user_confirmed": True,
    }


# ===========================================================================
# §1 Repeat confirmation idempotency (single session, sequential)
# ===========================================================================


class TestRepeatConfirmationIdempotency:
    """The same confirmation executed twice converges on one PlanVersion."""

    def test_second_call_returns_same_plan_version(self, db_session):
        scenario = _seed_scenario(db_session)
        service = _build_service(db_session)

        first = service.formalize_discussion(**_confirm_kwargs(scenario))
        second = service.formalize_discussion(**_confirm_kwargs(scenario))

        assert first.idempotent_replay is False
        assert second.idempotent_replay is True
        assert second.plan_version.id == first.plan_version.id
        assert second.proposal_id == scenario.proposal_id
        assert _count_plan_versions(db_session) == 1

    def test_plan_version_total_is_one(self, db_session_factory):
        setup = db_session_factory()
        try:
            scenario = _seed_scenario(setup)
        finally:
            setup.close()

        session = db_session_factory()
        try:
            service = _build_service(session)
            service.formalize_discussion(**_confirm_kwargs(scenario))
            service.formalize_discussion(**_confirm_kwargs(scenario))
            service.formalize_discussion(**_confirm_kwargs(scenario))
        finally:
            session.close()

        fresh = db_session_factory()
        try:
            assert _count_plan_versions(fresh) == 1
        finally:
            fresh.close()

    def test_proposal_bound_to_single_plan_version(self, db_session_factory):
        setup = db_session_factory()
        try:
            scenario = _seed_scenario(setup)
        finally:
            setup.close()

        session = db_session_factory()
        try:
            service = _build_service(session)
            result = service.formalize_discussion(**_confirm_kwargs(scenario))
            service.formalize_discussion(**_confirm_kwargs(scenario))
        finally:
            session.close()

        fresh = db_session_factory()
        try:
            proposal_repo = ProjectDirectorFormalizationProposalRepository(fresh)
            proposal = proposal_repo.get_by_id(scenario.proposal_id)
            assert proposal is not None
            assert proposal.status == FormalizationProposalStatus.CONFIRMED
            assert proposal.confirmed_plan_version_id == result.plan_version.id

            # Exactly one PlanVersion references this proposal.
            rows = fresh.execute(
                select(ProjectDirectorPlanVersionTable).where(
                    ProjectDirectorPlanVersionTable.formalization_proposal_id
                    == scenario.proposal_id
                )
            ).scalars().all()
            assert len(rows) == 1
            assert rows[0].id == result.plan_version.id
        finally:
            fresh.close()

    def test_confirmed_at_not_reset_on_replay(self, db_session_factory):
        setup = db_session_factory()
        try:
            scenario = _seed_scenario(setup)
        finally:
            setup.close()

        session = db_session_factory()
        try:
            service = _build_service(session)
            service.formalize_discussion(**_confirm_kwargs(scenario))
        finally:
            session.close()

        # Capture the committed confirmed_at, then replay and ensure it is stable.
        reader = db_session_factory()
        try:
            before_row = reader.get(
                ProjectDirectorFormalizationProposalTable, scenario.proposal_id
            )
            confirmed_at_before = before_row.confirmed_at
            updated_at_before = before_row.updated_at
            assert confirmed_at_before is not None
        finally:
            reader.close()

        replayer = db_session_factory()
        try:
            service = _build_service(replayer)
            replay = service.formalize_discussion(**_confirm_kwargs(scenario))
            assert replay.idempotent_replay is True
        finally:
            replayer.close()

        reader2 = db_session_factory()
        try:
            after_row = reader2.get(
                ProjectDirectorFormalizationProposalTable, scenario.proposal_id
            )
            # confirmed_at must be preserved, not reset to a newer timestamp.
            assert after_row.confirmed_at == confirmed_at_before
            assert after_row.updated_at == updated_at_before
            assert after_row.status == FormalizationProposalStatus.CONFIRMED
        finally:
            reader2.close()


# ===========================================================================
# §1b Repeat confirmation through the API client (no unhandled 500)
# ===========================================================================


class TestApiRepeatConfirmation:
    """A retried HTTP confirmation is idempotent and never a 500."""

    def test_api_double_confirm_same_plan_version(self, db_session_factory, client):
        setup = db_session_factory()
        try:
            scenario = _seed_scenario(setup)
        finally:
            setup.close()

        url = f"/project-director/sessions/{SESSION_ID}/discussion/formalize"
        body = {
            "proposal_id": str(scenario.proposal_id),
            "workspace_version": scenario.workspace_version,
            "target": "plan_revision",
            "user_confirmed": True,
        }

        first = client.post(url, json=body)
        second = client.post(url, json=body)

        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        assert first.json()["idempotent_replay"] is False
        assert second.json()["idempotent_replay"] is True
        assert (
            second.json()["plan_version"]["id"]
            == first.json()["plan_version"]["id"]
        )

        fresh = db_session_factory()
        try:
            assert _count_plan_versions(fresh) == 1
        finally:
            fresh.close()


# ===========================================================================
# §2 Concurrency — deterministic two-session race through the unique index
# ===========================================================================


class TestConcurrentConfirmationRace:
    """Two independent Sessions confirm the same Proposal concurrently.

    The race is staged so both sessions pass the pre-read and attempt the
    INSERT; the unique index ``uq_pd_plan_formalization_proposal`` then forces
    exactly one winner. The loser must roll back and read the winner's row
    back (``idempotent_replay=True``), converging on the same PlanVersion.
    """

    def test_race_converges_on_single_plan_version(self, db_session_factory):
        # ── Winner session: create + commit the competing PlanVersion ──────
        winner = db_session_factory()
        try:
            scenario = _seed_scenario(winner)
            winner_service = _build_service(winner)
            winner_result = winner_service.formalize_discussion(
                **_confirm_kwargs(scenario)
            )
            winner_plan_version_id = winner_result.plan_version.id
            assert winner_result.idempotent_replay is False
        finally:
            winner.close()

        # ── Loser session: staged pre-read so it also attempts the INSERT ──
        loser = db_session_factory()
        try:
            loser_service = _build_service(loser)
            plan_repo = loser_service._plan_version_repository
            proposal_repo = loser_service._proposal_repository

            real_get_by_proposal = plan_repo.get_by_formalization_proposal_id
            lookup_calls = [0]

            def staged_get_by_proposal(proposal_id):
                lookup_calls[0] += 1
                if lookup_calls[0] == 1:
                    # Simulate the pre-read happening before the winner commits.
                    return None
                return real_get_by_proposal(proposal_id)

            real_get_proposal = proposal_repo.get_by_id
            proposal_reads = [0]

            def staged_get_proposal(proposal_id):
                proposal_reads[0] += 1
                proposal = real_get_proposal(proposal_id)
                if proposal_reads[0] == 1 and proposal is not None:
                    # Simulate the loser reading the proposal as still PROPOSED
                    # before the winner marked it CONFIRMED.
                    return proposal.model_copy(
                        update={
                            "status": FormalizationProposalStatus.PROPOSED,
                            "confirmed_plan_version_id": None,
                        }
                    )
                return proposal

            create_calls = [0]
            real_create = plan_repo.create_no_commit

            def counted_create(plan_version):
                create_calls[0] += 1
                return real_create(plan_version)

            loser_service._plan_version_repository.get_by_formalization_proposal_id = (  # type: ignore[method-assign]
                staged_get_by_proposal
            )
            loser_service._proposal_repository.get_by_id = staged_get_proposal  # type: ignore[method-assign]
            loser_service._plan_version_repository.create_no_commit = counted_create  # type: ignore[method-assign]

            with SessionTransactionSpy(loser) as txspy:
                loser_result = loser_service.formalize_discussion(
                    **_confirm_kwargs(scenario)
                )

            # ── Strong assertions on the recovery path ─────────────────────
            assert lookup_calls[0] >= 2          # pre-read + recovery read
            assert create_calls[0] == 1          # loser attempted exactly one INSERT
            assert txspy.commit_count == 0       # loser never commits
            assert txspy.rollback_count == 1     # IntegrityError → rollback
            assert loser_result.idempotent_replay is True
            assert loser_result.plan_version.id == winner_plan_version_id
        finally:
            loser.close()

        # ── Durable end state: exactly one PlanVersion ─────────────────────
        fresh = db_session_factory()
        try:
            assert _count_plan_versions(fresh) == 1
            proposal = ProjectDirectorFormalizationProposalRepository(fresh).get_by_id(
                scenario.proposal_id
            )
            assert proposal is not None
            assert proposal.status == FormalizationProposalStatus.CONFIRMED
            assert proposal.confirmed_plan_version_id == winner_plan_version_id
        finally:
            fresh.close()

    def test_threaded_confirmation_exactly_once(self, db_session_factory):
        """Genuine thread-level concurrency over the shared SQLite file.

        Asserts the durable exactly-once invariants that must hold regardless
        of which session wins: one PlanVersion total, the Proposal confirmed
        and bound to it, every successful result pointing at that PlanVersion,
        and no uncommitted rows left behind by a conflicted loser.
        """

        setup = db_session_factory()
        try:
            scenario = _seed_scenario(setup)
        finally:
            setup.close()

        barrier = threading.Barrier(2)
        outcomes: dict[str, object] = {}

        def worker(name: str) -> None:
            session = db_session_factory()
            try:
                service = _build_service(session)
                barrier.wait()
                result = service.formalize_discussion(**_confirm_kwargs(scenario))
                outcomes[name] = {
                    "kind": "ok",
                    "plan_version_id": result.plan_version.id,
                    "idempotent_replay": result.idempotent_replay,
                }
            except Exception as exc:  # noqa: BLE001 - record, don't hide
                outcomes[name] = {
                    "kind": "conflict",
                    "exc_type": type(exc).__name__,
                    "message": str(exc)[:200],
                }
            finally:
                # A conflicted session must roll back; never leave a dangling
                # transaction open on the connection.
                if session.in_transaction():
                    session.rollback()
                session.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker, "A"), pool.submit(worker, "B")]
            for future in futures:
                future.result()

        successes = [o for o in outcomes.values() if o["kind"] == "ok"]
        conflicts = [o for o in outcomes.values() if o["kind"] == "conflict"]

        # At least one worker must succeed; a conflict, if any, must be a clean
        # transaction-safe contention (rolled back, no partial row).
        assert successes, f"no worker succeeded: {outcomes}"

        fresh = db_session_factory()
        try:
            total = _count_plan_versions(fresh)
            assert total == 1, f"expected exactly one PlanVersion, got {total}"

            sole = fresh.execute(
                select(ProjectDirectorPlanVersionTable)
            ).scalars().one()

            # Every successful result converges on the single PlanVersion.
            for ok in successes:
                assert ok["plan_version_id"] == sole.id

            # The Proposal is confirmed and bound to that single PlanVersion.
            proposal = ProjectDirectorFormalizationProposalRepository(
                fresh
            ).get_by_id(scenario.proposal_id)
            assert proposal is not None
            assert proposal.status == FormalizationProposalStatus.CONFIRMED
            assert proposal.confirmed_plan_version_id == sole.id
        finally:
            fresh.close()

        # Document (not assert away) any lock-conflict surfaced by SQLite's
        # deferred transactions; the durable state above is the guarantee.
        if conflicts:
            for conflict in conflicts:
                assert conflict["exc_type"] in {
                    "OperationalError",  # sqlite: database is locked
                    "ValueError",        # service-level conflict readback
                }, conflict


# ===========================================================================
# §3 Conflicting requests must be rejected
# ===========================================================================


class TestConflictingRequestsRejected:
    """Same proposal_id but a mismatched workspace/target/session is refused."""

    def test_wrong_workspace_version_rejected(self, db_session):
        scenario = _seed_scenario(db_session, workspace_version=1)
        service = _build_service(db_session)
        with pytest.raises(
            ValueError,
            match="proposal_workspace_mismatch|workspace_version_mismatch",
        ):
            service.formalize_discussion(
                **_confirm_kwargs(scenario, workspace_version=2)
            )
        assert _count_plan_versions(db_session) == 0

    def test_wrong_target_rejected(self, db_session):
        scenario = _seed_scenario(db_session)
        service = _build_service(db_session)
        # Only plan_revision is a valid target; any other value is invalid.
        with pytest.raises(ValueError):
            service.formalize_discussion(
                session_id=SESSION_ID,
                proposal_id=scenario.proposal_id,
                workspace_version=scenario.workspace_version,
                target="not_a_real_target",  # type: ignore[arg-type]
                user_confirmed=True,
            )
        assert _count_plan_versions(db_session) == 0

    def test_wrong_session_rejected(self, db_session_factory):
        setup = db_session_factory()
        try:
            scenario = _seed_scenario(setup)
        finally:
            setup.close()

        session = db_session_factory()
        try:
            service = _build_service(session)
            with pytest.raises(
                ValueError,
                match="proposal_not_found|proposal_session_mismatch|not found",
            ):
                service.formalize_discussion(
                    session_id=uuid4(),  # a different session
                    proposal_id=scenario.proposal_id,
                    workspace_version=scenario.workspace_version,
                    target=FormalizationTarget.PLAN_REVISION,
                    user_confirmed=True,
                )
            assert _count_plan_versions(session) == 0
        finally:
            session.close()

    def test_user_not_confirmed_rejected(self, db_session):
        scenario = _seed_scenario(db_session)
        service = _build_service(db_session)
        with pytest.raises(ValueError, match="user_confirmation_required"):
            service.formalize_discussion(
                session_id=SESSION_ID,
                proposal_id=scenario.proposal_id,
                workspace_version=scenario.workspace_version,
                target=FormalizationTarget.PLAN_REVISION,
                user_confirmed=False,
            )
        assert _count_plan_versions(db_session) == 0

    def test_unknown_proposal_rejected(self, db_session):
        _seed_scenario(db_session)
        service = _build_service(db_session)
        with pytest.raises(ValueError, match="proposal_not_found"):
            service.formalize_discussion(
                session_id=SESSION_ID,
                proposal_id=uuid4(),
                workspace_version=1,
                target=FormalizationTarget.PLAN_REVISION,
                user_confirmed=True,
            )
        assert _count_plan_versions(db_session) == 0

    def test_api_conflict_is_409_not_500(self, db_session_factory, client):
        setup = db_session_factory()
        try:
            scenario = _seed_scenario(setup)
        finally:
            setup.close()

        url = f"/project-director/sessions/{SESSION_ID}/discussion/formalize"
        # workspace_version mismatch → conflict, must not be a 500.
        resp = client.post(
            url,
            json={
                "proposal_id": str(scenario.proposal_id),
                "workspace_version": 999,
                "target": "plan_revision",
                "user_confirmed": True,
            },
        )
        assert resp.status_code == 409, resp.text


# ===========================================================================
# §4 Plan Service spy — generation input carries the Proposal lineage
# ===========================================================================


class TestPlanServiceGenerationInput:
    """Plan generation must be fed the persisted Proposal, not just workspace."""

    def test_revision_notes_carry_proposal_lineage(self, db_session):
        scenario = _seed_scenario(db_session)
        spy = _GenerateDraftSpy(plan_service=None)  # type: ignore[arg-type]
        service = _build_service(db_session, plan_spy=spy)

        result = service.formalize_discussion(**_confirm_kwargs(scenario))

        assert len(spy.calls) == 1, "plan generation must run exactly once"
        call = spy.calls[0]
        assert call["session_id"] == SESSION_ID
        parsed = call["parsed"]
        assert parsed is not None, "revision_notes must be structured JSON"

        # The generation input must carry the full persisted Proposal lineage.
        assert parsed["formalization_proposal_id"] == str(scenario.proposal_id)
        assert parsed["formalization_target"] == "plan_revision"
        assert parsed["workspace_version"] == scenario.workspace_version
        assert parsed["proposal_summary"] == "提案摘要"
        assert parsed["proposal_risk_summary"] == "风险摘要"

        # changes must be the Proposal's changes, not a workspace re-derivation.
        assert isinstance(parsed["proposal_changes"], list)
        assert parsed["proposal_changes"], "proposal_changes must not be empty"
        change = parsed["proposal_changes"][0]
        assert change["change_type"] == "add"
        assert change["subject_key"] == "topic"
        assert str(scenario.topic_event_id) in [
            str(eid) for eid in change["source_event_ids"]
        ]

        # source lineage must match the persisted Proposal exactly.
        assert parsed["proposal_source_message_ids"] == [
            str(scenario.user_message_id)
        ]
        assert parsed["proposal_source_event_ids"] == [str(scenario.topic_event_id)]

        # The resulting PlanVersion must persist that same lineage.
        assert result.plan_version.formalization_proposal_id == scenario.proposal_id
        assert result.plan_version.formalization_workspace_version == (
            scenario.workspace_version
        )
        assert list(result.plan_version.formalization_source_message_ids) == [
            scenario.user_message_id
        ]
        assert list(result.plan_version.formalization_source_event_ids) == [
            scenario.topic_event_id
        ]

    def test_replay_does_not_regenerate_plan(self, db_session):
        scenario = _seed_scenario(db_session)
        spy = _GenerateDraftSpy(plan_service=None)  # type: ignore[arg-type]
        service = _build_service(db_session, plan_spy=spy)

        service.formalize_discussion(**_confirm_kwargs(scenario))
        replay = service.formalize_discussion(**_confirm_kwargs(scenario))

        assert replay.idempotent_replay is True
        assert len(spy.calls) == 1, "replay must not re-invoke plan generation"
