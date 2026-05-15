type DeliverableVersionMiniInfoProps = {
  label: string;
  value: string;
};

export function DeliverableVersionMiniInfo(
  props: DeliverableVersionMiniInfoProps,
) {
  return (
    <div className="border-l border-[#333333] px-4 py-2">
      <div className="text-xs uppercase tracking-[0.18em] text-zinc-500">
        {props.label}
      </div>
      <div className="mt-2 text-sm font-medium text-zinc-100">
        {props.value}
      </div>
    </div>
  );
}
