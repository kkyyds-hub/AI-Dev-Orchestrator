import { useState } from "react";

const EXAMPLE_QUESTIONS = [
  "帮我分析当前项目的阻塞原因",
  "生成一份作战计划建议",
  "当前哪些任务需要我确认？",
  "重新评估项目风险并给出调整建议",
];

export function DirectorChatEntry() {
  const [draft, setDraft] = useState("");

  const handleExampleClick = (question: string) => {
    setDraft(question);
  };

  return (
    <section
      data-testid="director-chat-entry"
      className="flex flex-col rounded-lg border border-[#333333] bg-[#1a1a1a] p-6 lg:min-h-[calc(100vh-220px)]"
    >
      {/* 顶部：标题 + 极短说明 */}
      <div className="shrink-0 mb-5">
        <h2 className="text-xl font-semibold text-zinc-100">AI 项目主管</h2>
        <p className="mt-1.5 text-sm text-zinc-500">
          提出目标、查看阻塞、调整计划。
        </p>
      </div>

      {/* 中部：空状态引导区 */}
      <div className="flex-1 flex flex-col items-center justify-center mb-5 min-h-[160px]">
        <div className="w-full max-w-lg text-center">
          <p className="text-sm text-zinc-600 mb-4">
            暂无对话记录，输入目标开始
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {EXAMPLE_QUESTIONS.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => handleExampleClick(q)}
                className="text-left rounded border border-[#333333] px-3 py-2 text-xs text-zinc-400 transition hover:border-zinc-500 hover:bg-[#222222] hover:text-zinc-200"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 底部：输入框 composer（发送按钮嵌入右下角） */}
      <div className="shrink-0">
        <div className="relative rounded-md border border-[#333333] bg-[#111111] focus-within:border-zinc-500">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="描述你的项目目标或当前遇到的问题..."
            rows={3}
            className="w-full resize-none bg-transparent px-4 py-3 pr-24 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none"
          />
          <div className="absolute right-2 bottom-2 flex items-center gap-2">
            <button
              type="button"
              disabled
              title="会话接口待接入，暂不可发送"
              className="rounded border border-[#333333] bg-[#1a1a1a] px-3 py-1 text-xs text-zinc-600 cursor-not-allowed"
            >
              发送
            </button>
          </div>
        </div>
        <p className="mt-1.5 text-[10px] text-zinc-700">
          会话接口待接入，暂不可发送
        </p>
      </div>
    </section>
  );
}
