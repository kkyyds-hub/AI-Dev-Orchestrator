import { useSearchParams } from "react-router-dom";

import { ApprovalInboxPage } from "../../features/approvals/ApprovalInboxPage";
import { ProjectContextSelector } from "../shared/ProjectContextSelector";
import { useUrlProjectSelection } from "../shared/useUrlProjectSelection";

export function ApprovalsPage() {
  const [searchParams] = useSearchParams();
  const requestedApprovalId = searchParams.get("approvalId");
  const projectSelection = useUrlProjectSelection({
    resetParamKeys: ["approvalId"],
  });

  return (
    <div className="space-y-6">
      <ProjectContextSelector
        eyebrow="审批中心"
        title="审批中心"
        description="先选择要处理的项目，再查看该项目的审批队列、审批处理与放行状态。"
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

      <ApprovalInboxPage
        projectId={projectSelection.selectedProjectId}
        projectName={projectSelection.selectedProject?.name ?? null}
        requestedApprovalId={requestedApprovalId}
      />
    </div>
  );
}
