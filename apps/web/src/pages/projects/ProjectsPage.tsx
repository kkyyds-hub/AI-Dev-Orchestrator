import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { ProjectOverviewPage } from "../../features/projects/ProjectOverviewPage";
import { buildTaskRoute } from "../../lib/task-route";

export function ProjectsPage() {
  const navigate = useNavigate();
  const { projectId } = useParams();
  const [searchParams] = useSearchParams();

  return (
    <ProjectOverviewPage
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
      routeRequestedDeliverableId={searchParams.get("deliverableId")}
      routeRequestedApprovalId={searchParams.get("approvalId")}
    />
  );
}
