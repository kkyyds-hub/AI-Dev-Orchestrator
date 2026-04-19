import { requestJson } from "../../lib/http";
import type {
  MemoryGovernanceCompactResult,
  MemoryGovernanceRehydrateResult,
  MemoryGovernanceResetResult,
  MemoryGovernanceRunOnceEcho,
  MemoryGovernanceState,
} from "./types";

export function fetchMemoryGovernanceState(
  projectId: string,
): Promise<MemoryGovernanceState> {
  return requestJson<MemoryGovernanceState>(
    `/projects/${projectId}/memory/governance`,
  );
}

export function triggerMemoryGovernanceRehydrate(input: {
  projectId: string;
  taskId?: string | null;
}): Promise<MemoryGovernanceRehydrateResult> {
  const params = new URLSearchParams();
  if (input.taskId) {
    params.set("task_id", input.taskId);
  }

  const suffix = params.toString();
  return requestJson<MemoryGovernanceRehydrateResult>(
    `/projects/${input.projectId}/memory/governance/rehydrate${suffix ? `?${suffix}` : ""}`,
    {
      method: "POST",
    },
  );
}

export function triggerMemoryGovernanceCompact(input: {
  projectId: string;
  targetChars: number;
}): Promise<MemoryGovernanceCompactResult> {
  return requestJson<MemoryGovernanceCompactResult>(
    `/projects/${input.projectId}/memory/governance/compact`,
    {
      method: "POST",
      body: JSON.stringify({
        target_chars: input.targetChars,
      }),
    },
  );
}

export function triggerMemoryGovernanceReset(
  projectId: string,
): Promise<MemoryGovernanceResetResult> {
  return requestJson<MemoryGovernanceResetResult>(
    `/projects/${projectId}/memory/governance/reset`,
    {
      method: "POST",
    },
  );
}

export function runMemoryGovernanceProbe(
  projectId: string,
): Promise<MemoryGovernanceRunOnceEcho> {
  const params = new URLSearchParams();
  params.set("project_id", projectId);
  return requestJson<MemoryGovernanceRunOnceEcho>(
    `/workers/run-once?${params.toString()}`,
    {
      method: "POST",
    },
  );
}
