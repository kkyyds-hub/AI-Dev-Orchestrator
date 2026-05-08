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
  resolvePageHref?: (
    view: Exclude<ProjectOverviewPageView, "overview">,
    projectId: string,
  ) => string | null | undefined;
};

export function ProjectOverviewModuleNavSection(
  props: ProjectOverviewModuleNavSectionProps,
) {
  return (
    <nav
      aria-label="项目视图"
      data-testid="project-overview-module-nav"
      className="rounded-3xl border border-[#333333] bg-[#242424] p-2 shadow-sm shadow-black/10"
    >
      <div
        data-testid="project-overview-module-nav-tabs"
        className="flex gap-1 overflow-x-auto"
      >
        {props.navigationItems.map((item) => {
          const isActive = props.activeView === item.view;
          const href = buildViewHref({
            item,
            projectId: props.projectId,
            resolvePageHref: props.resolvePageHref,
          });

          return (
            <Link
              key={item.id}
              data-testid={`project-overview-nav-${item.id}`}
              to={href}
              aria-current={isActive ? "page" : undefined}
              className={`group min-w-max rounded-2xl px-4 py-3 text-sm font-medium transition ${
                isActive
                  ? "bg-[#303030] text-zinc-50 shadow-sm shadow-black/20"
                  : "text-zinc-500 hover:bg-[#292929] hover:text-zinc-200"
              }`}
              title={item.description}
            >
              {item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

function buildViewHref(input: {
  item: ProjectOverviewNavigationItem;
  projectId: string | null;
  resolvePageHref?: (
    view: Exclude<ProjectOverviewPageView, "overview">,
    projectId: string,
  ) => string | null | undefined;
}) {
  if (!input.projectId) {
    return "/projects";
  }

  if (input.item.view === "overview") {
    return buildProjectOverviewRoute({
      projectId: input.projectId,
      view: "overview",
    });
  }

  return (
    input.resolvePageHref?.(input.item.view, input.projectId) ??
    buildProjectOverviewRoute({
      projectId: input.projectId,
      view: input.item.view,
    })
  );
}
