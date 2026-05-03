import { StatusBadge } from "../../../components/StatusBadge";
import type { ApprovalAction, ApprovalStatus } from "../../approvals/types";
import type { ProjectApprovalCycleStatus } from "../../approvals/types";

export function ProjectRetrospectiveStat(props: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">{props.label}</div>
      <div className="mt-2 text-sm font-medium text-slate-100">{props.value}</div>
    </div>
  );
}

export function ProjectRetrospectiveTagList(props: {
  title: string;
  items: string[];
  tone: "neutral" | "info" | "warning";
}) {
  return (
    <div className="mt-4">
      <div className="text-xs uppercase tracking-[0.16em] text-slate-500">{props.title}</div>
      <div className="mt-2 flex flex-wrap gap-2">
        {props.items.map((item) => (
          <StatusBadge key={`${props.title}-${item}`} label={item} tone={props.tone} />
        ))}
      </div>
    </div>
  );
}

export function mapDecisionTone(action: ApprovalAction) {
  switch (action) {
    case "approve":
      return "success" as const;
    case "reject":
      return "danger" as const;
    case "request_changes":
      return "warning" as const;
    default:
      return "neutral" as const;
  }
}

export function mapApprovalTone(status: ApprovalStatus) {
  switch (status) {
    case "approved":
      return "success" as const;
    case "rejected":
      return "danger" as const;
    case "changes_requested":
      return "warning" as const;
    case "pending_approval":
      return "info" as const;
    default:
      return "neutral" as const;
  }
}

export function mapCycleTone(status: ProjectApprovalCycleStatus) {
  switch (status) {
    case "approved_after_rework":
      return "success" as const;
    case "resubmitted_pending_approval":
      return "info" as const;
    case "reworking":
      return "warning" as const;
    default:
      return "danger" as const;
  }
}
