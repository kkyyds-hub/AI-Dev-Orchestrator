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
  forbidden_actions: string[];
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

export interface ProjectDirectorTaskCreationResponse {
  plan_version_id: string;
  session_id: string;
  project_id: string;
  created_task_ids: string[];
  task_count: number;
  status: string;
  next_action: string;
  forbidden_actions: string[];
  gate_conclusion: string;
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
