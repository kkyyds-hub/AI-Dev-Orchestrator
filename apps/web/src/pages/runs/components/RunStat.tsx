type RunStatProps = {
  label: string;
  value: string;
};

export function RunStat(props: RunStatProps) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] uppercase tracking-[0.16em] text-zinc-600">
        {props.label}
      </div>
      <div className="mt-1 truncate text-sm text-zinc-200">{props.value}</div>
    </div>
  );
}
