import { Navigate, createBrowserRouter } from "react-router-dom";

import { AppShell } from "./AppShell";
import { PlaceholderPage } from "../pages/shared/PlaceholderPage";
import { ProjectsPage } from "../pages/projects/ProjectsPage";
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
        path: "tasks/*",
        element: (
          <PlaceholderPage
            title="任务域骨架已预留"
            description="按架构方案，本轮先建立正式路由入口，避免继续把任务域长期压在首页控制台中。"
            nextStep="Step 2 最合理的动作，是把 TaskTableSection 与 TaskDetailPanel 提升为 /tasks 与 /tasks/:taskId。"
          />
        ),
      },
      {
        path: "runs/*",
        element: (
          <PlaceholderPage
            title="运行观测骨架已预留"
            description="按架构方案，本轮先建立正式路由入口，后续再把 run detail 与 run logs 提升为独立深链接页面。"
            nextStep="Step 2 可先落 /runs 与 /runs/:runId，优先解决日志与运行详情深链接。"
          />
        ),
      },
      {
        path: "deliverables/*",
        element: (
          <PlaceholderPage
            title="交付物域骨架已预留"
            description="当前继续由项目域内部承接交付物中心，这里先保留正式路由入口。"
            nextStep="后续可以把交付物中心提升为 /deliverables 与 /deliverables/:deliverableId。"
          />
        ),
      },
      {
        path: "approvals/*",
        element: (
          <PlaceholderPage
            title="审批域骨架已预留"
            description="当前继续由项目域内部承接审批收件箱，这里先保留正式路由入口。"
            nextStep="后续可以把审批队列与审批详情提升为 /approvals 与 /approvals/:approvalId。"
          />
        ),
      },
      {
        path: "governance/*",
        element: (
          <PlaceholderPage
            title="治理域骨架已预留"
            description="角色、记忆、技能与策略能力已拥有正式导航入口，但本轮不继续大拆业务。"
            nextStep="后续再逐步把 roles / skills / providers 等能力迁移到治理域正式子路由。"
          />
        ),
      },
      {
        path: "me",
        element: (
          <PlaceholderPage
            title="我的页面骨架已预留"
            description="先把信息架构中的一级域立起来，再按优先级补个人视图。"
            nextStep="后续可以承接我的任务、我的审批、我的关注项目等内容。"
          />
        ),
      },
      {
        path: "settings",
        element: (
          <PlaceholderPage
            title="设置页骨架已预留"
            description="系统级设置入口已独立，为后续环境与策略配置预留位置。"
            nextStep="后续可以把 Provider Settings 与环境配置正式迁入设置域。"
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
