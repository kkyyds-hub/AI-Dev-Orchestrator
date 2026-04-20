import { useEffect } from "react";
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { ProjectOverviewPage } from "../../features/projects/ProjectOverviewPage";
import {
  buildProjectOverviewRoute,
  getProjectOverviewDefaultTargetId,
  parseProjectOverviewHash,
  projectOverviewRouteSegmentToView,
  type ProjectOverviewPageView,
} from "../../features/projects/lib/overviewNavigation";
import { buildApprovalsRoute } from "../../lib/approval-route";
import { buildGovernanceRoute } from "../../lib/governance-route";
import { buildTaskRoute } from "../../lib/task-route";

export function ProjectsPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { projectId } = useParams();
  const [searchParams] = useSearchParams();
  const routeProjectView = resolveRouteProjectView(location.pathname, projectId ?? null);

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
        navigate(
          buildApprovalsRoute({
            projectId: nextProjectId,
            approvalId,
          }),
        )
      }
      resolveProjectViewHref={(view, nextProjectId) =>
        view === "memory-role-governance"
          ? buildGovernanceRoute({ projectId: nextProjectId })
          : buildProjectOverviewRoute({ projectId: nextProjectId, view })
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
