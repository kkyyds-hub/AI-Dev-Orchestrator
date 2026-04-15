import { RepositoryHomeCard } from "../../repositories/RepositoryHomeCard";
import type { BossProjectItem } from "../types";

type RepositoryOverviewSectionProps = {
  featuredProjects: BossProjectItem[];
  selectedProjectId: string | null;
  onSelectProject: (projectId: string) => void;
};

export function RepositoryOverviewSection(props: RepositoryOverviewSectionProps) {
  return (
    <section data-testid="repository-overview-section" className="space-y-4">
              <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-slate-50">
                    仓库入口概览
                  </h2>
                  <p className="mt-1 text-sm text-slate-400">
                    把项目阶段统计、任务概览和仓库摘要放在同一屏联动查看；每张卡片只展示绑定、快照和变更会话的 Day04 最小入口。
                  </p>
                </div>
                <div className="text-xs text-slate-500">
                  默认展示当前排序最靠前的 {props.featuredProjects.length} 个项目
                </div>
              </div>

              <div className="grid gap-4 xl:grid-cols-3">
                {props.featuredProjects.map((project) => (
                  <RepositoryHomeCard
                    key={`repository-home-${project.id}`}
                    workspace={project.repository_workspace}
                    snapshot={project.latest_repository_snapshot}
                    changeSession={project.current_change_session}
                    title={project.name}
                    description={project.summary}
                    variant="compact"
                    actionLabel={
                      project.id === props.selectedProjectId ? "已在详情中" : "查看项目详情"
                    }
                    onAction={() =>
                      props.onSelectProject(project.id)
                    }
                  />
                ))}
              </div>
            </section>
  );
}
