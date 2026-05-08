type StatusBadgeProps = {
  label: string;
  tone?: "neutral" | "info" | "success" | "warning" | "danger";
};

const toneStyles: Record<NonNullable<StatusBadgeProps["tone"]>, string> = {
  neutral: "border-[#333333] bg-transparent text-zinc-300",
  info: "border-[#333333] bg-transparent text-zinc-300",
  success: "border-[#333333] bg-transparent text-zinc-100",
  warning: "border-[#333333] bg-transparent text-zinc-300",
  danger: "border-rose-900/60 bg-rose-950/20 text-rose-200",
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
