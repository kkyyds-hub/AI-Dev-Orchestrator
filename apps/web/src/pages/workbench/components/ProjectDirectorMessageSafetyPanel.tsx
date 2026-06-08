import type {
  ProjectDirectorMessage,
  ProjectDirectorMessageRiskLevel,
  ProjectDirectorSuggestedAction,
} from "../../../features/project-director/types";

interface ProjectDirectorMessageSafetyPanelProps {
  message: ProjectDirectorMessage;
}

const DEFAULT_FORBIDDEN_ACTIONS = [
  "不会自动执行任务",
  "不会自动创建任务",
  "不会修改仓库",
  "不会启动外部工具",
];

const TECHNICAL_TERM_REPLACEMENTS: Array<[string, string]> = [
  ["provider", "回答服务"],
  ["Provider", "回答服务"],
  ["worker", "外部工具"],
  ["Worker", "外部工具"],
  ["executor", "外部工具"],
  ["Executor", "外部工具"],
  ["runtime", "运行环境"],
  ["Runtime", "运行环境"],
  ["API", "接口"],
  ["payload", "数据"],
  ["Git", "仓库"],
  ["dispatch_question", "调度提醒"],
  ["session_id", "会话标识"],
  ["project_id", "项目标识"],
  ["synthetic", "汇总"],
  ["read model", "只读视图"],
  ["intent", "判断"],
  ["source_detail", "来源说明"],
  ["risk_level", "风险"],
  ["forbidden_actions_detected", "安全边界"],
  ["suggested_actions", "建议"],
];

const HIDDEN_ACTION_LABEL_KEYWORDS = [
  "启动执行",
  "创建任务",
  "重试",
  "提交代码",
  "推送",
  "合并",
];

export function ProjectDirectorMessageSafetyPanel({
  message,
}: ProjectDirectorMessageSafetyPanelProps) {
  const riskLabel = formatRiskLabel(message.risk_level);
  const riskTone = mapRiskTone(message.risk_level);
  const forbiddenActions = normalizeForbiddenActions(
    message.forbidden_actions_detected,
  );
  const safeSuggestedActions = normalizeSuggestedActions(
    message.suggested_actions,
  );

  return (
    <div
      data-testid="project-director-message-safety-panel"
      className={`mt-2 rounded-md border p-2.5 ${riskTone.container}`}
    >
      <div className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-medium text-zinc-100">安全说明</p>
          <p className="mt-0.5 text-[10px] leading-4 text-zinc-500">
            这是对本条回复的只读说明；建议不代表已经执行。
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <span className={`rounded border px-1.5 py-0.5 text-[10px] ${riskTone.badge}`}>
            {riskLabel}
          </span>
          <span
            className={`rounded border px-1.5 py-0.5 text-[10px] ${
              message.requires_confirmation
                ? "border-amber-500/40 bg-amber-500/10 text-amber-200"
                : "border-[#333333] bg-[#111111] text-zinc-400"
            }`}
          >
            {message.requires_confirmation ? "需要你确认" : "无需确认，仅供查看"}
          </span>
        </div>
      </div>

      {message.risk_level === "high" ? (
        <p className="mt-2 rounded border border-rose-500/30 bg-rose-500/10 px-2 py-1.5 text-[10px] leading-4 text-rose-100/90">
          这类请求可能涉及执行或修改，需要你确认。
        </p>
      ) : null}

      <div className="mt-2 grid gap-2 lg:grid-cols-2">
        <div>
          <p className="text-[10px] font-medium text-zinc-400">
            系统不会自动做这些事
          </p>
          <ul className="mt-1 flex flex-wrap gap-1">
            {forbiddenActions.map((action) => (
              <li
                key={action}
                className="rounded border border-[#333333] bg-[#111111] px-1.5 py-0.5 text-[10px] leading-4 text-zinc-400"
              >
                {action}
              </li>
            ))}
          </ul>
        </div>

        <div>
          <p className="text-[10px] font-medium text-zinc-400">建议下一步</p>
          {safeSuggestedActions.length > 0 ? (
            <ul className="mt-1 flex flex-wrap gap-1">
              {safeSuggestedActions.map((action, index) => (
                <li
                  key={`${action.label}-${index}`}
                  className="rounded border border-[#333333] bg-[#111111] px-1.5 py-0.5 text-[10px] leading-4 text-zinc-400"
                >
                  <span>{action.label}</span>
                  {action.requiresConfirmation || action.highRisk ? (
                    <span className="ml-2 text-amber-200">
                      {[
                        action.requiresConfirmation ? "需要确认" : null,
                        action.highRisk ? "高风险" : null,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 rounded border border-[#333333] bg-[#111111] px-1.5 py-0.5 text-[10px] leading-4 text-zinc-500">
              继续提问，或查看当前草案和提醒。
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function normalizeForbiddenActions(actions: string[]) {
  const source = actions.length > 0 ? actions : DEFAULT_FORBIDDEN_ACTIONS;
  const normalized = source
    .map((action) => sanitizeUserText(action))
    .filter((action) => action.length > 0);
  return Array.from(new Set(normalized)).slice(0, 5);
}

function normalizeSuggestedActions(actions: ProjectDirectorSuggestedAction[]) {
  return actions
    .map((action) => {
      const label = sanitizeActionLabel(action);
      if (!label) {
        return null;
      }
      return {
        label,
        requiresConfirmation: action.requires_confirmation === true,
        highRisk: action.risk_level === "high",
      };
    })
    .filter(
      (
        action,
      ): action is {
        label: string;
        requiresConfirmation: boolean;
        highRisk: boolean;
      } => action !== null,
    )
    .slice(0, 5);
}

function sanitizeActionLabel(action: ProjectDirectorSuggestedAction) {
  const rawLabel = action.label?.trim() || fallbackActionLabel(action.type);
  const sanitized = sanitizeUserText(rawLabel);
  if (
    HIDDEN_ACTION_LABEL_KEYWORDS.some((keyword) => sanitized.includes(keyword))
  ) {
    return action.requires_confirmation
      ? "先确认操作步骤"
      : "查看说明后再决定";
  }
  return sanitized;
}

function fallbackActionLabel(type?: string) {
  switch (type) {
    case "summarize":
      return "查看摘要";
    case "explain":
      return "要求解释原因";
    case "navigate":
      return "查看相关位置";
    case "request_changes":
      return "说明修改意见";
    case "none":
      return "继续提问";
    default:
      return "继续提问";
  }
}

function sanitizeUserText(value: string) {
  let sanitized = value.trim();
  for (const [term, replacement] of TECHNICAL_TERM_REPLACEMENTS) {
    sanitized = sanitized.split(term).join(replacement);
  }
  return sanitized;
}

function formatRiskLabel(riskLevel: ProjectDirectorMessageRiskLevel | null) {
  if (riskLevel === "low") {
    return "低风险";
  }
  if (riskLevel === "medium") {
    return "中风险";
  }
  if (riskLevel === "high") {
    return "高风险";
  }
  return "风险未知";
}

function mapRiskTone(riskLevel: ProjectDirectorMessageRiskLevel | null) {
  if (riskLevel === "high") {
    return {
      container: "border-rose-500/30 bg-rose-500/5",
      badge: "border-rose-500/40 bg-rose-500/10 text-rose-200",
    };
  }
  if (riskLevel === "medium") {
    return {
      container: "border-amber-500/30 bg-amber-500/5",
      badge: "border-amber-500/40 bg-amber-500/10 text-amber-200",
    };
  }
  if (riskLevel === "low") {
    return {
      container: "border-emerald-500/25 bg-emerald-500/5",
      badge: "border-emerald-500/35 bg-emerald-500/10 text-emerald-200",
    };
  }
  return {
    container: "border-[#333333] bg-[#111111]",
    badge: "border-[#333333] bg-[#111111] text-zinc-400",
  };
}
