import { StatusBadge } from "../../components/StatusBadge";
import { WorkerDeliveryGateEvidenceCard } from "../../features/task-actions/WorkerDeliveryGateEvidenceCard";
import { WorkerFailureRecoveryDecisionCard } from "../../features/task-actions/WorkerFailureRecoveryDecisionCard";
import { WorkerGitDiffDryRunEvidenceCard } from "../../features/task-actions/WorkerGitDiffDryRunEvidenceCard";
import { WorkerGitOperationDryRunPreviewCard } from "../../features/task-actions/WorkerGitOperationDryRunPreviewCard";
import { WorkerRuntimeLaunchGateEvidenceCard } from "../../features/task-actions/WorkerRuntimeLaunchGateEvidenceCard";
import type { WorkerPoolRunResponse } from "../../features/task-actions/types";

type WorkerPoolResultSectionProps = {
  data: WorkerPoolRunResponse | undefined;
  isError: boolean;
  errorMessage: string | null;
};

export function WorkerPoolResultSection(props: WorkerPoolResultSectionProps) {
  if (!props.data && !props.isError) {
    return null;
  }

  return (
    <section
      data-testid="home-worker-pool-result-section"
      className={`border-b border-[#333333] pb-5 px-0 py-0 ${
        props.isError ? "border-rose-500/50" : ""
      }`}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-zinc-50">最近一次批量执行</h2>
          <p className={`mt-1 text-sm ${props.isError ? "text-rose-100" : "text-zinc-300"}`}>
            {props.isError
              ? props.errorMessage
              : `请求 ${props.data?.requested_workers} 个槽位，启动 ${props.data?.launched_workers} 个执行器，领取 ${props.data?.claimed_runs} 个任务。`}
          </p>
        </div>
        {!props.isError && props.data ? <StatusBadge label={`${props.data.slot_snapshot.running_slots} 个槽位运行中`} tone="neutral" /> : null}
      </div>

      {!props.isError && props.data?.results.length ? (
        <div className="mt-4 space-y-3">
          {props.data.results.map((result, index) => (
            <div
              key={result.run_id ?? result.task_id ?? `worker-result-${index}`}
              className="rounded-xl border border-[#333333] bg-transparent p-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">
                  Worker #{index + 1} runtime gate evidence
                </div>
                <span className="text-xs text-zinc-400">
                  {result.task_title ?? result.message}
                </span>
              </div>
              <WorkerRuntimeLaunchGateEvidenceCard {...result} />
              <WorkerGitDiffDryRunEvidenceCard {...result} />
              <WorkerGitOperationDryRunPreviewCard {...result} />
              <WorkerDeliveryGateEvidenceCard {...result} />
              <WorkerFailureRecoveryDecisionCard
                decision={result.failure_recovery_decision}
              />
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
