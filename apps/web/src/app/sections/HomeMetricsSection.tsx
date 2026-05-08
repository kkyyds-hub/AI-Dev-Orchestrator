import { MetricCard } from "../../components/MetricCard";
import { formatCurrencyUsd, formatTokenCount } from "../../lib/format";

type HomeMetricsSectionProps = {
  totalTasks: number;
  runningTasks: number;
  pendingTasks: number;
  pausedTasks: number;
  waitingHumanTasks: number;
  completedTasks: number;
  failedTasks: number;
  totalPromptTokens: number;
  totalCompletionTokens: number;
  totalEstimatedCost: number;
};

export function HomeMetricsSection(props: HomeMetricsSectionProps) {
  const totalTokens = props.totalPromptTokens + props.totalCompletionTokens;

  return (
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      <MetricCard label="任务" value={String(props.totalTasks)} hint="当前追踪任务" />
      <MetricCard
        label="运行 / 待处理"
        value={`${props.runningTasks} / ${props.pendingTasks}`}
        hint="Worker 队列"
      />
      <MetricCard
        label="暂停 / 人工"
        value={`${props.pausedTasks} / ${props.waitingHumanTasks}`}
        hint="需关注状态"
      />
      <MetricCard
        label="完成 / 失败"
        value={`${props.completedTasks} / ${props.failedTasks}`}
        hint="收口结果"
      />
      <MetricCard
        label="预估费用"
        value={formatCurrencyUsd(props.totalEstimatedCost)}
        hint={`Token：${formatTokenCount(totalTokens)}`}
      />
    </section>
  );
}
