import type {
  BossProjectOverview,
  ProjectDetail,
  ProjectMemoryKind,
  ProjectMemorySearchResult,
  ProjectMemorySnapshot,
  ProjectTimeline,
  ProjectSopTemplateSelectResult,
  ProjectSopTemplateSummary,
  ProjectStageAdvanceResult,
  ProjectPlanApplyResult,
  ProjectPlanDraft,
} from "./types";
import { requestJson } from "../../lib/http";

export function fetchBossProjectOverview(): Promise<BossProjectOverview> {
  return requestJson<BossProjectOverview>("/console/project-overview");
}

export function fetchProjectDetail(projectId: string): Promise<ProjectDetail> {
  return requestJson<ProjectDetail>(`/projects/${projectId}`);
}

export function fetchProjectMemorySnapshot(
  projectId: string,
): Promise<ProjectMemorySnapshot> {
  return requestJson<ProjectMemorySnapshot>(`/projects/${projectId}/memory`);
}

export function searchProjectMemory(input: {
  projectId: string;
  query: string;
  limit?: number;
  memoryType?: ProjectMemoryKind | null;
}): Promise<ProjectMemorySearchResult> {
  const params = new URLSearchParams();
  params.set("q", input.query);
  if (typeof input.limit === "number") {
    params.set("limit", String(input.limit));
  }
  if (input.memoryType) {
    params.set("memory_type", input.memoryType);
  }

  return requestJson<ProjectMemorySearchResult>(
    `/projects/${input.projectId}/memory/search?${params.toString()}`,
  );
}

export function fetchProjectTimeline(projectId: string): Promise<ProjectTimeline> {
  return requestJson<ProjectTimeline>(`/projects/${projectId}/timeline`);
}

export function fetchProjectSopTemplates(): Promise<ProjectSopTemplateSummary[]> {
  return requestJson<ProjectSopTemplateSummary[]>("/projects/sop-templates");
}

export function selectProjectSopTemplate(input: {
  projectId: string;
  templateCode: string;
}): Promise<ProjectSopTemplateSelectResult> {
  return requestJson<ProjectSopTemplateSelectResult>(
    `/projects/${input.projectId}/sop-template`,
    {
      method: "PUT",
      body: JSON.stringify({
        template_code: input.templateCode,
      }),
    },
  );
}

export function advanceProjectStage(input: {
  projectId: string;
  note?: string | null;
}): Promise<ProjectStageAdvanceResult> {
  return requestJson<ProjectStageAdvanceResult>(
    `/projects/${input.projectId}/advance-stage`,
    {
      method: "POST",
      body: JSON.stringify({
        note: input.note ?? null,
      }),
    },
  );
}

export function createProjectPlanDraft(input: {
  brief: string;
  max_tasks: number;
}): Promise<ProjectPlanDraft> {
  return requestJson<ProjectPlanDraft>("/planning/drafts", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function applyProjectPlanDraft(input: {
  project_summary: string;
  project?: {
    name: string;
    summary: string;
    status: string;
    stage: string;
  } | null;
  tasks: Array<{
    draft_id: string;
    title: string;
    input_summary: string;
    priority: string;
    acceptance_criteria: string[];
    depends_on_draft_ids: string[];
    risk_level: string;
    human_status: string;
    paused_reason: string | null;
  }>;
}): Promise<ProjectPlanApplyResult> {
  return requestJson<ProjectPlanApplyResult>("/planning/apply", {
    method: "POST",
    body: JSON.stringify(input),
  });
}
