import { StatusBadge } from "../../../components/StatusBadge";
import type { AgentSessionSnapshot } from "../types";

type CodingTone = "neutral" | "info" | "success" | "warning" | "danger";

const AGENT_TYPE_LABELS: Record<string, string> = {
  claude_code: "Claude Code",
  codex: "Codex",
  opencode: "OpenCode",
  openai_provider: "OpenAI Provider",
  shell: "Shell",
  simulate: "模拟执行",
};

const RUNTIME_TYPE_LABELS: Record<string, string> = {
  docker: "Docker",
  process: "独立进程",
  subprocess: "子进程",
  tmux: "tmux",
};

const CODING_STATUS_LABELS: Record<string, string> = {
  completed: "编码完成",
  failed: "编码失败",
  idle: "空闲",
  needs_input: "等待输入",
  spawning: "启动中",
  stuck: "疑似卡住",
  terminated: "已终止",
  working: "编码中",
};

const ACTIVITY_STATE_LABELS: Record<string, string> = {
  active: "有活动",
  blocked: "阻塞",
  exited: "已退出",
  idle: "空闲",
  ready: "就绪",
  waiting_input: "等待输入",
};

const CODING_STATUS_TONES: Record<string, CodingTone> = {
  completed: "success",
  failed: "danger",
  idle: "neutral",
  needs_input: "warning",
  spawning: "info",
  stuck: "danger",
  terminated: "warning",
  working: "info",
};

const ACTIVITY_STATE_TONES: Record<string, CodingTone> = {
  active: "info",
  blocked: "danger",
  exited: "neutral",
  idle: "neutral",
  ready: "success",
  waiting_input: "warning",
};

function labelFromMap(
  value: string | null,
  labels: Record<string, string>,
  fallback = "未记录",
) {
  if (!value) {
    return fallback;
  }
  return labels[value] ?? value;
}

function toneFromMap(value: string | null, tones: Record<string, CodingTone>) {
  if (!value) {
    return "neutral";
  }
  return tones[value] ?? "neutral";
}

function CompactField(props: {
  label: string;
  value: string;
  title?: string | null;
}) {
  return (
    <div className="rounded-2xl border border-[#333333] bg-slate-950/30 px-3 py-2">
      <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
        {props.label}
      </div>
      <div
        className="mt-1 truncate text-sm font-medium text-slate-100"
        title={props.title ?? props.value}
      >
        {props.value}
      </div>
    </div>
  );
}

export function getAgentTypeLabel(value: string | null) {
  return labelFromMap(value, AGENT_TYPE_LABELS);
}

export function getRuntimeTypeLabel(value: string | null) {
  return labelFromMap(value, RUNTIME_TYPE_LABELS);
}

export function getCodingStatusLabel(value: string | null) {
  return labelFromMap(value, CODING_STATUS_LABELS);
}

export function getActivityStateLabel(value: string | null) {
  return labelFromMap(value, ACTIVITY_STATE_LABELS);
}

export function getCodingStatusTone(value: string | null): CodingTone {
  return toneFromMap(value, CODING_STATUS_TONES);
}

export function getActivityStateTone(value: string | null): CodingTone {
  return toneFromMap(value, ACTIVITY_STATE_TONES);
}

export function AgentCodingSessionSnapshot(props: {
  selectedSession: AgentSessionSnapshot | null;
}) {
  const session = props.selectedSession;

  if (!session) {
    return (
      <section className="rounded-3xl border border-dashed border-[#333333] bg-slate-950/20 p-4 text-sm leading-6 text-slate-400">
        请选择一个会话查看 Coding Session 运行快照。
      </section>
    );
  }

  const branchLabel = session.branch_name ?? "未创建独立分支";
  const handleLabel = session.runtime_handle_id ?? "未记录运行句柄";

  return (
    <section
      className="rounded-3xl border border-[#333333] bg-slate-950/30 p-4"
      data-testid="agent-coding-session-snapshot"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h4 className="text-sm font-semibold text-slate-100">
            Coding Session 运行快照
          </h4>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            只读展示当前会话的执行身份、运行载体与活动状态；这里不会启动终端、创建分支或触发 PR。
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-1.5">
          <StatusBadge
            label={getCodingStatusLabel(session.coding_status)}
            tone={getCodingStatusTone(session.coding_status)}
          />
          <StatusBadge
            label={getActivityStateLabel(session.activity_state)}
            tone={getActivityStateTone(session.activity_state)}
          />
        </div>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        <CompactField
          label="智能体"
          value={getAgentTypeLabel(session.agent_type)}
          title={session.agent_type}
        />
        <CompactField
          label="运行载体"
          value={getRuntimeTypeLabel(session.runtime_type)}
          title={session.runtime_type}
        />
        <CompactField label="运行句柄" value={handleLabel} title={session.runtime_handle_id} />
        <CompactField label="分支" value={branchLabel} title={session.branch_name} />
      </div>

      <p className="mt-3 rounded-2xl border border-[#333333] bg-black/20 px-3 py-2 text-xs leading-5 text-slate-500">
        P0 只提供可观测字段：智能体类型、运行载体、运行句柄、编码状态、活动状态、分支名。
        工作区、PR、CI 与 Review 状态仍属于后续阶段。
      </p>
    </section>
  );
}
