import { useEffect } from "react";
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { ProjectOverviewPage } from "../../features/projects/ProjectOverviewPage";
import {
  buildProjectOverviewRoute,
  getProjectOverviewDefaultTargetId,
  parseProjectOverviewHash,
  type ProjectOverviewPageView,
} from "../../features/projects/lib/overviewNavigation";
import { buildTaskRoute } from "../../lib/task-route";
import { useProjectScope } from "../shared/useProjectScope";

type ProjectOverviewRouteContainerProps = {
  routeProjectView?: Exclude<ProjectOverviewPageView, "overview"> | null;
};

export function ProjectOverviewRouteContainer(
  props: ProjectOverviewRouteContainerProps,
) {
  const location = useLocation();
  const navigate = useNavigate();
  const { projectId } = useParams();
  const [searchParams] = useSearchParams();
  const routeProjectView = props.routeProjectView ?? null;
  const { selectedProjectId, setSelectedProjectId } = useProjectScope();

  // Sync shared project context when navigating to a specific project route
  useEffect(() => {
    if (projectId && projectId !== selectedProjectId) {
      setSelectedProjectId(projectId);
    }
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!projectId || !location.hash || location.hash.startsWith("#boss-drilldown")) {
      return;
    }

    const parsed = parseProjectOverviewHash(location.hash);
    if (!parsed || parsed.view === "overview") {
      return;
    }

    const nextPathname = buildProjectOverviewRoute({
      projectId,
      view: parsed.view,
    });
    const defaultTargetId = getProjectOverviewDefaultTargetId(parsed.view);
    const nextHash =
      parsed.targetId && parsed.targetId !== defaultTargetId ? `#${parsed.targetId}` : "";
    const currentHash = location.hash;

    if (location.pathname === nextPathname && currentHash === nextHash) {
      return;
    }

    navigate(
      {
        pathname: nextPathname,
        search: location.search,
        hash: nextHash,
      },
      { replace: true },
    );
  }, [location.hash, location.pathname, location.search, navigate, projectId]);

  return (
    <ProjectOverviewPage
      onNavigateToProjectView={(view, options) => {
        const nextProjectId = options?.projectId ?? projectId ?? null;
        if (!nextProjectId) {
          return false;
        }

        navigate(buildProjectOverviewRoute({ projectId: nextProjectId, view }));
        return true;
      }}
      onNavigateToTask={(taskId, options) =>
        navigate(
          buildTaskRoute({
            taskId,
            runId: options?.runId ?? null,
            from: "project",
            projectId: projectId ?? null,
          }),
        )
      }
      onNavigateToApproval={(nextProjectId, approvalId) =>
        navigate({
          pathname: buildProjectOverviewRoute({
            projectId: nextProjectId,
            view: "approval-inbox",
          }),
          search: `?${new URLSearchParams({ approvalId }).toString()}`,
        })
      }
      resolveProjectViewHref={(view, nextProjectId) =>
        buildProjectOverviewRoute({ projectId: nextProjectId, view })
      }
      routeProjectId={projectId ?? null}
      routeProjectView={routeProjectView}
      routeRequestedDeliverableId={searchParams.get("deliverableId")}
      routeRequestedApprovalId={searchParams.get("approvalId")}
    />
  );
}
