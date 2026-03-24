import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import type { RepositoryReleaseGateDetail } from "./types";
import {
  REPOSITORY_RELEASE_CHECKLIST_ITEM_STATUS_LABELS,
  REPOSITORY_RELEASE_GATE_STATUS_LABELS,
} from "./types";

type RepositoryReleaseChecklistProps = {
  gate: RepositoryReleaseGateDetail;
};

export function RepositoryReleaseChecklist(props: RepositoryReleaseChecklistProps) {
  const gate = props.gate;

  return (
    <section className="space-y-4 rounded-2xl border border-slate-800 bg-slate-950/50 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-slate-100">{gate.change_batch_title}</div>
          <div className="mt-1 text-xs text-slate-500">
            批次：{gate.change_batch_id} · 生成时间：{formatDateTime(gate.generated_at)}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <StatusBadge
            label={REPOSITORY_RELEASE_GATE_STATUS_LABELS[gate.status] ?? gate.status}
            tone={mapGateTone(gate.status)}
          />
          <StatusBadge
            label={`${gate.passed_item_count}/${gate.required_item_count} 必需项通过`}
            tone={gate.blocked ? "warning" : "success"}
          />
          {gate.snapshot_age_minutes !== null ? (
            <StatusBadge label={`快照 ${gate.snapshot_age_minutes} 分钟前`} tone="neutral" />
          ) : null}
        </div>
      </div>

      {gate.gap_reasons.length > 0 ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3">
          <div className="text-sm font-medium text-rose-100">当前阻断缺口</div>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-rose-50/90">
            {gate.gap_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
          所有关键项已齐备，可进入审批决策。
        </div>
      )}

      <div className="space-y-3">
        {gate.checklist_items.map((item) => (
          <div
            key={`${item.key}-${item.checked_at ?? "na"}`}
            className="rounded-2xl border border-slate-800 bg-slate-900/60 px-4 py-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-sm font-medium text-slate-100">{item.title}</div>
              <StatusBadge
                label={
                  REPOSITORY_RELEASE_CHECKLIST_ITEM_STATUS_LABELS[item.status] ?? item.status
                }
                tone={item.status === "passed" ? "success" : "danger"}
              />
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-300">{item.summary}</p>
            {item.gap_reason ? (
              <p className="mt-1 text-xs leading-5 text-rose-200">{item.gap_reason}</p>
            ) : null}
            <div className="mt-1 text-xs text-slate-500">
              {item.evidence_key ? `证据键：${item.evidence_key}` : "无附加证据键"}
              {item.checked_at ? ` · 检查时间：${formatDateTime(item.checked_at)}` : ""}
            </div>
          </div>
        ))}
      </div>

      {gate.decisions.length > 0 ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 px-4 py-3">
          <div className="text-sm font-medium text-slate-100">审批记录</div>
          <div className="mt-3 space-y-2">
            {gate.decisions.map((decision) => (
              <div
                key={decision.id}
                className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <StatusBadge label={mapDecisionLabel(decision.action)} tone={mapDecisionTone(decision.action)} />
                  <span className="text-xs text-slate-500">
                    {decision.actor_name} · {formatDateTime(decision.created_at)}
                  </span>
                </div>
                <div className="mt-1 text-sm leading-6 text-slate-300">{decision.summary}</div>
                {decision.comment ? (
                  <div className="mt-1 text-xs leading-5 text-slate-400">{decision.comment}</div>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function mapGateTone(status: RepositoryReleaseGateDetail["status"]) {
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
      return "danger" as const;
  }
}

function mapDecisionLabel(action: "approve" | "reject" | "request_changes") {
  switch (action) {
    case "approve":
      return "通过";
    case "reject":
      return "驳回";
    default:
      return "补证据";
  }
}

function mapDecisionTone(action: "approve" | "reject" | "request_changes") {
  switch (action) {
    case "approve":
      return "success" as const;
    case "reject":
      return "danger" as const;
    default:
      return "warning" as const;
  }
}
