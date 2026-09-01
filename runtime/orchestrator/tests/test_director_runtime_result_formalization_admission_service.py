"""P26-BIG-C3-A governed admission of runtime formalization candidates."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.core.db import begin_sqlite_transaction, configure_sqlite
from app.core.db_tables import (
    ORMBase,
    ProjectDirectorDiscussionEventTable,
    ProjectDirectorFormalizationProposalTable,
    ProjectDirectorMessageTable,
    ProjectDirectorPlanVersionTable,
    ProjectDirectorSessionTable,
    ProjectTable,
)
from app.domain.director_runtime_protocol import (
    DIRECTOR_RUNTIME_SCHEMA_VERSION,
    parse_director_turn_result,
    validate_director_runtime_request,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
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
    DirectorRuntimeFormalizationAdmissionError,
    DirectorRuntimeFormalizationAdmissionStatus,
    DirectorRuntimeResultFormalizationAdmissionService,
)


PROJECT_ID = UUID("11111111-1111-1111-1111-111111111111")
SESSION_ID = UUID("22222222-2222-2222-2222-222222222222")
USER_ID = UUID("33333333-3333-3333-3333-333333333333")
PREVIOUS_ASSISTANT_ID = UUID("44444444-4444-4444-4444-444444444444")
ASSISTANT_ID = UUID("55555555-5555-5555-5555-555555555555")
FIXED_TIME = datetime(2026, 8, 31, 8, 0, tzinfo=timezone.utc)
PROPOSAL_TIME = datetime(2030, 1, 1, tzinfo=timezone.utc)


@pytest.fixture()
def factory(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'c3a.db'}")
    event.listen(engine, "connect", configure_sqlite)
    event.listen(engine, "begin", begin_sqlite_transaction)
    ORMBase.metadata.create_all(bind=engine)
    try:
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        engine.dispose()


def _request(active_workspace_version=None):
    return validate_director_runtime_request(
        {
            "schema_version": DIRECTOR_RUNTIME_SCHEMA_VERSION,
            "request_id": "c3-a-request",
            "project_id": str(PROJECT_ID),
            "session_id": str(SESSION_ID),
            "message_id": str(USER_ID),
            "current_user_message": {
                "content": "Please formalize the current discussion.",
                "occurred_at": "2026-08-31T08:00:00Z",
                "actor_claim": "user",
            },
            "authoritative_facts": {},
            "active_discussion_workspace": (
                None if active_workspace_version is None else {"version_no": active_workspace_version}
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
                "model_id": "c3-a-model",
                "provider_profile_id": "c3-a-profile",
                "timeout_ms": 1000.0,
                "max_tool_rounds": 0,
            },
        }
    )


def _result(*, delta=None, proposal=None):
    return parse_director_turn_result(
        {
            "schema_version": DIRECTOR_RUNTIME_SCHEMA_VERSION,
            "request_id": "c3-a-request",
            "response_text": "Runtime response.",
            "turn_semantics": {
                "conversation_mode": "general_discussion",
                "formal_action_requested": False,
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
                "model_id": "c3-a-model",
                "provider_profile_id": "c3-a-profile",
                "usage": {},
                "duration_ms": 1.0,
                "attempt": 0,
            },
            "error": None,
        },
        expected_request_id="c3-a-request",
    )


def _message(*, message_id, role, sequence_no, content):
    return ProjectDirectorMessage(
        id=message_id,
        session_id=SESSION_ID,
        role=role,
        content=content,
        sequence_no=sequence_no,
        related_project_id=PROJECT_ID,
        source=ProjectDirectorMessageSource.AI if role is ProjectDirectorMessageRole.ASSISTANT else ProjectDirectorMessageSource.SYSTEM,
        source_detail="director_runtime" if role is ProjectDirectorMessageRole.ASSISTANT else "test",
        created_at=FIXED_TIME,
    )


def _seed(db):
    db.add(ProjectTable(id=PROJECT_ID, name="C3-A", summary="C3-A", status="active", stage="intake", created_at=FIXED_TIME, updated_at=FIXED_TIME))
    db.flush()
    db.add(ProjectDirectorSessionTable(id=SESSION_ID, project_id=PROJECT_ID, goal_text="C3-A"))
    db.flush()
    user = _message(message_id=USER_ID, role=ProjectDirectorMessageRole.USER, sequence_no=1, content="Please formalize the current discussion.")
    db.add(
        ProjectDirectorMessageTable(
            id=user.id,
            session_id=user.session_id,
            role=user.role,
            content=user.content,
            sequence_no=user.sequence_no,
            related_project_id=user.related_project_id,
            source=user.source,
            source_detail=user.source_detail,
            created_at=user.created_at,
        )
    )
    db.commit()
    return user


def _delta(*, assistant_id, op, content):
    return {"operations": [{"op": op, "target_id": None, "subject_key": "c3-a", "content": content, "payload": {}, "source_message_ids": [str(assistant_id)], "actor_claim": "assistant_proposal", "supersedes_event_id": None}]}


def _proposal(*, event_id, workspace_version):
    return {
        "proposal_id": str(UUID("66666666-6666-6666-6666-666666666666")),
        "target": "plan_revision",
        "workspace_version": workspace_version,
        "summary": "Govern the current topic.",
        "changes": [{
            "change_type": "update",
            "subject_key": "c3-a-topic",
            "summary": "Use the governed topic.",
            "source_event_ids": [str(event_id)],
        }],
        "source_message_ids": [str(USER_ID)],
        "source_event_ids": [str(event_id)],
        "risk_summary": "Needs user confirmation.",
        "requires_confirmation": True,
        "status": "proposed",
    }


def _persist_turn(db, *, runtime_result, assistant_id, sequence_no, available_messages, current_events, current_workspace, start_sequence_no):
    admission = DirectorRuntimeResultDiscussionAdmissionService().admit(
        request=_request(), result=runtime_result, assistant_message_id=assistant_id,
        assistant_message_sequence_no=sequence_no, available_messages=available_messages,
        current_events=current_events, current_workspace=current_workspace,
        start_sequence_no=start_sequence_no, occurred_at=FIXED_TIME,
    )
    return DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
        admission=admission, available_messages=available_messages
    )


def test_no_candidate_is_explicit_no_admission(factory):
    with factory() as db:
        user = _seed(db)
        persisted = _persist_turn(
            db, runtime_result=_result(delta=None), assistant_id=ASSISTANT_ID,
            sequence_no=2, available_messages=[user], current_events=[],
            current_workspace=None, start_sequence_no=1,
        )
        result = DirectorRuntimeResultFormalizationAdmissionService(session=db).admit(
            request=_request(), result=_result(delta=None), discussion_persistence=persisted,
            occurred_at=PROPOSAL_TIME,
        )
        assert result.status is DirectorRuntimeFormalizationAdmissionStatus.NOT_ADMITTED
        assert result.no_admission_reason == "no_formalization_candidate"
        assert not db.execute(select(ProjectDirectorFormalizationProposalTable)).scalars().all()
        assert not db.execute(select(ProjectDirectorPlanVersionTable)).scalars().all()


def test_candidate_failures_cannot_write_formalization_records(factory):
    with factory() as db:
        user = _seed(db)
        persisted = _persist_turn(
            db, runtime_result=_result(delta=None), assistant_id=ASSISTANT_ID,
            sequence_no=2, available_messages=[user], current_events=[],
            current_workspace=None, start_sequence_no=1,
        )
        malformed = _result(proposal={"proposal_id": "not-a-uuid"})
        with pytest.raises(DirectorRuntimeFormalizationAdmissionError, match="candidate_invalid"):
            DirectorRuntimeResultFormalizationAdmissionService(session=db).admit(
                request=_request(), result=malformed, discussion_persistence=persisted,
                occurred_at=PROPOSAL_TIME,
            )
        no_turn = DirectorRuntimeDiscussionPersistenceResult(
            status=DirectorRuntimeDiscussionPersistenceStatus.NOT_ADMITTED,
            persisted_turn=None,
            no_admission_reason="runtime_error",
        )
        result = DirectorRuntimeResultFormalizationAdmissionService(session=db).admit(
            request=_request(), result=_result(proposal={"proposal_id": str(UUID(int=1))}),
            discussion_persistence=no_turn, occurred_at=PROPOSAL_TIME,
        )
        assert result.status is DirectorRuntimeFormalizationAdmissionStatus.NOT_ADMITTED
        assert result.no_admission_reason == "discussion_turn_not_persisted"
        assert not db.execute(select(ProjectDirectorFormalizationProposalTable)).scalars().all()
        assert not db.execute(select(ProjectDirectorPlanVersionTable)).scalars().all()


def test_same_turn_delta_candidate_normalizes_pre_turn_proposal_to_post_workspace(factory):
    with factory() as db:
        user = _seed(db)
        first = _persist_turn(
            db, runtime_result=_result(delta=_delta(assistant_id=PREVIOUS_ASSISTANT_ID, op="set_topic", content="C3-A topic")),
            assistant_id=PREVIOUS_ASSISTANT_ID, sequence_no=2, available_messages=[user],
            current_events=[], current_workspace=None, start_sequence_no=1,
        )
        assert first.persisted_turn is not None
        db.commit()
        pre_event = db.execute(select(ProjectDirectorDiscussionEventTable)).scalar_one()
        pre_workspace = first.persisted_turn.delta_apply_result.workspace

        second = _persist_turn(
            db, runtime_result=_result(delta=_delta(assistant_id=ASSISTANT_ID, op="add_concern", content="Keep the scope bounded.")),
            assistant_id=ASSISTANT_ID, sequence_no=3,
            available_messages=[user, first.persisted_turn.assistant_message],
            current_events=[pre_event], current_workspace=pre_workspace, start_sequence_no=2,
        )
        assert second.persisted_turn is not None
        post_workspace = second.persisted_turn.delta_apply_result.workspace
        assert post_workspace.version_no == pre_workspace.version_no + 1
        runtime_result = _result(
            delta=_delta(assistant_id=ASSISTANT_ID, op="add_concern", content="Keep the scope bounded."),
            proposal=_proposal(event_id=pre_event.id, workspace_version=pre_workspace.version_no),
        )
        service = DirectorRuntimeResultFormalizationAdmissionService(session=db)
        admitted = service.admit(
            request=_request(active_workspace_version=pre_workspace.version_no),
            result=runtime_result, discussion_persistence=second, occurred_at=PROPOSAL_TIME,
        )
        assert admitted.status is DirectorRuntimeFormalizationAdmissionStatus.GOVERNED
        assert admitted.governed_proposal_candidate is not None
        assert admitted.governed_proposal_candidate.workspace_version == post_workspace.version_no
        assert tuple(event.id for event in admitted.source_events) == (pre_event.id,)
        repeated = service.admit(
            request=_request(active_workspace_version=pre_workspace.version_no),
            result=runtime_result, discussion_persistence=second, occurred_at=PROPOSAL_TIME,
        )
        assert repeated == admitted
        missing_user = _proposal(event_id=pre_event.id, workspace_version=pre_workspace.version_no)
        missing_user["source_message_ids"] = [str(uuid4())]
        with pytest.raises(DirectorRuntimeFormalizationAdmissionError, match="current_user_source_required"):
            service.admit(
                request=_request(active_workspace_version=pre_workspace.version_no),
                result=_result(proposal=missing_user), discussion_persistence=second,
                occurred_at=PROPOSAL_TIME,
            )
        missing_event = _proposal(event_id=uuid4(), workspace_version=pre_workspace.version_no)
        with pytest.raises(ValueError, match="lineage_invalid"):
            service.admit(
                request=_request(active_workspace_version=pre_workspace.version_no),
                result=_result(proposal=missing_event), discussion_persistence=second,
                occurred_at=PROPOSAL_TIME,
            )
        stale = _proposal(event_id=pre_event.id, workspace_version=99)
        with pytest.raises(DirectorRuntimeFormalizationAdmissionError, match="workspace_version_invalid"):
            service.admit(
                request=_request(active_workspace_version=pre_workspace.version_no),
                result=_result(proposal=stale), discussion_persistence=second,
                occurred_at=PROPOSAL_TIME,
            )
        assert not db.execute(select(ProjectDirectorFormalizationProposalTable)).scalars().all()
        assert not db.execute(select(ProjectDirectorPlanVersionTable)).scalars().all()


def test_no_delta_turn_governs_proposal_against_existing_workspace(factory):
    with factory() as db:
        user = _seed(db)
        first = _persist_turn(
            db, runtime_result=_result(delta=_delta(assistant_id=PREVIOUS_ASSISTANT_ID, op="set_topic", content="C3-A topic")),
            assistant_id=PREVIOUS_ASSISTANT_ID, sequence_no=2, available_messages=[user],
            current_events=[], current_workspace=None, start_sequence_no=1,
        )
        assert first.persisted_turn is not None
        db.commit()
        event_row = db.execute(select(ProjectDirectorDiscussionEventTable)).scalar_one()
        workspace = first.persisted_turn.delta_apply_result.workspace
        second = _persist_turn(
            db, runtime_result=_result(delta=None), assistant_id=ASSISTANT_ID, sequence_no=3,
            available_messages=[user, first.persisted_turn.assistant_message],
            current_events=[event_row], current_workspace=workspace, start_sequence_no=2,
        )
        assert second.persisted_turn is not None
        assert second.persisted_turn.delta_apply_result.workspace.version_no == workspace.version_no
        admitted = DirectorRuntimeResultFormalizationAdmissionService(session=db).admit(
            request=_request(active_workspace_version=workspace.version_no),
            result=_result(proposal=_proposal(event_id=event_row.id, workspace_version=workspace.version_no)),
            discussion_persistence=second, occurred_at=PROPOSAL_TIME,
        )
        assert admitted.status is DirectorRuntimeFormalizationAdmissionStatus.GOVERNED
        assert admitted.governed_proposal_candidate is not None
        assert admitted.governed_proposal_candidate.assistant_message_id == ASSISTANT_ID
        assert not db.execute(select(ProjectDirectorFormalizationProposalTable)).scalars().all()
        assert not db.execute(select(ProjectDirectorPlanVersionTable)).scalars().all()


def test_service_has_only_read_lineage_dependencies():
    source = Path(__file__).parents[1] / "app/services/director_runtime_result_formalization_admission_service.py"
    module = ast.parse(source.read_text())
    calls = {
        node.func.attr
        for node in ast.walk(module)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    forbidden_calls = {
        "create", "create_no_commit", "update", "delete", "mark_confirmed",
        "mark_superseded", "flush", "commit", "rollback", "formalize_discussion",
    }
    assert calls.isdisjoint(forbidden_calls)
    source_text = source.read_text()
    assert "ProjectDirectorFormalizationProposalRepository" not in source_text
    assert "ProjectDirectorDiscussionFormalizationService" not in source_text
