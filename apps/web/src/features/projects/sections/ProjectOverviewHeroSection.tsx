type ProjectOverviewHeroSectionProps = {
  budgetStrategyLabel?: string | null;
  budgetPressureLevel?: string | null;
  lastUpdatedText: string;
};

export function ProjectOverviewHeroSection(props: ProjectOverviewHeroSectionProps) {
  return (
    <header
      data-testid="project-overview-hero-section"
      className="border-b border-[#333333] pb-5"
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-500">
            项目控制台
          </p>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-50 sm:text-3xl">
            项目工作区
          </h1>
        </div>

        <div className="text-xs text-zinc-500 lg:text-right">
          最近刷新：{props.lastUpdatedText}
        </div>
      </div>
    </header>
  );
}
