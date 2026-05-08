import { StatusBadge } from "../../components/StatusBadge";
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
      className={`rounded-2xl border px-4 py-3 ${
        props.isError
          ? "border-rose-500/25 bg-rose-500/10"
          : "border-slate-800 bg-slate-950/55"
      }`}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-50">Latest Worker Pool run</h2>
          <p className={`mt-1 text-sm ${props.isError ? "text-rose-100" : "text-slate-300"}`}>
            {props.isError
              ? props.errorMessage
              : `Requested ${props.data?.requested_workers} slots, launched ${props.data?.launched_workers} workers, claimed ${props.data?.claimed_runs} tasks.`}
          </p>
        </div>
        {!props.isError && props.data ? (
          <StatusBadge
            label={`${props.data.slot_snapshot.running_slots} slots running`}
            tone="info"
          />
        ) : null}
      </div>
    </section>
  );
}
