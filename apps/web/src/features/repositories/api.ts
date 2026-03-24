import { requestJson } from "../../lib/http";
import type { RepositorySnapshot } from "../projects/types";
import type {
  ChangeBatchCreateInput,
  ChangeBatchDetail,
  CommitCandidateDetail,
  CommitCandidateDraftInput,
  CommitCandidateSummary,
  ChangeBatchPreflightInput,
  ChangeBatchSummary,
  ChangeSession,
  CodeContextPack,
  CodeContextPackBuildInput,
  FileLocatorResult,
  FileLocatorSearchInput,
  RepositoryVerificationBaseline,
  RepositoryVerificationBaselineInput,
} from "./types";

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

export function fetchProjectRepositoryVerificationBaseline(
  projectId: string,
): Promise<RepositoryVerificationBaseline> {
  return requestJson<RepositoryVerificationBaseline>(
    `/repositories/projects/${projectId}/verification-baseline`,
  );
}

export function replaceProjectRepositoryVerificationBaseline(input: {
  projectId: string;
  payload: RepositoryVerificationBaselineInput;
}): Promise<RepositoryVerificationBaseline> {
  return requestJson<RepositoryVerificationBaseline>(
    `/repositories/projects/${input.projectId}/verification-baseline`,
    {
      method: "PUT",
      body: JSON.stringify(input.payload),
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

export function searchProjectRepositoryFiles(
  projectId: string,
  input: FileLocatorSearchInput,
): Promise<FileLocatorResult> {
  return requestJson<FileLocatorResult>(
    `/repositories/projects/${projectId}/file-locator/search`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
}

export function buildProjectCodeContextPack(
  projectId: string,
  input: CodeContextPackBuildInput,
): Promise<CodeContextPack> {
  return requestJson<CodeContextPack>(`/repositories/projects/${projectId}/context-pack`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function fetchProjectChangeBatches(
  projectId: string,
): Promise<ChangeBatchSummary[]> {
  return requestJson<ChangeBatchSummary[]>(
    `/repositories/projects/${projectId}/change-batches`,
  );
}

export function fetchChangeBatchDetail(
  changeBatchId: string,
): Promise<ChangeBatchDetail> {
  return requestJson<ChangeBatchDetail>(
    `/repositories/change-batches/${changeBatchId}`,
  );
}

export function createProjectChangeBatch(input: {
  projectId: string;
  payload: ChangeBatchCreateInput;
}): Promise<ChangeBatchDetail> {
  return requestJson<ChangeBatchDetail>(
    `/repositories/projects/${input.projectId}/change-batches`,
    {
      method: "POST",
      body: JSON.stringify(input.payload),
    },
  );
}

export function runChangeBatchPreflight(input: {
  changeBatchId: string;
  payload?: ChangeBatchPreflightInput;
}): Promise<ChangeBatchDetail> {
  return requestJson<ChangeBatchDetail>(
    `/repositories/change-batches/${input.changeBatchId}/preflight`,
    {
      method: "POST",
      body: JSON.stringify(input.payload ?? {}),
    },
  );
}

export function fetchProjectCommitCandidates(
  projectId: string,
): Promise<CommitCandidateSummary[]> {
  return requestJson<CommitCandidateSummary[]>(
    `/repositories/projects/${projectId}/commit-candidates`,
  );
}

export async function fetchChangeBatchCommitCandidate(
  changeBatchId: string,
): Promise<CommitCandidateDetail | null> {
  const response = await fetch(
    `/repositories/change-batches/${changeBatchId}/commit-candidate`,
    {
      headers: {
        Accept: "application/json",
      },
    },
  );

  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(await buildErrorMessage(response));
  }

  return (await response.json()) as CommitCandidateDetail;
}

export function generateChangeBatchCommitCandidate(input: {
  changeBatchId: string;
  payload?: CommitCandidateDraftInput;
}): Promise<CommitCandidateDetail> {
  return requestJson<CommitCandidateDetail>(
    `/repositories/change-batches/${input.changeBatchId}/commit-candidate`,
    {
      method: "POST",
      body: JSON.stringify(input.payload ?? {}),
    },
  );
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
