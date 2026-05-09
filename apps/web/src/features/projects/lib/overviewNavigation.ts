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

export type ProjectOverviewNavigationItem = {
  view: ProjectOverviewPageView;
  id: string;
  label: string;
  description: string;
};

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
      view: "overview",
      id: "overview",
      label: "总览",
      description: "项目组合、创建入口、仓库上下文与当前项目详情。",
    },
    {
      view: "timeline-retrospective",
      id: "timeline-retrospective",
      label: "时间线",
      description: "项目事件、阶段推进与复盘线索。",
    },
    {
      view: "collaboration-control",
      id: "collaboration-control",
      label: "协作",
      description: "Agent Thread、团队控制与协同状态。",
    },
    {
      view: "memory-role-governance",
      id: "memory-role-governance",
      label: "记忆与治理",
      description: "项目记忆、角色目录与治理工作台。",
    },
    {
      view: "deliverable-center",
      id: "deliverable-center",
      label: "交付物",
      description: "交付物仓库与版本快照。",
    },
    {
      view: "approval-inbox",
      id: "approval-inbox",
      label: "审批",
      description: "审批队列与关键决策入口。",
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
  const encodedProjectId = encodeURIComponent(input.projectId);
  return routeSegment
    ? `/projects/${encodedProjectId}/${routeSegment}`
    : `/projects/${encodedProjectId}`;
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
