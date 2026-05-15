import { useState } from "react";

import { StatusBadge } from "../../../components/StatusBadge";
import { formatCurrencyUsd, formatDateTime, formatTokenCount } from "../../../lib/format";
import {
  mapFailureCategoryTone,
  mapQualityGateTone,
  mapRunStatusTone,
} from "../../../lib/status";
import type { ConsoleRun } from "../../console/types";
import { type TaskDetailSurfaceVariant } from "./TaskDetailField";

export function TaskDetailLatestRunCard(props: {
  latestRun: ConsoleRun | null;
  selectedRun: ConsoleRun | null;
  surfaceVariant?: TaskDetailSurfaceVariant;
  onSelectRun: (runId: string) => void;
  onNavigateToLogs?: (runId: string) => void;
}) {
  return (
    <RunCard
      title="最新运行"
      run={props.latestRun}
      isSelected={props.latestRun?.id === props.selectedRun?.id}
      surfaceVariant={props.surfaceVariant}
      onViewLog={(run) => (props.onNavigateToLogs ?? props.onSelectRun)(run.id)}
    />
  );
}

export function TaskDetailRunHistorySection(props: {
  taskId: string;
  runs: ConsoleRun[];
  selectedRun: ConsoleRun | null;
  surfaceVariant?: TaskDetailSurfaceVariant;
  onSelectRun: (runId: string) => void;
  onNavigateToRun?: (runId: string, taskId: string) => void;
  onNavigateToLogs?: (runId: string) => void;
}) {
  const isLine = props.surfaceVariant === "line";

  return (
    <section
      className={
        isLine
          ? "border-b border-[#333333] pb-5"
          : "border-b border-[#333333] pb-5"
      }
    >
      {/* Current selected run detail */}
      {props.selectedRun ? (
        <SelectedRunDetail
          run={props.selectedRun}
          taskId={props.taskId}
          surfaceVariant={props.surfaceVariant}
          onNavigateToRun={props.onNavigateToRun}
          onNavigateToLogs={props.onNavigateToLogs}
        />
      ) : (
        <div className="border border-dashed border-[#3a3a3a] px-4 py-4 text-sm leading-6 text-zinc-400">
          先选择一条运行记录查看详情。
        </div>
      )}

      {/* Run history list */}
      <div className="mt-5">
        <div className="flex items-center justify-between gap-4">
          <h3 className="text-base font-semibold text-zinc-100">运行历史</h3>
          <span className="text-xs text-zinc-600">共 {props.runs.length} 条</span>
        </div>

        {props.runs.length ? (
          <div className="mt-3 max-h-[22rem] divide-y divide-[#333333] overflow-y-auto border-y border-[#333333]">
            {props.runs.map((run, index) => {
              const isSelected = run.id === props.selectedRun?.id;

              return (
                <div
                  key={run.id}
                  className={`px-3 py-3 ${
                    isSelected ? "bg-[#2b2b2b]" : "bg-transparent"
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-medium text-zinc-100">
                        运行 #{props.runs.length - index}
                      </span>
                      <StatusBadge label={run.status} tone={mapRunStatusTone(run.status)} />
                      <span className="text-xs text-zinc-500">
                        {formatDateTime(run.created_at)}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 text-xs text-zinc-500">
                      <span>
                        {formatTokenCount(run.prompt_tokens)} / {formatTokenCount(run.completion_tokens)}
                      </span>
                      <span>{formatCurrencyUsd(run.estimated_cost)}</span>
                      <button
                        type="button"
                        onClick={() => (props.onNavigateToLogs ?? props.onSelectRun)(run.id)}
                        className="rounded border border-[#333333] px-2 py-1 text-xs text-zinc-200 transition hover:border-zinc-500 hover:bg-[#2f2f2f]"
                      >
                        日志
                      </button>
                      {props.onNavigateToRun ? (
                        <button
                          type="button"
                          onClick={() => props.onNavigateToRun?.(run.id, props.taskId)}
                          className="rounded border border-[#333333] px-2 py-1 text-xs text-zinc-200 transition hover:border-zinc-500 hover:bg-[#2f2f2f]"
                        >
                          打开
                        </button>
                      ) : null}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="mt-3 border border-dashed border-[#3a3a3a] px-4 py-6 text-sm leading-6 text-zinc-400">
            这条任务还没有运行历史。你可以先在工作台手动执行一次任务。
          </div>
        )}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Selected run detail (only shown for the currently selected run)   */
/* ------------------------------------------------------------------ */

function SelectedRunDetail(props: {
  run: ConsoleRun;
  taskId: string;
  surfaceVariant?: TaskDetailSurfaceVariant;
  onNavigateToRun?: (runId: string, taskId: string) => void;
  onNavigateToLogs?: (runId: string) => void;
}) {
  const { run } = props;

  return (
    <section className="border-b border-[#333333] pb-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-zinc-100">当前选中运行</h3>
          <p className="mt-1 text-xs text-zinc-500">
            创建于 {formatDateTime(run.created_at)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge label={run.status} tone={mapRunStatusTone(run.status)} />
          {props.onNavigateToLogs ? (
            <button
              type="button"
              onClick={() => props.onNavigateToLogs?.(run.id)}
              className="rounded border border-[#333333] px-3 py-1.5 text-xs text-zinc-200 transition hover:border-zinc-500 hover:bg-[#2f2f2f]"
            >
              查看日志
            </button>
          ) : null}
          {props.onNavigateToRun ? (
            <button
              type="button"
              onClick={() => props.onNavigateToRun?.(run.id, props.taskId)}
              className="rounded border border-[#333333] px-3 py-1.5 text-xs text-zinc-200 transition hover:border-zinc-500 hover:bg-[#2f2f2f]"
            >
              打开运行中心
            </button>
          ) : null}
        </div>
      </div>

      {/* Compact summary fields */}
      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MiniField label="开始时间" value={formatDateTime(run.started_at)} />
        <MiniField label="结束时间" value={formatDateTime(run.finished_at)} />
        <MiniField
          label="令牌用量"
          value={`${formatTokenCount(run.prompt_tokens)} / ${formatTokenCount(run.completion_tokens)}`}
        />
        <MiniField label="估算成本" value={formatCurrencyUsd(run.estimated_cost)} />
        <MiniField
          label="质量闸门"
          value={formatQualityGateLabel(run.quality_gate_passed)}
          tone={mapQualityGateTone(run.quality_gate_passed)}
        />
        <MiniField
          label="失败分类"
          value={run.failure_category ?? "无"}
          tone={run.failure_category ? mapFailureCategoryTone(run.failure_category) : undefined}
        />
      </div>

      {/* Collapsible: route reason */}
      <CollapsibleSection summary="展开分配明细" className="mt-3">
        <div className="space-y-2 text-sm">
          <div>
            <div className="text-xs uppercase tracking-[0.18em] text-zinc-500">分配摘要</div>
            {run.route_reason ? (
              <p className="mt-1 leading-6 text-zinc-400 line-clamp-3">{run.route_reason}</p>
            ) : (
              <p className="mt-1 leading-6 text-zinc-500">暂无分配说明</p>
            )}
          </div>
        </div>
      </CollapsibleSection>

      {/* Collapsible: routing score breakdown */}
      {run.routing_score !== null ? (
        <CollapsibleSection summary="展开评分明细" className="mt-2">
          <div className="space-y-1 text-sm">
            <p className="text-xs text-zinc-400">
              分配评分：<span className="font-medium text-zinc-200">{run.routing_score}</span>
            </p>
            {run.routing_score_breakdown.length > 0 ? (
              <div className="mt-2 space-y-2">
                {run.routing_score_breakdown.map((item, index) => (
                  <div
                    key={`${run.id}-route-score-${item.code}-${index}`}
                    className="border-l border-[#333333] px-3 py-2"
                  >
                    <div className="flex items-center justify-between gap-3 text-xs">
                      <span className="font-medium text-zinc-100">
                        {item.label}
                        <span className="ml-2 text-zinc-500">({item.code})</span>
                      </span>
                      <span className={item.score >= 0 ? "text-emerald-300" : "text-amber-300"}>
                        {item.score >= 0 ? "+" : ""}
                        {item.score.toFixed(1)}
                      </span>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-zinc-400">{item.detail}</p>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </CollapsibleSection>
      ) : null}

      {/* Collapsible: verification details */}
      <CollapsibleSection summary="展开验证详情" className="mt-2">
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <MiniField label="验证模式" value={run.verification_mode ?? "未记录"} />
            <MiniField label="验证模板" value={run.verification_template ?? "未使用内置模板"} />
          </div>
          {run.verification_command ? (
            <div>
              <div className="mb-1 text-xs uppercase tracking-[0.18em] text-zinc-500">验证入口</div>
              <code className="block break-all text-xs text-zinc-400 border border-[#333333] px-3 py-2">
                {run.verification_command}
              </code>
            </div>
          ) : null}
          <div>
            <div className="mb-1 text-xs uppercase tracking-[0.18em] text-zinc-500">验证摘要</div>
            <p className="text-sm leading-6 text-zinc-400">
              {run.verification_summary ?? "暂无验证摘要"}
            </p>
          </div>
        </div>
      </CollapsibleSection>

      {/* Run summary - always shown */}
      {run.result_summary ? (
        <div className="mt-3 border-l border-[#333333] px-3 py-2">
          <div className="text-xs uppercase tracking-[0.18em] text-zinc-500">运行摘要</div>
          <p className="mt-1 text-sm leading-6 text-zinc-400">{run.result_summary}</p>
        </div>
      ) : null}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Latest run compact card (no narrative / verification expanded)    */
/* ------------------------------------------------------------------ */

function RunCard(props: {
  title: string;
  run: ConsoleRun | null;
  isSelected: boolean;
  surfaceVariant?: TaskDetailSurfaceVariant;
  onViewLog: (run: ConsoleRun) => void;
}) {
  if (!props.run) {
    return (
      <section className="border-b border-[#333333] pb-5">
        <h3 className="text-base font-semibold text-zinc-100">{props.title}</h3>
        <p className="mt-3 text-sm text-zinc-500">这条任务还没有最新运行记录。</p>
      </section>
    );
  }

  const run = props.run;

  return (
    <section className="border-b border-[#333333] pb-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-zinc-100">{props.title}</h3>
          <p className="mt-1 text-xs text-zinc-600">创建于 {formatDateTime(run.created_at)}</p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge label={run.status} tone={mapRunStatusTone(run.status)} />
          <button
            type="button"
            onClick={() => props.onViewLog(run)}
            className="rounded border border-[#333333] px-3 py-1.5 text-xs text-zinc-200 transition hover:border-zinc-500 hover:bg-[#2f2f2f]"
          >
            {props.isSelected ? "日志中" : "查看日志"}
          </button>
        </div>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MiniField label="令牌用量" value={`${formatTokenCount(run.prompt_tokens)} / ${formatTokenCount(run.completion_tokens)}`} />
        <MiniField label="估算成本" value={formatCurrencyUsd(run.estimated_cost)} />
        <MiniField label="开始时间" value={formatDateTime(run.started_at)} />
        <MiniField label="结束时间" value={formatDateTime(run.finished_at)} />
        <MiniField
          label="质量闸门"
          value={formatQualityGateLabel(run.quality_gate_passed)}
          tone={mapQualityGateTone(run.quality_gate_passed)}
        />
        <MiniField
          label="失败分类"
          value={run.failure_category ?? "无"}
          tone={run.failure_category ? mapFailureCategoryTone(run.failure_category) : undefined}
        />
      </div>

      {run.routing_score !== null ? (
        <p className="mt-2 text-xs text-zinc-500">
          分配评分：{run.routing_score}
        </p>
      ) : null}

      {run.result_summary ? (
        <p className="mt-2 text-sm leading-6 text-zinc-400 line-clamp-2">
          {run.result_summary}
        </p>
      ) : null}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

function CollapsibleSection(props: {
  summary: string;
  children: React.ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className={props.className}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex items-center gap-1 text-xs text-zinc-500 transition hover:text-zinc-200"
      >
        <span className={`transition ${open ? "rotate-90" : ""}`}>›</span>
        {props.summary}
      </button>
      {open ? <div className="mt-3">{props.children}</div> : null}
    </div>
  );
}

function MiniField(props: {
  label: string;
  value: string;
  tone?: "success" | "danger" | "warning" | "neutral" | "info";
}) {
  return (
    <div className="border-l border-[#333333] px-3 py-2">
      <div className="text-xs uppercase tracking-[0.18em] text-zinc-500">{props.label}</div>
      <div className="mt-1 text-sm font-medium text-zinc-100">{props.value}</div>
    </div>
  );
}

function formatQualityGateLabel(qualityGatePassed: boolean | null): string {
  if (qualityGatePassed === true) return "质量闸门放行";
  if (qualityGatePassed === false) return "质量闸门拦截";
  return "闸门未知";
}
