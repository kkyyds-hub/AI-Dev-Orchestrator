import { StatusBadge } from "../../components/StatusBadge";
import {
  useConsoleBudgetHealth,
  useConsoleFailureDistribution,
  useConsoleRoutingDistribution,
} from "./hooks";

type HintTone = "neutral" | "info" | "success" | "warning" | "danger";

type DecisionHint = {
  title: string;
  detail: string;
  tone: HintTone;
};

export function DecisionHintPanel() {
  const budgetQuery = useConsoleBudgetHealth();
  const failureQuery = useConsoleFailureDistribution();
  const routingQuery = useConsoleRoutingDistribution();

  const hints = buildHints(
    budgetQuery.data ?? null,
    failureQuery.data ?? null,
    routingQuery.data ?? null,
  );

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-50">管理决策提示</h2>
          <p className="mt-1 text-sm text-slate-400">
            根据预算压力、失败分布和路由热点，给出下一步优先动作建议。
          </p>
        </div>
        <StatusBadge
          label={
            budgetQuery.isLoading || failureQuery.isLoading || routingQuery.isLoading
              ? "计算中"
              : "已生成"
          }
          tone={
            budgetQuery.isLoading || failureQuery.isLoading || routingQuery.isLoading
              ? "warning"
              : "info"
          }
        />
      </div>

      <div className="mt-4 space-y-3">
        {hints.map((hint, index) => (
          <div
            key={`${hint.title}-${index}`}
            className="rounded-xl border border-slate-800 bg-slate-950/60 p-3"
          >
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-sm font-medium text-slate-100">{hint.title}</h3>
              <StatusBadge label={hintLabel(hint.tone)} tone={hint.tone} />
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-300">{hint.detail}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function buildHints(
  budget:
    | {
        pressure_level: "normal" | "warning" | "critical" | "blocked";
        strategy_label: string;
        strategy_code: string;
        daily_usage_ratio: number;
        session_usage_ratio: number;
      }
    | null,
  failure:
    | {
        total_runs: number;
        failed_or_cancelled_runs: number;
        failure_category_distribution: {
          category_label: string;
          count: number;
        }[];
      }
    | null,
  routing:
    | {
        distribution: {
          reason_code: string;
          reason_label: string;
          count: number;
        }[];
      }
    | null,
): DecisionHint[] {
  const hints: DecisionHint[] = [];

  if (budget) {
    const usageSummary = `日预算使用 ${(budget.daily_usage_ratio * 100).toFixed(1)}%，会话预算使用 ${(budget.session_usage_ratio * 100).toFixed(1)}%。`;
    if (budget.pressure_level === "blocked") {
      hints.push({
        title: "预算已进入阻断状态",
        detail: `${usageSummary} 当前策略 ${budget.strategy_label}（${budget.strategy_code}），建议先清理高风险任务并恢复预算窗口。`,
        tone: "danger",
      });
    } else if (budget.pressure_level === "critical") {
      hints.push({
        title: "预算处于临界压力",
        detail: `${usageSummary} 建议优先执行低风险、低上下文任务，减少重试放大。`,
        tone: "warning",
      });
    } else if (budget.pressure_level === "warning") {
      hints.push({
        title: "预算已进入预警",
        detail: `${usageSummary} 建议开启保守执行策略，优先收敛失败热点。`,
        tone: "warning",
      });
    } else {
      hints.push({
        title: "预算压力可控",
        detail: `${usageSummary} 可以继续常规推进，同时保持失败分布监控。`,
        tone: "success",
      });
    }
  }

  if (failure && failure.total_runs > 0) {
    const failedRatio = failure.failed_or_cancelled_runs / failure.total_runs;
    const topFailure = failure.failure_category_distribution[0];
    if (failedRatio >= 0.35) {
      hints.push({
        title: "失败占比较高，建议先止损",
        detail: `当前失败/取消占比 ${(failedRatio * 100).toFixed(1)}%。优先排查 ${topFailure?.category_label ?? "高频失败类型"}。`,
        tone: "danger",
      });
    } else if (failedRatio >= 0.2) {
      hints.push({
        title: "失败率进入关注区间",
        detail: `当前失败/取消占比 ${(failedRatio * 100).toFixed(1)}%。建议优先处理 ${topFailure?.category_label ?? "主要失败类型"} 并加强验证闸门。`,
        tone: "warning",
      });
    } else {
      hints.push({
        title: "失败率可控",
        detail: `当前失败/取消占比 ${(failedRatio * 100).toFixed(1)}%。维持当前节奏并持续跟踪失败聚类。`,
        tone: "success",
      });
    }
  }

  if (routing && routing.distribution.length > 0) {
    const topReason = routing.distribution[0];
    if (
      topReason.reason_code === "bg-blocked-stop"
      || topReason.reason_code === "bg-critical-degraded"
    ) {
      hints.push({
        title: "路由热点偏向预算压力路径",
        detail: `当前最高频路由原因为“${topReason.reason_label}”（${topReason.count} 次），建议先缓解预算压力再扩展吞吐。`,
        tone: "warning",
      });
    } else if (topReason.reason_code === "readiness_blocked") {
      hints.push({
        title: "路由热点偏向依赖阻塞",
        detail: `当前最高频路由原因为“${topReason.reason_label}”（${topReason.count} 次），建议先清理依赖就绪条件。`,
        tone: "warning",
      });
    } else {
      hints.push({
        title: "路由热点可接受",
        detail: `当前最高频路由原因为“${topReason.reason_label}”（${topReason.count} 次），未出现明显异常热点。`,
        tone: "info",
      });
    }
  }

  if (!hints.length) {
    hints.push({
      title: "等待观测数据",
      detail: "当前还没有足够运行数据生成决策提示，先执行一轮任务后再观察。",
      tone: "neutral",
    });
  }

  return hints.slice(0, 4);
}

function hintLabel(tone: HintTone): string {
  switch (tone) {
    case "success":
      return "正常";
    case "info":
      return "建议";
    case "warning":
      return "关注";
    case "danger":
      return "高优先";
    default:
      return "中性";
  }
}
