import {
  ArrowRight,
  Check,
  ChevronDown,
  ClipboardCheck,
  MessageSquareText,
  PencilLine,
} from "lucide-react";
import { useState } from "react";

import {
  Button,
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  Textarea,
} from "./ui";

const clarificationQuestions = [
  {
    id: "audience",
    label: "目标用户",
    question: "第一版主要给谁使用？",
    hint: "例如：普通买家、校园卖家、内部运营。",
  },
  {
    id: "scope",
    label: "第一版范围",
    question: "第一版必须保留哪 3 个能力？",
    hint: "建议先写核心能力，不要展开后台和运营细节。",
  },
  {
    id: "repository",
    label: "代码仓库",
    question: "是否已有仓库，还是需要创建新仓库？",
    hint: "这里只记录选择，不会自动写入 Git。",
  },
];

const nextSteps = [
  ["查看正式项目", "进入项目上下文，确认范围和阶段。"],
  ["绑定或创建仓库", "只读预检，真实写入继续保持关闭。"],
  ["等待执行器接入", "后端完成后再启动真实运行。"],
] as const;

const actionItems = [
  {
    title: "确认计划范围",
    body: "计划草案等待你确认",
    what: "确认当前项目范围与第一阶段目标",
    risk: "确认后会进入正式项目创建路径",
  },
  {
    title: "成果验收",
    body: "商品发布与搜索规划等待验收",
    what: "查看成果中心的摘要、证据和版本记录",
    risk: "通过后会作为当前阶段验收结论沉淀",
  },
  {
    title: "真实执行确认",
    body: "启动前需要你确认边界",
    what: "启动执行器处理已确认的下一步任务",
    risk: "会消耗模型额度；Git 写入仍保持关闭",
  },
  {
    title: "补充仓库选择",
    body: "稍后可在工作区完成",
    what: "选择已有本地仓库或创建新仓库",
    risk: "这里只绑定工作区，不会提交、推送或发布",
  },
] as const;

export type WorkbenchClarificationQuestion = {
  id: string;
  label: string;
  question: string;
  hint: string;
  required?: boolean;
};

export function WorkbenchClarificationPanel({
  questions = clarificationQuestions,
  answers: controlledAnswers,
  onAnswerChange,
  onSubmit,
  submitDisabled,
  submitLabel = "提交澄清",
  description = "回答后再生成计划草案；这里不会创建任务，也不会启动执行器。",
}: {
  questions?: WorkbenchClarificationQuestion[];
  answers?: Record<string, string>;
  onAnswerChange?: (questionId: string, answer: string) => void;
  onSubmit?: () => void;
  submitDisabled?: boolean;
  submitLabel?: string;
  description?: string;
}) {
  const [localAnswers, setLocalAnswers] = useState<Record<string, string>>({});
  const answers = controlledAnswers ?? localAnswers;
  const answeredCount = questions.filter((item) => answers[item.id]?.trim()).length;
  const requiredReady = questions
    .filter((item) => item.required !== false)
    .every((item) => answers[item.id]?.trim());

  function handleAnswerChange(questionId: string, answer: string) {
    if (!controlledAnswers) {
      setLocalAnswers((current) => ({ ...current, [questionId]: answer }));
    }
    onAnswerChange?.(questionId, answer);
  }

  return (
    <section
      data-testid="ui-lab-clarification-panel"
      className="w-full max-w-[880px] border-y border-[#2A2A2A] py-5"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-[#8A8A8A]">
            目标澄清
          </div>
          <h3 className="mt-2 text-lg font-semibold tracking-normal text-white">先确认 3 个必要问题</h3>
          <p className="mt-1.5 text-sm leading-6 text-[#8A8A8A]">
            {description}
          </p>
        </div>
        <span className="inline-flex h-7 w-fit items-center rounded-full border border-[#2A2A2A] px-2.5 text-xs text-[#C7C7C7]">
          {answeredCount} / {questions.length}
        </span>
      </div>

      <div className="mt-5 grid gap-4">
        {questions.map((item, index) => (
          <label key={item.id} className="block">
            <div className="mb-2 flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-full border border-[#2A2A2A] text-xs text-[#C7C7C7]">
                {index + 1}
              </span>
              <span className="text-sm font-medium text-white">{item.question}</span>
              <span className="text-xs text-[#5F5F5F]">{item.label}</span>
            </div>
            <Textarea
              data-testid={`ui-lab-clarification-answer-${item.id}`}
              className="min-h-16 rounded-2xl bg-[#111111]"
              placeholder={item.hint}
              value={answers[item.id] ?? ""}
              onChange={(event) => handleAnswerChange(item.id, event.target.value)}
            />
          </label>
        ))}
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-[#1F1F1F] pt-4">
        <p className="text-xs leading-5 text-[#8A8A8A]">只保留必要澄清，复杂判断后端静默处理。</p>
        <Button
          size="sm"
          disabled={submitDisabled ?? !requiredReady}
          onClick={onSubmit}
        >
          <Check className="h-4 w-4" />
          {submitLabel}
        </Button>
      </div>
    </section>
  );
}

export function WorkbenchProjectNextStepPanel({
  defaultCollapsed = true,
}: {
  defaultCollapsed?: boolean;
}) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  return (
    <section
      data-testid="ui-lab-project-next-step-panel"
      className="w-full max-w-[880px] overflow-hidden rounded-2xl border border-[#2A2A2A] bg-[#0B0B0B]"
    >
      <button
        type="button"
        className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition-colors hover:bg-white/[0.03]"
        onClick={() => setCollapsed((current) => !current)}
        aria-expanded={!collapsed}
      >
        <span className="min-w-0">
          <span className="block text-[11px] font-medium uppercase tracking-[0.08em] text-[#8A8A8A]">
            项目已创建
          </span>
          <span className="mt-1.5 block truncate text-lg font-semibold text-white">下一步只展示必要入口</span>
        </span>
        <span className="inline-flex items-center gap-2 text-xs text-[#C7C7C7]">
          {collapsed ? "展开" : "收起"}
          <ChevronDown
            className="h-4 w-4 transition-transform duration-200"
            style={{ transform: collapsed ? "rotate(0deg)" : "rotate(180deg)" }}
          />
        </span>
      </button>

      <div
        className={`overflow-hidden transition-[max-height,opacity,transform] duration-200 ease-out ${
          collapsed ? "max-h-0 -translate-y-1 opacity-0" : "max-h-[420px] translate-y-0 opacity-100"
        }`}
      >
        <div className="border-t border-[#1F1F1F] px-5 pb-5 pt-4">
          <div className="grid gap-3 md:grid-cols-3">
            {nextSteps.map(([title, body]) => (
              <div key={title} className="border-l border-[#2A2A2A] pl-3">
                <div className="text-sm font-medium text-white">{title}</div>
                <p className="mt-1 text-xs leading-5 text-[#8A8A8A]">{body}</p>
              </div>
            ))}
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            <Button size="sm">
              查看正式项目
              <ArrowRight className="h-4 w-4" />
            </Button>
            <Button size="sm" variant="secondary">
              继续对话
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}

export function WorkbenchUserActionStrip({
  defaultCollapsed = true,
}: {
  defaultCollapsed?: boolean;
}) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  return (
    <section data-testid="ui-lab-topbar-action-inbox" className="relative w-[min(38vw,420px)] min-w-[260px]">
      <button
        type="button"
        className="flex h-10 w-full items-center justify-between gap-3 border-y border-[#2A2A2A] px-2 text-left transition-colors hover:bg-white/[0.03]"
        onClick={() => setCollapsed((current) => !current)}
        aria-expanded={!collapsed}
      >
        <span className="flex min-w-0 items-center gap-2.5">
          <ClipboardCheck className="h-4 w-4 shrink-0 text-[#C7C7C7]" />
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold text-white">需要你处理 4 项</span>
            <span className="mt-0.5 hidden truncate text-xs text-[#8A8A8A] xl:block">影响项目推进</span>
          </span>
        </span>
        <span className="inline-flex shrink-0 items-center gap-2 text-xs text-[#C7C7C7]">
          {collapsed ? "展开" : "收起"}
          <ChevronDown
            className="h-4 w-4 transition-transform duration-200"
            style={{ transform: collapsed ? "rotate(0deg)" : "rotate(180deg)" }}
          />
        </span>
      </button>

      <div
        className={`ui-lab-popover-enter absolute right-0 top-[calc(100%+12px)] z-50 w-[min(520px,calc(100vw-48px))] overflow-hidden border border-[#2A2A2A] bg-[#050505] shadow-[0_24px_80px_rgba(0,0,0,0.72)] transition-[opacity,transform] duration-200 ease-out ${
          collapsed ? "pointer-events-none -translate-y-2 opacity-0" : "translate-y-0 opacity-100"
        }`}
      >
        <div className="flex items-start justify-between gap-4 border-b border-[#1F1F1F] px-4 py-3">
          <div>
            <div className="text-sm font-semibold text-white">需要你处理 4 项</div>
            <div className="mt-1 text-xs text-[#8A8A8A]">只显示会影响项目推进的确认事项</div>
          </div>
          <button
            type="button"
            className="rounded-full px-2 py-1 text-xs text-[#8A8A8A] transition-colors hover:bg-[#1F1F1F] hover:text-white"
            onClick={() => setCollapsed(true)}
          >
            收起
          </button>
        </div>
        <div className="grid gap-1 px-4 py-3">
          {actionItems.map((item) => (
            <div key={item.title} className="border-b border-[#111111] py-3 last:border-b-0">
              <div className="flex items-start justify-between gap-4">
                <span className="min-w-0">
                  <span className="block text-sm font-medium text-[#D7D7D7]">{item.title}</span>
                  <span className="mt-0.5 block text-xs text-[#8A8A8A]">{item.body}</span>
                </span>
                <Dialog>
                  <DialogTrigger asChild>
                    <Button size="sm" variant="ghost" className="h-7 shrink-0 px-2.5">
                      <PencilLine className="h-3.5 w-3.5" />
                      处理
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="ui-lab-dialog-enter w-[min(92vw,460px)]">
                    <DialogHeader>
                      <DialogTitle>{item.title}</DialogTitle>
                      <DialogDescription>{item.body}</DialogDescription>
                    </DialogHeader>
                    <div className="mt-5 border-y border-[#2A2A2A] py-4 text-sm leading-6">
                      <div className="text-[#C7C7C7]">会做什么</div>
                      <div className="mt-1 text-[#8A8A8A]">{item.what}</div>
                      <div className="mt-4 text-[#C7C7C7]">风险</div>
                      <div className="mt-1 text-[#8A8A8A]">{item.risk}</div>
                    </div>
                    <div className="mt-5 flex justify-end gap-3">
                      <DialogClose asChild>
                        <Button variant="secondary">拒绝</Button>
                      </DialogClose>
                      <DialogClose asChild>
                        <Button>通过</Button>
                      </DialogClose>
                    </div>
                  </DialogContent>
                </Dialog>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function WorkbenchUserDecisionSurfacePreview() {
  return (
    <div className="grid gap-5">
      <WorkbenchUserActionStrip />
      <WorkbenchClarificationPanel />
      <WorkbenchProjectNextStepPanel />
      <div className="rounded-2xl border border-[#2A2A2A] bg-[#0B0B0B] p-5">
        <div className="flex items-start gap-3">
          <MessageSquareText className="mt-0.5 h-5 w-5 text-[#C7C7C7]" />
          <p className="text-sm leading-6 text-[#8A8A8A]">
            验收、放行、执行确认都收进顶部“需要你处理”，不再单独增加确认弹窗。
          </p>
        </div>
      </div>
    </div>
  );
}
