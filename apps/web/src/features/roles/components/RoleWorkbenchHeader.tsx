import { formatDateTime } from "../../../lib/format";
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
    <header className="flex flex-col gap-4 border-b border-[#333333] pb-6 lg:flex-row lg:items-end lg:justify-between">
      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">
          工作台
        </p>
        <h2 className="text-3xl font-semibold tracking-tight text-zinc-50">
          角色工作台
        </h2>
        <p className="max-w-3xl text-sm leading-6 text-zinc-400">
          查看各角色的任务负载、协作交接和需要关注的阻塞事项，帮助团队从角色视角快速判断推进状态。
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <HeaderStat
          label="当前范围"
          value={props.selectedProjectName ?? props.scopeLabel ?? "全部项目"}
        />
        <HeaderStat
          label="预算策略"
          value={props.budget?.strategy_label ?? "未设置"}
        />
        <HeaderStat label="最近生成" value={lastGeneratedText} />
      </div>
    </header>
  );
}

function HeaderStat(props: { label: string; value: string }) {
  return (
    <div className="border-l border-[#333333] px-4 py-2">
      <div className="text-xs uppercase tracking-[0.16em] text-zinc-500">{props.label}</div>
      <div className="mt-2 text-sm font-medium text-zinc-100">{props.value}</div>
    </div>
  );
}