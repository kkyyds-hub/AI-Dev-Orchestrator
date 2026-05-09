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
    <section className="grid min-w-0 gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
      <section className="min-w-0 space-y-5 xl:border-r xl:border-[#333333] xl:pr-6">
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

      <section className="min-w-0 space-y-6">
        {props.timelineErrorMessage ? (
          <AgentThreadTimelineErrorState message={props.timelineErrorMessage} />
        ) : null}

        {props.interventionsErrorMessage ? (
          <AgentThreadInterventionsErrorState message={props.interventionsErrorMessage} />
        ) : null}

        <AgentTimelineList
          title="消息时间线"
          description="按序查看当前会话的消息摘要、事件类型和状态流转。"
          testId="agent-thread-timeline-list"
          messages={props.timelineMessages}
          emptyText="当前筛选条件下没有返回时间线消息。"
        />

        <AgentTimelineList
          title="介入动态"
          description="聚合人工介入与 note-event 相关消息，便于复盘操作结果。"
          testId="agent-thread-intervention-list"
          messages={props.interventionItems}
          emptyText="当前筛选条件下没有返回介入或 note-event 消息。"
        />
      </section>
    </section>
  );
}
