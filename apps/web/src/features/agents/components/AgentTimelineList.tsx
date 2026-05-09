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
  return (
    <section className="border-b border-[#333333] pb-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h4 className="text-sm font-medium text-slate-100">
            {props.title}
          </h4>
          <p className="mt-2 text-xs leading-5 text-slate-400">{props.description}</p>
        </div>
        <span className="text-xs text-slate-500">
          {props.messages.length} 条
        </span>
      </div>

      {!props.messages.length ? (
        <p className="mt-4 border-y border-dashed border-[#333333] px-1 py-5 text-sm text-slate-400">
          {props.emptyText}
        </p>
      ) : (
        <ul className="mt-3 divide-y divide-[#333333]" data-testid={props.testId}>
          {props.messages.map((message) => (
            <li
              key={message.message_id}
              className="py-4"
              data-testid={`${props.testId}-item`}
            >
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500">
                    <span>#{message.sequence_no}</span>
                    <span>角色：{message.role}</span>
                    <span>类型：{message.message_type}</span>
                    <span>事件：{message.event_type}</span>
                  </div>
                  <p className="mt-2 break-words text-sm leading-6 text-slate-100">
                    {message.content_summary}
                  </p>
                </div>
              </div>
              <details className="mt-2 text-xs text-slate-400">
                <summary
                  data-testid={`${props.testId}-detail-open`}
                  className="cursor-pointer select-none text-slate-400 transition hover:text-slate-200"
                >
                  查看详情
                </summary>
                <div
                  data-testid={`${props.testId}-detail-modal`}
                  className="mt-2 space-y-3 border-l border-[#333333] pl-3"
                >
                  {message.content_detail ? (
                    <pre className="whitespace-pre-wrap text-xs leading-5 text-slate-300">
                      {message.content_detail}
                    </pre>
                  ) : (
                    <p className="text-xs leading-5 text-slate-500">暂无详情内容。</p>
                  )}
                  <span
                    data-testid={`${props.testId}-detail-close`}
                    className="block text-[11px] text-slate-500"
                  >
                    再次点击“查看详情”可收起。
                  </span>
                </div>
              </details>
              <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500">
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
    </section>
  );
}
