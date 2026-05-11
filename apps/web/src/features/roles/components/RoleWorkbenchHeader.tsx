import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import { mapBudgetPressureTone } from "../../../lib/status";
import type { RoleWorkbenchSnapshot } from "../types";

type RoleWorkbenchHeaderProps = {
  selectedProjectName: string | null;
  scopeLabel: string | null;
  budget: RoleWorkbenchSnapshot["budget"] | null;
  generatedAt: string | null;
};

export function RoleWorkbenchHeader(props: RoleWorkbenchHeaderProps) {
  const lastGeneratedText = props.generatedAt ? formatDateTime(props.generatedAt) : "尚未生成";

  return (
    <header className="flex flex-col gap-4 border-b border-slate-800 pb-5 lg:flex-row lg:items-end lg:justify-between">
      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-slate-500">
          角色工作台
        </p>
        <h2 className="text-2xl font-semibold tracking-tight text-slate-50">
          团队协作概览
        </h2>
        <p className="max-w-3xl text-sm leading-6 text-slate-400">
          查看各角色的任务负载、协作交接和需要关注的阻塞事项。
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400 lg:justify-end">
        <StatusBadge
          label={
            props.selectedProjectName
              ? `当前项目：${props.selectedProjectName}`
              : props.scopeLabel ?? "全部项目"
          }
          tone={props.selectedProjectName ? "info" : "neutral"}
        />
        {props.budget ? (
          <StatusBadge
            label={props.budget.strategy_label}
            tone={mapBudgetPressureTone(props.budget.pressure_level)}
          />
        ) : null}
        <span>最近生成：{lastGeneratedText}</span>
      </div>
    </header>
  );
}
