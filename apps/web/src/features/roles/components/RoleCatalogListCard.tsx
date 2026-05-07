type RoleCatalogListCardProps = {
  title: string;
  items: string[];
  chips?: boolean;
};

export function RoleCatalogListCard(props: RoleCatalogListCardProps) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
        {props.title}
      </div>
      {props.items.length > 0 ? (
        props.chips ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {props.items.map((item) => (
              <span
                key={item}
                className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-100"
              >
                {item}
              </span>
            ))}
          </div>
        ) : (
          <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-300">
            {props.items.map((item) => (
              <li
                key={item}
                className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2"
              >
                {item}
              </li>
            ))}
          </ul>
        )
      ) : (
        <p className="mt-3 text-sm text-slate-500">暂无配置。</p>
      )}
    </section>
  );
}
