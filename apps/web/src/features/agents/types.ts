export type AgentSessionSnapshot = {
  session_id: string;
  project_id: string;
  task_id: string;
  run_id: string;
  session_status: string;
  review_status: string;
  current_phase: string;
  owner_role_code: string | null;
  context_checkpoint_id: string | null;
  context_rehydrated: boolean;
  latest_intervention_type: string | null;
  latest_note_event_type: string | null;
  summary: string | null;
  started_at: string;
  updated_at: string;
  finished_at: string | null;
};

export type AgentTimelineMessage = {
  message_id: string;
  session_id: string;
  project_id: string;
  task_id: string;
  run_id: string;
  sequence_no: number;
  role: string;
  message_type: string;
  event_type: string;
  phase: string | null;
  state_from: string | null;
  state_to: string | null;
  intervention_type: string | null;
  note_event_type: string | null;
  context_checkpoint_id: string | null;
  context_rehydrated: boolean | null;
  content_summary: string;
  content_detail: string | null;
  created_at: string;
};

export type AgentTimelineResponse = {
  project_id: string;
  session_id: string | null;
  total_messages: number;
  messages: AgentTimelineMessage[];
};

export type AgentInterventionResponse = {
  project_id: string;
  session_id: string | null;
  total_items: number;
  items: AgentTimelineMessage[];
};

export type AgentInterventionWriteResponse = {
  project_id: string;
  session_id: string;
  session: AgentSessionSnapshot;
  intervention_message: AgentTimelineMessage;
};
