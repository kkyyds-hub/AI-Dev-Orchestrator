"""Day12 smoke for formal session-level boss intervention write contract."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from uuid import UUID

from fastapi.testclient import TestClient

from _smoke_runtime_env import prepare_runtime_data_dir

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v5-day12-boss-intervention-smoke"

if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _request_json(
    client: TestClient,
    method: str,
    path: str,
    expected_status: int,
    payload: dict[str, object] | None = None,
) -> dict[str, object] | list[object]:
    response = client.request(method, path, json=payload)
    if response.status_code != expected_status:
        raise SystemExit(
            f"{method} {path} expected {expected_status}, got {response.status_code}: {response.text}"
        )
    return response.json()


def _prepare_env() -> Path:
    runtime_data_dir = prepare_runtime_data_dir(SMOKE_RUNTIME_DATA_DIR)
    os.environ["DAILY_BUDGET_USD"] = "8.00"
    os.environ["SESSION_BUDGET_USD"] = "8.00"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"
    return runtime_data_dir


def _seed_agent_session(
    *,
    task_id: str,
    state: str,
) -> dict[str, str]:
    from app.core.db import SessionLocal
    from app.domain.project_role import ProjectRoleCode
    from app.domain.run import RunFailureCategory, RunStatus
    from app.repositories.agent_message_repository import AgentMessageRepository
    from app.repositories.agent_session_repository import AgentSessionRepository
    from app.repositories.run_repository import RunRepository
    from app.repositories.task_repository import TaskRepository
    from app.services.agent_conversation_service import AgentConversationService
    from app.services.context_builder_service import AgentThreadContextSeed

    db_session = SessionLocal()
    try:
        task = TaskRepository(db_session).get_by_id(UUID(task_id))
        if task is None or task.project_id is None:
            raise SystemExit(f"Task not found or detached from project: {task_id}")

        run = RunRepository(db_session).create_running_run(
            task_id=task.id,
            model_name=f"day12-smoke-{state}",
            owner_role_code=ProjectRoleCode.PRODUCT_MANAGER,
        )
        service = AgentConversationService(
            agent_session_repository=AgentSessionRepository(db_session),
            agent_message_repository=AgentMessageRepository(db_session),
        )
        session = service.start_session(
            project_id=task.project_id,
            task_id=task.id,
            run_id=run.id,
            owner_role_code=ProjectRoleCode.PRODUCT_MANAGER,
            context_seed=AgentThreadContextSeed(
                task_id=task.id,
                context_checkpoint_id=f"ckpt-day12-{state}",
                context_rehydrated=False,
                pressure_level="normal",
                usage_ratio=0.25,
                bad_context_detected=False,
                bad_context_reasons=[],
                context_contract_summary=f"Day12 smoke seed for {state} session.",
            ),
        )
        session = service.record_execution_started(session_id=session.id)

        if state == "completed":
            session = service.record_execution_outcome(
                session_id=session.id,
                execution_success=True,
                execution_summary="Completed session prepared for terminal write gate smoke.",
                verification_present=True,
                verification_success=True,
                verification_summary="Verification passed.",
                run_failure_category=None,
            )
            session = service.finalize_session(
                session_id=session.id,
                run_status=RunStatus.SUCCEEDED,
                run_failure_category=None,
                final_summary="Completed terminal session for Day12 gate smoke.",
            )
        elif state == "failed":
            session = service.record_execution_outcome(
                session_id=session.id,
                execution_success=False,
                execution_summary="Failed session prepared for terminal write gate smoke.",
                verification_present=True,
                verification_success=False,
                verification_summary="Verification failed.",
                run_failure_category=RunFailureCategory.VERIFICATION_FAILED,
            )
            session = service.finalize_session(
                session_id=session.id,
                run_status=RunStatus.FAILED,
                run_failure_category=RunFailureCategory.VERIFICATION_FAILED,
                final_summary="Failed terminal session for Day12 gate smoke.",
            )
        elif state != "running":
            raise SystemExit(f"Unsupported smoke session state: {state}")

        db_session.commit()
        return {
            "task_id": str(task.id),
            "run_id": str(run.id),
            "session_id": str(session.id),
            "session_status": session.status.value,
            "session_phase": session.current_phase.value,
        }
    finally:
        db_session.close()


def main() -> None:
    runtime_data_dir = _prepare_env()

    from app.main import create_application

    app = create_application()

    with TestClient(app) as client:
        project = _request_json(
            client,
            "POST",
            "/projects",
            201,
            {
                "name": "Day12 Boss Intervention Smoke",
                "summary": "Validate formal session-level intervention write contract.",
                "stage": "execution",
            },
        )
        project_id = project["id"]

        running_task = _request_json(
            client,
            "POST",
            "/tasks",
            201,
            {
                "project_id": project_id,
                "title": "Day12 running-session seed",
                "input_summary": "seed non-terminal session for intervention success path",
                "priority": "high",
                "acceptance_criteria": ["manual running session created"],
            },
        )
        completed_task = _request_json(
            client,
            "POST",
            "/tasks",
            201,
            {
                "project_id": project_id,
                "title": "Day12 completed terminal session seed",
                "input_summary": "seed completed finalized session for gate verification",
                "priority": "high",
                "acceptance_criteria": ["completed terminal session created"],
            },
        )
        failed_task = _request_json(
            client,
            "POST",
            "/tasks",
            201,
            {
                "project_id": project_id,
                "title": "Day12 failed terminal session seed",
                "input_summary": "seed failed finalized session for gate verification",
                "priority": "high",
                "acceptance_criteria": ["failed terminal session created"],
            },
        )

        running_session = _seed_agent_session(
            task_id=running_task["id"],
            state="running",
        )
        completed_session = _seed_agent_session(
            task_id=completed_task["id"],
            state="completed",
        )
        failed_session = _seed_agent_session(
            task_id=failed_task["id"],
            state="failed",
        )
        session_id = running_session["session_id"]

        write_payload = {
            "intervention_type": "boss_directive",
            "note_event_type": "manual_intervention",
            "content_summary": "Boss requires a stricter validation pass before release.",
            "content_detail": "Pause current release handoff and run full regression checklist first.",
        }
        write_result = _request_json(
            client,
            "POST",
            f"/agent-threads/projects/{project_id}/sessions/{session_id}/interventions",
            201,
            write_payload,
        )

        intervention_message = write_result["intervention_message"]
        session_snapshot = write_result["session"]
        _assert(
            intervention_message["message_type"] == "intervention",
            "write response should persist intervention message_type",
        )
        _assert(
            intervention_message["event_type"] == "boss_intervention_submitted",
            "write response should use stable intervention event_type",
        )
        _assert(
            intervention_message["intervention_type"] == write_payload["intervention_type"],
            "write response should echo intervention_type",
        )
        _assert(
            intervention_message["note_event_type"] == write_payload["note_event_type"],
            "write response should echo note_event_type",
        )
        _assert(
            intervention_message["content_summary"] == write_payload["content_summary"],
            "write response should persist content_summary",
        )
        _assert(
            session_snapshot["latest_intervention_type"] == write_payload["intervention_type"],
            "session snapshot should backfill latest_intervention_type",
        )
        _assert(
            session_snapshot["latest_note_event_type"] == write_payload["note_event_type"],
            "session snapshot should backfill latest_note_event_type",
        )

        interventions = _request_json(
            client,
            "GET",
            (
                f"/agent-threads/projects/{project_id}/interventions"
                f"?session_id={session_id}&limit=20"
            ),
            200,
        )
        _assert(
            interventions["total_items"] >= 1,
            "intervention feed should contain at least one item after write",
        )
        intervention_items = interventions["items"]
        intervention_event_types = [item["event_type"] for item in intervention_items]
        _assert(
            "boss_intervention_submitted" in intervention_event_types,
            "intervention feed should include the newly written boss_intervention_submitted event",
        )
        _assert(
            any(
                item["message_type"] == "intervention"
                and item["intervention_type"] == write_payload["intervention_type"]
                for item in intervention_items
            ),
            "intervention feed should expose intervention_type on message_type=intervention rows",
        )

        sessions = _request_json(
            client,
            "GET",
            f"/agent-threads/projects/{project_id}/sessions?limit=20",
            200,
        )
        matched_session = next(
            item for item in sessions if item["session_id"] == session_id
        )
        _assert(
            matched_session["latest_intervention_type"] == write_payload["intervention_type"],
            "session list should surface latest_intervention_type after write",
        )

        terminal_completed_response = client.post(
            f"/agent-threads/projects/{project_id}/sessions/{completed_session['session_id']}/interventions",
            json=write_payload,
        )
        _assert(
            terminal_completed_response.status_code == 409,
            "completed finalized session should reject boss intervention writes with HTTP 409",
        )
        terminal_failed_response = client.post(
            f"/agent-threads/projects/{project_id}/sessions/{failed_session['session_id']}/interventions",
            json=write_payload,
        )
        _assert(
            terminal_failed_response.status_code == 409,
            "failed finalized session should reject boss intervention writes with HTTP 409",
        )

        another_project = _request_json(
            client,
            "POST",
            "/projects",
            201,
            {
                "name": "Day12 Boss Intervention Wrong Project",
                "summary": "Used to validate project/session boundary checks.",
                "stage": "execution",
            },
        )
        another_project_id = another_project["id"]
        _request_json(
            client,
            "POST",
            f"/agent-threads/projects/{another_project_id}/sessions/{session_id}/interventions",
            404,
            write_payload,
        )

    print(
        json.dumps(
            {
                "runtime_data_dir": str(SMOKE_RUNTIME_DATA_DIR),
                "runtime_data_dir_effective": str(runtime_data_dir),
                "project_id": project_id,
                "session_id": session_id,
                "running_session": running_session,
                "completed_session": completed_session,
                "failed_session": failed_session,
                "write_result": write_result,
                "interventions": interventions,
                "sessions": sessions,
                "terminal_completed_write_status": terminal_completed_response.status_code,
                "terminal_completed_write_body": terminal_completed_response.json(),
                "terminal_failed_write_status": terminal_failed_response.status_code,
                "terminal_failed_write_body": terminal_failed_response.json(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
