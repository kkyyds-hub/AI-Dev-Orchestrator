type DeliverableCenterMetricProps = {
  label: string;
  value: string;
};

export function DeliverableCenterMetric(props: DeliverableCenterMetricProps) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
        {props.label}
      </div>
      <div className="mt-2 text-sm font-medium text-slate-100">
        {props.value}
      </div>
    </div>
  );
}
