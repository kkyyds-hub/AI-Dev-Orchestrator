import { RunsSummaryCard } from "./RunsSummaryCard";

type RunsPageHeaderProps = {
  latestRunCount: number;
  runId: string | undefined;
  realtimeStatus: string;
  isRefreshing: boolean;
  onRefresh: () => void;
};

function formatRealtimeStatus(status: string): string {
  const labels: Record<string, string> = {
    open: "已连接",
    connecting: "连接中",
    reconnecting: "正在重连",
    unsupported: "不支持实时连接",
  };
  return labels[status] ?? "未知状态";
}

export function RunsPageHeader(props: RunsPageHeaderProps) {
  return (
    <header className="border-b border-[#333333] pb-6" data-testid="runs-page-header">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-600">
            Workflow Runs
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-zinc-100">
            工作流运行
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-500">
            按最近执行顺序查看运行记录、任务上下文和日志详情；选择左侧记录后，右侧展示任务动作、运行历史和项目上下文。
          </p>
        </div>

        <div className="flex flex-col gap-3 lg:items-end">
          <button
            type="button"
            onClick={props.onRefresh}
            disabled={props.isRefreshing}
            className="rounded-md border border-zinc-200 bg-transparent px-3.5 py-2 text-sm font-medium text-zinc-100 transition hover:bg-[#2f2f2f] disabled:cursor-not-allowed disabled:border-[#333333] disabled:text-zinc-600"
          >
            {props.isRefreshing ? "刷新中..." : "刷新运行数据"}
          </button>
          <dl className="grid min-w-full gap-x-5 gap-y-2 text-sm sm:grid-cols-3 lg:min-w-[520px]">
            <RunsSummaryCard label="可见运行" value={String(props.latestRunCount)} />
            <RunsSummaryCard label="当前运行" value={props.runId ?? "未选择"} />
            <RunsSummaryCard label="连接状态" value={formatRealtimeStatus(props.realtimeStatus)} />
          </dl>
        </div>
      </div>
    </header>
  );
}
