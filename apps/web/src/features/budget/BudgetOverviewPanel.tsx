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
  const dailyHealthy = !budget.daily_budget_exceeded;
  const sessionHealthy = !budget.session_budget_exceeded;
  const overallHealthy = dailyHealthy && sessionHealthy;

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-50">预算守卫</h2>
          <p className="mt-1 text-sm text-slate-400">
            Day 15 预算使用、剩余额度和重试上限总览。
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge
            label={overallHealthy ? "预算正常" : "预算告警"}
            tone={overallHealthy ? "success" : "warning"}
          />
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
          hint={`窗口开始：${formatDateTime(budget.daily_window_started_at)}`}
        />
        <BudgetField
          label="日预算剩余"
          value={formatCurrencyUsd(budget.daily_cost_remaining)}
          hint={`上限：${formatCurrencyUsd(budget.daily_budget_usd)}`}
        />
        <BudgetField
          label="会话预算已用"
          value={formatCurrencyUsd(budget.session_cost_used)}
          hint={`会话开始：${formatDateTime(budget.session_started_at)}`}
        />
        <BudgetField
          label="会话预算剩余"
          value={formatCurrencyUsd(budget.session_cost_remaining)}
          hint={`上限：${formatCurrencyUsd(budget.session_budget_usd)}`}
        />
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <BudgetState
          label="日预算状态"
          value={budget.daily_budget_exceeded ? "已耗尽" : "可继续执行"}
          tone={budget.daily_budget_exceeded ? "warning" : "success"}
        />
        <BudgetState
          label="会话预算状态"
          value={budget.session_budget_exceeded ? "已耗尽" : "可继续执行"}
          tone={budget.session_budget_exceeded ? "warning" : "success"}
        />
        <BudgetState
          label="单任务最大重试"
          value={`${budget.max_task_retries} 次`}
          tone="info"
        />
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
