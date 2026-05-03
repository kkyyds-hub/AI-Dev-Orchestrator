import { StatusBadge } from "../../../components/StatusBadge";
import { mapTaskStatusTone } from "../../../lib/status";
import { ProjectLatestRunControlSurface } from "../ProjectLatestRunControlSurface";
import type {
  BossDrilldownContext,
  BossProjectLatestTask,
  ProjectDetail,
  ProjectDetailTaskItem,
} from "../types";
import {
  HUMAN_STATUS_LABELS,
  TASK_PRIORITY_LABELS,
  TASK_RISK_LABELS,
  TASK_STATUS_LABELS,
} from "../types";
import { ProjectMiniStat } from "./ProjectMiniStat";

export function ProjectLatestTaskPreview(props: {
  latestTask: BossProjectLatestTask | null;
  detail: ProjectDetail | null;
  projectTasks: ProjectDetailTaskItem[];
  projectId: string | null;
  drilldownContext: BossDrilldownContext | null;
  onNavigateToStrategyPreview: (context: BossDrilldownContext) => void;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
  onNavigateToTaskDetailFromLatestRun: () => void;
}) {
  return (
    <section
      data-testid="project-detail-latest-task-preview"
      className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4"
    >
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
        最近任务预览
      </div>
      {props.latestTask ? (
        <div className="mt-3 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-sm font-medium text-slate-50">
              {props.latestTask.title}
            </div>
            <StatusBadge
              label={
                TASK_STATUS_LABELS[props.latestTask.status] ??
                props.latestTask.status
              }
              tone={mapTaskStatusTone(props.latestTask.status)}
            />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <ProjectMiniStat
              label="优先级"
              value={
                TASK_PRIORITY_LABELS[props.latestTask.priority] ??
                props.latestTask.priority
              }
            />
            <ProjectMiniStat
              label="风险等级"
              value={
                TASK_RISK_LABELS[props.latestTask.risk_level] ??
                props.latestTask.risk_level
              }
            />
            <ProjectMiniStat
              label="人工状态"
              value={
                HUMAN_STATUS_LABELS[props.latestTask.human_status] ??
                props.latestTask.human_status
              }
            />
            <ProjectMiniStat
              label="最近运行"
              value={props.latestTask.latest_run_status ?? "尚无运行"}
            />
          </div>
          {props.latestTask.latest_run_summary ? (
            <p className="text-sm leading-6 text-slate-300">
              运行摘要：{props.latestTask.latest_run_summary}
            </p>
          ) : null}
          <div data-testid="project-detail-latest-run-control-surface-slot">
            <ProjectLatestRunControlSurface
              latestTask={props.latestTask}
              drilldownContext={props.drilldownContext}
              onNavigateToStrategyPreview={
                props.projectId && props.latestTask.latest_run_id
                  ? () =>
                      props.onNavigateToStrategyPreview({
                        source: "project_latest_run",
                        project_id: props.projectId as string,
                        task_id: props.latestTask?.task_id as string,
                        run_id: props.latestTask?.latest_run_id as string,
                      })
                  : null
              }
              onNavigateToTaskDetail={
                props.latestTask.task_id
                  ? props.onNavigateToTaskDetailFromLatestRun
                  : null
              }
              onNavigateToRunLog={
                props.latestTask.latest_run_id
                  ? () =>
                      props.onNavigateToTask?.(props.latestTask?.task_id as string, {
                        runId: props.latestTask?.latest_run_id,
                      })
                  : null
              }
            />
          </div>
        </div>
      ) : props.detail && props.projectTasks.length > 0 ? (
        <p className="mt-3 text-sm leading-6 text-slate-300">
          老板首页聚合数据还未返回最新任务快照；当前可先查看上方的阶段守卫，以及下方的任务树与草案来源。
        </p>
      ) : (
        <p className="mt-3 text-sm leading-6 text-slate-400">
          当前还没有可展示的任务快照；可以先通过上方规划入口生成项目草案并映射任务。
        </p>
      )}
    </section>
  );
}
