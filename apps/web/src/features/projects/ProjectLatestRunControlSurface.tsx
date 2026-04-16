import {
  formatDateTime,
  formatNullableText,
} from "../../lib/format";
import {
  buildLatestRunRuntimeFields,
  buildRoleModelPolicyRuntimeFields,
  hasRoleModelPolicyRuntimeData,
} from "../../lib/latestRunRuntimeContract";

import type { BossDrilldownContext, BossProjectLatestTask } from "./types";

type ProjectLatestRunControlSurfaceProps = {
  latestTask: BossProjectLatestTask;
  drilldownContext?: BossDrilldownContext | null;
  onNavigateToTaskDetail?: (() => void) | null;
  onNavigateToStrategyPreview?: (() => void) | null;
  onNavigateToRunLog?: (() => void) | null;
};

export function ProjectLatestRunControlSurface(props: ProjectLatestRunControlSurfaceProps) {
  if (!props.latestTask.latest_run_id) {
    return null;
  }

  const runtimeContractInput = {
    providerKey: props.latestTask.latest_run_provider_key,
    promptTemplateKey: props.latestTask.latest_run_prompt_template_key,
    promptTemplateVersion: props.latestTask.latest_run_prompt_template_version,
    tokenAccountingMode: props.latestTask.latest_run_token_accounting_mode,
    tokenPricingSource: props.latestTask.latest_run_token_pricing_source,
    promptCharCount: props.latestTask.latest_run_prompt_char_count,
    promptTokens: props.latestTask.latest_run_prompt_tokens,
    completionTokens: props.latestTask.latest_run_completion_tokens,
    totalTokens: props.latestTask.latest_run_total_tokens,
    estimatedCost: props.latestTask.latest_run_estimated_cost,
    providerReceiptId: props.latestTask.latest_run_provider_receipt_id,
    roleModelPolicySource: props.latestTask.latest_run_role_model_policy_source,
    roleModelPolicyDesiredTier: props.latestTask.latest_run_role_model_policy_desired_tier,
    roleModelPolicyAdjustedTier: props.latestTask.latest_run_role_model_policy_adjusted_tier,
    roleModelPolicyFinalTier: props.latestTask.latest_run_role_model_policy_final_tier,
    roleModelPolicyStageOverrideApplied:
      props.latestTask.latest_run_role_model_policy_stage_override_applied,
  };
  const runtimeFields = buildLatestRunRuntimeFields(runtimeContractInput);
  const roleModelPolicyFields = buildRoleModelPolicyRuntimeFields(runtimeContractInput);
  const hasRoleModelPolicyData = hasRoleModelPolicyRuntimeData(runtimeContractInput);
  const hasDrilldownContext = Boolean(props.drilldownContext);
  const drilldownMatchesTask =
    props.drilldownContext?.task_id === props.latestTask.task_id;
  const drilldownMatchesRun =
    !props.drilldownContext?.run_id ||
    props.drilldownContext.run_id === props.latestTask.latest_run_id;
  const drilldownFullyMatched = Boolean(drilldownMatchesTask && drilldownMatchesRun);

  return (
    <section
      id="project-latest-run-control-surface"
      data-testid="project-latest-run-control-surface"
      className="mt-3 rounded-2xl border border-cyan-500/20 bg-cyan-500/5 p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-xs uppercase tracking-[0.2em] text-cyan-200">
          Latest Run Control Surface
        </div>
        {props.onNavigateToTaskDetail ||
        props.onNavigateToStrategyPreview ||
        props.onNavigateToRunLog ? (
          <div className="flex flex-wrap items-center gap-2">
            {props.onNavigateToTaskDetail ? (
              <button
                type="button"
                data-testid="goto-task-detail-from-project-latest-run"
                onClick={props.onNavigateToTaskDetail}
                className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-3 py-1.5 text-xs text-cyan-100 transition hover:bg-cyan-500/20"
              >
                Drill-down to Task Detail
              </button>
            ) : null}
            {props.onNavigateToStrategyPreview ? (
              <button
                type="button"
                data-testid="goto-strategy-preview-from-latest-run"
                onClick={props.onNavigateToStrategyPreview}
                className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-3 py-1.5 text-xs text-cyan-100 transition hover:bg-cyan-500/20"
              >
                Drill-down to Strategy Preview
              </button>
            ) : null}
            {props.onNavigateToRunLog ? (
              <button
                type="button"
                data-testid="goto-run-log-from-project-latest-run"
                onClick={props.onNavigateToRunLog}
                className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-3 py-1.5 text-xs text-cyan-100 transition hover:bg-cyan-500/20"
              >
                Drill-down to Run Log
              </button>
            ) : null}
          </div>
        ) : null}
      </div>

      {hasDrilldownContext ? (
        <div
          data-testid="project-latest-run-drilldown-status"
          className={`mt-3 rounded-xl border p-3 text-xs ${
            drilldownFullyMatched
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-100"
              : "border-amber-500/30 bg-amber-500/10 text-amber-100"
          }`}
        >
          <div className="font-medium">
            {drilldownFullyMatched
              ? "Current run matches the drill-down context."
              : "Current run sample differs from the drill-down context."}
          </div>
          <div className="mt-1">
            source={props.drilldownContext?.source ?? "unknown"}; task=
            {props.drilldownContext?.task_id ?? "n/a"}; run=
            {props.drilldownContext?.run_id ?? "n/a"}
          </div>
        </div>
      ) : null}

      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <InfoItem
          testId="project-latest-run-run-id-field"
          label="Run ID"
          value={props.latestTask.latest_run_id}
        />
        <InfoItem
          label="Run Status"
          value={formatNullableText(props.latestTask.latest_run_status)}
        />
        <InfoItem
          label="Model"
          value={
            props.latestTask.latest_run_model_name
              ? `${props.latestTask.latest_run_model_name}${
                  props.latestTask.latest_run_model_tier
                    ? ` (${props.latestTask.latest_run_model_tier})`
                    : ""
                }`
              : "n/a"
          }
        />
        <InfoItem
          label="Strategy"
          value={formatNullableText(props.latestTask.latest_run_strategy_code)}
        />
      </div>

      <div
        data-testid="project-latest-run-runtime-card"
        className="mt-3 rounded-xl border border-cyan-400/20 bg-cyan-500/5 p-3"
      >
        <div className="text-xs uppercase tracking-[0.2em] text-cyan-200">
          Latest Run Runtime
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {runtimeFields.map((field) => (
            <InfoItem
              key={field.key}
              testId={`project-latest-run-runtime-field-${field.key}`}
              label={field.label}
              value={field.value}
            />
          ))}
        </div>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <InfoItem
          label="Created At"
          value={
            props.latestTask.latest_run_created_at
              ? formatDateTime(props.latestTask.latest_run_created_at)
              : "n/a"
          }
        />
        <InfoItem
          label="Finished At"
          value={
            props.latestTask.latest_run_finished_at
              ? formatDateTime(props.latestTask.latest_run_finished_at)
              : "n/a"
          }
        />
      </div>

      {hasRoleModelPolicyData ? (
        <div
          data-testid="project-latest-run-policy-card"
          className="mt-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3"
        >
          <div className="text-xs uppercase tracking-[0.2em] text-emerald-200">
            Role Model Policy Runtime
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {roleModelPolicyFields.map((field) => (
              <InfoItem
                key={field.key}
                testId={`project-latest-run-policy-field-${field.key}`}
                label={field.label}
                value={field.value}
              />
            ))}
          </div>
        </div>
      ) : null}

      {props.latestTask.latest_run_log_path ? (
        <div className="mt-3 rounded-xl border border-slate-800 bg-slate-950/60 p-3">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Run Log</div>
          <code className="mt-2 block break-all text-xs text-cyan-200">
            {props.latestTask.latest_run_log_path}
          </code>
        </div>
      ) : null}
    </section>
  );
}

function InfoItem(props: { label: string; value: string; testId?: string }) {
  return (
    <div
      data-testid={props.testId}
      className="rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3"
    >
      <div data-slot="label" className="text-xs uppercase tracking-[0.2em] text-slate-500">
        {props.label}
      </div>
      <div data-slot="value" className="mt-2 break-all text-sm font-medium text-slate-100">
        {props.value}
      </div>
    </div>
  );
}
