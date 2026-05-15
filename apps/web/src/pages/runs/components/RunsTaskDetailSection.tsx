import { useState } from "react";

import { StatusBadge } from "../../../components/StatusBadge";
import { formatCurrencyUsd, formatDateTime, formatTokenCount } from "../../../lib/format";
import { useTaskDetail } from "../../../features/task-detail/hooks";
import { useSelectedTaskRun } from "../../../features/task-detail/useSelectedTaskRun";
import { useSelectedRunRuntimeContract } from "../../../features/task-detail/useSelectedRunRuntimeContract";
import { TaskDetailRuntimeContractSection } from "../../../features/task-detail/components/TaskDetailRuntimeContractSection";
import type { ConsoleBudget, ConsoleTask } from "../../../features/console/types";
import type { StreamConnectionStatus } from "../../../features/events/types";
import {
  mapFailureCategoryTone,
  mapQualityGateTone,
  mapRunStatusTone,
} from "../../../lib/status";

type RunsTaskDetailSectionProps = {
  runId: string | undefined;
  selectedTask: ConsoleTask | null;
  budget: ConsoleBudget | null;
  realtimeStatus: StreamConnectionStatus;
  onNavigateToDeliverable: (input: {
    projectId: string;
    deliverableId: string;
  }) => void;
  onNavigateToRun: (nextRunId: string, taskId: string) => void;
  onNavigateToStrategyPreview: (input: {
    taskId: string;
    runId?: string | null;
  }) => void;
};

export function RunsTaskDetailSection(props: RunsTaskDetailSectionProps) {
  const detailQuery = useTaskDetail(props.selectedTask?.id ?? null, {
    enablePollingFallback: props.realtimeStatus !== "open",
  });
  const detail = detailQuery.data;
  const { selectedRun } = useSelectedTaskRun({
    taskId: props.selectedTask?.id ?? null,
    detail,
    requestedRunId: props.runId ?? null,
  });
  const {
    runtimeFields,
    roleModelPolicyFields,
    hasRoleModelPolicyData,
  } = useSelectedRunRuntimeContract(selectedRun);

  const currentTaskId = detail?.id ?? props.selectedTask?.id ?? "";

  return (
    <section
      className="flex min-h-0 flex-col overflow-hidden border-l border-[#333333] bg-transparent"
      data-testid="runs-task-detail-section"
    >
      {!props.runId ? (
        <div className="flex flex-1 items-center justify-center px-6">
          <div className="max-w-sm text-center">
            <div className="text-4xl text-zinc-700">&#9654;</div>
            <h2 className="mt-4 text-lg font-semibold text-zinc-300">请选择一条运行记录</h2>
            <p className="mt-2 text-sm leading-6 text-zinc-500">
              从左侧列表中选择一条运行记录，查看任务详情、运行约束、令牌用量与诊断信息。
            </p>
          </div>
        </div>
      ) : !selectedRun ? (
        <div className="flex flex-1 items-center justify-center px-6">
          <p className="text-sm text-zinc-500">
            {detailQuery.isLoading ? "正在加载运行详情..." : "未能找到对应的运行记录。"}
          </p>
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className={`border-b border-[#333333] px-5 py-4 ${
            selectedRun.status === "failed" || selectedRun.status === "blocked"
              ? "border-l-4 border-l-rose-500/50"
              : ""
          }`}>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="truncate text-lg font-semibold text-zinc-100">
                    {props.selectedTask?.title ?? "未命名任务"}
                  </h2>
                  <StatusBadge label={formatRunStatusLabel(selectedRun.status)} tone={mapRunStatusTone(selectedRun.status)} />
                  {selectedRun.failure_category ? (
                    <StatusBadge label={formatFailureCategoryLabel(selectedRun.failure_category)} tone={mapFailureCategoryTone(selectedRun.failure_category)} />
                  ) : null}
                  <StatusBadge
                    label={formatQualityGateShort(selectedRun.quality_gate_passed)}
                    tone={mapQualityGateTone(selectedRun.quality_gate_passed)}
                  />
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-zinc-500">
                  <span>开始 {formatDateTime(selectedRun.started_at)}</span>
                  <span>结束 {formatDateTime(selectedRun.finished_at)}</span>
                  <span className="font-mono text-zinc-400">
                    {formatTokenCount(selectedRun.total_tokens ?? 0)} 令牌
                  </span>
                  <span className="font-mono text-zinc-400">
                    {formatCurrencyUsd(selectedRun.estimated_cost)}
                  </span>
                </div>

                {selectedRun.result_summary ? (
                  <p className="mt-2 line-clamp-2 text-sm leading-6 text-zinc-400">
                    {selectedRun.result_summary}
                  </p>
                ) : null}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-2 border-b border-[#333333] px-5 py-3">
            {props.onNavigateToStrategyPreview ? (
              <ActionBtn
                label="返回策略预览"
                data-testid="goto-strategy-preview-from-task-detail"
                onClick={() =>
                  props.onNavigateToStrategyPreview?.({
                    taskId: currentTaskId,
                    runId: selectedRun.id,
                  })
                }
              />
            ) : null}
            {props.onNavigateToRun ? (
              <ActionBtn
                label="打开运行中心"
                data-testid="goto-run-center-from-task-detail"
                onClick={() => props.onNavigateToRun?.(selectedRun.id, currentTaskId)}
              />
            ) : null}
            <CopyBtn label="复制任务 ID" value={currentTaskId} />
            <CopyBtn label="复制运行 ID" value={selectedRun.id} />
          </div>

          <div className="px-5 py-4">
            <TaskDetailRuntimeContractSection
              taskId={currentTaskId}
              selectedRun={selectedRun}
              runtimeFields={runtimeFields}
              roleModelPolicyFields={roleModelPolicyFields}
              hasRoleModelPolicyData={hasRoleModelPolicyData}
              surfaceVariant="line"
              hideHeaderAndActions
              onNavigateToRun={props.onNavigateToRun}
              onNavigateToStrategyPreview={props.onNavigateToStrategyPreview}
            />
          </div>
        </div>
      )}
    </section>
  );
}

function formatRunStatusLabel(status: string) {
  switch (status) {
    case "succeeded":
      return "已成功";
    case "running":
      return "运行中";
    case "failed":
      return "失败";
    case "cancelled":
      return "已取消";
    default:
      return status;
  }
}

function formatFailureCategoryLabel(category: string | null) {
  switch (category) {
    case "verification_configuration_failed":
      return "验证配置失败";
    case "verification_failed":
      return "验证失败";
    case "execution_failed":
      return "执行失败";
    case "daily_budget_exceeded":
      return "日预算超限";
    case "session_budget_exceeded":
      return "会话预算超限";
    case "retry_limit_exceeded":
      return "重试达到上限";
    default:
      return category ?? "无";
  }
}

function ActionBtn(props: { label: string; onClick: () => void; "data-testid"?: string }) {
  return (
    <button
      type="button"
      data-testid={props["data-testid"]}
      onClick={props.onClick}
      className="rounded border border-[#4a4a4a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:border-zinc-500 hover:bg-[#292929]"
    >
      {props.label}
    </button>
  );
}

function CopyBtn(props: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);

  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(props.value);
          setCopied(true);
          setTimeout(() => setCopied(false), 1600);
        } catch {}
      }}
      className="rounded border border-[#4a4a4a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-400 transition hover:border-zinc-500 hover:text-zinc-100"
    >
      {copied ? "已复制" : props.label}
    </button>
  );
}

function formatQualityGateShort(qualityGatePassed: boolean | null): string {
  if (qualityGatePassed === true) return "闸门放行";
  if (qualityGatePassed === false) return "闸门拦截";
  return "闸门未知";
}
