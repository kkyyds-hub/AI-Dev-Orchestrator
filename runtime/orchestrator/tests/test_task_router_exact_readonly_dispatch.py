"""Targeted acceptance tests for exact-task readonly routing."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, event, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.db_tables import (
    ORMBase,
    ProjectRoleSkillBindingTable,
    ProjectRoleTable,
    ProjectTable,
    RunTable,
    SkillTable,
    SkillVersionTable,
    TaskTable,
)
from app.domain.project import Project, ProjectStage
from app.domain.project_role import ProjectRoleCode
from app.domain.task import Task
from app.repositories.project_repository import ProjectRepository
from app.repositories.project_role_repository import ProjectRoleRepository
from app.repositories.run_repository import RunRepository
from app.repositories.skill_repository import SkillRepository
from app.repositories.task_repository import TaskRepository
from app.services.budget_guard_service import BudgetGuardService
from app.services.role_catalog_service import RoleCatalogService
from app.services.skill_registry_service import SkillRegistryService
from app.services.strategy_engine_service import StrategyEngineService
from app.domain.run import RunBudgetStrategyAction
from app.services.task_readiness_service import TaskReadinessService
from app.services.task_router_service import TaskRouterService


_BUSINESS_TABLES = (
    ProjectTable,
    ProjectRoleTable,
    SkillTable,
    SkillVersionTable,
    ProjectRoleSkillBindingTable,
    TaskTable,
    RunTable,
)
_WRITE_METHOD_PREFIXES = ("save", "create", "replace", "delete")


@dataclass(slots=True)
class RouterHarness:
    engine: Engine
    session: Session
    project_repository: ProjectRepository
    project_role_repository: ProjectRoleRepository
    skill_repository: SkillRepository
    task_repository: TaskRepository
    run_repository: RunRepository
    role_catalog_service: RoleCatalogService
    skill_registry_service: SkillRegistryService
    strategy_engine_service: StrategyEngineService
    router: TaskRouterService
    project: Project
    task: Task

    def rebuild_router(
        self,
        *,
        role_catalog_service: RoleCatalogService | None = None,
        skill_registry_service: SkillRegistryService | None = None,
    ) -> None:
        role_service = role_catalog_service or self.role_catalog_service
        skill_service = skill_registry_service or self.skill_registry_service
        self.role_catalog_service = role_service
        self.skill_registry_service = skill_service
        self.strategy_engine_service = StrategyEngineService(
            project_repository=self.project_repository,
            role_catalog_service=role_service,
            skill_registry_service=skill_service,
            budget_guard_service=BudgetGuardService(self.run_repository),
        )
        self.router = TaskRouterService(
            task_repository=self.task_repository,
            run_repository=self.run_repository,
            task_readiness_service=TaskReadinessService(
                task_repository=self.task_repository,
                run_repository=self.run_repository,
            ),
            budget_guard_service=BudgetGuardService(self.run_repository),
            strategy_engine_service=self.strategy_engine_service,
        )


@pytest.fixture()
def harness(tmp_path) -> Iterator[RouterHarness]:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'exact-readonly.db'}")
    ORMBase.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=True,
        autocommit=False,
        expire_on_commit=False,
    )
    session = session_factory()
    project_repository = ProjectRepository(session)
    project_role_repository = ProjectRoleRepository(session)
    skill_repository = SkillRepository(session)
    task_repository = TaskRepository(session)
    run_repository = RunRepository(session)
    role_catalog_service = RoleCatalogService(
        project_repository=project_repository,
        project_role_repository=project_role_repository,
    )
    skill_registry_service = SkillRegistryService(
        project_repository=project_repository,
        role_catalog_service=role_catalog_service,
        skill_repository=skill_repository,
    )
    project = project_repository.create(
        Project(
            name="Exact readonly routing",
            summary="Project used by PRE-B targeted acceptance tests.",
            stage=ProjectStage.EXECUTION,
        )
    )
    task = Task(
        project_id=project.id,
        title="实现 exact readonly routing",
        input_summary="实现代码并完成局部验证。",
        acceptance_criteria=["exact evaluator remains readonly"],
    )
    strategy_engine_service = StrategyEngineService(
        project_repository=project_repository,
        role_catalog_service=role_catalog_service,
        skill_registry_service=skill_registry_service,
        budget_guard_service=BudgetGuardService(run_repository),
    )
    router = TaskRouterService(
        task_repository=task_repository,
        run_repository=run_repository,
        task_readiness_service=TaskReadinessService(
            task_repository=task_repository,
            run_repository=run_repository,
        ),
        budget_guard_service=BudgetGuardService(run_repository),
        strategy_engine_service=strategy_engine_service,
    )
    result = RouterHarness(
        engine=engine,
        session=session,
        project_repository=project_repository,
        project_role_repository=project_role_repository,
        skill_repository=skill_repository,
        task_repository=task_repository,
        run_repository=run_repository,
        role_catalog_service=role_catalog_service,
        skill_registry_service=skill_registry_service,
        strategy_engine_service=strategy_engine_service,
        router=router,
        project=project,
        task=task,
    )
    try:
        yield result
    finally:
        session.close()
        engine.dispose()


def _initialize_all_authorities(harness: RouterHarness) -> None:
    assert harness.role_catalog_service.get_project_role_catalog(harness.project.id)
    assert harness.skill_registry_service.get_project_skill_bindings(harness.project.id)


def _business_row_counts(harness: RouterHarness) -> dict[str, int]:
    with harness.engine.connect() as connection:
        return {
            table.__tablename__: connection.scalar(
                select(func.count()).select_from(table)
            )
            or 0
            for table in _BUSINESS_TABLES
        }


@contextmanager
def _forbid_business_writes(
    harness: RouterHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    def fail_write(*args, **kwargs):
        raise AssertionError("exact readonly evaluator attempted a business write")

    repositories = (
        harness.project_repository,
        harness.project_role_repository,
        harness.skill_repository,
        harness.task_repository,
        harness.run_repository,
    )
    for repository in repositories:
        for method_name in dir(repository):
            if method_name.startswith(_WRITE_METHOD_PREFIXES):
                method = getattr(repository, method_name, None)
                if callable(method):
                    monkeypatch.setattr(repository, method_name, fail_write)

    for method_name in ("commit", "flush", "refresh", "add", "add_all", "delete"):
        monkeypatch.setattr(harness.session, method_name, fail_write)

    def reject_mutating_sql(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        del conn, cursor, parameters, context, executemany
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
            raise AssertionError(f"exact readonly evaluator emitted mutating SQL: {statement}")

    event.listen(harness.engine, "before_cursor_execute", reject_mutating_sql)
    try:
        yield
    finally:
        event.remove(harness.engine, "before_cursor_execute", reject_mutating_sql)


def _evaluate_readonly(
    harness: RouterHarness,
    monkeypatch: pytest.MonkeyPatch,
):
    before = _business_row_counts(harness)
    with _forbid_business_writes(harness, monkeypatch):
        candidate = harness.router.evaluate_exact_task_for_dispatch(task=harness.task)
        after = _business_row_counts(harness)
    assert after == before
    return candidate


def _reason_codes(candidate) -> set[str]:
    return {reason.code for reason in candidate.strategy_reasons}


def test_exact_evaluator_resolves_initialized_authorities_without_writes(
    harness: RouterHarness,
    monkeypatch: pytest.MonkeyPatch,
):
    _initialize_all_authorities(harness)

    candidate = _evaluate_readonly(harness, monkeypatch)

    assert candidate.ready is True
    assert candidate.owner_role_code == ProjectRoleCode.ENGINEER
    assert candidate.selected_skill_codes == (
        "code_implementation",
        "change_summary",
        "local_verification",
    )


def test_exact_evaluator_blocks_when_project_roles_are_missing(
    harness: RouterHarness,
    monkeypatch: pytest.MonkeyPatch,
):
    candidate = _evaluate_readonly(harness, monkeypatch)

    assert candidate.ready is False
    assert candidate.owner_role_code is None
    assert candidate.selected_skill_codes == ()
    assert "readonly_role_catalog_initialization_required" in _reason_codes(candidate)
    assert _business_row_counts(harness)[ProjectRoleTable.__tablename__] == 0


def test_exact_evaluator_blocks_on_conflicting_project_roles(
    harness: RouterHarness,
    monkeypatch: pytest.MonkeyPatch,
):
    roles = harness.role_catalog_service.get_project_role_catalog(harness.project.id).roles
    duplicate = roles[0].model_copy(update={"id": uuid4()})
    monkeypatch.setattr(
        harness.project_role_repository,
        "list_by_project_id",
        lambda project_id: [*roles, duplicate],
    )

    candidate = _evaluate_readonly(harness, monkeypatch)

    assert candidate.ready is False
    assert candidate.owner_role_code is None
    assert candidate.selected_skill_codes == ()
    assert "readonly_role_catalog_conflict" in _reason_codes(candidate)


def test_exact_evaluator_blocks_when_skill_registry_is_missing(
    harness: RouterHarness,
    monkeypatch: pytest.MonkeyPatch,
):
    assert harness.role_catalog_service.get_project_role_catalog(harness.project.id)

    candidate = _evaluate_readonly(harness, monkeypatch)

    assert candidate.ready is False
    assert candidate.selected_skill_codes == ()
    assert "readonly_skill_registry_initialization_required" in _reason_codes(candidate)
    assert _business_row_counts(harness)[SkillTable.__tablename__] == 0


def test_exact_evaluator_blocks_when_current_skill_version_is_missing(
    harness: RouterHarness,
    monkeypatch: pytest.MonkeyPatch,
):
    _initialize_all_authorities(harness)
    skill_id = harness.session.scalar(select(SkillTable.id).limit(1))
    harness.session.execute(
        delete(SkillVersionTable).where(SkillVersionTable.skill_id == skill_id)
    )
    harness.session.commit()

    candidate = _evaluate_readonly(harness, monkeypatch)

    assert candidate.ready is False
    assert candidate.selected_skill_codes == ()
    assert "readonly_skill_version_backfill_required" in _reason_codes(candidate)


def test_exact_evaluator_blocks_when_project_bindings_are_empty(
    harness: RouterHarness,
    monkeypatch: pytest.MonkeyPatch,
):
    _initialize_all_authorities(harness)
    harness.session.execute(
        delete(ProjectRoleSkillBindingTable).where(
            ProjectRoleSkillBindingTable.project_id == harness.project.id
        )
    )
    harness.session.commit()

    candidate = _evaluate_readonly(harness, monkeypatch)

    assert candidate.ready is False
    assert candidate.selected_skill_codes == ()
    assert "readonly_skill_bindings_initialization_required" in _reason_codes(candidate)


@pytest.mark.parametrize(
    ("binding_mutator", "expected_reason"),
    [
        (lambda bindings: [*bindings, bindings[0].model_copy(update={"id": uuid4()})],
         "readonly_skill_binding_conflict"),
        (lambda bindings: [bindings[0].model_copy(update={"skill_code": "invalid"}), *bindings[1:]],
         "readonly_skill_binding_invalid"),
    ],
    ids=("duplicate", "invalid"),
)
def test_exact_evaluator_blocks_on_duplicate_or_invalid_binding(
    harness: RouterHarness,
    monkeypatch: pytest.MonkeyPatch,
    binding_mutator,
    expected_reason: str,
):
    _initialize_all_authorities(harness)
    bindings = harness.skill_repository.list_role_bindings_by_project_id(harness.project.id)
    monkeypatch.setattr(
        harness.skill_repository,
        "list_role_bindings_by_project_id",
        lambda project_id: binding_mutator(bindings),
    )

    candidate = _evaluate_readonly(harness, monkeypatch)

    assert candidate.ready is False
    assert candidate.selected_skill_codes == ()
    assert expected_reason in _reason_codes(candidate)


def test_exact_evaluator_fails_closed_on_shared_session_mismatch(
    harness: RouterHarness,
    monkeypatch: pytest.MonkeyPatch,
):
    _initialize_all_authorities(harness)
    other_session = sessionmaker(
        bind=harness.engine,
        autoflush=False,
        expire_on_commit=False,
    )()
    try:
        mismatched_role_service = RoleCatalogService(
            project_repository=harness.project_repository,
            project_role_repository=ProjectRoleRepository(other_session),
        )
        mismatched_skill_service = SkillRegistryService(
            project_repository=harness.project_repository,
            role_catalog_service=mismatched_role_service,
            skill_repository=harness.skill_repository,
        )
        harness.rebuild_router(
            role_catalog_service=mismatched_role_service,
            skill_registry_service=mismatched_skill_service,
        )

        candidate = _evaluate_readonly(harness, monkeypatch)

        assert candidate.ready is False
        assert candidate.owner_role_code is None
        assert candidate.selected_skill_codes == ()
        assert "readonly_router_session_mismatch" in _reason_codes(candidate)
    finally:
        other_session.close()


def test_route_next_task_keeps_existing_write_capable_initialization_path(
    harness: RouterHarness,
):
    persisted_task = harness.task_repository.add_no_commit(harness.task)
    harness.session.commit()

    decision = harness.router.route_next_task(project_id=harness.project.id)

    assert decision.selected_task is not None
    assert decision.selected_task.id == persisted_task.id
    assert decision.owner_role_code == ProjectRoleCode.ENGINEER
    assert decision.selected_skill_codes
    assert harness.session.scalar(select(func.count()).select_from(ProjectRoleTable)) > 0
    assert harness.session.scalar(select(func.count()).select_from(SkillTable)) > 0
    assert (
        harness.session.scalar(select(func.count()).select_from(ProjectRoleSkillBindingTable))
        > 0
    )


# ══════════════════════════════════════════════════════════════════════
# P24-D2A1-PRE-B-R1: Session boundary acceptance tests
# ══════════════════════════════════════════════════════════════════════


def _make_other_session(engine):
    """Create a second Session bound to the same engine."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()


def _assert_session_mismatch_blocked(candidate):
    """Assert all fields match the session-mismatch blocked candidate contract."""
    assert candidate.ready is False
    assert "readonly_router_session_mismatch" in candidate.route_reason
    assert any(
        r.code == "readonly_router_session_mismatch"
        for r in candidate.strategy_reasons
    )
    assert candidate.budget_action == RunBudgetStrategyAction.BLOCK
    assert candidate.owner_role_code is None
    assert candidate.upstream_role_code is None
    assert candidate.downstream_role_code is None
    assert candidate.selected_skill_codes == ()
    assert candidate.selected_skill_names == ()
    assert candidate.execution_attempts == 0
    assert candidate.recent_failure_count == 0


def _count_sql_statements(engine, session, task, *, kinds=("SELECT", "INSERT", "UPDATE", "DELETE")):
    """Execute evaluate_exact_task_for_dispatch and count SQL by kind."""
    observed = []

    def _catch(conn, cursor, statement, parameters, context, executemany):
        del conn, cursor, parameters, context, executemany
        for kind in kinds:
            if statement.lstrip().upper().startswith(kind):
                observed.append(kind)
                break

    event.listen(engine, "before_cursor_execute", _catch)
    try:
        candidate = session and None  # noqa: just need the engine listener
        from app.services.task_router_service import TaskRouterService
        # We'll call the router externally
    finally:
        event.remove(engine, "before_cursor_execute", _catch)
    return observed


# ── A. Router Session mismatch parameterized tests ───────────────────


@pytest.mark.parametrize(
    "mismatch_scenario",
    [
        pytest.param("run_repository.session", id="1-run-repo-session"),
        pytest.param("readiness.task_repository.session", id="2-readiness-task-repo"),
        pytest.param("readiness.run_repository.session", id="3-readiness-run-repo"),
        pytest.param("router_budget.run_repository.session", id="4-router-budget-run-repo"),
        pytest.param("router_budget._db_session", id="5-router-budget-db-session"),
        pytest.param("strategy.project_repository.session", id="6-strategy-project-repo"),
        pytest.param("strategy_budget.run_repository.session", id="7-strategy-budget-run-repo"),
        pytest.param("strategy_budget._db_session", id="8-strategy-budget-db-session"),
        pytest.param("role.project_repository.session", id="9-role-project-repo"),
        pytest.param("role.project_role_repository.session", id="10-role-role-repo"),
        pytest.param("skill.project_repository.session", id="11-skill-project-repo"),
        pytest.param("skill.skill_repository.session", id="12-skill-skill-repo"),
        pytest.param("skill_role_service_object", id="13-skill-role-service-object"),
        pytest.param("skill_role_repo_session", id="14-skill-role-repo-session"),
    ],
)
def test_session_mismatch_fails_closed(
    harness: RouterHarness,
    monkeypatch: pytest.MonkeyPatch,
    mismatch_scenario: str,
):
    """Each Session mismatch must fail closed before any business query."""
    _initialize_all_authorities(harness)
    other_session = _make_other_session(harness.engine)
    try:
        if mismatch_scenario == "run_repository.session":
            harness.router.run_repository = RunRepository(other_session)
        elif mismatch_scenario == "readiness.task_repository.session":
            harness.router.task_readiness_service.task_repository = TaskRepository(other_session)
        elif mismatch_scenario == "readiness.run_repository.session":
            harness.router.task_readiness_service.run_repository = RunRepository(other_session)
        elif mismatch_scenario == "router_budget.run_repository.session":
            harness.router.budget_guard_service.run_repository = RunRepository(other_session)
        elif mismatch_scenario == "router_budget._db_session":
            harness.router.budget_guard_service._db_session = other_session
        elif mismatch_scenario == "strategy.project_repository.session":
            harness.strategy_engine_service.project_repository = ProjectRepository(other_session)
        elif mismatch_scenario == "strategy_budget.run_repository.session":
            harness.strategy_engine_service.budget_guard_service.run_repository = RunRepository(other_session)
        elif mismatch_scenario == "strategy_budget._db_session":
            harness.strategy_engine_service.budget_guard_service._db_session = other_session
        elif mismatch_scenario == "role.project_repository.session":
            harness.role_catalog_service.project_repository = ProjectRepository(other_session)
        elif mismatch_scenario == "role.project_role_repository.session":
            harness.role_catalog_service.project_role_repository = ProjectRoleRepository(other_session)
        elif mismatch_scenario == "skill.project_repository.session":
            harness.skill_registry_service.project_repository = ProjectRepository(other_session)
        elif mismatch_scenario == "skill.skill_repository.session":
            harness.skill_registry_service.skill_repository = SkillRepository(other_session)
        elif mismatch_scenario == "skill_role_service_object":
            other_role = RoleCatalogService(
                project_repository=harness.project_repository,
                project_role_repository=harness.project_role_repository,
            )
            harness.skill_registry_service.role_catalog_service = other_role
        elif mismatch_scenario == "skill_role_repo_session":
            harness.skill_registry_service.role_catalog_service.project_role_repository = (
                ProjectRoleRepository(other_session)
            )

        candidate = harness.router.evaluate_exact_task_for_dispatch(task=harness.task)
        _assert_session_mismatch_blocked(candidate)
    finally:
        other_session.close()


# ── B. Mismatch produces zero SQL ─────────────────────────────────────


def test_session_mismatch_emits_zero_sql(
    harness: RouterHarness,
    monkeypatch: pytest.MonkeyPatch,
):
    """Session mismatch must not emit any SQL including SELECT."""
    _initialize_all_authorities(harness)
    other_session = _make_other_session(harness.engine)
    try:
        harness.router.run_repository = RunRepository(other_session)

        observed_sql = []

        def _catch(conn, cursor, statement, parameters, context, executemany):
            del conn, cursor, parameters, context, executemany
            observed_sql.append(statement.lstrip().upper()[:20])

        event.listen(harness.engine, "before_cursor_execute", _catch)
        try:
            candidate = harness.router.evaluate_exact_task_for_dispatch(task=harness.task)
        finally:
            event.remove(harness.engine, "before_cursor_execute", _catch)

        _assert_session_mismatch_blocked(candidate)
        assert len(observed_sql) == 0, f"Session mismatch emitted SQL: {observed_sql}"
    finally:
        other_session.close()


def test_session_mismatch_does_not_call_business_services(
    harness: RouterHarness,
    monkeypatch: pytest.MonkeyPatch,
):
    """Session mismatch must not call Budget, Readiness, Strategy, Role, or Skill."""
    _initialize_all_authorities(harness)
    other_session = _make_other_session(harness.engine)
    try:
        harness.router.run_repository = RunRepository(other_session)

        calls = {"budget": 0, "readiness": 0, "strategy": 0, "role": 0, "skill": 0}

        orig_budget = harness.router.budget_guard_service.build_budget_snapshot
        orig_readiness = harness.router.task_readiness_service.evaluate_task
        orig_strategy = harness.strategy_engine_service.resolve_task_strategy_readonly
        orig_role = harness.role_catalog_service.inspect_project_role_catalog_readonly
        orig_skill = harness.skill_registry_service.inspect_project_skill_bindings_readonly

        def wrap(name, fn):
            def inner(*a, **kw):
                calls[name] += 1
                return fn(*a, **kw)
            return inner

        harness.router.budget_guard_service.build_budget_snapshot = wrap("budget", orig_budget)
        harness.router.task_readiness_service.evaluate_task = wrap("readiness", orig_readiness)
        harness.strategy_engine_service.resolve_task_strategy_readonly = wrap("strategy", orig_strategy)
        harness.role_catalog_service.inspect_project_role_catalog_readonly = wrap("role", orig_role)
        harness.skill_registry_service.inspect_project_skill_bindings_readonly = wrap("skill", orig_skill)

        candidate = harness.router.evaluate_exact_task_for_dispatch(task=harness.task)
        _assert_session_mismatch_blocked(candidate)

        assert calls == {"budget": 0, "readiness": 0, "strategy": 0, "role": 0, "skill": 0}, (
            f"Session mismatch called business services: {calls}"
        )
    finally:
        other_session.close()


# ── C. Router no_autoflush proof ──────────────────────────────────────


def test_router_no_autoflush_prevents_pending_object_flush(
    harness: RouterHarness,
    monkeypatch: pytest.MonkeyPatch,
):
    """Router no_autoflush must not flush pending ORM objects."""
    _initialize_all_authorities(harness)
    persisted_task = harness.task_repository.add_no_commit(harness.task)
    harness.session.commit()

    # Add a pending ORM object that should NOT be flushed
    pending_row = ProjectTable(
        id=uuid4(),
        name="Pending autoflush test",
        summary="Should not be flushed",
        status="active",
        stage="intake",
    )
    harness.session.add(pending_row)
    assert pending_row in harness.session.new

    # Guard against INSERT/UPDATE/DELETE
    mutating_sql = []

    def _guard(conn, cursor, statement, parameters, context, executemany):
        del conn, cursor, parameters, context, executemany
        upper = statement.lstrip().upper()
        if upper.startswith(("INSERT", "UPDATE", "DELETE")):
            mutating_sql.append(upper[:60])

    event.listen(harness.engine, "before_cursor_execute", _guard)
    try:
        candidate = harness.router.evaluate_exact_task_for_dispatch(task=harness.task)
    finally:
        event.remove(harness.engine, "before_cursor_execute", _guard)

    assert candidate.ready is True
    assert len(mutating_sql) == 0, f"Router autoflushed: {mutating_sql}"
    assert pending_row in harness.session.new, "Pending object was flushed"

    # Verify the pending row does NOT exist in the database via independent connection
    with harness.engine.connect() as conn:
        count = conn.scalar(
            select(func.count()).select_from(ProjectTable).where(
                ProjectTable.name == "Pending autoflush test"
            )
        )
    assert count == 0, "Pending object was written to database"


# ── D. Strategy readonly seam self-protection ─────────────────────────


def test_strategy_readonly_seam_no_autoflush(
    harness: RouterHarness,
    monkeypatch: pytest.MonkeyPatch,
):
    """Strategy readonly seam must not trigger autoflush."""
    _initialize_all_authorities(harness)
    persisted_task = harness.task_repository.add_no_commit(harness.task)
    harness.session.commit()

    pending_row = ProjectTable(
        id=uuid4(),
        name="Strategy readonly autoflush test",
        summary="Should not be flushed",
        status="active",
        stage="intake",
    )
    harness.session.add(pending_row)
    assert pending_row in harness.session.new

    mutating_sql = []

    def _guard(conn, cursor, statement, parameters, context, executemany):
        del conn, cursor, parameters, context, executemany
        upper = statement.lstrip().upper()
        if upper.startswith(("INSERT", "UPDATE", "DELETE")):
            mutating_sql.append(upper[:60])

    event.listen(harness.engine, "before_cursor_execute", _guard)
    try:
        strategy = harness.strategy_engine_service.resolve_task_strategy_readonly(
            task=harness.task,
            execution_attempts=0,
            recent_failure_count=0,
        )
    finally:
        event.remove(harness.engine, "before_cursor_execute", _guard)

    assert strategy is not None
    assert len(mutating_sql) == 0, f"Strategy readonly seam autoflushed: {mutating_sql}"
    assert pending_row in harness.session.new

    with harness.engine.connect() as conn:
        count = conn.scalar(
            select(func.count()).select_from(ProjectTable).where(
                ProjectTable.name == "Strategy readonly autoflush test"
            )
        )
    assert count == 0, "Strategy readonly seam wrote to database"


# ── E. Strategy Session mismatch ─────────────────────────────────────


def test_strategy_session_mismatch_raises_value_error(
    harness: RouterHarness,
):
    """Strategy readonly seam must raise ValueError on Session mismatch."""
    _initialize_all_authorities(harness)
    other_session = _make_other_session(harness.engine)
    try:
        harness.strategy_engine_service.project_repository = ProjectRepository(other_session)

        with pytest.raises(ValueError, match="readonly_strategy_session_mismatch"):
            harness.strategy_engine_service.resolve_task_strategy_readonly(
                task=harness.task,
                execution_attempts=0,
                recent_failure_count=0,
            )
    finally:
        other_session.close()


def test_strategy_session_mismatch_no_sql(
    harness: RouterHarness,
):
    """Strategy Session mismatch must not emit any SQL."""
    _initialize_all_authorities(harness)
    other_session = _make_other_session(harness.engine)
    try:
        harness.strategy_engine_service.project_repository = ProjectRepository(other_session)

        observed_sql = []

        def _catch(conn, cursor, statement, parameters, context, executemany):
            del conn, cursor, parameters, context, executemany
            observed_sql.append(statement.lstrip().upper()[:20])

        event.listen(harness.engine, "before_cursor_execute", _catch)
        try:
            with pytest.raises(ValueError, match="readonly_strategy_session_mismatch"):
                harness.strategy_engine_service.resolve_task_strategy_readonly(
                    task=harness.task,
                    execution_attempts=0,
                    recent_failure_count=0,
                )
        finally:
            event.remove(harness.engine, "before_cursor_execute", _catch)

        assert len(observed_sql) == 0, f"Strategy mismatch emitted SQL: {observed_sql}"
    finally:
        other_session.close()
