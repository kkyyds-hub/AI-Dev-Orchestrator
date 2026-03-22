import { useEffect, useMemo, useState } from "react";

import { MetricCard } from "../../components/MetricCard";
import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { mapBudgetPressureTone, mapRunStatusTone, mapTaskStatusTone } from "../../lib/status";
import {
  PROJECT_STAGE_LABELS,
  PROJECT_STATUS_LABELS,
  TASK_PRIORITY_LABELS,
  TASK_RISK_LABELS,
  TASK_STATUS_LABELS,
} from "../projects/types";
import { HandoffTimeline } from "./components/HandoffTimeline";
import { RoleLaneBoard } from "./components/RoleLaneBoard";
import { useRoleWorkbenchSnapshot } from "./hooks";
import type {
  RoleWorkbenchHandoffItem,
  RoleWorkbenchLane,
  RoleWorkbenchTaskItem,
} from "./types";

type ProjectOption = {
  id: string;
  name: string;
  stage: string;
  status: string;
};

type RoleWorkbenchPageProps = {
  selectedProjectId: string | null;
  selectedProjectName: string | null;
  projectOptions: ProjectOption[];
  onNavigateToProject?: (projectId: string) => void;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
};

export function RoleWorkbenchPage(props: RoleWorkbenchPageProps) {
  const workbenchQuery = useRoleWorkbenchSnapshot(props.selectedProjectId);
  const lanes = workbenchQuery.data?.lanes ?? [];
  const [selectedRoleCode, setSelectedRoleCode] = useState<string | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [selectedHandoffId, setSelectedHandoffId] = useState<string | null>(null);

  useEffect(() => {
    if (!lanes.length) {
      setSelectedRoleCode(null);
      return;
    }

    const roleStillExists = lanes.some((lane) => lane.role_code === selectedRoleCode);
    if (!selectedRoleCode || !roleStillExists) {
      setSelectedRoleCode(lanes.find((lane) => lane.enabled)?.role_code ?? lanes[0].role_code);
    }
  }, [lanes, selectedRoleCode]);

  const flattenedTasks = useMemo(() => {
    const taskMap = new Map<string, RoleWorkbenchTaskItem>();
    for (const lane of lanes) {
      for (const task of [
        ...lane.current_tasks,
        ...lane.blocked_tasks,
        ...lane.running_tasks,
      ]) {
        taskMap.set(task.task_id, task);
      }
    }
    return Array.from(taskMap.values());
  }, [lanes]);

  useEffect(() => {
    if (!flattenedTasks.length) {
      setSelectedTaskId(null);
      return;
    }

    const taskStillExists = flattenedTasks.some((task) => task.task_id === selectedTaskId);
    if (!selectedTaskId || !taskStillExists) {
      const preferredLane = lanes.find((lane) => lane.role_code === selectedRoleCode);
      const fallbackTask = preferredLane?.current_tasks[0] ?? flattenedTasks[0];
      setSelectedTaskId(fallbackTask?.task_id ?? null);
    }
  }, [flattenedTasks, lanes, selectedRoleCode, selectedTaskId]);

  useEffect(() => {
    const handoffs = workbenchQuery.data?.recent_handoffs ?? [];
    if (!handoffs.length) {
      setSelectedHandoffId(null);
      return;
    }

    const handoffStillExists = handoffs.some((handoff) => handoff.id === selectedHandoffId);
    if (!selectedHandoffId || !handoffStillExists) {
      setSelectedHandoffId(handoffs[0].id);
    }
  }, [selectedHandoffId, workbenchQuery.data?.recent_handoffs]);

  const selectedRole = useMemo<RoleWorkbenchLane | null>(
    () => lanes.find((lane) => lane.role_code === selectedRoleCode) ?? null,
    [lanes, selectedRoleCode],
  );
  const selectedTask = useMemo<RoleWorkbenchTaskItem | null>(
    () => flattenedTasks.find((task) => task.task_id === selectedTaskId) ?? null,
    [flattenedTasks, selectedTaskId],
  );
  const selectedHandoff = useMemo<RoleWorkbenchHandoffItem | null>(
    () =>
      workbenchQuery.data?.recent_handoffs.find((handoff) => handoff.id === selectedHandoffId) ??
      null,
    [selectedHandoffId, workbenchQuery.data?.recent_handoffs],
  );

  const lastGeneratedText = workbenchQuery.data?.generated_at
    ? formatDateTime(workbenchQuery.data.generated_at)
    : "尚未生成";

  return (
    <section className="space-y-6 rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/40">
      <header className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-2">
          <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">
            V3 Day08 Role Workbench
          </p>
          <h2 className="text-3xl font-semibold tracking-tight text-slate-50">
            角色工作台与协作可视化
          </h2>
          <p className="max-w-3xl text-sm leading-6 text-slate-300">
            角色工作台直接把 PM、架构师、工程师、评审者的当前负载、阻塞卡点、运行态和最近交接搬到前台，并与老板首页共用同一套项目 / 任务 / 运行聚合口径。
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
          <StatusBadge
            label={
              props.selectedProjectName
                ? `当前项目：${props.selectedProjectName}`
                : workbenchQuery.data?.scope_label ?? "全部项目"
            }
            tone={props.selectedProjectName ? "info" : "neutral"}
          />
          {workbenchQuery.data?.budget ? (
            <StatusBadge
              label={workbenchQuery.data.budget.strategy_label}
              tone={mapBudgetPressureTone(workbenchQuery.data.budget.pressure_level)}
            />
          ) : null}
          <span>最近生成：{lastGeneratedText}</span>
        </div>
      </header>

      {props.projectOptions.length ? (
        <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
          <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="text-xs uppercase tracking-[0.2em] text-slate-500">工作台范围</div>
              <p className="mt-2 text-sm text-slate-300">
                切换项目后，角色工作台、项目详情和任务跳转会同步聚焦到同一条项目链路。
              </p>
            </div>
            <StatusBadge
              label={props.selectedProjectName ? "项目视角" : "全局视角"}
              tone={props.selectedProjectName ? "success" : "neutral"}
            />
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {props.projectOptions.map((project) => {
              const selected = project.id === props.selectedProjectId;
              return (
                <button
                  key={project.id}
                  type="button"
                  onClick={() => props.onNavigateToProject?.(project.id)}
                  className={`rounded-xl border px-4 py-3 text-left transition ${
                    selected
                      ? "border-cyan-500/40 bg-cyan-500/10 text-cyan-50"
                      : "border-slate-800 bg-slate-900/70 text-slate-300 hover:border-slate-700 hover:bg-slate-900"
                  }`}
                >
                  <div className="text-sm font-medium">{project.name}</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <StatusBadge
                      label={PROJECT_STAGE_LABELS[project.stage] ?? project.stage}
                      tone="info"
                    />
                    <StatusBadge
                      label={PROJECT_STATUS_LABELS[project.status] ?? project.status}
                      tone="neutral"
                    />
                  </div>
                </button>
              );
            })}
          </div>
        </section>
      ) : null}

      {workbenchQuery.isLoading && !workbenchQuery.data ? (
        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 text-sm text-slate-400">
          正在加载角色工作台数据...
        </section>
      ) : null}

      {workbenchQuery.isError ? (
        <section className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-6 text-sm text-rose-100">
          角色工作台加载失败：{workbenchQuery.error.message}
        </section>
      ) : null}

      {workbenchQuery.data ? (
        <>
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
            <MetricCard
              label="角色列"
              value={String(workbenchQuery.data.total_roles)}
              hint={`已启用 ${workbenchQuery.data.enabled_roles} 个角色`}
              tone="info"
            />
            <MetricCard
              label="当前任务"
              value={String(workbenchQuery.data.active_tasks)}
              hint="未完成任务总量"
              tone="success"
            />
            <MetricCard
              label="运行中项"
              value={String(workbenchQuery.data.running_tasks)}
              hint="任务或运行仍在推进"
              tone="info"
            />
            <MetricCard
              label="阻塞项"
              value={String(workbenchQuery.data.blocked_tasks)}
              hint="包含阻塞 / 暂停 / 待人工 / 失败"
              tone="warning"
            />
            <MetricCard
              label="未分派"
              value={String(workbenchQuery.data.unassigned_tasks)}
              hint="当前没有明确 owner role 的任务"
            />
            <MetricCard
              label="最近交接"
              value={String(workbenchQuery.data.recent_handoff_count)}
              hint="来自最新运行日志中的 role_handoff"
              tone="info"
            />
          </section>

          <RoleLaneBoard
            lanes={workbenchQuery.data.lanes}
            selectedRoleCode={selectedRoleCode}
            selectedTaskId={selectedTaskId}
            onSelectRole={setSelectedRoleCode}
            onSelectTask={(task) => {
              setSelectedTaskId(task.task_id);
              if (task.owner_role_code) {
                setSelectedRoleCode(task.owner_role_code);
              }
            }}
            onSelectHandoff={(handoff) => {
              setSelectedHandoffId(handoff.id);
              setSelectedTaskId(handoff.task_id);
              if (handoff.owner_role_code) {
                setSelectedRoleCode(handoff.owner_role_code);
              }
            }}
          />

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,1fr)]">
            <HandoffTimeline
              handoffs={workbenchQuery.data.recent_handoffs}
              selectedHandoffId={selectedHandoffId}
              onSelectHandoff={(handoff) => {
                setSelectedHandoffId(handoff.id);
                setSelectedTaskId(handoff.task_id);
                if (handoff.owner_role_code) {
                  setSelectedRoleCode(handoff.owner_role_code);
                }
              }}
            />

            <RoleWorkbenchInspector
              selectedRole={selectedRole}
              selectedTask={selectedTask}
              selectedHandoff={selectedHandoff}
              onNavigateToProject={props.onNavigateToProject}
              onNavigateToTask={props.onNavigateToTask}
            />
          </div>
        </>
      ) : null}
    </section>
  );
}

function RoleWorkbenchInspector(props: {
  selectedRole: RoleWorkbenchLane | null;
  selectedTask: RoleWorkbenchTaskItem | null;
  selectedHandoff: RoleWorkbenchHandoffItem | null;
  onNavigateToProject?: (projectId: string) => void;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
}) {
  return (
    <aside className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-cyan-300">Workbench Inspector</div>
        <h3 className="mt-2 text-lg font-semibold text-slate-50">角色 / 任务 / 运行跳转面板</h3>
        <p className="mt-2 text-sm leading-6 text-slate-300">
          从角色视角选中任务后，可以直接跳到项目详情、任务详情和运行详情；如果当前没有选中对象，也会展示角色列的聚合摘要。
        </p>
      </div>

      {props.selectedRole ? (
        <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-medium text-slate-50">当前角色</div>
            <StatusBadge label={props.selectedRole.enabled ? "已启用" : "未启用"} tone={props.selectedRole.enabled ? "success" : "neutral"} />
          </div>
          <div className="mt-3 text-lg font-semibold text-slate-100">{props.selectedRole.role_name}</div>
          <p className="mt-2 text-sm leading-6 text-slate-300">{props.selectedRole.role_summary}</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <MiniInfo label="当前任务" value={String(props.selectedRole.current_task_count)} />
            <MiniInfo label="运行中项" value={String(props.selectedRole.running_task_count)} />
            <MiniInfo label="阻塞项" value={String(props.selectedRole.blocked_task_count)} />
            <MiniInfo label="最近交接" value={String(props.selectedRole.recent_handoff_count)} />
          </div>
        </section>
      ) : null}

      {props.selectedTask ? (
        <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4" id="role-workbench-task-detail">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-slate-50">当前任务</div>
              <div className="mt-2 text-lg font-semibold text-slate-100">{props.selectedTask.title}</div>
            </div>
            <StatusBadge
              label={TASK_STATUS_LABELS[props.selectedTask.status] ?? props.selectedTask.status}
              tone={mapTaskStatusTone(props.selectedTask.status)}
            />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {props.selectedTask.project_name ? (
              <StatusBadge label={props.selectedTask.project_name} tone="info" />
            ) : null}
            <StatusBadge
              label={`优先级：${TASK_PRIORITY_LABELS[props.selectedTask.priority] ?? props.selectedTask.priority}`}
              tone="neutral"
            />
            <StatusBadge
              label={`风险：${TASK_RISK_LABELS[props.selectedTask.risk_level] ?? props.selectedTask.risk_level}`}
              tone={props.selectedTask.risk_level === "high" ? "warning" : "neutral"}
            />
            {props.selectedTask.latest_run_status ? (
              <StatusBadge
                label={`运行：${props.selectedTask.latest_run_status}`}
                tone={mapRunStatusTone(props.selectedTask.latest_run_status)}
              />
            ) : null}
          </div>
          <p className="mt-4 text-sm leading-6 text-slate-300">{props.selectedTask.input_summary}</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <MiniInfo label="创建时间" value={formatDateTime(props.selectedTask.created_at)} />
            <MiniInfo label="更新时间" value={formatDateTime(props.selectedTask.updated_at)} />
          </div>
          {props.selectedTask.latest_run_summary ? (
            <div className="mt-4 rounded-xl border border-slate-800 bg-slate-900/70 p-3 text-sm leading-6 text-slate-300">
              {props.selectedTask.latest_run_summary}
            </div>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-3">
            {props.selectedTask.project_id && props.onNavigateToProject ? (
              <button
                type="button"
                onClick={() => props.onNavigateToProject?.(props.selectedTask!.project_id!)}
                className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-800"
              >
                跳到项目详情
              </button>
            ) : null}
            {props.onNavigateToTask ? (
              <button
                type="button"
                onClick={() => props.onNavigateToTask?.(props.selectedTask!.task_id)}
                className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 transition hover:bg-cyan-500/20"
              >
                跳到任务详情
              </button>
            ) : null}
            {props.selectedTask.latest_run_id && props.onNavigateToTask ? (
              <button
                type="button"
                onClick={() =>
                  props.onNavigateToTask?.(props.selectedTask!.task_id, {
                    runId: props.selectedTask!.latest_run_id,
                  })
                }
                className="rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-100 transition hover:bg-emerald-500/20"
              >
                跳到运行详情
              </button>
            ) : null}
          </div>
        </section>
      ) : (
        <section className="rounded-2xl border border-dashed border-slate-800 bg-slate-950/50 p-4 text-sm leading-6 text-slate-400">
          先从左侧角色列或交接时间线里选择一个任务，再查看更细的任务与运行信息。
        </section>
      )}

      {props.selectedHandoff ? (
        <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4" id="role-workbench-run-detail">
          <div className="text-sm font-medium text-slate-50">当前交接</div>
          <div className="mt-2 text-sm text-slate-300">{props.selectedHandoff.message}</div>
          <div className="mt-3 flex flex-wrap gap-2">
            {props.selectedHandoff.run_status ? (
              <StatusBadge
                label={`运行：${props.selectedHandoff.run_status}`}
                tone={mapRunStatusTone(props.selectedHandoff.run_status)}
              />
            ) : null}
            {props.selectedHandoff.dispatch_status ? (
              <StatusBadge label={props.selectedHandoff.dispatch_status} tone="neutral" />
            ) : null}
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <MiniInfo label="交接时间" value={formatDateTime(props.selectedHandoff.timestamp)} />
            <MiniInfo label="所属项目" value={props.selectedHandoff.project_name ?? "未归属项目"} />
          </div>
          {props.selectedHandoff.handoff_reason ? (
            <div className="mt-4 rounded-xl border border-slate-800 bg-slate-900/70 p-3 text-sm leading-6 text-slate-300">
              {props.selectedHandoff.handoff_reason}
            </div>
          ) : null}
        </section>
      ) : null}
    </aside>
  );
}

function MiniInfo(props: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{props.label}</div>
      <div className="mt-2 text-sm font-medium text-slate-100">{props.value}</div>
    </div>
  );
}
