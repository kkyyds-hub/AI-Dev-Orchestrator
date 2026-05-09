import { AgentSessionList } from "./AgentSessionList";
import type { AgentSessionSnapshot } from "../types";

export function AgentThreadSessionSelectorPanel(props: {
  projectId: string;
  sessions: AgentSessionSnapshot[];
  selectedSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
}) {
  return (
    <div className="min-h-0 border-b border-[#333333] pb-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h4 className="text-sm font-medium text-slate-100">
            会话选择
          </h4>
          <p className="mt-2 text-xs leading-5 text-slate-400">
            消费接口 GET /agent-threads/projects/{props.projectId}/sessions
          </p>
        </div>
        <span className="text-xs text-slate-500">
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
