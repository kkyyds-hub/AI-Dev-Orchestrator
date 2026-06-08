import { useEffect, useMemo, useState } from "react";

import { StatusBadge } from "../../../components/StatusBadge";
import {
  useRuntimeSessionEventsReadback,
  useRuntimeSessionReadback,
  useRuntimeSessionsReadback,
} from "../../../features/runtime/hooks";
import type {
  RuntimeEventReadback,
  RuntimeSessionReadback,
} from "../../../features/runtime/types";
import { formatDateTime } from "../../../lib/format";

const SAFETY_POINTS = [
  "当前仅展示 fake runtime / read-only runtime sessions",
  "不启动 Codex / Claude Code / DeepSeek",
  "不执行 subprocess / shell",
  "不触发产品运行时 Git 写",
];

export function RuntimeReadbackPanel() {
  const sessionsQuery = useRuntimeSessionsReadback();
  const sessions = useMemo(
    () => sessionsQuery.data ?? [],
    [sessionsQuery.data],
  );
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [copiedSessionId, setCopiedSessionId] = useState<string | null>(null);

  useEffect(() => {
    if (sessions.length === 0) {
      setSelectedSessionId(null);
      return;
    }
    setSelectedSessionId((current) =>
      current && sessions.some((session) => session.session_id === current)
        ? current
        : sessions[0].session_id,
    );
  }, [sessions]);

  const selectedSessionQuery = useRuntimeSessionReadback(selectedSessionId);
  const eventStreamQuery = useRuntimeSessionEventsReadback(selectedSessionId);
  const selectedSession =
    selectedSessionQuery.data ??
    sessions.find((session) => session.session_id === selectedSessionId) ??
    null;
  const events = eventStreamQuery.data?.events ?? [];

  const handleCopySessionId = async (sessionId: string) => {
    try {
      await navigator.clipboard.writeText(sessionId);
      setCopiedSessionId(sessionId);
      window.setTimeout(() => setCopiedSessionId(null), 1400);
    } catch {
      setCopiedSessionId(null);
    }
  };

  return (
    <section
      data-testid="runtime-readback-panel"
      className="rounded-lg border border-[#333333] bg-[#1a1a1a] p-4"
    >
      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-zinc-100">
              P9 受控运行时只读观察
            </h2>
            <p className="mt-1 text-xs leading-5 text-zinc-500">
              P9-F 只读取 fake runtime sessions，不代表真实执行器已启动。
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              void sessionsQuery.refetch();
              if (selectedSessionId) {
                void selectedSessionQuery.refetch();
                void eventStreamQuery.refetch();
              }
            }}
            className="w-fit rounded border border-[#333333] px-2 py-1 text-[10px] text-zinc-300 transition hover:border-zinc-500 hover:bg-[#222222]"
          >
            {sessionsQuery.isFetching ? "刷新中..." : "刷新"}
          </button>
        </div>

        <div className="grid gap-1.5">
          {SAFETY_POINTS.map((point) => (
            <p
              key={point}
              className="rounded border border-cyan-500/20 bg-cyan-500/5 px-2 py-1 text-[10px] leading-4 text-cyan-100/80"
            >
              {point}
            </p>
          ))}
        </div>

        {sessionsQuery.isLoading ? (
          <RuntimePanelState testId="runtime-readback-loading" message="正在读取 fake runtime sessions..." />
        ) : null}

        {sessionsQuery.isError ? (
          <RuntimePanelState
            testId="runtime-readback-error"
            tone="error"
            message={`runtime sessions 读取失败：${sessionsQuery.error.message}`}
          />
        ) : null}

        {!sessionsQuery.isLoading &&
        !sessionsQuery.isError &&
        sessions.length === 0 ? (
          <RuntimePanelState
            testId="runtime-readback-empty"
            message="暂无 fake runtime session"
          />
        ) : null}

        {sessions.length > 0 ? (
          <div className="grid gap-3">
            <div className="space-y-2">
              <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-zinc-600">
                sessions
              </p>
              <div className="max-h-56 space-y-2 overflow-y-auto pr-1">
                {sessions.map((session) => (
                  <RuntimeSessionListItem
                    key={session.session_id}
                    session={session}
                    selected={session.session_id === selectedSessionId}
                    copied={copiedSessionId === session.session_id}
                    onSelect={() => setSelectedSessionId(session.session_id)}
                    onCopy={() => void handleCopySessionId(session.session_id)}
                  />
                ))}
              </div>
            </div>

            <RuntimeSessionDetail
              session={selectedSession}
              loading={selectedSessionQuery.isFetching && !selectedSession}
              error={selectedSessionQuery.isError ? selectedSessionQuery.error.message : null}
            />

            <RuntimeEventStream
              events={events}
              loading={eventStreamQuery.isFetching && events.length === 0}
              error={eventStreamQuery.isError ? eventStreamQuery.error.message : null}
            />
          </div>
        ) : null}
      </div>
    </section>
  );
}

function RuntimeSessionListItem(props: {
  session: RuntimeSessionReadback;
  selected: boolean;
  copied: boolean;
  onSelect: () => void;
  onCopy: () => void;
}) {
  const fakeRuntime = props.session.source === "fake_adapter";

  return (
    <div
      className={`rounded border p-2 ${
        props.selected
          ? "border-cyan-500/40 bg-cyan-500/10"
          : "border-[#333333] bg-[#111111]"
      }`}
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <button
          type="button"
          onClick={props.onSelect}
          className="min-w-0 text-left"
        >
          <span className="block truncate text-xs font-medium text-zinc-100">
            {shortId(props.session.session_id)}
          </span>
          <span className="mt-1 block text-[10px] leading-4 text-zinc-500">
            {props.session.executor_id} / {formatStateLabel(props.session.state)}
          </span>
        </button>
        <div className="flex shrink-0 flex-wrap gap-1 sm:justify-end">
          <StatusBadge label={formatStateLabel(props.session.state)} tone="info" />
          <StatusBadge
            label={fakeRuntime ? "fake runtime" : props.session.source}
            tone={fakeRuntime ? "warning" : "info"}
          />
        </div>
      </div>

      <div className="mt-2 grid gap-1 text-[10px] leading-4 text-zinc-500">
        <RuntimeMetaRow label="source" value={props.session.source} />
        <RuntimeMetaRow label="project" value={props.session.project_id ?? "未绑定"} />
        <RuntimeMetaRow label="task" value={props.session.task_id ?? "未绑定"} />
        <RuntimeMetaRow label="run" value={props.session.run_id ?? "未绑定"} />
        <RuntimeMetaRow label="created" value={formatDateTime(props.session.created_at)} />
        <RuntimeMetaRow label="updated" value={formatDateTime(props.session.updated_at)} />
      </div>

      <button
        type="button"
        onClick={props.onCopy}
        className="mt-2 rounded border border-[#333333] px-2 py-1 text-[10px] text-zinc-300 transition hover:border-zinc-500 hover:bg-[#222222]"
      >
        {props.copied ? "已复制" : "复制 session_id"}
      </button>
    </div>
  );
}

function RuntimeSessionDetail(props: {
  session: RuntimeSessionReadback | null;
  loading: boolean;
  error: string | null;
}) {
  if (props.loading) {
    return <RuntimePanelState testId="runtime-session-detail-loading" message="正在读取 session detail..." />;
  }

  if (props.error) {
    return (
      <RuntimePanelState
        testId="runtime-session-detail-error"
        tone="error"
        message={`session detail 读取失败：${props.error}`}
      />
    );
  }

  if (!props.session) {
    return null;
  }

  const session = props.session;

  return (
    <div
      data-testid="runtime-session-detail"
      className="rounded border border-[#333333] bg-[#111111] p-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-medium text-zinc-100">selected session detail</p>
        <StatusBadge
          label={session.source === "fake_adapter" ? "fake runtime only" : session.source}
          tone={session.source === "fake_adapter" ? "warning" : "info"}
        />
      </div>

      <div className="mt-3 grid gap-2 text-[10px] leading-4 text-zinc-500">
        <RuntimeMetaRow label="session_id" value={session.session_id} />
        <RuntimeMetaRow label="executor_id" value={session.executor_id} />
        <RuntimeMetaRow label="state" value={formatStateLabel(session.state)} />
        <RuntimeMetaRow label="source" value={session.source} />
        <RuntimeMetaRow label="launch_preview_id" value={session.launch_preview_id ?? "未记录"} />
        <RuntimeMetaRow label="project_id" value={session.project_id ?? "未绑定"} />
        <RuntimeMetaRow label="task_id" value={session.task_id ?? "未绑定"} />
        <RuntimeMetaRow label="run_id" value={session.run_id ?? "未绑定"} />
      </div>

      <div className="mt-3 grid gap-2">
        <RuntimeSnapshotBlock title="process snapshot">
          <RuntimeMetaRow
            label="fake process_id"
            value={
              session.process.process_id === null
                ? "fake 未分配，不是操作系统 PID"
                : `${session.process.process_id}（fake，不是操作系统 PID）`
            }
          />
          <RuntimeMetaRow label="exit_code" value={formatNullableNumber(session.process.exit_code)} />
          <RuntimeMetaRow label="started_at" value={formatNullableDate(session.process.started_at)} />
          <RuntimeMetaRow label="finished_at" value={formatNullableDate(session.process.finished_at)} />
          <RuntimeMetaRow label="last_activity_at" value={formatNullableDate(session.process.last_activity_at)} />
          <RuntimeMetaRow label="heartbeat_at" value={formatNullableDate(session.process.heartbeat_at)} />
        </RuntimeSnapshotBlock>

        <RuntimeSnapshotBlock title="usage snapshot">
          <RuntimeMetaRow label="prompt_tokens" value={String(session.usage.prompt_tokens)} />
          <RuntimeMetaRow label="completion_tokens" value={String(session.usage.completion_tokens)} />
          <RuntimeMetaRow label="total_tokens" value={String(session.usage.total_tokens)} />
          <RuntimeMetaRow
            label="estimated_cost"
            value={formatCost(session.usage.estimated_cost, session.usage.cost_currency)}
          />
        </RuntimeSnapshotBlock>

        <RuntimeSnapshotBlock title="blocking reasons">
          {session.blocking_reasons.length > 0 ? (
            <ul className="space-y-1">
              {session.blocking_reasons.map((reason) => (
                <li key={reason} className="rounded bg-[#171717] px-2 py-1">
                  {reason}
                </li>
              ))}
            </ul>
          ) : (
            <p>暂无 blocking reason。</p>
          )}
        </RuntimeSnapshotBlock>

        <RuntimeSnapshotBlock title="workspace binding">
          <RuntimeMetaRow label="workspace_id" value={session.workspace.workspace_id ?? "未绑定"} />
          <RuntimeMetaRow
            label="workspace_path_hint"
            value={redactWorkspaceHint(session.workspace.workspace_path_hint)}
          />
          <RuntimeMetaRow label="repository_id" value={session.workspace.repository_id ?? "未绑定"} />
          <RuntimeMetaRow label="branch_name" value={session.workspace.branch_name ?? "未绑定"} />
          <RuntimeMetaRow label="worktree_id" value={session.workspace.worktree_id ?? "未绑定"} />
          <RuntimeMetaRow
            label="workspace_bound"
            value={session.workspace.workspace_bound ? "true" : "false"}
          />
        </RuntimeSnapshotBlock>
      </div>
    </div>
  );
}

function RuntimeEventStream(props: {
  events: RuntimeEventReadback[];
  loading: boolean;
  error: string | null;
}) {
  return (
    <div
      data-testid="runtime-event-stream"
      className="rounded border border-[#333333] bg-[#111111] p-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-medium text-zinc-100">append-only event stream</p>
        <StatusBadge label="append_only" tone="success" />
      </div>

      {props.loading ? (
        <RuntimePanelState testId="runtime-event-stream-loading" message="正在读取 event stream..." />
      ) : null}

      {props.error ? (
        <RuntimePanelState
          testId="runtime-event-stream-error"
          tone="error"
          message={`event stream 读取失败：${props.error}`}
        />
      ) : null}

      {!props.loading && !props.error && props.events.length === 0 ? (
        <RuntimePanelState
          testId="runtime-event-stream-empty"
          message="当前 session 暂无 runtime event。"
        />
      ) : null}

      {props.events.length > 0 ? (
        <ol className="mt-3 space-y-2">
          {props.events.map((event) => (
            <li
              key={event.event_id}
              className="rounded border border-[#333333] bg-[#171717] px-2 py-2"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-[11px] font-medium text-zinc-100">
                  {event.event_type}
                </p>
                <span className="text-[10px] text-zinc-600">
                  {formatDateTime(event.timestamp)}
                </span>
              </div>
              <p className="mt-1 text-[10px] leading-4 text-zinc-500">
                {event.payload.message ?? "无 message"}
              </p>
              <div className="mt-2 flex flex-wrap gap-1 text-[10px] text-zinc-500">
                <span className="rounded border border-[#333333] px-1.5 py-0.5">
                  state: {event.payload.state ?? "n/a"}
                </span>
                <span className="rounded border border-[#333333] px-1.5 py-0.5">
                  reason: {event.payload.reason_code ?? "n/a"}
                </span>
                <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-emerald-200">
                  append_only: {event.append_only ? "true" : "false"}
                </span>
              </div>
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}

function RuntimeSnapshotBlock(props: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded border border-[#333333] bg-[#151515] p-2">
      <p className="mb-1.5 text-[10px] font-medium uppercase tracking-[0.14em] text-zinc-600">
        {props.title}
      </p>
      <div className="grid gap-1 text-[10px] leading-4 text-zinc-500">
        {props.children}
      </div>
    </div>
  );
}

function RuntimeMetaRow(props: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 items-start justify-between gap-2">
      <span className="shrink-0 text-zinc-600">{props.label}</span>
      <span className="min-w-0 break-words text-right text-zinc-300">
        {props.value}
      </span>
    </div>
  );
}

function RuntimePanelState(props: {
  testId: string;
  message: string;
  tone?: "default" | "error";
}) {
  return (
    <div
      data-testid={props.testId}
      className={`rounded border px-3 py-2 text-xs ${
        props.tone === "error"
          ? "border-red-500/30 bg-red-500/10 text-red-300"
          : "border-dashed border-[#333333] bg-[#111111] text-zinc-500"
      }`}
    >
      {props.message}
    </div>
  );
}

function shortId(value: string) {
  return value.length > 12 ? `${value.slice(0, 8)}...${value.slice(-4)}` : value;
}

function formatStateLabel(state: string) {
  const labels: Record<string, string> = {
    requested: "已请求",
    spawning: "fake 准备中",
    running: "fake running",
    idle: "fake idle",
    completed: "已完成",
    failed: "失败",
    cancelled: "已取消",
    blocked: "已阻塞",
  };
  return labels[state] ?? state;
}

function formatNullableDate(value: string | null) {
  return value ? formatDateTime(value) : "未记录";
}

function formatNullableNumber(value: number | null) {
  return value === null ? "未记录" : String(value);
}

function formatCost(value: string | number | null, currency: string | null) {
  if (value === null) {
    return "未记录";
  }
  return currency ? `${value} ${currency}` : String(value);
}

function redactWorkspaceHint(value: string | null) {
  if (!value) {
    return "未提供";
  }
  const parts = value.split(/[\\/]+/).filter(Boolean);
  if (parts.length <= 2) {
    return `.../${parts.join("/")}`;
  }
  return `.../${parts.slice(-2).join("/")}`;
}
