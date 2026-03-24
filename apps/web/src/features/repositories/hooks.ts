import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  buildProjectCodeContextPack,
  captureProjectChangeSession,
  createProjectChangeBatch,
  fetchChangeBatchDetail,
  fetchChangeBatchCommitCandidate,
  fetchProjectChangeBatches,
  fetchProjectCommitCandidates,
  fetchProjectChangeSession,
  fetchProjectRepositoryVerificationBaseline,
  fetchProjectRepositorySnapshot,
  generateChangeBatchCommitCandidate,
  replaceProjectRepositoryVerificationBaseline,
  refreshProjectRepositorySnapshot,
  runChangeBatchPreflight,
  searchProjectRepositoryFiles,
} from "./api";
import type {
  ChangeBatchPreflightInput,
  CommitCandidateDraftInput,
  CodeContextPackBuildInput,
  FileLocatorSearchInput,
  RepositoryVerificationBaselineInput,
} from "./types";

export function useProjectRepositorySnapshot(projectId: string | null) {
  return useQuery({
    queryKey: ["repository-snapshot", projectId],
    queryFn: () => fetchProjectRepositorySnapshot(projectId ?? ""),
    enabled: projectId !== null,
  });
}

export function useRefreshProjectRepositorySnapshot(projectId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      if (!projectId) {
        throw new Error("当前没有可刷新的项目仓库。");
      }

      return refreshProjectRepositorySnapshot(projectId);
    },
    onSuccess: async (snapshot) => {
      queryClient.setQueryData(["repository-snapshot", snapshot.project_id], snapshot);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["project-detail", snapshot.project_id] }),
        queryClient.invalidateQueries({ queryKey: ["repository-snapshot", snapshot.project_id] }),
      ]);
    },
  });
}

export function useProjectChangeSession(projectId: string | null) {
  return useQuery({
    queryKey: ["change-session", projectId],
    queryFn: () => fetchProjectChangeSession(projectId ?? ""),
    enabled: projectId !== null,
    retry: false,
  });
}

export function useCaptureProjectChangeSession(projectId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      if (!projectId) {
        throw new Error("当前没有可记录变更会话的项目仓库。");
      }

      return captureProjectChangeSession(projectId);
    },
    onSuccess: async (changeSession) => {
      queryClient.setQueryData(
        ["change-session", changeSession.project_id],
        changeSession,
      );
      await queryClient.invalidateQueries({
        queryKey: ["change-session", changeSession.project_id],
      });
    },
  });
}

export function useProjectRepositoryVerificationBaseline(projectId: string | null) {
  return useQuery({
    queryKey: ["repository-verification-baseline", projectId],
    queryFn: () => fetchProjectRepositoryVerificationBaseline(projectId ?? ""),
    enabled: projectId !== null,
  });
}

export function useReplaceProjectRepositoryVerificationBaseline(
  projectId: string | null,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: RepositoryVerificationBaselineInput) => {
      if (!projectId) {
        throw new Error("当前没有可配置验证基线的项目仓库。");
      }

      return replaceProjectRepositoryVerificationBaseline({
        projectId,
        payload,
      });
    },
    onSuccess: async (baseline) => {
      queryClient.setQueryData(
        ["repository-verification-baseline", baseline.project_id],
        baseline,
      );
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["repository-verification-baseline", baseline.project_id],
        }),
        queryClient.invalidateQueries({
          queryKey: ["project-change-plans"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["project-change-batches", baseline.project_id],
        }),
      ]);
    },
  });
}

export function useProjectFileLocatorSearch(projectId: string | null) {
  return useMutation({
    mutationFn: async (input: FileLocatorSearchInput) => {
      if (!projectId) {
        throw new Error("当前没有可定位文件的项目仓库。");
      }

      return searchProjectRepositoryFiles(projectId, input);
    },
  });
}

export function useBuildProjectCodeContextPack(projectId: string | null) {
  return useMutation({
    mutationFn: async (input: CodeContextPackBuildInput) => {
      if (!projectId) {
        throw new Error("当前没有可生成上下文包的项目仓库。");
      }

      return buildProjectCodeContextPack(projectId, input);
    },
  });
}

export function useProjectChangeBatches(projectId: string | null) {
  return useQuery({
    queryKey: ["project-change-batches", projectId],
    queryFn: () => fetchProjectChangeBatches(projectId ?? ""),
    enabled: projectId !== null,
  });
}

export function useChangeBatchDetail(changeBatchId: string | null) {
  return useQuery({
    queryKey: ["change-batch-detail", changeBatchId],
    queryFn: () => fetchChangeBatchDetail(changeBatchId ?? ""),
    enabled: changeBatchId !== null,
  });
}

export function useCreateProjectChangeBatch(projectId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: {
      title?: string | null;
      change_plan_ids: string[];
    }) => {
      if (!projectId) {
        throw new Error("当前没有可创建变更批次的项目仓库。");
      }

      return createProjectChangeBatch({
        projectId,
        payload,
      });
    },
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["project-change-batches", result.project_id],
        }),
        queryClient.invalidateQueries({ queryKey: ["change-batch-detail"] }),
        queryClient.invalidateQueries({ queryKey: ["project-detail", result.project_id] }),
      ]);
      queryClient.setQueryData(["change-batch-detail", result.id], result);
    },
  });
}

export function useRunChangeBatchPreflight(
  projectId: string | null,
  changeBatchId: string | null,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload?: ChangeBatchPreflightInput) => {
      if (!changeBatchId) {
        throw new Error("当前没有可执行预检的变更批次。");
      }

      return runChangeBatchPreflight({
        changeBatchId,
        payload,
      });
    },
    onSuccess: async (result) => {
      queryClient.setQueryData(["change-batch-detail", result.id], result);
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["project-change-batches", result.project_id],
        }),
        queryClient.invalidateQueries({ queryKey: ["change-batch-detail", result.id] }),
        queryClient.invalidateQueries({ queryKey: ["project-detail", result.project_id] }),
        queryClient.invalidateQueries({ queryKey: ["project-timeline", result.project_id] }),
        queryClient.invalidateQueries({
          queryKey: ["approvals", "repository-preflight", result.project_id],
        }),
        ...(projectId
          ? [
              queryClient.invalidateQueries({
                queryKey: ["project-detail", projectId],
              }),
            ]
          : []),
      ]);
    },
  });
}

export function useProjectCommitCandidates(projectId: string | null) {
  return useQuery({
    queryKey: ["project-commit-candidates", projectId],
    queryFn: () => fetchProjectCommitCandidates(projectId ?? ""),
    enabled: projectId !== null,
  });
}

export function useChangeBatchCommitCandidate(changeBatchId: string | null) {
  return useQuery({
    queryKey: ["change-batch-commit-candidate", changeBatchId],
    queryFn: () => fetchChangeBatchCommitCandidate(changeBatchId ?? ""),
    enabled: changeBatchId !== null,
    retry: false,
  });
}

export function useGenerateChangeBatchCommitCandidate(
  projectId: string | null,
  changeBatchId: string | null,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload?: CommitCandidateDraftInput) => {
      if (!changeBatchId) {
        throw new Error("当前没有可生成提交草案的变更批次。");
      }

      return generateChangeBatchCommitCandidate({
        changeBatchId,
        payload,
      });
    },
    onSuccess: async (result) => {
      queryClient.setQueryData(
        ["change-batch-commit-candidate", result.change_batch_id],
        result,
      );
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["project-commit-candidates", result.project_id],
        }),
        queryClient.invalidateQueries({
          queryKey: ["change-batch-commit-candidate", result.change_batch_id],
        }),
        queryClient.invalidateQueries({ queryKey: ["project-detail", result.project_id] }),
        ...(projectId
          ? [
              queryClient.invalidateQueries({
                queryKey: ["project-detail", projectId],
              }),
            ]
          : []),
      ]);
    },
  });
}
