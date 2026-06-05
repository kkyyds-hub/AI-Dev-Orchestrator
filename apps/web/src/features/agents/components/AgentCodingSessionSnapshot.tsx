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

const WORKSPACE_TYPE_LABELS: Record<string, string> = {
  in_place: "项目原地工作区",
  worktree: "独立 Git 工作区",
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

const RUNTIME_LIFECYCLE_STATE_LABELS: Record<string, string> = {
  alive: "运行时已确认存活",
  exited: "运行时已确认退出",
  missing: "运行时句柄丢失",
  probe_failed: "运行时探测失败",
  spawning: "运行时启动中",
  unknown: "运行时未探测",
};

const RUNTIME_LIFECYCLE_STATE_TONES: Record<string, CodingTone> = {
  alive: "success",
  exited: "neutral",
  missing: "danger",
  probe_failed: "warning",
  spawning: "info",
  unknown: "neutral",
};

const SESSION_LIFECYCLE_STATE_LABELS: Record<string, string> = {
  done: "会话已完成",
  idle: "会话空闲",
  needs_input: "会话等待输入",
  not_started: "会话未开始",
  stuck: "会话卡住",
  terminated: "会话已终止",
  working: "会话处理中",
};

const SESSION_LIFECYCLE_STATE_TONES: Record<string, CodingTone> = {
  done: "success",
  idle: "neutral",
  needs_input: "warning",
  not_started: "neutral",
  stuck: "danger",
  terminated: "warning",
  working: "info",
};

const RUNTIME_LIFECYCLE_REASON_LABELS: Record<string, string> = {
  handle_not_assigned: "尚未分配运行时句柄",
  handle_recorded_no_probe: "已有运行时句柄记录，但本阶段未做探测",
  snapshot_only_no_runtime_probe: "仅基于会话记录生成快照，未做运行时探测",
};

const SESSION_LIFECYCLE_REASON_LABELS: Record<string, string> = {
  activity_blocked: "活动状态显示遇到阻塞",
  activity_exited: "活动状态显示本轮已结束",
  coding_completed: "编码会话已完成",
  coding_failed: "编码会话失败",
  coding_idle: "编码会话暂时空闲",
  coding_needs_input: "编码会话等待人工输入",
  coding_stuck: "编码会话需要关注",
  coding_terminated: "编码会话已停止",
  coding_working: "编码会话正在处理",
  session_created: "会话已创建，尚未进入执行",
};

const WORKSPACE_CLEAN_LABELS: Record<string, string> = {
  clean: "工作区干净",
  dirty: "存在未清理变更",
  unknown: "未检测清洁状态",
};

const WORKSPACE_CLEAN_TONES: Record<string, CodingTone> = {
  clean: "success",
  dirty: "warning",
  unknown: "neutral",
};

type RuntimeLifecycleSnapshot =
  AgentSessionSnapshot["runtime_lifecycle_snapshot"];

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

function resolveWorkspaceCleanState(value: boolean | null): "clean" | "dirty" | "unknown" {
  if (value === true) {
    return "clean";
  }
  if (value === false) {
    return "dirty";
  }
  return "unknown";
}

export function getAgentTypeLabel(value: string | null) {
  return labelFromMap(value, AGENT_TYPE_LABELS);
}

export function getRuntimeTypeLabel(value: string | null) {
  return labelFromMap(value, RUNTIME_TYPE_LABELS);
}

export function getWorkspaceTypeLabel(value: string | null) {
  return labelFromMap(value, WORKSPACE_TYPE_LABELS, "未绑定独立工作区");
}

export function getWorkspaceCleanLabel(value: boolean | null) {
  const state = resolveWorkspaceCleanState(value);
  return WORKSPACE_CLEAN_LABELS[state];
}

export function getWorkspaceCleanTone(value: boolean | null): CodingTone {
  const state = resolveWorkspaceCleanState(value);
  return WORKSPACE_CLEAN_TONES[state];
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

export function getRuntimeLifecycleStateLabel(value: string | null) {
  return labelFromMap(value, RUNTIME_LIFECYCLE_STATE_LABELS);
}

export function getRuntimeLifecycleStateTone(value: string | null): CodingTone {
  return toneFromMap(value, RUNTIME_LIFECYCLE_STATE_TONES);
}

export function getSessionLifecycleStateLabel(value: string | null) {
  return labelFromMap(value, SESSION_LIFECYCLE_STATE_LABELS);
}

export function getSessionLifecycleStateTone(value: string | null): CodingTone {
  return toneFromMap(value, SESSION_LIFECYCLE_STATE_TONES);
}

function getRuntimeLifecycleReasonLabel(value: string | null) {
  return labelFromMap(value, RUNTIME_LIFECYCLE_REASON_LABELS);
}

function getSessionLifecycleReasonLabel(value: string | null) {
  return labelFromMap(value, SESSION_LIFECYCLE_REASON_LABELS);
}

function formatBooleanLabel(value: boolean) {
  return value ? "是" : "否";
}

function buildRuntimeLifecycleSummary(snapshot: RuntimeLifecycleSnapshot) {
  return [
    `运行时轴：${getRuntimeLifecycleStateLabel(snapshot.state)}。`,
    `运行时原因：${getRuntimeLifecycleReasonLabel(snapshot.reason)}。`,
    `会话派生状态：${getSessionLifecycleStateLabel(
      snapshot.session_lifecycle_state,
    )}。`,
    `会话派生原因：${getSessionLifecycleReasonLabel(
      snapshot.session_lifecycle_reason,
    )}。`,
    "该快照只读取已保存的会话字段，不会触发模拟启动、真实运行时或运行时探测。",
  ].join("");
}

export function AgentCodingSessionSnapshot(props: {
  selectedSession: AgentSessionSnapshot | null;
}) {
  const session = props.selectedSession;

  if (!session) {
    return (
      <section className="rounded-3xl border border-dashed border-[#333333] bg-slate-950/20 p-4 text-sm leading-6 text-slate-400">
        请选择一个已有会话查看只读运行状态；本区域不会创建独立工作区、启动 AI 运行时或触发自动编码。
      </section>
    );
  }

  const branchLabel = session.branch_name ?? "暂未分配独立分支";
  const handleLabel = session.runtime_handle_id ?? "暂无后台通道编号";
  const workspacePathLabel = session.workspace_path ?? "暂未绑定独立工作区路径";
  const runtimeSnapshot = session.runtime_lifecycle_snapshot;
  const runtimeLifecycleSummary = buildRuntimeLifecycleSummary(runtimeSnapshot);

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
          <StatusBadge
            label={getWorkspaceCleanLabel(session.workspace_clean)}
            tone={getWorkspaceCleanTone(session.workspace_clean)}
          />
          <StatusBadge
            label={getRuntimeLifecycleStateLabel(runtimeSnapshot.state)}
            tone={getRuntimeLifecycleStateTone(runtimeSnapshot.state)}
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
        <CompactField
          label="P3-C1 运行时轴状态"
          value={getRuntimeLifecycleStateLabel(runtimeSnapshot.state)}
          title={runtimeLifecycleSummary}
        />
        <CompactField
          label="运行时轴原因"
          value={getRuntimeLifecycleReasonLabel(runtimeSnapshot.reason)}
          title={runtimeLifecycleSummary}
        />
        <CompactField
          label="会话派生状态"
          value={getSessionLifecycleStateLabel(
            runtimeSnapshot.session_lifecycle_state,
          )}
          title={runtimeLifecycleSummary}
        />
        <CompactField
          label="会话派生原因"
          value={getSessionLifecycleReasonLabel(
            runtimeSnapshot.session_lifecycle_reason,
          )}
          title={runtimeLifecycleSummary}
        />
        <CompactField label="后台通道" value={handleLabel} title={session.runtime_handle_id} />
        <CompactField label="分支" value={branchLabel} title={session.branch_name} />
        <CompactField
          label="工作区类型"
          value={getWorkspaceTypeLabel(session.workspace_type)}
          title={session.workspace_type}
        />
        <CompactField
          label="工作区路径"
          value={workspacePathLabel}
          title={session.workspace_path}
        />
      </div>

      {session.last_workspace_error ? (
        <p
          className="mt-3 rounded-2xl border border-rose-900/60 bg-rose-950/20 px-3 py-2 text-xs leading-5 text-rose-200"
          title={session.last_workspace_error}
        >
          最近工作区错误：{session.last_workspace_error}
        </p>
      ) : null}

      <p className="mt-3 rounded-2xl border border-[#333333] bg-black/20 px-3 py-2 text-xs leading-5 text-slate-500">
        当前阶段只读展示智能体会话与时间线已有数据：可看到处理者、后台通道、任务进度、活动情况、工作区绑定、分支名和工作区审计错误。
        P3-C1 的运行时轴只展示已有证据；未启动或未探测时不会把会话处理状态误标为运行时存活。这里不会创建或清理独立工作区，也不表示已经进入 AI 运行时、自动编码、提交、推送或创建 PR。
      </p>

      <div className="mt-3 rounded-2xl border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-xs leading-5 text-emerald-100">
        <div className="font-medium">P3-C1 智能体会话运行时生命周期快照</div>
        <div className="mt-1 text-emerald-100/80">
          {runtimeLifecycleSummary}
        </div>
        <div className="mt-2 grid gap-1 sm:grid-cols-2">
          <span>运行时轴状态：{getRuntimeLifecycleStateLabel(runtimeSnapshot.state)}</span>
          <span>
            会话派生状态：
            {getSessionLifecycleStateLabel(runtimeSnapshot.session_lifecycle_state)}
          </span>
          <span>
            模拟启动已触发：
            {formatBooleanLabel(runtimeSnapshot.fake_launch_started)}
          </span>
          <span>
            真实运行时已启动：
            {formatBooleanLabel(runtimeSnapshot.real_runtime_started)}
          </span>
          <span>
            运行时探测已启动：
            {formatBooleanLabel(runtimeSnapshot.runtime_probe_started)}
          </span>
          <span>
            执行开关已开启：
            {formatBooleanLabel(runtimeSnapshot.execution_enabled)}
          </span>
        </div>
      </div>
    </section>
  );
}
