import { StatusBadge } from "../../components/StatusBadge";
import type { WorkerRunOnceResponse } from "./types";

type WorkerDeliveryGateEvidenceCardProps = Pick<
  WorkerRunOnceResponse,
  | "delivery_gate_evidence_ready"
  | "delivery_gate_evidence_source"
  | "delivery_gate_evidence_reason_code"
  | "delivery_gate_evidence_worktree_path"
  | "delivery_gate_evidence_branch_name"
  | "delivery_gate_evidence_proposed_operation"
  | "delivery_gate_evidence_changed_files_count"
  | "delivery_gate_evidence_changed_files"
  | "delivery_gate_evidence_next_required_action"
  | "delivery_gate_evidence_user_confirmation_required"
  | "delivery_gate_evidence_human_approval_required"
  | "delivery_gate_evidence_delivery_audit_event_present"
  | "delivery_gate_evidence_delivery_audit_event_type"
  | "delivery_gate_evidence_delivery_audit_event_ready"
  | "delivery_gate_evidence_summary_cn"
  | "delivery_gate_evidence_satisfied_conditions"
  | "delivery_gate_evidence_blocking_reasons"
  | "delivery_gate_evidence_runs_git"
  | "delivery_gate_evidence_runs_write_git"
  | "delivery_gate_evidence_git_add_triggered"
  | "delivery_gate_evidence_git_commit_triggered"
  | "delivery_gate_evidence_git_push_triggered"
  | "delivery_gate_evidence_pr_opened"
  | "delivery_gate_evidence_ci_triggered"
  | "delivery_gate_evidence_execution_enabled"
  | "delivery_gate_evidence_operation_applied"
  | "delivery_gate_evidence_approval_granted"
  | "delivery_gate_evidence_gate_allows_write"
  | "delivery_gate_evidence_gate_allows_user_confirmation"
>;

type GateField = {
  key: string;
  label: string;
  value: string;
  tone?: "safe" | "warning" | "danger" | "neutral";
};

const REASON_LABELS: Record<string, string> = {
  agent_session_missing: "会话信息缺失",
  worktree_unavailable: "工作区不可用",
  branch_missing: "工作区未绑定分支",
  workspace_not_clean: "工作区状态不一致",
  diff_evidence_not_ready: "代码改动预览未就绪",
  no_changes: "当前没有可提交的代码改动",
  diff_write_flag_triggered: "代码改动预览安全标记异常",
  operation_dry_run_not_ready: "提交预览未就绪",
  unsupported_operation: "当前操作类型不支持交付前检查",
  operation_write_flag_triggered: "提交预览安全标记异常",
  operation_already_applied: "预览动作已被标记为应用",
  approval_already_granted: "审批已被标记为授予",
  feature_flag_enabled: "真实写入开关已开启",
  evidence_mismatch: "代码改动预览与提交预览不一致",
  audit_evidence_missing: "缺少交付审计记录",
};

export function WorkerDeliveryGateEvidenceCard(
  props: WorkerDeliveryGateEvidenceCardProps,
) {
  if (!hasDeliveryGateEvidence(props)) {
    return null;
  }

  const statusTone =
    props.delivery_gate_evidence_ready === false
      ? "warning"
      : props.delivery_gate_evidence_ready === true
        ? "success"
        : "neutral";

  const summaryFields: GateField[] = [
    {
      key: "ready",
      label: "交付前检查是否通过",
      value: formatBoolean(props.delivery_gate_evidence_ready),
      tone: booleanTone(props.delivery_gate_evidence_ready),
    },
    {
      key: "next_action",
      label: "下一步",
      value: localizeNextAction(props.delivery_gate_evidence_next_required_action),
      tone:
        props.delivery_gate_evidence_next_required_action ===
        "await_user_confirmation"
          ? "safe"
          : props.delivery_gate_evidence_next_required_action
            ? "warning"
            : "neutral",
    },
    {
      key: "reason",
      label: "阻断原因",
      value: localizeReason(props.delivery_gate_evidence_reason_code),
      tone: props.delivery_gate_evidence_reason_code ? "warning" : "neutral",
    },
    {
      key: "operation",
      label: "预览动作",
      value: localizeOperation(props.delivery_gate_evidence_proposed_operation),
    },
    {
      key: "changed_files_count",
      label: "涉及文件数量",
      value: formatCount(props.delivery_gate_evidence_changed_files_count),
    },
    {
      key: "branch",
      label: "目标分支",
      value: formatText(props.delivery_gate_evidence_branch_name),
    },
    {
      key: "worktree",
      label: "工作区",
      value: formatText(props.delivery_gate_evidence_worktree_path),
    },
    {
      key: "source",
      label: "证据来源",
      value: localizeSource(props.delivery_gate_evidence_source),
    },
  ];

  const auditFields: GateField[] = [
    {
      key: "audit_present",
      label: "存在交付审计记录",
      value: formatBoolean(props.delivery_gate_evidence_delivery_audit_event_present),
      tone: booleanTone(props.delivery_gate_evidence_delivery_audit_event_present),
    },
    {
      key: "audit_type",
      label: "最近审计类型",
      value: localizeAuditType(props.delivery_gate_evidence_delivery_audit_event_type),
    },
    {
      key: "audit_ready",
      label: "审计记录可用",
      value: formatBoolean(props.delivery_gate_evidence_delivery_audit_event_ready),
      tone: booleanTone(props.delivery_gate_evidence_delivery_audit_event_ready),
    },
    {
      key: "user_confirmation",
      label: "需要用户确认",
      value: formatBoolean(props.delivery_gate_evidence_user_confirmation_required),
      tone: booleanTone(props.delivery_gate_evidence_user_confirmation_required),
    },
    {
      key: "human_approval",
      label: "需要人工审批",
      value: formatBoolean(props.delivery_gate_evidence_human_approval_required),
      tone: booleanTone(props.delivery_gate_evidence_human_approval_required),
    },
  ];

  const safetyFields: GateField[] = [
    safeFlag("runs_git", "执行代码命令", props.delivery_gate_evidence_runs_git, "未执行代码命令"),
    safeFlag(
      "runs_write_git",
      "提交或推送等写操作",
      props.delivery_gate_evidence_runs_write_git,
      "未执行提交或推送等写操作",
    ),
    safeFlag(
      "git_add",
      "加入待提交区",
      props.delivery_gate_evidence_git_add_triggered,
      "未加入待提交区",
    ),
    safeFlag(
      "git_commit",
      "生成本地提交",
      props.delivery_gate_evidence_git_commit_triggered,
      "未生成本地提交",
    ),
    safeFlag(
      "git_push",
      "推送远程仓库",
      props.delivery_gate_evidence_git_push_triggered,
      "未推送到远程仓库",
    ),
    safeFlag(
      "pr_opened",
      "创建代码合并请求",
      props.delivery_gate_evidence_pr_opened,
      "未创建代码合并请求",
    ),
    safeFlag("ci", "触发自动检查", props.delivery_gate_evidence_ci_triggered, "未触发自动检查"),
    safeFlag(
      "execution_enabled",
      "开启真实写入",
      props.delivery_gate_evidence_execution_enabled,
      "未开启真实写入",
    ),
    safeFlag(
      "operation_applied",
      "应用预览动作",
      props.delivery_gate_evidence_operation_applied,
      "未应用预览动作",
    ),
    safeFlag(
      "approval_granted",
      "授予审批",
      props.delivery_gate_evidence_approval_granted,
      "未授予审批",
    ),
    safeFlag(
      "gate_allows_write",
      "授权写操作",
      props.delivery_gate_evidence_gate_allows_write,
      "未授权写操作",
    ),
    {
      key: "gate_allows_user_confirmation",
      label: "允许进入用户确认界面",
      value: formatBoolean(props.delivery_gate_evidence_gate_allows_user_confirmation),
      tone:
        props.delivery_gate_evidence_gate_allows_user_confirmation === true
          ? "safe"
          : props.delivery_gate_evidence_gate_allows_user_confirmation === false
            ? "warning"
            : "neutral",
    },
  ];

  return (
    <div
      data-testid="worker-delivery-gate-evidence-card"
      className="mt-3 rounded-xl border border-[#333333] bg-transparent p-3"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="text-xs tracking-[0.2em] text-zinc-400">
            交付前检查
          </div>
          <p className="mt-2 text-sm leading-6 text-zinc-300">
            {props.delivery_gate_evidence_summary_cn || "这里展示交付前检查结果。"}
          </p>
          <p className="mt-2 text-sm leading-6 text-zinc-300">
            这只是进入用户确认界面的前置检查，不表示代码已经写入仓库、推送远程仓库或创建代码合并请求。
          </p>
        </div>
        <StatusBadge label={statusLabel(props)} tone={statusTone} />
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {summaryFields.map((field) => (
          <GateInfo
            key={field.key}
            label={field.label}
            value={field.value}
            tone={field.tone}
          />
        ))}
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <ListBox label="已满足条件" values={props.delivery_gate_evidence_satisfied_conditions} />
        <ListBox label="未满足条件" values={props.delivery_gate_evidence_blocking_reasons} />
        <ListBox label="涉及文件" values={props.delivery_gate_evidence_changed_files} />
      </div>

      <div className="mt-3 rounded-xl border border-[#333333] bg-[#1f1f1f] p-3">
        <div className="text-xs tracking-[0.2em] text-zinc-500">审计证据与确认要求</div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {auditFields.map((field) => (
            <GateInfo
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
            <GateInfo
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

function hasDeliveryGateEvidence(props: WorkerDeliveryGateEvidenceCardProps): boolean {
  return (
    props.delivery_gate_evidence_ready !== null ||
    Boolean(props.delivery_gate_evidence_reason_code) ||
    Boolean(props.delivery_gate_evidence_summary_cn) ||
    props.delivery_gate_evidence_satisfied_conditions.length > 0 ||
    props.delivery_gate_evidence_blocking_reasons.length > 0
  );
}

function statusLabel(props: WorkerDeliveryGateEvidenceCardProps): string {
  if (props.delivery_gate_evidence_ready === true) {
    return "检查已通过";
  }
  if (props.delivery_gate_evidence_ready === false) {
    return "检查未通过";
  }
  return "未记录";
}

function safeFlag(
  key: string,
  label: string,
  value: boolean | null,
  falseText: string,
): GateField {
  return {
    key,
    label,
    value: formatForbiddenFlag(value, falseText),
    tone: forbiddenTone(value),
  };
}

function ListBox(props: { label: string; values: string[] }) {
  return (
    <div className="rounded-xl border border-[#333333] bg-[#1f1f1f] p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs tracking-[0.2em] text-zinc-500">{props.label}</div>
        <span className="text-xs text-zinc-500">{props.values.length} 项</span>
      </div>
      {props.values.length ? (
        <ul className="mt-2 max-h-36 space-y-1 overflow-auto pr-2 text-xs leading-5 text-zinc-300">
          {props.values.map((value) => (
            <li key={`${props.label}-${value}`} className="break-all">
              {localizeCondition(value)}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-xs leading-5 text-zinc-500">暂无记录。</p>
      )}
    </div>
  );
}

function GateInfo(field: Omit<GateField, "key">) {
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

function forbiddenTone(value: boolean | null | undefined): GateField["tone"] {
  if (value === true) {
    return "danger";
  }
  if (value === false) {
    return "safe";
  }
  return "neutral";
}

function booleanTone(value: boolean | null | undefined): GateField["tone"] {
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

function localizeNextAction(value: string | null | undefined): string {
  if (value === "await_user_confirmation") {
    return "等待用户确认";
  }
  if (value === "resolve_blocking_conditions") {
    return "需要解决阻断条件";
  }
  if (value === "none") {
    return "无下一步动作";
  }
  return formatText(value);
}

function localizeAuditType(value: string | null | undefined): string {
  if (value === "delivery_diff_dry_run_collected") {
    return "代码改动预览审计已记录";
  }
  if (value === "delivery_diff_dry_run_failed") {
    return "代码改动预览审计失败";
  }
  if (value === "delivery_diff_dry_run_skipped") {
    return "代码改动预览审计已跳过";
  }
  return formatText(value);
}

function localizeSource(value: string | null | undefined): string {
  if (value === "delivery_gate_evidence") {
    return "交付前检查证据";
  }
  return formatText(value);
}

function localizeCondition(value: string): string {
  const [, reasonCode] = value.split(":");
  if (reasonCode) {
    return `${value}（${localizeReason(reasonCode)}）`;
  }
  return value;
}

function fieldToneClass(tone: GateField["tone"]): string {
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
