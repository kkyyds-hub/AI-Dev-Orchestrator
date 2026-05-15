import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import type { DeliverableSummary } from "../types";
import { DeliverableCardButton } from "./DeliverableCardButton";

type DeliverableListPanelProps = {
  deliverables: DeliverableSummary[];
  generatedAt?: string | null;
  selectedDeliverableId: string | null;
  onSelectDeliverable: (deliverableId: string) => void;
};

export function DeliverableListPanel(props: DeliverableListPanelProps) {
  return (
    <section className="border-b border-[#333333] pb-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-zinc-100">交付件清单</h3>
          <p className="mt-1 text-sm text-zinc-400">
            项目当前阶段产生的正式产物与最新版本摘要。
          </p>
        </div>
        <StatusBadge
          label={
            props.generatedAt
              ? `生成于 ${formatDateTime(props.generatedAt)}`
              : "尚未生成"
          }
          tone="neutral"
        />
      </div>

      {props.deliverables.length > 0 ? (
        <div className="mt-4 divide-y divide-[#333333]">
          {props.deliverables.map((deliverable) => (
            <DeliverableCardButton
              key={deliverable.id}
              deliverable={deliverable}
              selected={deliverable.id === props.selectedDeliverableId}
              onSelect={() => props.onSelectDeliverable(deliverable.id)}
            />
          ))}
        </div>
      ) : (
        <div className="mt-4 border border-dashed border-[#3a3a3a] px-4 py-8 text-sm leading-6 text-zinc-400">
          当前项目还没有交付件。生成或提交 PRD、设计稿、任务拆分、代码计划、验收结论后，会在这里形成版本快照。
        </div>
      )}
    </section>
  );
}
