import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import type { AgentSessionSnapshot } from "../types";

type AgentSessionListProps = {
  sessions: AgentSessionSnapshot[];
  selectedSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
};

export function AgentSessionList(props: AgentSessionListProps) {
  if (!props.sessions.length) {
    return (
      <div className="border-y border-dashed border-[#333333] px-1 py-5 text-sm leading-6 text-slate-400">
        当前项目暂无智能体会话。
      </div>
    );
  }

  return (
    <div className="divide-y divide-[#333333]" data-testid="agent-thread-session-list">
      {props.sessions.map((session) => {
        const selected = session.session_id === props.selectedSessionId;
        return (
          <button
            key={session.session_id}
            type="button"
            data-testid={`agent-thread-session-item-${session.session_id}`}
            onClick={() => props.onSelectSession(session.session_id)}
            className={`group w-full px-1 py-4 text-left transition focus:outline-none ${
              selected
                ? "bg-slate-900/35"
                : "hover:bg-slate-900/20"
            }`}
          >
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium text-slate-100">
                    任务 {session.task_id}
                  </span>
                  {selected ? (
                    <span className="text-xs text-slate-400">当前会话</span>
                  ) : null}
                </div>
                <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500">
                  <span>运行：{session.run_id}</span>
                  <span>开始：{formatDateTime(session.started_at)}</span>
                </div>
              </div>
              <div className="flex shrink-0 flex-wrap items-center gap-2">
                <StatusBadge label={session.session_status} tone="info" />
                <StatusBadge label={session.review_status} tone="warning" />
                <StatusBadge label={session.current_phase} tone="neutral" />
              </div>
            </div>
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500">
              <span>上下文：{session.context_rehydrated ? "已恢复" : "未恢复"}</span>
              <span>检查点：{session.context_checkpoint_id ?? "无"}</span>
            </div>
            {session.summary ? (
              <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-400">
                {session.summary}
              </p>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
