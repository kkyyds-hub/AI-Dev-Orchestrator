export type ProjectDirectorSessionStatus =
  | "draft"
  | "clarifying"
  | "ready_to_confirm"
  | "confirmed";

export type ProjectDirectorPlanVersionStatus =
  | "draft"
  | "pending_confirmation"
  | "confirmed"
  | "superseded"
  | "rejected";

export type ProjectDirectorPlanReviewAction =
  | "approve"
  | "reject"
  | "request_changes";

export type ProjectDirectorMessageRole = "user" | "assistant" | "system";

export type ProjectDirectorMessageSource = "ai" | "rule_fallback" | "system" | string;

export type ProjectDirectorMessageRiskLevel = "low" | "medium" | "high" | string;

export const PROJECT_DIRECTOR_PLAN_STATUS_LABELS: Record<
  ProjectDirectorPlanVersionStatus,
  string
> = {
  draft: "草稿",
  pending_confirmation: "待审核",
  confirmed: "已通过",
  superseded: "已被新版本替换",
  rejected: "已拒绝",
};

export interface ClarifyingQuestion {
  id: string;
  question: string;
  hint: string;
  required: boolean;
  source?: "ai" | "rule_fallback" | string;
  source_detail?: string;
}

export interface ClarifyingAnswer {
  question_id: string;
  answer: string;
}

export interface ProjectDirectorSession {
  id: string;
  project_id: string | null;
  goal_text: string;
  constraints: string;
  status: ProjectDirectorSessionStatus;
  clarifying_questions: ClarifyingQuestion[];
  clarifying_answers: ClarifyingAnswer[];
  goal_summary: string;
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
  next_action: string;
  missing_info: string[];
  needs_user_confirmation: boolean;
  forbidden_actions: string[];
  gate_conclusion: string;
}

export interface ProjectDirectorPlanPhase {
  sequence: number;
  name: string;
  goal: string;
  task_count_hint: number;
}

export interface ProjectDirectorProposedTask {
  title: string;
  description: string;
  suggested_role_code: string;
  priority_hint: string;
}

export interface ProjectDirectorProjectScope {
  in_scope: string[];
  out_of_scope: string[];
  assumptions: string[];
}

export interface ProjectDirectorAgentTeamSuggestion {
  role_code: string;
  role_name: string;
  responsibility: string;
  collaboration_notes: string[];
}

export type ProjectDirectorAgentTeamConfigStatus =
  | "pending_confirmation"
  | "confirmed"
  | "rejected";

export type ProjectDirectorAgentTeamConfigReviewAction = "confirm" | "reject";

export interface ProjectDirectorAgentTeamConfigMember {
  role_code: string;
  role_name: string;
  responsibility: string;
  collaboration_notes: string[];
  review_status: string;
}

export interface ProjectDirectorAgentTeamConfig {
  id: string;
  project_id: string;
  plan_version_id: string;
  source_draft_id: string;
  status: ProjectDirectorAgentTeamConfigStatus;
  agent_team: ProjectDirectorAgentTeamConfigMember[];
  warnings: string[];
  review_note: string;
  created_at: string;
  updated_at: string;
  confirmed_at: string | null;
  rejected_at: string | null;
}

export interface ProjectDirectorAgentTeamConfigResponse {
  project_id: string;
  config: ProjectDirectorAgentTeamConfig | null;
  next_action: string;
}

export type ProjectDirectorSkillBindingConfigStatus =
  | "pending_confirmation"
  | "confirmed"
  | "rejected";

export type ProjectDirectorSkillBindingConfigReviewAction = "confirm" | "reject";

export interface ProjectDirectorSkillBindingConfigItem {
  skill_code: string;
  skill_name: string;
  owner_role_code: string;
  usage: string;
  activation_stage: string;
  binding_mode: string;
  reason: string;
  review_status: string;
}

export interface ProjectDirectorSkillBindingConfig {
  id: string;
  project_id: string;
  plan_version_id: string;
  source_draft_id: string;
  status: ProjectDirectorSkillBindingConfigStatus;
  skill_bindings: ProjectDirectorSkillBindingConfigItem[];
  warnings: string[];
  review_note: string;
  created_at: string;
  updated_at: string;
  confirmed_at: string | null;
  rejected_at: string | null;
}

export interface ProjectDirectorSkillBindingConfigResponse {
  project_id: string;
  config: ProjectDirectorSkillBindingConfig | null;
  next_action: string;
}

export type ProjectDirectorRepositoryBindingConfigStatus =
  | "pending_confirmation"
  | "confirmed"
  | "rejected";

export type ProjectDirectorRepositoryBindingConfigReviewAction = "confirm" | "reject";

export interface ProjectDirectorRepositoryBindingConfigItem {
  binding_type: string;
  binding_mode: string;
  target: string;
  branch: string;
  focus_paths: string[];
  usage: string;
  safety_note: string;
  review_status: string;
}

export interface ProjectDirectorRepositoryBindingConfig {
  id: string;
  project_id: string;
  plan_version_id: string;
  source_draft_id: string;
  status: ProjectDirectorRepositoryBindingConfigStatus;
  repository_bindings: ProjectDirectorRepositoryBindingConfigItem[];
  warnings: string[];
  review_note: string;
  created_at: string;
  updated_at: string;
  confirmed_at: string | null;
  rejected_at: string | null;
}

export interface ProjectDirectorRepositoryBindingConfigResponse {
  project_id: string;
  config: ProjectDirectorRepositoryBindingConfig | null;
  next_action: string;
}

export type ProjectDirectorVerificationConfigStatus =
  | "pending_confirmation"
  | "confirmed"
  | "rejected";

export type ProjectDirectorVerificationConfigReviewAction = "confirm" | "reject";

export interface ProjectDirectorVerificationConfigItem {
  name: string;
  command_or_method: string;
  purpose: string;
  evidence_required: string;
  owner_role_code: string;
  risk_level: string;
  requires_user_confirmation: boolean;
  review_status: string;
}

export interface ProjectDirectorVerificationConfig {
  id: string;
  project_id: string;
  plan_version_id: string;
  source_draft_id: string;
  status: ProjectDirectorVerificationConfigStatus;
  verification_mechanisms: ProjectDirectorVerificationConfigItem[];
  warnings: string[];
  review_note: string;
  created_at: string;
  updated_at: string;
  confirmed_at: string | null;
  rejected_at: string | null;
}

export interface ProjectDirectorVerificationConfigResponse {
  project_id: string;
  config: ProjectDirectorVerificationConfig | null;
  next_action: string;
}

export interface ProjectDirectorSkillBindingSuggestion {
  skill_code: string;
  owner_role_code: string;
  usage: string;
  activation_stage: string;
  binding_mode: string;
  reason: string;
}

export interface ProjectDirectorVerificationMechanism {
  name: string;
  command_or_method: string;
  evidence_required: string;
  owner_role_code: string;
  purpose: string;
  risk_level: string;
  requires_user_confirmation: boolean;
}

export interface ProjectDirectorRepositoryBindingSuggestion {
  binding_type: string;
  binding_mode: string;
  target: string;
  branch: string;
  focus_paths: string[];
  usage: string;
  safety_note: string;
}

export interface ProjectDirectorDeliverableBoundary {
  name: string;
  description: string;
  owner_role_code: string;
  required_contents: string[];
  done_definition: string;
  acceptance_signal: string;
}

export interface ProjectDirectorComplexityAssessment {
  level: string;
  label: string;
  score: number;
  recommended_agent_count: number;
  drivers: string[];
  mitigation_suggestions: string[];
}

export interface ProjectDirectorPlanVersion {
  id: string;
  session_id: string;
  project_id: string | null;
  version_no: number;
  status: ProjectDirectorPlanVersionStatus;
  plan_summary: string;
  phases: ProjectDirectorPlanPhase[];
  proposed_tasks: ProjectDirectorProposedTask[];
  acceptance_criteria: string[];
  risks: string[];
  project_scope: ProjectDirectorProjectScope;
  agent_team_suggestions: ProjectDirectorAgentTeamSuggestion[];
  skill_binding_suggestions: ProjectDirectorSkillBindingSuggestion[];
  verification_mechanisms: ProjectDirectorVerificationMechanism[];
  repository_binding_suggestions: ProjectDirectorRepositoryBindingSuggestion[];
  deliverable_boundaries: ProjectDirectorDeliverableBoundary[];
  complexity_assessment: ProjectDirectorComplexityAssessment;
  source?: "ai" | "rule_fallback" | string;
  source_detail?: string;
  normalization_warnings?: string[];
  forbidden_actions: string[];
  formalization_target: ProjectDirectorFormalizationTarget | null;
  formalization_workspace_version: number | null;
  formalization_source_message_ids: string[];
  formalization_source_event_ids: string[];
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
  next_action: string;
  missing_info: string[];
  needs_user_confirmation: boolean;
  gate_conclusion: string;
}

export interface ProjectDirectorPlanReviewResponse {
  action: ProjectDirectorPlanReviewAction;
  reviewed_plan_version: ProjectDirectorPlanVersion;
  replacement_plan_version: ProjectDirectorPlanVersion | null;
  next_action: string;
  gate_conclusion: string;
}

export interface ProjectDirectorSuggestedAction {
  type?: string;
  label?: string;
  requires_confirmation?: boolean;
  risk_level?: ProjectDirectorMessageRiskLevel;
}

export interface ProjectDirectorMessage {
  id: string;
  session_id: string;
  role: ProjectDirectorMessageRole;
  content: string;
  sequence_no: number;
  intent: string | null;
  related_plan_version_id: string | null;
  related_project_id: string | null;
  related_task_id: string | null;
  source: ProjectDirectorMessageSource;
  source_detail: string;
  suggested_actions: ProjectDirectorSuggestedAction[];
  requires_confirmation: boolean;
  risk_level: ProjectDirectorMessageRiskLevel | null;
  forbidden_actions_detected: string[];
  token_count: number | null;
  estimated_cost: number | null;
  created_at: string;
}

export interface ProjectDirectorMessageListResponse {
  session_id: string;
  messages: ProjectDirectorMessage[];
  has_more: boolean;
}

export interface PostProjectDirectorMessageInput {
  sessionId: string;
  content: string;
}

export type ProjectDirectorDiscussionStatus =
  | "exploring"
  | "comparing"
  | "converging"
  | "ready_to_formalize"
  | "formalized"
  | "paused";

export interface ProjectDirectorDiscussionWorkspace {
  session_id: string;
  project_id: string | null;
  topic: string;
  discussion_status: ProjectDirectorDiscussionStatus;
  active_option_ids: string[];
  preferred_option_id: string | null;
  active_constraint_ids: string[];
  open_question_ids: string[];
  temporary_conclusion_ids: string[];
  confirmed_decision_ids: string[];
  latest_user_correction_event_id: string | null;
  version_no: number;
  last_event_sequence_no: number;
  created_at: string;
  updated_at: string;
}

export type ProjectDirectorConversationMode =
  | "general_discussion"
  | "solution_exploration"
  | "option_comparison"
  | "clarification"
  | "challenge"
  | "constraint_update"
  | "preference_update"
  | "decision_confirmation"
  | "formalization_request"
  | "action_request"
  | "status_query";

export interface ProjectDirectorTurnInterpretation {
  conversation_mode: ProjectDirectorConversationMode;
  primary_intent: string;
  confidence: number;
  formal_action_requested: boolean;
  hypothetical_action: boolean;
  referenced_option_ids: string[];
  referenced_entity_ids: string[];
  needs_formal_fact_context: boolean;
  needs_discussion_history: boolean;
  needs_retrieval: boolean;
  reason_summary: string;
}

export type ProjectDirectorFormalizationTarget = "plan_revision";

export type ProjectDirectorFormalizationChangeType = "add" | "update" | "remove";

export interface ProjectDirectorFormalizationChange {
  change_type: ProjectDirectorFormalizationChangeType;
  subject_key: string;
  summary: string;
  source_event_ids: string[];
}

export interface ProjectDirectorFormalizationProposal {
  proposal_id: string;
  target: ProjectDirectorFormalizationTarget;
  workspace_version: number;
  summary: string;
  changes: ProjectDirectorFormalizationChange[];
  source_message_ids: string[];
  risk_summary: string;
  requires_confirmation: true;
  status: "proposed";
}

export interface PostProjectDirectorMessageResponse {
  session_id: string;
  user_message: ProjectDirectorMessage;
  assistant_message: ProjectDirectorMessage;
  messages: ProjectDirectorMessage[];
  source: ProjectDirectorMessageSource;
  turn_interpretation: ProjectDirectorTurnInterpretation;
  discussion_workspace_version: number | null;
  formalization_proposal: ProjectDirectorFormalizationProposal | null;
  delta_apply_status: "applied" | "replayed" | "requires_confirmation" | "no_changes";
  confirmation_reasons: string[];
  requires_confirmation: boolean;
  gate_conclusion: string;
  forbidden_actions: string[];
}

export type ProjectDirectorConversationStatus =
  | "active"
  | "idle"
  | "awaiting_user"
  | "archived"
  | "completed";

export type ProjectDirectorConversationKind =
  | "project_onboarding"
  | "general_discussion"
  | "plan_review"
  | "follow_up";

export type ProjectDirectorConversationTimelineItemKind =
  | "message"
  | "plan_draft"
  | "plan_confirmed"
  | "task_created"
  | string;

export interface ProjectDirectorConversationListItem {
  conversation_id: string;
  /**
   * P7-C1-R1 backend does not expose an independent session_id on the
   * ConversationListItem response. Per P7-C contract, session.id is reused as
   * conversation_id, so consumers may derive session_id = conversation_id.
   */
  session_id?: string;
  project_id: string | null;
  title: string;
  kind: ProjectDirectorConversationKind;
  status: ProjectDirectorConversationStatus;
  session_status: ProjectDirectorSessionStatus | string;
  last_message_preview: string;
  last_message_at: string | null;
  message_count: number;
  pending_challenge_count: number;
  pending_proposal_count: number;
  requires_user_action: boolean;
  owner_scope: "project" | "user" | string;
  created_at: string;
  updated_at: string;
}

export interface ProjectDirectorConversationListResponse {
  conversations: ProjectDirectorConversationListItem[];
  has_more: boolean;
  source: string;
}

export interface ProjectDirectorConversationTaskCreation {
  id: string;
  plan_version_id: string;
  session_id: string;
  project_id: string;
  version_no: number;
  source_type: string;
  created_task_ids: string[];
  task_count: number;
  created_at: string;
}

export interface ProjectDirectorConversationDetailResponse {
  conversation: ProjectDirectorConversationListItem;
  session: ProjectDirectorSession;
  recent_messages: ProjectDirectorMessage[];
  latest_plan_version: ProjectDirectorPlanVersion | null;
  task_creation: ProjectDirectorConversationTaskCreation | null;
  source: string;
}

export interface ProjectDirectorConversationTimelineItem {
  timestamp: string;
  kind: ProjectDirectorConversationTimelineItemKind;
  summary_cn: string;
  related_message_id: string | null;
  related_plan_version_id: string | null;
  related_task_id: string | null;
  related_proposal_id: string | null;
}

export interface ProjectDirectorConversationTimelineResponse {
  conversation_id: string;
  items: ProjectDirectorConversationTimelineItem[];
  source: string;
}

export type ProjectDirectorInboxItemKind =
  | "note"
  | "user_challenge_seed"
  | "plan_question"
  | "dispatch_question"
  | "approval_attention"
  | "run_blocker"
  | "failure_recovery_attention"
  | "proposal_attention"
  | "governance_warning"
  | "system_notice";

export type ProjectDirectorInboxItemStatus =
  | "unread"
  | "read"
  | "needs_response"
  | "linked_to_conversation"
  | "converted_to_challenge"
  | "converted_to_proposal"
  | "resolved"
  | "archived";

export type ProjectDirectorInboxItemPriority =
  | "low"
  | "normal"
  | "high"
  | "critical";

export interface ProjectDirectorInboxItem {
  id: string;
  conversation_id: string | null;
  session_id: string | null;
  project_id: string | null;
  source_page: string;
  source_entity_type: string;
  source_entity_id: string | null;
  kind: ProjectDirectorInboxItemKind;
  title: string;
  summary: string;
  status: ProjectDirectorInboxItemStatus;
  priority: ProjectDirectorInboxItemPriority;
  requires_user_action: boolean;
  related_message_id: string | null;
  related_plan_version_id: string | null;
  related_task_id: string | null;
  related_run_id: string | null;
  related_approval_id: string | null;
  related_dispatch_decision_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectDirectorInboxResponse {
  items: ProjectDirectorInboxItem[];
  has_more: boolean;
  source: string;
}

export interface ListProjectDirectorConversationsParams {
  project_id?: string | null;
  status?: ProjectDirectorConversationStatus | null;
  kind?: ProjectDirectorConversationKind | null;
  limit?: number | null;
  before?: string | null;
}

export interface ListProjectDirectorInboxParams {
  project_id?: string | null;
  kind?: ProjectDirectorInboxItemKind | null;
  status?: ProjectDirectorInboxItemStatus | null;
  priority?: ProjectDirectorInboxItemPriority | null;
  limit?: number | null;
}

export interface GetProjectDirectorConversationParams {
  project_id?: string | null;
  recent_message_limit?: number | null;
}

export interface GetProjectDirectorConversationTimelineParams {
  project_id?: string | null;
}

export interface ProjectDirectorWorkbenchResume {
  session: ProjectDirectorSession | null;
  plan_version: ProjectDirectorPlanVersion | null;
  task_creation: ProjectDirectorTaskCreationResponse | null;
  recent_messages: ProjectDirectorMessage[];
  discussion_workspace: ProjectDirectorDiscussionWorkspace | null;
  source:
    | "backend_recent_plan"
    | "backend_recent_session"
    | "backend_recent_task_creation"
    | "none"
    | string;
  next_action: string;
}

export interface ProjectDirectorWorkbenchResumableSession {
  session_id: string;
  project_id: string | null;
  project_name: string | null;
  status: ProjectDirectorSessionStatus;
  goal_text: string;
  goal_summary: string;
  updated_at: string;
  plan_version_id: string | null;
  plan_version_status: ProjectDirectorPlanVersionStatus | null;
  source: "backend_recent_plan" | "backend_recent_session" | string;
  next_action: string;
}

export interface ProjectDirectorWorkbenchResumableSessionsResponse {
  sessions: ProjectDirectorWorkbenchResumableSession[];
  source: string;
}

export interface ProjectDirectorTaskCreationResponse {
  plan_version_id: string;
  session_id: string;
  project_id: string;
  project_name: string | null;
  created_task_ids: string[];
  task_count: number;
  status: string;
  already_created: boolean;
  next_action: string;
  warnings: string[];
  forbidden_actions: string[];
  gate_conclusion: string;
}

export type ProjectDirectorSetupReadinessConfigStatus =
  | "pending_confirmation"
  | "confirmed"
  | "rejected"
  | "missing";

export interface ProjectDirectorSetupReadiness {
  project_id: string;
  source_plan_version_id: string | null;
  source_draft_id: string | null;
  created_by_director: boolean;
  formal_project_created: boolean;
  task_queue_created: boolean;
  task_count: number;
  pending_task_count: number;
  agent_team_config_status: ProjectDirectorSetupReadinessConfigStatus;
  skill_binding_config_status: ProjectDirectorSetupReadinessConfigStatus;
  repository_binding_config_status: ProjectDirectorSetupReadinessConfigStatus;
  verification_config_status: ProjectDirectorSetupReadinessConfigStatus;
  pending_confirmation_count: number;
  rejected_count: number;
  confirmed_count: number;
  ready_for_manual_execution: boolean;
  next_steps: string[];
  warnings: string[];
}

export interface CreateProjectDirectorSessionInput {
  goal_text: string;
  project_id?: string | null;
  constraints?: string;
}

export interface SubmitProjectDirectorAnswersInput {
  sessionId: string;
  answers: ClarifyingAnswer[];
}

export interface ConfirmProjectDirectorGoalInput {
  sessionId: string;
}

export interface CreateProjectDirectorPlanVersionInput {
  sessionId: string;
}

export interface FormalizeProjectDirectorDiscussionInput {
  sessionId: string;
  workspaceVersion: number;
}

export interface FormalizeProjectDirectorDiscussionResponse {
  session_id: string;
  workspace_version: number;
  target: "plan_revision";
  source_message_ids: string[];
  source_event_ids: string[];
  idempotent_replay: boolean;
  plan_version: ProjectDirectorPlanVersion;
  task_created: false;
  run_created: false;
  worker_started: false;
  executor_started: false;
  repository_write_performed: false;
  gate_conclusion: string;
}

export interface FetchProjectDirectorWorkbenchResumeInput {
  mode: "new-project" | "project";
  projectId?: string | null;
  sessionId?: string | null;
}

export interface ConfirmProjectDirectorPlanVersionInput {
  planVersionId: string;
}

export interface ReviewProjectDirectorPlanVersionInput {
  planVersionId: string;
  action: ProjectDirectorPlanReviewAction;
  feedback?: string;
}

export interface CreateProjectDirectorTaskQueueInput {
  planVersionId: string;
}

export interface ReviewProjectDirectorAgentTeamConfigInput {
  projectId: string;
  action: ProjectDirectorAgentTeamConfigReviewAction;
  note?: string;
}

export interface ReviewProjectDirectorSkillBindingConfigInput {
  projectId: string;
  action: ProjectDirectorSkillBindingConfigReviewAction;
  note?: string;
}

export interface ReviewProjectDirectorRepositoryBindingConfigInput {
  projectId: string;
  action: ProjectDirectorRepositoryBindingConfigReviewAction;
  note?: string;
}

export interface ReviewProjectDirectorVerificationConfigInput {
  projectId: string;
  action: ProjectDirectorVerificationConfigReviewAction;
  note?: string;
}
