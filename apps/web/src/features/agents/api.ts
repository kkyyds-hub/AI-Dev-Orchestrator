import { requestJson } from "../../lib/http";
import type {
  AgentInterventionResponse,
  AgentInterventionWriteResponse,
  AgentSessionSnapshot,
  AgentTimelineResponse,
} from "./types";

export function fetchAgentThreadSessions(input: {
  projectId: string;
  limit?: number;
}): Promise<AgentSessionSnapshot[]> {
  const params = new URLSearchParams();
  if (typeof input.limit === "number") {
    params.set("limit", String(input.limit));
  }

  const query = params.toString();
  return requestJson<AgentSessionSnapshot[]>(
    `/agent-threads/projects/${input.projectId}/sessions${query ? `?${query}` : ""}`,
  );
}

export function fetchAgentThreadTimeline(input: {
  projectId: string;
  sessionId?: string | null;
  limit?: number;
}): Promise<AgentTimelineResponse> {
  const params = new URLSearchParams();
  if (input.sessionId) {
    params.set("session_id", input.sessionId);
  }
  if (typeof input.limit === "number") {
    params.set("limit", String(input.limit));
  }

  const query = params.toString();
  return requestJson<AgentTimelineResponse>(
    `/agent-threads/projects/${input.projectId}/timeline${query ? `?${query}` : ""}`,
  );
}

export function fetchAgentThreadInterventions(input: {
  projectId: string;
  sessionId?: string | null;
  limit?: number;
}): Promise<AgentInterventionResponse> {
  const params = new URLSearchParams();
  if (input.sessionId) {
    params.set("session_id", input.sessionId);
  }
  if (typeof input.limit === "number") {
    params.set("limit", String(input.limit));
  }

  const query = params.toString();
  return requestJson<AgentInterventionResponse>(
    `/agent-threads/projects/${input.projectId}/interventions${query ? `?${query}` : ""}`,
  );
}

export function submitAgentThreadIntervention(input: {
  projectId: string;
  sessionId: string;
  interventionType: string;
  noteEventType?: string | null;
  contentSummary: string;
  contentDetail?: string | null;
}): Promise<AgentInterventionWriteResponse> {
  return requestJson<AgentInterventionWriteResponse>(
    `/agent-threads/projects/${input.projectId}/sessions/${input.sessionId}/interventions`,
    {
      method: "POST",
      body: JSON.stringify({
        intervention_type: input.interventionType,
        note_event_type: input.noteEventType ?? null,
        content_summary: input.contentSummary,
        content_detail: input.contentDetail ?? null,
      }),
    },
  );
}
