import { Bot } from "lucide-react";

import type { MockMessage } from "../mockInteractions";
import { StatusPill } from "./DataListPreview";

export function ConversationHeader({
  projectName,
  conversationTitle,
  status,
}: {
  projectName: string;
  conversationTitle: string;
  status: string;
}) {
  return (
    <div className="flex h-14 shrink-0 items-center justify-between border-b border-[#2A2A2A] px-5 md:h-16 md:px-8">
      <div className="text-sm text-[#8A8A8A]">
        <span className="text-[#C7C7C7]">{projectName}</span>
        <span className="mx-2 text-[#5F5F5F]">/</span>
        {conversationTitle}
        <span className="mx-2 text-[#5F5F5F]">/</span>
        <StatusPill status={status} />
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
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-5 pb-4 pt-4 md:px-8">
      {messages.map((msg, i) => (
        <div key={i} className="mb-5 flex gap-4">
          {msg.role === "assistant" ? (
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#1F1F1F]">
              <Bot className="h-4 w-4 text-[#C7C7C7]" />
            </div>
          ) : (
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#2A2A2A] text-xs font-medium text-white">
              K
            </div>
          )}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-medium text-white">
                {msg.role === "assistant" ? "AI 项目主管" : "kk"}
              </span>
              <span className="text-xs text-[#5F5F5F]">{msg.time}</span>
            </div>
            <div className="whitespace-pre-wrap text-sm leading-6 text-[#C7C7C7]">{msg.content}</div>
          </div>
        </div>
      ))}

      {messages.length === 0 && (
        <div className="flex flex-1 items-center justify-center">
          <p className="text-sm text-[#8A8A8A]">暂无消息</p>
        </div>
      )}
    </div>
  );
}
