export type ProjectOverviewPageView =
  | "overview"
  | "timeline-retrospective"
  | "collaboration-control"
  | "memory-role-governance"
  | "deliverable-center"
  | "approval-inbox";

export type ProjectOverviewRouteSegment =
  | "timeline"
  | "collaboration"
  | "governance"
  | "deliverables"
  | "approvals";

type ProjectOverviewSectionNavigationItem = {
  kind: "section";
  view: "overview";
  id: string;
  label: string;
  description: string;
};

type ProjectOverviewPageNavigationItem = {
  kind: "page";
  view: Exclude<ProjectOverviewPageView, "overview">;
  id: string;
  label: string;
  description: string;
};

export type ProjectOverviewNavigationItem =
  | ProjectOverviewSectionNavigationItem
  | ProjectOverviewPageNavigationItem;

const PROJECT_OVERVIEW_VIEWS: readonly ProjectOverviewPageView[] = [
  "overview",
  "timeline-retrospective",
  "collaboration-control",
  "memory-role-governance",
  "deliverable-center",
  "approval-inbox",
];

const PROJECT_OVERVIEW_ROUTE_SEGMENT_BY_VIEW: Readonly<
  Partial<Record<ProjectOverviewPageView, ProjectOverviewRouteSegment>>
> = {
  "timeline-retrospective": "timeline",
  "collaboration-control": "collaboration",
  "memory-role-governance": "governance",
  "deliverable-center": "deliverables",
  "approval-inbox": "approvals",
};

const PROJECT_OVERVIEW_VIEW_BY_ROUTE_SEGMENT: Readonly<
  Record<ProjectOverviewRouteSegment, Exclude<ProjectOverviewPageView, "overview">>
> = {
  timeline: "timeline-retrospective",
  collaboration: "collaboration-control",
  governance: "memory-role-governance",
  deliverables: "deliverable-center",
  approvals: "approval-inbox",
};

const LEGACY_PROJECT_OVERVIEW_HASH_COMPAT: Readonly<
  Record<string, { view: ProjectOverviewPageView; targetId: string | null }>
> = {
  "#project-detail": {
    view: "overview",
    targetId: "project-detail",
  },
  "#timeline-retrospective": {
    view: "timeline-retrospective",
    targetId: "timeline-retrospective",
  },
  "#collaboration-control": {
    view: "collaboration-control",
    targetId: "collaboration-control",
  },
  "#memory-role-governance": {
    view: "memory-role-governance",
    targetId: "memory-role-governance",
  },
  "#deliverable-center": {
    view: "deliverable-center",
    targetId: "deliverable-center",
  },
  "#approval-inbox": {
    view: "approval-inbox",
    targetId: "approval-inbox",
  },
  "#project-overview-view-timeline-retrospective": {
    view: "timeline-retrospective",
    targetId: "timeline-retrospective",
  },
  "#project-overview-view-collaboration-control": {
    view: "collaboration-control",
    targetId: "collaboration-control",
  },
  "#project-overview-view-memory-role-governance": {
    view: "memory-role-governance",
    targetId: "memory-role-governance",
  },
  "#project-overview-view-deliverable-center": {
    view: "deliverable-center",
    targetId: "deliverable-center",
  },
  "#project-overview-view-approval-inbox": {
    view: "approval-inbox",
    targetId: "approval-inbox",
  },
};

export const PROJECT_OVERVIEW_NAVIGATION_ITEMS: readonly ProjectOverviewNavigationItem[] =
  [
    {
      kind: "section",
      view: "overview",
      id: "project-detail",
      label: "项目详情",
      description: "页内定位到项目详情、阶段推进与关键钻取面板。",
    },
    {
      kind: "page",
      view: "timeline-retrospective",
      id: "timeline-retrospective",
      label: "时间线与复盘",
      description: "独立查看项目时间线、审批回退重做与复盘收口。",
    },
    {
      kind: "page",
      view: "collaboration-control",
      id: "collaboration-control",
      label: "协作控制面",
      description: "聚合 Agent Thread、Team Control 与成本看板能力。",
    },
    {
      kind: "page",
      view: "memory-role-governance",
      id: "memory-role-governance",
      label: "记忆与角色治理",
      description: "聚合记忆治理、角色目录、Skill 注册中心与工作台。",
    },
    {
      kind: "page",
      view: "deliverable-center",
      id: "deliverable-center",
      label: "交付物中心",
      description: "进入交付物仓库与版本快照列表。",
    },
    {
      kind: "page",
      view: "approval-inbox",
      id: "approval-inbox",
      label: "审批收件箱",
      description: "查看审批队列并处理关键审批动作。",
    },
  ];

export function getProjectOverviewDefaultTargetId(view: ProjectOverviewPageView) {
  return view === "overview" ? "project-detail" : view;
}

export function projectOverviewRouteSegmentToView(
  routeSegment: string | null | undefined,
): Exclude<ProjectOverviewPageView, "overview"> | null {
  if (!routeSegment) {
    return null;
  }

  return (
    PROJECT_OVERVIEW_VIEW_BY_ROUTE_SEGMENT[
      routeSegment as ProjectOverviewRouteSegment
    ] ?? null
  );
}

export function buildProjectOverviewRoute(input: {
  projectId: string | null;
  view: ProjectOverviewPageView;
}) {
  if (!input.projectId) {
    return "/projects";
  }

  const routeSegment = PROJECT_OVERVIEW_ROUTE_SEGMENT_BY_VIEW[input.view];
  return routeSegment
    ? `/projects/${input.projectId}/${routeSegment}`
    : `/projects/${input.projectId}`;
}

export function buildProjectOverviewHash(input: {
  view: ProjectOverviewPageView;
  targetId?: string | null;
}) {
  const params = new URLSearchParams();
  params.set("view", input.view);
  if (input.targetId) {
    params.set("targetId", input.targetId);
  }
  return `#project-overview?${params.toString()}`;
}

export function navigateToProjectOverviewHash(input: {
  view: ProjectOverviewPageView;
  targetId?: string | null;
}) {
  const nextHash = buildProjectOverviewHash(input);
  if (window.location.hash === nextHash) {
    window.dispatchEvent(new HashChangeEvent("hashchange"));
    return;
  }
  window.location.hash = nextHash;
}

function isProjectOverviewView(value: string | null): value is ProjectOverviewPageView {
  return Boolean(value && PROJECT_OVERVIEW_VIEWS.includes(value as ProjectOverviewPageView));
}

function parseLegacyProjectOverviewHash(hashValue: string): {
  view: ProjectOverviewPageView;
  targetId: string | null;
} | null {
  const normalizedHash = hashValue.split("?")[0] ?? hashValue;
  return LEGACY_PROJECT_OVERVIEW_HASH_COMPAT[normalizedHash] ?? null;
}

export function parseProjectOverviewHash(hashValue: string): {
  view: ProjectOverviewPageView;
  targetId: string | null;
} | null {
  if (hashValue === "#project-overview" || hashValue === "#project-overview/") {
    return {
      view: "overview",
      targetId: "project-detail",
    };
  }

  if (hashValue.startsWith("#project-overview")) {
    const queryIndex = hashValue.indexOf("?");
    const searchValue = queryIndex >= 0 ? hashValue.slice(queryIndex + 1) : "";
    const params = new URLSearchParams(searchValue);
    const view = params.get("view");

    if (isProjectOverviewView(view)) {
      return {
        view,
        targetId: params.get("targetId"),
      };
    }
  }
  return parseLegacyProjectOverviewHash(hashValue);
}
