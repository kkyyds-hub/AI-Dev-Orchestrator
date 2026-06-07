"""Worker endpoints."""

from datetime import datetime
from typing import Annotated, ClassVar
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain.failure_recovery_decision import FailureRecoveryDecision
from app.domain.project_role import ProjectRoleCode
from app.domain.run import (
    RunBudgetPressureLevel,
    RunBudgetStrategyAction,
    RunFailureCategory,
    RunRoutingScoreItem,
    RunStatus,
)
from app.domain.task import TaskStatus
from app.services.worker_slot_service import WorkerSlotSnapshot, WorkerSlotState, WorkerSlotStatus
from app.workers.task_worker import TaskWorker, WorkerRunResult, build_task_worker
from app.workers.worker_pool import WorkerPoolRunResult, worker_pool


class WorkerRunOnceResponse(BaseModel):
    """API response for one explicit worker cycle."""

    class RoutingScoreItemResponse(BaseModel):
        """One routing-score component returned to the caller."""

        code: str
        label: str
        score: float
        detail: str

        @classmethod
        def from_item(
            cls,
            item: RunRoutingScoreItem,
        ) -> "WorkerRunOnceResponse.RoutingScoreItemResponse":
            """Convert one domain routing-score item into an API DTO."""

            return cls(
                code=item.code,
                label=item.label,
                score=item.score,
                detail=item.detail,
            )

    class RuntimeLifecycleSnapshotResponse(BaseModel):
        """P3-C1 evidence-only runtime lifecycle snapshot."""

        ready: bool
        source: str
        state: str
        reason: str
        reason_code: str | None = None
        summary: str
        session_id: str | None = None
        agent_type: str | None = None
        runtime_type: str | None = None
        adapter_kind: str | None = None
        workspace_path: str | None = None
        resolved_workspace_path: str | None = None
        launch_cwd_preview: str | None = None
        runtime_handle_id: str | None = None
        gates_passed: list[str] = Field(default_factory=list)
        gates_failed: list[str] = Field(default_factory=list)
        blocking_reason_code: str | None = None
        blocking_summary: str | None = None
        launch_requested: bool = False
        fake_launch_started: bool = False
        real_runtime_started: bool = False
        runtime_probe_started: bool = False
        probe_state: str | None = None
        probe_reason_code: str | None = None
        probe_error_summary: str | None = None
        execution_enabled: bool = False
        changes_process_cwd: bool = False
        runs_real_command: bool = False
        runs_git: bool = False
        runs_write_git: bool = False
        launches_ai_runtime: bool = False

        @classmethod
        def from_snapshot(
            cls,
            snapshot,
        ) -> "WorkerRunOnceResponse.RuntimeLifecycleSnapshotResponse":
            """Convert one worker-side snapshot into an API DTO."""

            return cls(
                ready=snapshot.ready,
                source=snapshot.source,
                state=snapshot.state.value,
                reason=snapshot.reason.value,
                reason_code=snapshot.reason_code,
                summary=snapshot.summary,
                session_id=snapshot.session_id,
                agent_type=snapshot.agent_type,
                runtime_type=snapshot.runtime_type,
                adapter_kind=snapshot.adapter_kind,
                workspace_path=snapshot.workspace_path,
                resolved_workspace_path=snapshot.resolved_workspace_path,
                launch_cwd_preview=snapshot.launch_cwd_preview,
                runtime_handle_id=snapshot.runtime_handle_id,
                gates_passed=list(snapshot.gates_passed),
                gates_failed=list(snapshot.gates_failed),
                blocking_reason_code=snapshot.blocking_reason_code,
                blocking_summary=snapshot.blocking_summary,
                launch_requested=snapshot.launch_requested,
                fake_launch_started=snapshot.fake_launch_started,
                real_runtime_started=snapshot.real_runtime_started,
                runtime_probe_started=snapshot.runtime_probe_started,
                probe_state=snapshot.probe_state,
                probe_reason_code=snapshot.probe_reason_code,
                probe_error_summary=snapshot.probe_error_summary,
                execution_enabled=snapshot.execution_enabled,
                changes_process_cwd=snapshot.changes_process_cwd,
                runs_real_command=snapshot.runs_real_command,
                runs_git=snapshot.runs_git,
                runs_write_git=snapshot.runs_write_git,
                launches_ai_runtime=snapshot.launches_ai_runtime,
            )

    class FailureRecoveryDecisionResponse(BaseModel):
        """P5-E read-only recovery decision returned to API callers."""

        OWNER_LABELS_CN: ClassVar[dict[str, str]] = {
            "codex": "Codex 修复",
            "deepseek": "DeepSeek 配置修复",
            "user": "用户决策",
            "blocked": "阻塞等待",
        }
        ACTION_LABELS_CN: ClassVar[dict[str, str]] = {
            "retry": "重试",
            "fix_and_retry": "修复后重试",
            "pause_and_wait": "暂停等待",
            "replan": "重新规划",
            "escalate_to_human": "升级人工决策",
            "block_permanently": "永久阻塞",
            "archive": "归档",
        }
        INSTRUCTION_KIND_LABELS_CN: ClassVar[dict[str, str]] = {
            "code_fix": "代码修复",
            "test_fix": "测试修复",
            "config_fix": "配置修复",
            "evidence_fix": "证据修复",
            "replay": "重新执行",
            "pause": "暂停等待",
            "replan": "重新规划",
            "human_question": "人工问题",
        }

        class SafetyResponse(BaseModel):
            """Read-only P5-E safety flags nested under a recovery decision."""

            runs_git: bool = False
            runs_write_git: bool = False
            git_add_triggered: bool = False
            git_commit_triggered: bool = False
            git_push_triggered: bool = False
            pr_opened: bool = False
            merge_triggered: bool = False
            branch_deleted: bool = False
            git_reset_triggered: bool = False
            git_checkout_triggered: bool = False
            git_switch_triggered: bool = False
            git_stash_triggered: bool = False
            git_rebase_triggered: bool = False
            git_tag_triggered: bool = False
            ci_triggered: bool = False
            execution_enabled: bool = False
            worker_dispatch_triggered: bool = False
            api_response_exposed: bool = True
            agent_message_written: bool = False
            task_created: bool = False
            retry_triggered: bool = False

            @classmethod
            def from_decision(
                cls,
                decision: FailureRecoveryDecision,
            ) -> "WorkerRunOnceResponse.FailureRecoveryDecisionResponse.SafetyResponse":
                """Copy internal side-effect flags and mark P5-E API exposure."""

                flags = decision.safety_flags
                return cls(
                    runs_git=flags.runs_git,
                    runs_write_git=flags.runs_write_git,
                    git_add_triggered=flags.git_add_triggered,
                    git_commit_triggered=flags.git_commit_triggered,
                    git_push_triggered=flags.git_push_triggered,
                    pr_opened=flags.pr_opened,
                    merge_triggered=flags.merge_triggered,
                    branch_deleted=flags.branch_deleted,
                    git_reset_triggered=flags.git_reset_triggered,
                    git_checkout_triggered=flags.git_checkout_triggered,
                    git_switch_triggered=flags.git_switch_triggered,
                    git_stash_triggered=flags.git_stash_triggered,
                    git_rebase_triggered=flags.git_rebase_triggered,
                    git_tag_triggered=flags.git_tag_triggered,
                    ci_triggered=flags.ci_triggered,
                    execution_enabled=flags.execution_enabled,
                    worker_dispatch_triggered=flags.worker_dispatch_triggered,
                    api_response_exposed=True,
                    agent_message_written=flags.agent_message_written,
                    task_created=flags.task_created,
                    retry_triggered=flags.retry_triggered,
                )

        source: str
        version: str
        failure_category: str
        reason_code: str | None = None
        recoverable: bool
        retry_allowed: bool
        recommended_owner: str
        recommended_owner_label_cn: str
        next_action: str
        next_action_label_cn: str
        next_instruction_kind: str
        next_instruction_kind_label_cn: str
        next_instruction_draft_required: bool
        next_instruction_draft: str | None = None
        requires_human_decision: bool
        human_decision_reason: str | None = None
        user_visible_summary_cn: str
        audit_event_type: str
        rule_codes: list[str] = Field(default_factory=list)
        safety: SafetyResponse

        @classmethod
        def from_decision(
            cls,
            decision: FailureRecoveryDecision,
        ) -> "WorkerRunOnceResponse.FailureRecoveryDecisionResponse":
            """Copy the internal P5 decision into a read-only API DTO.

            This mapper only serializes existing values. It does not retry,
            dispatch workers, create tasks, write AgentMessage rows, or run Git.
            """

            return cls(
                source=decision.source,
                version=decision.version,
                failure_category=decision.failure_category.value,
                reason_code=(
                    decision.reason_code.value
                    if decision.reason_code is not None
                    else None
                ),
                recoverable=decision.recoverable,
                retry_allowed=decision.retry_allowed,
                recommended_owner=decision.recommended_owner.value,
                recommended_owner_label_cn=cls.OWNER_LABELS_CN[
                    decision.recommended_owner.value
                ],
                next_action=decision.next_action.value,
                next_action_label_cn=cls.ACTION_LABELS_CN[
                    decision.next_action.value
                ],
                next_instruction_kind=decision.next_instruction_kind.value,
                next_instruction_kind_label_cn=cls.INSTRUCTION_KIND_LABELS_CN[
                    decision.next_instruction_kind.value
                ],
                next_instruction_draft_required=decision.next_instruction_draft_required,
                next_instruction_draft=decision.next_instruction_draft,
                requires_human_decision=decision.requires_human_decision,
                human_decision_reason=decision.human_decision_reason,
                user_visible_summary_cn=decision.user_visible_summary_cn,
                audit_event_type=decision.audit_event_type,
                rule_codes=list(decision.rule_codes),
                safety=cls.SafetyResponse.from_decision(decision),
            )

    claimed: bool
    message: str
    execution_mode: str | None = None
    verification_mode: str | None = None
    verification_template: str | None = None
    verification_summary: str | None = None
    failure_category: RunFailureCategory | None = None
    quality_gate_passed: bool | None = None
    route_reason: str | None = None
    routing_score: float | None = None
    routing_score_breakdown: list[RoutingScoreItemResponse] = Field(default_factory=list)
    budget_pressure_level: RunBudgetPressureLevel | None = None
    budget_action: RunBudgetStrategyAction | None = None
    budget_strategy_code: str | None = None
    budget_strategy_summary: str | None = None
    result_summary: str | None = None
    context_summary: str | None = None
    model_name: str | None = None
    model_tier: str | None = None
    selected_skill_codes: list[str] = Field(default_factory=list)
    selected_skill_names: list[str] = Field(default_factory=list)
    strategy_code: str | None = None
    strategy_summary: str | None = None
    role_model_policy_source: str | None = None
    role_model_policy_desired_tier: str | None = None
    role_model_policy_adjusted_tier: str | None = None
    role_model_policy_final_tier: str | None = None
    role_model_policy_stage_override_applied: bool = False
    owner_role_code: ProjectRoleCode | None = None
    upstream_role_code: ProjectRoleCode | None = None
    downstream_role_code: ProjectRoleCode | None = None
    handoff_reason: str | None = None
    dispatch_status: str | None = None
    project_memory_enabled: bool | None = None
    project_memory_query_text: str | None = None
    project_memory_item_count: int | None = None
    project_memory_context_summary: str | None = None
    memory_governance_checkpoint_id: str | None = None
    memory_governance_rolling_summary: str | None = None
    memory_governance_bad_context_detected: bool | None = None
    memory_governance_bad_context_reasons: list[str] = Field(default_factory=list)
    memory_governance_pressure_level: str | None = None
    memory_governance_usage_ratio: float | None = None
    memory_governance_compaction_applied: bool | None = None
    memory_governance_compaction_ratio: float | None = None
    memory_governance_rehydrated: bool | None = None
    memory_governance_rehydrate_source_checkpoint_id: str | None = None
    agent_session_id: UUID | None = None
    agent_session_status: str | None = None
    agent_review_status: str | None = None
    agent_current_phase: str | None = None
    agent_type: str | None = None
    runtime_type: str | None = None
    runtime_handle_id: str | None = None
    coding_status: str | None = None
    activity_state: str | None = None
    branch_name: str | None = None
    workspace_type: str | None = None
    workspace_path: str | None = None
    workspace_clean: bool | None = None
    last_workspace_error: str | None = None
    workspace_context_ready: bool | None = None
    workspace_context_source: str | None = None
    workspace_context_reason_code: str | None = None
    workspace_context_path: str | None = None
    workspace_context_resolved_path: str | None = None
    workspace_context_uses_agent_workspace: bool | None = None
    workspace_context_changes_cwd: bool | None = None
    workspace_context_runs_git: bool | None = None
    workspace_context_runs_write_git: bool | None = None
    workspace_context_launches_runtime: bool | None = None
    runtime_launch_dry_run_ready: bool | None = None
    runtime_launch_dry_run_source: str | None = None
    runtime_launch_dry_run_reason_code: str | None = None
    runtime_launch_dry_run_session_id: str | None = None
    runtime_launch_dry_run_agent_type: str | None = None
    runtime_launch_dry_run_runtime_type: str | None = None
    runtime_launch_dry_run_workspace_path: str | None = None
    runtime_launch_dry_run_resolved_workspace_path: str | None = None
    runtime_launch_dry_run_launch_cwd_preview: str | None = None
    runtime_launch_dry_run_launch_command_preview: str | None = None
    runtime_launch_dry_run_uses_agent_workspace: bool | None = None
    runtime_launch_dry_run_command_preview_uses_workspace: bool | None = None
    runtime_launch_dry_run_execution_enabled: bool | None = None
    runtime_launch_dry_run_changes_cwd: bool | None = None
    runtime_launch_dry_run_runs_command: bool | None = None
    runtime_launch_dry_run_runs_git: bool | None = None
    runtime_launch_dry_run_runs_write_git: bool | None = None
    runtime_launch_dry_run_launches_runtime: bool | None = None
    runtime_launch_gate_ready: bool | None = None
    runtime_launch_gate_gates_passed: list[str] = Field(default_factory=list)
    runtime_launch_gate_gates_failed: list[str] = Field(default_factory=list)
    runtime_launch_gate_blocking_reason_code: str | None = None
    runtime_launch_gate_blocking_summary: str | None = None
    runtime_launch_gate_changes_process_cwd: bool | None = None
    runtime_launch_gate_runs_real_command: bool | None = None
    runtime_launch_gate_runs_git: bool | None = None
    runtime_launch_gate_runs_write_git: bool | None = None
    runtime_launch_gate_launches_ai_runtime: bool | None = None
    runtime_launch_gate_execution_enabled: bool | None = None
    runtime_lifecycle_snapshot: RuntimeLifecycleSnapshotResponse | None = None
    worktree_safe_command_proof_ready: bool | None = None
    worktree_safe_command_proof_source: str | None = None
    worktree_safe_command_proof_reason_code: str | None = None
    worktree_safe_command_proof_command: str | None = None
    worktree_safe_command_proof_cwd: str | None = None
    worktree_safe_command_proof_expected_workspace_path: str | None = None
    worktree_safe_command_proof_observed_pwd: str | None = None
    worktree_safe_command_proof_pwd_matches_workspace_path: bool | None = None
    worktree_safe_command_proof_exit_code: int | None = None
    worktree_safe_command_proof_stdout: str | None = None
    worktree_safe_command_proof_stderr: str | None = None
    worktree_safe_command_proof_timed_out: bool | None = None
    worktree_safe_command_proof_read_only: bool | None = None
    worktree_safe_command_proof_allowlisted: bool | None = None
    worktree_safe_command_proof_uses_agent_workspace: bool | None = None
    worktree_safe_command_proof_changes_process_cwd: bool | None = None
    worktree_safe_command_proof_runs_command: bool | None = None
    worktree_safe_command_proof_runs_git: bool | None = None
    worktree_safe_command_proof_runs_write_git: bool | None = None
    worktree_safe_command_proof_launches_worker_loop: bool | None = None
    worktree_safe_command_proof_launches_ai_runtime: bool | None = None
    git_diff_dry_run_ready: bool | None = None
    git_diff_dry_run_source: str | None = None
    git_diff_dry_run_reason_code: str | None = None
    git_diff_dry_run_worktree_path: str | None = None
    git_diff_dry_run_has_changes: bool | None = None
    git_diff_dry_run_changed_files_count: int | None = None
    git_diff_dry_run_changed_files: list[str] = Field(default_factory=list)
    git_diff_dry_run_added_files: list[str] = Field(default_factory=list)
    git_diff_dry_run_modified_files: list[str] = Field(default_factory=list)
    git_diff_dry_run_deleted_files: list[str] = Field(default_factory=list)
    git_diff_dry_run_renamed_files: list[str] = Field(default_factory=list)
    git_diff_dry_run_status_summary_cn: str | None = None
    git_diff_dry_run_diff_stat: str | None = None
    git_diff_dry_run_diff_shortstat: str | None = None
    git_diff_dry_run_branch_name: str | None = None
    git_diff_dry_run_compare_branch: str | None = None
    git_diff_dry_run_command: str | None = None
    git_diff_dry_run_peek_command: str | None = None
    git_diff_dry_run_danger_commands_applied: bool | None = None
    git_diff_dry_run_runs_git: bool | None = None
    git_diff_dry_run_runs_write_git: bool | None = None
    git_diff_dry_run_git_add_triggered: bool | None = None
    git_diff_dry_run_git_commit_triggered: bool | None = None
    git_diff_dry_run_git_push_triggered: bool | None = None
    git_diff_dry_run_pr_opened: bool | None = None
    git_diff_dry_run_ci_triggered: bool | None = None
    git_diff_dry_run_execution_enabled: bool | None = None
    git_operation_dry_run_ready: bool | None = None
    git_operation_dry_run_source: str | None = None
    git_operation_dry_run_reason_code: str | None = None
    git_operation_dry_run_session_id: str | None = None
    git_operation_dry_run_project_id: str | None = None
    git_operation_dry_run_task_id: str | None = None
    git_operation_dry_run_run_id: str | None = None
    git_operation_dry_run_worktree_path: str | None = None
    git_operation_dry_run_branch_name: str | None = None
    git_operation_dry_run_changed_files_count: int | None = None
    git_operation_dry_run_changed_files: list[str] = Field(default_factory=list)
    git_operation_dry_run_added_files: list[str] = Field(default_factory=list)
    git_operation_dry_run_modified_files: list[str] = Field(default_factory=list)
    git_operation_dry_run_deleted_files: list[str] = Field(default_factory=list)
    git_operation_dry_run_renamed_files: list[str] = Field(default_factory=list)
    git_operation_dry_run_proposed_operation: str | None = None
    git_operation_dry_run_proposed_steps: list[str] = Field(default_factory=list)
    git_operation_dry_run_proposed_commit_message: str | None = None
    git_operation_dry_run_proposed_pr_title: str | None = None
    git_operation_dry_run_proposed_pr_body: str | None = None
    git_operation_dry_run_user_confirmation_required: bool | None = None
    git_operation_dry_run_human_approval_required: bool | None = None
    git_operation_dry_run_feature_flag_required: bool | None = None
    git_operation_dry_run_summary_cn: str | None = None
    git_operation_dry_run_runs_git: bool | None = None
    git_operation_dry_run_runs_write_git: bool | None = None
    git_operation_dry_run_git_add_triggered: bool | None = None
    git_operation_dry_run_git_commit_triggered: bool | None = None
    git_operation_dry_run_git_push_triggered: bool | None = None
    git_operation_dry_run_pr_opened: bool | None = None
    git_operation_dry_run_ci_triggered: bool | None = None
    git_operation_dry_run_execution_enabled: bool | None = None
    git_operation_dry_run_operation_applied: bool | None = None
    git_operation_dry_run_approval_granted: bool | None = None
    delivery_gate_evidence_ready: bool | None = None
    delivery_gate_evidence_source: str | None = None
    delivery_gate_evidence_reason_code: str | None = None
    delivery_gate_evidence_session_id: str | None = None
    delivery_gate_evidence_project_id: str | None = None
    delivery_gate_evidence_task_id: str | None = None
    delivery_gate_evidence_run_id: str | None = None
    delivery_gate_evidence_worktree_path: str | None = None
    delivery_gate_evidence_branch_name: str | None = None
    delivery_gate_evidence_proposed_operation: str | None = None
    delivery_gate_evidence_changed_files_count: int | None = None
    delivery_gate_evidence_changed_files: list[str] = Field(default_factory=list)
    delivery_gate_evidence_next_required_action: str | None = None
    delivery_gate_evidence_user_confirmation_required: bool | None = None
    delivery_gate_evidence_human_approval_required: bool | None = None
    delivery_gate_evidence_delivery_audit_event_present: bool | None = None
    delivery_gate_evidence_delivery_audit_event_type: str | None = None
    delivery_gate_evidence_delivery_audit_event_ready: bool | None = None
    delivery_gate_evidence_summary_cn: str | None = None
    delivery_gate_evidence_satisfied_conditions: list[str] = Field(default_factory=list)
    delivery_gate_evidence_blocking_reasons: list[str] = Field(default_factory=list)
    delivery_gate_evidence_runs_git: bool | None = None
    delivery_gate_evidence_runs_write_git: bool | None = None
    delivery_gate_evidence_git_add_triggered: bool | None = None
    delivery_gate_evidence_git_commit_triggered: bool | None = None
    delivery_gate_evidence_git_push_triggered: bool | None = None
    delivery_gate_evidence_pr_opened: bool | None = None
    delivery_gate_evidence_ci_triggered: bool | None = None
    delivery_gate_evidence_execution_enabled: bool | None = None
    delivery_gate_evidence_operation_applied: bool | None = None
    delivery_gate_evidence_approval_granted: bool | None = None
    delivery_gate_evidence_gate_allows_write: bool | None = None
    delivery_gate_evidence_gate_allows_user_confirmation: bool | None = None
    delivery_human_approval_ready: bool | None = None
    delivery_human_approval_source: str | None = None
    delivery_human_approval_reason_code: str | None = None
    delivery_human_approval_summary_cn: str | None = None
    delivery_human_approval_session_id: str | None = None
    delivery_human_approval_project_id: str | None = None
    delivery_human_approval_task_id: str | None = None
    delivery_human_approval_run_id: str | None = None
    delivery_human_approval_required: bool | None = None
    delivery_human_approval_granted: bool | None = None
    delivery_human_approval_id: str | None = None
    delivery_human_approval_approved_by: str | None = None
    delivery_human_approval_approved_by_display_name: str | None = None
    delivery_human_approval_scope: str | None = None
    delivery_human_approval_requested_action: str | None = None
    delivery_human_approval_client_request_id: str | None = None
    delivery_human_approval_created_at: datetime | None = None
    delivery_human_approval_expires_at: datetime | None = None
    delivery_human_approval_applied: bool | None = None
    delivery_human_approval_revoked: bool | None = None
    delivery_human_approval_confirmation_fingerprint: str | None = None
    delivery_human_approval_operation_dry_run_ready: bool | None = None
    delivery_human_approval_delivery_gate_evidence_ready: bool | None = None
    delivery_human_approval_delivery_gate_allows_user_confirmation: bool | None = None
    delivery_human_approval_delivery_gate_allows_write: bool | None = None
    delivery_human_approval_proposed_operation: str | None = None
    delivery_human_approval_proposed_commit_message: str | None = None
    delivery_human_approval_changed_files_count: int | None = None
    delivery_human_approval_changed_files: list[str] = Field(default_factory=list)
    delivery_human_approval_satisfied_conditions: list[str] = Field(default_factory=list)
    delivery_human_approval_blocking_reasons: list[str] = Field(default_factory=list)
    delivery_human_approval_runs_git: bool | None = None
    delivery_human_approval_runs_write_git: bool | None = None
    delivery_human_approval_git_add_triggered: bool | None = None
    delivery_human_approval_git_commit_triggered: bool | None = None
    delivery_human_approval_git_push_triggered: bool | None = None
    delivery_human_approval_pr_opened: bool | None = None
    delivery_human_approval_ci_triggered: bool | None = None
    delivery_human_approval_execution_enabled: bool | None = None
    delivery_human_approval_operation_applied: bool | None = None
    delivery_human_approval_gate_allows_write: bool | None = None
    delivery_human_approval_gate_allows_next_guardrail: bool | None = None
    failure_recovery_decision: FailureRecoveryDecisionResponse | None = None
    task_id: UUID | None = None
    task_title: str | None = None
    task_status: TaskStatus | None = None
    run_id: UUID | None = None
    run_status: RunStatus | None = None
    run_created_at: datetime | None = None
    run_finished_at: datetime | None = None
    provider_key: str | None = None
    prompt_template_key: str | None = None
    prompt_template_version: str | None = None
    prompt_char_count: int | None = None
    token_accounting_mode: str | None = None
    provider_receipt_id: str | None = None
    total_tokens: int | None = None
    token_pricing_source: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    estimated_cost: float | None = None
    log_path: str | None = None

    @classmethod
    def from_result(cls, result: WorkerRunResult) -> "WorkerRunOnceResponse":
        """Convert the internal worker result into an API DTO."""

        return cls(
            claimed=result.claimed,
            message=result.message,
            execution_mode=result.execution_mode,
            verification_mode=result.verification_mode,
            verification_template=result.verification_template,
            verification_summary=result.verification_summary,
            failure_category=result.failure_category,
            quality_gate_passed=result.quality_gate_passed,
            route_reason=result.route_reason,
            routing_score=result.routing_score,
            routing_score_breakdown=[
                cls.RoutingScoreItemResponse.from_item(item)
                for item in result.routing_score_breakdown
            ],
            budget_pressure_level=result.budget_pressure_level,
            budget_action=result.budget_action,
            budget_strategy_code=result.budget_strategy_code,
            budget_strategy_summary=result.budget_strategy_summary,
            result_summary=result.result_summary,
            context_summary=result.context_summary,
            model_name=result.model_name,
            model_tier=result.model_tier,
            selected_skill_codes=result.selected_skill_codes,
            selected_skill_names=result.selected_skill_names,
            strategy_code=result.strategy_code,
            strategy_summary=result.strategy_summary,
            role_model_policy_source=(
                result.run.strategy_decision.role_model_policy_source
                if result.run and result.run.strategy_decision is not None
                else None
            ),
            role_model_policy_desired_tier=(
                result.run.strategy_decision.role_model_policy_desired_tier
                if result.run and result.run.strategy_decision is not None
                else None
            ),
            role_model_policy_adjusted_tier=(
                result.run.strategy_decision.role_model_policy_adjusted_tier
                if result.run and result.run.strategy_decision is not None
                else None
            ),
            role_model_policy_final_tier=(
                result.run.strategy_decision.role_model_policy_final_tier
                if result.run and result.run.strategy_decision is not None
                else None
            ),
            role_model_policy_stage_override_applied=(
                result.run.strategy_decision.role_model_policy_stage_override_applied
                if result.run and result.run.strategy_decision is not None
                else False
            ),
            owner_role_code=result.owner_role_code,
            upstream_role_code=result.upstream_role_code,
            downstream_role_code=result.downstream_role_code,
            handoff_reason=result.handoff_reason,
            dispatch_status=result.dispatch_status,
            project_memory_enabled=result.project_memory_enabled,
            project_memory_query_text=result.project_memory_query_text,
            project_memory_item_count=result.project_memory_item_count,
            project_memory_context_summary=result.project_memory_context_summary,
            memory_governance_checkpoint_id=result.memory_governance_checkpoint_id,
            memory_governance_rolling_summary=result.memory_governance_rolling_summary,
            memory_governance_bad_context_detected=(
                result.memory_governance_bad_context_detected
            ),
            memory_governance_bad_context_reasons=(
                result.memory_governance_bad_context_reasons
            ),
            memory_governance_pressure_level=result.memory_governance_pressure_level,
            memory_governance_usage_ratio=result.memory_governance_usage_ratio,
            memory_governance_compaction_applied=(
                result.memory_governance_compaction_applied
            ),
            memory_governance_compaction_ratio=result.memory_governance_compaction_ratio,
            memory_governance_rehydrated=result.memory_governance_rehydrated,
            memory_governance_rehydrate_source_checkpoint_id=(
                result.memory_governance_rehydrate_source_checkpoint_id
            ),
            agent_session_id=result.agent_session_id,
            agent_session_status=result.agent_session_status,
            agent_review_status=result.agent_review_status,
            agent_current_phase=result.agent_current_phase,
            agent_type=result.agent_type,
            runtime_type=result.runtime_type,
            runtime_handle_id=result.runtime_handle_id,
            coding_status=result.coding_status,
            activity_state=result.activity_state,
            branch_name=result.branch_name,
            workspace_type=result.workspace_type,
            workspace_path=result.workspace_path,
            workspace_clean=result.workspace_clean,
            last_workspace_error=result.last_workspace_error,
            workspace_context_ready=result.workspace_context_ready,
            workspace_context_source=result.workspace_context_source,
            workspace_context_reason_code=result.workspace_context_reason_code,
            workspace_context_path=result.workspace_context_path,
            workspace_context_resolved_path=result.workspace_context_resolved_path,
            workspace_context_uses_agent_workspace=(
                result.workspace_context_uses_agent_workspace
            ),
            workspace_context_changes_cwd=result.workspace_context_changes_cwd,
            workspace_context_runs_git=result.workspace_context_runs_git,
            workspace_context_runs_write_git=result.workspace_context_runs_write_git,
            workspace_context_launches_runtime=(
                result.workspace_context_launches_runtime
            ),
            runtime_launch_dry_run_ready=result.runtime_launch_dry_run_ready,
            runtime_launch_dry_run_source=result.runtime_launch_dry_run_source,
            runtime_launch_dry_run_reason_code=(
                result.runtime_launch_dry_run_reason_code
            ),
            runtime_launch_dry_run_session_id=(
                result.runtime_launch_dry_run_session_id
            ),
            runtime_launch_dry_run_agent_type=(
                result.runtime_launch_dry_run_agent_type
            ),
            runtime_launch_dry_run_runtime_type=(
                result.runtime_launch_dry_run_runtime_type
            ),
            runtime_launch_dry_run_workspace_path=(
                result.runtime_launch_dry_run_workspace_path
            ),
            runtime_launch_dry_run_resolved_workspace_path=(
                result.runtime_launch_dry_run_resolved_workspace_path
            ),
            runtime_launch_dry_run_launch_cwd_preview=(
                result.runtime_launch_dry_run_launch_cwd_preview
            ),
            runtime_launch_dry_run_launch_command_preview=(
                result.runtime_launch_dry_run_launch_command_preview
            ),
            runtime_launch_dry_run_uses_agent_workspace=(
                result.runtime_launch_dry_run_uses_agent_workspace
            ),
            runtime_launch_dry_run_command_preview_uses_workspace=(
                result.runtime_launch_dry_run_command_preview_uses_workspace
            ),
            runtime_launch_dry_run_execution_enabled=(
                result.runtime_launch_dry_run_execution_enabled
            ),
            runtime_launch_dry_run_changes_cwd=(
                result.runtime_launch_dry_run_changes_cwd
            ),
            runtime_launch_dry_run_runs_command=(
                result.runtime_launch_dry_run_runs_command
            ),
            runtime_launch_dry_run_runs_git=(
                result.runtime_launch_dry_run_runs_git
            ),
            runtime_launch_dry_run_runs_write_git=(
                result.runtime_launch_dry_run_runs_write_git
            ),
            runtime_launch_dry_run_launches_runtime=(
                result.runtime_launch_dry_run_launches_runtime
            ),
            runtime_launch_gate_ready=result.runtime_launch_gate_ready,
            runtime_launch_gate_gates_passed=(
                result.runtime_launch_gate_gates_passed
            ),
            runtime_launch_gate_gates_failed=(
                result.runtime_launch_gate_gates_failed
            ),
            runtime_launch_gate_blocking_reason_code=(
                result.runtime_launch_gate_blocking_reason_code
            ),
            runtime_launch_gate_blocking_summary=(
                result.runtime_launch_gate_blocking_summary
            ),
            runtime_launch_gate_changes_process_cwd=(
                result.runtime_launch_gate_changes_process_cwd
            ),
            runtime_launch_gate_runs_real_command=(
                result.runtime_launch_gate_runs_real_command
            ),
            runtime_launch_gate_runs_git=result.runtime_launch_gate_runs_git,
            runtime_launch_gate_runs_write_git=(
                result.runtime_launch_gate_runs_write_git
            ),
            runtime_launch_gate_launches_ai_runtime=(
                result.runtime_launch_gate_launches_ai_runtime
            ),
            runtime_launch_gate_execution_enabled=(
                result.runtime_launch_gate_execution_enabled
            ),
            runtime_lifecycle_snapshot=(
                cls.RuntimeLifecycleSnapshotResponse.from_snapshot(
                    result.runtime_lifecycle_snapshot
                )
                if result.runtime_lifecycle_snapshot is not None
                else None
            ),
            worktree_safe_command_proof_ready=(
                result.worktree_safe_command_proof_ready
            ),
            worktree_safe_command_proof_source=(
                result.worktree_safe_command_proof_source
            ),
            worktree_safe_command_proof_reason_code=(
                result.worktree_safe_command_proof_reason_code
            ),
            worktree_safe_command_proof_command=(
                result.worktree_safe_command_proof_command
            ),
            worktree_safe_command_proof_cwd=result.worktree_safe_command_proof_cwd,
            worktree_safe_command_proof_expected_workspace_path=(
                result.worktree_safe_command_proof_expected_workspace_path
            ),
            worktree_safe_command_proof_observed_pwd=(
                result.worktree_safe_command_proof_observed_pwd
            ),
            worktree_safe_command_proof_pwd_matches_workspace_path=(
                result.worktree_safe_command_proof_pwd_matches_workspace_path
            ),
            worktree_safe_command_proof_exit_code=(
                result.worktree_safe_command_proof_exit_code
            ),
            worktree_safe_command_proof_stdout=(
                result.worktree_safe_command_proof_stdout
            ),
            worktree_safe_command_proof_stderr=(
                result.worktree_safe_command_proof_stderr
            ),
            worktree_safe_command_proof_timed_out=(
                result.worktree_safe_command_proof_timed_out
            ),
            worktree_safe_command_proof_read_only=(
                result.worktree_safe_command_proof_read_only
            ),
            worktree_safe_command_proof_allowlisted=(
                result.worktree_safe_command_proof_allowlisted
            ),
            worktree_safe_command_proof_uses_agent_workspace=(
                result.worktree_safe_command_proof_uses_agent_workspace
            ),
            worktree_safe_command_proof_changes_process_cwd=(
                result.worktree_safe_command_proof_changes_process_cwd
            ),
            worktree_safe_command_proof_runs_command=(
                result.worktree_safe_command_proof_runs_command
            ),
            worktree_safe_command_proof_runs_git=(
                result.worktree_safe_command_proof_runs_git
            ),
            worktree_safe_command_proof_runs_write_git=(
                result.worktree_safe_command_proof_runs_write_git
            ),
            worktree_safe_command_proof_launches_worker_loop=(
                result.worktree_safe_command_proof_launches_worker_loop
            ),
            worktree_safe_command_proof_launches_ai_runtime=(
                result.worktree_safe_command_proof_launches_ai_runtime
            ),
            git_diff_dry_run_ready=result.git_diff_dry_run_ready,
            git_diff_dry_run_source=result.git_diff_dry_run_source,
            git_diff_dry_run_reason_code=result.git_diff_dry_run_reason_code,
            git_diff_dry_run_worktree_path=result.git_diff_dry_run_worktree_path,
            git_diff_dry_run_has_changes=result.git_diff_dry_run_has_changes,
            git_diff_dry_run_changed_files_count=(
                result.git_diff_dry_run_changed_files_count
            ),
            git_diff_dry_run_changed_files=(
                result.git_diff_dry_run_changed_files
            ),
            git_diff_dry_run_added_files=result.git_diff_dry_run_added_files,
            git_diff_dry_run_modified_files=(
                result.git_diff_dry_run_modified_files
            ),
            git_diff_dry_run_deleted_files=result.git_diff_dry_run_deleted_files,
            git_diff_dry_run_renamed_files=result.git_diff_dry_run_renamed_files,
            git_diff_dry_run_status_summary_cn=(
                result.git_diff_dry_run_status_summary_cn
            ),
            git_diff_dry_run_diff_stat=result.git_diff_dry_run_diff_stat,
            git_diff_dry_run_diff_shortstat=(
                result.git_diff_dry_run_diff_shortstat
            ),
            git_diff_dry_run_branch_name=result.git_diff_dry_run_branch_name,
            git_diff_dry_run_compare_branch=result.git_diff_dry_run_compare_branch,
            git_diff_dry_run_command=result.git_diff_dry_run_command,
            git_diff_dry_run_peek_command=result.git_diff_dry_run_peek_command,
            git_diff_dry_run_danger_commands_applied=(
                result.git_diff_dry_run_danger_commands_applied
            ),
            git_diff_dry_run_runs_git=result.git_diff_dry_run_runs_git,
            git_diff_dry_run_runs_write_git=(
                result.git_diff_dry_run_runs_write_git
            ),
            git_diff_dry_run_git_add_triggered=(
                result.git_diff_dry_run_git_add_triggered
            ),
            git_diff_dry_run_git_commit_triggered=(
                result.git_diff_dry_run_git_commit_triggered
            ),
            git_diff_dry_run_git_push_triggered=(
                result.git_diff_dry_run_git_push_triggered
            ),
            git_diff_dry_run_pr_opened=result.git_diff_dry_run_pr_opened,
            git_diff_dry_run_ci_triggered=result.git_diff_dry_run_ci_triggered,
            git_diff_dry_run_execution_enabled=(
                result.git_diff_dry_run_execution_enabled
            ),
            git_operation_dry_run_ready=result.git_operation_dry_run_ready,
            git_operation_dry_run_source=result.git_operation_dry_run_source,
            git_operation_dry_run_reason_code=(
                result.git_operation_dry_run_reason_code
            ),
            git_operation_dry_run_session_id=(
                result.git_operation_dry_run_session_id
            ),
            git_operation_dry_run_project_id=(
                result.git_operation_dry_run_project_id
            ),
            git_operation_dry_run_task_id=result.git_operation_dry_run_task_id,
            git_operation_dry_run_run_id=result.git_operation_dry_run_run_id,
            git_operation_dry_run_worktree_path=(
                result.git_operation_dry_run_worktree_path
            ),
            git_operation_dry_run_branch_name=(
                result.git_operation_dry_run_branch_name
            ),
            git_operation_dry_run_changed_files_count=(
                result.git_operation_dry_run_changed_files_count
            ),
            git_operation_dry_run_changed_files=(
                result.git_operation_dry_run_changed_files
            ),
            git_operation_dry_run_added_files=(
                result.git_operation_dry_run_added_files
            ),
            git_operation_dry_run_modified_files=(
                result.git_operation_dry_run_modified_files
            ),
            git_operation_dry_run_deleted_files=(
                result.git_operation_dry_run_deleted_files
            ),
            git_operation_dry_run_renamed_files=(
                result.git_operation_dry_run_renamed_files
            ),
            git_operation_dry_run_proposed_operation=(
                result.git_operation_dry_run_proposed_operation
            ),
            git_operation_dry_run_proposed_steps=(
                result.git_operation_dry_run_proposed_steps
            ),
            git_operation_dry_run_proposed_commit_message=(
                result.git_operation_dry_run_proposed_commit_message
            ),
            git_operation_dry_run_proposed_pr_title=(
                result.git_operation_dry_run_proposed_pr_title
            ),
            git_operation_dry_run_proposed_pr_body=(
                result.git_operation_dry_run_proposed_pr_body
            ),
            git_operation_dry_run_user_confirmation_required=(
                result.git_operation_dry_run_user_confirmation_required
            ),
            git_operation_dry_run_human_approval_required=(
                result.git_operation_dry_run_human_approval_required
            ),
            git_operation_dry_run_feature_flag_required=(
                result.git_operation_dry_run_feature_flag_required
            ),
            git_operation_dry_run_summary_cn=(
                result.git_operation_dry_run_summary_cn
            ),
            git_operation_dry_run_runs_git=result.git_operation_dry_run_runs_git,
            git_operation_dry_run_runs_write_git=(
                result.git_operation_dry_run_runs_write_git
            ),
            git_operation_dry_run_git_add_triggered=(
                result.git_operation_dry_run_git_add_triggered
            ),
            git_operation_dry_run_git_commit_triggered=(
                result.git_operation_dry_run_git_commit_triggered
            ),
            git_operation_dry_run_git_push_triggered=(
                result.git_operation_dry_run_git_push_triggered
            ),
            git_operation_dry_run_pr_opened=result.git_operation_dry_run_pr_opened,
            git_operation_dry_run_ci_triggered=result.git_operation_dry_run_ci_triggered,
            git_operation_dry_run_execution_enabled=(
                result.git_operation_dry_run_execution_enabled
            ),
            git_operation_dry_run_operation_applied=(
                result.git_operation_dry_run_operation_applied
            ),
            git_operation_dry_run_approval_granted=(
                result.git_operation_dry_run_approval_granted
            ),
            delivery_gate_evidence_ready=result.delivery_gate_evidence_ready,
            delivery_gate_evidence_source=result.delivery_gate_evidence_source,
            delivery_gate_evidence_reason_code=(
                result.delivery_gate_evidence_reason_code
            ),
            delivery_gate_evidence_session_id=(
                result.delivery_gate_evidence_session_id
            ),
            delivery_gate_evidence_project_id=(
                result.delivery_gate_evidence_project_id
            ),
            delivery_gate_evidence_task_id=result.delivery_gate_evidence_task_id,
            delivery_gate_evidence_run_id=result.delivery_gate_evidence_run_id,
            delivery_gate_evidence_worktree_path=(
                result.delivery_gate_evidence_worktree_path
            ),
            delivery_gate_evidence_branch_name=(
                result.delivery_gate_evidence_branch_name
            ),
            delivery_gate_evidence_proposed_operation=(
                result.delivery_gate_evidence_proposed_operation
            ),
            delivery_gate_evidence_changed_files_count=(
                result.delivery_gate_evidence_changed_files_count
            ),
            delivery_gate_evidence_changed_files=(
                result.delivery_gate_evidence_changed_files
            ),
            delivery_gate_evidence_next_required_action=(
                result.delivery_gate_evidence_next_required_action
            ),
            delivery_gate_evidence_user_confirmation_required=(
                result.delivery_gate_evidence_user_confirmation_required
            ),
            delivery_gate_evidence_human_approval_required=(
                result.delivery_gate_evidence_human_approval_required
            ),
            delivery_gate_evidence_delivery_audit_event_present=(
                result.delivery_gate_evidence_delivery_audit_event_present
            ),
            delivery_gate_evidence_delivery_audit_event_type=(
                result.delivery_gate_evidence_delivery_audit_event_type
            ),
            delivery_gate_evidence_delivery_audit_event_ready=(
                result.delivery_gate_evidence_delivery_audit_event_ready
            ),
            delivery_gate_evidence_summary_cn=(
                result.delivery_gate_evidence_summary_cn
            ),
            delivery_gate_evidence_satisfied_conditions=(
                result.delivery_gate_evidence_satisfied_conditions
            ),
            delivery_gate_evidence_blocking_reasons=(
                result.delivery_gate_evidence_blocking_reasons
            ),
            delivery_gate_evidence_runs_git=result.delivery_gate_evidence_runs_git,
            delivery_gate_evidence_runs_write_git=(
                result.delivery_gate_evidence_runs_write_git
            ),
            delivery_gate_evidence_git_add_triggered=(
                result.delivery_gate_evidence_git_add_triggered
            ),
            delivery_gate_evidence_git_commit_triggered=(
                result.delivery_gate_evidence_git_commit_triggered
            ),
            delivery_gate_evidence_git_push_triggered=(
                result.delivery_gate_evidence_git_push_triggered
            ),
            delivery_gate_evidence_pr_opened=result.delivery_gate_evidence_pr_opened,
            delivery_gate_evidence_ci_triggered=result.delivery_gate_evidence_ci_triggered,
            delivery_gate_evidence_execution_enabled=(
                result.delivery_gate_evidence_execution_enabled
            ),
            delivery_gate_evidence_operation_applied=(
                result.delivery_gate_evidence_operation_applied
            ),
            delivery_gate_evidence_approval_granted=(
                result.delivery_gate_evidence_approval_granted
            ),
            delivery_gate_evidence_gate_allows_write=(
                result.delivery_gate_evidence_gate_allows_write
            ),
            delivery_gate_evidence_gate_allows_user_confirmation=(
                result.delivery_gate_evidence_gate_allows_user_confirmation
            ),
            delivery_human_approval_ready=result.delivery_human_approval_ready,
            delivery_human_approval_source=result.delivery_human_approval_source,
            delivery_human_approval_reason_code=(
                result.delivery_human_approval_reason_code
            ),
            delivery_human_approval_summary_cn=(
                result.delivery_human_approval_summary_cn
            ),
            delivery_human_approval_session_id=(
                result.delivery_human_approval_session_id
            ),
            delivery_human_approval_project_id=(
                result.delivery_human_approval_project_id
            ),
            delivery_human_approval_task_id=result.delivery_human_approval_task_id,
            delivery_human_approval_run_id=result.delivery_human_approval_run_id,
            delivery_human_approval_required=(
                result.delivery_human_approval_required
            ),
            delivery_human_approval_granted=result.delivery_human_approval_granted,
            delivery_human_approval_id=result.delivery_human_approval_id,
            delivery_human_approval_approved_by=(
                result.delivery_human_approval_approved_by
            ),
            delivery_human_approval_approved_by_display_name=(
                result.delivery_human_approval_approved_by_display_name
            ),
            delivery_human_approval_scope=result.delivery_human_approval_scope,
            delivery_human_approval_requested_action=(
                result.delivery_human_approval_requested_action
            ),
            delivery_human_approval_client_request_id=(
                result.delivery_human_approval_client_request_id
            ),
            delivery_human_approval_created_at=(
                result.delivery_human_approval_created_at
            ),
            delivery_human_approval_expires_at=(
                result.delivery_human_approval_expires_at
            ),
            delivery_human_approval_applied=result.delivery_human_approval_applied,
            delivery_human_approval_revoked=result.delivery_human_approval_revoked,
            delivery_human_approval_confirmation_fingerprint=(
                result.delivery_human_approval_confirmation_fingerprint
            ),
            delivery_human_approval_operation_dry_run_ready=(
                result.delivery_human_approval_operation_dry_run_ready
            ),
            delivery_human_approval_delivery_gate_evidence_ready=(
                result.delivery_human_approval_delivery_gate_evidence_ready
            ),
            delivery_human_approval_delivery_gate_allows_user_confirmation=(
                result.delivery_human_approval_delivery_gate_allows_user_confirmation
            ),
            delivery_human_approval_delivery_gate_allows_write=(
                result.delivery_human_approval_delivery_gate_allows_write
            ),
            delivery_human_approval_proposed_operation=(
                result.delivery_human_approval_proposed_operation
            ),
            delivery_human_approval_proposed_commit_message=(
                result.delivery_human_approval_proposed_commit_message
            ),
            delivery_human_approval_changed_files_count=(
                result.delivery_human_approval_changed_files_count
            ),
            delivery_human_approval_changed_files=(
                result.delivery_human_approval_changed_files
            ),
            delivery_human_approval_satisfied_conditions=(
                result.delivery_human_approval_satisfied_conditions
            ),
            delivery_human_approval_blocking_reasons=(
                result.delivery_human_approval_blocking_reasons
            ),
            delivery_human_approval_runs_git=result.delivery_human_approval_runs_git,
            delivery_human_approval_runs_write_git=(
                result.delivery_human_approval_runs_write_git
            ),
            delivery_human_approval_git_add_triggered=(
                result.delivery_human_approval_git_add_triggered
            ),
            delivery_human_approval_git_commit_triggered=(
                result.delivery_human_approval_git_commit_triggered
            ),
            delivery_human_approval_git_push_triggered=(
                result.delivery_human_approval_git_push_triggered
            ),
            delivery_human_approval_pr_opened=result.delivery_human_approval_pr_opened,
            delivery_human_approval_ci_triggered=result.delivery_human_approval_ci_triggered,
            delivery_human_approval_execution_enabled=(
                result.delivery_human_approval_execution_enabled
            ),
            delivery_human_approval_operation_applied=(
                result.delivery_human_approval_operation_applied
            ),
            delivery_human_approval_gate_allows_write=(
                result.delivery_human_approval_gate_allows_write
            ),
            delivery_human_approval_gate_allows_next_guardrail=(
                result.delivery_human_approval_gate_allows_next_guardrail
            ),
            failure_recovery_decision=(
                cls.FailureRecoveryDecisionResponse.from_decision(
                    result.failure_recovery_decision
                )
                if result.failure_recovery_decision is not None
                else None
            ),
            task_id=result.task.id if result.task else None,
            task_title=result.task.title if result.task else None,
            task_status=result.task.status if result.task else None,
            run_id=result.run.id if result.run else None,
            run_status=result.run.status if result.run else None,
            run_created_at=result.run.created_at if result.run else None,
            run_finished_at=result.run.finished_at if result.run else None,
            provider_key=result.run.provider_key if result.run else None,
            prompt_template_key=result.run.prompt_template_key if result.run else None,
            prompt_template_version=result.run.prompt_template_version if result.run else None,
            prompt_char_count=result.run.prompt_char_count if result.run else None,
            token_accounting_mode=result.run.token_accounting_mode if result.run else None,
            provider_receipt_id=result.run.provider_receipt_id if result.run else None,
            total_tokens=result.run.total_tokens if result.run else None,
            token_pricing_source=result.run.token_pricing_source if result.run else None,
            prompt_tokens=result.run.prompt_tokens if result.run else None,
            completion_tokens=result.run.completion_tokens if result.run else None,
            estimated_cost=result.run.estimated_cost if result.run else None,
            log_path=result.run.log_path if result.run else None,
        )


def get_task_worker(
    session: Annotated[Session, Depends(get_db_session)],
) -> TaskWorker:
    """Create the minimal worker graph for one request."""

    return build_task_worker(session=session)


class WorkerSlotResponse(BaseModel):
    """Visible state of one local worker slot."""

    slot_id: int
    state: WorkerSlotState
    worker_name: str | None = None
    task_id: str | None = None
    task_title: str | None = None
    run_id: str | None = None
    acquired_at: str | None = None
    last_task_id: str | None = None
    last_task_title: str | None = None
    last_run_id: str | None = None
    last_released_at: str | None = None

    @classmethod
    def from_status(cls, status: WorkerSlotStatus) -> "WorkerSlotResponse":
        """Convert one slot snapshot into an API DTO."""

        return cls(
            slot_id=status.slot_id,
            state=status.state,
            worker_name=status.worker_name,
            task_id=status.task_id,
            task_title=status.task_title,
            run_id=status.run_id,
            acquired_at=status.acquired_at.isoformat() if status.acquired_at else None,
            last_task_id=status.last_task_id,
            last_task_title=status.last_task_title,
            last_run_id=status.last_run_id,
            last_released_at=(
                status.last_released_at.isoformat() if status.last_released_at else None
            ),
        )


class WorkerSlotSnapshotResponse(BaseModel):
    """Pool-wide worker-slot summary returned to the frontend."""

    max_concurrent_workers: int
    running_slots: int
    idle_slots: int
    slots: list[WorkerSlotResponse]

    @classmethod
    def from_snapshot(
        cls,
        snapshot: WorkerSlotSnapshot,
    ) -> "WorkerSlotSnapshotResponse":
        """Convert one slot snapshot into an API DTO."""

        return cls(
            max_concurrent_workers=snapshot.max_concurrent_workers,
            running_slots=snapshot.running_slots,
            idle_slots=snapshot.idle_slots,
            slots=[WorkerSlotResponse.from_status(slot) for slot in snapshot.slots],
        )


class WorkerPoolRunResponse(BaseModel):
    """API response for one local worker-pool cycle."""

    requested_workers: int
    launched_workers: int
    claimed_runs: int
    idle_workers: int
    results: list[WorkerRunOnceResponse]
    slot_snapshot: WorkerSlotSnapshotResponse

    @classmethod
    def from_result(cls, result: WorkerPoolRunResult) -> "WorkerPoolRunResponse":
        """Convert one pool-cycle result into an API DTO."""

        return cls(
            requested_workers=result.requested_workers,
            launched_workers=result.launched_workers,
            claimed_runs=result.claimed_runs,
            idle_workers=result.idle_workers,
            results=[WorkerRunOnceResponse.from_result(item) for item in result.results],
            slot_snapshot=WorkerSlotSnapshotResponse.from_snapshot(result.slot_snapshot),
        )


router = APIRouter(prefix="/workers", tags=["workers"])


@router.post(
    "/run-once",
    response_model=WorkerRunOnceResponse,
    summary="执行一次 Worker 最小循环",
)
def run_worker_once(
    task_worker: Annotated[TaskWorker, Depends(get_task_worker)],
    project_id: Annotated[UUID | None, Query(description="Optional project scope.")] = None,
) -> WorkerRunOnceResponse:
    """Explicitly trigger one worker cycle.

    When ``project_id`` is provided, the worker routes only within that project.
    """

    result = task_worker.run_once(project_id=project_id)
    return WorkerRunOnceResponse.from_result(result)


@router.post(
    "/run-pool-once",
    response_model=WorkerPoolRunResponse,
    summary="执行一次固定槽位 Worker Pool 循环",
)
def run_worker_pool_once(
    requested_workers: Annotated[int | None, Query(ge=1, le=8)] = None,
) -> WorkerPoolRunResponse:
    """Explicitly trigger one limited-parallel worker-pool cycle."""

    result = worker_pool.run_once(requested_workers=requested_workers)
    return WorkerPoolRunResponse.from_result(result)
