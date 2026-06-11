import { Bot } from "lucide-react";

import type { MessageCard, MessageCardType, MockMessage } from "../mockInteractions";

const cardLabelMap: Record<MessageCardType, string> = {
  draft: "主管建议",
  review: "审查结果",
  progress: "进度汇报",
  next_step: "下一步指令",
};

function MessageCardBlock({ card }: { card: MessageCard }) {
  const label = cardLabelMap[card.type] ?? card.type;

  return (
    <div className="mt-3 max-w-[640px] rounded-2xl border border-[#2A2A2A] bg-[#0B0B0B] p-4">
      {/* semantic label */}
      <div className="mb-3 text-[11px] font-medium uppercase tracking-[0.08em] text-[#8A8A8A]">
        {label}
      </div>

      {/* title + status */}
      <div className="mb-2 flex items-center gap-2">
        <span className="text-[15px] font-semibold text-white">{card.title}</span>
        <span className="inline-flex items-center gap-1 rounded-full border border-[#2A2A2A] px-2 py-0.5 text-[10px] text-[#8A8A8A]">
          {card.status}
        </span>
      </div>

      {/* summary */}
      <p className="mb-3 text-[13px] leading-[1.6] text-[#C7C7C7]">{card.summary}</p>

      {/* items */}
      <ul className="mb-4 space-y-1">
        {card.items.map((item, i) => (
          <li key={i} className="flex items-start gap-2 text-[13px] text-[#8A8A8A]">
            <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-[#5F5F5F]" />
            {item}
          </li>
        ))}
      </ul>

      {/* actions */}
      {(card.primaryAction || card.secondaryAction) && (
        <div className="flex items-center gap-2">
          {card.primaryAction && (
            <button className="rounded-full bg-white px-3 py-1.5 text-xs font-medium text-black transition-all active:scale-[0.97]">
              {card.primaryAction}
            </button>
          )}
          {card.secondaryAction && (
            <button className="rounded-full px-3 py-1.5 text-xs text-[#8A8A8A] transition-colors hover:bg-[#222222] hover:text-white">
              {card.secondaryAction}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function ConversationMessages({
  messages,
}: {
  messages: MockMessage[];
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-5 pb-4 pt-6 md:px-8">
      {messages.map((msg, i) => {
        const isAssistant = msg.role === "assistant";

        return (
          <div
            key={i}
            className={`mb-6 flex gap-3 ${isAssistant ? "justify-start" : "justify-end"}`}
          >
            {isAssistant ? (
              <>
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#222222]">
                  <Bot className="h-4 w-4 text-[#C7C7C7]" />
                </div>
                <div className="min-w-0 max-w-[760px]">
                  <div className="mb-1 flex items-center gap-2">
                    <span className="text-sm font-medium text-white">AI 项目主管</span>
                    <span className="text-xs text-[#5F5F5F]">{msg.time}</span>
                  </div>
                  {msg.content && (
                    <div className="whitespace-pre-wrap text-sm leading-6 text-[#C7C7C7]">
                      {msg.content}
                    </div>
                  )}
                  {msg.card && <MessageCardBlock card={msg.card} />}
                </div>
              </>
            ) : (
              <>
                <div className="min-w-0 max-w-[640px]">
                  <div className="mb-1 flex items-center justify-end gap-2">
                    <span className="text-xs text-[#5F5F5F]">{msg.time}</span>
                    <span className="text-sm font-medium text-white">kk</span>
                  </div>
                  <div className="whitespace-pre-wrap rounded-2xl bg-[#222222] px-4 py-3 text-sm leading-6 text-white">
                    {msg.content}
                  </div>
                </div>
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#2C2C2C] text-xs font-medium text-white">
                  K
                </div>
              </>
            )}
          </div>
        );
      })}

      {messages.length === 0 && (
        <div className="flex flex-1 items-center justify-center">
          <p className="text-sm text-[#8A8A8A]">暂无消息</p>
        </div>
      )}
    </div>
  );
}
