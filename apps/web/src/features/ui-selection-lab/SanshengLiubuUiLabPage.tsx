import {
  Activity,
  Archive,
  ArrowUp,
  Bot,
  ChevronDown,
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
  ShieldCheck,
  User,
  Workflow,
  XCircle,
} from "lucide-react";
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

const primaryNav = [
  { label: "数据看板", icon: LayoutDashboard, active: true },
  { label: "待审批", icon: ClipboardCheck, badge: "2" },
  { label: "执行状态", icon: Activity },
  { label: "... 更多", icon: CircleEllipsis, muted: true },
];

const pageNav = [
  { label: "项目管理", icon: FolderKanban },
  { label: "执行中心", icon: Workflow },
  { label: "成果中心", icon: Archive },
  { label: "治理", icon: ShieldCheck },
];

const quickActions = [
  {
    title: "创建项目计划",
    description: "从目标生成任务队列",
    icon: FolderKanban,
  },
  {
    title: "审查执行结果",
    description: "判断 Pass / Partial",
    icon: ClipboardCheck,
  },
  {
    title: "推进下一步",
    description: "生成最小执行指令",
    icon: Send,
  },
];

const tabCopy = {
  projects: "项目与会话入口，适合承载目标、范围、阶段计划和上下文。",
  execution: "执行状态、Agent 队列、失败恢复和人工介入会放在这里。",
  deliverables: "沉淀文档、代码变更、审查记录与可交付证据。",
  governance: "审批、策略、权限、成本与记忆治理的集中控制区。",
};

type SidebarNavItemProps = {
  label: string;
  icon?: React.ComponentType<{ className?: string }>;
  active?: boolean;
  hover?: boolean;
  muted?: boolean;
  badge?: string;
  className?: string;
};

function SidebarNavItem({ label, icon: Icon, active, hover, muted, badge, className }: SidebarNavItemProps) {
  return (
    <div
      className={cn(
        "flex h-9 items-center gap-3 rounded-md px-3 text-sm transition-colors",
        active && "bg-[#2A2A2A] text-white",
        hover && "bg-[#1F1F1F] text-white",
        !active && !hover && (muted ? "text-[#5F5F5F]" : "text-[#C7C7C7]"),
        className,
      )}
    >
      {Icon ? <Icon className="h-4 w-4 shrink-0 text-[#8A8A8A]" /> : null}
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {badge ? <Badge className="h-5 border-[#3A3A3A] bg-[#2A2A2A] text-[11px] text-white">{badge}</Badge> : null}
    </div>
  );
}

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

function WorkbenchSidebar() {
  return (
    <aside
      data-testid="ui-lab-sidebar"
      className="flex h-full shrink-0 flex-col border-r border-[#2A2A2A] bg-black px-3 py-4 md:px-4 md:py-5"
      style={{ width: "var(--lab-sidebar-width)" }}
    >
      <LabLogo />
      <Button variant="ghost" className="mt-4 w-full justify-start rounded-xl text-white md:mt-6">
        <MessageSquarePlus className="h-4 w-4" />
        新建会话
      </Button>
      <div className="relative mt-3">
        <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8A8A8A]" />
        <Input className="h-10 pl-9" placeholder="搜索项目、会话、任务..." />
      </div>

      <ScrollArea className="mt-4 min-h-0 flex-1 pr-1 md:mt-6">
        <div className="space-y-4 md:space-y-6">
          <div>
            <div className="mb-2 px-1 text-xs font-semibold uppercase tracking-[0.12em] text-[#5F5F5F]">运行与治理</div>
            <div className="space-y-1">
              {primaryNav.map((item) => (
                <SidebarNavItem key={item.label} {...item} />
              ))}
            </div>
          </div>

          <Separator />

          <div>
            <div className="mb-2 px-1 text-xs font-semibold uppercase tracking-[0.12em] text-[#5F5F5F]">主页面</div>
            <div className="space-y-1">
              {pageNav.map((item) => (
                <SidebarNavItem key={item.label} {...item} />
              ))}
            </div>
          </div>

          <Separator />

          <div>
            <div className="mb-3 px-1 text-xs font-semibold uppercase tracking-[0.12em] text-[#5F5F5F]">项目会话</div>
            <div className="space-y-4">
              <div>
                <div className="flex items-center gap-2 px-2 text-sm font-semibold text-white">
                  <ChevronDown className="h-4 w-4 text-[#8A8A8A]" />
                  二手交易平台 MVP
                </div>
                <div className="mt-2 space-y-1 pl-7">
                  <div className="truncate text-sm text-[#C7C7C7]">商品发布与搜索规划</div>
                  <div className="truncate text-sm text-[#8A8A8A]">聊天与订单闭环</div>
                  <div className="truncate text-sm text-[#8A8A8A]">后台审核方案</div>
                  <div className="truncate text-sm text-[#5F5F5F]">显示更多</div>
                </div>
              </div>
              <div>
                <div className="flex items-center gap-2 px-2 text-sm font-semibold text-white">
                  <ChevronDown className="h-4 w-4 text-[#8A8A8A]" />
                  AI 项目主管改造
                </div>
                <div className="mt-2 pl-7 text-sm text-[#8A8A8A]">Workbench 两栏布局</div>
              </div>
            </div>
          </div>
        </div>
      </ScrollArea>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button className="mt-4 flex h-11 w-full items-center gap-3 rounded-2xl px-3 text-left transition-colors hover:bg-[#1F1F1F]">
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
  );
}

function WorkbenchPreview() {
  return (
    <section
      data-testid="ui-lab-workbench-preview"
      aria-label="三省六部 Workbench Preview"
      className="h-[100dvh] min-h-[720px] w-full overflow-hidden text-white"
      style={{ ...workbenchShellStyle, backgroundColor: minimalDarkTokens.pageBg }}
    >
      <div className="flex h-full w-full overflow-hidden">
        <WorkbenchSidebar />
        <main className="relative flex min-w-0 flex-1 flex-col overflow-hidden bg-black">
          <div className="flex h-14 shrink-0 items-center justify-between border-b border-[#2A2A2A] px-5 md:h-16 md:px-8">
            <div className="text-sm text-[#8A8A8A]">当前项目 / 当前会话 / 状态</div>
            <Badge className="h-8 shrink-0 gap-2 rounded-full px-3 md:px-4">
              <span className="h-2 w-2 rounded-full bg-white" />
              准备接收任务
            </Badge>
          </div>

          <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-5 pb-24 pt-6 text-center md:px-8 md:pb-28 lg:px-10">
            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-2xl border border-[#2A2A2A] bg-black md:mb-5 md:h-14 md:w-14">
              <Bot className="h-6 w-6 text-[#C7C7C7] md:h-7 md:w-7" />
            </div>
            <h1 className="text-3xl font-semibold tracking-normal text-white md:text-[42px]">欢迎</h1>
            <h2 className="mt-3 text-xl font-semibold tracking-normal text-[#C7C7C7] md:mt-4 md:text-2xl">我们来构建什么？</h2>
            <p className="mt-3 max-w-xl text-sm leading-6 text-[#8A8A8A] md:mt-4">
              描述目标、粘贴执行结果，或让 AI 项目主管拆分下一步任务
            </p>

            <div className="mt-6 w-full max-w-[680px] space-y-1 text-left md:mt-10 lg:mt-12">
              {quickActions.map((action) => {
                const Icon = action.icon;
                return (
                  <button
                    key={action.title}
                    className="group flex w-full items-center gap-4 rounded-2xl px-4 py-3 text-left transition-colors hover:bg-[#1F1F1F]"
                  >
                    <Icon className="h-4 w-4 shrink-0 text-[#8A8A8A]" />
                    <span className="min-w-0 flex-1 text-sm font-medium text-white">{action.title}</span>
                    <span className="hidden max-w-[220px] text-sm text-[#8A8A8A] xl:block">{action.description}</span>
                    <span className="text-lg leading-none text-[#5F5F5F] transition-colors group-hover:text-[#C7C7C7]">&gt;</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div
            data-testid="ui-lab-promptbox"
            className="absolute bottom-5 left-1/2 max-w-[calc(100%-40px)] -translate-x-1/2 md:bottom-7 lg:bottom-9"
            style={{ width: "min(760px, calc(100vw - var(--lab-sidebar-width) - 64px))" }}
          >
            <div className="flex min-h-16 items-center gap-4 rounded-[24px] border border-[#2A2A2A] bg-[#1A1A1A] px-4 py-3 md:min-h-[72px] md:px-5 md:py-4">
              <div className="min-w-0 flex-1 text-left text-sm text-[#8A8A8A]">输入你的目标、需求或执行结果...</div>
              <Button size="icon" className="h-9 w-9 rounded-full">
                <ArrowUp className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </main>
      </div>
    </section>
  );
}

function ComponentRow({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-[#2A2A2A] py-7">
      <div className="mb-4 text-sm font-semibold text-white">{title}</div>
      {children}
    </div>
  );
}

function ComponentPlayground() {
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
