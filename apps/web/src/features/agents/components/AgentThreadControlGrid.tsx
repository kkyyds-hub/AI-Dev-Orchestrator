import { AgentTimelineList } from "./AgentTimelineList";
import { BossInterventionForm } from "./BossInterventionForm";
import type { AgentSessionSnapshot, AgentTimelineMessage } from "../types";
import {
  AgentThreadInterventionsErrorState,
  AgentThreadTimelineErrorState,
} from "./AgentThreadControlQueryState";
import { AgentThreadSessionSelectorPanel } from "./AgentThreadSessionSelectorPanel";

export function AgentThreadControlGrid(props: {
  projectId: string;
  sessions: AgentSessionSnapshot[];
  selectedSessionId: string | null;
  selectedSession: AgentSessionSnapshot | null;
  timelineMessages: AgentTimelineMessage[];
  interventionItems: AgentTimelineMessage[];
  timelineErrorMessage: string | null;
  interventionsErrorMessage: string | null;
  onSelectSession: (sessionId: string) => void;
}) {
  return (
    <section className="grid gap-4 xl:grid-cols-[minmax(280px,0.9fr)_minmax(0,1.1fr)]">
      <section className="space-y-4">
        <AgentThreadSessionSelectorPanel
          projectId={props.projectId}
          sessions={props.sessions}
          selectedSessionId={props.selectedSessionId}
          onSelectSession={props.onSelectSession}
        />

        <BossInterventionForm
          projectId={props.projectId}
          selectedSession={props.selectedSession}
          interventionCount={props.interventionItems.length}
        />
      </section>

      <section className="space-y-4">
        {props.timelineErrorMessage ? (
          <AgentThreadTimelineErrorState message={props.timelineErrorMessage} />
        ) : null}

        {props.interventionsErrorMessage ? (
          <AgentThreadInterventionsErrorState message={props.interventionsErrorMessage} />
        ) : null}

        <AgentTimelineList
          title="消息时间线"
          testId="agent-thread-timeline-list"
          messages={props.timelineMessages}
          emptyText="当前筛选条件下没有返回时间线消息。"
        />

        <AgentTimelineList
          title="介入动态"
          testId="agent-thread-intervention-list"
          messages={props.interventionItems}
          emptyText="当前筛选条件下没有返回介入或 note-event 消息。"
        />
      </section>
    </section>
  );
}
