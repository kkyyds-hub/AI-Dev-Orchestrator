import { useEffect, useState } from "react";
import type { KeyboardEvent } from "react";

import {
  useConfirmProjectDirectorGoal,
  useConfirmProjectDirectorPlanVersion,
  useCreateProjectDirectorPlanVersion,
  useCreateProjectDirectorSession,
  useSubmitProjectDirectorAnswers,
} from "../../../features/project-director/hooks";
import type {
  ProjectDirectorPlanVersion,
  ProjectDirectorSession,
} from "../../../features/project-director/types";

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
  const [planVersion, setPlanVersion] =
    useState<ProjectDirectorPlanVersion | null>(null);
  const [answerDrafts, setAnswerDrafts] = useState<Record<string, string>>({});
  const createSessionMutation = useCreateProjectDirectorSession();
  const submitAnswersMutation = useSubmitProjectDirectorAnswers();
  const confirmGoalMutation = useConfirmProjectDirectorGoal();
  const createPlanVersionMutation = useCreateProjectDirectorPlanVersion();
  const confirmPlanVersionMutation = useConfirmProjectDirectorPlanVersion();

  const scopedProjectId = selectedProjectId === "all" ? null : selectedProjectId;
  const trimmedDraft = draft.trim();
  const isMutating =
    createSessionMutation.isPending ||
    submitAnswersMutation.isPending ||
    confirmGoalMutation.isPending ||
    createPlanVersionMutation.isPending ||
    confirmPlanVersionMutation.isPending;
  const canSend = trimmedDraft.length > 0 && !isMutating;
  const requiredQuestions =
    session?.clarifying_questions.filter((question) => question.required) ?? [];
  const requiredAnswersReady = requiredQuestions.every(
    (question) => (answerDrafts[question.id] ?? "").trim().length > 0,
  );
  const canSubmitAnswers =
    session?.status === "clarifying" &&
    session.clarifying_questions.length > 0 &&
    requiredAnswersReady &&
    !submitAnswersMutation.isPending;
  const canConfirmGoal =
    session?.status === "ready_to_confirm" && !confirmGoalMutation.isPending;
  const canCreatePlanVersion =
    session?.status === "confirmed" &&
    !planVersion &&
    !createPlanVersionMutation.isPending;
  const canConfirmPlanVersion =
    planVersion?.status === "pending_confirmation" &&
    !confirmPlanVersionMutation.isPending;

  useEffect(() => {
    if (!session) {
      setAnswerDrafts({});
      return;
    }

    setAnswerDrafts(
      Object.fromEntries(
        session.clarifying_answers.map((answer) => [
          answer.question_id,
          answer.answer,
        ]),
      ),
    );
  }, [session]);

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

  const handleAnswerChange = (questionId: string, answer: string) => {
    setAnswerDrafts((current) => ({
      ...current,
      [questionId]: answer,
    }));
  };

  const handleSubmitAnswers = async () => {
    if (!session || !canSubmitAnswers) {
      return;
    }

    const answers = session.clarifying_questions
      .map((question) => ({
        question_id: question.id,
        answer: (answerDrafts[question.id] ?? "").trim(),
      }))
      .filter((answer) => answer.answer.length > 0);

    try {
      const updatedSession = await submitAnswersMutation.mutateAsync({
        sessionId: session.id,
        answers,
      });
      setSession(updatedSession);
    } catch {
      // Error details are rendered from the mutation state below.
    }
  };

  const handleConfirmGoal = async () => {
    if (!session || !canConfirmGoal) {
      return;
    }

    try {
      const updatedSession = await confirmGoalMutation.mutateAsync({
        sessionId: session.id,
      });
      setSession(updatedSession);
      setPlanVersion(null);
    } catch {
      // Error details are rendered from the mutation state below.
    }
  };

  const handleCreatePlanVersion = async () => {
    if (!session || !canCreatePlanVersion) {
      return;
    }

    try {
      const createdPlanVersion = await createPlanVersionMutation.mutateAsync({
        sessionId: session.id,
      });
      setPlanVersion(createdPlanVersion);
    } catch {
      // Error details are rendered from the mutation state below.
    }
  };

  const handleConfirmPlanVersion = async () => {
    if (!planVersion || !canConfirmPlanVersion) {
      return;
    }

    try {
      const confirmedPlanVersion =
        await confirmPlanVersionMutation.mutateAsync({
          planVersionId: planVersion.id,
        });
      setPlanVersion(confirmedPlanVersion);
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
              提出目标、查看阻塞、调整计划。当前 R1-D 仅接入作战计划确认，不创建任务或调度 Worker。
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
                          {session.status === "clarifying" ? (
                            <textarea
                              value={answerDrafts[question.id] ?? ""}
                              onChange={(event) =>
                                handleAnswerChange(question.id, event.target.value)
                              }
                              rows={2}
                              placeholder="填写你的澄清回答..."
                              className="mt-3 w-full resize-y rounded border border-[#333333] bg-[#101010] px-3 py-2 text-xs text-zinc-200 placeholder:text-zinc-600 focus:border-blue-500/50 focus:outline-none"
                            />
                          ) : (
                            <p className="mt-3 rounded border border-[#333333] bg-[#101010] px-3 py-2 text-xs text-zinc-400">
                              回答：
                              {session.clarifying_answers.find(
                                (answer) => answer.question_id === question.id,
                              )?.answer ?? "未提交"}
                            </p>
                          )}
                        </div>
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="mt-2 text-sm text-zinc-500">后端未返回澄清问题。</p>
              )}
              {session.status === "clarifying" ? (
                <div className="mt-4 flex flex-col gap-2 border-t border-blue-500/10 pt-4 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-xs text-zinc-500">
                    回答全部必答问题后，将提交到后端进入“待确认目标”状态。
                  </p>
                  <button
                    type="button"
                    disabled={!canSubmitAnswers}
                    onClick={() => {
                      void handleSubmitAnswers();
                    }}
                    className="rounded border border-blue-500/40 bg-blue-500/10 px-3 py-1.5 text-xs font-medium text-blue-200 transition hover:bg-blue-500/20 disabled:cursor-not-allowed disabled:border-[#333333] disabled:bg-[#171717] disabled:text-zinc-600"
                  >
                    {submitAnswersMutation.isPending ? "提交回答中..." : "提交澄清回答"}
                  </button>
                </div>
              ) : null}
            </div>

            {session.status === "ready_to_confirm" ||
            session.status === "confirmed" ? (
              <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <h3 className="text-sm font-medium text-emerald-200">
                      目标摘要
                    </h3>
                    <p className="mt-2 whitespace-pre-wrap text-sm text-zinc-300">
                      {session.goal_summary || "后端尚未返回目标摘要。"}
                    </p>
                    <p className="mt-2 text-xs text-zinc-500">
                      R1-D 仅在作战计划生成后允许用户确认计划；不会创建任务或调度 Worker。
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-col gap-2 sm:items-end">
                    <button
                      type="button"
                      disabled={!canConfirmGoal}
                      onClick={() => {
                        void handleConfirmGoal();
                      }}
                      className="rounded border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-200 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:border-[#333333] disabled:bg-[#171717] disabled:text-zinc-600"
                    >
                      {session.status === "confirmed"
                        ? "目标已确认"
                        : confirmGoalMutation.isPending
                          ? "确认中..."
                          : "确认目标"}
                    </button>
                    {session.status === "confirmed" ? (
                      <button
                        type="button"
                        disabled={!canCreatePlanVersion}
                        onClick={() => {
                          void handleCreatePlanVersion();
                        }}
                        className="rounded border border-violet-500/40 bg-violet-500/10 px-3 py-1.5 text-xs font-medium text-violet-200 transition hover:bg-violet-500/20 disabled:cursor-not-allowed disabled:border-[#333333] disabled:bg-[#171717] disabled:text-zinc-600"
                      >
                        {planVersion
                          ? "作战计划已生成"
                          : createPlanVersionMutation.isPending
                            ? "生成计划中..."
                            : "生成作战计划"}
                      </button>
                    ) : null}
                  </div>
                </div>
                {session.confirmed_at ? (
                  <p className="mt-3 text-xs text-emerald-300/80">
                    确认时间：{session.confirmed_at}
                  </p>
                ) : null}
              </div>
            ) : null}

            {planVersion ? (
              <div className="rounded-lg border border-violet-500/20 bg-violet-500/5 p-4">
                <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-500">
                  <span>计划版本 v{planVersion.version_no}</span>
                  <span className="rounded border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-violet-200">
                    {planVersion.status}
                  </span>
                  <span className="rounded border border-[#333333] px-2 py-0.5 text-zinc-400">
                    Gate: {planVersion.gate_conclusion}
                  </span>
                </div>
                <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h3 className="text-sm font-medium text-violet-200">
                      AI 主管生成的作战计划
                    </h3>
                    {planVersion.confirmed_at ? (
                      <p className="mt-1 text-xs text-emerald-300/80">
                        计划确认时间：{planVersion.confirmed_at}
                      </p>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    disabled={!canConfirmPlanVersion}
                    onClick={() => {
                      void handleConfirmPlanVersion();
                    }}
                    className="w-fit rounded border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-200 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:border-[#333333] disabled:bg-[#171717] disabled:text-zinc-600"
                  >
                    {planVersion.status === "confirmed"
                      ? "计划已确认"
                      : confirmPlanVersionMutation.isPending
                        ? "确认计划中..."
                        : "确认作战计划"}
                  </button>
                </div>
                <p className="mt-2 whitespace-pre-wrap text-sm text-zinc-300">
                  {planVersion.plan_summary}
                </p>

                {planVersion.phases.length > 0 ? (
                  <div className="mt-4">
                    <p className="text-xs font-medium text-zinc-400">阶段拆解</p>
                    <ol className="mt-2 space-y-2">
                      {planVersion.phases.map((phase, index) => (
                        <li
                          key={`${phase.title}-${index}`}
                          className="rounded border border-[#333333] bg-[#111111] p-3"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded bg-violet-500/10 px-1.5 py-0.5 text-[10px] text-violet-200">
                              P{index + 1}
                            </span>
                            <p className="text-sm text-zinc-200">{phase.title}</p>
                            <span className="text-[10px] text-zinc-600">
                              任务提示：{phase.task_count_hint}
                            </span>
                          </div>
                          <p className="mt-1 text-xs text-zinc-500">{phase.goal}</p>
                        </li>
                      ))}
                    </ol>
                  </div>
                ) : null}

                {planVersion.proposed_tasks.length > 0 ? (
                  <div className="mt-4">
                    <p className="text-xs font-medium text-zinc-400">
                      拟议任务（只读展示，未创建任务）
                    </p>
                    <div className="mt-2 grid gap-2 lg:grid-cols-2">
                      {planVersion.proposed_tasks.map((task, index) => (
                        <div
                          key={`${task.title}-${index}`}
                          className="rounded border border-[#333333] bg-[#111111] p-3"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-sm text-zinc-200">{task.title}</p>
                            <span className="rounded border border-[#333333] px-1.5 py-0.5 text-[10px] text-zinc-500">
                              {task.priority_hint}
                            </span>
                            <span className="rounded border border-[#333333] px-1.5 py-0.5 text-[10px] text-zinc-500">
                              {task.suggested_role_code}
                            </span>
                          </div>
                          <p className="mt-1 text-xs text-zinc-500">
                            {task.description}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                <div className="mt-4 grid gap-3 lg:grid-cols-2">
                  {planVersion.acceptance_criteria.length > 0 ? (
                    <div className="rounded border border-[#333333] bg-[#111111] p-3">
                      <p className="text-xs font-medium text-zinc-400">验收标准</p>
                      <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-zinc-500">
                        {planVersion.acceptance_criteria.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {planVersion.risks.length > 0 ? (
                    <div className="rounded border border-[#333333] bg-[#111111] p-3">
                      <p className="text-xs font-medium text-zinc-400">风险提示</p>
                      <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-zinc-500">
                        {planVersion.risks.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>

                <div className="mt-4 rounded border border-[#333333] bg-[#111111] p-3 text-xs text-zinc-500">
                  <p>下一步：{planVersion.next_action}</p>
                  <p className="mt-1">
                    R1-D 边界：仅确认 plan version；不创建任务 / 不调用 planning/apply / 不调度 Worker
                  </p>
                  {planVersion.forbidden_actions.length > 0 ? (
                    <p className="mt-1">
                      后端边界：{planVersion.forbidden_actions.join(" / ")}
                    </p>
                  ) : null}
                </div>
              </div>
            ) : null}

            {submitAnswersMutation.isError ? (
              <p className="rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                {submitAnswersMutation.error.message}
              </p>
            ) : null}
            {confirmGoalMutation.isError ? (
              <p className="rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                {confirmGoalMutation.error.message}
              </p>
            ) : null}
            {createPlanVersionMutation.isError ? (
              <p className="rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                {createPlanVersionMutation.error.message}
              </p>
            ) : null}
            {confirmPlanVersionMutation.isError ? (
              <p className="rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                {confirmPlanVersionMutation.error.message}
              </p>
            ) : null}

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
          <p>Ctrl/⌘ + Enter 发送；R1-D 仅确认计划，不会创建任务或调度 Worker。</p>
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
