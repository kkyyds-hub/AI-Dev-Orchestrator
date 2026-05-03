export function AgentThreadControlEmptyState() {
  return (
    <section
      id="agent-thread-control-surface"
      data-testid="agent-thread-control-surface"
      className="space-y-4 rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30"
    >
      <h2 className="text-2xl font-semibold text-slate-50">Day12 Agent Thread 控制面</h2>
      <p className="text-sm text-slate-400">
        先选择一个项目，再查看 Day12 会话列表、消息时间线和老板介入面板；这些区块会消费 Day11 agent-thread 契约。
      </p>
    </section>
  );
}
