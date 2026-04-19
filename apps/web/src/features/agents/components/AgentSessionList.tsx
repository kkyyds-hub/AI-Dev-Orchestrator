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
      <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 px-4 py-5 text-sm text-slate-400">
        No Day11 agent sessions were returned for this project.
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
            className={`w-full rounded-2xl border p-4 text-left transition ${
              selected
                ? "border-cyan-400/40 bg-cyan-500/10"
                : "border-slate-800 bg-slate-900/60 hover:border-slate-700"
            }`}
          >
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge label={`session ${session.session_status}`} tone="info" />
              <StatusBadge label={`review ${session.review_status}`} tone="warning" />
              <StatusBadge label={`phase ${session.current_phase}`} tone="neutral" />
            </div>
            <div className="mt-2 text-sm text-slate-100">task: {session.task_id}</div>
            <div className="mt-1 text-xs text-slate-400">run: {session.run_id}</div>
            <div className="mt-1 text-xs text-slate-400">
              started: {formatDateTime(session.started_at)}
            </div>
            <div className="mt-1 text-xs text-slate-400">
              checkpoint: {session.context_checkpoint_id ?? "none"}; rehydrated: {String(session.context_rehydrated)}
            </div>
            {session.summary ? (
              <div className="mt-2 rounded-xl border border-slate-800 bg-slate-950/70 px-3 py-2 text-xs text-slate-300">
                {session.summary}
              </div>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}