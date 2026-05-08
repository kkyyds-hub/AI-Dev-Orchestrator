import { useMemo } from "react";

import {
  buildLatestRunRuntimeFields,
  buildRoleModelPolicyRuntimeFields,
  hasRoleModelPolicyRuntimeData,
  type LatestRunRuntimeContractInput,
  type LatestRunRuntimeField,
} from "../../lib/latestRunRuntimeContract";
import type { ConsoleRun } from "../console/types";

type SelectedRunRuntimeContract = {
  runtimeFields: LatestRunRuntimeField[];
  roleModelPolicyFields: LatestRunRuntimeField[];
  hasRoleModelPolicyData: boolean;
};

const EMPTY_SELECTED_RUN_RUNTIME_CONTRACT: SelectedRunRuntimeContract = {
  runtimeFields: [],
  roleModelPolicyFields: [],
  hasRoleModelPolicyData: false,
};

function buildSelectedRunRuntimeContractInput(
  selectedRun: ConsoleRun,
): LatestRunRuntimeContractInput {
  return {
    providerKey: selectedRun.provider_key,
    promptTemplateKey: selectedRun.prompt_template_key,
    promptTemplateVersion: selectedRun.prompt_template_version,
    tokenAccountingMode: selectedRun.token_accounting_mode,
    tokenPricingSource: selectedRun.token_pricing_source,
    promptCharCount: selectedRun.prompt_char_count,
    promptTokens: selectedRun.prompt_tokens,
    completionTokens: selectedRun.completion_tokens,
    totalTokens: selectedRun.total_tokens,
    estimatedCost: selectedRun.estimated_cost,
    providerReceiptId: selectedRun.provider_receipt_id,
    roleModelPolicySource: selectedRun.role_model_policy_source,
    roleModelPolicyDesiredTier: selectedRun.role_model_policy_desired_tier,
    roleModelPolicyAdjustedTier: selectedRun.role_model_policy_adjusted_tier,
    roleModelPolicyFinalTier: selectedRun.role_model_policy_final_tier,
    roleModelPolicyStageOverrideApplied:
      selectedRun.role_model_policy_stage_override_applied,
  };
}

export function useSelectedRunRuntimeContract(
  selectedRun: ConsoleRun | null,
): SelectedRunRuntimeContract {
  return useMemo(() => {
    if (!selectedRun) {
      return EMPTY_SELECTED_RUN_RUNTIME_CONTRACT;
    }

    const runtimeContractInput = buildSelectedRunRuntimeContractInput(selectedRun);

    return {
      runtimeFields: buildLatestRunRuntimeFields(runtimeContractInput),
      roleModelPolicyFields:
        buildRoleModelPolicyRuntimeFields(runtimeContractInput),
      hasRoleModelPolicyData:
        hasRoleModelPolicyRuntimeData(runtimeContractInput),
    };
  }, [selectedRun]);
}
