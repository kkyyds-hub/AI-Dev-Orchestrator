export type ProjectDirectorSessionStatus =
  | "draft"
  | "clarifying"
  | "ready_to_confirm"
  | "confirmed";

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

export interface CreateProjectDirectorSessionInput {
  goal_text: string;
  project_id?: string | null;
  constraints?: string;
}
