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
    <header className="border-b border-[#333333] bg-[#212121]/95 px-4 py-3 sm:px-6 lg:px-8">
      <div className={`mx-auto flex w-full ${innerMaxWidth} items-center justify-between gap-4`}>
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            onClick={props.onToggleSidebar}
            aria-label={props.isSidebarCollapsed ? "展开左侧导航" : "收起左侧导航"}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[#333333] text-zinc-400 transition hover:bg-[#2f2f2f] hover:text-zinc-100 lg:hidden"
          >
            ☰
          </button>
          {props.suppressRouteIdentity ? null : (
            <div className="min-w-0 truncate text-sm text-zinc-500">
              <span className="font-medium text-zinc-200">{routeMeta.title}</span>
              <span className="ml-3 hidden sm:inline">AI 开发编排平台 / {routeMeta.section}</span>
            </div>
          )}
        </div>

        <div className="hidden shrink-0 items-center gap-3 text-sm text-zinc-500 sm:flex">
          <span className="rounded-full border border-[#333333] px-3 py-1 text-xs text-zinc-400">
            控制台
          </span>
        </div>
      </div>
    </header>
  );
}
