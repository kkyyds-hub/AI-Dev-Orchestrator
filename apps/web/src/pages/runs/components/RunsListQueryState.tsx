type RunsListQueryStateProps = {
  isError: boolean;
  hasRuns: boolean;
};

export function RunsListQueryState(props: RunsListQueryStateProps) {
  if (props.isError) {
    return (
      <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
        无法加载运行列表，请确认后端已启动并可访问 <code>GET /tasks/console</code>。
      </div>
    );
  }

  if (!props.hasRuns) {
    return (
      <div className="rounded-xl border border-dashed border-slate-800 bg-slate-950/40 p-4 text-sm text-slate-400">
        当前还没有可展示的最新运行记录。
      </div>
    );
  }

  return null;
}
