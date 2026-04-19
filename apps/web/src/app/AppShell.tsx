import { Outlet } from "react-router-dom";

import { Breadcrumbs } from "./layout/Breadcrumbs";
import { Sidebar } from "./layout/Sidebar";
import { Topbar } from "./layout/Topbar";

export function AppShell() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 lg:grid lg:grid-cols-[260px_minmax(0,1fr)]">
      <Sidebar />

      <div className="flex min-h-screen min-w-0 flex-col">
        <Topbar />

        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto flex w-full max-w-7xl min-w-0 flex-col gap-5">
            <Breadcrumbs />
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
