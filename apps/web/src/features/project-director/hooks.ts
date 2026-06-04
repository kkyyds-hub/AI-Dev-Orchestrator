import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createProjectDirectorTaskQueue,
  confirmProjectDirectorGoal,
  confirmProjectDirectorPlanVersion,
  createProjectDirectorPlanVersion,
  createProjectDirectorSession,
  fetchProjectDirectorAgentTeamConfig,
  fetchProjectDirectorRepositoryBindingConfig,
  fetchProjectDirectorSetupReadiness,
  fetchProjectDirectorSkillBindingConfig,
  fetchProjectDirectorSessionMessages,
  fetchProjectDirectorVerificationConfig,
  fetchProjectDirectorWorkbenchResume,
  fetchProjectDirectorWorkbenchResumableSessions,
  postProjectDirectorSessionMessage,
  reviewProjectDirectorAgentTeamConfig,
  reviewProjectDirectorRepositoryBindingConfig,
  reviewProjectDirectorSkillBindingConfig,
  reviewProjectDirectorVerificationConfig,
  reviewProjectDirectorPlanVersion,
  submitProjectDirectorAnswers,
} from "./api";

import type { FetchProjectDirectorWorkbenchResumeInput } from "./types";

export function useCreateProjectDirectorSession() {
  return useMutation({
    mutationFn: createProjectDirectorSession,
  });
}

export function useProjectDirectorWorkbenchResume(
  input: FetchProjectDirectorWorkbenchResumeInput,
) {
  return useQuery({
    queryKey: [
      "project-director",
      "workbench-resume",
      input.mode,
      input.projectId ?? null,
      input.sessionId ?? null,
    ],
    queryFn: () => fetchProjectDirectorWorkbenchResume(input),
    retry: false,
  });
}

export function useProjectDirectorWorkbenchResumableSessions() {
  return useQuery({
    queryKey: ["project-director", "workbench-resumable-sessions"],
    queryFn: fetchProjectDirectorWorkbenchResumableSessions,
    retry: false,
  });
}

export function useProjectDirectorSessionMessages(sessionId: string | null) {
  return useQuery({
    queryKey: ["project-director", "session-messages", sessionId],
    queryFn: () => fetchProjectDirectorSessionMessages(sessionId as string),
    enabled: Boolean(sessionId),
    retry: false,
  });
}

export function usePostProjectDirectorSessionMessage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: postProjectDirectorSessionMessage,
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({
        queryKey: ["project-director", "session-messages", result.session_id],
      });
    },
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

export function useReviewProjectDirectorPlanVersion() {
  return useMutation({
    mutationFn: reviewProjectDirectorPlanVersion,
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
        queryClient.invalidateQueries({
          queryKey: ["project-director", "setup-readiness", result.project_id],
        }),
      ]);
    },
  });
}

export function useProjectDirectorSetupReadiness(projectId: string | null) {
  return useQuery({
    queryKey: ["project-director", "setup-readiness", projectId],
    queryFn: () => fetchProjectDirectorSetupReadiness(projectId as string),
    enabled: Boolean(projectId),
    retry: false,
  });
}

export function useProjectDirectorAgentTeamConfig(projectId: string | null) {
  return useQuery({
    queryKey: ["project-director", "agent-team-config", projectId],
    queryFn: () => fetchProjectDirectorAgentTeamConfig(projectId as string),
    enabled: Boolean(projectId),
    retry: false,
  });
}

export function useReviewProjectDirectorAgentTeamConfigMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: reviewProjectDirectorAgentTeamConfig,
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["project-director", "agent-team-config", result.project_id],
        }),
        queryClient.invalidateQueries({ queryKey: ["project-detail"] }),
        queryClient.invalidateQueries({ queryKey: ["project-detail", result.project_id] }),
        queryClient.invalidateQueries({
          queryKey: ["project-director", "setup-readiness", result.project_id],
        }),
      ]);
    },
  });
}

export function useProjectDirectorSkillBindingConfig(projectId: string | null) {
  return useQuery({
    queryKey: ["project-director", "skill-binding-config", projectId],
    queryFn: () => fetchProjectDirectorSkillBindingConfig(projectId as string),
    enabled: Boolean(projectId),
    retry: false,
  });
}

export function useReviewProjectDirectorSkillBindingConfigMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: reviewProjectDirectorSkillBindingConfig,
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["project-director", "skill-binding-config", result.project_id],
        }),
        queryClient.invalidateQueries({ queryKey: ["project-detail"] }),
        queryClient.invalidateQueries({ queryKey: ["project-detail", result.project_id] }),
        queryClient.invalidateQueries({
          queryKey: ["project-director", "setup-readiness", result.project_id],
        }),
      ]);
    },
  });
}

export function useProjectDirectorRepositoryBindingConfig(projectId: string | null) {
  return useQuery({
    queryKey: ["project-director", "repository-binding-config", projectId],
    queryFn: () => fetchProjectDirectorRepositoryBindingConfig(projectId as string),
    enabled: Boolean(projectId),
    retry: false,
  });
}

export function useReviewProjectDirectorRepositoryBindingConfigMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: reviewProjectDirectorRepositoryBindingConfig,
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["project-director", "repository-binding-config", result.project_id],
        }),
        queryClient.invalidateQueries({ queryKey: ["project-detail"] }),
        queryClient.invalidateQueries({ queryKey: ["project-detail", result.project_id] }),
        queryClient.invalidateQueries({
          queryKey: ["project-director", "setup-readiness", result.project_id],
        }),
      ]);
    },
  });
}

export function useProjectDirectorVerificationConfig(projectId: string | null) {
  return useQuery({
    queryKey: ["project-director", "verification-config", projectId],
    queryFn: () => fetchProjectDirectorVerificationConfig(projectId as string),
    enabled: Boolean(projectId),
    retry: false,
  });
}

export function useReviewProjectDirectorVerificationConfigMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: reviewProjectDirectorVerificationConfig,
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["project-director", "verification-config", result.project_id],
        }),
        queryClient.invalidateQueries({ queryKey: ["project-detail"] }),
        queryClient.invalidateQueries({ queryKey: ["project-detail", result.project_id] }),
        queryClient.invalidateQueries({
          queryKey: ["project-director", "setup-readiness", result.project_id],
        }),
      ]);
    },
  });
}
