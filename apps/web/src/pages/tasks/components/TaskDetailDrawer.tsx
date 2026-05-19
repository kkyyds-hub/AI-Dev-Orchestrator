import type { ConsoleTask } from "../../../features/console/types";

type TaskDetailDrawerProps = {
  task: ConsoleTask;
  onClose: () => void;
  onNavigateToRun: (runId: string, taskId: string, projectId: string | null) => void;
  onNavigateToRepository: (taskId: string, projectId: string | null) => void;
};

const STATUS_LABELS: Record<string, string> = {
  waiting_human: "待人工",
  blocked: "阻塞",
  running: "运行中",
  pending: "待执行",
  completed: "已完成",
  failed: "失败",
  paused: "暂停",
};

export function TaskDetailDrawer({
  task,
  onClose,
  onNavigateToRun,
  onNavigateToRepository,
}: TaskDetailDrawerProps) {
  const hasRun = Boolean(task.latest_run?.id);
  const depIds = task.depends_on_task_ids ?? [];
  const priorityLabel = task.priority ? task.priority.toUpperCase() : null;

  return (
    <div
      className="fixed inset-0 z-40 flex justify-end"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" />

      {/* Panel */}
      <div
        className="relative w-full max-w-md bg-[#1a1a1a] border-l border-[#333333] overflow-y-auto shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#333333] px-5 py-4">
          <h2 className="text-base font-semibold text-zinc-100 truncate">
            {task.title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-[#333333] px-2.5 py-1 text-xs text-zinc-400 transition hover:border-zinc-500 hover:text-zinc-200"
          >
            关闭
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          {/* Status + priority */}
          <div className="flex items-center gap-2">
            <span className="rounded border border-[#333333] px-2 py-0.5 text-xs text-zinc-300">
              {STATUS_LABELS[task.status] ?? task.status}
            </span>
            {priorityLabel && (
              <span className="text-xs text-zinc-500">{priorityLabel}</span>
            )}
          </div>

          {/* Agent */}
          <Field label="Agent" value={task.owner_role_code || "未分配"} />

          {/* Dependencies */}
          <div>
            <p className="text-xs text-zinc-500 mb-1">依赖</p>
            {depIds.length > 0 ? (
              <p className="text-sm text-zinc-300">
                {depIds.length} 个依赖任务
              </p>
            ) : (
              <p className="text-sm text-zinc-600">无依赖</p>
            )}
          </div>

          {/* Block reason */}
          {task.paused_reason && (
            <Field label="阻塞原因" value={task.paused_reason} />
          )}
          {task.status === "waiting_human" && (
            <Field label="状态说明" value="待人工确认" />
          )}

          {/* Latest run summary */}
          <div>
            <p className="text-xs text-zinc-500 mb-1">最近运行</p>
            {hasRun && task.latest_run ? (
              <div className="rounded border border-[#333333] px-3 py-2">
                <p className="text-sm text-zinc-300">
                  {task.latest_run.result_summary || "无摘要"}
                </p>
                <p className="text-xs text-zinc-600 mt-1">
                  状态：{task.latest_run.status ?? "未知"}
                </p>
              </div>
            ) : (
              <p className="text-sm text-zinc-600">暂无运行记录</p>
            )}
          </div>

          {/* Input summary */}
          {task.input_summary && (
            <Field label="输入摘要" value={task.input_summary.slice(0, 120)} />
          )}

          {/* Actions */}
          <div className="flex flex-wrap gap-2 border-t border-[#333333] pt-4">
            {hasRun ? (
              <button
                type="button"
                onClick={() =>
                  onNavigateToRun(task.latest_run!.id, task.id, task.project_id)
                }
                className="rounded border border-[#444444] px-3 py-1.5 text-xs text-zinc-300 transition hover:border-zinc-400 hover:bg-[#2f2f2f]"
              >
                查看运行
              </button>
            ) : (
              <button
                type="button"
                disabled
                title="无最近运行"
                className="rounded border border-[#333333] px-3 py-1.5 text-xs text-zinc-700 cursor-not-allowed"
              >
                查看运行
              </button>
            )}

            {task.project_id ? (
              <button
                type="button"
                onClick={() =>
                  onNavigateToRepository(task.id, task.project_id)
                }
                className="rounded border border-[#444444] px-3 py-1.5 text-xs text-zinc-300 transition hover:border-zinc-400 hover:bg-[#2f2f2f]"
              >
                仓库上下文
              </button>
            ) : (
              <button
                type="button"
                disabled
                title="缺少项目上下文"
                className="rounded border border-[#333333] px-3 py-1.5 text-xs text-zinc-700 cursor-not-allowed"
              >
                仓库上下文
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-zinc-500 mb-0.5">{label}</p>
      <p className="text-sm text-zinc-300">{value}</p>
    </div>
  );
}
