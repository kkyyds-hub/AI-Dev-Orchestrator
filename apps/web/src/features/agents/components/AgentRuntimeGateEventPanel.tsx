import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import type { AgentTimelineMessage } from "../types";

type AgentRuntimeGateEventPanelProps = {
  messages: AgentTimelineMessage[];
};

type RuntimeEventTone = "neutral" | "info" | "success" | "warning" | "danger";

type RuntimeEventDetail = Record<string, unknown>;

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
  launches_ai_runtime: "启动 AI runtime",
  runs_real_command: "执行真实命令",
  runs_git: "执行 git",
  runs_write_git: "执行写 git",
  changes_process_cwd: "改变进程 cwd",
  fake_launch_started: "启动 fake launch",
  real_runtime_started: "启动真实 runtime",
  runtime_probe_started: "启动 runtime probe",
};

function isRuntimeGateEvent(message: AgentTimelineMessage) {
  return Object.prototype.hasOwnProperty.call(
    RUNTIME_GATE_EVENT_LABELS,
    message.event_type,
  );
}

function parseRuntimeDetail(contentDetail: string | null): RuntimeEventDetail | null {
  if (!contentDetail) {
    return null;
  }

  try {
    const parsed = JSON.parse(contentDetail) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as RuntimeEventDetail;
    }
  } catch {
    return null;
  }

  return null;
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
  return values.length ? values.join("、") : "未记录";
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
            从当前会话 timeline 只读筛选 runtime launch gate 事件；这里只展示门禁证据，不启动 fake launch、真实 runtime 或 runtime probe。
          </p>
        </div>
        <span className="text-xs text-slate-500">
          {runtimeGateMessages.length} 条
        </span>
      </div>

      {!runtimeGateMessages.length ? (
        <p className="mt-4 rounded-2xl border border-dashed border-[#333333] px-3 py-3 text-sm leading-6 text-slate-400">
          当前会话 timeline 暂无 runtime launch gate 事件。本页不会自动执行门禁、启动 runtime 或探测进程。
        </p>
      ) : (
        <ul className="mt-4 space-y-3">
          {runtimeGateMessages.map((message) => {
            const detail = parseRuntimeDetail(message.content_detail);
            const evidence = objectField(detail, "evidence");
            const safetyFlags = objectField(detail, "safety_flags");
            const passedGates = stringListField(evidence, "gates_passed");
            const failedGates = stringListField(evidence, "gates_failed");
            const summaryCn = stringField(detail, "summary_cn");
            const reasonCode =
              stringField(detail, "reason_code") ??
              stringField(evidence, "blocking_reason_code");
            const blockingSummary = stringField(evidence, "blocking_summary");

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
                      <span>{message.event_type}</span>
                    </div>
                    <p
                      className="mt-2 line-clamp-3 break-words text-sm leading-6 text-slate-100"
                      title={summaryCn ?? message.content_summary}
                    >
                      {summaryCn ?? message.content_summary}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-1.5">
                    <StatusBadge
                      label={
                        RUNTIME_GATE_EVENT_LABELS[message.event_type] ??
                        message.event_type
                      }
                      tone={RUNTIME_GATE_EVENT_TONES[message.event_type] ?? "neutral"}
                    />
                    <StatusBadge label="证据只读，未启动 runtime" tone="info" />
                  </div>
                </div>

                <dl className="mt-3 grid gap-x-4 gap-y-2 text-xs text-slate-500 sm:grid-cols-2">
                  <RuntimeGateDetail label="通过门禁" value={formatList(passedGates)} />
                  <RuntimeGateDetail label="失败门禁" value={formatList(failedGates)} />
                  <RuntimeGateDetail label="原因代码" value={reasonCode ?? "无"} />
                  <RuntimeGateDetail
                    label="阻断摘要"
                    value={blockingSummary ?? "无"}
                  />
                  <RuntimeGateDetail
                    label="运行时类型"
                    value={stringField(detail, "runtime_type") ?? "未记录"}
                  />
                  <RuntimeGateDetail
                    label="适配器"
                    value={stringField(detail, "adapter_kind") ?? "未记录"}
                  />
                  <RuntimeGateDetail
                    label="工作区路径"
                    value={stringField(evidence, "workspace_path") ?? "未记录"}
                  />
                  <RuntimeGateDetail
                    label="启动 cwd 预览"
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

function RuntimeGateDetail(props: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-slate-600">{props.label}</dt>
      <dd className="mt-0.5 truncate text-slate-300" title={props.value}>
        {props.value}
      </dd>
    </div>
  );
}
