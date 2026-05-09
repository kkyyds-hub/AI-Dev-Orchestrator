import { StatusBadge } from "../../../components/StatusBadge";
import { formatCurrencyUsd } from "../../../lib/format";
import { mapBudgetPressureTone } from "../../../lib/status";
import type { BossProjectOverview } from "../types";
import { PROJECT_STAGE_LABELS } from "../types";

type ProjectSummaryCardsProps = {
  overview: BossProjectOverview;
};

export function ProjectSummaryCards({ overview }: ProjectSummaryCardsProps) {
  const activeStageItems = overview.stage_distribution.filter(
    (item) => item.count > 0,
  );
  const dailyRatio = Math.min(overview.budget.daily_usage_ratio, 1);
  const sessionRatio = Math.min(overview.budget.session_usage_ratio, 1);
  const boundRepositoryProjects = overview.projects.filter(
    (project) => project.repository_workspace !== null,
  ).length;
  const activeChangeSessionProjects = overview.projects.filter(
    (project) => project.current_change_session !== null,
  ).length;

  return (
    <section className="border-b border-[#333333] pb-6">
      <div className="grid gap-x-8 gap-y-6 md:grid-cols-2 xl:grid-cols-4">
        <StatColumn
          label="项目总数"
          value={String(overview.total_projects)}
          description={`活跃 ${overview.active_projects} / 已完成 ${overview.completed_projects} / 已绑定仓库 ${boundRepositoryProjects}`}
        />

        <StatColumn
          label="阻塞项目"
          value={String(overview.blocked_projects)}
          description={`阻塞或等待人工；活跃变更会话 ${activeChangeSessionProjects}`}
          valueClassName={overview.blocked_projects > 0 ? "text-amber-200" : undefined}
        />

        <div className="min-w-0 space-y-3">
          <div className="flex items-start justify-between gap-4">
            <div className="text-sm text-zinc-400">阶段分布</div>
            <div className="text-right text-xs leading-5 text-zinc-600">
              <div>任务总数 {overview.total_project_tasks}</div>
              <div>{overview.stage_distribution.length} 个阶段</div>
            </div>
          </div>
          <div className="font-mono text-3xl font-semibold tracking-tight text-zinc-100">
            {overview.total_project_tasks}
          </div>
          <div className="flex flex-wrap gap-2">
            {(activeStageItems.length > 0
              ? activeStageItems
              : overview.stage_distribution
            ).map((item) => (
              <span
                key={item.stage}
                className="inline-flex items-center rounded border border-[#3a3a3a] px-2.5 py-1 text-xs text-zinc-400"
              >
                {PROJECT_STAGE_LABELS[item.stage] ?? item.stage}
                <span className="ml-2 text-zinc-600">{item.count}</span>
              </span>
            ))}
          </div>
        </div>

        <div className="min-w-0 space-y-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-sm text-zinc-400">预算摘要</div>
              <div className="mt-2 text-lg font-semibold text-zinc-100">
                {formatCurrencyUsd(overview.budget.daily_cost_used)} /{" "}
                {formatCurrencyUsd(overview.budget.daily_budget_usd)}
              </div>
              <div className="mt-1 text-xs text-zinc-600">
                会话剩余 {formatCurrencyUsd(overview.budget.session_cost_remaining)}
              </div>
            </div>
            <StatusBadge
              label={overview.budget.strategy_label}
              tone={mapBudgetPressureTone(overview.budget.pressure_level)}
            />
          </div>

          <div className="space-y-3 text-sm text-zinc-400">
            <RatioRow
              label="日预算使用率"
              value={dailyRatio}
              text={`${Math.round(dailyRatio * 100)}%`}
            />
            <RatioRow
              label="会话使用率"
              value={sessionRatio}
              text={`${Math.round(sessionRatio * 100)}%`}
            />
          </div>
        </div>
      </div>

      {overview.unassigned_tasks > 0 ? (
        <p className="mt-4 text-xs leading-5 text-zinc-600">
          另有 {overview.unassigned_tasks} 条历史任务尚未归属项目，已保留在任务域中。
        </p>
      ) : null}
    </section>
  );
}

function StatColumn(props: {
  label: string;
  value: string;
  description: string;
  valueClassName?: string;
}) {
  return (
    <div className="min-w-0 space-y-2">
      <div className="text-sm text-zinc-400">{props.label}</div>
      <div
        className={`font-mono text-3xl font-semibold tracking-tight ${
          props.valueClassName ?? "text-zinc-100"
        }`}
      >
        {props.value}
      </div>
      <div className="text-xs leading-5 text-zinc-600">{props.description}</div>
    </div>
  );
}

function RatioRow(props: { label: string; value: number; text: string }) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-xs text-zinc-500">
        <span>{props.label}</span>
        <span>{props.text}</span>
      </div>
      <div className="h-1 overflow-hidden rounded-full bg-[#333333]">
        <div
          className="h-full rounded-full bg-zinc-300 transition-all"
          style={{ width: `${Math.max(3, Math.round(props.value * 100))}%` }}
        />
      </div>
    </div>
  );
}
