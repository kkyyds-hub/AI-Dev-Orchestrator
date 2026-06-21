import { useMutation, useQueryClient } from "@tanstack/react-query";
import { GitBranch, Link2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useProjectDirectorRepositoryBindingConfig } from "../../../features/project-director/hooks";
import { bindProjectRepo } from "../../../features/settings/api";
import type { WorkbenchActionToastStatus } from "./WorkbenchActionToast";

type WorkbenchRepositoryBindingPanelProps = {
  projectId: string | null;
  projectName: string;
  onActionFeedback: (message: string, status?: WorkbenchActionToastStatus) => void;
};

export function WorkbenchRepositoryBindingPanel({
  projectId,
  projectName,
  onActionFeedback,
}: WorkbenchRepositoryBindingPanelProps) {
  const queryClient = useQueryClient();
  const [repositoryPath, setRepositoryPath] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [baseBranch, setBaseBranch] = useState("main");
  const repositoryConfigQuery = useProjectDirectorRepositoryBindingConfig(projectId);
  const suggestedBinding =
    repositoryConfigQuery.data?.config?.repository_bindings[0] ?? null;
  const suggestedTarget = suggestedBinding?.target ?? "";
  const canSubmit = Boolean(projectId) && repositoryPath.trim().length > 0;

  const bindingHint = useMemo(() => {
    if (!projectId) {
      return "先创建或选择正式项目，再绑定仓库。";
    }
    if (repositoryConfigQuery.isLoading) {
      return "正在读取 AI 主管建议的仓库绑定。";
    }
    if (repositoryConfigQuery.isError) {
      return "暂时没有读取到仓库建议，可先手动填写只读仓库路径。";
    }
    if (suggestedBinding) {
      return `AI 主管建议：${suggestedBinding.binding_type} · ${suggestedBinding.binding_mode}`;
    }
    return "暂无仓库建议，可先手动填写只读仓库路径。";
  }, [
    projectId,
    repositoryConfigQuery.isError,
    repositoryConfigQuery.isLoading,
    suggestedBinding,
  ]);

  const bindMutation = useMutation({
    mutationFn: async () => {
      if (!projectId) {
        throw new Error("当前没有可绑定仓库的正式项目。");
      }

      return bindProjectRepo({
        projectId,
        payload: {
          root_path: repositoryPath.trim(),
          display_name: displayName.trim() || null,
          access_mode: "read_only",
          default_base_branch: baseBranch.trim() || "main",
          ignore_rule_summary: [],
        },
      });
    },
    onSuccess: async (workspace) => {
      onActionFeedback("仓库绑定已更新", "done");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["project-detail", workspace.project_id] }),
        queryClient.invalidateQueries({
          queryKey: ["project-director", "repository-binding-config", workspace.project_id],
        }),
        queryClient.invalidateQueries({ queryKey: ["repository-workspace-settings"] }),
      ]);
    },
    onError: (error) => {
      onActionFeedback(
        error instanceof Error ? `仓库绑定失败：${error.message}` : "仓库绑定失败",
        "failed",
      );
    },
  });

  const handleUseSuggestion = () => {
    if (!suggestedTarget) {
      return;
    }
    setRepositoryPath(suggestedTarget);
    if (!displayName.trim()) {
      setDisplayName(projectName);
    }
    if (suggestedBinding?.branch) {
      setBaseBranch(suggestedBinding.branch);
    }
  };

  const handleSubmit = () => {
    if (!canSubmit || bindMutation.isPending) {
      return;
    }

    onActionFeedback("仓库绑定请求已排队", "queued");
    window.setTimeout(() => onActionFeedback("仓库绑定处理中", "processing"), 200);
    bindMutation.mutate();
  };

  return (
    <section
      data-testid="workbench-repository-binding"
      className="border border-[#242424] bg-[#0B0B0B] p-4"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.12em] text-[#8A8A8A]">
            <GitBranch className="h-4 w-4" />
            仓库绑定
          </div>
          <h2 className="mt-2 text-base font-semibold text-white">只读仓库工作区</h2>
          <p className="mt-1 text-xs leading-5 text-[#8A8A8A]">{bindingHint}</p>
        </div>
        <Link
          to={projectId ? `/projects/${encodeURIComponent(projectId)}/repository` : "/execution?tab=repository"}
          className="shrink-0 rounded-full border border-[#333333] px-2.5 py-1 text-xs text-[#C7C7C7] transition hover:border-[#5A5A5A] hover:text-white"
        >
          仓库页
        </Link>
      </div>

      {suggestedTarget ? (
        <button
          type="button"
          onClick={handleUseSuggestion}
          className="mt-3 flex w-full items-start gap-2 border border-[#242424] bg-[#111111] px-3 py-2 text-left text-xs text-[#C7C7C7] transition hover:border-[#3A3A3A] hover:text-white"
        >
          <Link2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span className="min-w-0">
            <span className="block">使用主管建议路径</span>
            <span className="mt-1 block truncate text-[#8A8A8A]">{suggestedTarget}</span>
          </span>
        </button>
      ) : null}

      <div className="mt-4 space-y-3">
        <label className="block">
          <span className="mb-1.5 block text-xs text-[#8A8A8A]">仓库路径</span>
          <input
            data-testid="workbench-repository-path"
            value={repositoryPath}
            onChange={(event) => setRepositoryPath(event.target.value)}
            placeholder="/Users/kk/project"
            className="h-10 w-full border border-[#2A2A2A] bg-[#111111] px-3 text-sm text-white outline-none placeholder:text-[#5F5F5F] focus:border-[#5A5A5A]"
          />
        </label>

        <div className="grid gap-3 sm:grid-cols-[1fr_120px]">
          <label className="block">
            <span className="mb-1.5 block text-xs text-[#8A8A8A]">显示名称</span>
            <input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder={projectName}
              className="h-10 w-full border border-[#2A2A2A] bg-[#111111] px-3 text-sm text-white outline-none placeholder:text-[#5F5F5F] focus:border-[#5A5A5A]"
            />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-xs text-[#8A8A8A]">基础分支</span>
            <input
              value={baseBranch}
              onChange={(event) => setBaseBranch(event.target.value)}
              className="h-10 w-full border border-[#2A2A2A] bg-[#111111] px-3 text-sm text-white outline-none placeholder:text-[#5F5F5F] focus:border-[#5A5A5A]"
            />
          </label>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-[#1F1F1F] pt-3">
        <p className="text-xs leading-5 text-[#8A8A8A]">
          当前仅绑定只读工作区，不提交、不推送、不发布。
        </p>
        <button
          type="button"
          data-testid="workbench-bind-repository"
          disabled={!canSubmit || bindMutation.isPending}
          onClick={handleSubmit}
          className="rounded-full border border-white bg-white px-3 py-1.5 text-xs font-medium text-black transition hover:bg-[#EDEDED] disabled:cursor-not-allowed disabled:border-[#333333] disabled:bg-[#1A1A1A] disabled:text-[#5F5F5F]"
        >
          {bindMutation.isPending ? "处理中..." : "绑定仓库"}
        </button>
      </div>
    </section>
  );
}
