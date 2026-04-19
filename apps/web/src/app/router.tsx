import { Navigate, createBrowserRouter } from "react-router-dom";

import { AppShell } from "./AppShell";
import { ProjectsPage } from "../pages/projects/ProjectsPage";
import { PlaceholderPage } from "../pages/shared/PlaceholderPage";
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
            title="任务中心即将开放"
            description="任务域入口已经接入正式导航，后续会在这里承接更完整的任务列表、任务详情与处理流转。"
            nextStep="优先完善任务对象的独立访问体验，让任务列表与任务详情可以在统一入口中连续操作。"
          />
        ),
      },
      {
        path: "runs/*",
        element: (
          <PlaceholderPage
            title="运行观测即将开放"
            description="运行观测入口已经准备就绪，后续会在这里集中承接运行状态、日志链路与执行细节。"
            nextStep="优先补齐运行详情与日志查看能力，让执行链路具备更清晰的深链接体验。"
          />
        ),
      },
      {
        path: "deliverables/*",
        element: (
          <PlaceholderPage
            title="交付物中心即将开放"
            description="交付物入口已经纳入统一导航，后续会在这里集中呈现交付物、版本快照与关联回溯能力。"
            nextStep="逐步把项目域中的交付物访问体验提升为统一入口，减少跨页面查找成本。"
          />
        ),
      },
      {
        path: "approvals/*",
        element: (
          <PlaceholderPage
            title="审批中心即将开放"
            description="审批入口已经纳入统一导航，后续会在这里承接审批队列、审批详情与人工确认动作。"
            nextStep="逐步完善审批列表、审批详情和项目上下文之间的连续跳转体验。"
          />
        ),
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
