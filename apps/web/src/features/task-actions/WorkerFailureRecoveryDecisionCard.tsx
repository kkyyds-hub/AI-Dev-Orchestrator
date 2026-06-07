import { StatusBadge } from "../../components/StatusBadge";
import type { WorkerRunOnceResponse } from "./types";

type WorkerFailureRecoveryDecisionCardProps = {
  decision: WorkerRunOnceResponse["failure_recovery_decision"] | null | undefined;
  compact?: boolean;
};

type RecoveryField = {
  key: string;
  label: string;
  value: string;
  tone?: "safe" | "warning" | "danger" | "neutral";
};

export function WorkerFailureRecoveryDecisionCard(
  props: WorkerFailureRecoveryDecisionCardProps,
) {
  const decision = props.decision;
  if (!decision) {
    return null;
  }

  const summaryFields: RecoveryField[] = [
    {
      key: "owner",
      label: "建议负责人",
      value: decision.recommended_owner_label_cn,
      tone: decision.requires_human_decision ? "warning" : "safe",
    },
    {
      key: "action",
      label: "建议动作",
      value: decision.next_action_label_cn,
      tone: decision.retry_allowed ? "safe" : "warning",
    },
    {
      key: "instruction_kind",
      label: "指令类型",
      value: decision.next_instruction_kind_label_cn,
    },
    {
      key: "recoverable",
      label: "可恢复",
      value: formatBoolean(decision.recoverable),
      tone: decision.recoverable ? "safe" : "warning",
    },
    {
      key: "retry_allowed",
      label: "允许重试",
      value: formatBoolean(decision.retry_allowed),
      tone: decision.retry_allowed ? "safe" : "warning",
    },
    {
      key: "human_decision",
      label: "需要用户决策",
      value: formatBoolean(decision.requires_human_decision),
      tone: decision.requires_human_decision ? "warning" : "safe",
    },
  ];

  const safetyFields: RecoveryField[] = [
    {
      key: "api_response_exposed",
      label: "API 只读展示",
      value: decision.safety.api_response_exposed ? "已只读展示" : "未展示",
      tone: decision.safety.api_response_exposed ? "safe" : "neutral",
    },
    safeFlag("runs_git", "运行 Git", decision.safety.runs_git, "未运行 Git"),
    safeFlag(
      "runs_write_git",
      "Git 写操作",
      decision.safety.runs_write_git,
      "未执行 Git 写操作",
    ),
    safeFlag(
      "git_add",
      "加入待提交区",
      decision.safety.git_add_triggered,
      "未加入待提交区",
    ),
    safeFlag(
      "git_commit",
      "生成提交",
      decision.safety.git_commit_triggered,
      "未生成提交",
    ),
    safeFlag(
      "git_push",
      "推送远程",
      decision.safety.git_push_triggered,
      "未推送远程",
    ),
    safeFlag(
      "worker_dispatch",
      "自动派发 Worker",
      decision.safety.worker_dispatch_triggered,
      "未自动派发",
    ),
    safeFlag(
      "retry",
      "自动重试",
      decision.safety.retry_triggered,
      "未自动重试",
    ),
    safeFlag(
      "task_created",
      "创建任务",
      decision.safety.task_created,
      "未创建任务",
    ),
  ];

  return (
    <div
      data-testid="worker-failure-recovery-decision-card"
      className="mt-3 rounded-xl border border-amber-500/20 bg-amber-500/5 p-3"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="text-xs tracking-[0.2em] text-amber-200">
            失败回流建议
          </div>
          <p className="mt-2 text-sm leading-6 text-zinc-200">
            {decision.user_visible_summary_cn}
          </p>
          <p className="mt-2 text-xs leading-5 text-zinc-500">
            只读展示：当前不会自动重试、不会自动派发 Worker、不会创建任务，也不会执行 Git 写操作。
          </p>
        </div>
        <StatusBadge label="只读建议" tone="warning" />
      </div>

      <div
        className={`mt-3 grid gap-3 ${
          props.compact ? "sm:grid-cols-1" : "sm:grid-cols-2 xl:grid-cols-4"
        }`}
      >
        {summaryFields.map((field) => (
          <RecoveryInfo
            key={field.key}
            label={field.label}
            value={field.value}
            tone={field.tone}
          />
        ))}
      </div>

      {decision.human_decision_reason ? (
        <div className="mt-3 rounded-xl border border-[#333333] bg-[#1f1f1f] p-3">
          <div className="text-xs tracking-[0.2em] text-zinc-500">
            用户决策原因
          </div>
          <p className="mt-2 text-sm leading-6 text-zinc-300">
            {decision.human_decision_reason}
          </p>
        </div>
      ) : null}

      {decision.next_instruction_draft ? (
        <div className="mt-3 rounded-xl border border-[#333333] bg-[#1f1f1f] p-3">
          <div className="text-xs tracking-[0.2em] text-zinc-500">
            下一步指令草案（只读）
          </div>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-zinc-300">
            {decision.next_instruction_draft}
          </p>
        </div>
      ) : null}

      <div className="mt-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3">
        <div className="text-xs tracking-[0.2em] text-emerald-200">
          只读安全标记
        </div>
        <div
          className={`mt-3 grid gap-3 ${
            props.compact ? "sm:grid-cols-1" : "sm:grid-cols-2 xl:grid-cols-3"
          }`}
        >
          {safetyFields.map((field) => (
            <RecoveryInfo
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

function safeFlag(
  key: string,
  label: string,
  value: boolean,
  falseText: string,
): RecoveryField {
  return {
    key,
    label,
    value: value ? "安全标记异常" : falseText,
    tone: value ? "danger" : "safe",
  };
}

function RecoveryInfo(field: Omit<RecoveryField, "key">) {
  return (
    <div className={`rounded-xl border px-4 py-3 ${fieldToneClass(field.tone)}`}>
      <div className="text-xs tracking-[0.2em] opacity-70">{field.label}</div>
      <div className="mt-2 break-all text-sm font-medium">{field.value}</div>
    </div>
  );
}

function formatBoolean(value: boolean): string {
  return value ? "是" : "否";
}

function fieldToneClass(fieldTone: RecoveryField["tone"]): string {
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
