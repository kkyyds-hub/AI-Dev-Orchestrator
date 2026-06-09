import { requestJson } from "../../lib/http";
import type {
  RealGitWritePilotApprovalReadback,
  RealGitWritePilotApprovalReadbackRequest,
  RealGitWritePilotDryRunPlan,
} from "./types";

export function buildSafeDryRunPlanSample(pilotId: string): RealGitWritePilotDryRunPlan {
  const now = new Date().toISOString();

  return {
    pilot_id: pilotId,
    readiness_ready_for_preview: true,
    preview_status: "approval_required",
    gate_snapshot_summary: {
      total_gates: 17,
      passed_gates: 12,
      blocked_gates: 0,
      pending_gates: 5,
      not_applicable_gates: 0,
      all_passed: false,
      blocking_reasons: [],
    },
    semantic_steps: [
      {
        step_id: `${pilotId}-dry-run-step-1`,
        step_order: 1,
        step_kind: "verify_executor_readiness_readback",
        safe_summary: "verify executor readiness readback",
        requires_human_confirmation: false,
        produces_repository_side_effect: false,
      },
      {
        step_id: `${pilotId}-dry-run-step-2`,
        step_order: 2,
        step_kind: "verify_workspace_binding_readback",
        safe_summary: "verify workspace binding readback",
        requires_human_confirmation: false,
        produces_repository_side_effect: false,
      },
      {
        step_id: `${pilotId}-dry-run-step-3`,
        step_order: 3,
        step_kind: "wait_for_manual_approval",
        safe_summary: "wait for manual approval",
        requires_human_confirmation: true,
        produces_repository_side_effect: false,
      },
    ],
    forbidden_operations: [
      "raw shell execution",
      "direct main write",
      "git force push",
      "automatic PR creation",
      "automatic merge",
      "branch delete",
      "reset hard",
      "tag creation",
      "stash operation",
    ],
    rollback_plan_summary: "Rollback remains a contract-only plan; no cleanup was run.",
    audit_event_summaries: [
      "Dry-run plan sample prepared for frontend approval readback.",
      "No executor launch, repository write, or host workspace inspection occurred.",
    ],
    dry_run_ready: true,
    ready_for_execution: false,
    product_runtime_git_write_executed: false,
    real_executor_started: false,
    created_at: now,
  };
}

export function createApprovalReadbackRequest(input: {
  pilotId: string;
  approvedBy: string;
  approvalPhrase: string;
  approvedScopeSummary: string;
  expiresAt: string;
}): RealGitWritePilotApprovalReadbackRequest {
  return {
    pilot_id: input.pilotId,
    dry_run_plan: buildSafeDryRunPlanSample(input.pilotId),
    approved_by: input.approvedBy,
    approval_phrase: input.approvalPhrase,
    approved_scope_summary: input.approvedScopeSummary,
    requested_at: new Date().toISOString(),
    expires_at: input.expiresAt,
  };
}

export function recordRealGitWritePilotApprovalReadback(
  payload: RealGitWritePilotApprovalReadbackRequest,
): Promise<RealGitWritePilotApprovalReadback> {
  return requestJson<RealGitWritePilotApprovalReadback>(
    "/real-git-write-pilot/approval-readback",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}
