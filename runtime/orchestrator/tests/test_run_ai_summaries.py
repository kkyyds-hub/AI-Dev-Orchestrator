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
from app.api.routes.runs import get_run_ai_summary_service as _original_get_run_ai_summary_service
from fastapi import Depends as _FastAPIDepends

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

    # Override to NOT inject ProviderConfigService so legacy tests stay
    # rule_fallback-only.  2C-A tests can create their own client with AI enabled.
    from sqlalchemy.orm import Session as _Session

    def _no_provider_summary_service(
        session: _Session = _FastAPIDepends(get_db_session),
    ):
        return RunAISummaryService(
            run_repository=RunRepository(session),
            task_repository=TaskRepository(session),
            run_ai_summary_repository=RunAISummaryRepository(session),
        )

    app.dependency_overrides[_original_get_run_ai_summary_service] = (
        _no_provider_summary_service
    )

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


# ═══════════════════════════════════════════════════════════════════
# 2C-A  tests — real AI summary generation with fake provider client
# ═══════════════════════════════════════════════════════════════════

_VALID_AI_MARKDOWN = """## 运行结论
本次运行已成功完成，由 AI 生成摘要。

## 已完成内容
- 任务：测试任务
- 运行状态：succeeded

## 风险与注意事项
- 当前没有额外风险信号。

## 下一步建议
- 可继续查看交付件或审批。

## 技术依据
- 运行状态：succeeded
- 结果摘要：执行完成
- 验证摘要：验证通过
- 质量检查：通过
- 模型服务 Key：deepseek
- 模型名称：deepseek-v4-pro
- 模型回执 ID：receipt-ai-001"""


def _fake_ai_success(model_name: str, prompt_text: str, request_id: str) -> tuple[str, str | None]:
    return _VALID_AI_MARKDOWN, "receipt-ai-001"


def _fake_ai_timeout(model_name: str, prompt_text: str, request_id: str) -> tuple[str, str | None]:
    from app.services.openai_provider_executor_service import OpenAIProviderExecutionError
    raise OpenAIProviderExecutionError(
        category="timeout",
        message="OpenAI request timed out after 120 seconds",
    )


def _fake_ai_empty(model_name: str, prompt_text: str, request_id: str) -> tuple[str, str | None]:
    return "   ", None


def _fake_ai_json(model_name: str, prompt_text: str, request_id: str) -> tuple[str, str | None]:
    return '{"summary": "not markdown"}', None


def _fake_ai_missing_heading(model_name: str, prompt_text: str, request_id: str) -> tuple[str, str | None]:
    return """## 运行结论
Done.

## 已完成内容
- OK

## 风险与注意事项
- None

## 下一步建议
- Go ahead
""", None  # missing 技术依据


# ── provider unconfigured ──────────────────────────────────────────

def test_ai_summary_no_provider_returns_rule_fallback(run_ai_summary_service, db_session, seeded_run):
    """Without provider config, generate returns source=rule_fallback."""
    _, _, run_id = seeded_run

    summary = run_ai_summary_service.generate_run_summary(run_id=run_id)
    assert summary.source == RunAISummarySource.RULE_FALLBACK
    assert summary.model_provider == "local_rule_engine"
    assert summary.model_name == "run_summary.rule_fallback.v2"
    assert summary.provider_receipt_id is None
    assert summary.status == RunAISummaryStatus.SUCCEEDED


# ── AI success ─────────────────────────────────────────────────────

def test_ai_summary_provider_success_returns_source_ai(db_session, seeded_run):
    """With a fake AI generator that returns valid markdown, source=ai."""
    _, _, run_id = seeded_run

    service = RunAISummaryService(
        run_repository=RunRepository(db_session),
        task_repository=TaskRepository(db_session),
        run_ai_summary_repository=RunAISummaryRepository(db_session),
        ai_text_generator=_fake_ai_success,
    )
    summary = service.generate_run_summary(run_id=run_id)
    assert summary.source == RunAISummarySource.AI
    assert summary.status == RunAISummaryStatus.SUCCEEDED
    assert summary.model_provider is not None
    assert summary.model_name is not None
    assert summary.provider_receipt_id == "receipt-ai-001"
    assert "## 运行结论" in summary.summary_markdown
    assert summary.summary_markdown == _VALID_AI_MARKDOWN
    assert summary.error_summary is None


# ── AI timeout fallback ────────────────────────────────────────────

def test_ai_summary_timeout_falls_back_to_rule(db_session, seeded_run):
    """AI timeout does not 500; falls back to rule_fallback with error_summary."""
    _, _, run_id = seeded_run

    service = RunAISummaryService(
        run_repository=RunRepository(db_session),
        task_repository=TaskRepository(db_session),
        run_ai_summary_repository=RunAISummaryRepository(db_session),
        ai_text_generator=_fake_ai_timeout,
    )
    summary = service.generate_run_summary(run_id=run_id)
    assert summary.source == RunAISummarySource.RULE_FALLBACK
    assert summary.status == RunAISummaryStatus.SUCCEEDED
    assert summary.error_summary is not None
    assert "timeout" in summary.error_summary
    # error_summary must NOT contain a traceback or API key
    assert "Traceback" not in (summary.error_summary or "")


# ── AI bad markdown fallbacks ──────────────────────────────────────

def test_ai_summary_empty_text_falls_back_to_rule(db_session, seeded_run):
    """Empty AI output → rule_fallback."""
    _, _, run_id = seeded_run

    service = RunAISummaryService(
        run_repository=RunRepository(db_session),
        task_repository=TaskRepository(db_session),
        run_ai_summary_repository=RunAISummaryRepository(db_session),
        ai_text_generator=_fake_ai_empty,
    )
    summary = service.generate_run_summary(run_id=run_id)
    assert summary.source == RunAISummarySource.RULE_FALLBACK
    assert summary.error_summary is not None
    assert "空文本" in (summary.error_summary or "")


def test_ai_summary_json_output_falls_back_to_rule(db_session, seeded_run):
    """JSON output from AI → rule_fallback."""
    _, _, run_id = seeded_run

    service = RunAISummaryService(
        run_repository=RunRepository(db_session),
        task_repository=TaskRepository(db_session),
        run_ai_summary_repository=RunAISummaryRepository(db_session),
        ai_text_generator=_fake_ai_json,
    )
    summary = service.generate_run_summary(run_id=run_id)
    assert summary.source == RunAISummarySource.RULE_FALLBACK
    assert "JSON" in (summary.error_summary or "")


def test_ai_summary_missing_heading_falls_back_to_rule(db_session, seeded_run):
    """AI output missing 技术依据 → rule_fallback."""
    _, _, run_id = seeded_run

    service = RunAISummaryService(
        run_repository=RunRepository(db_session),
        task_repository=TaskRepository(db_session),
        run_ai_summary_repository=RunAISummaryRepository(db_session),
        ai_text_generator=_fake_ai_missing_heading,
    )
    summary = service.generate_run_summary(run_id=run_id)
    assert summary.source == RunAISummarySource.RULE_FALLBACK
    assert "缺少必要标题" in (summary.error_summary or "")


# ── GET does not trigger AI ───────────────────────────────────────

def test_get_ai_summary_does_not_trigger_ai(db_session, seeded_run):
    """GET only reads existing active_summary; it never generates."""
    _, _, run_id = seeded_run

    # Service with a fake generator that would succeed — but GET should
    # never call it because get_active_summary is read-only.
    call_count = [0]

    def counting_generator(model_name: str, prompt_text: str, request_id: str) -> tuple[str, str | None]:
        call_count[0] += 1
        return _VALID_AI_MARKDOWN, "receipt-count"

    service = RunAISummaryService(
        run_repository=RunRepository(db_session),
        task_repository=TaskRepository(db_session),
        run_ai_summary_repository=RunAISummaryRepository(db_session),
        ai_text_generator=counting_generator,
    )
    # GET should return None (no active summary) without calling AI
    active = service.get_active_summary(run_id=run_id)
    assert active is None
    assert call_count[0] == 0

    # Even after generating, GET just reads
    summary = service.generate_run_summary(run_id=run_id)
    assert call_count[0] == 1
    active = service.get_active_summary(run_id=run_id)
    assert active is not None
    assert active.id == summary.id
    assert call_count[0] == 1  # still 1 — GET did not call AI


# ── regenerate with AI ────────────────────────────────────────────

def test_ai_summary_regenerate_retries_ai(db_session, seeded_run):
    """Regenerate with AI available should produce a new source=ai summary."""
    _, _, run_id = seeded_run

    service = RunAISummaryService(
        run_repository=RunRepository(db_session),
        task_repository=TaskRepository(db_session),
        run_ai_summary_repository=RunAISummaryRepository(db_session),
        ai_text_generator=_fake_ai_success,
    )
    first = service.generate_run_summary(run_id=run_id)
    assert first.source == RunAISummarySource.AI

    second = service.generate_run_summary(run_id=run_id, regenerate=True)
    assert second.source == RunAISummarySource.AI
    assert second.id != first.id

    history = RunAISummaryRepository(db_session).list_by_run_id(run_id)
    assert len(history) == 2
    assert history[1].stale is True


# ── existing rule_fallback + provider now available → AI retry ─────

def test_ai_summary_rule_fallback_active_with_provider_retries_ai(db_session, seeded_run):
    """When active summary is rule_fallback but provider is now configured,
    POST /generate should attempt AI generation."""
    _, _, run_id = seeded_run

    # First create a rule_fallback summary (no AI generator)
    no_ai_service = RunAISummaryService(
        run_repository=RunRepository(db_session),
        task_repository=TaskRepository(db_session),
        run_ai_summary_repository=RunAISummaryRepository(db_session),
    )
    first = no_ai_service.generate_run_summary(run_id=run_id)
    assert first.source == RunAISummarySource.RULE_FALLBACK

    # Now with AI generator available, generate should try AI
    ai_service = RunAISummaryService(
        run_repository=RunRepository(db_session),
        task_repository=TaskRepository(db_session),
        run_ai_summary_repository=RunAISummaryRepository(db_session),
        ai_text_generator=_fake_ai_success,
    )
    second = ai_service.generate_run_summary(run_id=run_id)
    assert second.source == RunAISummarySource.AI
    assert second.id != first.id


# ── markdown heading validation ────────────────────────────────────

def test_validate_ai_summary_markdown_accepts_valid():
    """Five headings + content passes validation."""
    from app.services.run_ai_summary_service import RunAISummaryService
    assert RunAISummaryService._validate_ai_summary_markdown(_VALID_AI_MARKDOWN) is None


def test_validate_ai_summary_markdown_rejects_empty():
    """Empty text fails validation."""
    from app.services.run_ai_summary_service import RunAISummaryService
    assert RunAISummaryService._validate_ai_summary_markdown("   ") is not None


def test_validate_ai_summary_markdown_rejects_code_wrapped():
    """Code-block-wrapped text fails validation."""
    from app.services.run_ai_summary_service import RunAISummaryService
    wrapped = "```\n" + _VALID_AI_MARKDOWN + "\n```"
    assert RunAISummaryService._validate_ai_summary_markdown(wrapped) is not None


# ═══════════════════════════════════════════════════════════════════
# 2C-A-R1  tests — prompt_hash, env-only provider, provider_key
# ═══════════════════════════════════════════════════════════════════

def test_ai_summary_uses_ai_prompt_hash(db_session, seeded_run):
    """source=ai must use AI prompt hash, not rule-fallback prompt hash."""
    _, _, run_id = seeded_run

    service = RunAISummaryService(
        run_repository=RunRepository(db_session),
        task_repository=TaskRepository(db_session),
        run_ai_summary_repository=RunAISummaryRepository(db_session),
        ai_text_generator=_fake_ai_success,
    )
    summary = service.generate_run_summary(run_id=run_id)
    assert summary.source == RunAISummarySource.AI

    # The AI prompt_hash must differ from the rule-fallback prompt_hash.
    # Build both hashes manually to compare.
    from hashlib import sha256

    # Rule-fallback prompt hash: _build_prompt_text
    # We don't have direct access, so compute a fallback summary instead.
    no_ai_service = RunAISummaryService(
        run_repository=RunRepository(db_session),
        task_repository=TaskRepository(db_session),
        run_ai_summary_repository=RunAISummaryRepository(db_session),
    )
    fallback = no_ai_service.generate_run_summary(run_id=run_id)
    assert fallback.source == RunAISummarySource.RULE_FALLBACK
    assert summary.prompt_hash != fallback.prompt_hash, (
        "AI summary prompt_hash must differ from rule-fallback prompt_hash"
    )
    # The AI prompt_hash should be deterministic: regenerate same data → same hash
    summary2 = service.generate_run_summary(run_id=run_id, regenerate=True)
    assert summary2.prompt_hash == summary.prompt_hash


def test_rule_fallback_still_uses_fallback_prompt_hash(db_session, seeded_run):
    """source=rule_fallback must still use the rule prompt hash (stable)."""
    _, _, run_id = seeded_run

    service = RunAISummaryService(
        run_repository=RunRepository(db_session),
        task_repository=TaskRepository(db_session),
        run_ai_summary_repository=RunAISummaryRepository(db_session),
    )
    first = service.generate_run_summary(run_id=run_id)
    assert first.source == RunAISummarySource.RULE_FALLBACK
    assert first.prompt_hash

    # Same data → same rule_fallback prompt_hash
    second = service.generate_run_summary(run_id=run_id, regenerate=True)
    assert second.prompt_hash == first.prompt_hash


def test_ai_summary_can_try_ai_respects_fake_generator(db_session):
    """_can_try_ai returns True when ai_text_generator is injected."""
    service = RunAISummaryService(
        run_repository=RunRepository(db_session),
        task_repository=TaskRepository(db_session),
        run_ai_summary_repository=RunAISummaryRepository(db_session),
        ai_text_generator=_fake_ai_success,
    )
    assert service._can_try_ai() is True


def test_ai_summary_can_try_ai_no_generator_no_provider(db_session):
    """_can_try_ai returns False without generator or provider_config_service."""
    service = RunAISummaryService(
        run_repository=RunRepository(db_session),
        task_repository=TaskRepository(db_session),
        run_ai_summary_repository=RunAISummaryRepository(db_session),
    )
    assert service._can_try_ai() is False


def test_generate_text_passes_provider_key(db_session, seeded_run):
    """generate_text receives correct provider_key from _call_provider_text path.

    Uses monkeypatch on OpenAIProviderExecutorService.generate_text so we
    exercise the real _call_provider_text → generate_text call stack.
    """
    from unittest.mock import MagicMock, patch
    from app.services.openai_provider_executor_service import (
        OpenAIProviderExecutionResponse,
        OpenAIProviderExecutorService,
        ProviderUsageReceipt,
    )
    from app.domain.prompt_contract import ProviderReceiptSource

    _, _, run_id = seeded_run

    captured: dict[str, str] = {}

    def fake_generate_text(
        self,
        *,
        model_name: str = "",
        prompt_text: str = "",
        request_id: str = "",
        prompt_key: str = "run_ai_summary",
        provider_key: str = "openai",
    ) -> OpenAIProviderExecutionResponse:
        captured["model_name"] = model_name
        captured["provider_key"] = provider_key
        captured["prompt_key"] = prompt_key
        captured["request_id"] = request_id
        receipt = ProviderUsageReceipt(
            provider_key=provider_key,
            model_name=model_name,
            receipt_id="receipt-cap-001",
            receipt_source=ProviderReceiptSource.REAL_PROVIDER,
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            estimated_cost_usd=0.0,
            pricing_source="openai.chat_completions.usage",
        )
        return OpenAIProviderExecutionResponse(
            success=True,
            mode="provider_openai",
            summary="ok",
            output_text=_VALID_AI_MARKDOWN,
            prompt_key=prompt_key,
            prompt_char_count=len(prompt_text.encode("utf-8")),
            provider_usage_receipt=receipt,
        )

    mock_config = MagicMock()
    mock_runtime_config = MagicMock()
    mock_runtime_config.api_key = "sk-test-deepseek"
    mock_runtime_config.base_url = "https://api.deepseek.com/v1"
    mock_runtime_config.timeout_seconds = 120
    mock_runtime_config.detected_provider_type = "deepseek"
    mock_runtime_config.model_names = {"balanced": "deepseek-v4-pro"}
    mock_config.resolve_openai_runtime_config.return_value = mock_runtime_config

    service = RunAISummaryService(
        run_repository=RunRepository(db_session),
        task_repository=TaskRepository(db_session),
        run_ai_summary_repository=RunAISummaryRepository(db_session),
        provider_config_service=mock_config,
        # No ai_text_generator — forces _call_provider_text → generate_text
    )

    with patch.object(
        OpenAIProviderExecutorService, "generate_text", fake_generate_text
    ):
        summary = service.generate_run_summary(run_id=run_id)

    assert captured["provider_key"] == "deepseek", (
        f"generate_text should receive provider_key='deepseek', got {captured.get('provider_key')}"
    )
    assert captured["model_name"] == "deepseek-v4-pro"
    assert captured["prompt_key"] == "run_ai_summary"
    assert captured["request_id"] == str(run_id)

    assert summary.source == RunAISummarySource.AI
    assert summary.model_provider == "deepseek"
    assert summary.model_name == "deepseek-v4-pro"
    assert summary.provider_receipt_id == "receipt-cap-001"


def test_env_only_provider_respected(db_session, seeded_run):
    """env-only api_key triggers AI via provider_config_service + generate_text path.

    No ai_text_generator — exercises the real _can_try_ai → _try_ai_summary
    → _call_provider_text → generate_text call stack.
    """
    from unittest.mock import MagicMock, patch
    from app.services.openai_provider_executor_service import (
        OpenAIProviderExecutionResponse,
        OpenAIProviderExecutorService,
        ProviderUsageReceipt,
    )
    from app.domain.prompt_contract import ProviderReceiptSource

    _, _, run_id = seeded_run

    call_count = [0]

    def fake_generate_text(
        self,
        *,
        model_name: str = "",
        prompt_text: str = "",
        request_id: str = "",
        prompt_key: str = "run_ai_summary",
        provider_key: str = "openai",
    ) -> OpenAIProviderExecutionResponse:
        call_count[0] += 1
        receipt = ProviderUsageReceipt(
            provider_key=provider_key,
            model_name=model_name,
            receipt_id="receipt-env-001",
            receipt_source=ProviderReceiptSource.REAL_PROVIDER,
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            estimated_cost_usd=0.0,
            pricing_source="openai.chat_completions.usage",
        )
        return OpenAIProviderExecutionResponse(
            success=True,
            mode="provider_openai",
            summary="ok",
            output_text=_VALID_AI_MARKDOWN,
            prompt_key=prompt_key,
            prompt_char_count=len(prompt_text.encode("utf-8")),
            provider_usage_receipt=receipt,
        )

    mock_config = MagicMock()
    mock_runtime_config = MagicMock()
    mock_runtime_config.api_key = "sk-test-env-key"
    mock_runtime_config.base_url = "https://api.deepseek.com/v1"
    mock_runtime_config.timeout_seconds = 120
    mock_runtime_config.detected_provider_type = "deepseek"
    mock_runtime_config.model_names = {"balanced": "deepseek-v4-pro"}
    mock_config.resolve_openai_runtime_config.return_value = mock_runtime_config

    service = RunAISummaryService(
        run_repository=RunRepository(db_session),
        task_repository=TaskRepository(db_session),
        run_ai_summary_repository=RunAISummaryRepository(db_session),
        provider_config_service=mock_config,
        # No ai_text_generator
    )
    assert service._can_try_ai() is True

    with patch.object(
        OpenAIProviderExecutorService, "generate_text", fake_generate_text
    ):
        summary = service.generate_run_summary(run_id=run_id)

    assert call_count[0] == 1, "generate_text should be called exactly once"
    assert summary.source == RunAISummarySource.AI
    assert summary.model_provider == "deepseek"
    assert summary.model_name == "deepseek-v4-pro"
    assert summary.provider_receipt_id == "receipt-env-001"
    assert "## 运行结论" in summary.summary_markdown


def test_no_env_no_config_still_falls_back():
    """ProviderConfigService with no api_key -> api_key is None."""

    from app.services.provider_config_service import ProviderConfigService
    from app.core.config import settings as _settings
    from pathlib import Path

    # Use a non-existent config path to ensure no saved config leaks
    fake_path = Path(_settings.runtime_data_dir) / "provider-settings" / "__nonexistent__.json"
    config_service = ProviderConfigService(config_path=fake_path)

    assert config_service.resolve_openai_runtime_config().api_key is None
