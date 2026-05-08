import { useLocation } from "react-router-dom";

import { resolveRouteMeta } from "../navigation";

export function Breadcrumbs() {
  const location = useLocation();
  const routeMeta = resolveRouteMeta(location.pathname);

  return (
    <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-2 text-xs text-zinc-500">
      <span className="rounded-full border border-[#333333] bg-[#212121] px-3 py-1">
        AI Dev Orchestrator
      </span>

      {routeMeta.breadcrumbs.map((crumb) => (
        <span key={crumb} className="flex items-center gap-2">
          <span>/</span>
          <span className="rounded-full border border-[#333333] bg-[#212121] px-3 py-1 text-zinc-300">
            {crumb}
          </span>
        </span>
      ))}
    </nav>
  );
}
