import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { useBackendHealth, useConsoleOverview } from "../../features/console/hooks";
import { useConsoleEventStream } from "../../features/events/hooks";
import { formatDateTime } from "../../lib/format";
import { useProjectScope } from "../shared/useProjectScope";

export function ExecutionCenterPage() {
  const navigate = useNavigate();
  const realtime = useConsoleEventStream();
  const overviewQuery = useConsoleOverview({
    enablePollingFallback: realtime.status !== "open",
  });
  const healthQuery = useBackendHealth();
  const { selectedProjectId, selectedProjectName } = useProjectScope();

  const lastUpdatedText = useMemo(() => {
    if (!overviewQuery.dataUpdatedAt) return "暂未刷新";
    return formatDateTime(new Date(overviewQuery.dataUpdatedAt).toISOString());
  }, [overviewQuery.dataUpdatedAt]);

  const total = overviewQuery.data?.total_tasks ?? 0;
  const running = overviewQuery.data?.running_tasks ?? 0;
  const blocked = overviewQuery.data?.blocked_tasks ?? 0;
  const failed = overviewQuery.data?.failed_tasks ?? 0;
  const completed = overviewQuery.data?.completed_tasks ?? 0;

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
    <div className="relative min-w-0 space-y-6">
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
            <span
              className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs ${
                healthQuery.data?.status === "ok"
                  ? "border-zinc-600 text-zinc-400"
                  : "border-zinc-700 text-zinc-500"
              }`}
            >
              {healthQuery.data?.status === "ok" ? "后端在线" : "后端未知"}
            </span>
            <span
              className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs ${
                realtime.status === "open"
                  ? "border-zinc-600 text-zinc-400"
                  : "border-zinc-700 text-zinc-500"
              }`}
            >
              {realtime.status === "open" ? "实时已连接" : "实时未连接"}
            </span>
            <span className="text-zinc-600">更新 {lastUpdatedText}</span>
          </div>
        </div>
      </header>

      {/* 说明 */}
      <p className="text-sm text-zinc-500">
        查看 AI 项目主管调度后的任务队列、运行观测与仓库证据。
      </p>

      {/* 三个同级入口卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 任务队列 */}
        <ExecutionEntryCard
          title="任务队列"
          description="管理 AI 项目主管调度后的任务列表、状态与优先级"
          stats={[
            { label: "总计", value: total },
            { label: "运行中", value: running },
            { label: "阻塞", value: blocked },
          ]}
          buttonLabel="进入任务队列"
          onClick={handleNavigateToTasks}
        />

        {/* 运行观测 */}
        <ExecutionEntryCard
          title="运行观测"
          description="查看每次任务执行的运行状态、摘要与日志证据"
          stats={[
            { label: "已完成", value: completed },
            { label: "失败", value: failed },
            { label: "运行中", value: running },
          ]}
          buttonLabel="进入运行观测"
          onClick={handleNavigateToRuns}
        />

        {/* 仓库工作区 */}
        <ExecutionEntryCard
          title="仓库工作区"
          description="基于代码证据管理变更需求、文件定位与提交草案"
          stats={[
            { label: "关联项目", value: hasSpecificProject ? 1 : 0 },
            { label: "关联任务", value: total },
            { label: "已完成", value: completed },
          ]}
          buttonLabel={
            hasSpecificProject ? "进入仓库工作区" : "仓库工作区（待选择项目）"
          }
          onClick={hasSpecificProject ? handleNavigateToRepository : undefined}
          disabled={!hasSpecificProject}
          disabledReason={
            hasSpecificProject
              ? undefined
              : "仓库工作区需在项目上下文内使用，请先在上方选择具体项目"
          }
        />
      </div>
    </div>
  );
}

/* ─── Entry Card ─── */

function ExecutionEntryCard({
  title,
  description,
  stats,
  buttonLabel,
  onClick,
  disabled,
  disabledReason,
}: {
  title: string;
  description: string;
  stats: { label: string; value: number | string }[];
  buttonLabel: string;
  onClick?: () => void;
  disabled?: boolean;
  disabledReason?: string;
}) {
  return (
    <div className="flex flex-col rounded-lg border border-[#333333] bg-[#1a1a1a] p-5">
      <h3 className="text-base font-semibold text-zinc-200">{title}</h3>
      <p className="mt-1.5 text-sm text-zinc-500">{description}</p>

      {/* 数量/状态摘要 */}
      <div className="mt-4 grid grid-cols-3 gap-2">
        {stats.map((s) => (
          <div
            key={s.label}
            className="rounded border border-[#333333] px-2 py-1.5 text-center"
          >
            <div className="text-[10px] text-zinc-500">{s.label}</div>
            <div className="text-sm font-medium text-zinc-300">
              {typeof s.value === "number" ? s.value : s.value}
            </div>
          </div>
        ))}
      </div>

      {/* 跳转按钮 */}
      <div className="mt-4 pt-4 border-t border-[#333333]">
        {onClick ? (
          <button
            type="button"
            onClick={onClick}
            className="w-full rounded border border-[#444444] px-3 py-2 text-sm text-zinc-300 transition hover:border-zinc-400 hover:bg-[#222222]"
          >
            {buttonLabel}
          </button>
        ) : (
          <button
            type="button"
            disabled
            className="w-full rounded border border-[#333333] px-3 py-2 text-sm text-zinc-600 cursor-not-allowed"
          >
            {buttonLabel}
          </button>
        )}
        {disabled && disabledReason && (
          <p className="mt-1.5 text-[10px] text-zinc-700">
            {disabledReason}
          </p>
        )}
      </div>
    </div>
  );
}
