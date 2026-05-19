import type { ConsoleTask } from "../../../features/console/types";
import { TaskDetailDrawer } from "./TaskDetailDrawer";
import { TaskExecutionSituationPanel } from "./TaskExecutionSituationPanel";
import { TaskQueueList } from "./TaskQueueList";

const noop = () => {};
const emptyState = { isPending: false, isError: false, errorMessage: null };

type TasksPageContentProps = {
  selectedTaskId: string | null;
  tasks: ConsoleTask[];
  onSelectTask: (taskId: string) => void;
  onNavigateToRun: (runId: string, taskId: string, projectId: string | null) => void;
  onNavigateToRepository: (taskId: string, projectId: string | null) => void;
  onCloseDrawer: () => void;
};

export function TasksPageContent({
  selectedTaskId,
  tasks,
  onSelectTask,
  onNavigateToRun,
  onNavigateToRepository,
  onCloseDrawer,
}: TasksPageContentProps) {
  const selectedTask = selectedTaskId
    ? tasks.find((t) => t.id === selectedTaskId) ?? null
    : null;

  return (
    <>
      <section className="flex flex-col gap-5 xl:grid xl:grid-cols-[55fr_45fr] xl:items-start min-h-0">
        {/* 左侧：轻量任务队列 */}
        <div className="min-h-0 overflow-y-auto">
          <TaskQueueList
            tasks={tasks}
            selectedTaskId={selectedTaskId}
            onSelectTask={onSelectTask}
            onNavigateToRun={onNavigateToRun}
            onNavigateToRepository={onNavigateToRepository}
          />
        </div>

        {/* 右侧：执行态势面板 */}
        <div className="min-h-0">
          <TaskExecutionSituationPanel
            tasks={tasks}
            onNavigateToRun={onNavigateToRun}
          />
        </div>
      </section>

      {/* 任务详情抽屉 */}
      {selectedTask && (
        <TaskDetailDrawer
          task={selectedTask}
          onClose={onCloseDrawer}
          onNavigateToRun={onNavigateToRun}
          onNavigateToRepository={onNavigateToRepository}
          onPause={noop}
          onResume={noop}
          onRequestHuman={noop}
          onResolveHuman={noop}
          onRetry={noop}
          pauseState={emptyState}
          resumeState={emptyState}
          requestHumanState={emptyState}
          resolveHumanState={emptyState}
          retryState={emptyState}
        />
      )}
    </>
  );
}
