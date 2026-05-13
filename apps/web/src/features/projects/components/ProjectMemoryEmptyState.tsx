export function ProjectMemoryEmptyState() {
  return (
    <section className="space-y-3 border-b border-[#333333] pb-5">
      <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">
        项目记忆
      </p>
      <h2 className="text-2xl font-semibold text-zinc-50">记忆概览</h2>
      <div className="border-y border-dashed border-[#333333] py-5 text-sm leading-6 text-zinc-500">
        <h3 className="text-base font-semibold text-zinc-100">请选择项目</h3>
        <p className="mt-2 max-w-3xl">
          选择项目后，这里会展示记忆类型统计和最近沉淀的项目记忆。
        </p>
      </div>
    </section>
  );
}
