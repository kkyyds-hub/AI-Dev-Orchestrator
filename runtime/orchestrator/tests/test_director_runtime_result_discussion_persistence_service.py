"""P26-BIG-C2-B1 governed runtime discussion persistence contract."""

from __future__ import annotations

import ast
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import begin_sqlite_transaction, configure_sqlite
from app.core.db_tables import (
    ORMBase,
    ProjectDirectorDiscussionEventTable,
    ProjectDirectorDiscussionWorkspaceTable,
    ProjectDirectorMessageTable,
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
from app.domain.project_director_discussion import (
    DiscussionActorClaim,
    DiscussionDelta,
    DiscussionDeltaOperation,
    DiscussionDeltaOperationType,
)
from app.services.director_runtime_result_discussion_admission_service import (
    DirectorRuntimeDiscussionAdmissionResult,
    DirectorRuntimeResultDiscussionAdmissionService,
)
from app.services.director_runtime_result_discussion_persistence_service import (
    DirectorRuntimeDiscussionPersistenceError,
    DirectorRuntimeDiscussionPersistenceStatus,
    DirectorRuntimeResultDiscussionPersistenceService,
)
from app.services.project_director_discussion_delta_apply_service import (
    DiscussionDeltaApplyStatus,
)
from app.services.project_director_discussion_delta_gate_service import (
    DiscussionDeltaGateStatus,
    ProjectDirectorDiscussionDeltaGateService,
)
from app.services.project_director_discussion_turn_persistence_service import (
    ProjectDirectorDiscussionTurnPersistenceService,
)


PROJECT_ID = UUID("11111111-1111-1111-1111-111111111111")
SESSION_ID = UUID("22222222-2222-2222-2222-222222222222")
USER_MESSAGE_ID = UUID("33333333-3333-3333-3333-333333333333")
ASSISTANT_MESSAGE_ID = UUID("44444444-4444-4444-4444-444444444444")
PRIOR_ASSISTANT_ID = UUID("55555555-5555-5555-5555-555555555555")
SYSTEM_MESSAGE_ID = UUID("66666666-6666-6666-6666-666666666666")
FIXED_TIME = datetime(2026, 8, 31, 8, 0, tzinfo=timezone.utc)


@pytest.fixture()
def factory(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'c2b1.db').as_posix()}")
    event.listen(engine, "connect", configure_sqlite)
    event.listen(engine, "begin", begin_sqlite_transaction)
    ORMBase.metadata.create_all(bind=engine)
    try:
        yield sessionmaker(
            bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
        )
    finally:
        engine.dispose()


def _seed(db: Session) -> None:
    db.add(
        ProjectTable(
            id=PROJECT_ID,
            name="C2-B1 project",
            summary="C2-B1 project",
            status="active",
            stage="intake",
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
    )
    db.flush()
    db.add(ProjectDirectorSessionTable(id=SESSION_ID, project_id=PROJECT_ID, goal_text="B1"))
    db.flush()
    db.add(
        ProjectDirectorMessageTable(
            id=USER_MESSAGE_ID,
            session_id=SESSION_ID,
            role=ProjectDirectorMessageRole.USER,
            content="请评估这个候选。",
            sequence_no=1,
            source=ProjectDirectorMessageSource.SYSTEM,
            source_detail="test",
            created_at=FIXED_TIME,
        )
    )
    db.commit()


def _user_message() -> ProjectDirectorMessage:
    return ProjectDirectorMessage(
        id=USER_MESSAGE_ID,
        session_id=SESSION_ID,
        role=ProjectDirectorMessageRole.USER,
        content="请评估这个候选。",
        sequence_no=1,
        source=ProjectDirectorMessageSource.SYSTEM,
        created_at=FIXED_TIME,
    )


def _assistant_message(*, message_id: UUID, sequence_no: int, content: str) -> ProjectDirectorMessage:
    return ProjectDirectorMessage(
        id=message_id,
        session_id=SESSION_ID,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content=content,
        sequence_no=sequence_no,
        related_project_id=PROJECT_ID,
        source=ProjectDirectorMessageSource.AI,
        source_detail="director_runtime",
        created_at=FIXED_TIME,
    )


def _system_message(*, sequence_no: int = 3) -> ProjectDirectorMessage:
    return ProjectDirectorMessage(
        id=SYSTEM_MESSAGE_ID,
        session_id=SESSION_ID,
        role=ProjectDirectorMessageRole.SYSTEM,
        content="受信任平台事实。",
        sequence_no=sequence_no,
        related_project_id=PROJECT_ID,
        source=ProjectDirectorMessageSource.SYSTEM,
        created_at=FIXED_TIME,
    )


def _request():
    return validate_director_runtime_request(
        {
            "schema_version": DIRECTOR_RUNTIME_SCHEMA_VERSION,
            "request_id": "c2-b1-request",
            "project_id": str(PROJECT_ID),
            "session_id": str(SESSION_ID),
            "message_id": str(USER_MESSAGE_ID),
            "current_user_message": {
                "content": "请评估这个候选。",
                "occurred_at": "2026-08-31T08:00:00Z",
                "actor_claim": "user",
            },
            "authoritative_facts": {},
            "active_discussion_workspace": None,
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
                "model_id": "c2-b1-model",
                "provider_profile_id": "c2-b1-profile",
                "timeout_ms": 1000.0,
                "max_tool_rounds": 0,
            },
        }
    )


def _result(*, candidate: dict | None = None, error: dict | None = None):
    return parse_director_turn_result(
        {
            "schema_version": DIRECTOR_RUNTIME_SCHEMA_VERSION,
            "request_id": "c2-b1-request",
            "response_text": "运行时回复",
            "turn_semantics": {
                "conversation_mode": "general_discussion",
                "formal_action_requested": False,
                "hypothetical_action": False,
                "confidence": 0.8,
            },
            "discussion_lifecycle": {"observed_status": None, "suggested_next_status": None},
            "discussion_delta_candidate": candidate,
            "formalization": {"proposal_candidate": None, "readiness": "not_ready"},
            "tool_activity": [],
            "source_references": [],
            "runtime_metadata": {
                "runtime_state": "ready",
                "model_id": "c2-b1-model",
                "provider_profile_id": "c2-b1-profile",
                "usage": {},
                "duration_ms": 1.0,
                "attempt": 0,
            },
            "error": error,
        },
        expected_request_id="c2-b1-request",
    )


def _candidate(
    *,
    op: str = "add_concern",
    target_id: UUID | None = None,
    source_message_id: UUID = ASSISTANT_MESSAGE_ID,
    actor_claim: str = "assistant_proposal",
) -> dict:
    return {
        "operations": [
            {
                "op": op,
                "target_id": str(target_id) if target_id else None,
                "subject_key": "runtime-candidate",
                "content": "运行时候选内容",
                "payload": {},
                "source_message_ids": [str(source_message_id)],
                "actor_claim": actor_claim,
                "supersedes_event_id": None,
            }
        ]
    }


def _admit(
    *,
    candidate: dict | None = None,
    error: dict | None = None,
    assistant_id: UUID = ASSISTANT_MESSAGE_ID,
    assistant_sequence_no: int = 2,
    available_messages: list[ProjectDirectorMessage] | None = None,
):
    return DirectorRuntimeResultDiscussionAdmissionService().admit(
        request=_request(),
        result=_result(candidate=candidate, error=error),
        assistant_message_id=assistant_id,
        assistant_message_sequence_no=assistant_sequence_no,
        available_messages=available_messages or [_user_message()],
        current_events=[],
        current_workspace=None,
        start_sequence_no=1,
        occurred_at=FIXED_TIME,
    )


def _counts(db: Session) -> tuple[int, int, int]:
    messages = db.execute(select(ProjectDirectorMessageTable)).scalars().all()
    events = db.execute(select(ProjectDirectorDiscussionEventTable)).scalars().all()
    workspaces = db.execute(select(ProjectDirectorDiscussionWorkspaceTable)).scalars().all()
    return len(messages), len(events), len(workspaces)


def _seed_system_message(db: Session) -> ProjectDirectorMessage:
    message = _system_message(sequence_no=1)
    db.add(
        ProjectDirectorMessageTable(
            id=message.id,
            session_id=message.session_id,
            role=message.role,
            content=message.content,
            sequence_no=message.sequence_no,
            related_project_id=message.related_project_id,
            source=message.source,
            source_detail="test",
            created_at=message.created_at,
        )
    )
    db.commit()
    return message


def _trusted_platform_delta(actor_claim: DiscussionActorClaim) -> DiscussionDelta:
    return DiscussionDelta(
        operations=[
            DiscussionDeltaOperation(
                op=DiscussionDeltaOperationType.ADD_CONSTRAINT,
                subject_key="trusted-platform-constraint",
                content="受信任平台约束",
                source_message_ids=[SYSTEM_MESSAGE_ID],
                actor_claim=actor_claim,
            )
        ]
    )


def test_prepared_admission_persists_assistant_event_and_workspace(factory) -> None:
    admission = _admit(candidate=_candidate())
    assert admission.governed_delta is not None
    assert admission.governed_delta.status is DiscussionDeltaGateStatus.PREPARED

    with factory() as db:
        _seed(db)
        result = DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
            admission=admission, available_messages=[_user_message()]
        )

        assert result.status is DirectorRuntimeDiscussionPersistenceStatus.PERSISTED
        assert result.persisted_turn is not None
        assert result.persisted_turn.delta_apply_result.status is DiscussionDeltaApplyStatus.APPLIED
        assert _counts(db) == (2, 1, 1)
        db.rollback()


def test_empty_prepared_admission_persists_message_with_no_changes(factory) -> None:
    admission = _admit(candidate={"operations": []})

    with factory() as db:
        _seed(db)
        result = DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
            admission=admission, available_messages=[_user_message()]
        )

        assert result.status is DirectorRuntimeDiscussionPersistenceStatus.PERSISTED
        assert result.persisted_turn is not None
        assert result.persisted_turn.delta_apply_result.status is DiscussionDeltaApplyStatus.NO_CHANGES
        assert _counts(db) == (2, 0, 0)
        db.rollback()


def test_no_delta_admission_persists_message_with_no_changes(factory) -> None:
    admission = _admit(candidate=None)
    assert admission.delta is None
    assert admission.assistant_message_candidate is not None
    assert admission.governed_delta is None
    assert admission.no_admission_reason == "no_delta_candidate"

    with factory() as db:
        _seed(db)
        result = DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
            admission=admission, available_messages=[_user_message()]
        )

        assert result.status is DirectorRuntimeDiscussionPersistenceStatus.PERSISTED
        assert result.persisted_turn is not None
        assert result.persisted_turn.assistant_message_inserted is True
        assert result.persisted_turn.delta_apply_result.status is DiscussionDeltaApplyStatus.NO_CHANGES
        assert _counts(db) == (2, 0, 0)
        db.rollback()


def test_no_delta_replay_does_not_duplicate_assistant_message(factory) -> None:
    admission = _admit(candidate=None)
    with factory() as db:
        _seed(db)
        DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
            admission=admission, available_messages=[_user_message()]
        )
        db.commit()

    with factory() as db:
        result = DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
            admission=admission, available_messages=[_user_message()]
        )
        assert result.status is DirectorRuntimeDiscussionPersistenceStatus.PERSISTED
        assert result.persisted_turn is not None
        assert result.persisted_turn.assistant_message_inserted is False
        assert result.persisted_turn.delta_apply_result.status is DiscussionDeltaApplyStatus.NO_CHANGES
        assert _counts(db) == (2, 0, 0)
        db.rollback()


def test_no_delta_assistant_message_conflict_fails_closed(factory) -> None:
    admission = _admit(candidate=None)
    conflicting = replace(
        admission,
        assistant_message_candidate=admission.assistant_message_candidate.model_copy(
            update={"content": "冲突回复"}
        ),
    )
    with factory() as db:
        _seed(db)
        service = DirectorRuntimeResultDiscussionPersistenceService(session=db)
        service.persist_admitted_turn(admission=admission, available_messages=[_user_message()])
        db.commit()

    with factory() as db:
        with pytest.raises(ValueError, match="^discussion_turn_assistant_message_conflict$"):
            DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
                admission=conflicting, available_messages=[_user_message()]
            )
        assert _counts(db) == (2, 0, 0)
        db.rollback()


def test_no_delta_stale_assistant_sequence_fails_closed_with_no_write(factory) -> None:
    admission = _admit(candidate=None, assistant_sequence_no=3)
    with factory() as db:
        _seed(db)
        with pytest.raises(ValueError, match="^discussion_turn_assistant_message_sequence_mismatch$"):
            DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
                admission=admission, available_messages=[_user_message()]
            )
        assert _counts(db) == (1, 0, 0)
        db.rollback()


def test_no_delta_persistence_rechecks_latest_sequence(factory) -> None:
    admission = _admit(candidate=None)
    prior = _assistant_message(
        message_id=PRIOR_ASSISTANT_ID, sequence_no=2, content="先前回复"
    )
    with factory() as db:
        _seed(db)
        ProjectDirectorDiscussionTurnPersistenceService(session=db).persist_assistant_turn(
            session_id=SESSION_ID,
            project_id=PROJECT_ID,
            assistant_message=prior,
            available_messages=[_user_message()],
            delta=DiscussionDelta(operations=[]),
            occurred_at=FIXED_TIME,
        )
        db.commit()

    with factory() as db:
        with pytest.raises(ValueError, match="^discussion_turn_assistant_message_sequence_mismatch$"):
            DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
                admission=admission, available_messages=[_user_message(), prior]
            )
        assert _counts(db) == (2, 0, 0)
        db.rollback()


def test_no_delta_outer_rollback_removes_assistant_message(factory) -> None:
    admission = _admit(candidate=None)
    with factory() as db:
        _seed(db)
        DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
            admission=admission, available_messages=[_user_message()]
        )
        db.rollback()

    with factory() as db:
        assert _counts(db) == (1, 0, 0)


def test_no_delta_outer_commit_persists_only_assistant_message(factory) -> None:
    admission = _admit(candidate=None)
    with factory() as db:
        _seed(db)
        DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
            admission=admission, available_messages=[_user_message()]
        )
        db.commit()

    with factory() as db:
        assert _counts(db) == (2, 0, 0)


def test_exact_prepared_replay_does_not_duplicate_message_or_event(factory) -> None:
    admission = _admit(candidate=_candidate())
    with factory() as db:
        _seed(db)
        service = DirectorRuntimeResultDiscussionPersistenceService(session=db)
        service.persist_admitted_turn(admission=admission, available_messages=[_user_message()])
        db.commit()

    with factory() as db:
        result = DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
            admission=admission, available_messages=[_user_message()]
        )
        assert result.persisted_turn is not None
        assert result.persisted_turn.assistant_message_inserted is False
        assert result.persisted_turn.delta_apply_result.status is DiscussionDeltaApplyStatus.REPLAYED
        assert _counts(db) == (2, 1, 1)
        db.rollback()


def test_assistant_message_conflict_has_no_partial_discussion_write(factory) -> None:
    admission = _admit(candidate=_candidate())
    conflicting = replace(
        admission,
        assistant_message_candidate=admission.assistant_message_candidate.model_copy(
            update={"content": "冲突回复"}
        ),
    )
    with factory() as db:
        _seed(db)
        service = DirectorRuntimeResultDiscussionPersistenceService(session=db)
        service.persist_admitted_turn(admission=admission, available_messages=[_user_message()])
        db.commit()

    with factory() as db:
        with pytest.raises(ValueError, match="^discussion_turn_assistant_message_conflict$"):
            DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
                admission=conflicting, available_messages=[_user_message()]
            )
        assert _counts(db) == (2, 1, 1)
        db.rollback()


def test_assistant_sequence_conflict_has_no_write(factory) -> None:
    admission = _admit(candidate=_candidate(), assistant_sequence_no=3)
    with factory() as db:
        _seed(db)
        with pytest.raises(ValueError, match="^discussion_turn_assistant_message_sequence_mismatch$"):
            DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
                admission=admission, available_messages=[_user_message()]
            )
        assert _counts(db) == (1, 0, 0)
        db.rollback()


def test_confirmation_admission_is_an_explicit_no_write_result(factory) -> None:
    admission = _admit(candidate=_candidate(op="confirm_decision"))
    assert admission.governed_delta is not None
    assert admission.governed_delta.status is DiscussionDeltaGateStatus.REQUIRES_CONFIRMATION
    with factory() as db:
        _seed(db)
        result = DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
            admission=admission, available_messages=[_user_message()]
        )
        assert result.status is DirectorRuntimeDiscussionPersistenceStatus.CONFIRMATION_REQUIRED
        assert result.persisted_turn is None
        assert _counts(db) == (1, 0, 0)
        db.rollback()


def test_runtime_error_result_is_an_explicit_no_write(factory) -> None:
    admission = _admit(
        error={
            "code": "runtime_failed",
            "stage": "runtime",
            "retryable": False,
            "safe_message": "运行时失败",
        }
    )
    with factory() as db:
        _seed(db)
        result = DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
            admission=admission, available_messages=[_user_message()]
        )
        assert result.status is DirectorRuntimeDiscussionPersistenceStatus.NOT_ADMITTED
        assert result.no_admission_reason == "runtime_error"
        assert _counts(db) == (1, 0, 0)
        db.rollback()


def test_inconsistent_prepared_admission_fails_closed_with_no_write(factory) -> None:
    valid = _admit(candidate=_candidate())
    inconsistent = DirectorRuntimeDiscussionAdmissionResult(
        delta=None,
        assistant_message_candidate=valid.assistant_message_candidate,
        governed_delta=valid.governed_delta,
        no_admission_reason=None,
    )
    with factory() as db:
        _seed(db)
        with pytest.raises(DirectorRuntimeDiscussionPersistenceError) as exc:
            DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
                admission=inconsistent, available_messages=[_user_message()]
            )
        assert exc.value.code == "director_runtime_discussion_persistence_admission_invalid"
        assert _counts(db) == (1, 0, 0)
        db.rollback()


def test_persistence_rereads_authoritative_state_after_preflight(factory) -> None:
    option_id = uuid4()
    prior = _assistant_message(message_id=PRIOR_ASSISTANT_ID, sequence_no=2, content="先前回复")
    candidate = _candidate(op="add_option", target_id=option_id)
    admission = _admit(
        candidate=candidate,
        assistant_sequence_no=3,
        available_messages=[_user_message(), prior],
    )
    assert admission.governed_delta is not None
    assert admission.governed_delta.status is DiscussionDeltaGateStatus.PREPARED
    prior_admission = _admit(
        candidate=_candidate(
            op="add_option", target_id=option_id, source_message_id=PRIOR_ASSISTANT_ID
        ),
        assistant_id=PRIOR_ASSISTANT_ID,
        assistant_sequence_no=2,
        available_messages=[_user_message()],
    )

    with factory() as db:
        _seed(db)
        ProjectDirectorDiscussionTurnPersistenceService(session=db).persist_assistant_turn(
            session_id=SESSION_ID,
            project_id=PROJECT_ID,
            assistant_message=prior,
            available_messages=[_user_message()],
            delta=prior_admission.delta,
            occurred_at=FIXED_TIME,
        )
        db.commit()

    with factory() as db:
        with pytest.raises(ValueError, match="^discussion_delta_option_target_not_new$"):
            DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
                admission=admission, available_messages=[_user_message(), prior]
            )
        assert _counts(db) == (2, 1, 1)
        db.rollback()


def test_outer_rollback_removes_all_b1_writes(factory) -> None:
    admission = _admit(candidate=_candidate())
    with factory() as db:
        _seed(db)
        DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
            admission=admission, available_messages=[_user_message()]
        )
        db.rollback()

    with factory() as db:
        assert _counts(db) == (1, 0, 0)


@pytest.mark.parametrize(
    "actor_claim",
    [DiscussionActorClaim.SYSTEM_FACT, DiscussionActorClaim.FORMAL_PROJECT_FACT],
)
def test_generic_gate_preserves_trusted_platform_authority(actor_claim) -> None:
    assistant = _admit(candidate=_candidate()).assistant_message_candidate
    result = ProjectDirectorDiscussionDeltaGateService().evaluate_delta(
        session_id=SESSION_ID,
        project_id=PROJECT_ID,
        assistant_message=assistant,
        available_messages=[_user_message(), _system_message()],
        current_events=[],
        current_workspace=None,
        delta=_trusted_platform_delta(actor_claim),
        start_sequence_no=1,
        occurred_at=FIXED_TIME,
    )
    assert result.status is DiscussionDeltaGateStatus.PREPARED


@pytest.mark.parametrize(
    "actor_claim",
    [DiscussionActorClaim.SYSTEM_FACT, DiscussionActorClaim.FORMAL_PROJECT_FACT],
)
def test_runtime_bridge_rejects_replaced_trusted_authority_delta(factory, actor_claim) -> None:
    valid = _admit(candidate=_candidate())
    forged = replace(valid, delta=_trusted_platform_delta(actor_claim))
    with factory() as db:
        _seed(db)
        system_message = _seed_system_message(db)
        with pytest.raises(DirectorRuntimeDiscussionPersistenceError) as exc:
            DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
                admission=forged, available_messages=[_user_message(), system_message]
            )
        assert exc.value.code == "director_runtime_discussion_persistence_authority_claim_invalid"
        assert _counts(db) == (2, 0, 0)
        db.rollback()


def test_runtime_bridge_checks_authority_before_confirmation_status(factory) -> None:
    confirmation = _admit(candidate=_candidate(op="confirm_decision"))
    forged = replace(
        confirmation,
        delta=_trusted_platform_delta(DiscussionActorClaim.SYSTEM_FACT),
    )
    with factory() as db:
        _seed(db)
        with pytest.raises(DirectorRuntimeDiscussionPersistenceError) as exc:
            DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
                admission=forged, available_messages=[_user_message(), _system_message()]
            )
        assert exc.value.code == "director_runtime_discussion_persistence_authority_claim_invalid"
        assert _counts(db) == (1, 0, 0)
        db.rollback()


def test_legal_runtime_user_inferred_admission_remains_persistable(factory) -> None:
    admission = _admit(
        candidate=_candidate(
            op="add_constraint",
            source_message_id=USER_MESSAGE_ID,
            actor_claim="user_inferred",
        )
    )
    with factory() as db:
        _seed(db)
        result = DirectorRuntimeResultDiscussionPersistenceService(session=db).persist_admitted_turn(
            admission=admission, available_messages=[_user_message()]
        )
        assert result.status is DirectorRuntimeDiscussionPersistenceStatus.PERSISTED
        assert _counts(db) == (2, 1, 1)
        db.rollback()


def test_bridge_static_boundary_has_no_raw_runtime_or_direct_event_persistence() -> None:
    path = Path(__file__).parents[1] / "app/services/director_runtime_result_discussion_persistence_service.py"
    source = path.read_text()
    module = ast.parse(source)
    imports = {
        node.module or ""
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom)
    }
    calls = {
        node.func.attr
        for node in ast.walk(module)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    forbidden = ("director_runtime_protocol", "formalization", "repository", "provider", "worker", "supervisor")
    assert all(token not in item.lower() for item in imports for token in forbidden)
    assert "persist_assistant_turn" in calls
    assert "commit" not in calls
    assert "rollback" not in calls
    assert "model_validate" not in calls
    assert "DirectorTurnResult" not in source
    assert "prepared_events" not in source
    assert "projected_workspace" not in source
