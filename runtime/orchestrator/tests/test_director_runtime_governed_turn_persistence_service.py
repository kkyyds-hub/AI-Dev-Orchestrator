from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import begin_sqlite_transaction, configure_sqlite
from app.core.db_tables import (
    AgentSessionTable, ORMBase, ProjectDirectorDiscussionEventTable,
    ProjectDirectorDiscussionWorkspaceTable, ProjectDirectorFormalizationProposalTable,
    ProjectDirectorMessageTable, ProjectDirectorPlanVersionTable, ProjectDirectorSessionTable,
    ProjectTable, RunTable, TaskTable,
)
from app.domain.director_runtime_protocol import parse_director_turn_result
from app.domain.project_director_message import (
    ProjectDirectorMessage, ProjectDirectorMessageRole, ProjectDirectorMessageSource,
)
from app.domain.project_director_session import ProjectDirectorSessionStatus
from app.repositories.project_director_message_repository import ProjectDirectorMessageRepository
from app.repositories.project_director_session_repository import ProjectDirectorSessionRepository
from app.services.director_runtime_governed_turn_persistence_service import (
    DirectorRuntimeGovernedTurnPersistenceError,
    DirectorRuntimeGovernedTurnPersistenceService,
    DirectorRuntimeGovernedTurnPersistenceStatus,
)
from app.services.director_runtime_request_assembler_service import (
    DirectorRuntimeRequestAssemblerService, DirectorRuntimeRequestRuntimeConfigOptions,
)
from app.services.director_runtime_session_turn_service import DirectorRuntimeSessionTurnResult
from app.services.director_runtime_supervisor_service import (
    DirectorRuntimeAttemptState, DirectorRuntimeLifecycleState, DirectorRuntimeSupervisionOutcome,
)

PROJECT = UUID("a1000000-0000-0000-0000-000000000001")
SESSION = UUID("a2000000-0000-0000-0000-000000000001")
USER = UUID("a3000000-0000-0000-0000-000000000001")
TABLES = (ProjectDirectorMessageTable, ProjectDirectorDiscussionEventTable,
          ProjectDirectorDiscussionWorkspaceTable, ProjectDirectorFormalizationProposalTable,
          ProjectDirectorPlanVersionTable, TaskTable, RunTable, AgentSessionTable)


def _db(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'c4b.db'}")
    event.listen(engine, "connect", configure_sqlite)
    event.listen(engine, "begin", lambda connection: begin_sqlite_transaction(connection))
    ORMBase.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)()


def _config():
    return DirectorRuntimeRequestRuntimeConfigOptions(model_id="m", provider_profile_id="p", timeout_ms=1000.0, max_tool_rounds=0)


def _seed(db: Session):
    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    db.add(ProjectTable(id=PROJECT, name="C4B", summary="C4B", status="active", stage="intake", created_at=now, updated_at=now)); db.flush()
    db.add(ProjectDirectorSessionTable(id=SESSION, project_id=PROJECT, goal_text="goal", constraints="", status=ProjectDirectorSessionStatus.CONFIRMED, clarifying_questions_json="[]", clarifying_answers_json="[]", goal_summary="", confirmed_at=now, created_at=now, updated_at=now)); db.commit()
    ProjectDirectorMessageRepository(db).create(ProjectDirectorMessage(id=USER, session_id=SESSION, role=ProjectDirectorMessageRole.USER, content="Persisted U1", sequence_no=1, related_project_id=PROJECT, source=ProjectDirectorMessageSource.SYSTEM, source_detail="c4b", created_at=now)); db.commit()
    return now


def _candidate(request_id: str, response="response"):
    return parse_director_turn_result({"schema_version":"p26-big-director-runtime/v1","request_id":request_id,"response_text":response,"turn_semantics":{"conversation_mode":"general_discussion","formal_action_requested":False,"hypothetical_action":False,"confidence":0.8},"discussion_lifecycle":{"observed_status":None,"suggested_next_status":None},"discussion_delta_candidate":None,"formalization":{"proposal_candidate":None,"readiness":"not_ready"},"tool_activity":[],"source_references":[],"runtime_metadata":{"runtime_state":"ready","model_id":"m","provider_profile_id":"p","usage":{},"duration_ms":1.0,"attempt":0},"error":None}, expected_request_id=request_id, authorized_tools=[])


def _turn(db, *, request_id="r", candidate=True):
    request = DirectorRuntimeRequestAssemblerService(db_session=db).build_request(session_id=SESSION, message_id=USER, runtime_config=_config(), request_id=request_id)
    outcome = DirectorRuntimeSupervisionOutcome(request_id=request_id, attempt_state=DirectorRuntimeAttemptState.SUCCEEDED if candidate else DirectorRuntimeAttemptState.FAILED, candidate=_candidate(request_id) if candidate else None, error=None if candidate else __import__('app.domain.director_runtime_protocol', fromlist=['normalize_runtime_failure']).normalize_runtime_failure(code='director_runtime_transport_failed', stage='runtime', retryable=False, safe_message='failed'))
    return DirectorRuntimeSessionTurnResult(project_id=PROJECT, session_id=SESSION, user_message_id=USER, user_message_sequence_no=1, assistant_message_sequence_no=2, request=request, supervision_outcome=outcome, supervisor_state_after=DirectorRuntimeLifecycleState.READY)


def _counts(db): return tuple(db.scalar(select(func.count()).select_from(table)) for table in TABLES)


def test_response_only_persists_assistant_without_commit_and_replays(tmp_path):
    engine, db = _db(tmp_path)
    try:
        when = _seed(db); turn = _turn(db); service = DirectorRuntimeGovernedTurnPersistenceService(session=db); before = _counts(db); assistant = uuid4()
        result = service.persist_session_turn(session_turn=turn, assistant_message_id=assistant, occurred_at=when)
        assert result.status is DirectorRuntimeGovernedTurnPersistenceStatus.PERSISTED
        assert result.discussion_persistence.persisted_turn.assistant_message_inserted is True
        assert _counts(db)[0] == before[0] + 1 and _counts(db)[1:] == before[1:]
        db.rollback()
        assert _counts(db) == before
        result = service.persist_session_turn(session_turn=turn, assistant_message_id=assistant, occurred_at=when)
        db.commit(); assert _counts(db)[0] == before[0] + 1
        replay = service.persist_session_turn(session_turn=turn, assistant_message_id=assistant, occurred_at=when)
        assert replay.status is DirectorRuntimeGovernedTurnPersistenceStatus.PERSISTED and _counts(db)[0] == before[0] + 1
    finally: db.close(); engine.dispose()


def test_runtime_failure_and_forged_handoff_write_nothing(tmp_path):
    engine, db = _db(tmp_path)
    try:
        when = _seed(db); service = DirectorRuntimeGovernedTurnPersistenceService(session=db); before = _counts(db)
        failed = service.persist_session_turn(session_turn=_turn(db, candidate=False), assistant_message_id=uuid4(), occurred_at=when)
        assert failed.status is DirectorRuntimeGovernedTurnPersistenceStatus.NOT_ADMITTED and _counts(db) == before
        forged = replace(_turn(db), assistant_message_sequence_no=8)
        with pytest.raises(DirectorRuntimeGovernedTurnPersistenceError, match="handoff_invalid"):
            service.persist_session_turn(session_turn=forged, assistant_message_id=uuid4(), occurred_at=when)
        assert _counts(db) == before
    finally: db.close(); engine.dispose()


def test_current_assistant_payload_conflict_preserves_c2_error(tmp_path):
    engine, db = _db(tmp_path)
    try:
        when = _seed(db); assistant = uuid4()
        ProjectDirectorMessageRepository(db).create(ProjectDirectorMessage(id=assistant, session_id=SESSION, role=ProjectDirectorMessageRole.ASSISTANT, content="historical response", sequence_no=2, related_project_id=PROJECT, source=ProjectDirectorMessageSource.AI, source_detail="director_runtime", created_at=when)); db.commit()
        service = DirectorRuntimeGovernedTurnPersistenceService(session=db)
        with pytest.raises(ValueError, match="discussion_turn_assistant_message_conflict"):
            service.persist_session_turn(session_turn=_turn(db), assistant_message_id=assistant, occurred_at=when)
    finally: db.close(); engine.dispose()


def test_c3_hard_failure_rolls_back_c2_savepoint(tmp_path):
    engine, db = _db(tmp_path)
    try:
        when = _seed(db); turn = _turn(db); before = _counts(db)
        class FailingC3:
            def admit(self, **kwargs):
                raise RuntimeError("c3 deliberately failed")
        service = DirectorRuntimeGovernedTurnPersistenceService(session=db, formalization_admission=FailingC3())
        with pytest.raises(RuntimeError, match="c3 deliberately failed"):
            service.persist_session_turn(session_turn=turn, assistant_message_id=uuid4(), occurred_at=when)
        assert _counts(db) == before
    finally: db.close(); engine.dispose()


def test_stale_before_c4b_and_assistant_conflict_write_nothing(tmp_path):
    engine, db = _db(tmp_path)
    try:
        when = _seed(db); turn = _turn(db); service = DirectorRuntimeGovernedTurnPersistenceService(session=db); before = _counts(db)
        ProjectDirectorMessageRepository(db).create(ProjectDirectorMessage(id=uuid4(), session_id=SESSION, role=ProjectDirectorMessageRole.USER, content="U2", sequence_no=2, related_project_id=PROJECT, source=ProjectDirectorMessageSource.SYSTEM, source_detail="c4b", created_at=when)); db.commit()
        with pytest.raises(DirectorRuntimeGovernedTurnPersistenceError, match="current_turn_stale"):
            service.persist_session_turn(session_turn=turn, assistant_message_id=uuid4(), occurred_at=when)
        assert _counts(db) == tuple(value + (1 if i == 0 else 0) for i, value in enumerate(before))
    finally: db.close(); engine.dispose()
