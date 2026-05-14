import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { StatusBadge } from "../../../components/StatusBadge";
import { requestJson } from "../../../lib/http";
import type { BossProjectItem, ProjectDetail } from "../types";

type ProviderSource = "saved_config" | "env" | "none";

type OpenAIProviderSettingsSummary = {
  provider_key: string;
  configured: boolean;
  base_url: string;
  timeout_seconds: number;
  source: ProviderSource;
};

function fetchOpenAIProviderSettings(): Promise<OpenAIProviderSettingsSummary> {
  return requestJson<OpenAIProviderSettingsSummary>("/provider-settings/openai");
}

export function ProjectSettingsEntryPanel(props: {
  project: BossProjectItem | null;
  detail: ProjectDetail | null;
}) {
  const providerSettingsQuery = useQuery({
    queryKey: ["provider-settings", "openai"],
    queryFn: fetchOpenAIProviderSettings,
  });
  const projectId = props.detail?.id ?? props.project?.id ?? null;
  const workspace =
    props.detail?.repository_workspace ?? props.project?.repository_workspace ?? null;
  const providerConfigured = providerSettingsQuery.data?.configured ?? false;

  return (
    <section className="border-l border-[#333333] px-4 py-1">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
            首次配置状态
          </div>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-400">
            OpenAI 连接参数与主仓库绑定已集中到设置页维护。项目详情只展示当前状态，
            配置完成后回到这里继续刷新目录快照、文件定位和变更计划。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <StatusBadge
            label={providerConfigured ? "模型已配置" : "模型待配置"}
            tone={providerConfigured ? "success" : "warning"}
          />
          <StatusBadge
            label={workspace ? "仓库已绑定" : "仓库待绑定"}
            tone={workspace ? "success" : "warning"}
          />
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <SetupEntry
          title="模型配置"
          description={
            providerSettingsQuery.isLoading
              ? "正在读取 OpenAI 配置状态..."
              : providerSettingsQuery.isError
                ? `配置状态读取失败：${providerSettingsQuery.error.message}`
                : providerConfigured
                  ? "OpenAI Key、Base URL 和超时时间已配置，可按需到设置页调整。"
                  : "尚未完成 OpenAI Key 配置，请先到设置页保存模型连接参数。"
          }
          to="/settings#model-config"
          actionLabel="去设置配置"
        />
        <SetupEntry
          title="主仓库绑定"
          description={
            workspace
              ? `已绑定：${workspace.display_name}。如需更换仓库，请到设置页更新。`
              : "当前项目尚未绑定主仓库，请先到设置页选择项目并保存仓库根目录。"
          }
          to={projectId ? `/settings?projectId=${projectId}#repository-binding` : "/settings#repository-binding"}
          actionLabel="去设置绑定"
        />
      </div>
    </section>
  );
}

function SetupEntry(props: {
  title: string;
  description: string;
  to: string;
  actionLabel: string;
}) {
  return (
    <div className="border-l border-[#333333] px-4 py-2">
      <div className="text-sm font-medium text-zinc-100">{props.title}</div>
      <p className="mt-2 text-sm leading-6 text-zinc-500">{props.description}</p>
      <Link
        to={props.to}
        className="mt-3 inline-flex rounded border border-[#4a4a4a] px-4 py-2 text-sm font-medium text-zinc-100 transition hover:border-zinc-500 hover:bg-[#292929]"
      >
        {props.actionLabel}
      </Link>
    </div>
  );
}
