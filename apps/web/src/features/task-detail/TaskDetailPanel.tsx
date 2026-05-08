import { useMemo } from "react";

import type { StreamConnectionStatus } from "../events/types";
import type { ConsoleBudget, ConsoleTask } from "../console/types";
import {
  usePauseTask,
  useRequestHumanReview,
  useResolveHumanReview,
  useResumeTask,
  useRetryTask,
} from "../task-actions/hooks";
import { DecisionHistoryPanel } from "../console-metrics/DecisionHistoryPanel";
import { useTaskDecisionHistory } from "../console-metrics/decision-hooks";
import { useTaskRelatedDeliverables } from "../deliverables/hooks";
import { RunLogPanel } from "../run-log/RunLogPanel";
import { useTaskDetail } from "./hooks";
import { TaskDetailActionsSection } from "./components/TaskDetailActionsSection";
import { TaskDetailBaseInfoCard } from "./components/TaskDetailBaseInfoCard";
import { TaskDetailEmptyState } from "./components/TaskDetailEmptyState";
import { TaskDetailErrorState } from "./components/TaskDetailErrorState";
import { TaskDetailContextPreviewSection } from "./components/TaskDetailContextPreviewSection";
import { TaskDetailLoadingState } from "./components/TaskDetailLoadingState";
import { TaskDetailPanelHeader } from "./components/TaskDetailPanelHeader";
import { TaskDetailRelatedDeliverablesSection } from "./components/TaskDetailRelatedDeliverablesSection";
import {
  TaskDetailLatestRunCard,
  TaskDetailRunHistorySection,
} from "./components/TaskDetailRunsSection";
import { TaskDetailRuntimeContractSection } from "./components/TaskDetailRuntimeContractSection";
import { useSelectedRunRuntimeContract } from "./useSelectedRunRuntimeContract";
import { useSelectedTaskRun } from "./useSelectedTaskRun";

type TaskDetailPanelProps = {
  panelId?: string;
  runLogPanelId?: string;
  requestedRunId?: string | null;
  selectedTask: ConsoleTask | null;
  budget: ConsoleBudget | null;
  realtimeStatus: StreamConnectionStatus;
  onNavigateToDeliverable?: (input: {
    projectId: string;
    deliverableId: string;
  }) => void;
  onNavigateToRun?: (runId: string, taskId: string) => void;
  onNavigateToStrategyPreview?: (input: {
    taskId: string;
    runId?: string | null;
  }) => void;
};

export function TaskDetailPanel({
  panelId,
  runLogPanelId,
  requestedRunId = null,
  selectedTask,
  budget,
  realtimeStatus,
  onNavigateToDeliverable,
  onNavigateToRun,
  onNavigateToStrategyPreview,
}: TaskDetailPanelProps) {
  const detailQuery = useTaskDetail(selectedTask?.id ?? null, {
    enablePollingFallback: realtimeStatus !== "open",
  });
  const retryMutation = useRetryTask();
  const pauseMutation = usePauseTask();
  const resumeMutation = useResumeTask();
  const requestHumanMutation = useRequestHumanReview();
  const resolveHumanMutation = useResolveHumanReview();
  const detail = detailQuery.data;
  const { selectedRun, setSelectedRunId } = useSelectedTaskRun({
    taskId: selectedTask?.id ?? null,
    detail,
    requestedRunId,
  });
  const {
    runtimeFields: selectedRunRuntimeFields,
    roleModelPolicyFields: selectedRunRoleModelPolicyFields,
    hasRoleModelPolicyData: hasSelectedRunRoleModelPolicyData,
  } = useSelectedRunRuntimeContract(selectedRun);

  const currentTaskId = detail?.id ?? selectedTask?.id ?? null;
  const relatedDeliverablesQuery = useTaskRelatedDeliverables(currentTaskId);
  const decisionHistoryQuery = useTaskDecisionHistory(currentTaskId);
  const currentTaskStatus = detail?.status ?? selectedTask?.status ?? null;
  const canPause =
    currentTaskStatus === "pending" ||
    currentTaskStatus === "failed" ||
    currentTaskStatus === "blocked";
  const canResume = currentTaskStatus === "paused";
  const canRequestHuman =
    currentTaskStatus === "pending" ||
    currentTaskStatus === "failed" ||
    currentTaskStatus === "blocked" ||
    currentTaskStatus === "paused";
  const canResolveHuman = currentTaskStatus === "waiting_human";
  const canRetry =
    currentTaskStatus === "failed" || currentTaskStatus === "blocked";
  const executionAttempts = useMemo(
    () => detail?.runs.filter((run) => run.status !== "cancelled").length ?? 0,
    [detail],
  );
  const retriesUsed = Math.max(executionAttempts - 1, 0);
  const retriesRemaining = budget
    ? Math.max(budget.max_task_retries - retriesUsed, 0)
    : 0;
  const retryLimitReached = budget
    ? executionAttempts > budget.max_task_retries
    : false;
  const canTriggerRetry = canRetry && !retryLimitReached;
  const retryResult =
    retryMutation.data?.task_id === currentTaskId ? retryMutation.data : null;
  const pauseResult =
    pauseMutation.data?.task_id === currentTaskId ? pauseMutation.data : null;
  const resumeResult =
    resumeMutation.data?.task_id === currentTaskId ? resumeMutation.data : null;
  const requestHumanResult =
    requestHumanMutation.data?.task_id === currentTaskId
      ? requestHumanMutation.data
      : null;
  const resolveHumanResult =
    resolveHumanMutation.data?.task_id === currentTaskId
      ? resolveHumanMutation.data
      : null;
  const retryError =
    retryMutation.isError && retryMutation.variables === currentTaskId
      ? retryMutation.error.message
      : null;
  const pauseError =
    pauseMutation.isError && pauseMutation.variables === currentTaskId
      ? pauseMutation.error.message
      : null;
  const resumeError =
    resumeMutation.isError && resumeMutation.variables === currentTaskId
      ? resumeMutation.error.message
      : null;
  const requestHumanError =
    requestHumanMutation.isError && requestHumanMutation.variables === currentTaskId
      ? requestHumanMutation.error.message
      : null;
  const resolveHumanError =
    resolveHumanMutation.isError && resolveHumanMutation.variables === currentTaskId
      ? resolveHumanMutation.error.message
      : null;
  const isActionPending =
    retryMutation.isPending ||
    pauseMutation.isPending ||
    resumeMutation.isPending ||
    requestHumanMutation.isPending ||
    resolveHumanMutation.isPending;

  return (
    <section
      id={panelId}
      className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5"
    >
      <TaskDetailPanelHeader selectedTask={selectedTask} />

      {!selectedTask ? (
        <TaskDetailEmptyState />
      ) : detailQuery.isError ? (
        <TaskDetailErrorState message={detailQuery.error.message} />
      ) : detailQuery.isLoading && !detail ? (
        <TaskDetailLoadingState title={selectedTask.title} />
      ) : detail ? (
        <div className="mt-4 space-y-4">
          <TaskDetailBaseInfoCard detail={detail} />

          <TaskDetailRelatedDeliverablesSection
            relatedDeliverables={relatedDeliverablesQuery.data}
            isLoading={relatedDeliverablesQuery.isLoading}
            isError={relatedDeliverablesQuery.isError}
            errorMessage={relatedDeliverablesQuery.error?.message ?? ""}
            onNavigateToDeliverable={onNavigateToDeliverable}
          />

          <TaskDetailContextPreviewSection contextPreview={detail.context_preview} />

          <TaskDetailActionsSection
            taskId={detail.id}
            status={detail.status}
            budget={budget}
            canPause={canPause}
            canResume={canResume}
            canRequestHuman={canRequestHuman}
            canResolveHuman={canResolveHuman}
            canRetry={canRetry}
            canTriggerRetry={canTriggerRetry}
            isActionPending={isActionPending}
            executionAttempts={executionAttempts}
            retriesUsed={retriesUsed}
            retriesRemaining={retriesRemaining}
            retryLimitReached={retryLimitReached}
            isPausePending={pauseMutation.isPending}
            isResumePending={resumeMutation.isPending}
            isRequestHumanPending={requestHumanMutation.isPending}
            isResolveHumanPending={resolveHumanMutation.isPending}
            isRetryPending={retryMutation.isPending}
            pauseResult={pauseResult}
            resumeResult={resumeResult}
            requestHumanResult={requestHumanResult}
            resolveHumanResult={resolveHumanResult}
            retryResult={retryResult}
            pauseError={pauseError}
            resumeError={resumeError}
            requestHumanError={requestHumanError}
            resolveHumanError={resolveHumanError}
            retryError={retryError}
            onPause={(taskId) => pauseMutation.mutate(taskId)}
            onResume={(taskId) => resumeMutation.mutate(taskId)}
            onRequestHuman={(taskId) => requestHumanMutation.mutate(taskId)}
            onResolveHuman={(taskId) => resolveHumanMutation.mutate(taskId)}
            onRetry={(taskId) => retryMutation.mutate(taskId)}
          />

          <TaskDetailLatestRunCard
            latestRun={detail.latest_run}
            selectedRun={selectedRun}
            onSelectRun={setSelectedRunId}
          />

          <TaskDetailRuntimeContractSection
            taskId={detail.id}
            selectedRun={selectedRun}
            runtimeFields={selectedRunRuntimeFields}
            roleModelPolicyFields={selectedRunRoleModelPolicyFields}
            hasRoleModelPolicyData={hasSelectedRunRoleModelPolicyData}
            onNavigateToRun={onNavigateToRun}
            onNavigateToStrategyPreview={onNavigateToStrategyPreview}
          />

          <TaskDetailRunHistorySection
            taskId={detail.id}
            runs={detail.runs}
            selectedRun={selectedRun}
            onSelectRun={setSelectedRunId}
            onNavigateToRun={onNavigateToRun}
          />

          <DecisionHistoryPanel
            taskId={currentTaskId}
            history={decisionHistoryQuery.data ?? []}
            isLoading={decisionHistoryQuery.isLoading && !decisionHistoryQuery.data}
            errorMessage={decisionHistoryQuery.isError ? decisionHistoryQuery.error.message : null}
            selectedRunId={selectedRun?.id ?? null}
            onSelectRun={setSelectedRunId}
          />

          <RunLogPanel
            panelId={runLogPanelId}
            taskId={detail.id}
            selectedRun={selectedRun}
            onNavigateToStrategyPreview={onNavigateToStrategyPreview}
          />
        </div>
      ) : null}
    </section>
  );
}

