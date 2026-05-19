import { useNavigate, useSearchParams } from "react-router-dom";

import { DeliverableCenterPage } from "../../features/deliverables/DeliverableCenterPage";
import { ApprovalInboxPage } from "../../features/approvals/ApprovalInboxPage";
import { buildTaskRoute } from "../../lib/task-route";
import { useProjectScope } from "../shared/useProjectScope";

const TABS = [
  { key: "deliverables", label: "交付物" },
  { key: "approvals", label: "审批" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

export function DeliveryCenterPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { selectedProjectId, setSelectedProjectId, projects, selectedProjectName, projectNotFound } =
    useProjectScope();

  const rawTab = searchParams.get("tab") ?? "";
  const activeTab: TabKey = rawTab === "approvals" ? "approvals" : "deliverables";

  const deliverableId = activeTab === "deliverables" ? searchParams.get("deliverableId") : null;
  const approvalId = activeTab === "approvals" ? searchParams.get("approvalId") : null;
  const projectName = selectedProjectId === "all" ? null : selectedProjectName;

  const setActiveTab = (tab: TabKey) => {
    const next = new URLSearchParams(searchParams);
    next.set("tab", tab);
    if (selectedProjectId !== "all") {
      next.set("projectId", selectedProjectId);
    } else {
      next.delete("projectId");
    }
    setSearchParams(next, { replace: true });
  };

  const handleProjectChange = (nextId: string) => {
    setSelectedProjectId(nextId);
    const next = new URLSearchParams();
    next.set("tab", activeTab);
    if (nextId !== "all") next.set("projectId", nextId);
    navigate(`/delivery?${next.toString()}`, { replace: true });
  };

  return (
    <div className="relative min-w-0 space-y-5">
      {/* Header */}
      <header className="border-b border-[#333333] pb-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">
              成果中心
            </h1>
            <p className="mt-1 text-sm text-zinc-500">
              {selectedProjectId === "all"
                ? "全部项目"
                : `当前项目：${selectedProjectName}`}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <label className="text-xs text-zinc-500">项目</label>
            <select
              value={selectedProjectId}
              onChange={(e) => handleProjectChange(e.target.value)}
              className="rounded border border-[#333333] bg-[#1a1a1a] px-2.5 py-1 text-xs text-zinc-300 outline-none focus:border-zinc-500"
            >
              <option value="all">全部项目</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[#333333]">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setActiveTab(t.key)}
            className={`px-4 py-2 text-sm transition border-b-2 -mb-[1px] ${
              activeTab === t.key
                ? "border-zinc-400 text-zinc-200"
                : "border-transparent text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {projectNotFound ? (
        <div className="rounded border border-zinc-700 px-4 py-3 text-sm text-zinc-400">
          项目不存在或已删除。{" "}
          <button onClick={() => setSelectedProjectId("all")} className="underline hover:text-zinc-200">
            切回全部项目
          </button>
        </div>
      ) : selectedProjectId === "all" ? (
        <div className="rounded border border-[#333333] px-4 py-6 text-sm text-zinc-500 text-center">
          请选择一个项目
        </div>
      ) : (
        <div className="min-h-[400px]">
          {activeTab === "deliverables" && (
            <DeliverableCenterPage
              projectId={selectedProjectId}
              projectName={projectName}
              requestedDeliverableId={deliverableId}
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
          {activeTab === "approvals" && (
            <ApprovalInboxPage
              projectId={selectedProjectId}
              projectName={projectName}
              requestedApprovalId={approvalId}
            />
          )}
        </div>
      )}
    </div>
  );
}
