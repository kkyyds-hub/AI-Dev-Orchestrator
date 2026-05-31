import { requestJson } from "../../lib/http";
import type { ProjectAiSummary, ProjectAiSummaryCurrentResponse } from "./types";

export function fetchProjectAiSummary(
  projectId: string,
): Promise<ProjectAiSummaryCurrentResponse> {
  return requestJson<ProjectAiSummaryCurrentResponse>(
    `/projects/${projectId}/ai-summary`,
  );
}

export function generateProjectAiSummary(
  projectId: string,
): Promise<ProjectAiSummary> {
  return requestJson<ProjectAiSummary>(
    `/projects/${projectId}/ai-summary/generate`,
    { method: "POST" },
  );
}

export function regenerateProjectAiSummary(
  projectId: string,
): Promise<ProjectAiSummary> {
  return requestJson<ProjectAiSummary>(
    `/projects/${projectId}/ai-summary/regenerate`,
    { method: "POST" },
  );
}
