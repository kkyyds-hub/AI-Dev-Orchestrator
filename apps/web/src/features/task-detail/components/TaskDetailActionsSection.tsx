import { StatusBadge } from "../../../components/StatusBadge";
import { mapTaskStatusTone } from "../../../lib/status";
import type { ConsoleBudget } from "../../console/types";
import { DetailField, type TaskDetailSurfaceVariant } from "./TaskDetailField";

type TaskActionResult = {
  message: string;
  previous_status: string;
  current_status: string;
};

export function TaskDetailActionsSection(props: {
  taskId: string;
  status: string;
  budget: ConsoleBudget | null;
  canPause: boolean;
  canResume: boolean;
  canRequestHuman: boolean;
  canResolveHuman: boolean;
  canRetry: boolean;
  canTriggerRetry: boolean;
  isActionPending: boolean;
  executionAttempts: number;
  retriesUsed: number;
  retriesRemaining: number;
  retryLimitReached: boolean;
  isPausePending: boolean;
  isResumePending: boolean;
  isRequestHumanPending: boolean;
  isResolveHumanPending: boolean;
  isRetryPending: boolean;
  pauseResult: TaskActionResult | null;
  resumeResult: TaskActionResult | null;
  requestHumanResult: TaskActionResult | null;
  resolveHumanResult: TaskActionResult | null;
  retryResult: TaskActionResult | null;
  pauseError: string | null;
  resumeError: string | null;
  requestHumanError: string | null;
  resolveHumanError: string | null;
  retryError: string | null;
  surfaceVariant?: TaskDetailSurfaceVariant;
  onPause: (taskId: string) => void;
  onResume: (taskId: string) => void;
  onRequestHuman: (taskId: string) => void;
  onResolveHuman: (taskId: string) => void;
  onRetry: (taskId: string) => void;
}) {
  const isLine = props.surfaceVariant === "line";

  return (
    <section
      className={
        isLine
          ? "border-b border-[#333333] pb-5"
          : "rounded-xl border border-slate-800 bg-slate-950/60 p-4"
      }
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h3 className={`text-base font-semibold ${isLine ? "text-zinc-100" : "text-slate-50"}`}>任务操作</h3>
          <p className={`mt-1 text-sm leading-6 ${isLine ? "text-zinc-500" : "text-slate-400"}`}>
            支持显式暂停、人工介入和失败重试；所有动作都只更新当前任务状态，不复制任务记录。
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <ActionButton
            label="暂停任务"
            pendingLabel="暂停中..."
            tone="amber"
            surfaceVariant={props.surfaceVariant}
            disabled={!props.canPause || props.isActionPending}
            isPending={props.isPausePending}
            onClick={() => props.onPause(props.taskId)}
          />
          <ActionButton
            label="恢复任务"
            pendingLabel="恢复中..."
            tone="emerald"
            surfaceVariant={props.surfaceVariant}
            disabled={!props.canResume || props.isActionPending}
            isPending={props.isResumePending}
            onClick={() => props.onResume(props.taskId)}
          />
          <ActionButton
            label="请求人工"
            pendingLabel="提交中..."
            tone="violet"
            surfaceVariant={props.surfaceVariant}
            disabled={!props.canRequestHuman || props.isActionPending}
            isPending={props.isRequestHumanPending}
            onClick={() => props.onRequestHuman(props.taskId)}
          />
          <ActionButton
            label="人工已处理"
            pendingLabel="恢复中..."
            tone="emerald"
            surfaceVariant={props.surfaceVariant}
            disabled={!props.canResolveHuman || props.isActionPending}
            isPending={props.isResolveHumanPending}
            onClick={() => props.onResolveHuman(props.taskId)}
          />
          <ActionButton
            label="重试任务"
            pendingLabel="重试中..."
            tone="cyan"
            surfaceVariant={props.surfaceVariant}
            disabled={!props.canTriggerRetry || props.isActionPending}
            isPending={props.isRetryPending}
            onClick={() => props.onRetry(props.taskId)}
          />
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <DetailField
          surfaceVariant={props.surfaceVariant}
          label="当前状态"
          value={<StatusBadge label={props.status} tone={mapTaskStatusTone(props.status)} />}
        />
        <DetailField
          surfaceVariant={props.surfaceVariant}
          label="重试资格"
          value={
            props.retryLimitReached
              ? "已达到重试上限"
              : props.canRetry
                ? "允许"
                : "仅 failed / blocked 可重试"
          }
        />
        <DetailField surfaceVariant={props.surfaceVariant} label="已执行次数" value={String(props.executionAttempts)} />
        <DetailField
          surfaceVariant={props.surfaceVariant}
          label="已用重试 / 上限"
          value={
            props.budget
              ? `${props.retriesUsed} / ${props.budget.max_task_retries}`
              : "预算未加载"
          }
        />
        <DetailField
          surfaceVariant={props.surfaceVariant}
          label="剩余重试"
          value={props.budget ? String(props.retriesRemaining) : "预算未加载"}
        />
        <DetailField surfaceVariant={props.surfaceVariant} label="预算状态" value={formatBudgetHealthLabel(props.budget)} />
      </div>

      {props.retryLimitReached ? (
        <div className={isLine ? "mt-4 border-l border-amber-700/70 pl-4 text-sm leading-6 text-amber-200" : "mt-4 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-100"}>
          当前任务已达到 Day 15 重试上限。若要继续尝试，请先提高 `MAX_TASK_RETRIES`
          或人工处理任务输入后再重试。
        </div>
      ) : null}

      {props.pauseResult ? (
        <StateActionNotice
          title="暂停已生效"
          surfaceVariant={props.surfaceVariant}
          message={props.pauseResult.message}
          previousStatus={props.pauseResult.previous_status}
          currentStatus={props.pauseResult.current_status}
        />
      ) : null}

      {props.resumeResult ? (
        <StateActionNotice
          title="任务已恢复"
          surfaceVariant={props.surfaceVariant}
          message={props.resumeResult.message}
          previousStatus={props.resumeResult.previous_status}
          currentStatus={props.resumeResult.current_status}
        />
      ) : null}

      {props.requestHumanResult ? (
        <StateActionNotice
          title="已请求人工处理"
          surfaceVariant={props.surfaceVariant}
          message={props.requestHumanResult.message}
          previousStatus={props.requestHumanResult.previous_status}
          currentStatus={props.requestHumanResult.current_status}
        />
      ) : null}

      {props.resolveHumanResult ? (
        <StateActionNotice
          title="人工处理已完成"
          surfaceVariant={props.surfaceVariant}
          message={props.resolveHumanResult.message}
          previousStatus={props.resolveHumanResult.previous_status}
          currentStatus={props.resolveHumanResult.current_status}
        />
      ) : null}

      {props.retryResult ? (
        <StateActionNotice
          title="重试已触发"
          surfaceVariant={props.surfaceVariant}
          message={props.retryResult.message}
          previousStatus={props.retryResult.previous_status}
          currentStatus={props.retryResult.current_status}
        />
      ) : null}

      {props.pauseError ? <ActionError title="暂停失败" message={props.pauseError} surfaceVariant={props.surfaceVariant} /> : null}

      {props.resumeError ? <ActionError title="恢复失败" message={props.resumeError} surfaceVariant={props.surfaceVariant} /> : null}

      {props.requestHumanError ? (
        <ActionError title="请求人工失败" message={props.requestHumanError} surfaceVariant={props.surfaceVariant} />
      ) : null}

      {props.resolveHumanError ? (
        <ActionError title="恢复人工任务失败" message={props.resolveHumanError} surfaceVariant={props.surfaceVariant} />
      ) : null}

      {props.retryError ? <ActionError title="重试失败" message={props.retryError} surfaceVariant={props.surfaceVariant} /> : null}
    </section>
  );
}

function ActionButton(props: {
  label: string;
  pendingLabel: string;
  onClick: () => void;
  disabled: boolean;
  isPending: boolean;
  tone: "cyan" | "amber" | "violet" | "emerald";
  surfaceVariant?: TaskDetailSurfaceVariant;
}) {
  const isLine = props.surfaceVariant === "line";
  const toneClassName = isLine
    ? "border-[#333333] bg-transparent text-zinc-200 hover:border-zinc-500 hover:bg-[#2f2f2f] hover:text-zinc-50"
    : {
        cyan: "border-cyan-400/30 bg-cyan-500/10 text-cyan-200 hover:bg-cyan-500/20",
        amber:
          "border-amber-400/30 bg-amber-500/10 text-amber-200 hover:bg-amber-500/20",
        violet:
          "border-violet-400/30 bg-violet-500/10 text-violet-200 hover:bg-violet-500/20",
        emerald:
          "border-emerald-400/30 bg-emerald-500/10 text-emerald-200 hover:bg-emerald-500/20",
      }[props.tone];

  return (
    <button
      type="button"
      onClick={props.onClick}
      disabled={props.disabled}
      className={`rounded-md border px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:border-[#333333] disabled:bg-transparent disabled:text-zinc-700 ${toneClassName}`}
    >
      {props.isPending ? props.pendingLabel : props.label}
    </button>
  );
}

function StateActionNotice(props: {
  title: string;
  message: string;
  previousStatus: string;
  currentStatus: string;
  surfaceVariant?: TaskDetailSurfaceVariant;
}) {
  const isLine = props.surfaceVariant === "line";

  return (
    <div className={isLine ? "mt-4 border-l border-emerald-700/70 pl-4 text-sm leading-6 text-emerald-200" : "mt-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-100"}>
      <div className={`font-medium ${isLine ? "text-emerald-100" : "text-emerald-50"}`}>{props.title}</div>
      <p className="mt-1">
        {props.message} 状态已从 `{props.previousStatus}` 更新为 `{props.currentStatus}`。
      </p>
    </div>
  );
}

function ActionError(props: {
  title: string;
  message: string;
  surfaceVariant?: TaskDetailSurfaceVariant;
}) {
  const isLine = props.surfaceVariant === "line";

  return (
    <div className={isLine ? "mt-4 border-l border-rose-700/70 pl-4 text-sm leading-6 text-rose-200" : "mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-100"}>
      {props.title}：{props.message}
    </div>
  );
}

function formatBudgetHealthLabel(budget: ConsoleBudget | null): string {
  if (!budget) {
    return "预算未加载";
  }

  if (budget.daily_budget_exceeded && budget.session_budget_exceeded) {
    return "日预算 / 会话预算均告警";
  }

  if (budget.daily_budget_exceeded) {
    return "日预算告警";
  }

  if (budget.session_budget_exceeded) {
    return "会话预算告警";
  }

  return "预算正常";
}
