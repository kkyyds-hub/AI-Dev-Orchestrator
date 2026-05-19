import { useState } from "react";
import type { ConsoleTask } from "../../../features/console/types";

type TaskQueueListProps = {
  tasks: ConsoleTask[];
  selectedTaskId: string | null;
  onSelectTask: (taskId: string) => void;
  onNavigateToRun: (runId: string, taskId: string, projectId: string | null) => void;
  onNavigateToRepository: (taskId: string, projectId: string | null) => void;
};

/* Group tasks: critical (waiting_human/blocked), running, active others, completed/failed */
function groupTasks(tasks: ConsoleTask[]) {
  const critical: ConsoleTask[] = [];
  const running: ConsoleTask[] = [];
  const active: ConsoleTask[] = [];
  const completed: ConsoleTask[] = [];

  for (const t of tasks) {
    if (t.status === "waiting_human" || t.status === "blocked") {
      critical.push(t);
    } else if (t.status === "running") {
      running.push(t);
    } else if (t.status === "completed" || t.status === "failed") {
      completed.push(t);
    } else {
      active.push(t);
    }
  }

  const groups: { key: string; label: string; tasks: ConsoleTask[]; collapsible?: boolean }[] = [];
  if (critical.length > 0) groups.push({ key: "critical", label: "待人工 / 阻塞", tasks: critical });
  if (running.length > 0) groups.push({ key: "running", label: "执行中", tasks: running });
  if (active.length > 0) groups.push({ key: "active", label: "可调度 / 等待中", tasks: active });
  if (completed.length > 0) groups.push({ key: "completed", label: "已完成 / 失败", tasks: completed, collapsible: true });

  return groups;
}

export function TaskQueueList({
  tasks,
  selectedTaskId,
  onSelectTask,
  onNavigateToRun,
  onNavigateToRepository,
}: TaskQueueListProps) {
  if (tasks.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-[200px] text-sm text-zinc-600">
        当前项目无任务
      </div>
    );
  }

  const groups = groupTasks(tasks);

  return (
    <div className="space-y-5">
      {groups.map((group) => (
        <TaskQueueGroup
          key={group.key}
          label={group.label}
          count={group.tasks.length}
          tasks={group.tasks}
          selectedTaskId={selectedTaskId}
          collapsedByDefault={group.collapsible === true}
          onSelect={onSelectTask}
          onNavigateToRun={onNavigateToRun}
          onNavigateToRepository={onNavigateToRepository}
        />
      ))}
    </div>
  );
}

/* ─── Group ─── */

function TaskQueueGroup({
  label,
  count,
  tasks,
  selectedTaskId,
  collapsedByDefault,
  onSelect,
  onNavigateToRun,
  onNavigateToRepository,
}: {
  label: string;
  count: number;
  tasks: ConsoleTask[];
  selectedTaskId: string | null;
  collapsedByDefault: boolean;
  onSelect: (taskId: string) => void;
  onNavigateToRun: (runId: string, taskId: string, projectId: string | null) => void;
  onNavigateToRepository: (taskId: string, projectId: string | null) => void;
}) {
  const [collapsed, setCollapsed] = useState(collapsedByDefault);

  return (
    <div>
      {/* Group header */}
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="flex items-center gap-2 mb-2 px-1 w-full text-left"
      >
        <span className="text-xs font-semibold uppercase tracking-[0.12em] text-zinc-500">
          {label}
        </span>
        <span className="text-xs text-zinc-600">{count}</span>
        {collapsedByDefault && (
          <span className="text-[10px] text-zinc-700 ml-auto">
            {collapsed ? "展开" : "收起"}
          </span>
        )}
      </button>

      {!collapsed && (
        <div className="space-y-1">
          {tasks.map((task) => (
            <TaskQueueItem
              key={task.id}
              task={task}
              isSelected={task.id === selectedTaskId}
              onSelect={() => onSelect(task.id)}
              onNavigateToRun={() =>
                onNavigateToRun(task.latest_run!.id, task.id, task.project_id)
              }
              onNavigateToRepository={() =>
                onNavigateToRepository(task.id, task.project_id)
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Item ─── */

const STATUS_LABELS: Record<string, string> = {
  waiting_human: "待人工",
  blocked: "阻塞",
  running: "运行中",
  pending: "待执行",
  completed: "已完成",
  failed: "失败",
  paused: "暂停",
};

function mapStatusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

function TaskQueueItem({
  task,
  isSelected,
  onSelect,
  onNavigateToRun,
  onNavigateToRepository,
}: {
  task: ConsoleTask;
  isSelected: boolean;
  onSelect: () => void;
  onNavigateToRun: () => void;
  onNavigateToRepository: () => void;
}) {
  const hasRun = Boolean(task.latest_run?.id);
  const depIds = task.depends_on_task_ids ?? [];

  return (
    <div
      onClick={onSelect}
      className={`rounded border px-3 py-2 cursor-pointer transition ${
        isSelected
          ? "border-zinc-500 bg-[#222222]"
          : "border-[#333333] bg-[#1a1a1a] hover:border-zinc-600 hover:bg-[#1f1f1f]"
      }`}
    >
      {/* Row: title + status */}
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm text-zinc-200 truncate min-w-0 flex-1">
          {task.title}
        </span>
        <span className="text-[10px] text-zinc-500 rounded border border-[#333333] px-1.5 py-0.5 shrink-0">
          {mapStatusLabel(task.status)}
        </span>
      </div>

      {/* Row: agent + deps + block reason */}
      <div className="mt-1 flex items-center gap-2 text-[11px] text-zinc-500">
        <span className="text-zinc-400">{task.owner_role_code || "未分配"}</span>
        {depIds.length > 0 && (
          <span className="text-zinc-600">依赖×{depIds.length}</span>
        )}
        {task.status === "blocked" && task.paused_reason && (
          <span className="text-zinc-600 truncate" title={task.paused_reason}>
            {task.paused_reason.slice(0, 36)}
          </span>
        )}
        {task.status === "waiting_human" && (
          <span className="text-zinc-600">待确认</span>
        )}
      </div>

      {/* Row: run summary + buttons */}
      <div className="mt-1 flex items-center justify-between gap-2">
        <span className="text-[11px] text-zinc-600 truncate min-w-0">
          {task.latest_run?.result_summary
            ? task.latest_run.result_summary.slice(0, 50)
            : "—"}
        </span>

        <div className="flex items-center gap-1 shrink-0">
          {hasRun ? (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onNavigateToRun(); }}
              className="rounded border border-[#444444] px-2 py-0.5 text-[10px] text-zinc-400 transition hover:border-zinc-400 hover:bg-[#2f2f2f]"
            >
              运行
            </button>
          ) : (
            <button
              type="button"
              disabled
              onClick={(e) => e.stopPropagation()}
              title="无最近运行"
              className="rounded border border-[#333333] px-2 py-0.5 text-[10px] text-zinc-700 cursor-not-allowed"
            >
              运行
            </button>
          )}

          {task.project_id ? (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onNavigateToRepository(); }}
              className="rounded border border-[#444444] px-2 py-0.5 text-[10px] text-zinc-400 transition hover:border-zinc-400 hover:bg-[#2f2f2f]"
            >
              仓库
            </button>
          ) : (
            <button
              type="button"
              disabled
              onClick={(e) => e.stopPropagation()}
              title="缺少项目上下文"
              className="rounded border border-[#333333] px-2 py-0.5 text-[10px] text-zinc-700 cursor-not-allowed"
            >
              仓库
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
