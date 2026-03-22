import { StatusBadge } from "../../../components/StatusBadge";
import { mapTaskStatusTone } from "../../../lib/status";
import type { ProjectSopSnapshot } from "../types";
import {
  PROJECT_STAGE_LABELS,
  TASK_STATUS_LABELS,
} from "../types";

type StageChecklistProps = {
  snapshot: ProjectSopSnapshot;
};

function ChecklistGroup(props: {
  title: string;
  items: string[];
  emptyText: string;
  tone?: "info" | "success" | "warning" | "neutral";
}) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
          {props.title}
        </div>
        <StatusBadge
          label={`${props.items.length} 项`}
          tone={props.tone ?? "neutral"}
        />
      </div>

      {props.items.length > 0 ? (
        <ul className="mt-4 space-y-2">
          {props.items.map((item) => (
            <li
              key={item}
              className="rounded-xl border border-slate-800 bg-slate-900/70 px-3 py-2 text-sm leading-6 text-slate-200"
            >
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm leading-6 text-slate-400">{props.emptyText}</p>
      )}
    </section>
  );
}

export function StageChecklist({ snapshot }: StageChecklistProps) {
  const progressText =
    snapshot.current_stage_task_count > 0
      ? `${snapshot.current_stage_completed_task_count}/${snapshot.current_stage_task_count}`
      : "0/0";

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
              当前 SOP 阶段
            </div>
            <h4 className="mt-3 text-lg font-semibold text-slate-50">
              {snapshot.current_stage_title ??
                PROJECT_STAGE_LABELS[snapshot.current_stage] ??
                snapshot.current_stage}
            </h4>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              {snapshot.current_stage_summary ?? "当前阶段暂无额外说明。"}
            </p>
          </div>

          <div className="grid gap-3 text-sm sm:grid-cols-3">
            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-3">
              <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
                阶段任务完成
              </div>
              <div className="mt-2 text-lg font-semibold text-slate-50">
                {progressText}
              </div>
            </div>
            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-3">
              <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
                下一阶段
              </div>
              <div className="mt-2 text-lg font-semibold text-slate-50">
                {snapshot.next_stage
                  ? (PROJECT_STAGE_LABELS[snapshot.next_stage] ?? snapshot.next_stage)
                  : "最终阶段"}
              </div>
            </div>
            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-3">
              <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
                推进状态
              </div>
              <div className="mt-2">
                <StatusBadge
                  label={
                    snapshot.can_advance === null
                      ? "待评估"
                      : snapshot.can_advance
                        ? "可推进"
                        : "未满足"
                  }
                  tone={
                    snapshot.can_advance === null
                      ? "neutral"
                      : snapshot.can_advance
                        ? "success"
                        : "warning"
                  }
                />
              </div>
            </div>
          </div>
        </div>

        {snapshot.owner_roles.length > 0 ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {snapshot.owner_roles.map((role) => (
              <StatusBadge
                key={role.role_code}
                label={`${role.name}${role.enabled ? "" : "（已停用）"}`}
                tone={role.enabled ? "info" : "warning"}
              />
            ))}
          </div>
        ) : null}
      </section>

      <div className="grid gap-4 xl:grid-cols-3">
        <ChecklistGroup
          title="必需输入"
          items={snapshot.required_inputs}
          emptyText="当前模板没有额外输入清单。"
          tone="info"
        />
        <ChecklistGroup
          title="阶段产出"
          items={snapshot.expected_outputs}
          emptyText="当前模板没有额外产出清单。"
          tone="success"
        />
        <ChecklistGroup
          title="守卫条件"
          items={snapshot.guard_conditions}
          emptyText="当前模板没有额外守卫条件。"
          tone="warning"
        />
      </div>

      <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            当前阶段模板任务
          </div>
          <StatusBadge
            label={`${snapshot.stage_tasks.length} 项`}
            tone={snapshot.all_current_stage_tasks_completed ? "success" : "warning"}
          />
        </div>

        {snapshot.stage_tasks.length > 0 ? (
          <div className="mt-4 space-y-3">
            {snapshot.stage_tasks.map((task) => (
              <article
                key={task.task_id}
                className="rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-4"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h5 className="text-sm font-medium text-slate-100">
                        {task.title}
                      </h5>
                      <StatusBadge
                        label={TASK_STATUS_LABELS[task.status] ?? task.status}
                        tone={mapTaskStatusTone(task.status)}
                      />
                    </div>
                    {task.owner_role_names.length > 0 ? (
                      <p className="mt-2 text-xs leading-6 text-slate-400">
                        责任角色：{task.owner_role_names.join(" / ")}
                      </p>
                    ) : null}
                  </div>

                  <div className="text-xs text-slate-500">
                    模板任务码：{task.task_code || "未命名"}
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="mt-4 text-sm leading-6 text-slate-400">
            当前阶段还没有模板任务；如果这是新绑定的模板，可重试同步一次。
          </p>
        )}
      </section>
    </div>
  );
}
