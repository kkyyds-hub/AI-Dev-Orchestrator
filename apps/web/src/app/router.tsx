import { Navigate, createBrowserRouter } from "react-router-dom";

import { AppShell } from "./AppShell";
import { buildTaskRoute } from "../lib/task-route";
import { ApprovalsPage } from "../pages/approvals/ApprovalsPage";
import { DeliverablesPage } from "../pages/deliverables/DeliverablesPage";
import { GovernancePage } from "../pages/governance/GovernancePage";
import { ProjectApprovalsRoutePage } from "../pages/projects/ProjectApprovalsRoutePage";
import { ProjectCollaborationRoutePage } from "../pages/projects/ProjectCollaborationRoutePage";
import { ProjectOverviewRoutePage } from "../pages/projects/ProjectOverviewRoutePage";
import { ProjectDeliverablesRoutePage } from "../pages/projects/ProjectDeliverablesRoutePage";
import { ProjectGovernanceRoutePage } from "../pages/projects/ProjectGovernanceRoutePage";
import { ProjectTimelineRoutePage } from "../pages/projects/ProjectTimelineRoutePage";
import { ProjectsPage } from "../pages/projects/ProjectsPage";
import { PlaceholderPage } from "../pages/shared/PlaceholderPage";
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
        path: "deliverables",
        element: (
          <DeliverablesPage
            onNavigateToTask={(taskId, options) =>
              buildTaskRoute({
                taskId,
                runId: options?.runId ?? null,
                from: "deliverables",
              })
            }
          />
        ),
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
        element: (
          <PlaceholderPage
            title="我的工作区即将开放"
            description="个人视图入口已经保留，后续会在这里集中呈现我的任务、我的审批与关注项目。"
            nextStep="优先完善与个人处理效率强相关的任务、审批与关注项聚合能力。"
          />
        ),
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
