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
        <div className="min-w-0">
          <h3 className="text-sm font-medium text-zinc-100">事件流</h3>
          <p className="mt-1 text-xs text-zinc-500">选择事件后在右侧查看详情</p>
        </div>
        <span className="shrink-0 text-xs text-zinc-500">{props.events.length} 条</span>
      </div>

      {props.events.length ? (
        <div className="mt-3 max-h-[640px] overflow-y-auto border border-[#333333]">
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
        </div>
      ) : (
        <div className="mt-4 border border-dashed border-[#3a3a3a] px-4 py-8 text-center text-sm text-zinc-400">
          当前筛选条件下没有匹配的时间线事件。
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
      <div className="grid min-w-0 gap-3 sm:grid-cols-[150px_minmax(0,1fr)]">
        <div className="pt-1 text-xs tabular-nums leading-5 text-zinc-500">
          {formatDateTime(props.event.occurred_at)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge label={eventTypeLabel} tone={props.event.tone ?? "neutral"} />
            {props.event.stage ? <StatusBadge label={props.event.stage} tone="neutral" /> : null}
          </div>
          <div className="mt-2 line-clamp-1 break-words text-sm font-medium text-zinc-100">
            {props.event.title}
          </div>
          <p className="mt-1 line-clamp-2 break-words text-xs leading-5 text-zinc-500">
            {props.event.summary}
          </p>
        </div>
      </div>
    </button>
  );
}
