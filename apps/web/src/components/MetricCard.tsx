type MetricCardProps = {
  label: string;
  value: string;
  hint?: string;
  tone?: "neutral" | "info" | "success" | "warning";
};

const toneStyles: Record<NonNullable<MetricCardProps["tone"]>, string> = {
  neutral: "border-slate-800 bg-slate-950/55",
  info: "border-cyan-500/20 bg-cyan-500/[0.06]",
  success: "border-emerald-500/20 bg-emerald-500/[0.06]",
  warning: "border-amber-500/20 bg-amber-500/[0.06]",
};

export function MetricCard({
  label,
  value,
  hint,
  tone = "neutral",
}: MetricCardProps) {
  return (
    <section className={`rounded-2xl border px-4 py-3.5 ${toneStyles[tone]}`}>
      <div className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className="mt-2 truncate text-2xl font-semibold tracking-tight text-slate-50">
        {value}
      </div>
      {hint ? <div className="mt-1 truncate text-xs text-slate-500">{hint}</div> : null}
    </section>
  );
}
