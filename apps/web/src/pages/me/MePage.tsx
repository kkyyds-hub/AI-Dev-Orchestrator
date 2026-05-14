import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";

import { StatusBadge } from "../../components/StatusBadge";
import { useConsoleOverview } from "../../features/console/hooks";
import type { ConsoleTask } from "../../features/console/types";
import { useBossProjectOverview } from "../../features/projects/hooks";
import {
  PROJECT_STAGE_LABELS,
  PROJECT_STATUS_LABELS,
  TASK_PRIORITY_LABELS,
  TASK_STATUS_LABELS,
} from "../../features/projects/types";
import { buildApprovalsRoute } from "../../lib/approval-route";
import { buildDeliverablesRoute } from "../../lib/deliverable-route";
import { formatDateTime } from "../../lib/format";
import { mapProjectStatusTone, mapTaskStatusTone } from "../../lib/status";
import { buildTaskRoute } from "../../lib/task-route";
import { buildProjectOverviewRoute } from "../../features/projects/lib/overviewNavigation";

const ACTIONABLE_TASK_STATUSES = new Set([
  "waiting_human",
  "pending",
  "blocked",
  "paused",
  "failed",
]);

function getTimestamp(value: string | null | undefined) {
  if (!value) {
    return 0;
  }

  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function sortTasksByRecency(left: ConsoleTask, right: ConsoleTask) {
  return getTimestamp(right.updated_at) - getTimestamp(left.updated_at);
}

export function MePage() {
  const navigate = useNavigate();
  const consoleOverviewQuery = useConsoleOverview({ enablePollingFallback: false });
  const projectOverviewQuery = useBossProjectOverview({ enablePolling: false });
  const tasks = consoleOverviewQuery.data?.tasks ?? [];
  const projects = projectOverviewQuery.data?.projects ?? [];

  const actionableTasks = useMemo(
    () =>
      tasks
        .filter(
          (task) =>
            ACTIONABLE_TASK_STATUSES.has(task.status) ||
            task.human_status === "requested" ||
            task.human_status === "in_progress",
        )
        .sort(sortTasksByRecency)
        .slice(0, 5),
    [tasks],
  );

  const recentTasks = useMemo(
    () => [...tasks].sort(sortTasksByRecency).slice(0, 5),
    [tasks],
  );

  const recentProjects = useMemo(
    () =>
      [...projects]
        .sort(
          (left, right) =>
            getTimestamp(right.latest_progress_at ?? right.updated_at) -
            getTimestamp(left.latest_progress_at ?? left.updated_at),
        )
        .slice(0, 4),
    [projects],
  );

  const primaryProject = recentProjects[0] ?? null;
  const isLoading = consoleOverviewQuery.isLoading || projectOverviewQuery.isLoading;
  const hasLoadError = consoleOverviewQuery.isError || projectOverviewQuery.isError;

  const navigateToTask = (task: ConsoleTask) => {
    navigate(
      buildTaskRoute({
        taskId: task.id,
        runId: task.latest_run?.id ?? null,
        from: "tasks",
      }),
    );
  };

  return (
    <div className="space-y-7">
      <section className="border-b border-[#333333] pb-6">
        <div className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-600">
          My Workspace
        </div>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-zinc-100">
          我的工作入口
        </h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-500">
          汇总当前最可能继续处理的任务、项目与审批/交付物入口。这里不绑定个人账号体系，只复用现有任务和项目数据，帮助你快速回到下一步。
        </p>
      </section>

      <section className="grid gap-3 md:grid-cols-4">
        <MetricLine label="待处理任务" value={String(actionableTasks.length)} />
        <MetricLine label="最近任务" value={String(recentTasks.length)} />
        <MetricLine label="最近项目" value={String(recentProjects.length)} />
        <MetricLine
          label="数据状态"
          value={isLoading ? "加载中" : hasLoadError ? "加载异常" : "已同步"}
        />
      </section>

      {hasLoadError ? (
        <section className="border-l border-rose-500/50 px-4 py-3 text-sm leading-6 text-rose-100">
          工作入口数据加载不完整，请确认后端服务可用后刷新页面。
        </section>
      ) : null}

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]">
        <TaskListPanel
          title="待处理任务"
          description="优先展示待人工、待处理、阻塞、暂停或失败的任务。"
          tasks={actionableTasks}
          isLoading={consoleOverviewQuery.isLoading}
          emptyText="当前没有待处理任务。可以查看最近任务，或去任务中心浏览完整队列。"
          emptyAction={{ label: "打开任务中心", to: "/tasks" }}
          onOpenTask={navigateToTask}
        />

        <QuickEntryPanel projectId={primaryProject?.id ?? null} />
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]">
        <TaskListPanel
          title="最近任务"
          description="按最近更新时间排序，方便继续查看刚处理过的任务。"
          tasks={recentTasks}
          isLoading={consoleOverviewQuery.isLoading}
          emptyText="当前还没有任务。可以先进入项目中心创建项目和任务上下文。"
          emptyAction={{ label: "去项目中心", to: "/projects" }}
          onOpenTask={navigateToTask}
        />

        <RecentProjectsPanel
          projects={recentProjects}
          isLoading={projectOverviewQuery.isLoading}
        />
      </section>
    </div>
  );
}

function MetricLine(props: { label: string; value: string }) {
  return (
    <div className="border-l border-[#333333] px-4 py-2">
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
        {props.label}
      </div>
      <div className="mt-2 text-xl font-semibold text-zinc-100">{props.value}</div>
    </div>
  );
}

function TaskListPanel(props: {
  title: string;
  description: string;
  tasks: ConsoleTask[];
  isLoading: boolean;
  emptyText: string;
  emptyAction: { label: string; to: string };
  onOpenTask: (task: ConsoleTask) => void;
}) {
  return (
    <section className="space-y-3">
      <div className="flex flex-col gap-2 border-b border-[#333333] pb-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-zinc-100">{props.title}</h2>
          <p className="mt-1 text-sm leading-6 text-zinc-500">{props.description}</p>
        </div>
        <Link
          to="/tasks"
          className="text-sm font-medium text-zinc-300 transition hover:text-zinc-50"
        >
          查看全部任务
        </Link>
      </div>

      {props.isLoading ? (
        <div className="border-l border-[#333333] px-4 py-3 text-sm text-zinc-500">
          正在加载任务...
        </div>
      ) : props.tasks.length ? (
        <div className="divide-y divide-[#333333] border-y border-[#333333]">
          {props.tasks.map((task) => (
            <button
              key={`${props.title}-${task.id}`}
              type="button"
              onClick={() => props.onOpenTask(task)}
              className="grid w-full gap-3 px-2 py-3 text-left transition hover:bg-[#292929] sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"
            >
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-zinc-100">
                  {task.title}
                </div>
                <div className="mt-1 line-clamp-2 text-xs leading-5 text-zinc-500">
                  {task.input_summary}
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  <StatusBadge
                    label={TASK_STATUS_LABELS[task.status] ?? "未知状态"}
                    tone={mapTaskStatusTone(task.status)}
                  />
                  <StatusBadge
                    label={`优先级 ${TASK_PRIORITY_LABELS[task.priority] ?? task.priority}`}
                    tone="neutral"
                  />
                </div>
              </div>
              <div className="text-xs leading-5 text-zinc-600 sm:text-right">
                更新 {formatDateTime(task.updated_at)}
                {task.latest_run ? (
                  <div>最近运行 {formatDateTime(task.latest_run.created_at)}</div>
                ) : null}
              </div>
            </button>
          ))}
        </div>
      ) : (
        <EmptyHint text={props.emptyText} action={props.emptyAction} />
      )}
    </section>
  );
}

function QuickEntryPanel(props: { projectId: string | null }) {
  const approvalHref = props.projectId
    ? buildApprovalsRoute({ projectId: props.projectId })
    : "/approvals";
  const deliverableHref = props.projectId
    ? buildDeliverablesRoute({ projectId: props.projectId })
    : "/deliverables";

  return (
    <section className="space-y-3">
      <div className="border-b border-[#333333] pb-3">
        <h2 className="text-lg font-semibold text-zinc-100">继续处理入口</h2>
        <p className="mt-1 text-sm leading-6 text-zinc-500">
          直接进入审批和交付物流，若没有可用项目，页面会引导你先选择或创建项目。
        </p>
      </div>

      <div className="divide-y divide-[#333333] border-y border-[#333333]">
        <QuickEntryLink
          to={approvalHref}
          title="审批入口"
          description="查看待审批项、放行动作和审批历史。"
        />
        <QuickEntryLink
          to={deliverableHref}
          title="交付物入口"
          description="查看交付物快照、版本与关联任务。"
        />
        <QuickEntryLink
          to="/projects"
          title="项目中心"
          description="创建项目、选择项目并进入项目内工作区。"
        />
      </div>
    </section>
  );
}

function QuickEntryLink(props: {
  to: string;
  title: string;
  description: string;
}) {
  return (
    <Link
      to={props.to}
      className="block px-2 py-3 transition hover:bg-[#292929]"
    >
      <div className="text-sm font-medium text-zinc-100">{props.title}</div>
      <div className="mt-1 text-xs leading-5 text-zinc-500">
        {props.description}
      </div>
    </Link>
  );
}

function RecentProjectsPanel(props: {
  projects: Array<{
    id: string;
    name: string;
    summary: string;
    stage: string;
    status: string;
    updated_at: string;
  }>;
  isLoading: boolean;
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-end justify-between gap-3 border-b border-[#333333] pb-3">
        <div>
          <h2 className="text-lg font-semibold text-zinc-100">最近项目</h2>
          <p className="mt-1 text-sm leading-6 text-zinc-500">
            进入最近活跃项目，继续查看总览、仓库、交付物或审批。
          </p>
        </div>
        <Link
          to="/projects"
          className="text-sm font-medium text-zinc-300 transition hover:text-zinc-50"
        >
          项目中心
        </Link>
      </div>

      {props.isLoading ? (
        <div className="border-l border-[#333333] px-4 py-3 text-sm text-zinc-500">
          正在加载项目...
        </div>
      ) : props.projects.length ? (
        <div className="divide-y divide-[#333333] border-y border-[#333333]">
          {props.projects.map((project) => (
            <Link
              key={project.id}
              to={buildProjectOverviewRoute({
                projectId: project.id,
                view: "overview",
              })}
              className="block px-2 py-3 transition hover:bg-[#292929]"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium text-zinc-100">
                  {project.name}
                </span>
                <StatusBadge
                  label={PROJECT_STAGE_LABELS[project.stage] ?? "未知阶段"}
                  tone="info"
                />
                <StatusBadge
                  label={PROJECT_STATUS_LABELS[project.status] ?? "未知状态"}
                  tone={mapProjectStatusTone(project.status)}
                />
              </div>
              <p className="mt-2 line-clamp-2 text-xs leading-5 text-zinc-500">
                {project.summary}
              </p>
              <div className="mt-2 text-xs text-zinc-600">
                更新 {formatDateTime(project.updated_at)}
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <EmptyHint
          text="当前还没有项目。创建项目后，这里会显示最近项目入口。"
          action={{ label: "去项目中心创建项目", to: "/projects" }}
        />
      )}
    </section>
  );
}

function EmptyHint(props: {
  text: string;
  action: { label: string; to: string };
}) {
  return (
    <div className="border-l border-dashed border-[#3a3a3a] px-4 py-4 text-sm leading-6 text-zinc-500">
      {props.text}
      <div className="mt-3">
        <Link
          to={props.action.to}
          className="inline-flex border-b border-zinc-500 pb-0.5 text-sm font-medium text-zinc-100 transition hover:border-zinc-200 hover:text-white"
        >
          {props.action.label}
        </Link>
      </div>
    </div>
  );
}
