import {
  ArrowUp,
  Briefcase,
  Check,
  ChevronRight,
  Clock3,
  FileText,
  FolderOpen,
} from "lucide-react";
import { useState } from "react";
import type * as React from "react";

import { mainPageMockContents, type MainPageContent } from "../mockInteractions";

const projectScopeRows = [
  ["项目目标", "构建营销数据分析平台，支持多维度洞察与增长决策"],
  ["当前边界", "聚焦接入、指标体系、可视化分析、报表导出"],
  ["关键约束", "数据合规、敏捷交付、上线时间"],
  ["交付标准", "功能可用、性能达标、文档完整、验收通过"],
] as const;

const projectPlanSteps = [
  { label: "目标澄清", status: "已完成", state: "done" },
  { label: "任务拆分", status: "进行中", state: "current" },
  { label: "执行规划", status: "待开始", state: "pending" },
  { label: "交付验收", status: "待开始", state: "pending" },
] as const;

const projectContextRows = [
  ["最近任务", "拆分数据接入模块任务", "32 分钟前"],
  ["最近操作", "数据源连通性测试", "1 小时前"],
  ["仓库绑定", "dev/marketing-analytics", "已绑定"],
  ["审批 / 交付物", "待审批 1 项 / 交付物 0 项", "待处理"],
] as const;

function ProjectSectionTitle({
  icon: Icon,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2 text-base font-semibold text-white">
      <Icon className="h-[18px] w-[18px] text-[#C7C7C7]" />
      <span>{children}</span>
    </div>
  );
}

function ProjectManagementMockPage() {
  const [discussion, setDiscussion] = useState("");
  const hasDiscussion = discussion.trim().length > 0;

  return (
    <div className="ui-lab-project-page min-h-0 flex-1 overflow-y-auto px-6 py-8 md:px-10">
      <div className="mx-auto flex w-full max-w-[980px] flex-col">
        <section className="pt-1">
          <h1 className="text-2xl font-semibold tracking-normal text-white">营销活动分析平台</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-[#C7C7C7]">
            构建统一的营销数据分析平台，整合多渠道数据，提供可视化洞察与增长决策支持。
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-[#C7C7C7]">
            <span className="inline-flex h-7 items-center gap-1.5 rounded-full border border-[#2A2A2A] bg-[#171717] px-3 text-xs text-white">
              <span className="h-1.5 w-1.5 rounded-full bg-[#C7C7C7]" />
              进行中
            </span>
            <span className="hidden h-5 w-px bg-[#2A2A2A] sm:block" />
            <span>当前阶段：任务拆分</span>
            <span className="hidden h-5 w-px bg-[#2A2A2A] sm:block" />
            <span>最后更新：2025-05-22 14:32</span>
          </div>
        </section>

        <section className="mt-6 rounded-lg border border-[#2A2A2A] bg-[#171717]/80 px-5 py-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <FileText className="h-4 w-4 text-[#C7C7C7]" />
            <span>摘要</span>
          </div>
          <div className="mt-4 space-y-2 text-sm leading-6 text-[#C7C7C7]">
            <p>项目整体进度顺利，已完成目标澄清并梳理核心需求，正在进行任务拆分与优先级排序。</p>
            <p>建议聚焦数据接入与指标体系搭建的核心路径，优先完成关键链路以尽早验证价值。</p>
          </div>
        </section>

        <section className="mt-6">
          <ProjectSectionTitle icon={FolderOpen}>项目范围</ProjectSectionTitle>
          <div className="mt-3 border-y border-[#2A2A2A]">
            {projectScopeRows.map(([label, value]) => (
              <div
                key={label}
                className="grid gap-2 border-b border-[#1F1F1F] px-3 py-2.5 text-sm last:border-b-0 md:grid-cols-[180px_1fr]"
              >
                <div className="text-[#8A8A8A]">{label}</div>
                <div className="text-[#C7C7C7]">{value}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-6">
          <ProjectSectionTitle icon={Clock3}>阶段计划</ProjectSectionTitle>
          <div className="mt-5 grid grid-cols-4 items-start">
            {projectPlanSteps.map((step, index) => (
              <div key={step.label} className="relative flex min-w-0 flex-col items-center text-center">
                {index > 0 ? (
                  <span className="absolute left-0 top-3 h-px w-1/2 bg-[#3A3A3A]" />
                ) : null}
                {index < projectPlanSteps.length - 1 ? (
                  <span className="absolute right-0 top-3 h-px w-1/2 bg-[#3A3A3A]" />
                ) : null}
                <span
                  className={[
                    "relative z-10 flex h-7 w-7 items-center justify-center rounded-full border text-xs font-semibold",
                    step.state === "done"
                      ? "border-[#3A3A3A] bg-[#2C2C2C] text-white"
                      : step.state === "current"
                        ? "border-white bg-black text-white"
                        : "border-[#2A2A2A] bg-[#171717] text-[#8A8A8A]",
                  ].join(" ")}
                >
                  {step.state === "done" ? <Check className="h-4 w-4" /> : index + 1}
                </span>
                <div className="mt-3 w-full px-1 text-sm font-medium text-[#C7C7C7]">{step.label}</div>
                <div className="mt-1 text-xs text-[#8A8A8A]">{step.status}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-6">
          <ProjectSectionTitle icon={Briefcase}>当前上下文</ProjectSectionTitle>
          <div className="mt-3 border-y border-[#2A2A2A]">
            {projectContextRows.map(([label, value, meta]) => (
              <button
                key={label}
                className="grid w-full items-center gap-2 border-b border-[#1F1F1F] px-3 py-2.5 text-left text-sm transition-colors last:border-b-0 hover:bg-[#111111] md:grid-cols-[170px_1fr_112px_16px]"
              >
                <span className="text-[#8A8A8A]">{label}</span>
                <span className="min-w-0 truncate text-[#C7C7C7]">{value}</span>
                <span className="text-left text-[#8A8A8A] md:text-right">{meta}</span>
                <ChevronRight className="hidden h-4 w-4 text-[#5F5F5F] md:block" />
              </button>
            ))}
          </div>
        </section>

        <div className="mt-4 flex h-11 items-center gap-2 rounded-[18px] border border-[#2A2A2A] bg-[#171717] px-4">
          <input
            className="min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-[#8A8A8A]"
            placeholder="讨论审批或需要改进的地方..."
            value={discussion}
            onChange={(event) => setDiscussion(event.target.value)}
          />
          <button
            className={[
              "flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-colors active:scale-[0.96]",
              hasDiscussion ? "bg-white text-black hover:bg-[#E7E7E7]" : "bg-[#2C2C2C] text-[#8A8A8A]",
            ].join(" ")}
            disabled={!hasDiscussion}
            aria-label="发送讨论"
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

export function MockPageContent({ pageKey }: { pageKey: string }) {
  if (pageKey === "projects") {
    return <ProjectManagementMockPage />;
  }

  const content: MainPageContent | undefined = mainPageMockContents[pageKey];

  if (!content) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-[#8A8A8A]">
        页面未找到
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col px-6 py-8 md:px-10 md:py-12">
      <h2 className="text-2xl font-semibold tracking-normal text-white">{content.title}</h2>
      <p className="mt-2 text-sm font-medium text-[#C7C7C7]">{content.subtitle}</p>
      <p className="mt-3 max-w-lg text-sm leading-6 text-[#8A8A8A]">{content.description}</p>

      <div className="mt-8 space-y-1 max-w-md">
        {content.items.map((item) => (
          <button
            key={item.label}
            className="flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left transition-colors hover:bg-[#222222] active:scale-[0.98]"
          >
            <span className="min-w-0 flex-1 text-sm font-medium text-white">{item.label}</span>
            <span className="text-xs text-[#8A8A8A]">{item.description}</span>
            <ChevronRight className="h-4 w-4 shrink-0 text-[#5F5F5F]" />
          </button>
        ))}
      </div>
    </div>
  );
}
