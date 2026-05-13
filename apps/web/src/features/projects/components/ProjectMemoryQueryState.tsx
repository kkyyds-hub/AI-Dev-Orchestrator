export function ProjectMemoryLoadingState() {
  return (
    <div className="border-y border-[#333333] py-6 text-sm text-zinc-500">
      正在汇总项目记忆…
    </div>
  );
}

export function ProjectMemoryErrorState(props: { message: string }) {
  return (
    <div className="border-l border-rose-700/70 py-2 pl-4 text-sm leading-6 text-rose-200">
      项目记忆加载失败：{props.message}
    </div>
  );
}
