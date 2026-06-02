import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import { PROJECT_STAGE_LABELS } from "../../projects/types";
import { ROLE_CODE_LABELS } from "../../roles/types";
import {
  DELIVERABLE_STATUS_LABELS,
  DELIVERABLE_STATUS_TONES,
  DELIVERABLE_TYPE_LABELS,
  type DeliverableSummary,
} from "../types";

const EMPTY_SUMMARY = "\u6682\u65e0\u4ea4\u4ed8\u6458\u8981\u3002";
const VERSION_COUNT_SUFFIX = "\u4e2a\u7248\u672c";
const UPDATED_PREFIX = "\u66f4\u65b0\u4e8e";

type DeliverableCardButtonProps = {
  deliverable: DeliverableSummary;
  selected: boolean;
  onSelect: () => void;
};

export function DeliverableCardButton(props: DeliverableCardButtonProps) {
  const deliverable = props.deliverable;

  return (
    <button
      type="button"
      onClick={props.onSelect}
      data-testid="deliverable-list-item"
      className={`w-full border-l-2 px-4 py-4 text-left transition ${
        props.selected
          ? "border-l-zinc-300 bg-white/[0.04]"
          : "border-l-transparent hover:border-l-[#555555] hover:bg-white/[0.02]"
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <div className="min-w-0 flex-1 text-sm font-medium text-zinc-100">
          {deliverable.title}
        </div>
        <StatusBadge
          label={DELIVERABLE_STATUS_LABELS[deliverable.status] ?? deliverable.status}
          tone={DELIVERABLE_STATUS_TONES[deliverable.status] ?? "neutral"}
        />
        <StatusBadge
          label={DELIVERABLE_TYPE_LABELS[deliverable.type] ?? deliverable.type}
          tone="info"
        />
      </div>

      <p className="mt-3 line-clamp-3 text-sm leading-6 text-zinc-400">
        {deliverable.summary || deliverable.latest_version.summary || EMPTY_SUMMARY}
      </p>

      <div className="mt-3 flex flex-wrap gap-2 text-xs text-zinc-500">
        <span>v{deliverable.version_no}</span>
        <span>{deliverable.total_versions} {VERSION_COUNT_SUFFIX}</span>
        <span>
          {PROJECT_STAGE_LABELS[deliverable.stage] ?? deliverable.stage}
        </span>
        <span>
          {ROLE_CODE_LABELS[deliverable.created_by] ??
            ROLE_CODE_LABELS[deliverable.created_by_role_code] ??
            deliverable.created_by}
        </span>
        <span>{UPDATED_PREFIX} {formatDateTime(deliverable.updated_at)}</span>
      </div>
    </button>
  );
}
