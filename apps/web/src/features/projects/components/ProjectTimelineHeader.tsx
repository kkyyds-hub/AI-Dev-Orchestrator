export function ProjectTimelineHeader(props: {
  projectName: string | null;
  totalEvents: number;
  visibleEventCount: number;
}) {
  return (
    <header className="border-b border-[#333333] pb-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-500">
            Timeline
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-50">
            Project event stream
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
            Browse project milestones, deliverables, approvals, and run decisions from one event stream.
          </p>
        </div>

        <div className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-3 lg:text-right">
          <TimelineMetric label="Project" value={props.projectName ?? "Unselected"} />
          <TimelineMetric label="Total" value={String(props.totalEvents)} />
          <TimelineMetric label="Visible" value={String(props.visibleEventCount)} />
        </div>
      </div>
    </header>
  );
}

function TimelineMetric(props: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-[0.16em] text-slate-500">
        {props.label}
      </div>
      <div className="mt-1 truncate text-sm font-medium text-slate-100">
        {props.value}
      </div>
    </div>
  );
}
