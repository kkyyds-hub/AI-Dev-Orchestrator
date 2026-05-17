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

function isTimeout(run: ConsoleRun): boolean {
  const summary = (run.result_summary ?? "").toLowerCase();
  return (
    summary.includes("timeout") ||
    summary.includes("timed out") ||
    summary.includes("超时") ||
    run.failure_category === "execution_failed"
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

// ── main generator ─────────────────────────────────────────────────

export function generateRunUserSummary(run: ConsoleRun): RunUserSummary {
  const mock = isMockExecution(run);
  const fallback = isFallbackExecution(run);
  const timeout = isTimeout(run);
  const providerName = detectProviderName(run);
  const isReal = !mock && !fallback && run.status === "succeeded";
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
    summary.executionModeLabel = "模拟执行（不可作为真实交付依据）";
  } else if (fallback) {
    summary.executionModeLabel = "降级执行（不可作为真实交付依据）";
  } else if (isReal) {
    summary.executionModeLabel = `模型服务 ${providerName} 已真实执行成功`;
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
    summary.conclusion = "本次为模拟执行结果，不能作为真实交付依据。";
  } else if (fallback) {
    summary.conclusion = "本次为降级执行结果，不能作为真实交付依据。";
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
      "模拟 / 降级执行，不能作为真实交付依据。请检查模型服务配置是否正确。"
    );
  }
  if (fallback) {
    summary.warnings.push(
      "本次发生了降级执行，未使用真实模型服务。请确认 Provider 配置和网络状态。"
    );
  }
  if (timeout) {
    summary.warnings.push(
      "模型请求超时，本次未完成或需要重试。建议检查网络状态或提高超时时间（当前默认 120 秒）。"
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
    summary.nextSteps.push("查看本次运行生成的交付件。");
    summary.nextSteps.push("审批或退回交付件。");
  }
  if (isSimulated) {
    summary.nextSteps.push("为该项目配置真实验证命令。");
  }
  if (mock || fallback) {
    summary.nextSteps.push("检查并修复模型服务配置。");
    summary.nextSteps.push("重新运行任务以获取真实结果。");
  }
  if (timeout || run.status === "failed") {
    summary.nextSteps.push("排查失败原因后重新运行任务。");
    summary.nextSteps.push("如需帮助，请查看技术日志。");
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
