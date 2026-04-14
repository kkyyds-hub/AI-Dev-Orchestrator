import type { WorkerRunOnceResponse } from "./types";

type WorkerRoleModelPolicyCardProps = Pick<
  WorkerRunOnceResponse,
  | "role_model_policy_source"
  | "role_model_policy_desired_tier"
  | "role_model_policy_adjusted_tier"
  | "role_model_policy_final_tier"
  | "role_model_policy_stage_override_applied"
>;

export function WorkerRoleModelPolicyCard(props: WorkerRoleModelPolicyCardProps) {
  if (!props.role_model_policy_source) {
    return null;
  }

  return (
    <div className="mt-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3">
      <div className="text-xs uppercase tracking-[0.2em] text-emerald-200">
        Role Model Policy Runtime
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <InfoItem label="Source" value={props.role_model_policy_source} />
        <InfoItem
          label="Desired Tier"
          value={props.role_model_policy_desired_tier ?? "n/a"}
        />
        <InfoItem
          label="Adjusted Tier"
          value={props.role_model_policy_adjusted_tier ?? "n/a"}
        />
        <InfoItem
          label="Final Tier"
          value={props.role_model_policy_final_tier ?? "n/a"}
        />
        <InfoItem
          label="Stage Override"
          value={props.role_model_policy_stage_override_applied ? "yes" : "no"}
        />
      </div>
    </div>
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

