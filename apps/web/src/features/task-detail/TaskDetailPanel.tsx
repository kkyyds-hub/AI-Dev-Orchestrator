import { useEffect, useMemo, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { formatCurrencyUsd, formatDateTime, formatTokenCount } from "../../lib/format";
import {
  buildLatestRunRuntimeFields,
  buildRoleModelPolicyRuntimeFields,
  hasRoleModelPolicyRuntimeData,
} from "../../lib/latestRunRuntimeContract";
import {
  mapFailureCategoryTone,
  mapQualityGateTone,
  mapRunStatusTone,
} from "../../lib/status";
import type { StreamConnectionStatus } from "../events/types";
import type {
  ConsoleBudget,
  ConsoleRun,
  ConsoleTask,
} from "../console/types";
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
import { DetailField } from "./components/TaskDetailField";
import { TaskDetailEmptyState } from "./components/TaskDetailEmptyState";
import { TaskDetailErrorState } from "./components/TaskDetailErrorState";
import { TaskDetailContextPreviewSection } from "./components/TaskDetailContextPreviewSection";
import { TaskDetailLoadingState } from "./components/TaskDetailLoadingState";
import { TaskDetailPanelHeader } from "./components/TaskDetailPanelHeader";
import { TaskDetailRelatedDeliverablesSection } from "./components/TaskDetailRelatedDeliverablesSection";

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
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  useEffect(() => {
    setSelectedRunId(null);
  }, [selectedTask?.id]);

  useEffect(() => {
    if (!detail?.latest_run) {
      return;
    }

    const hasSelectedRun = detail.runs.some((run) => run.id === selectedRunId);
    if (!selectedRunId || !hasSelectedRun) {
      setSelectedRunId(detail.latest_run.id);
    }
  }, [detail, selectedRunId]);

  useEffect(() => {
    if (!requestedRunId || !detail?.runs.length) {
      return;
    }

    if (detail.runs.some((run) => run.id === requestedRunId)) {
      setSelectedRunId(requestedRunId);
    }
  }, [detail?.runs, requestedRunId]);

  const selectedRun = useMemo(
    () =>
      detail?.runs.find((run) => run.id === selectedRunId) ??
      detail?.latest_run ??
      null,
    [detail, selectedRunId],
  );
  const selectedRunRuntimeContractInput = selectedRun
    ? {
        providerKey: selectedRun.provider_key,
        promptTemplateKey: selectedRun.prompt_template_key,
        promptTemplateVersion: selectedRun.prompt_template_version,
        tokenAccountingMode: selectedRun.token_accounting_mode,
        tokenPricingSource: selectedRun.token_pricing_source,
        promptCharCount: selectedRun.prompt_char_count,
        promptTokens: selectedRun.prompt_tokens,
        completionTokens: selectedRun.completion_tokens,
        totalTokens: selectedRun.total_tokens,
        estimatedCost: selectedRun.estimated_cost,
        providerReceiptId: selectedRun.provider_receipt_id,
        roleModelPolicySource: selectedRun.role_model_policy_source,
        roleModelPolicyDesiredTier: selectedRun.role_model_policy_desired_tier,
        roleModelPolicyAdjustedTier: selectedRun.role_model_policy_adjusted_tier,
        roleModelPolicyFinalTier: selectedRun.role_model_policy_final_tier,
        roleModelPolicyStageOverrideApplied:
          selectedRun.role_model_policy_stage_override_applied,
      }
    : null;
  const selectedRunRuntimeFields = selectedRunRuntimeContractInput
    ? buildLatestRunRuntimeFields(selectedRunRuntimeContractInput)
    : [];
  const selectedRunRoleModelPolicyFields = selectedRunRuntimeContractInput
    ? buildRoleModelPolicyRuntimeFields(selectedRunRuntimeContractInput)
    : [];
  const hasSelectedRunRoleModelPolicyData = selectedRunRuntimeContractInput
    ? hasRoleModelPolicyRuntimeData(selectedRunRuntimeContractInput)
    : false;

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

          <RunCard
            title="最新运行"
            run={detail.latest_run}
            isSelected={detail.latest_run?.id === selectedRun?.id}
            onViewLog={(run) => setSelectedRunId(run.id)}
          />

          {selectedRun ? (
            <div
              data-testid="task-detail-runtime-context"
              className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-4"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-base font-semibold text-slate-50">
                    Task Detail Runtime Contract
                  </h3>
                  <p className="mt-1 text-xs text-slate-300">
                    Task {detail.id}; Run {selectedRun.id}
                  </p>
                </div>
                <StatusBadge
                  label={selectedRun.status}
                  tone={mapRunStatusTone(selectedRun.status)}
                />
              </div>

              {onNavigateToStrategyPreview ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    data-testid="goto-strategy-preview-from-task-detail"
                    onClick={() =>
                      onNavigateToStrategyPreview({
                        taskId: detail.id,
                        runId: selectedRun.id,
                      })
                    }
                    className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-3 py-1.5 text-xs text-cyan-100 transition hover:bg-cyan-500/20"
                  >
                    Back to Strategy Preview
                  </button>
                  {onNavigateToRun ? (
                    <button
                      type="button"
                      data-testid="goto-run-center-from-task-detail"
                      onClick={() => onNavigateToRun(selectedRun.id, detail.id)}
                      className="rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-1.5 text-xs text-slate-200 transition hover:border-cyan-400/40 hover:text-cyan-100"
                    >
                      Open in Run Center
                    </button>
                  ) : null}
                </div>
              ) : onNavigateToRun ? (
                <div className="mt-3">
                  <button
                    type="button"
                    data-testid="goto-run-center-from-task-detail"
                    onClick={() => onNavigateToRun(selectedRun.id, detail.id)}
                    className="rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-1.5 text-xs text-slate-200 transition hover:border-cyan-400/40 hover:text-cyan-100"
                  >
                    Open in Run Center
                  </button>
                </div>
              ) : null}

              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <DetailField
                  testId="task-detail-runtime-field-task_id"
                  label="Task ID"
                  value={detail.id}
                />
                <DetailField
                  testId="task-detail-runtime-field-run_id"
                  label="Run ID"
                  value={selectedRun.id}
                />
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                {selectedRunRuntimeFields.map((field) => (
                  <DetailField
                    key={`task-runtime-${field.key}`}
                    testId={`task-detail-runtime-field-${field.key}`}
                    label={field.label}
                    value={field.value}
                  />
                ))}
              </div>

              {hasSelectedRunRoleModelPolicyData ? (
                <div className="mt-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3">
                  <div className="text-xs uppercase tracking-[0.2em] text-emerald-200">
                    Task Detail Role Model Policy Runtime
                  </div>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                    {selectedRunRoleModelPolicyFields.map((field) => (
                      <DetailField
                        key={`task-policy-${field.key}`}
                        testId={`task-detail-policy-field-${field.key}`}
                        label={field.label}
                        value={field.value}
                      />
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
            <div className="flex items-center justify-between gap-4">
              <h3 className="text-base font-semibold text-slate-50">运行历史</h3>
              <span className="text-xs text-slate-500">共 {detail.runs.length} 条</span>
            </div>

            {detail.runs.length ? (
              <div className="mt-4 max-h-[28rem] space-y-3 overflow-y-auto pr-1">
                {detail.runs.map((run, index) => {
                  const isSelected = run.id === selectedRun?.id;

                  return (
                    <div
                      key={run.id}
                      className={`rounded-xl border p-4 ${
                        isSelected
                          ? "border-cyan-500/40 bg-cyan-500/5"
                          : "border-slate-800 bg-slate-900/70"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <div className="text-sm font-medium text-slate-100">
                            Run #{detail.runs.length - index}
                          </div>
                          <div className="text-xs text-slate-500">
                            创建于 {formatDateTime(run.created_at)}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <StatusBadge label={run.status} tone={mapRunStatusTone(run.status)} />
                          <button
                            type="button"
                            onClick={() => setSelectedRunId(run.id)}
                            className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-200 transition hover:border-cyan-400/40 hover:text-cyan-200"
                          >
                            {isSelected ? "日志中" : "查看日志"}
                          </button>
                          {onNavigateToRun ? (
                            <button
                              type="button"
                              onClick={() => onNavigateToRun(run.id, detail.id)}
                              className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-200 transition hover:border-cyan-400/40 hover:text-cyan-200"
                            >
                              打开运行详情页
                            </button>
                          ) : null}
                        </div>
                      </div>

                      <div className="mt-3 grid gap-3 sm:grid-cols-2">
                        <DetailField
                          label="Token"
                          value={`${formatTokenCount(run.prompt_tokens)} / ${formatTokenCount(run.completion_tokens)}`}
                        />
                        <DetailField
                          label="估算成本"
                          value={formatCurrencyUsd(run.estimated_cost)}
                        />
                        <DetailField label="开始时间" value={formatDateTime(run.started_at)} />
                        <DetailField label="结束时间" value={formatDateTime(run.finished_at)} />
                      </div>

                      <RunNarrative run={run} />
                      <VerificationSection run={run} />
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="mt-4 rounded-xl border border-dashed border-slate-800 bg-slate-950/40 p-4 text-sm text-slate-400">
                这条任务还没有运行历史。你可以先在页面顶部手动触发一次 Worker。
              </div>
            )}
          </div>

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

function RunCard(props: {
  title: string;
  run: ConsoleRun | null;
  isSelected: boolean;
  onViewLog: (run: ConsoleRun) => void;
}) {
  if (!props.run) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
        <h3 className="text-base font-semibold text-slate-50">{props.title}</h3>
        <p className="mt-3 text-sm text-slate-400">这条任务还没有最新运行记录。</p>
      </div>
    );
  }

  const run = props.run;

  return (
    <div
      className={`rounded-xl border p-4 ${
        props.isSelected
          ? "border-cyan-500/40 bg-cyan-500/5"
          : "border-slate-800 bg-slate-950/60"
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-slate-50">{props.title}</h3>
          <p className="mt-1 text-xs text-slate-500">创建于 {formatDateTime(run.created_at)}</p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge label={run.status} tone={mapRunStatusTone(run.status)} />
          <button
            type="button"
            onClick={() => props.onViewLog(run)}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-200 transition hover:border-cyan-400/40 hover:text-cyan-200"
          >
            {props.isSelected ? "日志中" : "查看日志"}
          </button>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <DetailField
          label="Token"
          value={`${formatTokenCount(run.prompt_tokens)} / ${formatTokenCount(run.completion_tokens)}`}
        />
        <DetailField label="估算成本" value={formatCurrencyUsd(run.estimated_cost)} />
        <DetailField label="开始时间" value={formatDateTime(run.started_at)} />
        <DetailField label="结束时间" value={formatDateTime(run.finished_at)} />
      </div>

      <RunNarrative run={run} />
      <VerificationSection run={run} />
    </div>
  );
}

function RunNarrative(props: { run: ConsoleRun }) {
  return (
    <div className="mt-4 space-y-2 text-sm">
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-slate-500">路由原因</div>
        <p className="mt-1 leading-6 text-slate-300">
          {props.run.route_reason ?? "暂无路由说明"}
        </p>
        {props.run.routing_score !== null ? (
          <p className="mt-1 text-xs text-slate-500">
            路由分数：{props.run.routing_score}
          </p>
        ) : null}
        {props.run.routing_score_breakdown.length > 0 ? (
          <div className="mt-2 space-y-2">
            {props.run.routing_score_breakdown.map((item, index) => (
              <div
                key={`${props.run.id}-route-score-${item.code}-${index}`}
                className="rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2"
              >
                <div className="flex items-center justify-between gap-3 text-xs">
                  <span className="font-medium text-slate-100">
                    {item.label}
                    <span className="ml-2 text-slate-400">({item.code})</span>
                  </span>
                  <span
                    className={
                      item.score >= 0 ? "text-emerald-300" : "text-amber-300"
                    }
                  >
                    {item.score >= 0 ? "+" : ""}
                    {item.score.toFixed(1)}
                  </span>
                </div>
                <p className="mt-1 text-xs leading-5 text-slate-400">{item.detail}</p>
              </div>
            ))}
          </div>
        ) : null}
      </div>
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-slate-500">摘要</div>
        <p className="mt-1 leading-6 text-slate-300">
          {props.run.result_summary ?? "暂无运行摘要"}
        </p>
      </div>
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-slate-500">日志路径</div>
        {props.run.log_path ? (
          <code className="mt-1 block break-all text-xs text-cyan-200">
            {props.run.log_path}
          </code>
        ) : (
          <p className="mt-1 text-sm text-slate-500">暂无日志路径</p>
        )}
      </div>
    </div>
  );
}

function VerificationSection(props: { run: ConsoleRun }) {
  const run = props.run;

  return (
    <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h4 className="text-sm font-semibold text-slate-50">验证与质量闸门</h4>
          <p className="mt-1 text-xs text-slate-500">
            展示验证模板/命令、失败分类和是否允许最终进入 `completed`。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge
            label={formatQualityGateLabel(run.quality_gate_passed)}
            tone={mapQualityGateTone(run.quality_gate_passed)}
          />
          {run.failure_category ? (
            <StatusBadge
              label={run.failure_category}
              tone={mapFailureCategoryTone(run.failure_category)}
            />
          ) : null}
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <DetailField label="验证模式" value={run.verification_mode ?? "未记录"} />
        <DetailField
          label="验证模板"
          value={run.verification_template ?? "未使用内置模板"}
        />
        <DetailField
          label="失败分类"
          value={run.failure_category ?? "无"}
        />
        <DetailField
          label="闸门结果"
          value={formatQualityGateLabel(run.quality_gate_passed)}
        />
      </div>

      <div className="mt-4 space-y-2 text-sm">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            验证入口
          </div>
          {run.verification_command ? (
            <code className="mt-1 block break-all text-xs text-cyan-200">
              {run.verification_command}
            </code>
          ) : (
            <p className="mt-1 text-sm text-slate-400">
              {run.verification_template
                ? `使用内置模板 ${run.verification_template}`
                : "未记录显式验证命令"}
            </p>
          )}
        </div>
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            验证摘要
          </div>
          <p className="mt-1 leading-6 text-slate-300">
            {run.verification_summary ?? "暂无验证摘要"}
          </p>
        </div>
      </div>
    </div>
  );
}

function formatQualityGateLabel(qualityGatePassed: boolean | null): string {
  if (qualityGatePassed === true) {
    return "质量闸门放行";
  }

  if (qualityGatePassed === false) {
    return "质量闸门拦截";
  }

  return "闸门未知";
}

