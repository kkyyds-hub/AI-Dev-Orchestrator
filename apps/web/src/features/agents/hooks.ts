import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchAgentThreadInterventions,
  fetchAgentThreadSessions,
  fetchAgentThreadTimeline,
  submitAgentThreadIntervention,
} from "./api";

function sessionsKey(projectId: string | null) {
  return ["agent-thread", projectId, "sessions"] as const;
}

function timelineKey(projectId: string | null, sessionId: string | null) {
  return ["agent-thread", projectId, "timeline", sessionId ?? "all"] as const;
}

function interventionsKey(projectId: string | null, sessionId: string | null) {
  return ["agent-thread", projectId, "interventions", sessionId ?? "all"] as const;
}

export function useAgentThreadSessions(projectId: string | null) {
  return useQuery({
    queryKey: sessionsKey(projectId),
    queryFn: () => fetchAgentThreadSessions({ projectId: projectId ?? "", limit: 20 }),
    enabled: projectId !== null,
    staleTime: 10_000,
  });
}

export function useAgentThreadTimeline(input: {
  projectId: string | null;
  sessionId: string | null;
}) {
  return useQuery({
    queryKey: timelineKey(input.projectId, input.sessionId),
    queryFn: () =>
      fetchAgentThreadTimeline({
        projectId: input.projectId ?? "",
        sessionId: input.sessionId,
        limit: 200,
      }),
    enabled: input.projectId !== null,
    staleTime: 5_000,
  });
}

export function useAgentThreadInterventions(input: {
  projectId: string | null;
  sessionId: string | null;
}) {
  return useQuery({
    queryKey: interventionsKey(input.projectId, input.sessionId),
    queryFn: () =>
      fetchAgentThreadInterventions({
        projectId: input.projectId ?? "",
        sessionId: input.sessionId,
        limit: 100,
      }),
    enabled: input.projectId !== null,
    staleTime: 5_000,
  });
}

export function useSubmitBossIntervention(input: {
  projectId: string | null;
  sessionId: string | null;
}) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      interventionType: string;
      noteEventType?: string | null;
      contentSummary: string;
      contentDetail?: string | null;
    }) => {
      if (!input.projectId) {
        throw new Error("No project selected.");
      }
      if (!input.sessionId) {
        throw new Error("No agent session selected.");
      }
      return submitAgentThreadIntervention({
        projectId: input.projectId,
        sessionId: input.sessionId,
        interventionType: payload.interventionType,
        noteEventType: payload.noteEventType ?? null,
        contentSummary: payload.contentSummary,
        contentDetail: payload.contentDetail ?? null,
      });
    },
    onSuccess: async () => {
      if (!input.projectId) {
        return;
      }
      await queryClient.invalidateQueries({
        queryKey: ["agent-thread", input.projectId],
      });
    },
  });
}
