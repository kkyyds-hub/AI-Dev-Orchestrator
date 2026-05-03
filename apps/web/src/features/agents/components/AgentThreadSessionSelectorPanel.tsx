import { AgentSessionList } from "./AgentSessionList";
import type { AgentSessionSnapshot } from "../types";

export function AgentThreadSessionSelectorPanel(props: {
  projectId: string;
  sessions: AgentSessionSnapshot[];
  selectedSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
}) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <h4 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">
        会话选择器
      </h4>
      <p className="mt-2 text-xs text-slate-400">
        消费接口 GET /agent-threads/projects/{props.projectId}/sessions
      </p>
      <div className="mt-3">
        <AgentSessionList
          sessions={props.sessions}
          selectedSessionId={props.selectedSessionId}
          onSelectSession={props.onSelectSession}
        />
      </div>
    </div>
  );
}
