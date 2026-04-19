import { useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { ProjectOverviewPage } from "../../features/projects/ProjectOverviewPage";
import {
  buildProjectOverviewRoute,
  projectOverviewRouteSegmentToView,
  type ProjectOverviewPageView,
} from "../../features/projects/lib/overviewNavigation";
import { buildTaskRoute } from "../../lib/task-route";

export function ProjectsPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { projectId } = useParams();
  const [searchParams] = useSearchParams();
  const routeProjectView = resolveRouteProjectView(location.pathname, projectId ?? null);

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
      routeProjectId={projectId ?? null}
      routeProjectView={routeProjectView}
      routeRequestedDeliverableId={searchParams.get("deliverableId")}
      routeRequestedApprovalId={searchParams.get("approvalId")}
    />
  );
}

function resolveRouteProjectView(
  pathname: string,
  projectId: string | null,
): Exclude<ProjectOverviewPageView, "overview"> | null {
  if (!projectId) {
    return null;
  }

  const normalizedPath = pathname.replace(/\/+$/g, "");
  const segments = normalizedPath.split("/").filter(Boolean);
  return projectOverviewRouteSegmentToView(segments[2] ?? null);
}
