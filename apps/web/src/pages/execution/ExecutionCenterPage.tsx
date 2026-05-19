import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import { useBackendHealth, useConsoleOverview } from "../../features/console/hooks";
import { useConsoleEventStream } from "../../features/events/hooks";
import { formatDateTime } from "../../lib/format";
import { useProjectScope } from "../shared/useProjectScope";
import { ExecutionRepositoryTab } from "./components/ExecutionRepositoryTab";
import { ExecutionRunsTab } from "./components/ExecutionRunsTab";
import { ExecutionTasksTab } from "./components/ExecutionTasksTab";

const TABS = [
  { key: "tasks", label: "任务队列" },
  { key: "runs", label: "运行观测" },
  { key: "repository", label: "仓库工作区" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export function ExecutionCenterPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const realtime = useConsoleEventStream();
  const overviewQuery = useConsoleOverview({
    enablePollingFallback: realtime.status !== "open",
  });
  const healthQuery = useBackendHealth();
  const { selectedProjectId, selectedProjectName } = useProjectScope();

  const rawTab = searchParams.get("tab") ?? "";
  const activeTab: TabKey =
    rawTab === "runs" || rawTab === "repository" ? rawTab : "tasks";

  const taskId = searchParams.get("taskId") ?? null;

  const setActiveTab = (tab: TabKey) => {
    const next = new URLSearchParams(searchParams);
    next.set("tab", tab);
    // clear taskId when switching away from tasks tab
    if (tab !== "tasks") next.delete("taskId");
    if (selectedProjectId !== "all") {
      next.set("projectId", selectedProjectId);
    } else {
      next.delete("projectId");
    }
    setSearchParams(next, { replace: true });
  };

  const lastUpdatedText = useMemo(() => {
    if (!overviewQuery.dataUpdatedAt) return "暂未刷新";
    return formatDateTime(new Date(overviewQuery.dataUpdatedAt).toISOString());
  }, [overviewQuery.dataUpdatedAt]);

  return (
    <div className="relative min-w-0 space-y-5">
      {/* Header */}
      <header className="border-b border-[#333333] pb-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">
              执行中心
            </h1>
            <p className="mt-1 text-sm text-zinc-500">
              {selectedProjectId === "all"
                ? "全部项目"
                : `当前项目：${selectedProjectName}`}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
            <span className="inline-flex items-center gap-1 rounded-full border border-zinc-600 px-2.5 py-0.5 text-xs text-zinc-400">
              {healthQuery.data?.status === "ok" ? "后端在线" : "后端未知"}
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-zinc-600 px-2.5 py-0.5 text-xs text-zinc-400">
              {realtime.status === "open" ? "实时已连接" : "实时未连接"}
            </span>
            <span className="text-zinc-600">更新 {lastUpdatedText}</span>
          </div>
        </div>
      </header>

      {/* 页签 */}
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

      {/* 页签内容 */}
      <div className="min-h-[320px]">
        {activeTab === "tasks" && (
          <ExecutionTasksTab taskId={taskId} sourceRoute="execution" />
        )}

        {activeTab === "runs" && (
          <ExecutionRunsTab />
        )}

        {activeTab === "repository" && (
          <ExecutionRepositoryTab />
        )}
      </div>
    </div>
  );
}

