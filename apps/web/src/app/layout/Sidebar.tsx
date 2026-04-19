import { NavLink } from "react-router-dom";

import { PRIMARY_NAV_ITEMS } from "../navigation";

export function Sidebar() {
  return (
    <aside className="border-b border-slate-800 bg-slate-950/90 lg:sticky lg:top-0 lg:h-screen lg:border-b-0 lg:border-r">
      <div className="flex h-full flex-col px-4 py-5 sm:px-6">
        <div className="border-b border-slate-800 pb-5">
          <div className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-300">
            App Shell
          </div>
          <h1 className="mt-3 text-xl font-semibold text-slate-50">AI Dev Orchestrator</h1>
          <p className="mt-2 text-sm leading-6 text-slate-400">
            本轮先把单页控制台推进到可扩展多页面骨架，不做大拆业务。
          </p>
        </div>

        <nav className="mt-5 flex flex-1 flex-col gap-2">
          {PRIMARY_NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `rounded-2xl border px-4 py-3 transition ${
                  isActive
                    ? "border-cyan-400/40 bg-cyan-500/10 text-cyan-100"
                    : "border-slate-800 bg-slate-950/60 text-slate-300 hover:border-slate-700 hover:bg-slate-900/80"
                }`
              }
            >
              <div className="text-sm font-medium">{item.label}</div>
              <div className="mt-1 text-xs leading-5 text-slate-400">{item.description}</div>
            </NavLink>
          ))}
        </nav>

        <div className="mt-5 rounded-2xl border border-slate-800 bg-slate-900/70 p-4 text-xs leading-6 text-slate-400">
          Step 1：先立正式路由、左侧导航与页面壳层；任务域、运行域和项目子路由放到下一步渐进提升。
        </div>
      </div>
    </aside>
  );
}
