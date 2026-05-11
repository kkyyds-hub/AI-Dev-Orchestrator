type CostDashboardEmptyStateProps = {
  testId: string;
};

export function CostDashboardEmptyState(props: CostDashboardEmptyStateProps) {
  return (
    <section id={props.testId} data-testid={props.testId} className="space-y-3 border-b border-slate-800/80 pb-4">
      <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">
        成本分析
      </p>
      <h2 className="text-xl font-semibold text-slate-50">用量与成本</h2>
      <p className="text-sm text-slate-400">请先选择项目，再查看用量、数据来源和估算说明。</p>
    </section>
  );
}
