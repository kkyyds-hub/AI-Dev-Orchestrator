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
      <MetricCard
        label="任务总数"
        value={String(props.totalTasks)}
        hint="工作台当前追踪的全部任务"
      />
      <MetricCard
        label="运行 / 待处理"
        value={`${props.runningTasks} / ${props.pendingTasks}`}
        hint="Worker 负载与排队任务"
        tone="info"
      />
      <MetricCard
        label="暂停 / 人工"
        value={`${props.pausedTasks} / ${props.waitingHumanTasks}`}
        hint="需要操作员关注的状态"
        tone="warning"
      />
      <MetricCard
        label="完成 / 失败"
        value={`${props.completedTasks} / ${props.failedTasks}`}
        hint="任务收口质量"
        tone="success"
      />
      <MetricCard
        label="预估费用"
        value={formatCurrencyUsd(props.totalEstimatedCost)}
        hint={`总 Token：${formatTokenCount(totalTokens)}`}
        tone="warning"
      />
    </section>
  );
}
