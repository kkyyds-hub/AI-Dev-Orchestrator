import { NavLink } from "react-router-dom";

import { PRIMARY_NAV_ITEMS } from "../navigation";

type SidebarProps = {
  isCollapsed: boolean;
  onToggle: () => void;
};

export function Sidebar(props: SidebarProps) {
  return (
    <aside
      className={`border-b border-zinc-900 bg-black lg:sticky lg:top-0 lg:h-screen lg:border-b-0 lg:border-r lg:transition-[width,padding] lg:duration-300 ${
        props.isCollapsed ? "lg:w-[80px]" : "lg:w-[260px]"
      } z-30`}
    >
      <div
        className={`flex h-full flex-col py-5 transition-[padding] duration-300 ${
          props.isCollapsed ? "px-2" : "px-4"
        }`}
      >
        {/* LOGO Header */}
        <div className="relative flex items-center pb-6 border-b border-zinc-900">
          <div
            className={`flex min-w-0 items-center gap-2.5 ${
              props.isCollapsed ? "lg:justify-center w-full" : ""
            }`}
          >
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-900 text-xs font-bold text-zinc-100 shadow-sm">
              AI
            </div>

            <div className={`${props.isCollapsed ? "hidden" : "min-w-0"}`}>
              <h1 className="truncate whitespace-nowrap text-xs font-bold text-zinc-200 tracking-tight">
                AI 开发编排平台
              </h1>
              <p className="text-[10px] leading-4 text-zinc-500 font-mono tracking-wider">
                ORCHESTRATOR
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={props.onToggle}
            aria-label={props.isCollapsed ? "展开左侧导航" : "收起左侧导航"}
            title={props.isCollapsed ? "展开左侧导航" : "收起左侧导航"}
            className="absolute right-0 top-0.5 hidden h-6 w-6 shrink-0 items-center justify-center rounded-md border border-zinc-850 bg-black text-zinc-500 transition hover:bg-zinc-900 hover:text-zinc-200 lg:flex cursor-pointer"
          >
            <span className={`text-[10px] font-bold transition-transform duration-300 ${props.isCollapsed ? "rotate-180" : ""}`}>
              ←
            </span>
          </button>
        </div>

        {/* Navigation list */}
        <nav className="flex flex-1 flex-col gap-1 mt-6">
          {!props.isCollapsed ? (
            <div className="mb-2 px-3 text-[10px] font-bold uppercase tracking-wider text-zinc-600">
              主要导航入口
            </div>
          ) : null}
          {PRIMARY_NAV_ITEMS.map((item, index) => (
            <NavLink
              key={item.to}
              to={item.to}
              title={props.isCollapsed ? item.label : undefined}
              className={({ isActive }) =>
                `group rounded-lg border transition-all duration-200 ${
                  props.isCollapsed ? "px-1.5 py-2" : "px-3 py-2.5"
                } ${
                  isActive
                    ? "border-zinc-800 bg-zinc-900 text-white font-semibold"
                    : "border-transparent text-zinc-500 hover:bg-zinc-950 hover:text-zinc-300"
                } ${index === 3 && !props.isCollapsed ? "mt-3" : ""}`
              }
            >
              <div
                className={`flex items-center ${
                  props.isCollapsed ? "justify-center" : "gap-3"
                }`}
              >
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-xs font-semibold text-zinc-400 transition group-hover:text-white">
                  {item.shortLabel}
                </div>

                <div className={`${props.isCollapsed ? "hidden" : "min-w-0 flex-1"}`}>
                  <div className="truncate text-xs font-semibold">{item.label}</div>
                  <div className="text-[10px] leading-3 text-zinc-500 mt-0.5 font-medium truncate">
                    {item.description}
                  </div>
                </div>
              </div>
            </NavLink>
          ))}
        </nav>

        {/* Bottom environment and profile */}
        <div className="mt-5 border-t border-zinc-900 pt-4">
          {props.isCollapsed ? (
            <div className="flex justify-center" title="当前环境直接访问">
              <div className="h-1.5 w-1.5 rounded-full bg-zinc-600" />
            </div>
          ) : (
            <div className="flex items-center gap-3 rounded-lg px-2 py-1.5 text-zinc-500 hover:bg-zinc-950 transition">
              <div className="flex h-7 w-7 items-center justify-center rounded-full border border-zinc-800 bg-zinc-900 text-xs font-bold text-zinc-300">U</div>
              <div className="min-w-0">
                <div className="truncate text-xs font-bold text-zinc-300">直接访问</div>
                <div className="truncate text-[10px] text-zinc-600">测试权限已开通</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
