import type { TaskDetail } from "../../task-detail/types";
import type {
  BossDrilldownContext,
  BossDrilldownEventDetail,
  BossDrilldownSource,
  BossProjectLatestTask,
} from "../types";

export function buildBossDrilldownHash(detail: BossDrilldownContext): string {
  const params = new URLSearchParams();
  params.set("source", detail.source);
  params.set("taskId", detail.task_id);
  if (detail.project_id) {
    params.set("projectId", detail.project_id);
  }
  if (detail.run_id) {
    params.set("runId", detail.run_id);
  }
  return `#boss-drilldown?${params.toString()}`;
}

export function parseBossDrilldownHash(
  hashValue: string,
): BossDrilldownEventDetail | null {
  if (!hashValue.startsWith("#boss-drilldown")) {
    return null;
  }
  const queryIndex = hashValue.indexOf("?");
  const searchValue = queryIndex >= 0 ? hashValue.slice(queryIndex + 1) : "";
  const params = new URLSearchParams(searchValue);
  const taskId = params.get("taskId");
  if (!taskId) {
    return null;
  }

  return {
    source: (params.get("source") as BossDrilldownSource | null) ?? "home_latest_run",
    projectId: params.get("projectId"),
    taskId,
    runId: params.get("runId"),
  };
}

export function buildTaskSampleFromDetail(
  detail: TaskDetail,
  preferredRunId: string | null,
): BossProjectLatestTask | null {
  const matchedRun =
    (preferredRunId
      ? detail.runs.find((run) => run.id === preferredRunId)
      : null) ?? detail.latest_run;
  if (!matchedRun) {
    return null;
  }

  return {
    task_id: detail.id,
    title: detail.title,
    status: detail.status,
    priority: detail.priority,
    risk_level: detail.risk_level,
    human_status: detail.human_status,
    updated_at: detail.updated_at,
    latest_run_status: matchedRun.status,
    latest_run_summary: matchedRun.result_summary,
    latest_run_id: matchedRun.id,
    latest_run_log_path: matchedRun.log_path,
    latest_run_model_name: null,
    latest_run_model_tier: null,
    latest_run_strategy_code: null,
    latest_run_provider_key: matchedRun.provider_key,
    latest_run_prompt_template_key: matchedRun.prompt_template_key,
    latest_run_prompt_template_version: matchedRun.prompt_template_version,
    latest_run_prompt_char_count: matchedRun.prompt_char_count,
    latest_run_token_accounting_mode: matchedRun.token_accounting_mode,
    latest_run_token_pricing_source: matchedRun.token_pricing_source,
    latest_run_provider_receipt_id: matchedRun.provider_receipt_id,
    latest_run_prompt_tokens: matchedRun.prompt_tokens,
    latest_run_completion_tokens: matchedRun.completion_tokens,
    latest_run_total_tokens: matchedRun.total_tokens,
    latest_run_estimated_cost: matchedRun.estimated_cost,
    latest_run_created_at: matchedRun.created_at,
    latest_run_finished_at: matchedRun.finished_at,
    latest_run_role_model_policy_source: matchedRun.role_model_policy_source,
    latest_run_role_model_policy_desired_tier:
      matchedRun.role_model_policy_desired_tier,
    latest_run_role_model_policy_adjusted_tier:
      matchedRun.role_model_policy_adjusted_tier,
    latest_run_role_model_policy_final_tier:
      matchedRun.role_model_policy_final_tier,
    latest_run_role_model_policy_stage_override_applied:
      matchedRun.role_model_policy_stage_override_applied,
  };
}
