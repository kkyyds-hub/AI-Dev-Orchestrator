"""P14 Project Director controlled subprocess lifecycle smoke.

Default path delegates to the P13 dry-run chain and does not start native
executors, Codex, Claude Code, Worker subprocesses, worktree writes, or product
runtime Git writes. The controlled subprocess path is available only when every
explicit safety flag is present.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
from uuid import UUID, uuid4

from p13_project_director_controlled_executor_lifecycle_smoke import DEFAULT_RUNTIME_DATA_DIR


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON summary.")
    parser.add_argument(
        "--keep-temp-data",
        action="store_true",
        help="Keep the isolated runtime data directory after the smoke finishes.",
    )
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        help="Use this isolated runtime data directory instead of a temp directory.",
    )
    parser.add_argument(
        "--launch-mode",
        choices=("dry_run", "controlled_smoke"),
        default="dry_run",
    )
    parser.add_argument(
        "--executor",
        choices=("codex", "claude-code"),
        default="codex",
    )
    parser.add_argument(
        "--requested-agent-role",
        choices=("programmer", "reviewer"),
        default="programmer",
    )
    parser.add_argument("--enable-native-process", action="store_true")
    parser.add_argument("--auto-terminate", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=0.0)
    parser.add_argument("--use-supervisor", action="store_true")
    parser.add_argument("--supervisor-cleanup-after-launch", action="store_true")
    parser.add_argument(
        "--fake-runner",
        action="store_true",
        help="Use an in-process fake native runner for deterministic safety tests.",
    )
    return parser.parse_args()


def _base_summary(runtime_data_dir: Path, sqlite_db_path: Path) -> dict[str, Any]:
    return {
        "smoke_status": "failed",
        "session_created": False,
        "session_id": None,
        "project_id_present": False,
        "p11_dry_run_message_bound": False,
        "p12_safe_task_created": False,
        "p12_worker_run_once_ok": False,
        "p12_worker_simulate_mode": False,
        "run_created_by": None,
        "p13_dispatch_message_bound": False,
        "source_task_id_present": False,
        "source_message_id_present": False,
        "run_id_present": False,
        "controlled_subprocess_runner": "none",
        "p14_lifecycle_result_message_bound": False,
        "message_readback_ok": False,
        "launch_mode": "dry_run",
        "requested_executor": "codex",
        "requested_agent_role": "programmer",
        "controlled_executor_pilot": True,
        "executor_backed_agent": True,
        "native_executor_started": False,
        "codex_started": False,
        "claude_code_started": False,
        "agent_session_bound": False,
        "runtime_handle_id_present": False,
        "process_handle_id_present": False,
        "supervisor_required": True,
        "supervisor_registered": False,
        "auto_terminate_required": True,
        "terminate_attempted": False,
        "cleanup_required": True,
        "supervisor_cleanup_done": False,
        "product_runtime_git_write_allowed": False,
        "worktree_write_allowed": False,
        "frontend_required": False,
        "run_created": False,
        "real_code_modified": False,
        "git_write_performed": False,
        "ai_project_director_total_loop": "Partial",
        "p9_production_safe_long_running_executor_lifecycle": "Partial",
        "runtime_data_dir": str(runtime_data_dir),
        "sqlite_db_path": str(sqlite_db_path),
        "isolated_runtime_data": False,
        "blocked_reasons": [],
        "risks": [
            "controlled subprocess smoke is not code modification completion",
            "controlled subprocess smoke is not product runtime Git write authorization",
        ],
        "unknowns": [
            "production-safe long-running executor lifecycle is still downstream work",
        ],
    }


def _configure_isolated_environment(runtime_data_dir: Path) -> Path:
    sqlite_db_path = runtime_data_dir / "db" / "orchestrator.db"
    os.environ["RUNTIME_DATA_DIR"] = str(runtime_data_dir)
    os.environ["SQLITE_DB_PATH"] = str(sqlite_db_path)
    os.environ["WORKER_SIMULATE_EXECUTION_OVERRIDE"] = "true"
    os.environ.pop("OPENAI_API_KEY", None)
    return sqlite_db_path


def _controlled_smoke_gate(args: argparse.Namespace) -> list[str]:
    if args.launch_mode != "controlled_smoke":
        return []
    blocked_reasons: list[str] = []
    if not args.enable_native_process:
        blocked_reasons.append("enable_native_process_required")
    if not args.auto_terminate:
        blocked_reasons.append("auto_terminate_required")
    if args.timeout_seconds <= 0:
        blocked_reasons.append("positive_timeout_seconds_required")
    if not args.use_supervisor:
        blocked_reasons.append("supervisor_required")
    if not args.supervisor_cleanup_after_launch:
        blocked_reasons.append("supervisor_cleanup_after_launch_required")
    return blocked_reasons


def _request_json(
    client: Any,
    method: str,
    path: str,
    expected_status: int,
    **kwargs: Any,
) -> dict[str, Any] | list[Any]:
    response = getattr(client, method.lower())(path, **kwargs)
    if response.status_code != expected_status:
        raise RuntimeError(f"{method} {path} returned HTTP {response.status_code}")
    return response.json()


class _FakeProcessAdapter:
    def __init__(self) -> None:
        self.terminate_calls = 0
        self.kill_calls = 0

    def terminate(self) -> None:
        self.terminate_calls += 1

    def kill(self) -> None:
        self.kill_calls += 1


class _SupervisorFakeRunner:
    def __init__(self, *, supervisor: Any) -> None:
        self._supervisor = supervisor

    def start(
        self,
        *,
        argv: tuple[str, ...],
        workspace_path: str,
        agent_session_id: str,
    ) -> Any:
        from app.external_executors.actual_native_launcher import (
            RealExecutorNativeProcessHandle,
        )

        process_handle_id = f"fake-p14-process-{uuid4().hex}"
        self._supervisor.register(
            process_handle_id,
            executor_label=argv[0],
            agent_session_id=agent_session_id,
            workspace_path=workspace_path,
            process_adapter=_FakeProcessAdapter(),
        )
        return RealExecutorNativeProcessHandle(process_handle_id=process_handle_id)


def _prepare_project_director_chain(
    *,
    summary: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, str]:
    import warnings

    warnings.filterwarnings(
        "ignore",
        message="Using `httpx` with `starlette.testclient` is deprecated.*",
        category=Warning,
    )
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        project_payload = _request_json(
            client,
            "POST",
            "/projects",
            201,
            json={
                "name": "P14 controlled subprocess smoke",
                "summary": "Isolated Project Director controlled subprocess smoke.",
                "status": "active",
                "stage": "execution",
            },
        )
        project_id = project_payload["id"]
        summary["project_id_present"] = bool(project_id)

        session_payload = _request_json(
            client,
            "POST",
            "/project-director/sessions",
            201,
            json={
                "project_id": project_id,
                "goal_text": (
                    "P14 Project Director controlled subprocess lifecycle smoke"
                )
            },
        )
        session_id = session_payload["id"]
        summary["session_created"] = bool(session_id)
        summary["session_id"] = session_id

        p11_payload = _request_json(
            client,
            "POST",
            f"/project-director/sessions/{session_id}/evidence-to-agent/dry-run",
            200,
            json={"user_goal": "P14 evidence-to-agent source message"},
        )
        p11_message = p11_payload.get("message") or {}
        summary["p11_dry_run_message_bound"] = (
            p11_message.get("source_detail")
            == "p11_evidence_to_agent_session_dry_run"
        )

        p12_payload = _request_json(
            client,
            "POST",
            f"/project-director/sessions/{session_id}/dry-run-task-dispatch",
            200,
            json={
                "source_message_id": p11_message.get("id"),
                "user_confirmed": True,
            },
        )
        source_task_id = p12_payload.get("created_task_id")
        p12_message = p12_payload.get("message") or {}
        source_message_id = p12_message.get("id")
        summary["p12_safe_task_created"] = bool(
            source_task_id and p12_payload.get("safe_dry_run_task") is True
        )
        summary["source_task_id_present"] = bool(source_task_id)
        summary["source_message_id_present"] = bool(source_message_id)

        worker_payload = _request_json(client, "POST", "/workers/run-once", 200)
        run_id = worker_payload.get("run_id")
        summary["p12_worker_run_once_ok"] = (
            worker_payload.get("claimed") is True
            and worker_payload.get("task_id") == source_task_id
            and run_id is not None
        )
        summary["p12_worker_simulate_mode"] = bool(
            summary["p12_worker_run_once_ok"]
            and os.environ.get("WORKER_SIMULATE_EXECUTION_OVERRIDE") == "true"
        )
        summary["run_created"] = run_id is not None
        summary["run_created_by"] = "p12_worker_simulate" if run_id else None
        summary["run_id_present"] = run_id is not None

        p13_payload = _request_json(
            client,
            "POST",
            f"/project-director/sessions/{session_id}/controlled-executor-dispatch",
            200,
            json={
                "source_task_id": source_task_id,
                "source_message_id": source_message_id,
                "user_confirmed": True,
                "requested_agent_role": args.requested_agent_role,
                "requested_executor": args.executor,
                "launch_mode": "dry_run",
            },
        )
        summary["p13_dispatch_message_bound"] = bool(
            p13_payload.get("message_bound")
        )

        messages_payload = _request_json(
            client,
            "GET",
            f"/project-director/sessions/{session_id}/messages",
            200,
        )
        messages = messages_payload.get("messages") or []
        has_p11 = any(
            item.get("source_detail") == "p11_evidence_to_agent_session_dry_run"
            for item in messages
        )
        has_p12 = any(
            item.get("source_detail") == "p12_dry_run_task_dispatch"
            for item in messages
        )
        has_p13_dispatch = any(
            item.get("source_detail") == "p13_controlled_executor_dispatch"
            for item in messages
        )
        summary["message_readback_ok"] = has_p11 and has_p12 and has_p13_dispatch

    return {
        "project_id": project_id,
        "session_id": session_id,
        "source_task_id": source_task_id,
        "source_message_id": source_message_id,
        "run_id": run_id,
    }


def _create_agent_session(
    *,
    project_id: str,
    source_task_id: str,
    run_id: str,
    workspace_path: str,
) -> UUID:
    from app.core.db import SessionLocal
    from app.domain.agent_session import (
        AgentSessionPhase,
        AgentSessionReviewStatus,
        AgentSessionStatus,
        WorkspaceType,
    )
    from app.repositories.agent_session_repository import AgentSessionRepository

    db_session = SessionLocal()
    try:
        agent_session = AgentSessionRepository(db_session).create(
            project_id=UUID(project_id),
            task_id=UUID(source_task_id),
            run_id=UUID(run_id),
            status=AgentSessionStatus.RUNNING,
            review_status=AgentSessionReviewStatus.NONE,
            current_phase=AgentSessionPhase.CONTEXT_READY,
            owner_role_code=None,
            context_checkpoint_id=None,
            context_rehydrated=False,
            summary="P14 controlled subprocess lifecycle smoke",
            workspace_type=WorkspaceType.READ_ONLY,
            workspace_path=workspace_path,
            workspace_clean=True,
        )
        db_session.commit()
        return agent_session.id
    finally:
        db_session.close()


def _controlled_command_available(executor: str) -> bool:
    command_name = "codex" if executor == "codex" else "claude"
    return shutil.which(command_name) is not None


def _run_controlled_subprocess(
    *,
    summary: dict[str, Any],
    args: argparse.Namespace,
    project_id: str,
    source_task_id: str,
    run_id: str,
    runtime_data_dir: Path,
) -> None:
    from app.core.db import SessionLocal
    from app.external_executors.actual_native_launcher import (
        RealExecutorNativeLaunchMode,
        SubprocessRealExecutorNativeRunner,
    )
    from app.external_executors.actual_process_supervisor import (
        RealExecutorProcessStatus,
        RealExecutorProcessSupervisor,
    )
    from app.external_executors.actual_runner_wiring import (
        RealExecutorRunnerFactory,
        RealExecutorRunnerWiringInput,
        RealExecutorRunnerWiringMode,
    )
    from app.external_executors.actual_silent_launch_service import (
        RealExecutorSilentLaunchInput,
    )
    from app.repositories.agent_session_repository import AgentSessionRepository

    if not args.fake_runner and not _controlled_command_available(args.executor):
        summary["smoke_status"] = "blocked"
        summary["blocked_reasons"].append("executor_unavailable")
        return

    supervisor = RealExecutorProcessSupervisor()
    agent_session_id = _create_agent_session(
        project_id=project_id,
        source_task_id=source_task_id,
        run_id=run_id,
        workspace_path=str(runtime_data_dir),
    )
    db_session = SessionLocal()
    try:
        if args.fake_runner:
            wiring_mode = RealExecutorRunnerWiringMode.FAKE
            process_runner = None
            fake_runner = _SupervisorFakeRunner(supervisor=supervisor)
            summary["controlled_subprocess_runner"] = "fake"
        else:
            wiring_mode = RealExecutorRunnerWiringMode.SUBPROCESS_ENABLED
            process_runner = SubprocessRealExecutorNativeRunner(
                auto_terminate=args.auto_terminate,
                timeout_seconds=args.timeout_seconds,
                process_supervisor=supervisor,
            )
            fake_runner = None
            summary["controlled_subprocess_runner"] = "subprocess"

        wiring = RealExecutorRunnerFactory(
            fake_runner=fake_runner,
            process_runner=process_runner,
            process_supervisor=supervisor,
        ).wire(
            RealExecutorRunnerWiringInput(
                wiring_mode=wiring_mode,
                launch_mode=RealExecutorNativeLaunchMode.ENABLED,
                allow_native_process=True,
                executor_label=args.executor,
            ),
            agent_session_repository=AgentSessionRepository(db_session),
        )
        if wiring.silent_launch_service is None:
            summary["smoke_status"] = "blocked"
            summary["blocked_reasons"].append("silent_launch_service_missing")
            return

        launch_result = wiring.silent_launch_service.launch(
            RealExecutorSilentLaunchInput(
                agent_session_id=agent_session_id,
                executor_label=args.executor,
                workspace_path=str(runtime_data_dir),
                prelaunch_ready=True,
                launch_mode=wiring.launch_mode,
                allow_native_process=wiring.allow_native_process,
                command_plan_redacted=True,
            )
        )
        db_session.commit()
    except FileNotFoundError:
        summary["smoke_status"] = "blocked"
        summary["blocked_reasons"].append("executor_unavailable")
        return
    finally:
        db_session.close()

    if launch_result.launch_status != "launch_started":
        summary["smoke_status"] = "blocked"
        summary["blocked_reasons"].extend(launch_result.blocked_reasons)
        if not summary["blocked_reasons"]:
            summary["blocked_reasons"].append("launch_not_started")
        return

    runtime_handle_id = launch_result.runtime_handle_id
    supervisor_record = (
        supervisor.get_status(runtime_handle_id)
        if runtime_handle_id is not None
        else None
    )
    summary["native_executor_started"] = launch_result.native_process_started
    summary["codex_started"] = args.executor == "codex"
    summary["claude_code_started"] = args.executor == "claude-code"
    summary["agent_session_bound"] = launch_result.agent_session_bound
    summary["runtime_handle_id_present"] = runtime_handle_id is not None
    summary["process_handle_id_present"] = runtime_handle_id is not None
    summary["supervisor_registered"] = bool(
        supervisor_record is not None
        and supervisor_record.status != RealExecutorProcessStatus.MISSING
    )

    if runtime_handle_id is not None:
        terminate_result = supervisor.terminate(runtime_handle_id)
        summary["terminate_attempted"] = True
        summary["blocked_reasons"].extend(terminate_result.blocked_reasons)
        cleanup_result = supervisor.cleanup(runtime_handle_id)
        summary["supervisor_cleanup_done"] = cleanup_result.action_success
        summary["blocked_reasons"].extend(cleanup_result.blocked_reasons)

    required_checks = (
        "native_executor_started",
        "agent_session_bound",
        "runtime_handle_id_present",
        "process_handle_id_present",
        "supervisor_registered",
        "terminate_attempted",
        "supervisor_cleanup_done",
    )
    if all(summary[item] for item in required_checks):
        summary["smoke_status"] = "passed_controlled_smoke"
        summary["p9_production_safe_long_running_executor_lifecycle"] = (
            "Pass with note"
        )
        summary["blocked_reasons"] = []
    else:
        summary["smoke_status"] = "blocked"
        if not summary["blocked_reasons"]:
            summary["blocked_reasons"].append("controlled_lifecycle_incomplete")


def _record_p14_lifecycle_result(
    *,
    summary: dict[str, Any],
    session_id: str,
    source_task_id: str,
    source_message_id: str,
) -> None:
    from app.core.db import SessionLocal
    from app.domain.project_director_controlled_executor_dispatch import (
        ProjectDirectorControlledExecutorLifecycleResult,
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

    db_session = SessionLocal()
    try:
        service = ProjectDirectorControlledExecutorDispatchService(
            session_repository=ProjectDirectorSessionRepository(db_session),
            message_repository=ProjectDirectorMessageRepository(db_session),
            task_repository=TaskRepository(db_session),
        )
        service.record_lifecycle_result(
            result=ProjectDirectorControlledExecutorLifecycleResult(
                session_id=UUID(session_id),
                source_task_id=UUID(source_task_id),
                source_message_id=UUID(source_message_id),
                requested_agent_role=summary["requested_agent_role"],
                requested_executor=summary["requested_executor"],
                launch_mode=summary["launch_mode"],
                native_executor_started=summary["native_executor_started"],
                codex_started=summary["codex_started"],
                claude_code_started=summary["claude_code_started"],
                agent_session_bound=summary["agent_session_bound"],
                runtime_handle_id_present=summary["runtime_handle_id_present"],
                process_handle_id_present=summary["process_handle_id_present"],
                supervisor_registered=summary["supervisor_registered"],
                terminate_attempted=summary["terminate_attempted"],
                supervisor_cleanup_done=summary["supervisor_cleanup_done"],
                run_created=summary["run_created"],
                real_code_modified=False,
                git_write_performed=False,
                p9_production_safe_long_running_executor_lifecycle=summary[
                    "p9_production_safe_long_running_executor_lifecycle"
                ],
                blocked_reasons=list(summary["blocked_reasons"]),
            ),
            source_detail=P14_LIFECYCLE_RESULT_SOURCE_DETAIL,
        )
        summary["p14_lifecycle_result_message_bound"] = True
    finally:
        db_session.close()


def _readback_p14_lifecycle_message(*, session_id: str) -> bool:
    import warnings

    warnings.filterwarnings(
        "ignore",
        message="Using `httpx` with `starlette.testclient` is deprecated.*",
        category=Warning,
    )
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        messages_payload = _request_json(
            client,
            "GET",
            f"/project-director/sessions/{session_id}/messages",
            200,
        )
    messages = messages_payload.get("messages") or []
    return any(
        item.get("source_detail") == "p14_controlled_subprocess_lifecycle_result"
        and _p14_action_is_safe(item.get("suggested_actions") or [])
        for item in messages
    )


def _p14_action_is_safe(actions: list[dict[str, Any]]) -> bool:
    for action in actions:
        if action.get("type") != "p14_controlled_subprocess_lifecycle_result_record":
            continue
        return (
            action.get("launch_mode") == "controlled_smoke"
            and action.get("agent_session_bound") is True
            and action.get("process_handle_id_present") is True
            and action.get("supervisor_registered") is True
            and action.get("terminate_attempted") is True
            and action.get("supervisor_cleanup_done") is True
            and action.get("product_runtime_git_write_allowed") is False
            and action.get("worktree_write_allowed") is False
            and action.get("real_code_modified") is False
            and action.get("git_write_performed") is False
            and action.get("ai_project_director_total_loop") == "Partial"
        )
    return False


def run_smoke(runtime_data_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    sqlite_db_path = _configure_isolated_environment(runtime_data_dir)
    summary = _base_summary(runtime_data_dir.resolve(), sqlite_db_path.resolve())
    summary["isolated_runtime_data"] = runtime_data_dir.resolve() != DEFAULT_RUNTIME_DATA_DIR
    summary["launch_mode"] = args.launch_mode
    summary["requested_executor"] = args.executor
    summary["requested_agent_role"] = args.requested_agent_role

    if not summary["isolated_runtime_data"]:
        summary["smoke_status"] = "blocked"
        summary["blocked_reasons"].append("runtime_data_dir_must_be_isolated")
        return summary

    gate_blocks = _controlled_smoke_gate(args)
    if gate_blocks:
        summary["smoke_status"] = "blocked"
        summary["blocked_reasons"].extend(gate_blocks)
        return summary

    if (
        args.launch_mode == "controlled_smoke"
        and not args.fake_runner
        and not _controlled_command_available(args.executor)
    ):
        summary["smoke_status"] = "blocked"
        summary["blocked_reasons"].append("executor_unavailable")
        return summary

    try:
        chain = _prepare_project_director_chain(summary=summary, args=args)
    except Exception as exc:  # pragma: no cover - operator smoke evidence path.
        summary["smoke_status"] = "failed"
        summary["blocked_reasons"].append(type(exc).__name__)
        return summary

    if args.launch_mode == "controlled_smoke":
        _run_controlled_subprocess(
            summary=summary,
            args=args,
            project_id=chain["project_id"],
            source_task_id=chain["source_task_id"],
            run_id=chain["run_id"],
            runtime_data_dir=runtime_data_dir,
        )
        if summary["smoke_status"] == "passed_controlled_smoke":
            _record_p14_lifecycle_result(
                summary=summary,
                session_id=chain["session_id"],
                source_task_id=chain["source_task_id"],
                source_message_id=chain["source_message_id"],
            )
            summary["message_readback_ok"] = _readback_p14_lifecycle_message(
                session_id=chain["session_id"]
            )
            if not summary["message_readback_ok"]:
                summary["smoke_status"] = "partial"
                summary["blocked_reasons"].append("p14_message_readback_failed")
        return summary

    required_checks = (
        "session_created",
        "p11_dry_run_message_bound",
        "p12_safe_task_created",
        "p12_worker_run_once_ok",
        "p12_worker_simulate_mode",
        "run_created",
        "p13_dispatch_message_bound",
        "message_readback_ok",
        "isolated_runtime_data",
    )
    if all(summary[item] for item in required_checks):
        summary["smoke_status"] = "passed_dry_run"
    else:
        summary["smoke_status"] = "partial"
        summary["blocked_reasons"].append("required_smoke_check_failed")
    return summary


def main() -> int:
    args = _parse_args()
    temp_created = args.runtime_dir is None
    runtime_data_dir = (
        Path(tempfile.mkdtemp(prefix="p14-controlled-subprocess-smoke-"))
        if args.runtime_dir is None
        else args.runtime_dir
    ).resolve()
    runtime_data_dir.mkdir(parents=True, exist_ok=True)

    try:
        summary = run_smoke(runtime_data_dir, args)
    finally:
        should_cleanup = temp_created and not args.keep_temp_data
        if should_cleanup:
            shutil.rmtree(runtime_data_dir, ignore_errors=True)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    else:
        print(f"P14 controlled subprocess smoke: {summary['smoke_status']}")

    return (
        0
        if summary["smoke_status"] in {
            "passed",
            "passed_dry_run",
            "passed_controlled_smoke",
        }
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
