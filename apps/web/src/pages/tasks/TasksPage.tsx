import { useMemo } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { TaskTableSection } from "../../app/sections/TaskTableSection";
import { useConsoleOverview } from "../../features/console/hooks";
import type { ConsoleTask } from "../../features/console/types";
import { useConsoleEventStream } from "../../features/events/hooks";
import { TaskDetailPanel } from "../../features/task-detail/TaskDetailPanel";
import { buildRunRoute } from "../../lib/run-route";
import { buildTaskRoute } from "../../lib/task-route";

type BossDrilldownNavigateDetail = {
  source: "home_latest_run" | "home_manual_run";
  taskId: string;
  runId?: string | null;
};

function buildBossDrilldownHash(detail: BossDrilldownNavigateDetail) {
  const params = new URLSearchParams();
  params.set("source", detail.source);
  params.set("taskId", detail.taskId);

  if (detail.runId) {
    params.set("runId", detail.runId);
  }

  return `#boss-drilldown?${params.toString()}`;
}

export function TasksPage() {
  const navigate = useNavigate();
  const { taskId } = useParams();
  const [searchParams] = useSearchParams();
  const realtime = useConsoleEventStream();
  const overviewQuery = useConsoleOverview({
    enablePollingFallback: realtime.status !== "open",
  });

  const tasks = overviewQuery.data?.tasks ?? [];
  const selectedTask = useMemo<ConsoleTask | null>(
    () => tasks.find((task) => task.id === taskId) ?? null,
    [taskId, tasks],
  );
  const requestedRunId = searchParams.get("runId");
  const taskNotFound =
    Boolean(taskId) && !overviewQuery.isLoading && tasks.length > 0 && !selectedTask;

  const handleNavigateToDeliverable = (input: {
    projectId: string;
    deliverableId: string;
  }) => {
    const nextSearchParams = new URLSearchParams();
    nextSearchParams.set("deliverableId", input.deliverableId);

    navigate(
      `/projects/${input.projectId}?${nextSearchParams.toString()}#project-overview?view=deliverable-center&targetId=deliverable-center`,
    );
  };

  const handleNavigateToProjectDrilldown = (detail: BossDrilldownNavigateDetail) => {
    navigate(`/projects${buildBossDrilldownHash(detail)}`);
  };

  return (
    <div className="space-y-6">
      <section className="rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="text-xs font-medium uppercase tracking-[0.24em] text-cyan-300">
              Tasks
            </div>
            <h3 className="mt-2 text-xl font-semibold text-slate-50">任务中心</h3>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
              在正式任务域中查看任务列表、任务详情、上下文摘要、运行记录与交付物关联。
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <SummaryCard label="任务总数" value={String(tasks.length)} />
            <SummaryCard
              label="当前选中"
              value={selectedTask ? selectedTask.title : taskId ? "未命中任务" : "未选择"}
            />
            <SummaryCard label="连接状态" value={realtime.status} />
          </div>
        </div>
      </section>

      {taskNotFound ? (
        <section className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm leading-6 text-amber-100">
          当前 URL 中的任务 ID <code className="mx-1 rounded bg-slate-950/40 px-1.5 py-0.5">{taskId}</code>
          未出现在当前任务列表中。你仍然可以在左侧列表中重新选择一个任务。
        </section>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[1.2fr_minmax(360px,1fr)]">
        <TaskTableSection
          tasks={tasks}
          selectedTaskId={selectedTask?.id ?? taskId ?? null}
          overviewIsLoading={overviewQuery.isLoading}
          overviewIsError={overviewQuery.isError}
          onSelectTask={(nextTaskId) => {
            navigate(buildTaskRoute({ taskId: nextTaskId, from: "tasks" }));
          }}
          onNavigateToRun={(nextRunId, nextTaskId) => {
            navigate(
              buildRunRoute({
                runId: nextRunId,
                taskId: nextTaskId,
                from: "tasks",
              }),
            );
          }}
          onNavigateToProjectDrilldown={handleNavigateToProjectDrilldown}
        />

        <TaskDetailPanel
          panelId="tasks-detail-panel"
          runLogPanelId="tasks-run-log-panel"
          requestedRunId={requestedRunId}
          selectedTask={selectedTask}
          budget={overviewQuery.data?.budget ?? null}
          realtimeStatus={realtime.status}
          onNavigateToDeliverable={handleNavigateToDeliverable}
          onNavigateToRun={(nextRunId, nextTaskId) =>
            navigate(
              buildRunRoute({
                runId: nextRunId,
                taskId: nextTaskId,
                from: "tasks",
              }),
            )
          }
          onNavigateToStrategyPreview={({ taskId: nextTaskId, runId }) =>
            handleNavigateToProjectDrilldown({
              source: "home_latest_run",
              taskId: nextTaskId,
              runId,
            })
          }
        />
      </section>
    </div>
  );
}

function SummaryCard(props: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{props.label}</div>
      <div className="mt-2 line-clamp-2 text-sm font-medium text-slate-100">{props.value}</div>
    </div>
  );
}
