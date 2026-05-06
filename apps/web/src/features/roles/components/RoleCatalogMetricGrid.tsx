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
        label="?????"
        value={String(props.systemRoleCount)}
        hint="Day05 ?????????"
        tone="info"
      />
      <MetricCard
        label="?????"
        value={String(props.enabledRoleCount)}
        hint={
          props.selectedProjectName
            ? "??????????"
            : "????????"
        }
        tone="success"
      />
      <MetricCard
        label="?????"
        value={String(props.disabledRoleCount)}
        hint="??????????????"
        tone="warning"
      />
      <MetricCard
        label="????"
        value={props.selectedProjectName ? "????" : "????"}
        hint="Day05 ???????? Skill ??"
      />
    </div>
  );
}
