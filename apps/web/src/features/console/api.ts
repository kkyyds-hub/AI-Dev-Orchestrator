import type { ConsoleOverview, HealthResponse } from "./types";
import { requestJson } from "../../lib/http";

export function fetchConsoleOverview(): Promise<ConsoleOverview> {
  return requestJson<ConsoleOverview>("/tasks/console");
}

export function fetchBackendHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/health");
}
