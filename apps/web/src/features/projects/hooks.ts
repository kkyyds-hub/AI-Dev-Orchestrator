import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  advanceProjectStage,
  appendChangePlanVersion,
  applyProjectPlanDraft,
  createProjectChangePlan,
  createProjectPlanDraft,
  fetchChangePlanDetail,
  fetchBossProjectOverview,
  fetchProjectChangePlans,
  fetchProjectDetail,
  fetchProjectMemorySnapshot,
  fetchProjectTimeline,
  fetchProjectSopTemplates,
  searchProjectMemory,
  selectProjectSopTemplate,
} from "./api";
import type { ChangePlanCreateInput, ChangePlanDraftInput, ProjectMemoryKind } from "./types";

export function useBossProjectOverview(options?: { enablePolling?: boolean }) {
  return useQuery({
    queryKey: ["boss-project-overview"],
    queryFn: fetchBossProjectOverview,
    refetchInterval: options?.enablePolling === false ? false : 5_000,
  });
}

export function useProjectDetail(projectId: string | null) {
  return useQuery({
    queryKey: ["project-detail", projectId],
    queryFn: () => fetchProjectDetail(projectId ?? ""),
    enabled: projectId !== null,
  });
}

export function useProjectMemorySnapshot(projectId: string | null) {
  return useQuery({
    queryKey: ["project-memory", projectId, "snapshot"],
    queryFn: () => fetchProjectMemorySnapshot(projectId ?? ""),
    enabled: projectId !== null,
    staleTime: 30_000,
  });
}

export function useProjectMemorySearch(input: {
  projectId: string | null;
  query: string;
  limit?: number;
  memoryType?: ProjectMemoryKind | null;
  enabled?: boolean;
}) {
  const normalizedQuery = input.query.trim();
  return useQuery({
    queryKey: [
      "project-memory",
      input.projectId,
      "search",
      normalizedQuery,
      input.limit ?? 10,
      input.memoryType ?? "all",
    ],
    queryFn: () =>
      searchProjectMemory({
        projectId: input.projectId ?? "",
        query: normalizedQuery,
        limit: input.limit,
        memoryType: input.memoryType ?? null,
      }),
    enabled:
      (input.enabled ?? true) &&
      input.projectId !== null &&
      normalizedQuery.length > 0,
  });
}

export function useProjectTimeline(projectId: string | null) {
  return useQuery({
    queryKey: ["project-timeline", projectId],
    queryFn: () => fetchProjectTimeline(projectId ?? ""),
    enabled: projectId !== null,
  });
}

export function useProjectSopTemplates() {
  return useQuery({
    queryKey: ["project-sop-templates"],
    queryFn: fetchProjectSopTemplates,
    staleTime: 60_000,
  });
}

export function useSelectProjectSopTemplate(projectId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: { templateCode: string }) => {
      if (!projectId) {
        throw new Error("当前没有可绑定 SOP 模板的项目。");
      }

      return selectProjectSopTemplate({
        projectId,
        templateCode: input.templateCode,
      });
    },
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["boss-project-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["project-detail"] }),
        queryClient.invalidateQueries({ queryKey: ["project-timeline", projectId] }),
        queryClient.invalidateQueries({
          queryKey: ["project-detail", result.project_id],
        }),
      ]);
    },
  });
}

export function useAdvanceProjectStage(projectId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: { note?: string | null }) => {
      if (!projectId) {
        throw new Error("当前没有可推进阶段的项目。");
      }

      return advanceProjectStage({
        projectId,
        note: input.note ?? null,
      });
    },
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["boss-project-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["project-detail"] }),
        queryClient.invalidateQueries({ queryKey: ["project-timeline", projectId] }),
        queryClient.invalidateQueries({
          queryKey: ["project-detail", result.project_id],
        }),
      ]);
    },
  });
}

export function useCreateProjectPlanDraft() {
  return useMutation({
    mutationFn: createProjectPlanDraft,
  });
}

export function useApplyProjectPlanDraft() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: applyProjectPlanDraft,
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["boss-project-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["console-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["project-detail"] }),
        queryClient.invalidateQueries({ queryKey: ["project-timeline"] }),
        ...(result.project
          ? [
              queryClient.invalidateQueries({
                queryKey: ["project-detail", result.project.id],
              }),
              queryClient.invalidateQueries({
                queryKey: ["project-timeline", result.project.id],
              }),
            ]
          : []),
      ]);
    },
  });
}

export function useProjectChangePlans(input: {
  projectId: string | null;
  taskId?: string | null;
}) {
  return useQuery({
    queryKey: ["project-change-plans", input.projectId, input.taskId ?? "all"],
    queryFn: () =>
      fetchProjectChangePlans({
        projectId: input.projectId ?? "",
        taskId: input.taskId ?? null,
      }),
    enabled: input.projectId !== null,
  });
}

export function useChangePlanDetail(changePlanId: string | null) {
  return useQuery({
    queryKey: ["change-plan-detail", changePlanId],
    queryFn: () => fetchChangePlanDetail(changePlanId ?? ""),
    enabled: changePlanId !== null,
  });
}

export function useCreateProjectChangePlan(projectId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: ChangePlanCreateInput) => {
      if (!projectId) {
        throw new Error("当前没有可创建变更计划草案的项目。");
      }

      return createProjectChangePlan({
        projectId,
        payload,
      });
    },
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["project-change-plans", result.project_id] }),
        queryClient.invalidateQueries({ queryKey: ["change-plan-detail"] }),
        queryClient.invalidateQueries({ queryKey: ["project-detail", result.project_id] }),
      ]);
      queryClient.setQueryData(["change-plan-detail", result.id], result);
    },
  });
}

export function useAppendChangePlanVersion() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (input: {
      changePlanId: string;
      payload: ChangePlanDraftInput;
    }) =>
      appendChangePlanVersion({
        changePlanId: input.changePlanId,
        payload: input.payload,
      }),
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["project-change-plans", result.project_id] }),
        queryClient.invalidateQueries({ queryKey: ["change-plan-detail", result.id] }),
        queryClient.invalidateQueries({ queryKey: ["project-detail", result.project_id] }),
      ]);
      queryClient.setQueryData(["change-plan-detail", result.id], result);
    },
  });
}
