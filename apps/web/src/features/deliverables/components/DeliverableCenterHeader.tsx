import { DeliverableCenterMetric } from "./DeliverableCenterMetric";

type DeliverableCenterHeaderProps = {
  projectName: string | null;
  totalDeliverables: number;
  totalVersions: number;
};

export function DeliverableCenterHeader(props: DeliverableCenterHeaderProps) {
  return (
    <header className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-6 lg:flex-row lg:items-end lg:justify-between">
      <div className="space-y-2">
        <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">
          V3 Day09 Deliverable Repository
        </p>
        <h2 className="text-3xl font-semibold tracking-tight text-slate-50">
          交付件仓库与版本快照
        </h2>
        <p className="max-w-3xl text-sm leading-6 text-slate-300">
          把 PRD、设计稿、任务拆分、代码计划、验收结论等项目产物纳入统一仓库；同一交付件按版本持续提交，并保留完整快照、来源任务与运行关联。
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        <DeliverableCenterMetric
          label="当前项目"
          value={props.projectName ?? "未选择项目"}
        />
        <DeliverableCenterMetric
          label="交付件数量"
          value={String(props.totalDeliverables)}
        />
        <DeliverableCenterMetric
          label="版本快照数"
          value={String(props.totalVersions)}
        />
      </div>
    </header>
  );
}
