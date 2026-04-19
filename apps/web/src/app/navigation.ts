export type PrimaryNavigationItem = {
  label: string;
  shortLabel: string;
  to: string;
  description: string;
};

export type RouteMeta = {
  section: string;
  title: string;
  description: string;
  breadcrumbs: string[];
};

export const PRIMARY_NAV_ITEMS: readonly PrimaryNavigationItem[] = [
  {
    label: "工作台",
    shortLabel: "工",
    to: "/workbench",
    description: "聚合当前最值得处理的状态、任务与风险。",
  },
  {
    label: "项目",
    shortLabel: "项",
    to: "/projects",
    description: "进入项目域并查看项目总览与关键上下文。",
  },
  {
    label: "任务",
    shortLabel: "任",
    to: "/tasks",
    description: "统一承接任务列表、详情与后续处理入口。",
  },
  {
    label: "运行观测",
    shortLabel: "运",
    to: "/runs",
    description: "查看运行状态、日志链路与执行观测能力。",
  },
  {
    label: "交付物",
    shortLabel: "交",
    to: "/deliverables",
    description: "管理交付物、版本快照与回溯入口。",
  },
  {
    label: "审批",
    shortLabel: "审",
    to: "/approvals",
    description: "集中处理审批队列与人工决策事项。",
  },
  {
    label: "治理",
    shortLabel: "治",
    to: "/governance",
    description: "管理角色、记忆、技能与策略配置。",
  },
  {
    label: "我的",
    shortLabel: "我",
    to: "/me",
    description: "聚合个人待办、关注项与偏好入口。",
  },
  {
    label: "设置",
    shortLabel: "设",
    to: "/settings",
    description: "进入系统设置、环境配置与连接状态。",
  },
];

export function resolveRouteMeta(pathname: string): RouteMeta {
  if (pathname.startsWith("/projects/")) {
    const segments = pathname.split("/").filter(Boolean);
    const projectId = segments[1] ?? null;

    return {
      section: "项目",
      title: "项目总览",
      description: "查看项目当前阶段、关键模块与项目内协同上下文。",
      breadcrumbs: projectId ? ["项目", projectId] : ["项目"],
    };
  }

  if (pathname.startsWith("/projects")) {
    return {
      section: "项目",
      title: "项目中心",
      description: "统一进入项目域并承接项目总览相关能力。",
      breadcrumbs: ["项目"],
    };
  }

  if (pathname.startsWith("/tasks")) {
    return {
      section: "任务",
      title: "任务中心",
      description: "从统一入口管理任务列表、详情与处理流转。",
      breadcrumbs: ["任务"],
    };
  }

  if (pathname.startsWith("/runs")) {
    return {
      section: "运行观测",
      title: "运行观测",
      description: "集中查看运行状态、日志链路与执行细节。",
      breadcrumbs: ["运行观测"],
    };
  }

  if (pathname.startsWith("/deliverables")) {
    return {
      section: "交付物",
      title: "交付物中心",
      description: "在统一入口查看交付物、版本快照与关联上下文。",
      breadcrumbs: ["交付物"],
    };
  }

  if (pathname.startsWith("/approvals")) {
    return {
      section: "审批",
      title: "审批中心",
      description: "集中处理审批流、人工确认与关键决策节点。",
      breadcrumbs: ["审批"],
    };
  }

  if (pathname.startsWith("/governance")) {
    return {
      section: "治理",
      title: "治理中心",
      description: "统一管理角色、记忆、技能与平台治理能力。",
      breadcrumbs: ["治理"],
    };
  }

  if (pathname.startsWith("/me")) {
    return {
      section: "我的",
      title: "我的工作区",
      description: "聚合个人任务、关注项目与近期处理记录。",
      breadcrumbs: ["我的"],
    };
  }

  if (pathname.startsWith("/settings")) {
    return {
      section: "设置",
      title: "系统设置",
      description: "配置环境、连接状态与平台级参数。",
      breadcrumbs: ["设置"],
    };
  }

  return {
    section: "工作台",
    title: "控制台工作台",
    description: "聚合项目状态、待办事项与关键运行上下文。",
    breadcrumbs: ["工作台"],
  };
}
