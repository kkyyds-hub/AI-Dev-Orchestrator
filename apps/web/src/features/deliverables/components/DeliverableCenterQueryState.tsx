type DeliverableCenterQueryStateProps = {
  projectId: string | null;
  isLoading: boolean;
  hasData: boolean;
  errorMessage: string | null;
};

export function DeliverableCenterQueryState(props: DeliverableCenterQueryStateProps) {
  if (!props.projectId) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-800 bg-slate-950/40 px-4 py-8 text-center text-sm text-slate-400">
        先在老板首页选择一个项目，再查看该项目的交付件仓库与版本快照。
      </div>
    );
  }

  if (props.isLoading && !props.hasData) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-950/50 px-4 py-8 text-center text-sm text-slate-400">
        正在加载交付件仓库...
      </div>
    );
  }

  if (props.errorMessage) {
    return (
      <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-8 text-center text-sm text-rose-100">
        交付件仓库加载失败：{props.errorMessage}
      </div>
    );
  }

  return null;
}
