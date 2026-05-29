import { useMutation } from "@tanstack/react-query";

import {
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
