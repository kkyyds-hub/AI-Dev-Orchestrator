import { useState } from "react";

import { StatusBadge } from "../../../components/StatusBadge";
import { formatCurrencyUsd, formatDateTime, formatTokenCount } from "../../../lib/format";
import {
  mapQualityGateTone,
  mapRunStatusTone,
} from "../../../lib/status";
import type { ConsoleRun } from "../../console/types";
import { type TaskDetailSurfaceVariant } from "./TaskDetailField";

type RuntimeField = {
  key: string;
  label: string;
  value: string;
};

export function TaskDetailRuntimeContractSection(props: {
  taskId: string;
  selectedRun: ConsoleRun | null;
  runtimeFields: RuntimeField[];
  roleModelPolicyFields: RuntimeField[];
  hasRoleModelPolicyData: boolean;
  surfaceVariant?: TaskDetailSurfaceVariant;
  hideHeaderAndActions?: boolean;
  onNavigateToRun?: (runId: string, taskId: string) => void;
  onNavigateToStrategyPreview?: (input: {
    taskId: string;
    runId?: string | null;
  }) => void;
}) {
  const { selectedRun } = props;
  const isLine = props.surfaceVariant === "line";

  if (!selectedRun) {
    return null;
  }

  const runtimeMap = new Map(props.runtimeFields.map((f) => [f.key, f]));

  const provider = runtimeMap.get("provider_key")?.value;
  const promptTemplate = runtimeMap.get("prompt_template_key")?.value;
  const pricingSource = runtimeMap.get("token_pricing_source")?.value;
  const providerReceipt = runtimeMap.get("provider_receipt_id")?.value;
  const failureCategory = selectedRun.failure_category;

  return (
    <div
      data-testid="task-detail-runtime-context"
      className={isLine ? "space-y-4" : "space-y-4"}
    >
      {!props.hideHeaderAndActions ? (
        <>
          {/* ── Summary header ── */}
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[#333333] pb-4">
            <div>
              <h3 className="text-base font-semibold text-zinc-100">运行约束详情</h3>
              <p className="mt-1 text-xs text-zinc-500">
                任务 {props.taskId} · 运行 {selectedRun.id}
              </p>
              {selectedRun.result_summary ? (
                <p className="mt-2 line-clamp-2 text-sm leading-6 text-zinc-400">
                  {selectedRun.result_summary}
                </p>
              ) : null}
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge label={selectedRun.status} tone={mapRunStatusTone(selectedRun.status)} />
              <StatusBadge
                label={formatQualityGateLabel(selectedRun.quality_gate_passed)}
                tone={mapQualityGateTone(selectedRun.quality_gate_passed)}
              />
            </div>
          </div>

          {/* ── Action bar ── */}
          <div className="flex flex-wrap gap-2">
            {props.onNavigateToStrategyPreview ? (
              <button
                type="button"
                data-testid="goto-strategy-preview-from-task-detail"
                onClick={() => props.onNavigateToStrategyPreview?.({ taskId: props.taskId, runId: selectedRun.id })}
                className="rounded border border-[#4a4a4a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:border-zinc-500 hover:bg-[#292929]"
              >
                返回策略预览
              </button>
            ) : null}
            {props.onNavigateToRun ? (
              <button
                type="button"
                data-testid="goto-run-center-from-task-detail"
                onClick={() => props.onNavigateToRun?.(selectedRun.id, props.taskId)}
                className="rounded border border-[#4a4a4a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:border-zinc-500 hover:bg-[#292929]"
              >
                打开运行中心
              </button>
            ) : null}
            <CopyButton label="复制任务 ID" value={props.taskId} />
            <CopyButton label="复制运行 ID" value={selectedRun.id} />
          </div>
        </>
      ) : null}

      {/* ── A. 运行标识 ── */}
      <CardGroup title="运行标识" className={isLine ? "border-b border-[#333333] pb-4" : ""}>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <IdField label="任务 ID" value={props.taskId} />
          <IdField label="运行 ID" value={selectedRun.id} />
          <MiniField label="供应商" value={provider ?? "暂无"} />
          <MiniField label="提示词模板" value={promptTemplate ?? "暂无"} />
          <MiniField label="计算来源" value={pricingSource ?? "暂无"} />
        </div>
      </CardGroup>

      {/* ── B. Token 与成本 ── */}
      <CardGroup title="Token 与成本" className={isLine ? "border-b border-[#333333] pb-4" : ""}>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <NumberField label="提示词 Token" value={formatTokenCount(selectedRun.prompt_tokens)} />
          <NumberField label="补全 Token" value={formatTokenCount(selectedRun.completion_tokens)} />
          <NumberField label="总 Token" value={formatTokenCount(selectedRun.total_tokens ?? 0)} />
          <NumberField label="估算成本" value={formatCurrencyUsd(selectedRun.estimated_cost)} />
          <MiniField label="供应商回执" value={providerReceipt ? "已生成" : "暂无"} />
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <MiniField label="提示词字符数" value={selectedRun.prompt_char_count != null ? String(selectedRun.prompt_char_count) : "暂无"} />
          <MiniField label="计算模式" value={selectedRun.token_accounting_mode ?? "暂无"} />
          <MiniField label="开始 / 结束" value={`${formatDateTime(selectedRun.started_at)} → ${formatDateTime(selectedRun.finished_at)}`} />
        </div>
      </CardGroup>

      {/* ── C. 运行约束 / 模型策略 ── */}
      {props.hasRoleModelPolicyData ? (
        <CardGroup title="运行约束 / 模型策略" className={isLine ? "border-b border-[#333333] pb-4" : ""}>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            {props.roleModelPolicyFields.map((field) => (
              <MiniField
                key={`policy-${field.key}`}
                label={field.label}
                value={field.value || "暂无"}
              />
            ))}
          </div>
        </CardGroup>
      ) : null}

      {/* ── D. 失败与诊断 ── */}
      <CardGroup title="失败与诊断" className={isLine ? "border-b border-[#333333] pb-4" : ""}>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MiniField
            label="失败分类"
            value={failureCategory ?? "无"}
            tone={failureCategory ? "danger" : undefined}
          />
          <MiniField
            label="质量闸门"
            value={formatQualityGateLabel(selectedRun.quality_gate_passed)}
          />
          <MiniField
            label="分配评分"
            value={selectedRun.routing_score !== null ? String(selectedRun.routing_score) : "暂无"}
          />
          <MiniField
            label="验证模式"
            value={selectedRun.verification_mode ?? "未记录"}
          />
        </div>
        <DiagnosticBlock
          run={selectedRun}
          isLine={isLine}
        />
      </CardGroup>
    </div>
  );
}

/* ================================================================ */
/*  Sub-components                                                   */
/* ================================================================ */

function CardGroup(props: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={props.className}>
      <h4 className="mb-3 text-sm font-medium text-zinc-200">{props.title}</h4>
      {props.children}
    </section>
  );
}

function IdField(props: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(props.value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      // clipboard not available
    }
  };

  return (
    <div className="border-l border-[#333333] px-3 py-2 min-w-0">
      <div className="flex items-center justify-between gap-1">
        <span className="text-xs uppercase tracking-[0.18em] text-zinc-500">{props.label}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="shrink-0 text-[10px] text-zinc-500 transition hover:text-zinc-200"
        >
          {copied ? "已复制" : "复制"}
        </button>
      </div>
      <div
        className="mt-1 truncate font-mono text-sm text-zinc-100"
        title={props.value}
      >
        {props.value}
      </div>
    </div>
  );
}

function MiniField(props: {
  label: string;
  value: string;
  tone?: "success" | "danger" | "warning" | "neutral" | "info";
}) {
  return (
    <div className="border-l border-[#333333] px-3 py-2 min-w-0">
      <div className="text-xs uppercase tracking-[0.18em] text-zinc-500">{props.label}</div>
      <div
        className="mt-1 truncate text-sm font-medium text-zinc-100"
        title={props.value}
      >
        {props.value}
      </div>
    </div>
  );
}

function NumberField(props: { label: string; value: string }) {
  return (
    <div className="border-l border-[#333333] px-3 py-2">
      <div className="text-xs uppercase tracking-[0.18em] text-zinc-500">{props.label}</div>
      <div className="mt-1 font-mono text-sm font-semibold text-zinc-100">{props.value}</div>
    </div>
  );
}

function CopyButton(props: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(props.value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      // clipboard not available
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="rounded border border-[#4a4a4a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-400 transition hover:border-zinc-500 hover:text-zinc-100"
    >
      {copied ? "已复制" : props.label}
    </button>
  );
}

function DiagnosticBlock(props: { run: ConsoleRun; isLine: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const run = props.run;

  const diagnosticLines: string[] = [];
  if (run.failure_category) {
    diagnosticLines.push(`失败分类：${run.failure_category}`);
  }
  if (run.verification_summary) {
    diagnosticLines.push(`验证摘要：${run.verification_summary}`);
  }
  if (run.route_reason) {
    diagnosticLines.push(`分配说明：${run.route_reason}`);
  }
  if (run.result_summary) {
    diagnosticLines.push(`运行摘要：${run.result_summary}`);
  }

  if (diagnosticLines.length === 0) {
    return (
      <p className="mt-3 text-xs text-zinc-500">暂无详细诊断信息。</p>
    );
  }

  const visibleLines = expanded ? diagnosticLines : diagnosticLines.slice(0, 3);

  return (
    <div className="mt-3">
      <div className="border-l border-[#333333] px-4 py-3">
        <div className="text-xs uppercase tracking-[0.18em] text-zinc-500 mb-2">诊断信息</div>
        {visibleLines.map((line, i) => (
          <p key={i} className="text-sm leading-6 text-zinc-400">{line}</p>
        ))}
        {diagnosticLines.length > 3 ? (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="mt-2 text-xs text-zinc-500 transition hover:text-zinc-200"
          >
            {expanded ? "收起" : `展开全部（${diagnosticLines.length} 条）`}
          </button>
        ) : null}
      </div>
    </div>
  );
}

function formatQualityGateLabel(qualityGatePassed: boolean | null): string {
  if (qualityGatePassed === true) return "质量闸门放行";
  if (qualityGatePassed === false) return "质量闸门拦截";
  return "闸门未知";
}
