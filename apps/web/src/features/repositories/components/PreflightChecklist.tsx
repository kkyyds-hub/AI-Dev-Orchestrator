import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import type { ChangeBatchPreflight } from "../types";
import {
  CHANGE_BATCH_PREFLIGHT_STATUS_LABELS,
  CHANGE_BATCH_RISK_CATEGORY_LABELS,
  CHANGE_BATCH_RISK_SEVERITY_LABELS,
} from "../types";

type PreflightChecklistProps = {
  title: string;
  preflight: ChangeBatchPreflight;
  targetFileCount: number;
  taskCount: number;
  overlapFileCount?: number;
  onRunPreflight?: () => void;
  isRunning?: boolean;
  runDisabled?: boolean;
  helperText?: string;
  className?: string;
};

export function PreflightChecklist(props: PreflightChecklistProps) {
  const statusTone = mapPreflightTone(props.preflight.status);
  const overallSeverityTone = props.preflight.overall_severity
    ? mapSeverityTone(props.preflight.overall_severity)
    : "neutral";

  return (
    <section
      className={props.className ?? "rounded-2xl border border-slate-800 bg-slate-900/60 p-4"}
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-sm font-semibold text-slate-50">??????????</div>
          <div className="mt-2 text-sm leading-6 text-slate-400">
            {props.helperText ??
              "Day08 ??????????????????????????????????? Git ????"}
          </div>
        </div>

        {props.onRunPreflight ? (
          <button
            type="button"
            onClick={props.onRunPreflight}
            disabled={props.runDisabled || props.isRunning}
            className={`rounded-xl border px-4 py-2 text-sm font-medium transition ${
              props.runDisabled || props.isRunning
                ? "cursor-not-allowed border-slate-800 bg-slate-950 text-slate-500"
                : "border-cyan-400/30 bg-cyan-500/10 text-cyan-100 hover:bg-cyan-500/20"
            }`}
          >
            {props.isRunning ? "??????..." : "????"}
          </button>
        ) : null}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <StatusBadge
          label={CHANGE_BATCH_PREFLIGHT_STATUS_LABELS[props.preflight.status]}
          tone={statusTone}
        />
        <StatusBadge label={`?? ${props.taskCount}`} tone="info" />
        <StatusBadge label={`???? ${props.targetFileCount}`} tone="info" />
        <StatusBadge
          label={`?? ${props.overlapFileCount ?? 0}`}
          tone={(props.overlapFileCount ?? 0) > 0 ? "warning" : "success"}
        />
        {props.preflight.overall_severity ? (
          <StatusBadge
            label={CHANGE_BATCH_RISK_SEVERITY_LABELS[props.preflight.overall_severity]}
            tone={overallSeverityTone}
          />
        ) : null}
      </div>

      <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3 text-sm leading-6 text-slate-300">
        <div className="font-medium text-slate-100">{props.title}</div>
        <div className="mt-2">{props.preflight.summary ?? "???????? Day08 ???"}</div>
        <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
          <span>??? {props.preflight.finding_count}</span>
          <span>???? {props.preflight.inspected_command_count}</span>
          {props.preflight.evaluated_at ? (
            <span>???? {formatDateTime(props.preflight.evaluated_at)}</span>
          ) : null}
          {props.preflight.requested_at ? (
            <span>??? {formatDateTime(props.preflight.requested_at)}</span>
          ) : null}
          {props.preflight.decided_at ? (
            <span>???? {formatDateTime(props.preflight.decided_at)}</span>
          ) : null}
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="????" value={String(props.preflight.critical_risk_count)} tone="danger" />
        <MetricCard label="???" value={String(props.preflight.high_risk_count)} tone="warning" />
        <MetricCard label="???" value={String(props.preflight.medium_risk_count)} tone="info" />
        <MetricCard label="???" value={String(props.preflight.low_risk_count)} tone="neutral" />
      </div>

      {props.preflight.findings.length > 0 ? (
        <div className="mt-4 space-y-3">
          {props.preflight.findings.map((finding) => (
            <article
              key={`${finding.code}-${finding.summary}`}
              className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-4"
            >
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge
                  label={CHANGE_BATCH_RISK_CATEGORY_LABELS[finding.category]}
                  tone="warning"
                />
                <StatusBadge
                  label={CHANGE_BATCH_RISK_SEVERITY_LABELS[finding.severity]}
                  tone={mapSeverityTone(finding.severity)}
                />
                <div className="text-sm font-medium text-slate-100">{finding.title}</div>
              </div>
              <div className="mt-2 text-sm leading-6 text-slate-300">{finding.summary}</div>
              {finding.affected_paths.length > 0 ? (
                <div className="mt-3 text-xs leading-5 text-slate-400">
                  ?????{finding.affected_paths.join(" / ")}
                </div>
              ) : null}
              {finding.related_commands.length > 0 ? (
                <div className="mt-2 text-xs leading-5 text-slate-400">
                  ?????{finding.related_commands.join(" / ")}
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <div className="mt-4 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm leading-6 text-emerald-100">
          ???????????????? Day08 ??????????????????? Day09+ ???????????????
        </div>
      )}

      {props.preflight.inspected_commands.length > 0 ? (
        <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-4">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">????????</div>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-300">
            {props.preflight.inspected_commands.map((command) => (
              <li key={command} className="break-all rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2">
                {command}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function MetricCard(props: {
  label: string;
  value: string;
  tone: "neutral" | "info" | "warning" | "danger";
}) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">{props.label}</div>
      <div className={`mt-2 text-sm font-semibold ${mapMetricClass(props.tone)}`}>{props.value}</div>
    </div>
  );
}

function mapMetricClass(tone: "neutral" | "info" | "warning" | "danger") {
  switch (tone) {
    case "danger":
      return "text-rose-100";
    case "warning":
      return "text-amber-100";
    case "info":
      return "text-cyan-100";
    default:
      return "text-slate-100";
  }
}

function mapPreflightTone(status: ChangeBatchPreflight["status"]) {
  switch (status) {
    case "ready_for_execution":
    case "manual_confirmed":
      return "success" as const;
    case "blocked_requires_confirmation":
      return "warning" as const;
    case "manual_rejected":
      return "danger" as const;
    default:
      return "neutral" as const;
  }
}

function mapSeverityTone(severity: NonNullable<ChangeBatchPreflight["overall_severity"]>) {
  switch (severity) {
    case "critical":
      return "danger" as const;
    case "high":
      return "warning" as const;
    case "medium":
      return "info" as const;
    default:
      return "neutral" as const;
  }
}
