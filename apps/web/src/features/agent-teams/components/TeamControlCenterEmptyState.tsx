export function TeamControlCenterEmptyState() {
  return (
    <section
      id="team-control-center-surface"
      data-testid="team-control-center-surface"
      className="rounded-[28px] border border-slate-800 bg-slate-950/70 p-6"
    >
      <h2 className="text-2xl font-semibold text-slate-50">团队控制中心</h2>
      <p className="mt-2 text-sm text-slate-400">
        先选择项目，再编辑团队组装、团队策略和预算策略。
      </p>
    </section>
  );
}
