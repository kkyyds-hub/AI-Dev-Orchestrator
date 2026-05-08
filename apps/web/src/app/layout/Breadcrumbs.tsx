import { useLocation } from "react-router-dom";

import { resolveRouteMeta } from "../navigation";

export function Breadcrumbs() {
  const location = useLocation();
  const routeMeta = resolveRouteMeta(location.pathname);

  return (
    <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-2 text-xs text-zinc-500">
      <span className="text-zinc-600">
        AI Dev Orchestrator
      </span>

      {routeMeta.breadcrumbs.map((crumb) => (
        <span key={crumb} className="flex items-center gap-2">
          <span className="text-zinc-700">/</span>
          <span className="text-zinc-300">
            {crumb}
          </span>
        </span>
      ))}
    </nav>
  );
}
