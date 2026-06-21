import { Check, ChevronDown, FileText, FolderKanban, PencilLine, XCircle } from "lucide-react";
import { useState } from "react";

import type { PlanFlowState } from "../planFlowMock";
import { Button, Textarea } from "./ui";

type WorkbenchPlanFlowCardProps = {
  state: PlanFlowState;
  readonly?: boolean;
  compact?: boolean;
  defaultCollapsed?: boolean;
  onConfirm?: () => void;
  onReject?: () => void;
  onFeedbackChange?: (feedback: string) => void;
  onRequestChanges?: (feedback: string) => void;
  onCreateProject?: () => void;
};

const stageCopy: Record<PlanFlowState["stage"], { label: string; icon: typeof FileText }> = {
  draft: { label: "等待确认", icon: FileText },
  changes_requested: { label: "已记录修改意见", icon: PencilLine },
  rejected: { label: "已驳回", icon: XCircle },
  confirmed: { label: "已确认", icon: Check },
  created: { label: "已创建项目", icon: FolderKanban },
};

function TinyStatus({ state }: { state: PlanFlowState }) {
  const { label, icon: Icon } = stageCopy[state.stage];

  return (
    <span className="inline-flex h-6 items-center gap-1.5 rounded-full border border-[#2A2A2A] bg-[#111111] px-2.5 text-[11px] text-[#C7C7C7]">
      <Icon className="h-3.5 w-3.5 text-[#8A8A8A]" />
      {label}
    </span>
  );
}

export function WorkbenchPlanFlowCard({
  state,
  readonly = false,
  compact = false,
  defaultCollapsed = false,
  onConfirm,
  onReject,
  onFeedbackChange,
  onRequestChanges,
  onCreateProject,
}: WorkbenchPlanFlowCardProps) {
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);
  const canEditFeedback = !readonly && (state.stage === "draft" || state.stage === "changes_requested");
  const canCreateProject = !readonly && state.stage === "confirmed";

  return (
    <div
      data-testid={`ui-lab-plan-flow-${state.stage}`}
      className="w-full max-w-[880px] ui-lab-panel-enter rounded-2xl border border-[#2A2A2A] bg-[#0B0B0B] p-5 shadow-2xl shadow-black/20 md:p-6"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-[#8A8A8A]">
          AI 项目主管 / 计划流
        </div>
        <TinyStatus state={state} />
      </div>

      <div className="flex items-start gap-4">
        <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[#2A2A2A] bg-black">
          <FileText className="h-5 w-5 text-[#C7C7C7]" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-lg font-semibold tracking-normal text-white">{state.title}</div>
          <p className="mt-1.5 text-sm leading-6 text-[#C7C7C7]">{state.summary}</p>
        </div>
      </div>

      <div
        className={`overflow-hidden transition-[max-height,opacity,transform] duration-200 ease-out ${
          isCollapsed ? "max-h-0 translate-y-[-4px] opacity-0" : "max-h-[900px] translate-y-0 opacity-100"
        }`}
      >
        <div className={compact ? "mt-5 grid gap-3 md:grid-cols-3" : "mt-5 grid gap-3 md:grid-cols-3"}>
          {state.sections.map((section) => (
            <div key={section.label} className="rounded-xl border border-[#222222] bg-[#111111] px-4 py-3">
              <div className="text-xs text-[#8A8A8A]">{section.label}</div>
              <div className="mt-1.5 text-[13px] leading-5 text-[#C7C7C7]">{section.value}</div>
            </div>
          ))}
        </div>

        <div className="mt-5 rounded-xl border border-[#222222] bg-black/40 px-4 py-4">
          <div className="mb-2 text-xs text-[#8A8A8A]">最小确认路径</div>
          <ul className="grid gap-1.5 md:grid-cols-3">
            {state.milestones.map((item) => (
              <li key={item} className="flex items-start gap-2 text-[13px] leading-5 text-[#C7C7C7]">
                <span className="mt-[8px] h-1 w-1 shrink-0 rounded-full bg-[#5F5F5F]" />
                {item}
              </li>
            ))}
          </ul>
        </div>

        {state.stage === "changes_requested" || state.stage === "rejected" ? (
          <div className="mt-5 rounded-xl border border-[#2A2A2A] bg-[#111111] px-4 py-4">
            <div className="mb-1 text-xs text-[#8A8A8A]">
              {state.stage === "rejected" ? "驳回记录" : "修改意见"}
            </div>
            <p className="text-sm leading-6 text-[#C7C7C7]">
              {state.stage === "rejected" ? "当前计划暂不采用，用户可以继续在对话里重新描述目标。" : state.feedbackDraft}
            </p>
          </div>
        ) : null}

        {canEditFeedback ? (
          <div className="mt-5">
            <label className="mb-1.5 block text-xs text-[#8A8A8A]">修改意见</label>
            <Textarea
              className="min-h-24 rounded-2xl"
              value={state.feedbackDraft}
              placeholder="例如：第一版先不要做支付，把范围收敛到商品、搜索、聊天。"
              onChange={(event) => onFeedbackChange?.(event.target.value)}
            />
          </div>
        ) : null}

        {state.stage === "confirmed" ? (
          <div className="mt-5 rounded-xl border border-[#2A2A2A] bg-[#111111] px-4 py-4 text-sm leading-6 text-[#C7C7C7]">
            计划已确认。现在可以创建正式项目，并进入后续执行准备。
          </div>
        ) : null}

        {state.stage === "created" ? (
          <div className="mt-5 rounded-xl border border-[#2A2A2A] bg-[#111111] px-4 py-4 text-sm leading-6 text-[#C7C7C7]">
            已创建正式项目：<span className="text-white">{state.createdProjectName}</span>。当前只更新实验页本地状态。
          </div>
        ) : null}

        {!readonly ? (
          <div className="mt-5 flex flex-wrap items-center gap-2">
            {(state.stage === "draft" || state.stage === "changes_requested") && (
              <>
                <Button size="sm" onClick={onConfirm}>
                  <Check className="h-4 w-4" />
                  确认计划
                </Button>
                <Button size="sm" variant="secondary" onClick={() => onRequestChanges?.(state.feedbackDraft)}>
                  <PencilLine className="h-4 w-4" />
                  需要修改
                </Button>
                <Button size="sm" variant="ghost" onClick={onReject}>
                  <XCircle className="h-4 w-4" />
                  驳回
                </Button>
              </>
            )}
            {canCreateProject ? (
              <Button size="sm" onClick={onCreateProject}>
                <FolderKanban className="h-4 w-4" />
                创建正式项目
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>
      <button
        type="button"
        data-testid="ui-lab-plan-flow-gradient-toggle"
        aria-expanded={!isCollapsed}
        aria-label={isCollapsed ? "展开计划流卡片" : "收起计划流卡片"}
        className="-mx-5 -mb-5 mt-5 flex h-14 w-[calc(100%+2.5rem)] items-center justify-center bg-gradient-to-b from-transparent via-white/[0.03] to-white/[0.11] text-xs font-medium text-[#C7C7C7] transition-colors hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20 md:-mx-6 md:-mb-6 md:w-[calc(100%+3rem)]"
        onClick={() => setIsCollapsed((current) => !current)}
      >
        <span className="inline-flex items-center gap-2">
          <ChevronDown
            className="h-4 w-4 text-[#C7C7C7] transition-transform duration-200"
            style={{ transform: isCollapsed ? "rotate(0deg)" : "rotate(180deg)" }}
          />
          {isCollapsed ? "展开" : "收起"}
        </span>
      </button>
    </div>
  );
}
