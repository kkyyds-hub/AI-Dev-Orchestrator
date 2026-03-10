import type { ConsoleOverview, HealthResponse } from "./types";

async function requestJson<T>(input: string): Promise<T> {
  const response = await fetch(input, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

export function fetchConsoleOverview(): Promise<ConsoleOverview> {
  return requestJson<ConsoleOverview>("/tasks/console");
}

export function fetchBackendHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/health");
}
