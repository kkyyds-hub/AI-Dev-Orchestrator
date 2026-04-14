import { formatCurrencyUsd, formatDateTime, formatTokenCount } from "../../lib/format";

import type { BossProjectLatestTask } from "./types";

type ProjectLatestRunControlSurfaceProps = {
  latestTask: BossProjectLatestTask;
};

export function ProjectLatestRunControlSurface(props: ProjectLatestRunControlSurfaceProps) {
  if (!props.latestTask.latest_run_id) {
    return null;
  }

  const promptCharsText =
    props.latestTask.latest_run_prompt_char_count === null
      ? "n/a"
      : String(props.latestTask.latest_run_prompt_char_count);
  const tokenBreakdownText =
    props.latestTask.latest_run_prompt_tokens === null &&
    props.latestTask.latest_run_completion_tokens === null &&
    props.latestTask.latest_run_total_tokens === null
      ? "n/a"
      : `${formatTokenCount(props.latestTask.latest_run_prompt_tokens ?? 0)} / ${formatTokenCount(
          props.latestTask.latest_run_completion_tokens ?? 0,
        )} / ${formatTokenCount(props.latestTask.latest_run_total_tokens ?? 0)}`;
  const estimatedCostText =
    props.latestTask.latest_run_estimated_cost === null
      ? "n/a"
      : formatCurrencyUsd(props.latestTask.latest_run_estimated_cost);

  return (
    <section className="mt-3 rounded-2xl border border-cyan-500/20 bg-cyan-500/5 p-4">
      <div className="text-xs uppercase tracking-[0.2em] text-cyan-200">
        Latest Run Control Surface
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <InfoItem label="Run ID" value={props.latestTask.latest_run_id} />
        <InfoItem
          label="Run Status"
          value={props.latestTask.latest_run_status ?? "n/a"}
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
          value={props.latestTask.latest_run_strategy_code ?? "n/a"}
        />
        <InfoItem
          label="Provider"
          value={props.latestTask.latest_run_provider_key ?? "n/a"}
        />
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <InfoItem
          label="Prompt Template"
          value={
            props.latestTask.latest_run_prompt_template_key
              ? `${props.latestTask.latest_run_prompt_template_key}${
                  props.latestTask.latest_run_prompt_template_version
                    ? ` @${props.latestTask.latest_run_prompt_template_version}`
                    : ""
                }`
              : "n/a"
          }
        />
        <InfoItem
          label="Accounting Mode"
          value={props.latestTask.latest_run_token_accounting_mode ?? "n/a"}
        />
        <InfoItem
          label="Pricing Source"
          value={props.latestTask.latest_run_token_pricing_source ?? "n/a"}
        />
        <InfoItem
          label="Prompt Chars"
          value={promptCharsText}
        />
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <InfoItem
          label="Token P/C/T"
          value={tokenBreakdownText}
        />
        <InfoItem
          label="Provider Receipt"
          value={props.latestTask.latest_run_provider_receipt_id ?? "n/a"}
        />
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <InfoItem
          label="Estimated Cost"
          value={estimatedCostText}
        />
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

      {props.latestTask.latest_run_role_model_policy_source ? (
        <div className="mt-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3">
          <div className="text-xs uppercase tracking-[0.2em] text-emerald-200">
            Role Model Policy Runtime
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <InfoItem
              label="Source"
              value={props.latestTask.latest_run_role_model_policy_source}
            />
            <InfoItem
              label="Desired Tier"
              value={props.latestTask.latest_run_role_model_policy_desired_tier ?? "n/a"}
            />
            <InfoItem
              label="Adjusted Tier"
              value={props.latestTask.latest_run_role_model_policy_adjusted_tier ?? "n/a"}
            />
            <InfoItem
              label="Final Tier"
              value={props.latestTask.latest_run_role_model_policy_final_tier ?? "n/a"}
            />
            <InfoItem
              label="Stage Override"
              value={
                props.latestTask.latest_run_role_model_policy_stage_override_applied
                  ? "yes"
                  : "no"
              }
            />
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

function InfoItem(props: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{props.label}</div>
      <div className="mt-2 break-all text-sm font-medium text-slate-100">{props.value}</div>
    </div>
  );
}
