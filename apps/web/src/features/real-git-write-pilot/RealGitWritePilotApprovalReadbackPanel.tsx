import { useMemo, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { buildSafeDryRunPlanSample, createApprovalReadbackRequest } from "./api";
import { useRecordRealGitWritePilotApprovalReadback } from "./hooks";
import type { RealGitWritePilotApprovalReadback } from "./types";

const EXPLICIT_PHRASES = ["我确认此次试点写入", "I confirm this pilot write"];
const BROAD_PHRASES = ["approve", "ok", "yes", "同意", "确认"];

const STAGE_STATUS = [
  ["P9-RGWP-F1", "Pass"],
  ["P9-RGWP-F2", "本轮前端 readback"],
  ["P9-RGWP-G", "Not started"],
  ["P9 real executor launch", "Not started"],
  ["Real Git write pilot actual execution", "Not started"],
  ["产品运行时 Git 写操作", "Not started"],
  ["AI Project Director 总闭环", "Partial"],
] as const;

const SAFETY_STATEMENTS = [
  "本操作不会执行 Git 写",
  "本操作不会生成 one-shot token",
  "本操作不会启动外部执行器",
  "本操作不会提交、推送、创建 PR 或合并",
  "下一阶段 P9-RGWP-G 才会设计 one-shot token contract",
];

function defaultExpiryInputValue(): string {
  const later = new Date(Date.now() + 30 * 60 * 1000);
  const offsetMs = later.getTimezoneOffset() * 60 * 1000;
  return new Date(later.getTime() - offsetMs).toISOString().slice(0, 16);
}

function toIsoFromLocalInput(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return new Date(Date.now() + 30 * 60 * 1000).toISOString();
  }
  return parsed.toISOString();
}

export function RealGitWritePilotApprovalReadbackPanel() {
  const [pilotId, setPilotId] = useState("pilot-ui-readback-1");
  const [approvedBy, setApprovedBy] = useState("web-user");
  const [approvalPhrase, setApprovalPhrase] = useState("我确认此次试点写入");
  const [approvedScopeSummary, setApprovedScopeSummary] = useState(
    "approval covers the dry-run doc-only pilot scope",
  );
  const [expiresAt, setExpiresAt] = useState(defaultExpiryInputValue);
  const [latestReadback, setLatestReadback] =
    useState<RealGitWritePilotApprovalReadback | null>(null);
  const mutation = useRecordRealGitWritePilotApprovalReadback();

  const samplePlan = useMemo(
    () => buildSafeDryRunPlanSample(pilotId.trim() || "pilot-ui-readback-1"),
    [pilotId],
  );

  const handleSubmit = async () => {
    const payload = createApprovalReadbackRequest({
      pilotId: pilotId.trim() || "pilot-ui-readback-1",
      approvedBy: approvedBy.trim() || "web-user",
      approvalPhrase,
      approvedScopeSummary:
        approvedScopeSummary.trim() || "approval covers the dry-run doc-only pilot scope",
      expiresAt: toIsoFromLocalInput(expiresAt),
    });
    const readback = await mutation.mutateAsync(payload);
    setLatestReadback(readback);
  };

  return (
    <section
      data-testid="real-git-write-pilot-approval-readback-panel"
      className="rounded border border-[#333333] bg-[#1a1a1a] p-4"
    >
      <div className="flex flex-col gap-4">
        <header className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">
              P9 real Git write pilot
            </div>
            <h3 className="mt-2 text-base font-medium text-zinc-100">
              Manual approval readback
            </h3>
            <p className="mt-2 max-w-3xl text-xs leading-5 text-zinc-500">
              当前只记录确认 readback，不会发放 one-shot token，不会启动外部执行器，不会执行 Git 写。
            </p>
          </div>
          <button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={mutation.isPending}
            className="w-fit rounded border border-cyan-500/40 px-3 py-1.5 text-xs text-cyan-100 transition hover:border-cyan-300 hover:bg-cyan-500/10 disabled:cursor-not-allowed disabled:border-[#333333] disabled:text-zinc-600 disabled:hover:bg-transparent"
          >
            {mutation.isPending ? "记录中..." : "记录确认 readback"}
          </button>
        </header>

        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          {STAGE_STATUS.map(([label, value]) => (
            <ReadbackMetric
              key={label}
              label={label}
              value={value}
              tone={value === "Pass" ? "success" : value === "Partial" ? "warning" : "info"}
            />
          ))}
        </div>

        <div className="grid gap-1.5">
          {SAFETY_STATEMENTS.map((statement) => (
            <p
              key={statement}
              className="rounded border border-cyan-500/20 bg-cyan-500/5 px-2 py-1 text-[10px] leading-4 text-cyan-100/80"
            >
              {statement}
            </p>
          ))}
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
          <div className="space-y-3">
            <ApprovalForm
              pilotId={pilotId}
              approvedBy={approvedBy}
              approvalPhrase={approvalPhrase}
              approvedScopeSummary={approvedScopeSummary}
              expiresAt={expiresAt}
              onPilotIdChange={setPilotId}
              onApprovedByChange={setApprovedBy}
              onApprovalPhraseChange={setApprovalPhrase}
              onApprovedScopeSummaryChange={setApprovedScopeSummary}
              onExpiresAtChange={setExpiresAt}
            />
            <SamplePlanReadback
              dryRunReady={samplePlan.dry_run_ready}
              readyForExecution={samplePlan.ready_for_execution}
              auditSummaries={samplePlan.audit_event_summaries}
            />
          </div>

          <div className="space-y-3">
            <PhraseRules />
            {mutation.isError ? (
              <PanelState
                tone="error"
                message={`approval readback 记录失败：${mutation.error.message}`}
              />
            ) : null}
            {latestReadback ? (
              <ApprovalReadbackResult readback={latestReadback} />
            ) : (
              <PanelState message="尚未记录确认 readback。表单使用前端 safe sample dry-run plan，不读取真实 workspace。" />
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function ApprovalForm(props: {
  pilotId: string;
  approvedBy: string;
  approvalPhrase: string;
  approvedScopeSummary: string;
  expiresAt: string;
  onPilotIdChange: (value: string) => void;
  onApprovedByChange: (value: string) => void;
  onApprovalPhraseChange: (value: string) => void;
  onApprovedScopeSummaryChange: (value: string) => void;
  onExpiresAtChange: (value: string) => void;
}) {
  return (
    <article className="rounded border border-[#333333] bg-[#111111] p-3">
      <h4 className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">
        Approval readback form
      </h4>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <TextField label="pilot_id" value={props.pilotId} onChange={props.onPilotIdChange} />
        <TextField
          label="approved_by"
          value={props.approvedBy}
          onChange={props.onApprovedByChange}
        />
        <TextField
          label="approval_phrase"
          value={props.approvalPhrase}
          onChange={props.onApprovalPhraseChange}
        />
        <label className="grid gap-1 text-xs text-zinc-500">
          expires_at
          <input
            type="datetime-local"
            value={props.expiresAt}
            onChange={(event) => props.onExpiresAtChange(event.target.value)}
            className="rounded border border-[#333333] bg-[#1a1a1a] px-2 py-1.5 text-xs text-zinc-200 outline-none focus:border-zinc-500"
          />
        </label>
      </div>
      <label className="mt-3 grid gap-1 text-xs text-zinc-500">
        approved_scope_summary
        <textarea
          value={props.approvedScopeSummary}
          onChange={(event) => props.onApprovedScopeSummaryChange(event.target.value)}
          rows={3}
          className="resize-none rounded border border-[#333333] bg-[#1a1a1a] px-2 py-1.5 text-xs leading-5 text-zinc-200 outline-none focus:border-zinc-500"
        />
      </label>
    </article>
  );
}

function TextField(props: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-1 text-xs text-zinc-500">
      {props.label}
      <input
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
        className="rounded border border-[#333333] bg-[#1a1a1a] px-2 py-1.5 text-xs text-zinc-200 outline-none focus:border-zinc-500"
      />
    </label>
  );
}

function PhraseRules() {
  return (
    <article className="rounded border border-[#333333] bg-[#111111] p-3">
      <h4 className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">
        Phrase rules
      </h4>
      <div className="mt-3 grid gap-3 text-xs leading-5">
        <div>
          <p className="mb-1 text-zinc-500">允许通过的明确短语</p>
          <div className="flex flex-wrap gap-1.5">
            {EXPLICIT_PHRASES.map((phrase) => (
              <span key={phrase} className="rounded border border-emerald-500/30 px-2 py-1 text-emerald-100/80">
                {phrase}
              </span>
            ))}
          </div>
        </div>
        <div>
          <p className="mb-1 text-zinc-500">宽泛短语不会通过</p>
          <div className="flex flex-wrap gap-1.5">
            {BROAD_PHRASES.map((phrase) => (
              <span key={phrase} className="rounded border border-amber-500/30 px-2 py-1 text-amber-100/80">
                {phrase}
              </span>
            ))}
          </div>
        </div>
      </div>
    </article>
  );
}

function SamplePlanReadback(props: {
  dryRunReady: boolean;
  readyForExecution: false;
  auditSummaries: string[];
}) {
  return (
    <article className="rounded border border-[#333333] bg-[#111111] p-3">
      <h4 className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">
        Safe dry-run sample
      </h4>
      <div className="mt-3 grid gap-2 text-xs leading-5 text-zinc-400">
        <DetailRow label="dry_run_ready" value={props.dryRunReady ? "true" : "false"} />
        <DetailRow label="ready_for_execution" value="false" />
        <DetailRow label="sample source" value="frontend readback-safe sample only; no host probing" />
      </div>
      <div className="mt-3 space-y-1">
        {props.auditSummaries.map((summary) => (
          <p key={summary} className="text-[10px] leading-4 text-zinc-600">
            {summary}
          </p>
        ))}
      </div>
    </article>
  );
}

function ApprovalReadbackResult({
  readback,
}: {
  readback: RealGitWritePilotApprovalReadback;
}) {
  return (
    <article className="rounded border border-[#333333] bg-[#111111] p-3">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h4 className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">
          Approval readback result
        </h4>
        <StatusBadge
          label={readback.decision}
          tone={readback.decision === "approved" ? "success" : readback.decision === "blocked" ? "danger" : "warning"}
        />
      </div>
      <div className="space-y-2 text-xs leading-5">
        <DetailRow label="approval_phrase_matched" value={readback.approval_phrase_matched ? "true" : "false"} />
        <DetailRow label="dry_run_ready" value={readback.dry_run_ready ? "true" : "false"} />
        <DetailRow label="ready_for_execution" value="false" />
        <DetailRow label="one_shot_token_issued" value="false" />
        <DetailRow label="product_runtime_git_write_executed" value="false" />
        <DetailRow label="real_executor_started" value="false" />
        <DetailRow label="safe_summary" value={readback.safe_summary} />
        <DetailRow label="created_at" value={formatDateTime(readback.created_at)} />
        <DetailRow label="expires_at" value={formatDateTime(readback.expires_at)} />
      </div>
      <div className="mt-3 space-y-1">
        {readback.audit_event_summaries.map((summary) => (
          <p key={summary} className="rounded border border-[#333333] px-2 py-1 text-[10px] leading-4 text-zinc-500">
            {summary}
          </p>
        ))}
      </div>
    </article>
  );
}

function ReadbackMetric(props: {
  label: string;
  value: string;
  tone?: "success" | "warning" | "danger" | "info";
}) {
  return (
    <div className="rounded border border-[#333333] bg-[#111111] p-3">
      <p className="text-[10px] uppercase tracking-[0.14em] text-zinc-600">
        {props.label}
      </p>
      <p className="mt-2 text-xs font-medium text-zinc-200">{props.value}</p>
      {props.tone ? (
        <div className="mt-2">
          <StatusBadge label={props.tone} tone={props.tone} />
        </div>
      ) : null}
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[160px_1fr]">
      <dt className="text-zinc-500">{label}</dt>
      <dd className="break-words text-zinc-300">{value}</dd>
    </div>
  );
}

function PanelState({
  message,
  tone = "default",
}: {
  message: string;
  tone?: "default" | "error";
}) {
  return (
    <div
      className={`rounded border px-3 py-2 text-xs leading-5 ${
        tone === "error"
          ? "border-red-500/30 bg-red-500/5 text-red-100/80"
          : "border-[#333333] bg-[#111111] text-zinc-500"
      }`}
    >
      {message}
    </div>
  );
}
