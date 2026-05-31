export type ProjectAiSummary = {
  id: string;
  project_id: string;
  status: "pending" | "succeeded" | "failed" | string;
  source: "ai" | "rule_fallback" | string;
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
  triggered_ai: boolean;
};

export type ProjectAiSummaryCurrentResponse = {
  project_id: string;
  active_summary: ProjectAiSummary | null;
};
