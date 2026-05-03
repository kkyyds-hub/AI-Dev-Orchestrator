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
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-50">事件筛选</h3>
          <p className="mt-1 text-sm text-slate-400">
            支持按最小事件类型过滤，帮助老板快速聚焦“计划 / 验证 / 审批 / 失败 / 回退重做”相关节点。
          </p>
        </div>
        <div className="text-sm text-slate-400">
          生成时间：
          {props.generatedAt ? formatDateTime(props.generatedAt) : "—"}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={props.onClearFilters}
          className={`rounded-full border px-4 py-2 text-sm transition ${
            !props.activeFilters.length
              ? "border-cyan-400/60 bg-cyan-500/10 text-cyan-100"
              : "border-slate-700 bg-slate-950/70 text-slate-300 hover:border-slate-500"
          }`}
        >
          全部
        </button>
        {props.eventTypeCounts.map((bucket) => {
          const isActive = props.activeFilters.includes(bucket.event_type);
          return (
            <button
              key={bucket.event_type}
              type="button"
              onClick={() => props.onToggleFilter(bucket.event_type)}
              className={`rounded-full border px-4 py-2 text-sm transition ${
                isActive
                  ? "border-cyan-400/60 bg-cyan-500/10 text-cyan-100"
                  : "border-slate-700 bg-slate-950/70 text-slate-300 hover:border-slate-500"
              }`}
            >
              {PROJECT_TIMELINE_EVENT_TYPE_LABELS[bucket.event_type] ??
                bucket.label}
              <span className="ml-2 text-slate-400">{bucket.count}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
