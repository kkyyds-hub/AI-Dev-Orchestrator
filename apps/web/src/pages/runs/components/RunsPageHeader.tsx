import { RunsSummaryCard } from "./RunsSummaryCard";

type RunsPageHeaderProps = {
  latestRunCount: number;
  runId: string | undefined;
  realtimeStatus: string;
};

export function RunsPageHeader(props: RunsPageHeaderProps) {
  return (
    <section className="border-b border-[#333333] pb-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-600">
            Runs
          </div>
          <h3 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-100">运行观测</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-500">
            集中查看运行状态、日志事件与相关任务上下文。
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <RunsSummaryCard label="可见运行" value={String(props.latestRunCount)} />
          <RunsSummaryCard
            label="当前运行"
            value={props.runId ?? "未选择"}
          />
          <RunsSummaryCard label="连接状态" value={props.realtimeStatus} />
        </div>
      </div>
    </section>
  );
}
