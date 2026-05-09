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
            Project Console
          </p>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-50 sm:text-3xl">
            Project workspace
          </h1>
        </div>

        <div className="text-xs text-zinc-500 lg:text-right">
          Last updated: {props.lastUpdatedText}
        </div>
      </div>
    </header>
  );
}
