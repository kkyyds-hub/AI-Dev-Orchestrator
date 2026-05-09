export function TeamControlCenterEmptyState() {
  return (
    <section
      id="team-control-center-surface"
      data-testid="team-control-center-surface"
      className="border-b border-[#333333] pb-6"
    >
      <h2 className="text-lg font-semibold text-slate-50">团队设置</h2>
      <p className="mt-2 text-sm text-slate-400">
        先选择项目，再编辑团队组装、团队策略和预算策略。
      </p>
    </section>
  );
}
