import { useCallback, useEffect, useState } from "react";

import { formatDateTime } from "../../../lib/format";
import {
  fetchRunAiSummary,
  generateRunAiSummary,
  regenerateRunAiSummary,
  type RunAISummaryDTO,
} from "../api/runAiSummary";
import { RunAiSummaryMarkdown } from "./RunAiSummaryMarkdown";

// ── helpers ────────────────────────────────────────────────────────

function truncateHash(hash: string | null | undefined): string | null {
  if (!hash) return null;
  return hash.slice(0, 8);
}

// ── component ──────────────────────────────────────────────────────

type RunAiSummaryCardProps = {
  runId: string;
};

type CardState =
  | { kind: "loading" }
  | { kind: "empty" }
  | { kind: "ready"; summary: RunAISummaryDTO }
  | { kind: "error"; message: string };

export function RunAiSummaryCard({ runId }: RunAiSummaryCardProps) {
  const [cardState, setCardState] = useState<CardState>({ kind: "loading" });
  const [busy, setBusy] = useState(false);

  // ── auto-fetch on runId change ──────────────────────────────
  useEffect(() => {
    let cancelled = false;
    setCardState({ kind: "loading" });
    fetchRunAiSummary(runId)
      .then((res) => {
        if (cancelled) return;
        if (res.active_summary) {
          setCardState({ kind: "ready", summary: res.active_summary });
        } else {
          setCardState({ kind: "empty" });
        }
      })
      .catch((err) => {
        if (cancelled) return;
        setCardState({
          kind: "error",
          message: err instanceof Error ? err.message : "获取 AI 摘要失败",
        });
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
      setCardState({ kind: "ready", summary });
    } catch (err) {
      setCardState({
        kind: "error",
        message: err instanceof Error ? err.message : "生成 AI 摘要失败",
      });
    } finally {
      setBusy(false);
    }
  }, [runId]);

  // ── regenerate ──────────────────────────────────────────────
  const handleRegenerate = useCallback(async () => {
    setBusy(true);
    try {
      const summary = await regenerateRunAiSummary(runId);
      setCardState({ kind: "ready", summary });
    } catch (err) {
      setCardState({
        kind: "error",
        message: err instanceof Error ? err.message : "重新生成 AI 摘要失败",
      });
    } finally {
      setBusy(false);
    }
  }, [runId]);

  // ── render ──────────────────────────────────────────────────
  return (
    <div
      data-testid="run-ai-summary-card"
      className="space-y-4 rounded-lg border border-[#333333] bg-[#0f0f0f]/60 p-4"
    >
      {/* ── A. Header ──────────────────────────────────────── */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-zinc-200">AI 运行摘要</h3>
          <p className="mt-1 text-xs text-zinc-500">
            {cardState.kind === "empty"
              ? "根据本次运行记录生成中文摘要"
              : "已保存，可刷新后继续查看"}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {cardState.kind === "empty" ? (
            <ActionBtn
              data-testid="generate-ai-summary"
              disabled={busy}
              onClick={handleGenerate}
            >
              {busy ? "生成中…" : "生成 AI 摘要"}
            </ActionBtn>
          ) : cardState.kind === "ready" ? (
            <ActionBtn
              data-testid="regenerate-ai-summary"
              disabled={busy}
              onClick={handleRegenerate}
            >
              {busy ? "生成中…" : "重新生成"}
            </ActionBtn>
          ) : cardState.kind === "error" ? (
            <ActionBtn
              data-testid="retry-ai-summary"
              disabled={busy}
              onClick={handleGenerate}
            >
              {busy ? "生成中…" : "重试"}
            </ActionBtn>
          ) : null}
        </div>
      </div>

      {/* ── B. Status strip ─────────────────────────────────── */}
      {cardState.kind === "ready" ? (
        <StatusStrip summary={cardState.summary} />
      ) : null}

      {/* ── C. Body ─────────────────────────────────────────── */}
      <div className="border-t border-[#333333] pt-4">
        {cardState.kind === "loading" ? (
          <p className="text-sm text-zinc-500">正在读取 AI 摘要…</p>
        ) : cardState.kind === "empty" ? (
          <div>
            <p className="text-sm text-zinc-500">
              暂未生成本次运行的 AI 摘要。点击上方"生成 AI 摘要"按钮，系统将根据运行数据生成一份中文摘要。
            </p>
            <p className="mt-2 text-xs text-zinc-600">
              当前阶段由规则引擎生成（rule_fallback），不调用外部 AI 模型。
            </p>
          </div>
        ) : cardState.kind === "error" ? (
          <div className="border-l-2 border-zinc-600 bg-[#0a0a0a] px-3 py-2.5">
            <p className="text-sm text-zinc-400">{cardState.message}</p>
          </div>
        ) : cardState.summary.status === "pending" ? (
          <p className="text-sm text-zinc-500">摘要生成中，请稍后刷新查看…</p>
        ) : cardState.summary.status === "failed" ? (
          <div>
            <div className="border-l-2 border-zinc-600 bg-[#0a0a0a] px-3 py-2.5">
              <h4 className="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-400">
                生成失败
              </h4>
              <p className="mt-2 text-sm text-zinc-400">
                {cardState.summary.error_summary ?? "未记录失败原因"}
              </p>
            </div>
            <div className="mt-3">
              <ActionBtn
                data-testid="retry-after-failed-ai-summary"
                disabled={busy}
                onClick={handleRegenerate}
              >
                {busy ? "生成中…" : "重新生成"}
              </ActionBtn>
            </div>
          </div>
        ) : (
          <RunAiSummaryMarkdown markdown={cardState.summary.summary_markdown} />
        )}
      </div>

      {/* ── D. Footer ────────────────────────────────────────── */}
      {cardState.kind === "ready" ? (
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

function StatusStrip({ summary }: { summary: RunAISummaryDTO }) {
  const tags: { label: string; key: string }[] = [];

  if (summary.source === "rule_fallback") {
    tags.push({ label: "规则回退摘要 · 尚未调用真实 AI", key: "source" });
  } else {
    tags.push({ label: "AI 生成摘要", key: "source" });
  }

  if (summary.stale) {
    tags.push({ label: "摘要可能已过期", key: "stale" });
  }

  if (summary.generated_at) {
    tags.push({
      label: `生成时间：${formatDateTime(summary.generated_at)}`,
      key: "generated_at",
    });
  }

  const fp8 = truncateHash(summary.source_fingerprint);
  const ph8 = truncateHash(summary.prompt_hash);

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-500">
      {tags.map((t) => (
        <span key={t.key}>{t.label}</span>
      ))}
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

function ActionBtn({
  children,
  disabled,
  onClick,
  ...rest
}: {
  children: React.ReactNode;
  disabled?: boolean;
  onClick: () => void;
  "data-testid"?: string;
}) {
  return (
    <button
      type="button"
      data-testid={rest["data-testid"]}
      disabled={disabled}
      onClick={onClick}
      className="rounded border border-[#4a4a4a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:border-zinc-500 hover:bg-[#292929] disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {children}
    </button>
  );
}
