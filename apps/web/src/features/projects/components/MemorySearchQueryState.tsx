export function MemorySearchLoadingState() {
  return (
    <div className="border-y border-[#333333] py-6 text-sm text-zinc-500">
      正在检索项目记忆…
    </div>
  );
}

export function MemorySearchErrorState(props: { message: string }) {
  return (
    <div className="border-l border-rose-700/70 pl-4 text-sm leading-6 text-rose-200">
      项目记忆搜索失败：{props.message}
    </div>
  );
}
