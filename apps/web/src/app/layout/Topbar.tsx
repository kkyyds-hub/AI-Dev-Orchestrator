import { useLocation } from "react-router-dom";

import { resolveRouteMeta } from "../navigation";

type TopbarProps = {
  isSidebarCollapsed: boolean;
  onToggleSidebar: () => void;
};

export function Topbar(props: TopbarProps) {
  const location = useLocation();
  const routeMeta = resolveRouteMeta(location.pathname);
  const isWorkbenchRoute = location.pathname === "/workbench";

  return (
    <header className="border-b border-[#333333] bg-[#212121] px-4 py-3 sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-[1200px] items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            onClick={props.onToggleSidebar}
            aria-label={props.isSidebarCollapsed ? "展开左侧导航" : "收起左侧导航"}
            className="hidden h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[#333333] bg-transparent text-zinc-500 transition hover:bg-[#2f2f2f] hover:text-zinc-100 lg:flex"
          >
            <span className={`text-xs transition-transform duration-300 ${props.isSidebarCollapsed ? "rotate-180" : ""}`}>
              ←
            </span>
          </button>

          <div className="min-w-0 truncate text-sm text-zinc-500">
            {isWorkbenchRoute ? (
              <>
                <span className="font-medium text-zinc-200">控制台工作台</span>
                <span className="ml-3">AI Dev Orchestrator / 工作台</span>
              </>
            ) : (
              <>
                <span className="font-medium text-zinc-200">{routeMeta.title}</span>
                <span className="ml-3">AI Dev Orchestrator / {routeMeta.section}</span>
              </>
            )}
          </div>
        </div>

        <div className="hidden shrink-0 items-center gap-4 text-sm text-zinc-500 sm:flex">
          <span className="transition hover:text-zinc-200">Web Console</span>
        </div>
      </div>
    </header>
  );
}
