import { useState } from "react";

import { StatusBadge } from "../../../components/StatusBadge";
import {
  useProjectDirectorAgentTeamConfig,
  useReviewProjectDirectorAgentTeamConfigMutation,
} from "../../project-director/hooks";
import type {
  ProjectDirectorAgentTeamConfig,
  ProjectDirectorAgentTeamConfigStatus,
} from "../../project-director/types";

type AgentTeamConfigCardProps = {
  projectId: string | null;
};

const STATUS_LABELS: Record<ProjectDirectorAgentTeamConfigStatus, string> = {
  pending_confirmation: "待确认",
  confirmed: "Agent 编队已确认",
  rejected: "Agent 编队已拒绝",
};

const STATUS_TONES: Record<ProjectDirectorAgentTeamConfigStatus, "info" | "success" | "warning"> = {
  pending_confirmation: "warning",
  confirmed: "success",
  rejected: "info",
};

export function AgentTeamConfigCard({ projectId }: AgentTeamConfigCardProps) {
  const [feedback, setFeedback] = useState<string | null>(null);
  const query = useProjectDirectorAgentTeamConfig(projectId);
  const reviewMutation = useReviewProjectDirectorAgentTeamConfigMutation();

  if (!projectId) {
    return null;
  }

  if (query.isError) {
    return (
      <section className="rounded-lg border border-amber-500/25 bg-amber-500/5 p-4 text-sm text-amber-100">
        AI 主管 Agent 编队建议暂时读取失败，不影响项目详情主页面。
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
      data-testid="project-director-agent-team-config-card"
      className="rounded-lg border border-violet-500/25 bg-violet-500/5 p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-semibold text-violet-100">
              AI 主管 Agent 编队建议
            </h4>
            <StatusBadge
              label={STATUS_LABELS[config.status]}
              tone={STATUS_TONES[config.status]}
            />
          </div>
          <p className="mt-1 text-xs leading-5 text-violet-100/75">
            这是项目级 Agent 编队配置建议；未创建真实 Agent Session，未启动 Worker。
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
              确认 Agent 编队
            </button>
            <button
              type="button"
              onClick={() => void review("reject")}
              disabled={isReviewing}
              className="rounded border border-[#333333] bg-[#151515] px-3 py-1.5 text-xs font-semibold text-zinc-200 transition hover:border-zinc-500 disabled:cursor-not-allowed disabled:opacity-60"
            >
              拒绝 Agent 编队
            </button>
          </div>
        ) : null}
      </div>

      <ConfigMeta config={config} />
      <AgentTeamList config={config} />
      <BoundaryWarnings warnings={config.warnings} />

      {(query.data?.next_action || feedback) ? (
        <p className="mt-3 rounded border border-violet-500/20 bg-[#111111]/70 px-3 py-2 text-xs leading-5 text-violet-100/80">
          {feedback ?? query.data?.next_action}
        </p>
      ) : null}
    </section>
  );
}

function ConfigMeta({ config }: { config: ProjectDirectorAgentTeamConfig }) {
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

function AgentTeamList({ config }: { config: ProjectDirectorAgentTeamConfig }) {
  return (
    <div className="mt-3 space-y-2">
      {config.agent_team.map((agent) => (
        <div
          key={`${agent.role_code}-${agent.role_name}`}
          className="rounded border border-[#333333] bg-[#111111]/60 px-3 py-2"
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-zinc-100">
              {agent.role_name || agent.role_code}
            </span>
            <span className="rounded border border-[#333333] px-2 py-0.5 font-mono text-[11px] text-zinc-400">
              {agent.role_code}
            </span>
          </div>
          <p className="mt-2 text-xs leading-5 text-zinc-300">
            {agent.responsibility}
          </p>
          {agent.collaboration_notes.length > 0 ? (
            <ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-5 text-zinc-400">
              {agent.collaboration_notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function BoundaryWarnings({ warnings }: { warnings: string[] }) {
  const items =
    warnings.length > 0
      ? warnings
      : [
          "这只是项目级 Agent 编队配置。",
          "未创建真实 Agent Session。",
          "未启动 Worker。",
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

