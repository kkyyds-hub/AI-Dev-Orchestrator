type PlaceholderPageProps = {
  title: string;
  description: string;
  nextStep: string;
};

export function PlaceholderPage(props: PlaceholderPageProps) {
  return (
    <section className="rounded-2xl border border-[#333333] bg-[#242424] p-6 shadow-sm shadow-black/20">
      <div className="max-w-3xl">
        <div className="inline-flex items-center gap-2 rounded-full border border-[#333333] px-3 py-1 text-xs font-medium text-zinc-300">
          <span className="h-2 w-2 rounded-full bg-zinc-400" />
          即将开放
        </div>

        <h3 className="mt-4 text-2xl font-semibold text-zinc-100">{props.title}</h3>
        <p className="mt-3 text-sm leading-7 text-zinc-400">{props.description}</p>

        <div className="mt-5 rounded-xl border border-[#333333] bg-[#1f1f1f] p-5 text-sm leading-7 text-zinc-400">
          <div className="text-xs uppercase tracking-[0.22em] text-zinc-600">后续规划</div>
          <p className="mt-2">{props.nextStep}</p>
        </div>
      </div>
    </section>
  );
}
