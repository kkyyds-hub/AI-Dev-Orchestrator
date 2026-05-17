import { useCallback, useEffect, useState } from "react";

import { formatDateTime } from "../../../lib/format";
import type { RunUserSummary } from "../lib/runUserSummary";
import {
  fetchRunAiSummary,
  generateRunAiSummary,
  regenerateRunAiSummary,
  type RunAISummaryDTO,
} from "../api/runAiSummary";
import { RunAiSummaryMarkdown } from "./RunAiSummaryMarkdown";
import { RunUserSummaryContent } from "./RunUserSummaryCard";

// ── helpers ────────────────────────────────────────────────────────

function truncateHash(hash: string | null | undefined): string | null {
  if (!hash) return null;
  return hash.slice(0, 8);
}

// ── AI summary state machine ────────────────────────────────────────

type AiState =
  | { kind: "loading" }
  | { kind: "unavailable" }
  | { kind: "empty" }
  | { kind: "ready"; summary: RunAISummaryDTO }
  | { kind: "failed"; errorSummary: string | null };

// ── component ──────────────────────────────────────────────────────

type RunPrimarySummaryCardProps = {
  runId: string;
  fallbackSummary: RunUserSummary;
};

export function RunPrimarySummaryCard({
  runId,
  fallbackSummary,
}: RunPrimarySummaryCardProps) {
  const [aiState, setAiState] = useState<AiState>({ kind: "loading" });
  const [busy, setBusy] = useState(false);

  // ── auto-fetch on runId change ──────────────────────────────
  useEffect(() => {
    let cancelled = false;
    setAiState({ kind: "loading" });

    fetchRunAiSummary(runId)
      .then((res) => {
        if (cancelled) return;
        if (res.active_summary) {
          setAiState({ kind: "ready", summary: res.active_summary });
        } else {
          setAiState({ kind: "empty" });
        }
      })
      .catch(() => {
        if (cancelled) return;
        setAiState({ kind: "unavailable" });
      });

    return () => {
      cancelled = true;
    };
  }, [runId]);

  // ── generate ────────────────────────────────────────────────
  const handleGenerate = useCallback(async () => {
    setBusy(true);
    try {
      const summary = await generateRunAiSummary(runId);
      setAiState({ kind: "ready", summary });
    } catch {
      // keep existing state, show brief error status
    } finally {
      setBusy(false);
    }
  }, [runId]);

  // ── regenerate ──────────────────────────────────────────────
  const handleRegenerate = useCallback(async () => {
    setBusy(true);
    try {
      const summary = await regenerateRunAiSummary(runId);
      setAiState({ kind: "ready", summary });
    } catch {
      // keep existing state, show brief error status
    } finally {
      setBusy(false);
    }
  }, [runId]);

  // ── derived flags ───────────────────────────────────────────
  const aiReady = aiState.kind === "ready";
  const aiSucceeded = aiReady && aiState.summary.status === "succeeded";
  const aiFailed = aiReady && aiState.summary.status === "failed";
  const aiPending = aiReady && aiState.summary.status === "pending";
  const aiStale = aiReady && aiState.summary.stale;
  const showAiMarkdown = aiSucceeded;

  const subtitle = (() => {
    if (aiSucceeded) return "AI 摘要已保存，刷新页面不会丢失";
    if (aiState.kind === "unavailable") return "AI 摘要服务暂不可用，当前显示本地规则摘要";
    if (aiFailed) return "AI 摘要生成失败，当前显示本地规则摘要";
    if (aiState.kind === "empty") return "当前显示本地规则摘要，可生成 AI 摘要";
    return "当前显示本地规则摘要";
  })();

  const headerRight = (() => {
    if (busy) {
      return (
        <button
          type="button"
          disabled
          data-testid="ai-summary-busy"
          className="rounded border border-[#4a4a4a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          生成中…
        </button>
      );
    }

    if (aiSucceeded || aiStale) {
      return (
        <button
          type="button"
          data-testid="primary-regenerate-ai-summary"
          onClick={handleRegenerate}
          className="rounded border border-[#4a4a4a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:border-zinc-500 hover:bg-[#292929]"
        >
          重新生成
        </button>
      );
    }

    if (aiFailed || aiState.kind === "empty" || aiState.kind === "unavailable") {
      return (
        <button
          type="button"
          data-testid="primary-generate-ai-summary"
          onClick={handleGenerate}
          className="rounded border border-[#4a4a4a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:border-zinc-500 hover:bg-[#292929]"
        >
          生成 AI 摘要
        </button>
      );
    }

    // loading — no button yet
    return null;
  })();

  // ── render ──────────────────────────────────────────────────
  return (
    <div
      data-testid="run-primary-summary-card"
      className="space-y-4 rounded-lg border border-[#333333] bg-[#0f0f0f]/60 p-4"
    >
      {/* ── Header ────────────────────────────────────────── */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-zinc-200">运行摘要</h3>
          <p className="mt-1 text-xs text-zinc-500">{subtitle}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">{headerRight}</div>
      </div>

      {/* ── AI status strip (only when AI summary present) ─── */}
      {aiReady ? <AiStatusStrip summary={aiState.summary} /> : null}

      {/* ── AI unavailable hint ────────────────────────────── */}
      {aiState.kind === "unavailable" ? (
        <div className="border-t border-[#333333] pt-3">
          <p className="text-xs text-zinc-500">
            AI 摘要服务暂不可用，当前显示本地规则摘要。
          </p>
        </div>
      ) : null}

      {/* ── AI pending hint ────────────────────────────────── */}
      {aiPending ? (
        <div className="border-t border-[#333333] pt-3">
          <p className="text-xs text-zinc-500">
            AI 摘要生成中，当前先显示本地规则摘要。
          </p>
        </div>
      ) : null}

      {/* ── AI failed hint ─────────────────────────────────── */}
      {aiFailed ? (
        <div className="border-t border-[#333333] pt-3">
          <p className="text-xs text-zinc-500">
            AI 摘要生成失败，当前显示本地规则摘要。
          </p>
          {aiState.summary.error_summary ? (
            <p className="mt-1 text-xs text-zinc-600">
              {aiState.summary.error_summary}
            </p>
          ) : null}
        </div>
      ) : null}

      {/* ── Body: AI markdown or fallback ──────────────────── */}
      <div className="border-t border-[#333333] pt-4">
        {showAiMarkdown ? (
          <RunAiSummaryMarkdown markdown={aiState.summary.summary_markdown} />
        ) : (
          <RunUserSummaryContent summary={fallbackSummary} />
        )}
      </div>

      {/* ── Footer ─────────────────────────────────────────── */}
      {aiReady ? (
        <div className="border-t border-[#333333] pt-3">
          <p className="text-xs text-zinc-600">
            当前摘要来自后端保存记录，刷新页面不会丢失。
          </p>
        </div>
      ) : null}
    </div>
  );
}

// ── sub-components ──────────────────────────────────────────────────

function AiStatusStrip({ summary }: { summary: RunAISummaryDTO }) {
  const fp8 = truncateHash(summary.source_fingerprint);
  const ph8 = truncateHash(summary.prompt_hash);

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-500">
      {summary.source === "rule_fallback" ? (
        <span>规则回退摘要 · 尚未调用真实 AI</span>
      ) : (
        <span>AI 生成摘要</span>
      )}
      {summary.stale ? <span>摘要可能已过期</span> : null}
      {summary.generated_at ? (
        <span>生成时间：{formatDateTime(summary.generated_at)}</span>
      ) : null}
      {fp8 ? (
        <span
          className="font-mono text-zinc-600"
          title={`完整指纹：${summary.source_fingerprint}`}
        >
          指纹 {fp8}…
        </span>
      ) : null}
      {ph8 ? (
        <span
          className="font-mono text-zinc-600"
          title={`完整哈希：${summary.prompt_hash}`}
        >
          提示词 {ph8}…
        </span>
      ) : null}
    </div>
  );
}
