import { useMutation, useQuery } from "@tanstack/react-query";

import {
  buildRealExecutorLaunchReadback,
  getRuntimeSession,
  getRuntimeSessionEvents,
  listRuntimeSessions,
} from "./api";
import type { RealExecutorLaunchReadbackRequest } from "./types";

export function useRuntimeSessionsReadback() {
  return useQuery({
    queryKey: ["runtime", "sessions", "readback"],
    queryFn: listRuntimeSessions,
    retry: false,
  });
}

export function useRuntimeSessionReadback(sessionId: string | null) {
  return useQuery({
    queryKey: ["runtime", "session", sessionId],
    queryFn: () => getRuntimeSession(sessionId as string),
    enabled: Boolean(sessionId),
    retry: false,
  });
}

export function useRuntimeSessionEventsReadback(sessionId: string | null) {
  return useQuery({
    queryKey: ["runtime", "session-events", sessionId],
    queryFn: () => getRuntimeSessionEvents(sessionId as string),
    enabled: Boolean(sessionId),
    retry: false,
  });
}

export function useRealExecutorLaunchReadback() {
  return useMutation({
    mutationKey: ["runtime", "real-executor", "launch-readback"],
    mutationFn: (request: RealExecutorLaunchReadbackRequest) =>
      buildRealExecutorLaunchReadback(request),
    retry: false,
  });
}
