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
  Gauge,
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
import { useCallback, useMemo, useState } from "react";
import type * as React from "react";

import { cn } from "../../lib/cn";
import { ChartPreview } from "./components/ChartPreview";
import { DataListPreview } from "./components/DataListPreview";
import { FeedbackPreview } from "./components/FeedbackPreview";
import { ResponsiveNotes } from "./components/ResponsiveNotes";
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
  DialogTrigger,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Input,
  Separator,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Textarea,
} from "./components/ui";
import { ConversationMessages } from "./components/WorkbenchMockConversation";
import { MockPageContent } from "./components/WorkbenchMockPages";
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
  getDefaultMessages,
  getNewConversationWelcome,
  mockConversationMessages,
  pageNavItems,
  projectGroups as initialProjectGroups,
  type Conversation,
  type MockMessage,
  type ProjectGroup,
} from "./mockInteractions";

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
  "--lab-sidebar-width": "clamp(248px, 20.5vw, 300px)",
} as React.CSSProperties;

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

// ── Sidebar Nav Item ───────────────────────────────────────

type SidebarNavItemProps = {
  label: string;
  icon?: React.ComponentType<{ className?: string }>;
  active?: boolean;
  hover?: boolean;
  muted?: boolean;
  badge?: string;
  className?: string;
  onClick?: () => void;
};

function SidebarNavItem({ label, icon: Icon, active, hover, muted, badge, className, onClick }: SidebarNavItemProps) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onClick?.();
      }}
      className={cn(
        "flex h-9 cursor-pointer items-center gap-3 rounded-md px-3 text-sm transition-all duration-150 active:scale-[0.99]",
        active && "bg-[#2C2C2C] text-white",
        hover && "bg-[#222222] text-white",
        !active && !hover && (muted ? "text-[#5F5F5F]" : "text-[#C7C7C7]"),
        "hover:bg-[#222222] hover:text-white",
        className,
      )}
    >
      {Icon ? <Icon className="h-4 w-4 shrink-0 text-[#8A8A8A]" /> : null}
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {badge ? <Badge className="h-5 border-[#3A3A3A] bg-[#2C2C2C] text-[11px] text-white">{badge}</Badge> : null}
    </div>
  );
}

// ── Toast ──────────────────────────────────────────────────

function Toast({ message, onClose }: { message: string; onClose: () => void }) {
  return (
    <div className="fixed bottom-20 left-1/2 z-[100] -translate-x-1/2 animate-[fadeIn_150ms_ease-out]">
      <div className="flex items-center gap-3 rounded-full border border-[#3A3A3A] bg-[#202020] px-4 py-2.5 shadow-2xl shadow-black/60">
        <Check className="h-4 w-4 text-white" />
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
      <DialogContent className="w-[min(92vw,440px)]">
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

// ── Workbench Preview (Interactive) ────────────────────────

function WorkbenchPreview() {
  // -- state --
  const [activeMainPage, setActiveMainPage] = useState<string | null>(null);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [collapsedProjects, setCollapsedProjects] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState<string | null>(null);
  const [conversationMessages, setConversationMessages] = useState<Record<string, MockMessage[]>>(
    mockConversationMessages,
  );
  const [welcomeMessages, setWelcomeMessages] = useState<MockMessage[]>(getDefaultMessages());
  const [topContext, setTopContext] = useState({
    title: "新会话",
    subtitle: "未绑定项目 · 准备构建",
    status: "ready" as string,
  });
  const [moreToolsExpanded, setMoreToolsExpanded] = useState(false);
  const [projectGroupsState, setProjectGroupsState] = useState<ProjectGroup[]>(initialProjectGroups);
  const [createProjectOpen, setCreateProjectOpen] = useState(false);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [nextConvId, setNextConvId] = useState(10);

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

  const messages = useMemo(() => {
    if (activeConversationId) {
      return conversationMessages[activeConversationId] ?? [];
    }
    return welcomeMessages;
  }, [activeConversationId, conversationMessages, welcomeMessages]);

  // -- actions --
  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2500);
  }, []);

  const handleNewSession = useCallback(() => {
    // If no active project, open create project dialog
    if (!activeProjectId) {
      setCreateProjectOpen(true);
      return;
    }
    // Otherwise add new conversation under current project
    const newConv: Conversation = {
      id: `conv-${nextConvId}`,
      title: "新的 AI 主管对话",
      status: "pending",
    };
    setNextConvId((n) => n + 1);
    setProjectGroupsState((prev) =>
      prev.map((g) =>
        g.id === activeProjectId
          ? { ...g, conversations: [...g.conversations, newConv] }
          : g,
      ),
    );
    setConversationMessages((prev) => ({ ...prev, [newConv.id]: getNewConversationWelcome() }));
    setActiveMainPage(null);
    setActiveConversationId(newConv.id);
    setTopContext({
      title: "新的 AI 主管对话",
      subtitle: `${projectGroupsState.find((g) => g.id === activeProjectId)?.name ?? "项目"} · 目标澄清 · pending`,
      status: "pending",
    });
    setMoreToolsExpanded(false);
    // Ensure project is expanded
    setCollapsedProjects((prev) => {
      const next = new Set(prev);
      next.delete(activeProjectId!);
      return next;
    });
    showToast("已创建新对话");
  }, [activeProjectId, nextConvId, projectGroupsState, showToast]);

  const handleCreateProject = useCallback(
    (name: string, _note: string) => {
      const projectId = `proj-${nextConvId}`;
      const convId = `conv-${nextConvId + 1}`;
      setNextConvId((n) => n + 2);

      const newConv: Conversation = {
        id: convId,
        title: "新的 AI 主管对话",
        status: "pending",
      };

      const newGroup: ProjectGroup = {
        id: projectId,
        name: name,
        conversations: [newConv],
      };

      setProjectGroupsState((prev) => [...prev, newGroup]);
      setConversationMessages((prev) => ({ ...prev, [convId]: getNewConversationWelcome() }));
      setActiveMainPage(null);
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

  const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
  }, []);

  const toggleProject = useCallback((projectId: string) => {
    setCollapsedProjects((prev) => {
      const next = new Set(prev);
      if (next.has(projectId)) {
        next.delete(projectId);
      } else {
        next.add(projectId);
      }
      return next;
    });
  }, []);

  const handleSelectConversation = useCallback(
    (conv: Conversation, projectGroup: ProjectGroup) => {
      setActiveMainPage(null);
      setActiveProjectId(projectGroup.id);
      setActiveConversationId(conv.id);
      setTopContext({
        title: conv.title,
        subtitle: `${projectGroup.name} · 对话中 · ${conv.status}`,
        status: conv.status,
      });
    },
    [],
  );

  const handlePageNav = useCallback((label: string) => {
    const pageKeyMap: Record<string, string> = {
      "项目管理": "projects",
      "执行中心": "execution",
      "成果中心": "deliverables",
      "治理": "governance",
    };
    const key = pageKeyMap[label] ?? label;
    setActiveMainPage(key);
    setActiveConversationId(null);
    setTopContext({
      title: label,
      subtitle: "工作台页面 · mock",
      status: "page",
    });
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
            content: `收到：「${text}」\n\n这是 mock 回复。当前为实验页，不连接真实 AI 执行器。你的输入已记录在本地会话状态中。`,
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

      showToast("已添加到实验会话 mock");
    },
    [activeConversationId, conversationMessages, welcomeMessages, showToast],
  );

  // -- render main content --
  function renderMainContent() {
    // If a main page is selected, show mock page
    if (activeMainPage && !activeConversationId) {
      return <MockPageContent pageKey={activeMainPage} />;
    }

    // If a conversation is selected, show conversation (no duplicate header)
    if (activeConversation && activeConversationId) {
      return <ConversationMessages messages={messages} />;
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
      data-testid="ui-lab-workbench-preview"
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

          {/* 新建会话 — primary CTA anchor */}
          <button
            className="mt-5 flex h-11 w-full items-center justify-start gap-2 rounded-[14px] bg-white px-3 text-sm font-semibold text-black transition-all duration-150 hover:bg-[#EDEDED] active:scale-[0.99] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/25"
            onClick={handleNewSession}
          >
            <MessageSquarePlus className="h-4 w-4" />
            新建会话
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
              {/* 运行与治理 — open modals */}
              <div>
                <div className="mb-2 px-1 text-xs font-semibold uppercase tracking-[0.12em] text-[#5F5F5F]">
                  运行与治理
                </div>
                <div className="space-y-1">
                  <DashboardModal>
                    <SidebarNavItem
                      label="数据看板"
                      icon={LayoutDashboard}
                      active={false}
                    />
                  </DashboardModal>
                  <ApprovalsModal>
                    <SidebarNavItem
                      label="待审批"
                      icon={ClipboardCheck}
                      badge="2"
                      active={false}
                    />
                  </ApprovalsModal>
                  <ExecutionStatusModal>
                    <SidebarNavItem label="执行状态" icon={Activity} active={false} />
                  </ExecutionStatusModal>

                  {/* ... 更多 / 收起 — inline sidebar disclosure */}
                  {!moreToolsExpanded ? (
                    <SidebarNavItem
                      label="... 更多"
                      icon={CircleEllipsis}
                      active={false}
                      onClick={() => setMoreToolsExpanded(true)}
                    />
                  ) : (
                    <>
                      <CostUsageModal>
                        <SidebarNavItem label="成本用量" icon={Wallet} />
                      </CostUsageModal>
                      <RepositoryQueueModal>
                        <SidebarNavItem label="仓库队列" icon={Archive} />
                      </RepositoryQueueModal>
                      <GitWritePreviewModal>
                        <SidebarNavItem label="Git 写入预览" icon={GitBranch} />
                      </GitWritePreviewModal>
                      <SidebarNavItem
                        label="收起"
                        icon={ChevronUp}
                        muted
                        onClick={() => setMoreToolsExpanded(false)}
                      />
                    </>
                  )}
                </div>
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
                        { "项目管理": "projects", "执行中心": "execution", "成果中心": "deliverables", "治理": "governance" }[item.label]
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
                          <button
                            className="flex w-full items-center gap-2 px-2 text-left text-sm font-semibold text-white transition-colors hover:text-white"
                            onClick={() => toggleProject(group.id)}
                          >
                            <span className="transition-transform duration-200" style={{ display: "inline-flex" }}>
                              {isCollapsed ? (
                                <ChevronRight className="h-4 w-4 text-[#8A8A8A]" />
                              ) : (
                                <ChevronDown className="h-4 w-4 text-[#8A8A8A]" />
                              )}
                            </span>
                            {group.name}
                          </button>
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
              <DropdownMenuItem>
                <User className="mr-2 h-4 w-4 text-[#C7C7C7]" />
                账户信息
              </DropdownMenuItem>
              <DropdownMenuItem>
                <Settings className="mr-2 h-4 w-4 text-[#C7C7C7]" />
                工作台设置
              </DropdownMenuItem>
              <DropdownMenuSeparator className="my-1 h-px bg-[#2C2C2C]" />
              <DropdownMenuItem className="text-[#C7C7C7]">退出 mock 菜单</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </aside>

        {/* ── Main ── */}
        <main className="relative flex min-w-0 flex-1 flex-col overflow-hidden bg-[#000000]">
          {/* Top context bar */}
          <div className="flex h-[68px] shrink-0 items-center justify-between border-b border-[#2A2A2A] px-5 md:px-8">
            <div className="min-w-0 flex-1 mr-4">
              <div className="truncate text-[15px] font-semibold text-white">{topContext.title}</div>
              <div className="mt-0.5 truncate text-[13px] text-[#8A8A8A]">{topContext.subtitle}</div>
            </div>
            <Badge className="h-7 shrink-0 gap-1.5 rounded-full border-[#2A2A2A] bg-transparent px-2.5 text-[11px] text-[#C7C7C7]">
              <span className="h-1.5 w-1.5 rounded-full bg-[#C7C7C7]" />
              准备接收任务
            </Badge>
          </div>

          {renderMainContent()}

          {/* PromptBox */}
          <WorkbenchPromptBox onSend={handlePromptSend} />
        </main>
      </div>

      {/* Create Project Dialog */}
      <CreateProjectDialog
        open={createProjectOpen}
        onOpenChange={setCreateProjectOpen}
        onCreate={handleCreateProject}
      />

      {/* Toast */}
      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
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
      `}</style>
    </section>
  );
}

// ── Component Playground (updated with Interaction States) ─

const tabCopy = {
  projects: "项目与会话入口，适合承载目标、范围、阶段计划和上下文。",
  execution: "执行状态、Agent 队列、失败恢复和人工介入会放在这里。",
  deliverables: "沉淀文档、代码变更、审查记录与可交付证据。",
  governance: "审批、策略、权限、成本与记忆治理的集中控制区。",
};

function ComponentRow({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-[#2A2A2A] py-7">
      <div className="mb-4 text-sm font-semibold text-white">{title}</div>
      {children}
    </div>
  );
}

function ComponentPlayground() {
  const [demoCollapsed, setDemoCollapsed] = useState(false);

  return (
    <section aria-label="Minimal Dark Tokens" className="bg-[#050505] px-8 py-14 text-white">
      <div className="mx-auto max-w-5xl">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-sm font-medium text-[#8A8A8A]">Minimal Dark Tokens / 组件状态预览</div>
            <h2 className="mt-3 text-2xl font-semibold tracking-normal text-white">三省六部 Minimal Dark Tokens</h2>
          </div>
          <Badge className="h-7 rounded-full">shadcn-style + Radix UI + Tailwind + lucide-react</Badge>
        </div>

        <div>
          <ComponentRow title="Button">
            <div className="flex flex-wrap gap-3">
              <Button>Primary</Button>
              <Button variant="secondary">Secondary</Button>
              <Button variant="ghost">Ghost</Button>
              <Button variant="destructive">Destructive muted</Button>
            </div>
          </ComponentRow>

          <ComponentRow title="Input">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8A8A8A]" />
                <Input className="pl-10" placeholder="搜索项目、会话、任务..." />
              </div>
              <Input placeholder="普通输入框样式" />
            </div>
          </ComponentRow>

          <ComponentRow title="PromptBox">
            <div className="grid gap-3 md:grid-cols-2">
              <Textarea className="min-h-20" placeholder="compact prompt box" />
              <Textarea className="min-h-32" placeholder="comfortable prompt box" />
            </div>
          </ComponentRow>

          <ComponentRow title="Sidebar row">
            <div className="grid gap-2 md:grid-cols-4">
              <SidebarNavItem label="normal" icon={Gauge} />
              <SidebarNavItem label="hover" icon={Gauge} hover />
              <SidebarNavItem label="active" icon={Gauge} active />
              <SidebarNavItem label="with badge" icon={Gauge} badge="2" />
            </div>
          </ComponentRow>

          <ComponentRow title="Popover / Dropdown">
            <div className="flex flex-wrap gap-3">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="secondary">
                    <Settings className="h-4 w-4" />
                    用户设置菜单 mock
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                  <DropdownMenuItem>偏好设置</DropdownMenuItem>
                  <DropdownMenuItem>模型策略</DropdownMenuItem>
                  <DropdownMenuItem>通知方式</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </ComponentRow>

          <ComponentRow title="Dialog">
            <div className="flex flex-wrap gap-3">
              <Dialog>
                <DialogTrigger asChild>
                  <Button>
                    <ClipboardCheck className="h-4 w-4" />
                    审批确认弹窗 mock
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>确认放行本次审批？</DialogTitle>
                    <DialogDescription>
                      这是组件选型实验页的 mock 弹窗，用于验证 Radix Dialog 的暗色层级、按钮区和可访问性。
                    </DialogDescription>
                  </DialogHeader>
                  <div className="mt-5 rounded-2xl bg-[#222222] p-3 text-sm text-[#C7C7C7]">
                    二手交易平台 MVP / 商品发布与搜索规划 / Partial
                  </div>
                  <div className="mt-5 flex justify-end gap-3">
                    <DialogClose asChild>
                      <Button variant="secondary">取消</Button>
                    </DialogClose>
                    <DialogClose asChild>
                      <Button>确认</Button>
                    </DialogClose>
                  </div>
                </DialogContent>
              </Dialog>
            </div>
          </ComponentRow>

          <ComponentRow title="Tabs">
            <Tabs defaultValue="projects">
              <TabsList className="flex w-full justify-start overflow-x-auto">
                <TabsTrigger value="projects">项目管理</TabsTrigger>
                <TabsTrigger value="execution">执行中心</TabsTrigger>
                <TabsTrigger value="deliverables">成果中心</TabsTrigger>
                <TabsTrigger value="governance">治理</TabsTrigger>
              </TabsList>
              <TabsContent value="projects">{tabCopy.projects}</TabsContent>
              <TabsContent value="execution">{tabCopy.execution}</TabsContent>
              <TabsContent value="deliverables">{tabCopy.deliverables}</TabsContent>
              <TabsContent value="governance">{tabCopy.governance}</TabsContent>
            </Tabs>
          </ComponentRow>

          {/* ── INTERACTION STATES SECTION ── */}
          <ComponentRow title="Interaction States / 交互状态预览">
            <div className="space-y-3">
              <div className="rounded-2xl bg-[#222222] px-4 py-3 text-sm text-white">
                hover row — 灰色圆角背景 #222222
              </div>
              <div className="rounded-2xl bg-[#2C2C2C] px-4 py-3 text-sm text-white">
                active row — 深灰圆角背景 #2A2A2A
              </div>
              <button className="w-full rounded-2xl bg-white px-4 py-3 text-sm font-medium text-black transition-all active:scale-[0.98]">
                pressed button — active:scale-[0.98]
              </button>
              <input
                className="w-full rounded-full border-2 border-[#3A3A3A] bg-[#171717] px-4 py-3 text-sm text-white outline-none transition-all focus:border-[#2C2C2C] focus:ring-2 focus:ring-white/10"
                placeholder="focused input — border 变亮 + ring"
                readOnly
              />
              <div className="flex items-center gap-3 rounded-2xl bg-[#202020] px-4 py-3 text-sm text-white shadow-2xl shadow-black/60">
                <span className="flex items-center gap-1.5 rounded-full bg-white px-2 py-1 text-xs text-black">
                  <Check className="h-3 w-3" />
                  opened dialog trigger
                </span>
                opened dialog — #1C1C1C 背景 + 阴影
              </div>

              {/* collapsible project row demo */}
              <div>
                <button
                  className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-sm font-semibold text-white transition-colors hover:bg-[#222222]"
                  onClick={() => setDemoCollapsed(!demoCollapsed)}
                >
                  <ChevronDown
                    className="h-4 w-4 text-[#8A8A8A] transition-transform duration-200"
                    style={{ transform: demoCollapsed ? "rotate(-90deg)" : "rotate(0deg)" }}
                  />
                  collapsible project row
                </button>
                {!demoCollapsed && (
                  <div className="mt-1 space-y-1 pl-7">
                    <div className="rounded-md bg-[#2C2C2C] px-3 py-2 text-sm text-white">
                      selected conversation row — active bg
                    </div>
                    <div className="rounded-md px-3 py-2 text-sm text-[#C7C7C7] transition-colors hover:bg-[#222222] hover:text-white">
                      normal conversation row — hover bg only
                    </div>
                  </div>
                )}
              </div>
            </div>
          </ComponentRow>
        </div>

        <ChartPreview />
        <DataListPreview />
        <FeedbackPreview />
        <ResponsiveNotes />

        <div className="mt-8 grid gap-3 text-sm text-[#8A8A8A] md:grid-cols-3">
          <div className="rounded-2xl px-3 py-2 hover:bg-[#222222]">源码可控：组件代码在项目内继续演进。</div>
          <div className="rounded-2xl px-3 py-2 hover:bg-[#222222]">依赖克制：不新增更多 UI 库。</div>
          <div className="rounded-2xl px-3 py-2 hover:bg-[#222222]">可回滚隔离：隐藏路由不影响正式页面。</div>
        </div>
      </div>
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
        隐藏实验页：不接真实执行器、不写后端、不改正式 Workbench。
      </div>
    </div>
  );
}
