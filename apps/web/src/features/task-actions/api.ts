import { requestJson } from "../../lib/http";

import type {
  WorkerPoolRunResponse,
  TaskRetryResponse,
  TaskStateActionResponse,
  WorkerRunOnceResponse,
} from "./types";

export function runWorkerOnce(): Promise<WorkerRunOnceResponse> {
  return requestJson<WorkerRunOnceResponse>("/workers/run-once", {
    method: "POST",
  });
}

export function runWorkerPoolOnce(): Promise<WorkerPoolRunResponse> {
  return requestJson<WorkerPoolRunResponse>("/workers/run-pool-once", {
    method: "POST",
  });
}

export function retryTask(taskId: string): Promise<TaskRetryResponse> {
  return requestJson<TaskRetryResponse>(`/tasks/${taskId}/retry`, {
    method: "POST",
  });
}

export function pauseTask(
  taskId: string,
  reason = "Paused from console.",
): Promise<TaskStateActionResponse> {
  return requestJson<TaskStateActionResponse>(`/tasks/${taskId}/pause`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export function resumeTask(taskId: string): Promise<TaskStateActionResponse> {
  return requestJson<TaskStateActionResponse>(`/tasks/${taskId}/resume`, {
    method: "POST",
  });
}

export function requestHumanReview(
  taskId: string,
): Promise<TaskStateActionResponse> {
  return requestJson<TaskStateActionResponse>(`/tasks/${taskId}/request-human`, {
    method: "POST",
  });
}

export function resolveHumanReview(
  taskId: string,
): Promise<TaskStateActionResponse> {
  return requestJson<TaskStateActionResponse>(`/tasks/${taskId}/resolve-human`, {
    method: "POST",
  });
}
