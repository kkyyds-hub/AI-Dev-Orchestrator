import { useState } from "react";

import { StatusBadge } from "../../../components/StatusBadge";
import {
  useProjectDirectorSkillBindingConfig,
  useReviewProjectDirectorSkillBindingConfigMutation,
} from "../../project-director/hooks";
import type {
  ProjectDirectorSkillBindingConfig,
  ProjectDirectorSkillBindingConfigStatus,
} from "../../project-director/types";

type SkillBindingConfigCardProps = {
  projectId: string | null;
};

const STATUS_LABELS: Record<ProjectDirectorSkillBindingConfigStatus, string> = {
  pending_confirmation: "待确认",
  confirmed: "Skill 绑定已确认",
  rejected: "Skill 绑定已拒绝",
};

const STATUS_TONES: Record<
  ProjectDirectorSkillBindingConfigStatus,
  "info" | "success" | "warning"
> = {
  pending_confirmation: "warning",
  confirmed: "success",
  rejected: "info",
};

const BINDING_MODE_LABELS: Record<string, string> = {
  suggested: "建议绑定",
  not_bound: "未绑定",
};

export function SkillBindingConfigCard({ projectId }: SkillBindingConfigCardProps) {
  const [feedback, setFeedback] = useState<string | null>(null);
  const query = useProjectDirectorSkillBindingConfig(projectId);
  const reviewMutation = useReviewProjectDirectorSkillBindingConfigMutation();

  if (!projectId) {
    return null;
  }

  if (query.isError) {
    return (
      <section className="rounded-lg border border-amber-500/25 bg-amber-500/5 p-4 text-sm text-amber-100">
        AI 主管 Skill 绑定建议暂时读取失败，不影响项目详情主页面。
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
      data-testid="project-director-skill-binding-config-card"
      className="rounded-lg border border-sky-500/25 bg-sky-500/5 p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-semibold text-sky-100">
              AI 主管 Skill 绑定建议
            </h4>
            <StatusBadge
              label={STATUS_LABELS[config.status]}
              tone={STATUS_TONES[config.status]}
            />
          </div>
          <p className="mt-1 text-xs leading-5 text-sky-100/75">
            这是项目级 Skill 绑定配置建议；未创建真实 Skill 绑定，未启用 Skill，未启动 Worker。
          </p>
        </div>
        {isPending ? (
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void review("confirm")}
              disabled={isReviewing}
              className="rounded border border-sky-300 bg-sky-100 px-3 py-1.5 text-xs font-semibold text-sky-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              确认 Skill 绑定
            </button>
            <button
              type="button"
              onClick={() => void review("reject")}
              disabled={isReviewing}
              className="rounded border border-[#333333] bg-[#151515] px-3 py-1.5 text-xs font-semibold text-zinc-200 transition hover:border-zinc-500 disabled:cursor-not-allowed disabled:opacity-60"
            >
              拒绝 Skill 绑定
            </button>
          </div>
        ) : null}
      </div>

      <ConfigMeta config={config} />
      <SkillBindingList config={config} />
      <BoundaryWarnings warnings={config.warnings} />

      {(query.data?.next_action || feedback) ? (
        <p className="mt-3 rounded border border-sky-500/20 bg-[#111111]/70 px-3 py-2 text-xs leading-5 text-sky-100/80">
          {feedback ?? query.data?.next_action}
        </p>
      ) : null}
    </section>
  );
}

function ConfigMeta({ config }: { config: ProjectDirectorSkillBindingConfig }) {
  return (
    <div className="mt-3 grid gap-2 sm:grid-cols-2">
      <MetaBlock label="当前状态" value={STATUS_LABELS[config.status]} />
      <MetaBlock label="来源草案版本 ID" value={config.plan_version_id} mono />
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

function SkillBindingList({ config }: { config: ProjectDirectorSkillBindingConfig }) {
  return (
    <div className="mt-3 space-y-2">
      {config.skill_bindings.map((binding) => {
        const skillLabel = binding.skill_code || binding.skill_name || "未命名 Skill";
        const bindingModeLabel =
          BINDING_MODE_LABELS[binding.binding_mode] ?? binding.binding_mode;

        return (
          <div
            key={`${binding.owner_role_code}-${skillLabel}-${binding.activation_stage}`}
            className="rounded border border-[#333333] bg-[#111111]/60 px-3 py-2"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-zinc-100">
                {skillLabel}
              </span>
              <span className="rounded border border-[#333333] px-2 py-0.5 font-mono text-[11px] text-zinc-400">
                {binding.owner_role_code}
              </span>
              <span className="rounded border border-sky-500/20 px-2 py-0.5 text-[11px] text-sky-100/75">
                {bindingModeLabel}
              </span>
            </div>
            <dl className="mt-2 grid gap-2 text-xs leading-5 sm:grid-cols-2">
              <Field label="使用方式" value={binding.usage} />
              <Field label="激活阶段" value={binding.activation_stage} />
              <Field label="建议原因" value={binding.reason || "暂无说明"} />
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
      <dd className="mt-1 text-zinc-300">{value}</dd>
    </div>
  );
}

function BoundaryWarnings({ warnings }: { warnings: string[] }) {
  const items =
    warnings.length > 0
      ? warnings
      : [
          "这只是项目级 Skill 绑定配置。",
          "未创建真实 Skill 绑定。",
          "未启用 Skill，也未启动 Worker。",
        ];

  return (
    <div className="mt-3 rounded border border-sky-500/20 bg-[#111111]/70 px-3 py-2">
      <div className="text-xs font-medium text-sky-100">边界提示</div>
      <ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-5 text-sky-100/80">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
