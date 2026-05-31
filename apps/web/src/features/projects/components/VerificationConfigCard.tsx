import { useState } from "react";

import { StatusBadge } from "../../../components/StatusBadge";
import {
  useProjectDirectorVerificationConfig,
  useReviewProjectDirectorVerificationConfigMutation,
} from "../../project-director/hooks";
import type {
  ProjectDirectorVerificationConfig,
  ProjectDirectorVerificationConfigStatus,
} from "../../project-director/types";

type VerificationConfigCardProps = {
  projectId: string | null;
};

const STATUS_LABELS: Record<ProjectDirectorVerificationConfigStatus, string> = {
  pending_confirmation: "待确认",
  confirmed: "验证机制建议已确认",
  rejected: "验证机制建议已拒绝",
};

const STATUS_TONES: Record<
  ProjectDirectorVerificationConfigStatus,
  "info" | "success" | "warning"
> = {
  pending_confirmation: "warning",
  confirmed: "success",
  rejected: "info",
};

const RISK_LABELS: Record<string, string> = {
  low: "低",
  medium: "中",
  normal: "普通",
  high: "高",
};

export function VerificationConfigCard({ projectId }: VerificationConfigCardProps) {
  const [feedback, setFeedback] = useState<string | null>(null);
  const query = useProjectDirectorVerificationConfig(projectId);
  const reviewMutation = useReviewProjectDirectorVerificationConfigMutation();

  if (!projectId) {
    return null;
  }

  if (query.isError) {
    return (
      <section className="rounded-lg border border-amber-500/25 bg-amber-500/5 p-4 text-sm text-amber-100">
        AI 主管验证机制建议暂时读取失败，不影响项目详情主页面。
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
      data-testid="project-director-verification-config-card"
      className="rounded-lg border border-violet-500/25 bg-violet-500/5 p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-semibold text-violet-100">
              AI 主管验证机制建议
            </h4>
            <StatusBadge
              label={STATUS_LABELS[config.status]}
              tone={STATUS_TONES[config.status]}
            />
          </div>
          <p className="mt-1 text-xs leading-5 text-violet-100/75">
            这只是项目级验证机制配置建议；未执行任何验证命令，未创建 Run，
            未启动 Worker。
          </p>
        </div>
        {isPending ? (
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void review("confirm")}
              disabled={isReviewing}
              className="rounded border border-violet-300 bg-violet-100 px-3 py-1.5 text-xs font-semibold text-violet-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              确认验证机制建议
            </button>
            <button
              type="button"
              onClick={() => void review("reject")}
              disabled={isReviewing}
              className="rounded border border-[#333333] bg-[#151515] px-3 py-1.5 text-xs font-semibold text-zinc-200 transition hover:border-zinc-500 disabled:cursor-not-allowed disabled:opacity-60"
            >
              拒绝验证机制建议
            </button>
          </div>
        ) : null}
      </div>

      <ConfigMeta config={config} />
      <VerificationMechanismList config={config} />
      <BoundaryWarnings warnings={config.warnings} />

      {query.data?.next_action || feedback ? (
        <p className="mt-3 rounded border border-violet-500/20 bg-[#111111]/70 px-3 py-2 text-xs leading-5 text-violet-100/80">
          {feedback ?? query.data?.next_action}
        </p>
      ) : null}
    </section>
  );
}

function ConfigMeta({ config }: { config: ProjectDirectorVerificationConfig }) {
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

function VerificationMechanismList({
  config,
}: {
  config: ProjectDirectorVerificationConfig;
}) {
  return (
    <div className="mt-3 space-y-2">
      {config.verification_mechanisms.map((item) => (
        <div
          key={`${item.name}-${item.command_or_method}-${item.owner_role_code}`}
          className="rounded border border-[#333333] bg-[#111111]/60 px-3 py-2"
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-zinc-100">{item.name}</span>
            <span className="rounded border border-[#333333] px-2 py-0.5 font-mono text-[11px] text-zinc-400">
              {item.owner_role_code}
            </span>
            <span className="rounded border border-violet-500/20 px-2 py-0.5 text-[11px] text-violet-100/75">
              风险：{RISK_LABELS[item.risk_level] ?? item.risk_level}
            </span>
            <span className="rounded border border-violet-500/20 px-2 py-0.5 text-[11px] text-violet-100/75">
              {item.requires_user_confirmation ? "需要人工确认" : "无需额外确认"}
            </span>
          </div>
          <dl className="mt-2 grid gap-2 text-xs leading-5 sm:grid-cols-2">
            <Field label="方法或命令" value={item.command_or_method} mono />
            <Field label="目的" value={item.purpose || "暂无说明"} />
            <Field label="所需证据" value={item.evidence_required} />
          </dl>
        </div>
      ))}
    </div>
  );
}

function Field({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="text-[11px] text-zinc-500">{label}</dt>
      <dd className={`mt-1 break-words text-zinc-300 ${mono ? "font-mono" : ""}`}>
        {value}
      </dd>
    </div>
  );
}

function BoundaryWarnings({ warnings }: { warnings: string[] }) {
  const items =
    warnings.length > 0
      ? warnings
      : [
          "这只是项目级验证机制配置建议。",
          "未执行任何验证命令。",
          "未创建 Run。",
          "未启动 Worker。",
          "未调用 subprocess / os.system / planning/apply / apply-local / git-commit。",
        ];

  return (
    <div className="mt-3 rounded border border-violet-500/20 bg-[#111111]/70 px-3 py-2">
      <div className="text-xs font-medium text-violet-100">边界提示</div>
      <ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-5 text-violet-100/80">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
