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
      <section className="border-b border-[#333333] pb-6">
        <div className="text-lg font-semibold text-slate-50">项目预检</div>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          请先选择项目，再查看待预检的变更范围、风险提示和人工确认状态。
        </p>
      </section>
    );
  }

  return (
    <section className="border-b border-[#333333] pb-6">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="text-lg font-semibold text-slate-50">项目预检</div>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-300">
            在变更进入执行或审批前，先确认影响范围、风险提示和是否需要人工放行。
            这里帮助团队把“能不能继续推进”判断收束在一个轻量入口里。
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
        <div className="mt-4 border-l border-rose-500/50 px-4 py-3 text-sm leading-6 text-rose-100">
          预检列表加载失败：{inboxQuery.error.message}
        </div>
      ) : null}

      {items.length > 0 ? (
        <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(320px,0.95fr)_minmax(0,1.25fr)]">
          <section className="border-b border-[#333333] pb-4">
            <div className="text-sm font-semibold text-slate-50">待预检事项</div>
            <div className="mt-2 text-sm leading-6 text-slate-400">
              选择一个变更记录，查看范围、风险提示和当前处理状态。
            </div>

            <div className="mt-4 divide-y divide-[#333333] border-y border-[#333333]">
              {items.map((item) => (
                <button
                  key={item.change_batch_id}
                  type="button"
                  onClick={() => setSelectedChangeBatchId(item.change_batch_id)}
                  className={`w-full px-0 py-4 text-left transition ${
                    item.change_batch_id === selectedChangeBatchId
                      ? "border-l-2 border-zinc-300 pl-3"
                      : "border-l border-transparent pl-3 hover:border-[#4a4a4a]"
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
                    <span>涉及任务 {item.task_count}</span>
                    <span>涉及文件 {item.target_file_count}</span>
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
                <div className="border-b border-[#333333] px-0 py-6 text-sm leading-6 text-slate-400">
                  正在加载详情...
                </div>
              ) : detailQuery.isError ? (
                <div className="border-l border-rose-500/50 px-4 py-8 text-sm leading-6 text-rose-100">
                  预检详情加载失败：{detailQuery.error.message}
                </div>
              ) : detailQuery.data ? (
                <RepositoryPreflightDetailPanel
                  projectId={props.projectId}
                  detail={detailQuery.data}
                />
              ) : null
            ) : (
              <div className="border border-dashed border-[#3a3a3a] px-4 py-8 text-sm leading-6 text-slate-400">
                请选择一个变更记录以查看预检详情。
              </div>
            )}
          </section>
        </div>
      ) : !inboxQuery.isLoading && !inboxQuery.isError ? (
        <div className="mt-4 border border-dashed border-[#3a3a3a] px-4 py-8 text-sm leading-6 text-slate-400">
          当前没有需要预检的变更记录。
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
        helperText="这里展示范围摘要、风险提示与相关检查项，便于在继续推进前完成最终确认。"
      />

      <section className="border-b border-[#333333] pb-4">
        <div className="text-sm font-semibold text-slate-50">变更范围</div>
        <div className="mt-2 text-sm leading-6 text-slate-400">
          记录本次变更涉及的任务与文件，方便确认是否符合预期范围。
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <div>
            <div className="text-xs uppercase tracking-[0.18em] text-slate-500">任务清单</div>
            <ul className="mt-3 divide-y divide-[#333333] border-y border-[#333333] text-sm leading-6 text-slate-300">
              {props.detail.task_titles.map((taskTitle) => (
                <li key={taskTitle} className="px-0 py-2">
                  {taskTitle}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <div className="text-xs uppercase tracking-[0.18em] text-slate-500">目标文件</div>
            <ul className="mt-3 divide-y divide-[#333333] border-y border-[#333333] text-sm leading-6 text-slate-300">
              {props.detail.target_files.map((filePath) => (
                <li key={filePath} className="break-all px-0 py-2">
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
          className="border-b border-[#333333] pb-4"
        >
          <div className="text-sm font-semibold text-slate-50">人工确认</div>
          <div className="mt-2 text-sm leading-6 text-slate-400">
            当前预检仍需要人工判断。请补充确认摘要后，再决定是否放行。
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <label className="block text-sm text-slate-200">
              <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">动作</div>
              <select
                value={action}
                onChange={(event) => setAction(event.target.value as "approve" | "reject")}
                className="w-full rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-[#6a6a6a]"
              >
                <option value="approve">放行</option>
                <option value="reject">驳回</option>
              </select>
            </label>
            <label className="block text-sm text-slate-200">
              <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">操作者</div>
              <input
                value={actorName}
                onChange={(event) => setActorName(event.target.value)}
                className="w-full rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-[#6a6a6a]"
              />
            </label>
          </div>

          <label className="mt-4 block text-sm text-slate-200">
            <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">摘要</div>
            <input
              value={summary}
              onChange={(event) => setSummary(event.target.value)}
              placeholder="例如：范围可控，允许继续推进"
              className="w-full rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-[#6a6a6a]"
            />
          </label>

          <label className="mt-4 block text-sm text-slate-200">
            <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">备注</div>
            <textarea
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              rows={4}
              placeholder="可补充需要关注的范围、风险或后续处理建议"
              className="w-full rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-[#6a6a6a]"
            />
          </label>

          {feedback ? (
            <div
              className={`mt-4 border-l px-4 py-3 text-sm leading-6 ${
                feedback.tone === "success"
                  ? "border-emerald-500/50 text-emerald-100"
                  : feedback.tone === "warning"
                    ? "border-amber-500/50 text-amber-100"
                    : "border-rose-500/50 text-rose-100"
              }`}
            >
              {feedback.text}
            </div>
          ) : null}

          {mutation.isError ? (
            <div className="mt-4 border-l border-rose-500/50 px-4 py-3 text-sm leading-6 text-rose-100">
              提交失败：{mutation.error.message}
            </div>
          ) : null}

          <div className="mt-4 flex justify-end">
            <button
              type="submit"
            disabled={mutation.isPending}
            className="rounded border border-[#4a4a4a] bg-transparent px-4 py-2 text-sm font-medium text-zinc-100 transition hover:bg-[#292929] disabled:cursor-not-allowed disabled:opacity-60"
          >
              {mutation.isPending ? "提交中..." : "提交确认"}
            </button>
          </div>
        </form>
      ) : (
        <div className="border-l border-[#333333] px-4 py-3 text-sm leading-6 text-slate-300">
          当前预检已完成确认，后续可继续推进。
        </div>
      )}
    </div>
  );
}

function MiniStat(props: { label: string; value: string }) {
  return (
    <div className="border-l border-[#333333] px-4 py-2">
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
