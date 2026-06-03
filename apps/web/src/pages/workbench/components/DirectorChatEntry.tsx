import { useEffect, useMemo, useState } from "react";
import type { KeyboardEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { StatusBadge } from "../../../components/StatusBadge";
import { useConsoleBudgetHealth } from "../../../features/console-metrics/hooks";
import {
  useConfirmProjectDirectorGoal,
  useCreateProjectDirectorPlanVersion,
  useCreateProjectDirectorSession,
  useCreateProjectDirectorTaskQueue,
  useProjectDirectorWorkbenchResume,
  useReviewProjectDirectorPlanVersion,
  useSubmitProjectDirectorAnswers,
} from "../../../features/project-director/hooks";
import { PROJECT_DIRECTOR_PLAN_STATUS_LABELS } from "../../../features/project-director/types";
import type {
  ProjectDirectorPlanReviewAction,
  ProjectDirectorPlanVersion,
  ProjectDirectorSession,
  ProjectDirectorTaskCreationResponse,
} from "../../../features/project-director/types";
import { useRunWorkerOnce } from "../../../features/task-actions/hooks";
import {
  formatNullableCurrencyUsd,
  formatNullableTokenCount,
} from "../../../lib/format";
import { requestJson } from "../../../lib/http";
import { buildRunRoute } from "../../../lib/run-route";
import { buildTaskRoute } from "../../../lib/task-route";
import { ProjectDirectorPlanReviewModal } from "./ProjectDirectorPlanReviewModal";

type OpenAIProviderSettingsSummary = {
  provider_key: string;
  configured: boolean;
  source: "saved_config" | "env" | "none";
  detected_provider_type: "openai" | "deepseek" | "openai_compatible";
  model_preset: "openai" | "deepseek" | "custom";
};

function fetchOpenAIProviderSettings(): Promise<OpenAIProviderSettingsSummary> {
  return requestJson<OpenAIProviderSettingsSummary>("/provider-settings/openai");
}

function resolveProviderStatus(query: {
  data?: OpenAIProviderSettingsSummary;
  isLoading: boolean;
  isError: boolean;
}): { label: string; tone: "info" | "success" | "warning" | "danger"; detail: string } {
  if (query.isLoading) {
    return {
      label: "检查 Provider 配置中",
      tone: "info",
      detail: "正在读取 /provider-settings/openai，确认首次真实运行前的 Provider 状态。",
    };
  }

  if (query.isError) {
    return {
      label: "Provider 状态未知",
      tone: "danger",
      detail: "无法读取 Provider 配置，已禁止启动一次执行。",
    };
  }

  if (query.data?.configured) {
    return {
      label: "Provider 已配置",
      tone: "success",
      detail: `Provider 已配置（${query.data.detected_provider_type} / ${query.data.source}）。启动后可能调用真实 AI provider。`,
    };
  }

  return {
    label: "未配置 Provider",
    tone: "warning",
    detail: "请先到设置页配置并测试 Provider，再由你本人启动首次真实运行。",
  };
}

const EXAMPLE_QUESTIONS = [
  "我要从 0 创建一个新项目：做一个可验收的 MVP，请先帮我澄清目标。",
  "我想把现有想法收口成项目草案，请先追问范围、验收标准和风险。",
  "帮我为一个前后端功能生成首次项目创建会话，但不要自动执行任务。",
  "我还没有项目，请作为 AI 项目主管先问我必要澄清问题。",
];

const DIRECTOR_RESUME_STORAGE_PREFIX =
  "ai-dev-orchestrator:project-director-workbench-resume";

function buildDirectorResumeStorageKey(
  mode: "new-project" | "project",
  projectId: string | null,
) {
  return `${DIRECTOR_RESUME_STORAGE_PREFIX}:${mode}:${projectId ?? "unbound"}`;
}

interface DirectorChatEntryProps {
  selectedProjectId: string | null;
  selectedProjectName: string;
  mode: "new-project" | "project";
}

export function DirectorChatEntry({
  selectedProjectId,
  selectedProjectName,
  mode,
}: DirectorChatEntryProps) {
  const [draft, setDraft] = useState("");
  const [session, setSession] = useState<ProjectDirectorSession | null>(null);
  const [planVersion, setPlanVersion] =
    useState<ProjectDirectorPlanVersion | null>(null);
  const [taskCreation, setTaskCreation] =
    useState<ProjectDirectorTaskCreationResponse | null>(null);
  const [answerDrafts, setAnswerDrafts] = useState<Record<string, string>>({});
  const [isPlanReviewOpen, setIsPlanReviewOpen] = useState(false);
  const [reviewFeedback, setReviewFeedback] = useState("");
  const [pendingReviewAction, setPendingReviewAction] =
    useState<ProjectDirectorPlanReviewAction | null>(null);
  const [planReviewMessage, setPlanReviewMessage] = useState<string | null>(null);
  const [resumeMessage, setResumeMessage] = useState<string | null>(null);

  const createSessionMutation = useCreateProjectDirectorSession();
  const submitAnswersMutation = useSubmitProjectDirectorAnswers();
  const confirmGoalMutation = useConfirmProjectDirectorGoal();
  const createPlanVersionMutation = useCreateProjectDirectorPlanVersion();
  const reviewPlanVersionMutation = useReviewProjectDirectorPlanVersion();
  const createTaskQueueMutation = useCreateProjectDirectorTaskQueue();
  const runWorkerOnceMutation = useRunWorkerOnce();
  const providerSettingsQuery = useQuery({
    queryKey: ["provider-settings", "openai"],
    queryFn: fetchOpenAIProviderSettings,
  });
  const budgetHealthQuery = useConsoleBudgetHealth();

  const scopedProjectId =
    mode === "project" && selectedProjectId && selectedProjectId !== "all"
      ? selectedProjectId
      : null;
  const resumeQuery = useProjectDirectorWorkbenchResume({
    mode,
    projectId: scopedProjectId,
  });
  const trimmedDraft = draft.trim();
  const workerRunOnceResult = runWorkerOnceMutation.data ?? null;
  const providerSettings = providerSettingsQuery.data ?? null;
  const providerConfigured = providerSettings?.configured === true;
  const providerStatus = resolveProviderStatus(providerSettingsQuery);
  const budgetHealth = budgetHealthQuery.data ?? null;
  const visibleTaskIds = taskCreation?.created_task_ids.slice(0, 6) ?? [];
  const hiddenTaskCount = Math.max(
    0,
    (taskCreation?.created_task_ids.length ?? 0) - visibleTaskIds.length,
  );

  const requiredQuestions =
    session?.clarifying_questions.filter((question) => question.required) ?? [];
  const requiredAnswersReady = requiredQuestions.every(
    (question) => (answerDrafts[question.id] ?? "").trim().length > 0,
  );

  const isMutating =
    createSessionMutation.isPending ||
    submitAnswersMutation.isPending ||
    confirmGoalMutation.isPending ||
    createPlanVersionMutation.isPending ||
    reviewPlanVersionMutation.isPending ||
    createTaskQueueMutation.isPending;

  const canSend = trimmedDraft.length > 0 && !isMutating;
  const canSubmitAnswers =
    session?.status === "clarifying" &&
    session.clarifying_questions.length > 0 &&
    requiredAnswersReady &&
    !submitAnswersMutation.isPending;
  const canConfirmGoal =
    session?.status === "ready_to_confirm" && !confirmGoalMutation.isPending;
  const canCreatePlanVersion =
    session?.status === "confirmed" &&
    (!planVersion ||
      planVersion.status === "rejected" ||
      planVersion.status === "superseded") &&
    !createPlanVersionMutation.isPending;
  const canCreateTaskQueue =
    planVersion?.status === "confirmed" &&
    !taskCreation &&
    !createTaskQueueMutation.isPending;
  const canRunWorkerOnce =
    Boolean(taskCreation?.project_id) &&
    providerConfigured &&
    !providerSettingsQuery.isLoading &&
    !providerSettingsQuery.isError &&
    !runWorkerOnceMutation.isPending;

  const taskQueueActionLabel = taskCreation
    ? `正式项目已创建（${taskCreation.task_count} 个任务）`
    : createTaskQueueMutation.isPending
      ? "创建正式项目中..."
      : "创建正式项目";

  const directorStatusMessage = useMemo(() => {
    if (createPlanVersionMutation.isPending) {
      return "AI 项目主管正在思考项目草案，请稍候。";
    }
    if (
      reviewPlanVersionMutation.isPending &&
      pendingReviewAction === "request_changes"
    ) {
      return "AI 项目主管正在根据整改意见重新规划新版本。";
    }
    if (
      reviewPlanVersionMutation.isPending &&
      pendingReviewAction === "approve"
    ) {
      return "AI 项目主管正在提交通过结论。";
    }
    if (
      reviewPlanVersionMutation.isPending &&
      pendingReviewAction === "reject"
    ) {
      return "AI 项目主管正在记录驳回结论。";
    }
    if (!session && resumeQuery.isLoading) {
      return "正在检查是否有未完成的 Project Director 流程。";
    }
    if (!session && resumeQuery.isError) {
      return "暂时无法检查未完成流程，你仍可以发起新的 Project Director 会话。";
    }
    if (resumeMessage) {
      return resumeMessage;
    }
    return planReviewMessage;
  }, [
    createPlanVersionMutation.isPending,
    pendingReviewAction,
    planReviewMessage,
    resumeMessage,
    resumeQuery.isError,
    resumeQuery.isLoading,
    reviewPlanVersionMutation.isPending,
    session,
  ]);

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

  useEffect(() => {
    setDraft("");
    setSession(null);
    setPlanVersion(null);
    setTaskCreation(null);
    setAnswerDrafts({});
    setIsPlanReviewOpen(false);
    setReviewFeedback("");
    setPendingReviewAction(null);
    setPlanReviewMessage(null);
    setResumeMessage(null);
  }, [mode, scopedProjectId]);

  useEffect(() => {
    if (session || planVersion) {
      return;
    }

    const resume = resumeQuery.data;
    if (!resume) {
      return;
    }

    if (!resume.session) {
      setResumeMessage(null);
      return;
    }

    setSession(resume.session);
    setPlanVersion(resume.plan_version);
    setTaskCreation(null);
    setReviewFeedback("");
    setIsPlanReviewOpen(false);
    setPlanReviewMessage(null);
    setResumeMessage(resume.next_action);
  }, [planVersion, resumeQuery.data, session]);

  useEffect(() => {
    if (!session) {
      return;
    }

    try {
      localStorage.setItem(
        buildDirectorResumeStorageKey(mode, scopedProjectId),
        JSON.stringify({
          sessionId: session.id,
          planVersionId: planVersion?.id ?? null,
          updatedAt: new Date().toISOString(),
        }),
      );
    } catch {
      // storage unavailable — backend resume still works
    }
  }, [mode, planVersion?.id, scopedProjectId, session]);

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
      setReviewFeedback("");
      setPlanReviewMessage(null);
      setIsPlanReviewOpen(false);
      setResumeMessage(null);
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
      setPlanReviewMessage(null);
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
      setReviewFeedback("");
      setPlanReviewMessage("项目草案已生成，请点击“查看项目草案”进入审核弹窗。");
      setResumeMessage(null);
      setIsPlanReviewOpen(true);
    } catch {
      // Error details are rendered from the mutation state below.
    }
  };

  const handleReviewPlanVersion = async (
    action: ProjectDirectorPlanReviewAction,
  ) => {
    if (!planVersion || planVersion.status !== "pending_confirmation") {
      return;
    }

    try {
      setPendingReviewAction(action);
      const result = await reviewPlanVersionMutation.mutateAsync({
        planVersionId: planVersion.id,
        action,
        feedback: reviewFeedback,
      });

      setPlanVersion(result.replacement_plan_version ?? result.reviewed_plan_version);
      setPlanReviewMessage(result.next_action);
      setResumeMessage(null);
      setTaskCreation(null);

      if (result.replacement_plan_version) {
        setReviewFeedback("");
        setIsPlanReviewOpen(true);
      } else {
        setIsPlanReviewOpen(false);
      }
    } catch {
      // Error details are rendered from the mutation state below.
    } finally {
      setPendingReviewAction(null);
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
      setPlanVersion((current) =>
        current ? { ...current, project_id: createdTaskQueue.project_id } : current,
      );
    } catch {
      // Error details are rendered from the mutation state below.
    }
  };

  const handleRunWorkerOnce = async () => {
    if (!taskCreation?.project_id || !canRunWorkerOnce) {
      return;
    }

    const confirmed = window.confirm(
      "即将启动一次执行：Provider 已配置，启动后可能调用真实 AI provider 并产生费用。本次仅产生 Run / 日志 / 摘要 / 交付物 / 审批，不会执行 git commit / git push / apply-local。是否继续？",
    );

    if (!confirmed) {
      return;
    }

    try {
      await runWorkerOnceMutation.mutateAsync(taskCreation.project_id);
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
    <>
      <section
        data-testid="director-chat-entry"
        className="flex flex-col rounded-lg border border-[#333333] bg-[#1a1a1a] p-6 lg:min-h-[calc(100vh-220px)]"
      >
        <div className="mb-5 shrink-0">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-zinc-100">AI 项目主管</h2>
              <p className="mt-1.5 text-sm text-zinc-500">
                提出目标、澄清范围、查看项目草案并完成审核。草案通过前不会自动执行任何真实任务。
              </p>
            </div>
            <span className="inline-flex w-fit max-w-full items-center rounded-full border border-[#333333] bg-[#111111] px-3 py-1 text-xs text-zinc-400">
              {scopedProjectId
                ? `项目上下文：${selectedProjectName}`
                : mode === "new-project"
                  ? "新项目会话：project_id=null"
                  : "全部项目视图：新会话不绑定单个项目"}
            </span>
          </div>
          {directorStatusMessage ? (
            <div className="mt-4 rounded border border-cyan-500/30 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-100">
              {directorStatusMessage}
            </div>
          ) : null}
        </div>

        <div className="mb-5 min-h-[160px] flex-1 overflow-y-auto">
          {session ? (
            <div className="space-y-4">
              <div className="rounded-lg border border-[#333333] bg-[#111111] p-4">
                <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
                  <span>会话 {session.id.slice(0, 8)}</span>
                  <StatusBadge
                    label={session.status}
                    tone={mapSessionTone(session.status)}
                  />
                  <span className="rounded border border-[#333333] px-2 py-0.5 text-zinc-400">
                    Gate: {session.gate_conclusion}
                  </span>
                </div>
                <p className="whitespace-pre-wrap text-sm text-zinc-300">
                  {session.goal_text}
                </p>
              </div>

              <div className="rounded-lg border border-blue-500/20 bg-blue-500/5 p-4">
                <h3 className="text-sm font-medium text-blue-200">需要你澄清的问题</h3>
                {session.clarifying_questions.length > 0 ? (
                  <ol className="mt-3 space-y-3">
                    {session.clarifying_questions.map((question, index) => {
                      const existingAnswer = session.clarifying_answers.find(
                        (answer) => answer.question_id === question.id,
                      );

                      return (
                        <li
                          key={question.id}
                          className="rounded border border-[#333333] bg-[#171717] p-3"
                        >
                          <div className="flex items-start gap-2">
                            <span className="mt-0.5 rounded bg-blue-500/10 px-1.5 py-0.5 text-[10px] text-blue-300">
                              Q{index + 1}
                            </span>
                            <div className="min-w-0 flex-1">
                              <p className="text-sm text-zinc-200">
                                {question.question}
                                {question.required ? (
                                  <span className="ml-1 text-[10px] text-amber-300">
                                    必答
                                  </span>
                                ) : null}
                              </p>
                              <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-zinc-600">
                                <span
                                  className={`rounded border px-1.5 py-0.5 ${
                                    question.source === "ai"
                                      ? "border-emerald-500/30 text-emerald-300"
                                      : "border-amber-500/30 text-amber-300"
                                  }`}
                                >
                                  来源：
                                  {question.source === "ai"
                                    ? "AI 生成"
                                    : "系统规则生成"}
                                </span>
                              </div>
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
                                  回答：{existingAnswer?.answer ?? "未提交"}
                                </p>
                              )}
                            </div>
                          </div>
                        </li>
                      );
                    })}
                  </ol>
                ) : (
                  <p className="mt-2 text-sm text-zinc-500">后端暂未返回澄清问题。</p>
                )}
                {session.status === "clarifying" ? (
                  <div className="mt-4 flex flex-col gap-2 border-t border-blue-500/10 pt-4 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-xs text-zinc-500">
                      回答全部必答问题后，将进入“待确认目标”状态。
                    </p>
                    <button
                      type="button"
                      disabled={!canSubmitAnswers}
                      onClick={() => {
                        void handleSubmitAnswers();
                      }}
                      className="rounded border border-blue-500/40 bg-blue-500/10 px-3 py-1.5 text-xs font-medium text-blue-200 transition hover:bg-blue-500/20 disabled:cursor-not-allowed disabled:border-[#333333] disabled:bg-[#171717] disabled:text-zinc-600"
                    >
                      {submitAnswersMutation.isPending ? "提交中..." : "提交澄清回答"}
                    </button>
                  </div>
                ) : null}
              </div>

              {(session.status === "ready_to_confirm" ||
                session.status === "confirmed") && (
                <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <h3 className="text-sm font-medium text-emerald-200">目标摘要</h3>
                      <p className="mt-2 whitespace-pre-wrap text-sm text-zinc-300">
                        {session.goal_summary || "后端尚未返回目标摘要。"}
                      </p>
                      <p className="mt-2 text-xs text-zinc-500">
                        目标确认后，才会进入项目草案生成与审核阶段。
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
                          {createPlanVersionMutation.isPending
                            ? "思考草案中..."
                            : planVersion
                              ? "重新生成项目草案"
                              : "生成项目草案"}
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
              )}

              {planVersion ? (
                <div className="rounded-lg border border-violet-500/20 bg-violet-500/5 p-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
                        <StatusBadge label={`草案 v${planVersion.version_no}`} tone="info" />
                        <StatusBadge
                          label={PROJECT_DIRECTOR_PLAN_STATUS_LABELS[planVersion.status]}
                          tone={mapPlanTone(planVersion.status)}
                        />
                        <span>Gate: {planVersion.gate_conclusion}</span>
                      </div>
                      <h3 className="mt-3 text-sm font-medium text-violet-200">
                        AI 项目主管项目草案
                      </h3>
                      <p className="mt-2 text-sm text-zinc-300">
                        当前草案包含 {planVersion.phases.length} 个阶段、
                        {planVersion.proposed_tasks.length} 个拟议任务，需经人工审核后才能继续。
                      </p>
                      <p className="mt-2 text-xs text-zinc-500">
                        下一步：{planVersion.next_action}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-wrap gap-2">
                      <button
                        type="button"
                        data-testid="view-project-director-plan-draft"
                        onClick={() => setIsPlanReviewOpen(true)}
                        className="rounded border border-violet-500/40 bg-violet-500/10 px-3 py-1.5 text-xs font-medium text-violet-100 transition hover:bg-violet-500/20"
                      >
                        查看项目草案
                      </button>
                      {planVersion.status === "confirmed" ? (
                        <button
                          type="button"
                          disabled={!canCreateTaskQueue}
                          onClick={() => {
                            void handleCreateTaskQueue();
                          }}
                          className="rounded border border-cyan-500/40 bg-cyan-500/10 px-3 py-1.5 text-xs font-medium text-cyan-200 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:border-[#333333] disabled:bg-[#171717] disabled:text-zinc-600"
                        >
                          {taskQueueActionLabel}
                        </button>
                      ) : null}
                    </div>
                  </div>
                  {planVersion.confirmed_at ? (
                    <p className="mt-3 text-xs text-emerald-300/80">
                      草案通过时间：{planVersion.confirmed_at}
                    </p>
                  ) : null}
                  {planVersion.forbidden_actions.length > 0 ? (
                    <p className="mt-3 text-xs text-zinc-500">
                      边界：{planVersion.forbidden_actions.join(" / ")}
                    </p>
                  ) : null}

                  {taskCreation ? (
                    <div className="mt-4 rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-4">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0">
                          <h3 className="text-sm font-medium text-emerald-200">
                            正式项目与任务队列已创建
                          </h3>
                          <p className="mt-1 text-xs text-zinc-500">
                            项目 {taskCreation.project_name ?? taskCreation.project_id.slice(0, 8)}
                            {" · "}任务数 {taskCreation.task_count} · 队列状态 {taskCreation.status}
                            {" · "}Gate: {taskCreation.gate_conclusion}
                          </p>
                        </div>
                        <div className="flex shrink-0 flex-wrap gap-2 sm:justify-end">
                          <div
                            className="flex basis-full flex-wrap items-center gap-2 sm:justify-end"
                            data-testid="director-chat-provider-status"
                          >
                            <StatusBadge label={providerStatus.label} tone={providerStatus.tone} />
                            <span className="text-[11px] text-zinc-500">
                              {providerStatus.detail}
                            </span>
                          </div>
                          <button
                            type="button"
                            data-testid="director-chat-run-worker-once"
                            disabled={!canRunWorkerOnce}
                            onClick={() => {
                              void handleRunWorkerOnce();
                            }}
                            className="rounded border border-cyan-500/40 bg-cyan-500/10 px-3 py-1.5 text-xs font-medium text-cyan-200 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:border-[#333333] disabled:bg-[#171717] disabled:text-zinc-600"
                          >
                            {runWorkerOnceMutation.isPending ? "启动中..." : "启动一次执行"}
                          </button>
                          <Link
                            to={`/execution?tab=tasks&projectId=${encodeURIComponent(taskCreation.project_id)}`}
                            className="rounded border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-200 transition hover:bg-emerald-500/20"
                          >
                            查看执行中心
                          </Link>
                          <Link
                            to={`/projects/${encodeURIComponent(taskCreation.project_id)}`}
                            className="rounded border border-[#333333] bg-[#111111] px-3 py-1.5 text-xs font-medium text-zinc-300 transition hover:border-emerald-500/40 hover:text-emerald-200"
                          >
                            查看正式项目
                          </Link>
                        </div>
                      </div>
                      <div className="mt-3 space-y-2 rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs leading-5 text-amber-100/90">
                        <p data-testid="director-chat-real-run-confirmation-copy">
                          运行前确认：点击“启动一次执行”后会再次确认；Provider 已配置时，启动后可能调用真实 AI provider 并产生费用。
                        </p>
                        {providerConfigured ? (
                          <p data-testid="director-chat-real-run-budget-copy">
                            每日预算：{formatNullableCurrencyUsd(budgetHealth?.daily_budget_usd ?? null)}
                            {"，"}会话预算：{formatNullableCurrencyUsd(budgetHealth?.session_budget_usd ?? null)}
                            {"；"}本次可能产生费用。
                          </p>
                        ) : null}
                        <p data-testid="director-chat-real-run-safety-copy">
                          安全声明：本次仅产生 Run / 日志 / 摘要 / 交付物 / 审批，不会执行 git commit / git push / apply-local。
                        </p>
                      </div>
                      <p className="mt-3 whitespace-pre-wrap text-sm text-zinc-300">
                        {taskCreation.next_action}
                      </p>
                      {taskCreation.warnings.length > 0 ? (
                        <div className="mt-3 rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2">
                          <p className="text-xs font-medium text-amber-100">
                            创建结果边界提示
                          </p>
                          <ul className="mt-2 list-disc space-y-1 pl-5 text-xs leading-5 text-amber-100/90">
                            {taskCreation.warnings.map((warning) => (
                              <li key={warning}>{warning}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                      {workerRunOnceResult ? (
                        <div
                          data-testid="director-worker-run-result"
                          className="mt-3 rounded border border-cyan-500/20 bg-cyan-500/5 p-3"
                        >
                          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                            <div className="min-w-0">
                              <p className="text-xs font-medium text-cyan-200">
                                {workerRunOnceResult.claimed
                                  ? "已启动一次执行"
                                  : "当前没有可执行任务"}
                              </p>
                              {workerRunOnceResult.task_title ? (
                                <p className="mt-1 text-sm text-zinc-200">
                                  {workerRunOnceResult.task_title}
                                </p>
                              ) : null}
                            </div>
                            <div className="grid shrink-0 gap-1 text-xs text-zinc-500 sm:text-right">
                              <span>
                                运行记录：
                                {workerRunOnceResult.run_id?.slice(0, 8) ?? "暂无"}
                              </span>
                              <span>
                                用量：
                                {formatNullableTokenCount(workerRunOnceResult.total_tokens)}
                              </span>
                              <span>
                                预估费用：
                                {formatNullableCurrencyUsd(workerRunOnceResult.estimated_cost)}
                              </span>
                            </div>
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2">
                            {workerRunOnceResult.run_id ? (
                              <Link
                                to={buildRunRoute({
                                  runId: workerRunOnceResult.run_id,
                                  taskId: workerRunOnceResult.task_id,
                                  projectId: taskCreation.project_id,
                                  from: "workbench",
                                })}
                                className="rounded border border-cyan-500/40 bg-cyan-500/10 px-2 py-1 text-[10px] text-cyan-200 transition hover:bg-cyan-500/20"
                              >
                                查看运行记录、日志与摘要
                              </Link>
                            ) : null}
                            {workerRunOnceResult.task_id ? (
                              <Link
                                to={buildTaskRoute({
                                  taskId: workerRunOnceResult.task_id,
                                  projectId: taskCreation.project_id,
                                  from: "workbench",
                                })}
                                className="rounded border border-[#333333] bg-[#111111] px-2 py-1 text-[10px] text-zinc-400 transition hover:border-cyan-500/40 hover:text-cyan-200"
                              >
                                查看任务
                              </Link>
                            ) : null}
                          </div>
                        </div>
                      ) : null}
                      {runWorkerOnceMutation.isError ? (
                        <p className="mt-3 rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                          启动失败：{runWorkerOnceMutation.error.message}
                        </p>
                      ) : null}
                      {taskCreation.created_task_ids.length > 0 ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {visibleTaskIds.map((taskId, index) => (
                            <Link
                              key={taskId}
                              to={buildTaskRoute({
                                taskId,
                                projectId: taskCreation.project_id,
                                from: "workbench",
                              })}
                              title={taskId}
                              className="rounded border border-[#333333] bg-[#111111] px-2 py-1 text-[10px] text-zinc-400 transition hover:border-emerald-500/40 hover:text-emerald-200"
                            >
                              任务 {index + 1} · {taskId.slice(0, 8)}
                            </Link>
                          ))}
                          {hiddenTaskCount > 0 ? (
                            <span className="rounded border border-[#333333] bg-[#111111] px-2 py-1 text-[10px] text-zinc-500">
                              等 {hiddenTaskCount} 个任务
                            </span>
                          ) : null}
                        </div>
                      ) : null}
                      {taskCreation.forbidden_actions.length > 0 ? (
                        <p className="mt-3 text-xs text-zinc-500">
                          创建边界：{taskCreation.forbidden_actions.join(" / ")}
                        </p>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ) : null}

              {submitAnswersMutation.isError ? (
                <ErrorLine message={submitAnswersMutation.error.message} />
              ) : null}
              {confirmGoalMutation.isError ? (
                <ErrorLine message={confirmGoalMutation.error.message} />
              ) : null}
              {createPlanVersionMutation.isError ? (
                <ErrorLine message={createPlanVersionMutation.error.message} />
              ) : null}
              {reviewPlanVersionMutation.isError ? (
                <ErrorLine message={reviewPlanVersionMutation.error.message} />
              ) : null}
              {createTaskQueueMutation.isError ? (
                <ErrorLine message={createTaskQueueMutation.error.message} />
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
                <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-600">
                  {mode === "new-project" ? "新项目入口" : "项目主管对话"}
                </p>
                <h3 className="mt-2 text-lg font-semibold text-zinc-100">
                  {mode === "new-project"
                    ? "还没有正式项目时，从这里开始"
                    : scopedProjectId
                      ? `继续调度：${selectedProjectName}`
                      : "选择新项目会话或指定已有项目"}
                </h3>
                <p className="mb-4 mt-2 text-sm leading-6 text-zinc-500">
                  {mode === "new-project"
                    ? "输入目标后会创建 AI 项目主管会话，payload 中 project_id=null；系统优先生成贴合目标的澄清问题，必要时自动使用安全规则兜底。确认草案前不会创建任务或启动 Worker。"
                    : "输入目标或调度问题后会创建 AI 项目主管会话；选择具体已有项目时会带入该项目上下文，选择全部项目时不会绑定单个项目。"}
                </p>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {EXAMPLE_QUESTIONS.map((question) => (
                    <button
                      key={question}
                      type="button"
                      onClick={() => handleExampleClick(question)}
                      className="rounded border border-[#333333] px-3 py-2 text-left text-xs text-zinc-400 transition hover:border-zinc-500 hover:bg-[#222222] hover:text-zinc-200"
                    >
                      {question}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="shrink-0">
          <div className="relative rounded-md border border-[#333333] bg-[#111111] focus-within:border-zinc-500">
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="描述你的项目目标或当前遇到的问题..."
              rows={3}
              className="w-full resize-none bg-transparent px-4 py-3 pr-24 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none"
            />
            <div className="absolute bottom-2 right-2 flex items-center gap-2">
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
            <p>Ctrl/⌘ + Enter 发送；发送后会进入目标澄清与项目草案审核流程。</p>
            {scopedProjectId ? (
              <p>当前项目范围：{selectedProjectName}</p>
            ) : mode === "new-project" ? (
              <p>新项目模式：project_id=null</p>
            ) : (
              <p>全局项目范围</p>
            )}
          </div>
          {createSessionMutation.isError ? (
            <p className="mt-2 rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
              {createSessionMutation.error.message}
            </p>
          ) : null}
        </div>
      </section>

      <ProjectDirectorPlanReviewModal
        open={isPlanReviewOpen}
        onClose={() => setIsPlanReviewOpen(false)}
        planVersion={planVersion}
        reviewFeedback={reviewFeedback}
        onReviewFeedbackChange={setReviewFeedback}
        onReview={(action) => {
          void handleReviewPlanVersion(action);
        }}
        reviewErrorMessage={
          reviewPlanVersionMutation.isError
            ? reviewPlanVersionMutation.error.message
            : null
        }
        reviewStatusMessage={directorStatusMessage}
        isReviewPending={reviewPlanVersionMutation.isPending}
      />
    </>
  );
}

function ErrorLine({ message }: { message: string }) {
  return (
    <p className="rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
      {message}
    </p>
  );
}

function mapSessionTone(status: ProjectDirectorSession["status"]) {
  switch (status) {
    case "confirmed":
      return "success" as const;
    case "ready_to_confirm":
      return "warning" as const;
    default:
      return "info" as const;
  }
}

function mapPlanTone(status: ProjectDirectorPlanVersion["status"]) {
  switch (status) {
    case "confirmed":
      return "success" as const;
    case "rejected":
      return "danger" as const;
    case "pending_confirmation":
      return "warning" as const;
    case "superseded":
      return "neutral" as const;
    default:
      return "info" as const;
  }
}
