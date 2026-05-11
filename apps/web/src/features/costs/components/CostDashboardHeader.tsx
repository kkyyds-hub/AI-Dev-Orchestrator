type CostDashboardHeaderProps = {
  projectId: string;
  projectName: string | null;
  isRefreshing: boolean;
  onRefresh: () => void;
};

export function CostDashboardHeader(props: CostDashboardHeaderProps) {
  return (
    <header className="flex flex-col gap-4 border-b border-slate-800 pb-5 lg:flex-row lg:items-end lg:justify-between">
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-slate-500">
          成本看板
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-50">
          用量与成本
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
          汇总当前项目的运行成本、令牌消耗和数据来源，便于判断预算使用情况。
        </p>
        <p className="mt-1 truncate text-xs text-slate-500">
          当前项目：{props.projectName ?? props.projectId}
        </p>
      </div>
      <button
        type="button"
        onClick={props.onRefresh}
        disabled={props.isRefreshing}
        className="inline-flex w-fit items-center rounded-lg border border-slate-700 bg-slate-900/70 px-4 py-2 text-sm font-medium text-slate-100 transition hover:border-slate-600 hover:bg-slate-800/80 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {props.isRefreshing ? "刷新中..." : "刷新数据"}
      </button>
    </header>
  );
}
