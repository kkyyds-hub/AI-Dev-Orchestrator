import { Link } from "react-router-dom";

import {
  buildProjectOverviewRoute,
  type ProjectOverviewNavigationItem,
  type ProjectOverviewPageView,
} from "../lib/overviewNavigation";

type ProjectOverviewModuleNavSectionProps = {
  activeView: ProjectOverviewPageView;
  projectId: string | null;
  navigationItems: readonly ProjectOverviewNavigationItem[];
  onNavigateToOverviewSection: (sectionId: string) => void;
  resolvePageHref?: (
    item: Extract<ProjectOverviewNavigationItem, { kind: "page" }>,
    projectId: string,
  ) => string | null | undefined;
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
      className="rounded-3xl border border-[#333333] bg-[#242424] p-5 shadow-sm shadow-black/10"
    >
      <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-600">
            Project Domain Navigation
          </p>
          <h2
            data-testid="project-overview-module-nav-title"
            className="mt-2 text-lg font-semibold text-zinc-100"
          >
            项目域模块导航
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            通过统一入口进入项目总览、协作、交付、审批与治理模块。
          </p>
        </div>
        <div className="text-xs text-zinc-600">
          页内入口 {sectionEntryCount} 个 / 路由入口 {pageEntryCount} 个
        </div>
      </div>

      <div
        data-testid="project-overview-module-nav-grid"
        className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3"
      >
        {props.navigationItems.map((item) => {
          const isActive = props.activeView === item.view;
          const sharedClassName = `group relative overflow-hidden rounded-2xl border px-4 py-4 text-left transition ${
            isActive
              ? "border-[#555555] bg-[#303030] shadow-sm shadow-black/20"
              : "border-[#333333] bg-[#1f1f1f] hover:border-zinc-600 hover:bg-[#292929]"
          }`;

          const pageHref =
            props.projectId && item.kind === "page"
              ? props.resolvePageHref?.(item, props.projectId) ??
                buildProjectOverviewRoute({
                  projectId: props.projectId,
                  view: item.view,
                })
              : null;

          if (item.kind === "section") {
            return (
              <button
                key={item.id}
                type="button"
                data-testid={`project-overview-nav-${item.id}`}
                onClick={() => props.onNavigateToOverviewSection(item.id)}
                className={sharedClassName}
              >
                <NavigationCardContent
                  label={item.label}
                  description={item.description}
                  meta={`页内定位 #${item.id}`}
                />
              </button>
            );
          }

          if (!props.projectId) {
            return (
              <button
                key={item.id}
                type="button"
                data-testid={`project-overview-nav-${item.id}`}
                onClick={() => props.onNavigateToOverviewPage(item.view, item.id)}
                className={sharedClassName}
              >
                <NavigationCardContent
                  label={item.label}
                  description={item.description}
                  meta="先选择项目"
                />
              </button>
            );
          }

          return (
            <Link
              key={item.id}
              data-testid={`project-overview-nav-${item.id}`}
              to={pageHref ?? "/projects"}
              className={`${sharedClassName} block`}
            >
              <NavigationCardContent
                label={item.label}
                description={item.description}
                meta="路由页面"
              />
            </Link>
          );
        })}
      </div>
    </section>
  );
}

function NavigationCardContent(props: {
  label: string;
  description: string;
  meta: string;
}) {
  return (
    <div className="relative">
      <div className="absolute -right-3 -top-3 h-12 w-12 rounded-full border border-[#333333] bg-[#242424] opacity-0 transition group-hover:opacity-100" />
      <div className="text-sm font-medium text-zinc-100">{props.label}</div>
      <p className="mt-2 text-sm leading-6 text-zinc-500">{props.description}</p>
      <div className="mt-3 text-xs uppercase tracking-[0.18em] text-zinc-600">
        {props.meta}
      </div>
    </div>
  );
}
