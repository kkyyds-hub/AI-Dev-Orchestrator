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
    P14_LIFECYCLE_RESULT_SOURCE_DETAIL,
)
from app.services.project_director_readonly_review_service import (
    ProjectDirectorReadonlyReviewService,
)


FORBIDDEN_OUTPUT_KEYS = {
    "api_key",
    "token",
    "secret",
    "pid",
    "raw command",
    "raw stdout",
    "raw stderr",
}


def _walk_keys(value) -> set[str]:
    if isinstance(value, dict):
        keys = {str(key).lower() for key in value}
        for child in value.values():
            keys.update(_walk_keys(child))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for child in value:
            keys.update(_walk_keys(child))
        return keys
    return set()


def _safe_p12_task() -> Task:
    source_message_id = uuid4()
    return Task(
        title="Safe dry-run task dispatch for P15",
        input_summary=(
            "SAFE DRY-RUN TASK DISPATCH ONLY. "
            f"source_message_id={source_message_id}; "
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
        source_draft_id=f"p12-{source_message_id}",
    )


def _p14_message(
    *,
    session_id,
    task_id,
    source_detail=P14_LIFECYCLE_RESULT_SOURCE_DETAIL,
) -> ProjectDirectorMessage:
    return ProjectDirectorMessage(
        session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content="P14 controlled subprocess lifecycle result; no Git write.",
        sequence_no=1,
        related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=source_detail,
        suggested_actions=[
            {
                "type": "p14_controlled_subprocess_lifecycle_result_record",
                "source_task_id": str(task_id),
                "source_message_id": str(uuid4()),
                "launch_mode": "dry_run",
                "product_runtime_git_write_allowed": False,
                "worktree_write_allowed": False,
                "real_code_modified": False,
                "git_write_performed": False,
                "ai_project_director_total_loop": "Partial",
            }
        ],
    )


def test_builds_readonly_review_plan_from_p14_lifecycle_result() -> None:
    session_id = uuid4()
    task = _safe_p12_task()
    message = _p14_message(session_id=session_id, task_id=task.id)

    plan = ProjectDirectorReadonlyReviewService().build_plan_from_sources(
        session_id=session_id,
        source_task=task,
        source_message=message,
        user_confirmed=True,
        requested_reviewer_executor="codex",
        review_mode="dry_run",
    )

    assert plan.review_status == "planned"
    assert plan.session_id == session_id
    assert plan.source_task_id == task.id
    assert plan.source_message_id == message.id
    assert plan.p14_lifecycle_message_id == message.id
    assert plan.readonly_review is True
    assert plan.reviewer_agent is True
    assert plan.executor_backed_review_allowed is True
    assert plan.product_runtime_git_write_allowed is False
    assert plan.worktree_write_allowed is False
    assert plan.file_write_allowed is False
    assert plan.real_code_modified is False
    assert plan.git_write_performed is False
    assert plan.native_executor_started is False
    assert plan.codex_started is False
    assert plan.claude_code_started is False
    assert plan.review_result_message_bound is False
    assert plan.ai_project_director_total_loop == "Partial"
    assert plan.blocked_reasons == []

    payload = plan.model_dump(mode="json")
    assert _walk_keys(payload).isdisjoint(FORBIDDEN_OUTPUT_KEYS)
    assert "代码已完成" not in json.dumps(payload, ensure_ascii=False)


def test_readonly_review_plan_blocks_without_user_confirmation() -> None:
    session_id = uuid4()
    task = _safe_p12_task()
    message = _p14_message(session_id=session_id, task_id=task.id)

    plan = ProjectDirectorReadonlyReviewService().build_plan_from_sources(
        session_id=session_id,
        source_task=task,
        source_message=message,
        user_confirmed=False,
    )

    assert plan.review_status == "blocked"
    assert "user_confirmation_required" in plan.blocked_reasons
    assert plan.native_executor_started is False
    assert plan.product_runtime_git_write_allowed is False


def test_readonly_review_plan_blocks_without_p14_lifecycle_source() -> None:
    plan = ProjectDirectorReadonlyReviewService().build_plan_from_sources(
        session_id=uuid4(),
        source_task=_safe_p12_task(),
        source_message=None,
        user_confirmed=True,
    )

    assert plan.review_status == "blocked"
    assert "p14_lifecycle_message_missing" in plan.blocked_reasons
    assert plan.review_result_message_bound is False


def test_readonly_review_plan_blocks_source_message_from_other_session() -> None:
    session_id = uuid4()
    task = _safe_p12_task()
    message = _p14_message(session_id=uuid4(), task_id=task.id)

    plan = ProjectDirectorReadonlyReviewService().build_plan_from_sources(
        session_id=session_id,
        source_task=task,
        source_message=message,
        user_confirmed=True,
    )

    assert plan.review_status == "blocked"
    assert "source_message_not_in_session" in plan.blocked_reasons


def test_readonly_review_plan_blocks_non_p14_lifecycle_source_detail() -> None:
    session_id = uuid4()
    task = _safe_p12_task()
    message = _p14_message(
        session_id=session_id,
        task_id=task.id,
        source_detail="p13_controlled_executor_dispatch",
    )

    plan = ProjectDirectorReadonlyReviewService().build_plan_from_sources(
        session_id=session_id,
        source_task=task,
        source_message=message,
        user_confirmed=True,
    )

    assert plan.review_status == "blocked"
    assert "source_message_is_not_p14_lifecycle_result" in plan.blocked_reasons


def test_readonly_review_plan_does_not_create_task_run_worker_or_executor() -> None:
    session_id = uuid4()
    task = _safe_p12_task()
    message = _p14_message(session_id=session_id, task_id=task.id)

    plan = ProjectDirectorReadonlyReviewService().build_plan_from_sources(
        session_id=session_id,
        source_task=task,
        source_message=message,
        user_confirmed=True,
    )

    assert plan.review_status == "planned"
    assert plan.native_executor_started is False
    assert plan.codex_started is False
    assert plan.claude_code_started is False
    assert plan.file_write_allowed is False
    assert plan.real_code_modified is False
    assert plan.git_write_performed is False
