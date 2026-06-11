import { Bot } from "lucide-react";

import type { MockMessage } from "../mockInteractions";

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
                {/* AI avatar */}
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#1F1F1F]">
                  <Bot className="h-4 w-4 text-[#C7C7C7]" />
                </div>
                <div className="min-w-0 max-w-[760px]">
                  <div className="mb-1 flex items-center gap-2">
                    <span className="text-sm font-medium text-white">AI 项目主管</span>
                    <span className="text-xs text-[#5F5F5F]">{msg.time}</span>
                  </div>
                  <div className="whitespace-pre-wrap text-sm leading-6 text-[#C7C7C7]">
                    {msg.content}
                  </div>
                </div>
              </>
            ) : (
              <>
                <div className="min-w-0 max-w-[640px]">
                  <div className="mb-1 flex items-center justify-end gap-2">
                    <span className="text-xs text-[#5F5F5F]">{msg.time}</span>
                    <span className="text-sm font-medium text-white">kk</span>
                  </div>
                  <div className="whitespace-pre-wrap rounded-2xl bg-[#1F1F1F] px-4 py-3 text-sm leading-6 text-white">
                    {msg.content}
                  </div>
                </div>
                {/* User avatar */}
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#2A2A2A] text-xs font-medium text-white">
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
