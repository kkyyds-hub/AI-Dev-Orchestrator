import { useEffect, useMemo, useState } from "react";

import { ChangeReworkPanel } from "../approvals/ChangeReworkPanel";
import { ProjectTimelineEmptyState } from "./components/ProjectTimelineEmptyState";
import { ProjectTimelineEventList } from "./components/ProjectTimelineEventList";
import { ProjectTimelineFilterPanel } from "./components/ProjectTimelineFilterPanel";
import { ProjectTimelineHeader } from "./components/ProjectTimelineHeader";
import {
  ProjectTimelineErrorState,
  ProjectTimelineLoadingState,
} from "./components/ProjectTimelineQueryState";
import { useProjectTimeline } from "./hooks";
import type { ProjectTimelineEventType } from "./types";

type ProjectTimelinePageProps = {
  projectId: string | null;
  projectName: string | null;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
  onNavigateToDeliverable?: (input: {
    projectId: string;
    deliverableId: string;
  }) => void;
  onNavigateToApproval?: (input: {
    projectId: string;
    approvalId: string;
  }) => void;
};

export function ProjectTimelinePage(props: ProjectTimelinePageProps) {
  const timelineQuery = useProjectTimeline(props.projectId);
  const [activeFilters, setActiveFilters] = useState<ProjectTimelineEventType[]>([]);

  useEffect(() => {
    setActiveFilters([]);
  }, [props.projectId]);

  const visibleEvents = useMemo(() => {
    const events = timelineQuery.data?.events ?? [];
    if (!activeFilters.length) {
      return events;
    }

    return events.filter((event) => activeFilters.includes(event.event_type));
  }, [activeFilters, timelineQuery.data?.events]);

  const toggleFilter = (eventType: ProjectTimelineEventType) => {
    setActiveFilters((previous) =>
      previous.includes(eventType)
        ? previous.filter((item) => item !== eventType)
        : [...previous, eventType],
    );
  };

  if (!props.projectId) {
    return <ProjectTimelineEmptyState />;
  }

  const projectId = props.projectId;

  return (
    <section className="space-y-6 border-b border-[#333333] pb-7">
      <ProjectTimelineHeader
        projectName={props.projectName}
        totalEvents={timelineQuery.data?.total_events ?? 0}
        visibleEventCount={visibleEvents.length}
      />

      {timelineQuery.isLoading && !timelineQuery.data ? (
        <ProjectTimelineLoadingState />
      ) : timelineQuery.isError ? (
        <ProjectTimelineErrorState message={timelineQuery.error.message} />
      ) : (
        <>
          <ChangeReworkPanel
            projectId={projectId}
            projectName={props.projectName}
            onNavigateToApproval={props.onNavigateToApproval}
            onNavigateToDeliverable={props.onNavigateToDeliverable}
          />

          <ProjectTimelineFilterPanel
            generatedAt={timelineQuery.data?.generated_at ?? null}
            eventTypeCounts={timelineQuery.data?.event_type_counts ?? []}
            activeFilters={activeFilters}
            onClearFilters={() => setActiveFilters([])}
            onToggleFilter={toggleFilter}
          />

          <ProjectTimelineEventList
            projectId={projectId}
            events={visibleEvents}
            onNavigateToTask={props.onNavigateToTask}
            onNavigateToDeliverable={props.onNavigateToDeliverable}
            onNavigateToApproval={props.onNavigateToApproval}
          />
        </>
      )}
    </section>
  );
}
