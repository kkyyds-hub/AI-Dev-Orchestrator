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
  maxRows?: number;
};

export function ProjectTable({
  projects,
  selectedProjectId,
  onSelectProject,
  maxRows = 6,
}: ProjectTableProps) {
  const visibleProjects = projects.slice(0, maxRows);
  const hiddenProjectCount = Math.max(0, projects.length - visibleProjects.length);

  return (
    <section className="min-w-0 border-b border-[#333333] pb-7">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-600">
            Project Workspace
          </p>
          <h2 className="mt-2 text-lg font-semibold text-zinc-100">
            项目队列
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            默认展示最需要关注的 {visibleProjects.length} 个项目，点选后查看右侧摘要。
          </p>
        </div>
        <div className="text-xs text-zinc-600">共 {projects.length} 个项目</div>
      </div>

      {projects.length === 0 ? (
        <div className="mt-4 border border-dashed border-[#3a3a3a] px-4 py-8 text-center text-sm text-zinc-500">
          暂无项目；可展开下方“新建项目”入口创建项目。
        </div>
      ) : (
        <div className="mt-4 overflow-x-auto border-t border-[#333333]">
          <table className="min-w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-[#333333] text-left text-xs uppercase tracking-[0.18em] text-zinc-600">
                <th className="px-3 py-3">项目</th>
                <th className="px-3 py-3">阶段</th>
                <th className="px-3 py-3">任务</th>
                <th className="px-3 py-3">进度</th>
                <th className="px-3 py-3">风险</th>
                <th className="px-3 py-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {visibleProjects.map((project) => {
                const isSelected = project.id === selectedProjectId;
                const rowClassName = isSelected
                  ? "border-b border-[#444444] bg-white/[0.03] align-top"
                  : "border-b border-[#333333] align-top transition hover:bg-white/[0.02]";

                return (
                  <tr key={project.id} className={rowClassName}>
                    <td
                      className={`px-3 py-4 ${
                        isSelected
                          ? "border-l-2 border-l-zinc-300"
                          : "border-l-2 border-l-transparent"
                      }`}
                    >
                      <div className="font-medium text-zinc-100">{project.name}</div>
                      <p className="mt-2 max-w-xs line-clamp-2 text-xs leading-5 text-zinc-500">
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
                      </div>
                    </td>

                    <td className="px-3 py-4">
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

                    <td className="px-3 py-4">
                      <div className="text-xs leading-6 text-zinc-400">
                        <div>总数 {project.task_stats.total_tasks}</div>
                        <div>完成 {project.task_stats.completed_tasks}</div>
                        <div>阻塞/待人工 {project.task_stats.blocked_tasks} / {project.task_stats.waiting_human_tasks}</div>
                      </div>
                    </td>

                    <td className="px-3 py-4">
                      <p className="max-w-sm line-clamp-2 text-xs leading-5 text-zinc-400">
                        {project.latest_progress_summary}
                      </p>
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-zinc-600">
                        <span>{formatDateTime(project.latest_progress_at)}</span>
                        {project.latest_task ? (
                          <StatusBadge
                            label={project.latest_task.title}
                            tone={mapTaskStatusTone(project.latest_task.status)}
                          />
                        ) : null}
                      </div>
                    </td>

                    <td className="px-3 py-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge
                          label={
                            PROJECT_RISK_LABELS[project.risk_level] ??
                            project.risk_level
                          }
                          tone={mapProjectRiskTone(project.risk_level)}
                        />
                        {project.high_risk_task_count > 0 ? (
                          <span className="text-xs text-zinc-600">
                            高风险 {project.high_risk_task_count}
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-2 max-w-sm line-clamp-2 text-xs leading-5 text-zinc-500">
                        {project.key_risk_summary}
                      </p>
                    </td>

                    <td className="px-3 py-4 text-right">
                      <button
                        type="button"
                        onClick={() => onSelectProject(project.id)}
                        className="inline-flex rounded border border-[#4a4a4a] bg-transparent px-3 py-2 text-xs font-medium text-zinc-100 transition hover:border-zinc-500 hover:bg-[#292929]"
                      >
                        {isSelected ? "已选中" : "查看"}
                      </button>
                      <div className="mt-2 text-xs text-zinc-600">
                        {formatCurrencyUsd(project.estimated_cost)}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {hiddenProjectCount > 0 ? (
            <p className="mt-3 text-xs text-zinc-600">
              还有 {hiddenProjectCount} 个项目未在首页展开；可通过项目筛选或后续列表视图继续查看。
            </p>
          ) : null}
        </div>
      )}
    </section>
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
