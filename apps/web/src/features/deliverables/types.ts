export type DeliverableType =
  | "prd"
  | "design"
  | "task_breakdown"
  | "code_plan"
  | "acceptance_conclusion"
  | "stage_artifact";

export type DeliverableContentFormat =
  | "markdown"
  | "plain_text"
  | "json"
  | "link";

export type DeliverableVersionSummary = {
  id: string;
  version_number: number;
  author_role_code: string;
  summary: string;
  content_format: DeliverableContentFormat;
  source_task_id: string | null;
  source_run_id: string | null;
  created_at: string;
};

export type DeliverableVersion = DeliverableVersionSummary & {
  content: string;
};

export type DeliverableSummary = {
  id: string;
  project_id: string;
  type: DeliverableType;
  title: string;
  stage: string;
  created_by_role_code: string;
  current_version_number: number;
  total_versions: number;
  created_at: string;
  updated_at: string;
  latest_version: DeliverableVersionSummary;
};

export type ProjectDeliverableSnapshot = {
  project_id: string;
  total_deliverables: number;
  total_versions: number;
  generated_at: string;
  deliverables: DeliverableSummary[];
};

export type DeliverableDetail = {
  id: string;
  project_id: string;
  type: DeliverableType;
  title: string;
  stage: string;
  created_by_role_code: string;
  current_version_number: number;
  total_versions: number;
  created_at: string;
  updated_at: string;
  versions: DeliverableVersion[];
};

export type DeliverableDiffLine = {
  kind: "context" | "added" | "removed";
  content: string;
  base_line_number: number | null;
  target_line_number: number | null;
};

export type DeliverableVersionDiff = {
  deliverable_id: string;
  project_id: string;
  title: string;
  type: DeliverableType;
  stage: string;
  base_version: DeliverableVersion;
  target_version: DeliverableVersion;
  format_changed: boolean;
  added_line_count: number;
  removed_line_count: number;
  unchanged_line_count: number;
  changed_block_count: number;
  diff_lines: DeliverableDiffLine[];
};

export type TaskRelatedDeliverable = {
  deliverable_id: string;
  project_id: string;
  type: DeliverableType;
  title: string;
  stage: string;
  current_version_number: number;
  matched_version: DeliverableVersionSummary;
};

export const DELIVERABLE_TYPE_LABELS: Record<DeliverableType, string> = {
  prd: "PRD",
  design: "设计稿",
  task_breakdown: "任务拆分",
  code_plan: "代码计划",
  acceptance_conclusion: "验收结论",
  stage_artifact: "阶段产物",
};

export const DELIVERABLE_CONTENT_FORMAT_LABELS: Record<
  DeliverableContentFormat,
  string
> = {
  markdown: "Markdown",
  plain_text: "文本",
  json: "JSON",
  link: "链接",
};
