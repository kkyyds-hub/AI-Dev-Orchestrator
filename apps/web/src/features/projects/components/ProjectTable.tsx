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
} from "../types";

type ProjectTableProps = {
  projects: BossProjectItem[];
  selectedProjectId: string | null;
  onSelectProject: (projectId: string) => void;
};

export function ProjectTable({
  projects,
  selectedProjectId,
  onSelectProject,
}: ProjectTableProps) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-xl shadow-slate-950/30">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-50">
            项目总览列表
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            先看项目，再看任务；点击“查看详情”可切到右侧项目详情面板。
          </p>
        </div>
        <div className="text-xs text-slate-500">共 {projects.length} 个项目</div>
      </div>

      {projects.length === 0 ? (
        <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 px-4 py-8 text-center text-sm text-slate-400">
          暂无项目，可先通过 `/projects` 创建项目，再在下方任务控制台继续查看历史任务。
        </div>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full border-separate border-spacing-y-3 text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-[0.18em] text-slate-500">
                <th className="px-4 py-2">项目 / 仓库</th>
                <th className="px-4 py-2">阶段 / 状态</th>
                <th className="px-4 py-2">任务聚合</th>
                <th className="px-4 py-2">最新进度</th>
                <th className="px-4 py-2">关键风险</th>
                <th className="px-4 py-2 text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {projects.map((project) => {
                const isSelected = project.id === selectedProjectId;
                return (
                  <tr key={project.id} className="align-top">
                    <td
                      className={`rounded-l-2xl border border-r-0 px-4 py-4 ${
                        isSelected
                          ? "border-cyan-500/40 bg-cyan-500/10"
                          : "border-slate-800 bg-slate-950/70"
                      }`}
                    >
                      <div className="font-medium text-slate-50">
                        {project.name}
                      </div>
                      <p className="mt-2 max-w-xs text-xs leading-6 text-slate-400">
                        {project.summary}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <StatusBadge
                          label={
                            project.repository_workspace
                              ? "仓库已绑定"
                              : "待绑定仓库"
                          }
                          tone={
                            project.repository_workspace ? "success" : "warning"
                          }
                        />
                        <StatusBadge
                          label={buildSnapshotLabel(project)}
                          tone={mapSnapshotTone(project)}
                        />
                        <StatusBadge
                          label={buildChangeSessionLabel(project)}
                          tone={mapChangeSessionTone(project)}
                        />
                      </div>
                      <div className="mt-3 text-xs text-slate-500">
                        预估成本 {formatCurrencyUsd(project.estimated_cost)}
                      </div>
                    </td>

                    <td
                      className={`border border-x-0 px-4 py-4 ${
                        isSelected
                          ? "border-cyan-500/40 bg-cyan-500/10"
                          : "border-slate-800 bg-slate-950/70"
                      }`}
                    >
                      <div className="flex flex-wrap gap-2">
                        <StatusBadge
                          label={
                            PROJECT_STAGE_LABELS[project.stage] ?? project.stage
                          }
                          tone="info"
                        />
                        <StatusBadge
                          label={
                            PROJECT_STATUS_LABELS[project.status] ??
                            project.status
                          }
                          tone={mapProjectStatusTone(project.status)}
                        />
                      </div>
                    </td>

                    <td
                      className={`border border-x-0 px-4 py-4 ${
                        isSelected
                          ? "border-cyan-500/40 bg-cyan-500/10"
                          : "border-slate-800 bg-slate-950/70"
                      }`}
                    >
                      <div className="space-y-2 text-xs text-slate-300">
                        <AggregateRow
                          label="总任务"
                          value={String(project.task_stats.total_tasks)}
                        />
                        <AggregateRow
                          label="已完成"
                          value={String(project.task_stats.completed_tasks)}
                        />
                        <AggregateRow
                          label="执行中"
                          value={String(project.task_stats.running_tasks)}
                        />
                        <AggregateRow
                          label="阻塞 / 待人工"
                          value={`${project.task_stats.blocked_tasks} / ${project.task_stats.waiting_human_tasks}`}
                        />
                      </div>
                    </td>

                    <td
                      className={`border border-x-0 px-4 py-4 ${
                        isSelected
                          ? "border-cyan-500/40 bg-cyan-500/10"
                          : "border-slate-800 bg-slate-950/70"
                      }`}
                    >
                      <p className="max-w-sm text-xs leading-6 text-slate-300">
                        {project.latest_progress_summary}
                      </p>
                      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                        <span>
                          更新时间 {formatDateTime(project.latest_progress_at)}
                        </span>
                        {project.latest_task ? (
                          <StatusBadge
                            label={project.latest_task.title}
                            tone={mapTaskStatusTone(project.latest_task.status)}
                          />
                        ) : null}
                      </div>
                    </td>

                    <td
                      className={`border border-x-0 px-4 py-4 ${
                        isSelected
                          ? "border-cyan-500/40 bg-cyan-500/10"
                          : "border-slate-800 bg-slate-950/70"
                      }`}
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge
                          label={
                            PROJECT_RISK_LABELS[project.risk_level] ??
                            project.risk_level
                          }
                          tone={mapProjectRiskTone(project.risk_level)}
                        />
                        {project.high_risk_task_count > 0 ? (
                          <span className="text-xs text-slate-500">
                            高风险任务 {project.high_risk_task_count}
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-3 max-w-sm text-xs leading-6 text-slate-300">
                        {project.key_risk_summary}
                      </p>
                    </td>

                    <td
                      className={`rounded-r-2xl border border-l-0 px-4 py-4 text-right ${
                        isSelected
                          ? "border-cyan-500/40 bg-cyan-500/10"
                          : "border-slate-800 bg-slate-950/70"
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => onSelectProject(project.id)}
                        className="inline-flex rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-xs font-medium text-cyan-100 transition hover:border-cyan-400 hover:bg-cyan-500/20"
                      >
                        {isSelected ? "已在详情中" : "查看详情"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function AggregateRow(props: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-800/80 bg-slate-950/60 px-3 py-2">
      <span className="text-slate-400">{props.label}</span>
      <span className="font-medium text-slate-100">{props.value}</span>
    </div>
  );
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

function mapSnapshotTone(
  project: BossProjectItem,
): "neutral" | "info" | "success" | "warning" | "danger" {
  if (!project.repository_workspace) {
    return "neutral";
  }
  if (!project.latest_repository_snapshot) {
    return "info";
  }
  return project.latest_repository_snapshot.status === "success"
    ? "success"
    : "danger";
}

function buildChangeSessionLabel(project: BossProjectItem) {
  if (!project.repository_workspace) {
    return "未开始会话";
  }
  if (!project.current_change_session) {
    return "待记录会话";
  }
  if (project.current_change_session.guard_status === "blocked") {
    return "会话阻断";
  }
  if (project.current_change_session.workspace_status === "dirty") {
    return "工作区脏";
  }
  return "会话可复用";
}

function mapChangeSessionTone(
  project: BossProjectItem,
): "neutral" | "info" | "success" | "warning" | "danger" {
  if (!project.repository_workspace) {
    return "neutral";
  }
  if (!project.current_change_session) {
    return "info";
  }
  if (
    project.current_change_session.guard_status === "blocked" ||
    project.current_change_session.workspace_status === "dirty"
  ) {
    return "warning";
  }
  return "success";
}
