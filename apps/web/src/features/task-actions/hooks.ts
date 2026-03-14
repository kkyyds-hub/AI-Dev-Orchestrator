import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  pauseTask,
  requestHumanReview,
  resolveHumanReview,
  resumeTask,
  retryTask,
  runWorkerPoolOnce,
  runWorkerOnce,
} from "./api";

async function invalidateOperationalQueries(queryClient: ReturnType<typeof useQueryClient>) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["console-overview"] }),
    queryClient.invalidateQueries({ queryKey: ["console-metrics-overview"] }),
    queryClient.invalidateQueries({ queryKey: ["console-budget-health"] }),
    queryClient.invalidateQueries({ queryKey: ["console-failure-distribution"] }),
    queryClient.invalidateQueries({ queryKey: ["console-routing-distribution"] }),
    queryClient.invalidateQueries({ queryKey: ["worker-slots"] }),
    queryClient.invalidateQueries({ queryKey: ["review-clusters"] }),
    queryClient.invalidateQueries({ queryKey: ["task-detail"] }),
    queryClient.invalidateQueries({ queryKey: ["task-decision-history"] }),
    queryClient.invalidateQueries({ queryKey: ["run-logs"] }),
    queryClient.invalidateQueries({ queryKey: ["decision-trace"] }),
  ]);
}

export function useRunWorkerOnce() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: runWorkerOnce,
    onSuccess: async () => {
      await invalidateOperationalQueries(queryClient);
    },
  });
}

export function useRunWorkerPoolOnce() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: runWorkerPoolOnce,
    onSuccess: async () => {
      await invalidateOperationalQueries(queryClient);
    },
  });
}

export function useRetryTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: retryTask,
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["console-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["task-detail", result.task_id] }),
        queryClient.invalidateQueries({ queryKey: ["run-logs"] }),
        queryClient.invalidateQueries({ queryKey: ["decision-trace"] }),
      ]);
    },
  });
}

function useTaskStateMutation<TData>(
  mutationFn: (taskId: string) => Promise<TData>,
  getTaskId: (result: TData) => string,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn,
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["console-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["task-detail", getTaskId(result)] }),
        queryClient.invalidateQueries({ queryKey: ["run-logs"] }),
      ]);
    },
  });
}

export function usePauseTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (taskId: string) => pauseTask(taskId),
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["console-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["task-detail", result.task_id] }),
      ]);
    },
  });
}

export function useResumeTask() {
  return useTaskStateMutation(resumeTask, (result) => result.task_id);
}

export function useRequestHumanReview() {
  return useTaskStateMutation(requestHumanReview, (result) => result.task_id);
}

export function useResolveHumanReview() {
  return useTaskStateMutation(resolveHumanReview, (result) => result.task_id);
}
