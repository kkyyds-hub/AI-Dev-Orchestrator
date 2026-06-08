import { requestJson } from "../../lib/http";
import type {
  GitWriteApprovalRequest,
  GitWriteAuditEventReadback,
  GitWriteCreateIntentRequest,
  GitWriteReadbackRecord,
} from "./types";

export const SAFE_GIT_WRITE_READBACK_REQUEST: GitWriteCreateIntentRequest = {
  intent_id: "web-readback-preview-1",
  workspace_id: "workspace-readback-ui",
  repository_id: "repo-readback-ui",
  project_id: "project-readback-ui",
  task_id: "task-readback-ui",
  run_id: "run-readback-ui",
  requested_by: "web-user",
  target_branch: "feature/git-write-readback",
  base_branch: "main",
  file_paths: ["docs/readback-safe-summary.md"],
  changed_files: [
    {
      path: "docs/readback-safe-summary.md",
      change_type: "modified",
      additions: 8,
      deletions: 1,
      reviewed: true,
      safe_summary: "Safe readback summary for UI preview.",
    },
  ],
  allowed_branches: ["feature/git-write-readback"],
  feature_flag_enabled: true,
  diff_summary: "1 documentation summary change prepared for preview readback.",
  commit_message: "Add safe GitWrite readback summary",
  force_push_requested: false,
  destructive_operation_requested: false,
  ci_trigger_requested: false,
};

export function createGitWriteIntent(
  payload: GitWriteCreateIntentRequest = SAFE_GIT_WRITE_READBACK_REQUEST,
): Promise<GitWriteReadbackRecord> {
  return requestJson<GitWriteReadbackRecord>("/git-write/intents", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getGitWriteIntent(
  intentId: string,
): Promise<GitWriteReadbackRecord> {
  return requestJson<GitWriteReadbackRecord>(`/git-write/intents/${intentId}`);
}

export function recordGitWriteApproval(
  intentId: string,
  payload: GitWriteApprovalRequest,
): Promise<GitWriteReadbackRecord> {
  return requestJson<GitWriteReadbackRecord>(
    `/git-write/intents/${intentId}/approve`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function listGitWriteAuditEvents(
  intentId: string,
): Promise<GitWriteAuditEventReadback[]> {
  return requestJson<GitWriteAuditEventReadback[]>(
    `/git-write/intents/${intentId}/audit`,
  );
}
