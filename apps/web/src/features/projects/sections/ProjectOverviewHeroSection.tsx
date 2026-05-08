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
      className="relative overflow-hidden rounded-3xl border border-[#333333] bg-[#242424] px-6 py-6 shadow-sm shadow-black/20 lg:px-7"
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(113,113,122,0.18),transparent_34%),linear-gradient(135deg,rgba(255,255,255,0.05),transparent_46%)]" />

      <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl space-y-3">
          <p className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-500">
            Project Console
          </p>
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-zinc-50 sm:text-4xl">
              项目控制台
            </h1>
            <p className="mt-3 text-sm leading-6 text-zinc-400">
              汇总项目阶段、仓库上下文、协同链路与风险信号，把项目选择、模块跳转和任务追踪收拢到同一个工作台。
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs text-zinc-400">
            {["项目总览", "阶段治理", "交付闭环"].map((label) => (
              <span
                key={label}
                className="rounded-full border border-[#3a3a3a] bg-[#1f1f1f]/80 px-3 py-1"
              >
                {label}
              </span>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-2 rounded-2xl border border-[#333333] bg-[#1f1f1f]/80 p-4 text-xs text-zinc-500 lg:min-w-[260px]">
          <span className="uppercase tracking-[0.2em] text-zinc-600">
            Console Status
          </span>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge
              label={props.budgetStrategyLabel ?? "预算快照"}
              tone={mapBudgetPressureTone(props.budgetPressureLevel ?? "normal")}
            />
          </div>
          <span>最近刷新：{props.lastUpdatedText}</span>
        </div>
      </div>
    </header>
  );
}
