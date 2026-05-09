import { AgentSessionList } from "./AgentSessionList";
import type { AgentSessionSnapshot } from "../types";

export function AgentThreadSessionSelectorPanel(props: {
  projectId: string;
  sessions: AgentSessionSnapshot[];
  selectedSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
}) {
  return (
    <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-4 shadow-lg shadow-slate-950/15 sm:p-5">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h4 className="text-sm font-semibold tracking-[0.16em] text-slate-200">
            会话选择
          </h4>
          <p className="mt-2 text-xs leading-5 text-slate-400">
            消费接口 GET /agent-threads/projects/{props.projectId}/sessions
          </p>
        </div>
        <span className="rounded-full border border-slate-700/70 px-2.5 py-1 text-xs text-slate-300">
          {props.sessions.length} 个会话
        </span>
      </div>
      <div className="mt-4">
        <AgentSessionList
          sessions={props.sessions}
          selectedSessionId={props.selectedSessionId}
          onSelectSession={props.onSelectSession}
        />
      </div>
    </div>
  );
}