import { useParams, useSearchParams } from "react-router-dom";

import { ProjectOverviewPage } from "../../features/projects/ProjectOverviewPage";

export function ProjectsPage() {
  const { projectId } = useParams();
  const [searchParams] = useSearchParams();

  return (
    <ProjectOverviewPage
      routeProjectId={projectId ?? null}
      routeRequestedDeliverableId={searchParams.get("deliverableId")}
      routeRequestedApprovalId={searchParams.get("approvalId")}
    />
  );
}
