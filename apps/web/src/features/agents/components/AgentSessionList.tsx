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
      <div className="rounded-xl border border-dashed border-[#3a3a3a] px-4 py-6 text-sm leading-6 text-slate-400">
        当前项目暂无智能体会话。
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="agent-thread-session-list">
      {props.sessions.map((session) => {
        const selected = session.session_id === props.selectedSessionId;
        return (
          <button
            key={session.session_id}
            type="button"
            data-testid={`agent-thread-session-item-${session.session_id}`}
            onClick={() => props.onSelectSession(session.session_id)}
            className={`group w-full rounded-xl border p-3 text-left transition focus:outline-none focus:ring-2 focus:ring-slate-500/30 sm:p-4 ${
              selected
                ? "border-slate-500/80 bg-slate-900/55"
                : "border-[#333333] bg-transparent hover:border-slate-600 hover:bg-slate-900/35"
            }`}
          >
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge label={`会话状态 ${session.session_status}`} tone="info" />
              <StatusBadge label={`评审状态 ${session.review_status}`} tone="warning" />
              <StatusBadge label={`阶段 ${session.current_phase}`} tone="neutral" />
            </div>
            <div className="mt-3 grid gap-2 text-xs text-slate-400 sm:grid-cols-2">
              <div className="min-w-0">
                <span className="text-slate-500">任务：</span>
                <span className="break-all text-slate-200">{session.task_id}</span>
              </div>
              <div className="min-w-0">
                <span className="text-slate-500">运行：</span>
                <span className="break-all text-slate-300">{session.run_id}</span>
              </div>
              <div>
                <span className="text-slate-500">开始：</span>
                <span className="text-slate-300">{formatDateTime(session.started_at)}</span>
              </div>
              <div>
                <span className="text-slate-500">上下文：</span>
                <span className="text-slate-300">
                  {session.context_rehydrated ? "已恢复" : "未恢复"}
                </span>
              </div>
            </div>
            <div className="mt-2 text-xs text-slate-500">
              检查点：{session.context_checkpoint_id ?? "无"}
            </div>
            {session.summary ? (
              <div className="mt-3 rounded-lg border border-[#333333] bg-slate-950/35 px-3 py-2 text-xs leading-5 text-slate-300">
                {session.summary}
              </div>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
