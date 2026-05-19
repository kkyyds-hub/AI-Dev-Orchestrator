import { useSearchParams } from "react-router-dom";
import { Navigate } from "react-router-dom";

import { useProjectScope } from "../shared/useProjectScope";

export function ApprovalsPage() {
  const [searchParams] = useSearchParams();
  const { selectedProjectId } = useProjectScope();

  const toParams = new URLSearchParams();
  toParams.set("tab", "approvals");
  const approvalId = searchParams.get("approvalId");
  const pid = searchParams.get("projectId") ?? (selectedProjectId !== "all" ? selectedProjectId : null);
  if (pid) toParams.set("projectId", pid);
  if (approvalId) toParams.set("approvalId", approvalId);

  return <Navigate to={`/delivery?${toParams.toString()}`} replace />;
}
