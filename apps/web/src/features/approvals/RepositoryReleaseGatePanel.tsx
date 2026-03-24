import { type FormEvent, useEffect, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { RepositoryReleaseChecklist } from "./RepositoryReleaseChecklist";
import {
  useApplyRepositoryReleaseGateAction,
  useProjectRepositoryReleaseGateInbox,
  useRepositoryReleaseGateDetail,
} from "./hooks";
import type {
  ApprovalAction,
  RepositoryReleaseGateDetail,
  RepositoryReleaseGateSummary,
} from "./types";
import { REPOSITORY_RELEASE_GATE_STATUS_LABELS } from "./types";

type RepositoryReleaseGatePanelProps = {
  projectId: string | null;
  projectName: string | null;
};

export function RepositoryReleaseGatePanel(props: RepositoryReleaseGatePanelProps) {
  const inboxQuery = useProjectRepositoryReleaseGateInbox(props.projectId);
  const items = inboxQuery.data?.items ?? [];
  const [selectedChangeBatchId, setSelectedChangeBatchId] = useState<string | null>(null);

  useEffect(() => {
    if (!items.length) {
      setSelectedChangeBatchId(null);
      return;
    }

    const stillExists = items.some((item) => item.change_batch_id === selectedChangeBatchId);
    if (stillExists) {
      return;
    }

    const blockedItem = items.find((item) => item.blocked) ?? null;
    const pendingItem =
      items.find((item) => item.status === "pending_approval") ?? null;
    const preferred = blockedItem ?? pendingItem ?? items[0] ?? null;
    setSelectedChangeBatchId(preferred?.change_batch_id ?? null);
  }, [items, selectedChangeBatchId]);

  const detailQuery = useRepositoryReleaseGateDetail(selectedChangeBatchId, true);

  if (!props.projectId) {
    return (
      <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-xl shadow-slate-950/30">
        <div className="text-lg font-semibold text-slate-50">Day14 审批闸门与放行检查单</div>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          请先在上方选择项目，再查看放行检查单、阻断缺口和审批动作。
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-xl shadow-slate-950/30">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="text-lg font-semibold text-slate-50">Day14 审批闸门与放行检查单</div>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-300">
            汇总仓库绑定、快照、变更计划、风险预检、验证结果、差异证据和提交草案；缺少关键项会显式阻断，
            且审批通过只代表“放行资格成立”，不会自动触发真实 Git 写操作。
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-4">
          <MiniStat label="当前项目" value={props.projectName ?? "未命名项目"} />
          <MiniStat label="批次数" value={String(inboxQuery.data?.total_batches ?? 0)} />
          <MiniStat label="阻断中" value={String(inboxQuery.data?.blocked_batches ?? 0)} />
          <MiniStat label="已通过" value={String(inboxQuery.data?.approved_batches ?? 0)} />
        </div>
      </div>

      {inboxQuery.isLoading && !inboxQuery.data ? (
        <div className="mt-4 text-sm leading-6 text-slate-400">正在加载 Day14 放行检查单...</div>
      ) : null}
      {inboxQuery.isError ? (
        <div className="mt-4 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
          Day14 放行检查单加载失败：{inboxQuery.error.message}
        </div>
      ) : null}

      {items.length > 0 ? (
        <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(320px,0.95fr)_minmax(0,1.25fr)]">
          <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
            <div className="text-sm font-semibold text-slate-50">变更批次放行视图</div>
            <div className="mt-2 text-sm leading-6 text-slate-400">
              每个批次都对应一份 Day14 放行检查单，可切换查看阻断缺口与审批记录。
            </div>

            <div className="mt-4 space-y-3">
              {items.map((item) => (
                <button
                  key={item.change_batch_id}
                  type="button"
                  onClick={() => setSelectedChangeBatchId(item.change_batch_id)}
                  className={`w-full rounded-2xl border px-4 py-4 text-left transition ${
                    item.change_batch_id === selectedChangeBatchId
                      ? "border-cyan-400/40 bg-cyan-500/10"
                      : "border-slate-800 bg-slate-900/60 hover:border-slate-700"
                  }`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="text-sm font-medium text-slate-100">{item.change_batch_title}</div>
                    <StatusBadge
                      label={REPOSITORY_RELEASE_GATE_STATUS_LABELS[item.status] ?? item.status}
                      tone={mapItemTone(item)}
                    />
                    {item.blocked ? <StatusBadge label="阻断" tone="danger" /> : null}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
                    <span>缺口 {item.missing_item_count}</span>
                    <span>审批记录 {item.decision_count}</span>
                    <span>刷新于 {formatDateTime(item.generated_at)}</span>
                  </div>
                </button>
              ))}
            </div>
          </section>

          <section>
            {selectedChangeBatchId ? (
              detailQuery.isLoading && !detailQuery.data ? (
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-8 text-sm leading-6 text-slate-400">
                  正在加载放行检查单详情...
                </div>
              ) : detailQuery.isError ? (
                <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-8 text-sm leading-6 text-rose-100">
                  放行检查单详情加载失败：{detailQuery.error.message}
                </div>
              ) : detailQuery.data ? (
                <RepositoryReleaseGateDetailPanel
                  projectId={props.projectId}
                  detail={detailQuery.data}
                />
              ) : null
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 px-4 py-8 text-sm leading-6 text-slate-400">
                当前项目还没有可查看的放行检查单，请先生成 Day13 提交草案并进入 Day14 审批链路。
              </div>
            )}
          </section>
        </div>
      ) : !inboxQuery.isLoading && !inboxQuery.isError ? (
        <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 px-4 py-8 text-sm leading-6 text-slate-400">
          当前项目暂无 Day14 放行检查单；请先完成 Day07 批次、Day08 预检、Day10 验证和 Day13 提交草案。
        </div>
      ) : null}
    </section>
  );
}

function RepositoryReleaseGateDetailPanel(props: {
  projectId: string;
  detail: RepositoryReleaseGateDetail;
}) {
  const mutation = useApplyRepositoryReleaseGateAction(
    props.projectId,
    props.detail.change_batch_id,
  );

  const [action, setAction] = useState<ApprovalAction>("approve");
  const [actorName, setActorName] = useState("老板");
  const [summary, setSummary] = useState("");
  const [comment, setComment] = useState("");
  const [highlightedRisksText, setHighlightedRisksText] = useState("");
  const [requestedChangesText, setRequestedChangesText] = useState("");
  const [feedback, setFeedback] = useState<{
    tone: "success" | "warning" | "danger";
    text: string;
  } | null>(null);

  useEffect(() => {
    if (props.detail.blocked && action === "approve") {
      setAction("request_changes");
    }
  }, [action, props.detail.blocked]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!summary.trim()) {
      setFeedback({
        tone: "danger",
        text: "请填写审批结论摘要。",
      });
      return;
    }

    if (props.detail.blocked && action === "approve") {
      setFeedback({
        tone: "warning",
        text: "当前检查单仍有关键缺口，不能直接审批通过。",
      });
      return;
    }

    setFeedback(null);
    try {
      const result = await mutation.mutateAsync({
        action,
        actor_name: actorName.trim() || "老板",
        summary: summary.trim(),
        comment: comment.trim() || null,
        highlighted_risks: parseStructuredLines(highlightedRisksText),
        requested_changes: parseStructuredLines(requestedChangesText),
      });

      setSummary("");
      setComment("");
      setHighlightedRisksText("");
      setRequestedChangesText("");
      setFeedback({
        tone: action === "approve" ? "success" : action === "reject" ? "danger" : "warning",
        text:
          action === "approve"
            ? `审批已通过：${result.change_batch_title}，仅表示放行资格成立。`
            : action === "reject"
              ? `已驳回：${result.change_batch_title}。`
              : `已记录补证据意见：${result.change_batch_title}。`,
      });
    } catch (error) {
      setFeedback({
        tone: "danger",
        text: error instanceof Error ? error.message : "审批动作提交失败，请稍后重试。",
      });
    }
  }

  return (
    <div className="space-y-4">
      <RepositoryReleaseChecklist gate={props.detail} />

      <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
        <div className="text-sm font-semibold text-slate-50">审批动作</div>
        <div className="mt-2 text-sm leading-6 text-slate-400">
          可记录通过 / 驳回 / 补证据。注意：审批通过不自动触发真实 `git commit`、`push`、PR 或 `merge`。
        </div>

        <form
          onSubmit={(event) => {
            void handleSubmit(event);
          }}
          className="mt-4 space-y-4"
        >
          <div className="grid gap-4 md:grid-cols-2">
            <label className="block text-sm text-slate-200">
              <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">审批动作</div>
              <select
                value={action}
                onChange={(event) => setAction(event.target.value as ApprovalAction)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400"
              >
                <option value="approve" disabled={props.detail.blocked}>
                  通过
                </option>
                <option value="reject">驳回</option>
                <option value="request_changes">补证据</option>
              </select>
            </label>

            <label className="block text-sm text-slate-200">
              <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">审批人</div>
              <input
                value={actorName}
                onChange={(event) => setActorName(event.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400"
              />
            </label>
          </div>

          <label className="block text-sm text-slate-200">
            <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">结论摘要</div>
            <input
              value={summary}
              onChange={(event) => setSummary(event.target.value)}
              placeholder="例如：缺口已补齐，同意进入下一步人工放行。"
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400"
            />
          </label>

          <label className="block text-sm text-slate-200">
            <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">备注</div>
            <textarea
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              rows={3}
              className="w-full rounded-2xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400"
            />
          </label>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="block text-sm text-slate-200">
              <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">关注风险（每行一条）</div>
              <textarea
                value={highlightedRisksText}
                onChange={(event) => setHighlightedRisksText(event.target.value)}
                rows={4}
                className="w-full rounded-2xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400"
              />
            </label>
            <label className="block text-sm text-slate-200">
              <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">补充事项（每行一条）</div>
              <textarea
                value={requestedChangesText}
                onChange={(event) => setRequestedChangesText(event.target.value)}
                rows={4}
                className="w-full rounded-2xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400"
              />
            </label>
          </div>

          {feedback ? (
            <div
              className={`rounded-xl border px-4 py-3 text-sm leading-6 ${
                feedback.tone === "success"
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-100"
                  : feedback.tone === "warning"
                    ? "border-amber-500/30 bg-amber-500/10 text-amber-100"
                    : "border-rose-500/30 bg-rose-500/10 text-rose-100"
              }`}
            >
              {feedback.text}
            </div>
          ) : null}

          {mutation.isError ? (
            <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
              提交失败：{mutation.error.message}
            </div>
          ) : null}

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={mutation.isPending}
              className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-900 disabled:text-slate-500"
            >
              {mutation.isPending ? "提交中..." : "提交审批动作"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function MiniStat(props: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">{props.label}</div>
      <div className="mt-2 text-sm font-medium text-slate-100">{props.value}</div>
    </div>
  );
}

function mapItemTone(item: RepositoryReleaseGateSummary) {
  if (item.blocked) {
    return "danger" as const;
  }

  switch (item.status) {
    case "approved":
      return "success" as const;
    case "rejected":
      return "danger" as const;
    case "changes_requested":
      return "warning" as const;
    default:
      return "info" as const;
  }
}

function parseStructuredLines(value: string): string[] {
  const normalized: string[] = [];
  const seen = new Set<string>();

  value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .forEach((line) => {
      if (!line || seen.has(line)) {
        return;
      }
      normalized.push(line);
      seen.add(line);
    });

  return normalized.slice(0, 20);
}
