import type { ReactNode } from "react";

import type {
  RealExecutorLaunchReadbackRequest,
  RealExecutorLaunchReadbackResponse,
  RealExecutorSafetyBoundaryReadback,
} from "../../../features/runtime/types";
import { formatDateTime } from "../../../lib/format";

const REAL_EXECUTOR_READBACK_BOUNDARY: RealExecutorSafetyBoundaryReadback = {
  feature_flag_enabled: false,
  human_confirmation_present: false,
  executor_readiness_available: false,
  workspace_worktree_gate_passed: false,
  budget_cost_gate_passed: false,
  concurrency_gate_passed: false,
  timeout_supported: false,
  cancel_supported: false,
  kill_supported: false,
  audit_events_append_only: true,
  credential_exposure_blocked: true,
  environment_dump_blocked: true,
  product_runtime_git_write_allowed: false,
};

const DEFAULT_BLOCKING_REASONS = [
  "adapter remains disabled until a future approved phase",
];

const DEFAULT_DISPLAY_STEPS = [
  "Read safety boundary",
  "Build safe preview",
  "Return disabled adapter readback",
];

export function buildSafeRealExecutorReadbackRequest(): RealExecutorLaunchReadbackRequest {
  return {
    request_id: `ui-readback-${Date.now()}`,
    executor_label: "disabled-real-executor",
    command_summary: "read-only future launch summary",
    workspace_hint: "registered worktree",
    safety_boundary: REAL_EXECUTOR_READBACK_BOUNDARY,
  };
}

export function RealExecutorLaunchReadbackCard(props: {
  readback: RealExecutorLaunchReadbackResponse | null;
  loading: boolean;
  error: string | null;
  onBuild: (request: RealExecutorLaunchReadbackRequest) => void;
}) {
  const readback = props.readback;
  const blockingReasons = readback?.blocking_reasons ?? DEFAULT_BLOCKING_REASONS;
  const displaySteps = readback?.display_steps ?? DEFAULT_DISPLAY_STEPS;

  return (
    <div
      data-testid="real-executor-launch-readback-card"
      className="rounded border border-amber-500/25 bg-amber-500/5 p-3"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-xs font-semibold text-amber-100">
            真实执行器启动前只读读回
          </h3>
          <p className="mt-1 text-[10px] leading-4 text-amber-100/70">
            只读 readback；即使 preflight_ready=true，adapter 仍 disabled，且 real_executor_launch_started=false。
          </p>
        </div>
        <button
          type="button"
          onClick={() => props.onBuild(buildSafeRealExecutorReadbackRequest())}
          disabled={props.loading}
          className="w-fit rounded border border-amber-400/30 px-2 py-1 text-[10px] text-amber-100 transition hover:border-amber-300 hover:bg-amber-400/10 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {props.loading ? "读取中..." : "生成只读读回"}
        </button>
      </div>

      <div className="mt-3 grid gap-2 text-[10px] leading-4 text-zinc-500">
        <RuntimeSnapshotBlock title="readback safety flags">
          <RuntimeMetaRow label="api_mode" value={readback?.api_mode ?? "read_only"} />
          <RuntimeMetaRow
            label="adapter_enabled"
            value={formatBoolean(readback?.adapter_enabled ?? false)}
          />
          <RuntimeMetaRow
            label="adapter_launch_status"
            value={readback?.adapter_launch_status ?? "blocked"}
          />
          <RuntimeMetaRow
            label="preview_executable"
            value={formatBoolean(readback?.preview_executable ?? false)}
          />
          <RuntimeMetaRow
            label="real_executor_launch_started"
            value={formatBoolean(readback?.real_executor_launch_started ?? false)}
          />
          <RuntimeMetaRow
            label="product_runtime_git_write_allowed"
            value={formatBoolean(readback?.product_runtime_git_write_allowed ?? false)}
          />
        </RuntimeSnapshotBlock>

        <RuntimeSnapshotBlock title="preflight / preview readback">
          <RuntimeMetaRow
            label="readback_id"
            value={readback?.readback_id ?? "等待生成只读读回"}
          />
          <RuntimeMetaRow
            label="executor_label"
            value={readback?.executor_label ?? "disabled-real-executor"}
          />
          <RuntimeMetaRow
            label="preflight_ready"
            value={formatBoolean(readback?.preflight_ready ?? false)}
          />
          <RuntimeMetaRow
            label="preflight_status"
            value={readback?.preflight_status ?? "blocked"}
          />
          <RuntimeMetaRow
            label="preview_ready"
            value={formatBoolean(readback?.preview_ready ?? false)}
          />
          <RuntimeMetaRow
            label="redaction_applied"
            value={formatBoolean(readback?.redaction_applied ?? true)}
          />
          <RuntimeMetaRow
            label="created_at"
            value={readback ? formatDateTime(readback.created_at) : "等待生成只读读回"}
          />
        </RuntimeSnapshotBlock>

        <RuntimeSnapshotBlock title="blocking reasons">
          <ul className="space-y-1">
            {blockingReasons.map((reason) => (
              <li key={reason} className="rounded bg-[#171717] px-2 py-1 text-zinc-300">
                {reason}
              </li>
            ))}
          </ul>
        </RuntimeSnapshotBlock>

        <RuntimeSnapshotBlock title="display steps">
          <p className="mb-1 text-amber-100/70">
            说明性步骤，不是可运行指令。
          </p>
          <ol className="space-y-1">
            {displaySteps.map((step) => (
              <li key={step} className="rounded bg-[#171717] px-2 py-1 text-zinc-300">
                {step}
              </li>
            ))}
          </ol>
        </RuntimeSnapshotBlock>

        <RuntimeSnapshotBlock title="safe_summary">
          <p className="text-zinc-300">
            {readback?.safe_summary ?? "等待后端返回安全摘要；不展示原始启动细节。"}
          </p>
        </RuntimeSnapshotBlock>
      </div>

      {props.error ? (
        <RuntimePanelState
          testId="real-executor-launch-readback-error"
          tone="error"
          message={`只读 readback 读取失败：${props.error}`}
        />
      ) : null}
    </div>
  );
}

function RuntimeSnapshotBlock(props: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded border border-[#333333] bg-[#151515] p-2">
      <p className="mb-1.5 text-[10px] font-medium uppercase tracking-[0.14em] text-zinc-600">
        {props.title}
      </p>
      <div className="grid gap-1 text-[10px] leading-4 text-zinc-500">
        {props.children}
      </div>
    </div>
  );
}

function RuntimeMetaRow(props: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 items-start justify-between gap-2">
      <span className="shrink-0 text-zinc-600">{props.label}</span>
      <span className="min-w-0 break-words text-right text-zinc-300">
        {props.value}
      </span>
    </div>
  );
}

function RuntimePanelState(props: {
  testId: string;
  message: string;
  tone?: "default" | "error";
}) {
  return (
    <div
      data-testid={props.testId}
      className={`rounded border px-3 py-2 text-xs ${
        props.tone === "error"
          ? "border-red-500/30 bg-red-500/10 text-red-300"
          : "border-dashed border-[#333333] bg-[#111111] text-zinc-500"
      }`}
    >
      {props.message}
    </div>
  );
}

function formatBoolean(value: boolean) {
  return value ? "true" : "false";
}
