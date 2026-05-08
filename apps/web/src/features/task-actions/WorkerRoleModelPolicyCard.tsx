import type { WorkerRunOnceResponse } from "./types";
import {
  buildRoleModelPolicyRuntimeFields,
  hasRoleModelPolicyRuntimeData,
} from "../../lib/latestRunRuntimeContract";

type WorkerRoleModelPolicyCardProps = Pick<
  WorkerRunOnceResponse,
  | "role_model_policy_source"
  | "role_model_policy_desired_tier"
  | "role_model_policy_adjusted_tier"
  | "role_model_policy_final_tier"
  | "role_model_policy_stage_override_applied"
>;

export function WorkerRoleModelPolicyCard(props: WorkerRoleModelPolicyCardProps) {
  const runtimeContractInput = {
    roleModelPolicySource: props.role_model_policy_source,
    roleModelPolicyDesiredTier: props.role_model_policy_desired_tier,
    roleModelPolicyAdjustedTier: props.role_model_policy_adjusted_tier,
    roleModelPolicyFinalTier: props.role_model_policy_final_tier,
    roleModelPolicyStageOverrideApplied: props.role_model_policy_stage_override_applied,
  };
  const hasRoleModelPolicyData = hasRoleModelPolicyRuntimeData(runtimeContractInput);

  if (!hasRoleModelPolicyData) {
    return null;
  }

  const roleModelPolicyFields = buildRoleModelPolicyRuntimeFields(runtimeContractInput);

  return (
    <div className="mt-3 rounded-xl border border-[#333333] bg-transparent p-3">
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-400">
        Role Model Policy Runtime
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {roleModelPolicyFields.map((field) => (
          <InfoItem key={field.key} label={field.label} value={field.value} />
        ))}
      </div>
    </div>
  );
}

function InfoItem(props: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[#333333] bg-[#1f1f1f] px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">{props.label}</div>
      <div className="mt-2 break-all text-sm font-medium text-zinc-100">{props.value}</div>
    </div>
  );
}

