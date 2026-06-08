import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import type { AgentTimelineMessage } from "../types";

type AgentRuntimeGateEventPanelProps = {
  messages: AgentTimelineMessage[];
};

type RuntimeEventTone = "neutral" | "info" | "success" | "warning" | "danger";

type RuntimeEventDetail = Record<string, unknown>;

type RuntimeParseResult =
  | { parseState: "ok"; detail: RuntimeEventDetail }
  | { parseState: "empty"; detail: null }
  | { parseState: "invalid"; detail: null };

const RUNTIME_GATE_EVENT_LABELS: Record<string, string> = {
  runtime_launch_gate_evaluated: "运行时启动门禁已通过",
  runtime_launch_gate_blocked: "运行时启动门禁已阻断",
};

const RUNTIME_GATE_EVENT_TONES: Record<string, RuntimeEventTone> = {
  runtime_launch_gate_evaluated: "success",
  runtime_launch_gate_blocked: "warning",
};

const SAFETY_FLAG_LABELS: Record<string, string> = {
  execution_enabled: "允许执行",
  launches_ai_runtime: "启动 AI 运行时",
  runs_real_command: "执行真实命令",
  runs_git: "执行 Git 命令",
  runs_write_git: "Git 写入风险命令",
  changes_process_cwd: "改变进程工作目录",
  fake_launch_started: "启动模拟运行",
  real_runtime_started: "启动真实运行时",
  runtime_probe_started: "启动运行时探测",
};

const GATE_LABELS: Record<string, string> = {
  workspace_validation: "G1 工作区状态校验",
  workspace_context: "G2 工作区上下文校验",
  runtime_dry_run: "G3 运行时参数预览",
  safe_command_proof: "G4 工作区路径安全证明",
  adapter_capability: "G5 适配器能力检查",
};

const REASON_CODE_LABELS: Record<string, string> = {
  launch_gate_evaluated: "启动门禁已评估通过",
  launch_gate_blocked: "启动门禁已阻断",
  runtime_launch_gate_not_ready: "运行时启动门禁未就绪",
  workspace_context_not_ready: "工作区上下文未就绪",
  workspace_path_not_found: "工作区路径不存在",
  workspace_path_not_directory: "工作区路径不是目录",
  workspace_path_outside_allowed_root: "工作区路径不在允许范围内",
  agent_worktree_not_available: "智能体工作区不可用",
  runtime_dry_run_not_ready: "运行时参数预览未就绪",
  runtime_type_missing: "运行时类型缺失",
  agent_type_missing: "智能体类型缺失",
  workspace_path_missing: "工作区路径缺失",
  worktree_safe_command_proof_not_ready: "工作区安全命令证明未就绪",
  pwd_mismatch_workspace_path: "当前目录证明与工作区路径不一致",
  safe_command_timed_out: "安全命令证明超时",
  adapter_unavailable: "运行时适配器不可用",
  adapter_launch_blocked: "适配器能力检查阻断",
  snapshot_only: "仅记录快照，未启动运行时",
};

const BLOCKING_SUMMARY_LABELS: Record<string, string> = {
  "Workspace context is not ready for runtime launch.":
    "工作区上下文尚未满足运行时启动前置条件。",
  "Agent session is not bound to a clean worktree; runtime launch requires an active agent workspace.":
    "智能体会话未绑定干净的工作区；运行时启动需要可用的智能体工作区。",
  "Runtime launch dry-run configuration is not ready; agent_type / runtime_type / workspace_path may be missing.":
    "运行时参数预览未就绪；智能体类型、运行时类型或工作区路径可能缺失。",
  "Worker worktree safe command proof (pwd) failed or is not ready; cwd proof is required before runtime launch.":
    "工作区路径安全证明未通过或未就绪；启动前必须先确认当前工作目录。",
  "No runtime adapter is configured; cannot launch runtime.":
    "未配置运行时适配器，无法进入启动流程。",
};

function isRuntimeGateEvent(message: AgentTimelineMessage) {
  return Object.prototype.hasOwnProperty.call(
    RUNTIME_GATE_EVENT_LABELS,
    message.event_type,
  );
}

function parseRuntimeDetail(contentDetail: string | null): RuntimeParseResult {
  if (!contentDetail) {
    return { parseState: "empty", detail: null };
  }

  try {
    const parsed = JSON.parse(contentDetail) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return { parseState: "ok", detail: parsed as RuntimeEventDetail };
    }
  } catch {
    return { parseState: "invalid", detail: null };
  }

  return { parseState: "invalid", detail: null };
}

function stringField(
  detail: RuntimeEventDetail | null | undefined,
  key: string,
): string | null {
  const value = detail?.[key];
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function objectField(
  detail: RuntimeEventDetail | null,
  key: "evidence" | "safety_flags",
): Record<string, unknown> | null {
  const value = detail?.[key];
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

function stringListField(
  detail: Record<string, unknown> | null,
  key: string,
): string[] {
  const value = detail?.[key];
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is string => typeof item === "string")
    .filter((item) => item.trim().length > 0);
}

function booleanField(
  detail: Record<string, unknown> | null,
  key: string,
): boolean | null {
  const value = detail?.[key];
  return typeof value === "boolean" ? value : null;
}

function flagLabel(value: boolean | null) {
  if (value === true) {
    return "是";
  }
  if (value === false) {
    return "否";
  }
  return "未记录";
}

function formatList(values: string[]) {
  return values.length ? values.map(localizeGateName).join("、") : "未记录";
}

function localizeGateName(value: string) {
  return GATE_LABELS[value] ?? "未识别门禁";
}

function localizeReasonCode(value: string | null) {
  if (!value) {
    return "无";
  }
  return REASON_CODE_LABELS[value] ?? "未识别原因";
}

function localizeBlockingSummary(value: string | null) {
  if (!value) {
    return "无";
  }
  if (value.startsWith("Runtime adapter") && value.includes("cannot launch")) {
    return "运行时适配器能力检查未通过，未进入启动流程。";
  }
  return BLOCKING_SUMMARY_LABELS[value] ?? "门禁被阻断，详细原因已写入后端审计记录。";
}

const RUNTIME_TYPE_LABELS: Record<string, string> = {
  subprocess: "子进程运行方式",
  codex_cli: "Codex 命令行",
  claude_cli: "Claude 命令行",
  opencode_cli: "OpenCode 命令行",
  deepseek_provider: "DeepSeek 提供方",
  openai_provider: "OpenAI 提供方",
  fake: "模拟运行方式",
};

const ADAPTER_KIND_LABELS: Record<string, string> = {
  fake: "模拟适配器",
  subprocess: "子进程适配器",
  tmux: "Tmux 适配器",
  docker: "Docker 适配器",
};

function localizeRuntimeType(value: string | null) {
  if (!value) {
    return "未记录";
  }
  return RUNTIME_TYPE_LABELS[value] ?? "未知运行方式";
}

function localizeAdapterKind(value: string | null) {
  if (!value) {
    return "未记录";
  }
  return ADAPTER_KIND_LABELS[value] ?? "未知适配器";
}

export function AgentRuntimeGateEventPanel(
  props: AgentRuntimeGateEventPanelProps,
) {
  const runtimeGateMessages = props.messages
    .filter(isRuntimeGateEvent)
    .sort(
      (left, right) =>
        new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
    )
    .slice(0, 3);

  return (
    <section
      className="rounded-3xl border border-[#333333] bg-slate-950/25 p-4"
      data-testid="agent-runtime-gate-event-panel"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h4 className="text-sm font-semibold text-slate-100">
            最近运行时门禁事件
          </h4>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            从当前会话时间线只读筛选运行时启动门禁事件；这里只展示门禁证据，不启动模拟运行、真实运行时或运行时探测。
          </p>
        </div>
        <span className="text-xs text-slate-500">
          {runtimeGateMessages.length} 条
        </span>
      </div>

      {!runtimeGateMessages.length ? (
        <p className="mt-4 rounded-2xl border border-dashed border-[#333333] px-3 py-3 text-sm leading-6 text-slate-400">
          当前会话时间线暂无运行时启动门禁事件。本页不会自动执行门禁、启动运行时或探测进程。
        </p>
      ) : (
        <ul className="mt-4 space-y-3">
          {runtimeGateMessages.map((message) => {
            const parseResult = parseRuntimeDetail(message.content_detail);
            const detail =
              parseResult.parseState === "ok" ? parseResult.detail : null;
            const evidence = objectField(detail, "evidence");
            const safetyFlags = objectField(detail, "safety_flags");
            const passedGates = stringListField(evidence, "gates_passed");
            const failedGates = stringListField(evidence, "gates_failed");
            const summaryCn = stringField(detail, "summary_cn");
            const reasonCode =
              stringField(detail, "reason_code") ??
              stringField(evidence, "blocking_reason_code");
            const blockingSummary = stringField(evidence, "blocking_summary");
            const runtimeTypeValue = stringField(detail, "runtime_type");
            const adapterKindValue = stringField(detail, "adapter_kind");

            const detailMessage =
              parseResult.parseState === "empty"
                ? "事件详情未记录。"
                : parseResult.parseState === "invalid"
                  ? "事件详情无法解析。"
                  : null;

            return (
              <li
                key={message.message_id}
                className="rounded-2xl border border-[#333333] bg-black/15 p-3"
                data-testid="agent-runtime-gate-event-item"
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500">
                      <span>{formatDateTime(message.created_at)}</span>
                      <span>
                        {RUNTIME_GATE_EVENT_LABELS[message.event_type] ??
                          "运行时门禁事件"}
                      </span>
                    </div>
                    <p
                      className="mt-2 line-clamp-3 break-words text-sm leading-6 text-slate-100"
                      title={summaryCn ?? message.content_summary}
                    >
                      {summaryCn ?? message.content_summary}
                    </p>
                    {detailMessage ? (
                      <p className="mt-2 rounded-2xl border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs leading-5 text-amber-200">
                        {detailMessage}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-1.5">
                    <StatusBadge
                      label={
                        RUNTIME_GATE_EVENT_LABELS[message.event_type] ??
                        message.event_type
                      }
                      tone={RUNTIME_GATE_EVENT_TONES[message.event_type] ?? "neutral"}
                    />
                    <StatusBadge label="证据只读，未启动运行时" tone="info" />
                  </div>
                </div>

                <dl className="mt-3 grid gap-x-4 gap-y-2 text-xs text-slate-500 sm:grid-cols-2">
                  <RuntimeGateDetail label="通过门禁" value={formatList(passedGates)} />
                  <RuntimeGateDetail label="失败门禁" value={formatList(failedGates)} />
                  <RuntimeGateDetail label="阻断原因" value={localizeReasonCode(reasonCode)} />
                  <RuntimeGateDetail
                    label="阻断摘要"
                    value={localizeBlockingSummary(blockingSummary)}
                  />
                  <RuntimeGateDetail
                    label="运行时类型"
                    value={localizeRuntimeType(runtimeTypeValue)}
                    title={runtimeTypeValue ?? undefined}
                  />
                  <RuntimeGateDetail
                    label="适配器"
                    value={localizeAdapterKind(adapterKindValue)}
                    title={adapterKindValue ?? undefined}
                  />
                  <RuntimeGateDetail
                    label="工作区路径"
                    value={stringField(evidence, "workspace_path") ?? "未记录"}
                  />
                  <RuntimeGateDetail
                    label="启动工作目录预览"
                    value={stringField(evidence, "launch_cwd_preview") ?? "未记录"}
                  />
                </dl>

                <div className="mt-3 rounded-2xl border border-[#333333] bg-slate-950/30 p-3">
                  <div className="text-xs font-medium text-slate-300">
                    安全标记
                  </div>
                  <dl className="mt-2 grid gap-x-4 gap-y-2 text-xs text-slate-500 sm:grid-cols-2">
                    {Object.entries(SAFETY_FLAG_LABELS).map(([key, label]) => (
                      <RuntimeGateDetail
                        key={key}
                        label={label}
                        value={flagLabel(booleanField(safetyFlags, key))}
                      />
                    ))}
                  </dl>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function RuntimeGateDetail(props: {
  label: string;
  value: string;
  title?: string;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-slate-600">{props.label}</dt>
      <dd
        className="mt-0.5 truncate text-slate-300"
        title={props.title ?? props.value}
      >
        {props.value}
      </dd>
    </div>
  );
}
