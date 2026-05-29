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
  title: string;
  goal: string;
  task_count_hint: number;
}

export interface ProjectDirectorProposedTask {
  title: string;
  description: string;
  suggested_role_code: string;
  priority_hint: string;
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
  forbidden_actions: string[];
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
  next_action: string;
  missing_info: string[];
  needs_user_confirmation: boolean;
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
