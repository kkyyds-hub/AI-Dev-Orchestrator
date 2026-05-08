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
                  <h2 className="text-lg font-semibold text-zinc-100">
                    仓库入口概览
                  </h2>
                  <p className="mt-1 text-sm text-zinc-500">
                    汇总项目仓库绑定、最新快照与当前变更会话。
                  </p>
                </div>
                <div className="text-xs text-zinc-600">
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
