import { MetricCard } from "../../../components/MetricCard";

type RoleCatalogMetricGridProps = {
  systemRoleCount: number;
  enabledRoleCount: number;
  disabledRoleCount: number;
  selectedProjectName: string | null;
};

export function RoleCatalogMetricGrid(props: RoleCatalogMetricGridProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <MetricCard
        label="系统角色数"
        value={String(props.systemRoleCount)}
        hint="Day05 的最小内置角色目录"
        tone="info"
      />
      <MetricCard
        label="项目已启用"
        value={String(props.enabledRoleCount)}
        hint={
          props.selectedProjectName
            ? "当前项目启用的角色数"
            : "选择项目后可查看"
        }
        tone="success"
      />
      <MetricCard
        label="项目未启用"
        value={String(props.disabledRoleCount)}
        hint="可在角色编辑抽屉中启用或停用"
        tone="warning"
      />
      <MetricCard
        label="目录模式"
        value={props.selectedProjectName ? "项目配置" : "系统只读"}
        hint="Day05 不涉及任务调度与 Skill 引擎"
      />
    </div>
  );
}
