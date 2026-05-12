import type { RoleWorkbenchSnapshot } from "../types";

type RoleWorkbenchMetricGridProps = {
  snapshot: RoleWorkbenchSnapshot;
};

export function RoleWorkbenchMetricGrid(props: RoleWorkbenchMetricGridProps) {
  const { snapshot } = props;

  return (
    <dl className="grid gap-x-5 gap-y-3 border-b border-[#333333] pb-4 md:grid-cols-3 xl:grid-cols-6">
      <WorkbenchStat
        label="角色列"
        value={String(snapshot.total_roles)}
        hint={`已启用 ${snapshot.enabled_roles} 个角色`}
      />
      <WorkbenchStat
        label="当前任务"
        value={String(snapshot.active_tasks)}
        hint="未完成任务总量"
      />
      <WorkbenchStat
        label="运行中项"
        value={String(snapshot.running_tasks)}
        hint="任务或运行仍在推进"
      />
      <WorkbenchStat
        label="阻塞项"
        value={String(snapshot.blocked_tasks)}
        hint="包含阻塞 / 暂停 / 待人工 / 失败"
      />
      <WorkbenchStat
        label="未分派"
        value={String(snapshot.unassigned_tasks)}
        hint="当前没有明确 owner role 的任务"
      />
      <WorkbenchStat
        label="最近交接"
        value={String(snapshot.recent_handoff_count)}
        hint="来自最新运行日志中的角色交接事件"
      />
    </dl>
  );
}

function WorkbenchStat(props: { label: string; value: string; hint: string }) {
  return (
    <div className="min-w-0 border-l border-[#333333] px-3 py-1">
      <dt className="text-xs uppercase tracking-[0.16em] text-zinc-500">{props.label}</dt>
      <dd className="mt-1 text-base font-semibold tracking-tight text-zinc-100">{props.value}</dd>
      <dd className="mt-1 text-xs leading-5 text-zinc-600">{props.hint}</dd>
    </div>
  );
}
