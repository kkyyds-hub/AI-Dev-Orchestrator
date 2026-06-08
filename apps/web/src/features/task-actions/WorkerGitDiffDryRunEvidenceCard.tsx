import { StatusBadge } from "../../components/StatusBadge";
import type { WorkerRunOnceResponse } from "./types";

type WorkerGitDiffDryRunEvidenceCardProps = Pick<
  WorkerRunOnceResponse,
  | "git_diff_dry_run_ready"
  | "git_diff_dry_run_source"
  | "git_diff_dry_run_reason_code"
  | "git_diff_dry_run_worktree_path"
  | "git_diff_dry_run_has_changes"
  | "git_diff_dry_run_changed_files_count"
  | "git_diff_dry_run_changed_files"
  | "git_diff_dry_run_added_files"
  | "git_diff_dry_run_modified_files"
  | "git_diff_dry_run_deleted_files"
  | "git_diff_dry_run_renamed_files"
  | "git_diff_dry_run_status_summary_cn"
  | "git_diff_dry_run_diff_stat"
  | "git_diff_dry_run_diff_shortstat"
  | "git_diff_dry_run_branch_name"
  | "git_diff_dry_run_compare_branch"
  | "git_diff_dry_run_command"
  | "git_diff_dry_run_peek_command"
  | "git_diff_dry_run_danger_commands_applied"
  | "git_diff_dry_run_runs_git"
  | "git_diff_dry_run_runs_write_git"
  | "git_diff_dry_run_git_add_triggered"
  | "git_diff_dry_run_git_commit_triggered"
  | "git_diff_dry_run_git_push_triggered"
  | "git_diff_dry_run_pr_opened"
  | "git_diff_dry_run_ci_triggered"
  | "git_diff_dry_run_execution_enabled"
>;

type DiffInfoField = {
  key: string;
  label: string;
  value: string;
  tone?: "safe" | "warning" | "danger" | "neutral";
};

const REASON_LABELS: Record<string, string> = {
  worktree_path_unavailable: "当前没有可检查的工作区",
  worktree_path_missing: "工作区路径缺失",
  worktree_path_not_found: "工作区路径不存在",
  worktree_path_not_directory: "工作区路径不是目录",
  worktree_path_outside_allowed_root: "工作区路径不在允许范围内",
  git_diff_dry_run_command_failed: "只读检查命令失败",
  git_diff_dry_run_command_timed_out: "只读检查命令超时",
  git_diff_dry_run_failed: "代码改动预览失败",
};

export function WorkerGitDiffDryRunEvidenceCard(
  props: WorkerGitDiffDryRunEvidenceCardProps,
) {
  if (!hasGitDiffDryRunEvidence(props)) {
    return null;
  }

  const statusLabel = getStatusLabel(props);
  const summaryText = getSummaryText(props);
  const statusTone =
    props.git_diff_dry_run_ready === false
      ? "warning"
      : props.git_diff_dry_run_ready === true
        ? "success"
        : "neutral";

  const summaryFields: DiffInfoField[] = [
    {
      key: "ready",
      label: "预览是否就绪",
      value: formatBoolean(props.git_diff_dry_run_ready),
      tone: booleanTone(props.git_diff_dry_run_ready),
    },
    {
      key: "has_changes",
      label: "是否有改动",
      value: formatBoolean(props.git_diff_dry_run_has_changes),
      tone:
        props.git_diff_dry_run_has_changes === true
          ? "warning"
          : props.git_diff_dry_run_has_changes === false
            ? "safe"
            : "neutral",
    },
    {
      key: "changed_files_count",
      label: "改动文件数量",
      value:
        props.git_diff_dry_run_changed_files_count === null ||
        props.git_diff_dry_run_changed_files_count === undefined
          ? "未记录"
          : `${props.git_diff_dry_run_changed_files_count} 个`,
    },
    {
      key: "reason",
      label: "未就绪原因",
      value: localizeReason(props.git_diff_dry_run_reason_code),
      tone: props.git_diff_dry_run_reason_code ? "warning" : "neutral",
    },
    {
      key: "branch",
      label: "当前分支",
      value: formatText(props.git_diff_dry_run_branch_name),
    },
    {
      key: "compare_branch",
      label: "对比分支",
      value: formatText(props.git_diff_dry_run_compare_branch),
    },
    {
      key: "worktree_path",
      label: "检查工作区",
      value: formatText(props.git_diff_dry_run_worktree_path),
    },
    {
      key: "source",
      label: "检测来源",
      value: localizeSource(props.git_diff_dry_run_source),
    },
  ];

  const safetyFields: DiffInfoField[] = [
    {
      key: "runs_git",
      label: "只读代码检查",
      value:
        props.git_diff_dry_run_runs_git === true
          ? "已执行只读代码检查"
          : props.git_diff_dry_run_runs_git === false
            ? "未执行代码检查"
            : "未记录",
      tone: props.git_diff_dry_run_runs_git === true ? "safe" : "neutral",
    },
    {
      key: "runs_write_git",
      label: "提交或推送等写操作",
      value: formatForbiddenFlag(
        props.git_diff_dry_run_runs_write_git,
        "没有产生提交或推送等写操作",
      ),
      tone: forbiddenTone(props.git_diff_dry_run_runs_write_git),
    },
    {
      key: "git_add",
      label: "加入待提交区",
      value: formatForbiddenFlag(
        props.git_diff_dry_run_git_add_triggered,
        "未加入待提交区",
      ),
      tone: forbiddenTone(props.git_diff_dry_run_git_add_triggered),
    },
    {
      key: "git_commit",
      label: "生成本地提交",
      value: formatForbiddenFlag(
        props.git_diff_dry_run_git_commit_triggered,
        "未生成本地提交",
      ),
      tone: forbiddenTone(props.git_diff_dry_run_git_commit_triggered),
    },
    {
      key: "git_push",
      label: "推送远程仓库",
      value: formatForbiddenFlag(
        props.git_diff_dry_run_git_push_triggered,
        "未推送到远程仓库",
      ),
      tone: forbiddenTone(props.git_diff_dry_run_git_push_triggered),
    },
    {
      key: "pr_opened",
      label: "创建代码合并请求",
      value: formatForbiddenFlag(
        props.git_diff_dry_run_pr_opened,
        "未创建代码合并请求",
      ),
      tone: forbiddenTone(props.git_diff_dry_run_pr_opened),
    },
    {
      key: "ci_triggered",
      label: "触发自动检查",
      value: formatForbiddenFlag(
        props.git_diff_dry_run_ci_triggered,
        "未触发自动检查",
      ),
      tone: forbiddenTone(props.git_diff_dry_run_ci_triggered),
    },
    {
      key: "execution_enabled",
      label: "开启真实提交",
      value: formatForbiddenFlag(
        props.git_diff_dry_run_execution_enabled,
        "未开启真实提交",
      ),
      tone: forbiddenTone(props.git_diff_dry_run_execution_enabled),
    },
  ];

  const fileGroups = [
    { key: "changed", label: "全部改动文件", files: props.git_diff_dry_run_changed_files },
    { key: "added", label: "新增文件", files: props.git_diff_dry_run_added_files },
    { key: "modified", label: "修改文件", files: props.git_diff_dry_run_modified_files },
    { key: "deleted", label: "删除文件", files: props.git_diff_dry_run_deleted_files },
    { key: "renamed", label: "重命名文件", files: props.git_diff_dry_run_renamed_files },
  ];

  return (
    <div
      data-testid="worker-git-diff-dry-run-evidence-card"
      className="mt-3 rounded-xl border border-[#333333] bg-transparent p-3"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="text-xs tracking-[0.2em] text-zinc-400">
            代码改动预览
          </div>
          <p className="mt-2 text-sm leading-6 text-zinc-300">{summaryText}</p>
          <p className="mt-2 text-sm leading-6 text-zinc-300">
            这里只展示只读检查结果，不会加入待提交区、生成本地提交、推送远程仓库或创建代码合并请求。
          </p>
        </div>
        <StatusBadge label={statusLabel} tone={statusTone} />
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {summaryFields.map((field) => (
          <DiffInfo
            key={field.key}
            label={field.label}
            value={field.value}
            tone={field.tone}
          />
        ))}
      </div>

      {props.git_diff_dry_run_diff_shortstat || props.git_diff_dry_run_diff_stat ? (
        <div className="mt-3 rounded-xl border border-[#333333] bg-[#1f1f1f] p-3">
          <div className="text-xs tracking-[0.2em] text-zinc-500">改动统计</div>
          {props.git_diff_dry_run_diff_shortstat ? (
            <p className="mt-2 break-words text-sm leading-6 text-zinc-200">
              {props.git_diff_dry_run_diff_shortstat}
            </p>
          ) : null}
          {props.git_diff_dry_run_diff_stat ? (
            <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-zinc-300">
              {props.git_diff_dry_run_diff_stat}
            </pre>
          ) : null}
        </div>
      ) : null}

      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        {fileGroups.map((group) => (
          <FileList key={group.key} label={group.label} files={group.files} />
        ))}
      </div>

      <div className="mt-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3">
        <div className="text-xs tracking-[0.2em] text-emerald-200">
          只读安全标记
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {safetyFields.map((field) => (
            <DiffInfo
              key={field.key}
              label={field.label}
              value={field.value}
              tone={field.tone}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function hasGitDiffDryRunEvidence(
  props: WorkerGitDiffDryRunEvidenceCardProps,
): boolean {
  return (
    props.git_diff_dry_run_ready !== null ||
    props.git_diff_dry_run_has_changes !== null ||
    props.git_diff_dry_run_changed_files.length > 0 ||
    props.git_diff_dry_run_added_files.length > 0 ||
    props.git_diff_dry_run_modified_files.length > 0 ||
    props.git_diff_dry_run_deleted_files.length > 0 ||
    props.git_diff_dry_run_renamed_files.length > 0 ||
    Boolean(props.git_diff_dry_run_status_summary_cn) ||
    Boolean(props.git_diff_dry_run_reason_code)
  );
}

function getStatusLabel(props: WorkerGitDiffDryRunEvidenceCardProps): string {
  if (props.git_diff_dry_run_ready === true) {
    return props.git_diff_dry_run_has_changes ? "检测到改动" : "没有改动";
  }
  if (props.git_diff_dry_run_ready === false) {
    return "预览未完成";
  }
  return "未记录";
}

function getSummaryText(props: WorkerGitDiffDryRunEvidenceCardProps): string {
  if (props.git_diff_dry_run_status_summary_cn) {
    return `${props.git_diff_dry_run_status_summary_cn}。改动只是预览结果，尚未被提交或推送。`;
  }
  if (props.git_diff_dry_run_ready === true && props.git_diff_dry_run_has_changes) {
    return `代码改动预览已完成：检测到 ${props.git_diff_dry_run_changed_files_count ?? 0} 个文件变更。改动只是预览结果，尚未被提交或推送。`;
  }
  if (props.git_diff_dry_run_ready === true) {
    return "本次执行未产生代码改动。";
  }
  if (props.git_diff_dry_run_ready === false) {
    return "代码改动预览失败或已跳过，请查看未就绪原因。";
  }
  return "本次执行没有返回代码改动预览。";
}

function FileList(props: { label: string; files: string[] }) {
  return (
    <div className="rounded-xl border border-[#333333] bg-[#1f1f1f] p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs tracking-[0.2em] text-zinc-500">{props.label}</div>
        <span className="text-xs text-zinc-500">{props.files.length} 个</span>
      </div>
      {props.files.length ? (
        <ul className="mt-2 max-h-36 space-y-1 overflow-auto pr-2 text-xs leading-5 text-zinc-300">
          {props.files.map((file) => (
            <li key={`${props.label}-${file}`} className="break-all">
              {file}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-xs leading-5 text-zinc-500">暂无记录。</p>
      )}
    </div>
  );
}

function DiffInfo(field: DiffInfoField) {
  return (
    <div className={`rounded-xl border px-4 py-3 ${fieldToneClass(field.tone)}`}>
      <div className="text-xs tracking-[0.2em] opacity-70">{field.label}</div>
      <div className="mt-2 break-all text-sm font-medium">{field.value}</div>
    </div>
  );
}

function formatBoolean(value: boolean | null | undefined): string {
  if (value === null || value === undefined) {
    return "未记录";
  }
  return value ? "是" : "否";
}

function formatForbiddenFlag(value: boolean | null | undefined, falseText: string) {
  if (value === true) {
    return "安全标记异常";
  }
  if (value === false) {
    return falseText;
  }
  return "未记录";
}

function forbiddenTone(value: boolean | null | undefined): DiffInfoField["tone"] {
  if (value === true) {
    return "danger";
  }
  if (value === false) {
    return "safe";
  }
  return "neutral";
}

function booleanTone(value: boolean | null | undefined): DiffInfoField["tone"] {
  if (value === null || value === undefined) {
    return "neutral";
  }
  return value ? "safe" : "warning";
}

function formatText(value: string | null | undefined): string {
  if (!value) {
    return "未记录";
  }
  const normalized = value.trim();
  return normalized.length ? normalized : "未记录";
}

function localizeReason(value: string | null | undefined): string {
  if (!value) {
    return "无";
  }
  return REASON_LABELS[value] ?? "未识别原因";
}

function localizeSource(value: string | null | undefined): string {
  if (!value) {
    return "未记录";
  }
  if (value === "agent_session_worktree_diff") {
    return "智能体工作区只读检查";
  }
  return "其他只读检查来源";
}

function fieldToneClass(tone: DiffInfoField["tone"]): string {
  switch (tone) {
    case "safe":
      return "border-emerald-500/20 bg-emerald-500/5 text-emerald-100";
    case "warning":
      return "border-amber-500/20 bg-amber-500/5 text-amber-100";
    case "danger":
      return "border-rose-500/20 bg-rose-500/5 text-rose-100";
    default:
      return "border-[#333333] bg-[#1f1f1f] text-zinc-100";
  }
}
