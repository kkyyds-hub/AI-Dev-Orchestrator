import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";

import { Breadcrumbs } from "./layout/Breadcrumbs";
import { Sidebar } from "./layout/Sidebar";
import { Topbar } from "./layout/Topbar";

const SIDEBAR_STORAGE_KEY = "app-shell-sidebar-collapsed";

export function AppShell() {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

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
      className={`min-h-screen bg-slate-950 text-slate-100 lg:grid lg:transition-[grid-template-columns] lg:duration-300 ${
        isSidebarCollapsed
          ? "lg:grid-cols-[88px_minmax(0,1fr)]"
          : "lg:grid-cols-[264px_minmax(0,1fr)]"
      }`}
    >
      <Sidebar
        isCollapsed={isSidebarCollapsed}
        onToggle={() => setIsSidebarCollapsed((current) => !current)}
      />

      <div className="flex min-h-screen min-w-0 flex-col">
        <Topbar
          isSidebarCollapsed={isSidebarCollapsed}
          onToggleSidebar={() => setIsSidebarCollapsed((current) => !current)}
        />

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
