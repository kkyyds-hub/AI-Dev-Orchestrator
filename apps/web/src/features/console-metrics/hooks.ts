import { useQuery } from "@tanstack/react-query";

import {
  fetchConsoleBudgetHealth,
  fetchConsoleFailureDistribution,
  fetchConsoleMetrics,
  fetchConsoleRoutingDistribution,
  fetchWorkerSlots,
} from "./api";

export function useWorkerSlots() {
  return useQuery({
    queryKey: ["worker-slots"],
    queryFn: fetchWorkerSlots,
    refetchInterval: 5000,
  });
}

export function useConsoleMetricsOverview() {
  return useQuery({
    queryKey: ["console-metrics-overview"],
    queryFn: fetchConsoleMetrics,
    refetchInterval: 10_000,
  });
}

export function useConsoleBudgetHealth() {
  return useQuery({
    queryKey: ["console-budget-health"],
    queryFn: fetchConsoleBudgetHealth,
    refetchInterval: 10_000,
  });
}

export function useConsoleFailureDistribution() {
  return useQuery({
    queryKey: ["console-failure-distribution"],
    queryFn: fetchConsoleFailureDistribution,
    refetchInterval: 10_000,
  });
}

export function useConsoleRoutingDistribution() {
  return useQuery({
    queryKey: ["console-routing-distribution"],
    queryFn: fetchConsoleRoutingDistribution,
    refetchInterval: 10_000,
  });
}
