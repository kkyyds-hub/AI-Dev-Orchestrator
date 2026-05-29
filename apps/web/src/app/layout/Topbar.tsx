import { useLocation } from "react-router-dom";

import { resolveRouteMeta } from "../navigation";

type TopbarProps = {
  isSidebarCollapsed: boolean;
  onToggleSidebar: () => void;
  usesWideWorkspace?: boolean;
  suppressRouteIdentity?: boolean;
};

export function Topbar(props: TopbarProps) {
  const location = useLocation();
  const routeMeta = resolveRouteMeta(location.pathname);
  const innerMaxWidth = props.usesWideWorkspace ? "max-w-[1560px]" : "max-w-[1200px]";

  return (
    <header className="border-b border-zinc-900 bg-black px-4 py-3 sm:px-6 lg:px-8 z-20">
      <div className={`mx-auto flex w-full ${innerMaxWidth} items-center justify-between gap-4`}>
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            onClick={props.onToggleSidebar}
            aria-label={props.isSidebarCollapsed ? "展开左侧导航" : "收起左侧导航"}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-zinc-850 text-zinc-400 transition hover:bg-zinc-900 hover:text-zinc-100 lg:hidden"
          >
            ☰
          </button>
          {props.suppressRouteIdentity ? null : (
            <div className="min-w-0 truncate text-xs text-zinc-400 flex items-center gap-2">
              <span className="font-bold text-zinc-200 text-sm">{routeMeta.title}</span>
              <span className="text-zinc-700">|</span>
              <span className="hidden sm:inline text-zinc-500 font-mono uppercase tracking-wider">{routeMeta.section}</span>
            </div>
          )}
        </div>

        <div className="hidden shrink-0 items-center gap-3 text-sm text-zinc-500 sm:flex">
          <span className="rounded-lg border border-zinc-850 bg-zinc-950 px-2.5 py-1 text-[11px] font-mono text-zinc-500 uppercase tracking-wider">
            CONSOLE MODE
          </span>
        </div>
      </div>
    </header>
  );
}
