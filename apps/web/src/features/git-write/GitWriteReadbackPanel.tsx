import { useEffect, useMemo, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import {
  useCreateGitWriteIntentReadback,
  useGitWriteAuditReadback,
  useGitWriteIntentReadback,
  useRecordGitWriteApprovalReadback,
} from "./hooks";
import type {
  GitWriteApprovalReadback,
  GitWriteAuditEventReadback,
  GitWriteReadbackRecord,
  GitWriteSafetyGateReadback,
} from "./types";

const SAFETY_READBACK_POINTS = [
  "READY 仅代表 preview ready",
  "all_passed=false 是正常状态：human approval / one-shot token 仍 pending",
  "产品运行时 Git 写操作仍 Not started",
  "Approval readback 只是用户确认记录，不代表已产生仓库变更",
];

const LATER_STAGES = [
  ["GitWrite-F adapter design", "Not started"],
  ["GitWrite-G fake adapter evidence", "Not started"],
  ["GitWrite-Final", "Not started"],
] as const;

export function GitWriteReadbackPanel() {
  const [intentId, setIntentId] = useState<string | null>(null);
  const createIntentMutation = useCreateGitWriteIntentReadback();
  const intentQuery = useGitWriteIntentReadback(intentId);
  const auditQuery = useGitWriteAuditReadback(intentId);
  const approvalMutation = useRecordGitWriteApprovalReadback(intentId);
  const [latestRecord, setLatestRecord] = useState<GitWriteReadbackRecord | null>(null);

  useEffect(() => {
    if (createIntentMutation.data?.intent.intent_id) {
      setIntentId(createIntentMutation.data.intent.intent_id);
      setLatestRecord(createIntentMutation.data);
    }
  }, [createIntentMutation.data]);

  useEffect(() => {
    if (intentQuery.data) {
      setLatestRecord(intentQuery.data);
    }
  }, [intentQuery.data]);

  const record = intentQuery.data ?? latestRecord;
  const auditEvents = useMemo(
    () => auditQuery.data ?? record?.audit_events ?? [],
    [auditQuery.data, record?.audit_events],
  );
  const previewReady = record?.preview.status === "ready";
  const previewBlocked = record?.preview.status === "blocked";
  const canRecordApproval =
    Boolean(intentId) &&
    previewReady &&
    record?.preview.safety_snapshot.preview_gates_passed === true &&
    !approvalMutation.isPending;

  const handleCreateIntent = async () => {
    await createIntentMutation.mutateAsync();
  };

  const handleRecordApproval = async () => {
    if (!intentId) return;
    const updated = await approvalMutation.mutateAsync({
      actor: "web-user",
      approval_note: "UI readback confirmation recorded without repository side effects.",
    });
    setLatestRecord(updated);
  };

  return (
    <section
      data-testid="git-write-readback-panel"
      className="rounded border border-[#333333] bg-[#1a1a1a] p-4"
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">
              GitWrite-E readback
            </div>
            <h3 className="mt-2 text-base font-medium text-zinc-100">
              Preview / approval / audit readback
            </h3>
            <p className="mt-2 max-w-3xl text-xs leading-5 text-zinc-500">
              前端调用 GitWrite-D readback API，只展示 intent、preview、gate、rollback、用户确认记录与安全审计摘要。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void handleCreateIntent()}
              disabled={createIntentMutation.isPending}
              className="rounded border border-[#444444] px-3 py-1.5 text-xs text-zinc-200 transition hover:border-zinc-300 hover:bg-[#222222] disabled:cursor-not-allowed disabled:text-zinc-600"
            >
              {createIntentMutation.isPending ? "生成中..." : "生成 preview readback"}
            </button>
            <button
              type="button"
              onClick={() => void handleRecordApproval()}
              disabled={!canRecordApproval}
              className="rounded border border-cyan-500/40 px-3 py-1.5 text-xs text-cyan-100 transition hover:border-cyan-300 hover:bg-cyan-500/10 disabled:cursor-not-allowed disabled:border-[#333333] disabled:text-zinc-600 disabled:hover:bg-transparent"
            >
              {approvalMutation.isPending
                ? "记录中..."
                : "记录用户确认（不触发写入）"}
            </button>
          </div>
        </div>

        <div className="grid gap-1.5">
          {SAFETY_READBACK_POINTS.map((point) => (
            <p
              key={point}
              className="rounded border border-cyan-500/20 bg-cyan-500/5 px-2 py-1 text-[10px] leading-4 text-cyan-100/80"
            >
              {point}
            </p>
          ))}
        </div>

        {createIntentMutation.isError ? (
          <PanelState
            tone="error"
            message={`preview readback 生成失败：${createIntentMutation.error.message}`}
          />
        ) : null}

        {intentQuery.isError ? (
          <PanelState
            tone="error"
            message={`intent readback 读取失败：${intentQuery.error.message}`}
          />
        ) : null}

        {approvalMutation.isError ? (
          <PanelState
            tone="error"
            message={`用户确认记录失败：${approvalMutation.error.message}`}
          />
        ) : null}

        {!record ? (
          <PanelState message="点击生成 preview readback，使用内置安全 seed payload；不读取真实仓库差异、环境变量或密钥。" />
        ) : (
          <div className="grid gap-4">
            <div className="grid gap-3 xl:grid-cols-4">
              <ReadbackMetric label="intent id" value={record.intent.intent_id} />
              <ReadbackMetric label="target branch" value={record.intent.target_branch} />
              <ReadbackMetric
                label="preview status"
                value={formatStatus(record.preview.status)}
                tone={previewReady ? "success" : previewBlocked ? "danger" : "warning"}
              />
              <ReadbackMetric
                label="product_runtime_git_write_executed"
                value={record.product_runtime_git_write_executed ? "true" : "false"}
                tone={record.product_runtime_git_write_executed ? "danger" : "success"}
              />
            </div>

            <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_360px]">
              <div className="space-y-3">
                <ReadbackSummary record={record} />
                <SafetyGateList gates={record.preview.safety_snapshot.gate_checks} />
                <AuditTimeline
                  events={auditEvents}
                  loading={auditQuery.isFetching && auditEvents.length === 0}
                  error={auditQuery.isError ? auditQuery.error.message : null}
                />
              </div>
              <div className="space-y-3">
                <ApprovalReadback approval={record.approval} summary={record.approval_summary} />
                <LaterStageStatus />
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function ReadbackSummary({ record }: { record: GitWriteReadbackRecord }) {
  const snapshot = record.preview.safety_snapshot;
  const rollback = record.rollback_plan ?? record.preview.rollback_plan;

  return (
    <article className="rounded border border-[#333333] bg-[#111111] p-3">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge
          label={`preview gates passed: ${snapshot.preview_gates_passed ? "true" : "false"}`}
          tone={snapshot.preview_gates_passed ? "success" : "warning"}
        />
        <StatusBadge
          label={`full all_passed: ${snapshot.all_passed ? "true" : "false"}`}
          tone={snapshot.all_passed ? "success" : "warning"}
        />
        <StatusBadge label="runtime write: Not started" tone="success" />
      </div>
      <div className="mt-3 grid gap-2 text-xs leading-5 text-zinc-400">
        <DetailRow label="preview status 语义" value="READY 只代表 preview ready，不代表后续阶段已完成。" />
        <DetailRow
          label="pending 语义"
          value="human_approval 与 one_shot_token 在 preview 阶段保持 pending，后续审批阶段处理。"
        />
        <DetailRow
          label="rollback plan summary"
          value={rollback?.summary ?? "暂无 rollback plan readback"}
        />
        <DetailRow
          label="diff summary"
          value={record.preview.diff_summary ?? "暂无 safe diff summary"}
        />
      </div>
    </article>
  );
}

function SafetyGateList({ gates }: { gates: GitWriteSafetyGateReadback[] }) {
  return (
    <article className="rounded border border-[#333333] bg-[#111111] p-3">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h4 className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">
          Safety gates
        </h4>
        <StatusBadge label={`${gates.length} gates`} tone="info" />
      </div>
      <div className="grid gap-2 md:grid-cols-2">
        {gates.map((gate) => (
          <div key={gate.gate_name} className="rounded border border-[#333333] p-2">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate text-xs font-medium text-zinc-200">
                  {gate.gate_name}
                </p>
                <p className="mt-1 text-[10px] leading-4 text-zinc-600">
                  {gate.safe_summary ?? gate.block_reason ?? "safe summary unavailable"}
                </p>
              </div>
              <StatusBadge label={formatStatus(gate.status)} tone={gateTone(gate.status)} />
            </div>
          </div>
        ))}
      </div>
    </article>
  );
}

function ApprovalReadback(props: {
  approval: GitWriteApprovalReadback | null;
  summary: string | null;
}) {
  if (!props.approval) {
    return (
      <article className="rounded border border-[#333333] bg-[#111111] p-3">
        <h4 className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">
          Approval readback
        </h4>
        <p className="mt-3 text-xs leading-5 text-zinc-500">
          尚未记录用户确认。preview ready 后可记录确认；该动作只产生 readback，不代表仓库已变化。
        </p>
      </article>
    );
  }

  return (
    <article className="rounded border border-[#333333] bg-[#111111] p-3">
      <h4 className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">
        Approval readback
      </h4>
      <div className="mt-3 space-y-2 text-xs leading-5">
        <DetailRow label="approval id" value={props.approval.approval_id} />
        <DetailRow label="decision/status" value={formatStatus(props.approval.decision)} />
        <DetailRow label="token hint" value={props.approval.one_shot_token.token_hint} />
        <DetailRow label="token status" value={formatStatus(props.approval.one_shot_token.status)} />
        <DetailRow label="expires_at" value={formatDateTime(props.approval.one_shot_token.expires_at)} />
        <DetailRow
          label="approval summary"
          value={props.summary ?? "已记录用户确认；仍未产生提交或推送。"}
        />
      </div>
      <p className="mt-3 rounded border border-cyan-500/20 bg-cyan-500/5 px-2 py-1 text-[10px] leading-4 text-cyan-100/80">
        已记录用户确认；仍未产生提交或推送；不代表已执行 Git 写。
      </p>
    </article>
  );
}

function AuditTimeline(props: {
  events: GitWriteAuditEventReadback[];
  loading: boolean;
  error: string | null;
}) {
  return (
    <article className="rounded border border-[#333333] bg-[#111111] p-3">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h4 className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">
          Audit timeline
        </h4>
        <StatusBadge label={`${props.events.length} events`} tone="info" />
      </div>
      {props.loading ? <PanelState message="正在读取 audit timeline..." /> : null}
      {props.error ? <PanelState tone="error" message={`audit timeline 读取失败：${props.error}`} /> : null}
      {!props.loading && !props.error && props.events.length === 0 ? (
        <PanelState message="暂无 audit timeline readback" />
      ) : null}
      <div className="space-y-2">
        {props.events.map((event) => (
          <div key={event.event_id} className="border-l border-[#333333] px-3 py-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-zinc-200">
                {event.event_type}
              </span>
              <StatusBadge
                label={event.append_only ? "append_only: true" : "append_only: false"}
                tone={event.append_only ? "success" : "danger"}
              />
              <StatusBadge label={`metadata_count: ${event.metadata_count}`} tone="info" />
            </div>
            <p className="mt-1 text-[10px] leading-4 text-zinc-500">
              {formatDateTime(event.timestamp)} · {event.safe_summary}
            </p>
          </div>
        ))}
      </div>
    </article>
  );
}

function LaterStageStatus() {
  return (
    <article className="rounded border border-[#333333] bg-[#111111] p-3">
      <h4 className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">
        Later stages
      </h4>
      <div className="mt-3 space-y-2">
        {LATER_STAGES.map(([stage, status]) => (
          <div key={stage} className="flex items-center justify-between gap-3 text-xs">
            <span className="text-zinc-400">{stage}</span>
            <StatusBadge label={status} tone="warning" />
          </div>
        ))}
      </div>
    </article>
  );
}

function ReadbackMetric(props: {
  label: string;
  value: string;
  tone?: "neutral" | "info" | "success" | "warning" | "danger";
}) {
  return (
    <div className="rounded border border-[#333333] bg-[#111111] px-3 py-2">
      <p className="text-[10px] uppercase tracking-[0.14em] text-zinc-600">
        {props.label}
      </p>
      <p className="mt-1 break-all text-sm font-medium text-zinc-100">
        {props.value}
      </p>
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
    <div>
      <p className="text-[10px] uppercase tracking-[0.14em] text-zinc-600">
        {label}
      </p>
      <p className="break-words text-xs text-zinc-300">{value}</p>
    </div>
  );
}

function PanelState(props: { message: string; tone?: "neutral" | "error" }) {
  return (
    <div
      className={`rounded border px-3 py-2 text-xs leading-5 ${
        props.tone === "error"
          ? "border-rose-500/40 bg-rose-950/20 text-rose-100"
          : "border-[#333333] bg-[#151515] text-zinc-500"
      }`}
    >
      {props.message}
    </div>
  );
}

function gateTone(status: string): "neutral" | "info" | "success" | "warning" | "danger" {
  if (status === "passed") return "success";
  if (status === "blocked") return "danger";
  if (status === "pending") return "warning";
  return "info";
}

function formatStatus(value: string): string {
  return value.replace(/_/g, " ").toUpperCase();
}
