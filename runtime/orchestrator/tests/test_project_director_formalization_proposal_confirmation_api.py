"""P26-H2-T3-M6-R1-D: Exact Proposal Confirmation API Boundaries.

Tests the formalization proposal confirmation endpoint
(``POST /project-director/sessions/{session_id}/discussion/formalize``) with the
real API, real SQLite, and a deterministic fake Plan Service.

Covers:
- Success confirmation (9 assertions)
- Request schema rejection (6 scenarios) — each proves the Formalization Service
  is never dispatched and no PlanVersion is created
- Business rejection with exact error codes (13 reachable scenarios)
- Each rejection: PlanVersion increment = 0, Proposal status unchanged

There are no skips/xfails. A "target mismatch" is only reachable as a schema
rejection: ``FormalizeDiscussionRequest.target`` is ``Literal["plan_revision"]``
and the domain ``FormalizationTarget`` enum defines only ``PLAN_REVISION``, so an
unsupported target is turned away at request validation before service dispatch
(see ``test_unsupported_target_rejected_before_service_dispatch``).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.router import api_router
from app.api.routes.project_director import _get_discussion_formalization_service
from app.core.db import (
    begin_sqlite_transaction,
    configure_sqlite,
    get_db_session,
)
from app.core.db_tables import (
    ORMBase,
    ProjectDirectorDiscussionEventTable,
    ProjectDirectorDiscussionWorkspaceTable,
    ProjectDirectorFormalizationProposalTable,
    ProjectDirectorMessageTable,
    ProjectDirectorPlanVersionTable,
    ProjectDirectorSessionTable,
    ProjectTable,
    AgentSessionTable,
    RunTable,
    TaskTable,
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
    DiscussionStatus,
    DiscussionWorkspace,
)
from app.domain.project_director_formalization_proposal import (
    FormalizationProposalStatus,
    ProjectDirectorFormalizationProposal,
)
from app.domain.project_director_message import (
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_plan_version import (
    PlanVersionStatus,
    ProjectDirectorPlanVersion,
)
from app.domain.project_director_session import ProjectDirectorSessionStatus
from app.domain.project_role import ProjectRoleCode
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.services.project_director_discussion_formalization_service import (
    ProjectDirectorDiscussionFormalizationService,
)
from app.services.project_director_plan_service import ProjectDirectorPlanService


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SESSION_ID = UUID("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
PROJECT_ID = UUID("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
OTHER_SESSION_ID = UUID("cccccccccccccccccccccccccccccccc")
OTHER_PROJECT_ID = UUID("dddddddddddddddddddddddddddddddd")
FIXED_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)
LATER_TIME = datetime(2026, 1, 2, tzinfo=timezone.utc)

FORMALIZE_PATH = "/project-director/sessions/{sid}/discussion/formalize"


# ---------------------------------------------------------------------------
# Fake Plan Service collaborators (deterministic, no real Provider)
# ---------------------------------------------------------------------------


class _FakeProviderConfigService:
    """Deterministic Provider config service."""

    def __init__(self, *, configured: bool = True, model: str = "test-plan-model") -> None:
        self.configured = configured
        self._model = model

    def resolve_openai_runtime_config(self):
        return SimpleNamespace(
            api_key="test-provider-key" if self.configured else None,
            base_url="https://provider.invalid/v1",
            timeout_seconds=1,
            detected_provider_type="openai_compatible",
            model_names={"balanced": self._model},
        )


class _FakeProviderTextGenerator:
    """Deterministic Provider text generator."""

    def __init__(self, response: str | None = None) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self._response = response or _default_plan_payload()

    def __call__(self, model_name: str, prompt: str, request_id: str = "") -> tuple[str, str]:
        self.calls.append((model_name, prompt, request_id))
        return self._response, "test-receipt-id"


class _SequencedProviderTextGenerator:
    def __init__(self, responses: list[str]) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self._responses = iter(responses)

    def __call__(self, model_name: str, prompt: str, request_id: str = "") -> tuple[str, str]:
        self.calls.append((model_name, prompt, request_id))
        return next(self._responses), f"test-receipt-{len(self.calls)}"


def _default_plan_payload() -> str:
    return json.dumps(
        {
            "plan_summary": "测试计划摘要",
            "phases": [
                {"sequence": 1, "name": "阶段1", "goal": "目标1", "task_count_hint": 1}
            ],
            "proposed_tasks": [
                {
                    "title": "任务1",
                    "description": "描述",
                    "suggested_role_code": ProjectRoleCode.ENGINEER.value,
                    "priority_hint": "normal",
                }
            ],
            "acceptance_criteria": ["标准1"],
            "risks": ["风险1"],
            "project_scope": {
                "in_scope": ["范围1"],
                "out_of_scope": [],
                "assumptions": [],
            },
            "agent_team_suggestions": [],
            "skill_binding_suggestions": [],
            "verification_mechanisms": [],
            "repository_binding_suggestions": [],
            "deliverable_boundaries": [],
            "complexity_assessment": {
                "level": "medium",
                "label": "中等",
                "score": 2,
                "recommended_agent_count": 2,
                "drivers": [],
                "mitigation_suggestions": [],
            },
        },
        ensure_ascii=False,
    )


def _plan_payload_without_execution_boundary() -> str:
    payload = json.loads(_default_plan_payload())
    payload["project_scope"] = {
        "in_scope": ["范围1"],
        "out_of_scope": ["仅口头确认"],
        "assumptions": ["后续状态由系统界面展示"],
    }
    return json.dumps(payload, ensure_ascii=False)


def _plan_payload_with_execution_boundary() -> str:
    payload = json.loads(_default_plan_payload())
    payload["project_scope"] = {
        "in_scope": ["范围1"],
        "out_of_scope": ["不自动创建任务", "不自动调用 Worker", "不写仓库"],
        "assumptions": ["草案不会自动执行；后续执行由用户单独确认"],
    }
    return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_project(db_session: Session, *, project_id=PROJECT_ID):
    """Insert a project row if it doesn't exist."""
    existing = db_session.get(ProjectTable, project_id)
    if existing is not None:
        return
    row = ProjectTable(
        id=project_id,
        name="测试项目",
        summary="测试项目摘要",
        status="active",
        stage="planning",
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )
    db_session.add(row)
    db_session.flush()


def _seed_session(
    db_session: Session,
    *,
    session_id=SESSION_ID,
    project_id=PROJECT_ID,
    status=ProjectDirectorSessionStatus.CONFIRMED,
):
    """Insert a session row directly (seeds its project for FK integrity)."""
    existing = db_session.get(ProjectDirectorSessionTable, session_id)
    if existing is not None:
        return existing
    _seed_project(db_session, project_id=project_id)
    row = ProjectDirectorSessionTable(
        id=session_id,
        project_id=project_id,
        goal_text="测试目标：构建一个系统",
        constraints="",
        status=status,
        clarifying_questions_json="[]",
        clarifying_answers_json="[]",
        goal_summary="测试目标摘要",
        confirmed_at=FIXED_TIME if status == ProjectDirectorSessionStatus.CONFIRMED else None,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _seed_message(
    db_session: Session,
    session_id: UUID = SESSION_ID,
    *,
    project_id: UUID = PROJECT_ID,
    message_id: UUID | None = None,
    content: str = "用户消息",
    sequence_no: int = 1,
    role=ProjectDirectorMessageRole.USER,
) -> UUID:
    """Insert a message row and return its ID (ensures session + project exist)."""
    if db_session.get(ProjectDirectorSessionTable, session_id) is None:
        _seed_session(db_session, session_id=session_id, project_id=project_id)
    mid = message_id or uuid4()
    row = ProjectDirectorMessageTable(
        id=mid,
        session_id=session_id,
        role=role,
        content=content,
        sequence_no=sequence_no,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail="test",
        created_at=FIXED_TIME,
    )
    db_session.add(row)
    db_session.flush()
    return mid


def _make_event(
    session_id: UUID = SESSION_ID,
    *,
    project_id=PROJECT_ID,
    sequence_no: int = 1,
    event_type: DiscussionEventType = DiscussionEventType.TOPIC_SET,
    content: str = "测试主题",
    subject_key: str = "topic",
    status: DiscussionEventStatus = DiscussionEventStatus.ACTIVE,
    source_message_ids: list[UUID] | None = None,
    payload: dict | None = None,
    created_by: DiscussionActorClaim = DiscussionActorClaim.USER_EXPLICIT,
    event_id: UUID | None = None,
    created_at: datetime = FIXED_TIME,
) -> DiscussionEvent:
    return DiscussionEvent(
        id=event_id or uuid4(),
        session_id=session_id,
        project_id=project_id,
        sequence_no=sequence_no,
        event_type=event_type,
        subject_key=subject_key,
        content=content,
        status=status,
        payload=payload or {},
        source_message_ids=source_message_ids or [],
        supersedes_event_id=None,
        created_by=created_by,
        confidence=1.0,
        created_at=created_at,
    )


def _persist_event(db_session: Session, event_obj: DiscussionEvent):
    """Insert a DiscussionEvent row directly."""
    row = ProjectDirectorDiscussionEventTable(
        id=event_obj.id,
        session_id=event_obj.session_id,
        project_id=event_obj.project_id,
        sequence_no=event_obj.sequence_no,
        event_type=event_obj.event_type,
        subject_key=event_obj.subject_key,
        content=event_obj.content,
        status=event_obj.status,
        payload_json=json.dumps(event_obj.payload, default=str),
        source_message_ids_json=json.dumps(
            [str(mid) for mid in event_obj.source_message_ids]
        ),
        supersedes_event_id=event_obj.supersedes_event_id,
        created_by=event_obj.created_by,
        confidence=event_obj.confidence,
        idempotency_key=f"test-{event_obj.id}",
        created_at=event_obj.created_at,
    )
    db_session.add(row)
    db_session.flush()


def _make_workspace(
    session_id: UUID = SESSION_ID,
    *,
    project_id=PROJECT_ID,
    topic: str = "测试主题",
    discussion_status: DiscussionStatus = DiscussionStatus.READY_TO_FORMALIZE,
    version_no: int = 1,
    last_event_sequence_no: int = 2,
) -> DiscussionWorkspace:
    now = datetime.now(timezone.utc)
    return DiscussionWorkspace(
        session_id=session_id,
        project_id=project_id,
        topic=topic,
        discussion_status=discussion_status,
        active_option_ids=[],
        preferred_option_id=None,
        active_constraint_ids=[],
        open_question_ids=[],
        temporary_conclusion_ids=[],
        confirmed_decision_ids=[],
        latest_user_correction_event_id=None,
        version_no=version_no,
        last_event_sequence_no=last_event_sequence_no,
        created_at=now,
        updated_at=now,
    )


def _persist_workspace(db_session: Session, ws: DiscussionWorkspace):
    """Insert or update a workspace row."""
    state = {
        "active_option_ids": [],
        "preferred_option_id": None,
        "active_constraint_ids": [],
        "open_question_ids": [],
        "temporary_conclusion_ids": [],
        "confirmed_decision_ids": [],
        "latest_user_correction_event_id": None,
    }
    existing = db_session.get(
        ProjectDirectorDiscussionWorkspaceTable, ws.session_id
    )
    if existing is not None:
        existing.topic = ws.topic
        existing.discussion_status = ws.discussion_status
        existing.state_json = json.dumps(state)
        existing.version_no = ws.version_no
        existing.last_event_sequence_no = ws.last_event_sequence_no
        existing.updated_at = ws.updated_at
    else:
        row = ProjectDirectorDiscussionWorkspaceTable(
            session_id=ws.session_id,
            project_id=ws.project_id,
            topic=ws.topic,
            discussion_status=ws.discussion_status,
            state_json=json.dumps(state),
            version_no=ws.version_no,
            last_event_sequence_no=ws.last_event_sequence_no,
            created_at=ws.created_at,
            updated_at=ws.updated_at,
        )
        db_session.add(row)
    db_session.flush()


def _make_proposal(
    *,
    proposal_id: UUID | None = None,
    session_id: UUID = SESSION_ID,
    project_id: UUID = PROJECT_ID,
    assistant_message_id: UUID,
    workspace_version: int = 1,
    target: FormalizationTarget = FormalizationTarget.PLAN_REVISION,
    summary: str = "测试草案",
    changes: list[FormalizationChange] | None = None,
    source_message_ids: list[UUID],
    source_event_ids: list[UUID],
    risk_summary: str = "低风险",
    status: FormalizationProposalStatus = FormalizationProposalStatus.PROPOSED,
    confirmed_plan_version_id: UUID | None = None,
    created_at: datetime = LATER_TIME,
) -> ProjectDirectorFormalizationProposal:
    """Build a formalization proposal domain object."""
    if changes is None:
        changes = [
            FormalizationChange(
                change_type=FormalizationChangeType.UPDATE,
                subject_key="topic",
                summary="更新主题",
                source_event_ids=list(source_event_ids),
            )
        ]
    return ProjectDirectorFormalizationProposal(
        proposal_id=proposal_id or uuid4(),
        session_id=session_id,
        project_id=project_id,
        assistant_message_id=assistant_message_id,
        workspace_version=workspace_version,
        target=target,
        summary=summary,
        changes=changes,
        source_message_ids=source_message_ids,
        source_event_ids=source_event_ids,
        risk_summary=risk_summary,
        status=status,
        confirmed_plan_version_id=confirmed_plan_version_id,
        created_at=created_at,
        updated_at=created_at,
        confirmed_at=None,
    )


def _persist_proposal(db_session: Session, proposal: ProjectDirectorFormalizationProposal):
    """Insert a formalization proposal row directly."""
    row = ProjectDirectorFormalizationProposalTable(
        proposal_id=proposal.proposal_id,
        session_id=proposal.session_id,
        project_id=proposal.project_id,
        assistant_message_id=proposal.assistant_message_id,
        workspace_version=proposal.workspace_version,
        target=proposal.target.value,
        proposal_json=json.dumps(
            proposal.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        source_message_ids_json=json.dumps(
            [str(mid) for mid in proposal.source_message_ids],
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        source_event_ids_json=json.dumps(
            [str(eid) for eid in proposal.source_event_ids],
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        status=proposal.status.value,
        confirmed_plan_version_id=proposal.confirmed_plan_version_id,
        created_at=proposal.created_at,
        updated_at=proposal.updated_at,
        confirmed_at=proposal.confirmed_at,
    )
    db_session.add(row)
    db_session.flush()


def _seed_ready_scenario(
    db_session: Session,
    *,
    session_id: UUID = SESSION_ID,
    project_id: UUID = PROJECT_ID,
    workspace_version: int = 1,
    session_status=ProjectDirectorSessionStatus.CONFIRMED,
) -> tuple[UUID, UUID, UUID, UUID]:
    """Seed a complete ready-to-formalize scenario.

    Returns: (user_message_id, assistant_message_id, topic_event_id, proposal_id)
    """
    _seed_session(
        db_session,
        session_id=session_id,
        project_id=project_id,
        status=session_status,
    )

    user_msg_id = _seed_message(
        db_session, session_id=session_id, project_id=project_id,
        content="用户消息", sequence_no=1,
    )
    assistant_msg_id = _seed_message(
        db_session, session_id=session_id, project_id=project_id,
        content="助手回复", sequence_no=2,
        role=ProjectDirectorMessageRole.ASSISTANT,
    )

    topic_event = _make_event(
        session_id=session_id,
        project_id=project_id,
        sequence_no=1,
        event_type=DiscussionEventType.TOPIC_SET,
        content="测试主题",
        source_message_ids=[user_msg_id],
        created_at=FIXED_TIME,
    )
    _persist_event(db_session, topic_event)

    formalization_event = _make_event(
        session_id=session_id,
        project_id=project_id,
        sequence_no=2,
        event_type=DiscussionEventType.FORMALIZATION_REQUESTED,
        content="请求正式化",
        source_message_ids=[user_msg_id],
        created_at=FIXED_TIME,
    )
    _persist_event(db_session, formalization_event)

    ws = _make_workspace(
        session_id=session_id,
        project_id=project_id,
        topic="测试主题",
        discussion_status=DiscussionStatus.READY_TO_FORMALIZE,
        version_no=workspace_version,
        last_event_sequence_no=2,
    )
    _persist_workspace(db_session, ws)

    proposal = _make_proposal(
        session_id=session_id,
        project_id=project_id,
        assistant_message_id=assistant_msg_id,
        workspace_version=workspace_version,
        source_message_ids=[user_msg_id],
        source_event_ids=[topic_event.id],
        created_at=LATER_TIME,
    )
    _persist_proposal(db_session, proposal)

    return user_msg_id, assistant_msg_id, topic_event.id, proposal.proposal_id


# ---------------------------------------------------------------------------
# Read-back helpers
# ---------------------------------------------------------------------------


def _count_plan_versions(db_session: Session, session_id: UUID = SESSION_ID) -> int:
    return db_session.execute(
        select(func.count())
        .select_from(ProjectDirectorPlanVersionTable)
        .where(ProjectDirectorPlanVersionTable.session_id == session_id)
    ).scalar_one()


def _get_proposal_row(db_session: Session, proposal_id: UUID):
    return db_session.get(ProjectDirectorFormalizationProposalTable, proposal_id)


def _get_proposal_status(db_session: Session, proposal_id: UUID):
    row = _get_proposal_row(db_session, proposal_id)
    return FormalizationProposalStatus(row.status) if row is not None else None


def _delete_message(db_session: Session, message_id: UUID):
    db_session.execute(
        delete(ProjectDirectorMessageTable).where(
            ProjectDirectorMessageTable.id == message_id
        )
    )
    db_session.flush()


def _delete_message_bypass_fk(db_engine, message_id: UUID):
    """Delete a message WITHOUT triggering ON DELETE CASCADE.

    ``project_director_formalization_proposals.assistant_message_id`` references
    ``project_director_messages.id`` with ``ON DELETE CASCADE``. To simulate the
    defensive "assistant message no longer exists" state the service guards
    against, we must remove the message while keeping the proposal row, so FK
    enforcement is turned off on a dedicated raw connection for the delete.
    """
    raw = db_engine.raw_connection()
    try:
        raw.execute("PRAGMA foreign_keys = OFF")
        raw.execute(
            "DELETE FROM project_director_messages WHERE id = ?",
            (message_id.hex,),
        )
        raw.commit()
    finally:
        raw.execute("PRAGMA foreign_keys = ON")
        raw.close()


def _insert_plain_plan_version(db_session: Session, *, session_id: UUID, project_id: UUID) -> UUID:
    """Insert a minimal, non-formalized PlanVersion row and return its id."""
    pv = ProjectDirectorPlanVersion(
        id=uuid4(),
        session_id=session_id,
        project_id=project_id,
        version_no=999,
        status=PlanVersionStatus.PENDING_CONFIRMATION,
        plan_summary="外部计划",
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )
    row = ProjectDirectorPlanVersionTable(
        id=pv.id,
        session_id=pv.session_id,
        project_id=pv.project_id,
        version_no=pv.version_no,
        status=pv.status.value,
        plan_summary=pv.plan_summary,
        phases_json=json.dumps([]),
        proposed_tasks_json=json.dumps([]),
        acceptance_criteria_json=json.dumps([]),
        risks_json=json.dumps([]),
        project_scope_json=json.dumps({}),
        agent_team_suggestions_json=json.dumps([]),
        skill_binding_suggestions_json=json.dumps([]),
        verification_mechanisms_json=json.dumps([]),
        repository_binding_suggestions_json=json.dumps([]),
        deliverable_boundaries_json=json.dumps([]),
        complexity_assessment_json=json.dumps({}),
        source="test",
        source_detail="test",
        forbidden_actions_json=json.dumps([]),
        formalization_proposal_id=None,
        formalization_target=None,
        formalization_workspace_version=None,
        formalization_source_message_ids_json=None,
        formalization_source_event_ids_json=None,
        confirmed_at=None,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )
    db_session.add(row)
    db_session.flush()
    return pv.id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_engine(tmp_path):
    db_path = tmp_path / "p26-confirmation-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    event.listen(engine, "connect", configure_sqlite)
    event.listen(engine, "begin", begin_sqlite_transaction)
    ORMBase.metadata.create_all(bind=engine)
    return engine


@pytest.fixture()
def db_session(db_engine):
    session = sessionmaker(
        bind=db_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def db_session_factory(db_engine):
    return sessionmaker(
        bind=db_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


def _build_formalization_service(
    session: Session,
    *,
    provider_text_generator: object | None = None,
):
    """Build the real formalization service wired to a deterministic fake Plan
    Service (no real Provider)."""
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

    plan_version_repo = ProjectDirectorPlanVersionRepository(session)
    session_repo = ProjectDirectorSessionRepository(session)
    plan_service = ProjectDirectorPlanService(
        plan_version_repository=plan_version_repo,
        session_repository=session_repo,
        provider_config_service=_FakeProviderConfigService(configured=True),
        provider_text_generator=provider_text_generator or _FakeProviderTextGenerator(),
    )
    return ProjectDirectorDiscussionFormalizationService(
        session_repository=session_repo,
        discussion_workspace_repository=ProjectDirectorDiscussionWorkspaceRepository(session),
        discussion_event_repository=ProjectDirectorDiscussionEventRepository(session),
        message_repository=ProjectDirectorMessageRepository(session),
        formalization_proposal_repository=ProjectDirectorFormalizationProposalRepository(session),
        plan_version_repository=plan_version_repo,
        plan_service=plan_service,
    )


class _FormalizationServiceSpy:
    """Wraps the real service and records every ``formalize_discussion`` dispatch.

    Used to prove that schema-level rejections never reach the business layer:
    if a request is rejected before service dispatch, ``call_log`` stays empty.
    """

    def __init__(self, real_service, call_log: list) -> None:
        self._real = real_service
        self._call_log = call_log

    def formalize_discussion(self, **kwargs):
        self._call_log.append(kwargs)
        return self._real.formalize_discussion(**kwargs)

    def __getattr__(self, name):
        return getattr(self._real, name)


def _make_app(
    db_engine,
    *,
    spy_log: list | None = None,
    provider_text_generator: object | None = None,
) -> FastAPI:
    """Assemble the API app with DB + formalization-service overrides.

    When ``spy_log`` is provided, the injected service is wrapped so every
    ``formalize_discussion`` dispatch is recorded into that list.
    """
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

    def override_formalization_service(session: Session = Depends(get_db_session)):
        service = _build_formalization_service(
            session,
            provider_text_generator=provider_text_generator,
        )
        if spy_log is None:
            return service
        return _FormalizationServiceSpy(service, spy_log)

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[_get_discussion_formalization_service] = (
        override_formalization_service
    )
    return app


@pytest.fixture()
def client(db_engine):
    app = _make_app(db_engine)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def spy_client(db_engine):
    """Yield ``(client, spy_log)`` where ``spy_log`` records every
    ``formalize_discussion`` dispatch. Empty log ⇒ service never dispatched."""
    spy_log: list = []
    app = _make_app(db_engine, spy_log=spy_log)
    with TestClient(app) as test_client:
        yield test_client, spy_log
    app.dependency_overrides.clear()


def _formalize(client: TestClient, session_id: UUID, payload: dict):
    return client.post(FORMALIZE_PATH.format(sid=session_id), json=payload)


def _valid_payload(proposal_id: UUID, workspace_version: int = 1) -> dict:
    return {
        "proposal_id": str(proposal_id),
        "workspace_version": workspace_version,
        "target": "plan_revision",
        "user_confirmed": True,
    }


# ===========================================================================
# §1 Success Confirmation
# ===========================================================================


class TestSuccessConfirmation:
    """Successful proposal confirmation with all assertions."""

    def test_success_confirmation_full(self, db_session, db_session_factory, client):
        """Full success path: request has proposal_id, 201, pending_confirmation,
        provenance from proposal, proposal confirmed, resume hides proposal."""
        user_msg_id, assistant_msg_id, event_id, proposal_id = _seed_ready_scenario(db_session)
        db_session.commit()

        resp = _formalize(client, SESSION_ID, _valid_payload(proposal_id))

        # 1 & 2. Request carries proposal_id and returns HTTP 201
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["proposal_id"] == str(proposal_id)

        pv = data["plan_version"]

        # 3. PlanVersion = pending_confirmation
        assert pv["status"] == PlanVersionStatus.PENDING_CONFIRMATION.value

        # 4. formalization_proposal_id correct
        assert pv["formalization_proposal_id"] == str(proposal_id)

        # 5. workspace/target/source messages/source events come from the Proposal
        assert pv["formalization_workspace_version"] == 1
        assert pv["formalization_target"] == "plan_revision"
        assert str(user_msg_id) in pv["formalization_source_message_ids"]
        assert str(event_id) in pv["formalization_source_event_ids"]

        # Read back from a fresh session (the API committed on its own session)
        fresh = db_session_factory()
        try:
            # 6. Proposal becomes confirmed
            assert _get_proposal_status(fresh, proposal_id) == FormalizationProposalStatus.CONFIRMED

            proposal_row = _get_proposal_row(fresh, proposal_id)
            # 7. confirmed_plan_version_id correct
            assert proposal_row.confirmed_plan_version_id is not None
            assert str(proposal_row.confirmed_plan_version_id) == pv["id"]
            # 8. confirmed_at non-empty
            assert proposal_row.confirmed_at is not None

            # Exactly one new PlanVersion was created
            assert _count_plan_versions(fresh, SESSION_ID) == 1
        finally:
            fresh.close()

        # 9. Resume no longer returns the Proposal
        resume_resp = client.get(
            "/project-director/workbench/resume",
            params={
                "session_id": str(SESSION_ID),
                "mode": "project",
                "project_id": str(PROJECT_ID),
            },
        )
        assert resume_resp.status_code == 200
        assert resume_resp.json()["formalization_proposal"] is None


# ===========================================================================
# §2 Request Schema Rejection
# ===========================================================================


class TestRequestSchemaRejection:
    """Request schema validation failures.

    Every scenario is rejected at the FastAPI/pydantic request-validation layer
    and therefore must:
      - return HTTP 422 with the offending field in the error ``loc``;
      - never dispatch the Formalization Service (spy log stays empty);
      - create no PlanVersion (increment == 0).
    """

    def test_missing_proposal_id(self, db_session, db_session_factory, spy_client):
        client, spy_log = spy_client
        _seed_ready_scenario(db_session)
        db_session.commit()

        resp = _formalize(client, SESSION_ID, {
            "workspace_version": 1,
            "target": "plan_revision",
            "user_confirmed": True,
        })
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert isinstance(detail, list)
        assert any("proposal_id" in str(err.get("loc", [])) for err in detail)
        assert spy_log == []

        fresh = db_session_factory()
        try:
            assert _count_plan_versions(fresh, SESSION_ID) == 0
        finally:
            fresh.close()

    def test_malformed_proposal_id(self, db_session, db_session_factory, spy_client):
        client, spy_log = spy_client
        _seed_ready_scenario(db_session)
        db_session.commit()

        resp = _formalize(client, SESSION_ID, {
            "proposal_id": "not-a-uuid",
            "workspace_version": 1,
            "target": "plan_revision",
            "user_confirmed": True,
        })
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert isinstance(detail, list)
        assert any("proposal_id" in str(err.get("loc", [])) for err in detail)
        assert spy_log == []

        fresh = db_session_factory()
        try:
            assert _count_plan_versions(fresh, SESSION_ID) == 0
        finally:
            fresh.close()

    def test_user_confirmed_false(self, db_session, db_session_factory, spy_client):
        client, spy_log = spy_client
        _seed_ready_scenario(db_session)
        db_session.commit()

        resp = _formalize(client, SESSION_ID, {
            "proposal_id": str(uuid4()),
            "workspace_version": 1,
            "target": "plan_revision",
            "user_confirmed": False,
        })
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert isinstance(detail, list)
        assert any("user_confirmed" in str(err.get("loc", [])) for err in detail)
        assert spy_log == []

        fresh = db_session_factory()
        try:
            assert _count_plan_versions(fresh, SESSION_ID) == 0
        finally:
            fresh.close()

    def test_missing_user_confirmed(self, db_session, db_session_factory, spy_client):
        client, spy_log = spy_client
        _seed_ready_scenario(db_session)
        db_session.commit()

        resp = _formalize(client, SESSION_ID, {
            "proposal_id": str(uuid4()),
            "workspace_version": 1,
            "target": "plan_revision",
        })
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert isinstance(detail, list)
        assert any("user_confirmed" in str(err.get("loc", [])) for err in detail)
        assert spy_log == []

        fresh = db_session_factory()
        try:
            assert _count_plan_versions(fresh, SESSION_ID) == 0
        finally:
            fresh.close()

    def test_workspace_version_less_than_1(self, db_session, db_session_factory, spy_client):
        client, spy_log = spy_client
        _seed_ready_scenario(db_session)
        db_session.commit()

        resp = _formalize(client, SESSION_ID, {
            "proposal_id": str(uuid4()),
            "workspace_version": 0,
            "target": "plan_revision",
            "user_confirmed": True,
        })
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert isinstance(detail, list)
        assert any("workspace_version" in str(err.get("loc", [])) for err in detail)
        assert spy_log == []

        fresh = db_session_factory()
        try:
            assert _count_plan_versions(fresh, SESSION_ID) == 0
        finally:
            fresh.close()

    def test_unsupported_target_rejected_before_service_dispatch(
        self, db_session, db_session_factory, spy_client
    ):
        """An unsupported ``target`` string is rejected before service dispatch.

        ``FormalizeDiscussionRequest.target`` is typed ``Literal["plan_revision"]``
        and the domain ``FormalizationTarget`` enum defines only ``PLAN_REVISION``,
        so any other value is turned away at the request-validation layer. This is
        the sole reachable form of a "target mismatch": there is no second legal
        enum value that could reach the service and trip a business-level mismatch.
        """
        client, spy_log = spy_client
        _, _, _, proposal_id = _seed_ready_scenario(db_session)
        db_session.commit()

        resp = _formalize(client, SESSION_ID, {
            "proposal_id": str(proposal_id),
            "workspace_version": 1,
            "target": "wrong_target",
            "user_confirmed": True,
        })

        # HTTP 422 with the error located on the ``target`` field.
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert isinstance(detail, list)
        assert any("target" in str(err.get("loc", [])) for err in detail)

        # Formalization Service was never dispatched.
        assert spy_log == []

        # No PlanVersion created and the Proposal is untouched.
        fresh = db_session_factory()
        try:
            assert _count_plan_versions(fresh, SESSION_ID) == 0
            assert _get_proposal_status(fresh, proposal_id) == FormalizationProposalStatus.PROPOSED
        finally:
            fresh.close()


# ===========================================================================
# §3 Business Rejection with Exact Error Codes
# ===========================================================================


class TestBusinessRejection:
    """Business logic rejections with exact error codes.

    Every scenario asserts: PlanVersion increment == 0 and the Proposal status
    is not erroneously changed.
    """

    def test_01_proposal_not_found(self, db_session, db_session_factory, client):
        _seed_ready_scenario(db_session)
        db_session.commit()

        resp = _formalize(client, SESSION_ID, _valid_payload(uuid4()))

        assert resp.status_code == 409
        assert resp.json()["detail"] == "project_director_formalization_proposal_not_found"

        fresh = db_session_factory()
        try:
            assert _count_plan_versions(fresh, SESSION_ID) == 0
        finally:
            fresh.close()

    def test_02_proposal_belongs_to_other_session(self, db_session, db_session_factory, client):
        # Proposal lives in OTHER_SESSION_ID; we confirm against SESSION_ID.
        _seed_ready_scenario(db_session, session_id=OTHER_SESSION_ID, project_id=PROJECT_ID)
        _seed_session(db_session, session_id=SESSION_ID, project_id=PROJECT_ID)
        db_session.commit()

        fresh = db_session_factory()
        try:
            other_proposal_id = fresh.execute(
                select(ProjectDirectorFormalizationProposalTable.proposal_id).where(
                    ProjectDirectorFormalizationProposalTable.session_id == OTHER_SESSION_ID
                )
            ).scalar_one()
        finally:
            fresh.close()

        resp = _formalize(client, SESSION_ID, _valid_payload(other_proposal_id))

        assert resp.status_code == 409
        assert resp.json()["detail"] == "project_director_formalization_proposal_session_mismatch"

        fresh = db_session_factory()
        try:
            assert _count_plan_versions(fresh, SESSION_ID) == 0
            # Proposal in the other session stays PROPOSED
            assert _get_proposal_status(fresh, other_proposal_id) == FormalizationProposalStatus.PROPOSED
        finally:
            fresh.close()

    def test_03_project_mismatch(self, db_session, db_session_factory, client):
        # Session/project = PROJECT_ID, but the proposal names OTHER_PROJECT_ID.
        _seed_session(db_session, session_id=SESSION_ID, project_id=PROJECT_ID)
        _seed_project(db_session, project_id=OTHER_PROJECT_ID)
        user_msg_id = _seed_message(db_session, session_id=SESSION_ID)
        assistant_msg_id = _seed_message(
            db_session, session_id=SESSION_ID,
            role=ProjectDirectorMessageRole.ASSISTANT, sequence_no=2,
        )
        topic_event = _make_event(
            session_id=SESSION_ID, project_id=PROJECT_ID, sequence_no=1,
            source_message_ids=[user_msg_id],
        )
        _persist_event(db_session, topic_event)
        formalization_event = _make_event(
            session_id=SESSION_ID, project_id=PROJECT_ID, sequence_no=2,
            event_type=DiscussionEventType.FORMALIZATION_REQUESTED,
            source_message_ids=[user_msg_id],
        )
        _persist_event(db_session, formalization_event)
        _persist_workspace(db_session, _make_workspace(session_id=SESSION_ID, project_id=PROJECT_ID))

        proposal = _make_proposal(
            session_id=SESSION_ID,
            project_id=OTHER_PROJECT_ID,  # mismatch with session.project_id
            assistant_message_id=assistant_msg_id,
            source_message_ids=[user_msg_id],
            source_event_ids=[topic_event.id],
        )
        _persist_proposal(db_session, proposal)
        db_session.commit()

        resp = _formalize(client, SESSION_ID, _valid_payload(proposal.proposal_id))

        assert resp.status_code == 409
        assert resp.json()["detail"] == "project_director_formalization_proposal_project_mismatch"

        fresh = db_session_factory()
        try:
            assert _count_plan_versions(fresh, SESSION_ID) == 0
            assert _get_proposal_status(fresh, proposal.proposal_id) == FormalizationProposalStatus.PROPOSED
        finally:
            fresh.close()

    def test_04_request_workspace_mismatch(self, db_session, db_session_factory, client):
        # Proposal is for workspace_version=1; request sends 2.
        _, _, _, proposal_id = _seed_ready_scenario(db_session, workspace_version=1)
        db_session.commit()

        resp = _formalize(client, SESSION_ID, _valid_payload(proposal_id, workspace_version=2))

        assert resp.status_code == 409
        assert resp.json()["detail"] == "project_director_formalization_proposal_workspace_mismatch"

        fresh = db_session_factory()
        try:
            assert _count_plan_versions(fresh, SESSION_ID) == 0
            assert _get_proposal_status(fresh, proposal_id) == FormalizationProposalStatus.PROPOSED
        finally:
            fresh.close()

    def test_05_current_workspace_changed(self, db_session, db_session_factory, client):
        # Proposal & request agree on v1, but the live workspace moved to v2.
        _, _, _, proposal_id = _seed_ready_scenario(db_session, workspace_version=1)
        ws_row = db_session.get(ProjectDirectorDiscussionWorkspaceTable, SESSION_ID)
        ws_row.version_no = 2
        db_session.commit()

        resp = _formalize(client, SESSION_ID, _valid_payload(proposal_id, workspace_version=1))

        assert resp.status_code == 409
        assert resp.json()["detail"] == "project_director_formalization_workspace_version_mismatch"

        fresh = db_session_factory()
        try:
            assert _count_plan_versions(fresh, SESSION_ID) == 0
            assert _get_proposal_status(fresh, proposal_id) == FormalizationProposalStatus.PROPOSED
        finally:
            fresh.close()

    def test_06_proposal_superseded(self, db_session, db_session_factory, client):
        _, _, _, proposal_id = _seed_ready_scenario(db_session)
        proposal_row = _get_proposal_row(db_session, proposal_id)
        proposal_row.status = FormalizationProposalStatus.SUPERSEDED.value
        db_session.commit()

        resp = _formalize(client, SESSION_ID, _valid_payload(proposal_id))

        assert resp.status_code == 409
        assert resp.json()["detail"] == "project_director_formalization_proposal_not_active"

        fresh = db_session_factory()
        try:
            assert _count_plan_versions(fresh, SESSION_ID) == 0
            assert _get_proposal_status(fresh, proposal_id) == FormalizationProposalStatus.SUPERSEDED
        finally:
            fresh.close()

    def test_07_assistant_message_not_found(self, db_session, db_session_factory, db_engine, client):
        _, assistant_msg_id, _, proposal_id = _seed_ready_scenario(db_session)
        db_session.commit()

        # Break lineage after commit: remove the assistant message the proposal names.
        # Use FK-bypass to avoid ON DELETE CASCADE removing the proposal too.
        _delete_message_bypass_fk(db_engine, assistant_msg_id)

        resp = _formalize(client, SESSION_ID, _valid_payload(proposal_id))

        assert resp.status_code == 409
        assert resp.json()["detail"] == "project_director_formalization_proposal_lineage_invalid"

        fresh = db_session_factory()
        try:
            assert _count_plan_versions(fresh, SESSION_ID) == 0
            assert _get_proposal_status(fresh, proposal_id) == FormalizationProposalStatus.PROPOSED
        finally:
            fresh.close()

    def test_08_source_message_not_found(self, db_session, db_session_factory, client):
        user_msg_id, _, _, proposal_id = _seed_ready_scenario(db_session)
        db_session.commit()

        # Break lineage after commit: remove a source message the proposal names.
        _delete_message(db_session, user_msg_id)
        db_session.commit()

        resp = _formalize(client, SESSION_ID, _valid_payload(proposal_id))

        assert resp.status_code == 409
        assert resp.json()["detail"] == "project_director_formalization_source_message_not_found"

        fresh = db_session_factory()
        try:
            assert _count_plan_versions(fresh, SESSION_ID) == 0
            assert _get_proposal_status(fresh, proposal_id) == FormalizationProposalStatus.PROPOSED
        finally:
            fresh.close()

    def test_09_source_event_not_found(self, db_session, db_session_factory, client):
        # Proposal names a source event that is not part of the workspace history.
        _seed_session(db_session, session_id=SESSION_ID, project_id=PROJECT_ID)
        user_msg_id = _seed_message(db_session, session_id=SESSION_ID)
        assistant_msg_id = _seed_message(
            db_session, session_id=SESSION_ID,
            role=ProjectDirectorMessageRole.ASSISTANT, sequence_no=2,
        )
        topic_event = _make_event(
            session_id=SESSION_ID, project_id=PROJECT_ID, sequence_no=1,
            source_message_ids=[user_msg_id],
        )
        _persist_event(db_session, topic_event)
        formalization_event = _make_event(
            session_id=SESSION_ID, project_id=PROJECT_ID, sequence_no=2,
            event_type=DiscussionEventType.FORMALIZATION_REQUESTED,
            source_message_ids=[user_msg_id],
        )
        _persist_event(db_session, formalization_event)
        _persist_workspace(db_session, _make_workspace(session_id=SESSION_ID, project_id=PROJECT_ID))

        missing_event_id = uuid4()  # never persisted
        proposal = _make_proposal(
            session_id=SESSION_ID,
            project_id=PROJECT_ID,
            assistant_message_id=assistant_msg_id,
            source_message_ids=[user_msg_id],
            source_event_ids=[missing_event_id],
        )
        _persist_proposal(db_session, proposal)
        db_session.commit()

        resp = _formalize(client, SESSION_ID, _valid_payload(proposal.proposal_id))

        assert resp.status_code == 409
        assert resp.json()["detail"] == "project_director_formalization_proposal_lineage_invalid"

        fresh = db_session_factory()
        try:
            assert _count_plan_versions(fresh, SESSION_ID) == 0
            assert _get_proposal_status(fresh, proposal.proposal_id) == FormalizationProposalStatus.PROPOSED
        finally:
            fresh.close()

    def test_10_lineage_corrupted(self, db_session, db_session_factory, client):
        # Corrupted lineage: the source event was created AFTER the proposal.
        _seed_session(db_session, session_id=SESSION_ID, project_id=PROJECT_ID)
        user_msg_id = _seed_message(db_session, session_id=SESSION_ID)
        assistant_msg_id = _seed_message(
            db_session, session_id=SESSION_ID,
            role=ProjectDirectorMessageRole.ASSISTANT, sequence_no=2,
        )
        topic_event = _make_event(
            session_id=SESSION_ID, project_id=PROJECT_ID, sequence_no=1,
            source_message_ids=[user_msg_id], created_at=LATER_TIME,  # after proposal
        )
        _persist_event(db_session, topic_event)
        formalization_event = _make_event(
            session_id=SESSION_ID, project_id=PROJECT_ID, sequence_no=2,
            event_type=DiscussionEventType.FORMALIZATION_REQUESTED,
            source_message_ids=[user_msg_id], created_at=LATER_TIME,
        )
        _persist_event(db_session, formalization_event)
        _persist_workspace(db_session, _make_workspace(session_id=SESSION_ID, project_id=PROJECT_ID))

        proposal = _make_proposal(
            session_id=SESSION_ID,
            project_id=PROJECT_ID,
            assistant_message_id=assistant_msg_id,
            source_message_ids=[user_msg_id],
            source_event_ids=[topic_event.id],
            created_at=FIXED_TIME,  # before the event → corrupted
        )
        _persist_proposal(db_session, proposal)
        db_session.commit()

        resp = _formalize(client, SESSION_ID, _valid_payload(proposal.proposal_id))

        assert resp.status_code == 409
        assert resp.json()["detail"] == "project_director_formalization_proposal_lineage_invalid"

        fresh = db_session_factory()
        try:
            assert _count_plan_versions(fresh, SESSION_ID) == 0
            assert _get_proposal_status(fresh, proposal.proposal_id) == FormalizationProposalStatus.PROPOSED
        finally:
            fresh.close()

    def test_11_session_not_confirmed(self, db_session, db_session_factory, client):
        _, _, _, proposal_id = _seed_ready_scenario(
            db_session, session_status=ProjectDirectorSessionStatus.CLARIFYING
        )
        db_session.commit()

        resp = _formalize(client, SESSION_ID, _valid_payload(proposal_id))

        assert resp.status_code == 409
        assert resp.json()["detail"] == "project_director_formalization_session_not_confirmed"

        fresh = db_session_factory()
        try:
            assert _count_plan_versions(fresh, SESSION_ID) == 0
            assert _get_proposal_status(fresh, proposal_id) == FormalizationProposalStatus.PROPOSED
        finally:
            fresh.close()

    def test_12_confirmed_proposal_replay_different_params(self, db_session, db_session_factory, client):
        # A confirmed proposal replayed with a different workspace_version is
        # rejected before the confirmed-replay branch (workspace check is first).
        _, _, _, proposal_id = _seed_ready_scenario(db_session, workspace_version=1)
        db_session.commit()

        resp1 = _formalize(client, SESSION_ID, _valid_payload(proposal_id, workspace_version=1))
        assert resp1.status_code == 201

        resp2 = _formalize(client, SESSION_ID, _valid_payload(proposal_id, workspace_version=2))

        assert resp2.status_code == 409
        assert resp2.json()["detail"] == "project_director_formalization_proposal_workspace_mismatch"

        fresh = db_session_factory()
        try:
            # Still exactly one PlanVersion from the first confirmation
            assert _count_plan_versions(fresh, SESSION_ID) == 1
            assert _get_proposal_status(fresh, proposal_id) == FormalizationProposalStatus.CONFIRMED
        finally:
            fresh.close()

    def test_13_proposal_already_bound_to_other_plan_version(self, db_session, db_session_factory, client):
        # Confirm once (binds PV1), then re-point the confirmed proposal at a
        # different PlanVersion (PV2) and replay → already_confirmed_conflict.
        _, _, _, proposal_id = _seed_ready_scenario(db_session)
        db_session.commit()

        resp1 = _formalize(client, SESSION_ID, _valid_payload(proposal_id))
        assert resp1.status_code == 201

        # Insert a second, unrelated PlanVersion and rebind the proposal to it.
        other_pv_id = _insert_plain_plan_version(
            db_session, session_id=SESSION_ID, project_id=PROJECT_ID
        )
        proposal_row = _get_proposal_row(db_session, proposal_id)
        proposal_row.confirmed_plan_version_id = other_pv_id
        db_session.commit()

        resp2 = _formalize(client, SESSION_ID, _valid_payload(proposal_id))

        assert resp2.status_code == 409
        assert resp2.json()["detail"] == "project_director_formalization_idempotency_conflict"

        fresh = db_session_factory()
        try:
            # PV1 (from first confirmation) + PV2 (manually inserted) == 2; no third.
            assert _count_plan_versions(fresh, SESSION_ID) == 2
            assert _get_proposal_status(fresh, proposal_id) == FormalizationProposalStatus.CONFIRMED
        finally:
            fresh.close()


# ===========================================================================
# §4 Idempotent Replay
# ===========================================================================


class TestIdempotentReplay:
    """Idempotent replay of a confirmed proposal with identical parameters."""

    def test_confirmed_proposal_replay_same_params(self, db_session, db_session_factory, client):
        _, _, _, proposal_id = _seed_ready_scenario(db_session)
        db_session.commit()

        resp1 = _formalize(client, SESSION_ID, _valid_payload(proposal_id))
        assert resp1.status_code == 201
        assert resp1.json()["idempotent_replay"] is False
        pv1_id = resp1.json()["plan_version"]["id"]

        resp2 = _formalize(client, SESSION_ID, _valid_payload(proposal_id))
        assert resp2.status_code == 201
        assert resp2.json()["idempotent_replay"] is True
        assert resp2.json()["plan_version"]["id"] == pv1_id

        fresh = db_session_factory()
        try:
            assert _count_plan_versions(fresh, SESSION_ID) == 1
        finally:
            fresh.close()


# ===========================================================================
# §5 Plan boundary repair confirmation
# ===========================================================================


class TestPlanBoundaryRepairConfirmation:
    @staticmethod
    def _assert_no_execution_rows(db_session: Session) -> None:
        for table in (TaskTable, RunTable, AgentSessionTable):
            assert db_session.execute(select(func.count()).select_from(table)).scalar_one() == 0

    def test_repair_failure_keeps_proposal_proposed_and_creates_nothing(
        self, db_engine, db_session, db_session_factory
    ):
        _, _, _, proposal_id = _seed_ready_scenario(db_session)
        db_session.commit()
        provider = _SequencedProviderTextGenerator(
            [_plan_payload_without_execution_boundary()] * 2
        )
        app = _make_app(db_engine, provider_text_generator=provider)
        try:
            with TestClient(app) as client:
                response = _formalize(client, SESSION_ID, _valid_payload(proposal_id))
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 422
        assert len(provider.calls) == 2
        fresh = db_session_factory()
        try:
            proposal = _get_proposal_row(fresh, proposal_id)
            assert proposal.status == FormalizationProposalStatus.PROPOSED.value
            assert proposal.confirmed_plan_version_id is None
            assert proposal.confirmed_at is None
            assert _count_plan_versions(fresh, SESSION_ID) == 0
            self._assert_no_execution_rows(fresh)
        finally:
            fresh.close()

    def test_repair_success_confirms_proposal_without_execution_side_effects(
        self, db_engine, db_session, db_session_factory
    ):
        _, _, _, proposal_id = _seed_ready_scenario(db_session)
        db_session.commit()
        provider = _SequencedProviderTextGenerator(
            [
                _plan_payload_without_execution_boundary(),
                _plan_payload_with_execution_boundary(),
            ]
        )
        app = _make_app(db_engine, provider_text_generator=provider)
        try:
            with TestClient(app) as client:
                response = _formalize(client, SESSION_ID, _valid_payload(proposal_id))
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 201, response.text
        payload = response.json()
        assert len(provider.calls) == 2
        assert payload["plan_version"]["status"] == PlanVersionStatus.PENDING_CONFIRMATION.value
        assert payload["plan_version"]["source"] == "ai"
        assert payload["plan_version"]["formalization_proposal_id"] == str(proposal_id)
        fresh = db_session_factory()
        try:
            proposal = _get_proposal_row(fresh, proposal_id)
            assert proposal.status == FormalizationProposalStatus.CONFIRMED.value
            assert proposal.confirmed_plan_version_id is not None
            assert _count_plan_versions(fresh, SESSION_ID) == 1
            self._assert_no_execution_rows(fresh)
        finally:
            fresh.close()
