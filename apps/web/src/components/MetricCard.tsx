type MetricCardProps = {
  label: string;
  value: string;
  hint?: string;
  tone?: "neutral" | "info" | "success" | "warning" | "danger";
  variant?: "card" | "plain";
};

const toneStyles: Record<NonNullable<MetricCardProps["tone"]>, string> = {
  neutral: "border-zinc-800/90 bg-zinc-950/45",
  info: "border-zinc-800/90 bg-zinc-950/45",
  success: "border-zinc-800/90 bg-zinc-950/45",
  warning: "border-zinc-800/90 bg-zinc-950/45",
  danger: "border-rose-900/60 bg-rose-950/25",
};

export function MetricCard({
  label,
  value,
  hint,
  tone = "neutral",
  variant = "card",
}: MetricCardProps) {
  if (variant === "plain") {
    return (
      <section className="min-w-0">
        <div className="text-sm text-zinc-400">{label}</div>
        <div className="mt-2 truncate font-mono text-2xl font-semibold tracking-tight text-zinc-100">
          {value}
        </div>
        {hint ? <div className="mt-1.5 truncate text-xs text-zinc-600">{hint}</div> : null}
      </section>
    );
  }

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
