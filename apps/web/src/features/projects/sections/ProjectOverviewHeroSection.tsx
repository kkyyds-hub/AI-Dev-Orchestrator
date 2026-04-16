import { StatusBadge } from "../../../components/StatusBadge";
import { mapBudgetPressureTone } from "../../../lib/status";

type ProjectOverviewHeroSectionProps = {
  budgetStrategyLabel?: string | null;
  budgetPressureLevel?: string | null;
  lastUpdatedText: string;
};

export function ProjectOverviewHeroSection(props: ProjectOverviewHeroSectionProps) {
  return (
    <header
      data-testid="project-overview-hero-section"
      className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-6 lg:flex-row lg:items-end lg:justify-between"
    >
      <div className="space-y-2">
        <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">
          V4 Day04 Boss Entry
        </p>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-50">
          老板首页、项目总览与仓库入口整合
        </h1>
        <p className="max-w-3xl text-sm leading-6 text-slate-300">
          用户进入系统时先看项目全局，再同步看见仓库是否已绑定、最新目录快照和当前变更会话；Day04
          只把仓库视角整合进老板入口与项目详情，不扩展到文件级编辑、代码上下文包、验证证据视图或任何真实
          Git 写操作。
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
        <StatusBadge
          label={props.budgetStrategyLabel ?? "预算快照"}
          tone={mapBudgetPressureTone(props.budgetPressureLevel ?? "normal")}
        />
        <span>最近刷新：{props.lastUpdatedText}</span>
      </div>
    </header>
  );
}
