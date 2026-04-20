import { Navigate, createBrowserRouter } from "react-router-dom";

import { AppShell } from "./AppShell";
import { buildTaskRoute } from "../lib/task-route";
import { ApprovalsPage } from "../pages/approvals/ApprovalsPage";
import { DeliverablesPage } from "../pages/deliverables/DeliverablesPage";
import { ProjectsPage } from "../pages/projects/ProjectsPage";
import { PlaceholderPage } from "../pages/shared/PlaceholderPage";
import { RunsPage } from "../pages/runs/RunsPage";
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
        element: <ProjectsPage />,
      },
      {
        path: "projects/:projectId/timeline",
        element: <ProjectsPage />,
      },
      {
        path: "projects/:projectId/collaboration",
        element: <ProjectsPage />,
      },
      {
        path: "projects/:projectId/governance",
        element: <ProjectsPage />,
      },
      {
        path: "projects/:projectId/deliverables",
        element: <ProjectsPage />,
      },
      {
        path: "projects/:projectId/approvals",
        element: <ProjectsPage />,
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
        path: "governance/*",
        element: (
          <PlaceholderPage
            title="治理中心即将开放"
            description="治理入口已经建立，后续会在这里逐步整合角色、记忆、技能与策略相关能力。"
            nextStep="逐步把治理能力聚合到统一入口，提升配置检索与跨能力切换效率。"
          />
        ),
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
        element: (
          <PlaceholderPage
            title="系统设置即将开放"
            description="系统设置入口已经独立，后续会在这里承接环境配置、连接状态与平台级设置。"
            nextStep="逐步把系统设置能力集中到统一入口，便于维护环境与平台参数。"
          />
        ),
      },
      {
        path: "*",
        element: <Navigate to="/workbench" replace />,
      },
    ],
  },
]);