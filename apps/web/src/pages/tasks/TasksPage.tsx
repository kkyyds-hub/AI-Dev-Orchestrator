import { useParams, useSearchParams } from "react-router-dom";
import { Navigate } from "react-router-dom";

import { useProjectScope } from "../shared/useProjectScope";

export function TasksPage() {
  const { taskId } = useParams();
  const [searchParams] = useSearchParams();
  const { selectedProjectId } = useProjectScope();

  const toParams = new URLSearchParams();
  toParams.set("tab", "tasks");
  const pid = searchParams.get("projectId") ?? (selectedProjectId !== "all" ? selectedProjectId : null);
  if (pid) toParams.set("projectId", pid);
  if (taskId) toParams.set("taskId", taskId);

  return <Navigate to={`/execution?${toParams.toString()}`} replace />;
}
