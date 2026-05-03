import type { ProjectMemoryItem } from "../types";

export function ProjectMemoryMiniStat(props: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{props.label}</div>
      <div className="mt-2 text-sm font-medium text-slate-100">{props.value}</div>
    </div>
  );
}

export function mapMemoryTone(memoryType: ProjectMemoryItem["memory_type"]) {
  switch (memoryType) {
    case "conclusion":
      return "success" as const;
    case "failure_pattern":
      return "danger" as const;
    case "approval_feedback":
      return "warning" as const;
    case "deliverable_summary":
      return "info" as const;
    default:
      return "neutral" as const;
  }
}
