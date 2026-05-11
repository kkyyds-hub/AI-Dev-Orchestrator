import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import type { AgentSessionSnapshot } from "../types";

type AgentSessionListProps = {
  sessions: AgentSessionSnapshot[];
  selectedSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
};

const STATUS_LABELS: Record<string, string> = {
  blocked: "已阻塞",
  completed: "已完成",
  failed: "失败",
  finalized: "已归档",
  in_progress: "进行中",
  pending: "待处理",
  review_passed: "评审通过",
  running: "运行中",
};

function shortId(value: string | null | undefined) {
  if (!value) {
    return "无";
  }
  return value.length > 12 ? `${value.slice(0, 8)}…${value.slice(-4)}` : value;
}

function formatStatusLabel(value: string) {
  return STATUS_LABELS[value] ?? value;
}

export function AgentSessionList(props: AgentSessionListProps) {
  if (!props.sessions.length) {
    return (
      <div className="border-y border-dashed border-[#333333] px-1 py-5 text-sm leading-6 text-slate-400">
        当前项目暂无智能体会话。
      </div>
    );
  }

  return (
    <div className="max-h-[420px] divide-y divide-[#333333] overflow-y-auto overscroll-contain pr-2 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-slate-700/60 xl:max-h-[calc(100vh-28rem)]" data-testid="agent-thread-session-list">
      {props.sessions.map((session) => {
        const selected = session.session_id === props.selectedSessionId;
        return (
          <button
            key={session.session_id}
            type="button"
            data-testid={`agent-thread-session-item-${session.session_id}`}
            onClick={() => props.onSelectSession(session.session_id)}
            className={`group w-full border-l-2 py-3 pl-3 pr-2 text-left transition focus:outline-none ${
              selected
                ? "border-slate-200 bg-slate-900/20"
                : "border-transparent hover:bg-slate-900/15"
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-[11px] text-slate-500">任务</div>
                <div
                  className="mt-0.5 truncate font-mono text-sm font-medium text-slate-100"
                  title={session.task_id}
                >
                  {shortId(session.task_id)}
                </div>
              </div>
              {selected ? (
                <span className="shrink-0 text-xs text-slate-400">当前</span>
              ) : null}
            </div>

            <div className="mt-2 flex flex-wrap gap-1.5">
              <StatusBadge label={formatStatusLabel(session.session_status)} tone="info" />
              <StatusBadge label={formatStatusLabel(session.review_status)} tone="warning" />
              <StatusBadge label={formatStatusLabel(session.current_phase)} tone="neutral" />
            </div>

            <div className="mt-2 space-y-1 text-xs text-slate-500">
              <div className="flex min-w-0 gap-1.5">
                <span className="shrink-0">运行：</span>
                <span className="truncate font-mono" title={session.run_id}>
                  {shortId(session.run_id)}
                </span>
              </div>
              <div>开始：{formatDateTime(session.started_at)}</div>
              <div>
                上下文：{session.context_rehydrated ? "已恢复" : "未恢复"}
                {session.context_checkpoint_id ? (
                  <span title={session.context_checkpoint_id}>
                    {" "}
                    / 检查点 {shortId(session.context_checkpoint_id)}
                  </span>
                ) : null}
              </div>
            </div>

            {session.summary ? (
              <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-400" title={session.summary}>
                {session.summary}
              </p>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
