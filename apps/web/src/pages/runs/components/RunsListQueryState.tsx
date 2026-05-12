type RunsListQueryStateProps = {
  isError: boolean;
  hasRuns: boolean;
};

export function RunsListQueryState(props: RunsListQueryStateProps) {
  if (props.isError) {
    return (
      <div className="border-l border-rose-700/70 py-2 pl-4 text-sm leading-6 text-rose-200">
        无法加载运行列表，请确认后端已启动并可访问 <code>GET /tasks/console</code>。
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
