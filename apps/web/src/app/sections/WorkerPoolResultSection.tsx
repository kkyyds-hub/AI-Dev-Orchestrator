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
      className={`rounded-2xl border p-4 ${
        props.isError ? "border-rose-500/30 bg-rose-500/10" : "border-cyan-500/30 bg-cyan-500/10"
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-50">鏈€杩戜竴娆?Worker Pool 鎵ц</h2>
          <p className={`mt-1 text-sm ${props.isError ? "text-rose-100" : "text-cyan-100"}`}>
            {props.isError
              ? props.errorMessage
              : `璇锋眰 ${props.data?.requested_workers} 涓Ы浣嶏紝鍚姩 ${props.data?.launched_workers} 涓?worker锛屽疄闄呴鍙?${props.data?.claimed_runs} 鏉′换鍔°€?`}
          </p>
        </div>
        {!props.isError && props.data ? (
          <StatusBadge
            label={`${props.data.slot_snapshot.running_slots} 涓Ы浣嶈繍琛屼腑`}
            tone="info"
          />
        ) : null}
      </div>
    </section>
  );
}
