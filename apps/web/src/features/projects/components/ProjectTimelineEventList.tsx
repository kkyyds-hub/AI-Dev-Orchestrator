import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import type { ProjectTimelineEvent } from "../types";
import { PROJECT_TIMELINE_EVENT_TYPE_LABELS } from "../types";

export function ProjectTimelineEventList(props: {
  events: ProjectTimelineEvent[];
  selectedEventId: string | null;
  onSelectEvent: (eventId: string) => void;
}) {
  return (
    <section className="min-w-0">
      <div className="flex items-end justify-between gap-3 border-b border-[#333333] pb-3">
        <div>
          <h3 className="text-sm font-medium text-slate-100">Event stream</h3>
          <p className="mt-1 text-xs text-slate-500">Select an event to inspect details</p>
        </div>
        <span className="text-xs text-slate-500">{props.events.length} events</span>
      </div>

      {props.events.length ? (
        <div className="divide-y divide-[#333333]">
          {props.events.map((event) => (
            <TimelineEventRow
              key={event.id}
              event={event}
              selected={event.id === props.selectedEventId}
              onSelect={() => props.onSelectEvent(event.id)}
            />
          ))}
        </div>
      ) : (
        <div className="mt-4 border border-dashed border-[#3a3a3a] px-4 py-8 text-center text-sm text-slate-400">
          No events match the current filters.
        </div>
      )}
    </section>
  );
}

function TimelineEventRow(props: {
  event: ProjectTimelineEvent;
  selected: boolean;
  onSelect: () => void;
}) {
  const eventTypeLabel =
    PROJECT_TIMELINE_EVENT_TYPE_LABELS[props.event.event_type] ?? props.event.label;

  return (
    <button
      type="button"
      onClick={props.onSelect}
      className={`group w-full border-l-2 px-4 py-4 text-left transition ${
        props.selected
          ? "border-l-zinc-200 bg-white/[0.03]"
          : "border-l-transparent hover:border-l-[#555555] hover:bg-white/[0.02]"
      }`}
      aria-current={props.selected ? "true" : undefined}
    >
      <div className="flex items-start gap-3">
        <div className="pt-1 text-xs tabular-nums text-slate-500">
          {formatDateTime(props.event.occurred_at)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge label={eventTypeLabel} tone={props.event.tone ?? "neutral"} />
            {props.event.stage ? <StatusBadge label={props.event.stage} tone="neutral" /> : null}
          </div>
          <div className="mt-2 line-clamp-1 text-sm font-medium text-slate-100">
            {props.event.title}
          </div>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">
            {props.event.summary}
          </p>
        </div>
      </div>
    </button>
  );
}
