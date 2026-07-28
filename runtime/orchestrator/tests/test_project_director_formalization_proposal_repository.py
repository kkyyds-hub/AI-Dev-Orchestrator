"""P26-H2-T3-M6-R1-B: Proposal Repository and Legacy SQLite Upgrade tests.

Covers:
- create_no_commit full round-trip with real SQLite and real Repository
- Unicode, UUID, datetime, and changes order preservation
- source_message_ids / source_event_ids order preservation
- Idempotent replay (same proposal_id + same content)
- Conflict rejection (same proposal_id + different content)
- assistant_message_id uniqueness
- get_by_id / get_active_for_session / get_by_session_workspace_target
- mark_superseded_no_commit / mark_confirmed_no_commit
- confirmed_plan_version_id / confirmed_at
- Confirmed cannot rebind to another PlanVersion
- Superseded cannot be confirmed
- Historical proposals are never physically deleted
- Legacy SQLite upgrade via real bootstrap path (migrate_database_schema)
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import (
    _PROJECT_DIRECTOR_PLAN_VERSION_INDEXES,
    _PROJECT_DIRECTOR_PLAN_VERSION_TABLE_COLUMN_UPGRADES,
    _TABLE_COLUMN_UPGRADES,
    begin_sqlite_transaction,
    configure_sqlite,
    migrate_database_schema,
)
from app.core.db_tables import (
    ORMBase,
    ProjectDirectorFormalizationProposalTable,
    ProjectDirectorMessageTable,
    ProjectDirectorPlanVersionTable,
    ProjectDirectorSessionTable,
)
from app.domain.project_director_conversation_intelligence import (
    FormalizationChange,
    FormalizationChangeType,
    FormalizationTarget,
    ordered_unique_formalization_source_event_ids,
)
from app.domain.project_director_formalization_proposal import (
    FormalizationProposalStatus,
    ProjectDirectorFormalizationProposal,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_plan_version import (
    PlanVersionStatus,
    ProjectDirectorPlanVersion,
)
from app.domain.project_director_session import (
    ProjectDirectorSession,
    ProjectDirectorSessionStatus,
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_changes(
    event_ids_per_change: list[list[UUID]],
) -> list[FormalizationChange]:
    """Build FormalizationChange list with explicit per-change source_event_ids."""
    changes = []
    for i, event_ids in enumerate(event_ids_per_change):
        changes.append(
            FormalizationChange(
                change_type=FormalizationChangeType.ADD,
                subject_key=f"subject_{i}",
                summary=f"Change summary {i} — 中文测试 🚀",
                source_event_ids=event_ids,
            )
        )
    return changes


def _make_proposal(
    *,
    session_id: UUID,
    assistant_message_id: UUID,
    workspace_version: int = 1,
    source_message_ids: list[UUID] | None = None,
    changes: list[FormalizationChange] | None = None,
    proposal_id: UUID | None = None,
    summary: str = "Proposal summary — 提案摘要 🎯",
    risk_summary: str = "Risk summary — 风险概述 ⚠️",
) -> ProjectDirectorFormalizationProposal:
    """Create a valid ProjectDirectorFormalizationProposal."""
    if changes is None:
        eid1, eid2 = uuid4(), uuid4()
        changes = _make_changes([[eid1], [eid2]])
    source_event_ids = ordered_unique_formalization_source_event_ids(changes)
    if source_message_ids is None:
        source_message_ids = [uuid4(), uuid4()]
    return ProjectDirectorFormalizationProposal(
        proposal_id=proposal_id or uuid4(),
        session_id=session_id,
        project_id=None,
        assistant_message_id=assistant_message_id,
        workspace_version=workspace_version,
        target=FormalizationTarget.PLAN_REVISION,
        summary=summary,
        changes=changes,
        source_message_ids=source_message_ids,
        source_event_ids=source_event_ids,
        risk_summary=risk_summary,
        requires_confirmation=True,
        status=FormalizationProposalStatus.PROPOSED,
    )


def _seed_session_and_message(
    db_session: Session,
) -> tuple[UUID, UUID]:
    """Insert a ProjectDirectorSession and an assistant message; return their IDs."""
    session_obj = ProjectDirectorSession(
        goal_text="Test goal — 测试目标",
        status=ProjectDirectorSessionStatus.CONFIRMED,
    )
    session_repo = ProjectDirectorSessionRepository(db_session)
    session_repo.create(session_obj)

    msg = ProjectDirectorMessage(
        session_id=session_obj.id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="Assistant reply — 助手回复",
        sequence_no=1,
        source=ProjectDirectorMessageSource.AI,
        source_detail="test_seed",
    )
    msg_repo = ProjectDirectorMessageRepository(db_session)
    msg_repo.create(msg)
    db_session.commit()
    return session_obj.id, msg.id


def _seed_plan_version(db_session: Session, session_id: UUID) -> UUID:
    """Insert a real PlanVersion row and return its ID (satisfies FK)."""
    pv = ProjectDirectorPlanVersion(
        session_id=session_id,
        version_no=1,
        status=PlanVersionStatus.DRAFT,
        plan_summary="Test plan version",
    )
    pv_repo = ProjectDirectorPlanVersionRepository(db_session)
    pv_repo.create_no_commit(pv)
    db_session.commit()
    return pv.id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sqlite_engine(tmp_path):
    """Create a real SQLite engine with full ORM schema."""
    db_path = tmp_path / "test-proposal-repo.db"
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _on_connect(connection: sqlite3.Connection, _: object) -> None:
        configure_sqlite(connection, _)

    @event.listens_for(engine, "begin")
    def _on_begin(connection) -> None:
        begin_sqlite_transaction(connection)

    ORMBase.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(sqlite_engine):
    factory = sessionmaker(
        bind=sqlite_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def repo(db_session):
    return ProjectDirectorFormalizationProposalRepository(db_session)


@pytest.fixture()
def seeded(db_session):
    """Return (session_id, assistant_message_id) with FK rows committed."""
    return _seed_session_and_message(db_session)


# ===========================================================================
# 1. create_no_commit — full round-trip
# ===========================================================================


class TestCreateNoCommitRoundTrip:
    def test_round_trip_preserves_all_fields(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        proposal = _make_proposal(session_id=session_id, assistant_message_id=msg_id)

        result = repo.create_no_commit(proposal)
        db_session.commit()

        assert result.proposal_id == proposal.proposal_id
        assert result.session_id == session_id
        assert result.assistant_message_id == msg_id
        assert result.workspace_version == proposal.workspace_version
        assert result.target == FormalizationTarget.PLAN_REVISION
        assert result.summary == proposal.summary
        assert result.risk_summary == proposal.risk_summary
        assert result.requires_confirmation is True
        assert result.status == FormalizationProposalStatus.PROPOSED
        assert result.confirmed_plan_version_id is None
        assert result.confirmed_at is None

    def test_round_trip_via_get_by_id(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        proposal = _make_proposal(session_id=session_id, assistant_message_id=msg_id)
        repo.create_no_commit(proposal)
        db_session.commit()

        fetched = repo.get_by_id(proposal.proposal_id)
        assert fetched is not None
        assert fetched.proposal_id == proposal.proposal_id
        assert fetched.summary == proposal.summary


# ===========================================================================
# 2. Unicode, UUID, datetime, and changes order preservation
# ===========================================================================


class TestFieldPreservation:
    def test_unicode_preserved(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        proposal = _make_proposal(
            session_id=session_id,
            assistant_message_id=msg_id,
            summary="Unicode: 你好世界 — héllo wörld 🌍🚀",
            risk_summary="Risk: 风险 — rïsqué ⚡",
        )
        result = repo.create_no_commit(proposal)
        db_session.commit()

        fetched = repo.get_by_id(proposal.proposal_id)
        assert fetched is not None
        assert fetched.summary == "Unicode: 你好世界 — héllo wörld 🌍🚀"
        assert fetched.risk_summary == "Risk: 风险 — rïsqué ⚡"

    def test_uuid_types_preserved(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        proposal = _make_proposal(session_id=session_id, assistant_message_id=msg_id)
        repo.create_no_commit(proposal)
        db_session.commit()

        fetched = repo.get_by_id(proposal.proposal_id)
        assert fetched is not None
        assert isinstance(fetched.proposal_id, UUID)
        assert isinstance(fetched.session_id, UUID)
        assert isinstance(fetched.assistant_message_id, UUID)
        for mid in fetched.source_message_ids:
            assert isinstance(mid, UUID)
        for eid in fetched.source_event_ids:
            assert isinstance(eid, UUID)

    def test_datetime_utc_aware(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        proposal = _make_proposal(session_id=session_id, assistant_message_id=msg_id)
        repo.create_no_commit(proposal)
        db_session.commit()

        fetched = repo.get_by_id(proposal.proposal_id)
        assert fetched is not None
        assert fetched.created_at.tzinfo is not None
        assert fetched.updated_at.tzinfo is not None

    def test_changes_order_preserved(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        eid_a, eid_b, eid_c = uuid4(), uuid4(), uuid4()
        changes = [
            FormalizationChange(
                change_type=FormalizationChangeType.REMOVE,
                subject_key="zeta",
                summary="Third change",
                source_event_ids=[eid_c],
            ),
            FormalizationChange(
                change_type=FormalizationChangeType.ADD,
                subject_key="alpha",
                summary="First change",
                source_event_ids=[eid_a],
            ),
            FormalizationChange(
                change_type=FormalizationChangeType.UPDATE,
                subject_key="beta",
                summary="Second change",
                source_event_ids=[eid_b],
            ),
        ]
        proposal = _make_proposal(
            session_id=session_id,
            assistant_message_id=msg_id,
            changes=changes,
        )
        repo.create_no_commit(proposal)
        db_session.commit()

        fetched = repo.get_by_id(proposal.proposal_id)
        assert fetched is not None
        assert len(fetched.changes) == 3
        assert fetched.changes[0].subject_key == "zeta"
        assert fetched.changes[0].change_type == FormalizationChangeType.REMOVE
        assert fetched.changes[1].subject_key == "alpha"
        assert fetched.changes[1].change_type == FormalizationChangeType.ADD
        assert fetched.changes[2].subject_key == "beta"
        assert fetched.changes[2].change_type == FormalizationChangeType.UPDATE


# ===========================================================================
# 3. source_message_ids order preservation
# ===========================================================================


class TestSourceMessageIdsOrder:
    def test_order_preserved(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        mid_1, mid_2, mid_3 = uuid4(), uuid4(), uuid4()
        proposal = _make_proposal(
            session_id=session_id,
            assistant_message_id=msg_id,
            source_message_ids=[mid_3, mid_1, mid_2],
        )
        repo.create_no_commit(proposal)
        db_session.commit()

        fetched = repo.get_by_id(proposal.proposal_id)
        assert fetched is not None
        assert fetched.source_message_ids == [mid_3, mid_1, mid_2]


# ===========================================================================
# 4. source_event_ids order preservation
# ===========================================================================


class TestSourceEventIdsOrder:
    def test_order_matches_changes_lineage(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        eid_x, eid_y, eid_z = uuid4(), uuid4(), uuid4()
        # Deliberately non-alphabetical order
        changes = _make_changes([[eid_z], [eid_x, eid_y]])
        expected_event_ids = [eid_z, eid_x, eid_y]

        proposal = _make_proposal(
            session_id=session_id,
            assistant_message_id=msg_id,
            changes=changes,
        )
        assert proposal.source_event_ids == expected_event_ids

        repo.create_no_commit(proposal)
        db_session.commit()

        fetched = repo.get_by_id(proposal.proposal_id)
        assert fetched is not None
        assert fetched.source_event_ids == expected_event_ids


# ===========================================================================
# 5. Idempotent replay — same proposal_id + same content
# ===========================================================================


class TestIdempotentReplay:
    def test_same_content_returns_existing(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        proposal = _make_proposal(session_id=session_id, assistant_message_id=msg_id)

        first = repo.create_no_commit(proposal)
        db_session.commit()

        # Replay with identical content
        replay = _make_proposal(
            session_id=session_id,
            assistant_message_id=msg_id,
            proposal_id=proposal.proposal_id,
            source_message_ids=proposal.source_message_ids,
            changes=proposal.changes,
            summary=proposal.summary,
            risk_summary=proposal.risk_summary,
            workspace_version=proposal.workspace_version,
        )
        second = repo.create_no_commit(replay)
        db_session.commit()

        assert second.proposal_id == first.proposal_id
        assert second.summary == first.summary


# ===========================================================================
# 6. Conflict rejection — same proposal_id + different content
# ===========================================================================


class TestConflictRejection:
    def test_different_summary_raises(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        proposal = _make_proposal(session_id=session_id, assistant_message_id=msg_id)
        repo.create_no_commit(proposal)
        db_session.commit()

        conflicting = _make_proposal(
            session_id=session_id,
            assistant_message_id=msg_id,
            proposal_id=proposal.proposal_id,
            source_message_ids=proposal.source_message_ids,
            changes=proposal.changes,
            summary="DIFFERENT SUMMARY",
            workspace_version=proposal.workspace_version,
        )
        with pytest.raises(ValueError, match="proposal_id_conflict"):
            repo.create_no_commit(conflicting)

    def test_different_changes_raises(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        proposal = _make_proposal(session_id=session_id, assistant_message_id=msg_id)
        repo.create_no_commit(proposal)
        db_session.commit()

        different_changes = _make_changes([[uuid4()]])
        conflicting = _make_proposal(
            session_id=session_id,
            assistant_message_id=msg_id,
            proposal_id=proposal.proposal_id,
            source_message_ids=proposal.source_message_ids,
            changes=different_changes,
            summary=proposal.summary,
            risk_summary=proposal.risk_summary,
            workspace_version=proposal.workspace_version,
        )
        with pytest.raises(ValueError, match="proposal_id_conflict"):
            repo.create_no_commit(conflicting)


# ===========================================================================
# 7. assistant_message_id uniqueness
# ===========================================================================


class TestAssistantMessageUniqueness:
    def test_duplicate_assistant_message_rejected(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        p1 = _make_proposal(session_id=session_id, assistant_message_id=msg_id)
        repo.create_no_commit(p1)
        db_session.commit()

        p2 = _make_proposal(session_id=session_id, assistant_message_id=msg_id)
        with pytest.raises(Exception):
            repo.create_no_commit(p2)
            db_session.flush()


# ===========================================================================
# 8. get_by_id
# ===========================================================================


class TestGetById:
    def test_returns_none_for_missing(self, repo):
        assert repo.get_by_id(uuid4()) is None

    def test_returns_proposal(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        proposal = _make_proposal(session_id=session_id, assistant_message_id=msg_id)
        repo.create_no_commit(proposal)
        db_session.commit()

        fetched = repo.get_by_id(proposal.proposal_id)
        assert fetched is not None
        assert fetched.proposal_id == proposal.proposal_id


# ===========================================================================
# 9. get_active_for_session
# ===========================================================================


class TestGetActiveForSession:
    def test_returns_none_when_empty(self, repo):
        assert repo.get_active_for_session(session_id=uuid4()) is None

    def test_returns_latest_active(self, repo, db_session, seeded):
        session_id, msg_id = seeded

        # Need a second assistant message for the second proposal
        msg2 = ProjectDirectorMessage(
            session_id=session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content="Second assistant reply",
            sequence_no=2,
            source=ProjectDirectorMessageSource.AI,
            source_detail="test_seed",
        )
        msg_repo = ProjectDirectorMessageRepository(db_session)
        msg_repo.create(msg2)
        db_session.commit()

        p1 = _make_proposal(
            session_id=session_id,
            assistant_message_id=msg_id,
            workspace_version=1,
        )
        repo.create_no_commit(p1)
        db_session.commit()

        p2 = _make_proposal(
            session_id=session_id,
            assistant_message_id=msg2.id,
            workspace_version=2,
        )
        repo.create_no_commit(p2)
        db_session.commit()

        active = repo.get_active_for_session(session_id=session_id)
        assert active is not None
        # Should return the highest workspace_version active proposal
        assert active.proposal_id == p2.proposal_id

    def test_excludes_superseded(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        proposal = _make_proposal(session_id=session_id, assistant_message_id=msg_id)
        repo.create_no_commit(proposal)
        db_session.commit()

        # Supersede it
        msg2 = ProjectDirectorMessage(
            session_id=session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content="Third assistant reply",
            sequence_no=3,
            source=ProjectDirectorMessageSource.AI,
            source_detail="test_seed",
        )
        msg_repo = ProjectDirectorMessageRepository(db_session)
        msg_repo.create(msg2)
        db_session.commit()

        p2 = _make_proposal(
            session_id=session_id,
            assistant_message_id=msg2.id,
            workspace_version=2,
        )
        repo.create_no_commit(p2)
        repo.mark_superseded_no_commit(
            session_id=session_id,
            workspace_version=proposal.workspace_version,
            target=FormalizationTarget.PLAN_REVISION,
            except_proposal_id=p2.proposal_id,
        )
        db_session.commit()

        active = repo.get_active_for_session(session_id=session_id)
        assert active is not None
        assert active.proposal_id == p2.proposal_id


# ===========================================================================
# 10. get_by_session_workspace_target
# ===========================================================================


class TestGetBySessionWorkspaceTarget:
    def test_filters_correctly(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        proposal = _make_proposal(
            session_id=session_id,
            assistant_message_id=msg_id,
            workspace_version=5,
        )
        repo.create_no_commit(proposal)
        db_session.commit()

        results = repo.get_by_session_workspace_target(
            session_id=session_id,
            workspace_version=5,
            target=FormalizationTarget.PLAN_REVISION,
        )
        assert len(results) == 1
        assert results[0].proposal_id == proposal.proposal_id

        # Wrong workspace_version
        results_wrong = repo.get_by_session_workspace_target(
            session_id=session_id,
            workspace_version=99,
            target=FormalizationTarget.PLAN_REVISION,
        )
        assert len(results_wrong) == 0

    def test_status_filter(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        proposal = _make_proposal(
            session_id=session_id,
            assistant_message_id=msg_id,
            workspace_version=3,
        )
        repo.create_no_commit(proposal)
        db_session.commit()

        # Filter by PROPOSED
        proposed = repo.get_by_session_workspace_target(
            session_id=session_id,
            workspace_version=3,
            target=FormalizationTarget.PLAN_REVISION,
            status=FormalizationProposalStatus.PROPOSED,
        )
        assert len(proposed) == 1

        # Filter by CONFIRMED — should be empty
        confirmed = repo.get_by_session_workspace_target(
            session_id=session_id,
            workspace_version=3,
            target=FormalizationTarget.PLAN_REVISION,
            status=FormalizationProposalStatus.CONFIRMED,
        )
        assert len(confirmed) == 0


# ===========================================================================
# 11. mark_superseded_no_commit
# ===========================================================================


class TestMarkSuperseded:
    def test_supersedes_prior_active(self, repo, db_session, seeded):
        session_id, msg_id = seeded

        msg2 = ProjectDirectorMessage(
            session_id=session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content="Another assistant reply",
            sequence_no=2,
            source=ProjectDirectorMessageSource.AI,
            source_detail="test_seed",
        )
        msg_repo = ProjectDirectorMessageRepository(db_session)
        msg_repo.create(msg2)
        db_session.commit()

        p1 = _make_proposal(
            session_id=session_id,
            assistant_message_id=msg_id,
            workspace_version=1,
        )
        p2 = _make_proposal(
            session_id=session_id,
            assistant_message_id=msg2.id,
            workspace_version=1,
        )
        repo.create_no_commit(p1)
        repo.create_no_commit(p2)
        db_session.commit()

        repo.mark_superseded_no_commit(
            session_id=session_id,
            workspace_version=1,
            target=FormalizationTarget.PLAN_REVISION,
            except_proposal_id=p2.proposal_id,
        )
        db_session.commit()

        fetched_p1 = repo.get_by_id(p1.proposal_id)
        fetched_p2 = repo.get_by_id(p2.proposal_id)
        assert fetched_p1 is not None
        assert fetched_p1.status == FormalizationProposalStatus.SUPERSEDED
        assert fetched_p2 is not None
        assert fetched_p2.status == FormalizationProposalStatus.PROPOSED


# ===========================================================================
# 12. mark_confirmed_no_commit
# ===========================================================================


class TestMarkConfirmed:
    def test_confirms_proposed(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        proposal = _make_proposal(session_id=session_id, assistant_message_id=msg_id)
        repo.create_no_commit(proposal)
        db_session.commit()

        plan_version_id = _seed_plan_version(db_session, session_id)
        confirmed_at = datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc)
        result = repo.mark_confirmed_no_commit(
            proposal_id=proposal.proposal_id,
            confirmed_plan_version_id=plan_version_id,
            confirmed_at=confirmed_at,
        )
        db_session.commit()

        assert result.status == FormalizationProposalStatus.CONFIRMED
        assert result.confirmed_plan_version_id == plan_version_id

    def test_not_found_raises(self, repo):
        with pytest.raises(ValueError, match="not_found"):
            repo.mark_confirmed_no_commit(
                proposal_id=uuid4(),
                confirmed_plan_version_id=uuid4(),
            )


# ===========================================================================
# 13. confirmed_plan_version_id
# ===========================================================================


class TestConfirmedPlanVersionId:
    def test_set_on_confirmation(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        proposal = _make_proposal(session_id=session_id, assistant_message_id=msg_id)
        repo.create_no_commit(proposal)
        db_session.commit()

        pv_id = _seed_plan_version(db_session, session_id)
        repo.mark_confirmed_no_commit(
            proposal_id=proposal.proposal_id,
            confirmed_plan_version_id=pv_id,
        )
        db_session.commit()

        fetched = repo.get_by_id(proposal.proposal_id)
        assert fetched is not None
        assert fetched.confirmed_plan_version_id == pv_id

    def test_null_before_confirmation(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        proposal = _make_proposal(session_id=session_id, assistant_message_id=msg_id)
        repo.create_no_commit(proposal)
        db_session.commit()

        fetched = repo.get_by_id(proposal.proposal_id)
        assert fetched is not None
        assert fetched.confirmed_plan_version_id is None


# ===========================================================================
# 14. confirmed_at
# ===========================================================================


class TestConfirmedAt:
    def test_set_on_confirmation(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        proposal = _make_proposal(session_id=session_id, assistant_message_id=msg_id)
        repo.create_no_commit(proposal)
        db_session.commit()

        ts = datetime(2026, 7, 29, 15, 30, 0, tzinfo=timezone.utc)
        pv_id = _seed_plan_version(db_session, session_id)
        repo.mark_confirmed_no_commit(
            proposal_id=proposal.proposal_id,
            confirmed_plan_version_id=pv_id,
            confirmed_at=ts,
        )
        db_session.commit()

        fetched = repo.get_by_id(proposal.proposal_id)
        assert fetched is not None
        assert fetched.confirmed_at is not None
        assert fetched.confirmed_at.year == 2026
        assert fetched.confirmed_at.month == 7
        assert fetched.confirmed_at.day == 29

    def test_null_before_confirmation(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        proposal = _make_proposal(session_id=session_id, assistant_message_id=msg_id)
        repo.create_no_commit(proposal)
        db_session.commit()

        fetched = repo.get_by_id(proposal.proposal_id)
        assert fetched is not None
        assert fetched.confirmed_at is None


# ===========================================================================
# 15. Confirmed cannot rebind to another PlanVersion
# ===========================================================================


class TestConfirmedRebindRejected:
    def test_rebind_different_plan_version_raises(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        proposal = _make_proposal(session_id=session_id, assistant_message_id=msg_id)
        repo.create_no_commit(proposal)
        db_session.commit()

        pv_id_1 = _seed_plan_version(db_session, session_id)
        repo.mark_confirmed_no_commit(
            proposal_id=proposal.proposal_id,
            confirmed_plan_version_id=pv_id_1,
        )
        db_session.commit()

        pv_id_2 = _seed_plan_version(db_session, session_id)
        with pytest.raises(ValueError, match="already_confirmed_conflict"):
            repo.mark_confirmed_no_commit(
                proposal_id=proposal.proposal_id,
                confirmed_plan_version_id=pv_id_2,
            )

    def test_rebind_same_plan_version_idempotent(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        proposal = _make_proposal(session_id=session_id, assistant_message_id=msg_id)
        repo.create_no_commit(proposal)
        db_session.commit()

        pv_id = _seed_plan_version(db_session, session_id)
        repo.mark_confirmed_no_commit(
            proposal_id=proposal.proposal_id,
            confirmed_plan_version_id=pv_id,
        )
        db_session.commit()

        # Same pv_id — should be idempotent
        result = repo.mark_confirmed_no_commit(
            proposal_id=proposal.proposal_id,
            confirmed_plan_version_id=pv_id,
        )
        assert result.status == FormalizationProposalStatus.CONFIRMED
        assert result.confirmed_plan_version_id == pv_id


# ===========================================================================
# 16. Superseded cannot be confirmed
# ===========================================================================


class TestSupersededCannotConfirm:
    def test_superseded_confirm_raises(self, repo, db_session, seeded):
        session_id, msg_id = seeded

        msg2 = ProjectDirectorMessage(
            session_id=session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content="Second reply for supersede test",
            sequence_no=2,
            source=ProjectDirectorMessageSource.AI,
            source_detail="test_seed",
        )
        msg_repo = ProjectDirectorMessageRepository(db_session)
        msg_repo.create(msg2)
        db_session.commit()

        p1 = _make_proposal(
            session_id=session_id,
            assistant_message_id=msg_id,
            workspace_version=1,
        )
        p2 = _make_proposal(
            session_id=session_id,
            assistant_message_id=msg2.id,
            workspace_version=1,
        )
        repo.create_no_commit(p1)
        repo.create_no_commit(p2)
        db_session.commit()

        # Supersede p1
        repo.mark_superseded_no_commit(
            session_id=session_id,
            workspace_version=1,
            target=FormalizationTarget.PLAN_REVISION,
            except_proposal_id=p2.proposal_id,
        )
        db_session.commit()

        with pytest.raises(ValueError, match="not_active"):
            repo.mark_confirmed_no_commit(
                proposal_id=p1.proposal_id,
                confirmed_plan_version_id=_seed_plan_version(db_session, session_id),
            )


# ===========================================================================
# 17. Historical proposals are never physically deleted
# ===========================================================================


class TestNoPhysicalDeletion:
    def test_superseded_row_still_exists(self, repo, db_session, seeded):
        session_id, msg_id = seeded

        msg2 = ProjectDirectorMessage(
            session_id=session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content="Reply for deletion test",
            sequence_no=2,
            source=ProjectDirectorMessageSource.AI,
            source_detail="test_seed",
        )
        msg_repo = ProjectDirectorMessageRepository(db_session)
        msg_repo.create(msg2)
        db_session.commit()

        p1 = _make_proposal(
            session_id=session_id,
            assistant_message_id=msg_id,
            workspace_version=1,
        )
        p2 = _make_proposal(
            session_id=session_id,
            assistant_message_id=msg2.id,
            workspace_version=1,
        )
        repo.create_no_commit(p1)
        repo.create_no_commit(p2)
        db_session.commit()

        repo.mark_superseded_no_commit(
            session_id=session_id,
            workspace_version=1,
            target=FormalizationTarget.PLAN_REVISION,
            except_proposal_id=p2.proposal_id,
        )
        db_session.commit()

        # p1 is superseded but still retrievable
        fetched = repo.get_by_id(p1.proposal_id)
        assert fetched is not None
        assert fetched.status == FormalizationProposalStatus.SUPERSEDED

    def test_confirmed_row_still_exists(self, repo, db_session, seeded):
        session_id, msg_id = seeded
        proposal = _make_proposal(session_id=session_id, assistant_message_id=msg_id)
        repo.create_no_commit(proposal)
        db_session.commit()

        repo.mark_confirmed_no_commit(
            proposal_id=proposal.proposal_id,
            confirmed_plan_version_id=_seed_plan_version(db_session, session_id),
        )
        db_session.commit()

        fetched = repo.get_by_id(proposal.proposal_id)
        assert fetched is not None
        assert fetched.status == FormalizationProposalStatus.CONFIRMED

    def test_all_statuses_coexist_in_db(self, repo, db_session, seeded):
        session_id, msg_id = seeded

        # Create 3 assistant messages for 3 proposals
        msg_ids = [msg_id]
        msg_repo = ProjectDirectorMessageRepository(db_session)
        for seq in (2, 3):
            m = ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=f"Reply {seq}",
                sequence_no=seq,
                source=ProjectDirectorMessageSource.AI,
                source_detail="test_seed",
            )
            msg_repo.create(m)
            msg_ids.append(m.id)
        db_session.commit()

        proposals = []
        for i, mid in enumerate(msg_ids):
            p = _make_proposal(
                session_id=session_id,
                assistant_message_id=mid,
                workspace_version=1,
            )
            repo.create_no_commit(p)
            proposals.append(p)
        db_session.commit()

        # Confirm first
        repo.mark_confirmed_no_commit(
            proposal_id=proposals[0].proposal_id,
            confirmed_plan_version_id=_seed_plan_version(db_session, session_id),
        )
        # Supersede second (third is the replacement)
        repo.mark_superseded_no_commit(
            session_id=session_id,
            workspace_version=1,
            target=FormalizationTarget.PLAN_REVISION,
            except_proposal_id=proposals[2].proposal_id,
        )
        db_session.commit()

        # All three still exist
        for p in proposals:
            fetched = repo.get_by_id(p.proposal_id)
            assert fetched is not None

        statuses = {
            repo.get_by_id(p.proposal_id).status for p in proposals
        }
        assert FormalizationProposalStatus.CONFIRMED in statuses
        assert FormalizationProposalStatus.SUPERSEDED in statuses
        assert FormalizationProposalStatus.PROPOSED in statuses


# ===========================================================================
# Legacy SQLite Upgrade Tests
# ===========================================================================


def _create_legacy_db(db_path) -> None:
    """Create a legacy SQLite database that predates the proposal schema.

    Simulates a real old database:
    - project_director_plan_versions table exists (without formalization columns)
    - At least one historical PlanVersion row exists
    - No formalization_proposal_id column
    - No proposal table
    - No proposal unique indexes
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create minimal prerequisite tables for FK references
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_director_sessions (
            id CHAR(32) PRIMARY KEY,
            project_id CHAR(32),
            goal_text TEXT NOT NULL,
            constraints TEXT NOT NULL DEFAULT '',
            status VARCHAR(20) NOT NULL DEFAULT 'draft',
            clarifying_questions_json TEXT NOT NULL DEFAULT '[]',
            clarifying_answers_json TEXT NOT NULL DEFAULT '[]',
            goal_summary TEXT NOT NULL DEFAULT '',
            confirmed_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id CHAR(32) PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            summary TEXT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            stage VARCHAR(20) NOT NULL DEFAULT 'intake',
            sop_template_code VARCHAR(100),
            stage_history_json TEXT NOT NULL DEFAULT '[]',
            team_assembly_json TEXT NOT NULL DEFAULT '[]',
            team_policy_json TEXT NOT NULL DEFAULT '{}',
            budget_policy_json TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
    """)

    # Create the OLD plan_versions table WITHOUT formalization columns
    cursor.execute("""
        CREATE TABLE project_director_plan_versions (
            id CHAR(32) PRIMARY KEY,
            session_id CHAR(32) NOT NULL
                REFERENCES project_director_sessions(id) ON DELETE CASCADE,
            project_id CHAR(32) REFERENCES projects(id) ON DELETE SET NULL,
            version_no INTEGER NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'draft',
            plan_summary TEXT NOT NULL DEFAULT '',
            phases_json TEXT NOT NULL DEFAULT '[]',
            proposed_tasks_json TEXT NOT NULL DEFAULT '[]',
            acceptance_criteria_json TEXT NOT NULL DEFAULT '[]',
            risks_json TEXT NOT NULL DEFAULT '[]',
            forbidden_actions_json TEXT NOT NULL DEFAULT '[]',
            confirmed_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
    """)

    # Insert a historical session
    session_id = uuid4().hex
    now = datetime.now(timezone.utc).isoformat(" ")
    cursor.execute(
        "INSERT INTO project_director_sessions "
        "(id, goal_text, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (session_id, "Legacy goal", "confirmed", now, now),
    )

    # Insert a historical PlanVersion (no formalization columns)
    plan_version_id = uuid4().hex
    cursor.execute(
        "INSERT INTO project_director_plan_versions "
        "(id, session_id, version_no, status, plan_summary, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (plan_version_id, session_id, 1, "confirmed", "Legacy plan", now, now),
    )

    conn.commit()
    conn.close()
    return session_id, plan_version_id


class TestLegacySqliteUpgrade:
    """Simulate a real legacy database and run the project's real bootstrap."""

    @pytest.fixture()
    def legacy_db(self, tmp_path):
        """Create a legacy DB and return (db_path, session_id, plan_version_id)."""
        db_path = tmp_path / "legacy-orchestrator.db"
        session_id, plan_version_id = _create_legacy_db(db_path)
        return db_path, session_id, plan_version_id

    def _make_engine(self, db_path):
        engine = create_engine(
            f"sqlite+pysqlite:///{db_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(engine, "connect")
        def _on_connect(connection: sqlite3.Connection, _: object) -> None:
            configure_sqlite(connection, _)

        @event.listens_for(engine, "begin")
        def _on_begin(connection) -> None:
            begin_sqlite_transaction(connection)

        return engine

    def test_preconditions(self, legacy_db):
        """Verify the legacy DB matches all preconditions before upgrade."""
        db_path, session_id, plan_version_id = legacy_db
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 1. Old plan_versions table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='project_director_plan_versions'"
        )
        assert cursor.fetchone() is not None, "plan_versions table must exist"

        # 2. At least one historical PlanVersion
        cursor.execute("SELECT COUNT(*) FROM project_director_plan_versions")
        count = cursor.fetchone()[0]
        assert count >= 1, "Must have at least one historical PlanVersion"

        # 3. No formalization_proposal_id column
        cursor.execute("PRAGMA table_info(project_director_plan_versions)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "formalization_proposal_id" not in columns

        # 4. No proposal table
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='project_director_formalization_proposals'"
        )
        assert cursor.fetchone() is None, "Proposal table must NOT exist yet"

        # 5. No proposal unique index
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name='uq_pd_plan_formalization_proposal'"
        )
        assert cursor.fetchone() is None, "Proposal unique index must NOT exist yet"

        conn.close()

    def test_bootstrap_upgrade(self, legacy_db, tmp_path):
        """Run the real bootstrap path and verify all upgrade outcomes."""
        db_path, session_id, plan_version_id = legacy_db

        # Monkey-patch settings and engine for migrate_database_schema
        engine = self._make_engine(db_path)

        import app.core.db as db_module

        original_engine = db_module.engine
        db_module.engine = engine
        try:
            # First, create all ORM tables (this is what init_database does)
            ORMBase.metadata.create_all(bind=engine)

            # Then run the real migration path
            migrate_database_schema()
        finally:
            db_module.engine = original_engine

        # Now verify all upgrade outcomes
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 7. New proposal table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='project_director_formalization_proposals'"
        )
        assert cursor.fetchone() is not None, "Proposal table must exist after upgrade"

        # 8. New nullable formalization_proposal_id column exists on plan_versions
        cursor.execute("PRAGMA table_info(project_director_plan_versions)")
        columns = {row[1]: row for row in cursor.fetchall()}
        assert "formalization_proposal_id" in columns, (
            "formalization_proposal_id column must exist after upgrade"
        )
        # Verify it's nullable (notnull == 0)
        col_info = columns["formalization_proposal_id"]
        assert col_info[3] == 0, "formalization_proposal_id must be nullable"

        # Also check other formalization columns
        assert "formalization_target" in columns
        assert "formalization_workspace_version" in columns
        assert "formalization_source_message_ids_json" in columns
        assert "formalization_source_event_ids_json" in columns

        # 9. Partial unique index exists
        cursor.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='index' "
            "AND name='uq_pd_plan_formalization_proposal'"
        )
        idx_row = cursor.fetchone()
        assert idx_row is not None, "Partial unique index must exist"
        assert "WHERE formalization_proposal_id IS NOT NULL" in idx_row[1]

        # Also check the source unique index
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name='uq_pd_plan_formalization_source'"
        )
        assert cursor.fetchone() is not None, "Source unique index must exist"

        # 10. Historical data preserved with proposal_id=null
        cursor.execute(
            "SELECT id, plan_summary, formalization_proposal_id "
            "FROM project_director_plan_versions WHERE id = ?",
            (plan_version_id,),
        )
        row = cursor.fetchone()
        assert row is not None, "Historical PlanVersion must be preserved"
        assert row[1] == "Legacy plan", "Plan summary must be unchanged"
        assert row[2] is None, "formalization_proposal_id must be NULL for legacy rows"

        # 12. Old table not rebuilt or emptied
        cursor.execute("SELECT COUNT(*) FROM project_director_plan_versions")
        count = cursor.fetchone()[0]
        assert count >= 1, "Old table must not be emptied"

        conn.close()
        engine.dispose()

    def test_second_bootstrap_idempotent(self, legacy_db):
        """Running bootstrap twice must not fail or alter data."""
        db_path, session_id, plan_version_id = legacy_db
        engine = self._make_engine(db_path)

        import app.core.db as db_module

        original_engine = db_module.engine
        db_module.engine = engine
        try:
            ORMBase.metadata.create_all(bind=engine)
            migrate_database_schema()

            # Second run — must be idempotent
            ORMBase.metadata.create_all(bind=engine)
            migrate_database_schema()
        finally:
            db_module.engine = original_engine

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Historical data still intact
        cursor.execute(
            "SELECT id, plan_summary, formalization_proposal_id "
            "FROM project_director_plan_versions WHERE id = ?",
            (plan_version_id,),
        )
        row = cursor.fetchone()
        assert row is not None, "Historical row must survive double bootstrap"
        assert row[1] == "Legacy plan"
        assert row[2] is None

        # Table count unchanged
        cursor.execute("SELECT COUNT(*) FROM project_director_plan_versions")
        assert cursor.fetchone()[0] >= 1

        # Proposal table still exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='project_director_formalization_proposals'"
        )
        assert cursor.fetchone() is not None

        conn.close()
        engine.dispose()

    def test_no_table_rebuild(self, legacy_db):
        """Verify bootstrap does not drop/recreate the plan_versions table."""
        db_path, session_id, plan_version_id = legacy_db

        # Record the original rootpage of the table
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT rootpage FROM sqlite_master WHERE type='table' "
            "AND name='project_director_plan_versions'"
        )
        original_rootpage = cursor.fetchone()[0]
        conn.close()

        engine = self._make_engine(db_path)
        import app.core.db as db_module

        original_engine = db_module.engine
        db_module.engine = engine
        try:
            ORMBase.metadata.create_all(bind=engine)
            migrate_database_schema()
        finally:
            db_module.engine = original_engine

        # rootpage should be unchanged (table was ALTERed, not rebuilt)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT rootpage FROM sqlite_master WHERE type='table' "
            "AND name='project_director_plan_versions'"
        )
        new_rootpage = cursor.fetchone()[0]
        conn.close()
        engine.dispose()

        assert new_rootpage == original_rootpage, (
            "Table rootpage changed — table was rebuilt instead of ALTERed"
        )
