type DeliverableVersionQueryStateProps = {
  isLoading: boolean;
  errorMessage: string | null;
  hasVersions: boolean;
};

export function DeliverableVersionQueryState(
  props: DeliverableVersionQueryStateProps,
) {
  if (props.isLoading) {
    return (
      <p className="text-sm leading-6 text-zinc-400">
        正在加载交付件版本快照…
      </p>
    );
  }

  if (props.errorMessage) {
    return (
      <p className="text-sm leading-6 text-rose-200">
        交付件详情加载失败：{props.errorMessage}
      </p>
    );
  }

  if (!props.hasVersions) {
    return (
      <p className="text-sm leading-6 text-zinc-400">
        当前交付件尚未产生可展示的版本快照。
      </p>
    );
  }

  return null;
}
