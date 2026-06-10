import {
  Activity,
  Archive,
  ArrowUp,
  Bot,
  CheckCircle2,
  ChevronDown,
  CircleEllipsis,
  ClipboardCheck,
  Database,
  FolderKanban,
  Gauge,
  LayoutDashboard,
  MessageSquarePlus,
  MoreHorizontal,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  User,
  Workflow,
  XCircle,
} from "lucide-react";
import type * as React from "react";

import { cn } from "../../lib/cn";
import {
  Avatar,
  AvatarFallback,
  Badge,
  Button,
  Card,
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

const quickCards = [
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
        active && "bg-zinc-900 text-zinc-50",
        hover && "bg-zinc-900/70 text-zinc-100",
        !active && !hover && (muted ? "text-zinc-500" : "text-zinc-300"),
        className,
      )}
    >
      {Icon ? <Icon className="h-4 w-4 shrink-0 text-zinc-500" /> : null}
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {badge ? <Badge className="h-5 border-sky-500/40 bg-sky-500 text-[11px] text-white">{badge}</Badge> : null}
    </div>
  );
}

function LabLogo() {
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-9 w-9 rounded-lg border border-sky-400/50 bg-zinc-900">
        <span className="absolute left-2 top-2 h-2 w-2 rounded-full bg-violet-400" />
        <span className="absolute left-[15px] top-2 h-2 w-2 rounded-full bg-sky-400" />
        <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-emerald-400" />
        <span className="absolute bottom-2 left-[7px] h-1.5 w-1.5 rounded-full bg-zinc-400" />
        <span className="absolute bottom-2 left-[14px] h-1.5 w-1.5 rounded-full bg-zinc-400" />
        <span className="absolute bottom-2 left-[21px] h-1.5 w-1.5 rounded-full bg-zinc-400" />
        <span className="absolute bottom-2 right-[7px] h-1.5 w-1.5 rounded-full bg-zinc-400" />
      </div>
      <div className="text-xl font-semibold tracking-normal text-zinc-50">三省六部</div>
    </div>
  );
}

function WorkbenchSidebar() {
  return (
    <aside className="flex h-full w-[300px] shrink-0 flex-col border-r border-zinc-800 bg-[#0d0d0f] px-4 py-5">
      <LabLogo />
      <Button variant="secondary" className="mt-6 w-full justify-start border-zinc-800 bg-zinc-900">
        <MessageSquarePlus className="h-4 w-4" />
        新建会话
      </Button>
      <div className="relative mt-3">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-600" />
        <Input className="h-10 pl-9" placeholder="搜索项目、会话、任务..." />
      </div>

      <ScrollArea className="mt-6 min-h-0 flex-1 pr-1">
        <div className="space-y-6">
          <div>
            <div className="mb-2 px-1 text-xs font-semibold uppercase tracking-[0.12em] text-zinc-600">运行与治理</div>
            <div className="space-y-1">
              {primaryNav.map((item) => (
                <SidebarNavItem key={item.label} {...item} />
              ))}
            </div>
          </div>

          <Separator />

          <div>
            <div className="mb-2 px-1 text-xs font-semibold uppercase tracking-[0.12em] text-zinc-600">主页面</div>
            <div className="space-y-1">
              {pageNav.map((item) => (
                <SidebarNavItem key={item.label} {...item} />
              ))}
            </div>
          </div>

          <Separator />

          <div>
            <div className="mb-3 px-1 text-xs font-semibold uppercase tracking-[0.12em] text-zinc-600">项目会话</div>
            <div className="space-y-4">
              <div>
                <div className="flex items-center gap-2 px-2 text-sm font-semibold text-zinc-100">
                  <ChevronDown className="h-4 w-4 text-zinc-500" />
                  二手交易平台 MVP
                </div>
                <div className="mt-2 space-y-1 pl-7">
                  <div className="truncate text-sm text-zinc-300">商品发布与搜索规划</div>
                  <div className="truncate text-sm text-zinc-500">聊天与订单闭环</div>
                  <div className="truncate text-sm text-zinc-500">后台审核方案</div>
                  <div className="truncate text-sm text-zinc-600">显示更多</div>
                </div>
              </div>
              <div>
                <div className="flex items-center gap-2 px-2 text-sm font-semibold text-zinc-100">
                  <ChevronDown className="h-4 w-4 text-zinc-500" />
                  AI 项目主管改造
                </div>
                <div className="mt-2 pl-7 text-sm text-zinc-500">Workbench 两栏布局</div>
              </div>
            </div>
          </div>
        </div>
      </ScrollArea>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button className="mt-4 flex h-11 w-full items-center gap-3 rounded-md border border-zinc-800 bg-zinc-950 px-3 text-left transition-colors hover:bg-zinc-900">
            <Avatar className="h-7 w-7 rounded-full">
              <AvatarFallback>K</AvatarFallback>
            </Avatar>
            <span className="min-w-0 flex-1 text-sm text-zinc-200">kk / 设置</span>
            <MoreHorizontal className="h-4 w-4 text-zinc-500" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem>
            <User className="mr-2 h-4 w-4 text-zinc-500" />
            账户信息
          </DropdownMenuItem>
          <DropdownMenuItem>
            <Settings className="mr-2 h-4 w-4 text-zinc-500" />
            工作台设置
          </DropdownMenuItem>
          <DropdownMenuSeparator className="my-1 h-px bg-zinc-800" />
          <DropdownMenuItem className="text-zinc-400">退出 mock 菜单</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </aside>
  );
}

function WorkbenchPreview() {
  return (
    <section aria-label="三省六部 Workbench Preview" className="h-[900px] min-h-screen bg-[#070708] text-zinc-100">
      <div className="flex h-full min-w-[1120px]">
        <WorkbenchSidebar />
        <main className="relative flex min-w-0 flex-1 flex-col">
          <div className="flex h-16 items-center justify-between border-b border-zinc-900 px-8">
            <div className="text-sm text-zinc-500">当前项目 / 当前会话 / 状态</div>
            <Badge variant="success" className="h-8 gap-2 rounded-full px-4">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              准备接收任务
            </Badge>
          </div>

          <div className="flex flex-1 flex-col items-center justify-center px-10 pb-32 text-center">
            <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl border border-zinc-800 bg-zinc-950">
              <Bot className="h-7 w-7 text-sky-300" />
            </div>
            <h1 className="text-[42px] font-semibold tracking-normal text-zinc-50">欢迎</h1>
            <h2 className="mt-4 text-2xl font-semibold tracking-normal text-zinc-200">我们来构建什么？</h2>
            <p className="mt-4 max-w-xl text-sm leading-6 text-zinc-500">
              描述目标、粘贴执行结果，或让 AI 项目主管拆分下一步任务
            </p>

            <div className="mt-14 grid w-full max-w-[676px] grid-cols-3 gap-5">
              {quickCards.map((card) => {
                const Icon = card.icon;
                return (
                  <Card key={card.title} className="h-24 rounded-lg bg-[#111113] p-5 text-left transition-colors hover:border-zinc-700">
                    <Icon className="mb-3 h-4 w-4 text-zinc-500" />
                    <div className="text-sm font-semibold text-zinc-100">{card.title}</div>
                    <div className="mt-2 text-xs text-zinc-600">{card.description}</div>
                  </Card>
                );
              })}
            </div>
          </div>

          <div className="absolute bottom-9 left-1/2 w-[min(760px,calc(100%-96px))] -translate-x-1/2">
            <div className="flex min-h-[72px] items-center gap-4 rounded-2xl border border-zinc-800 bg-[#111113] px-5 py-4">
              <div className="min-w-0 flex-1 text-left text-sm text-zinc-600">输入你的目标、需求或执行结果...</div>
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
    <Card className="rounded-lg bg-[#111113] p-5">
      <div className="mb-4 text-sm font-semibold text-zinc-300">{title}</div>
      {children}
    </Card>
  );
}

function ComponentPlayground() {
  return (
    <section aria-label="UI Component Selection Playground" className="bg-[#0a0a0b] px-8 py-12 text-zinc-100">
      <div className="mx-auto max-w-7xl">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-sm font-medium text-sky-300">UI Component Selection Playground / 组件选型试验区</div>
            <h2 className="mt-3 text-2xl font-semibold tracking-normal text-zinc-50">长期组件栈可视化样张</h2>
          </div>
          <Badge className="h-7 rounded-full">shadcn-style + Radix UI + Tailwind + lucide-react</Badge>
        </div>

        <div className="grid gap-5 lg:grid-cols-2">
          <ComponentRow title="Button">
            <div className="flex flex-wrap gap-3">
              <Button>Primary</Button>
              <Button variant="secondary">Secondary</Button>
              <Button variant="ghost">Ghost</Button>
              <Button variant="destructive">Destructive</Button>
            </div>
          </ComponentRow>

          <ComponentRow title="Input / Search">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-600" />
                <Input className="pl-9" placeholder="搜索项目、会话、任务..." />
              </div>
              <Input placeholder="普通输入框样式" />
            </div>
          </ComponentRow>

          <ComponentRow title="Textarea / PromptBox">
            <div className="grid gap-3 sm:grid-cols-2">
              <Textarea className="min-h-20" placeholder="compact prompt box" />
              <Textarea className="min-h-32" placeholder="comfortable prompt box" />
            </div>
          </ComponentRow>

          <ComponentRow title="Card">
            <div className="grid gap-3 sm:grid-cols-3">
              <Card className="p-4">normal</Card>
              <Card className="border-sky-400/40 bg-sky-400/10 p-4 text-sky-100">highlighted</Card>
              <Card className="border-zinc-900 bg-zinc-950/50 p-4 text-zinc-500">muted</Card>
            </div>
          </ComponentRow>

          <ComponentRow title="Badge">
            <div className="flex flex-wrap gap-2">
              <Badge>default</Badge>
              <Badge variant="success">success</Badge>
              <Badge variant="warning">warning</Badge>
              <Badge variant="danger">danger</Badge>
            </div>
          </ComponentRow>

          <ComponentRow title="SidebarNavItem">
            <div className="grid gap-2 sm:grid-cols-2">
              <SidebarNavItem label="normal" icon={Gauge} />
              <SidebarNavItem label="hover" icon={Gauge} hover />
              <SidebarNavItem label="active" icon={Gauge} active />
              <SidebarNavItem label="with badge" icon={Gauge} badge="2" />
            </div>
          </ComponentRow>

          <ComponentRow title="Dialog / Dropdown">
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
                  <div className="mt-5 rounded-md border border-zinc-800 bg-zinc-900/60 p-3 text-sm text-zinc-400">
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

        <div className="mt-5 grid gap-5 lg:grid-cols-3">
          <Card className="rounded-lg bg-[#111113] p-5">
            <Sparkles className="mb-4 h-5 w-5 text-sky-300" />
            <div className="font-semibold text-zinc-100">源码可控</div>
            <p className="mt-2 text-sm leading-6 text-zinc-500">组件代码在项目内，可按三省六部语义继续演进。</p>
          </Card>
          <Card className="rounded-lg bg-[#111113] p-5">
            <Database className="mb-4 h-5 w-5 text-emerald-300" />
            <div className="font-semibold text-zinc-100">依赖克制</div>
            <p className="mt-2 text-sm leading-6 text-zinc-500">只安装当前 Lab 需要的 Radix primitives 和图标，不做全量替换。</p>
          </Card>
          <Card className="rounded-lg bg-[#111113] p-5">
            <CheckCircle2 className="mb-4 h-5 w-5 text-violet-300" />
            <div className="font-semibold text-zinc-100">可回滚隔离</div>
            <p className="mt-2 text-sm leading-6 text-zinc-500">隐藏路由、独立 feature、独立组件层，不影响正式 Workbench。</p>
          </Card>
        </div>
      </div>
    </section>
  );
}

export function SanshengLiubuUiLabPage() {
  return (
    <div className="min-h-screen bg-[#070708]">
      <WorkbenchPreview />
      <ComponentPlayground />
      <div className="border-t border-zinc-900 bg-[#070708] px-8 py-6 text-center text-xs text-zinc-600">
        <XCircle className="mr-2 inline h-3.5 w-3.5" />
        隐藏实验页：不接真实执行器、不写后端、不改正式 Workbench。
      </div>
    </div>
  );
}
