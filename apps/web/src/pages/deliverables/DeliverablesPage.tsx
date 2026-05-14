import { useNavigate, useSearchParams } from "react-router-dom";

import { DeliverableCenterPage } from "../../features/deliverables/DeliverableCenterPage";
import { buildTaskRoute } from "../../lib/task-route";
import { ProjectContextSelector } from "../shared/ProjectContextSelector";
import { useUrlProjectSelection } from "../shared/useUrlProjectSelection";

export function DeliverablesPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const requestedDeliverableId = searchParams.get("deliverableId");
  const projectSelection = useUrlProjectSelection({
    resetParamKeys: ["deliverableId"],
  });

  return (
    <div className="space-y-6">
      <ProjectContextSelector
        eyebrow="Deliverables"
        title="交付物中心"
        description="先选择要查看的项目，再浏览该项目的交付物、版本快照和关联任务。"
        projects={projectSelection.projects}
        selectedProjectId={projectSelection.selectedProjectId}
        hasInvalidRequestedProject={projectSelection.hasInvalidRequestedProject}
        isLoading={projectSelection.overviewQuery.isLoading}
        errorMessage={
          projectSelection.overviewQuery.isError
            ? projectSelection.overviewQuery.error.message
            : null
        }
        onSelectProject={projectSelection.setSelectedProjectId}
      />

      <DeliverableCenterPage
        projectId={projectSelection.selectedProjectId}
        projectName={projectSelection.selectedProject?.name ?? null}
        requestedDeliverableId={requestedDeliverableId}
        onNavigateToTask={(taskId, options) =>
          navigate(
            buildTaskRoute({
              taskId,
              runId: options?.runId ?? null,
              from: "deliverables",
              projectId: projectSelection.selectedProjectId,
            }),
          )
        }
      />
    </div>
  );
}
