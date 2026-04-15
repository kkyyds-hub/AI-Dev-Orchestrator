import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

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
  mapTaskStatusTone,
} from "../../lib/status";
import type { StreamConnectionStatus } from "../events/types";
import type {
  ConsoleBudget,
  ConsoleRun,
  ConsoleTask,
  TaskBlockingSignal,
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
import {
  DELIVERABLE_TYPE_LABELS,
  type TaskRelatedDeliverable,
} from "../deliverables/types";
import { RunLogPanel } from "../run-log/RunLogPanel";
import { useTaskDetail } from "./hooks";

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
};

export function TaskDetailPanel({
  panelId,
  runLogPanelId,
  requestedRunId = null,
  selectedTask,
  budget,
  realtimeStatus,
  onNavigateToDeliverable,
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
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-50">任务详情</h2>
          <p className="text-sm text-slate-400">
            {selectedTask
              ? "查看单任务的结构化上下文、决策历史、质量闸门结果、最小操作入口和运行日志。"
              : "从左侧任务列表中选择一条任务，打开 Day 15 详情侧板。"}
          </p>
        </div>
        {selectedTask ? <StatusBadge label="详情已启用" tone="info" /> : null}
      </div>

      {!selectedTask ? (
        <EmptyPanel />
      ) : detailQuery.isError ? (
        <ErrorPanel message={detailQuery.error.message} />
      ) : detailQuery.isLoading && !detail ? (
        <LoadingPanel title={selectedTask.title} />
      ) : detail ? (
        <div className="mt-4 space-y-4">
          <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-1">
                <h3 className="text-lg font-semibold text-slate-50">{detail.title}</h3>
                <p className="text-xs text-slate-500">Task ID：{detail.id}</p>
              </div>
              <StatusBadge label={detail.status} tone={mapTaskStatusTone(detail.status)} />
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <DetailField label="优先级" value={detail.priority} />
              <DetailField label="风险等级" value={detail.risk_level} />
              <DetailField label="人工状态" value={detail.human_status} />
              <DetailField label="验收项数量" value={String(detail.acceptance_criteria.length)} />
              <DetailField label="依赖数量" value={String(detail.depends_on_task_ids.length)} />
              <DetailField label="创建时间" value={formatDateTime(detail.created_at)} />
              <DetailField label="更新时间" value={formatDateTime(detail.updated_at)} />
              <DetailField label="运行次数" value={String(detail.runs.length)} />
            </div>

            <div className="mt-4">
              <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                输入摘要
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-300">
                {detail.input_summary}
              </p>
            </div>

            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                  验收标准
                </div>
                {detail.acceptance_criteria.length > 0 ? (
                  <ul className="mt-2 space-y-2 text-sm text-slate-300">
                    {detail.acceptance_criteria.map((criterion, index) => (
                      <li key={`${detail.id}-criterion-${index}`} className="rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2">
                        {criterion}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-sm text-slate-500">暂无显式验收标准</p>
                )}
              </div>

              <div className="space-y-4">
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                    依赖任务
                  </div>
                  {detail.depends_on_task_ids.length > 0 ? (
                    <div className="mt-2 space-y-2">
                      {detail.depends_on_task_ids.map((dependencyId) => (
                        <code
                          key={dependencyId}
                          className="block break-all rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2 text-xs text-cyan-200"
                        >
                          {dependencyId}
                        </code>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-2 text-sm text-slate-500">无前置依赖</p>
                  )}
                </div>

                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                    暂停说明
                  </div>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-300">
                    {detail.paused_reason ?? "未设置暂停说明"}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-base font-semibold text-slate-50">关联交付件</h3>
                <p className="mt-1 text-sm text-slate-400">
                  反查当前任务及其运行记录对应的 PRD、设计稿、代码计划或验收结论快照。
                </p>
              </div>
              <StatusBadge
                label={`${relatedDeliverablesQuery.data?.length ?? 0} 条关联`}
                tone="info"
              />
            </div>

            {relatedDeliverablesQuery.isLoading && !relatedDeliverablesQuery.data ? (
              <p className="mt-4 text-sm leading-6 text-slate-400">
                正在查询关联交付件...
              </p>
            ) : relatedDeliverablesQuery.isError ? (
              <p className="mt-4 text-sm leading-6 text-rose-200">
                关联交付件加载失败：{relatedDeliverablesQuery.error.message}
              </p>
            ) : relatedDeliverablesQuery.data &&
              relatedDeliverablesQuery.data.length > 0 ? (
              <div className="mt-4 space-y-3">
                {relatedDeliverablesQuery.data.map((relatedItem) => (
                  <RelatedDeliverableCard
                    key={`${relatedItem.deliverable_id}-${relatedItem.matched_version.id}`}
                    item={relatedItem}
                    onNavigateToDeliverable={onNavigateToDeliverable}
                  />
                ))}
              </div>
            ) : (
              <div className="mt-4 rounded-xl border border-dashed border-slate-800 bg-slate-950/40 p-4 text-sm leading-6 text-slate-400">
                当前任务或其运行记录还没有关联的交付件快照。
              </div>
            )}
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-base font-semibold text-slate-50">最小上下文包</h3>
                <p className="mt-1 text-sm text-slate-400">
                  Worker 在执行前会聚合任务目标、依赖状态、最近运行片段和阻塞信号。
                </p>
              </div>
              <StatusBadge
                label={
                  detail.context_preview.ready_for_execution ? "上下文就绪" : "存在阻塞信号"
                }
                tone={detail.context_preview.ready_for_execution ? "success" : "warning"}
              />
            </div>

            <div className="mt-4 rounded-xl border border-slate-800 bg-slate-900/70 p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                上下文摘要
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-300">
                {detail.context_preview.context_summary}
              </p>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <DetailField
                label="上下文状态"
                value={detail.context_preview.ready_for_execution ? "可执行" : "需人工关注"}
              />
              <DetailField
                label="最近运行片段"
                value={String(detail.context_preview.recent_runs.length)}
              />
              <DetailField
                label="依赖摘要"
                value={String(detail.context_preview.dependency_items.length)}
              />
              <DetailField
                label="阻塞项"
                value={String(detail.context_preview.blocking_signals.length)}
              />
            </div>

            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                  依赖状态
                </div>
                {detail.context_preview.dependency_items.length > 0 ? (
                  <div className="mt-2 space-y-3">
                    {detail.context_preview.dependency_items.map((dependency) => (
                      <div
                        key={dependency.task_id}
                        className="rounded-xl border border-slate-800 bg-slate-900/70 p-3"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="text-sm font-medium text-slate-100">
                              {dependency.title}
                            </div>
                            <code className="mt-1 block break-all text-xs text-cyan-200">
                              {dependency.task_id}
                            </code>
                          </div>
                          <StatusBadge
                            label={dependency.status}
                            tone={mapTaskStatusTone(dependency.status)}
                          />
                        </div>
                        <p className="mt-3 text-sm leading-6 text-slate-300">
                          {dependency.missing
                            ? "依赖任务不存在，需先补齐或重建。"
                            : dependency.latest_run_summary ?? "暂无依赖运行摘要"}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-slate-500">无前置依赖，上下文更轻量。</p>
                )}
              </div>

              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                  最近运行摘要
                </div>
                {detail.context_preview.recent_runs.length > 0 ? (
                  <div className="mt-2 space-y-3">
                    {detail.context_preview.recent_runs.map((run) => (
                      <div
                        key={run.run_id}
                        className="rounded-xl border border-slate-800 bg-slate-900/70 p-3"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="text-sm font-medium text-slate-100">
                              {formatDateTime(run.created_at)}
                            </div>
                            <code className="mt-1 block break-all text-xs text-cyan-200">
                              {run.run_id}
                            </code>
                          </div>
                          <StatusBadge
                            label={run.status}
                            tone={mapRunStatusTone(run.status)}
                          />
                        </div>
                        <p className="mt-3 text-sm leading-6 text-slate-300">
                          {run.result_summary ?? "暂无运行摘要"}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-slate-500">这是首次执行，没有历史运行片段。</p>
                )}
              </div>
            </div>

            <div className="mt-4">
              <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                阻塞信号
              </div>
              {detail.context_preview.blocking_signals.length > 0 ? (
                <div className="mt-2 space-y-2">
                  {detail.context_preview.blocking_signals.map((signal, index) => (
                    <div
                      key={`${detail.id}-context-block-${signal.code}-${index}`}
                      className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-100"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="font-medium text-amber-50">
                          {mapBlockingCategoryLabel(signal)}
                        </div>
                        <code className="text-[11px] uppercase tracking-[0.12em] text-amber-200">
                          {signal.code}
                        </code>
                      </div>
                      <div className="mt-2 leading-6 text-amber-100">{signal.message}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mt-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-100">
                  当前没有显式阻塞信号；Worker 会按此上下文继续执行。
                </div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h3 className="text-base font-semibold text-slate-50">任务操作</h3>
                <p className="mt-1 text-sm text-slate-400">
                  支持显式暂停、人工介入和失败重试；所有动作都只更新当前任务状态，不复制任务记录。
                </p>
              </div>
              <div className="flex flex-wrap items-center justify-end gap-2">
                <ActionButton
                  label="暂停任务"
                  pendingLabel="暂停中..."
                  tone="amber"
                  disabled={!canPause || isActionPending}
                  isPending={pauseMutation.isPending}
                  onClick={() => pauseMutation.mutate(detail.id)}
                />
                <ActionButton
                  label="恢复任务"
                  pendingLabel="恢复中..."
                  tone="emerald"
                  disabled={!canResume || isActionPending}
                  isPending={resumeMutation.isPending}
                  onClick={() => resumeMutation.mutate(detail.id)}
                />
                <ActionButton
                  label="请求人工"
                  pendingLabel="提交中..."
                  tone="violet"
                  disabled={!canRequestHuman || isActionPending}
                  isPending={requestHumanMutation.isPending}
                  onClick={() => requestHumanMutation.mutate(detail.id)}
                />
                <ActionButton
                  label="人工已处理"
                  pendingLabel="恢复中..."
                  tone="emerald"
                  disabled={!canResolveHuman || isActionPending}
                  isPending={resolveHumanMutation.isPending}
                  onClick={() => resolveHumanMutation.mutate(detail.id)}
                />
                <ActionButton
                  label="重试任务"
                  pendingLabel="重试中..."
                  tone="cyan"
                  disabled={!canTriggerRetry || isActionPending}
                  isPending={retryMutation.isPending}
                  onClick={() => retryMutation.mutate(detail.id)}
                />
              </div>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <DetailField
                label="当前状态"
                value={
                  <StatusBadge
                    label={detail.status}
                    tone={mapTaskStatusTone(detail.status)}
                  />
                }
              />
              <DetailField
                label="重试资格"
                value={
                  retryLimitReached
                    ? "已达到重试上限"
                    : canRetry
                      ? "允许"
                      : "仅 failed / blocked 可重试"
                }
              />
              <DetailField
                label="已执行次数"
                value={String(executionAttempts)}
              />
              <DetailField
                label="已用重试 / 上限"
                value={
                  budget
                    ? `${retriesUsed} / ${budget.max_task_retries}`
                    : "预算未加载"
                }
              />
              <DetailField
                label="剩余重试"
                value={budget ? String(retriesRemaining) : "预算未加载"}
              />
              <DetailField
                label="预算状态"
                value={formatBudgetHealthLabel(budget)}
              />
            </div>

            {retryLimitReached ? (
              <div className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-100">
                当前任务已达到 Day 15 重试上限。若要继续尝试，请先提高 `MAX_TASK_RETRIES`
                或人工处理任务输入后再重试。
              </div>
            ) : null}

            {pauseResult ? (
              <StateActionNotice
                title="暂停已生效"
                message={pauseResult.message}
                previousStatus={pauseResult.previous_status}
                currentStatus={pauseResult.current_status}
              />
            ) : null}

            {resumeResult ? (
              <StateActionNotice
                title="任务已恢复"
                message={resumeResult.message}
                previousStatus={resumeResult.previous_status}
                currentStatus={resumeResult.current_status}
              />
            ) : null}

            {requestHumanResult ? (
              <StateActionNotice
                title="已请求人工处理"
                message={requestHumanResult.message}
                previousStatus={requestHumanResult.previous_status}
                currentStatus={requestHumanResult.current_status}
              />
            ) : null}

            {resolveHumanResult ? (
              <StateActionNotice
                title="人工处理已完成"
                message={resolveHumanResult.message}
                previousStatus={resolveHumanResult.previous_status}
                currentStatus={resolveHumanResult.current_status}
              />
            ) : null}

            {retryResult ? (
              <StateActionNotice
                title="重试已触发"
                message={retryResult.message}
                previousStatus={retryResult.previous_status}
                currentStatus={retryResult.current_status}
              />
            ) : null}

            {pauseError ? (
              <ActionError title="暂停失败" message={pauseError} />
            ) : null}

            {resumeError ? (
              <ActionError title="恢复失败" message={resumeError} />
            ) : null}

            {requestHumanError ? (
              <ActionError title="请求人工失败" message={requestHumanError} />
            ) : null}

            {resolveHumanError ? (
              <ActionError title="恢复人工任务失败" message={resolveHumanError} />
            ) : null}

            {retryError ? (
              <ActionError title="重试失败" message={retryError} />
            ) : null}
          </div>

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

              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <DetailField label="Task ID" value={detail.id} />
                <DetailField label="Run ID" value={selectedRun.id} />
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                {selectedRunRuntimeFields.map((field) => (
                  <DetailField
                    key={`task-runtime-${field.key}`}
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

          <RunLogPanel panelId={runLogPanelId} selectedRun={selectedRun} />
        </div>
      ) : null}
    </section>
  );
}

function RelatedDeliverableCard(props: {
  item: TaskRelatedDeliverable;
  onNavigateToDeliverable?: (input: {
    projectId: string;
    deliverableId: string;
  }) => void;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-sm font-medium text-slate-50">{props.item.title}</div>
            <StatusBadge
              label={DELIVERABLE_TYPE_LABELS[props.item.type]}
              tone="info"
            />
            <StatusBadge label={`v${props.item.matched_version.version_number}`} tone="neutral" />
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            {props.item.matched_version.summary}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <StatusBadge label={props.item.stage} tone="neutral" />
          {props.item.matched_version.source_run_id ? (
            <StatusBadge label="来自运行快照" tone="success" />
          ) : (
            <StatusBadge label="来自任务快照" tone="warning" />
          )}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
        <span>交付件 ID：{props.item.deliverable_id}</span>
        <span>最新版本：v{props.item.current_version_number}</span>
        <span>快照时间：{formatDateTime(props.item.matched_version.created_at)}</span>
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        {props.onNavigateToDeliverable ? (
          <button
            type="button"
            onClick={() =>
              props.onNavigateToDeliverable?.({
                projectId: props.item.project_id,
                deliverableId: props.item.deliverable_id,
              })
            }
            className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 transition hover:bg-cyan-500/20"
          >
            跳到交付件中心
          </button>
        ) : null}
        {props.item.matched_version.source_run_id ? (
          <code className="rounded-lg border border-slate-800 bg-slate-950/70 px-3 py-2 text-xs text-slate-400">
            Run {props.item.matched_version.source_run_id}
          </code>
        ) : null}
      </div>
    </div>
  );
}

function mapBlockingCategoryLabel(signal: TaskBlockingSignal): string {
  if (signal.category === "dependency") {
    return "依赖阻塞";
  }
  if (signal.category === "human") {
    return "人工阻塞";
  }
  if (signal.category === "pause") {
    return "暂停阻塞";
  }
  if (signal.category === "budget") {
    return "预算阻塞";
  }
  return "状态阻塞";
}

function EmptyPanel() {
  return (
    <div className="mt-4 rounded-xl border border-dashed border-slate-800 bg-slate-950/40 p-4 text-sm text-slate-400">
      点击左侧任意任务后，这里会展示任务基础信息、最新运行、质量闸门结果和结构化日志事件。
    </div>
  );
}

function LoadingPanel(props: { title: string }) {
  return (
    <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-sm text-slate-300">
      正在加载 <span className="font-medium text-slate-100">{props.title}</span> 的详情数据…
    </div>
  );
}

function ErrorPanel(props: { message: string }) {
  return (
    <div className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
      无法加载任务详情：{props.message}
    </div>
  );
}

function DetailField(props: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{props.label}</div>
      <div className="mt-2 text-sm font-medium text-slate-100">{props.value}</div>
    </div>
  );
}

function ActionButton(props: {
  label: string;
  pendingLabel: string;
  onClick: () => void;
  disabled: boolean;
  isPending: boolean;
  tone: "cyan" | "amber" | "violet" | "emerald";
}) {
  const toneClassName = {
    cyan: "border-cyan-400/30 bg-cyan-500/10 text-cyan-200 hover:bg-cyan-500/20",
    amber:
      "border-amber-400/30 bg-amber-500/10 text-amber-200 hover:bg-amber-500/20",
    violet:
      "border-violet-400/30 bg-violet-500/10 text-violet-200 hover:bg-violet-500/20",
    emerald:
      "border-emerald-400/30 bg-emerald-500/10 text-emerald-200 hover:bg-emerald-500/20",
  }[props.tone];

  return (
    <button
      type="button"
      onClick={props.onClick}
      disabled={props.disabled}
      className={`rounded-lg border px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900 disabled:text-slate-500 ${toneClassName}`}
    >
      {props.isPending ? props.pendingLabel : props.label}
    </button>
  );
}

function StateActionNotice(props: {
  title: string;
  message: string;
  previousStatus: string;
  currentStatus: string;
}) {
  return (
    <div className="mt-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-100">
      <div className="font-medium text-emerald-50">{props.title}</div>
      <p className="mt-1">
        {props.message} 状态已从 `{props.previousStatus}` 更新为 `{props.currentStatus}`。
      </p>
    </div>
  );
}

function ActionError(props: { title: string; message: string }) {
  return (
    <div className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-100">
      {props.title}：{props.message}
    </div>
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

function formatBudgetHealthLabel(budget: ConsoleBudget | null): string {
  if (!budget) {
    return "预算未加载";
  }

  if (budget.daily_budget_exceeded && budget.session_budget_exceeded) {
    return "日预算 / 会话预算均告警";
  }

  if (budget.daily_budget_exceeded) {
    return "日预算告警";
  }

  if (budget.session_budget_exceeded) {
    return "会话预算告警";
  }

  return "预算正常";
}
