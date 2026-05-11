import { StatusBadge } from "../../../components/StatusBadge";
import { formatCurrencyUsd, formatDateTime } from "../../../lib/format";
import {
  mapProjectRiskTone,
  mapProjectStatusTone,
  mapTaskStatusTone,
} from "../../../lib/status";
import type { BossProjectItem } from "../types";
import {
  PROJECT_RISK_LABELS,
  PROJECT_STAGE_LABELS,
  PROJECT_STATUS_LABELS,
  TASK_STATUS_LABELS,
} from "../types";

type ProjectTableProps = {
  projects: BossProjectItem[];
  selectedProjectId: string | null;
  onSelectProject: (projectId: string) => void;
  maxRows?: number;
  onCreateProjectDraft: () => void;
};

export function ProjectTable({
  projects,
  selectedProjectId,
  onSelectProject,
  maxRows = 6,
  onCreateProjectDraft,
}: ProjectTableProps) {
  const visibleProjects = projects.slice(0, maxRows);
  const hiddenProjectCount = Math.max(0, projects.length - visibleProjects.length);

  return (
    <section className="min-w-0 border-b border-[#333333] pb-7">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium tracking-[0.24em] text-zinc-600">
            项目队列
          </p>
          <h2 className="mt-2 text-lg font-semibold text-zinc-100">
            项目工作清单
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            按项目汇总任务、进展和风险，方便快速选择处理对象。
          </p>
        </div>
        <div className="text-xs text-zinc-600">共 {projects.length} 个项目</div>
      </div>

      {projects.length === 0 ? (
        <div className="mt-4 border border-dashed border-[#3a3a3a] px-4 py-8 text-center text-sm text-zinc-500">
          <p className="text-base font-medium text-zinc-300">还没有项目</p>
          <p className="mt-2">可以先创建一个项目草案，再确认生成项目与任务。</p>
          <button
            type="button"
            onClick={onCreateProjectDraft}
            className="mt-4 inline-flex rounded border border-zinc-300 bg-zinc-100 px-4 py-2 text-sm font-semibold text-zinc-950 transition hover:bg-white"
          >
            创建项目草案
          </button>
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          {visibleProjects.map((project) => {
            const isSelected = project.id === selectedProjectId;

            return (
              <button
                key={project.id}
                type="button"
                data-testid={`project-row-${project.id}`}
                onClick={() => onSelectProject(project.id)}
                className={`w-full border px-4 py-4 text-left transition ${
                  isSelected
                    ? "border-[#555555] bg-white/[0.035] shadow-[inset_3px_0_0_#d4d4d8]"
                    : "border-[#333333] bg-transparent hover:border-[#4a4a4a] hover:bg-white/[0.02]"
                }`}
              >
                <div className="flex min-w-0 flex-col gap-4">
                  <div className="flex min-w-0 flex-col gap-3 2xl:flex-row 2xl:items-start 2xl:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="min-w-0 break-words text-base font-semibold text-zinc-100">
                          {project.name}
                        </h3>
                        {isSelected ? (
                          <span className="shrink-0 text-xs text-zinc-500">当前查看</span>
                        ) : null}
                      </div>
                      <p className="mt-2 line-clamp-2 text-sm leading-6 text-zinc-500">
                        {project.summary}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <StatusBadge
                          label={PROJECT_STAGE_LABELS[project.stage] ?? "未知阶段"}
                          tone="info"
                        />
                        <StatusBadge
                          label={PROJECT_STATUS_LABELS[project.status] ?? "未知状态"}
                          tone={mapProjectStatusTone(project.status)}
                        />
                        <StatusBadge
                          label={buildRepositoryLabel(project)}
                          tone={project.repository_workspace ? "success" : "warning"}
                        />
                      </div>
                    </div>

                    <div className="flex shrink-0 flex-wrap items-center gap-3 2xl:justify-end">
                      <span className="text-xs text-zinc-600">
                        {formatCurrencyUsd(project.estimated_cost)}
                      </span>
                      <span className="inline-flex rounded border border-[#4a4a4a] px-3 py-2 text-xs font-medium text-zinc-100">
                        {isSelected ? "已选中" : "查看摘要"}
                      </span>
                    </div>
                  </div>

                  <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(180px,0.78fr)_minmax(0,1.12fr)_minmax(0,1fr)]">
                    <div className="grid grid-cols-3 gap-3 rounded border border-[#333333] px-3 py-3">
                      <MiniMetric
                        label="任务"
                        value={`${project.task_stats.completed_tasks}/${project.task_stats.total_tasks}`}
                        hint="已完成/总数"
                      />
                      <MiniMetric
                        label="执行"
                        value={String(project.task_stats.running_tasks)}
                        hint="运行中"
                      />
                      <MiniMetric
                        label="阻塞"
                        value={`${project.task_stats.blocked_tasks}/${project.task_stats.waiting_human_tasks}`}
                        hint="阻塞/待人工"
                        valueClassName={
                          project.task_stats.blocked_tasks +
                            project.task_stats.waiting_human_tasks >
                          0
                            ? "text-amber-200"
                            : undefined
                        }
                      />
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <div className="min-w-0">
                        <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-600">
                          <span>最新进展</span>
                          <span>{formatDateTime(project.latest_progress_at)}</span>
                        </div>
                        <p className="line-clamp-2 text-sm leading-6 text-zinc-400">
                          {project.latest_progress_summary}
                        </p>
                        {project.latest_task ? (
                          <div className="mt-3 flex min-w-0 flex-wrap items-center gap-2">
                            <StatusBadge
                              label={
                                TASK_STATUS_LABELS[project.latest_task.status] ??
                                "未知任务状态"
                              }
                              tone={mapTaskStatusTone(project.latest_task.status)}
                            />
                            <span className="min-w-0 truncate text-xs text-zinc-500">
                              {project.latest_task.title}
                            </span>
                          </div>
                        ) : null}
                      </div>
                    </div>

                    <div className="min-w-0">
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <span className="text-xs text-zinc-600">风险</span>
                        <StatusBadge
                          label={PROJECT_RISK_LABELS[project.risk_level] ?? "未知风险"}
                          tone={mapProjectRiskTone(project.risk_level)}
                        />
                        {project.high_risk_task_count > 0 ? (
                          <span className="text-xs text-zinc-500">
                            高风险 {project.high_risk_task_count}
                          </span>
                        ) : null}
                      </div>
                      <p className="line-clamp-2 break-words text-sm leading-6 text-zinc-500">
                        {project.key_risk_summary}
                      </p>
                      <div className="mt-3 text-xs text-zinc-600">
                        {buildSnapshotLabel(project)}
                      </div>
                    </div>
                  </div>
                </div>
              </button>
            );
          })}

          {hiddenProjectCount > 0 ? (
            <p className="text-xs text-zinc-600">
              还有 {hiddenProjectCount} 个项目未在当前总览展开；此处仅保留最需要处理的队列。
            </p>
          ) : null}
        </div>
      )}
    </section>
  );
}

function MiniMetric(props: {
  label: string;
  value: string;
  hint: string;
  valueClassName?: string;
}) {
  return (
    <div className="min-w-0">
      <div className="text-xs text-zinc-600">{props.label}</div>
      <div
        className={`mt-1 font-mono text-lg font-semibold ${
          props.valueClassName ?? "text-zinc-100"
        }`}
      >
        {props.value}
      </div>
      <div className="mt-1 text-xs text-zinc-600">{props.hint}</div>
    </div>
  );
}

function buildRepositoryLabel(project: BossProjectItem) {
  return project.repository_workspace ? "仓库已绑定" : "待绑定仓库";
}

function buildSnapshotLabel(project: BossProjectItem) {
  if (!project.repository_workspace) {
    return "无仓库快照";
  }
  if (!project.latest_repository_snapshot) {
    return "待生成快照";
  }
  return project.latest_repository_snapshot.status === "success"
    ? "快照已就绪"
    : "快照失败";
}
