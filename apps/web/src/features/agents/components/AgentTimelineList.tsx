import { formatDateTime } from "../../../lib/format";
import type { AgentTimelineMessage } from "../types";

type AgentTimelineListProps = {
  title: string;
  testId: string;
  messages: AgentTimelineMessage[];
  emptyText: string;
};

export function AgentTimelineList(props: AgentTimelineListProps) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <h4 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">
        {props.title}
      </h4>
      {!props.messages.length ? (
        <p className="mt-3 text-sm text-slate-400">{props.emptyText}</p>
      ) : (
        <ul className="mt-3 space-y-3" data-testid={props.testId}>
          {props.messages.map((message) => (
            <li
              key={message.message_id}
              className="rounded-xl border border-slate-800 bg-slate-950/60 p-3"
              data-testid={`${props.testId}-item`}
            >
              <div className="flex flex-wrap gap-2 text-xs text-cyan-200">
                <span>#{message.sequence_no}</span>
                <span>{message.role}</span>
                <span>{message.message_type}</span>
                <span>{message.event_type}</span>
              </div>
              <p className="mt-2 text-sm text-slate-100">{message.content_summary}</p>
              {message.content_detail ? (
                <p className="mt-1 text-xs text-slate-400 whitespace-pre-wrap">
                  {message.content_detail}
                </p>
              ) : null}
              <div className="mt-2 text-xs text-slate-500">
                phase={message.phase ?? "n/a"}; state={message.state_from ?? "n/a"} -&gt; {message.state_to ?? "n/a"}; intervention={message.intervention_type ?? "none"}; note={message.note_event_type ?? "none"}; at={formatDateTime(message.created_at)}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}