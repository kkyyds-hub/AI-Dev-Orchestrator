import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import { PROJECT_STAGE_LABELS } from "../../projects/types";
import { ROLE_CODE_LABELS } from "../../roles/types";
import { DELIVERABLE_TYPE_LABELS, type DeliverableSummary } from "../types";
import { DeliverableVersionMiniInfo } from "./DeliverableVersionMiniInfo";

type DeliverableVersionHeaderProps = {
  deliverable: DeliverableSummary;
};

export function DeliverableVersionHeader(props: DeliverableVersionHeaderProps) {
  return (
    <header className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-lg font-semibold text-zinc-100">
            {props.deliverable.title}
          </h3>
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
        <p className="mt-2 text-sm leading-6 text-zinc-400">
          创建角色：
          {ROLE_CODE_LABELS[props.deliverable.created_by_role_code] ??
            props.deliverable.created_by_role_code}
          ，当前版本 v{props.deliverable.current_version_number}，累计
          {props.deliverable.total_versions} 个快照。
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <DeliverableVersionMiniInfo
          label="创建时间"
          value={formatDateTime(props.deliverable.created_at)}
        />
        <DeliverableVersionMiniInfo
          label="最近更新"
          value={formatDateTime(props.deliverable.updated_at)}
        />
      </div>
    </header>
  );
}
