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
    <header className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-6 lg:flex-row lg:items-end lg:justify-between">
      <div className="space-y-2">
        <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">
          V3 Day08 Role Workbench
        </p>
        <h2 className="text-3xl font-semibold tracking-tight text-slate-50">
          角色工作台与协作可视化
        </h2>
        <p className="max-w-3xl text-sm leading-6 text-slate-300">
          角色工作台直接把 PM、架构师、工程师、评审者的当前负载、阻塞卡点、运行态和最近交接搬到前台，并与老板首页共用同一套项目 / 任务 / 运行聚合口径。
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
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
