import type { ProjectDirectorMessage } from "../../../features/project-director/types";

interface ProjectDirectorProposalReadbackPanelProps {
  message: ProjectDirectorMessage;
}

const PROPOSAL_HINT_KEYWORDS = [
  "可审查的建议",
  "修改建议",
  "这只是修改建议",
  "不会直接改草案",
  "继续处理前需要你确认或复核",
  "建议摘要",
  "建议原因",
];

const READONLY_BOUNDARIES = [
  "不会自动修改草案",
  "不会自动创建任务",
  "不会自动执行任务",
  "不会修改仓库",
  "不会启动外部工具",
  "不会自动应用建议",
];

export function ProjectDirectorProposalReadbackPanel({
  message,
}: ProjectDirectorProposalReadbackPanelProps) {
  if (!shouldShowProposalReadback(message)) {
    return null;
  }

  const mayAffectPlan = message.intent === "request_plan_change";
  const needsConfirmation = message.requires_confirmation === true;

  return (
    <div
      data-testid="project-director-proposal-readback-panel"
      className="mt-2 rounded-md border border-violet-500/25 bg-violet-500/5 p-2.5"
    >
      <div className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-medium text-violet-100">可审查建议</p>
          <p className="mt-0.5 text-[10px] leading-4 text-violet-100/75">
            系统可能已经把你的反馈整理成一个建议。这个建议只用于查看和确认，不会自动应用。
          </p>
        </div>
        <span className="w-fit rounded border border-violet-500/40 bg-violet-500/10 px-1.5 py-0.5 text-[10px] text-violet-200">
          只读提示
        </span>
      </div>

      <div className="mt-2 space-y-1 text-[10px] leading-4 text-zinc-400">
        {mayAffectPlan ? (
          <p className="rounded border border-[#333333] bg-[#111111] px-2 py-1">
            这类建议可能影响项目草案。
          </p>
        ) : null}
        {needsConfirmation ? (
          <p className="rounded border border-amber-500/30 bg-[#111111] px-2 py-1 text-amber-100/90">
            继续处理前需要你确认或复核。
          </p>
        ) : null}
      </div>

      <div className="mt-2">
        <p className="text-[10px] font-medium text-zinc-400">系统不会做这些事</p>
        <ul className="mt-1 flex flex-wrap gap-1">
          {READONLY_BOUNDARIES.map((boundary) => (
            <li
              key={boundary}
              className="rounded border border-[#333333] bg-[#111111] px-1.5 py-0.5 text-[10px] leading-4 text-zinc-400"
            >
              {boundary}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function shouldShowProposalReadback(message: ProjectDirectorMessage) {
  if (message.intent === "request_plan_change") {
    return true;
  }
  if (
    message.suggested_actions.some((action) => action.type === "request_changes")
  ) {
    return true;
  }
  return PROPOSAL_HINT_KEYWORDS.some((keyword) =>
    message.content.includes(keyword),
  );
}
