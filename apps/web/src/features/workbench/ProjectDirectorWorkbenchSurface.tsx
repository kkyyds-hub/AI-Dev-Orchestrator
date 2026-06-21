import { Bot, FolderKanban } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  useConfirmProjectDirectorGoal,
  useCreateProjectDirectorPlanVersion,
  useCreateProjectDirectorSession,
  useCreateProjectDirectorTaskQueue,
  usePostProjectDirectorSessionMessage,
  useProjectDirectorSessionMessages,
  useProjectDirectorWorkbenchResume,
  useReviewProjectDirectorPlanVersion,
  useSubmitProjectDirectorAnswers,
} from "../project-director/hooks";
import type {
  ClarifyingQuestion,
  ProjectDirectorMessage,
  ProjectDirectorPlanReviewAction,
  ProjectDirectorPlanVersion,
  ProjectDirectorSession,
  ProjectDirectorTaskCreationResponse,
} from "../project-director/types";
import { ConversationMessages } from "../ui-selection-lab/components/WorkbenchMockConversation";
import { WorkbenchPlanFlowCard } from "../ui-selection-lab/components/WorkbenchPlanFlowCards";
import { WorkbenchPromptBox } from "../ui-selection-lab/components/WorkbenchPromptBox";
import {
  WorkbenchClarificationPanel,
  type WorkbenchClarificationQuestion,
} from "../ui-selection-lab/components/WorkbenchUserDecisionSurfaces";
import type { MockMessage } from "../ui-selection-lab/mockInteractions";
import type { PlanFlowState } from "../ui-selection-lab/planFlowMock";
import type { WorkbenchDirectorSurfaceContext } from "./WorkbenchExperience";

type ProjectDirectorWorkbenchSurfaceProps = {
  context: WorkbenchDirectorSurfaceContext;
  fallbackProjectId: string | null;
  fallbackProjectName: string;
  mode: "new-project" | "project";
};

export function ProjectDirectorWorkbenchSurface({
  context,
  fallbackProjectId,
  fallbackProjectName,
  mode,
}: ProjectDirectorWorkbenchSurfaceProps) {
  const selectedProjectId =
    context.activeProjectId && !context.activeProjectId.startsWith("project:")
      ? context.activeProjectId
      : fallbackProjectId;
  const selectedProjectName = context.activeProjectName ?? fallbackProjectName;
  const resumeSessionId =
    context.activeConversationId && !context.activeConversationId.startsWith("project:")
      ? context.activeConversationId
      : null;

  const adapter = useProjectDirectorWorkbenchAdapter({
    mode,
    projectId: selectedProjectId,
    projectName: selectedProjectName,
    resumeSessionId,
  });

  const promptBox = <WorkbenchPromptBox onSend={adapter.handlePromptSend} />;

  if (adapter.showWelcome) {
    return (
      <div
        data-testid="workbench-project-director-adapter-surface"
        className="relative flex min-h-0 flex-1 flex-col overflow-hidden bg-black"
      >
        <WorkbenchWelcomeSurface />
        {promptBox}
      </div>
    );
  }

  return (
    <div
      data-testid="workbench-project-director-adapter-surface"
      className="relative flex min-h-0 flex-1 flex-col overflow-hidden bg-black"
    >
      <ConversationMessages
        messages={adapter.messages}
        topSurface={adapter.topSurface}
        planFlowCard={adapter.planFlowCard}
      />
      {promptBox}
    </div>
  );
}

function useProjectDirectorWorkbenchAdapter(input: {
  mode: "new-project" | "project";
  projectId: string | null;
  projectName: string;
  resumeSessionId: string | null;
}) {
  const [session, setSession] = useState<ProjectDirectorSession | null>(null);
  const [planVersion, setPlanVersion] = useState<ProjectDirectorPlanVersion | null>(null);
  const [taskCreation, setTaskCreation] =
    useState<ProjectDirectorTaskCreationResponse | null>(null);
  const [messageTimeline, setMessageTimeline] = useState<ProjectDirectorMessage[]>([]);
  const [answerDrafts, setAnswerDrafts] = useState<Record<string, string>>({});
  const [planFeedback, setPlanFeedback] = useState("");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const createSessionMutation = useCreateProjectDirectorSession();
  const postMessageMutation = usePostProjectDirectorSessionMessage();
  const submitAnswersMutation = useSubmitProjectDirectorAnswers();
  const confirmGoalMutation = useConfirmProjectDirectorGoal();
  const createPlanVersionMutation = useCreateProjectDirectorPlanVersion();
  const reviewPlanVersionMutation = useReviewProjectDirectorPlanVersion();
  const createTaskQueueMutation = useCreateProjectDirectorTaskQueue();
  const resumeQuery = useProjectDirectorWorkbenchResume({
    mode: input.mode,
    projectId: input.mode === "project" ? input.projectId : null,
    sessionId: input.resumeSessionId,
  }, {
    enabled: Boolean(input.resumeSessionId),
  });
  const messagesQuery = useProjectDirectorSessionMessages(session?.id ?? null);

  useEffect(() => {
    setSession(null);
    setPlanVersion(null);
    setTaskCreation(null);
    setMessageTimeline([]);
    setAnswerDrafts({});
    setPlanFeedback("");
    setStatusMessage(null);
  }, [input.mode, input.projectId, input.resumeSessionId]);

  useEffect(() => {
    const resume = resumeQuery.data;
    if (!resume?.session) {
      return;
    }

    setSession(resume.session);
    setPlanVersion(resume.plan_version);
    setTaskCreation(resume.task_creation);
    setMessageTimeline(resume.recent_messages ?? []);
    setStatusMessage(resume.next_action || null);
  }, [resumeQuery.data]);

  useEffect(() => {
    if (messagesQuery.data?.messages) {
      setMessageTimeline(messagesQuery.data.messages);
    }
  }, [messagesQuery.data]);

  const isMutating =
    createSessionMutation.isPending ||
    postMessageMutation.isPending ||
    submitAnswersMutation.isPending ||
    confirmGoalMutation.isPending ||
    createPlanVersionMutation.isPending ||
    reviewPlanVersionMutation.isPending ||
    createTaskQueueMutation.isPending;

  const requiredQuestions =
    session?.clarifying_questions.filter((question) => question.required) ?? [];
  const requiredAnswersReady = requiredQuestions.every(
    (question) => (answerDrafts[question.id] ?? "").trim().length > 0,
  );

  async function handlePromptSend(text: string) {
    const trimmed = text.trim();
    if (!trimmed || isMutating) {
      return;
    }

    if (session) {
      const result = await postMessageMutation.mutateAsync({
        sessionId: session.id,
        content: trimmed,
      });
      setMessageTimeline(result.messages);
      setStatusMessage("AI 项目主管已回复。");
      return;
    }

    const createdSession = await createSessionMutation.mutateAsync({
      goal_text: trimmed,
      project_id: input.mode === "project" ? input.projectId : null,
      constraints: "",
    });
    setSession(createdSession);
    setPlanVersion(null);
    setTaskCreation(null);
    setStatusMessage(createdSession.next_action);
  }

  async function handleSubmitAnswers() {
    if (!session || !requiredAnswersReady || submitAnswersMutation.isPending) {
      return;
    }

    const answers = session.clarifying_questions
      .map((question) => ({
        question_id: question.id,
        answer: (answerDrafts[question.id] ?? "").trim(),
      }))
      .filter((answer) => answer.answer.length > 0);

    const updatedSession = await submitAnswersMutation.mutateAsync({
      sessionId: session.id,
      answers,
    });
    setSession(updatedSession);
    setStatusMessage(updatedSession.next_action);
  }

  async function handleConfirmGoal() {
    if (!session || session.status !== "ready_to_confirm") {
      return;
    }

    const updatedSession = await confirmGoalMutation.mutateAsync({
      sessionId: session.id,
    });
    setSession(updatedSession);
    setStatusMessage(updatedSession.next_action);
  }

  async function handleCreatePlanVersion() {
    if (!session || session.status !== "confirmed") {
      return;
    }

    const createdPlanVersion = await createPlanVersionMutation.mutateAsync({
      sessionId: session.id,
    });
    setPlanVersion(createdPlanVersion);
    setPlanFeedback("");
    setStatusMessage(createdPlanVersion.next_action);
  }

  async function handleReviewPlanVersion(action: ProjectDirectorPlanReviewAction) {
    if (!planVersion || planVersion.status !== "pending_confirmation") {
      return;
    }

    const result = await reviewPlanVersionMutation.mutateAsync({
      planVersionId: planVersion.id,
      action,
      feedback: planFeedback,
    });
    const nextPlan = result.replacement_plan_version ?? result.reviewed_plan_version;
    setPlanVersion(nextPlan);
    setPlanFeedback("");
    setTaskCreation(null);
    setStatusMessage(result.next_action);
  }

  async function handleCreateFormalProject() {
    if (!planVersion || planVersion.status !== "confirmed") {
      return;
    }

    const createdTaskQueue = await createTaskQueueMutation.mutateAsync({
      planVersionId: planVersion.id,
    });
    setTaskCreation(createdTaskQueue);
    setStatusMessage(createdTaskQueue.next_action);
  }

  const messages = useMemo(
    () =>
      buildDirectorMessages({
        session,
        messages: messageTimeline,
        statusMessage,
        isLoading: resumeQuery.isLoading && Boolean(input.resumeSessionId),
        errorMessage:
          createSessionMutation.error?.message ??
          postMessageMutation.error?.message ??
          messagesQuery.error?.message ??
          null,
      }),
    [
      createSessionMutation.error?.message,
      input.resumeSessionId,
      messageTimeline,
      messagesQuery.error?.message,
      postMessageMutation.error?.message,
      resumeQuery.isLoading,
      session,
      statusMessage,
    ],
  );

  const topSurface = session?.status === "clarifying" ? (
    <WorkbenchClarificationPanel
      questions={session.clarifying_questions.map(mapClarifyingQuestion)}
      answers={answerDrafts}
      onAnswerChange={(questionId, answer) =>
        setAnswerDrafts((current) => ({ ...current, [questionId]: answer }))
      }
      onSubmit={() => {
        void handleSubmitAnswers();
      }}
      submitDisabled={!requiredAnswersReady || submitAnswersMutation.isPending}
      submitLabel={submitAnswersMutation.isPending ? "提交中..." : "提交澄清"}
      description="这些问题来自真实 AI 主管会话；提交后再进入目标确认。"
    />
  ) : session?.status === "ready_to_confirm" ? (
    <GoalConfirmationPanel
      summary={session.goal_summary || session.goal_text}
      disabled={confirmGoalMutation.isPending}
      onConfirm={() => {
        void handleConfirmGoal();
      }}
    />
  ) : session?.status === "confirmed" && !planVersion ? (
    <GoalConfirmationPanel
      summary={session.goal_summary || session.goal_text}
      disabled={createPlanVersionMutation.isPending}
      confirmLabel={createPlanVersionMutation.isPending ? "生成中..." : "生成计划草案"}
      onConfirm={() => {
        void handleCreatePlanVersion();
      }}
    />
  ) : null;

  const planFlowCard = planVersion ? (
    <WorkbenchPlanFlowCard
      state={mapPlanVersionToPlanFlowState(planVersion, taskCreation, planFeedback)}
      defaultCollapsed={false}
      onFeedbackChange={setPlanFeedback}
      onRequestChanges={() => {
        void handleReviewPlanVersion("request_changes");
      }}
      onReject={() => {
        void handleReviewPlanVersion("reject");
      }}
      onConfirm={() => {
        void handleReviewPlanVersion("approve");
      }}
      onCreateProject={() => {
        void handleCreateFormalProject();
      }}
    />
  ) : null;

  return {
    handlePromptSend,
    showWelcome:
      !session &&
      messageTimeline.length === 0 &&
      !resumeQuery.isLoading &&
      !createSessionMutation.isError &&
      !postMessageMutation.isError &&
      !messagesQuery.isError,
    messages,
    topSurface,
    planFlowCard,
  };
}

function WorkbenchWelcomeSurface() {
  return (
    <div
      data-testid="workbench-director-welcome"
      className="flex min-h-0 flex-1 flex-col items-center justify-center px-5 pb-24 pt-6 text-center md:px-8 md:pb-28 lg:px-10"
    >
      <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-2xl border border-[#2A2A2A] bg-black md:mb-5 md:h-14 md:w-14">
        <Bot className="h-6 w-6 text-[#C7C7C7] md:h-7 md:w-7" />
      </div>
      <h1 className="text-3xl font-semibold tracking-normal text-white md:text-[42px]">
        欢迎
      </h1>
      <h2 className="mt-3 text-xl font-semibold tracking-normal text-[#C7C7C7] md:mt-4 md:text-2xl">
        我们来构建什么？
      </h2>
      <p className="mt-3 max-w-xl text-sm leading-6 text-[#8A8A8A] md:mt-4">
        创建一个项目，AI 主管会逐步帮你澄清目标、生成计划并推进执行
      </p>

      <button
        type="button"
        className="mt-8 flex h-11 items-center gap-2 rounded-[14px] bg-white px-5 text-sm font-semibold text-black transition-all duration-150 hover:bg-[#EDEDED] active:scale-[0.99]"
        onClick={() => {
          const promptInput = document.querySelector<HTMLTextAreaElement>(
            '[data-testid="ui-lab-promptbox"] textarea',
          );
          promptInput?.focus();
        }}
      >
        <FolderKanban className="h-4 w-4" />
        创建项目
      </button>
    </div>
  );
}

function buildDirectorMessages(input: {
  session: ProjectDirectorSession | null;
  messages: ProjectDirectorMessage[];
  statusMessage: string | null;
  isLoading: boolean;
  errorMessage: string | null;
}): MockMessage[] {
  if (input.messages.length > 0) {
    return input.messages.map(mapProjectDirectorMessage);
  }

  if (input.errorMessage) {
    return [
      {
        role: "assistant",
        content: `读取 AI 主管会话失败：${input.errorMessage}`,
        time: "刚刚",
      },
    ];
  }

  if (input.isLoading) {
    return [
      {
        role: "assistant",
        content: "正在恢复 AI 主管会话...",
        time: "刚刚",
      },
    ];
  }

  if (input.session) {
    return [
      {
        role: "user",
        content: input.session.goal_text,
        time: formatTime(input.session.created_at),
      },
      {
        role: "assistant",
        content:
          input.statusMessage ||
          input.session.next_action ||
          "我会先澄清目标，再生成需要你确认的计划草案。",
        time: formatTime(input.session.updated_at),
      },
    ];
  }

  return [
    {
      role: "assistant",
      content: "创建一个项目或选择一个已有项目来开始。",
      time: "刚刚",
    },
  ];
}

function mapProjectDirectorMessage(message: ProjectDirectorMessage): MockMessage {
  return {
    role: message.role === "user" ? "user" : "assistant",
    content: message.content,
    time: formatTime(message.created_at),
  };
}

function mapClarifyingQuestion(
  question: ClarifyingQuestion,
): WorkbenchClarificationQuestion {
  return {
    id: question.id,
    label: question.required ? "必答" : "可选",
    question: question.question,
    hint: question.hint || "补充你的回答...",
    required: question.required,
  };
}

function mapPlanVersionToPlanFlowState(
  planVersion: ProjectDirectorPlanVersion,
  taskCreation: ProjectDirectorTaskCreationResponse | null,
  feedbackDraft: string,
): PlanFlowState {
  const stage =
    taskCreation
      ? "created"
      : planVersion.status === "confirmed"
        ? "confirmed"
        : planVersion.status === "rejected"
          ? "rejected"
          : planVersion.status === "superseded"
            ? "changes_requested"
            : "draft";

  return {
    stage,
    title: `计划草案 v${planVersion.version_no}`,
    summary: planVersion.plan_summary || planVersion.next_action,
    projectName: taskCreation?.project_name ?? "正式项目",
    revisionCount: Math.max(0, planVersion.version_no - 1),
    feedbackDraft,
    confirmedAt: planVersion.confirmed_at ?? undefined,
    rejectedAt: stage === "rejected" ? planVersion.updated_at : undefined,
    projectCreated: Boolean(taskCreation),
    createdProjectName: taskCreation?.project_name ?? undefined,
    sections: [
      {
        label: "范围",
        value:
          planVersion.project_scope.in_scope.slice(0, 3).join("、") ||
          "等待 AI 主管补全范围。",
      },
      {
        label: "阶段",
        value:
          planVersion.phases.map((phase) => phase.name).slice(0, 3).join("、") ||
          "等待阶段拆分。",
      },
      {
        label: "任务",
        value: `${planVersion.proposed_tasks.length} 个拟议任务，确认后再创建正式任务队列。`,
      },
    ],
    milestones:
      planVersion.acceptance_criteria.length > 0
        ? planVersion.acceptance_criteria.slice(0, 4)
        : ["确认计划草案", "创建正式项目", "后续进入执行和成果跟踪"],
  };
}

function GoalConfirmationPanel({
  summary,
  disabled,
  confirmLabel = "确认目标",
  onConfirm,
}: {
  summary: string;
  disabled: boolean;
  confirmLabel?: string;
  onConfirm: () => void;
}) {
  return (
    <section className="w-full max-w-[880px] border-y border-[#2A2A2A] py-5">
      <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-[#8A8A8A]">
        目标确认
      </div>
      <h3 className="mt-2 text-lg font-semibold tracking-normal text-white">
        确认后再生成计划
      </h3>
      <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[#C7C7C7]">
        {summary}
      </p>
      <div className="mt-5 flex justify-end border-t border-[#1F1F1F] pt-4">
        <button
          type="button"
          disabled={disabled}
          onClick={onConfirm}
          className="rounded-full bg-white px-4 py-2 text-sm font-semibold text-black transition hover:bg-[#EDEDED] disabled:cursor-not-allowed disabled:bg-[#2C2C2C] disabled:text-[#5F5F5F]"
        >
          {confirmLabel}
        </button>
      </div>
    </section>
  );
}

function formatTime(value: string | null) {
  if (!value) {
    return "刚刚";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "刚刚";
  }

  return date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });
}
