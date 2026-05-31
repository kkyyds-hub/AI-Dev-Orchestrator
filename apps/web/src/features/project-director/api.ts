import { requestJson } from "../../lib/http";

import type {
  ConfirmProjectDirectorGoalInput,
  ConfirmProjectDirectorPlanVersionInput,
  CreateProjectDirectorPlanVersionInput,
  CreateProjectDirectorSessionInput,
  CreateProjectDirectorTaskQueueInput,
  ProjectDirectorPlanReviewResponse,
  ProjectDirectorPlanVersion,
  ProjectDirectorSession,
  ProjectDirectorTaskCreationResponse,
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
    `/project-director/plan-versions/${input.planVersionId}/create-tasks`,
    {
      method: "POST",
    },
  );
}
