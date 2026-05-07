import { RunsSummaryCard } from "./RunsSummaryCard";

type RunsPageHeaderProps = {
  latestRunCount: number;
  runId: string | undefined;
  realtimeStatus: string;
};

export function RunsPageHeader(props: RunsPageHeaderProps) {
  return (
    <section className="rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs font-medium uppercase tracking-[0.24em] text-cyan-300">
            Runs
          </div>
          <h3 className="mt-2 text-xl font-semibold text-slate-50">运行中心</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
            在正式运行域中查看运行状态、决策回放、结构化日志事件与运行上下文。
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
