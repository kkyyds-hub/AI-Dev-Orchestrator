import { useEffect, useMemo, useState } from "react";

import { StatusBadge } from "../../../components/StatusBadge";
import { AgentSessionList } from "../components/AgentSessionList";
import { AgentTimelineList } from "../components/AgentTimelineList";
import { BossInterventionForm } from "../components/BossInterventionForm";
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
    return (
      <section
        id="agent-thread-control-surface"
        data-testid="agent-thread-control-surface"
        className="space-y-4 rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30"
      >
        <h2 className="text-2xl font-semibold text-slate-50">Day12 Agent Thread Control Surface</h2>
        <p className="text-sm text-slate-400">
          Select one project first, then Day12 session list / message timeline / intervention panel will
          consume Day11 agent-thread contracts.
        </p>
      </section>
    );
  }

  return (
    <section
      id="agent-thread-control-surface"
      data-testid="agent-thread-control-surface"
      className="space-y-5 rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30"
    >
      <header className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-cyan-300">Day12 Agent Thread</p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-50">
              Message Timeline and Boss Intervention Entry
            </h2>
            <p className="mt-2 text-sm text-slate-300">project: {props.projectName ?? props.projectId}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge label={`sessions ${sessions.length}`} tone="info" />
            <StatusBadge label={`timeline ${timelineMessages.length}`} tone="success" />
            <StatusBadge label={`interventions ${interventionItems.length}`} tone="warning" />
            <button
              type="button"
              data-testid="agent-thread-refresh-btn"
              onClick={() => {
                void Promise.all([
                  sessionsQuery.refetch(),
                  timelineQuery.refetch(),
                  interventionsQuery.refetch(),
                ]);
              }}
              className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-3 py-1.5 text-xs text-cyan-100 transition hover:bg-cyan-500/20"
            >
              Refresh
            </button>
          </div>
        </div>
      </header>

      {sessionsQuery.isLoading && !sessionsQuery.data ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-6 text-sm text-slate-400">
          Loading Day11 sessions contract...
        </div>
      ) : null}

      {sessionsQuery.isError ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-6 text-sm text-rose-100">
          Failed to load sessions: {sessionsQuery.error.message}
        </div>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[minmax(280px,0.9fr)_minmax(0,1.1fr)]">
        <section className="space-y-4">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
            <h4 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">
              Session Selector
            </h4>
            <p className="mt-2 text-xs text-slate-400">
              Consumes GET /agent-threads/projects/{props.projectId}/sessions
            </p>
            <div className="mt-3">
              <AgentSessionList
                sessions={sessions}
                selectedSessionId={selectedSessionId}
                onSelectSession={setSelectedSessionId}
              />
            </div>
          </div>

          <BossInterventionForm
            projectId={props.projectId}
            selectedSession={selectedSession}
            interventionCount={interventionItems.length}
          />
        </section>

        <section className="space-y-4">
          {timelineQuery.isError ? (
            <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-6 text-sm text-rose-100">
              Failed to load timeline: {timelineQuery.error.message}
            </div>
          ) : null}

          {interventionsQuery.isError ? (
            <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-6 text-sm text-rose-100">
              Failed to load interventions: {interventionsQuery.error.message}
            </div>
          ) : null}

          <AgentTimelineList
            title="Message Timeline"
            testId="agent-thread-timeline-list"
            messages={timelineMessages}
            emptyText="No timeline messages returned for current filter."
          />

          <AgentTimelineList
            title="Intervention Feed"
            testId="agent-thread-intervention-list"
            messages={interventionItems}
            emptyText="No intervention/note-event messages returned for current filter."
          />
        </section>
      </section>
    </section>
  );
}
