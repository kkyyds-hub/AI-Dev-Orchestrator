import { formatDateTime } from "../../../lib/format";
import type {
  ProjectTimelineEventType,
  ProjectTimelineEventTypeCount,
} from "../types";
import { PROJECT_TIMELINE_EVENT_TYPE_LABELS } from "../types";

export function ProjectTimelineFilterPanel(props: {
  generatedAt: string | null;
  eventTypeCounts: ProjectTimelineEventTypeCount[];
  activeFilters: ProjectTimelineEventType[];
  onClearFilters: () => void;
  onToggleFilter: (eventType: ProjectTimelineEventType) => void;
}) {
  return (
    <section className="border-b border-[#333333] pb-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h3 className="text-sm font-medium text-slate-100">事件筛选</h3>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            {props.generatedAt
              ? `生成时间：${formatDateTime(props.generatedAt)}`
              : "等待生成时间"}
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <FilterButton active={!props.activeFilters.length} onClick={props.onClearFilters}>
            全部
          </FilterButton>
          {props.eventTypeCounts.map((bucket) => {
            const isActive = props.activeFilters.includes(bucket.event_type);
            return (
              <FilterButton
                key={bucket.event_type}
                active={isActive}
                onClick={() => props.onToggleFilter(bucket.event_type)}
              >
                {PROJECT_TIMELINE_EVENT_TYPE_LABELS[bucket.event_type] ?? bucket.label}
                <span className="ml-2 text-slate-500">{bucket.count}</span>
              </FilterButton>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function FilterButton(props: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={props.onClick}
      className={`border-b px-1 pb-2 pt-1 text-sm transition ${
        props.active
          ? "border-zinc-100 text-zinc-100"
          : "border-[#333333] text-slate-400 hover:border-zinc-500 hover:text-slate-200"
      }`}
    >
      {props.children}
    </button>
  );
}
