import type { ConsoleRun } from "../../../features/console/types";

export type RunUserSummary = {
  /** One-line conclusion in Chinese */
  conclusion: string;
  /** What was completed (bullet items) */
  completedItems: string[];
  /** Warnings and notes the user should know */
  warnings: string[];
  /** Suggested next steps */
  nextSteps: string[];
  /** Whether the run was a real provider execution (not mock/fallback) */
  isRealExecution: boolean;
  /** Whether this was a simulated verification */
  isSimulatedVerification: boolean;
  /** Whether quality gate passed */
  qualityGatePassed: boolean | null;
  /** Detected execution mode description */
  executionModeLabel: string;
};

// ── detection helpers ──────────────────────────────────────────────

function isMockExecution(run: ConsoleRun): boolean {
  const summary = (run.result_summary ?? "").toLowerCase();
  const provider = (run.provider_key ?? "").toLowerCase();
  return (
    summary.includes("provider_mock") ||
    summary.includes("mock execution") ||
    summary.includes("mock provider") ||
    provider.includes("mock")
  );
}

function isFallbackExecution(run: ConsoleRun): boolean {
  const summary = (run.result_summary ?? "").toLowerCase();
  return (
    summary.includes("fallback_applied") ||
    summary.includes("fallback") ||
    summary.includes("降级")
  );
}

/**
 * timeout 只能由 result_summary / verification_summary / route_reason
 * 中明确包含 timeout、timed out、超时等信息判断。
 * 不允许把 failure_category === "execution_failed" 直接等同于 timeout。
 */
function isTimeout(run: ConsoleRun): boolean {
  const haystack = [
    run.result_summary ?? "",
    run.verification_summary ?? "",
    run.route_reason ?? "",
  ]
    .join(" ")
    .toLowerCase();
  return (
    haystack.includes("timeout") ||
    haystack.includes("timed out") ||
    haystack.includes("超时")
  );
}

function detectProviderName(run: ConsoleRun): string {
  const key = (run.provider_key ?? "").toLowerCase();
  if (key.includes("deepseek")) return "DeepSeek";
  if (key.includes("openai")) return "OpenAI";
  if (key.includes("anthropic")) return "Anthropic";
  if (key.includes("mock")) return "模拟模型";
  return run.provider_key ?? "未知模型服务";
}

/**
 * 真实模型执行成功至少应满足：
 * - run.status === "succeeded"
 * - provider_key 存在且不包含 mock
 * - result_summary 不包含 provider_mock / fallback
 * - provider_receipt_id 存在
 */
function isRealProviderExecution(run: ConsoleRun): boolean {
  const summary = (run.result_summary ?? "").toLowerCase();
  const provider = (run.provider_key ?? "").toLowerCase();
  return (
    run.status === "succeeded" &&
    !!run.provider_key &&
    !provider.includes("mock") &&
    !summary.includes("provider_mock") &&
    !summary.includes("mock execution") &&
    !summary.includes("mock provider") &&
    !summary.includes("fallback") &&
    !!run.provider_receipt_id
  );
}

/**
 * 运行已完成但缺少 provider_receipt_id，不能确认模型服务回执。
 */
function isSucceededWithoutReceipt(run: ConsoleRun): boolean {
  return (
    run.status === "succeeded" &&
    !isMockExecution(run) &&
    !isFallbackExecution(run) &&
    !run.provider_receipt_id
  );
}

// ── main generator ─────────────────────────────────────────────────

export function generateRunUserSummary(run: ConsoleRun): RunUserSummary {
  const mock = isMockExecution(run);
  const fallback = isFallbackExecution(run);
  const timeout = isTimeout(run);
  const providerName = detectProviderName(run);
  const isReal = isRealProviderExecution(run);
  const isSucceededNoReceipt = isSucceededWithoutReceipt(run);
  const isSimulated = run.verification_mode === "simulate";
  const qgPassed = run.quality_gate_passed;

  const summary: RunUserSummary = {
    isRealExecution: isReal,
    isSimulatedVerification: isSimulated,
    qualityGatePassed: qgPassed,
    executionModeLabel: "",
    conclusion: "",
    completedItems: [],
    warnings: [],
    nextSteps: [],
  };

  // ── execution mode label ────────────────────────────────────
  if (mock) {
    summary.executionModeLabel = "模拟模型执行（不可作为真实交付依据）";
  } else if (fallback) {
    summary.executionModeLabel = "降级执行（不可作为真实交付依据）";
  } else if (isReal) {
    summary.executionModeLabel = `模型服务 ${providerName} 已真实执行成功`;
  } else if (isSucceededNoReceipt) {
    summary.executionModeLabel = "运行已完成，但未确认模型服务回执";
  } else if (timeout) {
    summary.executionModeLabel = "模型请求超时，本次未完成";
  } else if (run.status === "failed") {
    summary.executionModeLabel = "本次运行失败";
  } else if (run.status === "running") {
    summary.executionModeLabel = "运行中";
  } else if (run.status === "cancelled") {
    summary.executionModeLabel = "已取消";
  } else {
    summary.executionModeLabel = "状态未知";
  }

  // ── conclusion ──────────────────────────────────────────────
  if (isReal) {
    summary.conclusion = `本次任务已由 ${providerName} 成功执行。`;
  } else if (mock) {
    summary.conclusion = "本次为模拟模型执行结果，不能作为真实交付依据。";
  } else if (fallback) {
    summary.conclusion = "本次发生降级执行，不能作为真实交付依据。";
  } else if (isSucceededNoReceipt) {
    summary.conclusion = "运行已完成，但未确认模型服务回执。请查看技术日志了解详情。";
  } else if (timeout) {
    summary.conclusion = "模型请求超时，本次未完成或需要重试。";
  } else if (run.status === "failed") {
    summary.conclusion = "本次运行失败，请查看技术日志了解原因。";
  } else if (run.status === "running") {
    summary.conclusion = "任务正在运行中，请稍后查看结果。";
  } else if (run.status === "cancelled") {
    summary.conclusion = "本次运行已被取消。";
  } else {
    summary.conclusion = "运行状态未知，请查看技术日志。";
  }

  // ── completed items ─────────────────────────────────────────
  if (run.status === "succeeded") {
    summary.completedItems.push("已根据任务目标生成执行结果。");
    if (run.provider_receipt_id) {
      summary.completedItems.push("已收到模型服务回执。");
    }
    summary.completedItems.push("已完成当前配置的质量检查。");
  } else if (run.status === "failed") {
    summary.completedItems.push("已尝试执行任务。");
    if (run.failure_category) {
      summary.completedItems.push(
        `失败原因类别：${formatFailureCategory(run.failure_category)}。`
      );
    }
  } else if (run.status === "running") {
    summary.completedItems.push("已领取任务并开始执行。");
  }

  // ── warnings ────────────────────────────────────────────────
  if (isSimulated) {
    summary.warnings.push(
      "当前为模拟验证，不代表代码真实构建通过。建议为该项目配置真实验证命令，例如 npm run build 或 pytest。"
    );
  }
  if (mock) {
    summary.warnings.push(
      "模拟模型执行，不能作为真实交付依据。请检查模型服务配置是否正确。"
    );
  }
  if (fallback) {
    summary.warnings.push(
      "发生降级执行，未使用真实模型服务。请确认 Provider 配置和网络状态。"
    );
  }
  if (timeout) {
    summary.warnings.push(
      "模型请求超时，本次未完成或需要重试。建议检查网络状态或提高超时时间（当前默认 120 秒）。"
    );
  }
  if (isSucceededNoReceipt) {
    summary.warnings.push(
      "运行已完成但缺少模型服务回执，无法确认是否由真实模型执行。建议查看技术日志中的原始字段。"
    );
  }
  if (qgPassed === false) {
    summary.warnings.push(
      "本次运行被质量检查拦截，请查看技术日志定位原因。"
    );
  }
  if (run.status === "failed" && !timeout && !mock && !fallback) {
    summary.warnings.push("运行失败，建议查看技术日志了解详细原因。");
  }

  // ── next steps ──────────────────────────────────────────────
  if (isReal) {
    summary.nextSteps.push("前往交付件页和审批页查看后端自动生成结果。");
  }
  if (isSimulated) {
    summary.nextSteps.push("为该项目配置真实验证命令。");
  }
  if (mock) {
    summary.nextSteps.push("检查并修复模型服务配置（当前为模拟模型）。");
    summary.nextSteps.push("重新运行任务以获取真实结果。");
  } else if (fallback) {
    summary.nextSteps.push("排查降级原因，确认 Provider 配置和网络状态。");
    summary.nextSteps.push("重新运行任务以获取真实结果。");
  }
  if (timeout || run.status === "failed") {
    summary.nextSteps.push("排查失败原因后重新运行任务。");
  }
  if (isSucceededNoReceipt) {
    summary.nextSteps.push("查看技术日志确认执行详情。");
  }
  if (run.status === "running") {
    summary.nextSteps.push("等待任务执行完成。");
    summary.nextSteps.push("可刷新页面查看最新状态。");
  }
  summary.nextSteps.push('点击下方\u201C查看技术日志\u201D了解更多执行细节。');

  return summary;
}

function formatFailureCategory(category: string): string {
  switch (category) {
    case "verification_configuration_failed":
      return "验证配置失败";
    case "verification_failed":
      return "验证失败";
    case "execution_failed":
      return "执行失败";
    case "daily_budget_exceeded":
      return "日预算超限";
    case "session_budget_exceeded":
      return "会话预算超限";
    case "retry_limit_exceeded":
      return "重试达到上限";
    default:
      return category;
  }
}
