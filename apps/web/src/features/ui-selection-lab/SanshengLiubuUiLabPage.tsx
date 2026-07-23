import {
  Activity,
  Archive,
  Bot,
  Check,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  CircleEllipsis,
  ClipboardCheck,
  FolderKanban,
  GitBranch,
  LayoutDashboard,
  MessageSquarePlus,
  MoreHorizontal,
  Search,
  Settings,
  User,
  Wallet,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type * as React from "react";

import { cn } from "../../lib/cn";
import {
  AccountSettingsModal,
  type WorkbenchAccountAdapter,
} from "./components/AccountSettingsModal";
import { ComponentPlayground } from "./components/ComponentPlayground";
import { SidebarNavItem } from "./components/SidebarNavItem";
import {
  Avatar,
  AvatarFallback,
  Badge,
  Button,
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Input,
  Separator,
} from "./components/ui";
import { ConversationMessages } from "./components/WorkbenchMockConversation";
import { MockPageContent } from "./components/WorkbenchMockPages";
import type {
  WorkbenchPageAdapterMode,
  WorkbenchPageSurfaceData,
} from "./components/WorkbenchMockPages";
import { WorkbenchPlanFlowCard } from "./components/WorkbenchPlanFlowCards";
import { WorkbenchPromptBox } from "./components/WorkbenchPromptBox";
import {
  ApprovalsModal,
  CostUsageModal,
  DashboardModal,
  ExecutionStatusModal,
  GitWritePreviewModal,
  RepositoryQueueModal,
} from "./components/WorkbenchRuntimeModals";
import {
  WorkbenchSettingsModal,
  type WorkbenchSettingsAdapter,
} from "./components/WorkbenchSettingsModal";
import {
  WorkbenchClarificationPanel,
  WorkbenchProjectNextStepPanel,
  WorkbenchUserActionStrip,
} from "./components/WorkbenchUserDecisionSurfaces";
import {
  getDefaultMessages,
  getNewConversationWelcome,
  mockConversationMessages,
  pageNavItems,
  projectGroups as initialProjectGroups,
  type Conversation,
  type MockMessage,
  type ProjectGroup,
} from "./mockInteractions";
import { applyPlanFlowAction, createInitialPlanFlowState } from "./planFlowMock";

// ── Tokens ─────────────────────────────────────────────────

const minimalDarkTokens = {
  appBg: "#050505",
  sidebarBg: "#080808",
  mainBg: "#000000",
  surface: "#171717",
  surfaceHover: "#222222",
  surfaceActive: "#2C2C2C",
  modalBg: "#1C1C1C",
  popoverBg: "#202020",
  inputBg: "#171717",
  borderSubtle: "#2A2A2A",
  borderStrong: "#3A3A3A",
  textPrimary: "#FFFFFF",
  textSecondary: "#C7C7C7",
  textMuted: "#8A8A8A",
  textDisabled: "#5F5F5F",
} as const;

const workbenchShellStyle = {
  "--lab-sidebar-width": "clamp(220px, 18vw, 260px)",
} as React.CSSProperties;

function createSupervisorConversation(id: string): Conversation {
  return {
    id,
    title: "新的 AI 主管对话",
    status: "pending",
  };
}

function resolveMainPageContext(pageKey: WorkbenchMainPageKey) {
  switch (pageKey) {
    case "projects":
      return {
        title: "项目管理",
        subtitle: "当前项目页面",
        status: "page",
      };
    case "execution":
      return {
        title: "执行中心",
        subtitle: "当前项目执行流",
        status: "page",
      };
    case "deliverables":
      return {
        title: "成果中心",
        subtitle: "工作台页面",
        status: "page",
      };
    case "repository":
      return {
        title: "仓库",
        subtitle: "当前项目工作区",
        status: "page",
      };
    case "governance":
      return {
        title: "治理",
        subtitle: "Skill 治理 · 当前项目：营销活动分析平台",
        status: "page",
      };
  }
}

// ── Lab Logo ───────────────────────────────────────────────

function LabLogo() {
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-9 w-9 rounded-lg border border-[#3A3A3A] bg-black">
        <span className="absolute left-2 top-2 h-2 w-2 rounded-full bg-white" />
        <span className="absolute left-[15px] top-2 h-2 w-2 rounded-full bg-[#C7C7C7]" />
        <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-[#8A8A8A]" />
        <span className="absolute bottom-2 left-[7px] h-1.5 w-1.5 rounded-full bg-[#8A8A8A]" />
        <span className="absolute bottom-2 left-[14px] h-1.5 w-1.5 rounded-full bg-[#8A8A8A]" />
        <span className="absolute bottom-2 left-[21px] h-1.5 w-1.5 rounded-full bg-[#8A8A8A]" />
        <span className="absolute bottom-2 right-[7px] h-1.5 w-1.5 rounded-full bg-[#8A8A8A]" />
      </div>
      <div className="text-xl font-semibold tracking-normal text-white">三省六部</div>
    </div>
  );
}

// ── Toast ──────────────────────────────────────────────────

type ToastStatus = "queued" | "processing" | "done" | "failed";

const toastStatusLabel: Record<ToastStatus, string> = {
  queued: "已排队",
  processing: "处理中",
  done: "已完成",
  failed: "失败",
};

function Toast({ message, status, onClose }: { message: string; status: ToastStatus; onClose: () => void }) {
  return (
    <div className="fixed bottom-20 left-1/2 z-[100] -translate-x-1/2 animate-[uiLabToastLifecycle_3000ms_ease-in-out_forwards]">
      <div className="flex items-center gap-3 rounded-full border border-[#3A3A3A] bg-[#202020] px-4 py-2.5 shadow-2xl shadow-black/60">
        <Check className="h-4 w-4 text-white" />
        <span className="text-xs text-[#8A8A8A]">{toastStatusLabel[status]}</span>
        <span className="text-sm text-white">{message}</span>
        <button className="ml-1 rounded-full p-0.5 text-[#8A8A8A] transition-colors hover:text-white" onClick={onClose}>
          <XCircle className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

// ── Create Project Dialog ───────────────────────────────────

function CreateProjectDialog({
  open,
  onOpenChange,
  onCreate,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onCreate: (name: string, note: string) => void;
}) {
  const [name, setName] = useState("");
  const [note, setNote] = useState("");

  function handleCreate() {
    const trimmed = name.trim();
    if (!trimmed) return;
    onCreate(trimmed, note.trim());
    setName("");
    setNote("");
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="ui-lab-dialog-enter w-[min(92vw,440px)]">
        <DialogHeader>
          <DialogTitle>创建项目</DialogTitle>
          <DialogDescription>
            先创建一个项目文件夹。目标、范围和计划将在项目对话中由 AI 主管逐步澄清。
          </DialogDescription>
        </DialogHeader>

        <div className="mt-5 space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-[#C7C7C7]">项目名称</label>
            <input
              className="flex h-10 w-full rounded-full border border-[#2A2A2A] bg-[#171717] px-4 text-sm text-white outline-none transition-colors placeholder:text-[#8A8A8A] focus:border-[#3A3A3A] focus:ring-2 focus:ring-white/10"
              placeholder="例如：二手交易平台 MVP"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCreate();
              }}
              autoFocus
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-[#C7C7C7]">
              项目备注<span className="text-[#5F5F5F]">（可选）</span>
            </label>
            <input
              className="flex h-10 w-full rounded-full border border-[#2A2A2A] bg-[#171717] px-4 text-sm text-white outline-none transition-colors placeholder:text-[#8A8A8A] focus:border-[#3A3A3A] focus:ring-2 focus:ring-white/10"
              placeholder="简短备注..."
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
        </div>

        <div className="mt-5 flex justify-end gap-3">
          <DialogClose asChild>
            <Button variant="secondary">取消</Button>
          </DialogClose>
          <Button onClick={handleCreate} disabled={!name.trim()}>
            创建
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export type WorkbenchExperienceMode = "lab" | "real";
export type WorkbenchMainPageKey =
  | "projects"
  | "execution"
  | "deliverables"
  | "repository"
  | "governance";
export type WorkbenchInitialModal = "settings" | "account";

export type WorkbenchDirectorSurfaceContext = {
  workbenchMode: "new-project" | "project";
  activeConversationId: string | null;
  activeProjectId: string | null;
  activeProjectName: string | null;
  topContext: {
    title: string;
    subtitle: string;
    status: string;
  };
};

export interface WorkbenchExperienceProps {
  mode?: WorkbenchExperienceMode;
  projectGroups?: ProjectGroup[];
  initialMainPage?: WorkbenchMainPageKey | null;
  initialProjectId?: string | null;
  initialSelectionMode?: "new-project" | "project";
  initialModal?: WorkbenchInitialModal | null;
  pageAdapterMode?: WorkbenchPageAdapterMode;
  surfaceData?: WorkbenchPageSurfaceData;
  settingsAdapter?: WorkbenchSettingsAdapter;
  accountAdapter?: WorkbenchAccountAdapter;
  topActionSlot?: React.ReactNode;
  repositoryBindingPanel?: React.ReactNode;
  suppressPromptBox?: boolean;
  renderTopActionSlot?: (context: WorkbenchDirectorSurfaceContext) => React.ReactNode;
  renderRepositoryBindingPanel?: (context: WorkbenchDirectorSurfaceContext) => React.ReactNode;
  renderDirectorSurface?: (context: WorkbenchDirectorSurfaceContext) => React.ReactNode;
  onNewProjectSession?: () => void;
}

// ── Workbench Experience (Interactive) ─────────────────────

export function WorkbenchPreview({
  mode = "lab",
  projectGroups,
  initialMainPage = null,
  initialProjectId = null,
  initialSelectionMode = "new-project",
  initialModal = null,
  pageAdapterMode,
  surfaceData,
  settingsAdapter,
  accountAdapter,
  topActionSlot,
  repositoryBindingPanel,
  suppressPromptBox = false,
  renderTopActionSlot,
  renderRepositoryBindingPanel,
  renderDirectorSurface,
  onNewProjectSession,
}: WorkbenchExperienceProps = {}) {
  // -- state --
  const [activeMainPage, setActiveMainPage] = useState<WorkbenchMainPageKey | null>(
    initialMainPage,
  );
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(
    initialSelectionMode === "project" ? initialProjectId : null,
  );
  const [workbenchMode, setWorkbenchMode] = useState(initialSelectionMode);
  const [searchQuery, setSearchQuery] = useState("");
  const [collapsedProjects, setCollapsedProjects] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState<{ message: string; status: ToastStatus } | null>(null);
  const [conversationMessages, setConversationMessages] = useState<Record<string, MockMessage[]>>(
    mockConversationMessages,
  );
  const [welcomeMessages, setWelcomeMessages] = useState<MockMessage[]>(getDefaultMessages());
  const [topContext, setTopContext] = useState({
    ...(initialMainPage
      ? resolveMainPageContext(initialMainPage)
      : {
          title: "新会话",
          subtitle: "未绑定项目 · 准备构建",
          status: "ready",
        }),
  });
  const [moreToolsExpanded, setMoreToolsExpanded] = useState(false);
  const [projectGroupsState, setProjectGroupsState] = useState<ProjectGroup[]>(
    projectGroups ?? initialProjectGroups,
  );
  const [createProjectOpen, setCreateProjectOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(initialModal === "settings");
  const [accountSettingsOpen, setAccountSettingsOpen] = useState(initialModal === "account");
  const [nextConvId, setNextConvId] = useState(10);
  const [planFlowState, setPlanFlowState] = useState(createInitialPlanFlowState);

  useEffect(() => {
    if (!projectGroups) return;
    setProjectGroupsState(projectGroups);
  }, [projectGroups]);

  useEffect(() => {
    setActiveMainPage(initialMainPage);
    setActiveConversationId(null);
    setMoreToolsExpanded(false);
    setTopContext(
      initialMainPage
        ? resolveMainPageContext(initialMainPage)
        : {
            title: "新会话",
            subtitle: "未绑定项目 · 准备构建",
            status: "ready",
          },
    );
  }, [initialMainPage]);

  useEffect(() => {
    setWorkbenchMode(initialSelectionMode);
    setActiveProjectId(initialSelectionMode === "project" ? initialProjectId : null);
    setActiveConversationId(null);
  }, [initialProjectId, initialSelectionMode]);

  useEffect(() => {
    if (initialModal === "settings") {
      setSettingsOpen(true);
    } else if (initialModal === "account") {
      setAccountSettingsOpen(true);
    }
  }, [initialModal]);

  // -- derived --
  const filteredGroups = useMemo(() => {
    if (!searchQuery.trim()) return projectGroupsState;
    const q = searchQuery.toLowerCase();
    return projectGroupsState
      .map((g) => ({
        ...g,
        conversations: g.conversations.filter((c) => c.title.toLowerCase().includes(q)),
      }))
      .filter((g) => g.name.toLowerCase().includes(q) || g.conversations.length > 0);
  }, [searchQuery, projectGroupsState]);

  const activeConversation = useMemo(() => {
    if (!activeConversationId) return null;
    for (const g of projectGroupsState) {
      const found = g.conversations.find((c) => c.id === activeConversationId);
      if (found) return { conversation: found, project: g };
    }
    return null;
  }, [activeConversationId, projectGroupsState]);
  const activeProject = useMemo(
    () => projectGroupsState.find((group) => group.id === activeProjectId) ?? null,
    [activeProjectId, projectGroupsState],
  );

  const messages = useMemo(() => {
    if (activeConversationId) {
      return conversationMessages[activeConversationId] ?? [];
    }
    return welcomeMessages;
  }, [activeConversationId, conversationMessages, welcomeMessages]);

  const hasWorkbenchDiscussionMessages = useMemo(
    () => welcomeMessages.some((message) => message.content.includes("@「")),
    [welcomeMessages],
  );
  const directorContext: WorkbenchDirectorSurfaceContext = {
    workbenchMode,
    activeConversationId,
    activeProjectId,
    activeProjectName: activeProject?.name ?? null,
    topContext,
  };

  // -- actions --
  const showToast = useCallback((message: string, status: ToastStatus = "done") => {
    setToast({ message, status });
    setTimeout(() => setToast(null), 3000);
  }, []);

  const handleQueueDiscussionAction = useCallback(
    (mode: "add" | "add-and-open", title: string) => {
      const discussionMessage: MockMessage = {
        role: "assistant",
        content: `@「${title}」\n\n已加入工作台讨论。这里会继续澄清人工确认项，并生成下一步处理建议。`,
        time: "刚刚",
      };

      setWelcomeMessages((prev) => {
        const alreadyExists = prev.some((message) => message.content.includes(`@「${title}」`));
        if (alreadyExists) return prev;
        return [...prev, discussionMessage];
      });

      if (mode === "add") {
        return;
      }

      setActiveMainPage(null);
      setWorkbenchMode("new-project");
      setActiveProjectId(null);
      setActiveConversationId(null);
      setTopContext({
        title: "工作台讨论",
        subtitle: title,
        status: "pending",
      });
    },
    [],
  );

  const handleNewProjectSession = useCallback(() => {
    if (onNewProjectSession) {
      setActiveMainPage(null);
      setWorkbenchMode("new-project");
      setActiveProjectId(null);
      setActiveConversationId(null);
      setTopContext({
        title: "新项目会话",
        subtitle: "未绑定项目 · 准备构建",
        status: "ready",
      });
      onNewProjectSession();
      return;
    }
    setCreateProjectOpen(true);
  }, [onNewProjectSession]);

  const handleAddConversationToProject = useCallback(
    (projectGroup: ProjectGroup, event?: React.MouseEvent<HTMLButtonElement>) => {
      event?.stopPropagation();
      const newConv = createSupervisorConversation(`conv-${nextConvId}`);

      setNextConvId((n) => n + 1);
      setProjectGroupsState((prev) =>
        prev.map((g) =>
          g.id === projectGroup.id
            ? { ...g, conversations: [...g.conversations, newConv] }
            : g,
        ),
      );
      setConversationMessages((prev) => ({ ...prev, [newConv.id]: getNewConversationWelcome() }));
      setActiveMainPage(null);
      setWorkbenchMode("project");
      setActiveProjectId(projectGroup.id);
      setActiveConversationId(newConv.id);
      setTopContext({
        title: "新的 AI 主管对话",
        subtitle: `${projectGroup.name} · 目标澄清 · pending`,
        status: "pending",
      });
      setMoreToolsExpanded(false);
      setCollapsedProjects((prev) => {
        const next = new Set(prev);
        next.delete(projectGroup.id);
        return next;
      });
      showToast("已创建新对话");
    },
    [nextConvId, showToast],
  );

  const handleCreateProject = useCallback(
    (name: string, _note: string) => {
      const projectId = `proj-${nextConvId}`;
      const convId = `conv-${nextConvId + 1}`;
      setNextConvId((n) => n + 2);

      const newConv = createSupervisorConversation(convId);

      const newGroup: ProjectGroup = {
        id: projectId,
        name: name,
        conversations: [newConv],
      };

      setProjectGroupsState((prev) => [...prev, newGroup]);
      setConversationMessages((prev) => ({ ...prev, [convId]: getNewConversationWelcome() }));
      setActiveMainPage(null);
      setWorkbenchMode("project");
      setActiveProjectId(projectId);
      setActiveConversationId(convId);
      setTopContext({
        title: "新的 AI 主管对话",
        subtitle: `${name} · 目标澄清 · pending`,
        status: "pending",
      });
      setCollapsedProjects((prev) => {
        const next = new Set(prev);
        // Collapse all others, expand the new one
        projectGroupsState.forEach((g) => next.add(g.id));
        next.delete(projectId);
        return next;
      });
      setMoreToolsExpanded(false);
      showToast(`已创建项目「${name}」`);
    },
    [nextConvId, projectGroupsState, showToast],
  );

  const handlePlanFeedbackChange = useCallback((feedback: string) => {
    setPlanFlowState((prev) => applyPlanFlowAction(prev, { type: "update_feedback", feedback }));
  }, []);

  const handleRequestPlanChanges = useCallback(
    (feedback: string) => {
      setPlanFlowState((prev) => applyPlanFlowAction(prev, { type: "request_changes", feedback }));
      showToast("已记录修改意见 mock");
    },
    [showToast],
  );

  const handleRejectPlan = useCallback(() => {
    setPlanFlowState((prev) => applyPlanFlowAction(prev, { type: "reject_plan" }));
    showToast("已驳回计划草案 mock");
  }, [showToast]);

  const handleConfirmPlan = useCallback(() => {
    setPlanFlowState((prev) => applyPlanFlowAction(prev, { type: "confirm_plan" }));
    showToast("已确认计划草案 mock");
  }, [showToast]);

  const handleCreateFormalProject = useCallback(() => {
    const projectName = planFlowState.projectName;
    const convId = `conv-${nextConvId}`;
    const projectId = `proj-formal-${nextConvId}`;
    const formalConversation: Conversation = {
      id: convId,
      title: "正式项目启动",
      status: "pending",
    };

    setNextConvId((n) => n + 1);
    setPlanFlowState((prev) => applyPlanFlowAction(prev, { type: "create_project", projectName }));
    setProjectGroupsState((prev) => {
      const existing = prev.find((group) => group.name === projectName);
      if (existing) {
        return prev.map((group) =>
          group.id === existing.id
            ? { ...group, conversations: [...group.conversations, formalConversation] }
            : group,
        );
      }
      return [
        ...prev,
        {
          id: projectId,
          name: projectName,
          conversations: [formalConversation],
        },
      ];
    });
      setConversationMessages((prev) => ({
        ...prev,
        [convId]: [
          {
            role: "assistant",
            content: `已创建正式项目「${projectName}」。\n\n下一步可以补充仓库、团队与执行边界。`,
            time: "刚刚",
          },
        ],
      }));
    const existingProject = projectGroupsState.find((group) => group.name === projectName);
    setActiveMainPage(null);
    setWorkbenchMode("project");
    setActiveProjectId(existingProject?.id ?? projectId);
    setActiveConversationId(convId);
      setTopContext({
        title: "正式项目启动",
        subtitle: `${projectName} · 已创建`,
        status: "pending",
      });
    setCollapsedProjects((prev) => {
      const next = new Set(prev);
      projectGroupsState.forEach((group) => {
        if (group.name !== projectName) next.add(group.id);
      });
      next.delete(projectId);
      if (existingProject) next.delete(existingProject.id);
      return next;
    });
      showToast("已创建正式项目");
  }, [nextConvId, planFlowState.projectName, projectGroupsState, showToast]);

  const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
  }, []);

  const toggleProject = useCallback((projectGroup: ProjectGroup) => {
    const isUnboundSessionGroup = projectGroup.id === "new-project";
    setActiveMainPage(null);
    setWorkbenchMode(isUnboundSessionGroup ? "new-project" : "project");
    setActiveProjectId(isUnboundSessionGroup ? null : projectGroup.id);
    setActiveConversationId(null);
    setTopContext({
      title: projectGroup.name,
      subtitle: isUnboundSessionGroup
        ? "未绑定项目 · 准备开始新讨论"
        : "项目上下文 · 准备开始新讨论",
      status: "ready",
    });
    setCollapsedProjects((prev) => {
      const next = new Set(prev);
      if (next.has(projectGroup.id)) {
        next.delete(projectGroup.id);
      } else {
        next.add(projectGroup.id);
      }
      return next;
    });
  }, []);

  const handleSelectConversation = useCallback(
    (conv: Conversation, projectGroup: ProjectGroup) => {
      const isUnboundSession = projectGroup.id === "new-project";
      setActiveMainPage(null);
      setWorkbenchMode(isUnboundSession ? "new-project" : "project");
      setActiveProjectId(isUnboundSession ? null : projectGroup.id);
      setActiveConversationId(conv.id);
      setTopContext({
        title: conv.title,
        subtitle: `${isUnboundSession ? "未绑定项目" : projectGroup.name} · 对话中 · ${conv.status}`,
        status: conv.status,
      });
    },
    [],
  );

  const handlePageNav = useCallback((label: string) => {
    const pageKeyMap: Record<string, WorkbenchMainPageKey> = {
      "项目管理": "projects",
      "执行中心": "execution",
      "成果中心": "deliverables",
      "仓库": "repository",
      "治理": "governance",
    };
    const key = pageKeyMap[label] ?? "projects";
    setActiveMainPage(key);
    setActiveConversationId(null);
    setTopContext(resolveMainPageContext(key));
  }, []);

  const handlePromptSend = useCallback(
    (text: string) => {
      const timeStr = new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
      const newMsg: MockMessage = {
        role: "user",
        content: text,
        time: timeStr,
      };
      // Check if this is a fresh conversation (0 or 1 messages)
      const existingMsgs = activeConversationId
        ? (conversationMessages[activeConversationId] ?? [])
        : welcomeMessages;
      const isFreshConversation = existingMsgs.length <= 1;

      const reply: MockMessage = isFreshConversation
        ? {
            role: "assistant",
            content:
              `好的，我先帮你把目标澄清清楚。为了避免过早拆任务，我需要先确认几个问题：\n\n1. 目标用户是谁？\n2. 第一版 MVP 只做哪些能力？\n3. 是否已有代码仓库？\n\n你可以直接回复，我会逐步整理出项目草案。`,
            time: timeStr,
          }
        : {
            role: "assistant",
            content: `收到：「${text}」\n\n我已记录这条输入，会继续整理目标和下一步建议。`,
            time: timeStr,
          };

      if (activeConversationId) {
        setConversationMessages((prev) => ({
          ...prev,
          [activeConversationId]: [...(prev[activeConversationId] ?? []), newMsg, reply],
        }));
      } else {
        setWelcomeMessages((prev) => [...prev, newMsg, reply]);
      }

      showToast("已添加到会话");
    },
    [activeConversationId, conversationMessages, welcomeMessages, showToast],
  );

  const activePlanFlowCard = activeConversationId ? (
    <div className="grid gap-5">
      {planFlowState.stage === "draft" ? <WorkbenchClarificationPanel /> : null}
      <WorkbenchPlanFlowCard
        state={planFlowState}
        defaultCollapsed
        onFeedbackChange={handlePlanFeedbackChange}
        onRequestChanges={handleRequestPlanChanges}
        onReject={handleRejectPlan}
        onConfirm={handleConfirmPlan}
        onCreateProject={handleCreateFormalProject}
      />
      {planFlowState.stage === "created" ? <WorkbenchProjectNextStepPanel /> : null}
    </div>
  ) : null;

  // -- render main content --
  function renderMainContent() {
    // If a main page is selected, show mock page
    if (activeMainPage && !activeConversationId) {
      return (
        <MockPageContent
          pageKey={activeMainPage}
          onQueueDiscussionAction={handleQueueDiscussionAction}
          onTaskFeedback={showToast}
          adapterMode={pageAdapterMode ?? (mode === "real" ? "hybrid" : "mock")}
          surfaceData={surfaceData}
          repositoryBindingPanel={
            renderRepositoryBindingPanel?.(directorContext) ?? repositoryBindingPanel
          }
        />
      );
    }

    if (renderDirectorSurface) {
      return renderDirectorSurface(directorContext);
    }

    // If a conversation is selected, show conversation (no duplicate header)
    if (activeConversation && activeConversationId) {
      return <ConversationMessages messages={messages} planFlowCard={activePlanFlowCard} />;
    }

    // Show queued workbench discussion content
    if (hasWorkbenchDiscussionMessages) {
      return <ConversationMessages messages={welcomeMessages} />;
    }

    // Welcome state — single CTA: 创建项目
    return (
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-5 pb-24 pt-6 text-center md:px-8 md:pb-28 lg:px-10">
        <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-2xl border border-[#2A2A2A] bg-black md:mb-5 md:h-14 md:w-14">
          <Bot className="h-6 w-6 text-[#C7C7C7] md:h-7 md:w-7" />
        </div>
        <h1 className="text-3xl font-semibold tracking-normal text-white md:text-[42px]">欢迎</h1>
        <h2 className="mt-3 text-xl font-semibold tracking-normal text-[#C7C7C7] md:mt-4 md:text-2xl">
          我们来构建什么？
        </h2>
        <p className="mt-3 max-w-xl text-sm leading-6 text-[#8A8A8A] md:mt-4">
          创建一个项目，AI 主管会逐步帮你澄清目标、生成计划并推进执行
        </p>

        <button
          className="mt-8 flex h-11 items-center gap-2 rounded-[14px] bg-white px-5 text-sm font-semibold text-black transition-all duration-150 hover:bg-[#EDEDED] active:scale-[0.99]"
          onClick={() => setCreateProjectOpen(true)}
        >
          <FolderKanban className="h-4 w-4" />
          创建项目
        </button>
      </div>
    );
  }

  return (
    <section
      data-testid={mode === "real" ? "workbench-main-shell" : "ui-lab-workbench-preview"}
      aria-label="三省六部 Workbench Preview"
      className="h-[100dvh] min-h-[720px] w-full overflow-hidden text-white"
      style={{ ...workbenchShellStyle, backgroundColor: minimalDarkTokens.appBg }}
    >
      <div className="flex h-full w-full overflow-hidden">
        {/* ── Sidebar ── */}
        <aside
          data-testid="ui-lab-sidebar"
          className="flex h-full shrink-0 flex-col border-r border-[#2A2A2A] bg-[#080808] px-3 py-4 md:px-4 md:py-5"
          style={{ width: "var(--lab-sidebar-width)" }}
        >
          <LabLogo />

          {/* 新建项目会话 — primary CTA anchor */}
          <button
            className="mt-5 flex h-11 w-full items-center justify-start gap-2 rounded-[14px] bg-white px-3 text-sm font-semibold text-black transition-all duration-150 hover:bg-[#EDEDED] active:scale-[0.99] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/25"
            onClick={handleNewProjectSession}
          >
            <MessageSquarePlus className="h-4 w-4" />
            新建项目会话
          </button>

          {/* Search */}
          <div className="relative mt-3">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8A8A8A]" />
            <Input
              className="h-10 pl-9"
              placeholder="搜索项目、会话、任务..."
              value={searchQuery}
              onChange={handleSearchChange}
            />
          </div>

          <div className="ui-lab-sidebar-scroll mt-4 min-h-0 flex-1 overflow-y-auto overscroll-contain pr-1 md:mt-6">
            <div className="space-y-4 md:space-y-6">
              <div className="space-y-1">
                {!moreToolsExpanded ? (
                  <SidebarNavItem
                    label="高级详情"
                    icon={CircleEllipsis}
                    muted
                    active={false}
                    className="h-8 text-xs"
                    onClick={() => setMoreToolsExpanded(true)}
                  />
                ) : (
                  <>
                    <SidebarNavItem
                      label="高级详情"
                      icon={CircleEllipsis}
                      muted
                      active={false}
                      className="h-8 text-xs"
                    />
                    <DashboardModal>
                      <SidebarNavItem label="数据看板" icon={LayoutDashboard} active={false} className="h-8 text-xs" />
                    </DashboardModal>
                    <ApprovalsModal>
                      <SidebarNavItem label="待审批" icon={ClipboardCheck} badge="2" active={false} className="h-8 text-xs" />
                    </ApprovalsModal>
                    <ExecutionStatusModal>
                      <SidebarNavItem label="执行状态" icon={Activity} active={false} className="h-8 text-xs" />
                    </ExecutionStatusModal>
                    <CostUsageModal>
                      <SidebarNavItem label="成本用量" icon={Wallet} className="h-8 text-xs" />
                    </CostUsageModal>
                    <RepositoryQueueModal>
                      <SidebarNavItem label="仓库队列" icon={Archive} className="h-8 text-xs" />
                    </RepositoryQueueModal>
                    <GitWritePreviewModal>
                      <SidebarNavItem label="Git 写入预览" icon={GitBranch} className="h-8 text-xs" />
                    </GitWritePreviewModal>
                    <SidebarNavItem
                      label="收起"
                      icon={ChevronUp}
                      muted
                      className="h-8 text-xs"
                      onClick={() => setMoreToolsExpanded(false)}
                    />
                  </>
                )}
              </div>

              <Separator />

              {/* 主页面 — switch main content */}
              <div>
                <div className="mb-2 px-1 text-xs font-semibold uppercase tracking-[0.12em] text-[#5F5F5F]">
                  主页面
                </div>
                <div className="space-y-1">
                  {pageNavItems.map((item) => (
                    <SidebarNavItem
                      key={item.label}
                      label={item.label}
                      icon={item.icon}
                      active={activeMainPage === item.label || activeMainPage ===
                        { "项目管理": "projects", "执行中心": "execution", "成果中心": "deliverables", "仓库": "repository", "治理": "governance" }[item.label]
                      }
                      onClick={() => handlePageNav(item.label)}
                    />
                  ))}
                </div>
              </div>

              <Separator />

              {/* 项目会话 — collapsible, selectable */}
              <div>
                <div className="mb-3 px-1 text-xs font-semibold uppercase tracking-[0.12em] text-[#5F5F5F]">
                  项目会话
                </div>
                <div className="space-y-4">
                  {filteredGroups.length === 0 ? (
                    <p className="px-2 text-sm text-[#8A8A8A]">没有匹配的会话</p>
                  ) : (
                    filteredGroups.map((group) => {
                      const isCollapsed = collapsedProjects.has(group.id);
                      return (
                        <div key={group.id}>
                          <div className="group flex w-full items-center gap-1">
                            <button
                              className="flex min-w-0 flex-1 items-center gap-2 px-2 text-left text-sm font-semibold text-white transition-colors hover:text-white"
                              onClick={() => toggleProject(group)}
                            >
                              <span
                                className="shrink-0 transition-transform duration-200"
                                style={{ display: "inline-flex" }}
                              >
                                {isCollapsed ? (
                                  <ChevronRight className="h-4 w-4 text-[#8A8A8A]" />
                                ) : (
                                  <ChevronDown className="h-4 w-4 text-[#8A8A8A]" />
                                )}
                              </span>
                              <span className="min-w-0 flex-1 truncate">{group.name}</span>
                            </button>
                            <button
                              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[#8A8A8A] opacity-0 transition-all duration-150 hover:bg-[#222222] hover:text-white active:scale-[0.96] group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20"
                              onClick={(event) => handleAddConversationToProject(group, event)}
                            >
                              <MessageSquarePlus className="h-[15px] w-[15px]" />
                            </button>
                          </div>
                          {!isCollapsed && (
                            <div className="mt-2 space-y-1 pl-7">
                              {group.conversations.map((conv) => (
                                <button
                                  key={conv.id}
                                  className={cn(
                                    "block w-full truncate rounded-md px-2 py-1.5 text-left text-sm transition-colors",
                                    activeConversationId === conv.id
                                      ? "bg-[#2C2C2C] text-white"
                                      : "text-[#C7C7C7] hover:bg-[#222222] hover:text-white",
                                  )}
                                  onClick={() => handleSelectConversation(conv, group)}
                                >
                                  <div className="truncate">{conv.title}</div>
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* User menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="mt-4 flex h-11 w-full items-center gap-3 rounded-2xl px-3 text-left transition-all duration-150 hover:bg-[#222222] active:scale-[0.98]">
                <Avatar className="h-7 w-7 rounded-full">
                  <AvatarFallback>K</AvatarFallback>
                </Avatar>
                <span className="min-w-0 flex-1 text-sm text-[#C7C7C7]">kk / 设置</span>
                <MoreHorizontal className="h-4 w-4 text-[#8A8A8A]" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onSelect={() => setAccountSettingsOpen(true)}>
                <User className="mr-2 h-4 w-4 text-[#C7C7C7]" />
                账户信息
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => setSettingsOpen(true)}>
                <Settings className="mr-2 h-4 w-4 text-[#C7C7C7]" />
                工作台设置
              </DropdownMenuItem>
              <DropdownMenuSeparator className="my-1 h-px bg-[#2C2C2C]" />
              <DropdownMenuItem className="text-[#C7C7C7]">退出菜单</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </aside>

        {/* ── Main ── */}
        <main className="relative flex min-w-0 flex-1 flex-col overflow-hidden bg-[#000000]">
          {/* Top context bar */}
          <div className="relative z-30 flex h-[68px] shrink-0 items-center justify-between border-b border-[#2A2A2A] px-5 md:px-8">
            <div className="min-w-0 flex-1 mr-4">
              <div className="truncate text-[15px] font-semibold text-white">{topContext.title}</div>
              <div className="mt-0.5 truncate text-[13px] text-[#8A8A8A]">{topContext.subtitle}</div>
            </div>
            <div className="mr-3 hidden shrink-0 md:block">
              {renderTopActionSlot?.(directorContext) ?? topActionSlot ?? <WorkbenchUserActionStrip />}
            </div>
            <Badge className="h-7 shrink-0 gap-1.5 rounded-full border-[#2A2A2A] bg-transparent px-2.5 text-[11px] text-[#C7C7C7]">
              <span className="h-1.5 w-1.5 rounded-full bg-[#C7C7C7]" />
              {activeMainPage === "execution" ? "进行中" : activeMainPage === "governance" || activeMainPage === "repository" ? "只读" : "准备中"}
            </Badge>
          </div>

          {renderMainContent()}

          {!suppressPromptBox && activeMainPage !== "projects" && activeMainPage !== "execution" && activeMainPage !== "deliverables" && activeMainPage !== "repository" && activeMainPage !== "governance" ? (
            <WorkbenchPromptBox onSend={handlePromptSend} />
          ) : null}
        </main>
      </div>

      {/* Create Project Dialog */}
      <CreateProjectDialog
        open={createProjectOpen}
        onOpenChange={setCreateProjectOpen}
        onCreate={handleCreateProject}
      />
      <AccountSettingsModal
        open={accountSettingsOpen}
        onOpenChange={setAccountSettingsOpen}
        adapter={accountAdapter}
      />
      <WorkbenchSettingsModal
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        adapter={settingsAdapter}
      />

      {/* Toast */}
      {toast && <Toast message={toast.message} status={toast.status} onClose={() => setToast(null)} />}
      <style>{`
        .ui-lab-sidebar-scroll {
          scrollbar-width: none;
          -ms-overflow-style: none;
        }

        .ui-lab-sidebar-scroll::-webkit-scrollbar {
          display: none;
          width: 0;
          height: 0;
        }

        .ui-lab-page-enter {
          animation: uiLabPageEnter 180ms cubic-bezier(0.2, 0, 0, 1) both;
        }

        .ui-lab-panel-enter {
          animation: uiLabPanelEnter 180ms cubic-bezier(0.2, 0, 0, 1) both;
        }

        .ui-lab-popover-enter {
          transform-origin: top right;
          will-change: opacity, transform;
        }

        .ui-lab-dialog-enter {
          animation: uiLabDialogEnter 180ms cubic-bezier(0.2, 0, 0, 1) both;
        }

        .ui-lab-detail-switch {
          animation: uiLabDetailSwitch 150ms cubic-bezier(0.2, 0, 0, 1) both;
        }

        @keyframes uiLabPageEnter {
          from {
            opacity: 0;
            translate: 0 8px;
          }
          to {
            opacity: 1;
            translate: 0 0;
          }
        }

        @keyframes uiLabPanelEnter {
          from {
            opacity: 0;
            translate: 0 6px;
          }
          to {
            opacity: 1;
            translate: 0 0;
          }
        }

        @keyframes uiLabDialogEnter {
          from {
            opacity: 0;
            translate: 0 4px;
            scale: 0.985;
          }
          to {
            opacity: 1;
            translate: 0 0;
            scale: 1;
          }
        }

        @keyframes uiLabDetailSwitch {
          from {
            opacity: 0;
            translate: 0 4px;
          }
          to {
            opacity: 1;
            translate: 0 0;
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .ui-lab-page-enter,
          .ui-lab-panel-enter,
          .ui-lab-popover-enter,
          .ui-lab-dialog-enter,
          .ui-lab-detail-switch,
          [class*="uiLabToastLifecycle"],
          [class*="animate-pulse"] {
            animation-duration: 1ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 1ms !important;
            translate: none !important;
            scale: none !important;
          }
        }
      `}</style>
    </section>
  );
}

// ── Page Export ────────────────────────────────────────────

export function SanshengLiubuUiLabPage() {
  return (
    <div className="min-h-screen bg-[#050505]">
      <WorkbenchPreview />
      <ComponentPlayground />
      <div className="border-t border-[#2A2A2A] bg-[#050505] px-8 py-6 text-center text-xs text-[#5F5F5F]">
        <XCircle className="mr-2 inline h-3.5 w-3.5" />
        隐藏实验页：同一套工作台组件的 mock / preview 入口。
      </div>
    </div>
  );
}
