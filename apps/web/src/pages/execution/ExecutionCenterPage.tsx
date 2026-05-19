import { useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useBackendHealth, useConsoleOverview } from "../../features/console/hooks";
import { useConsoleEventStream } from "../../features/events/hooks";
import { formatDateTime } from "../../lib/format";
import { useProjectScope } from "../shared/useProjectScope";

const TABS = [
  { key: "tasks", label: "任务队列" },
  { key: "runs", label: "运行观测" },
  { key: "repository", label: "仓库工作区" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export function ExecutionCenterPage() {
  const navigate = useNavigate();
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

  const lastUpdatedText = useMemo(() => {
    if (!overviewQuery.dataUpdatedAt) return "暂未刷新";
    return formatDateTime(new Date(overviewQuery.dataUpdatedAt).toISOString());
  }, [overviewQuery.dataUpdatedAt]);

  const total = overviewQuery.data?.total_tasks ?? 0;
  const running = overviewQuery.data?.running_tasks ?? 0;
  const blocked = overviewQuery.data?.blocked_tasks ?? 0;
  const failed = overviewQuery.data?.failed_tasks ?? 0;
  const completed = overviewQuery.data?.completed_tasks ?? 0;
  const waitingHuman = overviewQuery.data?.waiting_human_tasks ?? 0;

  const hasSpecificProject = selectedProjectId !== "all";

  const handleNavigateToTasks = () => {
    if (hasSpecificProject) {
      navigate(`/tasks?projectId=${selectedProjectId}`);
    } else {
      navigate("/tasks");
    }
  };

  const handleNavigateToRuns = () => {
    if (hasSpecificProject) {
      navigate(`/runs?projectId=${selectedProjectId}`);
    } else {
      navigate("/runs");
    }
  };

  const handleNavigateToRepository = () => {
    if (hasSpecificProject) {
      navigate(`/projects/${selectedProjectId}/repository`);
    }
  };

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
          <TabTasks
            total={total}
            running={running}
            blocked={blocked}
            failed={failed}
            waitingHuman={waitingHuman}
            onOpenFull={handleNavigateToTasks}
          />
        )}

        {activeTab === "runs" && (
          <TabRuns
            completed={completed}
            failed={failed}
            running={running}
            onOpenFull={handleNavigateToRuns}
          />
        )}

        {activeTab === "repository" && (
          <TabRepository
            hasSpecificProject={hasSpecificProject}
            projectName={selectedProjectName}
            onOpenRepository={
              hasSpecificProject ? handleNavigateToRepository : undefined
            }
          />
        )}
      </div>
    </div>
  );
}

/* ─── Tab: 任务队列 ─── */

function TabTasks({
  total,
  running,
  blocked,
  failed,
  waitingHuman,
  onOpenFull,
}: {
  total: number;
  running: number;
  blocked: number;
  failed: number;
  waitingHuman: number;
  onOpenFull: () => void;
}) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
        <StatItem label="总数" value={total} />
        <StatItem label="运行中" value={running} />
        <StatItem label="阻塞" value={blocked} />
        <StatItem label="失败" value={failed} />
        <StatItem label="待确认" value={waitingHuman} />
      </div>

      <button
        type="button"
        onClick={onOpenFull}
        className="rounded border border-[#444444] px-4 py-2 text-sm text-zinc-300 transition hover:border-zinc-400 hover:bg-[#222222]"
      >
        打开完整任务队列
      </button>
    </div>
  );
}

/* ─── Tab: 运行观测 ─── */

function TabRuns({
  completed,
  failed,
  running,
  onOpenFull,
}: {
  completed: number;
  failed: number;
  running: number;
  onOpenFull: () => void;
}) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-2 max-w-sm">
        <StatItem label="已完成" value={completed} />
        <StatItem label="失败" value={failed} />
        <StatItem label="运行中" value={running} />
      </div>

      <button
        type="button"
        onClick={onOpenFull}
        className="rounded border border-[#444444] px-4 py-2 text-sm text-zinc-300 transition hover:border-zinc-400 hover:bg-[#222222]"
      >
        打开完整运行观测
      </button>
    </div>
  );
}

/* ─── Tab: 仓库工作区 ─── */

function TabRepository({
  hasSpecificProject,
  projectName,
  onOpenRepository,
}: {
  hasSpecificProject: boolean;
  projectName: string;
  onOpenRepository: (() => void) | undefined;
}) {
  if (!hasSpecificProject) {
    return (
      <div className="space-y-3">
        <button
          type="button"
          disabled
          className="rounded border border-[#333333] px-4 py-2 text-sm text-zinc-600 cursor-not-allowed"
        >
          打开仓库工作区
        </button>
        <p className="text-xs text-zinc-600">需先选择具体项目</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-500">当前项目：{projectName}</p>

      <button
        type="button"
        onClick={onOpenRepository}
        className="rounded border border-[#444444] px-4 py-2 text-sm text-zinc-300 transition hover:border-zinc-400 hover:bg-[#222222]"
      >
        打开仓库工作区
      </button>
    </div>
  );
}

/* ─── Stat Item ─── */

function StatItem({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-[#333333] px-3 py-2 text-center">
      <div className="text-xs text-zinc-500">{label}</div>
      <div className="text-lg font-medium text-zinc-300">{value}</div>
    </div>
  );
}
