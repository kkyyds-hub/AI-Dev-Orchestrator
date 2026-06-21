import { Bell, PanelRightOpen, RotateCcw, ShieldCheck, Trash2 } from "lucide-react";

import {
  Button,
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "./ui";

const notices = [
  { title: "普通提示", body: "已保存当前视觉选择。" },
  { title: "警告提示", body: "该样张仍是隐藏实验页，不代表正式迁移完成。" },
  { title: "失败提示", body: "执行器连接失败时使用灰阶危险提示，不使用鲜红色。" },
] as const;

export function FeedbackPreview() {
  return (
    <>
      <div className="border-t border-[#2A2A2A] py-7">
        <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-white">
          <Bell className="h-4 w-4 text-[#8A8A8A]" />
          Alert / Toast / Inline Notice
        </div>
        <div className="space-y-2">
          {notices.map((notice) => (
            <div key={notice.title} className="rounded-2xl border border-[#2A2A2A] bg-black px-4 py-3">
              <div className="text-sm font-medium text-white">{notice.title}</div>
              <div className="mt-1 text-sm text-[#8A8A8A]">{notice.body}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="border-t border-[#2A2A2A] py-7">
        <div className="mb-4 text-sm font-semibold text-white">Confirm Dialog</div>
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="secondary">
              <ShieldCheck className="h-4 w-4" />
              打开确认弹窗样张
            </Button>
          </DialogTrigger>
          <DialogContent className="ui-lab-dialog-enter">
            <DialogHeader>
              <DialogTitle>确认下一步操作</DialogTitle>
              <DialogDescription>删除、放行、重新执行会共享同一套 Minimal Dark 弹窗层级。</DialogDescription>
            </DialogHeader>
            <div className="mt-5 grid gap-2">
              <button className="flex items-center gap-3 rounded-2xl px-3 py-3 text-left transition-colors hover:bg-[#2C2C2C]">
                <Trash2 className="h-4 w-4 text-[#C7C7C7]" />
                <span className="flex-1 text-sm text-white">删除当前草稿</span>
                <span className="text-xs text-[#8A8A8A]">低频危险态</span>
              </button>
              <button className="flex items-center gap-3 rounded-2xl px-3 py-3 text-left transition-colors hover:bg-[#2C2C2C]">
                <ShieldCheck className="h-4 w-4 text-[#C7C7C7]" />
                <span className="flex-1 text-sm text-white">放行审批结果</span>
                <span className="text-xs text-[#8A8A8A]">确认</span>
              </button>
              <button className="flex items-center gap-3 rounded-2xl px-3 py-3 text-left transition-colors hover:bg-[#2C2C2C]">
                <RotateCcw className="h-4 w-4 text-[#C7C7C7]" />
                <span className="flex-1 text-sm text-white">重新执行任务</span>
                <span className="text-xs text-[#8A8A8A]">重试</span>
              </button>
            </div>
            <div className="mt-5 flex justify-end">
              <DialogClose asChild>
                <Button>关闭</Button>
              </DialogClose>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="border-t border-[#2A2A2A] py-7">
        <div className="mb-4 text-sm font-semibold text-white">Sheet / Drawer / 侧滑面板样张</div>
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="secondary">
              <PanelRightOpen className="h-4 w-4" />
              打开运行详情抽屉
            </Button>
          </DialogTrigger>
          <DialogContent className="ui-lab-dialog-enter left-auto right-3 top-3 h-[calc(100dvh-1.5rem)] w-[min(92vw,420px)] translate-x-0 translate-y-0 overflow-hidden rounded-[24px] p-0">
            <div className="flex h-full flex-col">
              <DialogHeader className="border-b border-[#3A3A3A] p-5">
                <DialogTitle>运行详情</DialogTitle>
                <DialogDescription>用于任务详情、运行详情、审批详情的临时右侧面板。</DialogDescription>
              </DialogHeader>
              <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5 text-sm text-[#C7C7C7]">
                <div>
                  <div className="text-xs text-[#8A8A8A]">状态</div>
                  <div className="mt-1 text-white">等待人工确认</div>
                </div>
                <div>
                  <div className="text-xs text-[#8A8A8A]">摘要</div>
                  <p className="mt-1 leading-6">抽屉仅作为临时详情层，不作为固定右栏，避免破坏 ChatGPT-like 两栏主体验。</p>
                </div>
                <div className="rounded-2xl bg-[#222222] p-3 font-mono text-xs">运行记录: ui_lab_preview_001</div>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </>
  );
}
