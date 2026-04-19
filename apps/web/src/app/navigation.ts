export type PrimaryNavigationItem = {
  label: string;
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
    to: "/workbench",
    description: "当前最值得处理的控制台聚合页。",
  },
  {
    label: "项目",
    to: "/projects",
    description: "项目域入口与项目总览承接页。",
  },
  {
    label: "任务",
    to: "/tasks",
    description: "后续提升任务列表与详情。",
  },
  {
    label: "运行观测",
    to: "/runs",
    description: "后续提升运行与日志深链接。",
  },
  {
    label: "交付物",
    to: "/deliverables",
    description: "交付与版本快照域。",
  },
  {
    label: "审批",
    to: "/approvals",
    description: "集中处理审批与人工决策。",
  },
  {
    label: "治理",
    to: "/governance",
    description: "角色、记忆、技能与策略配置。",
  },
  {
    label: "我的",
    to: "/me",
    description: "个人工作视图占位入口。",
  },
  {
    label: "设置",
    to: "/settings",
    description: "系统级设置与环境配置。",
  },
];

export function resolveRouteMeta(pathname: string): RouteMeta {
  if (pathname.startsWith("/projects/")) {
    const segments = pathname.split("/").filter(Boolean);
    const projectId = segments[1] ?? null;
    return {
      section: "项目",
      title: "项目总览",
      description: "正式项目域路由入口，当前继续复用现有 ProjectOverviewPage。",
      breadcrumbs: projectId ? ["项目", projectId] : ["项目"],
    };
  }

  if (pathname.startsWith("/projects")) {
    return {
      section: "项目",
      title: "项目域入口",
      description: "承接现有项目总览与项目内模块导航。",
      breadcrumbs: ["项目"],
    };
  }

  if (pathname.startsWith("/tasks")) {
    return {
      section: "任务",
      title: "任务域骨架",
      description: "本轮先建立正式路由入口，业务提升放到 Step 2。",
      breadcrumbs: ["任务"],
    };
  }

  if (pathname.startsWith("/runs")) {
    return {
      section: "运行观测",
      title: "运行观测骨架",
      description: "本轮先建立正式路由入口，日志与详情后续再提升。",
      breadcrumbs: ["运行观测"],
    };
  }

  if (pathname.startsWith("/deliverables")) {
    return {
      section: "交付物",
      title: "交付物骨架",
      description: "预留正式路由入口，避免继续把入口挂在大首页里。",
      breadcrumbs: ["交付物"],
    };
  }

  if (pathname.startsWith("/approvals")) {
    return {
      section: "审批",
      title: "审批骨架",
      description: "预留审批域路由入口，后续再提升审批列表与详情。",
      breadcrumbs: ["审批"],
    };
  }

  if (pathname.startsWith("/governance")) {
    return {
      section: "治理",
      title: "治理骨架",
      description: "角色、记忆、Skill 与策略能力的正式域入口。",
      breadcrumbs: ["治理"],
    };
  }

  if (pathname.startsWith("/me")) {
    return {
      section: "我的",
      title: "我的工作台骨架",
      description: "预留个人视图入口。",
      breadcrumbs: ["我的"],
    };
  }

  if (pathname.startsWith("/settings")) {
    return {
      section: "设置",
      title: "设置骨架",
      description: "系统级设置入口占位。",
      breadcrumbs: ["设置"],
    };
  }

  return {
    section: "工作台",
    title: "控制台工作台",
    description: "承接当前首页控制台内容，并从正式路由访问。",
    breadcrumbs: ["工作台"],
  };
}
