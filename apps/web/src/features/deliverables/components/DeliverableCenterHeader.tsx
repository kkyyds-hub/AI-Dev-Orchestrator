import { DeliverableCenterMetric } from "./DeliverableCenterMetric";

type DeliverableCenterHeaderProps = {
  projectName: string | null;
  totalDeliverables: number;
  totalVersions: number;
};

export function DeliverableCenterHeader(props: DeliverableCenterHeaderProps) {
  return (
    <header className="flex flex-col gap-4 border-b border-[#333333] pb-6 lg:flex-row lg:items-end lg:justify-between">
      <div className="space-y-2">
        <p className="text-sm font-medium uppercase tracking-[0.24em] text-zinc-500">
          交付物中心
        </p>
        <h2 className="text-3xl font-semibold tracking-tight text-zinc-100">
          交付件仓库与版本快照
        </h2>
        <p className="max-w-3xl text-sm leading-6 text-zinc-400">
          集中查看当前项目的交付件、版本快照、来源任务和后续审批依据。
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
