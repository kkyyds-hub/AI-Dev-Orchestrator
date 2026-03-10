type StatusBadgeProps = {
  label: string;
  tone?: "neutral" | "info" | "success" | "warning" | "danger";
};

const toneStyles: Record<NonNullable<StatusBadgeProps["tone"]>, string> = {
  neutral: "border-slate-700 bg-slate-800 text-slate-200",
  info: "border-cyan-500/30 bg-cyan-500/10 text-cyan-100",
  success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-100",
  warning: "border-amber-500/30 bg-amber-500/10 text-amber-100",
  danger: "border-rose-500/30 bg-rose-500/10 text-rose-100",
};

export function StatusBadge({
  label,
  tone = "neutral",
}: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium uppercase tracking-wide ${toneStyles[tone]}`}
    >
      {label}
    </span>
  );
}
