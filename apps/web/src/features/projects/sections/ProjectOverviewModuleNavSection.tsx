import type {
  ProjectOverviewNavigationItem,
  ProjectOverviewPageView,
} from "../lib/overviewNavigation";

type ProjectOverviewModuleNavSectionProps = {
  activeView: ProjectOverviewPageView;
  navigationItems: readonly ProjectOverviewNavigationItem[];
  onNavigateToOverviewSection: (sectionId: string) => void;
  onNavigateToOverviewPage: (
    view: Exclude<ProjectOverviewPageView, "overview">,
    targetId?: string | null,
  ) => void;
};

export function ProjectOverviewModuleNavSection(
  props: ProjectOverviewModuleNavSectionProps,
) {
  const sectionEntryCount = props.navigationItems.filter(
    (item) => item.kind === "section",
  ).length;
  const pageEntryCount = props.navigationItems.length - sectionEntryCount;

  return (
    <section
      data-testid="project-overview-module-nav"
      className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-xl shadow-slate-950/30"
    >
      <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.24em] text-cyan-300">
            Frontend Entry Governance
          </p>
          <h2
            data-testid="project-overview-module-nav-title"
            className="mt-2 text-lg font-semibold text-slate-50"
          >
            项目概览统一导航
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            统一“页内区块定位”和“跨页入口跳达”，继续使用 hash 页面态，不做正式 Router 重构。
          </p>
        </div>
        <div className="text-xs text-slate-500">
          当前入口：{sectionEntryCount} 个页内区块 / {pageEntryCount} 个跨页视图
        </div>
      </div>

      <div
        data-testid="project-overview-module-nav-grid"
        className="mt-4 grid gap-3 lg:grid-cols-3"
      >
        {props.navigationItems.map((item) => (
          <button
            key={item.id}
            type="button"
            data-testid={`project-overview-nav-${item.id}`}
            onClick={() =>
              item.kind === "section"
                ? props.onNavigateToOverviewSection(item.id)
                : props.onNavigateToOverviewPage(item.view, item.id)
            }
            className={`rounded-2xl border px-4 py-4 text-left transition ${
              props.activeView === item.view
                ? "border-cyan-400/60 bg-cyan-500/10"
                : "border-slate-800 bg-slate-950/60 hover:border-cyan-400/40 hover:bg-cyan-500/10"
            }`}
          >
            <div className="text-sm font-medium text-slate-100">{item.label}</div>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              {item.description}
            </p>
            <div className="mt-3 text-xs uppercase tracking-[0.18em] text-cyan-300">
              {item.kind === "section" ? `页内定位 #${item.id}` : "跨页入口"}
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
