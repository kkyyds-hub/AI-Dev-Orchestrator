type MetricCardProps = {
  label: string;
  value: string;
  hint?: string;
  tone?: "neutral" | "info" | "success" | "warning";
};

const toneStyles: Record<NonNullable<MetricCardProps["tone"]>, string> = {
  neutral: "border-slate-800 bg-slate-900/70",
  info: "border-cyan-500/20 bg-cyan-500/5",
  success: "border-emerald-500/20 bg-emerald-500/5",
  warning: "border-amber-500/20 bg-amber-500/5",
};

export function MetricCard({
  label,
  value,
  hint,
  tone = "neutral",
}: MetricCardProps) {
  return (
    <section className={`rounded-2xl border p-5 ${toneStyles[tone]}`}>
      <div className="text-sm text-slate-400">{label}</div>
      <div className="mt-3 text-3xl font-semibold tracking-tight text-slate-50">
        {value}
      </div>
      {hint ? <div className="mt-2 text-xs text-slate-500">{hint}</div> : null}
    </section>
  );
}
