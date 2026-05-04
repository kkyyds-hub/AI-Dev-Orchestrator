import { CostDashboardEmptyState } from "../components/CostDashboardEmptyState";
import { CostDashboardFallbackSummary } from "../components/CostDashboardFallbackSummary";
import { CostDashboardHeader } from "../components/CostDashboardHeader";
import { CostDashboardMetricGrid } from "../components/CostDashboardMetricGrid";
import { CostDashboardModeCacheGrid } from "../components/CostDashboardModeCacheGrid";
import { CostDashboardQueryState } from "../components/CostDashboardQueryState";
import { CostDashboardRoleBreakdownTable } from "../components/CostDashboardRoleBreakdownTable";
import { CostDashboardSmokeRoutes } from "../components/CostDashboardSmokeRoutes";
import { CostDashboardThreadBreakdownTable } from "../components/CostDashboardThreadBreakdownTable";
import { useProjectCostDashboardSnapshot } from "../hooks";

const COST_DASHBOARD_TEST_ID = "day14-cost-dashboard";

type CostDashboardSectionProps = {
  projectId: string | null;
  projectName: string | null;
};

export function CostDashboardSection(props: CostDashboardSectionProps) {
  const costQuery = useProjectCostDashboardSnapshot(props.projectId);

  if (!props.projectId) {
    return <CostDashboardEmptyState testId={COST_DASHBOARD_TEST_ID} />;
  }

  const snapshot = costQuery.data ?? null;

  return (
    <section
      id={COST_DASHBOARD_TEST_ID}
      data-testid={COST_DASHBOARD_TEST_ID}
      className="space-y-5 rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30"
    >
      <CostDashboardHeader
        projectId={props.projectId}
        projectName={props.projectName}
        onRefresh={() => void costQuery.refetch()}
      />

      <CostDashboardQueryState
        isLoading={costQuery.isLoading && !snapshot}
        isError={costQuery.isError}
        errorMessage={costQuery.error?.message ?? null}
      />

      {snapshot ? (
        <>
          <CostDashboardMetricGrid snapshot={snapshot} />
          <CostDashboardFallbackSummary snapshot={snapshot} />
          <CostDashboardModeCacheGrid snapshot={snapshot} />
          <CostDashboardRoleBreakdownTable snapshot={snapshot} />
          <CostDashboardThreadBreakdownTable snapshot={snapshot} />
          <CostDashboardSmokeRoutes snapshot={snapshot} />
        </>
      ) : null}
    </section>
  );
}
