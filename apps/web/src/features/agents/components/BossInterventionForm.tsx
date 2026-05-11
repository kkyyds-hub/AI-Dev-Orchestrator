import { useEffect, useState } from "react";

import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import { useSubmitBossIntervention } from "../hooks";
import type { AgentSessionSnapshot } from "../types";

type BossInterventionFormProps = {
  projectId: string | null;
  selectedSession: AgentSessionSnapshot | null;
  interventionCount: number;
};

function getServerWriteGateHint(session: AgentSessionSnapshot | null): string | null {
  if (!session) {
    return null;
  }

  const terminalStatuses = new Set(["completed", "failed", "blocked"]);
  if (
    terminalStatuses.has(session.session_status) ||
    session.current_phase === "finalized"
  ) {
    return `该会话已结束，可能无法继续追加介入（${session.session_status} / ${session.current_phase}）。`;
  }

  return null;
}

export function BossInterventionForm(props: BossInterventionFormProps) {
  const submitMutation = useSubmitBossIntervention({
    projectId: props.projectId,
    sessionId: props.selectedSession?.session_id ?? null,
  });
  const [interventionType, setInterventionType] = useState("boss_directive");
  const [noteEventType, setNoteEventType] = useState("manual_intervention");
  const [contentSummary, setContentSummary] = useState("");
  const [contentDetail, setContentDetail] = useState("");
  const [actionFeedback, setActionFeedback] = useState<{
    tone: "success" | "danger";
    text: string;
  } | null>(null);
  const [latestWriteAt, setLatestWriteAt] = useState<string | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const serverWriteGateHint = getServerWriteGateHint(props.selectedSession);

  useEffect(() => {
    setActionFeedback(null);
    setLatestWriteAt(null);
    setIsFormOpen(false);
  }, [props.projectId, props.selectedSession?.session_id]);

  const disabledReason = !props.projectId
    ? "请先选择项目。"
    : !props.selectedSession
      ? "请先选择一个智能体会话。"
      : interventionType.trim().length === 0
        ? "请填写介入类型。"
      : contentSummary.trim().length === 0
        ? "请填写介入摘要。"
        : null;

  const submitDisabled = submitMutation.isPending || disabledReason !== null;

  async function handleSubmit() {
    if (submitDisabled) {
      return;
    }

    try {
      const result = await submitMutation.mutateAsync({
        interventionType,
        noteEventType: noteEventType.trim() || null,
        contentSummary: contentSummary.trim(),
        contentDetail: contentDetail.trim() || null,
      });
      setActionFeedback({
        tone: "success",
        text: `介入已记录：${result.intervention_message.event_type}。`,
      });
      setLatestWriteAt(result.intervention_message.created_at);
      setContentSummary("");
      setContentDetail("");
    } catch (error) {
      setActionFeedback({
        tone: "danger",
        text: error instanceof Error ? error.message : "介入提交失败。",
      });
    }
  }

  return (
    <section
      className="border-b border-[#333333] pb-4"
      data-testid="boss-intervention-entry-panel"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-slate-100">人工介入</h4>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            对当前会话追加人工指令和处理说明。
          </p>
        </div>
        <StatusBadge
          label={disabledReason ? "暂不可介入" : "可介入"}
          tone={disabledReason ? "warning" : "success"}
        />
      </div>

      <div
        className="mt-3 text-xs leading-5 text-slate-400"
        data-testid="boss-intervention-contract-gap"
      >
        {disabledReason ??
          serverWriteGateHint ??
          "当前会话可以追加人工介入。"}
      </div>

      <dl
        className="mt-3 grid gap-x-4 gap-y-2 text-xs text-slate-500"
        data-testid="boss-intervention-entry-summary"
      >
        <div>
          <dt className="text-slate-600">会话状态</dt>
          <dd className="mt-0.5 text-slate-300">
            {props.selectedSession?.session_status ?? "无"}
          </dd>
        </div>
        <div>
          <dt className="text-slate-600">当前阶段</dt>
          <dd className="mt-0.5 text-slate-300">
            {props.selectedSession?.current_phase ?? "无"}
          </dd>
        </div>
        <div>
          <dt className="text-slate-600">介入消息</dt>
          <dd className="mt-0.5 text-slate-300">{props.interventionCount}</dd>
        </div>
        <div>
          <dt className="text-slate-600">最近介入</dt>
          <dd className="mt-0.5 text-slate-300">
            {latestWriteAt ? formatDateTime(latestWriteAt) : "无"}
          </dd>
        </div>
      </dl>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setIsFormOpen(true)}
          disabled={!props.selectedSession}
          className="rounded border border-[#4a4a4a] bg-transparent px-3 py-2 text-xs font-medium text-zinc-100 transition hover:bg-[#292929] disabled:cursor-not-allowed disabled:opacity-60"
        >
          发起人工介入
        </button>
        <button
          type="button"
          data-testid="boss-intervention-help-open"
          onClick={() => setIsHelpOpen(true)}
          className="rounded border border-transparent px-3 py-2 text-xs text-slate-400 transition hover:text-slate-100"
        >
          提交提示
        </button>
      </div>

      {isFormOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="boss-intervention-form-title"
        >
          <div className="max-h-[88vh] w-full max-w-2xl overflow-auto rounded-2xl border border-[#333333] bg-slate-950 p-5 shadow-2xl shadow-slate-950/60">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs tracking-[0.18em] text-slate-500">人工介入</p>
                <h5
                  id="boss-intervention-form-title"
                  className="mt-2 text-xl font-semibold text-slate-50"
                >
                  向当前会话追加指令
                </h5>
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  填写摘要与详情后，将记录到当前会话的介入动态中。
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsFormOpen(false)}
                className="rounded border border-[#4a4a4a] px-3 py-1.5 text-sm text-zinc-100 transition hover:bg-[#292929]"
              >
                关闭
              </button>
            </div>

            <div className="mt-5 grid gap-4">
              <label className="grid gap-1.5 text-xs text-slate-400">
                <span className="font-medium text-slate-500">介入类型</span>
                <input
                  type="text"
                  value={interventionType}
                  onChange={(event) => setInterventionType(event.target.value)}
                  data-testid="boss-intervention-type-input"
                  placeholder="boss_directive"
                  className="rounded-lg border border-[#3a3a3a] bg-slate-950/35 px-3 py-2 text-sm text-slate-100 transition focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-500/20"
                />
              </label>

              <label className="grid gap-1.5 text-xs text-slate-400">
                <span className="font-medium text-slate-500">备注事件类型（可选）</span>
                <input
                  type="text"
                  value={noteEventType}
                  onChange={(event) => setNoteEventType(event.target.value)}
                  data-testid="boss-intervention-note-event-input"
                  placeholder="manual_intervention"
                  className="rounded-lg border border-[#3a3a3a] bg-slate-950/35 px-3 py-2 text-sm text-slate-100 transition focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-500/20"
                />
              </label>

              <label className="grid gap-1.5 text-xs text-slate-400">
                <span className="font-medium text-slate-500">介入摘要</span>
                <textarea
                  value={contentSummary}
                  onChange={(event) => setContentSummary(event.target.value)}
                  data-testid="boss-intervention-summary-input"
                  rows={3}
                  placeholder="描述本次人工介入指令。"
                  className="rounded-lg border border-[#3a3a3a] bg-slate-950/35 px-3 py-2 text-sm text-slate-100 transition focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-500/20"
                />
              </label>

              <label className="grid gap-1.5 text-xs text-slate-400">
                <span className="font-medium text-slate-500">介入详情（可选）</span>
                <textarea
                  value={contentDetail}
                  onChange={(event) => setContentDetail(event.target.value)}
                  data-testid="boss-intervention-detail-input"
                  rows={4}
                  placeholder="补充操作背景、边界或期望结果。"
                  className="rounded-lg border border-[#3a3a3a] bg-slate-950/35 px-3 py-2 text-sm text-slate-100 transition focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-500/20"
                />
              </label>
            </div>

            {actionFeedback ? (
              <div
                data-testid="boss-intervention-submit-feedback"
                className={`mt-4 rounded-xl border px-3 py-2 text-xs ${
                  actionFeedback.tone === "success"
                    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-100"
                    : "border-rose-500/30 bg-rose-500/10 text-rose-100"
                }`}
              >
                {actionFeedback.text}
              </div>
            ) : null}

            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setIsFormOpen(false)}
                className="rounded border border-transparent px-4 py-2 text-sm text-slate-400 transition hover:text-slate-100"
              >
                取消
              </button>
              <button
                type="button"
                data-testid="boss-intervention-submit-btn"
                disabled={submitDisabled}
                aria-disabled={submitDisabled}
                onClick={() => void handleSubmit()}
                title={disabledReason ?? "提交一条正式人工介入指令。"}
                className="rounded border border-[#4a4a4a] bg-transparent px-4 py-2 text-sm font-medium text-zinc-100 transition hover:bg-[#292929] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitMutation.isPending ? "提交中..." : "提交人工介入"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {isHelpOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="boss-intervention-help-title"
          data-testid="boss-intervention-help-modal"
        >
          <div className="w-full max-w-xl rounded-2xl border border-[#333333] bg-slate-950 p-5 shadow-2xl shadow-slate-950/60">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs tracking-[0.18em] text-slate-500">提交提示</p>
                <h5 id="boss-intervention-help-title" className="mt-2 text-xl font-semibold text-slate-50">
                  人工介入提示
                </h5>
              </div>
              <button
                type="button"
                data-testid="boss-intervention-help-close"
                onClick={() => setIsHelpOpen(false)}
                className="rounded border border-[#4a4a4a] px-3 py-1.5 text-sm text-zinc-100 transition hover:bg-[#292929]"
              >
                关闭
              </button>
            </div>
            <div className="mt-4 space-y-3 text-sm leading-6 text-slate-300">
              <p>提交前需要先选中一个会话，并填写介入类型与介入摘要。</p>
              <p>备注事件类型可用于分类检索；摘要和详情会出现在当前会话的介入动态中。</p>
              <p>已结束的会话可能无法继续追加介入。</p>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
