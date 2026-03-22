import { requestJson } from "../../lib/http";
import type { RepositorySnapshot } from "../projects/types";
import type { ChangeSession } from "./types";

export function fetchProjectRepositorySnapshot(
  projectId: string,
): Promise<RepositorySnapshot> {
  return requestJson<RepositorySnapshot>(
    `/repositories/projects/${projectId}/snapshot`,
  );
}

export function refreshProjectRepositorySnapshot(
  projectId: string,
): Promise<RepositorySnapshot> {
  return requestJson<RepositorySnapshot>(
    `/repositories/projects/${projectId}/snapshot/refresh`,
    {
      method: "POST",
    },
  );
}

export async function fetchProjectChangeSession(
  projectId: string,
): Promise<ChangeSession | null> {
  const response = await fetch(`/repositories/projects/${projectId}/change-session`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(await buildErrorMessage(response));
  }

  return (await response.json()) as ChangeSession;
}

export function captureProjectChangeSession(
  projectId: string,
): Promise<ChangeSession> {
  return requestJson<ChangeSession>(`/repositories/projects/${projectId}/change-session`, {
    method: "POST",
  });
}

async function buildErrorMessage(response: Response): Promise<string> {
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
