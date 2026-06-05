import { formatNullableText } from "../../lib/format";
import type { WorkerRunOnceResponse } from "./types";

type WorkerRuntimeLaunchGateEvidenceCardProps = Pick<
  WorkerRunOnceResponse,
  | "agent_session_id"
  | "agent_type"
  | "runtime_type"
  | "runtime_handle_id"
  | "coding_status"
  | "activity_state"
  | "workspace_context_ready"
  | "workspace_context_source"
  | "workspace_context_reason_code"
  | "workspace_context_resolved_path"
  | "workspace_context_uses_agent_workspace"
  | "runtime_launch_dry_run_ready"
  | "runtime_launch_dry_run_reason_code"
  | "runtime_launch_dry_run_launch_cwd_preview"
  | "runtime_launch_dry_run_launch_command_preview"
  | "runtime_launch_dry_run_execution_enabled"
  | "runtime_launch_dry_run_changes_cwd"
  | "runtime_launch_dry_run_runs_command"
  | "runtime_launch_dry_run_runs_git"
  | "runtime_launch_dry_run_runs_write_git"
  | "runtime_launch_dry_run_launches_runtime"
  | "runtime_launch_gate_ready"
  | "runtime_launch_gate_gates_passed"
  | "runtime_launch_gate_gates_failed"
  | "runtime_launch_gate_blocking_reason_code"
  | "runtime_launch_gate_blocking_summary"
  | "runtime_launch_gate_changes_process_cwd"
  | "runtime_launch_gate_runs_real_command"
  | "runtime_launch_gate_runs_git"
  | "runtime_launch_gate_runs_write_git"
  | "runtime_launch_gate_launches_ai_runtime"
  | "runtime_launch_gate_execution_enabled"
  | "runtime_lifecycle_snapshot"
  | "worktree_safe_command_proof_ready"
  | "worktree_safe_command_proof_reason_code"
  | "worktree_safe_command_proof_observed_pwd"
  | "worktree_safe_command_proof_pwd_matches_workspace_path"
>;

type EvidenceField = {
  key: string;
  label: string;
  value: string;
  tone?: "safe" | "warning" | "danger" | "neutral";
};

export function WorkerRuntimeLaunchGateEvidenceCard(
  props: WorkerRuntimeLaunchGateEvidenceCardProps,
) {
  if (!hasRuntimeLaunchGateEvidence(props)) {
    return null;
  }

  const gateTone =
    props.runtime_launch_gate_ready === false
      ? "danger"
      : props.runtime_launch_gate_ready === true
        ? "safe"
        : "neutral";
  const gateStatusLabel =
    props.runtime_launch_gate_ready === false
      ? "Controlled Blocked"
      : props.runtime_launch_gate_ready === true
        ? "Ready (gates only)"
        : "Evidence not received";
  const gateStatusCopy =
    props.runtime_launch_gate_ready === false
      ? "Runtime gate stopped executor dispatch by design. This is a controlled safety block, not a crash."
      : props.runtime_launch_gate_ready === true
        ? "All runtime launch gates passed. This means prerequisites are ready only; no fake launch or real runtime was started."
        : "The worker response did not include runtime launch gate evidence for this run.";

  const contextFields: EvidenceField[] = [
    {
      key: "agent_session",
      label: "AgentSession",
      value: formatNullableText(props.agent_session_id),
    },
    {
      key: "agent_runtime",
      label: "Agent / Runtime",
      value: `${formatNullableText(props.agent_type)} / ${formatNullableText(
        props.runtime_type,
      )}`,
    },
    {
      key: "runtime_handle",
      label: "Runtime Handle",
      value: formatNullableText(props.runtime_handle_id),
      tone: props.runtime_handle_id ? "warning" : "safe",
    },
    {
      key: "coding_activity",
      label: "Coding / Activity",
      value: `${formatNullableText(props.coding_status)} / ${formatNullableText(
        props.activity_state,
      )}`,
    },
    {
      key: "workspace_context",
      label: "Workspace Context",
      value: formatBooleanEvidence(props.workspace_context_ready),
      tone: booleanTone(props.workspace_context_ready),
    },
    {
      key: "workspace_source",
      label: "Workspace Source",
      value: formatNullableText(
        props.workspace_context_reason_code ?? props.workspace_context_source,
      ),
    },
    {
      key: "agent_workspace",
      label: "Uses Agent Workspace",
      value: formatBooleanEvidence(props.workspace_context_uses_agent_workspace),
      tone: booleanTone(props.workspace_context_uses_agent_workspace),
    },
    {
      key: "workspace_path",
      label: "Resolved Workspace",
      value: formatNullableText(props.workspace_context_resolved_path),
    },
  ];

  const dryRunFields: EvidenceField[] = [
    {
      key: "dry_run_ready",
      label: "Dry-run Ready",
      value: formatBooleanEvidence(props.runtime_launch_dry_run_ready),
      tone: booleanTone(props.runtime_launch_dry_run_ready),
    },
    {
      key: "dry_run_reason",
      label: "Dry-run Reason",
      value: formatNullableText(props.runtime_launch_dry_run_reason_code),
    },
    {
      key: "launch_cwd_preview",
      label: "Launch CWD Preview",
      value: formatNullableText(props.runtime_launch_dry_run_launch_cwd_preview),
    },
    {
      key: "launch_command_preview",
      label: "Launch Command Preview",
      value: formatNullableText(props.runtime_launch_dry_run_launch_command_preview),
    },
    {
      key: "proof_ready",
      label: "Safe Command Proof",
      value: formatBooleanEvidence(props.worktree_safe_command_proof_ready),
      tone: booleanTone(props.worktree_safe_command_proof_ready),
    },
    {
      key: "proof_reason",
      label: "Proof Reason",
      value: formatNullableText(props.worktree_safe_command_proof_reason_code),
    },
    {
      key: "observed_pwd",
      label: "Observed PWD",
      value: formatNullableText(props.worktree_safe_command_proof_observed_pwd),
    },
    {
      key: "pwd_matches",
      label: "PWD Matches Workspace",
      value: formatBooleanEvidence(
        props.worktree_safe_command_proof_pwd_matches_workspace_path,
      ),
      tone: booleanTone(props.worktree_safe_command_proof_pwd_matches_workspace_path),
    },
  ];

  const safetyFields: EvidenceField[] = [
    {
      key: "snapshot_launch_requested",
      label: "Snapshot Launch Requested",
      value: formatBooleanEvidence(props.runtime_lifecycle_snapshot?.launch_requested),
      tone: props.runtime_lifecycle_snapshot?.launch_requested ? "danger" : "safe",
    },
    {
      key: "snapshot_fake_launch_started",
      label: "Snapshot Fake Launch",
      value: formatBooleanEvidence(
        props.runtime_lifecycle_snapshot?.fake_launch_started,
      ),
      tone: props.runtime_lifecycle_snapshot?.fake_launch_started ? "danger" : "safe",
    },
    {
      key: "snapshot_real_runtime_started",
      label: "Snapshot Real Runtime",
      value: formatBooleanEvidence(
        props.runtime_lifecycle_snapshot?.real_runtime_started,
      ),
      tone: props.runtime_lifecycle_snapshot?.real_runtime_started ? "danger" : "safe",
    },
    {
      key: "snapshot_runtime_probe_started",
      label: "Snapshot Runtime Probe",
      value: formatBooleanEvidence(
        props.runtime_lifecycle_snapshot?.runtime_probe_started,
      ),
      tone: props.runtime_lifecycle_snapshot?.runtime_probe_started ? "danger" : "safe",
    },
    {
      key: "gate_execution_enabled",
      label: "Gate Execution Enabled",
      value: formatBooleanEvidence(props.runtime_launch_gate_execution_enabled),
      tone: props.runtime_launch_gate_execution_enabled ? "danger" : "safe",
    },
    {
      key: "gate_launches_runtime",
      label: "Gate Launches AI Runtime",
      value: formatBooleanEvidence(props.runtime_launch_gate_launches_ai_runtime),
      tone: props.runtime_launch_gate_launches_ai_runtime ? "danger" : "safe",
    },
    {
      key: "gate_runs_command",
      label: "Gate Runs Real Command",
      value: formatBooleanEvidence(props.runtime_launch_gate_runs_real_command),
      tone: props.runtime_launch_gate_runs_real_command ? "danger" : "safe",
    },
    {
      key: "gate_changes_cwd",
      label: "Gate Changes CWD",
      value: formatBooleanEvidence(props.runtime_launch_gate_changes_process_cwd),
      tone: props.runtime_launch_gate_changes_process_cwd ? "danger" : "safe",
    },
    {
      key: "gate_runs_git",
      label: "Gate Runs Git",
      value: formatBooleanEvidence(props.runtime_launch_gate_runs_git),
      tone: props.runtime_launch_gate_runs_git ? "danger" : "safe",
    },
    {
      key: "gate_runs_write_git",
      label: "Gate Runs Write Git",
      value: formatBooleanEvidence(props.runtime_launch_gate_runs_write_git),
      tone: props.runtime_launch_gate_runs_write_git ? "danger" : "safe",
    },
    {
      key: "dry_run_execution_enabled",
      label: "Dry-run Execution Enabled",
      value: formatBooleanEvidence(props.runtime_launch_dry_run_execution_enabled),
      tone: props.runtime_launch_dry_run_execution_enabled ? "danger" : "safe",
    },
    {
      key: "dry_run_launches_runtime",
      label: "Dry-run Launches Runtime",
      value: formatBooleanEvidence(props.runtime_launch_dry_run_launches_runtime),
      tone: props.runtime_launch_dry_run_launches_runtime ? "danger" : "safe",
    },
    {
      key: "dry_run_runs_command",
      label: "Dry-run Runs Command",
      value: formatBooleanEvidence(props.runtime_launch_dry_run_runs_command),
      tone: props.runtime_launch_dry_run_runs_command ? "danger" : "safe",
    },
    {
      key: "dry_run_changes_cwd",
      label: "Dry-run Changes CWD",
      value: formatBooleanEvidence(props.runtime_launch_dry_run_changes_cwd),
      tone: props.runtime_launch_dry_run_changes_cwd ? "danger" : "safe",
    },
    {
      key: "dry_run_runs_git",
      label: "Dry-run Runs Git",
      value: formatBooleanEvidence(props.runtime_launch_dry_run_runs_git),
      tone: props.runtime_launch_dry_run_runs_git ? "danger" : "safe",
    },
    {
      key: "dry_run_runs_write_git",
      label: "Dry-run Runs Write Git",
      value: formatBooleanEvidence(props.runtime_launch_dry_run_runs_write_git),
      tone: props.runtime_launch_dry_run_runs_write_git ? "danger" : "safe",
    },
  ];

  return (
    <div
      data-testid="worker-runtime-launch-gate-evidence-card"
      className="mt-3 rounded-xl border border-[#333333] bg-transparent p-3"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-400">
            P3-B3 Runtime Launch Gate Evidence
          </div>
          <p className="mt-2 text-sm leading-6 text-zinc-300">
            Read-only evidence from the worker response. It explains gate readiness
            or controlled blocking; it does not imply a runtime was launched.
          </p>
          <p className="mt-2 text-sm leading-6 text-zinc-300">
            {gateStatusCopy}
          </p>
        </div>
        <span
          data-testid="worker-runtime-launch-gate-status"
          className={`rounded-full border px-3 py-1 text-xs font-medium ${toneClass(
            gateTone,
          )}`}
        >
          {gateStatusLabel}
        </span>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {contextFields.map((field) => (
          <EvidenceInfo
            key={field.key}
            label={field.label}
            value={field.value}
            tone={field.tone}
          />
        ))}
      </div>

      <div className="mt-3 rounded-xl border border-[#333333] bg-[#1f1f1f] p-3">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">
          Gate Chain Evidence
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <EvidenceInfo
            key="gates_passed"
            label="Gates Passed"
            value={formatList(props.runtime_launch_gate_gates_passed)}
            tone="safe"
          />
          <EvidenceInfo
            key="gates_failed"
            label="Gates Failed"
            value={formatList(props.runtime_launch_gate_gates_failed)}
            tone={props.runtime_launch_gate_gates_failed.length ? "danger" : "safe"}
          />
          <EvidenceInfo
            key="blocking_reason"
            label="Controlled Blocking Reason"
            value={formatNullableText(props.runtime_launch_gate_blocking_reason_code)}
            tone={props.runtime_launch_gate_blocking_reason_code ? "danger" : "neutral"}
          />
          <EvidenceInfo
            key="blocking_summary"
            label="Controlled Blocking Summary"
            value={formatNullableText(props.runtime_launch_gate_blocking_summary)}
            tone={props.runtime_launch_gate_blocking_summary ? "warning" : "neutral"}
          />
        </div>
      </div>

      {props.runtime_lifecycle_snapshot ? (
        <div className="mt-3 rounded-xl border border-[#333333] bg-[#1f1f1f] p-3">
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">
            P3-C1 Runtime Lifecycle Snapshot
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <EvidenceInfo
              label="Snapshot Source"
              value={formatNullableText(props.runtime_lifecycle_snapshot.source)}
            />
            <EvidenceInfo
              label="Runtime State / Reason"
              value={`${formatNullableText(
                props.runtime_lifecycle_snapshot.state,
              )} / ${formatNullableText(props.runtime_lifecycle_snapshot.reason)}`}
            />
            <EvidenceInfo
              label="Snapshot Reason Code"
              value={formatNullableText(props.runtime_lifecycle_snapshot.reason_code)}
            />
            <EvidenceInfo
              label="Adapter Kind"
              value={formatNullableText(props.runtime_lifecycle_snapshot.adapter_kind)}
            />
            <EvidenceInfo
              label="Snapshot Runtime Handle"
              value={formatNullableText(
                props.runtime_lifecycle_snapshot.runtime_handle_id,
              )}
              tone={props.runtime_lifecycle_snapshot.runtime_handle_id ? "warning" : "safe"}
            />
            <EvidenceInfo
              label="Probe State"
              value={formatNullableText(props.runtime_lifecycle_snapshot.probe_state)}
              tone={props.runtime_lifecycle_snapshot.probe_state ? "warning" : "safe"}
            />
            <EvidenceInfo
              label="Lifecycle Summary"
              value={props.runtime_lifecycle_snapshot.summary}
            />
          </div>
        </div>
      ) : null}

      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {dryRunFields.map((field) => (
          <EvidenceInfo
            key={field.key}
            label={field.label}
            value={field.value}
            tone={field.tone}
          />
        ))}
      </div>

      <div className="mt-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3">
        <div className="text-xs uppercase tracking-[0.2em] text-emerald-200">
          Safety Flags (all false means no launch)
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {safetyFields.map((field) => (
            <EvidenceInfo
              key={field.key}
              label={field.label}
              value={field.value}
              tone={field.tone}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function hasRuntimeLaunchGateEvidence(
  props: WorkerRuntimeLaunchGateEvidenceCardProps,
): boolean {
  return (
    props.runtime_launch_gate_ready !== null ||
    props.runtime_launch_dry_run_ready !== null ||
    props.workspace_context_ready !== null ||
    props.worktree_safe_command_proof_ready !== null ||
    props.runtime_launch_gate_gates_passed.length > 0 ||
    props.runtime_launch_gate_gates_failed.length > 0 ||
    Boolean(props.runtime_launch_gate_blocking_reason_code) ||
    props.runtime_lifecycle_snapshot !== null
  );
}

function EvidenceInfo(field: Omit<EvidenceField, "key">) {
  return (
    <div className={`rounded-xl border px-4 py-3 ${fieldToneClass(field.tone)}`}>
      <div className="text-xs uppercase tracking-[0.2em] opacity-70">{field.label}</div>
      <div className="mt-2 break-all text-sm font-medium">{field.value}</div>
    </div>
  );
}

function formatBooleanEvidence(value: boolean | null | undefined): string {
  if (value === null || value === undefined) {
    return "n/a";
  }

  return value ? "true" : "false";
}

function booleanTone(value: boolean | null | undefined): EvidenceField["tone"] {
  if (value === null || value === undefined) {
    return "neutral";
  }

  return value ? "safe" : "warning";
}

function formatList(values: string[]): string {
  return values.length ? values.join(" → ") : "none";
}

function toneClass(tone: EvidenceField["tone"]): string {
  switch (tone) {
    case "safe":
      return "border-emerald-500/30 bg-emerald-500/10 text-emerald-100";
    case "warning":
      return "border-amber-500/30 bg-amber-500/10 text-amber-100";
    case "danger":
      return "border-rose-500/30 bg-rose-500/10 text-rose-100";
    default:
      return "border-[#4a4a4a] bg-[#1f1f1f] text-zinc-100";
  }
}

function fieldToneClass(tone: EvidenceField["tone"]): string {
  switch (tone) {
    case "safe":
      return "border-emerald-500/20 bg-emerald-500/5 text-emerald-100";
    case "warning":
      return "border-amber-500/20 bg-amber-500/5 text-amber-100";
    case "danger":
      return "border-rose-500/20 bg-rose-500/5 text-rose-100";
    default:
      return "border-[#333333] bg-[#1f1f1f] text-zinc-100";
  }
}
