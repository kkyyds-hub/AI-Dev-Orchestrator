import type { ConsoleTask } from "../../../features/console/types";

type TaskActionState = {
  isPending: boolean;
  isError: boolean;
  errorMessage: string | null;
};

type TaskDetailDrawerProps = {
  task: ConsoleTask;
  onClose: () => void;
  onNavigateToRun: (runId: string, taskId: string, projectId: string | null) => void;
  onNavigateToRepository: (taskId: string, projectId: string | null) => void;
  onPause: (taskId: string) => void;
  onResume: (taskId: string) => void;
  onRequestHuman: (taskId: string) => void;
  onResolveHuman: (taskId: string) => void;
  onRetry: (taskId: string) => void;
  pauseState: TaskActionState;
  resumeState: TaskActionState;
  requestHumanState: TaskActionState;
  resolveHumanState: TaskActionState;
  retryState: TaskActionState;
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
  onPause,
  onResume,
  onRequestHuman,
  onResolveHuman,
  onRetry,
  pauseState,
  resumeState,
  requestHumanState,
  resolveHumanState,
  retryState,
}: TaskDetailDrawerProps) {
  const hasRun = Boolean(task.latest_run?.id);
  const depIds = task.depends_on_task_ids ?? [];
  const priorityLabel = task.priority ? task.priority.toUpperCase() : null;

  /* State-based action visibility — aligned with TaskStateMachineService */
  const canPause =
    task.status === "pending" ||
    task.status === "failed" ||
    task.status === "blocked";
  const canResume = task.status === "paused";
  const canRequestHuman =
    task.status === "pending" ||
    task.status === "failed" ||
    task.status === "blocked" ||
    task.status === "paused";
  const canResolveHuman = task.status === "waiting_human";
  const canRetry = task.status === "failed" || task.status === "blocked";

  return (
    <div className="fixed inset-0 z-40 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/50" />

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

          {task.source_plan_version_id ? (
            <div className="rounded border border-cyan-500/25 bg-cyan-500/5 px-3 py-2">
              <p className="text-xs font-medium text-cyan-100">
                AI 主管草案来源
              </p>
              <div className="mt-2 grid gap-1 text-xs text-zinc-400">
                <span className="break-all font-mono">
                  source_plan_version_id: {task.source_plan_version_id}
                </span>
                <span className="break-all font-mono">
                  source_draft_id: {task.source_draft_id ?? "后端未返回"}
                </span>
              </div>
              <p className="mt-2 text-xs leading-5 text-cyan-100/70">
                该来源只表示草案到正式任务的映射；未自动创建 Agent Session、Skill 绑定、仓库绑定或 Run。
              </p>
            </div>
          ) : null}

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
            <Field label="暂停/阻塞原因" value={task.paused_reason} />
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

          {/* Navigation actions */}
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

          {/* State action buttons */}
          <div className="flex flex-wrap gap-2 border-t border-[#333333] pt-4">
            {canPause && (
              <ActionButton
                label={pauseState.isPending ? "暂停中..." : "暂停"}
                isPending={pauseState.isPending}
                isError={pauseState.isError}
                onClick={() => onPause(task.id)}
              />
            )}
            {canResume && (
              <ActionButton
                label={resumeState.isPending ? "恢复中..." : "恢复"}
                isPending={resumeState.isPending}
                isError={resumeState.isError}
                onClick={() => onResume(task.id)}
              />
            )}
            {canRequestHuman && (
              <ActionButton
                label={requestHumanState.isPending ? "处理中..." : "请求人工"}
                isPending={requestHumanState.isPending}
                isError={requestHumanState.isError}
                onClick={() => onRequestHuman(task.id)}
              />
            )}
            {canResolveHuman && (
              <ActionButton
                label={resolveHumanState.isPending ? "处理中..." : "人工已处理"}
                isPending={resolveHumanState.isPending}
                isError={resolveHumanState.isError}
                onClick={() => onResolveHuman(task.id)}
              />
            )}
            {canRetry && (
              <div>
                <ActionButton
                  label={retryState.isPending ? "重新入队中..." : "重新入队"}
                  isPending={retryState.isPending}
                  isError={retryState.isError}
                  onClick={() => onRetry(task.id)}
                />
                <p className="mt-1 text-[10px] text-zinc-600">
                  重置为待执行，下一次 Worker 调度时执行
                </p>
              </div>
            )}
          </div>

          {/* Error feedback */}
          {pauseState.isError && pauseState.errorMessage && (
            <p className="text-xs text-red-400">暂停失败：{pauseState.errorMessage}</p>
          )}
          {resumeState.isError && resumeState.errorMessage && (
            <p className="text-xs text-red-400">恢复失败：{resumeState.errorMessage}</p>
          )}
          {requestHumanState.isError && requestHumanState.errorMessage && (
            <p className="text-xs text-red-400">请求人工失败：{requestHumanState.errorMessage}</p>
          )}
          {resolveHumanState.isError && resolveHumanState.errorMessage && (
            <p className="text-xs text-red-400">处理失败：{resolveHumanState.errorMessage}</p>
          )}
          {retryState.isError && retryState.errorMessage && (
            <p className="text-xs text-red-400">重新入队失败：{retryState.errorMessage}</p>
          )}
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

function ActionButton({
  label,
  isPending,
  isError,
  onClick,
}: {
  label: string;
  isPending: boolean;
  isError: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={isPending}
      className={`rounded border px-3 py-1.5 text-xs transition ${
        isError
          ? "border-red-800 text-red-400 hover:border-red-700 hover:bg-[#2a1111]"
          : "border-[#444444] text-zinc-300 hover:border-zinc-400 hover:bg-[#222222] disabled:cursor-not-allowed disabled:text-zinc-600"
      }`}
    >
      {label}
    </button>
  );
}
