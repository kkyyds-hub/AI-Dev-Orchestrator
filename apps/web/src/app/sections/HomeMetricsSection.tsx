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
        label="Total tasks"
        value={String(props.totalTasks)}
        hint="All tasks tracked by the workbench"
      />
      <MetricCard
        label="Running / Pending"
        value={`${props.runningTasks} / ${props.pendingTasks}`}
        hint="Worker load and queued work"
        tone="info"
      />
      <MetricCard
        label="Paused / Human"
        value={`${props.pausedTasks} / ${props.waitingHumanTasks}`}
        hint="States that need operator attention"
        tone="warning"
      />
      <MetricCard
        label="Done / Failed"
        value={`${props.completedTasks} / ${props.failedTasks}`}
        hint="Task closure quality"
        tone="success"
      />
      <MetricCard
        label="Estimated cost"
        value={formatCurrencyUsd(props.totalEstimatedCost)}
        hint={`Total tokens: ${formatTokenCount(totalTokens)}`}
        tone="warning"
      />
    </section>
  );
}
