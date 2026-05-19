import { Navigate, createBrowserRouter } from "react-router-dom";

import { AppShell } from "./AppShell";
import { ApprovalsPage } from "../pages/approvals/ApprovalsPage";
import { DeliverablesPage } from "../pages/deliverables/DeliverablesPage";
import { DeliveryCenterPage } from "../pages/delivery/DeliveryCenterPage";
import { ExecutionCenterPage } from "../pages/execution/ExecutionCenterPage";
import { GovernancePage } from "../pages/governance/GovernancePage";
import { MePage } from "../pages/me/MePage";
import { ProjectApprovalsRoutePage } from "../pages/projects/ProjectApprovalsRoutePage";
import { ProjectCollaborationRoutePage } from "../pages/projects/ProjectCollaborationRoutePage";
import { ProjectOverviewRoutePage } from "../pages/projects/ProjectOverviewRoutePage";
import { ProjectDeliverablesRoutePage } from "../pages/projects/ProjectDeliverablesRoutePage";
import { ProjectGovernanceRoutePage } from "../pages/projects/ProjectGovernanceRoutePage";
import { ProjectRepositoryRoutePage } from "../pages/projects/ProjectRepositoryRoutePage";
import { ProjectTimelineRoutePage } from "../pages/projects/ProjectTimelineRoutePage";
import { ProjectsPage } from "../pages/projects/ProjectsPage";
import { RunsPage } from "../pages/runs/RunsPage";
import { SettingsPage } from "../features/settings/SettingsPage";
import { TasksPage } from "../pages/tasks/TasksPage";
import { WorkbenchPage } from "../pages/workbench/WorkbenchPage";

export const router = createBrowserRouter([
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
        element: <ProjectsPage />,
      },
      {
        path: "projects/:projectId",
        element: <ProjectOverviewRoutePage />,
      },
      {
        path: "projects/:projectId/repository",
        element: <ProjectRepositoryRoutePage />,
      },
      {
        path: "projects/:projectId/timeline",
        element: <ProjectTimelineRoutePage />,
      },
      {
        path: "projects/:projectId/collaboration",
        element: <ProjectCollaborationRoutePage />,
      },
      {
        path: "projects/:projectId/governance",
        element: <ProjectGovernanceRoutePage />,
      },
      {
        path: "projects/:projectId/deliverables",
        element: <ProjectDeliverablesRoutePage />,
      },
      {
        path: "projects/:projectId/approvals",
        element: <ProjectApprovalsRoutePage />,
      },
      {
        path: "tasks",
        element: <TasksPage />,
      },
      {
        path: "tasks/:taskId",
        element: <TasksPage />,
      },
      {
        path: "runs",
        element: <RunsPage />,
      },
      {
        path: "runs/:runId",
        element: <RunsPage />,
      },
      {
        path: "delivery",
        element: <DeliveryCenterPage />,
      },
      {
        path: "deliverables",
        element: <DeliverablesPage />,
      },
      {
        path: "approvals",
        element: <ApprovalsPage />,
      },
      {
        path: "governance",
        element: <GovernancePage />,
      },
      {
        path: "me",
        element: <MePage />,
      },
      {
        path: "execution",
        element: <ExecutionCenterPage />,
      },
      {
        path: "settings",
        element: <SettingsPage />,
      },
      {
        path: "*",
        element: <Navigate to="/workbench" replace />,
      },
    ],
  },
]);
