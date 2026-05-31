import { useCallback, useEffect, useState } from "react";

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
  return error instanceof Error
    ? error.message
    : "Project AI summary is temporarily unavailable.";
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
      const summary = await generateProjectAiSummary(projectId);
      setState({ kind: "ready", summary });
    } catch (error) {
      setState({ kind: "error", message: toErrorMessage(error) });
    } finally {
      setBusyAction(null);
    }
  }, [projectId]);

  const handleRegenerate = useCallback(async () => {
    if (!projectId) {
      return;
    }

    setBusyAction("regenerate");
    try {
      const summary = await regenerateProjectAiSummary(projectId);
      setState({ kind: "ready", summary });
    } catch (error) {
      setState({ kind: "error", message: toErrorMessage(error) });
    } finally {
      setBusyAction(null);
    }
  }, [projectId]);

  if (!projectId) {
    return null;
  }

  const isBusy = busyAction !== null;

  return (
    <section
      className="mt-4 rounded-lg border border-[#333333] bg-[#111111]/70 p-4"
      data-testid="project-ai-summary-card"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-zinc-100">AI Summary</h4>
          <p className="mt-1 text-xs text-zinc-500">
            GET only reads the current persisted summary. Generate and regenerate
            save a local rule-fallback snapshot for readback.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {open && state.kind === "empty" ? (
            <button
              type="button"
              onClick={handleGenerate}
              disabled={isBusy}
              className="rounded border border-[#4a4a4a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:border-zinc-500 hover:bg-[#292929] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busyAction === "generate" ? "Generating..." : "Generate Project Summary"}
            </button>
          ) : null}

          {open && state.kind === "ready" ? (
            <button
              type="button"
              onClick={handleRegenerate}
              disabled={isBusy}
              className="rounded border border-[#4a4a4a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:border-zinc-500 hover:bg-[#292929] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busyAction === "regenerate" ? "Regenerating..." : "Regenerate Summary"}
            </button>
          ) : null}

          <button
            type="button"
            onClick={handleToggle}
            className="rounded border border-[#4a4a4a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:border-zinc-500 hover:bg-[#292929]"
          >
            {open ? "Hide AI Summary" : "View AI Summary"}
          </button>
        </div>
      </div>

      {open ? (
        <div className="mt-4 border-t border-[#333333] pt-4">
          {state.kind === "loading" ? (
            <p className="text-sm text-zinc-500">Loading project summary...</p>
          ) : null}

          {state.kind === "empty" ? (
            <p className="text-sm leading-6 text-zinc-500">
              No saved project summary yet. Generate one to persist a snapshot and
              make it available through GET readback.
            </p>
          ) : null}

          {state.kind === "error" ? (
            <p className="text-sm text-rose-200">{state.message}</p>
          ) : null}

          {state.kind === "ready" ? (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-500">
                <span>Source: {state.summary.source}</span>
                <span>Provider: {state.summary.model_provider ?? "local"}</span>
                <span>Model: {state.summary.model_name ?? "rule-fallback"}</span>
                <span>
                  Triggered live AI: {state.summary.triggered_ai ? "yes" : "no"}
                </span>
                <span>Generated at: {formatDateTime(state.summary.generated_at)}</span>
              </div>
              <RunAiSummaryMarkdown markdown={state.summary.summary_markdown} />
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
