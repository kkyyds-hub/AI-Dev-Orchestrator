import { useSearchParams } from "react-router-dom";

import { DeliverableCenterPage } from "../../features/deliverables/DeliverableCenterPage";
import { ProjectContextSelector } from "../shared/ProjectContextSelector";
import { useUrlProjectSelection } from "../shared/useUrlProjectSelection";

type DeliverablesPageProps = {
  onNavigateToTask: (taskId: string, options?: { runId?: string | null }) => void;
};

export function DeliverablesPage(props: DeliverablesPageProps) {
  const [searchParams] = useSearchParams();
  const requestedDeliverableId = searchParams.get("deliverableId");
  const projectSelection = useUrlProjectSelection();

  return (
    <div className="space-y-6">
      <ProjectContextSelector
        eyebrow="Deliverables"
        title="交付物中心"
        description="交付物数据依赖项目上下文。先在这里选择项目，页面会自动把 projectId 写入 URL，刷新或分享时也能保留当前项目。"
        projects={projectSelection.projects}
        selectedProjectId={projectSelection.selectedProjectId}
        requestedProjectId={projectSelection.requestedProjectId}
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
        onNavigateToTask={props.onNavigateToTask}
      />
    </div>
  );
}
