import type { ConsoleRun } from "../../../features/console/types";
import {
  formatCurrencyUsd,
  formatDateTime,
  formatTokenCount,
} from "../../../lib/format";

export type TechnicalLogSection = {
  id: string;
  title: string;
  fields: TechnicalLogField[];
  /** Optional free-text content for this section */
  content?: string;
};

export type TechnicalLogField = {
  label: string;
  value: string;
  /** If true, display in monospace */
  mono?: boolean;
  /** If true, this is a long value that should word-wrap */
  long?: boolean;
};

export type TechnicalLogData = {
  runId: string;
  taskTitle: string;
  sections: TechnicalLogSection[];
  /** All raw fields concatenated for copy-all */
  rawText: string;
};

// ── helpers ────────────────────────────────────────────────────────

function field(label: string, value: string, opts?: { mono?: boolean; long?: boolean }): TechnicalLogField {
  return { label, value: value || "暂无", ...opts };
}

function fmtBool(val: boolean | null): string {
  if (val === true) return "是";
  if (val === false) return "否";
  return "未知";
}

function formatVerificationMode(mode: string | null): string {
  switch (mode) {
    case "simulate": return "模拟验证";
    case "command": return "命令验证";
    case "template": return "模板验证";
    default: return mode ?? "未记录";
  }
}

function formatQualityGate(qg: boolean | null): string {
  if (qg === true) return "通过";
  if (qg === false) return "拦截";
  return "未知";
}

function formatRunStatus(status: string): string {
  switch (status) {
    case "succeeded": return "已成功";
    case "running": return "运行中";
    case "failed": return "失败";
    case "cancelled": return "已取消";
    default: return status;
  }
}

// ── main builder ───────────────────────────────────────────────────

export function buildTechnicalLog(
  run: ConsoleRun,
  taskTitle: string,
): TechnicalLogData {
  const sections: TechnicalLogSection[] = [];

  // ── A. 状态概览 ─────────────────────────────────────────────
  sections.push({
    id: "status-overview",
    title: "状态概览",
    fields: [
      field("运行状态", formatRunStatus(run.status)),
      field("执行模式", formatExecutionMode(run)),
      field("是否真实模型执行", fmtBool(isRealProvider(run))),
      field("是否发生降级", fmtBool(isFallback(run))),
      field("质量检查", formatQualityGate(run.quality_gate_passed)),
      field("失败分类", formatFailureCategory(run.failure_category)),
      field("开始时间", formatDateTime(run.started_at)),
      field("结束时间", formatDateTime(run.finished_at)),
    ],
  });

  // ── B. 执行轨迹 ─────────────────────────────────────────────
  sections.push({
    id: "execution-trace",
    title: "执行轨迹",
    content: buildExecutionTrace(run),
    fields: [
      field("调度状态", run.dispatch_status ?? "暂无"),
      field("分配评分", run.routing_score !== null ? String(run.routing_score) : "暂无"),
      field("角色代码", run.owner_role_code ?? "暂无"),
      field("交接原因", run.handoff_reason ?? "无"),
    ],
  });

  // ── C. 模型调用 ─────────────────────────────────────────────
  sections.push({
    id: "model-invocation",
    title: "模型调用",
    fields: [
      field("模型服务", formatProviderLabel(run.provider_key)),
      field("模型名称", run.provider_key ?? "暂无"),
      field("接口类型", "OpenAI-compatible"),
      field("模型回执", run.provider_receipt_id ?? "不存在", { mono: true, long: true }),
      field("提示词模板", run.prompt_template_key ?? "暂无", { mono: true }),
      field("提示词版本", run.prompt_template_version ?? "暂无"),
      field("提示词字符数", run.prompt_char_count != null ? String(run.prompt_char_count) : "暂无"),
      field("是否降级", fmtBool(isFallback(run))),
    ],
  });

  // ── D. 质量检查 ─────────────────────────────────────────────
  sections.push({
    id: "quality-check",
    title: "质量检查",
    fields: [
      field("验证方式", formatVerificationMode(run.verification_mode)),
      field("验证模板", run.verification_template ?? "未配置"),
      field("验证命令", run.verification_command ?? "未配置"),
      field("质量检查结果", formatQualityGate(run.quality_gate_passed)),
      field("失败分类", formatFailureCategory(run.failure_category)),
    ],
    content: run.verification_summary
      ? `验证摘要：${run.verification_summary}`
      : undefined,
  });

  // ── E. 用量成本 ─────────────────────────────────────────────
  sections.push({
    id: "usage-cost",
    title: "用量与成本",
    fields: [
      field("输入 Token", formatTokenCount(run.prompt_tokens), { mono: true }),
      field("输出 Token", formatTokenCount(run.completion_tokens), { mono: true }),
      field("总 Token", formatTokenCount(run.total_tokens ?? 0), { mono: true }),
      field("估算成本", formatCurrencyUsd(run.estimated_cost), { mono: true }),
      field("计费来源", run.token_pricing_source ?? "暂无"),
      field("用量统计模式", run.token_accounting_mode ?? "暂无"),
    ],
  });

  // ── F. 交付件与审批 ─────────────────────────────────────────
  sections.push({
    id: "deliverable-approval",
    title: "交付件与审批",
    fields: [
      field("运行 ID", run.id, { mono: true }),
      field("日志路径", run.log_path ?? "暂无", { mono: true }),
      field("创建时间", formatDateTime(run.created_at)),
    ],
  });

  // ── G. 原始摘要 / 原始日志 ──────────────────────────────────
  const rawLines: string[] = [];
  if (run.result_summary) {
    rawLines.push("=== result_summary ===");
    rawLines.push(run.result_summary);
    rawLines.push("");
  }
  if (run.verification_summary) {
    rawLines.push("=== verification_summary ===");
    rawLines.push(run.verification_summary);
    rawLines.push("");
  }
  if (run.route_reason) {
    rawLines.push("=== route_reason ===");
    rawLines.push(run.route_reason);
    rawLines.push("");
  }

  sections.push({
    id: "raw-summaries",
    title: "原始摘要",
    content: rawLines.length > 0 ? rawLines.join("\n") : "暂无原始摘要数据。",
    fields: [
      field("结果摘要", run.result_summary ? "已生成（见下方原始文本）" : "无", { long: true }),
      field("验证摘要", run.verification_summary ? "已生成（见下方原始文本）" : "无", { long: true }),
      field("分配说明", run.route_reason ? "已生成（见下方原始文本）" : "无", { long: true }),
    ],
  });

  // ── H. 原始字段 ─────────────────────────────────────────────
  const rawFieldText = buildRawFieldsText(run);

  sections.push({
    id: "raw-fields",
    title: "原始字段",
    content: rawFieldText,
    fields: [],
  });

  // ── build raw text for copy-all ─────────────────────────────
  const rawText = buildCopyAllText(sections, taskTitle, run);

  return {
    runId: run.id,
    taskTitle,
    sections,
    rawText,
  };
}

// ── internal helpers ───────────────────────────────────────────────

function isRealProvider(run: ConsoleRun): boolean {
  const summary = (run.result_summary ?? "").toLowerCase();
  const provider = (run.provider_key ?? "").toLowerCase();
  return (
    run.status === "succeeded" &&
    !summary.includes("provider_mock") &&
    !summary.includes("mock execution") &&
    !summary.includes("mock provider") &&
    !provider.includes("mock") &&
    !summary.includes("fallback")
  );
}

function isFallback(run: ConsoleRun): boolean {
  const summary = (run.result_summary ?? "").toLowerCase();
  return summary.includes("fallback");
}

function formatExecutionMode(run: ConsoleRun): string {
  const summary = (run.result_summary ?? "").toLowerCase();
  const provider = (run.provider_key ?? "").toLowerCase();
  if (summary.includes("provider_mock") || provider.includes("mock")) {
    return "模拟执行（provider_mock）";
  }
  if (summary.includes("fallback")) {
    return "降级执行（fallback）";
  }
  if (run.status === "succeeded" && run.provider_receipt_id) {
    return "真实模型执行";
  }
  if (run.status === "failed") {
    return "执行失败";
  }
  return run.status;
}

function formatProviderLabel(key: string | null): string {
  if (!key) return "暂无";
  const lower = key.toLowerCase();
  if (lower.includes("deepseek")) return "DeepSeek";
  if (lower.includes("openai")) return "OpenAI";
  if (lower.includes("anthropic")) return "Anthropic";
  if (lower.includes("mock")) return "模拟模型";
  return key;
}

function formatFailureCategory(category: string | null): string {
  switch (category) {
    case "verification_configuration_failed": return "验证配置失败";
    case "verification_failed": return "验证失败";
    case "execution_failed": return "执行失败";
    case "daily_budget_exceeded": return "日预算超限";
    case "session_budget_exceeded": return "会话预算超限";
    case "retry_limit_exceeded": return "重试达到上限";
    default: return category ?? "无";
  }
}

function buildExecutionTrace(run: ConsoleRun): string {
  const steps: string[] = [];
  steps.push("1. 已领取任务");
  steps.push("2. 已构建提示词");

  if (run.status === "failed" || run.status === "succeeded" || run.status === "cancelled") {
    const summary = (run.result_summary ?? "").toLowerCase();
    if (summary.includes("timeout")) {
      steps.push("3. 调用模型服务超时");
      steps.push("4. 本次运行已标记失败");
      steps.push("5. 未生成交付件和审批");
    } else if (summary.includes("provider_mock") || (run.provider_key ?? "").toLowerCase().includes("mock")) {
      steps.push("3. 使用模拟模型执行");
      steps.push("4. 已完成模拟执行（非真实结果）");
    } else if (run.status === "succeeded") {
      steps.push(`3. 已调用模型服务（${formatProviderLabel(run.provider_key)}）`);
      steps.push("4. 已收到模型回执");
      steps.push("5. 已完成验证");
      steps.push("6. 已生成交付件");
      steps.push("7. 已创建审批记录");
    } else {
      steps.push(`3. 已调用模型服务（${formatProviderLabel(run.provider_key)}）`);
      steps.push("4. 执行过程出现异常");
    }
  } else {
    steps.push("3. 正在调用模型服务...");
  }

  return steps.join("\n");
}

function buildRawFieldsText(run: ConsoleRun): string {
  const fields: Record<string, unknown> = {
    id: run.id,
    status: run.status,
    provider_key: run.provider_key,
    prompt_template_key: run.prompt_template_key,
    prompt_template_version: run.prompt_template_version,
    token_accounting_mode: run.token_accounting_mode,
    token_pricing_source: run.token_pricing_source,
    prompt_char_count: run.prompt_char_count,
    prompt_tokens: run.prompt_tokens,
    completion_tokens: run.completion_tokens,
    total_tokens: run.total_tokens,
    estimated_cost: run.estimated_cost,
    provider_receipt_id: run.provider_receipt_id,
    verification_mode: run.verification_mode,
    verification_template: run.verification_template,
    verification_command: run.verification_command,
    verification_summary: run.verification_summary,
    failure_category: run.failure_category,
    quality_gate_passed: run.quality_gate_passed,
    route_reason: run.route_reason,
    routing_score: run.routing_score,
    dispatch_status: run.dispatch_status,
    owner_role_code: run.owner_role_code,
    handoff_reason: run.handoff_reason,
    started_at: run.started_at,
    finished_at: run.finished_at,
    created_at: run.created_at,
    log_path: run.log_path,
    result_summary: run.result_summary,
  };

  return "以下内容为系统调试字段，普通用户无需关注。\n\n" +
    JSON.stringify(fields, null, 2);
}

function buildCopyAllText(
  sections: TechnicalLogSection[],
  taskTitle: string,
  run: ConsoleRun,
): string {
  const lines: string[] = [];
  lines.push(`===== 技术日志 · 运行详情 =====`);
  lines.push(`任务：${taskTitle}`);
  lines.push(`运行 ID：${run.id}`);
  lines.push("");

  for (const section of sections) {
    lines.push(`--- ${section.title} ---`);
    for (const f of section.fields) {
      lines.push(`${f.label}：${f.value}`);
    }
    if (section.content) {
      lines.push("");
      lines.push(section.content);
    }
    lines.push("");
  }

  return lines.join("\n");
}
