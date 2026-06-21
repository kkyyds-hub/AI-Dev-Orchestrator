import { Clock3, FileCode2, GitBranch, ListChecks } from "lucide-react";

const statusItems = ["pending", "running", "partial", "passed", "blocked"] as const;

const rows = [
  { type: "任务行", title: "商品发布与搜索规划", status: "running", time: "12:42", action: "查看" },
  { type: "执行记录行", title: "Codex 实现前端实验页", status: "passed", time: "11:18", action: "日志" },
  { type: "审批记录行", title: "放行 Minimal Dark Tokens", status: "pending", time: "09:36", action: "审批" },
] as const;

const activities = [
  { title: "创建项目计划", body: "AI 项目主管拆分了 4 个最小执行任务。", time: "刚刚" },
  { title: "审查执行结果", body: "Workbench Preview 通过构建检查。", time: "12 分钟前" },
  { title: "等待审批", body: "需要确认 UI 体系是否进入正式迁移。", time: "28 分钟前" },
] as const;

export function StatusPill({ status }: { status: string }) {
  const shade = {
    pending: "bg-[#171717] text-[#C7C7C7]",
    running: "bg-[#2C2C2C] text-white",
    partial: "bg-[#222222] text-[#C7C7C7]",
    passed: "bg-[#1C1C1C] text-white",
    blocked: "bg-[#171717] text-[#8A8A8A]",
  }[status] ?? "bg-[#171717] text-[#C7C7C7]";

  return (
    <span className={`inline-flex items-center gap-2 rounded-full border border-[#3A3A3A] px-2.5 py-1 text-xs ${shade}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-80" />
      {status}
    </span>
  );
}

export function DataListPreview() {
  return (
    <>
      <div className="border-t border-[#2A2A2A] py-7">
        <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-white">
          <ListChecks className="h-4 w-4 text-[#8A8A8A]" />
          Data List / 数据列表行
        </div>
        <div className="space-y-1">
          {rows.map((row) => (
            <div key={row.title} className="grid gap-3 rounded-2xl px-3 py-3 transition-colors hover:bg-[#222222] md:grid-cols-[112px_minmax(0,1fr)_96px_80px_56px] md:items-center">
              <div className="text-xs text-[#8A8A8A]">{row.type}</div>
              <div className="min-w-0 truncate text-sm text-white">{row.title}</div>
              <StatusPill status={row.status} />
              <div className="flex items-center gap-1 text-xs text-[#8A8A8A]">
                <Clock3 className="h-3.5 w-3.5" />
                {row.time}
              </div>
              <button className="text-left text-sm text-[#C7C7C7] hover:text-white">{row.action}</button>
            </div>
          ))}
        </div>
      </div>

      <div className="border-t border-[#2A2A2A] py-7">
        <div className="mb-4 text-sm font-semibold text-white">Status / 状态组件</div>
        <div className="flex flex-wrap gap-2">
          {statusItems.map((status) => (
            <StatusPill key={status} status={status} />
          ))}
        </div>
      </div>

      <div className="border-t border-[#2A2A2A] py-7">
        <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-white">
          <GitBranch className="h-4 w-4 text-[#8A8A8A]" />
          Timeline / Activity Feed
        </div>
        <div className="space-y-0">
          {activities.map((activity, index) => (
            <div key={activity.title} className="grid grid-cols-[22px_minmax(0,1fr)] gap-3">
              <div className="flex flex-col items-center">
                <span className="mt-1 h-2.5 w-2.5 rounded-full border border-[#C7C7C7] bg-black" />
                {index < activities.length - 1 ? <span className="mt-1 h-full min-h-12 w-px bg-[#2C2C2C]" /> : null}
              </div>
              <div className="pb-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-sm font-medium text-white">{activity.title}</div>
                  <div className="text-xs text-[#5F5F5F]">{activity.time}</div>
                </div>
                <div className="mt-1 text-sm text-[#8A8A8A]">{activity.body}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="border-t border-[#2A2A2A] py-7">
        <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-white">
          <FileCode2 className="h-4 w-4 text-[#8A8A8A]" />
          Code / Log Block
        </div>
        <div className="max-w-full overflow-hidden rounded-[20px] border border-[#2A2A2A] bg-black">
          <pre className="overflow-x-auto p-4 font-mono text-xs leading-6 text-[#C7C7C7]">
{`[12:42:10] run started: workbench-ui-lab
[12:42:14] build passed
[12:42:18] diff summary: 3 files changed
diff --git a/apps/web/src/features/ui-selection-lab/SanshengLiubuUiLabPage.tsx b/apps/web/src/features/ui-selection-lab/SanshengLiubuUiLabPage.tsx`}
          </pre>
        </div>
      </div>
    </>
  );
}
