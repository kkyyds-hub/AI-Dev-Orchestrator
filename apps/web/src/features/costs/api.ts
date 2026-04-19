import { requestJson } from "../../lib/http";
import type { ProjectCostDashboardSnapshot } from "./types";

export function fetchProjectCostDashboardSnapshot(
  projectId: string,
): Promise<ProjectCostDashboardSnapshot> {
  return requestJson<ProjectCostDashboardSnapshot>(
    `/projects/${projectId}/cost-dashboard`,
  );
}
