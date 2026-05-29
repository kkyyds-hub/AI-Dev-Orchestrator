import { useEffect, useState } from "react";
import type { KeyboardEvent } from "react";
import { Link } from "react-router-dom";

import {
  useConfirmProjectDirectorGoal,
  useConfirmProjectDirectorPlanVersion,
  useCreateProjectDirectorPlanVersion,
  useCreateProjectDirectorSession,
  useCreateProjectDirectorTaskQueue,
  useSubmitProjectDirectorAnswers,
} from "../../../features/project-director/hooks";
import type {
  ProjectDirectorPlanVersion,
  ProjectDirectorSession,
  ProjectDirectorTaskCreationResponse,
} from "../../../features/project-director/types";
import { useRunWorkerOnce } from "../../../features/task-actions/hooks";
import {
  formatNullableCurrencyUsd,
  formatNullableTokenCount,
} from "../../../lib/format";
import { buildRunRoute } from "../../../lib/run-route";
import { buildTaskRoute } from "../../../lib/task-route";

const EXAMPLE_QUESTIONS = [
  "帮我分析当前项目的阻塞原因",
  "生成一份作战计划建议",
  "当前哪些任务需要我确认？",
  "重新评估项目风险并给出调整建议",
];

interface DirectorChatEntryProps {
  selectedProjectId: string;
  selectedProjectName: string;
  onSessionChange?: (hasSession: boolean) => void;
}

export function DirectorChatEntry({
  selectedProjectId,
  selectedProjectName,
  onSessionChange,
}: DirectorChatEntryProps) {
  const [draft, setDraft] = useState("");
  const [session, setSession] = useState<ProjectDirectorSession | null>(null);
  const [planVersion, setPlanVersion] =
    useState<ProjectDirectorPlanVersion | null>(null);
  const [taskCreation, setTaskCreation] =
    useState<ProjectDirectorTaskCreationResponse | null>(null);
  const [answerDrafts, setAnswerDrafts] = useState<Record<string, string>>({});
  const createSessionMutation = useCreateProjectDirectorSession();
  const submitAnswersMutation = useSubmitProjectDirectorAnswers();
  const confirmGoalMutation = useConfirmProjectDirectorGoal();
  const createPlanVersionMutation = useCreateProjectDirectorPlanVersion();
  const confirmPlanVersionMutation = useConfirmProjectDirectorPlanVersion();
  const createTaskQueueMutation = useCreateProjectDirectorTaskQueue();
  const runWorkerOnceMutation = useRunWorkerOnce();

  const scopedProjectId = selectedProjectId === "all" ? null : selectedProjectId;
  const workerRunOnceResult = runWorkerOnceMutation.data ?? null;
  const trimmedDraft = draft.trim();
  const isMutating =
    createSessionMutation.isPending ||
    submitAnswersMutation.isPending ||
    confirmGoalMutation.isPending ||
    createPlanVersionMutation.isPending ||
    confirmPlanVersionMutation.isPending ||
    createTaskQueueMutation.isPending;
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
  const canCreateTaskQueue =
    planVersion?.status === "confirmed" &&
    planVersion.project_id !== null &&
    !taskCreation &&
    !createTaskQueueMutation.isPending;
  const taskQueueActionLabel = taskCreation
    ? `任务队列已创建（${taskCreation.task_count}）`
    : createTaskQueueMutation.isPending
      ? "创建任务队列中..."
      : planVersion?.project_id
        ? "创建真实任务队列"
        : "需要绑定具体项目";
  const visibleTaskIds = taskCreation?.created_task_ids.slice(0, 6) ?? [];
  const hiddenTaskCount = Math.max(
    0,
    (taskCreation?.created_task_ids.length ?? 0) - visibleTaskIds.length,
  );

  // Notify parent if active session changes
  useEffect(() => {
    onSessionChange?.(session !== null);
  }, [session, onSessionChange]);

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
      setPlanVersion(null);
      setTaskCreation(null);
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
      setTaskCreation(null);
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
      setTaskCreation(null);
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

  const handleCreateTaskQueue = async () => {
    if (!planVersion || !canCreateTaskQueue) {
      return;
    }

    try {
      const createdTaskQueue = await createTaskQueueMutation.mutateAsync({
        planVersionId: planVersion.id,
      });
      setTaskCreation(createdTaskQueue);
    } catch {
      // Error details are rendered from the mutation state below.
    }
  };

  const handleRunWorkerOnce = async () => {
    if (runWorkerOnceMutation.isPending) {
      return;
    }

    try {
      await runWorkerOnceMutation.mutateAsync(scopedProjectId);
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
      className="flex flex-col bg-transparent lg:min-h-[calc(100vh-220px)] relative overflow-hidden w-full pb-2"
    >
      <div className="monochrome-glow-bg" />
      {/* 顶部栏：标题 + 项目上下文 */}
      <div className="shrink-0 mb-6 pb-4 border-b border-zinc-900 relative z-10 w-full">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between w-full">
          <div>
            <div className="flex items-center gap-2">
              <span className="flex h-1.5 w-1.5 rounded-full bg-zinc-500" />
              <h2 className="text-base font-bold text-white tracking-tight">AI Project Director</h2>
            </div>
            <p className="mt-1 text-xs text-zinc-500 max-w-xl">
              提出项目目标、回答澄清问题并由 AI 主管一键调度 Agent 团队执行任务。
            </p>
          </div>
          <span className="inline-flex items-center rounded-lg border border-zinc-850 bg-zinc-950 px-3 py-1.5 text-xs text-zinc-400 shrink-0">
            项目上下文：{selectedProjectName}
          </span>
        </div>
      </div>

      {/* 中部：会话内容 / 空白首屏 */}
      <div className="flex-1 mb-6 min-h-[220px] overflow-y-auto custom-scrollbar pr-1 relative z-10 w-full">
        {session ? (
          /* 💬 FLOWING CONVERSATIONAL MESSAGES STREAM (No max-width constraints, fully wide) 💬 */
          <div className="space-y-6 w-full">
            
            {/* Exchange 1: User's Initial Prompt (Right Bubble) */}
            <div className="flex justify-end w-full">
              <div className="max-w-[85%] rounded-2xl bg-zinc-800 border border-zinc-700/40 text-zinc-100 px-4 py-3 text-sm leading-relaxed shadow-md select-text">
                <span className="text-[10px] text-zinc-400 block font-mono font-bold uppercase mb-1">您的问题</span>
                {session.goal_text}
              </div>
            </div>

            {/* Exchange 1: AI Clarifying Questions Box (Left Bubble) */}
            <div className="flex justify-start w-full">
              <div className="w-full rounded-2xl border border-zinc-900 bg-zinc-950 p-5 shadow-sm space-y-4">
                <div className="flex items-center gap-1.5 border-b border-zinc-900 pb-2.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-zinc-500" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400">AI 主管的澄清建议</h3>
                </div>
                
                {session.clarifying_questions.length > 0 ? (
                  <ol className="space-y-4 w-full">
                    {session.clarifying_questions.map((question, index) => (
                      <li
                        key={question.id}
                        className="rounded-xl border border-zinc-900 bg-black p-4 w-full"
                      >
                        <div className="flex items-start gap-3 w-full">
                          <span className="mt-0.5 text-xs font-bold text-zinc-500 font-mono">
                            Q{index + 1}
                          </span>
                          <div className="min-w-0 flex-1 w-full">
                            <p className="text-xs font-bold text-zinc-200 leading-relaxed">
                              {question.question}
                              {question.required ? (
                                <span className="ml-2 text-[9px] text-amber-500 font-bold">[必答]</span>
                              ) : null}
                            </p>
                            {question.hint ? (
                              <p className="mt-1 text-[11px] text-zinc-500">提示：{question.hint}</p>
                            ) : null}
                            {session.status === "clarifying" ? (
                              <textarea
                                value={answerDrafts[question.id] ?? ""}
                                onChange={(event) =>
                                  handleAnswerChange(question.id, event.target.value)
                                }
                                rows={2}
                                placeholder="输入您的回复..."
                                className="mt-3.5 w-full resize-none rounded-lg border border-zinc-800 bg-[#09090a] px-3.5 py-2.5 text-xs text-zinc-200 focus:border-zinc-600 focus:outline-none transition"
                              />
                            ) : (
                              <p className="mt-3.5 rounded border border-zinc-900 bg-[#060607] px-3.5 py-2.5 text-xs text-zinc-400 leading-relaxed">
                                <span className="text-zinc-600 block text-[9px] font-bold mb-1">您的解答</span>
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
                  <p className="text-xs text-zinc-600">当前没有需要澄清的事项。</p>
                )}

                {session.status === "clarifying" && (
                  <div className="mt-4 flex flex-col gap-3 border-t border-zinc-900 pt-3.5 sm:flex-row sm:items-center sm:justify-between w-full">
                    <p className="text-[10px] text-zinc-500">
                      * 提交澄清回答后，将生成完整的开发目标确认函。
                    </p>
                    <button
                      type="button"
                      disabled={!canSubmitAnswers}
                      onClick={() => {
                        void handleSubmitAnswers();
                      }}
                      className="rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-1.5 text-xs font-semibold text-zinc-200 hover:bg-zinc-800/80 transition disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                    >
                      {submitAnswersMutation.isPending ? "正在提交..." : "提交解答并生成目标"}
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Exchange 2: User's Answers (Right Bubble, if already answered) */}
            {session.status !== "clarifying" && session.clarifying_answers.length > 0 && (
              <div className="flex justify-end w-full">
                <div className="max-w-[85%] rounded-2xl bg-zinc-800 border border-zinc-700/40 text-zinc-100 px-4 py-3.5 text-sm leading-relaxed shadow-md select-text">
                  <span className="text-[10px] text-zinc-400 block font-mono font-bold uppercase mb-2">已提交的澄清回答</span>
                  <ul className="space-y-1.5 text-xs">
                    {session.clarifying_answers.map((ans) => {
                      const q = session.clarifying_questions.find(x => x.id === ans.question_id);
                      return (
                        <li key={ans.question_id} className="border-l border-zinc-600 pl-2">
                          <span className="text-zinc-400 text-[10px] block">Q: {q?.question || "问题"}</span>
                          <span className="text-zinc-200">{ans.answer}</span>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              </div>
            )}

            {/* Exchange 3: AI Core Goal Confirmation / Battle Plan (Left Bubble) */}
            {(session.status === "ready_to_confirm" || session.status === "confirmed") && (
              <div className="flex justify-start w-full">
                <div className="w-full rounded-2xl border border-zinc-900 bg-zinc-950 p-5 shadow-sm space-y-4">
                  
                  {/* Goal Summary Header */}
                  <div className="flex items-center gap-1.5 border-b border-zinc-900 pb-2.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-zinc-500" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-300">
                      确立的开发范围与目标
                    </h3>
                  </div>

                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between w-full">
                    <div className="min-w-0 flex-1 w-full">
                      <p className="whitespace-pre-wrap text-xs text-zinc-300 leading-relaxed bg-black p-3.5 rounded-lg border border-zinc-900">
                        {session.goal_summary || "评估中..."}
                      </p>
                      {session.confirmed_at && (
                        <p className="mt-2.5 text-[10px] font-mono text-zinc-500">
                          ✓ 同意并确认目标：{session.confirmed_at}
                        </p>
                      )}
                    </div>
                    
                    <div className="flex shrink-0 flex-col gap-2 sm:items-end">
                      <button
                        type="button"
                        disabled={!canConfirmGoal}
                        onClick={() => {
                          void handleConfirmGoal();
                        }}
                        className="rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-1.5 text-xs font-semibold text-zinc-200 hover:bg-zinc-850 transition disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                      >
                        {session.status === "confirmed" ? "目标已确认" : confirmGoalMutation.isPending ? "确认中..." : "同意并确认目标"}
                      </button>
                      {session.status === "confirmed" && (
                        <button
                          type="button"
                          disabled={!canCreatePlanVersion}
                          onClick={() => {
                            void handleCreatePlanVersion();
                          }}
                          className="rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-1.5 text-xs font-semibold text-zinc-200 hover:bg-zinc-85 transition disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                        >
                          {planVersion ? "计划定制成功" : createPlanVersionMutation.isPending ? "正在生成..." : "制定完整作战计划"}
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Battle Plan Details Box */}
                  {planVersion && (
                    <div className="border-t border-zinc-900 pt-4 space-y-4">
                      <div className="flex items-center justify-between gap-2 border-b border-zinc-900 pb-2">
                        <span className="text-xs font-bold text-zinc-300">作战计划详细部署 v{planVersion.version_no}</span>
                        <span className="text-[10px] text-zinc-500 border border-zinc-900 bg-black px-1.5 py-0.5 rounded">
                          计划状态: {planVersion.status}
                        </span>
                      </div>

                      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between w-full">
                        <span className="text-xs text-zinc-400 font-bold">任务拆解与队列规划建议</span>
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            disabled={!canConfirmPlanVersion}
                            onClick={() => {
                              void handleConfirmPlanVersion();
                            }}
                            className="rounded-lg border border-zinc-800 bg-zinc-900 px-3.5 py-1.5 text-xs font-semibold text-zinc-200 hover:bg-zinc-85 transition disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                          >
                            {planVersion.status === "confirmed" ? "计划已确认" : confirmPlanVersionMutation.isPending ? "正在签署..." : "确认作战计划"}
                          </button>
                          {planVersion.status === "confirmed" && (
                            <button
                              type="button"
                              disabled={!canCreateTaskQueue}
                              onClick={() => {
                                void handleCreateTaskQueue();
                              }}
                              className="rounded-lg border border-zinc-800 bg-zinc-900 px-3.5 py-1.5 text-xs font-semibold text-zinc-200 hover:bg-zinc-85 transition disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                            >
                              {taskQueueActionLabel}
                            </button>
                          )}
                        </div>
                      </div>

                      <p className="rounded-lg border border-zinc-900 bg-black p-3.5 text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap">
                        {planVersion.plan_summary}
                      </p>

                      {/* Stages */}
                      {planVersion.phases.length > 0 && (
                        <div className="space-y-2">
                          <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">执行阶段拆解</p>
                          <ol className="grid gap-2.5 sm:grid-cols-2">
                            {planVersion.phases.map((phase, index) => (
                              <li key={`${phase.title}-${index}`} className="rounded-lg border border-zinc-900 bg-black p-3">
                                <div className="flex items-center gap-2 mb-1">
                                  <span className="text-[10px] font-bold text-zinc-500">STAGE {index + 1}:</span>
                                  <p className="text-xs font-bold text-zinc-200 truncate">{phase.title}</p>
                                </div>
                                <p className="text-[11px] text-zinc-400 leading-normal">{phase.goal}</p>
                              </li>
                            ))}
                          </ol>
                        </div>
                      )}

                      {/* Proposed Tasks */}
                      {planVersion.proposed_tasks.length > 0 && (
                        <div className="space-y-2">
                          <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">计划建议生成的任务</p>
                          <div className="grid gap-2 sm:grid-cols-2">
                            {planVersion.proposed_tasks.map((task, index) => (
                              <div key={`${task.title}-${index}`} className="rounded-lg border border-zinc-900 bg-black p-3 flex flex-col justify-between">
                                <div>
                                  <div className="flex items-center gap-2 mb-1">
                                    <span className="text-[9px] font-bold text-zinc-500 uppercase">[{task.suggested_role_code}]</span>
                                    <span className="text-[9px] text-zinc-500 border border-zinc-900 px-1 rounded bg-[#09090a]">{task.priority_hint}</span>
                                  </div>
                                  <p className="text-xs font-bold text-zinc-300 leading-tight mb-1">{task.title}</p>
                                  <p className="text-[10px] text-zinc-500 leading-normal">{task.description}</p>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Criteria and risks */}
                      <div className="grid gap-4 sm:grid-cols-2">
                        {planVersion.acceptance_criteria.length > 0 && (
                          <div className="rounded-lg border border-zinc-900 bg-black p-3">
                            <p className="text-[10px] font-bold text-zinc-500 uppercase mb-2">验收通过标准</p>
                            <ul className="list-disc pl-4 text-[11px] text-zinc-400 space-y-1">
                              {planVersion.acceptance_criteria.map((item) => (
                                <li key={item} className="leading-relaxed">{item}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {planVersion.risks.length > 0 && (
                          <div className="rounded-lg border border-zinc-900 bg-black p-3">
                            <p className="text-[10px] font-bold text-zinc-500 uppercase mb-2">潜在架构风险</p>
                            <ul className="list-disc pl-4 text-[11px] text-zinc-400 space-y-1">
                              {planVersion.risks.map((item) => (
                                <li key={item} className="leading-relaxed">{item}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>

                      {/* Plan boundaries */}
                      <div className="rounded-lg border border-zinc-900 bg-black p-3 text-[11px] text-zinc-500 leading-relaxed font-mono">
                        <p>执行边界指引：{planVersion.next_action}</p>
                        {planVersion.forbidden_actions.length > 0 && (
                          <p className="mt-0.5 text-zinc-600">调度红线：{planVersion.forbidden_actions.join(" / ")}</p>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Deployed Task Queue Section (Active Run log) */}
                  {taskCreation && (
                    <div className="border-t border-zinc-900 pt-4 space-y-3">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-zinc-900 pb-2">
                        <div>
                          <h3 className="text-xs font-bold text-zinc-300">开发任务队列已部署部署</h3>
                          <p className="mt-0.5 text-[10px] text-zinc-500 font-mono">
                            项目范围: {taskCreation.project_id} · 队列状态 {taskCreation.status} · 共计 {taskCreation.task_count} 个任务
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            disabled={runWorkerOnceMutation.isPending}
                            onClick={() => {
                              void handleRunWorkerOnce();
                            }}
                            className="rounded-lg border border-zinc-800 bg-zinc-900 px-3.5 py-1.5 text-xs font-semibold text-zinc-300 hover:bg-zinc-80 transition disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                          >
                            {runWorkerOnceMutation.isPending ? "正在调度..." : "手动启动单次调度"}
                          </button>
                          <Link
                            to={`/execution?tab=tasks&projectId=${encodeURIComponent(taskCreation.project_id)}`}
                            className="rounded-lg border border-zinc-800 bg-zinc-900 px-3.5 py-1.5 text-xs font-semibold text-zinc-300 hover:bg-zinc-80 transition text-center"
                          >
                            进入执行中心
                          </Link>
                        </div>
                      </div>

                      <p className="text-[11px] text-zinc-400 bg-black p-2.5 rounded border border-zinc-900 font-mono">
                        {taskCreation.next_action}
                      </p>

                      {/* Execution Console */}
                      {workerRunOnceResult && (
                        <div className="rounded-lg border border-zinc-900 bg-black p-3 shadow-inner space-y-2.5">
                          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                            <div className="min-w-0 flex-1">
                              <p className="text-xs font-bold text-zinc-300">
                                {workerRunOnceResult.claimed ? "单次调度启动，任务已被认领并分配给 Agent" : "当前没有等待调度的就绪任务"}
                              </p>
                              {workerRunOnceResult.task_title && (
                                <p className="mt-1.5 text-xs text-zinc-400">{workerRunOnceResult.task_title}</p>
                              )}
                            </div>
                            
                            <div className="grid shrink-0 gap-0.5 text-[10px] font-mono text-zinc-500 sm:text-right border-t sm:border-t-0 sm:border-l border-zinc-900 pt-2 sm:pt-0 sm:pl-3">
                              <span>RUN: {workerRunOnceResult.run_id?.slice(0, 8) || "无"}</span>
                              <span>Tokens: {formatNullableTokenCount(workerRunOnceResult.total_tokens)}</span>
                              <span>调度预估成本: {formatNullableCurrencyUsd(workerRunOnceResult.estimated_cost)}</span>
                            </div>
                          </div>

                          <div className="flex flex-wrap gap-2">
                            {workerRunOnceResult.run_id && (
                              <Link
                                to={buildRunRoute({
                                  runId: workerRunOnceResult.run_id,
                                  taskId: workerRunOnceResult.task_id,
                                  projectId: scopedProjectId,
                                  from: "workbench",
                                })}
                                className="rounded border border-zinc-800 bg-zinc-900/50 px-2 py-1 text-[10px] text-zinc-400 hover:text-zinc-200 transition"
                              >
                                查看实时调度日志与证据
                              </Link>
                            )}
                            {workerRunOnceResult.task_id && (
                              <Link
                                to={buildTaskRoute({
                                  taskId: workerRunOnceResult.task_id,
                                  projectId: scopedProjectId,
                                  from: "workbench",
                                })}
                                className="rounded border border-zinc-800 bg-zinc-900/50 px-2 py-1 text-[10px] text-zinc-400 hover:text-zinc-200 transition"
                              >
                                定位当前任务
                              </Link>
                            )}
                          </div>
                        </div>
                      )}

                      {runWorkerOnceMutation.isError && (
                        <p className="mt-2 rounded-lg border border-zinc-900 bg-black px-3.5 py-2 text-xs text-rose-500 font-mono">
                          ✗ 启动调度失败：{runWorkerOnceMutation.error.message}
                        </p>
                      )}

                      {taskCreation.created_task_ids.length > 0 && (
                        <div className="space-y-1.5 pt-1.5">
                          <p className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">生成的任务队列条目 ({taskCreation.created_task_ids.length})</p>
                          <div className="flex flex-wrap gap-1.5">
                            {visibleTaskIds.map((taskId, index) => (
                              <Link
                                key={taskId}
                                to={buildTaskRoute({
                                  taskId,
                                  projectId: taskCreation.project_id,
                                  from: "workbench",
                                })}
                                title={taskId}
                                className="rounded-md border border-zinc-900 bg-black px-2 py-0.5 text-[10px] font-mono text-zinc-400 hover:text-zinc-200 transition"
                              >
                                T{index + 1} · {taskId.slice(0, 8)}
                              </Link>
                            ))}
                            {hiddenTaskCount > 0 && (
                              <span className="rounded-md border border-zinc-900 bg-black px-2 py-0.5 text-[10px] text-zinc-500">
                                + {hiddenTaskCount} 更多任务
                              </span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                </div>
              </div>
            )}

            {/* Error popups */}
            {submitAnswersMutation.isError && (
              <p className="rounded-lg border border-zinc-900 bg-black px-3 py-2 text-xs text-rose-500 font-mono">
                ✗ {submitAnswersMutation.error.message}
              </p>
            )}
            {confirmGoalMutation.isError && (
              <p className="rounded-lg border border-zinc-900 bg-black px-3 py-2 text-xs text-rose-500 font-mono">
                ✗ {confirmGoalMutation.error.message}
              </p>
            )}
            {createPlanVersionMutation.isError && (
              <p className="rounded-lg border border-zinc-900 bg-black px-3 py-2 text-xs text-rose-500 font-mono">
                ✗ {createPlanVersionMutation.error.message}
              </p>
            )}
            {confirmPlanVersionMutation.isError && (
              <p className="rounded-lg border border-zinc-900 bg-black px-3 py-2 text-xs text-rose-500 font-mono">
                ✗ {confirmPlanVersionMutation.error.message}
              </p>
            )}
            {createTaskQueueMutation.isError && (
              <p className="rounded-lg border border-zinc-900 bg-black px-3 py-2 text-xs text-rose-500 font-mono">
                ✗ {createTaskQueueMutation.error.message}
              </p>
            )}

            {/* Next actions box */}
            <div className="rounded-lg border border-zinc-900 bg-black p-3 text-[11px] text-zinc-500 font-mono">
              <p>调度流下一环：{session.next_action}</p>
              {session.forbidden_actions.length > 0 && (
                <p className="mt-0.5 text-zinc-600">红线限制：{session.forbidden_actions.join(" / ")}</p>
              )}
            </div>
          </div>
        ) : (
          /* 💎 GEMINI-STYLE EXTREMELY CLEAN PURE BLACK GREETING (STRETCHES DYNAMICALLY) 💎 */
          <div className="flex h-full min-h-[380px] flex-col justify-center items-start px-2 py-4 w-full">
            <div className="w-full text-left space-y-8">
              {/* Crisp Solid White Greeting */}
              <div className="space-y-3 relative z-10">
                <h3 className="text-3xl sm:text-4xl font-light text-zinc-300 tracking-tight select-none">
                  您好，我是 <span className="font-medium text-white tracking-wide">AI 项目主管</span>
                </h3>
                <p className="text-zinc-500 text-sm font-medium tracking-wide leading-relaxed max-w-2xl">
                  今天有什么开发目标？我将为你规划作战计划，并调度 Agent 协同完成。
                </p>
              </div>

              {/* 2x2 Clean, Solid Black Grid Cards (occupies the entire screen/container width) */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 w-full">
                {EXAMPLE_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => handleExampleClick(q)}
                    className="wireframe-btn text-left border border-zinc-900/50 bg-transparent px-5 py-4.5 text-xs text-zinc-400 flex items-center justify-between group cursor-pointer w-full h-14"
                  >
                    <span className="font-semibold leading-relaxed pr-4 text-zinc-400 group-hover:text-zinc-200">{q}</span>
                    <span className="text-zinc-700 group-hover:text-zinc-400 transition-transform group-hover:translate-x-0.5">
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                      </svg>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 底部：输入框 composer (No max-width constraints, fully wide) */}
      <div className="shrink-0 relative z-10 w-full mt-auto pt-6">
        {/* Composer Outer Border - Monochrome Capsule Glow */}
        <div className="composer-monochrome-wrapper w-full">
          <div className="flex flex-col bg-black rounded-[27px] overflow-hidden w-full relative z-10">
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="描述您的开发需求与目标，或遇到的故障阻塞..."
              rows={3}
              className="w-full resize-none bg-transparent px-5 py-4 text-sm text-zinc-200 placeholder:text-zinc-700 focus:outline-none custom-scrollbar"
            />
            
            {/* bottom actions bar inside Composer */}
            <div className="flex items-center justify-between border-t border-zinc-900 px-5 py-3.5 bg-black w-full">
              <div className="flex items-center gap-3 text-zinc-700 select-none">
                <span className="text-[10px] text-zinc-500 font-mono">
                  {scopedProjectId ? `SCOPE: ${selectedProjectName}` : "SCOPE: GLOBAL"}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={!canSend}
                  onClick={() => {
                    void handleSubmit();
                  }}
                  className="rounded-full bg-white px-5 py-1.5 text-xs font-semibold text-black transition hover:bg-zinc-200 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-white flex items-center gap-1.5 cursor-pointer"
                >
                  {createSessionMutation.isPending ? (
                    <>
                      <svg className="animate-spin h-3.5 w-3.5 text-black" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      <span>制定中...</span>
                    </>
                  ) : (
                    <>
                      <span>发送</span>
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                      </svg>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 text-[10px] text-zinc-600 w-full">
          <span>快捷指令：Ctrl/⌘ + Enter 发送目标并启动澄清。</span>
          <span>敏捷主管 · 支持基于历史数据实时微调</span>
        </div>
        {createSessionMutation.isError && (
          <p className="mt-2 rounded-lg border border-zinc-900 bg-black px-3.5 py-2 text-xs text-rose-500 font-mono w-full">
            ✗ 异常：{createSessionMutation.error.message}
          </p>
        )}
      </div>
    </section>
  );
}
