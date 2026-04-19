type PlaceholderPageProps = {
  title: string;
  description: string;
  nextStep: string;
};

export function PlaceholderPage(props: PlaceholderPageProps) {
  return (
    <section className="rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/40">
      <div className="max-w-3xl">
        <div className="inline-flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-500/10 px-3 py-1 text-xs font-medium text-cyan-100">
          <span className="h-2 w-2 rounded-full bg-cyan-300" />
          即将开放
        </div>

        <h3 className="mt-4 text-2xl font-semibold text-slate-50">{props.title}</h3>
        <p className="mt-3 text-sm leading-7 text-slate-300">{props.description}</p>

        <div className="mt-5 rounded-2xl border border-slate-800 bg-slate-900/70 p-5 text-sm leading-7 text-slate-300">
          <div className="text-xs uppercase tracking-[0.22em] text-slate-500">后续规划</div>
          <p className="mt-2">{props.nextStep}</p>
        </div>
      </div>
    </section>
  );
}
