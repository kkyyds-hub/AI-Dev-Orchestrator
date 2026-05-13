export function MemorySearchLoadingState() {
  return (
    <div className="py-6 text-sm text-zinc-500">
      正在检索项目记忆…
    </div>
  );
}

export function MemorySearchErrorState(props: { message: string }) {
  return (
    <div className="border-l border-rose-700/70 py-2 pl-4 text-sm leading-6 text-rose-200">
      检索失败：{props.message}
    </div>
  );
}
