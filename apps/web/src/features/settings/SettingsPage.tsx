import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { StatusBadge } from "../../components/StatusBadge";
import { requestJson } from "../../lib/http";
import { formatDateTime } from "../../lib/format";
import { useBossProjectOverview } from "../projects/hooks";
import { buildProjectOverviewRoute } from "../projects/lib/overviewNavigation";
import type { RepositoryWorkspace } from "../projects/types";
import { PROJECT_STAGE_LABELS } from "../projects/types";

type ProviderSource = "saved_config" | "env" | "none";
type ProviderModelPreset = "openai" | "deepseek" | "custom";
type ProviderType = "openai" | "deepseek" | "openai_compatible";
type TierModelNames = { economy: string; balanced: string; premium: string };

type OpenAIProviderSettingsSummary = {
  provider_key: string;
  configured: boolean;
  masked_api_key?: string | null;
  base_url: string;
  timeout_seconds: number;
  source: ProviderSource;
  detected_provider_type: ProviderType;
  model_preset: ProviderModelPreset;
  model_names: TierModelNames;
};

type OpenAIProviderSettingsUpdateRequest = {
  api_key?: string;
  base_url: string;
  timeout_seconds: number;
  model_preset?: ProviderModelPreset;
  model_names?: TierModelNames;
};

type RepositoryWorkspaceBindRequest = {
  root_path: string;
  display_name?: string | null;
  access_mode: "read_only";
  default_base_branch: string;
  ignore_rule_summary: string[];
};

type RepositoryWorkspaceSettingsSummary = {
  allowed_workspace_roots: string[];
  default_workspace_root: string;
  using_default: boolean;
};

type RepositoryWorkspaceSettingsUpdateRequest = {
  allowed_workspace_roots: string[];
};

const SOURCE_LABELS: Record<ProviderSource, string> = {
  saved_config: "已保存",
  env: "环境变量",
  none: "未配置",
};


const PRESET_MODELS: Record<Exclude<ProviderModelPreset, "custom">, TierModelNames> = {
  deepseek: {
    economy: "deepseek-v4-pro",
    balanced: "deepseek-v4-pro",
    premium: "deepseek-v4-pro",
  },
  openai: {
    economy: "gpt-5.5",
    balanced: "gpt-5.5",
    premium: "gpt-5.5",
  },
};

const PROVIDER_TYPE_LABELS: Record<ProviderType, string> = {
  openai: "OpenAI",
  deepseek: "DeepSeek",
  openai_compatible: "OpenAI-compatible",
};

const PRESET_LABELS: Record<ProviderModelPreset, string> = {
  deepseek: "DeepSeek preset",
  openai: "OpenAI preset",
  custom: "Custom",
};

function fetchOpenAIProviderSettings(): Promise<OpenAIProviderSettingsSummary> {
  return requestJson<OpenAIProviderSettingsSummary>("/provider-settings/openai");
}

function updateOpenAIProviderSettings(
  payload: OpenAIProviderSettingsUpdateRequest,
): Promise<OpenAIProviderSettingsSummary> {
  return requestJson<OpenAIProviderSettingsSummary>("/provider-settings/openai", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

function bindProjectRepository(input: {
  projectId: string;
  payload: RepositoryWorkspaceBindRequest;
}): Promise<RepositoryWorkspace> {
  return requestJson<RepositoryWorkspace>(`/repositories/projects/${input.projectId}`, {
    method: "PUT",
    body: JSON.stringify(input.payload),
  });
}

function fetchRepositoryWorkspaceSettings(): Promise<RepositoryWorkspaceSettingsSummary> {
  return requestJson<RepositoryWorkspaceSettingsSummary>("/repositories/workspace-settings");
}

function updateRepositoryWorkspaceSettings(
  payload: RepositoryWorkspaceSettingsUpdateRequest,
): Promise<RepositoryWorkspaceSettingsSummary> {
  return requestJson<RepositoryWorkspaceSettingsSummary>("/repositories/workspace-settings", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function SettingsPage() {
  return (
    <div className="space-y-7">
      <section className="border-l border-[#333333] px-4 py-1">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
          系统设置
        </div>
        <h2 className="mt-2 text-2xl font-semibold text-zinc-100">
          系统设置
        </h2>
        <p className="mt-3 max-w-4xl text-sm leading-6 text-zinc-400">
          集中管理模型连接、项目仓库绑定和运行环境配置。
        </p>
      </section>

      <div className="grid gap-8 xl:grid-cols-[220px_minmax(0,1fr)]">
        <SettingsSideNav />
        <div className="space-y-7">
          <ModelConfigurationSection />
          <RepositoryWorkspaceSettingsSection />
          <RepositoryBindingSection />
        </div>
      </div>
    </div>
  );
}

function SettingsSideNav() {
  const items = [
    { label: "模型配置", href: "#model-config" },
    { label: "仓库安全边界", href: "#repository-workspace-settings" },
    { label: "仓库绑定", href: "#repository-binding" },
  ];

  return (
    <nav className="hidden xl:block">
      <div className="sticky top-20 space-y-1 border-l border-[#333333] pl-4">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
          设置分组
        </div>
        {items.map((item) => (
          <a
            key={item.href}
            href={item.href}
            className="block text-sm leading-7 text-zinc-400 transition hover:text-zinc-100"
          >
            {item.label}
          </a>
        ))}
      </div>
    </nav>
  );
}

function ModelConfigurationSection() {
  const queryClient = useQueryClient();
  const providerSettingsQuery = useQuery({
    queryKey: ["provider-settings", "openai"],
    queryFn: fetchOpenAIProviderSettings,
  });
  const [secretInput, setSecretInput] = useState("");
  const [baseUrlInput, setBaseUrlInput] = useState("https://api.openai.com/v1");
  const [timeoutSecondsInput, setTimeoutSecondsInput] = useState("30");
  const [selectedPreset, setSelectedPreset] = useState<ProviderModelPreset>("openai");
  const [modelNamesInput, setModelNamesInput] = useState<TierModelNames>(PRESET_MODELS.openai);
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    if (!providerSettingsQuery.data) {
      return;
    }
    setBaseUrlInput(providerSettingsQuery.data.base_url);
    setTimeoutSecondsInput(String(providerSettingsQuery.data.timeout_seconds));
    setSelectedPreset(providerSettingsQuery.data.model_preset);
    setModelNamesInput(providerSettingsQuery.data.model_names);
  }, [providerSettingsQuery.data]);

  const updateMutation = useMutation({
    mutationFn: updateOpenAIProviderSettings,
    onSuccess: async (result) => {
      setSecretInput("");
      setBaseUrlInput(result.base_url);
      setTimeoutSecondsInput(String(result.timeout_seconds));
      setSelectedPreset(result.model_preset);
      setModelNamesInput(result.model_names);
      setFeedback("Provider model settings saved.");
      await queryClient.invalidateQueries({
        queryKey: ["provider-settings", "openai"],
      });
    },
  });

  const summary = providerSettingsQuery.data ?? null;
  const canSubmit = useMemo(() => {
    return (
      !updateMutation.isPending &&
      baseUrlInput.trim().length > 0 &&
      timeoutSecondsInput.trim().length > 0 &&
      Object.values(modelNamesInput).every((value) => value.trim().length > 0)
    );
  }, [baseUrlInput, modelNamesInput, timeoutSecondsInput, updateMutation.isPending]);

  const applyPreset = (preset: Exclude<ProviderModelPreset, "custom">) => {
    setSelectedPreset(preset);
    setModelNamesInput(PRESET_MODELS[preset]);
    if (preset === "deepseek") {
      setBaseUrlInput("https://api.deepseek.com");
    }
    if (preset === "openai") {
      setBaseUrlInput("https://api.openai.com/v1");
    }
  };

  const updateModelNameInput = (tier: keyof TierModelNames, value: string) => {
    setSelectedPreset("custom");
    setModelNamesInput((current) => ({ ...current, [tier]: value }));
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFeedback(null);

    const timeoutSeconds = Number.parseInt(timeoutSecondsInput, 10);
    if (!Number.isFinite(timeoutSeconds) || timeoutSeconds < 1) {
      setFeedback("Timeout seconds must be an integer greater than or equal to 1.");
      return;
    }

    const payload: OpenAIProviderSettingsUpdateRequest = {
      base_url: baseUrlInput.trim(),
      timeout_seconds: timeoutSeconds,
      model_preset: selectedPreset,
    };
    if (selectedPreset === "custom") {
      payload.model_names = {
        economy: modelNamesInput.economy.trim(),
        balanced: modelNamesInput.balanced.trim(),
        premium: modelNamesInput.premium.trim(),
      };
    }
    const enteredSecret = secretInput.trim();
    if (enteredSecret.length > 0) {
      payload.api_key = enteredSecret;
    }

    void updateMutation.mutateAsync(payload);
  };

  return (
    <section id="model-config" className="scroll-mt-24 border-b border-[#333333] pb-7">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
            Provider Model Configuration
          </div>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-400">
            Configure API credentials, base URL, timeout, and the economy / balanced / premium model names used by worker routing.
          </p>
        </div>
        <StatusBadge
          label={summary?.configured ? "configured" : "not configured"}
          tone={summary?.configured ? "success" : "warning"}
        />
      </div>

      {providerSettingsQuery.isLoading ? (
        <p className="mt-4 text-sm leading-6 text-zinc-500">Loading provider model configuration...</p>
      ) : providerSettingsQuery.isError ? (
        <p className="mt-4 text-sm leading-6 text-rose-100">
          Failed to load provider model configuration: {providerSettingsQuery.error.message}
        </p>
      ) : (
        <>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <InfoLine label="Current key" value={formatMaskedKey(summary?.masked_api_key)} />
            <InfoLine label="Source" value={summary ? SOURCE_LABELS[summary.source] : "not configured"} />
            <InfoLine label="Provider type" value={summary ? PROVIDER_TYPE_LABELS[summary.detected_provider_type] : "OpenAI"} />
            <InfoLine label="Model preset" value={summary ? PRESET_LABELS[summary.model_preset] : "OpenAI preset"} />
            <InfoLine label="Timeout" value={`${summary?.timeout_seconds ?? 30} seconds`} />
            <InfoLine label="Tier models" value={formatTierModels(summary?.model_names ?? modelNamesInput)} />
          </div>

          <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
            <div className="flex flex-wrap gap-2">
              <button type="button" className={secondaryButtonClassName} onClick={() => applyPreset("deepseek")}>
                Use DeepSeek preset
              </button>
              <button type="button" className={secondaryButtonClassName} onClick={() => applyPreset("openai")}>
                Use OpenAI preset
              </button>
              <span className="text-sm leading-9 text-zinc-500">Selected: {PRESET_LABELS[selectedPreset]}</span>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <Field label="API key">
                <input
                  type="password"
                  value={secretInput}
                  onChange={(event) => setSecretInput(event.target.value)}
                  placeholder="Leave blank to keep the current key"
                  className={inputClassName}
                />
              </Field>
              <Field label="Timeout seconds">
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={timeoutSecondsInput}
                  onChange={(event) => setTimeoutSecondsInput(event.target.value)}
                  className={inputClassName}
                />
              </Field>
            </div>

            <Field label="Base URL">
              <input
                type="url"
                value={baseUrlInput}
                onChange={(event) => setBaseUrlInput(event.target.value)}
                placeholder="https://api.openai.com/v1"
                className={inputClassName}
              />
            </Field>

            <div className="grid gap-4 md:grid-cols-3">
              <Field label="Economy model">
                <input
                  value={modelNamesInput.economy}
                  onChange={(event) => updateModelNameInput("economy", event.target.value)}
                  placeholder="deepseek-v4-pro"
                  className={inputClassName}
                />
              </Field>
              <Field label="Balanced model">
                <input
                  value={modelNamesInput.balanced}
                  onChange={(event) => updateModelNameInput("balanced", event.target.value)}
                  placeholder="deepseek-v4-pro"
                  className={inputClassName}
                />
              </Field>
              <Field label="Premium model">
                <input
                  value={modelNamesInput.premium}
                  onChange={(event) => updateModelNameInput("premium", event.target.value)}
                  placeholder="deepseek-v4-pro"
                  className={inputClassName}
                />
              </Field>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button type="submit" disabled={!canSubmit} className={buttonClassName}>
                {updateMutation.isPending ? "Saving..." : "Save model configuration"}
              </button>
              {feedback ? (
                <span className="text-sm leading-6 text-zinc-400">{feedback}</span>
              ) : null}
              {updateMutation.isError ? (
                <span className="text-sm leading-6 text-rose-100">
                  Save failed: {updateMutation.error.message}
                </span>
              ) : null}
            </div>
          </form>
        </>
      )}
    </section>
  );
}

function RepositoryWorkspaceSettingsSection() {
  const queryClient = useQueryClient();
  const workspaceSettingsQuery = useQuery({
    queryKey: ["repository-workspace-settings"],
    queryFn: fetchRepositoryWorkspaceSettings,
  });
  const [rootsInput, setRootsInput] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    if (!workspaceSettingsQuery.data) {
      return;
    }
    setRootsInput(workspaceSettingsQuery.data.allowed_workspace_roots.join("\n"));
  }, [workspaceSettingsQuery.data]);

  const updateMutation = useMutation({
    mutationFn: updateRepositoryWorkspaceSettings,
    onSuccess: async (result) => {
      setRootsInput(result.allowed_workspace_roots.join("\n"));
      setFeedback("仓库安全边界已保存，新的允许根目录已立即生效。");
      await queryClient.invalidateQueries({
        queryKey: ["repository-workspace-settings"],
      });
    },
  });

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFeedback(null);
    void updateMutation.mutateAsync({
      allowed_workspace_roots: parseLines(rootsInput),
    });
  };

  const summary = workspaceSettingsQuery.data ?? null;

  return (
    <section
      id="repository-workspace-settings"
      className="scroll-mt-24 border-b border-[#333333] pb-7"
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
            仓库安全边界
          </div>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-400">
            维护允许工作区根目录列表。项目绑定时，主仓库根目录必须位于其中任一根目录下；未保存用户配置时继续使用默认 REPOSITORY_WORKSPACE_ROOT_DIR。
          </p>
        </div>
        <StatusBadge
          label={summary?.using_default ? "使用默认边界" : "用户配置已生效"}
          tone={summary?.using_default ? "warning" : "success"}
        />
      </div>

      {workspaceSettingsQuery.isLoading ? (
        <p className="mt-4 text-sm leading-6 text-zinc-500">正在加载仓库安全边界...</p>
      ) : workspaceSettingsQuery.isError ? (
        <p className="mt-4 text-sm leading-6 text-rose-100">
          仓库安全边界加载失败：{workspaceSettingsQuery.error.message}
        </p>
      ) : (
        <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
          <Field label="允许工作区根目录列表">
            <textarea
              rows={5}
              value={rootsInput}
              onChange={(event) => setRootsInput(event.target.value)}
              placeholder={"每行一个本地目录，例如：\nE:\\test\nD:\\workspace"}
              className={inputClassName}
            />
          </Field>

          <div className="grid gap-3 md:grid-cols-2">
            <InfoLine label="默认兜底根目录" value={summary?.default_workspace_root ?? "—"} />
            <InfoLine
              label="当前生效根目录"
              value={(summary?.allowed_workspace_roots ?? []).join("；") || "—"}
            />
          </div>

          <p className="text-sm leading-6 text-zinc-500">
            删除某一行即可移除对应根目录；留空保存后将回到默认兜底行为。系统仍会拒绝非 Git 目录、运行时数据目录、临时目录和未在边界内的路径。
          </p>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={updateMutation.isPending}
              className={buttonClassName}
            >
              {updateMutation.isPending ? "保存中..." : "保存仓库安全边界"}
            </button>
            {feedback ? (
              <span className="text-sm leading-6 text-zinc-400">{feedback}</span>
            ) : null}
            {updateMutation.isError ? (
              <span className="text-sm leading-6 text-rose-100">
                保存失败：{updateMutation.error.message}
              </span>
            ) : null}
          </div>
        </form>
      )}
    </section>
  );
}

function RepositoryBindingSection() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const overviewQuery = useBossProjectOverview({ enablePolling: false });
  const projects = overviewQuery.data?.projects ?? [];
  const requestedProjectId = searchParams.get("projectId") ?? "";
  const [selectedProjectId, setSelectedProjectId] = useState(requestedProjectId);
  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? null;
  const hasInvalidRequestedProject =
    requestedProjectId.length > 0 &&
    projects.length > 0 &&
    !projects.some((project) => project.id === requestedProjectId);
  const [rootPathInput, setRootPathInput] = useState("");
  const [displayNameInput, setDisplayNameInput] = useState("");
  const [baseBranchInput, setBaseBranchInput] = useState("main");
  const [ignoreRulesInput, setIgnoreRulesInput] = useState(".git\nnode_modules\ndist\nbuild");
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    if (projects.length === 0) {
      return;
    }

    const selectedProjectExists = projects.some(
      (project) => project.id === selectedProjectId,
    );
    if (selectedProjectExists) {
      return;
    }

    const fallbackProject =
      projects.find((project) => project.repository_workspace === null) ?? projects[0];
    setSelectedProjectId(fallbackProject.id);

    const nextSearchParams = new URLSearchParams(searchParams);
    nextSearchParams.set("projectId", fallbackProject.id);
    setSearchParams(nextSearchParams, { replace: true });
  }, [projects, searchParams, selectedProjectId, setSearchParams]);

  useEffect(() => {
    if (!selectedProject) {
      return;
    }

    const workspace = selectedProject.repository_workspace;
    setRootPathInput(workspace?.root_path ?? "");
    setDisplayNameInput(workspace?.display_name ?? selectedProject.name);
    setBaseBranchInput(workspace?.default_base_branch ?? "main");
    setIgnoreRulesInput(
      (workspace?.ignore_rule_summary.length
        ? workspace.ignore_rule_summary
        : [".git", "node_modules", "dist", "build"]
      ).join("\n"),
    );
  }, [selectedProject]);

  const bindMutation = useMutation({
    mutationFn: bindProjectRepository,
    onSuccess: async (workspace) => {
      setFeedback("主仓库绑定已保存，正在回到仓库工作区。");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["boss-project-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["project-detail"] }),
        queryClient.invalidateQueries({
          queryKey: ["project-detail", workspace.project_id],
        }),
      ]);
      navigate(
        buildProjectOverviewRoute({
          projectId: workspace.project_id,
          view: "repository-workspace",
        }),
      );
    },
  });

  const canSubmit = Boolean(
    selectedProject && rootPathInput.trim() && baseBranchInput.trim() && !bindMutation.isPending,
  );

  const handleProjectChange = (projectId: string) => {
    setSelectedProjectId(projectId);
    const nextSearchParams = new URLSearchParams(searchParams);
    if (projectId) {
      nextSearchParams.set("projectId", projectId);
    } else {
      nextSearchParams.delete("projectId");
    }
    setSearchParams(nextSearchParams, { replace: true });
    setFeedback(null);
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFeedback(null);
    if (!selectedProject) {
      return;
    }

    void bindMutation.mutateAsync({
      projectId: selectedProject.id,
      payload: {
        root_path: rootPathInput.trim(),
        display_name: displayNameInput.trim() || null,
        access_mode: "read_only",
        default_base_branch: baseBranchInput.trim(),
        ignore_rule_summary: parseLines(ignoreRulesInput),
      },
    });
  };

  return (
    <section id="repository-binding" className="scroll-mt-24 border-b border-[#333333] pb-7">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
            项目仓库绑定
          </div>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-400">
            在这里为项目绑定主仓库根目录。绑定后，可以进入仓库工作区查看文件、定位代码和生成变更计划。
          </p>
        </div>
        <StatusBadge
          label={selectedProject?.repository_workspace ? "已绑定" : "待绑定"}
          tone={selectedProject?.repository_workspace ? "success" : "warning"}
        />
      </div>

      {hasInvalidRequestedProject ? (
        <div className="mt-4 border-l border-amber-500/50 px-4 py-3 text-sm leading-6 text-amber-100">
          当前项目不可用，已切换到可配置项目；也可以在下方重新选择。
        </div>
      ) : null}

      {overviewQuery.isLoading ? (
        <p className="mt-4 text-sm leading-6 text-zinc-500">正在加载项目列表...</p>
      ) : overviewQuery.isError ? (
        <p className="mt-4 text-sm leading-6 text-rose-100">
          项目列表加载失败：{overviewQuery.error.message}
        </p>
      ) : (
        <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
          <Field label="选择项目">
            <select
              value={selectedProjectId}
              onChange={(event) => handleProjectChange(event.target.value)}
              className={inputClassName}
            >
              <option value="">请选择项目</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </Field>

          {selectedProject ? (
            <>
              <div className="grid gap-3 md:grid-cols-3">
                <InfoLine
                  label="当前状态"
                  value={selectedProject.repository_workspace ? "主仓库已绑定" : "尚未绑定主仓库"}
                />
                <InfoLine
                  label="项目阶段"
                  value={PROJECT_STAGE_LABELS[selectedProject.stage] ?? "未识别阶段"}
                />
                <InfoLine
                  label="最近更新"
                  value={formatDateTime(selectedProject.updated_at)}
                />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <Field label="仓库显示名">
                  <input
                    value={displayNameInput}
                    onChange={(event) => setDisplayNameInput(event.target.value)}
                    className={inputClassName}
                  />
                </Field>
                <Field label="默认基线分支">
                  <input
                    value={baseBranchInput}
                    onChange={(event) => setBaseBranchInput(event.target.value)}
                    className={inputClassName}
                  />
                </Field>
              </div>

              <Field label="主仓库根目录">
                <input
                  value={rootPathInput}
                  onChange={(event) => setRootPathInput(event.target.value)}
                  placeholder="填写已允许根目录下的本地 Git 仓库路径，例如 E:\test\my-repo"
                  className={inputClassName}
                />
              </Field>

              <Field label="忽略目录摘要">
                <textarea
                  rows={4}
                  value={ignoreRulesInput}
                  onChange={(event) => setIgnoreRulesInput(event.target.value)}
                  className={inputClassName}
                />
              </Field>

              {selectedProject.repository_workspace ? (
                <div className="border-l border-[#333333] px-4 py-3 text-sm leading-6 text-zinc-400">
                  当前允许工作区根：
                  <span className="break-all text-zinc-100">
                    {selectedProject.repository_workspace.allowed_workspace_root}
                  </span>
                </div>
              ) : null}

              <div className="flex flex-wrap items-center gap-3">
                <button type="submit" disabled={!canSubmit} className={buttonClassName}>
                  {bindMutation.isPending ? "保存中..." : "保存主仓库绑定"}
                </button>
                <Link
                  to={buildProjectOverviewRoute({
                    projectId: selectedProject.id,
                    view: "repository-workspace",
                  })}
                  className="rounded border border-[#4a4a4a] px-4 py-2 text-sm font-medium text-zinc-100 transition hover:border-zinc-500 hover:bg-[#292929]"
                >
                  回到仓库工作区
                </Link>
                {feedback ? (
                  <span className="text-sm leading-6 text-zinc-400">{feedback}</span>
                ) : null}
                {bindMutation.isError ? (
                  <span className="text-sm leading-6 text-rose-100">
                    {buildRepositoryBindingErrorMessage(bindMutation.error, rootPathInput)}
                  </span>
                ) : null}
              </div>
            </>
          ) : (
            <div className="space-y-3">
              <p className="text-sm leading-6 text-zinc-500">
                当前还没有可配置的项目。
              </p>
              <Link
                to="/projects"
                className="inline-block rounded border border-[#4a4a4a] px-4 py-2 text-sm font-medium text-zinc-100 transition hover:border-zinc-500 hover:bg-[#292929]"
              >
                去项目中心
              </Link>
            </div>
          )}
        </form>
      )}
    </section>
  );
}

function Field(props: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
        {props.label}
      </div>
      <div className="mt-2">{props.children}</div>
    </label>
  );
}

function InfoLine(props: { label: string; value: string }) {
  return (
    <div className="border-l border-[#333333] px-4 py-2">
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
        {props.label}
      </div>
      <div className="mt-2 break-all text-sm leading-6 text-zinc-100">
        {props.value}
      </div>
    </div>
  );
}

function parseLines(value: string) {
  return Array.from(
    new Set(
      value
        .split(/[\n,]/)
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  );
}

function buildRepositoryBindingErrorMessage(error: Error, rootPathInput: string) {
  const message = error.message;
  if (message.includes("exceeds the configured allowed workspace root")) {
    const suggestedRoot = inferSuggestedWorkspaceRoot(rootPathInput);
    return suggestedRoot
      ? `保存失败：仓库路径不在允许的工作区根目录内。请先在仓库安全边界中添加 ${suggestedRoot}，或把仓库移动到已允许的根目录下。`
      : "保存失败：仓库路径不在允许的工作区根目录内。请先在仓库安全边界中添加该仓库的上级工作区根目录，或把仓库移动到已允许的根目录下。";
  }
  if (message.includes("does not exist")) {
    return "保存失败：这个仓库路径不存在。请确认路径拼写正确，并且该目录已经在本机创建。";
  }
  if (message.includes("must be a directory")) {
    return "保存失败：填写的路径不是目录。请选择项目主仓库所在的文件夹。";
  }
  if (
    message.includes("does not look like a Git repository") ||
    message.includes("must point to one local Git repository root")
  ) {
    return "保存失败：这个目录不像 Git 仓库。请确认目录内存在 .git，或先完成仓库初始化。";
  }
  return `保存失败：${message}`;
}

function inferSuggestedWorkspaceRoot(rootPathInput: string) {
  const normalizedInput = rootPathInput.trim().replace(/\//g, "\\");
  if (!normalizedInput) {
    return "";
  }

  const windowsMatch = normalizedInput.match(/^([A-Za-z]:\\[^\\]+)(?:\\.*)?$/);
  if (windowsMatch) {
    return windowsMatch[1];
  }

  const posixParts = rootPathInput.trim().split("/").filter(Boolean);
  if (rootPathInput.trim().startsWith("/") && posixParts.length >= 2) {
    return `/${posixParts.slice(0, 2).join("/")}`;
  }

  return rootPathInput.trim();
}

function formatMaskedKey(value: unknown) {
  return typeof value === "string" && value.length > 0 ? value : "未配置";
}

function formatTierModels(modelNames: TierModelNames) {
  return `economy ${modelNames.economy} / balanced ${modelNames.balanced} / premium ${modelNames.premium}`;
}

const inputClassName =
  "w-full border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm leading-6 text-zinc-100 outline-none transition focus:border-zinc-500";

const buttonClassName =
  "rounded border border-[#4a4a4a] bg-transparent px-4 py-2 text-sm font-medium text-zinc-100 transition hover:border-zinc-500 hover:bg-[#292929] disabled:cursor-not-allowed disabled:border-[#333333] disabled:text-zinc-600";

const secondaryButtonClassName =
  "rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm font-medium text-zinc-200 transition hover:border-zinc-500 hover:bg-[#292929]";
