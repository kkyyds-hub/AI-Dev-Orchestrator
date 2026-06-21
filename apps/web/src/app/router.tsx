import { Navigate, createBrowserRouter } from "react-router-dom";

import { AppShell } from "./AppShell";
import { SanshengLiubuUiLabPage } from "../features/ui-selection-lab/SanshengLiubuUiLabPage";
import { WorkbenchPage } from "../pages/workbench/WorkbenchPage";

export const router = createBrowserRouter([
  {
    path: "/__lab/sansheng-liubu-ui",
    element: <SanshengLiubuUiLabPage />,
  },
  {
    path: "/",
    element: <AppShell />,
    children: [
      {
        index: true,
        element: <Navigate to="/workbench" replace />,
      },
      {
        path: "workbench",
        element: <WorkbenchPage />,
      },
      {
        path: "projects",
        element: <WorkbenchPage initialMainPage="projects" />,
      },
      {
        path: "projects/:projectId",
        element: <WorkbenchPage initialMainPage="projects" />,
      },
      {
        path: "projects/:projectId/repository",
        element: <WorkbenchPage initialMainPage="repository" />,
      },
      {
        path: "projects/:projectId/timeline",
        element: <WorkbenchPage initialMainPage="projects" />,
      },
      {
        path: "projects/:projectId/collaboration",
        element: <WorkbenchPage initialMainPage="governance" />,
      },
      {
        path: "projects/:projectId/governance",
        element: <WorkbenchPage initialMainPage="governance" />,
      },
      {
        path: "projects/:projectId/deliverables",
        element: <WorkbenchPage initialMainPage="deliverables" />,
      },
      {
        path: "projects/:projectId/approvals",
        element: <WorkbenchPage initialMainPage="deliverables" />,
      },
      {
        path: "tasks",
        element: <WorkbenchPage initialMainPage="execution" />,
      },
      {
        path: "tasks/:taskId",
        element: <WorkbenchPage initialMainPage="execution" />,
      },
      {
        path: "runs",
        element: <WorkbenchPage initialMainPage="execution" />,
      },
      {
        path: "runs/:runId",
        element: <WorkbenchPage initialMainPage="execution" />,
      },
      {
        path: "execution",
        element: <WorkbenchPage initialMainPage="execution" />,
      },
      {
        path: "delivery",
        element: <WorkbenchPage initialMainPage="deliverables" />,
      },
      {
        path: "deliverables",
        element: <WorkbenchPage initialMainPage="deliverables" />,
      },
      {
        path: "approvals",
        element: <WorkbenchPage initialMainPage="deliverables" />,
      },
      {
        path: "governance",
        element: <WorkbenchPage initialMainPage="governance" />,
      },
      {
        path: "me",
        element: <WorkbenchPage initialModal="account" />,
      },
      {
        path: "settings",
        element: <WorkbenchPage initialModal="settings" />,
      },
      {
        path: "*",
        element: <Navigate to="/workbench" replace />,
      },
    ],
  },
]);
