import { requestJson } from "../../lib/http";

import type { ProjectStrategyPreview, StrategyRulesSnapshot } from "./types";

export function fetchProjectStrategyPreview(
  projectId: string,
): Promise<ProjectStrategyPreview> {
  return requestJson<ProjectStrategyPreview>(`/strategy/projects/${projectId}/preview`);
}

export function fetchStrategyRules(): Promise<StrategyRulesSnapshot> {
  return requestJson<StrategyRulesSnapshot>("/strategy/rules");
}

export function updateStrategyRules(input: {
  rules: Record<string, unknown>;
}): Promise<StrategyRulesSnapshot> {
  return requestJson<StrategyRulesSnapshot>("/strategy/rules", {
    method: "PUT",
    body: JSON.stringify(input),
  });
}
