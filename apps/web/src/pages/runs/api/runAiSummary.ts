import { requestJson } from "../../../lib/http";

// ── Types (mirrors backend RunAISummaryResponse / RunAISummaryCurrentResponse) ──

export type RunAISummaryDTO = {
  id: string;
  run_id: string;
  project_id: string | null;
  task_id: string | null;
  deliverable_id: string | null;
  summary_type: string;
  status: "pending" | "succeeded" | "failed";
  source: "ai" | "rule_fallback";
  summary_markdown: string;
  source_version: string;
  source_fingerprint: string;
  source_hash: string;
  model_provider: string | null;
  model_name: string | null;
  prompt_hash: string;
  provider_receipt_id: string | null;
  generated_at: string;
  created_at: string;
  updated_at: string;
  error_summary: string | null;
  stale: boolean;
};

export type RunAISummaryCurrentResponse = {
  run_id: string;
  active_summary: RunAISummaryDTO | null;
};

// ── API functions ──────────────────────────────────────────────────

/** GET /runs/{run_id}/ai-summary — fetch current active summary */
export function fetchRunAiSummary(runId: string): Promise<RunAISummaryCurrentResponse> {
  return requestJson<RunAISummaryCurrentResponse>(`/runs/${runId}/ai-summary`);
}

/** POST /runs/{run_id}/ai-summary/generate — create or reuse active summary */
export function generateRunAiSummary(runId: string): Promise<RunAISummaryDTO> {
  return requestJson<RunAISummaryDTO>(`/runs/${runId}/ai-summary/generate`, {
    method: "POST",
  });
}

/** POST /runs/{run_id}/ai-summary/regenerate — force new summary */
export function regenerateRunAiSummary(runId: string): Promise<RunAISummaryDTO> {
  return requestJson<RunAISummaryDTO>(`/runs/${runId}/ai-summary/regenerate`, {
    method: "POST",
  });
}
