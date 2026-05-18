import { useState } from "react";

type DirectorChatEntryProps = {
  isRunWorkerOncePending: boolean;
  onRunWorkerOnce: () => void;
  workerOnceData: unknown;
  workerOnceIsError: boolean;
  workerOnceErrorMessage: string | null;
};

export function DirectorChatEntry({
  isRunWorkerOncePending,
  onRunWorkerOnce,
  workerOnceData,
  workerOnceIsError,
  workerOnceErrorMessage,
}: DirectorChatEntryProps) {
  const [draft, setDraft] = useState("");

  return (
    <section
      data-testid="director-chat-entry"
      className="rounded-lg border border-[#333333] bg-[#1a1a1a] p-6"
    >
      <div className="mb-4">
        <h2 className="text-xl font-semibold text-zinc-100">AI 项目主管</h2>
        <p className="mt-2 text-sm leading-relaxed text-zinc-400">
          向 AI 项目主管提出目标，由我负责生成作战计划、拆分任务、分配
          Agent、监督运行、识别阻塞并提出调整建议。
        </p>
      </div>

      <div className="space-y-4">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="描述你的项目目标或当前遇到的问题…"
          rows={3}
          className="w-full resize-none rounded-md border border-[#333333] bg-[#111111] px-4 py-3 text-sm text-zinc-200 placeholder:text-zinc-600 focus:border-zinc-500 focus:outline-none"
        />

        <div className="flex flex-wrap items-center gap-3">
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

        <div className="border-t border-[#333333] pt-4">
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              data-testid="director-run-worker-once"
              onClick={onRunWorkerOnce}
              disabled={isRunWorkerOncePending}
              className="rounded-md border border-zinc-200 bg-transparent px-4 py-2 text-sm font-medium text-zinc-100 transition hover:bg-[#2f2f2f] disabled:cursor-not-allowed disabled:border-[#333333] disabled:text-zinc-600"
            >
              {isRunWorkerOncePending ? "调度中…" : "触发 Worker 单次调度"}
            </button>
            <span className="text-xs text-zinc-500">
              立即触发一次 Worker 调度执行
            </span>
          </div>

          {workerOnceData != null && !workerOnceIsError && (
            <p className="mt-2 text-xs text-green-500">调度已触发，请查看任务页或运行页了解进展。</p>
          )}
          {workerOnceIsError && workerOnceErrorMessage != null && (
            <p className="mt-2 text-xs text-red-400">调度失败：{workerOnceErrorMessage}</p>
          )}
        </div>
      </div>
    </section>
  );
}
