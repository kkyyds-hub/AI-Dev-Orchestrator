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
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
      <MetricCard
        label="浠诲姟鎬绘暟"
        value={String(props.totalTasks)}
        hint="褰撳墠绯荤粺鍐呭凡鍒涘缓鐨勪换鍔℃暟"
      />
      <MetricCard
        label="杩愯涓?/ 寰呭鐞?"
        value={`${props.runningTasks} / ${props.pendingTasks}`}
        hint="鏈€灏?Worker 褰撳墠鍙鐨勫伐浣滈噺"
        tone="info"
      />
      <MetricCard
        label="鏆傚仠 / 寰呬汉宸?"
        value={`${props.pausedTasks} / ${props.waitingHumanTasks}`}
        hint="鏄惧紡鏆傚仠鍜屼汉宸ヤ粙鍏ョ姸鎬?"
        tone="warning"
      />
      <MetricCard
        label="宸插畬鎴?/ 澶辫触"
        value={`${props.completedTasks} / ${props.failedTasks}`}
        hint="鎴愬姛涓庡け璐ヤ换鍔℃暟閲?"
        tone="success"
      />
      <MetricCard
        label="绱浼扮畻鎴愭湰"
        value={formatCurrencyUsd(props.totalEstimatedCost)}
        hint={`鎬?token锛?${formatTokenCount(totalTokens)}`}
        tone="warning"
      />
    </section>
  );
}
