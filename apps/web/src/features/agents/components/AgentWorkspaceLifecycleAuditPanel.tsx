import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import type { AgentTimelineMessage } from "../types";

type WorkspaceLifecycleAuditPanelProps = {
  messages: AgentTimelineMessage[];
};

type AuditTone = "neutral" | "info" | "success" | "warning" | "danger";

const WORKSPACE_LIFECYCLE_EVENT_TYPE = "workspace_lifecycle_audit";
const WORKSPACE_CREATE_PREFIX = "workspace.create.";
const WORKSPACE_CLEANUP_PREFIX = "workspace.cleanup.";

const NOTE_EVENT_LABELS: Record<string, string> = {
  "workspace.create.blocked": "创建被阻止",
  "workspace.create.created": "创建成功",
  "workspace.create.failed": "创建失败",
  "workspace.cleanup.blocked": "清理被阻止",
  "workspace.cleanup.cleaned": "清理成功",
  "workspace.cleanup.failed": "清理失败",
};

const OUTCOME_LABELS: Record<string, string> = {
  blocked: "已阻止",
  failed: "失败",
  succeeded: "成功",
};

const OUTCOME_TONES: Record<string, AuditTone> = {
  blocked: "warning",
  failed: "danger",
  succeeded: "success",
};

function isWorkspaceLifecycleAudit(message: AgentTimelineMessage) {
  const noteEventType = message.note_event_type ?? "";
  return (
    message.event_type === WORKSPACE_LIFECYCLE_EVENT_TYPE ||
    noteEventType.startsWith(WORKSPACE_CREATE_PREFIX) ||
    noteEventType.startsWith(WORKSPACE_CLEANUP_PREFIX)
  );
}

function parseDetail(contentDetail: string | null): Record<string, unknown> | null {
  if (!contentDetail) {
    return null;
  }

  try {
    const parsed = JSON.parse(contentDetail) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    return null;
  }

  return null;
}

function stringField(
  detail: Record<string, unknown> | null,
  key: string,
): string | null {
  const value = detail?.[key];
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function booleanField(
  detail: Record<string, unknown> | null,
  key: string,
): boolean | null {
  const value = detail?.[key];
  return typeof value === "boolean" ? value : null;
}

function getOutcome(message: AgentTimelineMessage, detail: Record<string, unknown> | null) {
  const detailOutcome = stringField(detail, "outcome");
  if (detailOutcome) {
    return detailOutcome;
  }

  const noteEventType = message.note_event_type ?? "";
  if (noteEventType.endsWith(".created") || noteEventType.endsWith(".cleaned")) {
    return "succeeded";
  }
  if (noteEventType.endsWith(".failed")) {
    return "failed";
  }
  if (noteEventType.endsWith(".blocked")) {
    return "blocked";
  }

  return null;
}

function getActionLabel(message: AgentTimelineMessage, detail: Record<string, unknown> | null) {
  const noteEventType = message.note_event_type ?? "";
  if (NOTE_EVENT_LABELS[noteEventType]) {
    return NOTE_EVENT_LABELS[noteEventType];
  }

  const action = stringField(detail, "action");
  if (action === "create") {
    return "创建";
  }
  if (action === "cleanup") {
    return "清理";
  }

  return noteEventType || "workspace lifecycle";
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

export function AgentWorkspaceLifecycleAuditPanel(
  props: WorkspaceLifecycleAuditPanelProps,
) {
  const auditMessages = props.messages
    .filter(isWorkspaceLifecycleAudit)
    .sort(
      (left, right) =>
        new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
    )
    .slice(0, 3);

  return (
    <section
      className="rounded-3xl border border-[#333333] bg-slate-950/25 p-4"
      data-testid="agent-workspace-lifecycle-audit-panel"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h4 className="text-sm font-semibold text-slate-100">
            最近工作区生命周期审计
          </h4>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            从当前会话 timeline 只读筛选 workspace lifecycle audit 事件；这里只展示审计结果，不调用创建、清理、worker 或 runtime。
          </p>
        </div>
        <span className="text-xs text-slate-500">{auditMessages.length} 条</span>
      </div>

      {!auditMessages.length ? (
        <p className="mt-4 rounded-2xl border border-dashed border-[#333333] px-3 py-3 text-sm leading-6 text-slate-400">
          当前会话 timeline 暂无 workspace create / cleanup 审计记录。可能尚未执行 P1 worktree 生命周期动作；本页不会自动创建或清理 worktree，也不表示已进入 AI runtime。
        </p>
      ) : (
        <ul className="mt-4 space-y-3">
          {auditMessages.map((message) => {
            const detail = parseDetail(message.content_detail);
            const outcome = getOutcome(message, detail);
            const worktreePath =
              stringField(detail, "workspace_path") ??
              stringField(detail, "worktree_path");
            const branchName = stringField(detail, "branch_name");
            const status =
              stringField(detail, "create_status") ??
              stringField(detail, "cleanup_status") ??
              message.state_to;
            const blockedReason = stringField(detail, "blocked_reason");

            return (
              <li
                key={message.message_id}
                className="rounded-2xl border border-[#333333] bg-black/15 p-3"
                data-testid="agent-workspace-lifecycle-audit-item"
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500">
                      <span>{formatDateTime(message.created_at)}</span>
                      <span>{message.note_event_type ?? message.event_type}</span>
                    </div>
                    <p
                      className="mt-2 line-clamp-3 break-words text-sm leading-6 text-slate-100"
                      title={message.content_summary}
                    >
                      {message.content_summary}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-1.5">
                    <StatusBadge label={getActionLabel(message, detail)} tone="info" />
                    <StatusBadge
                      label={outcome ? OUTCOME_LABELS[outcome] ?? outcome : "结果未记录"}
                      tone={outcome ? OUTCOME_TONES[outcome] ?? "neutral" : "neutral"}
                    />
                  </div>
                </div>

                <dl className="mt-3 grid gap-x-4 gap-y-2 text-xs text-slate-500 sm:grid-cols-2">
                  <div className="min-w-0">
                    <dt className="text-slate-600">工作区路径</dt>
                    <dd className="mt-0.5 truncate text-slate-300" title={worktreePath ?? undefined}>
                      {worktreePath ?? "未记录"}
                    </dd>
                  </div>
                  <div className="min-w-0">
                    <dt className="text-slate-600">分支</dt>
                    <dd className="mt-0.5 truncate text-slate-300" title={branchName ?? undefined}>
                      {branchName ?? "未记录"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-600">状态</dt>
                    <dd className="mt-0.5 text-slate-300">{status ?? "未记录"}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-600">阻止原因</dt>
                    <dd className="mt-0.5 text-slate-300">
                      {blockedReason ?? "无"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-600">执行只读 git</dt>
                    <dd className="mt-0.5 text-slate-300">
                      {flagLabel(booleanField(detail, "runs_git"))}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-600">执行写 git</dt>
                    <dd className="mt-0.5 text-slate-300">
                      {flagLabel(booleanField(detail, "runs_write_git"))}
                    </dd>
                  </div>
                </dl>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
