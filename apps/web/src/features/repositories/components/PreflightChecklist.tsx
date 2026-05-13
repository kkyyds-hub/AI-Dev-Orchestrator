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
      className={props.className ?? "border-b border-[#333333] pb-4"}
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-sm font-semibold text-slate-50">预检结果</div>
          <div className="mt-2 text-sm leading-6 text-slate-400">
            {props.helperText ??
              "展示当前变更的范围、风险提示与确认前检查项，帮助判断是否可以继续推进。"}
          </div>
        </div>

        {props.onRunPreflight ? (
          <button
            type="button"
            onClick={props.onRunPreflight}
            disabled={props.runDisabled || props.isRunning}
            className={`rounded border px-4 py-2 text-sm font-medium transition ${
              props.runDisabled || props.isRunning
                ? "cursor-not-allowed border-[#333333] bg-transparent text-slate-500"
                : "border-[#4a4a4a] bg-transparent text-zinc-100 hover:bg-[#292929]"
            }`}
          >
            {props.isRunning ? "执行中..." : "运行预检"}
          </button>
        ) : null}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <StatusBadge
          label={CHANGE_BATCH_PREFLIGHT_STATUS_LABELS[props.preflight.status]}
          tone={statusTone}
        />
        <StatusBadge label={`任务 ${props.taskCount}`} tone="info" />
        <StatusBadge label={`文件 ${props.targetFileCount}`} tone="info" />
        <StatusBadge
          label={`重叠 ${props.overlapFileCount ?? 0}`}
          tone={(props.overlapFileCount ?? 0) > 0 ? "warning" : "success"}
        />
        {props.preflight.overall_severity ? (
          <StatusBadge
            label={CHANGE_BATCH_RISK_SEVERITY_LABELS[props.preflight.overall_severity]}
            tone={overallSeverityTone}
          />
        ) : null}
      </div>

      <div className="mt-4 border-l border-[#333333] px-4 py-3 text-sm leading-6 text-slate-300">
        <div className="font-medium text-slate-100">{props.title}</div>
        <div className="mt-2">{props.preflight.summary ?? "暂无预检摘要"}</div>
        <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
          <span>发现 {props.preflight.finding_count}</span>
          <span>检查项 {props.preflight.inspected_command_count}</span>
          {props.preflight.evaluated_at ? (
            <span>评估于 {formatDateTime(props.preflight.evaluated_at)}</span>
          ) : null}
          {props.preflight.requested_at ? (
            <span>请求于 {formatDateTime(props.preflight.requested_at)}</span>
          ) : null}
          {props.preflight.decided_at ? (
            <span>决策于 {formatDateTime(props.preflight.decided_at)}</span>
          ) : null}
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="严重" value={String(props.preflight.critical_risk_count)} tone="danger" />
        <MetricCard label="高" value={String(props.preflight.high_risk_count)} tone="warning" />
        <MetricCard label="中" value={String(props.preflight.medium_risk_count)} tone="info" />
        <MetricCard label="低" value={String(props.preflight.low_risk_count)} tone="neutral" />
      </div>

      {props.preflight.findings.length > 0 ? (
        <div className="mt-4 divide-y divide-[#333333] border-y border-[#333333]">
          {props.preflight.findings.map((finding) => (
            <article
              key={`${finding.code}-${finding.summary}`}
              className="px-0 py-4"
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
                  影响路径：{finding.affected_paths.join(" / ")}
                </div>
              ) : null}
              {finding.related_commands.length > 0 ? (
                <div className="mt-2 text-xs leading-5 text-slate-400">
                  关联命令：{finding.related_commands.join(" / ")}
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <div className="mt-4 border-l border-emerald-500/50 px-4 py-3 text-sm leading-6 text-emerald-100">
          当前未发现高风险项，可以继续推进到下一步。
        </div>
      )}

      {props.preflight.inspected_commands.length > 0 ? (
        <div className="mt-4 border-b border-[#333333] pb-4">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">检查项</div>
          <ul className="mt-3 divide-y divide-[#333333] border-y border-[#333333] text-sm leading-6 text-slate-300">
            {props.preflight.inspected_commands.map((command) => (
              <li key={command} className="break-all px-0 py-2">
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
    <div className="border-l border-[#333333] px-4 py-2">
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
      return "text-slate-100";
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
