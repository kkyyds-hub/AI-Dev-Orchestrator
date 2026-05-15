import { NavLink } from "react-router-dom";

import { PRIMARY_NAV_ITEMS } from "../navigation";

type SidebarProps = {
  isCollapsed: boolean;
  onToggle: () => void;
};

export function Sidebar(props: SidebarProps) {
  return (
    <aside
      className={`border-b border-[#333333] bg-[#181818] lg:sticky lg:top-0 lg:h-screen lg:border-b-0 lg:border-r lg:transition-[width,padding] lg:duration-300 ${
        props.isCollapsed ? "lg:w-[88px]" : "lg:w-[260px]"
      }`}
    >
      <div
        className={`flex h-full flex-col py-5 transition-[padding] duration-300 ${
          props.isCollapsed ? "px-3" : "px-4"
        }`}
      >
        <div className="relative flex items-center pb-7">
          <div
            className={`flex min-w-0 items-center gap-3 pr-10 ${
              props.isCollapsed ? "lg:justify-center" : ""
            }`}
          >
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-zinc-500/30 bg-zinc-100 text-xs font-bold text-[#171717]">
              AI
            </div>

            <div className={`${props.isCollapsed ? "hidden" : "min-w-0"}`}>
              <h1 className="truncate whitespace-nowrap text-sm font-semibold text-zinc-100">
                AI 开发编排平台
              </h1>
              <p className="mt-1 text-xs leading-5 text-zinc-500">
                全局控制台
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={props.onToggle}
            aria-label={props.isCollapsed ? "展开左侧导航" : "收起左侧导航"}
            title={props.isCollapsed ? "展开左侧导航" : "收起左侧导航"}
            className="absolute right-0 top-0 hidden h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[#333333] bg-transparent text-zinc-500 transition hover:bg-[#2f2f2f] hover:text-zinc-100 lg:flex"
          >
            <span className={`text-xs transition-transform duration-300 ${props.isCollapsed ? "rotate-180" : ""}`}>
              ←
            </span>
          </button>
        </div>

        <nav className="flex flex-1 flex-col gap-1.5">
          {!props.isCollapsed ? (
            <div className="mb-1 px-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-600">
              主要入口
            </div>
          ) : null}
          {PRIMARY_NAV_ITEMS.map((item, index) => (
            <NavLink
              key={item.to}
              to={item.to}
              title={props.isCollapsed ? item.label : undefined}
              className={({ isActive }) =>
                `group rounded-lg border transition ${
                  props.isCollapsed ? "px-2 py-2.5" : "px-3 py-3"
                } ${
                  isActive
                    ? "border-l-2 border-zinc-300 bg-white/[0.03] text-zinc-100"
                    : "border-transparent text-zinc-400 hover:bg-white/[0.03] hover:text-zinc-100"
                } ${index === 3 && !props.isCollapsed ? "mt-4" : ""}`
              }
            >
              <div
                className={`flex items-start ${
                  props.isCollapsed ? "justify-center" : "gap-3"
                }`}
              >
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-sm font-medium text-zinc-300 transition group-hover:text-zinc-100">
                  {item.shortLabel}
                </div>

                <div className={`${props.isCollapsed ? "hidden" : "min-w-0 flex-1"}`}>
                  <div className="truncate text-sm font-medium">{item.label}</div>
                  <div className="mt-1 text-xs leading-5 text-zinc-500">
                    {item.description}
                  </div>
                </div>
              </div>
            </NavLink>
          ))}
        </nav>

        <div className="mt-5 border-t border-[#333333] pt-4">
          {props.isCollapsed ? (
            <div className="flex justify-center" title="当前环境直接访问">
              <div className="h-2 w-2 rounded-full bg-zinc-400" />
            </div>
          ) : (
            <div className="flex items-center gap-3 rounded-lg px-2 py-2 text-zinc-400 transition hover:bg-white/[0.03]">
              <div className="flex h-8 w-8 items-center justify-center rounded-full border border-zinc-500/30 bg-zinc-100 text-sm font-bold text-[#171717]">U</div>
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-zinc-100">直接访问</div>
                <div className="truncate text-xs text-zinc-600">账号登录尚未开放</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
