import { type ReactNode, useState } from "react";

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
type GovernanceLocalView = "overview" | "actions" | "echo";

const GOVERNANCE_LOCAL_VIEWS: ReadonlyArray<{
  id: GovernanceLocalView;
  label: string;
  description: string;
}> = [
  { id: "overview", label: "治理概览", description: "健康状态与上下文摘要" },
  { id: "actions", label: "手动动作", description: "恢复、压缩、重置与运行检查" },
  { id: "echo", label: "运行回显", description: "最近一次检查结果" },
];

export function MemoryGovernanceSection(props: MemoryGovernanceSectionProps) {
  const stateQuery = useMemoryGovernanceState(props.projectId);
  const rehydrateMutation = useMemoryGovernanceRehydrate(props.projectId);
  const compactMutation = useMemoryGovernanceCompact(props.projectId);
  const resetMutation = useMemoryGovernanceReset(props.projectId);
  const runCheckMutation = useMemoryGovernanceProbe(props.projectId);

  const [activeView, setActiveView] = useState<GovernanceLocalView>("overview");
  const [compactTargetChars, setCompactTargetChars] = useState("900");
  const [actionFeedback, setActionFeedback] = useState<{
    tone: ActionFeedbackTone;
    text: string;
  } | null>(null);
  const [latestRunEcho, setLatestRunEcho] = useState<MemoryGovernanceRunOnceEcho | null>(
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
        <h2 className="text-2xl font-semibold text-zinc-50">运行上下文健康状态</h2>
        <p className="max-w-3xl text-sm leading-6 text-zinc-400">
          请选择项目后查看治理概览、执行必要的手动动作，并检查最近一次运行回显。
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
          ? "上下文恢复完成，已使用检查点 " + (result.used_checkpoint_id ?? "未记录") + "。"
          : result.rehydrated_context_summary || "当前没有可恢复的检查点。",
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
        text: "压缩目标需为 300 到 2000 之间的整数。",
      });
      return;
    }

    try {
      const result = await compactMutation.mutateAsync({ targetChars: parsed });
      setActionFeedback({
        tone: "success",
        text:
          "摘要压缩完成，目标 " +
          String(parsed) +
          " 字，压缩比例 " +
          formatRatio(result.reduction_ratio) +
          "，检查点 " +
          (result.checkpoint_id ?? "未记录") +
          "。",
      });
    } catch (error) {
      setActionFeedback({
        tone: "danger",
        text: error instanceof Error ? error.message : "摘要压缩失败。",
      });
    }
  }

  async function handleReset() {
    try {
      const result = await resetMutation.mutateAsync();
      setActionFeedback({
        tone: result.reset_performed ? "success" : "warning",
        text: result.reset_performed
          ? "治理状态已重置，新的状态会在刷新后展示。"
          : "重置请求已完成，当前没有可清理的治理记录。",
      });
      setLatestRunEcho(null);
    } catch (error) {
      setActionFeedback({
        tone: "danger",
        text: error instanceof Error ? error.message : "治理状态重置失败。",
      });
    }
  }

  async function handleRunCheck() {
    try {
      const result = await runCheckMutation.mutateAsync();
      setLatestRunEcho(result);
      setActiveView("echo");
      setActionFeedback({
        tone: result.claimed ? "success" : "warning",
        text: result.claimed
          ? "单次运行检查已完成，回显已更新。"
          : "单次运行未产生可用结果：" + result.message,
      });
    } catch (error) {
      setActionFeedback({
        tone: "danger",
        text: error instanceof Error ? error.message : "单次运行检查失败。",
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
              记忆治理
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-zinc-50">
              运行上下文健康状态
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
              将治理信息收口为三个局部视图：先看概览，需要时执行手动动作，再查看最近一次运行回显。
            </p>
            <p className="mt-2 text-xs text-zinc-500">
              当前项目：{props.projectName ?? projectId}
            </p>
          </div>
          <button
            type="button"
            onClick={() => void stateQuery.refetch()}
            className="rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
          >
            刷新状态
          </button>
        </div>
      </header>

      <GovernanceLocalTabs activeView={activeView} onChange={setActiveView} />

      {stateQuery.isLoading && !state ? (
        <div className="border-y border-[#333333] py-5 text-sm text-zinc-500">
          正在读取治理状态...
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
          className={
            "border-l pl-4 text-sm leading-6 " +
            (actionFeedback.tone === "success"
              ? "border-emerald-700/70 text-emerald-200"
              : actionFeedback.tone === "warning"
                ? "border-amber-700/70 text-amber-200"
                : "border-rose-700/70 text-rose-200")
          }
        >
          {actionFeedback.text}
        </div>
      ) : null}

      <div id={"memory-governance-" + activeView + "-view"} className="min-w-0">
        {activeView === "overview" ? (
          state ? <GovernanceOverview state={state} /> : <GovernanceStateEmpty />
        ) : null}

        {activeView === "actions" ? (
          <GovernanceManualActions
            compactTargetChars={compactTargetChars}
            isStateReady={Boolean(state)}
            onCompactTargetCharsChange={setCompactTargetChars}
            onCompact={() => void handleCompact()}
            onRunCheck={() => void handleRunCheck()}
            onRehydrate={() => void handleRehydrate()}
            onReset={() => void handleReset()}
            pending={{
              compact: compactMutation.isPending,
              runCheck: runCheckMutation.isPending,
              rehydrate: rehydrateMutation.isPending,
              reset: resetMutation.isPending,
            }}
          />
        ) : null}

        {activeView === "echo" ? <GovernanceRunEcho latestRunEcho={latestRunEcho} /> : null}
      </div>
    </section>
  );
}

function GovernanceLocalTabs(props: {
  activeView: GovernanceLocalView;
  onChange: (view: GovernanceLocalView) => void;
}) {
  return (
    <nav aria-label="治理局部视图" className="grid gap-3 md:grid-cols-3">
      {GOVERNANCE_LOCAL_VIEWS.map((item) => {
        const isActive = item.id === props.activeView;

        return (
          <button
            key={item.id}
            type="button"
            aria-current={isActive ? "page" : undefined}
            onClick={() => props.onChange(item.id)}
            className={
              "border-l px-3 py-2 text-left transition " +
              (isActive
                ? "border-zinc-100 text-zinc-100"
                : "border-[#333333] text-zinc-500 hover:border-zinc-500 hover:text-zinc-200")
            }
          >
            <span className="block text-sm font-medium">{item.label}</span>
            <span className="mt-1 block text-xs leading-5 text-zinc-600">
              {item.description}
            </span>
          </button>
        );
      })}
    </nav>
  );
}

function GovernanceOverview(props: { state: MemoryGovernanceState }) {
  const state = props.state;
  const healthTone = state.latest_bad_context_detected ? "danger" : "success";
  const healthText = state.latest_bad_context_detected ? "需要关注" : "上下文正常";
  const latestGovernanceAt =
    state.latest_compacted_at ?? state.latest_rehydrate_at ?? state.generated_at;

  return (
    <section className="space-y-6" aria-label="治理概览">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge label={healthText} tone={healthTone} />
        <StatusBadge
          label={state.latest_compaction_applied ? "已执行压缩" : "未执行压缩"}
          tone={state.latest_compaction_applied ? "warning" : "neutral"}
        />
        <StatusBadge
          label={
            state.latest_rehydrate_used_checkpoint_id
              ? "已恢复上下文"
              : "未恢复上下文"
          }
          tone={state.latest_rehydrate_used_checkpoint_id ? "info" : "neutral"}
        />
      </div>

      <dl className="grid gap-x-6 gap-y-4 md:grid-cols-2 xl:grid-cols-4">
        <GovernanceStatCard label="检查点" value={String(state.checkpoint_count) + " 个"} />
        <GovernanceStatCard label="压力等级" value={formatPressure(state.latest_pressure_level)} />
        <GovernanceStatCard label="使用率" value={formatRatio(state.latest_usage_ratio)} />
        <GovernanceStatCard label="最近治理" value={formatDateTime(latestGovernanceAt)} />
      </dl>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(280px,0.6fr)]">
        <div className="space-y-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-zinc-500">
              上下文摘要
            </p>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-zinc-300">
              {state.latest_rolling_summary ?? "暂无滚动摘要。系统会在运行产生检查点后沉淀摘要。"}
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <GovernanceSignalCard
              title="风险线索"
              description={
                state.latest_bad_context_reasons.length
                  ? state.latest_bad_context_reasons.join(" / ")
                  : "暂无上下文风险线索。"
              }
            />
            <GovernanceSignalCard
              title="压缩线索"
              description={
                state.latest_compaction_reason_codes.length
                  ? state.latest_compaction_reason_codes.join(" / ")
                  : "暂无压缩线索。"
              }
            />
          </div>
        </div>

        <aside className="space-y-3 border-y border-[#333333] py-4 text-sm text-zinc-300 xl:border-y-0 xl:border-l xl:py-0 xl:pl-5">
          <h3 className="text-base font-semibold text-zinc-50">最近记录</h3>
          <GovernanceMetaRow label="检查点" value={state.latest_checkpoint_id ?? "未记录"} />
          <GovernanceMetaRow label="任务" value={state.latest_task_id ?? "未记录"} />
          <GovernanceMetaRow label="运行" value={state.latest_run_id ?? "未记录"} />
          <GovernanceMetaRow
            label="压缩比例"
            value={formatRatio(state.latest_compaction_reduction_ratio)}
          />
          <GovernanceMetaRow
            label="恢复时间"
            value={state.latest_rehydrate_at ? formatDateTime(state.latest_rehydrate_at) : "未记录"}
          />
          <GovernanceMetaRow
            label="压缩时间"
            value={state.latest_compacted_at ? formatDateTime(state.latest_compacted_at) : "未记录"}
          />
        </aside>
      </div>
    </section>
  );
}

function GovernanceManualActions(props: {
  compactTargetChars: string;
  isStateReady: boolean;
  onCompact: () => void;
  onCompactTargetCharsChange: (value: string) => void;
  onRunCheck: () => void;
  onRehydrate: () => void;
  onReset: () => void;
  pending: {
    compact: boolean;
    runCheck: boolean;
    rehydrate: boolean;
    reset: boolean;
  };
}) {
  return (
    <section className="space-y-5" aria-label="手动动作">
      <div>
        <h3 className="text-lg font-semibold text-zinc-50">手动治理动作</h3>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-zinc-500">
          保留四个必要入口，用于人工确认后的恢复、压缩、重置和单次运行检查。日常判断优先查看治理概览。
        </p>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <ActionCard
          title="恢复上下文"
          description="从最近可用检查点恢复项目上下文，适合摘要缺失或上下文异常时使用。"
        >
          <button
            type="button"
            data-testid="memory-governance-rehydrate-btn"
            onClick={props.onRehydrate}
            disabled={props.pending.rehydrate || !props.isStateReady}
            className="rounded border border-[#3a3a3a] bg-transparent px-4 py-3 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {props.pending.rehydrate ? "恢复中..." : "恢复上下文"}
          </button>
        </ActionCard>

        <ActionCard
          title="压缩摘要"
          description="按目标字数压缩滚动摘要，适合上下文压力升高时使用。"
        >
          <div className="flex gap-2">
            <input
              type="number"
              min={300}
              max={2000}
              aria-label="压缩目标字数"
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
              {props.pending.compact ? "压缩中..." : "压缩"}
            </button>
          </div>
          <p className="mt-2 text-xs text-zinc-600">目标范围：300-2000 字</p>
        </ActionCard>

        <ActionCard
          title="重置治理状态"
          description="清理已沉淀的治理状态，用于重新建立项目记忆基线。"
        >
          <button
            type="button"
            data-testid="memory-governance-reset-btn"
            onClick={props.onReset}
            disabled={props.pending.reset || !props.isStateReady}
            className="rounded border border-[#3a3a3a] bg-transparent px-4 py-3 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {props.pending.reset ? "重置中..." : "重置治理状态"}
          </button>
        </ActionCard>

        <ActionCard
          title="检查单次运行"
          description="触发一次运行检查，并把结果更新到运行回显视图。"
        >
          <button
            type="button"
            data-testid="memory-governance-run-once-btn"
            onClick={props.onRunCheck}
            disabled={props.pending.runCheck}
            className="rounded border border-[#3a3a3a] bg-transparent px-4 py-3 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {props.pending.runCheck ? "检查中..." : "检查单次运行"}
          </button>
        </ActionCard>
      </div>
    </section>
  );
}

function GovernanceRunEcho(props: { latestRunEcho: MemoryGovernanceRunOnceEcho | null }) {
  const latestRunEcho = props.latestRunEcho;

  if (!latestRunEcho) {
    return (
      <section className="space-y-3 border-y border-dashed border-[#333333] py-6" aria-label="运行回显">
        <h3 className="text-lg font-semibold text-zinc-50">暂无运行回显</h3>
        <p className="max-w-3xl text-sm leading-6 text-zinc-500">
          当前还没有单次运行检查结果。请切换到“手动动作”，点击“检查单次运行”后再回来查看。
        </p>
      </section>
    );
  }

  const hasRisk = latestRunEcho.memory_governance_bad_context_detected === true;
  const runSummary = latestRunEcho.claimed
    ? hasRisk
      ? "本次运行检查已完成，并提示上下文需要关注。"
      : "本次运行检查已完成，未发现上下文异常。"
    : latestRunEcho.message;

  return (
    <section className="space-y-5" aria-label="运行回显">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-zinc-50">最近一次运行回显</h3>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-zinc-500">
            这里只展示本次检查结论、关键状态和必要追踪信息，避免把技术细节全部铺开。
          </p>
        </div>
        <StatusBadge
          label={latestRunEcho.claimed ? "已取得结果" : "未取得结果"}
          tone={latestRunEcho.claimed ? "success" : "warning"}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-[minmax(0,1.3fr)_minmax(260px,0.7fr)]">
        <div className="space-y-3">
          <p className="text-sm leading-6 text-zinc-300">{runSummary}</p>
          <p className="whitespace-pre-wrap border-y border-[#333333] py-4 text-sm leading-6 text-zinc-300">
            {latestRunEcho.memory_governance_rolling_summary ?? "本次运行暂无滚动摘要。"}
          </p>
        </div>

        <dl className="space-y-3 text-sm text-zinc-300">
          <GovernanceMetaRow
            label="压力等级"
            value={formatPressure(latestRunEcho.memory_governance_pressure_level)}
          />
          <GovernanceMetaRow
            label="使用率"
            value={formatRatio(latestRunEcho.memory_governance_usage_ratio)}
          />
          <GovernanceMetaRow
            label="压缩恢复"
            value={
              formatBoolean(latestRunEcho.memory_governance_compaction_applied) +
              " / " +
              formatBoolean(latestRunEcho.memory_governance_rehydrated)
            }
          />
          <GovernanceMetaRow label="运行" value={latestRunEcho.run_id ?? "未记录"} />
          <GovernanceMetaRow label="任务" value={latestRunEcho.task_id ?? "未记录"} />
          <GovernanceMetaRow
            label="检查点"
            value={latestRunEcho.memory_governance_checkpoint_id ?? "未记录"}
          />
        </dl>
      </div>
    </section>
  );
}

function GovernanceStateEmpty() {
  return (
    <section className="border-y border-dashed border-[#333333] py-6">
      <h3 className="text-lg font-semibold text-zinc-50">暂无治理状态</h3>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-500">
        当前项目还没有可展示的治理记录。运行任务或执行手动动作后，这里会展示上下文健康状态。
      </p>
    </section>
  );
}

function ActionCard(props: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <div className="border border-[#333333] p-4">
      <h4 className="text-base font-semibold text-zinc-50">{props.title}</h4>
      <p className="mt-2 min-h-[48px] text-sm leading-6 text-zinc-500">
        {props.description}
      </p>
      <div className="mt-4">{props.children}</div>
    </div>
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
    return "未记录";
  }

  return (value * 100).toFixed(1) + "%";
}

function formatPressure(value: string | null) {
  if (!value) {
    return "未记录";
  }

  const labelMap: Record<string, string> = {
    low: "低",
    medium: "中",
    high: "高",
    critical: "严重",
  };

  return labelMap[value] ? labelMap[value] + "（" + value + "）" : value;
}

function formatBoolean(value: boolean | null) {
  if (value === null) {
    return "未记录";
  }

  return value ? "是" : "否";
}
