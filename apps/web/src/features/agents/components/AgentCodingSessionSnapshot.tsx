import { StatusBadge } from "../../../components/StatusBadge";
import type { AgentSessionSnapshot } from "../types";

type CodingTone = "neutral" | "info" | "success" | "warning" | "danger";

const AGENT_TYPE_LABELS: Record<string, string> = {
  claude_code: "Claude Code",
  codex: "Codex",
  opencode: "OpenCode",
  openai_provider: "在线模型执行",
  shell: "本地命令执行",
  simulate: "模拟任务执行",
};

const RUNTIME_TYPE_LABELS: Record<string, string> = {
  docker: "容器环境",
  process: "本地进程",
  subprocess: "后台执行通道",
  tmux: "终端会话",
};

const CODING_STATUS_LABELS: Record<string, string> = {
  completed: "任务已完成",
  failed: "任务失败",
  idle: "暂时空闲",
  needs_input: "等待人工输入",
  spawning: "正在准备",
  stuck: "需要关注",
  terminated: "已停止",
  working: "正在处理",
};

const ACTIVITY_STATE_LABELS: Record<string, string> = {
  active: "有新动作",
  blocked: "遇到阻塞",
  exited: "本轮已结束",
  idle: "暂无动作",
  ready: "可继续",
  waiting_input: "等你回复",
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
        请选择一个会话查看运行状态。
      </section>
    );
  }

  const branchLabel = session.branch_name ?? "暂未分配独立分支";
  const handleLabel = session.runtime_handle_id ?? "暂无后台通道编号";

  return (
    <section
      className="rounded-3xl border border-[#333333] bg-slate-950/30 p-4"
      data-testid="agent-coding-session-snapshot"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h4 className="text-sm font-semibold text-slate-100">
            会话运行状态
          </h4>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            只读展示这轮任务是谁在处理、处理到哪一步，以及当前是否还在活动；这里不会启动终端、创建分支或发起交付。
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
        <CompactField label="后台通道" value={handleLabel} title={session.runtime_handle_id} />
        <CompactField label="分支" value={branchLabel} title={session.branch_name} />
      </div>

      <p className="mt-3 rounded-2xl border border-[#333333] bg-black/20 px-3 py-2 text-xs leading-5 text-slate-500">
        当前阶段只做运行状态可视化：可看到处理者、后台通道、任务进度、活动情况和分支占位。
        独立工作区、交付请求、自动检查和评审结果仍将在后续阶段接入。
      </p>
    </section>
  );
}
