import { useEffect, useMemo, useState } from "react";

import { AgentThreadControlEmptyState } from "../components/AgentThreadControlEmptyState";
import { AgentThreadControlGrid } from "../components/AgentThreadControlGrid";
import { AgentThreadControlHeader } from "../components/AgentThreadControlHeader";
import {
  AgentThreadSessionsErrorState,
  AgentThreadSessionsLoadingState,
} from "../components/AgentThreadControlQueryState";
import {
  useAgentThreadInterventions,
  useAgentThreadSessions,
  useAgentThreadTimeline,
} from "../hooks";

type AgentThreadControlSectionProps = {
  projectId: string | null;
  projectName: string | null;
};

export function AgentThreadControlSection(props: AgentThreadControlSectionProps) {
  const sessionsQuery = useAgentThreadSessions(props.projectId);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const timelineQuery = useAgentThreadTimeline({
    projectId: props.projectId,
    sessionId: selectedSessionId,
  });
  const interventionsQuery = useAgentThreadInterventions({
    projectId: props.projectId,
    sessionId: selectedSessionId,
  });

  const sessions = sessionsQuery.data ?? [];
  const selectedSession = useMemo(
    () => sessions.find((session) => session.session_id === selectedSessionId) ?? null,
    [sessions, selectedSessionId],
  );
  const timelineMessages = timelineQuery.data?.messages ?? [];
  const interventionItems = interventionsQuery.data?.items ?? [];

  useEffect(() => {
    if (!sessions.length) {
      if (selectedSessionId !== null) {
        setSelectedSessionId(null);
      }
      return;
    }

    const hasSelected = sessions.some((session) => session.session_id === selectedSessionId);
    if (!selectedSessionId || !hasSelected) {
      setSelectedSessionId(sessions[0].session_id);
    }
  }, [sessions, selectedSessionId]);

  if (!props.projectId) {
    return <AgentThreadControlEmptyState />;
  }

  const projectId = props.projectId;

  return (
    <section
      id="agent-thread-control-surface"
      data-testid="agent-thread-control-surface"
      className="space-y-4"
    >
      <AgentThreadControlHeader
        projectLabel={props.projectName ?? projectId}
        sessionCount={sessions.length}
        timelineCount={timelineMessages.length}
        interventionCount={interventionItems.length}
        onRefresh={() => {
          void Promise.all([
            sessionsQuery.refetch(),
            timelineQuery.refetch(),
            interventionsQuery.refetch(),
          ]);
        }}
      />

      {sessionsQuery.isLoading && !sessionsQuery.data ? (
        <AgentThreadSessionsLoadingState />
      ) : null}

      {sessionsQuery.isError ? (
        <AgentThreadSessionsErrorState message={sessionsQuery.error.message} />
      ) : null}

      <AgentThreadControlGrid
        projectId={projectId}
        sessions={sessions}
        selectedSessionId={selectedSessionId}
        selectedSession={selectedSession}
        timelineMessages={timelineMessages}
        interventionItems={interventionItems}
        timelineErrorMessage={
          timelineQuery.isError ? timelineQuery.error.message : null
        }
        interventionsErrorMessage={
          interventionsQuery.isError ? interventionsQuery.error.message : null
        }
        onSelectSession={setSelectedSessionId}
      />
    </section>
  );
}
