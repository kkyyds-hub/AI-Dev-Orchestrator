export function ProjectMiniStat(props: { label: string; value: string }) {
  return (
    <div className="border border-[#333333] bg-transparent/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">
        {props.label}
      </div>
      <div className="mt-2 text-sm font-medium text-zinc-100">
        {props.value}
      </div>
    </div>
  );
}
