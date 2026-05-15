type RunsListQueryStateProps = {
  isError: boolean;
  hasRuns: boolean;
};

export function RunsListQueryState(props: RunsListQueryStateProps) {
  if (props.isError) {
    return (
      <div className="border-l border-rose-500/50 px-4 py-3 text-sm leading-6 text-rose-100">
        运行列表加载失败，请刷新页面或检查服务状态。
      </div>
    );
  }

  if (!props.hasRuns) {
    return (
      <div className="border-y border-dashed border-[#333333] py-8 text-center text-sm text-zinc-500">
        当前还没有可展示的最新运行记录。
      </div>
    );
  }

  return null;
}
