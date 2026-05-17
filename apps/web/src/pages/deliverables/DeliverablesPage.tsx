import { useNavigate, useSearchParams } from "react-router-dom";

import { DeliverableCenterPage } from "../../features/deliverables/DeliverableCenterPage";
import { buildTaskRoute } from "../../lib/task-route";
import { useProjectScope } from "../shared/useProjectScope";

export function DeliverablesPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const requestedDeliverableId = searchParams.get("deliverableId");
  const { selectedProjectId, setSelectedProjectId, projects, selectedProjectName, projectNotFound } =
    useProjectScope();

  const selectedProjectNameOrNull = selectedProjectId === "all" ? null : selectedProjectName;

  const handleProjectChange = (nextId: string) => {
    setSelectedProjectId(nextId);
    // Navigate to the canonical URL so setSearchParams inside
    // setSelectedProjectId can't race-stomp the deliverableId cleanup.
    navigate(
      nextId === "all" ? "/deliverables" : `/deliverables?projectId=${encodeURIComponent(nextId)}`,
      { replace: true },
    );
  };

  return (
    <div className="space-y-6">
      <header className="border-b border-white/10 pb-6" data-testid="deliverables-page-header">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-500">
              Deliverables
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-zinc-100">
              交付物中心
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-400">
              选择项目后浏览该项目的交付物、版本快照和关联任务。
            </p>
          </div>

          <div className="w-full min-w-0 xl:w-[360px]">
            <label className="text-xs uppercase tracking-[0.2em] text-zinc-500">
              当前项目
            </label>
            <select
              value={selectedProjectId}
              onChange={(event) => handleProjectChange(event.target.value)}
              className="mt-2 w-full rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-zinc-100 outline-none ring-0 transition focus:border-white/20"
            >
              <option value="all" className="bg-[#161616] text-zinc-100">
                全部项目 · 请先选择项目查看交付物
              </option>
              {projects.map((project) => (
                <option key={project.id} value={project.id} className="bg-[#161616] text-zinc-100">
                  {project.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </header>

      {projectNotFound ? (
        <div className="rounded-2xl border border-amber-500/[0.15] bg-amber-500/[0.06] px-4 py-3 text-sm leading-6 text-amber-200">
          当前项目不存在或已被删除。{" "}
          <button
            type="button"
            onClick={() => setSelectedProjectId("all")}
            className="underline transition hover:text-amber-100"
          >
            切回全部项目
          </button>
        </div>
      ) : null}

      {selectedProjectId === "all" ? (
        <section className="border-y border-dashed border-white/10 py-6">
          <h2 className="text-base font-semibold text-zinc-100">选择项目后查看交付物</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
            请使用上方项目选择器选择一个项目，然后查看该项目的交付物详情。
          </p>
        </section>
      ) : (
        <DeliverableCenterPage
          projectId={selectedProjectId}
          projectName={selectedProjectNameOrNull}
          requestedDeliverableId={requestedDeliverableId}
          onNavigateToTask={(taskId, options) =>
            navigate(
              buildTaskRoute({
                taskId,
                runId: options?.runId ?? null,
                from: "deliverables",
                projectId: selectedProjectId === "all" ? null : selectedProjectId,
              }),
            )
          }
        />
      )}
    </div>
  );
}
