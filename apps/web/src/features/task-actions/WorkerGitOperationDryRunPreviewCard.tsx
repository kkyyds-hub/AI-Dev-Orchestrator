import { StatusBadge } from "../../components/StatusBadge";
import type { WorkerRunOnceResponse } from "./types";

type WorkerGitOperationDryRunPreviewCardProps = Pick<
  WorkerRunOnceResponse,
  | "git_operation_dry_run_ready"
  | "git_operation_dry_run_source"
  | "git_operation_dry_run_reason_code"
  | "git_operation_dry_run_worktree_path"
  | "git_operation_dry_run_branch_name"
  | "git_operation_dry_run_changed_files_count"
  | "git_operation_dry_run_changed_files"
  | "git_operation_dry_run_added_files"
  | "git_operation_dry_run_modified_files"
  | "git_operation_dry_run_deleted_files"
  | "git_operation_dry_run_renamed_files"
  | "git_operation_dry_run_proposed_operation"
  | "git_operation_dry_run_proposed_steps"
  | "git_operation_dry_run_proposed_commit_message"
  | "git_operation_dry_run_user_confirmation_required"
  | "git_operation_dry_run_human_approval_required"
  | "git_operation_dry_run_feature_flag_required"
  | "git_operation_dry_run_summary_cn"
  | "git_operation_dry_run_runs_git"
  | "git_operation_dry_run_runs_write_git"
  | "git_operation_dry_run_git_add_triggered"
  | "git_operation_dry_run_git_commit_triggered"
  | "git_operation_dry_run_git_push_triggered"
  | "git_operation_dry_run_pr_opened"
  | "git_operation_dry_run_ci_triggered"
  | "git_operation_dry_run_execution_enabled"
  | "git_operation_dry_run_operation_applied"
  | "git_operation_dry_run_approval_granted"
>;

type PreviewField = {
  key: string;
  label: string;
  value: string;
  tone?: "safe" | "warning" | "danger" | "neutral";
};

const REASON_LABELS: Record<string, string> = {
  session_missing: "会话信息缺失",
  worktree_unavailable: "工作区不可用",
  feature_flag_disabled: "提交预览开关未开启",
  feature_flag_enabled: "真实写入开关已开启",
  diff_evidence_not_ready: "代码改动预览未就绪",
  no_changes: "当前没有可提交的代码改动",
  write_already_triggered: "检测到写操作标记异常",
};

export function WorkerGitOperationDryRunPreviewCard(
  props: WorkerGitOperationDryRunPreviewCardProps,
) {
  if (!hasOperationPreview(props)) {
    return null;
  }

  const statusTone =
    props.git_operation_dry_run_ready === false
      ? "warning"
      : props.git_operation_dry_run_ready === true
        ? "success"
        : "neutral";

  const summaryFields: PreviewField[] = [
    {
      key: "ready",
      label: "提交预览是否就绪",
      value: formatBoolean(props.git_operation_dry_run_ready),
      tone: booleanTone(props.git_operation_dry_run_ready),
    },
    {
      key: "operation",
      label: "预览动作",
      value: localizeOperation(props.git_operation_dry_run_proposed_operation),
    },
    {
      key: "changed_files_count",
      label: "涉及文件数量",
      value: formatCount(props.git_operation_dry_run_changed_files_count),
    },
    {
      key: "reason",
      label: "未就绪原因",
      value: localizeReason(props.git_operation_dry_run_reason_code),
      tone: props.git_operation_dry_run_reason_code ? "warning" : "neutral",
    },
    {
      key: "branch",
      label: "目标分支",
      value: formatText(props.git_operation_dry_run_branch_name),
    },
    {
      key: "worktree",
      label: "工作区",
      value: formatText(props.git_operation_dry_run_worktree_path),
    },
    {
      key: "source",
      label: "证据来源",
      value: localizeSource(props.git_operation_dry_run_source),
    },
    {
      key: "commit_message",
      label: "建议提交说明",
      value: formatText(props.git_operation_dry_run_proposed_commit_message),
    },
  ];

  const confirmationFields: PreviewField[] = [
    {
      key: "user_confirmation",
      label: "需要用户确认",
      value: formatBoolean(props.git_operation_dry_run_user_confirmation_required),
      tone: booleanTone(props.git_operation_dry_run_user_confirmation_required),
    },
    {
      key: "human_approval",
      label: "需要人工审批",
      value: formatBoolean(props.git_operation_dry_run_human_approval_required),
      tone: booleanTone(props.git_operation_dry_run_human_approval_required),
    },
    {
      key: "feature_flag",
      label: "需要功能开关",
      value: formatBoolean(props.git_operation_dry_run_feature_flag_required),
      tone: booleanTone(props.git_operation_dry_run_feature_flag_required),
    },
  ];

  const safetyFields: PreviewField[] = [
    safeFlag("runs_git", "Git 检查", props.git_operation_dry_run_runs_git, "未执行 Git 检查"),
    safeFlag(
      "runs_write_git",
      "提交或推送等写操作",
      props.git_operation_dry_run_runs_write_git,
      "未执行提交或推送等写操作",
    ),
    safeFlag(
      "git_add",
      "加入待提交区",
      props.git_operation_dry_run_git_add_triggered,
      "未加入待提交区",
    ),
    safeFlag(
      "git_commit",
      "生成本地提交",
      props.git_operation_dry_run_git_commit_triggered,
      "未生成本地提交",
    ),
    safeFlag(
      "git_push",
      "推送远程仓库",
      props.git_operation_dry_run_git_push_triggered,
      "未推送到远程仓库",
    ),
    safeFlag(
      "pr_opened",
      "创建代码合并请求",
      props.git_operation_dry_run_pr_opened,
      "未创建代码合并请求",
    ),
    safeFlag("ci", "触发自动检查", props.git_operation_dry_run_ci_triggered, "未触发自动检查"),
    safeFlag(
      "execution_enabled",
      "开启真实写入",
      props.git_operation_dry_run_execution_enabled,
      "未开启真实写入",
    ),
    safeFlag(
      "operation_applied",
      "应用预览动作",
      props.git_operation_dry_run_operation_applied,
      "未应用预览动作",
    ),
    safeFlag(
      "approval_granted",
      "用户确认",
      props.git_operation_dry_run_approval_granted,
      "用户尚未确认",
    ),
  ];

  return (
    <div
      data-testid="worker-git-operation-dry-run-preview-card"
      className="mt-3 rounded-xl border border-[#333333] bg-transparent p-3"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="text-xs tracking-[0.2em] text-zinc-400">
            提交预览
          </div>
          <p className="mt-2 text-sm leading-6 text-zinc-300">
            {props.git_operation_dry_run_summary_cn ||
              "这里展示如果后续由用户确认，系统计划准备的提交动作。当前仅为只读预览。"}
          </p>
          <p className="mt-2 text-sm leading-6 text-zinc-300">
            当前未加入待提交区、未生成本地提交、未推送远程仓库、未创建代码合并请求。
          </p>
        </div>
        <StatusBadge label={statusLabel(props)} tone={statusTone} />
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {summaryFields.map((field) => (
          <PreviewInfo
            key={field.key}
            label={field.label}
            value={field.value}
            tone={field.tone}
          />
        ))}
      </div>

      {props.git_operation_dry_run_proposed_steps.length ? (
        <div className="mt-3 rounded-xl border border-[#333333] bg-[#1f1f1f] p-3">
          <div className="text-xs tracking-[0.2em] text-zinc-500">预览步骤</div>
          <ol className="mt-2 space-y-1 text-sm leading-6 text-zinc-300">
            {props.git_operation_dry_run_proposed_steps.map((step) => (
              <li key={step} className="break-words">
                {step}
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <FileList label="全部涉及文件" files={props.git_operation_dry_run_changed_files} />
        <FileList label="新增文件" files={props.git_operation_dry_run_added_files} />
        <FileList label="修改文件" files={props.git_operation_dry_run_modified_files} />
        <FileList label="删除文件" files={props.git_operation_dry_run_deleted_files} />
        <FileList label="重命名文件" files={props.git_operation_dry_run_renamed_files} />
      </div>

      <div className="mt-3 rounded-xl border border-[#333333] bg-[#1f1f1f] p-3">
        <div className="text-xs tracking-[0.2em] text-zinc-500">确认要求</div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {confirmationFields.map((field) => (
            <PreviewInfo
              key={field.key}
              label={field.label}
              value={field.value}
              tone={field.tone}
            />
          ))}
        </div>
      </div>

      <div className="mt-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3">
        <div className="text-xs tracking-[0.2em] text-emerald-200">操作安全标记</div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {safetyFields.map((field) => (
            <PreviewInfo
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

function hasOperationPreview(props: WorkerGitOperationDryRunPreviewCardProps): boolean {
  return (
    props.git_operation_dry_run_ready !== null ||
    Boolean(props.git_operation_dry_run_reason_code) ||
    Boolean(props.git_operation_dry_run_summary_cn) ||
    Boolean(props.git_operation_dry_run_proposed_operation) ||
    props.git_operation_dry_run_changed_files.length > 0
  );
}

function statusLabel(props: WorkerGitOperationDryRunPreviewCardProps): string {
  if (props.git_operation_dry_run_ready === true) {
    return "预览已就绪";
  }
  if (props.git_operation_dry_run_ready === false) {
    return "预览未就绪";
  }
  return "未记录";
}

function safeFlag(
  key: string,
  label: string,
  value: boolean | null,
  falseText: string,
): PreviewField {
  return {
    key,
    label,
    value: formatForbiddenFlag(value, falseText),
    tone: forbiddenTone(value),
  };
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

function PreviewInfo(field: Omit<PreviewField, "key">) {
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

function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "未记录";
  }
  return `${value} 个`;
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

function forbiddenTone(value: boolean | null | undefined): PreviewField["tone"] {
  if (value === true) {
    return "danger";
  }
  if (value === false) {
    return "safe";
  }
  return "neutral";
}

function booleanTone(value: boolean | null | undefined): PreviewField["tone"] {
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
  return REASON_LABELS[value] ?? value;
}

function localizeOperation(value: string | null | undefined): string {
  if (value === "git_add_commit") {
    return "准备加入待提交区并生成本地提交";
  }
  if (value === "none") {
    return "暂无可预览动作";
  }
  return formatText(value);
}

function localizeSource(value: string | null | undefined): string {
  if (value === "git_operation_dry_run") {
    return "提交预览证据";
  }
  return formatText(value);
}

function fieldToneClass(tone: PreviewField["tone"]): string {
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
