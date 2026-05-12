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
    <header className="flex flex-col gap-4 border-b border-[#333333] pb-4 lg:flex-row lg:items-start lg:justify-between">
      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">
          工作台
        </p>
        <h2 className="text-xl font-semibold tracking-tight text-zinc-50">角色工作台</h2>
        <p className="max-w-3xl text-sm leading-6 text-zinc-400">
          在当前治理父页面内查看角色负载、协作交接和阻塞事项。
        </p>
      </div>

      <dl className="grid gap-3 sm:grid-cols-3 lg:min-w-[420px]">
        <HeaderStat
          label="当前范围"
          value={props.selectedProjectName ?? props.scopeLabel ?? "全部项目"}
        />
        <HeaderStat
          label="预算策略"
          value={props.budget?.strategy_label ?? "未设置"}
        />
        <HeaderStat label="最近生成" value={lastGeneratedText} />
      </dl>
    </header>
  );
}

function HeaderStat(props: { label: string; value: string }) {
  return (
    <div className="min-w-0 border-l border-[#333333] px-3 py-1">
      <dt className="text-xs uppercase tracking-[0.16em] text-zinc-500">{props.label}</dt>
      <dd className="mt-1 truncate text-sm font-medium text-zinc-100">{props.value}</dd>
    </div>
  );
}
