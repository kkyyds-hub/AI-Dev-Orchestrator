type CostDashboardEmptyStateProps = {
  testId: string;
};

export function CostDashboardEmptyState(props: CostDashboardEmptyStateProps) {
  return (
    <section
      id={props.testId}
      data-testid={props.testId}
      className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 shadow-xl shadow-slate-950/30"
    >
      <div className="border-b border-slate-800 pb-5">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-slate-500">
          成本看板
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-50">
          用量与成本
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
          选择项目后，可以查看运行成本、令牌消耗和数据来源。
        </p>
      </div>
      <div className="mt-5 rounded-xl border border-dashed border-slate-800 bg-slate-900/30 px-5 py-8 text-center">
        <p className="text-sm font-medium text-slate-200">请选择一个项目</p>
        <p className="mt-2 text-sm text-slate-500">
          成本看板会随项目范围更新，用于查看该项目的用量与成本明细。
        </p>
      </div>
    </section>
  );
}
