import type { ConsoleTask } from "../../../features/console/types";

type TaskQueueListProps = {
  tasks: ConsoleTask[];
  selectedTaskId: string | null;
  onSelectTask: (taskId: string) => void;
  onNavigateToRun: (runId: string, taskId: string, projectId: string | null) => void;
  onNavigateToRepository: (taskId: string, projectId: string | null) => void;
};

function groupTasks(tasks: ConsoleTask[]) {
  const critical: ConsoleTask[] = [];
  const running: ConsoleTask[] = [];
  const others: ConsoleTask[] = [];

  for (const t of tasks) {
    if (t.status === "waiting_human" || t.status === "blocked") {
      critical.push(t);
    } else if (t.status === "running") {
      running.push(t);
    } else {
      others.push(t);
    }
  }

  const groups: { key: string; label: string; tasks: ConsoleTask[] }[] = [];
  if (critical.length > 0) groups.push({ key: "critical", label: "待人工 / 阻塞", tasks: critical });
  if (running.length > 0) groups.push({ key: "running", label: "执行中", tasks: running });
  if (others.length > 0) groups.push({ key: "others", label: "其他任务", tasks: others });

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
      <div className="flex items-center justify-center min-h-[240px] text-sm text-zinc-600">
        当前项目范围内无任务
      </div>
    );
  }

  const groups = groupTasks(tasks);

  return (
    <div className="space-y-4">
      {groups.map((group) => (
        <div key={group.key}>
          <div className="flex items-center gap-2 mb-2 px-1">
            <span className="text-xs font-semibold uppercase tracking-[0.12em] text-zinc-500">
              {group.label}
            </span>
            <span className="text-xs text-zinc-600">{group.tasks.length}</span>
          </div>

          <div className="space-y-1">
            {group.tasks.map((task) => (
              <TaskQueueItem
                key={task.id}
                task={task}
                isSelected={task.id === selectedTaskId}
                onSelect={() => onSelectTask(task.id)}
                onNavigateToRun={() =>
                  onNavigateToRun(
                    task.latest_run!.id,
                    task.id,
                    task.project_id,
                  )
                }
                onNavigateToRepository={() =>
                  onNavigateToRepository(task.id, task.project_id)
                }
              />
            ))}
          </div>
        </div>
      ))}
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
  const priorityLabel = task.priority ? task.priority.toUpperCase() : null;

  return (
    <div
      onClick={onSelect}
      className={`rounded border px-3 py-2.5 cursor-pointer transition ${
        isSelected
          ? "border-zinc-500 bg-[#222222]"
          : "border-[#333333] bg-[#1a1a1a] hover:border-zinc-600 hover:bg-[#1f1f1f]"
      }`}
    >
      {/* Row 1: title + status + agent */}
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm text-zinc-200 truncate min-w-0 flex-1">
          {task.title}
        </span>
        <div className="flex items-center gap-1.5 shrink-0">
          <span className="text-[10px] text-zinc-500 rounded border border-[#333333] px-1.5 py-0.5">
            {mapStatusLabel(task.status)}
          </span>
          {priorityLabel && (
            <span className="text-[10px] text-zinc-500">{priorityLabel}</span>
          )}
        </div>
      </div>

      {/* Row 2: agent + blocking */}
      <div className="mt-1 flex items-center gap-3 text-xs text-zinc-500">
        <span>{task.owner_role_code || "未分配 Agent"}</span>
        {depIds.length > 0 && (
          <span className="text-zinc-600">
            依赖 {depIds.length} 个任务
          </span>
        )}
        {task.status === "blocked" && task.paused_reason && (
          <span className="text-zinc-600 truncate">
            {task.paused_reason.slice(0, 40)}
          </span>
        )}
        {task.status === "waiting_human" && (
          <span className="text-zinc-600">待人工确认</span>
        )}
      </div>

      {/* Row 3: latest run summary + actions */}
      <div className="mt-1.5 flex items-center justify-between gap-2">
        <span className="text-xs text-zinc-600 truncate min-w-0">
          {task.latest_run?.result_summary
            ? task.latest_run.result_summary.slice(0, 60)
            : "暂无运行摘要"}
        </span>

        <div className="flex items-center gap-1.5 shrink-0">
          {hasRun ? (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onNavigateToRun();
              }}
              className="rounded border border-[#444444] px-2 py-0.5 text-[10px] text-zinc-400 transition hover:border-zinc-400 hover:bg-[#2f2f2f]"
            >
              查看运行
            </button>
          ) : (
            <button
              type="button"
              disabled
              onClick={(e) => e.stopPropagation()}
              title="无最近运行"
              className="rounded border border-[#333333] px-2 py-0.5 text-[10px] text-zinc-700 cursor-not-allowed"
            >
              查看运行
            </button>
          )}

          {task.project_id ? (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onNavigateToRepository();
              }}
              className="rounded border border-[#444444] px-2 py-0.5 text-[10px] text-zinc-400 transition hover:border-zinc-400 hover:bg-[#2f2f2f]"
            >
              仓库上下文
            </button>
          ) : (
            <button
              type="button"
              disabled
              onClick={(e) => e.stopPropagation()}
              title="缺少项目上下文"
              className="rounded border border-[#333333] px-2 py-0.5 text-[10px] text-zinc-700 cursor-not-allowed"
            >
              仓库上下文
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
