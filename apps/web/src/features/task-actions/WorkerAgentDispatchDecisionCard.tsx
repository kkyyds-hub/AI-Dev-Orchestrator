import { StatusBadge } from "../../components/StatusBadge";
import type {
  WorkerAgentDispatchDecision,
  WorkerAgentDispatchDecisionSafety,
  WorkerRunOnceResponse,
} from "./types";

type WorkerAgentDispatchDecisionCardProps = {
  decision: WorkerRunOnceResponse["agent_dispatch_decision"] | null | undefined;
  compact?: boolean;
};

type DispatchField = {
  key: string;
  label: string;
  value: string;
  tone?: "safe" | "warning" | "danger" | "neutral";
};

type DangerousSafetyField = {
  key: keyof WorkerAgentDispatchDecisionSafety;
  label: string;
};

const AGENT_LABELS_CN: Record<string, string> = {
  codex: "Codex 代码实现智能体",
  deepseek: "DeepSeek 文档与证据智能体",
  user: "用户决策",
  blocked: "安全阻断",
};

const STATUS_LABELS_CN: Record<string, string> = {
  suggested: "仅建议，未派发",
  needs_user_decision: "需要用户决策",
  blocked: "安全阻断",
  not_applicable: "不适用调度",
};

const INSTRUCTION_KIND_LABELS_CN: Record<string, string> = {
  none: "无需下一步指令",
  coding: "代码实现指令",
  review: "审查指令",
  docs: "文档与证据指令",
  user_decision: "用户决策指令",
  blocked: "阻断说明",
  retry: "重试说明",
  replay: "重新执行说明",
  pause: "暂停等待说明",
  replan: "重新规划说明",
  human_question: "人工问题",
};

const DANGEROUS_DISPATCH_SAFETY_FIELDS: DangerousSafetyField[] = [
  { key: "runs_git", label: "运行 Git" },
  { key: "runs_write_git", label: "Git 写操作风险" },
  { key: "git_add_triggered", label: "加入待提交区" },
  { key: "git_commit_triggered", label: "生成提交" },
  { key: "git_push_triggered", label: "推送远程" },
  { key: "pr_opened", label: "代码合并请求记录" },
  { key: "merge_triggered", label: "合并分支" },
  { key: "branch_deleted", label: "删除分支" },
  { key: "git_reset_triggered", label: "执行 Git reset" },
  { key: "git_checkout_triggered", label: "执行 Git checkout" },
  { key: "git_switch_triggered", label: "执行 Git switch" },
  { key: "git_stash_triggered", label: "执行 Git stash" },
  { key: "git_rebase_triggered", label: "执行 Git rebase" },
  { key: "git_tag_triggered", label: "创建 Git tag" },
  { key: "ci_triggered", label: "触发 CI" },
  { key: "execution_enabled", label: "启用执行" },
  { key: "worker_dispatch_triggered", label: "自动派发 Worker" },
  { key: "task_created", label: "创建任务" },
  { key: "retry_triggered", label: "自动重试" },
  { key: "auto_dispatch_triggered", label: "自动调度" },
];

export function WorkerAgentDispatchDecisionCard(
  props: WorkerAgentDispatchDecisionCardProps,
) {
  const decision = props.decision;
  if (!decision) {
    return null;
  }

  const dangerousFlags = getDangerousSafetyFlags(decision.safety);
  const hasDangerousFlags = dangerousFlags.length > 0;
  const recommendedAgentLabel = formatAgentLabel(decision);
  const statusLabel = formatStatusLabel(decision);
  const instructionKindLabel = formatInstructionKindLabel(decision);

  const summaryFields: DispatchField[] = [
    {
      key: "recommended_agent",
      label: "建议接手方",
      value: recommendedAgentLabel,
      tone: decision.dispatch_status === "blocked" ? "warning" : "safe",
    },
    {
      key: "dispatch_status",
      label: "调度状态",
      value: statusLabel,
      tone: decision.dispatch_status === "blocked" ? "warning" : "safe",
    },
    {
      key: "instruction_kind",
      label: "指令类型",
      value: instructionKindLabel,
    },
  ];

  return (
    <div
      data-testid="worker-agent-dispatch-decision-card"
      className="mt-3 rounded-xl border border-sky-500/20 bg-sky-500/5 p-3"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="text-xs tracking-[0.2em] text-sky-200">
            调度建议（只读）
          </div>
          <p className="mt-2 text-sm leading-6 text-zinc-200">
            AI 项目主管建议由 {recommendedAgentLabel} 接手下一步。
          </p>
          <p className="mt-2 text-sm leading-6 text-zinc-300">
            {decision.dispatch_reason_cn}
          </p>
          <p className="mt-2 text-xs leading-5 text-zinc-500">
            当前仅展示调度建议，不会自动派发 Worker、不会自动重试、不会创建任务，也不会执行任何产品运行时 Git 写操作。
          </p>
        </div>
        <StatusBadge
          label={hasDangerousFlags ? "安全标记异常" : "只读建议"}
          tone={hasDangerousFlags ? "danger" : "info"}
        />
      </div>

      <div
        className={`mt-3 grid gap-3 ${
          props.compact ? "sm:grid-cols-1" : "sm:grid-cols-2 xl:grid-cols-3"
        }`}
      >
        {summaryFields.map((field) => (
          <DispatchInfo
            key={field.key}
            label={field.label}
            value={field.value}
            tone={field.tone}
          />
        ))}
      </div>

      <div className="mt-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3">
        <div className="text-xs tracking-[0.2em] text-emerald-200">
          只读安全检查
        </div>
        {hasDangerousFlags ? (
          <div
            className={`mt-3 grid gap-3 ${
              props.compact ? "sm:grid-cols-1" : "sm:grid-cols-2 xl:grid-cols-3"
            }`}
          >
            <DispatchInfo
              label="危险安全标记"
              value={dangerousFlags.join("、")}
              tone="danger"
            />
          </div>
        ) : (
          <p className="mt-2 text-sm leading-6 text-emerald-100">
            未检测到自动派发、自动重试、创建任务、CI 触发或产品运行时 Git 写操作。
          </p>
        )}
      </div>
    </div>
  );
}

function formatAgentLabel(decision: WorkerAgentDispatchDecision): string {
  return (
    normalizeLabel(decision.recommended_agent_label_cn) ??
    AGENT_LABELS_CN[decision.recommended_agent] ??
    "未知智能体"
  );
}

function formatStatusLabel(decision: WorkerAgentDispatchDecision): string {
  return (
    STATUS_LABELS_CN[decision.dispatch_status] ??
    normalizeLabel(decision.dispatch_status_label_cn) ??
    "未知状态"
  );
}

function formatInstructionKindLabel(decision: WorkerAgentDispatchDecision): string {
  return (
    normalizeLabel(decision.instruction_kind_label_cn) ??
    INSTRUCTION_KIND_LABELS_CN[decision.instruction_kind] ??
    "未知指令类型"
  );
}

function normalizeLabel(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}

function getDangerousSafetyFlags(
  safety: WorkerAgentDispatchDecisionSafety,
): string[] {
  return DANGEROUS_DISPATCH_SAFETY_FIELDS.filter((field) => safety[field.key]).map(
    (field) => field.label,
  );
}

function DispatchInfo(field: Omit<DispatchField, "key">) {
  return (
    <div className={`rounded-xl border px-4 py-3 ${fieldToneClass(field.tone)}`}>
      <div className="text-xs tracking-[0.2em] opacity-70">{field.label}</div>
      <div className="mt-2 break-all text-sm font-medium">{field.value}</div>
    </div>
  );
}

function fieldToneClass(fieldTone: DispatchField["tone"]): string {
  switch (fieldTone) {
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
