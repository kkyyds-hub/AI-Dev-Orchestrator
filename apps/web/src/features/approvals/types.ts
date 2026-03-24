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

export type ChangeReworkStepStage =
  | "plan"
  | "verification"
  | "decision"
  | "failure"
  | "rework";

export type ChangeReworkRecommendation = "rework" | "rollback" | "replan";

export type ChangeReworkSource = "approval_rework" | "verification_rework";

export type ChangeReworkChainStep = {
  step_id: string;
  stage: ChangeReworkStepStage;
  label: string;
  summary: string;
  occurred_at: string;
  metadata: Record<string, unknown>;
};

export type ProjectChangeReworkItem = {
  rework_id: string;
  project_id: string;
  chain_source: ChangeReworkSource;
  status: string;
  recommendation: ChangeReworkRecommendation;
  closed: boolean;
  occurred_at: string;
  change_batch_id: string | null;
  change_batch_title: string | null;
  evidence_package_key: string | null;
  deliverable_id: string | null;
  deliverable_title: string | null;
  approval_id: string | null;
  approval_status: ApprovalStatus | null;
  decision_action: ApprovalAction | null;
  reason_summary: string;
  reason_comment: string | null;
  requested_changes: string[];
  highlighted_risks: string[];
  latest_failure_category: string | null;
  verification_total_runs: number;
  verification_failed_runs: number;
  linked_task_ids: string[];
  linked_run_ids: string[];
  steps: ChangeReworkChainStep[];
};

export type ProjectChangeReworkSummary = {
  total_items: number;
  approval_rework_items: number;
  verification_rework_items: number;
  rollback_recommendations: number;
  replan_recommendations: number;
  open_items: number;
  closed_items: number;
};

export type ProjectChangeRework = {
  project_id: string;
  generated_at: string;
  summary: ProjectChangeReworkSummary;
  items: ProjectChangeReworkItem[];
};

export type RepositoryReleaseChecklistItemStatus = "passed" | "missing";

export type RepositoryReleaseGateStatus =
  | "blocked"
  | "pending_approval"
  | "approved"
  | "rejected"
  | "changes_requested";

export type RepositoryReleaseChecklistItem = {
  key: string;
  title: string;
  required: boolean;
  status: RepositoryReleaseChecklistItemStatus;
  summary: string;
  gap_reason: string | null;
  evidence_key: string | null;
  checked_at: string | null;
};

export type RepositoryReleaseGateDecision = {
  id: string;
  change_batch_id: string;
  action: ApprovalAction;
  actor_name: string;
  summary: string;
  comment: string | null;
  highlighted_risks: string[];
  requested_changes: string[];
  created_at: string;
};

export type RepositoryReleaseGateSummary = {
  change_batch_id: string;
  change_batch_title: string;
  generated_at: string;
  status: RepositoryReleaseGateStatus;
  blocked: boolean;
  missing_item_count: number;
  decision_count: number;
  release_qualification_established: boolean;
  latest_decision: RepositoryReleaseGateDecision | null;
};

export type ProjectRepositoryReleaseGateInbox = {
  project_id: string;
  generated_at: string;
  total_batches: number;
  blocked_batches: number;
  pending_batches: number;
  approved_batches: number;
  rejected_batches: number;
  changes_requested_batches: number;
  items: RepositoryReleaseGateSummary[];
};

export type RepositoryReleaseGateDetail = {
  project_id: string;
  change_batch_id: string;
  change_batch_title: string;
  generated_at: string;
  snapshot_age_minutes: number | null;
  required_item_count: number;
  passed_item_count: number;
  checklist_items: RepositoryReleaseChecklistItem[];
  missing_item_keys: string[];
  gap_reasons: string[];
  blocked: boolean;
  status: RepositoryReleaseGateStatus;
  approval_status: ApprovalStatus | null;
  release_qualification_established: boolean;
  git_write_actions_triggered: boolean;
  decision_count: number;
  latest_decision: RepositoryReleaseGateDecision | null;
  decisions: RepositoryReleaseGateDecision[];
};

export type ApplyRepositoryReleaseGateActionInput = {
  action: ApprovalAction;
  actor_name: string;
  summary: string;
  comment?: string | null;
  highlighted_risks?: string[];
  requested_changes?: string[];
};

export const CHANGE_REWORK_STAGE_LABELS: Record<ChangeReworkStepStage, string> = {
  plan: "计划",
  verification: "验证",
  decision: "结论",
  failure: "失败复盘",
  rework: "回退重做",
};

export const CHANGE_REWORK_RECOMMENDATION_LABELS: Record<
  ChangeReworkRecommendation,
  string
> = {
  rework: "继续重做",
  rollback: "先回退",
  replan: "重新规划",
};

export const CHANGE_REWORK_SOURCE_LABELS: Record<ChangeReworkSource, string> = {
  approval_rework: "审批驳回链路",
  verification_rework: "验证失败链路",
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

export const REPOSITORY_RELEASE_GATE_STATUS_LABELS: Record<
  RepositoryReleaseGateStatus,
  string
> = {
  blocked: "检查单阻断",
  pending_approval: "待审批",
  approved: "已通过",
  rejected: "已驳回",
  changes_requested: "待补证据",
};

export const REPOSITORY_RELEASE_CHECKLIST_ITEM_STATUS_LABELS: Record<
  RepositoryReleaseChecklistItemStatus,
  string
> = {
  passed: "通过",
  missing: "缺失",
};
