import { requestJson } from "../../lib/http";

import type {
  DeliveryHumanApprovalRequest,
  DeliveryHumanApprovalResponse,
  WorkerPoolRunResponse,
  TaskRetryResponse,
  TaskStateActionResponse,
  WorkerRunOnceResponse,
} from "./types";

export class DeliveryHumanApprovalHttpError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "DeliveryHumanApprovalHttpError";
    this.status = status;
  }
}

export function runWorkerOnce(projectId?: string | null): Promise<WorkerRunOnceResponse> {
  const params = new URLSearchParams();
  if (projectId && projectId !== "all") {
    params.set("project_id", projectId);
  }

  const query = params.toString();
  return requestJson<WorkerRunOnceResponse>(`/workers/run-once${query ? `?${query}` : ""}`, {
    method: "POST",
  });
}

export function runWorkerPoolOnce(): Promise<WorkerPoolRunResponse> {
  return requestJson<WorkerPoolRunResponse>("/workers/run-pool-once", {
    method: "POST",
  });
}

export async function evaluateDeliveryHumanApproval(
  input: DeliveryHumanApprovalRequest,
): Promise<DeliveryHumanApprovalResponse> {
  const response = await fetch("/approvals/delivery-human-approval", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    throw new DeliveryHumanApprovalHttpError(
      response.status,
      await buildDeliveryHumanApprovalErrorMessage(response),
    );
  }

  return (await response.json()) as DeliveryHumanApprovalResponse;
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

async function buildDeliveryHumanApprovalErrorMessage(
  response: Response,
): Promise<string> {
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    try {
      const payload = (await response.json()) as { detail?: string };
      if (typeof payload.detail === "string" && payload.detail.length > 0) {
        return payload.detail;
      }
    } catch {
      return `Request failed: ${response.status}`;
    }
  }

  return `Request failed: ${response.status}`;
}
