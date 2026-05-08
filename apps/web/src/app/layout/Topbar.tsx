import { useLocation } from "react-router-dom";

import { resolveRouteMeta } from "../navigation";

type TopbarProps = {
  isSidebarCollapsed: boolean;
  onToggleSidebar: () => void;
};

export function Topbar(props: TopbarProps) {
  const location = useLocation();
  const routeMeta = resolveRouteMeta(location.pathname);

  return (
    <header className="h-auto border-b border-[#333333] bg-[#212121] px-4 py-4 sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-3 lg:min-h-16 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            onClick={props.onToggleSidebar}
            aria-label={props.isSidebarCollapsed ? "展开左侧导航" : "收起左侧导航"}
            className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[#333333] bg-transparent text-zinc-500 transition hover:bg-[#2f2f2f] hover:text-zinc-100 lg:flex"
          >
            <span className={`text-xs transition-transform duration-300 ${props.isSidebarCollapsed ? "rotate-180" : ""}`}>
              ←
            </span>
          </button>

          <div className="min-w-0">
            <div className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-1">
              <h2 className="truncate text-lg font-semibold text-zinc-100">{routeMeta.title}</h2>
              <span className="text-sm text-zinc-500">AI Dev Orchestrator / {routeMeta.section}</span>
            </div>
            <p className="mt-1 max-w-3xl truncate text-sm text-zinc-500">
              {routeMeta.description}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-4 text-sm text-zinc-500">
          <span className="transition hover:text-zinc-200">{routeMeta.section}（当前视图）</span>
          <span className="transition hover:text-zinc-200">Web Console</span>
        </div>
      </div>
    </header>
  );
}
