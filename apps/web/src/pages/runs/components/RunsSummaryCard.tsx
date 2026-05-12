type RunsSummaryCardProps = {
  label: string;
  value: string;
};

export function RunsSummaryCard(props: RunsSummaryCardProps) {
  return (
    <div className="min-w-0 border-l border-[#333333] pl-3">
      <dt className="text-xs uppercase tracking-[0.18em] text-zinc-600">
        {props.label}
      </dt>
      <dd className="mt-1 break-all text-sm font-medium text-zinc-100">
        {props.value}
      </dd>
    </div>
  );
}
