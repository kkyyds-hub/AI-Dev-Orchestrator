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
      className="flex flex-col rounded-lg border border-[#333333] bg-[#1a1a1a] p-6 lg:min-h-[600px]"
    >
      {/* 顶部：标题 + 短说明 */}
      <div className="shrink-0 mb-6">
        <h2 className="text-xl font-semibold text-zinc-100">AI 项目主管</h2>
        <p className="mt-2 text-sm leading-relaxed text-zinc-400">
          向 AI 项目主管提出目标，由我负责生成作战计划、拆分任务、分配 Agent、监督运行、识别阻塞并提出调整建议。
        </p>
      </div>

      {/* 中部：空状态引导区 / 对话历史占位 */}
      <div className="flex-1 flex flex-col items-center justify-center mb-6 min-h-[200px]">
        <div className="w-full max-w-lg text-center">
          <p className="text-sm text-zinc-500 mb-4">
            暂无对话记录。你可以从以下示例开始，或直接输入你的项目目标：
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

      {/* 底部：输入框 + 发送按钮 */}
      <div className="shrink-0 space-y-3">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="描述你的项目目标或当前遇到的问题..."
          rows={3}
          className="w-full resize-none rounded-md border border-[#333333] bg-[#111111] px-4 py-3 text-sm text-zinc-200 placeholder:text-zinc-600 focus:border-zinc-500 focus:outline-none"
        />

        <div className="flex items-center gap-3">
          <button
            type="button"
            disabled
            className="rounded-md border border-[#333333] bg-transparent px-4 py-2 text-sm font-medium text-zinc-600 cursor-not-allowed"
          >
            发送给 AI 项目主管
          </button>
          <span className="text-xs text-zinc-600">
            待接入真实 AI 项目主管会话接口
          </span>
        </div>
      </div>
    </section>
  );
}
