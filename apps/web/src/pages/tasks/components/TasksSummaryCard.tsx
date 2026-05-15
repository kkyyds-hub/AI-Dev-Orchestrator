type TasksSummaryCardProps = {
  label: string;
  value: string;
};

export function TasksSummaryCard(props: TasksSummaryCardProps) {
  return (
    <div className="border-l border-[#333333] px-4 py-2">
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
        {props.label}
      </div>
      <div className="mt-2 line-clamp-2 text-sm font-medium text-zinc-100">
        {props.value}
      </div>
    </div>
  );
}
