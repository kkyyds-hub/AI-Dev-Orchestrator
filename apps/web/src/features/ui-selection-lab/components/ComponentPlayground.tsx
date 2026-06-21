import {
  Check,
  ChevronDown,
  ClipboardCheck,
  Gauge,
  Search,
  Settings,
  User,
} from "lucide-react";
import { useState } from "react";
import type * as React from "react";

import { planFlowPreviewStates } from "../planFlowMock";
import { ChartPreview } from "./ChartPreview";
import { DataListPreview } from "./DataListPreview";
import { FeedbackPreview } from "./FeedbackPreview";
import { ResponsiveNotes } from "./ResponsiveNotes";
import { SidebarNavItem } from "./SidebarNavItem";
import { AccountSettingsModal } from "./AccountSettingsModal";
import { WorkbenchSettingsModal, type WorkbenchSettingsSection } from "./WorkbenchSettingsModal";
import { WorkbenchUserDecisionSurfacePreview } from "./WorkbenchUserDecisionSurfaces";
import {
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
  DropdownMenuTrigger,
  Input,
  ReadbackRows,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Textarea,
} from "./ui";
import { WorkbenchPlanFlowCard } from "./WorkbenchPlanFlowCards";

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

export function ComponentPlayground() {
  const [demoCollapsed, setDemoCollapsed] = useState(false);
  const [accountPreviewOpen, setAccountPreviewOpen] = useState(false);
  const [settingsPreviewOpen, setSettingsPreviewOpen] = useState(false);
  const [settingsPreviewSection, setSettingsPreviewSection] = useState<WorkbenchSettingsSection>("workspace");

  function openSettingsPreview(section: WorkbenchSettingsSection) {
    setSettingsPreviewSection(section);
    setSettingsPreviewOpen(true);
  }

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
          <ComponentRow title="Plan Flow / 工作台计划流">
            <div className="grid gap-5">
              <WorkbenchPlanFlowCard state={planFlowPreviewStates.draft} readonly compact defaultCollapsed />
              <WorkbenchPlanFlowCard state={planFlowPreviewStates.changesRequested} readonly compact defaultCollapsed />
              <WorkbenchPlanFlowCard state={planFlowPreviewStates.rejected} readonly compact defaultCollapsed />
              <WorkbenchPlanFlowCard state={planFlowPreviewStates.confirmed} readonly compact defaultCollapsed />
              <WorkbenchPlanFlowCard state={planFlowPreviewStates.created} readonly compact defaultCollapsed />
            </div>
          </ComponentRow>

          <ComponentRow title="User Decision Surfaces / 普通用户承接组件">
            <WorkbenchUserDecisionSurfacePreview />
          </ComponentRow>

          <ComponentRow title="Account Settings Modal / 账户设置弹窗">
            <div className="flex flex-col gap-4 border-y border-[#2A2A2A] py-5 md:flex-row md:items-center md:justify-between">
              <div>
                <div className="text-sm font-semibold text-white">左下角账户信息入口</div>
                <div className="mt-1 text-sm text-[#8A8A8A]">
                  独立账户弹窗，只从用户菜单的账户信息进入，后续账户能力可单独扩展。
                </div>
              </div>
              <Button variant="secondary" onClick={() => setAccountPreviewOpen(true)}>
                <User className="h-4 w-4" />
                打开账户信息
              </Button>
            </div>
            <AccountSettingsModal open={accountPreviewOpen} onOpenChange={setAccountPreviewOpen} />
          </ComponentRow>

          <ComponentRow title="Workbench Settings Modal / 工作台设置大弹窗">
            <div className="flex flex-col gap-4 border-y border-[#2A2A2A] py-5 md:flex-row md:items-center md:justify-between">
              <div>
                <div className="text-sm font-semibold text-white">左下角 kk / 设置入口</div>
                <div className="mt-1 text-sm text-[#8A8A8A]">
                  工作台设置独立承载工作台、模型和安全边界，不包含账户信息。
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" onClick={() => openSettingsPreview("workspace")}>
                  <Settings className="h-4 w-4" />
                  打开工作台页
                </Button>
              </div>
            </div>
            <WorkbenchSettingsModal
              open={settingsPreviewOpen}
              onOpenChange={setSettingsPreviewOpen}
              defaultSection={settingsPreviewSection}
            />
          </ComponentRow>

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
                    用户设置菜单
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
                    审批确认弹窗
                  </Button>
                </DialogTrigger>
                <DialogContent className="ui-lab-dialog-enter">
                  <DialogHeader>
                    <DialogTitle>确认放行本次审批？</DialogTitle>
                    <DialogDescription>
                      这是组件选型实验页的 弹窗，用于验证 Radix Dialog 的暗色层级、按钮区和可访问性。
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
              <TabsContent value="projects" className="ui-lab-detail-switch">{tabCopy.projects}</TabsContent>
              <TabsContent value="execution" className="ui-lab-detail-switch">{tabCopy.execution}</TabsContent>
              <TabsContent value="deliverables" className="ui-lab-detail-switch">{tabCopy.deliverables}</TabsContent>
              <TabsContent value="governance" className="ui-lab-detail-switch">{tabCopy.governance}</TabsContent>
            </Tabs>
          </ComponentRow>

          <ComponentRow title="Interaction States / 交互状态预览">
            <div className="space-y-3">
              <div className="rounded-2xl bg-[#222222] px-4 py-3 text-sm text-white">
                hover row - 灰色圆角背景 #222222
              </div>
              <div className="rounded-2xl bg-[#2C2C2C] px-4 py-3 text-sm text-white">
                active row - 深灰圆角背景 #2A2A2A
              </div>
              <button className="w-full rounded-2xl bg-white px-4 py-3 text-sm font-medium text-black transition-all active:scale-[0.98]">
                pressed button - active:scale-[0.98]
              </button>
              <input
                className="w-full rounded-full border-2 border-[#3A3A3A] bg-[#171717] px-4 py-3 text-sm text-white outline-none transition-all focus:border-[#2C2C2C] focus:ring-2 focus:ring-white/10"
                placeholder="focused input - border 变亮 + ring"
                readOnly
              />
              <div className="flex items-center gap-3 rounded-2xl bg-[#202020] px-4 py-3 text-sm text-white shadow-2xl shadow-black/60">
                <span className="flex items-center gap-1.5 rounded-full bg-white px-2 py-1 text-xs text-black">
                  <Check className="h-3 w-3" />
                  opened dialog trigger
                </span>
                opened dialog - #1C1C1C 背景 + 阴影
              </div>

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
                      selected conversation row - active bg
                    </div>
                    <div className="rounded-md px-3 py-2 text-sm text-[#C7C7C7] transition-colors hover:bg-[#222222] hover:text-white">
                      normal conversation row - hover bg only
                    </div>
                  </div>
                )}
              </div>
            </div>
          </ComponentRow>

          <ComponentRow title="ReadbackRows">
            <ReadbackRows
              rows={[
                ["运行", "running · run_7F3A"],
                ["Git", "只读预检 · 写入关闭"],
                ["质量闸门", "等待结果"],
              ]}
              records={[
                "11:34:08 读取当前项目上下文",
                "11:34:37 生成接入任务拆分建议",
              ]}
              footer="仅展示读回信息，不触发执行操作"
            />
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
