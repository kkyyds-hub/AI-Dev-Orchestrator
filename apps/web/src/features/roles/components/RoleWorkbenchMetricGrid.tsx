import { MetricCard } from "../../../components/MetricCard";
import type { RoleWorkbenchSnapshot } from "../types";

type RoleWorkbenchMetricGridProps = {
  snapshot: RoleWorkbenchSnapshot;
};

export function RoleWorkbenchMetricGrid(props: RoleWorkbenchMetricGridProps) {
  const { snapshot } = props;

  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
      <MetricCard
        label="角色列"
        value={String(snapshot.total_roles)}
        hint={`已启用 ${snapshot.enabled_roles} 个角色`}
        tone="info"
      />
      <MetricCard
        label="当前任务"
        value={String(snapshot.active_tasks)}
        hint="未完成任务总量"
        tone="success"
      />
      <MetricCard
        label="运行中项"
        value={String(snapshot.running_tasks)}
        hint="任务或运行仍在推进"
        tone="info"
      />
      <MetricCard
        label="阻塞项"
        value={String(snapshot.blocked_tasks)}
        hint="包含阻塞 / 暂停 / 待人工 / 失败"
        tone="warning"
      />
      <MetricCard
        label="未分派"
        value={String(snapshot.unassigned_tasks)}
        hint="当前没有明确 owner role 的任务"
      />
      <MetricCard
        label="最近交接"
        value={String(snapshot.recent_handoff_count)}
        hint="来自最新运行日志中的 role_handoff"
        tone="info"
      />
    </section>
  );
}
