import {
  buildLatestRunRuntimeFields,
  hasLatestRunRuntimeData,
} from "../../lib/latestRunRuntimeContract";
import type { WorkerRunOnceResponse } from "./types";

type WorkerProviderPromptTokenCardProps = Pick<
  WorkerRunOnceResponse,
  | "provider_key"
  | "provider_receipt_id"
  | "prompt_template_key"
  | "prompt_template_version"
  | "prompt_char_count"
  | "token_accounting_mode"
  | "token_pricing_source"
  | "prompt_tokens"
  | "completion_tokens"
  | "total_tokens"
  | "estimated_cost"
>;

export function WorkerProviderPromptTokenCard(props: WorkerProviderPromptTokenCardProps) {
  const runtimeContractInput = {
    providerKey: props.provider_key,
    promptTemplateKey: props.prompt_template_key,
    promptTemplateVersion: props.prompt_template_version,
    tokenAccountingMode: props.token_accounting_mode,
    tokenPricingSource: props.token_pricing_source,
    promptCharCount: props.prompt_char_count,
    promptTokens: props.prompt_tokens,
    completionTokens: props.completion_tokens,
    totalTokens: props.total_tokens,
    estimatedCost: props.estimated_cost,
    providerReceiptId: props.provider_receipt_id,
  };
  const hasProviderPromptTokenData = hasLatestRunRuntimeData(runtimeContractInput);

  if (!hasProviderPromptTokenData) {
    return null;
  }

  const runtimeFields = buildLatestRunRuntimeFields(runtimeContractInput);

  return (
    <div className="mt-3 rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-3">
      <div className="text-xs uppercase tracking-[0.2em] text-cyan-200">
        Latest Run Runtime
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {runtimeFields.map((field) => (
          <InfoItem key={field.key} label={field.label} value={field.value} />
        ))}
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
