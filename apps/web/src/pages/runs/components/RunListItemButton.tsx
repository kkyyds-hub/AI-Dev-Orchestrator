import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime, formatNullableCurrencyUsd } from "../../../lib/format";
import { mapRunStatusTone } from "../../../lib/status";
import type { RunListItem } from "../types";

type RunListItemButtonProps = {
  item: RunListItem;
  selected: boolean;
  onSelect: () => void;
};

function formatRunStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: "待运行",
    queued: "排队中",
    running: "运行中",
    completed: "已完成",
    failed: "失败",
    cancelled: "已取消",
    blocked: "已阻断",
    paused: "已暂停",
    waiting_human: "等待人工",
  };
  return labels[status] ?? status;
}

function formatFailureReason(run: RunListItem["run"]): string | null {
  if (run.failure_category) return run.failure_category;
  if (run.status === "failed") return "execution_failed";
  if (run.status === "blocked") return "blocked";
  return null;
}

export function RunListItemButton(props: RunListItemButtonProps) {
  const failureReason = formatFailureReason(props.item.run);
  const isFailed = props.item.run.status === "failed" || props.item.run.status === "blocked";

  return (
    <button
      type="button"
      onClick={props.onSelect}
      className={`w-full px-3 py-3 text-left transition ${
        props.selected
          ? "border-l-2 border-zinc-300 bg-[#2b2b2b]"
          : `border-l-2 border-transparent bg-transparent hover:bg-[#252525] ${
              isFailed ? "border-l-red-500/30" : ""
            }`
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate text-sm font-medium text-zinc-100">
              {props.item.task.title}
            </span>
            <StatusBadge
              label={formatRunStatusLabel(props.item.run.status)}
              tone={mapRunStatusTone(props.item.run.status)}
            />
            {failureReason ? (
              <span className="truncate text-xs text-rose-400">{failureReason}</span>
            ) : null}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-500">
            <span>{formatDateTime(props.item.run.created_at)}</span>
            <span>{formatNullableCurrencyUsd(props.item.run.estimated_cost)}</span>
          </div>
        </div>
        <span className="shrink-0 text-xs text-zinc-600">
          {props.selected ? "查看中" : "选择"}
        </span>
      </div>
    </button>
  );
}
