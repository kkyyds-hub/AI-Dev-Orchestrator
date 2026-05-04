type CostDashboardEmptyStateProps = {
  testId: string;
};

export function CostDashboardEmptyState(props: CostDashboardEmptyStateProps) {
  return (
    <section
      id={props.testId}
      data-testid={props.testId}
      className="space-y-4 rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30"
    >
      <h2 className="text-2xl font-semibold text-slate-50">Day14 成本看板</h2>
      <p className="text-sm text-slate-400">
        请先选择项目，再查看缓存 / 成本聚合与兜底（fallback）路径。
      </p>
    </section>
  );
}
