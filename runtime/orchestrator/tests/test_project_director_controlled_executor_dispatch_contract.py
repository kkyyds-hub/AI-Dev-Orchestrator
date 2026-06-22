from __future__ import annotations

import json
from uuid import uuid4

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.task import Task, TaskPriority, TaskRiskLevel
from app.services.project_director_controlled_executor_dispatch_service import (
    P12_DISPATCH_SOURCE_DETAIL,
    ProjectDirectorControlledExecutorDispatchService,
)


def _p12_message(*, session_id) -> ProjectDirectorMessage:
    return ProjectDirectorMessage(
        session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="P12 safe dry-run task dispatch; not executor completion.",
        sequence_no=1,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=P12_DISPATCH_SOURCE_DETAIL,
        suggested_actions=[
            {
                "type": "p12_dry_run_task_dispatch_record",
                "safe_dry_run_task": True,
                "worker_simulate_required": True,
                "product_runtime_git_write_allowed": False,
                "frontend_required": False,
                "native_executor_started": False,
                "codex_started": False,
                "claude_code_started": False,
            }
        ],
    )


def _safe_p12_task(*, message_id) -> Task:
    return Task(
        title="Safe dry-run task dispatch for p10-a-pack",
        input_summary=(
            "SAFE DRY-RUN TASK DISPATCH ONLY. "
            f"source_message_id={message_id}; "
            "worker_simulate_required=true; "
            "product_runtime_git_write_allowed=false; "
            "native_executor_started=false; codex_started=false; "
            "claude_code_started=false;"
        ),
        priority=TaskPriority.NORMAL,
        acceptance_criteria=[
            "safe_dry_run_task=true",
            "worker_simulate_required=true",
            "product_runtime_git_write_allowed=false",
            "native_executor_started=false",
            "codex_started=false",
            "claude_code_started=false",
            "AI Project Director total loop remains Partial",
        ],
        risk_level=TaskRiskLevel.LOW,
        source_draft_id=f"p12-{message_id}",
    )


def _bind_message_to_task(
    message: ProjectDirectorMessage,
    task: Task,
) -> ProjectDirectorMessage:
    actions = list(message.suggested_actions)
    actions[0] = {
        **actions[0],
        "type": "p12_dry_run_task_dispatch_record",
        "created_task_id": str(task.id),
    }
    return message.model_copy(update={"suggested_actions": actions})


def test_builds_controlled_executor_plan_from_p12_safe_dry_run_source() -> None:
    session_id = uuid4()
    message = _p12_message(session_id=session_id)
    task = _safe_p12_task(message_id=message.id)
    message = _bind_message_to_task(message, task)

    plan = ProjectDirectorControlledExecutorDispatchService().build_plan_from_sources(
        session_id=session_id,
        source_task=task,
        source_message=message,
        user_confirmed=True,
        requested_agent_role="programmer",
        requested_executor="codex",
    )

    assert plan.dispatch_status == "planned"
    assert plan.session_id == session_id
    assert plan.source_task_id == task.id
    assert plan.source_message_id == message.id
    assert plan.controlled_executor_pilot is True
    assert plan.executor_backed_agent is True
    assert plan.programmer_agent_allowed is True
    assert plan.reviewer_agent_allowed is True
    assert plan.product_runtime_git_write_allowed is False
    assert plan.worktree_write_allowed is False
    assert plan.native_executor_started is False
    assert plan.codex_started is False
    assert plan.claude_code_started is False
    assert plan.supervisor_required is True
    assert plan.auto_terminate_required is True
    assert plan.cleanup_required is True
    assert plan.frontend_required is False
    assert plan.agent_session_bound is False
    assert plan.process_handle_id_present is False
    assert plan.supervisor_registered is False
    assert plan.supervisor_cleanup_done is False
    assert plan.run_created is False
    assert plan.ai_project_director_total_loop == "Partial"
    assert plan.p9_production_safe_long_running_executor_lifecycle == "Partial"
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


def test_controlled_executor_plan_blocks_without_user_confirmation() -> None:
    session_id = uuid4()
    message = _p12_message(session_id=session_id)
    task = _safe_p12_task(message_id=message.id)
    message = _bind_message_to_task(message, task)

    plan = ProjectDirectorControlledExecutorDispatchService().build_plan_from_sources(
        session_id=session_id,
        source_task=task,
        source_message=message,
        user_confirmed=False,
    )

    assert plan.dispatch_status == "blocked"
    assert "user_confirmation_required" in plan.blocked_reasons
    assert plan.product_runtime_git_write_allowed is False
    assert plan.native_executor_started is False
    assert plan.run_created is False


def test_controlled_executor_plan_blocks_without_source_task_or_message() -> None:
    plan = ProjectDirectorControlledExecutorDispatchService().build_plan_from_sources(
        session_id=uuid4(),
        source_task=None,
        source_message=None,
        user_confirmed=True,
    )

    assert plan.dispatch_status == "blocked"
    assert "source_task_missing" in plan.blocked_reasons
    assert "source_message_missing" in plan.blocked_reasons
    assert plan.agent_session_bound is False
    assert plan.process_handle_id_present is False


def test_controlled_executor_plan_blocks_non_safe_dry_run_source() -> None:
    session_id = uuid4()
    message = _p12_message(session_id=session_id)
    task = Task(
        title="Not a P12 safe task",
        input_summary="regular task",
        acceptance_criteria=["product_runtime_git_write_allowed=false"],
        source_draft_id=f"p12-{message.id}",
    )
    message = _bind_message_to_task(message, task)

    plan = ProjectDirectorControlledExecutorDispatchService().build_plan_from_sources(
        session_id=session_id,
        source_task=task,
        source_message=message,
        user_confirmed=True,
    )

    assert plan.dispatch_status == "blocked"
    assert "source_task_is_not_safe_dry_run" in plan.blocked_reasons
    assert plan.product_runtime_git_write_allowed is False
    assert plan.worktree_write_allowed is False
    assert plan.native_executor_started is False


def test_controlled_executor_plan_blocks_controlled_smoke_in_api_contract() -> None:
    session_id = uuid4()
    message = _p12_message(session_id=session_id)
    task = _safe_p12_task(message_id=message.id)
    message = _bind_message_to_task(message, task)

    plan = ProjectDirectorControlledExecutorDispatchService().build_plan_from_sources(
        session_id=session_id,
        source_task=task,
        source_message=message,
        user_confirmed=True,
        launch_mode="controlled_smoke",
    )

    assert plan.dispatch_status == "blocked"
    assert "controlled_smoke_not_enabled_in_api" in plan.blocked_reasons
    assert plan.native_executor_started is False
    assert plan.codex_started is False
    assert plan.claude_code_started is False
