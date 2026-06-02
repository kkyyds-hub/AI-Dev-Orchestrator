import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import {
  DELIVERABLE_TYPE_LABELS,
  type DeliverableSummary,
} from "../deliverables/types";
import { useProjectDeliverableSnapshot } from "../deliverables/hooks";
import { ProjectSubviewTabs } from "../projects/components/ProjectSubviewTabs";
import { PROJECT_STAGE_LABELS } from "../projects/types";
import { ROLE_CODE_LABELS } from "../roles/types";
import { ApprovalActionDrawer } from "./ApprovalActionDrawer";
import { RepositoryPreflightPanel } from "./RepositoryPreflightPanel";
import { RepositoryReleaseGatePanel } from "./RepositoryReleaseGatePanel";
import { useCreateApprovalRequest, useProjectApprovalInbox } from "./hooks";
import type { ApprovalQueueItem } from "./types";
import { APPROVAL_STATUS_LABELS } from "./types";

type ApprovalInboxPageProps = {
  projectId: string | null;
  projectName: string | null;
  requestedApprovalId?: string | null;
  onRequestedApprovalHandled?: () => void;
};

export function ApprovalInboxPage(props: ApprovalInboxPageProps) {
  const inboxQuery = useProjectApprovalInbox(props.projectId);
  const deliverableSnapshotQuery = useProjectDeliverableSnapshot(props.projectId);
  const createMutation = useCreateApprovalRequest(props.projectId);

  const [selectedDeliverableId, setSelectedDeliverableId] = useState<string>("");
  const [requesterRoleCode, setRequesterRoleCode] = useState("product_manager");
  const [dueHoursText, setDueHoursText] = useState("24");
  const [requestNote, setRequestNote] = useState("");
  const [feedback, setFeedback] = useState<{
    tone: "success" | "warning" | "danger";
    text: string;
  } | null>(null);
  const [selectedApprovalId, setSelectedApprovalId] = useState<string | null>(null);

  const rawApprovals = inboxQuery.data?.approvals ?? [];
  const approvals = useMemo(
    () => sortApprovalsByHandlingPriority(rawApprovals),
    [rawApprovals],
  );
  const deliverables = deliverableSnapshotQuery.data?.deliverables ?? [];

  const latestApprovalByDeliverable = useMemo(() => {
    const mapping = new Map<string, ApprovalQueueItem>();
    approvals.forEach((approval) => {
      if (!mapping.has(approval.deliverable_id)) {
        mapping.set(approval.deliverable_id, approval);
      }
    });
    return mapping;
  }, [approvals]);

  const eligibleDeliverables = useMemo(() => {
    return deliverables.filter((deliverable) => {
      const latestApproval = latestApprovalByDeliverable.get(deliverable.id);
      if (!latestApproval) {
        return true;
      }

      return latestApproval.deliverable_version_number !== deliverable.current_version_number;
    });
  }, [deliverables, latestApprovalByDeliverable]);

  const selectedDeliverable = useMemo<DeliverableSummary | null>(
    () =>
      eligibleDeliverables.find((deliverable) => deliverable.id === selectedDeliverableId) ??
      null,
    [eligibleDeliverables, selectedDeliverableId],
  );

  useEffect(() => {
    if (!eligibleDeliverables.length) {
      if (selectedDeliverableId) {
        setSelectedDeliverableId("");
      }
      return;
    }

    const stillExists = eligibleDeliverables.some(
      (deliverable) => deliverable.id === selectedDeliverableId,
    );
    if (!selectedDeliverableId || !stillExists) {
      setSelectedDeliverableId(eligibleDeliverables[0].id);
    }
  }, [eligibleDeliverables, selectedDeliverableId]);

  useEffect(() => {
    if (!selectedDeliverable) {
      return;
    }

    setRequesterRoleCode(selectedDeliverable.created_by_role_code);
  }, [selectedDeliverable]);

  useEffect(() => {
    if (!props.requestedApprovalId) {
      return;
    }

    const exists = approvals.some((approval) => approval.id === props.requestedApprovalId);
    if (!exists) {
      return;
    }

    setSelectedApprovalId(props.requestedApprovalId);
    props.onRequestedApprovalHandled?.();
  }, [approvals, props.onRequestedApprovalHandled, props.requestedApprovalId]);

  if (!props.projectId) {
    return (
      <section className="border-b border-[#333333] pb-6">
        <div className="text-lg font-semibold text-zinc-100">审批中心</div>
        <p className="mt-3 text-sm leading-6 text-zinc-400">
          请先在上方选择项目，再查看审批队列与审批处理状态。
        </p>
      </section>
    );
  }

  const overdueApprovals = approvals.filter(
    (approval) => approval.status === "pending_approval" && approval.overdue,
  );

  const handleCreateRequest = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedDeliverable) {
      setFeedback({
        tone: "warning",
        text: "当前没有可送审的交付件，请先生成新版本后再发起审批。",
      });
      return;
    }

    const dueInHours = Number(dueHoursText);
    if (!Number.isFinite(dueInHours) || dueInHours < 0) {
      setFeedback({
        tone: "danger",
        text: "审批截止时长必须是大于等于 0 的数字。",
      });
      return;
    }

    setFeedback(null);
    try {
      const detail = await createMutation.mutateAsync({
        deliverable_id: selectedDeliverable.id,
        requester_role_code: requesterRoleCode,
        request_note: requestNote.trim() ? requestNote.trim() : null,
        due_in_hours: dueInHours,
      });
      setRequestNote("");
      setFeedback({
        tone: "success",
        text: `已为《${detail.deliverable_title}》v${detail.deliverable_version_number} 发起审批。`,
      });
    } catch (error) {
      setFeedback({
        tone: "danger",
        text: error instanceof Error ? error.message : "发起审批失败，请稍后重试。",
      });
    }
  };

  return (
    <div className="project-quiet-workspace">
      <ProjectSubviewTabs
        ariaLabel="项目审批视图"
      defaultTabId="approval-inbox"
      items={[
        {
          id: "approval-inbox",
          label: "审批队列",
          panelId: "approval-inbox-tab-panel",
          content: (
            <>
              <section
        id="approval-inbox"
        data-testid="approval-inbox-section"
        className="scroll-mt-24 border-b border-[#333333] pb-6"
      >
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">审批处理</h2>
            <p className="mt-1 text-sm leading-6 text-zinc-400">
              在关键交付件上引入显式审批，支持批准、驳回、要求补充，并把意见结构化沉淀为可回放记录。
            </p>
          </div>
          <div className="text-xs text-zinc-500">
            当前项目：{props.projectName ?? "未命名项目"}
          </div>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-4">
          <ApprovalStat
            label="审批总数"
            value={String(inboxQuery.data?.total_requests ?? 0)}
          />
          <ApprovalStat
            label="待审批"
            value={String(inboxQuery.data?.pending_requests ?? 0)}
          />
          <ApprovalStat
            label="超时项"
            value={String(inboxQuery.data?.overdue_requests ?? 0)}
          />
          <ApprovalStat
            label="已结束"
            value={String(inboxQuery.data?.completed_requests ?? 0)}
          />
        </div>

        <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
          <form
            onSubmit={handleCreateRequest}
            className="border-b border-[#333333] pb-4"
          >
            <div className="text-sm font-medium text-zinc-100">发起审批</div>
            <div className="mt-1 text-xs leading-5 text-zinc-400">
              先选择当前版本的交付件，再发起审批。
            </div>

            <div className="mt-4 space-y-4">
              <FieldBlock label="选择交付件">
                <select
                  value={selectedDeliverableId}
                  onChange={(event) => setSelectedDeliverableId(event.target.value)}
                  disabled={!eligibleDeliverables.length || createMutation.isPending}
                  className="w-full rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm leading-6 text-zinc-200 outline-none transition focus:border-[#6a6a6a] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {eligibleDeliverables.length > 0 ? (
                    eligibleDeliverables.map((deliverable) => (
                      <option key={deliverable.id} value={deliverable.id}>
                        {deliverable.title} · v{deliverable.current_version_number}
                      </option>
                    ))
                  ) : (
                    <option value="">暂无可送审的新版本交付件</option>
                  )}
                </select>
              </FieldBlock>

              <div className="grid gap-4 md:grid-cols-2">
                <FieldBlock label="发起角色">
                  <select
                    value={requesterRoleCode}
                    onChange={(event) => setRequesterRoleCode(event.target.value)}
                    disabled={createMutation.isPending}
                    className="w-full rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm leading-6 text-zinc-200 outline-none transition focus:border-[#6a6a6a]"
                  >
                    {Object.entries(ROLE_CODE_LABELS).map(([roleCode, label]) => (
                      <option key={roleCode} value={roleCode}>
                        {label}
                      </option>
                    ))}
                  </select>
                </FieldBlock>

                <FieldBlock label="截止时长（小时）">
                  <input
                    value={dueHoursText}
                    onChange={(event) => setDueHoursText(event.target.value)}
                    inputMode="decimal"
                    className="w-full rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm leading-6 text-zinc-200 outline-none transition focus:border-[#6a6a6a]"
                  />
                </FieldBlock>
              </div>

              {selectedDeliverable ? (
                <div className="border-l border-[#333333] px-4 py-3 text-sm leading-6 text-zinc-400">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge
                      label={
                        DELIVERABLE_TYPE_LABELS[
                          selectedDeliverable.type as keyof typeof DELIVERABLE_TYPE_LABELS
                        ] ?? selectedDeliverable.type
                      }
                      tone="info"
                    />
                    <StatusBadge
                      label={
                        PROJECT_STAGE_LABELS[selectedDeliverable.stage] ??
                        selectedDeliverable.stage
                      }
                      tone="neutral"
                    />
                    <StatusBadge
                      label={`v${selectedDeliverable.current_version_number}`}
                      tone="success"
                    />
                  </div>
                  <div className="mt-3">
                    创建角色：
                    {ROLE_CODE_LABELS[selectedDeliverable.created_by_role_code] ??
                      selectedDeliverable.created_by_role_code}
                  </div>
                  <div className="mt-1">
                    最近更新：{formatDateTime(selectedDeliverable.updated_at)}
                  </div>
                </div>
              ) : null}

              <FieldBlock label="审批说明">
                <textarea
                  value={requestNote}
                  onChange={(event) => setRequestNote(event.target.value)}
                  rows={4}
                  placeholder="例如：请确认 PRD 的业务范围、优先级和验收口径是否可以进入执行阶段。"
                  className="w-full rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm leading-6 text-zinc-200 outline-none transition focus:border-[#6a6a6a]"
                />
              </FieldBlock>

              {feedback ? (
                <div
                  className={`rounded border px-4 py-3 text-sm leading-6 ${
                    feedback.tone === "success"
                      ? "border-emerald-500/30 bg-transparent text-emerald-200"
                      : feedback.tone === "warning"
                        ? "border-amber-500/30 bg-transparent text-amber-200"
                        : "border-rose-500/30 bg-transparent text-rose-200"
                  }`}
                >
                  {feedback.text}
                </div>
              ) : null}

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={!eligibleDeliverables.length || createMutation.isPending}
                  className="rounded border border-[#4a4a4a] bg-transparent px-4 py-2 text-sm font-medium text-zinc-100 transition hover:bg-[#292929] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {createMutation.isPending ? "发起中..." : "发起审批"}
                </button>
              </div>
            </div>
          </form>

          <section className="border-b border-[#333333] pb-4">
            <div className="text-sm font-medium text-zinc-100">超时审批提醒</div>
            <div className="mt-1 text-xs leading-5 text-zinc-400">
              这里聚焦所有已经超过截止时间、但仍未完成处理的审批项。
            </div>

            {overdueApprovals.length > 0 ? (
              <div className="mt-4 space-y-3">
                {overdueApprovals.map((approval) => (
                  <ApprovalHighlight
                    key={approval.id}
                    approval={approval}
                    onOpen={() => setSelectedApprovalId(approval.id)}
                  />
                ))}
              </div>
            ) : (
              <div className="mt-4 border border-dashed border-[#3a3a3a] px-4 py-6 text-sm leading-6 text-zinc-400">
                当前没有超时审批项，可以继续关注下方审批队列。
              </div>
            )}
          </section>
        </div>

        <section className="mt-6 border-b border-[#333333] pb-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-zinc-100">审批队列</div>
              <div className="mt-1 text-xs leading-5 text-zinc-400">
                按处理优先级展示：待审批超时 &gt; 待审批未超时 &gt; 需补充 &gt; 已驳回 &gt; 已通过；同组内按发起时间倒序，并保留审批记录回放入口。
              </div>
            </div>
            <div className="text-xs text-zinc-500">
              刷新时间：{formatDateTime(inboxQuery.data?.generated_at ?? null)}
            </div>
          </div>

          {inboxQuery.isLoading && !inboxQuery.data ? (
            <div className="mt-4 text-sm leading-6 text-zinc-400">正在加载审批队列...</div>
          ) : inboxQuery.isError ? (
            <div className="mt-4 text-sm leading-6 text-rose-200">
              审批队列加载失败：{inboxQuery.error.message}
            </div>
          ) : approvals.length > 0 ? (
            <div className="mt-4 divide-y divide-[#333333]" data-testid="approval-queue-list">
              {approvals.map((approval) => (
                <ApprovalQueueCard
                  key={approval.id}
                  approval={approval}
                  onOpen={() => setSelectedApprovalId(approval.id)}
                />
              ))}
            </div>
          ) : (
            <div className="mt-4 border border-dashed border-[#3a3a3a] px-4 py-6 text-sm leading-6 text-zinc-400">
              当前项目还没有发起过审批请求；可以先从左侧选中交付件并送审。
            </div>
          )}
        </section>
      </section>

              <ApprovalActionDrawer
                open={selectedApprovalId !== null}
                approvalId={selectedApprovalId}
                projectId={props.projectId}
                projectName={props.projectName}
                onClose={() => setSelectedApprovalId(null)}
              />
            </>
          ),
        },
        {
          id: "preflight",
          label: "预检",
          panelId: "repository-preflight-tab-panel",
          content: (
            <>
              <MigrationNotice
                testId="approval-preflight-migration-notice"
                title="预检能力后续迁移提示"
                body="预检属于执行中心 / 仓库工作区视角，本阶段仅保留兼容入口并提示职责边界，不迁移现有预检能力。"
              />
              <RepositoryPreflightPanel
                projectId={props.projectId}
                projectName={props.projectName ?? null}
              />
            </>
          ),
        },
        {
          id: "release-gate",
          label: "发布门禁",
          panelId: "repository-release-gate-tab-panel",
          content: (
            <>
              <MigrationNotice
                testId="approval-release-gate-migration-notice"
                title="发布门禁后续迁移提示"
                body="发布门禁属于后续 release gate / 仓库工作区职责，本阶段仅保留兼容入口并提示迁移方向，不迁移发布门禁能力。"
              />
              <RepositoryReleaseGatePanel
                projectId={props.projectId}
                projectName={props.projectName ?? null}
              />
            </>
          ),
        },
        ]}
      />
    </div>
  );
}

function MigrationNotice(props: { testId: string; title: string; body: string }) {
  return (
    <section
      data-testid={props.testId}
      className="mb-5 border-l border-amber-500/50 px-4 py-3 text-sm leading-6 text-amber-100"
    >
      <div className="font-medium">{props.title}</div>
      <p className="mt-1 text-amber-100/80">{props.body}</p>
    </section>
  );
}

const APPROVAL_HANDLING_PRIORITY: Record<ApprovalQueueItem["status"], number> = {
  pending_approval: 1,
  changes_requested: 2,
  rejected: 3,
  approved: 4,
};

function getApprovalHandlingPriority(approval: ApprovalQueueItem): number {
  if (approval.status === "pending_approval" && approval.overdue) {
    return 0;
  }

  return APPROVAL_HANDLING_PRIORITY[approval.status] ?? 5;
}

function sortApprovalsByHandlingPriority(
  approvals: ApprovalQueueItem[],
): ApprovalQueueItem[] {
  return [...approvals].sort((a, b) => {
    const priorityDiff =
      getApprovalHandlingPriority(a) - getApprovalHandlingPriority(b);
    if (priorityDiff !== 0) {
      return priorityDiff;
    }

    const requestedAtDiff =
      Date.parse(b.requested_at) - Date.parse(a.requested_at);
    if (requestedAtDiff !== 0 && Number.isFinite(requestedAtDiff)) {
      return requestedAtDiff;
    }

    return a.id.localeCompare(b.id);
  });
}

function ApprovalStat(props: { label: string; value: string }) {
  return (
    <div className="border-l border-[#333333] px-4 py-2">
      <div className="text-xs uppercase tracking-[0.16em] text-zinc-500">{props.label}</div>
      <div className="mt-2 text-sm font-medium text-zinc-100">{props.value}</div>
    </div>
  );
}

function FieldBlock(props: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <div className="mb-2 text-xs uppercase tracking-[0.16em] text-zinc-500">{props.label}</div>
      {props.children}
    </label>
  );
}

function ApprovalHighlight(props: {
  approval: ApprovalQueueItem;
  onOpen: () => void;
}) {
  return (
    <div className="border-l border-rose-500/50 px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-rose-100">
            {props.approval.deliverable_title} · v{props.approval.deliverable_version_number}
          </div>
          <div className="mt-1 text-xs leading-5 text-rose-100/80">
            已超时，截止于 {formatDateTime(props.approval.due_at)}
          </div>
        </div>

        <button
          type="button"
          onClick={props.onOpen}
          className="rounded border border-rose-400/40 px-3 py-2 text-xs font-medium text-rose-100 transition hover:bg-rose-500/10"
        >
          立即处理
        </button>
      </div>
    </div>
  );
}

function ApprovalQueueCard(props: {
  approval: ApprovalQueueItem;
  onOpen: () => void;
}) {
  const typeLabel =
    DELIVERABLE_TYPE_LABELS[
      props.approval.deliverable_type as keyof typeof DELIVERABLE_TYPE_LABELS
    ] ?? props.approval.deliverable_type;

  return (
    <div className="px-0 py-4" data-testid="approval-queue-card">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-zinc-100">
              {props.approval.deliverable_title}
            </span>
            <StatusBadge label={typeLabel} tone="info" />
            <StatusBadge
              label={
                PROJECT_STAGE_LABELS[props.approval.deliverable_stage] ??
                props.approval.deliverable_stage
              }
              tone="neutral"
            />
            <StatusBadge
              label={`v${props.approval.deliverable_version_number}`}
              tone="success"
            />
            <StatusBadge
              label={
                APPROVAL_STATUS_LABELS[props.approval.status] ?? props.approval.status
              }
              tone={mapApprovalTone(props.approval.status)}
            />
            {props.approval.overdue ? <StatusBadge label="已超时" tone="danger" /> : null}
          </div>

          <div className="mt-3 flex flex-wrap gap-3 text-xs text-zinc-500">
            <span>
              发起角色：
              {ROLE_CODE_LABELS[props.approval.requester_role_code] ??
                props.approval.requester_role_code}
            </span>
            <span>发起时间：{formatDateTime(props.approval.requested_at)}</span>
            <span>截止时间：{formatDateTime(props.approval.due_at)}</span>
          </div>

          {props.approval.request_note ? (
            <p className="mt-3 text-sm leading-6 text-zinc-400">
              发起说明：{props.approval.request_note}
            </p>
          ) : null}

          {props.approval.latest_summary ? (
            <p className="mt-2 text-sm leading-6 text-zinc-400">
              最近结论：{props.approval.latest_summary}
            </p>
          ) : (
            <p className="mt-2 text-sm leading-6 text-zinc-400">
              当前尚未形成审批结论。
            </p>
          )}
        </div>

        <div className="flex flex-col items-start gap-3 xl:items-end">
          {props.approval.latest_decision ? (
            <div className="border-l border-[#333333] px-3 py-2 text-xs leading-5 text-zinc-400">
              <div className="text-zinc-200">
                {APPROVAL_STATUS_LABELS[props.approval.status] ?? props.approval.status}
              </div>
              <div className="mt-1">决策人：{props.approval.latest_decision.actor_name}</div>
              <div className="mt-1">
                {formatDateTime(props.approval.latest_decision.created_at)}
              </div>
            </div>
          ) : null}

          <button
            type="button"
            onClick={props.onOpen}
            className="rounded border border-[#4a4a4a] bg-transparent px-3 py-2 text-xs font-medium text-zinc-100 transition hover:bg-[#292929]"
          >
            {props.approval.status === "pending_approval" ? "处理审批" : "查看回放"}
          </button>
        </div>
      </div>
    </div>
  );
}

function mapApprovalTone(status: ApprovalQueueItem["status"]) {
  switch (status) {
    case "approved":
      return "success";
    case "rejected":
      return "danger";
    case "changes_requested":
      return "warning";
    default:
      return "warning";
  }
}
