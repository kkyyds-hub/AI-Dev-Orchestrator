import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { Breadcrumbs } from "./layout/Breadcrumbs";
import { Sidebar } from "./layout/Sidebar";
import { Topbar } from "./layout/Topbar";

const SIDEBAR_STORAGE_KEY = "app-shell-sidebar-collapsed";

export function AppShell() {
  const location = useLocation();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const isWorkbenchRoute = location.pathname === "/workbench";
  const isProjectRoute = location.pathname === "/projects" || location.pathname.startsWith("/projects/");
  const usesWideWorkspace = isWorkbenchRoute || isProjectRoute;
  const contentMaxWidthClassName = usesWideWorkspace ? "max-w-[1560px]" : "max-w-[1200px]";

  useEffect(() => {
    const savedValue = window.localStorage.getItem(SIDEBAR_STORAGE_KEY);
    if (savedValue === "true") {
      setIsSidebarCollapsed(true);
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem(SIDEBAR_STORAGE_KEY, String(isSidebarCollapsed));
  }, [isSidebarCollapsed]);

  return (
    <div
      className={`min-h-screen bg-[#212121] text-zinc-100 lg:grid lg:transition-[grid-template-columns] lg:duration-300 ${
        isSidebarCollapsed
          ? "lg:grid-cols-[88px_minmax(0,1fr)]"
          : "lg:grid-cols-[260px_minmax(0,1fr)]"
      }`}
    >
      <Sidebar isCollapsed={isSidebarCollapsed} onToggle={() => setIsSidebarCollapsed((current) => !current)} />

      <div className="flex min-h-screen min-w-0 flex-col bg-[#212121]">
        <Topbar isSidebarCollapsed={isSidebarCollapsed} onToggleSidebar={() => setIsSidebarCollapsed((current) => !current)} />

        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <div className={`mx-auto flex w-full ${contentMaxWidthClassName} min-w-0 flex-col ${isWorkbenchRoute ? "gap-7" : "gap-5"}`}>
            {isWorkbenchRoute ? null : <Breadcrumbs />}
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
