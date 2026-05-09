import { StatusBadge } from "../../../components/StatusBadge";
import type { DeliverableSummary, DeliverableVersion } from "../types";
import { DeliverableVersionCard } from "./DeliverableVersionCard";

type DeliverableVersionSnapshotSectionProps = {
  deliverableType: DeliverableSummary["type"];
  versions: DeliverableVersion[];
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
};

export function DeliverableVersionSnapshotSection(
  props: DeliverableVersionSnapshotSectionProps,
) {
  return (
    <section className="border-b border-[#333333] pb-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h4 className="text-base font-semibold text-slate-50">
            版本快照列表
          </h4>
          <p className="mt-1 text-sm leading-6 text-slate-400">
            先看每次提交的摘要，再进入下方对比视图查看版本变化。
          </p>
        </div>
        <StatusBadge label={`${props.versions.length} 个版本`} tone="neutral" />
      </div>

      <div className="mt-4 divide-y divide-[#333333]">
        {props.versions.map((version) => (
          <DeliverableVersionCard
            key={version.id}
            deliverableType={props.deliverableType}
            version={version}
            onNavigateToTask={props.onNavigateToTask}
          />
        ))}
      </div>
    </section>
  );
}
