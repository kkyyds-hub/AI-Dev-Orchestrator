export type ChangeSessionWorkspaceStatus = "clean" | "dirty";

export type ChangeSessionGuardStatus = "ready" | "blocked";

export type ChangeSessionDirtyFileScope =
  | "untracked"
  | "staged"
  | "unstaged"
  | "mixed";

export type ChangeSessionDirtyFile = {
  path: string;
  git_status: string;
  change_scope: ChangeSessionDirtyFileScope;
};

export type ChangeSession = {
  id: string;
  project_id: string;
  repository_workspace_id: string;
  repository_root_path: string;
  current_branch: string;
  head_ref: string;
  head_commit_sha: string | null;
  baseline_branch: string;
  baseline_ref: string;
  baseline_commit_sha: string | null;
  workspace_status: ChangeSessionWorkspaceStatus;
  guard_status: ChangeSessionGuardStatus;
  guard_summary: string;
  blocking_reasons: string[];
  dirty_file_count: number;
  dirty_files_truncated: boolean;
  dirty_files: ChangeSessionDirtyFile[];
  created_at: string;
  updated_at: string;
};
