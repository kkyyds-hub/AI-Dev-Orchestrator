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
import type { MemoryGovernanceRunOnceEcho, MemoryGovernanceState } from "../types";

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
          ????
        </p>
        <h2 className="text-2xl font-semibold text-zinc-50">?????????</h2>
        <p className="max-w-3xl text-sm leading-6 text-zinc-400">
          ????????????????????????????????????????????????????
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
          ? `?????????????? ${result.used_checkpoint_id ?? "???"}?`
          : result.rehydrated_context_summary || "????????????????????",
      });
    } catch (error) {
      setActionFeedback({
        tone: "danger",
        text: error instanceof Error ? error.message : "????????",
      });
    }
  }

  async function handleCompact() {
    const parsed = Number.parseInt(compactTargetChars, 10);
    if (!Number.isFinite(parsed) || parsed < 300 || parsed > 2000) {
      setActionFeedback({
        tone: "warning",
        text: "?????? 300 ? 2000 ??????",
      });
      return;
    }

    try {
      const result = await compactMutation.mutateAsync({ targetChars: parsed });
      setActionFeedback({
        tone: "success",
        text: `????????? ${parsed} ?????? ${formatRatio(result.reduction_ratio)}???? ${result.checkpoint_id ?? "???"}?`,
      });
    } catch (error) {
      setActionFeedback({
        tone: "danger",
        text: error instanceof Error ? error.message : "???????",
      });
    }
  }

  async function handleReset() {
    try {
      const result = await resetMutation.mutateAsync();
      setActionFeedback({
        tone: result.reset_performed ? "success" : "warning",
        text: result.reset_performed
          ? "??????????????????????"
          : "??????????????????????",
      });
      setLatestProbe(null);
    } catch (error) {
      setActionFeedback({
        tone: "danger",
        text: error instanceof Error ? error.message : "?????????",
      });
    }
  }

  async function handleProbeRunOnce() {
    try {
      const result = await probeMutation.mutateAsync();
      setLatestProbe(result);
      setActionFeedback({
        tone: result.claimed ? "success" : "warning",
        text: result.claimed
          ? "?????????????????????"
          : `????????${result.message}`,
      });
    } catch (error) {
      setActionFeedback({
        tone: "danger",
        text: error instanceof Error ? error.message : "?????????",
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
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">
              ????
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-zinc-50">
              ?????????
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
              ?????????????????????????????????????????????????
            </p>
            <p className="mt-2 text-xs text-zinc-500">
              ?????{props.projectName ?? projectId}
            </p>
          </div>
          <button
            type="button"
            onClick={() => void stateQuery.refetch()}
            className="rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
          >
            ????
          </button>
        </div>
      </header>

      {stateQuery.isLoading && !state ? (
        <div className="border-y border-[#333333] py-5 text-sm text-zinc-500">
          ????????...
        </div>
      ) : null}

      {stateQuery.isError ? (
        <div className="border-l border-rose-700/70 pl-4 text-sm leading-6 text-rose-200">
          ?????????{stateQuery.error.message}
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

      {state ? <GovernanceOverview state={state} /> : null}
      {state ? <GovernanceContextPanel state={state} /> : null}

      <GovernanceManualActions
        compactTargetChars={compactTargetChars}
        isStateReady={Boolean(state)}
        onCompactTargetCharsChange={setCompactTargetChars}
        onCompact={() => void handleCompact()}
        onProbeRunOnce={() => void handleProbeRunOnce()}
        onRehydrate={() => void handleRehydrate()}
        onReset={() => void handleReset()}
        pending={{
          compact: compactMutation.isPending,
          probe: probeMutation.isPending,
          rehydrate: rehydrateMutation.isPending,
          reset: resetMutation.isPending,
        }}
      />

      {latestProbe ? <GovernanceRunEcho latestProbe={latestProbe} /> : null}
    </section>
  );
}

function GovernanceOverview(props: { state: MemoryGovernanceState }) {
  const state = props.state;
  const healthTone = state.latest_bad_context_detected ? "danger" : "success";
  const healthText = state.latest_bad_context_detected ? "????" : "?????";
  const latestGovernanceAt =
    state.latest_compacted_at ?? state.latest_rehydrate_at ?? state.generated_at;

  return (
    <section className="space-y-4 border-b border-[#333333] pb-6" aria-label="??????">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge label={healthText} tone={healthTone} />
        <StatusBadge
          label={state.latest_compaction_applied ? "?????" : "?????"}
          tone={state.latest_compaction_applied ? "warning" : "neutral"}
        />
        <StatusBadge
          label={
            state.latest_rehydrate_used_checkpoint_id
              ? "????????"
              : "?????"
          }
          tone={state.latest_rehydrate_used_checkpoint_id ? "info" : "neutral"}
        />
      </div>

      <dl className="grid gap-x-6 gap-y-4 md:grid-cols-2 xl:grid-cols-4">
        <GovernanceStatCard label="???" value={`${state.checkpoint_count} ?`} />
        <GovernanceStatCard label="????" value={formatPressure(state.latest_pressure_level)} />
        <GovernanceStatCard label="???" value={formatRatio(state.latest_usage_ratio)} />
        <GovernanceStatCard label="????" value={formatDateTime(latestGovernanceAt)} />
      </dl>
    </section>
  );
}

function GovernanceContextPanel(props: { state: MemoryGovernanceState }) {
  const state = props.state;

  return (
    <section className="grid gap-5 border-b border-[#333333] pb-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(280px,0.6fr)]">
      <div className="space-y-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-zinc-500">
            ?????
          </p>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-zinc-300">
            {state.latest_rolling_summary ?? "????????????????????????"}
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <GovernanceSignalCard
            title="????"
            description={
              state.latest_bad_context_reasons.length
                ? state.latest_bad_context_reasons.join(" / ")
                : "??????????"
            }
          />
          <GovernanceSignalCard
            title="????"
            description={
              state.latest_compaction_reason_codes.length
                ? state.latest_compaction_reason_codes.join(" / ")
                : "?????????"
            }
          />
        </div>
      </div>

      <aside className="space-y-3 border-y border-[#333333] py-4 text-sm text-zinc-300 xl:border-y-0 xl:border-l xl:py-0 xl:pl-5">
        <h3 className="text-base font-semibold text-zinc-50">????</h3>
        <GovernanceMetaRow label="???" value={state.latest_checkpoint_id ?? "???"} />
        <GovernanceMetaRow label="??" value={state.latest_task_id ?? "???"} />
        <GovernanceMetaRow label="??" value={state.latest_run_id ?? "???"} />
        <GovernanceMetaRow
          label="????"
          value={formatRatio(state.latest_compaction_reduction_ratio)}
        />
        <GovernanceMetaRow
          label="????"
          value={state.latest_rehydrate_at ? formatDateTime(state.latest_rehydrate_at) : "???"}
        />
        <GovernanceMetaRow
          label="????"
          value={state.latest_compacted_at ? formatDateTime(state.latest_compacted_at) : "???"}
        />
      </aside>
    </section>
  );
}

function GovernanceManualActions(props: {
  compactTargetChars: string;
  isStateReady: boolean;
  onCompact: () => void;
  onCompactTargetCharsChange: (value: string) => void;
  onProbeRunOnce: () => void;
  onRehydrate: () => void;
  onReset: () => void;
  pending: {
    compact: boolean;
    probe: boolean;
    rehydrate: boolean;
    reset: boolean;
  };
}) {
  return (
    <section className="border-b border-[#333333] pb-6">
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-zinc-50">??????</h3>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-zinc-500">
            ??????????????????????????????????????????????????
          </p>
        </div>
        <p className="text-xs text-zinc-600">???????300-2000 ?</p>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <button
          type="button"
          data-testid="memory-governance-rehydrate-btn"
          onClick={props.onRehydrate}
          disabled={props.pending.rehydrate || !props.isStateReady}
          className="rounded border border-[#3a3a3a] bg-transparent px-4 py-3 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {props.pending.rehydrate ? "???..." : "?????"}
        </button>

        <div className="flex gap-2">
          <input
            type="number"
            min={300}
            max={2000}
            aria-label="??????"
            value={props.compactTargetChars}
            onChange={(event) => props.onCompactTargetCharsChange(event.target.value)}
            className="w-full rounded border border-[#3a3a3a] bg-transparent px-3 py-3 text-sm text-zinc-100 focus:border-zinc-500 focus:outline-none"
          />
          <button
            type="button"
            data-testid="memory-governance-compact-btn"
            onClick={props.onCompact}
            disabled={props.pending.compact || !props.isStateReady}
            className="rounded border border-[#3a3a3a] bg-transparent px-4 py-3 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {props.pending.compact ? "???..." : "??"}
          </button>
        </div>

        <button
          type="button"
          data-testid="memory-governance-reset-btn"
          onClick={props.onReset}
          disabled={props.pending.reset || !props.isStateReady}
          className="rounded border border-[#3a3a3a] bg-transparent px-4 py-3 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {props.pending.reset ? "???..." : "??????"}
        </button>

        <button
          type="button"
          data-testid="memory-governance-run-once-btn"
          onClick={props.onProbeRunOnce}
          disabled={props.pending.probe}
          className="rounded border border-[#3a3a3a] bg-transparent px-4 py-3 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {props.pending.probe ? "???..." : "??????"}
        </button>
      </div>
    </section>
  );
}

function GovernanceRunEcho(props: { latestProbe: MemoryGovernanceRunOnceEcho }) {
  const latestProbe = props.latestProbe;
  const hasRisk = latestProbe.memory_governance_bad_context_detected === true;
  const runSummary = latestProbe.claimed
    ? hasRisk
      ? "?????????????????????"
      : "?????????????????????"
    : latestProbe.message;

  return (
    <section className="border-b border-[#333333] pb-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-zinc-50">????</h3>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-zinc-500">
            ?????????????????????????????????
          </p>
        </div>
        <StatusBadge label={latestProbe.claimed ? "???" : "???"} tone={latestProbe.claimed ? "success" : "warning"} />
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-[minmax(0,1.3fr)_minmax(260px,0.7fr)]">
        <div className="space-y-3">
          <p className="text-sm leading-6 text-zinc-300">{runSummary}</p>
          <p className="whitespace-pre-wrap border-y border-[#333333] py-4 text-sm leading-6 text-zinc-300">
            {latestProbe.memory_governance_rolling_summary ?? "?????????????"}
          </p>
        </div>

        <dl className="space-y-3 text-sm text-zinc-300">
          <GovernanceMetaRow
            label="????"
            value={formatPressure(latestProbe.memory_governance_pressure_level)}
          />
          <GovernanceMetaRow
            label="???"
            value={formatRatio(latestProbe.memory_governance_usage_ratio)}
          />
          <GovernanceMetaRow
            label="?? / ??"
            value={`${formatBoolean(latestProbe.memory_governance_compaction_applied)} / ${formatBoolean(latestProbe.memory_governance_rehydrated)}`}
          />
          <GovernanceMetaRow label="??" value={latestProbe.run_id ?? "???"} />
          <GovernanceMetaRow label="??" value={latestProbe.task_id ?? "???"} />
          <GovernanceMetaRow
            label="???"
            value={latestProbe.memory_governance_checkpoint_id ?? "???"}
          />
        </dl>
      </div>
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

function GovernanceSignalCard(props: { title: string; description: string }) {
  return (
    <div className="border-l border-[#333333] pl-4">
      <h3 className="text-sm font-semibold text-zinc-100">{props.title}</h3>
      <p className="mt-2 text-sm leading-6 text-zinc-400">{props.description}</p>
    </div>
  );
}

function GovernanceMetaRow(props: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[72px_minmax(0,1fr)] gap-3">
      <dt className="text-zinc-500">{props.label}</dt>
      <dd className="min-w-0 truncate text-zinc-300" title={props.value}>
        {props.value}
      </dd>
    </div>
  );
}

function formatRatio(value: number | null) {
  if (value === null || Number.isNaN(value)) {
    return "???";
  }

  return `${(value * 100).toFixed(1)}%`;
}

function formatPressure(value: string | null) {
  if (!value) {
    return "???";
  }

  const labelMap: Record<string, string> = {
    low: "?",
    medium: "?",
    high: "?",
    critical: "??",
  };

  return labelMap[value] ? `${labelMap[value]}?${value}?` : value;
}

function formatBoolean(value: boolean | null) {
  if (value === null) {
    return "???";
  }

  return value ? "?" : "?";
}
