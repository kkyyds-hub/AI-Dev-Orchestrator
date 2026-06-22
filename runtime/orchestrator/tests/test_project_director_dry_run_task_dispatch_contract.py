from __future__ import annotations

import json
from uuid import uuid4

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.services.project_director_dry_run_task_dispatch_service import (
    P11_DRY_RUN_SOURCE_DETAIL,
    ProjectDirectorDryRunTaskDispatchService,
)


def _p11_message(*, session_id, evidence_pack_id: str | None = "p10-a-pack") -> ProjectDirectorMessage:
    return ProjectDirectorMessage(
        session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="P11 dry-run summary; not execution completion.",
        sequence_no=1,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=P11_DRY_RUN_SOURCE_DETAIL,
        suggested_actions=[
            {
                "type": "evidence_to_agent_dry_run_record",
                "evidence_pack_id": evidence_pack_id,
                "dry_run_status": "passed",
                "composed_tasks_count": 1,
                "product_runtime_git_write_allowed": False,
                "frontend_required": False,
                "ai_project_director_total_loop": "Partial",
            }
        ],
    )


def test_builds_confirmation_plan_from_p11_dry_run_message() -> None:
    session_id = uuid4()
    message = _p11_message(session_id=session_id)

    plan = ProjectDirectorDryRunTaskDispatchService().build_plan_from_message(
        session_id=session_id,
        source_message=message,
        user_goal="Create a safe dry-run task from P11 trace",
    )

    assert plan.dispatch_status == "ready_for_confirmation"
    assert plan.session_id == session_id
    assert plan.source_message_id == message.id
    assert plan.evidence_pack_id == "p10-a-pack"
    assert plan.safe_dry_run_task is True
    assert plan.worker_simulate_required is True
    assert plan.product_runtime_git_write_allowed is False
    assert plan.frontend_required is False
    assert plan.native_executor_started is False
    assert plan.codex_started is False
    assert plan.claude_code_started is False
    assert plan.ai_project_director_total_loop == "Partial"
    assert plan.allowed_files
    assert plan.forbidden_files
    assert plan.targeted_tests
    assert plan.blocked_reasons == []

    payload = json.dumps(plan.model_dump(mode="json"), ensure_ascii=False).lower()
    for forbidden in (
        "api_key",
        "token",
        "secret",
        "pid",
        "raw command",
        "raw stdout",
        "raw stderr",
    ):
        assert forbidden not in payload


def test_builds_confirmation_plan_from_p11_dry_run_summary() -> None:
    session_id = uuid4()
    source_message_id = uuid4()

    plan = ProjectDirectorDryRunTaskDispatchService().build_plan_from_dry_run_summary(
        session_id=session_id,
        source_message_id=source_message_id,
        dry_run_summary={
            "dry_run_status": "passed",
            "evidence_pack_id": "p10-a-summary-pack",
            "product_runtime_git_write_allowed": False,
            "frontend_required": False,
        },
        user_goal="P12-A contract summary path",
    )

    assert plan.dispatch_status == "ready_for_confirmation"
    assert plan.evidence_pack_id == "p10-a-summary-pack"
    assert plan.safe_dry_run_task is True
    assert plan.worker_simulate_required is True
    assert plan.product_runtime_git_write_allowed is False
    assert plan.frontend_required is False


def test_blocks_missing_evidence_pack_without_creating_task_or_worker() -> None:
    session_id = uuid4()
    message = _p11_message(session_id=session_id, evidence_pack_id=None)

    plan = ProjectDirectorDryRunTaskDispatchService().build_plan_from_message(
        session_id=session_id,
        source_message=message,
    )

    assert plan.dispatch_status == "blocked"
    assert "evidence_pack_id_missing" in plan.blocked_reasons
    assert plan.safe_dry_run_task is True
    assert plan.worker_simulate_required is True
    assert plan.product_runtime_git_write_allowed is False
    assert plan.frontend_required is False
