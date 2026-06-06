import { StatusBadge } from "../../components/StatusBadge";
import { WorkerDeliveryGateEvidenceCard } from "../../features/task-actions/WorkerDeliveryGateEvidenceCard";
import { WorkerGitDiffDryRunEvidenceCard } from "../../features/task-actions/WorkerGitDiffDryRunEvidenceCard";
import { WorkerGitOperationDryRunPreviewCard } from "../../features/task-actions/WorkerGitOperationDryRunPreviewCard";
import { WorkerMemoryRecallCard } from "../../features/task-actions/WorkerMemoryRecallCard";
import { WorkerProviderPromptTokenCard } from "../../features/task-actions/WorkerProviderPromptTokenCard";
import { WorkerRoleModelPolicyCard } from "../../features/task-actions/WorkerRoleModelPolicyCard";
import { WorkerRuntimeLaunchGateEvidenceCard } from "../../features/task-actions/WorkerRuntimeLaunchGateEvidenceCard";
import type { WorkerRunOnceResponse } from "../../features/task-actions/types";
import { formatDateTime } from "../../lib/format";

type ManualRunResultSectionProps = {
  data: WorkerRunOnceResponse | undefined;
  isError: boolean;
  errorMessage: string | null;
  onNavigateToProjectDrilldown: (detail: {
    source: "home_latest_run" | "home_manual_run";
    taskId: string;
    runId?: string | null;
  }) => void;
};

export function ManualRunResultSection(props: ManualRunResultSectionProps) {
  if (!props.data && !props.isError) {
    return null;
  }

  return (
    <section
      data-testid="home-manual-run-result-section"
      className={`border-b border-[#333333] pb-5 ${
        props.isError ? "border-rose-500/50" : ""
      }`}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-zinc-50">最近一次手动执行</h2>
          <p className={`mt-1 text-sm ${props.isError ? "text-rose-100" : "text-zinc-300"}`}>
            {props.isError ? props.errorMessage : props.data?.message}
          </p>
        </div>
        {!props.isError && props.data ? (
          <StatusBadge label={props.data.claimed ? "已处理任务" : "未领取任务"} tone={props.data.claimed ? "success" : "warning"} />
        ) : null}
      </div>

      {!props.isError && props.data?.task_title ? (
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          <MiniInfo label="任务" value={props.data.task_title} />
          <MiniInfo label="运行状态" value={formatRunStatusLabel(props.data.run_status)} />
          <MiniInfo
            label="分配评分"
            value={props.data.routing_score !== null && props.data.routing_score !== undefined ? String(props.data.routing_score) : "-"}
          />
          <MiniInfo label="运行 ID" value={props.data.run_id ?? "-"} />
          <MiniInfo label="创建时间" value={formatDateTime(props.data.run_created_at)} />
          <MiniInfo label="完成时间" value={formatDateTime(props.data.run_finished_at)} />
        </div>
      ) : null}

      {!props.isError && props.data?.task_id && props.data?.run_id ? (
        <div className="mt-3">
          <button
            type="button"
            data-testid="home-manual-run-drilldown"
            onClick={() =>
              props.onNavigateToProjectDrilldown({
                source: "home_manual_run",
                taskId: props.data?.task_id as string,
                runId: props.data?.run_id,
              })
            }
            className="rounded border border-[#4a4a4a] bg-transparent px-4 py-2 text-sm font-medium text-zinc-100 transition hover:bg-[#292929]"
          >
            查看项目上下文
          </button>
        </div>
      ) : null}

      {!props.isError && props.data?.route_reason ? (
        <div className="mt-3 border-l border-[#333333] px-4 py-3">
          <div className="text-xs tracking-[0.16em] text-zinc-500">分配说明</div>
          <p className="mt-2 text-sm leading-6 text-zinc-300">{props.data.route_reason}</p>
        </div>
      ) : null}

      {!props.isError && (props.data?.model_name || props.data?.selected_skill_names.length) ? (
        <div className="mt-3 border-l border-[#333333] px-4 py-3">
          <div className="text-xs tracking-[0.16em] text-zinc-500">策略结果</div>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <MiniInfo
              label="模型"
              value={
                props.data?.model_name
                  ? `${props.data.model_name}${props.data.model_tier ? ` (${props.data.model_tier})` : ""}`
                  : "-"
              }
            />
            <MiniInfo label="策略代码" value={props.data?.strategy_code ?? "-"} />
          </div>
          {props.data?.strategy_summary ? <p className="mt-3 text-sm leading-6 text-zinc-300">{props.data.strategy_summary}</p> : null}
          {props.data?.selected_skill_names.length ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {props.data.selected_skill_names.map((skillName) => (
                <span key={`${skillName}-${props.data?.run_id ?? "run"}`} className="rounded-full border border-[#333333] bg-[#1f1f1f] px-3 py-1 text-xs text-zinc-300">
                  {skillName}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      {!props.isError && props.data ? <WorkerRoleModelPolicyCard {...props.data} /> : null}
      {!props.isError && props.data ? (
        <WorkerRuntimeLaunchGateEvidenceCard {...props.data} />
      ) : null}
      {!props.isError && props.data ? (
        <WorkerGitDiffDryRunEvidenceCard {...props.data} />
      ) : null}
      {!props.isError && props.data ? (
        <WorkerGitOperationDryRunPreviewCard {...props.data} />
      ) : null}
      {!props.isError && props.data ? (
        <WorkerDeliveryGateEvidenceCard {...props.data} />
      ) : null}

      {!props.isError && props.data ? <div className="mt-3 text-xs tracking-[0.16em] text-zinc-500">模型调用信息</div> : null}
      {!props.isError && props.data ? <WorkerProviderPromptTokenCard {...props.data} /> : null}
      {!props.isError && props.data ? <WorkerMemoryRecallCard {...props.data} /> : null}
    </section>
  );
}

function formatRunStatusLabel(status: string | null | undefined) {
  if (!status) {
    return "-";
  }

  const labels: Record<string, string> = {
    queued: "排队中",
    running: "运行中",
    succeeded: "成功",
    completed: "已完成",
    failed: "失败",
    cancelled: "已取消",
  };

  return labels[status] ?? status;
}

function MiniInfo(props: { label: string; value: string }) {
  return (
    <div className="border-l border-[#333333] px-4 py-2">
      <div className="text-xs tracking-[0.16em] text-zinc-500">{props.label}</div>
      <div className="mt-1 break-all text-sm font-medium text-zinc-100">{props.value}</div>
    </div>
  );
}
