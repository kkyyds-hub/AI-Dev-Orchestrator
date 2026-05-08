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
      className="flex flex-col gap-4 border-b border-[#333333] pb-6 lg:flex-row lg:items-end lg:justify-between"
    >
      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-600">
          Projects
        </p>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-100">
          项目中心
        </h1>
        <p className="max-w-3xl text-sm leading-6 text-zinc-500">
          查看项目总览、阶段状态、仓库绑定与当前协同上下文。
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-500">
        <StatusBadge
          label={props.budgetStrategyLabel ?? "预算快照"}
          tone={mapBudgetPressureTone(props.budgetPressureLevel ?? "normal")}
        />
        <span>最近刷新：{props.lastUpdatedText}</span>
      </div>
    </header>
  );
}
