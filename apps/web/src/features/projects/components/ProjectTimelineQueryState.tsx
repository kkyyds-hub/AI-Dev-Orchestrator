export function ProjectTimelineLoadingState() {
  return (
    <div className="border border-dashed border-[#3a3a3a] px-4 py-8 text-center text-sm text-slate-400">
      Loading project events...
    </div>
  );
}

export function ProjectTimelineErrorState(props: { message: string }) {
  return (
    <div className="border-l-2 border-l-rose-400 py-4 pl-4 text-sm text-rose-100">
      Failed to load project events: {props.message}
    </div>
  );
}
