import { BudgetOverviewPanel } from "../../features/budget/BudgetOverviewPanel";
import { ConsoleMetricsPanel } from "../../features/console-metrics/ConsoleMetricsPanel";
import { DecisionHintPanel } from "../../features/console-metrics/DecisionHintPanel";
import { FailureDistributionPanel } from "../../features/console-metrics/FailureDistributionPanel";
import { ReviewClustersPanel } from "../../features/console-metrics/ReviewClustersPanel";
import { WorkerSlotPanel } from "../../features/console-metrics/WorkerSlotPanel";
import type { ConsoleBudget, ConsoleTask } from "../../features/console/types";
import type { StreamConnectionStatus } from "../../features/events/types";
import { TaskDetailPanel } from "../../features/task-detail/TaskDetailPanel";
import { formatCurrencyUsd, formatTokenCount } from "../../lib/format";

type RightSidebarOverviewSectionProps = {
  requestedRunId: string | null;
  selectedTask: ConsoleTask | null;
  budget: ConsoleBudget | null;
  blockedTasks: number;
  realtimeStatus: StreamConnectionStatus;
  onNavigateToRun?: (runId: string, taskId: string) => void;
  onNavigateToProjectDrilldown: (detail: {
    source: "home_latest_run" | "home_manual_run";
    taskId: string;
    runId?: string | null;
  }) => void;
  onNavigateToDeliverable: (input: { projectId: string; deliverableId: string }) => void;
  reviewClusters: Parameters<typeof ReviewClustersPanel>[0]["clusters"];
  reviewClustersIsLoading: boolean;
  reviewClustersErrorMessage: string | null;
  pendingTasks: number;
  runningTasks: number;
  completedTasks: number;
  failedTasks: number;
  totalPromptTokens: number;
  totalCompletionTokens: number;
  totalEstimatedCost: number;
};

export function RightSidebarOverviewSection(props: RightSidebarOverviewSectionProps) {
  return (
    <aside
      data-testid="home-right-sidebar-overview-section"
      className="space-y-4 xl:max-h-[calc(100vh-9rem)] xl:overflow-y-auto xl:pr-1"
    >
      <TaskDetailPanel
        panelId="task-detail-panel"
        runLogPanelId="task-run-log-panel"
        requestedRunId={props.requestedRunId}
        selectedTask={props.selectedTask}
        budget={props.budget}
        realtimeStatus={props.realtimeStatus}
        onNavigateToDeliverable={props.onNavigateToDeliverable}
        onNavigateToRun={props.onNavigateToRun}
        onNavigateToStrategyPreview={({ taskId, runId }) =>
          props.onNavigateToProjectDrilldown({
            source: "home_latest_run",
            taskId,
            runId,
          })
        }
      />

      <div
        data-testid="home-right-overview-section"
        className="rounded-2xl border border-slate-800 bg-slate-950/55 p-4"
      >
        <h2 className="text-base font-semibold text-slate-50">Run overview</h2>
        <div className="mt-3 grid gap-2 text-sm text-slate-300 sm:grid-cols-2 xl:grid-cols-1">
          <OverviewRow label="Pending" value={String(props.pendingTasks)} />
          <OverviewRow label="Running" value={String(props.runningTasks)} />
          <OverviewRow label="Completed" value={String(props.completedTasks)} />
          <OverviewRow label="Failed" value={String(props.failedTasks)} />
          <OverviewRow label="Blocked" value={String(props.blockedTasks)} />
        </div>
      </div>

      <div
        data-testid="home-right-cost-section"
        className="rounded-2xl border border-slate-800 bg-slate-950/55 p-4"
      >
        <h2 className="text-base font-semibold text-slate-50">Cost overview</h2>
        <div className="mt-3 space-y-2 text-sm text-slate-300">
          <OverviewRow
            label="Prompt Tokens"
            value={formatTokenCount(props.totalPromptTokens)}
          />
          <OverviewRow
            label="Completion Tokens"
            value={formatTokenCount(props.totalCompletionTokens)}
          />
          <OverviewRow
            label="Estimated cost"
            value={formatCurrencyUsd(props.totalEstimatedCost)}
          />
        </div>
        <p className="mt-3 text-xs leading-5 text-slate-500">
          Estimated cost is used as a lightweight reference for budget guardrails on the workbench.
        </p>
      </div>

      {props.budget ? (
        <BudgetOverviewPanel budget={props.budget} blockedTasks={props.blockedTasks} />
      ) : null}

      <ConsoleMetricsPanel />

      <FailureDistributionPanel />

      <ReviewClustersPanel
        clusters={props.reviewClusters}
        isLoading={props.reviewClustersIsLoading}
        errorMessage={props.reviewClustersErrorMessage}
      />

      <DecisionHintPanel />

      <WorkerSlotPanel />
    </aside>
  );
}

function OverviewRow(props: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-800/90 bg-slate-950/70 px-3 py-2.5">
      <span className="truncate text-slate-500">{props.label}</span>
      <span className="shrink-0 font-medium text-slate-100">{props.value}</span>
    </div>
  );
}
