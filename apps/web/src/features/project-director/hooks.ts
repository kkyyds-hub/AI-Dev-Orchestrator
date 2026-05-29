import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  createProjectDirectorTaskQueue,
  confirmProjectDirectorGoal,
  confirmProjectDirectorPlanVersion,
  createProjectDirectorPlanVersion,
  createProjectDirectorSession,
  submitProjectDirectorAnswers,
} from "./api";

export function useCreateProjectDirectorSession() {
  return useMutation({
    mutationFn: createProjectDirectorSession,
  });
}

export function useSubmitProjectDirectorAnswers() {
  return useMutation({
    mutationFn: submitProjectDirectorAnswers,
  });
}

export function useConfirmProjectDirectorGoal() {
  return useMutation({
    mutationFn: confirmProjectDirectorGoal,
  });
}

export function useCreateProjectDirectorPlanVersion() {
  return useMutation({
    mutationFn: createProjectDirectorPlanVersion,
  });
}

export function useConfirmProjectDirectorPlanVersion() {
  return useMutation({
    mutationFn: confirmProjectDirectorPlanVersion,
  });
}

export function useCreateProjectDirectorTaskQueue() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createProjectDirectorTaskQueue,
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["console-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["boss-project-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["project-detail"] }),
        queryClient.invalidateQueries({ queryKey: ["project-detail", result.project_id] }),
        queryClient.invalidateQueries({ queryKey: ["project-timeline", result.project_id] }),
      ]);
    },
  });
}
