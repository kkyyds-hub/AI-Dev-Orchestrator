type RunsSummaryCardProps = {
  label: string;
  value: string;
};

export function RunsSummaryCard(props: RunsSummaryCardProps) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
        {props.label}
      </div>
      <div className="mt-2 break-all text-sm font-medium text-slate-100">
        {props.value}
      </div>
    </div>
  );
}
