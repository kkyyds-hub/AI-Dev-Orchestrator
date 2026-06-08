import { useQuery } from "@tanstack/react-query";

import {
  getRuntimeSession,
  getRuntimeSessionEvents,
  listRuntimeSessions,
} from "./api";

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
