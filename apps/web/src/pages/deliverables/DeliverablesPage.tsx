import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import { DeliverableCenterPage } from "../../features/deliverables/DeliverableCenterPage";
import { useBossProjectOverview } from "../../features/projects/hooks";

type DeliverablesPageProps = {
  onNavigateToTask: (taskId: string, options?: { runId?: string | null }) => void;
};

export function DeliverablesPage(props: DeliverablesPageProps) {
  const [searchParams] = useSearchParams();
  const overviewQuery = useBossProjectOverview();
  const projectId = searchParams.get("projectId");
  const requestedDeliverableId = searchParams.get("deliverableId");

  const selectedProject = useMemo(
    () => overviewQuery.data?.projects.find((project) => project.id === projectId) ?? null,
    [overviewQuery.data?.projects, projectId],
  );

  return (
    <div className="space-y-6">
      {!projectId ? (
        <section className="rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30">
          <div className="max-w-3xl">
            <div className="text-xs font-medium uppercase tracking-[0.24em] text-cyan-300">
              Deliverables
            </div>
            <h3 className="mt-2 text-xl font-semibold text-slate-50">交付物中心</h3>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              当前顶级 Deliverables 域已建立正式入口。由于现阶段的交付物数据仍依赖项目上下文，
              请先通过
              <code className="mx-1 rounded bg-slate-900 px-1.5 py-0.5">projectId</code>
              指定项目，再进入对应交付物中心，例如：
              <code className="mx-1 rounded bg-slate-900 px-1.5 py-0.5">
                /deliverables?projectId=your-project-id
              </code>
              。
            </p>
          </div>
        </section>
      ) : null}

      {projectId && !selectedProject && !overviewQuery.isLoading ? (
        <section className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm leading-6 text-amber-100">
          当前 URL 中的项目 ID
          <code className="mx-1 rounded bg-slate-950/40 px-1.5 py-0.5">{projectId}</code>
          未出现在当前项目列表中。你仍然可以继续访问该页面，但建议核对 projectId 是否正确。
        </section>
      ) : null}

      <DeliverableCenterPage
        projectId={projectId}
        projectName={selectedProject?.name ?? null}
        requestedDeliverableId={requestedDeliverableId}
        onNavigateToTask={props.onNavigateToTask}
      />
    </div>
  );
}
