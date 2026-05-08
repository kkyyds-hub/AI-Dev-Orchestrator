import { StatusBadge } from "../../components/StatusBadge";
import type { ConsoleBudget } from "../console/types";
import { formatCurrencyUsd, formatDateTime } from "../../lib/format";

type BudgetOverviewPanelProps = {
  budget: ConsoleBudget;
  blockedTasks: number;
};

export function BudgetOverviewPanel({
  budget,
  blockedTasks,
}: BudgetOverviewPanelProps) {
  const pressureMeta = pressureMetaByLevel[budget.pressure_level];
  const actionMeta = actionMetaByType[budget.suggested_action];

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-50">预算守卫</h2>
          <p className="mt-1 text-sm text-slate-400">
            V2 Day7 预算层级、降级动作与策略命中总览。
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge label={pressureMeta.label} tone={pressureMeta.tone} />
          <StatusBadge label={actionMeta.label} tone={actionMeta.tone} />
          <StatusBadge
            label={`阻塞任务 ${blockedTasks}`}
            tone={blockedTasks > 0 ? "warning" : "neutral"}
          />
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <BudgetField
          label="日预算已用"
          value={formatCurrencyUsd(budget.daily_cost_used)}
          hint={`占比：${formatPercent(budget.daily_usage_ratio)} · 窗口开始：${formatDateTime(budget.daily_window_started_at)}`}
        />
        <BudgetField
          label="日预算剩余"
          value={formatCurrencyUsd(budget.daily_cost_remaining)}
          hint={`上限：${formatCurrencyUsd(budget.daily_budget_usd)}`}
        />
        <BudgetField
          label="会话预算已用"
          value={formatCurrencyUsd(budget.session_cost_used)}
          hint={`占比：${formatPercent(budget.session_usage_ratio)} · 会话开始：${formatDateTime(budget.session_started_at)}`}
        />
        <BudgetField
          label="会话预算剩余"
          value={formatCurrencyUsd(budget.session_cost_remaining)}
          hint={`上限：${formatCurrencyUsd(budget.session_budget_usd)}`}
        />
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <BudgetState
          label="预算压力层级"
          value={pressureMeta.label}
          tone={pressureMeta.tone}
        />
        <BudgetState
          label="建议动作"
          value={actionMeta.label}
          tone={actionMeta.tone}
        />
        <BudgetState
          label="单任务最大重试"
          value={`${budget.max_task_retries} 次`}
          tone="info"
        />
      </div>

      <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3">
        <div className="text-xs uppercase tracking-[0.2em] text-slate-500">策略命中</div>
        <div className="mt-2 text-sm font-medium text-slate-100">
          {budget.strategy_label}（{budget.strategy_code}）
        </div>
        <div className="mt-1 text-xs text-slate-400">{budget.strategy_summary}</div>
        <div className="mt-2 text-xs text-slate-500">
          当日预算阻断：{budget.budget_blocked_runs_daily} 次 · 会话预算阻断：
          {budget.budget_blocked_runs_session} 次
        </div>
      </div>
    </div>
  );
}

function BudgetField(props: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{props.label}</div>
      <div className="mt-2 text-sm font-medium text-slate-100">{props.value}</div>
      <div className="mt-1 text-xs text-slate-500">{props.hint}</div>
    </div>
  );
}

function BudgetState(props: { label: string; value: string; tone: "neutral" | "info" | "success" | "warning" | "danger" }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{props.label}</div>
      <div className="mt-2">
        <StatusBadge label={props.value} tone={props.tone} />
      </div>
    </div>
  );
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

const pressureMetaByLevel: Record<
  ConsoleBudget["pressure_level"],
  { label: string; tone: "success" | "warning" | "danger" }
> = {
  normal: { label: "预算正常", tone: "success" },
  warning: { label: "预算预警", tone: "warning" },
  critical: { label: "预算临界", tone: "warning" },
  blocked: { label: "预算阻断", tone: "danger" },
};

const actionMetaByType: Record<
  ConsoleBudget["suggested_action"],
  { label: string; tone: "neutral" | "info" | "warning" | "danger" }
> = {
  full_speed: { label: "常规执行", tone: "info" },
  conservative: { label: "保守执行", tone: "warning" },
  degraded: { label: "降级执行", tone: "warning" },
  block: { label: "阻断执行", tone: "danger" },
};
