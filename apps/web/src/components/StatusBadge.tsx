type StatusBadgeProps = {
  label: string;
  tone?: "neutral" | "info" | "success" | "warning" | "danger";
};

const toneStyles: Record<NonNullable<StatusBadgeProps["tone"]>, string> = {
  neutral: "border-zinc-700/80 bg-zinc-900/80 text-zinc-200",
  info: "border-zinc-700/75 bg-zinc-900/70 text-zinc-200",
  success: "border-zinc-700/75 bg-zinc-900/70 text-zinc-100",
  warning: "border-zinc-700/75 bg-zinc-900/70 text-zinc-300",
  danger: "border-rose-900/60 bg-rose-950/30 text-rose-200",
};

export function StatusBadge({
  label,
  tone = "neutral",
}: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium tracking-wide ${toneStyles[tone]}`}
    >
      {label}
    </span>
  );
}
