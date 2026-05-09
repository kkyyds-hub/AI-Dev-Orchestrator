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
    return `后端写入门禁会冻结终态会话，提交会返回冲突（${session.session_status} / ${session.current_phase}）。`;
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
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const serverWriteGateHint = getServerWriteGateHint(props.selectedSession);

  useEffect(() => {
    setActionFeedback(null);
    setLatestWriteAt(null);
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
        text: `介入已写入：${result.intervention_message.event_type}。`,
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
      className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-4 shadow-lg shadow-slate-950/15 sm:p-5"
      data-testid="boss-intervention-entry-panel"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h4 className="text-sm font-semibold tracking-[0.16em] text-slate-200">
            人工介入入口
          </h4>
          <p className="mt-2 text-xs leading-5 text-slate-400">
            通过正式会话级写入契约提交介入指令。
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge
            label={disabledReason ? "暂不可写" : "可写入"}
            tone={disabledReason ? "warning" : "success"}
          />
          <button
            type="button"
            data-testid="boss-intervention-help-open"
            onClick={() => setIsHelpOpen(true)}
            className="rounded-full border border-slate-700 bg-slate-950/40 px-3 py-1.5 text-xs text-slate-200 transition hover:border-cyan-300/50 hover:text-cyan-100 focus:outline-none focus:ring-2 focus:ring-cyan-300/35"
          >
            查看说明
          </button>
        </div>
      </div>

      <p className="mt-3 rounded-2xl border border-slate-800/80 bg-slate-950/45 px-3 py-2 text-xs leading-5 text-slate-400">
        写入接口 POST /agent-threads/projects/{"{project_id}"}/sessions/{"{session_id}"}/interventions
      </p>

      <div
        className="mt-3 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs leading-5 text-amber-100"
        data-testid="boss-intervention-contract-gap"
      >
        {disabledReason ??
          serverWriteGateHint ??
          "会话级介入写入契约已可用。"}
      </div>

      <div
        className="mt-3 grid gap-2 rounded-2xl border border-slate-800/80 bg-slate-950/55 p-3 text-xs text-slate-300 sm:grid-cols-2"
        data-testid="boss-intervention-entry-summary"
      >
        <div className="break-all">project_id：{props.projectId ?? "无"}</div>
        <div className="break-all">session_id：{props.selectedSession?.session_id ?? "无"}</div>
        <div>session_status：{props.selectedSession?.session_status ?? "无"}</div>
        <div>review_status：{props.selectedSession?.review_status ?? "无"}</div>
        <div>current_phase：{props.selectedSession?.current_phase ?? "无"}</div>
        <div>latest_intervention_type：{props.selectedSession?.latest_intervention_type ?? "无"}</div>
        <div>latest_note_event_type：{props.selectedSession?.latest_note_event_type ?? "无"}</div>
        <div>intervention_feed_items：{props.interventionCount}</div>
        <div>latest_write_at：{latestWriteAt ? formatDateTime(latestWriteAt) : "无"}</div>
        <div>server_write_gate：{serverWriteGateHint ?? "writable_or_pending_server_check"}</div>
      </div>

      <div className="mt-4 grid gap-3">
        <label className="grid gap-1.5 text-xs text-slate-400">
          <span className="font-semibold tracking-[0.14em] text-slate-500">介入类型</span>
          <input
            type="text"
            value={interventionType}
            onChange={(event) => setInterventionType(event.target.value)}
            data-testid="boss-intervention-type-input"
            placeholder="boss_directive"
            className="rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 transition focus:border-cyan-400/60 focus:outline-none focus:ring-2 focus:ring-cyan-300/20"
          />
        </label>

        <label className="grid gap-1.5 text-xs text-slate-400">
          <span className="font-semibold tracking-[0.14em] text-slate-500">备注事件类型（可选）</span>
          <input
            type="text"
            value={noteEventType}
            onChange={(event) => setNoteEventType(event.target.value)}
            data-testid="boss-intervention-note-event-input"
            placeholder="manual_intervention"
            className="rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 transition focus:border-cyan-400/60 focus:outline-none focus:ring-2 focus:ring-cyan-300/20"
          />
        </label>

        <label className="grid gap-1.5 text-xs text-slate-400">
          <span className="font-semibold tracking-[0.14em] text-slate-500">介入摘要</span>
          <textarea
            value={contentSummary}
            onChange={(event) => setContentSummary(event.target.value)}
            data-testid="boss-intervention-summary-input"
            rows={3}
            placeholder="描述本次人工介入指令。"
            className="rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 transition focus:border-cyan-400/60 focus:outline-none focus:ring-2 focus:ring-cyan-300/20"
          />
        </label>

        <label className="grid gap-1.5 text-xs text-slate-400">
          <span className="font-semibold tracking-[0.14em] text-slate-500">介入详情（可选）</span>
          <textarea
            value={contentDetail}
            onChange={(event) => setContentDetail(event.target.value)}
            data-testid="boss-intervention-detail-input"
            rows={4}
            placeholder="补充操作背景、边界或期望结果。"
            className="rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 transition focus:border-cyan-400/60 focus:outline-none focus:ring-2 focus:ring-cyan-300/20"
          />
        </label>
      </div>

      {actionFeedback ? (
        <div
          data-testid="boss-intervention-submit-feedback"
          className={`mt-3 rounded-xl border px-3 py-2 text-xs ${
            actionFeedback.tone === "success"
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-100"
              : "border-rose-500/30 bg-rose-500/10 text-rose-100"
          }`}
        >
          {actionFeedback.text}
        </div>
      ) : null}

      <button
        type="button"
        data-testid="boss-intervention-submit-btn"
        disabled={submitDisabled}
        aria-disabled={submitDisabled}
        onClick={() => void handleSubmit()}
        title={disabledReason ?? "提交一条正式人工介入指令。"}
        className="mt-4 w-full rounded-xl border border-cyan-300/35 bg-cyan-400/10 px-4 py-2.5 text-sm font-semibold text-cyan-50 transition hover:border-cyan-200/60 hover:bg-cyan-400/20 focus:outline-none focus:ring-2 focus:ring-cyan-300/35 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {submitMutation.isPending ? "提交中..." : "提交人工介入"}
      </button>

      {isHelpOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="boss-intervention-help-title"
          data-testid="boss-intervention-help-modal"
        >
          <div className="w-full max-w-xl rounded-3xl border border-slate-700 bg-slate-950 p-5 shadow-2xl shadow-slate-950/60">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs tracking-[0.18em] text-cyan-200">提交说明</p>
                <h5 id="boss-intervention-help-title" className="mt-2 text-xl font-semibold text-slate-50">
                  人工介入写入规则
                </h5>
              </div>
              <button
                type="button"
                data-testid="boss-intervention-help-close"
                onClick={() => setIsHelpOpen(false)}
                className="rounded-full border border-slate-700 px-3 py-1.5 text-sm text-slate-200 transition hover:border-cyan-300/50 hover:text-cyan-100 focus:outline-none focus:ring-2 focus:ring-cyan-300/35"
              >
                关闭
              </button>
            </div>
            <div className="mt-4 space-y-3 text-sm leading-6 text-slate-300">
              <p>提交前需要先选中一个会话，并填写介入类型与介入摘要。</p>
              <p>介入类型、备注事件类型会按后端字段值原样提交；摘要和详情会写入当前会话的介入消息流。</p>
              <p>若会话已进入终态，后端写入门禁可能拒绝本次提交。</p>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}