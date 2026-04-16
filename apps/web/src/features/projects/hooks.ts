import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  advanceProjectStage,
  appendChangePlanVersion,
  applyProjectPlanDraft,
  createProjectChangePlan,
  createProjectPlanDraft,
  fetchTaskOwnership,
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
import {
  buildBossDrilldownHash,
  parseBossDrilldownHash,
} from "./lib/bossDrilldown";
import type {
  BossDrilldownContext,
  BossDrilldownEventDetail,
  BossDrilldownFeedback,
  BossProjectItem,
  ChangePlanCreateInput,
  ChangePlanDraftInput,
  ProjectMemoryKind,
} from "./types";

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

export function useBossProjectDrilldown(input: {
  projects: BossProjectItem[];
  refetchOverview: () => Promise<{ data?: { projects: BossProjectItem[] } }>;
  onSelectProject: (
    projectId: string,
    options?: {
      scrollIntoDetail?: boolean;
      preserveDrilldownContext?: boolean;
    },
  ) => void;
}) {
  const lastAppliedDrilldownHashRef = useRef<string | null>(null);
  const [drilldownContext, setDrilldownContext] =
    useState<BossDrilldownContext | null>(null);
  const [drilldownFeedback, setDrilldownFeedback] =
    useState<BossDrilldownFeedback | null>(null);

  const navigateToDrilldown = async (detail: BossDrilldownEventDetail) => {
    if (!detail.taskId) {
      return;
    }

    let resolvedProjectId: string | null = null;
    try {
      const task = await fetchTaskOwnership(detail.taskId);
      resolvedProjectId = task.project_id ?? null;
    } catch (error) {
      setDrilldownFeedback({
        tone: "warning",
        text:
          error instanceof Error
            ? `Unable to resolve authoritative project ownership for task ${detail.taskId}: ${error.message}`
            : `Unable to resolve authoritative project ownership for task ${detail.taskId}.`,
      });
      return;
    }

    if (!resolvedProjectId) {
      setDrilldownFeedback({
        tone: "warning",
        text:
          "Unable to resolve authoritative project ownership for this task. Drill-down was not applied.",
      });
      return;
    }

    let availableProjects = input.projects;
    if (!availableProjects.some((project) => project.id === resolvedProjectId)) {
      const refreshedOverview = await input.refetchOverview();
      availableProjects = refreshedOverview.data?.projects ?? availableProjects;
    }

    if (!availableProjects.some((project) => project.id === resolvedProjectId)) {
      setDrilldownFeedback({
        tone: "warning",
        text: `Task ${detail.taskId} belongs to project ${resolvedProjectId}, but that project is not available in current homepage overview.`,
      });
      return;
    }

    const nextContext: BossDrilldownContext = {
      source: detail.source ?? "home_latest_run",
      project_id: resolvedProjectId,
      task_id: detail.taskId,
      run_id: detail.runId ?? null,
    };

    setDrilldownContext(nextContext);
    setDrilldownFeedback({
      tone: "success",
      text:
        detail.projectId && detail.projectId !== resolvedProjectId
          ? `Drill-down context active with authoritative project override (${detail.projectId} -> ${resolvedProjectId}): task ${nextContext.task_id}, run ${nextContext.run_id ?? "n/a"}.`
          : `Drill-down context active: task ${nextContext.task_id}, run ${nextContext.run_id ?? "n/a"}.`,
    });

    const nextHash = buildBossDrilldownHash(nextContext);
    window.location.hash = nextHash;
    lastAppliedDrilldownHashRef.current = nextHash;

    input.onSelectProject(resolvedProjectId, {
      scrollIntoDetail: true,
      preserveDrilldownContext: true,
    });

    requestAnimationFrame(() => {
      document.getElementById("project-latest-run-control-surface")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  };

  const navigateToStrategyPreview = (context: BossDrilldownContext) => {
    setDrilldownContext(context);
    setDrilldownFeedback({
      tone: "success",
      text: `Continue drill-down to Strategy Preview with run ${context.run_id ?? "n/a"}.`,
    });

    const nextHash = buildBossDrilldownHash(context);
    window.location.hash = nextHash;
    lastAppliedDrilldownHashRef.current = nextHash;

    requestAnimationFrame(() => {
      document.getElementById("strategy-preview-panel")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  };

  const navigateToProjectLatestRun = (context: BossDrilldownContext) => {
    const nextContext: BossDrilldownContext = {
      ...context,
      source: "strategy_preview",
    };
    setDrilldownContext(nextContext);
    setDrilldownFeedback({
      tone: "success",
      text: `Return to Project Latest Run with run ${nextContext.run_id ?? "n/a"}.`,
    });

    const nextHash = buildBossDrilldownHash(nextContext);
    window.location.hash = nextHash;
    lastAppliedDrilldownHashRef.current = nextHash;

    requestAnimationFrame(() => {
      document.getElementById("project-latest-run-control-surface")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  };

  useEffect(() => {
    const handleDrilldownNavigation = (event: Event) => {
      const detail = (event as CustomEvent<BossDrilldownEventDetail>).detail;
      void navigateToDrilldown(detail);
    };

    window.addEventListener(
      "boss:drilldown-navigate",
      handleDrilldownNavigation as EventListener,
    );

    return () => {
      window.removeEventListener(
        "boss:drilldown-navigate",
        handleDrilldownNavigation as EventListener,
      );
    };
  }, [input.projects, input.refetchOverview, input.onSelectProject]);

  useEffect(() => {
    const applyHashDrilldown = () => {
      if (window.location.hash === lastAppliedDrilldownHashRef.current) {
        return;
      }

      const parsed = parseBossDrilldownHash(window.location.hash);
      if (!parsed?.taskId) {
        return;
      }
      void navigateToDrilldown(parsed);
    };

    applyHashDrilldown();
    window.addEventListener("hashchange", applyHashDrilldown);

    return () => {
      window.removeEventListener("hashchange", applyHashDrilldown);
    };
  }, [input.projects, input.refetchOverview, input.onSelectProject]);

  return {
    drilldownContext,
    drilldownFeedback,
    setDrilldownContext,
    setDrilldownFeedback,
    navigateToStrategyPreview,
    navigateToProjectLatestRun,
  };
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
