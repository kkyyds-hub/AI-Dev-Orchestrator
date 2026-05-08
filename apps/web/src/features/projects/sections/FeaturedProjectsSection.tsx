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
    <section
      data-testid="featured-projects-section"
      className="space-y-4 border-b border-[#333333] pb-8"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-600">
            Focus Queue
          </p>
          <h2 className="mt-2 text-lg font-semibold text-zinc-100">重点项目</h2>
        </div>
        <p className="text-xs text-zinc-600">按阻塞风险和最近进展排序</p>
      </div>

      <div className="divide-y divide-[#333333]">
        {props.featuredProjects.map((project) => (
          <button
            key={project.id}
            type="button"
            data-testid={`featured-project-card-${project.id}`}
            onClick={() => props.onSelectProject(project.id)}
            className={`w-full py-4 text-left transition first:pt-0 last:pb-0 ${
              project.id === props.selectedProjectId
                ? "border-l-2 border-l-zinc-300 pl-4"
                : "pl-4 hover:border-l-2 hover:border-l-[#555555]"
            }`}
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-lg font-semibold text-zinc-100">{project.name}</div>
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

            <p className="mt-4 text-sm leading-6 text-zinc-400">{project.summary}</p>
            <p className="mt-4 text-sm leading-6 text-zinc-300">
              {project.latest_progress_summary}
            </p>
            <p className="mt-3 text-xs leading-6 text-zinc-500">{project.key_risk_summary}</p>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
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
    <div className="border-l border-[#333333] px-4 py-2">
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
        {props.label}
      </div>
      <div className="mt-2 text-sm font-medium text-zinc-100">{props.value}</div>
    </div>
  );
}
