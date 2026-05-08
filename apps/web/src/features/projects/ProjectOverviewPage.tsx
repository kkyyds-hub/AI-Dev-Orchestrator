import { ProjectOverviewViewSwitch } from "./components/ProjectOverviewViewSwitch";
import { PROJECT_OVERVIEW_NAVIGATION_ITEMS } from "./lib/overviewNavigation";
import {
  type ProjectOverviewPageProps,
  useProjectOverviewPageController,
} from "./hooks/useProjectOverviewPageController";
import { ProjectOverviewHeroSection } from "./sections/ProjectOverviewHeroSection";
import { ProjectOverviewModuleNavSection } from "./sections/ProjectOverviewModuleNavSection";

export function ProjectOverviewPage(props: ProjectOverviewPageProps) {
  const controller = useProjectOverviewPageController(props);
  const { activeView, lastUpdatedText, overviewQuery, selectedProjectId } = controller;

  return (
    <section data-testid="project-overview-page" className="space-y-7">
      <ProjectOverviewHeroSection
        budgetStrategyLabel={overviewQuery.data?.budget.strategy_label}
        budgetPressureLevel={overviewQuery.data?.budget.pressure_level}
        lastUpdatedText={lastUpdatedText}
      />

      <ProjectOverviewModuleNavSection
        activeView={activeView}
        projectId={selectedProjectId}
        navigationItems={PROJECT_OVERVIEW_NAVIGATION_ITEMS}
        resolvePageHref={(view, projectId) =>
          props.resolveProjectViewHref?.(view, projectId) ?? null
        }
      />

      {overviewQuery.isLoading && !overviewQuery.data ? (
        <section className="border-b border-[#333333] py-6 text-sm text-zinc-500">
          正在加载项目数据...
        </section>
      ) : null}

      {overviewQuery.isError ? (
        <section className="border-l-2 border-l-rose-400 py-4 pl-4 text-sm text-rose-100">
          项目总览加载失败：{overviewQuery.error.message}
        </section>
      ) : null}

      {overviewQuery.data ? (
        <ProjectOverviewViewSwitch
          activeView={activeView}
          controller={controller}
          overview={overviewQuery.data}
          onNavigateToTask={props.onNavigateToTask}
        />
      ) : null}
    </section>
  );
}
