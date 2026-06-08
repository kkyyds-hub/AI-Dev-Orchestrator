import type { ProjectDirectorMessage } from "../../../features/project-director/types";

interface ProjectDirectorConversionReadbackPanelProps {
  message: ProjectDirectorMessage;
}

const CONVERSION_HINT_KEYWORDS = [
  "可查看的草稿",
  "计划修改草稿",
  "任务草稿",
  "不会直接改草案",
  "不会自动创建任务",
  "继续处理前需要你确认",
];

const READONLY_BOUNDARIES = [
  "不会自动修改草案",
  "不会自动创建任务",
  "不会自动执行任务",
  "不会修改仓库",
  "不会启动外部工具",
  "不会自动应用建议",
  "不会自动执行审批",
];

export function ProjectDirectorConversionReadbackPanel({
  message,
}: ProjectDirectorConversionReadbackPanelProps) {
  if (!shouldShowConversionReadback(message)) {
    return null;
  }

  const mayAffectPlan = message.intent === "request_plan_change";
  const needsConfirmation = message.requires_confirmation === true;

  return (
    <div
      data-testid="project-director-conversion-readback-panel"
      className="mt-2 rounded-md border border-cyan-500/25 bg-cyan-500/5 p-2.5"
    >
      <div className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-medium text-cyan-100">可查看草稿</p>
          <p className="mt-0.5 text-[10px] leading-4 text-cyan-100/75">
            系统可能已经把你的反馈整理成草稿。草稿只用于查看和确认，不会自动生效。
          </p>
        </div>
        <span className="w-fit rounded border border-cyan-500/40 bg-cyan-500/10 px-1.5 py-0.5 text-[10px] text-cyan-200">
          只读提示
        </span>
      </div>

      <div className="mt-2 space-y-1 text-[10px] leading-4 text-zinc-400">
        {mayAffectPlan ? (
          <p className="rounded border border-[#333333] bg-[#111111] px-2 py-1">
            这类草稿可能影响项目草案或任务安排。
          </p>
        ) : null}
        {needsConfirmation ? (
          <p className="rounded border border-amber-500/30 bg-[#111111] px-2 py-1 text-amber-100/90">
            继续处理前需要你确认。
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

function shouldShowConversionReadback(message: ProjectDirectorMessage) {
  if (message.intent === "request_plan_change") {
    return true;
  }
  if (
    message.suggested_actions.some((action) => action.type === "request_changes")
  ) {
    return true;
  }
  return CONVERSION_HINT_KEYWORDS.some((keyword) =>
    message.content.includes(keyword),
  );
}
