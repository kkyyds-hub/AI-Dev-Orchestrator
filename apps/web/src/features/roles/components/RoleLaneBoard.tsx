import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import { mapRunStatusTone, mapTaskStatusTone } from "../../../lib/status";
import { HUMAN_STATUS_LABELS, TASK_PRIORITY_LABELS, TASK_STATUS_LABELS } from "../../projects/types";
import type {
  RoleWorkbenchHandoffItem,
  RoleWorkbenchLane,
  RoleWorkbenchTaskItem,
} from "../types";
import { ROLE_CODE_LABELS } from "../types";

type RoleLaneBoardProps = {
  lanes: RoleWorkbenchLane[];
  selectedRoleCode: string | null;
  selectedTaskId: string | null;
  onSelectRole: (roleCode: string) => void;
  onSelectTask: (task: RoleWorkbenchTaskItem) => void;
  onSelectHandoff: (handoff: RoleWorkbenchHandoffItem) => void;
};

export function RoleLaneBoard(props: RoleLaneBoardProps) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-cyan-300">
            Day08 Role Lane Board
          </div>
          <h3 className="mt-2 text-lg font-semibold text-slate-50">按角色分栏查看当前协作负载</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
            每个角色列都直接展示当前任务、阻塞项、运行中项和最近交接，方便老板从“谁在做什么”视角快速判断协作状态。
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs text-slate-400">
          <StatusBadge label={`角色列 ${props.lanes.length}`} tone="info" />
          <StatusBadge
            label={`已启用 ${props.lanes.filter((lane) => lane.enabled).length}`}
            tone="success"
          />
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-4">
        {props.lanes.map((lane) => {
          const isSelected = lane.role_code === props.selectedRoleCode;
          return (
            <section
              key={lane.role_code}
              className={`rounded-2xl border p-4 transition ${
                isSelected
                  ? "border-cyan-500/40 bg-cyan-500/5 shadow-lg shadow-cyan-950/10"
                  : "border-slate-800 bg-slate-900/70"
              }`}
            >
              <button
                type="button"
                onClick={() => props.onSelectRole(lane.role_code)}
                className="w-full text-left"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="text-base font-semibold text-slate-50">{lane.role_name}</div>
                    <p className="mt-2 text-sm leading-6 text-slate-400">{lane.role_summary}</p>
                  </div>
                  <StatusBadge label={lane.enabled ? "已启用" : "未启用"} tone={lane.enabled ? "success" : "neutral"} />
                </div>
              </button>

              <div className="mt-4 flex flex-wrap gap-2">
                <StatusBadge label={`当前 ${lane.current_task_count}`} tone="info" />
                <StatusBadge label={`运行 ${lane.running_task_count}`} tone={lane.running_task_count > 0 ? "success" : "neutral"} />
                <StatusBadge label={`阻塞 ${lane.blocked_task_count}`} tone={lane.blocked_task_count > 0 ? "warning" : "neutral"} />
              </div>

              <div className="mt-4 space-y-4">
                <RoleLaneTaskSection
                  title="当前任务"
                  emptyText="暂无待跟进任务。"
                  tasks={lane.current_tasks.slice(0, 4)}
                  selectedTaskId={props.selectedTaskId}
                  onSelectTask={props.onSelectTask}
                />
                <RoleLaneTaskSection
                  title="运行中项"
                  emptyText="当前没有运行中的任务。"
                  tasks={lane.running_tasks.slice(0, 3)}
                  selectedTaskId={props.selectedTaskId}
                  onSelectTask={props.onSelectTask}
                  emphasizeRun
                />
                <RoleLaneTaskSection
                  title="阻塞项"
                  emptyText="当前没有阻塞卡点。"
                  tasks={lane.blocked_tasks.slice(0, 3)}
                  selectedTaskId={props.selectedTaskId}
                  onSelectTask={props.onSelectTask}
                  emphasizeRisk
                />
                <section>
                  <div className="text-xs uppercase tracking-[0.2em] text-slate-500">最近交接</div>
                  {lane.recent_handoffs.length ? (
                    <div className="mt-3 space-y-2">
                      {lane.recent_handoffs.slice(0, 3).map((handoff) => (
                        <button
                          key={handoff.id}
                          type="button"
                          onClick={() => props.onSelectHandoff(handoff)}
                          className="w-full rounded-xl border border-slate-800 bg-slate-950/70 px-3 py-3 text-left transition hover:border-cyan-400/30 hover:bg-slate-950"
                        >
                          <div className="text-xs font-medium text-slate-200">
                            {formatRoleChain(handoff)}
                          </div>
                          <div className="mt-1 text-xs text-slate-400">{handoff.task_title}</div>
                          <div className="mt-2 text-[11px] text-slate-500">
                            {formatDateTime(handoff.timestamp)}
                          </div>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="mt-3 rounded-xl border border-dashed border-slate-800 bg-slate-950/50 px-3 py-3 text-sm text-slate-500">
                      暂无交接记录。
                    </div>
                  )}
                </section>
              </div>
            </section>
          );
        })}
      </div>
    </section>
  );
}

function RoleLaneTaskSection(props: {
  title: string;
  emptyText: string;
  tasks: RoleWorkbenchTaskItem[];
  selectedTaskId: string | null;
  onSelectTask: (task: RoleWorkbenchTaskItem) => void;
  emphasizeRun?: boolean;
  emphasizeRisk?: boolean;
}) {
  return (
    <section>
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{props.title}</div>
      {props.tasks.length ? (
        <div className="mt-3 space-y-2">
          {props.tasks.map((task) => {
            const isSelected = task.task_id === props.selectedTaskId;
            return (
              <button
                key={task.task_id}
                type="button"
                onClick={() => props.onSelectTask(task)}
                className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                  isSelected
                    ? "border-cyan-500/40 bg-cyan-500/10"
                    : props.emphasizeRisk
                      ? "border-amber-500/20 bg-amber-500/5 hover:border-amber-400/30"
                      : props.emphasizeRun
                        ? "border-emerald-500/20 bg-emerald-500/5 hover:border-emerald-400/30"
                        : "border-slate-800 bg-slate-950/70 hover:border-cyan-400/20"
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="text-sm font-medium text-slate-100">{task.title}</div>
                  <StatusBadge
                    label={TASK_STATUS_LABELS[task.status] ?? task.status}
                    tone={mapTaskStatusTone(task.status)}
                  />
                </div>
                <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-400">
                  <span>优先级：{TASK_PRIORITY_LABELS[task.priority] ?? task.priority}</span>
                  {task.latest_run_status ? (
                    <StatusBadge
                      label={`运行：${task.latest_run_status}`}
                      tone={mapRunStatusTone(task.latest_run_status)}
                    />
                  ) : null}
                  {task.human_status !== "none" ? (
                    <StatusBadge
                      label={HUMAN_STATUS_LABELS[task.human_status] ?? task.human_status}
                      tone="warning"
                    />
                  ) : null}
                </div>
                <p className="mt-2 text-xs leading-5 text-slate-400">{task.input_summary}</p>
                <div className="mt-2 text-[11px] text-slate-500">
                  更新时间：{formatDateTime(task.updated_at)}
                </div>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="mt-3 rounded-xl border border-dashed border-slate-800 bg-slate-950/50 px-3 py-3 text-sm text-slate-500">
          {props.emptyText}
        </div>
      )}
    </section>
  );
}

function formatRoleChain(handoff: RoleWorkbenchHandoffItem): string {
  const roleCodes = [
    handoff.upstream_role_code,
    handoff.owner_role_code,
    handoff.downstream_role_code,
  ].filter((roleCode, index, items): roleCode is string => {
    return Boolean(roleCode) && items.indexOf(roleCode) === index;
  });

  if (!roleCodes.length) {
    return "未识别角色交接";
  }

  return roleCodes.map((roleCode) => ROLE_CODE_LABELS[roleCode] ?? roleCode).join(" → ");
}
