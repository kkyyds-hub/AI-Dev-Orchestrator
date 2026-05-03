export function ProjectTimelineEmptyState() {
  return (
    <section className="rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30">
      <div className="text-lg font-semibold text-slate-50">项目时间线</div>
      <p className="mt-3 text-sm leading-6 text-slate-400">
        请先选择一个项目，再查看阶段推进、角色交接、审批动作和交付件版本的统一时间线。
      </p>
    </section>
  );
}
