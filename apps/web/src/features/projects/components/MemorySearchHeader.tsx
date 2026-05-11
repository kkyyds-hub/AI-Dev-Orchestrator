export function MemorySearchHeader() {
  return (
    <header className="space-y-2 rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
      <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">
        ????
      </p>
      <h2 className="text-3xl font-semibold tracking-tight text-slate-50">
        可检索经验搜索
      </h2>
      <p className="max-w-3xl text-sm leading-6 text-slate-300">
        面向当前项目执行最小关键词检索，避免引入更重的长期记忆或复杂向量检索体系。
      </p>
    </header>
  );
}
