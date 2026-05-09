import { useState } from "react";

import { formatDateTime } from "../../../lib/format";
import type { AgentTimelineMessage } from "../types";

type AgentTimelineListProps = {
  title: string;
  description: string;
  testId: string;
  messages: AgentTimelineMessage[];
  emptyText: string;
};

function FieldRow(props: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="min-w-0 rounded-xl border border-slate-800/80 bg-slate-950/55 px-3 py-2">
      <dt className="text-[11px] text-slate-500">{props.label}</dt>
      <dd className="mt-1 break-all text-xs text-slate-200">{props.value ?? "无"}</dd>
    </div>
  );
}

export function AgentTimelineList(props: AgentTimelineListProps) {
  const [detailMessage, setDetailMessage] = useState<AgentTimelineMessage | null>(null);

  return (
    <section className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-4 shadow-lg shadow-slate-950/15 sm:p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h4 className="text-sm font-semibold tracking-[0.16em] text-slate-200">
            {props.title}
          </h4>
          <p className="mt-2 text-xs leading-5 text-slate-400">{props.description}</p>
        </div>
        <span className="rounded-full border border-slate-700/70 px-2.5 py-1 text-xs text-slate-300">
          {props.messages.length} 条
        </span>
      </div>

      {!props.messages.length ? (
        <p className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/45 px-4 py-5 text-sm text-slate-400">
          {props.emptyText}
        </p>
      ) : (
        <ul className="mt-4 space-y-3" data-testid={props.testId}>
          {props.messages.map((message) => (
            <li
              key={message.message_id}
              className="rounded-2xl border border-slate-800/90 bg-slate-950/55 p-4 transition hover:border-slate-700/90 hover:bg-slate-950/75"
              data-testid={`${props.testId}-item`}
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap gap-2 text-xs text-cyan-100">
                    <span className="rounded-full bg-cyan-400/10 px-2 py-1">序号 #{message.sequence_no}</span>
                    <span className="rounded-full bg-slate-800/80 px-2 py-1">角色 {message.role}</span>
                    <span className="rounded-full bg-slate-800/80 px-2 py-1">类型 {message.message_type}</span>
                    <span className="rounded-full bg-slate-800/80 px-2 py-1">事件 {message.event_type}</span>
                  </div>
                  <p className="mt-3 break-words text-sm leading-6 text-slate-100">
                    {message.content_summary}
                  </p>
                </div>
                <button
                  type="button"
                  data-testid={`${props.testId}-detail-open`}
                  onClick={() => setDetailMessage(message)}
                  className="shrink-0 rounded-full border border-slate-700 bg-slate-900/80 px-3 py-1.5 text-xs text-slate-200 transition hover:border-cyan-300/50 hover:text-cyan-100 focus:outline-none focus:ring-2 focus:ring-cyan-300/35"
                >
                  查看详情
                </button>
              </div>
              {message.content_detail ? (
                <p className="mt-3 max-h-28 overflow-auto whitespace-pre-wrap rounded-xl border border-slate-800/80 bg-slate-950/70 px-3 py-2 text-xs leading-5 text-slate-400">
                  {message.content_detail}
                </p>
              ) : null}
              <div className="mt-3 grid gap-2 text-xs text-slate-500 sm:grid-cols-2 xl:grid-cols-4">
                <span>阶段：{message.phase ?? "无"}</span>
                <span>
                  状态：{message.state_from ?? "无"} → {message.state_to ?? "无"}
                </span>
                <span>介入：{message.intervention_type ?? "无"}</span>
                <span>时间：{formatDateTime(message.created_at)}</span>
              </div>
            </li>
          ))}
        </ul>
      )}

      {detailMessage ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby={`${props.testId}-detail-title`}
          data-testid={`${props.testId}-detail-modal`}
        >
          <div className="max-h-[86vh] w-full max-w-3xl overflow-auto rounded-3xl border border-slate-700 bg-slate-950 p-5 shadow-2xl shadow-slate-950/60">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs tracking-[0.18em] text-cyan-200">消息详情</p>
                <h5
                  id={`${props.testId}-detail-title`}
                  className="mt-2 text-xl font-semibold text-slate-50"
                >
                  {props.title} #{detailMessage.sequence_no}
                </h5>
              </div>
              <button
                type="button"
                data-testid={`${props.testId}-detail-close`}
                onClick={() => setDetailMessage(null)}
                className="rounded-full border border-slate-700 px-3 py-1.5 text-sm text-slate-200 transition hover:border-cyan-300/50 hover:text-cyan-100 focus:outline-none focus:ring-2 focus:ring-cyan-300/35"
              >
                关闭
              </button>
            </div>

            <p className="mt-4 rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-3 text-sm leading-6 text-slate-100">
              {detailMessage.content_summary}
            </p>
            {detailMessage.content_detail ? (
              <pre className="mt-3 whitespace-pre-wrap rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-3 text-xs leading-5 text-slate-300">
                {detailMessage.content_detail}
              </pre>
            ) : null}

            <dl className="mt-4 grid gap-2 sm:grid-cols-2">
              <FieldRow label="message_id" value={detailMessage.message_id} />
              <FieldRow label="session_id" value={detailMessage.session_id} />
              <FieldRow label="task_id" value={detailMessage.task_id} />
              <FieldRow label="run_id" value={detailMessage.run_id} />
              <FieldRow label="role" value={detailMessage.role} />
              <FieldRow label="message_type" value={detailMessage.message_type} />
              <FieldRow label="event_type" value={detailMessage.event_type} />
              <FieldRow label="phase" value={detailMessage.phase} />
              <FieldRow label="state_from" value={detailMessage.state_from} />
              <FieldRow label="state_to" value={detailMessage.state_to} />
              <FieldRow label="intervention_type" value={detailMessage.intervention_type} />
              <FieldRow label="note_event_type" value={detailMessage.note_event_type} />
              <FieldRow label="context_checkpoint_id" value={detailMessage.context_checkpoint_id} />
              <FieldRow
                label="context_rehydrated"
                value={
                  detailMessage.context_rehydrated === null
                    ? null
                    : String(detailMessage.context_rehydrated)
                }
              />
              <FieldRow label="created_at" value={formatDateTime(detailMessage.created_at)} />
            </dl>
          </div>
        </div>
      ) : null}
    </section>
  );
}