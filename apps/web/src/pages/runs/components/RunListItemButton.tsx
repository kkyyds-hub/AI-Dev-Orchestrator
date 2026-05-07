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

export function RunListItemButton(props: RunListItemButtonProps) {
  return (
    <button
      type="button"
      onClick={props.onSelect}
      className={`w-full rounded-2xl border p-4 text-left transition ${
        props.selected
          ? "border-cyan-500/40 bg-cyan-500/10"
          : "border-slate-800 bg-slate-950/60 hover:border-slate-700 hover:bg-slate-950/80"
      }`}
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-sm font-medium text-slate-100">
              {props.item.task.title}
            </div>
            <StatusBadge
              label={props.item.run.status}
              tone={mapRunStatusTone(props.item.run.status)}
            />
          </div>
          <div className="mt-2 text-xs text-slate-500">
            Task {props.item.task.id} · Run {props.item.run.id}
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-300">
            {props.item.run.result_summary ?? "暂无运行摘要"}
          </p>
        </div>

        <div className="grid gap-2 text-xs text-slate-400 sm:grid-cols-2 lg:min-w-[220px]">
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
