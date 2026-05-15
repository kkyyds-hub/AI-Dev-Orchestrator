type DeliverableCenterQueryStateProps = {
  projectId: string | null;
  isLoading: boolean;
  hasData: boolean;
  errorMessage: string | null;
};

export function DeliverableCenterQueryState(props: DeliverableCenterQueryStateProps) {
  if (!props.projectId) {
    return (
      <div className="border border-dashed border-[#3a3a3a] px-4 py-8 text-sm leading-6 text-zinc-400">
        请先选择项目，再查看该项目的交付件与版本快照。
      </div>
    );
  }

  if (props.isLoading && !props.hasData) {
    return (
      <div className="border border-dashed border-[#3a3a3a] px-4 py-8 text-sm leading-6 text-zinc-400">
        正在加载交付件与版本快照...
      </div>
    );
  }

  if (props.errorMessage) {
    return (
      <div className="border-l border-rose-500/50 px-4 py-3 text-sm leading-6 text-rose-100">
        交付物中心加载失败：{props.errorMessage}
      </div>
    );
  }

  return null;
}
