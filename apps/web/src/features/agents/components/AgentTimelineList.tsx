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

export function AgentTimelineList(props: AgentTimelineListProps) {
  const [expandedMessageId, setExpandedMessageId] = useState<string | null>(null);

  return (
    <section className="pb-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h4 className="text-sm font-semibold text-slate-100">
            {props.title}
          </h4>
          <p className="mt-1 text-xs leading-5 text-slate-500">{props.description}</p>
        </div>
        <span className="text-xs text-slate-500">
          {props.messages.length} 条记录
        </span>
      </div>

      {!props.messages.length ? (
        <p className="mt-4 border-y border-dashed border-[#333333] px-1 py-5 text-sm text-slate-400">
          {props.emptyText}
        </p>
      ) : (
        <ul
          className="mt-4 max-h-[520px] space-y-0 overflow-y-auto pr-3 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-slate-700/60"
          data-testid={props.testId}
        >
          {props.messages.map((message, index) => (
            <li
              key={message.message_id}
              className="relative border-l border-[#333333] pb-5 pl-5 last:pb-0"
              data-testid={`${props.testId}-item`}
            >
              <span className="absolute -left-[5px] top-1.5 h-2.5 w-2.5 rounded-full border border-slate-500 bg-slate-950" />
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500">
                    <span>#{message.sequence_no || index + 1}</span>
                    <span>{formatDateTime(message.created_at)}</span>
                    <span>{message.role}</span>
                    <span>{message.message_type}</span>
                    <span>{message.event_type}</span>
                  </div>
                  <p className="mt-2 break-words text-sm leading-6 text-slate-100">
                    {message.content_summary}
                  </p>
                </div>
                <button
                  type="button"
                  data-testid={`${props.testId}-detail-open`}
                  onClick={() =>
                    setExpandedMessageId(
                      expandedMessageId === message.message_id ? null : message.message_id,
                    )
                  }
                  className="shrink-0 text-xs text-slate-400 transition hover:text-slate-100"
                >
                  {expandedMessageId === message.message_id ? "收起" : "展开"}
                </button>
              </div>

              {expandedMessageId === message.message_id ? (
                <div
                  data-testid={`${props.testId}-detail-modal`}
                  className="mt-3 space-y-3 border-l border-[#333333] pl-3 text-xs leading-5 text-slate-400"
                >
                  {message.content_detail ? (
                    <pre className="whitespace-pre-wrap text-xs leading-5 text-slate-300">
                      {message.content_detail}
                    </pre>
                  ) : (
                    <p className="text-xs leading-5 text-slate-500">暂无详情内容。</p>
                  )}
                  <div className="flex flex-wrap gap-x-3 gap-y-1 text-slate-500">
                    <span>阶段：{message.phase ?? "无"}</span>
                    <span>
                      状态：{message.state_from ?? "无"} → {message.state_to ?? "无"}
                    </span>
                    <span>介入：{message.intervention_type ?? "无"}</span>
                    <span>备注事件：{message.note_event_type ?? "无"}</span>
                  </div>
                  <button
                    type="button"
                    data-testid={`${props.testId}-detail-close`}
                    onClick={() => setExpandedMessageId(null)}
                    className="text-xs text-slate-500 transition hover:text-slate-200"
                  >
                    关闭详情
                  </button>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
