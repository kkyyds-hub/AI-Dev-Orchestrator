import type { ProjectDirectorMessage } from "../../../features/project-director/types";

interface ProjectDirectorChallengeReadbackPanelProps {
  message: ProjectDirectorMessage;
}

const REVIEW_HINT_KEYWORDS = [
  "需要复核",
  "质疑",
  "需求变更",
  "不会直接修改草案",
  "调度依据",
  "外部工具",
];

const READONLY_BOUNDARIES = [
  "不会自动修改草案",
  "不会自动创建任务",
  "不会自动执行任务",
  "不会修改仓库",
  "不会启动外部工具",
];

export function ProjectDirectorChallengeReadbackPanel({
  message,
}: ProjectDirectorChallengeReadbackPanelProps) {
  if (!shouldShowChallengeReadback(message)) {
    return null;
  }

  const needsConfirmation = message.requires_confirmation === true;
  const mayAffectPlan = message.intent === "request_plan_change";

  return (
    <div
      data-testid="project-director-challenge-readback-panel"
      className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-medium text-amber-100">复核提示</p>
          <p className="mt-1 text-[10px] leading-4 text-amber-100/75">
            这条回复可能涉及你的质疑或需求变化。系统只会先解释和整理，不会直接修改草案。
          </p>
        </div>
        <span className="w-fit rounded border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-200">
          只读提示
        </span>
      </div>

      <div className="mt-2 space-y-1 text-[10px] leading-4 text-zinc-400">
        {needsConfirmation ? (
          <p className="rounded border border-amber-500/30 bg-[#111111] px-2 py-1 text-amber-100/90">
            继续处理前需要你确认。
          </p>
        ) : null}
        {mayAffectPlan ? (
          <p className="rounded border border-[#333333] bg-[#111111] px-2 py-1">
            这类反馈可能影响项目草案。
          </p>
        ) : null}
      </div>

      <div className="mt-3">
        <p className="text-[10px] font-medium text-zinc-400">系统不会做这些事</p>
        <ul className="mt-1 grid gap-1 sm:grid-cols-2">
          {READONLY_BOUNDARIES.map((boundary) => (
            <li
              key={boundary}
              className="rounded border border-[#333333] bg-[#111111] px-2 py-1 text-[10px] leading-4 text-zinc-400"
            >
              {boundary}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function shouldShowChallengeReadback(message: ProjectDirectorMessage) {
  if (message.intent === "request_plan_change") {
    return true;
  }
  if (
    message.requires_confirmation === true &&
    (message.risk_level === "medium" || message.risk_level === "high")
  ) {
    return true;
  }
  return REVIEW_HINT_KEYWORDS.some((keyword) => message.content.includes(keyword));
}
