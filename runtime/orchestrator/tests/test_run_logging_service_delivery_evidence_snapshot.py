"""Targeted tests for P4-F2-C0 delivery evidence snapshot source run logs."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.domain.agent_session import AgentSession, WorkspaceType
from app.domain.delivery_gate_evidence import (
    DELIVERY_AUDIT_COLLECTED_EVENT_TYPE,
    DeliveryGateEvidenceBuilder,
)
from app.domain.git_operation_dry_run import GitOperationDryRunBuilder
from app.services.git_diff_dry_run_runner import GitDiffDryRunResult
from app.services.run_logging_service import (
    DELIVERY_EVIDENCE_SNAPSHOT_EVENT,
    DELIVERY_EVIDENCE_SNAPSHOT_MESSAGE,
    DELIVERY_EVIDENCE_SNAPSHOT_SOURCE_RUN_LOG_JSONL,
    DELIVERY_EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
    RunLoggingService,
)


def test_delivery_evidence_snapshot_contract_constants_are_stable():
    assert DELIVERY_EVIDENCE_SNAPSHOT_EVENT == "delivery_evidence_snapshot"
    assert DELIVERY_EVIDENCE_SNAPSHOT_SCHEMA_VERSION == "p4f2c0.v1"
    assert DELIVERY_EVIDENCE_SNAPSHOT_MESSAGE == (
        "已记录交付审批证据快照来源：运行日志 JSONL。"
    )


def test_run_logging_service_writes_delivery_evidence_snapshot(
    tmp_path,
):
    original_runtime_data_dir = settings.runtime_data_dir
    object.__setattr__(settings, "runtime_data_dir", tmp_path)
    try:
        service = RunLoggingService()
        task_id = uuid4()
        run_id = uuid4()
        session = AgentSession(
            id=uuid4(),
            project_id=uuid4(),
            task_id=task_id,
            run_id=run_id,
            branch_name="main",
            workspace_type=WorkspaceType.WORKTREE,
            workspace_path=tmp_path.as_posix(),
            workspace_clean=True,
        )
        diff = GitDiffDryRunResult(
            ready=True,
            source="agent_session_worktree_diff",
            reason_code=None,
            worktree_path=tmp_path.as_posix(),
            has_changes=True,
            changed_files_count=1,
            changed_files=["README.md"],
            modified_files=["README.md"],
            status_summary_cn="1 个文件修改",
            branch_name="main",
            runs_git=True,
        )
        operation = GitOperationDryRunBuilder.build_from_diff_evidence(
            agent_session=session,
            diff_evidence=diff,
        )
        delivery_gate = DeliveryGateEvidenceBuilder.evaluate(
            agent_session=session,
            diff_evidence=diff,
            operation_dry_run=operation,
            delivery_audit_event_present=True,
            delivery_audit_event_type=DELIVERY_AUDIT_COLLECTED_EVENT_TYPE,
            delivery_audit_event_ready=True,
            delivery_git_write_enabled=False,
        )

        log_path = service.initialize_run_log(task_id=task_id, run_id=run_id)
        service.append_delivery_evidence_snapshot(
            log_path=log_path,
            run_id=run_id,
            operation_dry_run=operation,
            delivery_gate_evidence=delivery_gate,
        )

        read_result = service.read_events(log_path=log_path)
    finally:
        object.__setattr__(settings, "runtime_data_dir", original_runtime_data_dir)

    assert (Path(tmp_path) / log_path).exists()
    assert len(read_result.events) == 1
    event = read_result.events[0]
    assert event.event == DELIVERY_EVIDENCE_SNAPSHOT_EVENT
    assert event.level == "info"
    assert event.message == DELIVERY_EVIDENCE_SNAPSHOT_MESSAGE
    assert event.data["schema_version"] == (
        DELIVERY_EVIDENCE_SNAPSHOT_SCHEMA_VERSION
    )
    assert event.data["snapshot_source"] == DELIVERY_EVIDENCE_SNAPSHOT_SOURCE_RUN_LOG_JSONL
    assert event.data["purpose"] == "delivery_human_approval_evidence_source"
    assert event.data["run_id"] == str(run_id)
    assert event.data["operation_dry_run_available"] is True
    assert event.data["operation_dry_run_ready"] is True
    assert event.data["delivery_gate_evidence_available"] is True
    assert event.data["delivery_gate_evidence_ready"] is True
    assert event.data["human_approval_evaluated"] is False
    assert event.data["approval_record_created"] is False
    assert event.data["runs_write_git"] is False
    assert event.data["git_add_triggered"] is False
    assert event.data["git_commit_triggered"] is False
    assert event.data["git_push_triggered"] is False
    assert event.data["pr_opened"] is False
    assert event.data["ci_triggered"] is False
    assert event.data["gate_allows_write"] is False
    assert event.data["operation_dry_run"]["source"] == "git_operation_dry_run"
    assert event.data["operation_dry_run"]["ready"] is True
    assert event.data["operation_dry_run"]["changed_files"] == ["README.md"]
    assert event.data["operation_dry_run"]["safety_flags"]["git_commit_triggered"] is False
    assert event.data["delivery_gate_evidence"]["source"] == "delivery_gate_evidence"
    assert event.data["delivery_gate_evidence"]["ready"] is True
    assert event.data["delivery_gate_evidence"]["changed_files"] == ["README.md"]
    assert event.data["delivery_gate_evidence"]["safety_flags"]["gate_allows_write"] is False


def test_run_logging_service_reads_latest_delivery_evidence_snapshot(
    tmp_path,
):
    original_runtime_data_dir = settings.runtime_data_dir
    object.__setattr__(settings, "runtime_data_dir", tmp_path)
    try:
        service = RunLoggingService()
        task_id = uuid4()
        run_id = uuid4()
        session = AgentSession(
            id=uuid4(),
            project_id=uuid4(),
            task_id=task_id,
            run_id=run_id,
            branch_name="main",
            workspace_type=WorkspaceType.WORKTREE,
            workspace_path=tmp_path.as_posix(),
            workspace_clean=True,
        )
        first_diff = GitDiffDryRunResult(
            ready=True,
            source="agent_session_worktree_diff",
            reason_code=None,
            worktree_path=tmp_path.as_posix(),
            has_changes=True,
            changed_files_count=1,
            changed_files=["README.md"],
            modified_files=["README.md"],
            status_summary_cn="1 个文件修改",
            branch_name="main",
            runs_git=True,
        )
        latest_diff = GitDiffDryRunResult(
            ready=True,
            source="agent_session_worktree_diff",
            reason_code=None,
            worktree_path=tmp_path.as_posix(),
            has_changes=True,
            changed_files_count=2,
            changed_files=["README.md", "src/app.py"],
            added_files=["src/app.py"],
            modified_files=["README.md"],
            status_summary_cn="1 个文件修改，1 个文件新增",
            branch_name="main",
            runs_git=True,
        )
        first_operation = GitOperationDryRunBuilder.build_from_diff_evidence(
            agent_session=session,
            diff_evidence=first_diff,
        )
        latest_operation = GitOperationDryRunBuilder.build_from_diff_evidence(
            agent_session=session,
            diff_evidence=latest_diff,
        )
        first_delivery_gate = DeliveryGateEvidenceBuilder.evaluate(
            agent_session=session,
            diff_evidence=first_diff,
            operation_dry_run=first_operation,
            delivery_audit_event_present=True,
            delivery_audit_event_type=DELIVERY_AUDIT_COLLECTED_EVENT_TYPE,
            delivery_audit_event_ready=True,
            delivery_git_write_enabled=False,
        )
        latest_delivery_gate = DeliveryGateEvidenceBuilder.evaluate(
            agent_session=session,
            diff_evidence=latest_diff,
            operation_dry_run=latest_operation,
            delivery_audit_event_present=True,
            delivery_audit_event_type=DELIVERY_AUDIT_COLLECTED_EVENT_TYPE,
            delivery_audit_event_ready=True,
            delivery_git_write_enabled=False,
        )

        log_path = service.initialize_run_log(task_id=task_id, run_id=run_id)
        service.append_delivery_evidence_snapshot(
            log_path=log_path,
            run_id=run_id,
            operation_dry_run=first_operation,
            delivery_gate_evidence=first_delivery_gate,
        )
        service.append_event(
            log_path=log_path,
            event="execution_finished",
            message="Non-snapshot log event should be ignored.",
            data={"success": True},
        )
        service.append_delivery_evidence_snapshot(
            log_path=log_path,
            run_id=run_id,
            operation_dry_run=latest_operation,
            delivery_gate_evidence=latest_delivery_gate,
        )

        latest_snapshot = service.read_latest_delivery_evidence_snapshot(
            log_path=log_path
        )
        missing_snapshot = service.read_latest_delivery_evidence_snapshot(
            log_path="logs/task-runs/missing/missing.jsonl"
        )
        none_snapshot = service.read_latest_delivery_evidence_snapshot(log_path=None)
    finally:
        object.__setattr__(settings, "runtime_data_dir", original_runtime_data_dir)

    assert latest_snapshot is not None
    assert latest_snapshot.event == DELIVERY_EVIDENCE_SNAPSHOT_EVENT
    assert latest_snapshot.data["schema_version"] == (
        DELIVERY_EVIDENCE_SNAPSHOT_SCHEMA_VERSION
    )
    assert latest_snapshot.data["snapshot_source"] == (
        DELIVERY_EVIDENCE_SNAPSHOT_SOURCE_RUN_LOG_JSONL
    )
    assert latest_snapshot.data["operation_dry_run_ready"] is True
    assert latest_snapshot.data["delivery_gate_evidence_ready"] is True
    assert latest_snapshot.data["human_approval_evaluated"] is False
    assert latest_snapshot.data["approval_record_created"] is False
    assert latest_snapshot.data["git_commit_triggered"] is False
    assert latest_snapshot.data["gate_allows_write"] is False
    assert latest_snapshot.data["operation_dry_run"]["changed_files_count"] == 2
    assert latest_snapshot.data["operation_dry_run"]["changed_files"] == [
        "README.md",
        "src/app.py",
    ]
    assert latest_snapshot.data["delivery_gate_evidence"]["changed_files"] == [
        "README.md",
        "src/app.py",
    ]
    assert latest_snapshot.data["delivery_gate_evidence"]["safety_flags"][
        "gate_allows_user_confirmation"
    ] is True
    assert latest_snapshot.data["delivery_gate_evidence"]["safety_flags"][
        "gate_allows_write"
    ] is False
    assert missing_snapshot is None
    assert none_snapshot is None
