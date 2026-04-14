import {
  NA_TEXT,
  formatNullableCurrencyUsd,
  formatNullableText,
  formatNullableTokenCount,
} from "./format";

const RUNTIME_EMPTY_TEXT_VALUES = new Set(["unknown", "not returned", "null"]);

export type LatestRunRuntimeContractInput = {
  providerKey?: string | null;
  promptTemplateKey?: string | null;
  promptTemplateVersion?: string | null;
  tokenAccountingMode?: string | null;
  tokenPricingSource?: string | null;
  promptCharCount?: number | null;
  promptTokens?: number | null;
  completionTokens?: number | null;
  totalTokens?: number | null;
  estimatedCost?: number | null;
  providerReceiptId?: string | null;
  roleModelPolicySource?: string | null;
  roleModelPolicyDesiredTier?: string | null;
  roleModelPolicyAdjustedTier?: string | null;
  roleModelPolicyFinalTier?: string | null;
  roleModelPolicyStageOverrideApplied?: boolean | null;
};

export type LatestRunRuntimeField = {
  key: string;
  label: string;
  value: string;
};

function formatRuntimeText(value: string | null | undefined): string {
  const formattedValue = formatNullableText(value);
  if (formattedValue === NA_TEXT) {
    return NA_TEXT;
  }

  const normalizedValue = formattedValue.toLowerCase();
  if (RUNTIME_EMPTY_TEXT_VALUES.has(normalizedValue)) {
    return NA_TEXT;
  }

  return formattedValue;
}

function hasRuntimeTextValue(value: string | null | undefined): boolean {
  return formatRuntimeText(value) !== NA_TEXT;
}

function formatPromptTemplate(
  promptTemplateKey: string | null | undefined,
  promptTemplateVersion: string | null | undefined,
): string {
  const normalizedTemplateKey = formatRuntimeText(promptTemplateKey);
  if (normalizedTemplateKey === NA_TEXT) {
    return NA_TEXT;
  }

  const normalizedTemplateVersion = formatRuntimeText(promptTemplateVersion);
  if (normalizedTemplateVersion === NA_TEXT) {
    return normalizedTemplateKey;
  }

  return `${normalizedTemplateKey} @${normalizedTemplateVersion}`;
}

function formatRoleModelPolicyStageOverride(value: boolean | null | undefined): string {
  if (value === null || value === undefined) {
    return NA_TEXT;
  }

  return value ? "yes" : "no";
}

export function buildLatestRunRuntimeFields(
  input: LatestRunRuntimeContractInput,
): LatestRunRuntimeField[] {
  return [
    {
      key: "provider",
      label: "Provider",
      value: formatRuntimeText(input.providerKey),
    },
    {
      key: "prompt_template",
      label: "Prompt Template",
      value: formatPromptTemplate(input.promptTemplateKey, input.promptTemplateVersion),
    },
    {
      key: "token_accounting",
      label: "Token Accounting",
      value: formatRuntimeText(input.tokenAccountingMode),
    },
    {
      key: "token_pricing",
      label: "Token Pricing",
      value: formatRuntimeText(input.tokenPricingSource),
    },
    {
      key: "prompt_chars",
      label: "Prompt Chars",
      value: formatNullableTokenCount(input.promptCharCount),
    },
    {
      key: "prompt_tokens",
      label: "Prompt Tokens",
      value: formatNullableTokenCount(input.promptTokens),
    },
    {
      key: "completion_tokens",
      label: "Completion Tokens",
      value: formatNullableTokenCount(input.completionTokens),
    },
    {
      key: "total_tokens",
      label: "Total Tokens",
      value: formatNullableTokenCount(input.totalTokens),
    },
    {
      key: "estimated_cost",
      label: "Estimated Cost",
      value: formatNullableCurrencyUsd(input.estimatedCost),
    },
    {
      key: "provider_receipt",
      label: "Provider Receipt",
      value: formatRuntimeText(input.providerReceiptId),
    },
  ];
}

export function buildRoleModelPolicyRuntimeFields(
  input: LatestRunRuntimeContractInput,
): LatestRunRuntimeField[] {
  return [
    {
      key: "policy_source",
      label: "Source",
      value: formatRuntimeText(input.roleModelPolicySource),
    },
    {
      key: "policy_desired_tier",
      label: "Desired Tier",
      value: formatRuntimeText(input.roleModelPolicyDesiredTier),
    },
    {
      key: "policy_adjusted_tier",
      label: "Adjusted Tier",
      value: formatRuntimeText(input.roleModelPolicyAdjustedTier),
    },
    {
      key: "policy_final_tier",
      label: "Final Tier",
      value: formatRuntimeText(input.roleModelPolicyFinalTier),
    },
    {
      key: "policy_stage_override",
      label: "Stage Override",
      value: formatRoleModelPolicyStageOverride(input.roleModelPolicyStageOverrideApplied),
    },
  ];
}

export function hasLatestRunRuntimeData(input: LatestRunRuntimeContractInput): boolean {
  return (
    hasRuntimeTextValue(input.providerKey) ||
    hasRuntimeTextValue(input.promptTemplateKey) ||
    hasRuntimeTextValue(input.promptTemplateVersion) ||
    hasRuntimeTextValue(input.tokenAccountingMode) ||
    hasRuntimeTextValue(input.tokenPricingSource) ||
    hasRuntimeTextValue(input.providerReceiptId) ||
    input.promptCharCount !== null && input.promptCharCount !== undefined ||
    input.promptTokens !== null && input.promptTokens !== undefined ||
    input.completionTokens !== null && input.completionTokens !== undefined ||
    input.totalTokens !== null && input.totalTokens !== undefined ||
    input.estimatedCost !== null && input.estimatedCost !== undefined
  );
}

export function hasRoleModelPolicyRuntimeData(
  input: LatestRunRuntimeContractInput,
): boolean {
  return (
    hasRuntimeTextValue(input.roleModelPolicySource) ||
    hasRuntimeTextValue(input.roleModelPolicyDesiredTier) ||
    hasRuntimeTextValue(input.roleModelPolicyAdjustedTier) ||
    hasRuntimeTextValue(input.roleModelPolicyFinalTier) ||
    input.roleModelPolicyStageOverrideApplied === true
  );
}
