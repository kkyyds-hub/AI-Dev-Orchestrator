import { requestJson } from "../../lib/http";

import type {
  ConsoleBudgetHealth,
  ConsoleFailureDistribution,
  ConsoleMetricsOverview,
  ConsoleRoutingDistribution,
  WorkerSlotOverview,
} from "./types";

export function fetchWorkerSlots(): Promise<WorkerSlotOverview> {
  return requestJson<WorkerSlotOverview>("/console/worker-slots");
}

export function fetchConsoleMetrics(): Promise<ConsoleMetricsOverview> {
  return requestJson<ConsoleMetricsOverview>("/console/metrics");
}

export function fetchConsoleBudgetHealth(): Promise<ConsoleBudgetHealth> {
  return requestJson<ConsoleBudgetHealth>("/console/budget-health");
}

export function fetchConsoleFailureDistribution(): Promise<ConsoleFailureDistribution> {
  return requestJson<ConsoleFailureDistribution>("/console/failure-distribution");
}

export function fetchConsoleRoutingDistribution(): Promise<ConsoleRoutingDistribution> {
  return requestJson<ConsoleRoutingDistribution>("/console/routing-distribution");
}
