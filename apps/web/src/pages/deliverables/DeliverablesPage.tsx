import { useSearchParams } from "react-router-dom";
import { Navigate } from "react-router-dom";

import { useProjectScope } from "../shared/useProjectScope";

export function DeliverablesPage() {
  const [searchParams] = useSearchParams();
  const { selectedProjectId } = useProjectScope();

  const toParams = new URLSearchParams();
  toParams.set("tab", "deliverables");
  const deliverableId = searchParams.get("deliverableId");
  const pid = searchParams.get("projectId") ?? (selectedProjectId !== "all" ? selectedProjectId : null);
  if (pid) toParams.set("projectId", pid);
  if (deliverableId) toParams.set("deliverableId", deliverableId);

  return <Navigate to={`/delivery?${toParams.toString()}`} replace />;
}
