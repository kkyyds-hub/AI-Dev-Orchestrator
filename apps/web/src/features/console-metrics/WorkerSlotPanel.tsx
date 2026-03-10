import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { useWorkerSlots } from "./hooks";

export function WorkerSlotPanel() {
  const workerSlotsQuery = useWorkerSlots();
  const overview = workerSlotsQuery.data;

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-50">Worker 槽位</h2>
          <p className="mt-1 text-sm text-slate-400">
            展示固定并行槽位、等待压力和预算守卫状态，避免并行执行变成黑盒。
          </p>
        </div>
        <StatusBadge
          label={
            workerSlotsQuery.isLoading
              ? "加载中"
              : workerSlotsQuery.isError
                ? "加载失败"
                : "已接通"
          }
          tone={
            workerSlotsQuery.isLoading
              ? "warning"
              : workerSlotsQuery.isError
                ? "danger"
                : "success"
          }
        />
      </div>

      {workerSlotsQuery.isError ? (
        <div className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
          无法加载槽位状态：{workerSlotsQuery.error.message}
        </div>
      ) : null}

      {overview ? (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="最大并行" value={String(overview.slot_snapshot.max_concurrent_workers)} />
            <Metric
              label="运行中 / 空闲"
              value={`${overview.slot_snapshot.running_slots} / ${overview.slot_snapshot.idle_slots}`}
            />
            <Metric
              label="待处理 / 运行中任务"
              value={`${overview.pending_tasks} / ${overview.running_tasks}`}
            />
            <Metric
              label="预算守卫"
              value={overview.budget_guard_active ? "已告警" : "正常"}
            />
          </div>

          <div className="mt-4 space-y-3">
            {overview.slot_snapshot.slots.map((slot) => (
              <div
                key={slot.slot_id}
                className="rounded-xl border border-slate-800 bg-slate-950/60 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-slate-100">
                      槽位 #{slot.slot_id}
                    </div>
                    <div className="mt-1 text-xs text-slate-500">
                      {slot.worker_name ?? "当前未分配 worker 标识"}
                    </div>
                  </div>
                  <StatusBadge
                    label={slot.state === "running" ? "运行中" : "空闲"}
                    tone={slot.state === "running" ? "info" : "neutral"}
                  />
                </div>

                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <Metric label="当前任务" value={slot.task_title ?? "—"} />
                  <Metric
                    label="当前 Run"
                    value={slot.run_id ? slot.run_id.slice(0, 8) : "—"}
                  />
                  <Metric
                    label="占用开始"
                    value={slot.acquired_at ? formatDateTime(slot.acquired_at) : "—"}
                  />
                  <Metric
                    label="最近释放"
                    value={slot.last_released_at ? formatDateTime(slot.last_released_at) : "—"}
                  />
                </div>

                {slot.last_task_title ? (
                  <div className="mt-3 rounded-xl border border-slate-800 bg-slate-900/70 p-3 text-sm text-slate-300">
                    最近一次处理：{slot.last_task_title}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}

function Metric(props: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{props.label}</div>
      <div className="mt-2 break-all text-sm font-medium text-slate-100">{props.value}</div>
    </div>
  );
}
