import { type FormEvent, useEffect, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { PreflightChecklist } from "../repositories/components/PreflightChecklist";
import {
  useApplyRepositoryPreflightAction,
  useProjectRepositoryPreflightInbox,
  useRepositoryPreflightDetail,
} from "./hooks";
import type { RepositoryPreflightApprovalSummary } from "./types";
import { CHANGE_BATCH_PREFLIGHT_STATUS_LABELS } from "../repositories/types";

type RepositoryPreflightPanelProps = {
  projectId: string | null;
  projectName: string | null;
};

export function RepositoryPreflightPanel(props: RepositoryPreflightPanelProps) {
  const inboxQuery = useProjectRepositoryPreflightInbox(props.projectId);
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

    const pendingItem =
      items.find((item) => item.preflight.status === "blocked_requires_confirmation") ??
      items[0] ??
      null;
    setSelectedChangeBatchId(pendingItem?.change_batch_id ?? null);
  }, [items, selectedChangeBatchId]);

  const detailQuery = useRepositoryPreflightDetail(selectedChangeBatchId, true);

  if (!props.projectId) {
    return (
      <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-xl shadow-slate-950/30">
        <div className="text-lg font-semibold text-slate-50">Day08 预检中心</div>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          这里展示仓库预检与审批前确认流程。请先选择项目，再查看对应的变更批次。
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-xl shadow-slate-950/30">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="text-lg font-semibold text-slate-50">Day08 预检中心</div>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-300">
            这里汇总 Day08 预检结果与人工确认状态。当前页面主要面向仓库预检与 ChangeBatch
            审批前检查，Day09+ 的更深层自动化能力仍在逐步接入。
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <MiniStat
            label="项目"
            value={props.projectName ?? "未选择"}
          />
          <MiniStat
            label="待确认"
            value={String(inboxQuery.data?.pending_confirmations ?? 0)}
          />
          <MiniStat
            label="可执行"
            value={String(inboxQuery.data?.ready_batches ?? 0)}
          />
        </div>
      </div>

      {inboxQuery.isLoading && !inboxQuery.data ? (
        <div className="mt-4 text-sm leading-6 text-slate-400">正在加载预检列表...</div>
      ) : null}
      {inboxQuery.isError ? (
        <div className="mt-4 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
          预检列表加载失败：{inboxQuery.error.message}
        </div>
      ) : null}

      {items.length > 0 ? (
        <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(320px,0.95fr)_minmax(0,1.25fr)]">
          <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
            <div className="text-sm font-semibold text-slate-50">变更批次</div>
            <div className="mt-2 text-sm leading-6 text-slate-400">
              选择一个 Day08 ChangeBatch 查看预检结果、风险与人工确认面板。
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
                    <div className="text-sm font-medium text-slate-100">{item.title}</div>
                    <StatusBadge
                      label={CHANGE_BATCH_PREFLIGHT_STATUS_LABELS[item.preflight.status]}
                      tone={mapItemTone(item)}
                    />
                  </div>
                  <div className="mt-2 text-sm leading-6 text-slate-300">{item.preflight.summary ?? item.summary}</div>
                  <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
                    <span>任务 {item.task_count}</span>
                    <span>目标文件 {item.target_file_count}</span>
                    <span>重叠文件 {item.overlap_file_count}</span>
                    <span>更新于 {formatDateTime(item.updated_at)}</span>
                  </div>
                </button>
              ))}
            </div>
          </section>

          <section>
            {selectedChangeBatchId ? (
              detailQuery.isLoading && !detailQuery.data ? (
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-8 text-sm leading-6 text-slate-400">
                  正在加载详情...
                </div>
              ) : detailQuery.isError ? (
                <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-8 text-sm leading-6 text-rose-100">
                  预检详情加载失败：{detailQuery.error.message}
                </div>
              ) : detailQuery.data ? (
                <RepositoryPreflightDetailPanel
                  projectId={props.projectId}
                  detail={detailQuery.data}
                />
              ) : null
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 px-4 py-8 text-sm leading-6 text-slate-400">
                请选择一个 Day08 ChangeBatch 以查看其预检详情。
              </div>
            )}
          </section>
        </div>
      ) : !inboxQuery.isLoading && !inboxQuery.isError ? (
        <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 px-4 py-8 text-sm leading-6 text-slate-400">
          当前没有可展示的 Day08 ChangeBatch 预检项。
        </div>
      ) : null}
    </section>
  );
}

function RepositoryPreflightDetailPanel(props: {
  projectId: string;
  detail: NonNullable<ReturnType<typeof useRepositoryPreflightDetail>["data"]>;
}) {
  const mutation = useApplyRepositoryPreflightAction(
    props.projectId,
    props.detail.change_batch_id,
  );
  const [action, setAction] = useState<"approve" | "reject">("approve");
  const [actorName, setActorName] = useState("审查人");
  const [summary, setSummary] = useState("");
  const [comment, setComment] = useState("");
  const [feedback, setFeedback] = useState<{
    tone: "success" | "warning" | "danger";
    text: string;
  } | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (props.detail.preflight.manual_confirmation_status !== "pending") {
      setFeedback({
        tone: "warning",
        text: "当前预检状态不允许再次提交。",
      });
      return;
    }
    if (!summary.trim()) {
      setFeedback({
        tone: "danger",
        text: "请先填写简要说明。",
      });
      return;
    }

    setFeedback(null);
    try {
      await mutation.mutateAsync({
        action,
        actor_name: actorName.trim() || "审查人",
        summary: summary.trim(),
        comment: comment.trim() || null,
        highlighted_risks: props.detail.preflight.findings.map((item) => item.title).slice(0, 6),
      });
      setFeedback({
        tone: action === "approve" ? "success" : "warning",
        text: action === "approve" ? "已提交审批通过确认。" : "已提交拒绝确认。",
      });
      setSummary("");
      setComment("");
    } catch (error) {
      setFeedback({
        tone: "danger",
        text: error instanceof Error ? error.message : "提交失败，请稍后重试。",
      });
    }
  }

  return (
    <div className="space-y-4">
      <PreflightChecklist
        title={props.detail.title}
        preflight={props.detail.preflight}
        targetFileCount={props.detail.target_files.length}
        taskCount={props.detail.task_titles.length}
        overlapFileCount={props.detail.overlap_files.length}
        helperText="这里展示预检摘要、风险点与相关命令，便于在进入 Git 操作前完成最终确认。"
      />

      <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
        <div className="text-sm font-semibold text-slate-50">变更摘要</div>
        <div className="mt-2 text-sm leading-6 text-slate-400">
          记录本次 ChangeBatch 的任务范围、目标文件与人工确认备注。
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <div>
            <div className="text-xs uppercase tracking-[0.18em] text-slate-500">任务清单</div>
            <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-300">
              {props.detail.task_titles.map((taskTitle) => (
                <li key={taskTitle} className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2">
                  {taskTitle}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <div className="text-xs uppercase tracking-[0.18em] text-slate-500">目标文件</div>
            <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-300">
              {props.detail.target_files.map((filePath) => (
                <li key={filePath} className="break-all rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2">
                  {filePath}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {props.detail.preflight.manual_confirmation_status === "pending" ? (
        <form
          onSubmit={(event) => {
            void handleSubmit(event);
          }}
          className="rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4"
        >
          <div className="text-sm font-semibold text-amber-50">人工确认</div>
          <div className="mt-2 text-sm leading-6 text-amber-100/80">
            预检结果仍处于待确认状态，请填写简要说明后再提交审批决定。
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <label className="block text-sm text-slate-200">
              <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">动作</div>
              <select
                value={action}
                onChange={(event) => setAction(event.target.value as "approve" | "reject")}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400"
              >
                <option value="approve">通过</option>
                <option value="reject">拒绝</option>
              </select>
            </label>
            <label className="block text-sm text-slate-200">
              <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">操作者</div>
              <input
                value={actorName}
                onChange={(event) => setActorName(event.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400"
              />
            </label>
          </div>

          <label className="mt-4 block text-sm text-slate-200">
            <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">摘要</div>
            <input
              value={summary}
              onChange={(event) => setSummary(event.target.value)}
              placeholder="请输入确认摘要"
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400"
            />
          </label>

          <label className="mt-4 block text-sm text-slate-200">
            <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">备注</div>
            <textarea
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              rows={4}
              className="w-full rounded-2xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400"
            />
          </label>

          {feedback ? (
            <div
              className={`mt-4 rounded-xl border px-4 py-3 text-sm leading-6 ${
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
            <div className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
              提交失败：{mutation.error.message}
            </div>
          ) : null}

          <div className="mt-4 flex justify-end">
            <button
              type="submit"
            disabled={mutation.isPending}
            className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-900 disabled:text-slate-500"
          >
              {mutation.isPending ? "提交中..." : "提交确认"}
            </button>
          </div>
        </form>
      ) : (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-4 text-sm leading-6 text-slate-300">
          当前预检已完成确认，后续可继续推进 Day08 流程。
        </div>
      )}
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

function mapItemTone(item: RepositoryPreflightApprovalSummary) {
  switch (item.preflight.status) {
    case "ready_for_execution":
    case "manual_confirmed":
      return "success" as const;
    case "manual_rejected":
      return "danger" as const;
    case "blocked_requires_confirmation":
      return "warning" as const;
    default:
      return "neutral" as const;
  }
}
