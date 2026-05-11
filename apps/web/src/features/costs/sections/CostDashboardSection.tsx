import { CostDashboardEmptyState } from "../components/CostDashboardEmptyState";
import { CostDashboardFallbackSummary } from "../components/CostDashboardFallbackSummary";
import { CostDashboardHeader } from "../components/CostDashboardHeader";
import { CostDashboardMetricGrid } from "../components/CostDashboardMetricGrid";
import {
  CostDashboardCacheSummaryPanel,
  CostDashboardCostSourcePanel,
} from "../components/CostDashboardModeCacheGrid";
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
      className="space-y-4"
    >
      <CostDashboardHeader
        projectId={props.projectId}
        projectName={props.projectName}
        isRefreshing={costQuery.isFetching}
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

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
            <div className="space-y-4">
              <CostDashboardCostSourcePanel snapshot={snapshot} />
              <CostDashboardRoleBreakdownTable snapshot={snapshot} />
              <CostDashboardThreadBreakdownTable snapshot={snapshot} />
            </div>

            <aside className="space-y-4 xl:sticky xl:top-4 xl:self-start">
              <CostDashboardFallbackSummary snapshot={snapshot} />
              <CostDashboardCacheSummaryPanel snapshot={snapshot} />
              <CostDashboardSmokeRoutes snapshot={snapshot} />
            </aside>
          </div>
        </>
      ) : null}
    </section>
  );
}
