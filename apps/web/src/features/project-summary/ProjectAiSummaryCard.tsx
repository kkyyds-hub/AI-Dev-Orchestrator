import { useCallback, useEffect, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { RunAiSummaryMarkdown } from "../../pages/runs/components/RunAiSummaryMarkdown";
import {
  fetchProjectAiSummary,
  generateProjectAiSummary,
  regenerateProjectAiSummary,
} from "./api";
import type { ProjectAiSummary } from "./types";

type ProjectAiSummaryCardProps = {
  projectId: string | null;
};

type ProjectAiSummaryState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "empty" }
  | { kind: "ready"; summary: ProjectAiSummary }
  | { kind: "error"; message: string };

function toErrorMessage(error: unknown): string {
  return error instanceof Error && error.message.trim()
    ? `项目总结暂时不可用：${error.message}`
    : "项目总结暂时不可用，请稍后重试。";
}

export function ProjectAiSummaryCard({ projectId }: ProjectAiSummaryCardProps) {
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<ProjectAiSummaryState>({ kind: "idle" });
  const [busyAction, setBusyAction] = useState<"generate" | "regenerate" | null>(
    null,
  );

  useEffect(() => {
    setOpen(false);
    setState({ kind: "idle" });
    setBusyAction(null);
  }, [projectId]);

  const loadSummary = useCallback(async () => {
    if (!projectId) {
      return;
    }

    setState({ kind: "loading" });
    try {
      const response = await fetchProjectAiSummary(projectId);
      setState(
        response.active_summary
          ? { kind: "ready", summary: response.active_summary }
          : { kind: "empty" },
      );
    } catch (error) {
      setState({ kind: "error", message: toErrorMessage(error) });
    }
  }, [projectId]);

  const readbackSummary = useCallback(async () => {
    if (!projectId) {
      return;
    }

    const response = await fetchProjectAiSummary(projectId);
    setState(
      response.active_summary
        ? { kind: "ready", summary: response.active_summary }
        : { kind: "empty" },
    );
  }, [projectId]);

  const handleToggle = useCallback(() => {
    const nextOpen = !open;
    setOpen(nextOpen);
    if (nextOpen && state.kind === "idle") {
      void loadSummary();
    }
  }, [loadSummary, open, state.kind]);

  const handleGenerate = useCallback(async () => {
    if (!projectId) {
      return;
    }

    setBusyAction("generate");
    try {
      await generateProjectAiSummary(projectId);
      await readbackSummary();
    } catch (error) {
      setState({ kind: "error", message: toErrorMessage(error) });
    } finally {
      setBusyAction(null);
    }
  }, [projectId, readbackSummary]);

  const handleRegenerate = useCallback(async () => {
    if (!projectId) {
      return;
    }

    setBusyAction("regenerate");
    try {
      await regenerateProjectAiSummary(projectId);
      await readbackSummary();
    } catch (error) {
      setState({ kind: "error", message: toErrorMessage(error) });
    } finally {
      setBusyAction(null);
    }
  }, [projectId, readbackSummary]);

  if (!projectId) {
    return null;
  }

  const isBusy = busyAction !== null;
  const readySummary = state.kind === "ready" ? state.summary : null;
  const sourceBadge =
    readySummary?.source === "rule_fallback"
      ? { label: "规则回退", tone: "warning" as const }
      : { label: "AI 生成", tone: "success" as const };

  return (
    <section
      className="mt-4 rounded-lg border border-[#333333] bg-[#111111]/70 p-4"
      data-testid="project-ai-summary-card"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-zinc-100">项目总结</h4>
          <p className="mt-1 text-xs text-zinc-500">
            读取已保存的项目总结；生成或重新生成后会自动刷新最新结果。
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {open && (state.kind === "empty" || state.kind === "error") ? (
            <button
              type="button"
              onClick={handleGenerate}
              disabled={isBusy}
              className="rounded border border-[#4a4a4a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:border-zinc-500 hover:bg-[#292929] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busyAction === "generate" ? "生成中..." : "生成项目总结"}
            </button>
          ) : null}

          {open && state.kind === "ready" ? (
            <button
              type="button"
              onClick={handleRegenerate}
              disabled={isBusy}
              className="rounded border border-[#4a4a4a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:border-zinc-500 hover:bg-[#292929] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busyAction === "regenerate" ? "重新生成中..." : "重新生成项目总结"}
            </button>
          ) : null}

          <button
            type="button"
            onClick={handleToggle}
            className="rounded border border-[#4a4a4a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:border-zinc-500 hover:bg-[#292929]"
          >
            {open ? "收起项目总结" : "查看项目总结"}
          </button>
        </div>
      </div>

      {open ? (
        <div className="mt-4 border-t border-[#333333] pt-4">
          {state.kind === "loading" ? (
            <p className="text-sm text-zinc-500">正在读取项目总结...</p>
          ) : null}

          {state.kind === "empty" ? (
            <p className="text-sm leading-6 text-zinc-500">
              当前还没有已保存的项目总结。点击“生成项目总结”后，可在这里查看最新读回结果。
            </p>
          ) : null}

          {state.kind === "error" ? (
            <p className="text-sm text-rose-200">{state.message}</p>
          ) : null}

          {state.kind === "ready" ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge
                  label={sourceBadge.label}
                  tone={sourceBadge.tone}
                />
                {state.summary.stale ? (
                  <StatusBadge label="摘要可能已过期" tone="warning" />
                ) : null}
                <span className="text-xs text-zinc-500">
                  生成时间：{formatDateTime(state.summary.generated_at)}
                </span>
              </div>

              {state.summary.status === "pending" ? (
                <p className="text-sm leading-6 text-zinc-400">
                  项目总结生成中，请稍后重新打开查看。
                </p>
              ) : state.summary.status === "failed" ? (
                <p className="text-sm leading-6 text-rose-200">
                  项目总结生成失败，请稍后重试。
                  {state.summary.error_summary ? ` ${state.summary.error_summary}` : ""}
                </p>
              ) : (
                <RunAiSummaryMarkdown markdown={state.summary.summary_markdown} />
              )}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
