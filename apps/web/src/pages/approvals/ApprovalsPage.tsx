import { useSearchParams } from "react-router-dom";

import { ApprovalInboxPage } from "../../features/approvals/ApprovalInboxPage";
import { ProjectContextSelector } from "../shared/ProjectContextSelector";
import { useUrlProjectSelection } from "../shared/useUrlProjectSelection";

export function ApprovalsPage() {
  const [searchParams] = useSearchParams();
  const requestedApprovalId = searchParams.get("approvalId");
  const projectSelection = useUrlProjectSelection();

  return (
    <div className="space-y-6">
      <ProjectContextSelector
        eyebrow="Approvals"
        title="审批中心"
        description="审批队列依赖项目上下文。先在这里选择项目，页面会自动把 projectId 写入 URL，刷新或分享时也能保留当前项目。"
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

      <ApprovalInboxPage
        projectId={projectSelection.selectedProjectId}
        projectName={projectSelection.selectedProject?.name ?? null}
        requestedApprovalId={requestedApprovalId}
      />
    </div>
  );
}
