import { requestJson } from "../../lib/http";

import type {
  ConfirmProjectDirectorGoalInput,
  ConfirmProjectDirectorPlanVersionInput,
  CreateProjectDirectorPlanVersionInput,
  CreateProjectDirectorSessionInput,
  CreateProjectDirectorTaskQueueInput,
  FetchProjectDirectorWorkbenchResumeInput,
  ProjectDirectorAgentTeamConfigResponse,
  ProjectDirectorPlanReviewResponse,
  ProjectDirectorPlanVersion,
  ProjectDirectorRepositoryBindingConfigResponse,
  ProjectDirectorSession,
  ProjectDirectorSetupReadiness,
  ProjectDirectorSkillBindingConfigResponse,
  ProjectDirectorTaskCreationResponse,
  ProjectDirectorVerificationConfigResponse,
  ProjectDirectorWorkbenchResume,
  ProjectDirectorWorkbenchResumableSessionsResponse,
  ReviewProjectDirectorAgentTeamConfigInput,
  ReviewProjectDirectorRepositoryBindingConfigInput,
  ReviewProjectDirectorSkillBindingConfigInput,
  ReviewProjectDirectorVerificationConfigInput,
  ReviewProjectDirectorPlanVersionInput,
  SubmitProjectDirectorAnswersInput,
} from "./types";

export function createProjectDirectorSession(
  input: CreateProjectDirectorSessionInput,
): Promise<ProjectDirectorSession> {
  return requestJson<ProjectDirectorSession>("/project-director/sessions", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function fetchProjectDirectorWorkbenchResume(
  input: FetchProjectDirectorWorkbenchResumeInput,
): Promise<ProjectDirectorWorkbenchResume> {
  const params = new URLSearchParams({ mode: input.mode });
  if (input.projectId) {
    params.set("project_id", input.projectId);
  }
  if (input.sessionId) {
    params.set("session_id", input.sessionId);
  }

  return requestJson<ProjectDirectorWorkbenchResume>(
    `/project-director/workbench/resume?${params.toString()}`,
  );
}

export function fetchProjectDirectorWorkbenchResumableSessions(): Promise<ProjectDirectorWorkbenchResumableSessionsResponse> {
  return requestJson<ProjectDirectorWorkbenchResumableSessionsResponse>(
    "/project-director/workbench/resumable-sessions",
  );
}

export function submitProjectDirectorAnswers(
  input: SubmitProjectDirectorAnswersInput,
): Promise<ProjectDirectorSession> {
  return requestJson<ProjectDirectorSession>(
    `/project-director/sessions/${input.sessionId}/answers`,
    {
      method: "POST",
      body: JSON.stringify({ answers: input.answers }),
    },
  );
}

export function confirmProjectDirectorGoal(
  input: ConfirmProjectDirectorGoalInput,
): Promise<ProjectDirectorSession> {
  return requestJson<ProjectDirectorSession>(
    `/project-director/sessions/${input.sessionId}/confirm`,
    {
      method: "POST",
    },
  );
}

export function createProjectDirectorPlanVersion(
  input: CreateProjectDirectorPlanVersionInput,
): Promise<ProjectDirectorPlanVersion> {
  return requestJson<ProjectDirectorPlanVersion>(
    `/project-director/sessions/${input.sessionId}/plan-versions`,
    {
      method: "POST",
    },
  );
}

export function confirmProjectDirectorPlanVersion(
  input: ConfirmProjectDirectorPlanVersionInput,
): Promise<ProjectDirectorPlanVersion> {
  return requestJson<ProjectDirectorPlanVersion>(
    `/project-director/plan-versions/${input.planVersionId}/confirm`,
    {
      method: "POST",
    },
  );
}

export function reviewProjectDirectorPlanVersion(
  input: ReviewProjectDirectorPlanVersionInput,
): Promise<ProjectDirectorPlanReviewResponse> {
  return requestJson<ProjectDirectorPlanReviewResponse>(
    `/project-director/plan-versions/${input.planVersionId}/review`,
    {
      method: "POST",
      body: JSON.stringify({
        action: input.action,
        feedback: input.feedback ?? "",
      }),
    },
  );
}

export function createProjectDirectorTaskQueue(
  input: CreateProjectDirectorTaskQueueInput,
): Promise<ProjectDirectorTaskCreationResponse> {
  return requestJson<ProjectDirectorTaskCreationResponse>(
    `/project-director/plan-versions/${input.planVersionId}/create-formal-project`,
    {
      method: "POST",
    },
  );
}

export function fetchProjectDirectorSetupReadiness(
  projectId: string,
): Promise<ProjectDirectorSetupReadiness> {
  return requestJson<ProjectDirectorSetupReadiness>(
    `/project-director/projects/${projectId}/setup-readiness`,
  );
}

export function fetchProjectDirectorAgentTeamConfig(
  projectId: string,
): Promise<ProjectDirectorAgentTeamConfigResponse> {
  return requestJson<ProjectDirectorAgentTeamConfigResponse>(
    `/project-director/projects/${projectId}/agent-team-config`,
  );
}

export function reviewProjectDirectorAgentTeamConfig(
  input: ReviewProjectDirectorAgentTeamConfigInput,
): Promise<ProjectDirectorAgentTeamConfigResponse> {
  return requestJson<ProjectDirectorAgentTeamConfigResponse>(
    `/project-director/projects/${input.projectId}/agent-team-config/review`,
    {
      method: "POST",
      body: JSON.stringify({
        action: input.action,
        note: input.note ?? "",
      }),
    },
  );
}

export function fetchProjectDirectorSkillBindingConfig(
  projectId: string,
): Promise<ProjectDirectorSkillBindingConfigResponse> {
  return requestJson<ProjectDirectorSkillBindingConfigResponse>(
    `/project-director/projects/${projectId}/skill-binding-config`,
  );
}

export function reviewProjectDirectorSkillBindingConfig(
  input: ReviewProjectDirectorSkillBindingConfigInput,
): Promise<ProjectDirectorSkillBindingConfigResponse> {
  return requestJson<ProjectDirectorSkillBindingConfigResponse>(
    `/project-director/projects/${input.projectId}/skill-binding-config/review`,
    {
      method: "POST",
      body: JSON.stringify({
        action: input.action,
        note: input.note ?? "",
      }),
    },
  );
}

export function fetchProjectDirectorRepositoryBindingConfig(
  projectId: string,
): Promise<ProjectDirectorRepositoryBindingConfigResponse> {
  return requestJson<ProjectDirectorRepositoryBindingConfigResponse>(
    `/project-director/projects/${projectId}/repository-binding-config`,
  );
}

export function reviewProjectDirectorRepositoryBindingConfig(
  input: ReviewProjectDirectorRepositoryBindingConfigInput,
): Promise<ProjectDirectorRepositoryBindingConfigResponse> {
  return requestJson<ProjectDirectorRepositoryBindingConfigResponse>(
    `/project-director/projects/${input.projectId}/repository-binding-config/review`,
    {
      method: "POST",
      body: JSON.stringify({
        action: input.action,
        note: input.note ?? "",
      }),
    },
  );
}

export function fetchProjectDirectorVerificationConfig(
  projectId: string,
): Promise<ProjectDirectorVerificationConfigResponse> {
  return requestJson<ProjectDirectorVerificationConfigResponse>(
    `/project-director/projects/${projectId}/verification-config`,
  );
}

export function reviewProjectDirectorVerificationConfig(
  input: ReviewProjectDirectorVerificationConfigInput,
): Promise<ProjectDirectorVerificationConfigResponse> {
  return requestJson<ProjectDirectorVerificationConfigResponse>(
    `/project-director/projects/${input.projectId}/verification-config/review`,
    {
      method: "POST",
      body: JSON.stringify({
        action: input.action,
        note: input.note ?? "",
      }),
    },
  );
}
