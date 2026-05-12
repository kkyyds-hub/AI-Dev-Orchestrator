type CostDashboardEmptyStateProps = {
  testId: string;
};

export function CostDashboardEmptyState(props: CostDashboardEmptyStateProps) {
  return (
    <section
      id={props.testId}
      data-testid={props.testId}
      className="border-b border-[#333333] pb-7"
    >
      <div className="border-b border-[#333333] pb-5">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">
          成本看板
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-50">
          用量与成本
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
          选择项目后，可以查看运行成本、令牌消耗和数据来源。
        </p>
      </div>
      <div className="mt-5 border-y border-dashed border-[#333333] py-7">
        <p className="text-sm font-medium text-zinc-200">请选择一个项目</p>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-500">
          成本看板会随项目范围更新，用于查看该项目的用量与成本明细。
        </p>
      </div>
    </section>
  );
}
