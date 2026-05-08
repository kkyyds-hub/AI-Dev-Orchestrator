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
    <section className="min-w-0 border-b border-[#333333] pb-8">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-600">
            Project Workspace
          </p>
          <h2 className="mt-2 text-lg font-semibold text-zinc-100">
            项目总览列表
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            先看项目，再看任务；点击“查看详情”可切到右侧项目详情面板。
          </p>
        </div>
        <div className="text-xs text-zinc-600">共 {projects.length} 个项目</div>
      </div>

      {projects.length === 0 ? (
        <div className="mt-4 border border-dashed border-[#3a3a3a] px-4 py-8 text-center text-sm text-zinc-500">
          暂无项目，可先通过 `/projects` 创建项目，再在下方任务控制台继续查看历史任务。
        </div>
      ) : (
        <div className="mt-4 overflow-x-auto border-t border-[#333333]">
          <table className="min-w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-[#333333] text-left text-xs uppercase tracking-[0.18em] text-zinc-600">
                <th className="px-3 py-3">项目 / 仓库</th>
                <th className="px-3 py-3">阶段 / 状态</th>
                <th className="px-3 py-3">任务聚合</th>
                <th className="px-3 py-3">最新进度</th>
                <th className="px-3 py-3">关键风险</th>
                <th className="px-3 py-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {projects.map((project) => {
                const isSelected = project.id === selectedProjectId;
                const rowClassName = isSelected
                  ? "border-b border-[#444444] bg-white/[0.03] align-top"
                  : "border-b border-[#333333] align-top transition hover:bg-white/[0.02]";

                return (
                  <tr key={project.id} className={rowClassName}>
                    <td className={`px-3 py-4 ${isSelected ? "border-l-2 border-l-zinc-300" : "border-l-2 border-l-transparent"}`}>
                      <div className="font-medium text-zinc-100">{project.name}</div>
                      <p className="mt-2 max-w-xs text-xs leading-6 text-zinc-500">
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
                      <div className="mt-3 text-xs text-zinc-600">
                        预估成本 {formatCurrencyUsd(project.estimated_cost)}
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
                      <div className="space-y-2 text-xs text-zinc-400">
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

                    <td className="px-3 py-4">
                      <p className="max-w-sm text-xs leading-6 text-zinc-400">
                        {project.latest_progress_summary}
                      </p>
                      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-zinc-600">
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
                            高风险任务 {project.high_risk_task_count}
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-3 max-w-sm text-xs leading-6 text-zinc-400">
                        {project.key_risk_summary}
                      </p>
                    </td>

                    <td className="px-3 py-4 text-right">
                      <button
                        type="button"
                        onClick={() => onSelectProject(project.id)}
                        className="inline-flex rounded border border-[#4a4a4a] bg-transparent px-3 py-2 text-xs font-medium text-zinc-100 transition hover:border-zinc-500 hover:bg-[#292929]"
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
    <div className="flex items-center justify-between gap-3 border-b border-[#333333]/70 pb-1 last:border-b-0">
      <span className="text-zinc-500">{props.label}</span>
      <span className="font-medium text-zinc-100">{props.value}</span>
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
