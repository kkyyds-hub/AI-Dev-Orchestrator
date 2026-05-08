import { MetricCard } from "../../../components/MetricCard";
import { StatusBadge } from "../../../components/StatusBadge";
import { formatCurrencyUsd } from "../../../lib/format";
import { mapBudgetPressureTone } from "../../../lib/status";
import type { BossProjectOverview } from "../types";
import { PROJECT_STAGE_LABELS } from "../types";

type ProjectSummaryCardsProps = {
  overview: BossProjectOverview;
};

export function ProjectSummaryCards({
  overview,
}: ProjectSummaryCardsProps) {
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
    <section className="space-y-4 rounded-3xl border border-[#333333] bg-[#242424] p-5 shadow-sm shadow-black/10">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-600">
            Portfolio Snapshot
          </p>
          <h2 className="mt-2 text-lg font-semibold text-zinc-100">
            项目组合态势
          </h2>
        </div>
        <p className="text-xs text-zinc-600">
          任务、阶段、预算与仓库绑定状态一屏总览
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="项目总数"
          value={String(overview.total_projects)}
          hint={`活跃 ${overview.active_projects} / 已完成 ${overview.completed_projects} / 已绑定仓库 ${boundRepositoryProjects}`}
          tone="info"
        />

        <MetricCard
          label="阻塞项目"
          value={String(overview.blocked_projects)}
          hint={`挂起、阻塞或等待人工的项目；已记录会话 ${activeChangeSessionProjects}`}
          tone={overview.blocked_projects > 0 ? "warning" : "success"}
        />

        <section className="rounded-2xl border border-zinc-800/90 bg-zinc-950/45 p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-sm text-zinc-500">阶段分布</div>
              <div className="mt-2 text-2xl font-semibold tracking-tight text-zinc-100">
                {overview.total_project_tasks}
              </div>
            </div>
            <div className="text-right text-xs text-zinc-600">
              <div>项目内任务总量</div>
              <div className="mt-1">
                共 {overview.stage_distribution.length} 个阶段桶
              </div>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {(activeStageItems.length > 0
              ? activeStageItems
              : overview.stage_distribution
            ).map((item) => (
              <span
                key={item.stage}
                className="inline-flex items-center rounded-full border border-[#3a3a3a] bg-[#1f1f1f] px-3 py-1 text-xs text-zinc-300"
              >
                {PROJECT_STAGE_LABELS[item.stage] ?? item.stage}
                <span className="ml-2 text-zinc-500">{item.count}</span>
              </span>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-zinc-800/90 bg-zinc-950/45 p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-sm text-zinc-500">预算摘要</div>
              <div className="mt-2 text-lg font-semibold text-zinc-100">
                {formatCurrencyUsd(overview.budget.daily_cost_used)} /{" "}
                {formatCurrencyUsd(overview.budget.daily_budget_usd)}
              </div>
              <div className="mt-1 text-xs text-zinc-600">
                会话剩余{" "}
                {formatCurrencyUsd(overview.budget.session_cost_remaining)}
              </div>
            </div>
            <StatusBadge
              label={overview.budget.strategy_label}
              tone={mapBudgetPressureTone(overview.budget.pressure_level)}
            />
          </div>

          <div className="mt-4 space-y-3 text-sm text-zinc-400">
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
        </section>
      </div>

      {overview.unassigned_tasks > 0 ? (
        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 px-4 py-3 text-sm text-amber-100">
          还有 {overview.unassigned_tasks} 条历史任务尚未归属到项目，会继续保留在下方任务控制台中，不影响
          V1/V2 现有能力。
        </div>
      ) : null}
    </section>
  );
}

function RatioRow(props: { label: string; value: number; text: string }) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-xs text-zinc-500">
        <span>{props.label}</span>
        <span>{props.text}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-[#333333]">
        <div
          className="h-full rounded-full bg-zinc-400 transition-all"
          style={{ width: `${Math.max(4, Math.round(props.value * 100))}%` }}
        />
      </div>
    </div>
  );
}
