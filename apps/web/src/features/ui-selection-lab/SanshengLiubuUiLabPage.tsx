import {
  Activity,
  Bot,
  Check,
  ChevronDown,
  ChevronRight,
  CircleEllipsis,
  ClipboardCheck,
  FolderKanban,
  Gauge,
  LayoutDashboard,
  MessageSquarePlus,
  MoreHorizontal,
  Search,
  Send,
  Settings,
  User,
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
  ScrollArea,
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
  AdvanceNextModal,
  ApprovalsModal,
  CostUsageModal,
  CreatePlanModal,
  DashboardModal,
  ExecutionStatusModal,
  GitWritePreviewModal,
  RepositoryQueueModal,
  ReviewResultModal,
} from "./components/WorkbenchRuntimeModals";
import {
  getDefaultMessages,
  mockConversationMessages,
  pageNavItems,
  projectGroups,
  slimMoreTools,
  type Conversation,
  type MockMessage,
} from "./mockInteractions";

// ── Tokens ─────────────────────────────────────────────────

const minimalDarkTokens = {
  pageBg: "#000000",
  sidebarBg: "#000000",
  mainBg: "#000000",
  hoverBg: "#1F1F1F",
  activeBg: "#2A2A2A",
  modalBg: "#303030",
  popoverBg: "#303030",
  inputBg: "#1A1A1A",
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

// ── Quick Actions ──────────────────────────────────────────

const quickActions = [
  { title: "创建项目计划", description: "从目标生成任务队列", icon: FolderKanban, modal: "createPlan" as const },
  { title: "审查执行结果", description: "判断 Pass / Partial", icon: ClipboardCheck, modal: "reviewResult" as const },
  { title: "推进下一步", description: "生成最小执行指令", icon: Send, modal: "advanceNext" as const },
];

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
        active && "bg-[#2A2A2A] text-white",
        hover && "bg-[#1F1F1F] text-white",
        !active && !hover && (muted ? "text-[#5F5F5F]" : "text-[#C7C7C7]"),
        "hover:bg-[#1F1F1F] hover:text-white",
        className,
      )}
    >
      {Icon ? <Icon className="h-4 w-4 shrink-0 text-[#8A8A8A]" /> : null}
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {badge ? <Badge className="h-5 border-[#3A3A3A] bg-[#2A2A2A] text-[11px] text-white">{badge}</Badge> : null}
    </div>
  );
}

// ── Toast ──────────────────────────────────────────────────

function Toast({ message, onClose }: { message: string; onClose: () => void }) {
  return (
    <div className="fixed bottom-20 left-1/2 z-[100] -translate-x-1/2 animate-[fadeIn_150ms_ease-out]">
      <div className="flex items-center gap-3 rounded-full border border-[#3A3A3A] bg-[#303030] px-4 py-2.5 shadow-2xl shadow-black/60">
        <Check className="h-4 w-4 text-white" />
        <span className="text-sm text-white">{message}</span>
        <button className="ml-1 rounded-full p-0.5 text-[#8A8A8A] transition-colors hover:text-white" onClick={onClose}>
          <XCircle className="h-4 w-4" />
        </button>
      </div>
    </div>
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
  const [topStatus, setTopStatus] = useState("当前项目 / 当前会话 / 状态");
  const [moreToolsExpanded, setMoreToolsExpanded] = useState(false);

  // -- derived --
  const filteredGroups = useMemo(() => {
    if (!searchQuery.trim()) return projectGroups;
    const q = searchQuery.toLowerCase();
    return projectGroups
      .map((g) => ({
        ...g,
        conversations: g.conversations.filter((c) => c.title.toLowerCase().includes(q)),
      }))
      .filter((g) => g.name.toLowerCase().includes(q) || g.conversations.length > 0);
  }, [searchQuery]);

  const activeConversation = useMemo(() => {
    if (!activeConversationId) return null;
    for (const g of projectGroups) {
      const found = g.conversations.find((c) => c.id === activeConversationId);
      if (found) return { conversation: found, project: g };
    }
    return null;
  }, [activeConversationId]);

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
    setActiveMainPage(null);
    setActiveConversationId(null);
    setWelcomeMessages(getDefaultMessages());
    setTopStatus("新会话 / 未绑定项目 / 准备构建");
    setMoreToolsExpanded(false);
  }, []);

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

  const handleSelectConversation = useCallback((conv: Conversation, projectName: string) => {
    setActiveMainPage(null);
    setActiveConversationId(conv.id);
    setTopStatus(`${projectName} / ${conv.title} / ${conv.status}`);
  }, []);

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
    setTopStatus(`${label} / mock 页面`);
  }, []);

  const handlePromptSend = useCallback(
    (text: string) => {
      const newMsg: MockMessage = {
        role: "user",
        content: text,
        time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
      };
      const reply: MockMessage = {
        role: "assistant",
        content: `收到：「${text}」\n\n这是 mock 回复。当前为实验页，不连接真实 AI 执行器。你的输入已记录在本地会话状态中。`,
        time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
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
    [activeConversationId, showToast],
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

    // Welcome state
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
          描述目标、粘贴执行结果，或让 AI 项目主管拆分下一步任务
        </p>

        <div className="mt-6 w-full max-w-[680px] space-y-1 text-left md:mt-10 lg:mt-12">
          {quickActions.map((action) => {
            const Icon = action.icon;
            const buttonContent = (
              <button className="group flex w-full items-center gap-4 rounded-2xl px-4 py-3 text-left transition-all duration-150 hover:bg-[#1F1F1F] active:scale-[0.98]">
                <Icon className="h-4 w-4 shrink-0 text-[#8A8A8A]" />
                <span className="min-w-0 flex-1 text-sm font-medium text-white">{action.title}</span>
                <span className="hidden max-w-[220px] text-sm text-[#8A8A8A] xl:block">{action.description}</span>
                <span className="text-lg leading-none text-[#5F5F5F] transition-colors group-hover:text-[#C7C7C7]">
                  &gt;
                </span>
              </button>
            );

            if (action.modal === "createPlan") {
              return <CreatePlanModal key={action.title}>{buttonContent}</CreatePlanModal>;
            }
            if (action.modal === "reviewResult") {
              return <ReviewResultModal key={action.title}>{buttonContent}</ReviewResultModal>;
            }
            return <AdvanceNextModal key={action.title}>{buttonContent}</AdvanceNextModal>;
          })}
        </div>
      </div>
    );
  }

  return (
    <section
      data-testid="ui-lab-workbench-preview"
      aria-label="三省六部 Workbench Preview"
      className="h-[100dvh] min-h-[720px] w-full overflow-hidden text-white"
      style={{ ...workbenchShellStyle, backgroundColor: minimalDarkTokens.pageBg }}
    >
      <div className="flex h-full w-full overflow-hidden">
        {/* ── Sidebar ── */}
        <aside
          data-testid="ui-lab-sidebar"
          className="flex h-full shrink-0 flex-col border-r border-[#2A2A2A] bg-black px-3 py-4 md:px-4 md:py-5"
          style={{ width: "var(--lab-sidebar-width)" }}
        >
          <LabLogo />

          {/* 新建会话 */}
          <button
            className="mt-4 flex w-full items-center justify-start gap-2 rounded-xl px-3 py-2.5 text-sm text-white transition-all duration-150 hover:bg-[#1F1F1F] active:scale-[0.98] md:mt-6"
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

          <ScrollArea className="mt-4 min-h-0 flex-1 pr-1 md:mt-6">
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

                  {/* ... 更多 — inline sidebar disclosure, NOT a main page entry */}
                  <div>
                    <SidebarNavItem
                      label="... 更多"
                      icon={CircleEllipsis}
                      muted={!moreToolsExpanded}
                      active={false}
                      onClick={() => setMoreToolsExpanded((prev) => !prev)}
                    />
                    <div
                      className={`grid transition-all duration-200 ease-out ${
                        moreToolsExpanded
                          ? "grid-rows-[1fr] opacity-100 translate-y-0"
                          : "grid-rows-[0fr] opacity-0 -translate-y-1"
                      }`}
                    >
                      <div className="overflow-hidden">
                        <div className="space-y-0.5 pt-0.5">
                          <CostUsageModal>
                            <SidebarNavItem label="成本用量" icon={slimMoreTools[0].icon} />
                          </CostUsageModal>
                          <RepositoryQueueModal>
                            <SidebarNavItem label="仓库队列" icon={slimMoreTools[1].icon} />
                          </RepositoryQueueModal>
                          <GitWritePreviewModal>
                            <SidebarNavItem label="Git 写入预览" icon={slimMoreTools[2].icon} />
                          </GitWritePreviewModal>
                        </div>
                      </div>
                    </div>
                  </div>
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
                                      ? "bg-[#2A2A2A] text-white"
                                      : "text-[#C7C7C7] hover:bg-[#1F1F1F] hover:text-white",
                                  )}
                                  onClick={() => handleSelectConversation(conv, group.name)}
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
          </ScrollArea>

          {/* User menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="mt-4 flex h-11 w-full items-center gap-3 rounded-2xl px-3 text-left transition-all duration-150 hover:bg-[#1F1F1F] active:scale-[0.98]">
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
              <DropdownMenuSeparator className="my-1 h-px bg-[#4A4A4A]" />
              <DropdownMenuItem className="text-[#C7C7C7]">退出 mock 菜单</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </aside>

        {/* ── Main ── */}
        <main className="relative flex min-w-0 flex-1 flex-col overflow-hidden bg-black">
          {/* Top status bar */}
          <div className="flex h-14 shrink-0 items-center justify-between border-b border-[#2A2A2A] px-5 md:h-16 md:px-8">
            <div className="text-sm text-[#8A8A8A]">{topStatus}</div>
            <Badge className="h-8 shrink-0 gap-2 rounded-full px-3 md:px-4">
              <span className="h-2 w-2 rounded-full bg-white" />
              准备接收任务
            </Badge>
          </div>

          {renderMainContent()}

          {/* PromptBox */}
          <WorkbenchPromptBox onSend={handlePromptSend} />
        </main>
      </div>

      {/* Toast */}
      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
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
    <section aria-label="Minimal Dark Tokens" className="bg-black px-8 py-14 text-white">
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
                  <div className="mt-5 rounded-2xl bg-[#1F1F1F] p-3 text-sm text-[#C7C7C7]">
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
              <div className="rounded-2xl bg-[#1F1F1F] px-4 py-3 text-sm text-white">
                hover row — 灰色圆角背景 #1F1F1F
              </div>
              <div className="rounded-2xl bg-[#2A2A2A] px-4 py-3 text-sm text-white">
                active row — 深灰圆角背景 #2A2A2A
              </div>
              <button className="w-full rounded-2xl bg-white px-4 py-3 text-sm font-medium text-black transition-all active:scale-[0.98]">
                pressed button — active:scale-[0.98]
              </button>
              <input
                className="w-full rounded-full border-2 border-[#3A3A3A] bg-[#1A1A1A] px-4 py-3 text-sm text-white outline-none transition-all focus:border-[#4A4A4A] focus:ring-2 focus:ring-white/10"
                placeholder="focused input — border 变亮 + ring"
                readOnly
              />
              <div className="flex items-center gap-3 rounded-2xl bg-[#303030] px-4 py-3 text-sm text-white shadow-2xl shadow-black/60">
                <span className="flex items-center gap-1.5 rounded-full bg-white px-2 py-1 text-xs text-black">
                  <Check className="h-3 w-3" />
                  opened dialog trigger
                </span>
                opened dialog — #303030 背景 + 阴影
              </div>

              {/* collapsible project row demo */}
              <div>
                <button
                  className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-sm font-semibold text-white transition-colors hover:bg-[#1F1F1F]"
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
                    <div className="rounded-md bg-[#2A2A2A] px-3 py-2 text-sm text-white">
                      selected conversation row — active bg
                    </div>
                    <div className="rounded-md px-3 py-2 text-sm text-[#C7C7C7] transition-colors hover:bg-[#1F1F1F] hover:text-white">
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
          <div className="rounded-2xl px-3 py-2 hover:bg-[#1F1F1F]">源码可控：组件代码在项目内继续演进。</div>
          <div className="rounded-2xl px-3 py-2 hover:bg-[#1F1F1F]">依赖克制：不新增更多 UI 库。</div>
          <div className="rounded-2xl px-3 py-2 hover:bg-[#1F1F1F]">可回滚隔离：隐藏路由不影响正式页面。</div>
        </div>
      </div>
    </section>
  );
}

// ── Page Export ────────────────────────────────────────────

export function SanshengLiubuUiLabPage() {
  return (
    <div className="min-h-screen bg-black">
      <WorkbenchPreview />
      <ComponentPlayground />
      <div className="border-t border-[#2A2A2A] bg-black px-8 py-6 text-center text-xs text-[#5F5F5F]">
        <XCircle className="mr-2 inline h-3.5 w-3.5" />
        隐藏实验页：不接真实执行器、不写后端、不改正式 Workbench。
      </div>
    </div>
  );
}
