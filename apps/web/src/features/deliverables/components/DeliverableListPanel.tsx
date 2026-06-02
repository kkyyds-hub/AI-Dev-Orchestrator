import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import type { DeliverableSummary } from "../types";
import { DeliverableCardButton } from "./DeliverableCardButton";

const TITLE = "\u4ea4\u4ed8\u7269\u8f7b\u5217\u8868";
const DESCRIPTION = "\u6309 Stage 6-A \u517c\u5bb9\u5408\u540c\u8bfb\u53d6\u5f53\u524d\u9879\u76ee\u4ea4\u4ed8\u7269\uff0c\u5de6\u4fa7\u53ea\u4fdd\u7559\u6807\u9898\u3001\u72b6\u6001\u3001\u6458\u8981\u548c\u7248\u672c\u53f7\u3002";
const REFRESH_PREFIX = "\u5237\u65b0\u4e8e";
const WAITING_REFRESH = "\u7b49\u5f85\u5237\u65b0";
const EMPTY_TEXT = "\u5f53\u524d\u9879\u76ee\u8fd8\u6ca1\u6709\u4ea4\u4ed8\u7269\u3002\u4ea7\u751f PRD\u3001\u8bbe\u8ba1\u7a3f\u3001\u4efb\u52a1\u62c6\u89e3\u3001\u4ee3\u7801\u8ba1\u5212\u6216\u9a8c\u6536\u7ed3\u8bba\u540e\uff0c\u4f1a\u5728\u8fd9\u91cc\u5f62\u6210\u53ef\u8bc4\u5ba1\u7684\u4ea4\u4ed8\u7269\u5217\u8868\u3002";

type DeliverableListPanelProps = {
  deliverables: DeliverableSummary[];
  generatedAt?: string | null;
  selectedDeliverableId: string | null;
  onSelectDeliverable: (deliverableId: string) => void;
};

export function DeliverableListPanel(props: DeliverableListPanelProps) {
  return (
    <section
      className="border-b border-[#333333] pb-5"
      data-testid="deliverable-light-list"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-zinc-100">{TITLE}</h3>
          <p className="mt-1 text-sm leading-6 text-zinc-400">{DESCRIPTION}</p>
        </div>
        <StatusBadge
          label={
            props.generatedAt
              ? `${REFRESH_PREFIX} ${formatDateTime(props.generatedAt)}`
              : WAITING_REFRESH
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
          {EMPTY_TEXT}
        </div>
      )}
    </section>
  );
}
