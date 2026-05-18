import { useCallback, useEffect, useState } from "react";

import { formatDateTime } from "../../../lib/format";
import type { RunUserSummary } from "../lib/runUserSummary";
import {
  fetchRunAiSummary,
  generateRunAiSummary,
  regenerateRunAiSummary,
  type AiSummaryError,
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
  | { kind: "unavailable"; fetchError: AiSummaryError | null }
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
  const [lastActionError, setLastActionError] =
    useState<AiSummaryError | null>(null);

  // ── auto-fetch on runId change ──────────────────────────────
  useEffect(() => {
    let cancelled = false;
    setAiState({ kind: "loading" });
    setLastActionError(null);

    fetchRunAiSummary(runId)
      .then((res) => {
        if (cancelled) return;
        if (res.active_summary) {
          setAiState({ kind: "ready", summary: res.active_summary });
        } else {
          setAiState({ kind: "empty" });
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const classified = err as AiSummaryError;
        setAiState({
          kind: "unavailable",
          fetchError: classified,
        });
      });

    return () => {
      cancelled = true;
    };
  }, [runId]);

  // ── generate ────────────────────────────────────────────────
  const handleGenerate = useCallback(async () => {
    setBusy(true);
    setLastActionError(null);
    try {
      const summary = await generateRunAiSummary(runId);
      setAiState({ kind: "ready", summary });
    } catch (err: unknown) {
      const classified = err as AiSummaryError;
      setLastActionError(classified);
    } finally {
      setBusy(false);
    }
  }, [runId]);

  // ── regenerate ──────────────────────────────────────────────
  const handleRegenerate = useCallback(async () => {
    setBusy(true);
    setLastActionError(null);
    try {
      const summary = await regenerateRunAiSummary(runId);
      setAiState({ kind: "ready", summary });
    } catch (err: unknown) {
      const classified = err as AiSummaryError;
      setLastActionError(classified);
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

  // Short header subtitle — source-aware
  const subtitle = (() => {
    if (aiState.kind === "loading") return "正在检查运行摘要…";
    if (aiSucceeded) {
      if (aiState.summary.source === "rule_fallback") {
        return "摘要已保存，当前由规则回退生成，刷新页面不会丢失。";
      }
      return "摘要已保存，刷新页面不会丢失。";
    }
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
          重新生成摘要
        </button>
      );
    }

    if (aiFailed || aiState.kind === "empty" || aiState.kind === "unavailable") {
      return (
        <button
          type="button"
          data-testid="primary-generate-run-summary"
          onClick={handleGenerate}
          className="rounded border border-[#4a4a4a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:border-zinc-500 hover:bg-[#292929]"
        >
          生成运行摘要
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

      {/* ── Status hints (body area, shown only once per state) ── */}
      {aiState.kind === "unavailable" ? (
        <HintBox>
          {aiState.fetchError
            ? aiState.fetchError.userMessage
            : "运行摘要服务暂不可用，当前显示本地规则摘要。"}
        </HintBox>
      ) : null}

      {aiState.kind === "empty" ? (
        <HintBox>
          当前显示本地规则摘要。可以生成一份可保存的运行摘要，刷新页面后仍可查看。
        </HintBox>
      ) : null}

      {aiPending ? (
        <HintBox>
          摘要生成中，当前先显示本地规则摘要。
        </HintBox>
      ) : null}

      {aiFailed ? (
        <HintBox>
          摘要生成失败，当前显示本地规则摘要。
          {aiState.summary.error_summary ? (
            <span className="block mt-1 text-zinc-600">
              {aiState.summary.error_summary}
            </span>
          ) : null}
        </HintBox>
      ) : null}

      {/* ── Action error hint (generate/regenerate failure) ──── */}
      {lastActionError ? (
        <HintBox>
          {lastActionError.userMessage}
        </HintBox>
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
            {aiState.summary.source === "rule_fallback"
              ? "当前阶段的保存摘要由规则回退生成；真实 AI 摘要将在后续阶段接入。"
              : "当前摘要来自后端保存记录，刷新页面不会丢失。"}
          </p>
        </div>
      ) : null}
    </div>
  );
}

// ── sub-components ──────────────────────────────────────────────────

function HintBox({ children }: { children: React.ReactNode }) {
  return (
    <div className="border-t border-[#333333] pt-3">
      <p className="text-xs text-zinc-500">{children}</p>
    </div>
  );
}

function AiStatusStrip({ summary }: { summary: RunAISummaryDTO }) {
  const fp8 = truncateHash(summary.source_fingerprint);
  const ph8 = truncateHash(summary.prompt_hash);

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-500">
      {summary.source === "rule_fallback" ? (
        <span>摘要来源：规则回退 · 尚未调用真实 AI</span>
      ) : (
        <span>
          摘要来源：AI 生成
          {summary.model_provider || summary.model_name ? (
            <> · {summary.model_provider || summary.model_name}</>
          ) : null}
        </span>
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
