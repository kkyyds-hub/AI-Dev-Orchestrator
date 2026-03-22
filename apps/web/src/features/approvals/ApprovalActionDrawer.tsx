import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { DELIVERABLE_TYPE_LABELS } from "../deliverables/types";
import { PROJECT_STAGE_LABELS } from "../projects/types";
import { ROLE_CODE_LABELS } from "../roles/types";
import { ApprovalHistoryPanel } from "./ApprovalHistoryPanel";
import { useApprovalDetail, useApplyApprovalAction } from "./hooks";
import type { ApprovalAction, ApprovalDetail } from "./types";
import { APPROVAL_ACTION_LABELS, APPROVAL_STATUS_LABELS } from "./types";

type ApprovalActionDrawerProps = {
  open: boolean;
  approvalId: string | null;
  projectId: string | null;
  projectName: string | null;
  onClose: () => void;
};

export function ApprovalActionDrawer(props: ApprovalActionDrawerProps) {
  const detailQuery = useApprovalDetail(props.approvalId, props.open);
  const actionMutation = useApplyApprovalAction(props.projectId, props.approvalId);

  const [selectedAction, setSelectedAction] = useState<ApprovalAction>("approve");
  const [actorName, setActorName] = useState("老板");
  const [summary, setSummary] = useState("");
  const [comment, setComment] = useState("");
  const [highlightedRisksText, setHighlightedRisksText] = useState("");
  const [requestedChangesText, setRequestedChangesText] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!props.open) {
      setSelectedAction("approve");
      setActorName("老板");
      setSummary("");
      setComment("");
      setHighlightedRisksText("");
      setRequestedChangesText("");
      setErrorMessage(null);
    }
  }, [props.open, props.approvalId]);

  const detail = detailQuery.data ?? null;
  const canAct = detail?.status === "pending_approval";
  const title = detail?.deliverable_title ?? "审批项";
  const versionLabel = detail ? `v${detail.deliverable_version_number}` : null;
  const formId = "approval-action-form";

  const selectedActionDescription = useMemo(() => {
    switch (selectedAction) {
      case "approve":
        return "确认该版本可以通过老板闸门并允许后续阶段继续推进。";
      case "reject":
        return "明确驳回当前版本，要求下游先处理结论后再继续。";
      case "request_changes":
        return "记录需要补充的信息、风险说明或修改方向。";
      default:
        return "";
    }
  }, [selectedAction]);

  if (!props.open) {
    return null;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canAct) {
      return;
    }

    const normalizedSummary = summary.trim();
    if (!normalizedSummary) {
      setErrorMessage("请先填写本次审批结论摘要。");
      return;
    }

    setErrorMessage(null);
    try {
      await actionMutation.mutateAsync({
        action: selectedAction,
        actor_name: actorName.trim() || "老板",
        summary: normalizedSummary,
        comment: comment.trim() ? comment.trim() : null,
        highlighted_risks: parseLineItems(highlightedRisksText),
        requested_changes: parseLineItems(requestedChangesText),
      });
      props.onClose();
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "审批动作提交失败，请稍后重试。",
      );
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/75 backdrop-blur-sm">
      <button
        type="button"
        aria-label="关闭审批抽屉"
        className="flex-1 cursor-default"
        onClick={props.onClose}
      />

      <aside className="flex h-full w-full max-w-3xl flex-col border-l border-slate-800 bg-slate-950 shadow-2xl shadow-slate-950/70">
        <header className="border-b border-slate-800 px-6 py-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-xs uppercase tracking-[0.24em] text-cyan-300">
                Day10 Approval Gate
              </div>
              <h2 className="mt-2 text-2xl font-semibold text-slate-50">{title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                项目：<span className="font-medium text-slate-100">{props.projectName ?? "未选择项目"}</span>
              </p>
            </div>

            {detail ? (
              <div className="flex flex-wrap gap-2">
                {versionLabel ? <StatusBadge label={versionLabel} tone="info" /> : null}
                <StatusBadge
                  label={
                    APPROVAL_STATUS_LABELS[detail.status] ?? detail.status
                  }
                  tone={mapApprovalTone(detail.status)}
                />
                {detail.overdue ? <StatusBadge label="已超时" tone="danger" /> : null}
              </div>
            ) : null}
          </div>
        </header>

        <div className="flex-1 overflow-y-auto">
          {detailQuery.isLoading && !detail ? (
            <div className="px-6 py-8 text-sm leading-6 text-slate-400">
              正在加载审批详情...
            </div>
          ) : detailQuery.isError ? (
            <div className="px-6 py-8 text-sm leading-6 text-rose-200">
              审批详情加载失败：{detailQuery.error.message}
            </div>
          ) : detail ? (
            <form id={formId} onSubmit={handleSubmit} className="space-y-6 px-6 py-6">
              <section className="grid gap-4 lg:grid-cols-2">
                <FieldCard label="交付件快照" description="审批请求固定绑定到一个具体版本，便于后续回放。">
                  <div className="space-y-3 text-sm leading-6 text-slate-300">
                    <div className="flex flex-wrap gap-2">
                      <StatusBadge
                        label={
                          DELIVERABLE_TYPE_LABELS[
                            detail.deliverable_type as keyof typeof DELIVERABLE_TYPE_LABELS
                          ] ?? detail.deliverable_type
                        }
                        tone="info"
                      />
                      <StatusBadge
                        label={
                          PROJECT_STAGE_LABELS[detail.deliverable_stage] ??
                          detail.deliverable_stage
                        }
                        tone="neutral"
                      />
                    </div>
                    <div>版本：v{detail.deliverable_version_number}</div>
                    <div>
                      发起角色：
                      {ROLE_CODE_LABELS[detail.requester_role_code] ?? detail.requester_role_code}
                    </div>
                    <div>发起时间：{formatDateTime(detail.requested_at)}</div>
                    <div>截止时间：{formatDateTime(detail.due_at)}</div>
                  </div>
                </FieldCard>

                <FieldCard label="请求说明" description="这里记录为什么要在当前节点触发老板审批。">
                  <div className="space-y-3 text-sm leading-6 text-slate-300">
                    <p>{detail.request_note ?? "本次未附加额外说明。"}</p>
                    {detail.latest_summary ? (
                      <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-3 text-sm text-slate-200">
                        最近结论：{detail.latest_summary}
                      </div>
                    ) : (
                      <div className="rounded-xl border border-dashed border-slate-700 bg-slate-950/40 px-3 py-3 text-sm text-slate-400">
                        当前还没有老板审批动作。
                      </div>
                    )}
                  </div>
                </FieldCard>
              </section>

              {canAct ? (
                <>
                  <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                    <div className="text-sm font-medium text-slate-100">选择审批动作</div>
                    <div className="mt-1 text-xs leading-5 text-slate-400">
                      {selectedActionDescription}
                    </div>

                    <div className="mt-4 flex flex-wrap gap-3">
                      {(
                        [
                          ["approve", "success"],
                          ["request_changes", "warning"],
                          ["reject", "danger"],
                        ] as const
                      ).map(([action, tone]) => {
                        const active = selectedAction === action;
                        return (
                          <button
                            key={action}
                            type="button"
                            onClick={() => setSelectedAction(action)}
                            className={`rounded-xl border px-4 py-2 text-sm font-medium transition ${
                              active
                                ? tone === "success"
                                  ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-100"
                                  : tone === "warning"
                                    ? "border-amber-400/40 bg-amber-500/10 text-amber-100"
                                    : "border-rose-400/40 bg-rose-500/10 text-rose-100"
                                : "border-slate-700 bg-slate-950/60 text-slate-300 hover:border-slate-500"
                            }`}
                          >
                            {APPROVAL_ACTION_LABELS[action]}
                          </button>
                        );
                      })}
                    </div>
                  </section>

                  <section className="grid gap-4 lg:grid-cols-2">
                    <FieldCard label="决策人" description="当前仓库尚未接入账号体系，先记录显式名字。">
                      <input
                        value={actorName}
                        onChange={(event) => setActorName(event.target.value)}
                        className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-400"
                      />
                    </FieldCard>

                    <FieldCard label="结论摘要" description="会作为审批队列中的主摘要与后续回放标题。">
                      <input
                        value={summary}
                        onChange={(event) => setSummary(event.target.value)}
                        placeholder="例如：PRD 范围清晰，可进入执行阶段"
                        className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-400"
                      />
                    </FieldCard>
                  </section>

                  <FieldCard label="补充说明" description="记录老板对范围、节奏、风险或约束的具体判断。">
                    <textarea
                      value={comment}
                      onChange={(event) => setComment(event.target.value)}
                      rows={4}
                      className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-400"
                    />
                  </FieldCard>

                  <section className="grid gap-4 lg:grid-cols-2">
                    <FieldCard label="重点风险" description="按行填写，适合沉淀审批关注点。">
                      <textarea
                        value={highlightedRisksText}
                        onChange={(event) => setHighlightedRisksText(event.target.value)}
                        rows={5}
                        placeholder="例如：\n上线窗口过窄\n消息中心接口限流"
                        className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-400"
                      />
                    </FieldCard>

                    <FieldCard label="要求补充项" description="驳回或要求补充时可按行记录具体改动。">
                      <textarea
                        value={requestedChangesText}
                        onChange={(event) => setRequestedChangesText(event.target.value)}
                        rows={5}
                        placeholder="例如：\n补充验收口径\n明确兼容旧接口策略"
                        className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-400"
                      />
                    </FieldCard>
                  </section>
                </>
              ) : (
                <div className="rounded-2xl border border-slate-800 bg-slate-900/60 px-4 py-4 text-sm leading-6 text-slate-300">
                  当前审批已结束，抽屉保留为回放视图；如需再次送审，请先提交交付件新版本后重新发起审批。
                </div>
              )}

              <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-slate-100">审批回放</div>
                    <div className="mt-1 text-xs leading-5 text-slate-400">
                      结构化记录老板每一次决策动作与理由。
                    </div>
                  </div>
                  <StatusBadge
                    label={`${detail.decisions.length} 条动作`}
                    tone={detail.decisions.length > 0 ? "info" : "neutral"}
                  />
                </div>

                {detail.decisions.length > 0 ? (
                  <div className="mt-4 space-y-4">
                    {detail.decisions.map((decision) => (
                      <div
                        key={decision.id}
                        className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-4"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <StatusBadge
                              label={APPROVAL_ACTION_LABELS[decision.action]}
                              tone={mapDecisionTone(decision.action)}
                            />
                            <StatusBadge label={decision.actor_name} tone="neutral" />
                          </div>
                          <div className="text-xs text-slate-500">
                            {formatDateTime(decision.created_at)}
                          </div>
                        </div>

                        <div className="mt-3 text-sm font-medium text-slate-100">
                          {decision.summary}
                        </div>
                        {decision.comment ? (
                          <p className="mt-2 text-sm leading-6 text-slate-300">
                            {decision.comment}
                          </p>
                        ) : null}

                        {decision.highlighted_risks.length > 0 ? (
                          <ReplayList
                            title="重点风险"
                            items={decision.highlighted_risks}
                            tone="warning"
                          />
                        ) : null}

                        {decision.requested_changes.length > 0 ? (
                          <ReplayList
                            title="要求补充项"
                            items={decision.requested_changes}
                            tone="info"
                          />
                        ) : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 px-4 py-4 text-sm leading-6 text-slate-400">
                    暂无审批动作，等待老板首次给出决策。
                  </div>
                )}
              </section>

              <ApprovalHistoryPanel approvalId={props.approvalId} open={props.open} />

              {errorMessage ? (
                <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
                  {errorMessage}
                </div>
              ) : null}
            </form>
          ) : null}
        </div>

        <footer className="flex items-center justify-between gap-3 border-t border-slate-800 px-6 py-4">
          <button
            type="button"
            onClick={props.onClose}
            className="rounded-xl border border-slate-700 px-4 py-2 text-sm font-medium text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
          >
            关闭
          </button>

          {canAct ? (
            <button
              type="submit"
              form={formId}
              disabled={actionMutation.isPending || detailQuery.isLoading}
              className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900 disabled:text-slate-500"
            >
              {actionMutation.isPending ? "提交中..." : "提交审批动作"}
            </button>
          ) : null}
        </footer>
      </aside>
    </div>
  );
}

function FieldCard(props: {
  label: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="text-sm font-medium text-slate-100">{props.label}</div>
      <div className="mt-1 text-xs leading-5 text-slate-400">{props.description}</div>
      <div className="mt-3">{props.children}</div>
    </section>
  );
}

function ReplayList(props: {
  title: string;
  items: string[];
  tone: "info" | "warning";
}) {
  return (
    <div className="mt-4">
      <div className="text-xs uppercase tracking-[0.16em] text-slate-500">
        {props.title}
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        {props.items.map((item) => (
          <StatusBadge key={item} label={item} tone={props.tone} />
        ))}
      </div>
    </div>
  );
}

function mapApprovalTone(status: ApprovalDetail["status"]) {
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

function mapDecisionTone(action: ApprovalAction) {
  switch (action) {
    case "approve":
      return "success";
    case "reject":
      return "danger";
    case "request_changes":
      return "warning";
    default:
      return "neutral";
  }
}

function parseLineItems(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter((item, index, collection) => item.length > 0 && collection.indexOf(item) === index);
}
