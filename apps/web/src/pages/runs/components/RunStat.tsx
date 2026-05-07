type RunStatProps = {
  label: string;
  value: string;
};

export function RunStat(props: RunStatProps) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-3 py-2">
      <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
        {props.label}
      </div>
      <div className="mt-1 text-sm text-slate-200">{props.value}</div>
    </div>
  );
}
