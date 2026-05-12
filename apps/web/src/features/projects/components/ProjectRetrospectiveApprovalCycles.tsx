import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import {
  APPROVAL_ACTION_LABELS,
  APPROVAL_STATUS_LABELS,
  PROJECT_APPROVAL_CYCLE_STATUS_LABELS,
  type ProjectRetrospectiveApprovalCycle,
} from "../../approvals/types";
import { PROJECT_STAGE_LABELS } from "../types";
import {
  mapApprovalTone,
  mapCycleTone,
  mapDecisionTone,
  ProjectRetrospectiveTagList,
} from "./ProjectRetrospectiveShared";

export function ProjectRetrospectiveApprovalCycles(props: {
  projectId: string;
  generatedAt: string;
  approvalCycles: ProjectRetrospectiveApprovalCycle[];
  onNavigateToApproval?: (input: { projectId: string; approvalId: string }) => void;
}) {
  return (
    <section className="border-b border-[#333333] pb-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-lg font-semibold text-zinc-50">审批返工回路</div>
          <div className="mt-1 text-sm leading-6 text-zinc-500">
            聚焦所有被驳回或要求补充的审批，并标记它们目前处于待返工、返工中、已重提还是返工后通过。
          </div>
        </div>
        <div className="text-sm text-zinc-500">
          生成时间：{formatDateTime(props.generatedAt)}
        </div>
      </div>

      {props.approvalCycles.length > 0 ? (
        <div className="mt-4 divide-y divide-[#333333] border-y border-[#333333]">
          {props.approvalCycles.map((cycle) => (
            <ProjectRetrospectiveApprovalCycleCard
              key={cycle.cycle_id}
              projectId={props.projectId}
              cycle={cycle}
              onNavigateToApproval={props.onNavigateToApproval}
            />
          ))}
        </div>
      ) : (
        <div className="mt-4 border-y border-dashed border-[#333333] py-6 text-sm leading-6 text-zinc-500">
          当前项目还没有形成审批返工回路，说明审批暂未被驳回，或尚未提交审批。
        </div>
      )}
    </section>
  );
}

function ProjectRetrospectiveApprovalCycleCard(props: {
  projectId: string;
  cycle: ProjectRetrospectiveApprovalCycle;
  onNavigateToApproval?: (input: { projectId: string; approvalId: string }) => void;
}) {
  const cycle = props.cycle;
  const latestApprovalId = cycle.latest_approval_id;
  const canNavigateToLatestApproval =
    latestApprovalId && latestApprovalId !== cycle.approval_id;

  return (
    <article className="px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge
              label={PROJECT_APPROVAL_CYCLE_STATUS_LABELS[cycle.status]}
              tone={mapCycleTone(cycle.status)}
            />
            <StatusBadge
              label={APPROVAL_ACTION_LABELS[cycle.decision_action]}
              tone={mapDecisionTone(cycle.decision_action)}
            />
            <StatusBadge
              label={PROJECT_STAGE_LABELS[cycle.deliverable_stage] ?? cycle.deliverable_stage}
              tone="info"
            />
            <StatusBadge
              label={`v${cycle.deliverable_version_number} -> v${cycle.current_version_number}`}
              tone="neutral"
            />
            {cycle.latest_approval_status ? (
              <StatusBadge
                label={APPROVAL_STATUS_LABELS[cycle.latest_approval_status]}
                tone={mapApprovalTone(cycle.latest_approval_status)}
              />
            ) : null}
          </div>
          <div className="mt-3 text-lg font-semibold text-zinc-50">
            {cycle.deliverable_title}
          </div>
          <p className="mt-2 text-sm leading-6 text-zinc-300">{cycle.summary}</p>
          {cycle.comment ? (
            <p className="mt-2 text-sm leading-6 text-zinc-400">{cycle.comment}</p>
          ) : null}
        </div>
        <div className="text-right text-xs text-zinc-500">
          <div>驳回时间：{formatDateTime(cycle.decided_at)}</div>
          {cycle.resubmitted_at ? (
            <div className="mt-1">
              最近重提：{formatDateTime(cycle.resubmitted_at)}
            </div>
          ) : null}
        </div>
      </div>

      {cycle.requested_changes.length > 0 ? (
        <ProjectRetrospectiveTagList
          title="改动方向"
          items={cycle.requested_changes}
          tone="info"
        />
      ) : null}
      {cycle.highlighted_risks.length > 0 ? (
        <ProjectRetrospectiveTagList
          title="关键风险"
          items={cycle.highlighted_risks}
          tone="warning"
        />
      ) : null}

      <div className="mt-4 flex flex-wrap gap-3">
        {props.onNavigateToApproval ? (
          <button
            type="button"
            onClick={() =>
              props.onNavigateToApproval?.({
                projectId: props.projectId,
                approvalId: cycle.approval_id,
              })
            }
            className="rounded border border-[#3a3a3a] bg-transparent px-4 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
          >
            查看原审批
          </button>
        ) : null}
        {props.onNavigateToApproval && canNavigateToLatestApproval ? (
          <button
            type="button"
            onClick={() =>
              props.onNavigateToApproval?.({
                projectId: props.projectId,
                approvalId: latestApprovalId,
              })
            }
            className="rounded border border-[#3a3a3a] bg-transparent px-4 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
          >
            查看最新重提
          </button>
        ) : null}
      </div>
    </article>
  );
}
