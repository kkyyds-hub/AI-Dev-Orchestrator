type CostDashboardHeaderProps = {
  projectId: string;
  projectName: string | null;
  onRefresh: () => void;
};

export function CostDashboardHeader(props: CostDashboardHeaderProps) {
  return (
    <header className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-cyan-300">
            Day14 缓存与成本看板
          </p>
          <h2 className="mt-2 text-2xl font-semibold text-slate-50">
            成本聚合与兜底观测面
          </h2>
          <p className="mt-2 text-sm text-slate-300">
            当前项目：{props.projectName ?? props.projectId}
          </p>
        </div>
        <button
          type="button"
          onClick={props.onRefresh}
          className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-3 py-2 text-sm text-cyan-100 transition hover:bg-cyan-500/20"
        >
          刷新聚合
        </button>
      </div>
    </header>
  );
}
