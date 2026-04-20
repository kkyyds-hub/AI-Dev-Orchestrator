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
      className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-xl shadow-slate-950/30"
    >
      <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.24em] text-cyan-300">
            Project Domain Navigation
          </p>
          <h2
            data-testid="project-overview-module-nav-title"
            className="mt-2 text-lg font-semibold text-slate-50"
          >
            ???????
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            ??????????????????????????????????
          </p>
        </div>
        <div className="text-xs text-slate-500">
          ?????{sectionEntryCount} ????? / {pageEntryCount} ??????
        </div>
      </div>

      <div
        data-testid="project-overview-module-nav-grid"
        className="mt-4 grid gap-3 lg:grid-cols-3"
      >
        {props.navigationItems.map((item) => {
          const isActive = props.activeView === item.view;
          const sharedClassName = `rounded-2xl border px-4 py-4 text-left transition ${
            isActive
              ? "border-cyan-400/60 bg-cyan-500/10"
              : "border-slate-800 bg-slate-950/60 hover:border-cyan-400/40 hover:bg-cyan-500/10"
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
                  meta={`???? #${item.id}`}
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
                  meta="?????"
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
                meta="?????"
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
    <>
      <div className="text-sm font-medium text-slate-100">{props.label}</div>
      <p className="mt-2 text-sm leading-6 text-slate-400">{props.description}</p>
      <div className="mt-3 text-xs uppercase tracking-[0.18em] text-cyan-300">
        {props.meta}
      </div>
    </>
  );
}
