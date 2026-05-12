export function ProjectRetrospectiveLoadingState() {
  return (
    <div className="border-y border-[#333333] py-6 text-sm text-zinc-500">
      正在汇总项目复盘结论...
    </div>
  );
}

export function ProjectRetrospectiveErrorState(props: { message: string }) {
  return (
    <div className="border-l border-rose-700/70 pl-4 text-sm leading-6 text-rose-200">
      项目复盘加载失败：{props.message}
    </div>
  );
}
