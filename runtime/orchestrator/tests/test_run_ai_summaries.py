from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.router import api_router
from app.core.db import get_db_session
from app.core.db_tables import ORMBase, RunTable
from app.domain._base import utc_now
from app.domain.project import Project
from app.domain.run import RunStatus
from app.domain.run_ai_summary import RunAISummarySource, RunAISummaryStatus
from app.domain.task import Task, TaskPriority, TaskRiskLevel, TaskStatus
from app.repositories.project_repository import ProjectRepository
from app.repositories.run_ai_summary_repository import RunAISummaryRepository
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.run_ai_summary_service import RunAISummaryService

_REQUIRED_MARKDOWN_HEADINGS = [
    "## 运行结论",
    "## 已完成内容",
    "## 风险与注意事项",
    "## 下一步建议",
    "## 技术依据",
]

_FORBIDDEN_MARKDOWN_HEADINGS = [
    "## 一句话结论",
    "## 本次完成内容",
    "## 关键结果",
]


@pytest.fixture()
def sqlite_session_factory(tmp_path):
    db_path = tmp_path / "orchestrator-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@pytest.fixture()
def db_session(sqlite_session_factory):
    session = sqlite_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def seeded_run(db_session):
    project = Project(
        name="AI 摘要测试项目",
        summary="用于验证运行摘要后端契约。",
    )
    project = ProjectRepository(db_session).create(project)

    task = Task(
        project_id=project.id,
        title="整理运行摘要",
        input_summary="为当前运行生成一段中文摘要。",
        status=TaskStatus.COMPLETED,
        priority=TaskPriority.NORMAL,
        risk_level=TaskRiskLevel.NORMAL,
    )
    task = TaskRepository(db_session).create(task)

    run_id = uuid4()
    db_session.add(
        RunTable(
            id=run_id,
            task_id=task.id,
            status=RunStatus.SUCCEEDED,
            result_summary="执行完成，交付结果已记录。",
            verification_summary="验证通过。",
            quality_gate_passed=True,
            provider_key="deepseek",
            model_name="deepseek-v4-pro",
            provider_receipt_id="receipt-test-001",
            created_at=utc_now(),
            started_at=utc_now() - timedelta(minutes=5),
            finished_at=utc_now(),
        )
    )
    db_session.commit()

    return project, task, run_id


@pytest.fixture()
def run_ai_summary_service(db_session):
    return RunAISummaryService(
        run_repository=RunRepository(db_session),
        task_repository=TaskRepository(db_session),
        run_ai_summary_repository=RunAISummaryRepository(db_session),
    )


@pytest.fixture()
def client(sqlite_session_factory):
    app = FastAPI()
    app.include_router(api_router)

    def override_get_db_session():
        session = sqlite_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session
    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ── Plural endpoint tests (existing, kept intact) ──────────────────

def test_generate_and_regenerate_run_ai_summary(run_ai_summary_service, db_session, seeded_run):
    project, task, run_id = seeded_run

    first = run_ai_summary_service.generate_run_summary(run_id=run_id)
    second = run_ai_summary_service.generate_run_summary(run_id=run_id)
    regenerated = run_ai_summary_service.generate_run_summary(run_id=run_id, regenerate=True)

    assert first.id == second.id
    assert first.status == RunAISummaryStatus.SUCCEEDED
    assert first.source == RunAISummarySource.RULE_FALLBACK
    assert first.source_fingerprint == first.source_hash
    assert first.model_provider == "local_rule_engine"
    assert first.model_name == "run_summary.rule_fallback.v2"
    assert first.prompt_hash
    assert first.summary_markdown.count("## ") == 5

    # DTO fields
    assert first.created_at is not None
    assert first.updated_at is not None
    assert first.error_summary is None

    # Markdown headings
    for heading in _REQUIRED_MARKDOWN_HEADINGS:
        assert heading in first.summary_markdown, f"Missing heading: {heading}"
    for forbidden in _FORBIDDEN_MARKDOWN_HEADINGS:
        assert forbidden not in first.summary_markdown, f"Forbidden heading present: {forbidden}"

    assert regenerated.id != first.id
    assert regenerated.stale is False

    history = RunAISummaryRepository(db_session).list_by_run_id(run_id)
    assert len(history) == 2
    assert history[0].id == regenerated.id
    assert history[1].id == first.id
    assert history[1].stale is True
    assert history[0].project_id == project.id
    assert history[0].task_id == task.id


def test_run_ai_summary_endpoints(client, seeded_run):
    _, _, run_id = seeded_run

    created = client.post(f"/runs/{run_id}/ai-summaries")
    assert created.status_code == 200
    created_payload = created.json()
    assert created_payload["run_id"] == str(run_id)
    assert created_payload["status"] == RunAISummaryStatus.SUCCEEDED.value
    assert created_payload["source"] == RunAISummarySource.RULE_FALLBACK.value
    assert created_payload["source_fingerprint"] == created_payload["source_hash"]
    assert created_payload["prompt_hash"]
    assert created_payload["summary_markdown"].count("## ") == 5
    assert created_payload["created_at"] is not None
    assert created_payload["updated_at"] is not None
    assert created_payload["error_summary"] is None

    history = client.get(f"/runs/{run_id}/ai-summaries")
    assert history.status_code == 200
    history_payload = history.json()
    assert history_payload["run_id"] == str(run_id)
    assert history_payload["active_summary"]["id"] == created_payload["id"]
    assert len(history_payload["summaries"]) == 1

    regenerated = client.post(f"/runs/{run_id}/ai-summaries/regenerate")
    assert regenerated.status_code == 201
    regenerated_payload = regenerated.json()
    assert regenerated_payload["id"] != created_payload["id"]
    assert regenerated_payload["status"] == RunAISummaryStatus.SUCCEEDED.value
    assert regenerated_payload["source"] == RunAISummarySource.RULE_FALLBACK.value

    history_after = client.get(f"/runs/{run_id}/ai-summaries")
    assert history_after.status_code == 200
    history_after_payload = history_after.json()
    assert len(history_after_payload["summaries"]) == 2
    assert history_after_payload["active_summary"]["id"] == regenerated_payload["id"]
    assert history_after_payload["summaries"][1]["stale"] is True


def test_run_ai_summary_endpoint_returns_404_for_missing_run(client):
    missing_run_id = uuid4()
    response = client.post(f"/runs/{missing_run_id}/ai-summaries")
    assert response.status_code == 404


# ── Singular endpoint tests ────────────────────────────────────────


def test_get_ai_summary_returns_null_when_no_summary(client, seeded_run):
    """GET /{run_id}/ai-summary without prior generation returns active_summary=null."""
    _, _, run_id = seeded_run

    response = client.get(f"/runs/{run_id}/ai-summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == str(run_id)
    assert payload["active_summary"] is None


def test_get_ai_summary_returns_active_after_generation(client, seeded_run):
    """GET /{run_id}/ai-summary returns the active summary after generate."""
    _, _, run_id = seeded_run

    # Generate via singular endpoint
    gen = client.post(f"/runs/{run_id}/ai-summary/generate")
    assert gen.status_code == 200
    gen_payload = gen.json()

    # Fetch current
    response = client.get(f"/runs/{run_id}/ai-summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["active_summary"] is not None
    assert payload["active_summary"]["id"] == gen_payload["id"]


def test_singular_generate_creates_rule_fallback_summary(client, seeded_run):
    """POST /{run_id}/ai-summary/generate creates a rule_fallback summary."""
    _, _, run_id = seeded_run

    response = client.post(f"/runs/{run_id}/ai-summary/generate")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == RunAISummaryStatus.SUCCEEDED.value
    assert payload["source"] == RunAISummarySource.RULE_FALLBACK.value
    assert payload["summary_markdown"].count("## ") == 5

    # DTO must contain created_at / updated_at / error_summary
    assert payload["created_at"] is not None
    assert payload["updated_at"] is not None
    assert payload["error_summary"] is None

    # Markdown headings exactly the 5 required
    for heading in _REQUIRED_MARKDOWN_HEADINGS:
        assert heading in payload["summary_markdown"], f"Missing: {heading}"
    for forbidden in _FORBIDDEN_MARKDOWN_HEADINGS:
        assert forbidden not in payload["summary_markdown"], f"Forbidden: {forbidden}"


def test_singular_generate_reuses_active_on_duplicate_call(client, seeded_run):
    """Repeat POST /{run_id}/ai-summary/generate reuses the same active summary."""
    _, _, run_id = seeded_run

    first = client.post(f"/runs/{run_id}/ai-summary/generate")
    second = client.post(f"/runs/{run_id}/ai-summary/generate")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_singular_regenerate_creates_new_and_marks_old_stale(client, seeded_run):
    """POST /{run_id}/ai-summary/regenerate creates new, marks old stale."""
    _, _, run_id = seeded_run

    first = client.post(f"/runs/{run_id}/ai-summary/generate")
    first_id = first.json()["id"]

    regen = client.post(f"/runs/{run_id}/ai-summary/regenerate")
    assert regen.status_code == 201
    regen_payload = regen.json()
    assert regen_payload["id"] != first_id
    assert regen_payload["stale"] is False

    # Current should be the regenerated one
    current = client.get(f"/runs/{run_id}/ai-summary")
    assert current.json()["active_summary"]["id"] == regen_payload["id"]


def test_singular_endpoints_return_404_for_missing_run(client):
    """All singular endpoints return 404 for non-existent run."""
    missing = uuid4()

    assert client.get(f"/runs/{missing}/ai-summary").status_code == 404
    assert client.post(f"/runs/{missing}/ai-summary/generate").status_code == 404
    assert client.post(f"/runs/{missing}/ai-summary/regenerate").status_code == 404


def test_mark_failed_writes_error_summary(db_session, seeded_run):
    """Repository mark_failed writes error_summary correctly."""
    _, _, run_id = seeded_run

    repo = RunAISummaryRepository(db_session)

    # Create a pending summary first
    from app.domain.run_ai_summary import RunAISummary, RunAISummaryType
    from uuid import uuid4 as _uuid4
    from app.domain._base import utc_now as _utc_now
    from hashlib import sha256

    now = _utc_now()
    fp = sha256(b"test-fingerprint").hexdigest()

    summary = RunAISummary(
        id=_uuid4(),
        run_id=run_id,
        summary_type=RunAISummaryType.RUN,
        status=RunAISummaryStatus.PENDING,
        source=RunAISummarySource.RULE_FALLBACK,
        summary_markdown="# pending",
        source_version="test.v1",
        source_fingerprint=fp,
        source_hash=fp,
        prompt_hash=sha256(b"test-prompt").hexdigest(),
        generated_at=now,
        created_at=now,
        updated_at=now,
    )
    created = repo.create(summary)

    # Mark as failed
    failed = repo.mark_failed(
        summary_id=created.id,
        error_summary="AI provider timed out after 120s",
    )
    assert failed is not None
    assert failed.status == RunAISummaryStatus.FAILED
    assert failed.error_summary == "AI provider timed out after 120s"

    # Re-read to confirm persistence
    reloaded = repo.get_by_id(created.id)
    assert reloaded is not None
    assert reloaded.status == RunAISummaryStatus.FAILED
    assert reloaded.error_summary == "AI provider timed out after 120s"


def test_markdown_contains_tech_basis_section(client, seeded_run):
    """技术依据 section contains run metadata with field-fallback language."""
    _, _, run_id = seeded_run

    gen = client.post(f"/runs/{run_id}/ai-summary/generate")
    md = gen.json()["summary_markdown"]

    assert "## 技术依据" in md
    assert "运行状态" in md
    assert "结果摘要" in md
    assert "验证摘要" in md
    assert "质量检查" in md
    assert "模型服务 Key" in md
    assert "模型名称" in md
    assert "模型回执 ID" in md


# ── 2A-R3: historical data tolerance tests ──────────────────────────


def test_old_row_with_empty_fields_does_not_500(db_session, seeded_run, client):
    """Legacy row with empty fingerprints/hashes is readable via repository + API."""
    _, _, run_id = seeded_run

    from app.domain.run_ai_summary import RunAISummary, RunAISummaryType, RunAISummarySource
    from uuid import uuid4 as _uuid4
    from app.domain._base import utc_now as _utc_now

    now = _utc_now()
    repo = RunAISummaryRepository(db_session)

    # Create a summary via repository (valid fields)
    legacy = repo.create(RunAISummary(
        id=_uuid4(),
        run_id=run_id,
        summary_type=RunAISummaryType.RUN,
        status=RunAISummaryStatus.SUCCEEDED,
        source=RunAISummarySource.RULE_FALLBACK,
        summary_markdown="# legacy",
        source_version="legacy.v1",
        source_fingerprint="placeholder",
        source_hash="placeholder",
        prompt_hash="placeholder",
        generated_at=now,
        created_at=now,
        updated_at=now,
    ))

    # Corrupt the row to simulate a pre-migration legacy state
    from sqlalchemy import text
    db_session.execute(
        text(
            "UPDATE run_ai_summaries "
            "SET source_fingerprint = '', source_hash = '', prompt_hash = '' "
            "WHERE id = :id"
        ),
        {"id": str(legacy.id)},
    )
    db_session.commit()
    db_session.expire_all()

    # Repository list should tolerate the corrupted row without exception
    summaries = repo.list_by_run_id(run_id)
    match = next((s for s in summaries if s.id == legacy.id), None)
    assert match is not None, "legacy row not returned by list_by_run_id"
    assert match.source_fingerprint, "fingerprint should be backfilled"
    assert match.source_hash, "source_hash should be backfilled"
    assert match.prompt_hash, "prompt_hash should be backfilled"

    # GET /ai-summary should not 500 when legacy row exists (stale=0)
    response = client.get(f"/runs/{run_id}/ai-summary")
    assert response.status_code == 200
    payload = response.json()
    if payload["active_summary"] is not None:
        assert payload["active_summary"]["status"] == "succeeded"
        assert payload["active_summary"]["created_at"] is not None
        assert payload["active_summary"]["updated_at"] is not None


def test_generate_works_with_old_rows_present(db_session, seeded_run, client):
    """generate/regenerate still work when legacy rows (empty fingerprints) exist."""
    _, _, run_id = seeded_run

    from app.domain.run_ai_summary import RunAISummary, RunAISummaryType, RunAISummarySource
    from uuid import uuid4 as _uuid4
    from app.domain._base import utc_now as _utc_now

    now = _utc_now()
    repo = RunAISummaryRepository(db_session)

    legacy = repo.create(RunAISummary(
        id=_uuid4(),
        run_id=run_id,
        summary_type=RunAISummaryType.RUN,
        status=RunAISummaryStatus.SUCCEEDED,
        source=RunAISummarySource.RULE_FALLBACK,
        summary_markdown="# legacy2",
        source_version="legacy.v2",
        source_fingerprint="p",
        source_hash="p",
        prompt_hash="p",
        generated_at=now,
        created_at=now,
        updated_at=now,
    ))

    # Corrupt to simulate legacy state with empty fingerprints
    from sqlalchemy import text
    db_session.execute(
        text("UPDATE run_ai_summaries SET source_fingerprint='', source_hash='', prompt_hash='' WHERE id=:id"),
        {"id": str(legacy.id)},
    )
    db_session.commit()
    db_session.expire_all()

    # generate should succeed — old row gets marked stale, new one created
    gen = client.post(f"/runs/{run_id}/ai-summary/generate")
    assert gen.status_code == 200
    gen_payload = gen.json()
    assert gen_payload["id"] != str(legacy.id)
    assert gen_payload["created_at"] is not None
    assert gen_payload["updated_at"] is not None
    assert gen_payload["source_fingerprint"]

    # regenerate should also work
    regen = client.post(f"/runs/{run_id}/ai-summary/regenerate")
    assert regen.status_code == 201


def test_mark_succeeded_syncs_source_hash(db_session, seeded_run):
    """When source_fingerprint is updated, source_hash must be synced."""
    _, _, run_id = seeded_run

    from app.domain.run_ai_summary import RunAISummary, RunAISummaryType
    from uuid import uuid4 as _uuid4
    from app.domain._base import utc_now as _utc_now
    from hashlib import sha256

    now = _utc_now()
    fp_old = sha256(b"old-fingerprint").hexdigest()

    repo = RunAISummaryRepository(db_session)
    summary = RunAISummary(
        id=_uuid4(),
        run_id=run_id,
        summary_type=RunAISummaryType.RUN,
        status=RunAISummaryStatus.PENDING,
        source=RunAISummarySource.RULE_FALLBACK,
        summary_markdown="# pending",
        source_version="test.v1",
        source_fingerprint=fp_old,
        source_hash="OLD_HASH_NOT_EQUAL",
        prompt_hash=sha256(b"test-prompt").hexdigest(),
        generated_at=now,
        created_at=now,
        updated_at=now,
    )
    created = repo.create(summary)
    assert created.source_fingerprint == fp_old
    assert created.source_hash == "OLD_HASH_NOT_EQUAL"  # pre-condition

    fp_new = sha256(b"new-fingerprint").hexdigest()
    updated = repo.mark_succeeded(
        summary_id=created.id,
        summary_markdown="# succeeded",
        source_fingerprint=fp_new,
    )
    assert updated is not None
    assert updated.source_fingerprint == fp_new
    assert updated.source_hash == fp_new  # must be synced


def test_upsert_pending_forces_status_pending(db_session, seeded_run):
    """upsert_pending must store status=pending even when passed succeeded."""
    _, _, run_id = seeded_run

    from app.domain.run_ai_summary import RunAISummary, RunAISummaryType
    from uuid import uuid4 as _uuid4
    from app.domain._base import utc_now as _utc_now
    from hashlib import sha256

    now = _utc_now()
    fp = sha256(b"upsert-test-fp").hexdigest()

    repo = RunAISummaryRepository(db_session)

    # Create summary with status=SUCCEEDED
    summary = RunAISummary(
        id=_uuid4(),
        run_id=run_id,
        summary_type=RunAISummaryType.RUN,
        status=RunAISummaryStatus.SUCCEEDED,  # <-- NOT pending
        source=RunAISummarySource.RULE_FALLBACK,
        summary_markdown="# should be forced to pending",
        source_version="test.upsert",
        source_fingerprint=fp,
        source_hash=fp,
        prompt_hash=sha256(b"test-upsert-prompt").hexdigest(),
        generated_at=now,
        created_at=now,
        updated_at=now,
    )

    result = repo.upsert_pending(summary)
    assert result.status == RunAISummaryStatus.PENDING

    # Re-read to confirm persistence
    reloaded = repo.get_by_id(result.id)
    assert reloaded is not None
    assert reloaded.status == RunAISummaryStatus.PENDING


def test_singular_404_for_missing_run_all_paths(client):
    """All singular paths return 404 for non-existent run_id."""
    missing = uuid4()
    assert client.get(f"/runs/{missing}/ai-summary").status_code == 404
    assert client.post(f"/runs/{missing}/ai-summary/generate").status_code == 404
    assert client.post(f"/runs/{missing}/ai-summary/regenerate").status_code == 404
