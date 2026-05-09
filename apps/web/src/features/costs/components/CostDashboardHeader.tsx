type CostDashboardHeaderProps = {
  projectId: string;
  projectName: string | null;
  isRefreshing: boolean;
  onRefresh: () => void;
};

export function CostDashboardHeader(props: CostDashboardHeaderProps) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800/80 pb-4">
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">
          Usage & Cost Analytics
        </p>
        <h2 className="mt-1 text-xl font-semibold text-slate-50">用量与成本分析</h2>
        <p className="mt-1 truncate text-sm text-slate-400">
          当前项目：{props.projectName ?? props.projectId}
        </p>
      </div>
      <button
        type="button"
        onClick={props.onRefresh}
        disabled={props.isRefreshing}
        className="inline-flex items-center rounded-lg border border-slate-700 bg-slate-900/40 px-3 py-2 text-sm font-medium text-slate-200 transition hover:border-slate-600 hover:bg-slate-800/70 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {props.isRefreshing ? "刷新中..." : "刷新数据"}
      </button>
    </header>
  );
}
