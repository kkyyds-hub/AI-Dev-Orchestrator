import { useState } from "react";

import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import {
  useMemoryGovernanceCompact,
  useMemoryGovernanceProbe,
  useMemoryGovernanceRehydrate,
  useMemoryGovernanceReset,
  useMemoryGovernanceState,
} from "../hooks";
import type { MemoryGovernanceRunOnceEcho } from "../types";

type MemoryGovernanceSectionProps = {
  projectId: string | null;
  projectName: string | null;
};

type ActionFeedbackTone = "success" | "warning" | "danger";

export function MemoryGovernanceSection(props: MemoryGovernanceSectionProps) {
  const stateQuery = useMemoryGovernanceState(props.projectId);
  const rehydrateMutation = useMemoryGovernanceRehydrate(props.projectId);
  const compactMutation = useMemoryGovernanceCompact(props.projectId);
  const resetMutation = useMemoryGovernanceReset(props.projectId);
  const probeMutation = useMemoryGovernanceProbe(props.projectId);

  const [compactTargetChars, setCompactTargetChars] = useState("900");
  const [actionFeedback, setActionFeedback] = useState<{
    tone: ActionFeedbackTone;
    text: string;
  } | null>(null);
  const [latestProbe, setLatestProbe] = useState<MemoryGovernanceRunOnceEcho | null>(
    null,
  );

  if (!props.projectId) {
    return (
      <section
        id="memory-governance-control-surface"
        data-testid="memory-governance-control-surface"
        className="space-y-3 border-b border-[#333333] pb-5"
      >
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">
          记忆治理
        </p>
        <h2 className="text-2xl font-semibold text-zinc-50">治理状态观察与动作入口</h2>
        <p className="text-sm leading-6 text-zinc-400">
          先选择项目，再查看 checkpoint、summary、risk 与手动 rehydrate/compact/reset
          控制入口。
        </p>
      </section>
    );
  }

  const projectId = props.projectId;
  const state = stateQuery.data ?? null;

  async function handleRehydrate() {
    try {
      const result = await rehydrateMutation.mutateAsync(undefined);
      setActionFeedback({
        tone: result.rehydrated ? "success" : "warning",
        text: result.rehydrated
          ? `Rehydrate succeeded from checkpoint ${result.used_checkpoint_id ?? "unknown"}.`
          : result.rehydrated_context_summary,
      });
    } catch (error) {
      setActionFeedback({
        tone: "danger",
        text: error instanceof Error ? error.message : "Rehydrate failed.",
      });
    }
  }

  async function handleCompact() {
    const parsed = Number.parseInt(compactTargetChars, 10);
    if (!Number.isFinite(parsed) || parsed < 300 || parsed > 2000) {
      setActionFeedback({
        tone: "warning",
        text: "Compact target must be an integer between 300 and 2000.",
      });
      return;
    }

    try {
      const result = await compactMutation.mutateAsync({ targetChars: parsed });
      setActionFeedback({
        tone: "success",
        text: `Compact succeeded with ratio ${formatRatio(result.reduction_ratio)} (checkpoint ${result.checkpoint_id ?? "n/a"}).`,
      });
    } catch (error) {
      setActionFeedback({
        tone: "danger",
        text: error instanceof Error ? error.message : "Compact failed.",
      });
    }
  }

  async function handleReset() {
    try {
      const result = await resetMutation.mutateAsync();
      setActionFeedback({
        tone: result.reset_performed ? "success" : "warning",
        text: result.reset_performed
          ? "Governance state was reset."
          : "Reset completed but no persisted governance artifact existed.",
      });
      setLatestProbe(null);
    } catch (error) {
      setActionFeedback({
        tone: "danger",
        text: error instanceof Error ? error.message : "Reset failed.",
      });
    }
  }

  async function handleProbeRunOnce() {
    try {
      const result = await probeMutation.mutateAsync();
      setLatestProbe(result);
      setActionFeedback({
        tone: result.claimed ? "success" : "warning",
        text: `Run-once probe: ${result.message}`,
      });
    } catch (error) {
      setActionFeedback({
        tone: "danger",
        text: error instanceof Error ? error.message : "Run-once probe failed.",
      });
    }
  }

  return (
    <section
      id="memory-governance-control-surface"
      data-testid="memory-governance-control-surface"
      className="space-y-6"
    >
      <header className="border-b border-[#333333] pb-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">
              记忆治理
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-zinc-50">
              治理状态观察与动作入口
            </h2>
            <p className="mt-2 text-sm text-zinc-400">
              当前项目：{props.projectName ?? projectId}
            </p>
          </div>
          <button
            type="button"
            onClick={() => void stateQuery.refetch()}
            className="rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
          >
            刷新治理状态
          </button>
        </div>
      </header>

      {stateQuery.isLoading && !state ? (
        <div className="border-y border-[#333333] py-5 text-sm text-zinc-500">
          正在加载治理状态...
        </div>
      ) : null}

      {stateQuery.isError ? (
        <div className="border-l border-rose-700/70 pl-4 text-sm leading-6 text-rose-200">
          治理状态加载失败：{stateQuery.error.message}
        </div>
      ) : null}

      {actionFeedback ? (
        <div
          data-testid="memory-governance-action-feedback"
          className={`border-l pl-4 text-sm leading-6 ${
            actionFeedback.tone === "success"
              ? "border-emerald-700/70 text-emerald-200"
              : actionFeedback.tone === "warning"
                ? "border-amber-700/70 text-amber-200"
                : "border-rose-700/70 text-rose-200"
          }`}
        >
          {actionFeedback.text}
        </div>
      ) : null}

      {state ? (
        <>
          <section className="border-b border-[#333333] pb-5" aria-label="记忆治理指标摘要">
            <dl className="grid gap-x-6 gap-y-4 md:grid-cols-2 xl:grid-cols-4">
            <GovernanceStatCard label="Checkpoint 数" value={String(state.checkpoint_count)} />
            <GovernanceStatCard
              label="压力等级"
              value={state.latest_pressure_level ?? "none"}
            />
            <GovernanceStatCard
              label="Usage Ratio"
              value={formatRatio(state.latest_usage_ratio)}
            />
            <GovernanceStatCard
              label="风险标记"
              value={state.latest_bad_context_detected ? "detected" : "clear"}
            />
            </dl>
          </section>

          <section className="space-y-5 border-b border-[#333333] pb-6">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge
                label={state.latest_bad_context_detected ? "bad context" : "context clear"}
                tone={state.latest_bad_context_detected ? "danger" : "success"}
              />
              <StatusBadge
                label={
                  state.latest_compaction_applied
                    ? "compaction applied"
                    : "compaction not applied"
                }
                tone={state.latest_compaction_applied ? "warning" : "neutral"}
              />
              <StatusBadge
                label={
                  state.latest_rehydrate_used_checkpoint_id
                    ? `rehydrate: ${state.latest_rehydrate_used_checkpoint_id}`
                    : "rehydrate: none"
                }
                tone={state.latest_rehydrate_used_checkpoint_id ? "info" : "neutral"}
              />
            </div>

            <div className="grid gap-x-6 gap-y-3 text-sm text-zinc-300 md:grid-cols-2">
              <div>Latest checkpoint: {state.latest_checkpoint_id ?? "none"}</div>
              <div>Latest task: {state.latest_task_id ?? "none"}</div>
              <div>Latest run: {state.latest_run_id ?? "none"}</div>
              <div>
                Latest compact ratio: {formatRatio(state.latest_compaction_reduction_ratio)}
              </div>
              <div>
                Latest rehydrate at:{" "}
                {state.latest_rehydrate_at ? formatDateTime(state.latest_rehydrate_at) : "none"}
              </div>
              <div>
                Latest compacted at:{" "}
                {state.latest_compacted_at ? formatDateTime(state.latest_compacted_at) : "none"}
              </div>
            </div>

            <div className="divide-y divide-[#333333] border-y border-[#333333] text-sm text-zinc-300">
              <div className="py-4">
                <div className="text-xs font-medium uppercase tracking-[0.16em] text-zinc-500">
                  Rolling summary
                </div>
                <p className="mt-2 whitespace-pre-wrap">
                  {state.latest_rolling_summary ?? "No rolling summary yet."}
                </p>
              </div>

              <div className="py-4">
                <div className="text-xs font-medium uppercase tracking-[0.16em] text-zinc-500">
                  Risk reasons
                </div>
                <p className="mt-2">
                  {state.latest_bad_context_reasons.length
                    ? state.latest_bad_context_reasons.join(" | ")
                    : "No bad-context reasons."}
                </p>
              </div>

              <div className="py-4">
                <div className="text-xs font-medium uppercase tracking-[0.16em] text-zinc-500">
                  Compact reasons
                </div>
                <p className="mt-2">
                  {state.latest_compaction_reason_codes.length
                    ? state.latest_compaction_reason_codes.join(" | ")
                    : "No compaction reason codes."}
                </p>
              </div>
            </div>
          </section>
        </>
      ) : null}

      <section className="border-b border-[#333333] pb-6">
        <h3 className="text-lg font-semibold text-zinc-50">Manual 动作入口</h3>
        <p className="mt-1 text-sm text-zinc-500">
          覆盖 rehydrate / compact / reset，并附带 run-once 合同回显消费入口。
        </p>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <button
            type="button"
            data-testid="memory-governance-rehydrate-btn"
            onClick={() => void handleRehydrate()}
            disabled={rehydrateMutation.isPending || !state}
            className="rounded border border-[#3a3a3a] bg-transparent px-4 py-3 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {rehydrateMutation.isPending ? "Rehydrate..." : "Manual Rehydrate"}
          </button>

          <div className="flex gap-2">
            <input
              type="number"
              min={300}
              max={2000}
              value={compactTargetChars}
              onChange={(event) => setCompactTargetChars(event.target.value)}
              className="w-full rounded border border-[#3a3a3a] bg-transparent px-3 py-3 text-sm text-zinc-100 focus:border-zinc-500 focus:outline-none"
            />
            <button
              type="button"
              data-testid="memory-governance-compact-btn"
              onClick={() => void handleCompact()}
              disabled={compactMutation.isPending || !state}
              className="rounded border border-[#3a3a3a] bg-transparent px-4 py-3 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {compactMutation.isPending ? "Compact..." : "Compact"}
            </button>
          </div>

          <button
            type="button"
            data-testid="memory-governance-reset-btn"
            onClick={() => void handleReset()}
            disabled={resetMutation.isPending || !state}
            className="rounded border border-[#3a3a3a] bg-transparent px-4 py-3 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {resetMutation.isPending ? "Reset..." : "Reset Governance"}
          </button>

          <button
            type="button"
            data-testid="memory-governance-run-once-btn"
            onClick={() => void handleProbeRunOnce()}
            disabled={probeMutation.isPending}
            className="rounded border border-[#3a3a3a] bg-transparent px-4 py-3 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {probeMutation.isPending ? "Probing..." : "Probe /workers/run-once"}
          </button>
        </div>
      </section>

      {latestProbe ? (
        <section className="border-b border-[#333333] pb-6">
          <h3 className="text-lg font-semibold text-zinc-50">Run-once 治理回显</h3>
          <p className="mt-1 text-sm text-zinc-500">
            该区块直接消费 `POST /workers/run-once` 的 `memory_governance_*` 字段。
          </p>

          <div className="mt-3 grid gap-x-6 gap-y-3 text-sm text-zinc-300 md:grid-cols-2">
            <div>claimed: {String(latestProbe.claimed)}</div>
            <div>run_id: {latestProbe.run_id ?? "none"}</div>
            <div>task_id: {latestProbe.task_id ?? "none"}</div>
            <div>checkpoint_id: {latestProbe.memory_governance_checkpoint_id ?? "none"}</div>
            <div>
              pressure_level: {latestProbe.memory_governance_pressure_level ?? "none"}
            </div>
            <div>usage_ratio: {formatRatio(latestProbe.memory_governance_usage_ratio)}</div>
            <div>
              compaction_applied: {String(latestProbe.memory_governance_compaction_applied)}
            </div>
            <div>
              rehydrated: {String(latestProbe.memory_governance_rehydrated)}
            </div>
          </div>

          <div className="mt-4 border-y border-[#333333] py-4 text-sm text-zinc-300">
            {latestProbe.memory_governance_rolling_summary ?? "No rolling summary echoed."}
          </div>
        </section>
      ) : null}
    </section>
  );
}

function GovernanceStatCard(props: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-medium uppercase tracking-[0.16em] text-zinc-500">
        {props.label}
      </dt>
      <dd className="mt-2 truncate font-mono text-2xl font-semibold tracking-tight text-zinc-100">
        {props.value}
      </dd>
    </div>
  );
}

function formatRatio(value: number | null) {
  if (value === null || Number.isNaN(value)) {
    return "n/a";
  }
  return value.toFixed(4);
}
