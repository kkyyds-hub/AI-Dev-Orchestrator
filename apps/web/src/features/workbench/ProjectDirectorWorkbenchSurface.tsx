import { Bot, FolderKanban } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  useConfirmProjectDirectorGoal,
  useCreateProjectDirectorSession,
  useCreateProjectDirectorTaskQueue,
  useFormalizeProjectDirectorDiscussion,
  usePostProjectDirectorSessionMessage,
  useProjectDirectorSessionMessages,
  useProjectDirectorWorkbenchResume,
  useReviewProjectDirectorPlanVersion,
  useSubmitProjectDirectorAnswers,
} from "../project-director/hooks";
import type {
  ClarifyingQuestion,
  ProjectDirectorMessage,
  ProjectDirectorDiscussionWorkspace,
  ProjectDirectorFormalizationProposal,
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
  WorkbenchDiscussionStateBar,
  WorkbenchFormalizationProposalCard,
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

type PendingPrompt = {
  id: string;
  content: string;
  kind: "create_session" | "post_message";
};

function canOfferDiscussionFormalization(input: {
  workspace: ProjectDirectorDiscussionWorkspace | null;
  proposal: ProjectDirectorFormalizationProposal | null;
  existingWorkspaceVersions: number[];
  planVersion: ProjectDirectorPlanVersion | null;
}): boolean {
  const { workspace, proposal, existingWorkspaceVersions, planVersion } = input;
  if (!workspace) {
    return false;
  }
  if (existingWorkspaceVersions.includes(workspace.version_no)) {
    return false;
  }
  return Boolean(
    (proposal?.requires_confirmation &&
      proposal.workspace_version === workspace.version_no) ||
      (workspace.discussion_status === "ready_to_formalize" &&
        (!planVersion ||
          planVersion.formalization_workspace_version !== workspace.version_no)),
  );
}

function mergeFormalizationWorkspaceVersions(
  existingVersions: number[],
  workspaceVersion: number,
): number[] {
  return [...new Set([...existingVersions, workspaceVersion])].sort(
    (left, right) => left - right,
  );
}

export function ProjectDirectorWorkbenchSurface({
  context,
  fallbackProjectId,
  fallbackProjectName,
  mode,
}: ProjectDirectorWorkbenchSurfaceProps) {
  const selectedProjectId =
    mode === "project"
      ? context.activeProjectId && !context.activeProjectId.startsWith("project:")
        ? context.activeProjectId
        : fallbackProjectId
      : null;
  const selectedProjectName = context.activeProjectName ?? fallbackProjectName;
  const resumeSessionId =
    context.activeConversationId && !context.activeConversationId.startsWith("project:")
      ? context.activeConversationId
      : null;
  const selectionKey = `${mode}:${selectedProjectId ?? "none"}:${resumeSessionId ?? "none"}`;

  return (
    <ProjectDirectorWorkbenchSelection
      key={selectionKey}
      mode={mode}
      projectId={selectedProjectId}
      projectName={selectedProjectName}
      resumeSessionId={resumeSessionId}
    />
  );
}

function ProjectDirectorWorkbenchSelection(input: {
  mode: "new-project" | "project";
  projectId: string | null;
  projectName: string;
  resumeSessionId: string | null;
}) {
  const adapter = useProjectDirectorWorkbenchAdapter({
    mode: input.mode,
    projectId: input.projectId,
    projectName: input.projectName,
    resumeSessionId: input.resumeSessionId,
  });

  const promptBox = (
    <WorkbenchPromptBox
      key={adapter.promptContextKey}
      onSend={adapter.handlePromptSend}
    />
  );

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
  const [pendingPrompt, setPendingPrompt] = useState<PendingPrompt | null>(null);
  const [promptError, setPromptError] = useState<string | null>(null);
  const [answerDrafts, setAnswerDrafts] = useState<Record<string, string>>({});
  const [planFeedback, setPlanFeedback] = useState("");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [discussionWorkspace, setDiscussionWorkspace] =
    useState<ProjectDirectorDiscussionWorkspace | null>(null);
  const [formalizationProposal, setFormalizationProposal] =
    useState<ProjectDirectorFormalizationProposal | null>(null);
  const [formalizationError, setFormalizationError] = useState<string | null>(null);
  const [
    existingFormalizationWorkspaceVersions,
    setExistingFormalizationWorkspaceVersions,
  ] = useState<number[]>([]);
  const contextKey = `${input.mode}:${input.projectId ?? "none"}:${input.resumeSessionId ?? "none"}`;
  const contextKeyRef = useRef(contextKey);
  const pendingPromptIdRef = useRef(0);
  const requestedMode = input.mode;
  const requestedProjectId = requestedMode === "project" ? input.projectId : null;
  const requestedSessionId = input.resumeSessionId;
  const activeSessionId = requestedSessionId ?? session?.id ?? null;

  const createSessionMutation = useCreateProjectDirectorSession();
  const postMessageMutation = usePostProjectDirectorSessionMessage();
  const submitAnswersMutation = useSubmitProjectDirectorAnswers();
  const confirmGoalMutation = useConfirmProjectDirectorGoal();
  const reviewPlanVersionMutation = useReviewProjectDirectorPlanVersion();
  const createTaskQueueMutation = useCreateProjectDirectorTaskQueue();
  const formalizeDiscussionMutation = useFormalizeProjectDirectorDiscussion();
  const resumeQuery = useProjectDirectorWorkbenchResume({
    mode: requestedMode,
    projectId: requestedProjectId,
    sessionId: activeSessionId,
  }, {
    enabled: Boolean(activeSessionId),
  });
  const messagesQuery = useProjectDirectorSessionMessages(activeSessionId);

  useEffect(() => {
    contextKeyRef.current = contextKey;
  }, [contextKey]);

  useEffect(() => {
    setPendingPrompt(null);
    setPromptError(null);
  }, [contextKey]);

  useEffect(() => {
    setSession(null);
    setPlanVersion(null);
    setTaskCreation(null);
    setMessageTimeline([]);
    setAnswerDrafts({});
    setPlanFeedback("");
    setStatusMessage(null);
    setDiscussionWorkspace(null);
    setFormalizationProposal(null);
    setFormalizationError(null);
    setExistingFormalizationWorkspaceVersions([]);
  }, [input.mode, input.projectId, input.resumeSessionId]);

  useEffect(() => {
    const resume = resumeQuery.data;
    if (
      !resume?.session ||
      contextKeyRef.current !== contextKey ||
      !isSessionForSelection(
        resume.session,
        requestedMode,
        requestedProjectId,
        activeSessionId,
      ) ||
      !areMessagesForSession(resume.recent_messages ?? [], resume.session.id)
    ) {
      return;
    }

    setSession(resume.session);
    setPlanVersion(resume.plan_version);
    setTaskCreation(resume.task_creation);
    setMessageTimeline(resume.recent_messages ?? []);
    setDiscussionWorkspace(resume.discussion_workspace);
    setExistingFormalizationWorkspaceVersions(
      resume.existing_formalization_workspace_versions ?? [],
    );
    setFormalizationProposal((current) =>
      current?.workspace_version === resume.discussion_workspace?.version_no
        ? current
        : null,
    );
    setStatusMessage(resume.next_action || null);
  }, [
    activeSessionId,
    contextKey,
    requestedMode,
    requestedProjectId,
    resumeQuery.data,
  ]);

  useEffect(() => {
    const response = messagesQuery.data;
    if (
      !response ||
      !activeSessionId ||
      contextKeyRef.current !== contextKey ||
      response.session_id !== activeSessionId ||
      !areMessagesForSession(response.messages, activeSessionId)
    ) {
      return;
    }
    setMessageTimeline(response.messages);
  }, [activeSessionId, contextKey, messagesQuery.data]);

  const isMutating =
    createSessionMutation.isPending ||
    postMessageMutation.isPending ||
    submitAnswersMutation.isPending ||
    confirmGoalMutation.isPending ||
    reviewPlanVersionMutation.isPending ||
    createTaskQueueMutation.isPending ||
    formalizeDiscussionMutation.isPending;

  const requiredQuestions =
    session?.clarifying_questions.filter((question) => question.required) ?? [];
  const requiredAnswersReady = requiredQuestions.every(
    (question) => (answerDrafts[question.id] ?? "").trim().length > 0,
  );

  async function handlePromptSend(text: string): Promise<boolean> {
    const trimmed = text.trim();
    if (!trimmed || isMutating) {
      return false;
    }

    if (session) {
      const requestContextKey = contextKeyRef.current;
      const requestSessionId = session.id;
      setPendingPrompt({
        id: `pending-${++pendingPromptIdRef.current}`,
        content: trimmed,
        kind: "post_message",
      });
      setPromptError(null);
      try {
        const result = await postMessageMutation.mutateAsync({
          sessionId: requestSessionId,
          content: trimmed,
        });
        if (
          contextKeyRef.current !== requestContextKey ||
          result.session_id !== requestSessionId ||
          !areMessagesForSession(
            [result.user_message, result.assistant_message],
            requestSessionId,
          )
        ) {
          return false;
        }
        setMessageTimeline((current) =>
          mergeProjectDirectorMessages(current, [result.user_message, result.assistant_message]),
        );
        setPendingPrompt(null);
        setFormalizationProposal(result.formalization_proposal);
        setFormalizationError(null);
        setStatusMessage("AI 项目主管已回复。");
        const resumeResult = await resumeQuery.refetch();
        if (
          contextKeyRef.current === requestContextKey &&
          resumeResult.data?.session &&
          isSessionForSelection(
            resumeResult.data.session,
            requestedMode,
            requestedProjectId,
            requestSessionId,
          )
        ) {
          setDiscussionWorkspace(resumeResult.data.discussion_workspace);
          setPlanVersion(resumeResult.data.plan_version);
          setTaskCreation(resumeResult.data.task_creation);
          setExistingFormalizationWorkspaceVersions(
            resumeResult.data.existing_formalization_workspace_versions ?? [],
          );
        }
        return true;
      } catch {
        if (contextKeyRef.current === requestContextKey) {
          setPendingPrompt(null);
          setPromptError("消息发送失败，请重试。");
        }
        return false;
      }
    }

    const requestContextKey = contextKeyRef.current;
    setPendingPrompt({
      id: `pending-${++pendingPromptIdRef.current}`,
      content: trimmed,
      kind: "create_session",
    });
    setPromptError(null);
    try {
      const createdSession = await createSessionMutation.mutateAsync({
        goal_text: trimmed,
        project_id: input.mode === "project" ? input.projectId : null,
        constraints: "",
      });
      if (contextKeyRef.current !== requestContextKey) {
        return false;
      }
      if (
        !isSessionForSelection(
          createdSession,
          requestedMode,
          requestedProjectId,
          createdSession.id,
        )
      ) {
        return false;
      }
      setPendingPrompt(null);
      setSession(createdSession);
      setPlanVersion(null);
      setTaskCreation(null);
      setDiscussionWorkspace(null);
      setFormalizationProposal(null);
      setFormalizationError(null);
      setExistingFormalizationWorkspaceVersions([]);
      setStatusMessage(createdSession.next_action);
      return true;
    } catch {
      if (contextKeyRef.current === requestContextKey) {
        setPendingPrompt(null);
        setPromptError("消息发送失败，请重试。");
      }
      return false;
    }
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

    const requestContextKey = contextKeyRef.current;
    const updatedSession = await submitAnswersMutation.mutateAsync({
      sessionId: session.id,
      answers,
    });
    if (contextKeyRef.current !== requestContextKey) {
      return;
    }
    if (
      !isSessionForSelection(
        updatedSession,
        requestedMode,
        requestedProjectId,
        session.id,
      )
    ) {
      return;
    }
    setSession(updatedSession);
    setStatusMessage(updatedSession.next_action);
  }

  async function handleConfirmGoal() {
    if (!session || session.status !== "ready_to_confirm") {
      return;
    }

    const requestContextKey = contextKeyRef.current;
    const updatedSession = await confirmGoalMutation.mutateAsync({
      sessionId: session.id,
    });
    if (contextKeyRef.current !== requestContextKey) {
      return;
    }
    if (
      !isSessionForSelection(
        updatedSession,
        requestedMode,
        requestedProjectId,
        session.id,
      )
    ) {
      return;
    }
    setSession(updatedSession);
    setStatusMessage(updatedSession.next_action);
  }

  async function handleReviewPlanVersion(action: ProjectDirectorPlanReviewAction) {
    if (!planVersion || planVersion.status !== "pending_confirmation") {
      return;
    }

    const requestContextKey = contextKeyRef.current;
    const result = await reviewPlanVersionMutation.mutateAsync({
      planVersionId: planVersion.id,
      action,
      feedback: planFeedback,
    });
    if (contextKeyRef.current !== requestContextKey) {
      return;
    }
    const nextPlan = result.replacement_plan_version ?? result.reviewed_plan_version;
    setPlanVersion(nextPlan);
    setPlanFeedback("");
    setTaskCreation(null);
    if (action === "request_changes") {
      setFormalizationProposal(null);
      setFormalizationError(null);
    }
    setStatusMessage(result.next_action);
  }

  async function handleCreateFormalProject() {
    if (!planVersion || planVersion.status !== "confirmed") {
      return;
    }

    const requestContextKey = contextKeyRef.current;
    const createdTaskQueue = await createTaskQueueMutation.mutateAsync({
      planVersionId: planVersion.id,
    });
    if (contextKeyRef.current !== requestContextKey) {
      return;
    }
    setTaskCreation(createdTaskQueue);
    setStatusMessage(createdTaskQueue.next_action);
  }

  async function handleFormalizeDiscussion() {
    if (!session || !discussionWorkspace || formalizeDiscussionMutation.isPending) {
      return;
    }
    if (
      existingFormalizationWorkspaceVersions.includes(
        discussionWorkspace.version_no,
      )
    ) {
      setFormalizationProposal(null);
      setFormalizationError("当前讨论版本已生成过计划草案，请继续审核现有计划。");
      return;
    }
    if (
      !canOfferDiscussionFormalization({
        workspace: discussionWorkspace,
        proposal: formalizationProposal,
        existingWorkspaceVersions: existingFormalizationWorkspaceVersions,
        planVersion,
      })
    ) {
      return;
    }

    const requestContextKey = contextKeyRef.current;
    setFormalizationError(null);
    try {
      const result = await formalizeDiscussionMutation.mutateAsync({
        sessionId: session.id,
        workspaceVersion: discussionWorkspace.version_no,
      });
      if (
        contextKeyRef.current !== requestContextKey ||
        result.session_id !== session.id
      ) {
        return;
      }
      setPlanVersion(result.plan_version);
      setTaskCreation(null);
      setFormalizationProposal(null);
      setFormalizationError(null);
      setExistingFormalizationWorkspaceVersions((current) =>
        mergeFormalizationWorkspaceVersions(current, result.workspace_version),
      );
      setStatusMessage(result.plan_version.next_action);
    } catch (error) {
      if (contextKeyRef.current !== requestContextKey) {
        return;
      }
      const message = error instanceof Error ? error.message : "生成计划草案失败，请重试。";
      if (message.startsWith("project_director_formalization_")) {
        setFormalizationProposal(null);
        setFormalizationError("讨论状态已更新，请重新确认");
        const resumeResult = await resumeQuery.refetch();
        if (
          contextKeyRef.current === requestContextKey &&
          resumeResult.data?.session &&
          isSessionForSelection(
            resumeResult.data.session,
            requestedMode,
            requestedProjectId,
            session.id,
          ) &&
          areMessagesForSession(
            resumeResult.data.recent_messages ?? [],
            session.id,
          )
        ) {
          setSession(resumeResult.data.session);
          setPlanVersion(resumeResult.data.plan_version);
          setTaskCreation(resumeResult.data.task_creation);
          setMessageTimeline(resumeResult.data.recent_messages ?? []);
          setDiscussionWorkspace(resumeResult.data.discussion_workspace);
          setExistingFormalizationWorkspaceVersions(
            resumeResult.data.existing_formalization_workspace_versions ?? [],
          );
        }
        setStatusMessage("讨论状态已更新，请重新确认");
        return;
      }
      setFormalizationError(message);
    }
  }

  const messages = useMemo(
    () =>
      buildDirectorMessages({
        session,
        messages: messageTimeline,
        statusMessage,
        isLoading: resumeQuery.isLoading && Boolean(input.resumeSessionId),
        pendingPrompt,
        promptError,
        loadErrorMessage: messagesQuery.error?.message ?? null,
      }),
    [
      input.resumeSessionId,
      messageTimeline,
      messagesQuery.error?.message,
      pendingPrompt,
      promptError,
      resumeQuery.isLoading,
      session,
      statusMessage,
    ],
  );

  const workflowSurface = session?.status === "clarifying" ? (
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
  ) : null;

  const shouldShowFormalizationCard = canOfferDiscussionFormalization({
    workspace: discussionWorkspace,
    proposal: formalizationProposal,
    existingWorkspaceVersions: existingFormalizationWorkspaceVersions,
    planVersion,
  });

  const topSurface = workflowSurface || discussionWorkspace || shouldShowFormalizationCard ? (
    <div className="grid gap-5">
      <WorkbenchDiscussionStateBar workspace={discussionWorkspace} />
      {formalizationError && !shouldShowFormalizationCard ? (
        <p className="text-sm text-[#F0A6A6]">{formalizationError}</p>
      ) : null}
      {workflowSurface}
      {shouldShowFormalizationCard && discussionWorkspace ? (
        <WorkbenchFormalizationProposalCard
          workspace={discussionWorkspace}
          proposal={formalizationProposal}
          disabled={formalizeDiscussionMutation.isPending}
          errorMessage={formalizationError}
          onConfirm={() => {
            void handleFormalizeDiscussion();
          }}
        />
      ) : null}
    </div>
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
    promptContextKey: contextKey,
    showWelcome:
      !session &&
      messageTimeline.length === 0 &&
      !pendingPrompt &&
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
  pendingPrompt: PendingPrompt | null;
  promptError: string | null;
  loadErrorMessage: string | null;
}): MockMessage[] {
  let result: MockMessage[] = [];
  if (input.messages.length > 0) {
    result = input.messages.map(mapProjectDirectorMessage);
  } else if (input.loadErrorMessage) {
    result = [
      {
        role: "assistant",
        content: `读取 AI 主管会话失败：${input.loadErrorMessage}`,
        time: "刚刚",
      },
    ];
  } else if (input.isLoading) {
    result = [
      {
        role: "assistant",
        content: "正在恢复 AI 主管会话...",
        time: "刚刚",
      },
    ];
  } else if (input.session) {
    result = [
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
  } else if (input.pendingPrompt?.kind !== "create_session") {
    result = [
      {
        role: "assistant",
        content: "创建一个项目或选择一个已有项目来开始。",
        time: "刚刚",
      },
    ];
  }

  if (input.pendingPrompt) {
    result.push({
      role: "user",
      content: input.pendingPrompt.content,
      time: "刚刚",
    });
    result.push({
      role: "assistant",
      content:
        input.pendingPrompt.kind === "create_session"
          ? "正在创建会话并准备澄清问题..."
          : "正在发送消息...",
      time: "刚刚",
    });
  }

  if (input.promptError) {
    result.push({
      role: "assistant",
      content: input.promptError,
      time: "刚刚",
    });
  }

  return result;
}

function isSessionForSelection(
  session: ProjectDirectorSession,
  mode: "new-project" | "project",
  projectId: string | null,
  sessionId: string | null,
): boolean {
  if (!sessionId || session.id !== sessionId) {
    return false;
  }
  return mode === "project"
    ? session.project_id === projectId
    : session.project_id === null;
}

function areMessagesForSession(
  messages: ProjectDirectorMessage[],
  sessionId: string,
): boolean {
  return messages.every((message) => message.session_id === sessionId);
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
      ...(planVersion.formalization_target === "plan_revision"
        ? [
            {
              label: "来源",
              value: `讨论工作区 v${planVersion.formalization_workspace_version}，基于 ${planVersion.formalization_source_message_ids.length} 条消息和 ${planVersion.formalization_source_event_ids.length} 条讨论记录。`,
            },
          ]
        : []),
    ],
    milestones:
      planVersion.acceptance_criteria.length > 0
        ? planVersion.acceptance_criteria.slice(0, 4)
        : ["确认计划草案", "创建正式项目", "后续进入执行和成果跟踪"],
  };
}

function mergeProjectDirectorMessages(
  current: ProjectDirectorMessage[],
  additions: ProjectDirectorMessage[],
): ProjectDirectorMessage[] {
  const messagesById = new Map(
    [...current, ...additions].map((message) => [message.id, message]),
  );
  return [...messagesById.values()].sort(
    (left, right) => left.sequence_no - right.sequence_no,
  );
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
