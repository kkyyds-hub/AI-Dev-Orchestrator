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
    DELIVERY_EVIDENCE_SNAPSHOT_SOURCE_EVENT,
    DELIVERY_EVIDENCE_SNAPSHOT_SOURCE_RUN_LOG_JSONL,
    DELIVERY_EVIDENCE_SNAPSHOT_SOURCE_SCHEMA_VERSION,
    RunLoggingService,
)


def test_run_logging_service_writes_delivery_evidence_snapshot_source_event(
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
        service.append_delivery_evidence_snapshot_source_event(
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
    assert event.event == DELIVERY_EVIDENCE_SNAPSHOT_SOURCE_EVENT
    assert event.level == "info"
    assert event.message == (
        "Run log JSONL is the source for delivery human approval evidence snapshots."
    )
    assert event.data["schema_version"] == (
        DELIVERY_EVIDENCE_SNAPSHOT_SOURCE_SCHEMA_VERSION
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
