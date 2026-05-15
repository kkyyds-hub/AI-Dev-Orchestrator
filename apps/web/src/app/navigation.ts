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
    description: "查看关键状态、任务与风险。",
  },
  {
    label: "项目",
    shortLabel: "项",
    to: "/projects",
    description: "管理项目总览与关键上下文。",
  },
  {
    label: "任务",
    shortLabel: "任",
    to: "/tasks",
    description: "处理任务列表、详情与流转。",
  },
  {
    label: "运行观测",
    shortLabel: "运",
    to: "/runs",
    description: "查看运行状态与日志链路。",
  },
  {
    label: "交付物",
    shortLabel: "交",
    to: "/deliverables",
    description: "管理交付物与版本快照。",
  },
  {
    label: "审批",
    shortLabel: "审",
    to: "/approvals",
    description: "处理审批队列与人工决策。",
  },
  {
    label: "治理",
    shortLabel: "治",
    to: "/governance",
    description: "管理角色、记忆与策略配置。",
  },
  {
    label: "账户",
    shortLabel: "账",
    to: "/me",
    description: "查看账户中心与登录注册接入说明。",
  },
  {
    label: "设置",
    shortLabel: "设",
    to: "/settings",
    description: "配置环境与连接状态。",
  },
];

const PROJECT_ROUTE_META_BY_SEGMENT: Record<
  string,
  Pick<RouteMeta, "title" | "description"> & { breadcrumb: string }
> = {
  repository: {
    title: "项目仓库工作区",
    description: "集中处理目录快照、变更会话、文件定位、变更计划、验证与提交草案。",
    breadcrumb: "仓库工作区",
  },
  timeline: {
    title: "项目时间线与复盘",
    description: "独立查看项目时间线、审批回退重做与复盘收口上下文。",
    breadcrumb: "时间线与复盘",
  },
  collaboration: {
    title: "项目协作控制面",
    description: "聚合 Agent Thread、团队控制中心与项目成本看板。",
    breadcrumb: "协作控制",
  },
  governance: {
    title: "项目记忆与角色治理",
    description: "在项目上下文内查看记忆、角色、技能与工作台治理能力。",
    breadcrumb: "记忆与角色治理",
  },
  deliverables: {
    title: "项目交付物中心",
    description: "在项目上下文内查看交付物仓库、版本快照与关联任务。",
    breadcrumb: "交付物中心",
  },
  approvals: {
    title: "项目审批收件箱",
    description: "在项目上下文内处理审批队列、人工确认与关键决策节点。",
    breadcrumb: "审批收件箱",
  },
};

export function resolveRouteMeta(pathname: string): RouteMeta {
  if (pathname.startsWith("/projects/")) {
    const segments = pathname.split("/").filter(Boolean);
    const projectId = segments[1] ?? null;
    const projectRouteSegment = segments[2] ?? null;
    const projectRouteMeta = projectRouteSegment
      ? PROJECT_ROUTE_META_BY_SEGMENT[projectRouteSegment]
      : null;

    return {
      section: "项目",
      title: projectRouteMeta?.title ?? "项目总览",
      description:
        projectRouteMeta?.description ??
        "查看项目当前阶段、关键模块与项目内协同上下文。",
      breadcrumbs: [
        "项目",
        ...(projectId ? [projectId] : []),
        ...(projectRouteMeta ? [projectRouteMeta.breadcrumb] : []),
      ],
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
    const segments = pathname.split("/").filter(Boolean);
    const selectedTaskId = segments[1] ?? null;

    return {
      section: "任务",
      title: "任务中心",
      description: "从统一入口管理任务列表、详情与处理流转。",
      breadcrumbs: selectedTaskId ? ["任务", selectedTaskId] : ["任务"],
    };
  }

  if (pathname.startsWith("/runs")) {
    const segments = pathname.split("/").filter(Boolean);
    const selectedRunId = segments[1] ?? null;

    return {
      section: "运行观测",
      title: "运行观测",
      description: "集中查看运行状态、日志链路与执行细节。",
      breadcrumbs: selectedRunId ? ["运行观测", selectedRunId] : ["运行观测"],
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
      section: "账户",
      title: "我的账户",
      description: "收口账户中心、访问状态、登录注册接入说明与个人账户结构。",
      breadcrumbs: ["账户"],
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
