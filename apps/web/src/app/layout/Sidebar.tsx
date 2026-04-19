import { NavLink } from "react-router-dom";

import { PRIMARY_NAV_ITEMS } from "../navigation";

type SidebarProps = {
  isCollapsed: boolean;
  onToggle: () => void;
};

export function Sidebar(props: SidebarProps) {
  return (
    <aside
      className={`border-b border-slate-800 bg-slate-950/92 lg:sticky lg:top-0 lg:h-screen lg:border-b-0 lg:border-r lg:transition-[width,padding] lg:duration-300 ${
        props.isCollapsed ? "lg:w-[88px]" : "lg:w-[264px]"
      }`}
    >
      <div
        className={`flex h-full flex-col py-5 transition-[padding] duration-300 ${
          props.isCollapsed ? "px-3" : "px-4 sm:px-6 lg:px-4"
        }`}
      >
        <div className="flex items-start justify-between gap-3 border-b border-slate-800 pb-5">
          <div
            className={`flex min-w-0 items-start gap-3 ${
              props.isCollapsed ? "lg:justify-center" : ""
            }`}
          >
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-cyan-400/30 bg-cyan-500/10 text-sm font-semibold text-cyan-100 shadow-lg shadow-cyan-950/20">
              AI
            </div>

            <div className={`${props.isCollapsed ? "hidden" : "min-w-0"}`}>
              <div className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-300">
                Workspace
              </div>
              <h1 className="mt-2 truncate text-lg font-semibold text-slate-50">
                AI Dev Orchestrator
              </h1>
              <p className="mt-1 text-sm leading-6 text-slate-400">
                面向智能研发协同的统一工作台。
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={props.onToggle}
            aria-label={props.isCollapsed ? "展开左侧导航" : "收起左侧导航"}
            title={props.isCollapsed ? "展开左侧导航" : "收起左侧导航"}
            className="hidden h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-slate-800 bg-slate-900/80 text-slate-300 transition hover:border-cyan-400/40 hover:bg-slate-900 hover:text-cyan-100 lg:flex"
          >
            <span className={`text-sm transition-transform duration-300 ${props.isCollapsed ? "rotate-180" : ""}`}>
              ←
            </span>
          </button>
        </div>

        <nav className="mt-5 flex flex-1 flex-col gap-2">
          {PRIMARY_NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              title={props.isCollapsed ? item.label : undefined}
              className={({ isActive }) =>
                `group rounded-2xl border transition ${
                  props.isCollapsed ? "px-2 py-2.5" : "px-3 py-3"
                } ${
                  isActive
                    ? "border-cyan-400/40 bg-cyan-500/10 text-cyan-100"
                    : "border-slate-800 bg-slate-950/60 text-slate-300 hover:border-slate-700 hover:bg-slate-900/80"
                }`
              }
            >
              <div
                className={`flex items-center ${
                  props.isCollapsed ? "justify-center" : "gap-3"
                }`}
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-slate-800 bg-slate-900/80 text-sm font-medium text-slate-200 transition group-hover:border-cyan-400/30 group-hover:text-cyan-100">
                  {item.shortLabel}
                </div>

                <div className={`${props.isCollapsed ? "hidden" : "min-w-0 flex-1"}`}>
                  <div className="truncate text-sm font-medium">{item.label}</div>
                  <div className="mt-1 text-xs leading-5 text-slate-400">
                    {item.description}
                  </div>
                </div>
              </div>
            </NavLink>
          ))}
        </nav>

        <div
          className={`mt-5 rounded-2xl border border-slate-800 bg-slate-900/70 transition-all duration-300 ${
            props.isCollapsed ? "px-2 py-3" : "p-4"
          }`}
        >
          {props.isCollapsed ? (
            <div className="flex justify-center" title="统一导航已启用">
              <div className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-[0_0_20px_rgba(74,222,128,0.35)]" />
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <div className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-[0_0_20px_rgba(74,222,128,0.35)]" />
                <div className="text-xs font-medium uppercase tracking-[0.22em] text-slate-500">
                  Navigation
                </div>
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-300">
                当前导航按业务域组织，可在工作台、项目、审批与治理之间快速切换。
              </p>
            </>
          )}
        </div>
      </div>
    </aside>
  );
}
