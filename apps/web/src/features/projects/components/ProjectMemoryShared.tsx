import type { ProjectMemoryItem } from "../types";

export function ProjectMemoryMiniStat(props: { label: string; value: string }) {
  return (
    <div className="min-w-[120px] border-l border-[#333333] px-4 py-1">
      <div className="text-xs font-medium uppercase tracking-[0.16em] text-zinc-500">{props.label}</div>
      <div className="mt-2 truncate text-sm font-medium text-zinc-100">{props.value}</div>
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
