type MetricCardProps = {
  label: string;
  value: string;
  hint?: string;
  tone?: "neutral" | "info" | "success" | "warning";
};

const toneStyles: Record<NonNullable<MetricCardProps["tone"]>, string> = {
  neutral: "border-zinc-800/90 bg-zinc-950/45",
  info: "border-zinc-800/90 bg-zinc-950/45",
  success: "border-zinc-800/90 bg-zinc-950/45",
  warning: "border-zinc-800/90 bg-zinc-950/45",
};

export function MetricCard({
  label,
  value,
  hint,
  tone = "neutral",
}: MetricCardProps) {
  return (
    <section className={`rounded-2xl border px-4 py-4 shadow-sm shadow-black/10 ${toneStyles[tone]}`}>
      <div className="text-xs font-medium tracking-[0.12em] text-zinc-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold tracking-tight text-zinc-50">
        {value}
      </div>
      {hint ? <div className="mt-1.5 truncate text-xs text-zinc-500">{hint}</div> : null}
    </section>
  );
}
