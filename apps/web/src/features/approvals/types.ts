import type {
  ChangeBatchManualConfirmationAction,
  ChangeBatchPreflight,
} from "../repositories/types";

export type ApprovalStatus =
  | "pending_approval"
  | "approved"
  | "rejected"
  | "changes_requested";

export type ApprovalAction = "approve" | "reject" | "request_changes";

export type ApprovalDecisionSummary = {
  id: string;
  action: ApprovalAction;
  actor_name: string;
  summary: string;
  created_at: string;
};

export type ApprovalDecision = ApprovalDecisionSummary & {
  comment: string | null;
  highlighted_risks: string[];
  requested_changes: string[];
};

export type ApprovalQueueItem = {
  id: string;
  project_id: string;
  deliverable_id: string;
  deliverable_version_id: string | null;
  deliverable_title: string;
  deliverable_type: string;
  deliverable_stage: string;
  deliverable_version_number: number;
  requester_role_code: string;
  request_note: string | null;
  status: ApprovalStatus;
  requested_at: string;
  due_at: string;
  decided_at: string | null;
  latest_summary: string | null;
  overdue: boolean;
  latest_decision: ApprovalDecisionSummary | null;
};

export type ApprovalDetail = ApprovalQueueItem & {
  decisions: ApprovalDecision[];
};

export type ProjectApprovalInbox = {
  project_id: string;
  total_requests: number;
  pending_requests: number;
  overdue_requests: number;
  completed_requests: number;
  generated_at: string;
  approvals: ApprovalQueueItem[];
};

export type RepositoryPreflightApprovalSummary = {
  change_batch_id: string;
  project_id: string;
  title: string;
  summary: string;
  task_count: number;
  target_file_count: number;
  overlap_file_count: number;
  preflight: ChangeBatchPreflight;
  created_at: string;
  updated_at: string;
};

export type ProjectRepositoryPreflightInbox = {
  project_id: string;
  total_batches: number;
  pending_confirmations: number;
  ready_batches: number;
  rejected_batches: number;
  generated_at: string;
  items: RepositoryPreflightApprovalSummary[];
};

export type RepositoryPreflightApprovalDetail = {
  change_batch_id: string;
  project_id: string;
  title: string;
  summary: string;
  task_titles: string[];
  target_files: string[];
  overlap_files: string[];
  preflight: ChangeBatchPreflight;
  timeline: string[];
  created_at: string;
  updated_at: string;
};

export type CreateApprovalRequestInput = {
  deliverable_id: string;
  requester_role_code: string;
  request_note?: string | null;
  due_in_hours?: number;
};

export type ApplyApprovalActionInput = {
  action: ApprovalAction;
  actor_name: string;
  summary: string;
  comment?: string | null;
  highlighted_risks?: string[];
  requested_changes?: string[];
};

export type ApplyRepositoryPreflightActionInput = {
  action: ChangeBatchManualConfirmationAction;
  actor_name: string;
  summary: string;
  comment?: string | null;
  highlighted_risks?: string[];
};

export type ApprovalHistoryEventKind =
  | "approval_requested"
  | "approval_decided"
  | "rework_version_submitted";

export type ApprovalHistoryReworkStatus =
  | "clean"
  | "pending_approval"
  | "rework_required"
  | "reworking"
  | "resubmitted"
  | "approved_after_rework";

export type ProjectApprovalCycleStatus =
  | "rework_required"
  | "reworking"
  | "resubmitted_pending_approval"
  | "approved_after_rework";

export type ApprovalHistoryStep = {
  id: string;
  event_kind: ApprovalHistoryEventKind;
  occurred_at: string;
  deliverable_version_number: number;
  approval_id: string | null;
  decision_id: string | null;
  approval_status: ApprovalStatus | null;
  decision_action: ApprovalAction | null;
  actor_name: string | null;
  requester_role_code: string | null;
  author_role_code: string | null;
  summary: string;
  comment: string | null;
  request_note: string | null;
  requested_changes: string[];
  highlighted_risks: string[];
  is_rework: boolean;
};

export type ApprovalHistory = {
  project_id: string;
  deliverable_id: string;
  deliverable_title: string;
  deliverable_stage: string;
  current_version_number: number;
  latest_approval_id: string | null;
  latest_approval_status: ApprovalStatus | null;
  rework_status: ApprovalHistoryReworkStatus;
  total_requests: number;
  negative_decision_count: number;
  rework_round_count: number;
  steps: ApprovalHistoryStep[];
};

export type ProjectRetrospectiveSummary = {
  total_approval_requests: number;
  negative_approval_cycles: number;
  open_rework_cycles: number;
  total_failure_reviews: number;
  failure_clusters: number;
};

export type ProjectRetrospectiveApprovalCycle = {
  cycle_id: string;
  deliverable_id: string;
  deliverable_title: string;
  deliverable_stage: string;
  approval_id: string;
  deliverable_version_number: number;
  current_version_number: number;
  decided_at: string;
  decision_action: ApprovalAction;
  summary: string;
  comment: string | null;
  requested_changes: string[];
  highlighted_risks: string[];
  status: ProjectApprovalCycleStatus;
  latest_approval_id: string | null;
  latest_approval_status: ApprovalStatus | null;
  resubmitted_version_number: number | null;
  resubmitted_at: string | null;
};

export type ProjectRetrospectiveFailureCluster = {
  cluster_key: string;
  failure_category: string;
  count: number;
  latest_run_created_at: string;
  route_reason_excerpt: string | null;
  sample_task_titles: string[];
  run_ids: string[];
};

export type ProjectRetrospectiveFailureRun = {
  run_id: string;
  task_id: string;
  task_title: string | null;
  created_at: string;
  run_status: string;
  failure_category: string | null;
  headline: string;
  stages: string[];
  review:
    | {
        review_id: string;
        conclusion: string;
        action_summary: string;
      }
    | null;
};

export type ProjectApprovalRetrospective = {
  project_id: string;
  generated_at: string;
  summary: ProjectRetrospectiveSummary;
  approval_cycles: ProjectRetrospectiveApprovalCycle[];
  failure_clusters: ProjectRetrospectiveFailureCluster[];
  recent_failures: ProjectRetrospectiveFailureRun[];
};

export const APPROVAL_STATUS_LABELS: Record<ApprovalStatus, string> = {
  pending_approval: "???",
  approved: "???",
  rejected: "???",
  changes_requested: "???",
};

export const APPROVAL_ACTION_LABELS: Record<ApprovalAction, string> = {
  approve: "??",
  reject: "??",
  request_changes: "????",
};

export const APPROVAL_HISTORY_EVENT_LABELS: Record<
  ApprovalHistoryEventKind,
  string
> = {
  approval_requested: "????",
  approval_decided: "????",
  rework_version_submitted: "????",
};

export const APPROVAL_REWORK_STATUS_LABELS: Record<
  ApprovalHistoryReworkStatus,
  string
> = {
  clean: "????",
  pending_approval: "????",
  rework_required: "???",
  reworking: "???",
  resubmitted: "???",
  approved_after_rework: "?????",
};

export const PROJECT_APPROVAL_CYCLE_STATUS_LABELS: Record<
  ProjectApprovalCycleStatus,
  string
> = {
  rework_required: "???",
  reworking: "???",
  resubmitted_pending_approval: "??????",
  approved_after_rework: "?????",
};
