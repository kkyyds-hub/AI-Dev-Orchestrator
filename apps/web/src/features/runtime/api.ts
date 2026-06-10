import { requestJson } from "../../lib/http";

import type {
  RealExecutorLaunchReadbackRequest,
  RealExecutorLaunchReadbackResponse,
  RuntimeEventStreamReadback,
  RuntimeSessionReadback,
} from "./types";

export function listRuntimeSessions(): Promise<RuntimeSessionReadback[]> {
  return requestJson<RuntimeSessionReadback[]>("/runtime/sessions");
}

export function getRuntimeSession(
  sessionId: string,
): Promise<RuntimeSessionReadback> {
  return requestJson<RuntimeSessionReadback>(`/runtime/sessions/${sessionId}`);
}

export function getRuntimeSessionEvents(
  sessionId: string,
): Promise<RuntimeEventStreamReadback> {
  return requestJson<RuntimeEventStreamReadback>(
    `/runtime/sessions/${sessionId}/events`,
  );
}

export function buildRealExecutorLaunchReadback(
  request: RealExecutorLaunchReadbackRequest,
): Promise<RealExecutorLaunchReadbackResponse> {
  return requestJson<RealExecutorLaunchReadbackResponse>(
    "/runtime/real-executor/launch-readback",
    {
      method: "POST",
      body: JSON.stringify(request),
    },
  );
}
