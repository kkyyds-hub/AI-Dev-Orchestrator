import { useState } from "react";
import type { KeyboardEvent } from "react";

import { useCreateProjectDirectorSession } from "../../../features/project-director/hooks";
import type { ProjectDirectorSession } from "../../../features/project-director/types";

const EXAMPLE_QUESTIONS = [
  "帮我分析当前项目的阻塞原因",
  "生成一份作战计划建议",
  "当前哪些任务需要我确认？",
  "重新评估项目风险并给出调整建议",
];

interface DirectorChatEntryProps {
  selectedProjectId: string;
  selectedProjectName: string;
}

export function DirectorChatEntry({
  selectedProjectId,
  selectedProjectName,
}: DirectorChatEntryProps) {
  const [draft, setDraft] = useState("");
  const [session, setSession] = useState<ProjectDirectorSession | null>(null);
  const createSessionMutation = useCreateProjectDirectorSession();

  const scopedProjectId = selectedProjectId === "all" ? null : selectedProjectId;
  const trimmedDraft = draft.trim();
  const canSend = trimmedDraft.length > 0 && !createSessionMutation.isPending;

  const handleExampleClick = (question: string) => {
    setDraft(question);
  };

  const handleSubmit = async () => {
    if (!canSend) {
      return;
    }

    try {
      const createdSession = await createSessionMutation.mutateAsync({
        goal_text: trimmedDraft,
        project_id: scopedProjectId,
        constraints: "",
      });

      setSession(createdSession);
      setDraft("");
    } catch {
      // Error details are rendered from the mutation state below.
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      void handleSubmit();
    }
  };

  return (
    <section
      data-testid="director-chat-entry"
      className="flex flex-col rounded-lg border border-[#333333] bg-[#1a1a1a] p-6 lg:min-h-[calc(100vh-220px)]"
    >
      {/* 顶部：标题 + 当前项目上下文 */}
      <div className="shrink-0 mb-5">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-xl font-semibold text-zinc-100">AI 项目主管</h2>
            <p className="mt-1.5 text-sm text-zinc-500">
              提出目标、查看阻塞、调整计划。当前 R1 仅接入目标提交与澄清问题读取。
            </p>
          </div>
          <span className="inline-flex w-fit max-w-full items-center rounded-full border border-[#333333] bg-[#111111] px-3 py-1 text-xs text-zinc-400">
            项目上下文：{selectedProjectName}
          </span>
        </div>
      </div>

      {/* 中部：会话/空状态 */}
      <div className="flex-1 mb-5 min-h-[160px] overflow-y-auto">
        {session ? (
          <div className="space-y-4">
            <div className="rounded-lg border border-[#333333] bg-[#111111] p-4">
              <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
                <span>会话 {session.id.slice(0, 8)}</span>
                <span className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-amber-300">
                  {session.status}
                </span>
                <span className="rounded border border-[#333333] px-2 py-0.5 text-zinc-400">
                  Gate: {session.gate_conclusion}
                </span>
              </div>
              <p className="text-sm text-zinc-300 whitespace-pre-wrap">
                {session.goal_text}
              </p>
            </div>

            <div className="rounded-lg border border-blue-500/20 bg-blue-500/5 p-4">
              <h3 className="text-sm font-medium text-blue-200">
                需要你澄清的问题
              </h3>
              {session.clarifying_questions.length > 0 ? (
                <ol className="mt-3 space-y-3">
                  {session.clarifying_questions.map((question, index) => (
                    <li
                      key={question.id}
                      className="rounded border border-[#333333] bg-[#171717] p-3"
                    >
                      <div className="flex items-start gap-2">
                        <span className="mt-0.5 rounded bg-blue-500/10 px-1.5 py-0.5 text-[10px] text-blue-300">
                          Q{index + 1}
                        </span>
                        <div className="min-w-0">
                          <p className="text-sm text-zinc-200">
                            {question.question}
                            {question.required ? (
                              <span className="ml-1 text-[10px] text-amber-300">
                                必答
                              </span>
                            ) : null}
                          </p>
                          {question.hint ? (
                            <p className="mt-1 text-xs text-zinc-500">
                              {question.hint}
                            </p>
                          ) : null}
                        </div>
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="mt-2 text-sm text-zinc-500">后端未返回澄清问题。</p>
              )}
            </div>

            <div className="rounded border border-[#333333] bg-[#111111] p-3 text-xs text-zinc-500">
              <p>下一步：{session.next_action}</p>
              {session.forbidden_actions.length > 0 ? (
                <p className="mt-1">
                  R1 边界：{session.forbidden_actions.join(" / ")}
                </p>
              ) : null}
            </div>
          </div>
        ) : (
          <div className="flex h-full min-h-[260px] flex-col items-center justify-center">
            <div className="w-full max-w-lg text-center">
              <p className="text-sm text-zinc-600 mb-4">
                暂无对话记录，输入目标开始。发送后会创建 Project Director
                会话并读取澄清问题。
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
        )}
      </div>

      {/* 底部：输入框 composer */}
      <div className="shrink-0">
        <div className="relative rounded-md border border-[#333333] bg-[#111111] focus-within:border-zinc-500">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="描述你的项目目标或当前遇到的问题..."
            rows={3}
            className="w-full resize-none bg-transparent px-4 py-3 pr-24 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none"
          />
          <div className="absolute right-2 bottom-2 flex items-center gap-2">
            <button
              type="button"
              disabled={!canSend}
              onClick={() => {
                void handleSubmit();
              }}
              className="rounded border border-[#3f3f46] bg-zinc-100 px-3 py-1 text-xs font-medium text-zinc-950 transition hover:bg-white disabled:cursor-not-allowed disabled:border-[#333333] disabled:bg-[#1a1a1a] disabled:text-zinc-600"
            >
              {createSessionMutation.isPending ? "发送中..." : "发送"}
            </button>
          </div>
        </div>
        <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2 text-[10px] text-zinc-700">
          <p>Ctrl/⌘ + Enter 发送；当前只会创建会话并读取澄清问题。</p>
          {scopedProjectId ? <p>project_id: {scopedProjectId}</p> : <p>全局项目上下文</p>}
        </div>
        {createSessionMutation.isError ? (
          <p className="mt-2 rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
            {createSessionMutation.error.message}
          </p>
        ) : null}
      </div>
    </section>
  );
}
