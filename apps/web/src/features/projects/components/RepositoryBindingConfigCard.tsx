import { useState } from "react";

import { StatusBadge } from "../../../components/StatusBadge";
import {
  useProjectDirectorRepositoryBindingConfig,
  useReviewProjectDirectorRepositoryBindingConfigMutation,
} from "../../project-director/hooks";
import type {
  ProjectDirectorRepositoryBindingConfig,
  ProjectDirectorRepositoryBindingConfigStatus,
} from "../../project-director/types";

type RepositoryBindingConfigCardProps = {
  projectId: string | null;
};

const STATUS_LABELS: Record<ProjectDirectorRepositoryBindingConfigStatus, string> = {
  pending_confirmation: "待确认",
  confirmed: "仓库绑定建议已确认",
  rejected: "仓库绑定建议已拒绝",
};

const STATUS_TONES: Record<
  ProjectDirectorRepositoryBindingConfigStatus,
  "info" | "success" | "warning"
> = {
  pending_confirmation: "warning",
  confirmed: "success",
  rejected: "info",
};

const BINDING_TYPE_LABELS: Record<string, string> = {
  review_only: "仅审阅",
  suggested: "建议绑定",
  not_bound: "未绑定",
};

const BINDING_MODE_LABELS: Record<string, string> = {
  suggested: "建议",
  not_bound: "未绑定",
  review_only: "仅审阅",
};

export function RepositoryBindingConfigCard({
  projectId,
}: RepositoryBindingConfigCardProps) {
  const [feedback, setFeedback] = useState<string | null>(null);
  const query = useProjectDirectorRepositoryBindingConfig(projectId);
  const reviewMutation = useReviewProjectDirectorRepositoryBindingConfigMutation();

  if (!projectId) {
    return null;
  }

  if (query.isError) {
    return (
      <section className="rounded-lg border border-amber-500/25 bg-amber-500/5 p-4 text-sm text-amber-100">
        AI 主管仓库绑定建议暂时读取失败，不影响项目详情主页面。
      </section>
    );
  }

  const config = query.data?.config ?? null;
  if (!config) {
    return null;
  }

  const isPending = config.status === "pending_confirmation";
  const isReviewing = reviewMutation.isPending;

  const review = async (action: "confirm" | "reject") => {
    setFeedback(null);
    try {
      const result = await reviewMutation.mutateAsync({
        projectId,
        action,
      });
      setFeedback(result.next_action);
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "操作失败，请稍后重试。");
    }
  };

  return (
    <section
      data-testid="project-director-repository-binding-config-card"
      className="rounded-lg border border-emerald-500/25 bg-emerald-500/5 p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-semibold text-emerald-100">
              AI 主管仓库绑定建议
            </h4>
            <StatusBadge
              label={STATUS_LABELS[config.status]}
              tone={STATUS_TONES[config.status]}
            />
          </div>
          <p className="mt-1 text-xs leading-5 text-emerald-100/75">
            这只是项目级仓库绑定配置建议；未创建真实仓库绑定，未写入仓库，
            未调用 git-commit / apply-local / planning/apply。
          </p>
        </div>
        {isPending ? (
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void review("confirm")}
              disabled={isReviewing}
              className="rounded border border-emerald-300 bg-emerald-100 px-3 py-1.5 text-xs font-semibold text-emerald-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              确认仓库绑定建议
            </button>
            <button
              type="button"
              onClick={() => void review("reject")}
              disabled={isReviewing}
              className="rounded border border-[#333333] bg-[#151515] px-3 py-1.5 text-xs font-semibold text-zinc-200 transition hover:border-zinc-500 disabled:cursor-not-allowed disabled:opacity-60"
            >
              拒绝仓库绑定建议
            </button>
          </div>
        ) : null}
      </div>

      <ConfigMeta config={config} />
      <RepositoryBindingList config={config} />
      <BoundaryWarnings warnings={config.warnings} />

      {query.data?.next_action || feedback ? (
        <p className="mt-3 rounded border border-emerald-500/20 bg-[#111111]/70 px-3 py-2 text-xs leading-5 text-emerald-100/80">
          {feedback ?? query.data?.next_action}
        </p>
      ) : null}
    </section>
  );
}

function ConfigMeta({ config }: { config: ProjectDirectorRepositoryBindingConfig }) {
  return (
    <div className="mt-3 grid gap-2 sm:grid-cols-2">
      <MetaBlock label="当前状态" value={STATUS_LABELS[config.status]} />
      <MetaBlock label="来源草稿版本 ID" value={config.plan_version_id} mono />
    </div>
  );
}

function MetaBlock({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded border border-[#333333] bg-[#111111]/60 px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-600">
        {label}
      </div>
      <div className={`mt-1 break-all text-xs text-zinc-300 ${mono ? "font-mono" : ""}`}>
        {value}
      </div>
    </div>
  );
}

function RepositoryBindingList({
  config,
}: {
  config: ProjectDirectorRepositoryBindingConfig;
}) {
  return (
    <div className="mt-3 space-y-2">
      {config.repository_bindings.map((binding) => {
        const bindingTypeLabel =
          BINDING_TYPE_LABELS[binding.binding_type] ?? binding.binding_type;
        const bindingModeLabel =
          BINDING_MODE_LABELS[binding.binding_mode] ?? binding.binding_mode;

        return (
          <div
            key={`${binding.target}-${binding.branch}-${binding.usage}`}
            className="rounded border border-[#333333] bg-[#111111]/60 px-3 py-2"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-zinc-100">
                {binding.target}
              </span>
              <span className="rounded border border-[#333333] px-2 py-0.5 font-mono text-[11px] text-zinc-400">
                {binding.branch || "未指定分支"}
              </span>
              <span className="rounded border border-emerald-500/20 px-2 py-0.5 text-[11px] text-emerald-100/75">
                {bindingTypeLabel}
              </span>
              <span className="rounded border border-emerald-500/20 px-2 py-0.5 text-[11px] text-emerald-100/75">
                {bindingModeLabel}
              </span>
            </div>
            <dl className="mt-2 grid gap-2 text-xs leading-5 sm:grid-cols-2">
              <Field label="用途" value={binding.usage} />
              <Field label="安全说明" value={binding.safety_note} />
              <Field
                label="关注路径"
                value={
                  binding.focus_paths.length > 0
                    ? binding.focus_paths.join("、")
                    : "未指定"
                }
              />
            </dl>
          </div>
        );
      })}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[11px] text-zinc-500">{label}</dt>
      <dd className="mt-1 break-words text-zinc-300">{value}</dd>
    </div>
  );
}

function BoundaryWarnings({ warnings }: { warnings: string[] }) {
  const items =
    warnings.length > 0
      ? warnings
      : [
          "这只是项目级仓库绑定配置建议。",
          "未创建真实仓库绑定。",
          "未写入仓库。",
          "未调用 git-commit / apply-local / planning/apply。",
        ];

  return (
    <div className="mt-3 rounded border border-emerald-500/20 bg-[#111111]/70 px-3 py-2">
      <div className="text-xs font-medium text-emerald-100">边界提示</div>
      <ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-5 text-emerald-100/80">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
