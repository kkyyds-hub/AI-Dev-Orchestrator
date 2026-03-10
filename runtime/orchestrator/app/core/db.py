"""Database infrastructure for the local orchestrator runtime."""

from collections.abc import Generator
import sqlite3

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


_RUN_TABLE_COLUMN_UPGRADES = {
    "prompt_tokens": "ALTER TABLE runs ADD COLUMN prompt_tokens INTEGER NOT NULL DEFAULT 0",
    "completion_tokens": "ALTER TABLE runs ADD COLUMN completion_tokens INTEGER NOT NULL DEFAULT 0",
    "estimated_cost": "ALTER TABLE runs ADD COLUMN estimated_cost FLOAT NOT NULL DEFAULT 0.0",
    "log_path": "ALTER TABLE runs ADD COLUMN log_path TEXT",
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
    if "runs" not in table_names:
        return

    existing_columns = {column["name"] for column in inspector.get_columns("runs")}
    statements = [
        statement
        for column_name, statement in _RUN_TABLE_COLUMN_UPGRADES.items()
        if column_name not in existing_columns
    ]
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
