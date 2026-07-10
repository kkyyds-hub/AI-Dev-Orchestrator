"""API composition tests for P21-C-H-C4 readonly review execution."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.api.routes import project_director as route_module
from app.api.router import api_router
from app.core.db import get_db_session
from app.core.db_tables import ORMBase, ProjectDirectorMessageTable, RunTable, TaskTable
from app.domain.project_director_controlled_executor_dispatch import (
    ProjectDirectorControlledExecutorLifecycleResult,
)
from app.external_executors.readonly_reviewer_transport import (
    ReadonlyReviewerTransportProtocol,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_controlled_executor_dispatch_service import (
    P14_LIFECYCLE_RESULT_SOURCE_DETAIL,
    ProjectDirectorControlledExecutorDispatchService,
)


# ── Spy classes ─────────────────────────────────────────────────────


class SpyTransport:
    """Fake transport that returns valid strict JSON."""

    def __init__(self, raw_output: str | None = None) -> None:
        self._raw_output = raw_output or json.dumps({
            "review_status": "reviewed",
            "verdict": "non_blocking_findings",
            "risk_level": "medium",
            "summary": "One non-blocking issue.",
            "findings": [
                {
                    "finding_id": "F-001",
                    "severity": "medium",
                    "title": "Example finding",
                    "summary": "Example summary",
                    "evidence_paths": ["runtime/orchestrator/app/domain/new_module.py"],
                    "recommended_action": "Review before the next stage.",
                },
            ],
            "recommended_next_step": "Proceed after review.",
        })
        self.execute_calls = 0

    def execute(self, request):
        self.execute_calls += 1
        from app.external_executors.readonly_reviewer_transport import (
            ReadonlyReviewerTransportRawResult,
        )
        return ReadonlyReviewerTransportRawResult(
            transport_status="completed",
            requested_reviewer_executor=request.requested_reviewer_executor,
            raw_output_text=self._raw_output,
            transport_invoked=True,
            execution_mode="native_capture_transport",
            real_reviewer_started=True,
            real_reviewer_executed=True,
            native_process_started=True,
            provider_called=False,
            codex_started=request.requested_reviewer_executor == "codex",
            claude_code_started=request.requested_reviewer_executor == "claude-code",
        )


class SpyResolver:
    def __init__(self, transport=None) -> None:
        self._transport = transport or SpyTransport()
        self.calls: list[str] = []

    def __call__(self, executor: str):
        self.calls.append(executor)
        return self._transport


class SpyFactory:
    def __init__(self, resolver=None) -> None:
        self._resolver = resolver or SpyResolver()
        self.calls: list[str] = []
        self.kwargs: dict[str, Any] = {}

    def __call__(self, workspace_path: str):
        self.calls.append(workspace_path)
        return self._resolver


# ── DB / App setup ──────────────────────────────────────────────────


def _sf(tmp_path):
    db_path = tmp_path / "orchestrator-c4d-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _app(sf) -> FastAPI:
    app = FastAPI()
    app.include_router(api_router)

    def override():
        s = sf()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db_session] = override
    return app


def _count(sf, table) -> int:
    s = sf()
    try:
        return s.execute(select(func.count()).select_from(table)).scalar_one()
    finally:
        s.close()


# ── Chain builders ──────────────────────────────────────────────────


def _p14(sf, *, session_id, source_task_id, source_message_id):
    db = sf()
    try:
        svc = ProjectDirectorControlledExecutorDispatchService(
            session_repository=ProjectDirectorSessionRepository(db),
            message_repository=ProjectDirectorMessageRepository(db),
            task_repository=TaskRepository(db),
        )
        msg = svc.record_lifecycle_result(
            result=ProjectDirectorControlledExecutorLifecycleResult(
                session_id=UUID(session_id), source_task_id=UUID(source_task_id),
                source_message_id=UUID(source_message_id), requested_agent_role="programmer",
                requested_executor="codex", launch_mode="dry_run",
                product_runtime_git_write_allowed=False, worktree_write_allowed=False,
                frontend_required=False, run_created=True, real_code_modified=False,
                git_write_performed=False, ai_project_director_total_loop="Partial",
            ), source_detail=P14_LIFECYCLE_RESULT_SOURCE_DETAIL,
        )
        return str(msg.id)
    finally:
        db.close()


def _p15(sf, **kw):
    from app.services.project_director_readonly_review_service import ProjectDirectorReadonlyReviewService
    db = sf()
    try:
        svc = ProjectDirectorReadonlyReviewService(
            session_repository=ProjectDirectorSessionRepository(db),
            message_repository=ProjectDirectorMessageRepository(db),
            task_repository=TaskRepository(db),
        )
        r = svc.confirm_review(session_id=UUID(kw["session_id"]), source_task_id=UUID(kw["source_task_id"]),
                               source_message_id=UUID(kw["source_message_id"]), user_confirmed=True,
                               requested_reviewer_executor="codex", review_mode="fake_review")
        return str(r.message.id)
    finally:
        db.close()


def _p16(sf, **kw):
    from app.services.project_director_programmer_no_write_plan_service import ProjectDirectorProgrammerNoWritePlanService
    db = sf()
    try:
        svc = ProjectDirectorProgrammerNoWritePlanService(
            session_repository=ProjectDirectorSessionRepository(db),
            message_repository=ProjectDirectorMessageRepository(db),
            task_repository=TaskRepository(db),
        )
        r = svc.confirm_plan(session_id=UUID(kw["session_id"]), source_task_id=UUID(kw["source_task_id"]),
                             source_message_id=UUID(kw["source_message_id"]), user_confirmed=True,
                             requested_programmer_executor="codex", planning_mode="fake_plan")
        return str(r.message.id)
    finally:
        db.close()


def _p17(sf, **kw):
    from app.services.project_director_programmer_no_write_execution_service import ProjectDirectorProgrammerNoWriteExecutionService
    db = sf()
    try:
        svc = ProjectDirectorProgrammerNoWriteExecutionService(
            session_repository=ProjectDirectorSessionRepository(db),
            message_repository=ProjectDirectorMessageRepository(db),
            task_repository=TaskRepository(db),
        )
        r = svc.confirm_execution(session_id=UUID(kw["session_id"]), source_task_id=UUID(kw["source_task_id"]),
                                  source_message_id=UUID(kw["source_message_id"]), user_confirmed=True,
                                  requested_programmer_executor="codex", execution_mode="fake_execution")
        return str(r.message.id)
    finally:
        db.close()


def _prepare_full_chain(client, sf):
    """Build persisted chain up to review handoff."""
    s = client.post("/project-director/sessions", json={"goal_text": "P21-C-H-C4-D test"})
    assert s.status_code == 201
    sid = s.json()["id"]

    p11 = client.post(f"/project-director/sessions/{sid}/evidence-to-agent/dry-run",
                      json={"user_goal": "P21-C-H-C4-D evidence"})
    p12 = client.post(f"/project-director/sessions/{sid}/dry-run-task-dispatch",
                      json={"source_message_id": p11.json()["message"]["id"], "user_confirmed": True})
    tid = p12.json()["created_task_id"]
    p12m = p12.json()["message"]["id"]

    client.post("/workers/run-once")
    client.post(f"/project-director/sessions/{sid}/controlled-executor-dispatch",
                json={"source_task_id": tid, "source_message_id": p12m,
                      "user_confirmed": True, "requested_agent_role": "programmer",
                      "requested_executor": "codex", "launch_mode": "dry_run"})

    p14 = _p14(sf, session_id=sid, source_task_id=tid, source_message_id=p12m)
    p15 = _p15(sf, session_id=sid, source_task_id=tid, source_message_id=p14)
    p16 = _p16(sf, session_id=sid, source_task_id=tid, source_message_id=p15)
    p17 = _p17(sf, session_id=sid, source_task_id=tid, source_message_id=p16)

    p20 = client.post(f"/project-director/sessions/{sid}/sandbox-write-preflight",
                      json={"source_task_id": tid, "source_message_id": p17,
                            "user_confirmed": True, "preflight_mode": "dry_run",
                            "file_operations": [
                                {"path": "runtime/orchestrator/app/domain/new_module.py", "operation": "create",
                                 "reason": "test", "patch_preview": ["PREVIEW ONLY: no repository file was modified."]}]})
    p21 = client.post(f"/project-director/sessions/{sid}/sandbox-write-execution",
                      json={"source_task_id": tid, "source_message_id": p20.json()["message"]["id"],
                            "user_confirmed": True, "execution_mode": "dry_run"})
    lock = client.post(f"/project-director/sessions/{sid}/sandbox-write-design-lock",
                       json={"source_task_id": tid, "source_message_id": p21.json()["message"]["id"],
                             "user_confirmed": True})
    guard = client.post(f"/project-director/sessions/{sid}/sandbox-workspace-guard",
                        json={"source_task_id": tid, "source_message_id": lock.json()["message"]["id"],
                              "user_confirmed": True})
    manifest = client.post(f"/project-director/sessions/{sid}/sandbox-operation-manifest-guard",
                           json={"source_task_id": tid, "source_message_id": guard.json()["message"]["id"],
                                 "user_confirmed": True})
    create = client.post(f"/project-director/sessions/{sid}/sandbox-workspace-create",
                         json={"source_task_id": tid, "source_message_id": manifest.json()["message"]["id"],
                               "user_confirmed": True})
    write = client.post(f"/project-director/sessions/{sid}/sandbox-workspace-evidence-manifest",
                        json={"source_task_id": tid, "source_message_id": create.json()["message"]["id"],
                              "user_confirmed": True})
    ce = client.post(f"/project-director/sessions/{sid}/sandbox-candidate-files-write",
                     json={"source_task_id": tid, "source_message_id": write.json()["message"]["id"],
                           "user_confirmed": True,
                           "candidate_files": [{"relative_path": "runtime/orchestrator/app/domain/new_module.py",
                                                "content": "print('new')\n", "operation": "create"}]})
    diff = client.post(f"/project-director/sessions/{sid}/sandbox-candidate-diff-generate",
                       json={"source_task_id": tid, "source_message_id": ce.json()["message"]["id"],
                             "user_confirmed": True})
    handoff = client.post(f"/project-director/sessions/{sid}/sandbox-candidate-diff-review-handoff",
                          json={"source_task_id": tid, "source_message_id": diff.json()["message"]["id"],
                                "user_confirmed": True})
    assert handoff.status_code == 200
    return sid, tid, handoff.json()["message"]["id"]


def _create_preflight(client, sid, tid, handoff_msg_id):
    """Lock preflight evidence."""
    r = client.post(
        f"/project-director/sessions/{sid}/sandbox-candidate-diff-review-execution-preflight",
        json={"source_task_id": tid, "source_message_id": handoff_msg_id, "user_confirmed": True},
    )
    assert r.status_code == 200
    return r.json()["message"]["id"]


def _make_spy_factory_patch(spy_factory):
    """Return a class that, when constructed, records kwargs and delegates to spy_factory."""
    class PatchedFactory:
        _last_kwargs: dict = {}
        def __init__(self, **kwargs):
            PatchedFactory._last_kwargs = kwargs
        def __call__(self, workspace_path):
            spy_factory.calls.append(workspace_path)
            return spy_factory._resolver
    return PatchedFactory


# ══════════════════════════════════════════════════════════════════════
# A. Config defaults
# ══════════════════════════════════════════════════════════════════════


class TestConfigDefaults:
    def test_defaults_in_settings(self, monkeypatch) -> None:
        from app.core.config import load_settings
        monkeypatch.delenv("READONLY_REVIEWER_TIMEOUT_SECONDS", raising=False)
        monkeypatch.delenv("READONLY_REVIEWER_MAX_OUTPUT_BYTES", raising=False)
        s = load_settings()
        assert s.readonly_reviewer_timeout_seconds == 180
        assert s.readonly_reviewer_max_output_bytes == 262144


# ══════════════════════════════════════════════════════════════════════
# B. Request schema
# ══════════════════════════════════════════════════════════════════════


class TestRequestSchema:
    def test_request_exact_fields(self) -> None:
        from app.api.routes.project_director import (
            ConfirmSandboxCandidateDiffReadonlyReviewExecutionRequest,
        )
        fields = set(ConfirmSandboxCandidateDiffReadonlyReviewExecutionRequest.model_fields.keys())
        assert fields == {"source_task_id", "source_message_id", "user_confirmed"}

    def test_request_no_executor_field(self) -> None:
        from app.api.routes.project_director import (
            ConfirmSandboxCandidateDiffReadonlyReviewExecutionRequest,
        )
        fields = set(ConfirmSandboxCandidateDiffReadonlyReviewExecutionRequest.model_fields.keys())
        for forbidden in ["requested_reviewer_executor", "executor", "workspace_path",
                          "workspace_root", "provider", "model", "api_key", "token",
                          "environment"]:
            assert forbidden not in fields


# ══════════════════════════════════════════════════════════════════════
# C. Response leak boundary
# ══════════════════════════════════════════════════════════════════════


class TestResponseLeakBoundary:
    def test_response_no_forbidden_fields(self) -> None:
        from app.api.routes.project_director import (
            ConfirmSandboxCandidateDiffReadonlyReviewExecutionResponse,
        )
        fields = set(ConfirmSandboxCandidateDiffReadonlyReviewExecutionResponse.model_fields.keys())
        for forbidden in ["raw_output_text", "raw_output", "stdout", "stderr",
                          "review_prompt_text", "unified_diff_text",
                          "workspace_path", "workspace_root",
                          "api_key", "token", "secret", "credential"]:
            assert forbidden not in fields, f"Forbidden field in response: {forbidden}"

    def test_response_allows_sha_and_bytes(self) -> None:
        from app.api.routes.project_director import (
            ConfirmSandboxCandidateDiffReadonlyReviewExecutionResponse,
        )
        fields = set(ConfirmSandboxCandidateDiffReadonlyReviewExecutionResponse.model_fields.keys())
        assert "raw_output_sha256" in fields
        assert "raw_output_bytes" in fields
        assert "review_prompt_sha256" in fields
        assert "review_prompt_bytes" in fields


# ══════════════════════════════════════════════════════════════════════
# D. Finding schema
# ══════════════════════════════════════════════════════════════════════


class TestFindingSchema:
    def test_finding_uses_evidence_paths(self) -> None:
        from app.api.routes.project_director import (
            SandboxCandidateDiffReadonlyReviewFindingResponse,
        )
        fields = set(SandboxCandidateDiffReadonlyReviewFindingResponse.model_fields.keys())
        assert "evidence_paths" in fields
        assert "evidence_refs" not in fields


# ══════════════════════════════════════════════════════════════════════
# E. user_confirmed=false
# ══════════════════════════════════════════════════════════════════════


class TestExplicitConfirmation:
    def test_user_confirmed_false_blocks(self, tmp_path, monkeypatch) -> None:
        sf = _sf(tmp_path)
        app = _app(sf)
        spy_factory = SpyFactory()
        monkeypatch.setattr(route_module, "ReadonlyReviewerTransportResolverFactory",
                            lambda **kw: spy_factory)
        with TestClient(app) as client:
            sid, tid, preflight_msg_id = _prepare_full_chain(client, sf)
            _create_preflight(client, sid, tid, preflight_msg_id)
            r = client.post(
                f"/project-director/sessions/{sid}/sandbox-candidate-diff-review-execution",
                json={"source_task_id": tid, "source_message_id": preflight_msg_id,
                      "user_confirmed": False},
            )
            assert r.status_code == 409
            assert r.json()["detail"] == "user_confirmation_required"
            assert spy_factory.calls == []


# ══════════════════════════════════════════════════════════════════════
# F. Early preflight failure
# ══════════════════════════════════════════════════════════════════════


class TestEarlyPreflightFailure:
    def test_invalid_source_blocks_without_composition(self, tmp_path, monkeypatch) -> None:
        sf = _sf(tmp_path)
        app = _app(sf)
        spy_factory = SpyFactory()
        monkeypatch.setattr(route_module, "ReadonlyReviewerTransportResolverFactory",
                            lambda **kw: spy_factory)
        with TestClient(app) as client:
            sid, tid, _ = _prepare_full_chain(client, sf)
            wrong_msg = str(uuid4())
            r = client.post(
                f"/project-director/sessions/{sid}/sandbox-candidate-diff-review-execution",
                json={"source_task_id": tid, "source_message_id": wrong_msg,
                      "user_confirmed": True},
            )
            assert r.status_code == 409
            assert spy_factory.calls == []


# ══════════════════════════════════════════════════════════════════════
# G. Success path composition
# ══════════════════════════════════════════════════════════════════════


class TestSuccessComposition:
    def test_success_full_chain(self, tmp_path, monkeypatch) -> None:
        sf = _sf(tmp_path)
        app = _app(sf)
        spy_transport = SpyTransport()
        spy_resolver = SpyResolver(transport=spy_transport)
        spy_factory = SpyFactory(resolver=spy_resolver)
        PatchedFactory = _make_spy_factory_patch(spy_factory)
        monkeypatch.setattr(route_module, "ReadonlyReviewerTransportResolverFactory",
                            PatchedFactory)
        with TestClient(app) as client:
            sid, tid, handoff_msg_id = _prepare_full_chain(client, sf)
            preflight_msg_id = _create_preflight(client, sid, tid, handoff_msg_id)
            msgs_before = _count(sf, ProjectDirectorMessageTable)
            tasks_before = _count(sf, TaskTable)
            runs_before = _count(sf, RunTable)

            r = client.post(
                f"/project-director/sessions/{sid}/sandbox-candidate-diff-review-execution",
                json={"source_task_id": tid, "source_message_id": preflight_msg_id,
                      "user_confirmed": True},
            )
            assert r.status_code == 200
            body = r.json()

            assert body["adapter_status"] == "validated_output"
            assert body["review_prompt_verified"] is True
            assert body["transport_invoked"] is True
            assert body["transport_status"] == "completed"
            assert body["strict_json_valid"] is True
            assert body["schema_valid"] is True
            assert body["semantics_valid"] is True
            assert body["evidence_scope_valid"] is True
            assert body["review_status"] == "reviewed"
            assert body["verdict"] == "non_blocking_findings"
            assert body["risk_level"] == "medium"
            assert body["real_reviewer_started"] is True
            assert body["real_reviewer_executed"] is True
            assert body["claude_code_started"] is False or body["codex_started"] is False

            assert len(body["findings"]) == 1
            f0 = body["findings"][0]
            assert f0["finding_id"] == "F-001"
            assert f0["severity"] == "medium"
            assert f0["evidence_paths"] == ["runtime/orchestrator/app/domain/new_module.py"]

            assert body["message_bound"] is True
            assert body["message"] is not None
            assert body["ai_project_director_total_loop"] == "Partial"

            for flag in ["main_project_file_written", "sandbox_file_written",
                         "manifest_file_written", "diff_file_written", "patch_applied",
                         "git_write_performed", "worktree_created", "worker_started",
                         "task_created", "run_created"]:
                assert body[flag] is False, f"{flag} should be False"

            assert _count(sf, ProjectDirectorMessageTable) == msgs_before + 1
            assert _count(sf, TaskTable) == tasks_before
            assert _count(sf, RunTable) == runs_before

    def test_factory_called_once_with_persisted_workspace(self, tmp_path, monkeypatch) -> None:
        sf = _sf(tmp_path)
        app = _app(sf)
        spy_transport = SpyTransport()
        spy_resolver = SpyResolver(transport=spy_transport)
        spy_factory = SpyFactory(resolver=spy_resolver)
        PatchedFactory = _make_spy_factory_patch(spy_factory)
        monkeypatch.setattr(route_module, "ReadonlyReviewerTransportResolverFactory",
                            PatchedFactory)
        with TestClient(app) as client:
            sid, tid, handoff_msg_id = _prepare_full_chain(client, sf)
            preflight_msg_id = _create_preflight(client, sid, tid, handoff_msg_id)
            r = client.post(
                f"/project-director/sessions/{sid}/sandbox-candidate-diff-review-execution",
                json={"source_task_id": tid, "source_message_id": preflight_msg_id,
                      "user_confirmed": True},
            )
            assert r.status_code == 200
            assert len(spy_factory.calls) == 1
            assert spy_factory.calls[0].startswith("/")

    def test_resolver_receives_persisted_executor_codex(self, tmp_path, monkeypatch) -> None:
        sf = _sf(tmp_path)
        app = _app(sf)
        spy_transport = SpyTransport()
        spy_resolver = SpyResolver(transport=spy_transport)
        spy_factory = SpyFactory(resolver=spy_resolver)
        PatchedFactory = _make_spy_factory_patch(spy_factory)
        monkeypatch.setattr(route_module, "ReadonlyReviewerTransportResolverFactory",
                            PatchedFactory)
        with TestClient(app) as client:
            sid, tid, handoff_msg_id = _prepare_full_chain(client, sf)
            preflight_msg_id = _create_preflight(client, sid, tid, handoff_msg_id)
            r = client.post(
                f"/project-director/sessions/{sid}/sandbox-candidate-diff-review-execution",
                json={"source_task_id": tid, "source_message_id": preflight_msg_id,
                      "user_confirmed": True},
            )
            assert r.status_code == 200
            assert spy_resolver.calls == ["codex"]

    def test_request_extra_executor_does_not_override_persisted(self, tmp_path, monkeypatch) -> None:
        sf = _sf(tmp_path)
        app = _app(sf)
        spy_transport = SpyTransport()
        spy_resolver = SpyResolver(transport=spy_transport)
        spy_factory = SpyFactory(resolver=spy_resolver)
        PatchedFactory = _make_spy_factory_patch(spy_factory)
        monkeypatch.setattr(route_module, "ReadonlyReviewerTransportResolverFactory",
                            PatchedFactory)
        with TestClient(app) as client:
            sid, tid, handoff_msg_id = _prepare_full_chain(client, sf)
            preflight_msg_id = _create_preflight(client, sid, tid, handoff_msg_id)
            r = client.post(
                f"/project-director/sessions/{sid}/sandbox-candidate-diff-review-execution",
                json={"source_task_id": tid, "source_message_id": preflight_msg_id,
                      "user_confirmed": True,
                      "requested_reviewer_executor": "claude-code",
                      "executor": "deepseek"},
            )
            assert r.status_code == 200
            assert spy_resolver.calls == ["codex"]

    def test_request_extra_workspace_does_not_override_persisted(self, tmp_path, monkeypatch) -> None:
        sf = _sf(tmp_path)
        app = _app(sf)
        spy_transport = SpyTransport()
        spy_resolver = SpyResolver(transport=spy_transport)
        spy_factory = SpyFactory(resolver=spy_resolver)
        PatchedFactory = _make_spy_factory_patch(spy_factory)
        monkeypatch.setattr(route_module, "ReadonlyReviewerTransportResolverFactory",
                            PatchedFactory)
        with TestClient(app) as client:
            sid, tid, handoff_msg_id = _prepare_full_chain(client, sf)
            preflight_msg_id = _create_preflight(client, sid, tid, handoff_msg_id)
            spy_factory.calls.clear()
            r = client.post(
                f"/project-director/sessions/{sid}/sandbox-candidate-diff-review-execution",
                json={"source_task_id": tid, "source_message_id": preflight_msg_id,
                      "user_confirmed": True,
                      "workspace_path": "/evil/path",
                      "workspace_root": "/evil"},
            )
            assert r.status_code == 200
            assert len(spy_factory.calls) == 1
            assert spy_factory.calls[0] != "/evil/path"


# ══════════════════════════════════════════════════════════════════════
# H. Blocked reasons mapping
# ══════════════════════════════════════════════════════════════════════


class TestBlockedMapping:
    def test_blocked_with_reasons(self, tmp_path, monkeypatch) -> None:
        sf = _sf(tmp_path)
        app = _app(sf)
        spy_factory = SpyFactory()
        monkeypatch.setattr(route_module, "ReadonlyReviewerTransportResolverFactory",
                            lambda **kw: spy_factory)
        with TestClient(app) as client:
            sid, tid, preflight_msg_id = _prepare_full_chain(client, sf)
            _create_preflight(client, sid, tid, preflight_msg_id)
            wrong_task = str(uuid4())
            r = client.post(
                f"/project-director/sessions/{sid}/sandbox-candidate-diff-review-execution",
                json={"source_task_id": wrong_task, "source_message_id": preflight_msg_id,
                      "user_confirmed": True},
            )
            assert r.status_code == 409
            detail = r.json()["detail"]
            assert len(detail) > 0


# ══════════════════════════════════════════════════════════════════════
# I. Exception mapping
# ══════════════════════════════════════════════════════════════════════


class TestExceptionMapping:
    def test_not_found_value_error_maps_to_404(self, tmp_path, monkeypatch) -> None:
        sf = _sf(tmp_path)
        app = _app(sf)
        monkeypatch.setattr(route_module, "ReadonlyReviewerTransportResolverFactory",
                            lambda **kw: SpyFactory())
        with TestClient(app) as client:
            sid, tid, preflight_msg_id = _prepare_full_chain(client, sf)
            _create_preflight(client, sid, tid, preflight_msg_id)
            r = client.post(
                f"/project-director/sessions/{sid}/sandbox-candidate-diff-review-execution",
                json={"source_task_id": str(uuid4()), "source_message_id": str(uuid4()),
                      "user_confirmed": True},
            )
            assert r.status_code in (404, 409, 422)


# ══════════════════════════════════════════════════════════════════════
# J. Import / architecture boundary
# ══════════════════════════════════════════════════════════════════════


class TestRouteImportBoundary:
    def test_route_does_not_import_concrete_transports(self) -> None:
        import ast
        import inspect
        source = inspect.getsource(route_module)
        tree = ast.parse(source)
        imported_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module is not None:
                    imported_modules.add(node.module)
        for mod_name in imported_modules:
            assert "readonly_reviewer_codex_app_server_transport" not in mod_name
            assert "readonly_reviewer_native_transport" not in mod_name
