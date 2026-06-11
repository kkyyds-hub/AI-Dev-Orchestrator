import { Bot, CheckCircle2, FileText, TrendingUp } from "lucide-react";

import type { MessageCard, MockMessage } from "../mockInteractions";
import { Badge } from "./ui";

function MessageCardBlock({ card }: { card: MessageCard }) {
  const iconMap = {
    draft: FileText,
    review: CheckCircle2,
    progress: TrendingUp,
  };
  const Icon = iconMap[card.type] ?? FileText;

  return (
    <div className="mt-3 rounded-2xl border border-[#2A2A2A] bg-[#171717] p-4 max-w-[640px]">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="h-4 w-4 text-[#C7C7C7]" />
        <span className="text-sm font-semibold text-white">{card.title}</span>
        <Badge className="h-5 text-[11px]">{card.status}</Badge>
      </div>
      <p className="text-sm leading-6 text-[#C7C7C7] mb-3">{card.summary}</p>
      <ul className="space-y-1 mb-3">
        {card.items.map((item, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-[#8A8A8A]">
            <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-[#8A8A8A]" />
            {item}
          </li>
        ))}
      </ul>
      <div className="flex items-center gap-2">
        <button className="rounded-full bg-white px-3 py-1.5 text-xs font-medium text-black transition-all active:scale-[0.98]">
          {card.primaryAction}
        </button>
        {card.secondaryAction && (
          <button className="rounded-full px-3 py-1.5 text-xs text-[#8A8A8A] transition-colors hover:bg-[#2C2C2C] hover:text-white">
            {card.secondaryAction}
          </button>
        )}
      </div>
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
