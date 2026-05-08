import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import { PROJECT_STAGE_LABELS } from "../../projects/types";
import { ROLE_CODE_LABELS } from "../../roles/types";
import { DELIVERABLE_TYPE_LABELS, type DeliverableSummary } from "../types";

type DeliverableCardButtonProps = {
  deliverable: DeliverableSummary;
  selected: boolean;
  onSelect: () => void;
};

export function DeliverableCardButton(props: DeliverableCardButtonProps) {
  return (
    <button
      type="button"
      onClick={props.onSelect}
      className={`w-full border-l-2 px-4 py-4 text-left transition ${
        props.selected
          ? "border-l-zinc-300 bg-white/[0.03]"
          : "border-l-transparent hover:border-l-[#555555] hover:bg-white/[0.02]"
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <div className="text-sm font-medium text-slate-50">
          {props.deliverable.title}
        </div>
        <StatusBadge
          label={DELIVERABLE_TYPE_LABELS[props.deliverable.type]}
          tone="info"
        />
        <StatusBadge
          label={
            PROJECT_STAGE_LABELS[props.deliverable.stage] ??
            props.deliverable.stage
          }
          tone="neutral"
        />
      </div>

      <p className="mt-3 text-sm leading-6 text-slate-300">
        {props.deliverable.latest_version.summary}
      </p>

      <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
        <span>
          提交者{" "}
          {ROLE_CODE_LABELS[
            props.deliverable.latest_version.author_role_code
          ] ?? props.deliverable.latest_version.author_role_code}
        </span>
        <span>v{props.deliverable.current_version_number}</span>
        <span>{props.deliverable.total_versions} 个快照</span>
        <span>更新于 {formatDateTime(props.deliverable.updated_at)}</span>
      </div>
    </button>
  );
}
