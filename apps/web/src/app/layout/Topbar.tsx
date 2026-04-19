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
    <header className="border-b border-slate-800 bg-slate-950/75 px-4 py-5 backdrop-blur sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-start gap-3">
          <button
            type="button"
            onClick={props.onToggleSidebar}
            aria-label={props.isSidebarCollapsed ? "展开左侧导航" : "收起左侧导航"}
            className="hidden h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-slate-800 bg-slate-900/80 text-slate-300 transition hover:border-cyan-400/40 hover:bg-slate-900 hover:text-cyan-100 lg:flex"
          >
            <span className={`text-sm transition-transform duration-300 ${props.isSidebarCollapsed ? "rotate-180" : ""}`}>
              ←
            </span>
          </button>

          <div>
            <p className="text-xs font-medium uppercase tracking-[0.24em] text-cyan-300">
              {routeMeta.section}
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-50">{routeMeta.title}</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
              {routeMeta.description}
            </p>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <TopbarInfoCard label="当前视图" value={routeMeta.section} hint="按业务域组织导航入口" />
          <TopbarInfoCard label="工作区" value="Web Console" hint="统一承接工作台与项目入口" />
        </div>
      </div>
    </header>
  );
}

function TopbarInfoCard(props: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{props.label}</div>
      <div className="mt-2 text-sm font-medium text-slate-100">{props.value}</div>
      <div className="mt-1 text-xs leading-5 text-slate-400">{props.hint}</div>
    </div>
  );
}
