"""Database infrastructure for the local orchestrator runtime."""

from collections.abc import Generator
import sqlite3

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


_TASK_TABLE_COLUMN_UPGRADES = {
    "project_id": "ALTER TABLE tasks ADD COLUMN project_id CHAR(32)",
    "acceptance_criteria": "ALTER TABLE tasks ADD COLUMN acceptance_criteria TEXT NOT NULL DEFAULT '[]'",
    "depends_on_task_ids": "ALTER TABLE tasks ADD COLUMN depends_on_task_ids TEXT NOT NULL DEFAULT '[]'",
    "risk_level": "ALTER TABLE tasks ADD COLUMN risk_level TEXT NOT NULL DEFAULT 'normal'",
    "owner_role_code": "ALTER TABLE tasks ADD COLUMN owner_role_code TEXT",
    "upstream_role_code": "ALTER TABLE tasks ADD COLUMN upstream_role_code TEXT",
    "downstream_role_code": "ALTER TABLE tasks ADD COLUMN downstream_role_code TEXT",
    "human_status": "ALTER TABLE tasks ADD COLUMN human_status TEXT NOT NULL DEFAULT 'none'",
    "paused_reason": "ALTER TABLE tasks ADD COLUMN paused_reason TEXT",
    "source_draft_id": "ALTER TABLE tasks ADD COLUMN source_draft_id VARCHAR(50)",
}

_RUN_TABLE_COLUMN_UPGRADES = {
    "route_reason": "ALTER TABLE runs ADD COLUMN route_reason TEXT",
    "routing_score": "ALTER TABLE runs ADD COLUMN routing_score FLOAT",
    "routing_score_breakdown": "ALTER TABLE runs ADD COLUMN routing_score_breakdown TEXT",
    "strategy_decision_json": "ALTER TABLE runs ADD COLUMN strategy_decision_json TEXT",
    "owner_role_code": "ALTER TABLE runs ADD COLUMN owner_role_code TEXT",
    "upstream_role_code": "ALTER TABLE runs ADD COLUMN upstream_role_code TEXT",
    "downstream_role_code": "ALTER TABLE runs ADD COLUMN downstream_role_code TEXT",
    "handoff_reason": "ALTER TABLE runs ADD COLUMN handoff_reason TEXT",
    "dispatch_status": "ALTER TABLE runs ADD COLUMN dispatch_status VARCHAR(100)",
    "provider_key": "ALTER TABLE runs ADD COLUMN provider_key VARCHAR(50)",
    "prompt_template_key": "ALTER TABLE runs ADD COLUMN prompt_template_key VARCHAR(100)",
    "prompt_template_version": "ALTER TABLE runs ADD COLUMN prompt_template_version VARCHAR(40)",
    "prompt_char_count": "ALTER TABLE runs ADD COLUMN prompt_char_count INTEGER NOT NULL DEFAULT 0",
    "token_accounting_mode": "ALTER TABLE runs ADD COLUMN token_accounting_mode VARCHAR(40)",
    "provider_receipt_id": "ALTER TABLE runs ADD COLUMN provider_receipt_id VARCHAR(100)",
    "total_tokens": "ALTER TABLE runs ADD COLUMN total_tokens INTEGER NOT NULL DEFAULT 0",
    "token_pricing_source": "ALTER TABLE runs ADD COLUMN token_pricing_source VARCHAR(100)",
    "prompt_tokens": "ALTER TABLE runs ADD COLUMN prompt_tokens INTEGER NOT NULL DEFAULT 0",
    "completion_tokens": "ALTER TABLE runs ADD COLUMN completion_tokens INTEGER NOT NULL DEFAULT 0",
    "estimated_cost": "ALTER TABLE runs ADD COLUMN estimated_cost FLOAT NOT NULL DEFAULT 0.0",
    "log_path": "ALTER TABLE runs ADD COLUMN log_path TEXT",
    "verification_mode": "ALTER TABLE runs ADD COLUMN verification_mode TEXT",
    "verification_template": "ALTER TABLE runs ADD COLUMN verification_template TEXT",
    "verification_command": "ALTER TABLE runs ADD COLUMN verification_command TEXT",
    "verification_summary": "ALTER TABLE runs ADD COLUMN verification_summary TEXT",
    "failure_category": "ALTER TABLE runs ADD COLUMN failure_category TEXT",
    "quality_gate_passed": "ALTER TABLE runs ADD COLUMN quality_gate_passed INTEGER",
}

_PROJECT_TABLE_COLUMN_UPGRADES = {
    "sop_template_code": "ALTER TABLE projects ADD COLUMN sop_template_code VARCHAR(100)",
    "stage_history_json": "ALTER TABLE projects ADD COLUMN stage_history_json TEXT NOT NULL DEFAULT '[]'",
    "team_assembly_json": "ALTER TABLE projects ADD COLUMN team_assembly_json TEXT NOT NULL DEFAULT '[]'",
    "team_policy_json": "ALTER TABLE projects ADD COLUMN team_policy_json TEXT NOT NULL DEFAULT '{}'",
    "budget_policy_json": "ALTER TABLE projects ADD COLUMN budget_policy_json TEXT NOT NULL DEFAULT '{}'",
}

_CHANGE_BATCH_TABLE_COLUMN_UPGRADES = {
    "preflight_json": "ALTER TABLE change_batches ADD COLUMN preflight_json TEXT NOT NULL DEFAULT '{}'",
}

_CHANGE_PLAN_VERSION_TABLE_COLUMN_UPGRADES = {
    "verification_templates_json": "ALTER TABLE change_plan_versions ADD COLUMN verification_templates_json TEXT NOT NULL DEFAULT '[]'",
}

_TABLE_COLUMN_UPGRADES = {
    "projects": _PROJECT_TABLE_COLUMN_UPGRADES,
    "tasks": _TASK_TABLE_COLUMN_UPGRADES,
    "runs": _RUN_TABLE_COLUMN_UPGRADES,
    "change_plan_versions": _CHANGE_PLAN_VERSION_TABLE_COLUMN_UPGRADES,
    "change_batches": _CHANGE_BATCH_TABLE_COLUMN_UPGRADES,
}


def ensure_runtime_directories() -> None:
    """Ensure local runtime folders exist before using SQLite or log files."""

    settings.runtime_data_dir.mkdir(parents=True, exist_ok=True)
    settings.sqlite_db_dir.mkdir(parents=True, exist_ok=True)
    (settings.runtime_data_dir / "logs").mkdir(parents=True, exist_ok=True)


engine = create_engine(
    settings.sqlite_db_url,
    echo=settings.debug,
    future=True,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


@event.listens_for(engine, "connect")
def configure_sqlite(connection: sqlite3.Connection, _: object) -> None:
    """Apply a few pragmatic SQLite settings for local development."""

    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.close()


def migrate_database_schema() -> None:
    """Apply lightweight column upgrades for the local SQLite database."""

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    statements: list[str] = []

    for table_name, column_upgrades in _TABLE_COLUMN_UPGRADES.items():
        if table_name not in table_names:
            continue

        existing_columns = {
            column["name"] for column in inspector.get_columns(table_name)
        }
        statements.extend(
            statement
            for column_name, statement in column_upgrades.items()
            if column_name not in existing_columns
        )

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)


def init_database() -> None:
    """Create the core schema and apply local, additive upgrades."""

    ensure_runtime_directories()

    from app.core.db_tables import ORMBase

    ORMBase.metadata.create_all(bind=engine)
    migrate_database_schema()


def get_db_session() -> Generator[Session, None, None]:
    """Yield a database session to API routes and services."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
