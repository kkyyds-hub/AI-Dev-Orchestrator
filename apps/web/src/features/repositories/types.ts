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

export type FileLocatorQuery = {
  task_id: string | null;
  task_title: string | null;
  task_query: string | null;
  keywords: string[];
  path_prefixes: string[];
  module_names: string[];
  file_types: string[];
  limit: number;
  summary: string;
};

export type FileLocatorCandidate = {
  relative_path: string;
  language: string;
  file_type: string;
  byte_size: number;
  line_count: number;
  score: number;
  match_reasons: string[];
  matched_keywords: string[];
  preview: string | null;
};

export type FileLocatorResult = {
  project_id: string;
  repository_root_path: string;
  ignored_directory_names: string[];
  query: FileLocatorQuery;
  scanned_file_count: number;
  candidate_count: number;
  total_match_count: number;
  truncated: boolean;
  generated_at: string;
  candidates: FileLocatorCandidate[];
};

export type CodeContextPackEntry = {
  relative_path: string;
  language: string;
  file_type: string;
  byte_size: number;
  line_count: number;
  included_bytes: number;
  included_line_count: number;
  start_line: number;
  end_line: number;
  truncated: boolean;
  match_reasons: string[];
  excerpt: string;
};

export type CodeContextPack = {
  project_id: string | null;
  repository_root_path: string;
  source_summary: string;
  focus_terms: string[];
  selected_paths: string[];
  omitted_paths: string[];
  max_total_bytes: number;
  max_bytes_per_file: number;
  included_file_count: number;
  total_included_bytes: number;
  truncated: boolean;
  generated_at: string;
  entries: CodeContextPackEntry[];
};

export type FileLocatorSearchInput = {
  task_id?: string | null;
  task_query?: string | null;
  keywords?: string[];
  path_prefixes?: string[];
  module_names?: string[];
  file_types?: string[];
  limit?: number;
};

export type CodeContextPackBuildInput = FileLocatorSearchInput & {
  selected_paths: string[];
  max_total_bytes?: number;
  max_bytes_per_file?: number;
  selection_reasons_by_path?: Record<string, string[]>;
};
