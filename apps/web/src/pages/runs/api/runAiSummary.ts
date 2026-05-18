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

// ── Error classification ────────────────────────────────────────────

export type AiSummaryErrorCategory =
  | "not_found"
  | "server_error"
  | "network_error"
  | "unknown";

export type AiSummaryError = {
  action: "fetch" | "generate" | "regenerate";
  category: AiSummaryErrorCategory;
  userMessage: string;
  debugMessage: string;
};

function classifyError(
  action: AiSummaryError["action"],
  err: unknown,
): AiSummaryError {
  const msg =
    err instanceof Error ? err.message : String(err ?? "");

  const lowerMsg = msg.toLowerCase();

  // 404 / Not Found
  if (
    lowerMsg.includes("404") ||
    lowerMsg.includes("not found") ||
    lowerMsg.includes("not_found")
  ) {
    return {
      action,
      category: "not_found",
      userMessage:
        "运行摘要接口暂不可用。请确认后端服务已重启到包含 /runs/{run_id}/ai-summary 的版本，且当前运行记录存在。",
      debugMessage: msg,
    };
  }

  // 5xx server error
  if (
    lowerMsg.includes("500") ||
    lowerMsg.includes("502") ||
    lowerMsg.includes("503") ||
    lowerMsg.includes("server error") ||
    lowerMsg.includes("internal server")
  ) {
    return {
      action,
      category: "server_error",
      userMessage:
        "摘要生成失败，后端返回错误。当前继续显示本地规则摘要。",
      debugMessage: msg,
    };
  }

  // Network / fetch error
  if (
    lowerMsg.includes("network") ||
    lowerMsg.includes("fetch") ||
    lowerMsg.includes("timeout") ||
    lowerMsg.includes("abort") ||
    lowerMsg.includes("econnrefused") ||
    lowerMsg.includes("failed to fetch")
  ) {
    return {
      action,
      category: "network_error",
      userMessage:
        "无法连接运行摘要服务，当前继续显示本地规则摘要。",
      debugMessage: msg,
    };
  }

  // Unknown
  return {
    action,
    category: "unknown",
    userMessage: "运行摘要暂时不可用，当前继续显示本地规则摘要。",
    debugMessage: msg,
  };
}

// ── API functions (with error classification) ───────────────────────

/** GET /runs/{run_id}/ai-summary — fetch current active summary */
export function fetchRunAiSummary(
  runId: string,
): Promise<RunAISummaryCurrentResponse> {
  return requestJson<RunAISummaryCurrentResponse>(
    `/runs/${runId}/ai-summary`,
  ).catch((err) => {
    const classified = classifyError("fetch", err);
    console.warn("[ai-summary fetch]", classified.debugMessage);
    throw classified;
  });
}

/** POST /runs/{run_id}/ai-summary/generate — create or reuse active summary */
export function generateRunAiSummary(
  runId: string,
): Promise<RunAISummaryDTO> {
  return requestJson<RunAISummaryDTO>(
    `/runs/${runId}/ai-summary/generate`,
    { method: "POST" },
  ).catch((err) => {
    const classified = classifyError("generate", err);
    console.warn("[ai-summary generate]", classified.debugMessage);
    throw classified;
  });
}

/** POST /runs/{run_id}/ai-summary/regenerate — force new summary */
export function regenerateRunAiSummary(
  runId: string,
): Promise<RunAISummaryDTO> {
  return requestJson<RunAISummaryDTO>(
    `/runs/${runId}/ai-summary/regenerate`,
    { method: "POST" },
  ).catch((err) => {
    const classified = classifyError("regenerate", err);
    console.warn("[ai-summary regenerate]", classified.debugMessage);
    throw classified;
  });
}
