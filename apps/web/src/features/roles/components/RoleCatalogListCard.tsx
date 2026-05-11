type RoleCatalogListCardProps = {
  title: string;
  items: string[];
  chips?: boolean;
};

export function RoleCatalogListCard(props: RoleCatalogListCardProps) {
  return (
    <section className="min-w-0">
      <div className="text-xs font-medium uppercase tracking-[0.16em] text-zinc-500">
        {props.title}
      </div>
      {props.items.length > 0 ? (
        props.chips ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {props.items.map((item) => (
              <span
                key={item}
                className="rounded-full border border-[#3a3a3a] px-2.5 py-1 text-xs text-zinc-300"
              >
                {item}
              </span>
            ))}
          </div>
        ) : (
          <ul className="mt-3 divide-y divide-[#333333] border-t border-[#333333] text-sm leading-6 text-zinc-300">
            {props.items.map((item) => (
              <li key={item} className="py-2">
                {item}
              </li>
            ))}
          </ul>
        )
      ) : (
        <p className="mt-3 text-sm text-zinc-600">暂无配置。</p>
      )}
    </section>
  );
}
