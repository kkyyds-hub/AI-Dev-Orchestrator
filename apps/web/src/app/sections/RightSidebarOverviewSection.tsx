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
    <aside data-testid="home-right-sidebar-overview-section" className="space-y-4">
      <TaskDetailPanel
        panelId="task-detail-panel"
        runLogPanelId="task-run-log-panel"
        requestedRunId={props.requestedRunId}
        selectedTask={props.selectedTask}
        budget={props.budget}
        realtimeStatus={props.realtimeStatus}
        onNavigateToDeliverable={props.onNavigateToDeliverable}
      />

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

      <div
        data-testid="home-right-overview-section"
        className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5"
      >
        <h2 className="text-lg font-semibold text-slate-50">杩愯姒傝</h2>
        <div className="mt-4 space-y-3 text-sm text-slate-300">
          <OverviewRow label="寰呭鐞?" value={String(props.pendingTasks)} />
          <OverviewRow label="杩愯涓?" value={String(props.runningTasks)} />
          <OverviewRow label="宸插畬鎴?" value={String(props.completedTasks)} />
          <OverviewRow label="澶辫触" value={String(props.failedTasks)} />
          <OverviewRow label="闃诲" value={String(props.blockedTasks)} />
        </div>
      </div>

      <div
        data-testid="home-right-cost-section"
        className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5"
      >
        <h2 className="text-lg font-semibold text-slate-50">鎴愭湰缁熻</h2>
        <div className="mt-4 space-y-3 text-sm text-slate-300">
          <OverviewRow
            label="Prompt Tokens"
            value={formatTokenCount(props.totalPromptTokens)}
          />
          <OverviewRow
            label="Completion Tokens"
            value={formatTokenCount(props.totalCompletionTokens)}
          />
          <OverviewRow
            label="浼扮畻鎴愭湰"
            value={formatCurrencyUsd(props.totalEstimatedCost)}
          />
        </div>
        <p className="mt-4 text-xs leading-5 text-slate-500">
          褰撳墠鎴愭湰鏉ヨ嚜 Day 9 鐨勫惎鍙戝紡浼扮畻锛岀敤浜庢帶鍒跺彴灞曠ず锛屼笉绛夊悓浜庣湡瀹炴ā鍨嬪巶鍟嗚处鍗曘€?
        </p>
      </div>
    </aside>
  );
}

function OverviewRow(props: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <span className="text-slate-400">{props.label}</span>
      <span className="font-medium text-slate-100">{props.value}</span>
    </div>
  );
}
