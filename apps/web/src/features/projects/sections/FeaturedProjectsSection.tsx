import { StatusBadge } from "../../../components/StatusBadge";
import { formatCurrencyUsd } from "../../../lib/format";
import { mapProjectRiskTone, mapProjectStatusTone } from "../../../lib/status";
import type { BossProjectItem } from "../types";
import {
  PROJECT_RISK_LABELS,
  PROJECT_STAGE_LABELS,
  PROJECT_STATUS_LABELS,
} from "../types";

type FeaturedProjectsSectionProps = {
  featuredProjects: BossProjectItem[];
  selectedProjectId: string | null;
  onSelectProject: (projectId: string) => void;
};

export function FeaturedProjectsSection(props: FeaturedProjectsSectionProps) {
  return (
    <section data-testid="featured-projects-section" className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-50">重点项目卡片</h2>
        <p className="text-xs text-slate-500">默认按阻塞风险和最近进展排序</p>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        {props.featuredProjects.map((project) => (
          <button
            key={project.id}
            type="button"
            data-testid={`featured-project-card-${project.id}`}
            onClick={() => props.onSelectProject(project.id)}
            className={`rounded-2xl border p-5 text-left transition ${
              project.id === props.selectedProjectId
                ? "border-cyan-500/40 bg-cyan-500/10 shadow-lg shadow-cyan-950/20"
                : "border-slate-800 bg-slate-900/70 hover:border-slate-700 hover:bg-slate-900"
            }`}
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-lg font-semibold text-slate-50">{project.name}</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  <StatusBadge
                    label={PROJECT_STAGE_LABELS[project.stage] ?? project.stage}
                    tone="info"
                  />
                  <StatusBadge
                    label={PROJECT_STATUS_LABELS[project.status] ?? project.status}
                    tone={mapProjectStatusTone(project.status)}
                  />
                </div>
              </div>

              <StatusBadge
                label={PROJECT_RISK_LABELS[project.risk_level] ?? project.risk_level}
                tone={mapProjectRiskTone(project.risk_level)}
              />
            </div>

            <p className="mt-4 text-sm leading-6 text-slate-300">{project.summary}</p>
            <p className="mt-4 text-sm leading-6 text-slate-200">
              {project.latest_progress_summary}
            </p>
            <p className="mt-3 text-xs leading-6 text-slate-400">{project.key_risk_summary}</p>

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <MiniStat
                label="任务状态"
                value={`${project.task_stats.completed_tasks}/${project.task_stats.total_tasks} 完成`}
              />
              <MiniStat label="预估成本" value={formatCurrencyUsd(project.estimated_cost)} />
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}

function MiniStat(props: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
        {props.label}
      </div>
      <div className="mt-2 text-sm font-medium text-slate-100">{props.value}</div>
    </div>
  );
}
