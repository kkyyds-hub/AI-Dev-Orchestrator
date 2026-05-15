import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime, formatNullableCurrencyUsd } from "../../../lib/format";
import { mapRunStatusTone } from "../../../lib/status";
import type { RunListItem } from "../types";
import { RunStat } from "./RunStat";

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

export function RunListItemButton(props: RunListItemButtonProps) {
  return (
    <button
      type="button"
      onClick={props.onSelect}
      className={`w-full px-3 py-4 text-left transition ${
        props.selected
          ? "bg-[#2b2b2b]"
          : "bg-transparent hover:bg-[#252525]"
      }`}
    >
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_210px] lg:items-start">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <div className="truncate text-sm font-medium text-zinc-100">
              {props.item.task.title}
            </div>
            <StatusBadge
              label={formatRunStatusLabel(props.item.run.status)}
              tone={mapRunStatusTone(props.item.run.status)}
            />
          </div>
          <div className="mt-2 truncate text-xs text-zinc-600">
            关联任务：{props.item.task.title}
          </div>
          <p className="mt-3 line-clamp-2 text-sm leading-6 text-zinc-400">
            {props.item.run.result_summary ?? "暂无运行摘要"}
          </p>
        </div>

        <div className="grid gap-3 border-l border-[#333333] pl-4 text-xs text-zinc-500">
          <RunStat
            label="创建时间"
            value={formatDateTime(props.item.run.created_at)}
          />
          <RunStat
            label="估算成本"
            value={formatNullableCurrencyUsd(props.item.run.estimated_cost)}
          />
        </div>
      </div>
    </button>
  );
}
