import { useLocation } from "react-router-dom";

import { resolveRouteMeta } from "../navigation";

export function Topbar() {
  const location = useLocation();
  const routeMeta = resolveRouteMeta(location.pathname);

  return (
    <header className="border-b border-slate-800 bg-slate-950/70 px-4 py-5 backdrop-blur sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.24em] text-cyan-300">
            {routeMeta.section}
          </p>
          <h2 className="mt-2 text-2xl font-semibold text-slate-50">{routeMeta.title}</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">{routeMeta.description}</p>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-3 text-xs leading-6 text-slate-400">
          当前为最小可落地多页面骨架：正式路由先行，现有业务组件尽量原位复用。
        </div>
      </div>
    </header>
  );
}
