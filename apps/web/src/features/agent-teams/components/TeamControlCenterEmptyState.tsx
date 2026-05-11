export function TeamControlCenterEmptyState() {
  return (
    <section
      id="team-control-center-surface"
      data-testid="team-control-center-surface"
      className="space-y-5"
    >
      <div className="border-b border-[#333333] pb-5">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">
          团队设置
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-50">
          团队配置与运行策略
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
          选择项目后，可以维护团队角色、协作规则、预算边界和模型档位。
        </p>
      </div>
      <div className="border-b border-dashed border-[#333333] py-8 text-center">
        <p className="text-sm font-medium text-zinc-200">请选择一个项目</p>
        <p className="mt-2 text-sm text-zinc-500">
          团队设置会随项目范围加载，用于编辑该项目的运行策略。
        </p>
      </div>
    </section>
  );
}
