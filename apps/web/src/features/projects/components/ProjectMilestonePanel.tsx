import { StatusBadge } from "../../../components/StatusBadge";
import { mapTaskStatusTone } from "../../../lib/status";
import type { ProjectDetail } from "../types";
import {
  PROJECT_STAGE_LABELS,
  TASK_STATUS_LABELS,
} from "../types";

type ProjectMilestonePanelProps = {
  detail: ProjectDetail | null;
};

export function ProjectMilestonePanel({
  detail,
}: ProjectMilestonePanelProps) {
  const guard = detail?.stage_guard;

  if (!guard) {
    return (
      <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
        <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
          项目里程碑
        </div>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          正在读取当前项目的阶段守卫与里程碑状态...
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            项目里程碑
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-300">
            当前阶段：
            <span className="mx-1 font-medium text-slate-100">
              {PROJECT_STAGE_LABELS[guard.current_stage] ?? guard.current_stage}
            </span>
            {guard.target_stage ? (
              <>
                ，下一阶段：
                <span className="mx-1 font-medium text-slate-100">
                  {PROJECT_STAGE_LABELS[guard.target_stage] ?? guard.target_stage}
                </span>
              </>
            ) : (
              <>，当前已经处于最终阶段。</>
            )}
          </p>
        </div>

        <div className="grid gap-3 text-sm sm:grid-cols-3">
          <SummaryChip label="总任务数" value={String(guard.total_tasks)} />
          <SummaryChip
            label={guard.current_stage_task_count > 0 ? "阶段任务完成" : "可执行任务"}
            value={
              guard.current_stage_task_count > 0
                ? `${guard.current_stage_completed_task_count}/${guard.current_stage_task_count}`
                : String(guard.ready_task_count)
            }
          />
          <SummaryChip
            label="已完成任务"
            value={String(guard.completed_task_count)}
          />
        </div>
      </div>

      {guard.milestones.length > 0 ? (
        <div className="mt-4 grid gap-3 xl:grid-cols-2">
          {guard.milestones.map((milestone) => (
            <article
              key={milestone.code}
              className={`rounded-2xl border px-4 py-4 ${
                milestone.satisfied
                  ? "border-emerald-500/20 bg-emerald-500/5"
                  : "border-amber-500/20 bg-amber-500/5"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h4 className="text-sm font-medium text-slate-100">
                    {milestone.title}
                  </h4>
                  <p className="mt-2 text-sm leading-6 text-slate-300">
                    {milestone.summary}
                  </p>
                </div>

                <StatusBadge
                  label={milestone.satisfied ? "已满足" : "未满足"}
                  tone={milestone.satisfied ? "success" : "warning"}
                />
              </div>

              {milestone.blocking_reasons.length > 0 ? (
                <ul className="mt-3 space-y-2 text-xs leading-6 text-amber-100">
                  {milestone.blocking_reasons.map((reason) => (
                    <li
                      key={reason}
                      className="rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-2"
                    >
                      {reason}
                    </li>
                  ))}
                </ul>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm leading-6 text-slate-400">
          当前没有更多需要检查的阶段里程碑。
        </p>
      )}

      {guard.blocking_tasks.length > 0 ? (
        <div className="mt-5 rounded-2xl border border-amber-500/20 bg-slate-950/80 p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
              当前阻塞任务
            </div>
            <span className="text-xs text-slate-500">
              {guard.blocking_tasks.length} 个
            </span>
          </div>

          <div className="mt-4 space-y-3">
            {guard.blocking_tasks.map((task) => (
              <article
                key={task.task_id}
                className="rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-4"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <div className="text-sm font-medium text-slate-100">
                    {task.title}
                  </div>
                  <StatusBadge
                    label={TASK_STATUS_LABELS[task.status] ?? task.status}
                    tone={mapTaskStatusTone(task.status)}
                  />
                </div>

                <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-300">
                  {task.blocking_reasons.map((reason) => (
                    <li
                      key={`${task.task_id}-${reason}`}
                      className="rounded-xl border border-slate-800 bg-slate-950/70 px-3 py-2"
                    >
                      {reason}
                    </li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </div>
      ) : null}

      {!guard.can_advance && guard.blocking_reasons.length > 0 ? (
        <div className="mt-5 rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm leading-6 text-amber-100">
          {guard.blocking_reasons.join("；")}
        </div>
      ) : null}
    </section>
  );
}

function SummaryChip(props: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
        {props.label}
      </div>
      <div className="mt-2 text-sm font-medium text-slate-100">
        {props.value}
      </div>
    </div>
  );
}
