"""C3-B persistence-time governance for runtime formalization proposals."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, select, update
from sqlalchemy.orm import sessionmaker

from app.core.db import begin_sqlite_transaction, configure_sqlite
from app.core.db_tables import (
    AgentSessionTable,
    ORMBase,
    ProjectDirectorDiscussionEventTable,
    ProjectDirectorDiscussionWorkspaceTable,
    ProjectDirectorFormalizationProposalTable,
    ProjectDirectorMessageTable,
    ProjectDirectorPlanVersionTable,
    ProjectDirectorSessionTable,
    ProjectTable,
    RunTable,
    TaskTable,
)
from app.domain.director_runtime_protocol import (
    DIRECTOR_RUNTIME_SCHEMA_VERSION,
    parse_director_turn_result,
    validate_director_runtime_request,
)
from app.domain.project_director_discussion import DiscussionEventStatus
from app.domain.project_director_formalization_proposal import (
    FormalizationProposalStatus,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.repositories.project_director_formalization_proposal_repository import (
    ProjectDirectorFormalizationProposalRepository,
)
from app.repositories.project_director_discussion_workspace_repository import (
    ProjectDirectorDiscussionWorkspaceRepository,
)
from app.repositories.project_director_discussion_event_repository import (
    ProjectDirectorDiscussionEventRepository,
)
from app.services.director_runtime_result_discussion_admission_service import (
    DirectorRuntimeResultDiscussionAdmissionService,
)
from app.services.director_runtime_result_discussion_persistence_service import (
    DirectorRuntimeDiscussionPersistenceResult,
    DirectorRuntimeDiscussionPersistenceStatus,
    DirectorRuntimeResultDiscussionPersistenceService,
)
from app.services.director_runtime_result_formalization_admission_service import (
    DirectorRuntimeResultFormalizationAdmissionService,
)
from app.services.director_runtime_result_formalization_persistence_service import (
    DirectorRuntimeFormalizationPersistenceError,
    DirectorRuntimeFormalizationPersistenceStatus,
    DirectorRuntimeResultFormalizationPersistenceService,
)


PROJECT_ID = UUID("11111111-1111-1111-1111-111111111111")
SESSION_ID = UUID("22222222-2222-2222-2222-222222222222")
USER_ID = UUID("33333333-3333-3333-3333-333333333333")
PREVIOUS_ASSISTANT_ID = UUID("44444444-4444-4444-4444-444444444444")
ASSISTANT_ID = UUID("55555555-5555-5555-5555-555555555555")
PROPOSAL_ID = UUID("66666666-6666-6666-6666-666666666666")
FIXED_TIME = datetime(2026, 8, 31, 8, 0, tzinfo=timezone.utc)
PROPOSAL_TIME = datetime(2030, 1, 1, tzinfo=timezone.utc)


@pytest.fixture()
def factory(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'c3b.db'}")
    event.listen(engine, "connect", configure_sqlite)
    event.listen(engine, "begin", begin_sqlite_transaction)
    ORMBase.metadata.create_all(bind=engine)
    try:
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        engine.dispose()


def _request(*, message_id=USER_ID, workspace_version=None):
    return validate_director_runtime_request(
        {
            "schema_version": DIRECTOR_RUNTIME_SCHEMA_VERSION,
            "request_id": "c3-b-request",
            "project_id": str(PROJECT_ID),
            "session_id": str(SESSION_ID),
            "message_id": str(message_id),
            "current_user_message": {
                "content": "Please formalize the current discussion.",
                "occurred_at": "2026-08-31T08:00:00Z",
                "actor_claim": "user",
            },
            "authoritative_facts": {},
            "active_discussion_workspace": (
                None if workspace_version is None else {"version_no": workspace_version}
            ),
            "relevant_discussion_events": [],
            "active_formalization": {"proposal": None, "plan_version": None},
            "governance_boundaries": {
                "authoritative_write": False,
                "director_may_modify_code": False,
                "formalization_requires_explicit_request": True,
                "confirmation_is_separate": True,
                "execution_boundary": "no_task_run_agent_session_before_execution",
            },
            "available_skills": [],
            "available_tools": [],
            "permission_context": {},
            "runtime_config": {
                "model_id": "c3-b-model",
                "provider_profile_id": "c3-b-profile",
                "timeout_ms": 1000.0,
                "max_tool_rounds": 0,
            },
        }
    )


def _result(*, delta=None, proposal=None):
    return parse_director_turn_result(
        {
            "schema_version": DIRECTOR_RUNTIME_SCHEMA_VERSION,
            "request_id": "c3-b-request",
            "response_text": "Runtime response.",
            "turn_semantics": {
                "conversation_mode": "formalization_request",
                "formal_action_requested": True,
                "hypothetical_action": False,
                "confidence": 0.8,
            },
            "discussion_lifecycle": {"observed_status": None, "suggested_next_status": None},
            "discussion_delta_candidate": delta,
            "formalization": {"proposal_candidate": proposal, "readiness": "candidate"},
            "tool_activity": [],
            "source_references": [],
            "runtime_metadata": {
                "runtime_state": "ready",
                "model_id": "c3-b-model",
                "provider_profile_id": "c3-b-profile",
                "usage": {},
                "duration_ms": 1.0,
                "attempt": 0,
            },
            "error": None,
        },
        expected_request_id="c3-b-request",
    )


def _message(*, message_id, role, sequence_no):
    return ProjectDirectorMessage(
        id=message_id,
        session_id=SESSION_ID,
        role=role,
        content="Please formalize the current discussion.",
        sequence_no=sequence_no,
        related_project_id=PROJECT_ID,
        source=(
            ProjectDirectorMessageSource.AI
            if role is ProjectDirectorMessageRole.ASSISTANT
            else ProjectDirectorMessageSource.SYSTEM
        ),
        source_detail="director_runtime",
        created_at=FIXED_TIME,
    )


def _seed(db):
    db.add(ProjectTable(id=PROJECT_ID, name="C3-B", summary="C3-B", status="active", stage="intake", created_at=FIXED_TIME, updated_at=FIXED_TIME))
    db.flush()
    db.add(ProjectDirectorSessionTable(id=SESSION_ID, project_id=PROJECT_ID, goal_text="C3-B"))
    db.flush()
    user = _message(message_id=USER_ID, role=ProjectDirectorMessageRole.USER, sequence_no=1)
    db.add(ProjectDirectorMessageTable(
        id=user.id, session_id=user.session_id, role=user.role, content=user.content,
        sequence_no=user.sequence_no, related_project_id=user.related_project_id,
        source=user.source, source_detail=user.source_detail, created_at=user.created_at,
    ))
    db.commit()
    return user


def _delta(*, op, source_message_ids, actor_claim):
    return {
        "operations": [{
            "op": op,
            "target_id": None,
            "subject_key": "c3-b-topic",
            "content": "Govern the C3-B topic.",
            "payload": {},
            "source_message_ids": [str(item) for item in source_message_ids],
            "actor_claim": actor_claim,
            "supersedes_event_id": None,
        }]
    }


def _formalization_delta():
    return _delta(
        op="request_formalization",
        source_message_ids=[USER_ID],
        actor_claim="user_explicit",
    )


def _proposal(*, event_id, workspace_version, proposal_id=PROPOSAL_ID, summary="Govern the current topic."):
    return {
        "proposal_id": str(proposal_id),
        "target": "plan_revision",
        "workspace_version": workspace_version,
        "summary": summary,
        "changes": [{
            "change_type": "update",
            "subject_key": "c3-b-topic",
            "summary": "Use the governed topic.",
            "source_event_ids": [str(event_id)],
        }],
        "source_message_ids": [str(USER_ID)],
        "source_event_ids": [str(event_id)],
        "risk_summary": "Needs user confirmation.",
        "requires_confirmation": True,
        "status": "proposed",
    }


def _persist_turn(db, *, request, result, assistant_id, sequence_no, available_messages, current_events, current_workspace, start_sequence_no):
    admission = DirectorRuntimeResultDiscussionAdmissionService().admit(
        request=request,
        result=result,
        assistant_message_id=assistant_id,
        assistant_message_sequence_no=sequence_no,
        available_messages=available_messages,
        current_events=current_events,
        current_workspace=current_workspace,
        start_sequence_no=start_sequence_no,
        occurred_at=FIXED_TIME,
    )
    return DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
        admission=admission, available_messages=available_messages
    )


def _prepare_governed(db, *, proposal_id=PROPOSAL_ID, assistant_id=ASSISTANT_ID):
    user = _seed(db)
    first = _persist_turn(
        db,
        request=_request(),
        result=_result(delta=_delta(op="set_topic", source_message_ids=[PREVIOUS_ASSISTANT_ID], actor_claim="assistant_proposal")),
        assistant_id=PREVIOUS_ASSISTANT_ID,
        sequence_no=2,
        available_messages=[user],
        current_events=[],
        current_workspace=None,
        start_sequence_no=1,
    )
    assert first.persisted_turn is not None
    db.commit()
    pre_event = db.execute(select(ProjectDirectorDiscussionEventTable)).scalar_one()
    pre_workspace = first.persisted_turn.delta_apply_result.workspace
    request = _request(workspace_version=pre_workspace.version_no)
    result = _result(
        delta=_formalization_delta(),
        proposal=_proposal(event_id=pre_event.id, workspace_version=pre_workspace.version_no, proposal_id=proposal_id),
    )
    discussion_persistence = _persist_turn(
        db,
        request=request,
        result=result,
        assistant_id=assistant_id,
        sequence_no=3,
        available_messages=[user, first.persisted_turn.assistant_message],
        current_events=[pre_event],
        current_workspace=pre_workspace,
        start_sequence_no=2,
    )
    admission = DirectorRuntimeResultFormalizationAdmissionService(session=db).admit(
        request=request,
        result=result,
        discussion_persistence=discussion_persistence,
        occurred_at=PROPOSAL_TIME,
    )
    return request, result, discussion_persistence, admission, pre_workspace


def _persist(db, *, admission, request, result, discussion_persistence, repository=None):
    return DirectorRuntimeResultFormalizationPersistenceService(
        session=db,
        proposal_repository=repository,
    ).persist_admitted_candidate(
        admission=admission,
        request=request,
        result=result,
        discussion_persistence=discussion_persistence,
        occurred_at=PROPOSAL_TIME,
    )


def _proposal_rows(db):
    return db.execute(select(ProjectDirectorFormalizationProposalTable)).scalars().all()


def test_b1_first_persistence_creates_proposed_proposal(factory):
    with factory() as db:
        request, result, persisted, admission, _ = _prepare_governed(db)
        outcome = _persist(db, admission=admission, request=request, result=result, discussion_persistence=persisted)

        assert outcome.status is DirectorRuntimeFormalizationPersistenceStatus.PERSISTED
        assert outcome.stored_proposal is not None
        assert outcome.stored_proposal.status is FormalizationProposalStatus.PROPOSED
        assert outcome.stored_proposal.requires_confirmation is True
        assert outcome.stored_proposal.confirmed_plan_version_id is None
        assert outcome.stored_proposal.confirmed_at is None
        assert len(_proposal_rows(db)) == 1
        assert not db.execute(select(ProjectDirectorPlanVersionTable)).scalars().all()
        assert not db.execute(select(TaskTable)).scalars().all()
        assert not db.execute(select(RunTable)).scalars().all()
        assert not db.execute(select(AgentSessionTable)).scalars().all()


def test_b2_not_admitted_returns_no_write(factory):
    with factory() as db:
        _seed(db)
        request = _request()
        result = _result(proposal=None)
        no_turn = DirectorRuntimeDiscussionPersistenceResult(
            status=DirectorRuntimeDiscussionPersistenceStatus.NOT_ADMITTED,
            persisted_turn=None,
            no_admission_reason="runtime_error",
        )
        empty = DirectorRuntimeResultFormalizationAdmissionService(session=db).admit(
            request=request,
            result=result,
            discussion_persistence=no_turn,
            occurred_at=PROPOSAL_TIME,
        )
        outcome = _persist(
            db,
            admission=empty,
            request=request,
            result=result,
            discussion_persistence=no_turn,
        )

        assert outcome.status is DirectorRuntimeFormalizationPersistenceStatus.NOT_ADMITTED
        assert outcome.no_admission_reason == "no_formalization_candidate"
        assert not _proposal_rows(db)


def test_b3_forged_admission_mismatch_writes_nothing(factory):
    with factory() as db:
        request, result, persisted, admission, _ = _prepare_governed(db)
        assert admission.governed_proposal_candidate is not None
        forged = replace(
            admission,
            governed_proposal_candidate=admission.governed_proposal_candidate.model_copy(update={"summary": "forged"}),
        )

        with pytest.raises(DirectorRuntimeFormalizationPersistenceError, match="admission_mismatch"):
            _persist(db, admission=forged, request=request, result=result, discussion_persistence=persisted)
        assert not _proposal_rows(db)


def test_b4_workspace_drift_rejects_stale_candidate(factory):
    with factory() as db:
        request, result, persisted, admission, pre_workspace = _prepare_governed(db)
        current = persisted.persisted_turn.delta_apply_result.workspace
        ProjectDirectorDiscussionWorkspaceRepository(db).update_if_version(
            workspace=current.model_copy(update={"version_no": current.version_no + 1}),
            expected_version_no=current.version_no,
        )

        with pytest.raises(DirectorRuntimeFormalizationPersistenceError, match="workspace_stale"):
            _persist(db, admission=admission, request=request, result=result, discussion_persistence=persisted)
        assert not _proposal_rows(db)
        assert pre_workspace.version_no + 2 == current.version_no + 1


def test_b5_lineage_drift_rejects_before_write(factory):
    with factory() as db:
        request, result, persisted, admission, _ = _prepare_governed(db)
        source_event_id = admission.source_events[0].id
        db.execute(
            update(ProjectDirectorDiscussionEventTable)
            .where(ProjectDirectorDiscussionEventTable.id == source_event_id)
            .values(status=DiscussionEventStatus.HISTORICAL.value)
        )

        with pytest.raises(ValueError, match="workspace_projection_mismatch"):
            _persist(db, admission=admission, request=request, result=result, discussion_persistence=persisted)
        assert not _proposal_rows(db)


def test_b6_equivalent_replay_is_reported_without_new_row(factory):
    with factory() as db:
        request, result, persisted, admission, _ = _prepare_governed(db)
        first = _persist(db, admission=admission, request=request, result=result, discussion_persistence=persisted)
        replay = _persist(db, admission=admission, request=request, result=result, discussion_persistence=persisted)

        assert first.status is DirectorRuntimeFormalizationPersistenceStatus.PERSISTED
        assert replay.status is DirectorRuntimeFormalizationPersistenceStatus.REPLAYED
        assert len(_proposal_rows(db)) == 1


def test_b7_same_id_conflict_preserves_existing_proposal(factory):
    with factory() as db:
        request, result, persisted, admission, _ = _prepare_governed(db)
        _persist(db, admission=admission, request=request, result=result, discussion_persistence=persisted)
        conflicting = _result(
            delta=_formalization_delta(),
            proposal={**result.formalization.proposal_candidate, "summary": "different"},
        )
        fresh = DirectorRuntimeResultFormalizationAdmissionService(session=db).admit(
            request=request, result=conflicting, discussion_persistence=persisted, occurred_at=PROPOSAL_TIME
        )

        with pytest.raises(ValueError, match="project_director_formalization_proposal_id_conflict"):
            _persist(db, admission=fresh, request=request, result=conflicting, discussion_persistence=persisted)
        assert _proposal_rows(db)[0].proposal_json.find("Govern the current topic.") >= 0


def test_b8_replacement_supersedes_same_workspace_target(factory):
    with factory() as db:
        request, result, persisted, admission, _ = _prepare_governed(db)
        prior_id = uuid4()
        prior = admission.governed_proposal_candidate.model_copy(
            update={
                "proposal_id": prior_id,
                "assistant_message_id": PREVIOUS_ASSISTANT_ID,
            }
        )
        ProjectDirectorFormalizationProposalRepository(db).create_no_commit(prior)
        outcome = _persist(db, admission=admission, request=request, result=result, discussion_persistence=persisted)

        rows = {row.proposal_id: row.status for row in _proposal_rows(db)}
        assert outcome.status is DirectorRuntimeFormalizationPersistenceStatus.PERSISTED
        assert rows[prior_id] == FormalizationProposalStatus.SUPERSEDED
        assert rows[PROPOSAL_ID] == FormalizationProposalStatus.PROPOSED


def test_b9_different_workspace_does_not_supersede_prior_proposal(factory):
    with factory() as db:
        request, result, persisted, admission, _ = _prepare_governed(db)
        _persist(db, admission=admission, request=request, result=result, discussion_persistence=persisted)
        user = _message(message_id=USER_ID, role=ProjectDirectorMessageRole.USER, sequence_no=1)
        current = persisted.persisted_turn.delta_apply_result.workspace
        previous_event_rows = db.execute(select(ProjectDirectorDiscussionEventTable).order_by(ProjectDirectorDiscussionEventTable.sequence_no)).scalars().all()
        next_request = _request(workspace_version=current.version_no)
        next_result = _result(delta=_formalization_delta())
        next_persisted = _persist_turn(
            db, request=next_request, result=next_result, assistant_id=uuid4(), sequence_no=4,
            available_messages=[user, persisted.persisted_turn.assistant_message],
            current_events=previous_event_rows, current_workspace=current, start_sequence_no=3,
        )
        source_event = previous_event_rows[0]
        second_id = uuid4()
        next_result = _result(
            delta=_formalization_delta(),
            proposal=_proposal(event_id=source_event.id, workspace_version=current.version_no, proposal_id=second_id),
        )
        next_admission = DirectorRuntimeResultFormalizationAdmissionService(session=db).admit(
            request=next_request, result=next_result, discussion_persistence=next_persisted, occurred_at=PROPOSAL_TIME
        )
        _persist(db, admission=next_admission, request=next_request, result=next_result, discussion_persistence=next_persisted)

        rows = {row.proposal_id: row.status for row in _proposal_rows(db)}
        assert rows[PROPOSAL_ID] == FormalizationProposalStatus.PROPOSED
        assert rows[second_id] == FormalizationProposalStatus.PROPOSED


class _CreateThenFailRepository:
    def __init__(self, session):
        self._delegate = ProjectDirectorFormalizationProposalRepository(session)

    def get_by_id(self, proposal_id):
        return self._delegate.get_by_id(proposal_id)

    def create_no_commit(self, proposal):
        self._delegate.create_no_commit(proposal)
        raise RuntimeError("create_failed")

    def mark_superseded_no_commit(self, **kwargs):
        raise AssertionError("mark must not follow a create failure")


class _SupersedeThenFailRepository(_CreateThenFailRepository):
    def create_no_commit(self, proposal):
        return self._delegate.create_no_commit(proposal)

    def mark_superseded_no_commit(self, **kwargs):
        raise RuntimeError("supersede_failed")


def test_b10_create_failure_rolls_back_nested_write(factory):
    with factory() as db:
        request, result, persisted, admission, _ = _prepare_governed(db)
        with pytest.raises(RuntimeError, match="create_failed"):
            _persist(db, admission=admission, request=request, result=result, discussion_persistence=persisted, repository=_CreateThenFailRepository(db))
        assert not _proposal_rows(db)


def test_b11_supersede_failure_rolls_back_nested_replacement(factory):
    with factory() as db:
        request, result, persisted, admission, _ = _prepare_governed(db)
        prior_id = uuid4()
        prior = admission.governed_proposal_candidate.model_copy(
            update={
                "proposal_id": prior_id,
                "assistant_message_id": PREVIOUS_ASSISTANT_ID,
            }
        )
        ProjectDirectorFormalizationProposalRepository(db).create_no_commit(prior)
        with pytest.raises(RuntimeError, match="supersede_failed"):
            _persist(db, admission=admission, request=request, result=result, discussion_persistence=persisted, repository=_SupersedeThenFailRepository(db))
        rows = {row.proposal_id: row.status for row in _proposal_rows(db)}
        assert rows == {prior_id: FormalizationProposalStatus.PROPOSED}


def test_b12_outer_rollback_reverts_c2_and_c3b_together(factory):
    with factory() as db:
        request, result, persisted, admission, _ = _prepare_governed(db)
        _persist(db, admission=admission, request=request, result=result, discussion_persistence=persisted)
        db.rollback()

        assert not db.execute(select(ProjectDirectorFormalizationProposalTable)).scalars().all()
        assert len(db.execute(select(ProjectDirectorDiscussionEventTable)).scalars().all()) == 1
        assert len(db.execute(select(ProjectDirectorMessageTable)).scalars().all()) == 2
        assert db.execute(select(ProjectDirectorDiscussionWorkspaceTable)).scalar_one().version_no == 1


def test_b13_rollback_then_retry_is_first_persistence(factory):
    with factory() as db:
        request, result, persisted, admission, _ = _prepare_governed(db)
        _persist(db, admission=admission, request=request, result=result, discussion_persistence=persisted)
        db.rollback()
        baseline_event = db.execute(select(ProjectDirectorDiscussionEventTable)).scalar_one()
        baseline_workspace = ProjectDirectorDiscussionWorkspaceRepository(db).get_by_session_id(session_id=SESSION_ID)
        user = _message(message_id=USER_ID, role=ProjectDirectorMessageRole.USER, sequence_no=1)
        retry = _persist_turn(
            db, request=request, result=result, assistant_id=ASSISTANT_ID, sequence_no=3,
            available_messages=[user, _message(message_id=PREVIOUS_ASSISTANT_ID, role=ProjectDirectorMessageRole.ASSISTANT, sequence_no=2)],
            current_events=[
                ProjectDirectorDiscussionEventRepository(db).get_by_id(
                    event_id=baseline_event.id
                )
            ],
            current_workspace=baseline_workspace, start_sequence_no=2,
        )
        retry_admission = DirectorRuntimeResultFormalizationAdmissionService(session=db).admit(request=request, result=result, discussion_persistence=retry, occurred_at=PROPOSAL_TIME)
        outcome = _persist(db, admission=retry_admission, request=request, result=result, discussion_persistence=retry)

        assert outcome.status is DirectorRuntimeFormalizationPersistenceStatus.PERSISTED
        assert len(_proposal_rows(db)) == 1


def test_b14_b15_b16_persistence_never_creates_confirmation_or_execution_rows(factory):
    with factory() as db:
        request, result, persisted, admission, _ = _prepare_governed(db)
        outcome = _persist(db, admission=admission, request=request, result=result, discussion_persistence=persisted)

        assert outcome.stored_proposal.status is FormalizationProposalStatus.PROPOSED
        assert outcome.stored_proposal.confirmed_at is None
        assert not db.execute(select(ProjectDirectorPlanVersionTable)).scalars().all()
        assert not db.execute(select(TaskTable)).scalars().all()
        assert not db.execute(select(RunTable)).scalars().all()
        assert not db.execute(select(AgentSessionTable)).scalars().all()


def test_b17_service_has_no_runtime_provider_or_outer_transaction_surface():
    source = Path(
        "app/services/director_runtime_result_formalization_persistence_service.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "ProjectDirectorDiscussionFormalizationService",
        "mark_confirmed_no_commit",
        "project_director_plan_version",
        "app.repositories.task_repository",
        "app.repositories.run_repository",
        "agent_session_repository",
        "provider",
        "execute_director_runtime",
        ".commit(",
        ".rollback(",
    ):
        assert forbidden not in source
