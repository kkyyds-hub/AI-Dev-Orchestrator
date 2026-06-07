"""Targeted P5-C/P5-D/P5-E tests for failed worker run recovery decisions."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes.workers import WorkerRunOnceResponse
from app.core.config import settings
from app.core.db_tables import ORMBase
from app.domain.agent_dispatch_decision import (
    P6_AGENT_DISPATCH_DECISION_AUDIT_EVENT_TYPE,
)
from app.domain.agent_message import AgentMessageType
from app.domain.failure_recovery_decision import (
    P5_FAILURE_RECOVERY_DECISION_AUDIT_EVENT_TYPE,
    P5_FAILURE_RECOVERY_DECISION_SOURCE,
    P5_FAILURE_RECOVERY_DECISION_VERSION,
)
from app.domain.project import Project
from app.domain.run import Run, RunFailureCategory, RunStatus
from app.domain.task import Task, TaskBlockingReasonCode, TaskStatus
from app.repositories.agent_message_repository import AgentMessageRepository
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.failure_review_repository import FailureReviewRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.services.failure_recovery_audit_service import FailureRecoveryAuditService
from app.services.failure_review_service import (
    P5C_FAILURE_RECOVERY_DECISION_PAYLOAD_KEY,
    FailureReviewService,
)
from app.services.run_logging_service import RunLoggingService
from app.workers.task_worker import TaskWorker, WorkerRunResult, build_task_worker


def _assert_p5c_internal_decision_payload(payload: dict) -> dict:
    decision = payload[P5C_FAILURE_RECOVERY_DECISION_PAYLOAD_KEY]

    assert decision["source"] == P5_FAILURE_RECOVERY_DECISION_SOURCE
    assert decision["version"] == P5_FAILURE_RECOVERY_DECISION_VERSION
    assert decision["audit_event_type"] == (
        P5_FAILURE_RECOVERY_DECISION_AUDIT_EVENT_TYPE
    )
    assert decision["failure_category"] == "execution_failed"
    assert decision["recoverable"] is True
    assert decision["retry_allowed"] is True
    assert decision["recommended_owner"] == "codex"
    assert decision["next_action"] == "fix_and_retry"
    assert decision["next_instruction_kind"] == "code_fix"
    assert decision["next_instruction_draft_required"] is True
    assert decision["next_instruction_draft"]
    assert decision["requires_human_decision"] is False
    assert decision["human_decision_reason"] is None
    assert decision["rule_codes"] == ["failure_execution_codex_fix_and_retry"]
    assert all(flag_value is False for flag_value in decision["safety_flags"].values())

    return decision


def _assert_p5e_response_decision_payload(
    *,
    response_payload: dict,
    failure_category: RunFailureCategory,
    reason_code: TaskBlockingReasonCode | None,
    expected_owner: str,
    expected_action: str,
    expected_instruction_kind: str,
    expected_recoverable: bool,
    expected_retry_allowed: bool,
    expected_draft_required: bool,
    expected_requires_human: bool,
) -> dict:
    """Assert P5-E exposes only a read-only recovery decision DTO."""

    owner_labels = {
        "codex": "Codex 修复",
        "deepseek": "DeepSeek 配置修复",
        "user": "用户决策",
        "blocked": "阻塞等待",
    }
    action_labels = {
        "retry": "重试",
        "fix_and_retry": "修复后重试",
        "pause_and_wait": "暂停等待",
        "replan": "重新规划",
        "escalate_to_human": "升级人工决策",
        "block_permanently": "永久阻塞",
        "archive": "归档",
    }
    instruction_kind_labels = {
        "code_fix": "代码修复",
        "test_fix": "测试修复",
        "config_fix": "配置修复",
        "evidence_fix": "证据修复",
        "replay": "重新执行",
        "pause": "暂停等待",
        "replan": "重新规划",
        "human_question": "人工问题",
    }

    assert "failure_recovery_reason_code" not in response_payload

    decision = response_payload["failure_recovery_decision"]
    assert decision["source"] == P5_FAILURE_RECOVERY_DECISION_SOURCE
    assert decision["version"] == P5_FAILURE_RECOVERY_DECISION_VERSION
    assert decision["audit_event_type"] == (
        P5_FAILURE_RECOVERY_DECISION_AUDIT_EVENT_TYPE
    )
    assert decision["failure_category"] == failure_category.value
    assert decision["reason_code"] == (
        reason_code.value if reason_code is not None else None
    )
    assert decision["recoverable"] is expected_recoverable
    assert decision["retry_allowed"] is expected_retry_allowed
    assert decision["recommended_owner"] == expected_owner
    assert decision["recommended_owner_label_cn"] == owner_labels[expected_owner]
    assert decision["next_action"] == expected_action
    assert decision["next_action_label_cn"] == action_labels[expected_action]
    assert decision["next_instruction_kind"] == expected_instruction_kind
    assert decision["next_instruction_kind_label_cn"] == (
        instruction_kind_labels[expected_instruction_kind]
    )
    assert decision["next_instruction_draft_required"] is expected_draft_required
    assert bool(decision["next_instruction_draft"]) is expected_draft_required
    assert decision["requires_human_decision"] is expected_requires_human
    assert decision["user_visible_summary_cn"]
    assert isinstance(decision["rule_codes"], list)
    assert "safety_flags" not in decision
    assert decision["safety"]["api_response_exposed"] is True
    assert decision["safety"]["runs_git"] is False
    assert decision["safety"]["runs_write_git"] is False
    assert decision["safety"]["git_add_triggered"] is False
    assert decision["safety"]["git_commit_triggered"] is False
    assert decision["safety"]["git_push_triggered"] is False
    assert decision["safety"]["pr_opened"] is False
    assert decision["safety"]["worker_dispatch_triggered"] is False
    assert decision["safety"]["agent_message_written"] is False
    assert decision["safety"]["task_created"] is False
    assert decision["safety"]["retry_triggered"] is False
    assert all(
        flag_value is False
        for flag_name, flag_value in decision["safety"].items()
        if flag_name != "api_response_exposed"
    )

    return decision


def _assert_worker_result_decision(
    *,
    failure_category: RunFailureCategory,
    reason_code: TaskBlockingReasonCode | None = None,
    expected_owner: str,
    expected_action: str,
    expected_instruction_kind: str,
    expected_recoverable: bool,
    expected_retry_allowed: bool,
    expected_draft_required: bool,
    expected_requires_human: bool,
) -> None:
    result = WorkerRunResult(
        claimed=True,
        message="internal failed worker result",
        failure_category=failure_category,
        failure_recovery_reason_code=reason_code,
        quality_gate_passed=False,
    )

    assert result.failure_recovery_decision is not None
    decision = result.failure_recovery_decision
    assert decision.source == P5_FAILURE_RECOVERY_DECISION_SOURCE
    assert decision.version == P5_FAILURE_RECOVERY_DECISION_VERSION
    assert decision.audit_event_type == P5_FAILURE_RECOVERY_DECISION_AUDIT_EVENT_TYPE
    assert decision.failure_category == failure_category
    assert decision.reason_code == reason_code
    assert decision.recommended_owner.value == expected_owner
    assert decision.next_action.value == expected_action
    assert decision.next_instruction_kind.value == expected_instruction_kind
    assert decision.recoverable is expected_recoverable
    assert decision.retry_allowed is expected_retry_allowed
    assert decision.next_instruction_draft_required is expected_draft_required
    assert decision.requires_human_decision is expected_requires_human
    assert all(
        flag_value is False
        for flag_value in decision.safety_flags.model_dump().values()
    )
    assert decision.safety_flags.api_response_exposed is False

    response_payload = WorkerRunOnceResponse.from_result(result).model_dump(mode="json")
    _assert_p5e_response_decision_payload(
        response_payload=response_payload,
        failure_category=failure_category,
        reason_code=reason_code,
        expected_owner=expected_owner,
        expected_action=expected_action,
        expected_instruction_kind=expected_instruction_kind,
        expected_recoverable=expected_recoverable,
        expected_retry_allowed=expected_retry_allowed,
        expected_draft_required=expected_draft_required,
        expected_requires_human=expected_requires_human,
    )


def test_worker_result_without_failure_category_has_no_recovery_decision():
    result = WorkerRunResult(
        claimed=True,
        message="successful worker result",
        failure_category=None,
        quality_gate_passed=True,
    )

    assert result.failure_recovery_decision is None
    response_payload = WorkerRunOnceResponse.from_result(result).model_dump(mode="json")
    assert response_payload["failure_recovery_decision"] is None
    assert "failure_recovery_reason_code" not in response_payload


def test_worker_result_preserves_explicit_recovery_decision():
    explicit_result = WorkerRunResult(
        claimed=True,
        message="explicit failed worker result",
        failure_category=RunFailureCategory.VERIFICATION_FAILED,
        quality_gate_passed=False,
    )
    assert explicit_result.failure_recovery_decision is not None

    result = WorkerRunResult(
        claimed=True,
        message="reused failed worker result",
        failure_category=RunFailureCategory.VERIFICATION_FAILED,
        quality_gate_passed=False,
        failure_recovery_decision=explicit_result.failure_recovery_decision,
    )

    assert result.failure_recovery_decision is explicit_result.failure_recovery_decision


def test_worker_result_carries_execution_failure_recovery_decision():
    _assert_worker_result_decision(
        failure_category=RunFailureCategory.EXECUTION_FAILED,
        expected_owner="codex",
        expected_action="fix_and_retry",
        expected_instruction_kind="code_fix",
        expected_recoverable=True,
        expected_retry_allowed=True,
        expected_draft_required=True,
        expected_requires_human=False,
    )


def test_worker_result_carries_verification_failure_recovery_decision():
    _assert_worker_result_decision(
        failure_category=RunFailureCategory.VERIFICATION_FAILED,
        expected_owner="codex",
        expected_action="fix_and_retry",
        expected_instruction_kind="test_fix",
        expected_recoverable=True,
        expected_retry_allowed=True,
        expected_draft_required=True,
        expected_requires_human=False,
    )


def test_worker_result_carries_verification_config_recovery_decision():
    _assert_worker_result_decision(
        failure_category=RunFailureCategory.VERIFICATION_CONFIGURATION_FAILED,
        expected_owner="deepseek",
        expected_action="fix_and_retry",
        expected_instruction_kind="config_fix",
        expected_recoverable=True,
        expected_retry_allowed=False,
        expected_draft_required=True,
        expected_requires_human=False,
    )


def test_worker_result_carries_daily_budget_recovery_decision():
    _assert_worker_result_decision(
        failure_category=RunFailureCategory.DAILY_BUDGET_EXCEEDED,
        expected_owner="user",
        expected_action="escalate_to_human",
        expected_instruction_kind="human_question",
        expected_recoverable=False,
        expected_retry_allowed=False,
        expected_draft_required=False,
        expected_requires_human=True,
    )


def test_worker_result_carries_session_budget_recovery_decision():
    _assert_worker_result_decision(
        failure_category=RunFailureCategory.SESSION_BUDGET_EXCEEDED,
        expected_owner="user",
        expected_action="escalate_to_human",
        expected_instruction_kind="human_question",
        expected_recoverable=False,
        expected_retry_allowed=False,
        expected_draft_required=False,
        expected_requires_human=True,
    )


def test_worker_result_carries_retry_limit_recovery_decision():
    _assert_worker_result_decision(
        failure_category=RunFailureCategory.RETRY_LIMIT_EXCEEDED,
        expected_owner="user",
        expected_action="escalate_to_human",
        expected_instruction_kind="human_question",
        expected_recoverable=False,
        expected_retry_allowed=False,
        expected_draft_required=False,
        expected_requires_human=True,
    )


def test_worker_result_routes_dependency_missing_reason_to_blocked_pause_decision():
    _assert_worker_result_decision(
        failure_category=RunFailureCategory.EXECUTION_FAILED,
        reason_code=TaskBlockingReasonCode.DEPENDENCY_MISSING,
        expected_owner="blocked",
        expected_action="pause_and_wait",
        expected_instruction_kind="pause",
        expected_recoverable=False,
        expected_retry_allowed=False,
        expected_draft_required=False,
        expected_requires_human=False,
    )


def test_failure_review_persists_internal_recovery_decision_payload(tmp_path):
    original_runtime_data_dir = settings.runtime_data_dir
    object.__setattr__(settings, "runtime_data_dir", tmp_path)
    try:
        task = Task(
            title="P5-C failed run",
            input_summary="simulate: failed worker recovery decision",
            status=TaskStatus.FAILED,
        )
        run = Run(
            task_id=task.id,
            status=RunStatus.FAILED,
            result_summary="Execution failed during worker run.",
            failure_category=RunFailureCategory.EXECUTION_FAILED,
            quality_gate_passed=False,
        )
        repository = FailureReviewRepository()
        service = FailureReviewService(
            failure_review_repository=repository,
            run_logging_service=RunLoggingService(),
        )

        review = service.ensure_review(task=task, run=run)
        payload = repository.get(run_id=run.id)
        api_facing_review = service.get_review(run_id=run.id)
    finally:
        object.__setattr__(settings, "runtime_data_dir", original_runtime_data_dir)

    assert review is not None
    assert payload is not None
    decision = _assert_p5c_internal_decision_payload(payload)
    assert api_facing_review is not None
    assert not hasattr(api_facing_review, P5C_FAILURE_RECOVERY_DECISION_PAYLOAD_KEY)
    assert "api_response_exposed" in decision["safety_flags"]
    assert decision["safety_flags"]["api_response_exposed"] is False
    assert decision["safety_flags"]["agent_message_written"] is False
    assert decision["safety_flags"]["retry_triggered"] is False


def test_worker_failed_run_generates_internal_recovery_decision_payload(tmp_path):
    original_runtime_data_dir = settings.runtime_data_dir
    original_simulate_override = settings.worker_simulate_execution_override
    original_simulate_failure_mode = settings.worker_simulate_failure_mode
    original_daily_budget = settings.daily_budget_usd
    original_session_budget = settings.session_budget_usd
    original_max_task_retries = settings.max_task_retries

    object.__setattr__(settings, "runtime_data_dir", tmp_path / "runtime-data")
    object.__setattr__(settings, "worker_simulate_execution_override", True)
    object.__setattr__(settings, "worker_simulate_failure_mode", "failed")
    object.__setattr__(settings, "daily_budget_usd", 100.0)
    object.__setattr__(settings, "session_budget_usd", 100.0)
    object.__setattr__(settings, "max_task_retries", 3)

    db_path = tmp_path / "orchestrator-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    session = session_factory()
    try:
        task = TaskRepository(session).create(
            Task(
                title="P5-C worker failed run",
                input_summary="created through API only",
            )
        )
        worker = build_task_worker(session=session)

        result = worker.run_once()
        run_id = result.run.id if result.run is not None else None
        assert isinstance(run_id, UUID)

        payload = FailureReviewRepository().get(run_id=run_id)
        persisted_task = TaskRepository(session).get_by_id(task.id)
    finally:
        session.close()
        object.__setattr__(settings, "runtime_data_dir", original_runtime_data_dir)
        object.__setattr__(
            settings,
            "worker_simulate_execution_override",
            original_simulate_override,
        )
        object.__setattr__(
            settings,
            "worker_simulate_failure_mode",
            original_simulate_failure_mode,
        )
        object.__setattr__(settings, "daily_budget_usd", original_daily_budget)
        object.__setattr__(settings, "session_budget_usd", original_session_budget)
        object.__setattr__(settings, "max_task_retries", original_max_task_retries)

    assert result.claimed is True
    assert result.run is not None
    assert result.run.status == RunStatus.FAILED
    assert result.failure_category == RunFailureCategory.EXECUTION_FAILED
    assert result.quality_gate_passed is False
    assert result.message.startswith("Worker execution failed via simulate.")
    assert persisted_task is not None
    assert persisted_task.status == TaskStatus.FAILED
    assert payload is not None
    _assert_p5c_internal_decision_payload(payload)


def test_worker_failed_run_records_recovery_decision_agent_timeline(tmp_path):
    original_runtime_data_dir = settings.runtime_data_dir
    original_simulate_override = settings.worker_simulate_execution_override
    original_simulate_failure_mode = settings.worker_simulate_failure_mode
    original_daily_budget = settings.daily_budget_usd
    original_session_budget = settings.session_budget_usd
    original_max_task_retries = settings.max_task_retries

    object.__setattr__(settings, "runtime_data_dir", tmp_path / "runtime-data")
    object.__setattr__(settings, "worker_simulate_execution_override", True)
    object.__setattr__(settings, "worker_simulate_failure_mode", "failed")
    object.__setattr__(settings, "daily_budget_usd", 100.0)
    object.__setattr__(settings, "session_budget_usd", 100.0)
    object.__setattr__(settings, "max_task_retries", 3)

    db_path = tmp_path / "orchestrator-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    session = session_factory()
    try:
        project = ProjectRepository(session).create(
            Project(
                name="P5-D project",
                summary="Project-bound worker run creates an AgentSession timeline.",
            )
        )
        task = TaskRepository(session).create(
            Task(
                project_id=project.id,
                title="P5-D worker failed run",
                input_summary="simulate: failed worker recovery audit",
            )
        )
        worker = build_task_worker(session=session)

        result = worker.run_once()
        assert result.run is not None
        assert result.agent_session_id is not None
        assert result.failure_recovery_decision is not None

        agent_session = AgentSessionRepository(session).get_by_id(
            result.agent_session_id
        )
        assert agent_session is not None
        audit_service = FailureRecoveryAuditService(
            agent_message_repository=AgentMessageRepository(session)
        )
        first_message = audit_service.record_decision(
            session=agent_session,
            decision=result.failure_recovery_decision,
            run_status=result.run.status,
            task_status=result.task.status if result.task is not None else None,
            result_summary=result.run.result_summary,
        )
        second_message = audit_service.record_decision(
            session=agent_session,
            decision=result.failure_recovery_decision,
            run_status=result.run.status,
            task_status=result.task.status if result.task is not None else None,
            result_summary=result.run.result_summary,
        )

        messages = AgentMessageRepository(session).list_by_project_id(
            project_id=project.id,
            message_types=[AgentMessageType.TIMELINE],
        )
        recovery_messages = [
            message
            for message in messages
            if message.event_type == P5_FAILURE_RECOVERY_DECISION_AUDIT_EVENT_TYPE
        ]
        dispatch_messages = [
            message
            for message in messages
            if message.event_type == P6_AGENT_DISPATCH_DECISION_AUDIT_EVENT_TYPE
        ]
        response_payload = WorkerRunOnceResponse.from_result(result).model_dump(
            mode="json"
        )
    finally:
        session.close()
        object.__setattr__(settings, "runtime_data_dir", original_runtime_data_dir)
        object.__setattr__(
            settings,
            "worker_simulate_execution_override",
            original_simulate_override,
        )
        object.__setattr__(
            settings,
            "worker_simulate_failure_mode",
            original_simulate_failure_mode,
        )
        object.__setattr__(settings, "daily_budget_usd", original_daily_budget)
        object.__setattr__(settings, "session_budget_usd", original_session_budget)
        object.__setattr__(settings, "max_task_retries", original_max_task_retries)

    assert result.claimed is True
    assert result.run.status == RunStatus.CANCELLED
    assert result.failure_recovery_decision is not None
    assert len(recovery_messages) == 1
    assert len(dispatch_messages) == 1
    assert first_message.id == recovery_messages[0].id
    assert second_message.id == recovery_messages[0].id

    message = recovery_messages[0]
    assert message.message_type == AgentMessageType.TIMELINE
    assert message.role == "system"
    assert message.run_id == result.run.id
    assert message.task_id == task.id
    assert message.session_id == result.agent_session_id
    assert "P5 失败回流建议" in message.content_summary
    assert "系统已准备下一步修复指令草案" in message.content_summary
    assert "暂不需要用户决策" in message.content_summary
    assert "owner=" not in message.content_summary
    assert "action=" not in message.content_summary
    assert "draft_required=" not in message.content_summary
    assert "codex" not in message.content_summary
    assert "fix_and_retry" not in message.content_summary

    assert message.content_detail is not None
    detail = json.loads(message.content_detail)
    assert detail["p5_stage"] == "P5-D"
    assert detail["run_status"] == "cancelled"
    assert detail["task_status"] == "blocked"
    assert detail["decision"]["audit_event_type"] == (
        P5_FAILURE_RECOVERY_DECISION_AUDIT_EVENT_TYPE
    )
    assert detail["decision"]["recommended_owner"] == "codex"
    assert detail["decision"]["next_action"] == "fix_and_retry"
    assert detail["decision"]["next_instruction_draft_required"] is True
    assert detail["decision"]["safety_flags"]["agent_message_written"] is False
    assert detail["p5_d_safety"]["api_response_exposed"] is False
    assert detail["p5_d_safety"]["retry_triggered"] is False
    assert detail["p5_d_safety"]["worker_dispatch_triggered"] is False
    assert detail["p5_d_safety"]["task_created"] is False
    assert detail["p5_d_safety"]["runs_git"] is False
    assert detail["p5_d_safety"]["runs_write_git"] is False
    assert detail["p5_d_safety"]["git_add_triggered"] is False
    assert detail["p5_d_safety"]["git_commit_triggered"] is False
    assert detail["p5_d_safety"]["git_push_triggered"] is False
    assert detail["p5_d_safety"]["pr_opened"] is False

    dispatch_message = dispatch_messages[0]
    assert dispatch_message.message_type == AgentMessageType.TIMELINE
    assert dispatch_message.role == "system"
    assert dispatch_message.run_id == result.run.id
    assert dispatch_message.task_id == task.id
    assert dispatch_message.session_id == result.agent_session_id
    assert dispatch_message.state_from == "cancelled"
    assert dispatch_message.state_to == "suggested"
    assert "P6 调度建议" in dispatch_message.content_summary
    assert "Codex 继续处理" in dispatch_message.content_summary
    assert "不会自动派发、重试或创建任务" in dispatch_message.content_summary
    assert "p5_owner_codex" not in dispatch_message.content_summary
    assert "suggested" not in dispatch_message.content_summary

    assert dispatch_message.content_detail is not None
    dispatch_detail = json.loads(dispatch_message.content_detail)
    assert dispatch_detail["p6_stage"] == "P6-D"
    assert dispatch_detail["run_status"] == "cancelled"
    assert dispatch_detail["task_status"] == "blocked"
    assert dispatch_detail["decision"]["audit_event_type"] == (
        P6_AGENT_DISPATCH_DECISION_AUDIT_EVENT_TYPE
    )
    assert dispatch_detail["decision"]["recommended_agent"] == "codex"
    assert dispatch_detail["decision"]["dispatch_status"] == "suggested"
    assert dispatch_detail["decision"]["instruction_kind"] == "code_fix"
    assert dispatch_detail["decision"]["instruction_draft"] is not None
    assert dispatch_detail["decision"]["safety_flags"]["agent_message_written"] is False
    assert dispatch_detail["decision"]["safety_flags"]["worker_dispatch_triggered"] is False
    assert dispatch_detail["decision"]["safety_flags"]["retry_triggered"] is False
    assert dispatch_detail["decision"]["safety_flags"]["auto_dispatch_triggered"] is False
    assert dispatch_detail["p6_d_audit"]["agent_message_recorded"] is True
    assert dispatch_detail["p6_d_audit"]["api_response_exposed"] is False
    assert dispatch_detail["p6_d_audit"]["retry_triggered"] is False
    assert dispatch_detail["p6_d_audit"]["worker_dispatch_triggered"] is False
    assert dispatch_detail["p6_d_audit"]["task_created"] is False
    assert dispatch_detail["p6_d_audit"]["auto_dispatch_triggered"] is False
    assert dispatch_detail["p6_d_audit"]["runs_git"] is False
    assert dispatch_detail["p6_d_audit"]["runs_write_git"] is False
    assert dispatch_detail["p6_d_audit"]["git_add_triggered"] is False
    assert dispatch_detail["p6_d_audit"]["git_commit_triggered"] is False
    assert dispatch_detail["p6_d_audit"]["git_push_triggered"] is False
    assert dispatch_detail["p6_d_audit"]["pr_opened"] is False

    _assert_p5e_response_decision_payload(
        response_payload=response_payload,
        failure_category=RunFailureCategory.EXECUTION_FAILED,
        reason_code=None,
        expected_owner="codex",
        expected_action="fix_and_retry",
        expected_instruction_kind="code_fix",
        expected_recoverable=True,
        expected_retry_allowed=True,
        expected_draft_required=True,
        expected_requires_human=False,
    )
    assert "failure_recovery_reason_code" not in response_payload
    assert "agent_dispatch_decision" not in response_payload
    assert "dispatch_decision" not in response_payload


def test_worker_recovery_audit_helper_skips_empty_session_or_decision():
    class _CountingFailureRecoveryAuditService:
        def __init__(self) -> None:
            self.call_count = 0

        def record_decision(self, **kwargs):
            self.call_count += 1
            raise AssertionError("audit service must not be called for skipped paths")

    class _CountingAgentDispatchAuditService:
        def __init__(self) -> None:
            self.call_count = 0

        def record_decision(self, **kwargs):
            self.call_count += 1
            raise AssertionError(
                "dispatch audit service must not be called for skipped paths"
            )

    class _NoopDbSession:
        def commit(self) -> None:
            raise AssertionError("commit must not be called for skipped paths")

        def rollback(self) -> None:
            raise AssertionError("rollback must not be called for skipped paths")

    recovery_audit_service = _CountingFailureRecoveryAuditService()
    dispatch_audit_service = _CountingAgentDispatchAuditService()
    worker = type(
        "_Worker",
        (),
        {
            "failure_recovery_audit_service": recovery_audit_service,
            "agent_dispatch_audit_service": dispatch_audit_service,
            "session": _NoopDbSession(),
        },
    )()

    failed_run = Run(
        task_id=Task(title="P5-D helper task", input_summary="skip audit").id,
        status=RunStatus.FAILED,
        failure_category=RunFailureCategory.EXECUTION_FAILED,
        quality_gate_passed=False,
    )
    decision_result = WorkerRunResult(
        claimed=True,
        message="failed result with decision",
        failure_category=RunFailureCategory.EXECUTION_FAILED,
        quality_gate_passed=False,
        run=failed_run,
    )
    no_decision_result = WorkerRunResult(
        claimed=True,
        message="failed result without decision",
        failure_category=None,
        quality_gate_passed=False,
        run=failed_run,
    )

    assert decision_result.failure_recovery_decision is not None
    assert no_decision_result.failure_recovery_decision is None

    TaskWorker._record_failure_recovery_audit_if_needed(
        worker,
        agent_session=None,
        result=decision_result,
    )
    TaskWorker._record_failure_recovery_audit_if_needed(
        worker,
        agent_session=object(),
        result=no_decision_result,
    )

    assert recovery_audit_service.call_count == 0
    assert dispatch_audit_service.call_count == 0


def test_worker_dispatch_audit_helper_does_not_require_p5_audit_service():
    class _CountingAgentDispatchAuditService:
        def __init__(self) -> None:
            self.call_count = 0
            self.last_kwargs = None

        def record_decision(self, **kwargs):
            self.call_count += 1
            self.last_kwargs = kwargs

    class _CountingDbSession:
        def __init__(self) -> None:
            self.commit_count = 0
            self.rollback_count = 0

        def commit(self) -> None:
            self.commit_count += 1

        def rollback(self) -> None:
            self.rollback_count += 1

    task = Task(title="P6-D helper task", input_summary="dispatch audit")
    failed_run = Run(
        task_id=task.id,
        status=RunStatus.FAILED,
        failure_category=RunFailureCategory.EXECUTION_FAILED,
        quality_gate_passed=False,
        result_summary="Failed run needs dispatch audit.",
    )
    result = WorkerRunResult(
        claimed=True,
        message="failed result with P6-D dispatch audit",
        failure_category=RunFailureCategory.EXECUTION_FAILED,
        quality_gate_passed=False,
        task=task,
        run=failed_run,
    )
    dispatch_audit_service = _CountingAgentDispatchAuditService()
    db_session = _CountingDbSession()
    worker = type(
        "_Worker",
        (),
        {
            "failure_recovery_audit_service": None,
            "agent_dispatch_audit_service": dispatch_audit_service,
            "session": db_session,
        },
    )()
    agent_session = object()

    TaskWorker._record_failure_recovery_audit_if_needed(
        worker,
        agent_session=agent_session,
        result=result,
    )

    assert result.failure_recovery_decision is not None
    assert dispatch_audit_service.call_count == 1
    assert dispatch_audit_service.last_kwargs is not None
    assert dispatch_audit_service.last_kwargs["session"] is agent_session
    assert dispatch_audit_service.last_kwargs["run_status"] == RunStatus.FAILED
    assert dispatch_audit_service.last_kwargs["task_status"] == TaskStatus.PENDING
    assert dispatch_audit_service.last_kwargs["result_summary"] == (
        "Failed run needs dispatch audit."
    )
    decision = dispatch_audit_service.last_kwargs["decision"]
    assert decision.recommended_agent == "codex"
    assert decision.dispatch_status == "suggested"
    assert decision.source_run_id == failed_run.id
    assert decision.source_task_id == task.id
    assert decision.safety_flags.worker_dispatch_triggered is False
    assert decision.safety_flags.retry_triggered is False
    assert decision.safety_flags.auto_dispatch_triggered is False
    assert db_session.commit_count == 1
    assert db_session.rollback_count == 0
