type DeliverableVersionMiniInfoProps = {
  label: string;
  value: string;
};

export function DeliverableVersionMiniInfo(
  props: DeliverableVersionMiniInfoProps,
) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
        {props.label}
      </div>
      <div className="mt-2 text-sm font-medium text-slate-100">
        {props.value}
      </div>
    </div>
  );
}
