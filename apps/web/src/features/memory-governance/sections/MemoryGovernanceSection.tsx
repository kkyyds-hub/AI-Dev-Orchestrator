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
          先选择项目，再查看记忆检查点、滚动摘要、风险标记，并使用手动恢复、压缩和重置控制入口。
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
          ? `上下文恢复成功，使用检查点 ${result.used_checkpoint_id ?? "未知"}。`
          : result.rehydrated_context_summary,
      });
    } catch (error) {
      setActionFeedback({
        tone: "danger",
        text: error instanceof Error ? error.message : "上下文恢复失败。",
      });
    }
  }

  async function handleCompact() {
    const parsed = Number.parseInt(compactTargetChars, 10);
    if (!Number.isFinite(parsed) || parsed < 300 || parsed > 2000) {
      setActionFeedback({
        tone: "warning",
        text: "压缩目标必须是 300 到 2000 之间的整数。",
      });
      return;
    }

    try {
      const result = await compactMutation.mutateAsync({ targetChars: parsed });
      setActionFeedback({
        tone: "success",
        text: `压缩完成，压缩比例 ${formatRatio(result.reduction_ratio)}（检查点 ${result.checkpoint_id ?? "无"}）。`,
      });
    } catch (error) {
      setActionFeedback({
        tone: "danger",
        text: error instanceof Error ? error.message : "压缩失败。",
      });
    }
  }

  async function handleReset() {
    try {
      const result = await resetMutation.mutateAsync();
      setActionFeedback({
        tone: result.reset_performed ? "success" : "warning",
        text: result.reset_performed
          ? "治理状态已重置。"
          : "重置完成，但没有已持久化的治理产物。",
      });
      setLatestProbe(null);
    } catch (error) {
      setActionFeedback({
        tone: "danger",
        text: error instanceof Error ? error.message : "重置失败。",
      });
    }
  }

  async function handleProbeRunOnce() {
    try {
      const result = await probeMutation.mutateAsync();
      setLatestProbe(result);
      setActionFeedback({
        tone: result.claimed ? "success" : "warning",
        text: `单次运行探测：${result.message}`,
      });
    } catch (error) {
      setActionFeedback({
        tone: "danger",
        text: error instanceof Error ? error.message : "单次运行探测失败。",
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
            <GovernanceStatCard label="检查点数" value={String(state.checkpoint_count)} />
            <GovernanceStatCard
              label="压力等级"
              value={state.latest_pressure_level ?? "无"}
            />
            <GovernanceStatCard
              label="使用率"
              value={formatRatio(state.latest_usage_ratio)}
            />
            <GovernanceStatCard
              label="风险标记"
              value={state.latest_bad_context_detected ? "已发现" : "正常"}
            />
            </dl>
          </section>

          <section className="space-y-5 border-b border-[#333333] pb-6">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge
                label={state.latest_bad_context_detected ? "上下文异常" : "上下文正常"}
                tone={state.latest_bad_context_detected ? "danger" : "success"}
              />
              <StatusBadge
                label={
                  state.latest_compaction_applied
                    ? "已执行压缩"
                    : "未执行压缩"
                }
                tone={state.latest_compaction_applied ? "warning" : "neutral"}
              />
              <StatusBadge
                label={
                  state.latest_rehydrate_used_checkpoint_id
                    ? `恢复自：${state.latest_rehydrate_used_checkpoint_id}`
                    : "未恢复上下文"
                }
                tone={state.latest_rehydrate_used_checkpoint_id ? "info" : "neutral"}
              />
            </div>

            <div className="grid gap-x-6 gap-y-3 text-sm text-zinc-300 md:grid-cols-2">
              <div>最新检查点：{state.latest_checkpoint_id ?? "无"}</div>
              <div>最新任务：{state.latest_task_id ?? "无"}</div>
              <div>最新运行：{state.latest_run_id ?? "无"}</div>
              <div>
                最新压缩比例：{formatRatio(state.latest_compaction_reduction_ratio)}
              </div>
              <div>
                最近恢复时间：{" "}
                {state.latest_rehydrate_at ? formatDateTime(state.latest_rehydrate_at) : "无"}
              </div>
              <div>
                最近压缩时间：{" "}
                {state.latest_compacted_at ? formatDateTime(state.latest_compacted_at) : "无"}
              </div>
            </div>

            <div className="divide-y divide-[#333333] border-y border-[#333333] text-sm text-zinc-300">
              <div className="py-4">
                <div className="text-xs font-medium uppercase tracking-[0.16em] text-zinc-500">
                  滚动摘要
                </div>
                <p className="mt-2 whitespace-pre-wrap">
                  {state.latest_rolling_summary ?? "暂无滚动摘要。"}
                </p>
              </div>

              <div className="py-4">
                <div className="text-xs font-medium uppercase tracking-[0.16em] text-zinc-500">
                  风险原因
                </div>
                <p className="mt-2">
                  {state.latest_bad_context_reasons.length
                    ? state.latest_bad_context_reasons.join(" | ")
                    : "暂无上下文风险原因。"}
                </p>
              </div>

              <div className="py-4">
                <div className="text-xs font-medium uppercase tracking-[0.16em] text-zinc-500">
                  压缩原因
                </div>
                <p className="mt-2">
                  {state.latest_compaction_reason_codes.length
                    ? state.latest_compaction_reason_codes.join(" | ")
                    : "暂无压缩原因代码。"}
                </p>
              </div>
            </div>
          </section>
        </>
      ) : null}

      <section className="border-b border-[#333333] pb-6">
        <h3 className="text-lg font-semibold text-zinc-50">手动治理动作</h3>
        <p className="mt-1 text-sm text-zinc-500">
          覆盖上下文恢复、压缩和重置，并附带单次运行合同回显消费入口。
        </p>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <button
            type="button"
            data-testid="memory-governance-rehydrate-btn"
            onClick={() => void handleRehydrate()}
            disabled={rehydrateMutation.isPending || !state}
            className="rounded border border-[#3a3a3a] bg-transparent px-4 py-3 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {rehydrateMutation.isPending ? "恢复中..." : "手动恢复上下文"}
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
              {compactMutation.isPending ? "压缩中..." : "压缩"}
            </button>
          </div>

          <button
            type="button"
            data-testid="memory-governance-reset-btn"
            onClick={() => void handleReset()}
            disabled={resetMutation.isPending || !state}
            className="rounded border border-[#3a3a3a] bg-transparent px-4 py-3 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {resetMutation.isPending ? "重置中..." : "重置治理状态"}
          </button>

          <button
            type="button"
            data-testid="memory-governance-run-once-btn"
            onClick={() => void handleProbeRunOnce()}
            disabled={probeMutation.isPending}
            className="rounded border border-[#3a3a3a] bg-transparent px-4 py-3 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {probeMutation.isPending ? "探测中..." : "探测单次运行"}
          </button>
        </div>
      </section>

      {latestProbe ? (
        <section className="border-b border-[#333333] pb-6">
          <h3 className="text-lg font-semibold text-zinc-50">单次运行治理回显</h3>
          <p className="mt-1 text-sm text-zinc-500">
            该区块直接消费单次运行接口返回的记忆治理字段。
          </p>

          <div className="mt-3 grid gap-x-6 gap-y-3 text-sm text-zinc-300 md:grid-cols-2">
            <div>是否认领：{String(latestProbe.claimed)}</div>
            <div>运行 ID：{latestProbe.run_id ?? "无"}</div>
            <div>任务 ID：{latestProbe.task_id ?? "无"}</div>
            <div>检查点 ID：{latestProbe.memory_governance_checkpoint_id ?? "无"}</div>
            <div>
              压力等级：{latestProbe.memory_governance_pressure_level ?? "无"}
            </div>
            <div>使用率：{formatRatio(latestProbe.memory_governance_usage_ratio)}</div>
            <div>
              是否压缩：{String(latestProbe.memory_governance_compaction_applied)}
            </div>
            <div>
              是否恢复：{String(latestProbe.memory_governance_rehydrated)}
            </div>
          </div>

          <div className="mt-4 border-y border-[#333333] py-4 text-sm text-zinc-300">
            {latestProbe.memory_governance_rolling_summary ?? "暂无滚动摘要回显。"}
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
