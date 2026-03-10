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

export function useRunWorkerOnce() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: runWorkerOnce,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["console-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["worker-slots"] }),
        queryClient.invalidateQueries({ queryKey: ["task-detail"] }),
        queryClient.invalidateQueries({ queryKey: ["run-logs"] }),
        queryClient.invalidateQueries({ queryKey: ["decision-trace"] }),
      ]);
    },
  });
}

export function useRunWorkerPoolOnce() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: runWorkerPoolOnce,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["console-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["worker-slots"] }),
        queryClient.invalidateQueries({ queryKey: ["task-detail"] }),
        queryClient.invalidateQueries({ queryKey: ["run-logs"] }),
        queryClient.invalidateQueries({ queryKey: ["decision-trace"] }),
      ]);
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
