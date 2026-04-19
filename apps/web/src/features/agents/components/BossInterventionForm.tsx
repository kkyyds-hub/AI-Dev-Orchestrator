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
    return (
      "Terminal session is frozen by backend gate; submit will return conflict " +
      `(${session.session_status} / ${session.current_phase}).`
    );
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
  const serverWriteGateHint = getServerWriteGateHint(props.selectedSession);

  useEffect(() => {
    setActionFeedback(null);
    setLatestWriteAt(null);
  }, [props.projectId, props.selectedSession?.session_id]);

  const disabledReason = !props.projectId
    ? "No project selected."
    : !props.selectedSession
      ? "No agent session selected."
      : interventionType.trim().length === 0
        ? "Intervention type is required."
      : contentSummary.trim().length === 0
        ? "Intervention summary is required."
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
        text: `Intervention persisted: ${result.intervention_message.event_type}.`,
      });
      setLatestWriteAt(result.intervention_message.created_at);
      setContentSummary("");
      setContentDetail("");
    } catch (error) {
      setActionFeedback({
        tone: "danger",
        text: error instanceof Error ? error.message : "Intervention submit failed.",
      });
    }
  }

  return (
    <section
      className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4"
      data-testid="boss-intervention-entry-panel"
    >
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">
          Boss Intervention Entry
        </h4>
        <StatusBadge
          label={disabledReason ? "write gated" : "write enabled"}
          tone={disabledReason ? "warning" : "success"}
        />
      </div>

      <p className="mt-2 text-sm text-slate-400">
        Day12 consumes Day11 read contracts and now exposes a formal session-level write contract:
        POST /agent-threads/projects/{"{project_id}"}/sessions/{"{session_id}"}/interventions.
      </p>

      <div
        className="mt-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100"
        data-testid="boss-intervention-contract-gap"
      >
        {disabledReason ??
          serverWriteGateHint ??
          "Formal session-level intervention write contract is active."}
      </div>

      <div
        className="mt-3 rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-300"
        data-testid="boss-intervention-entry-summary"
      >
        <div>project_id: {props.projectId ?? "none"}</div>
        <div>session_id: {props.selectedSession?.session_id ?? "none"}</div>
        <div>session_status: {props.selectedSession?.session_status ?? "none"}</div>
        <div>review_status: {props.selectedSession?.review_status ?? "none"}</div>
        <div>current_phase: {props.selectedSession?.current_phase ?? "none"}</div>
        <div>latest_intervention_type: {props.selectedSession?.latest_intervention_type ?? "none"}</div>
        <div>latest_note_event_type: {props.selectedSession?.latest_note_event_type ?? "none"}</div>
        <div>intervention_feed_items: {props.interventionCount}</div>
        <div>latest_write_at: {latestWriteAt ? formatDateTime(latestWriteAt) : "none"}</div>
        <div>server_write_gate: {serverWriteGateHint ?? "writable_or_pending_server_check"}</div>
      </div>

      <div className="mt-3 grid gap-2">
        <label className="text-xs uppercase tracking-[0.16em] text-slate-500">
          Intervention Type
        </label>
        <input
          type="text"
          value={interventionType}
          onChange={(event) => setInterventionType(event.target.value)}
          data-testid="boss-intervention-type-input"
          placeholder="boss_directive"
          className="rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 focus:border-cyan-400/50 focus:outline-none"
        />

        <label className="text-xs uppercase tracking-[0.16em] text-slate-500">
          Note Event Type (optional)
        </label>
        <input
          type="text"
          value={noteEventType}
          onChange={(event) => setNoteEventType(event.target.value)}
          data-testid="boss-intervention-note-event-input"
          placeholder="manual_intervention"
          className="rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 focus:border-cyan-400/50 focus:outline-none"
        />

        <label className="text-xs uppercase tracking-[0.16em] text-slate-500">
          Summary
        </label>
        <textarea
          value={contentSummary}
          onChange={(event) => setContentSummary(event.target.value)}
          data-testid="boss-intervention-summary-input"
          rows={3}
          placeholder="Describe the boss intervention command."
          className="rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 focus:border-cyan-400/50 focus:outline-none"
        />

        <label className="text-xs uppercase tracking-[0.16em] text-slate-500">
          Detail (optional)
        </label>
        <textarea
          value={contentDetail}
          onChange={(event) => setContentDetail(event.target.value)}
          data-testid="boss-intervention-detail-input"
          rows={4}
          placeholder="Optional operator detail."
          className="rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 focus:border-cyan-400/50 focus:outline-none"
        />
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
        title={disabledReason ?? "Submit one formal boss intervention command."}
        className="mt-3 rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {submitMutation.isPending ? "Submitting..." : "Submit Boss Intervention"}
      </button>
    </section>
  );
}
