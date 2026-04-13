import { formatTokenCount } from "../../lib/format";
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
>;

export function WorkerProviderPromptTokenCard(props: WorkerProviderPromptTokenCardProps) {
  const hasProviderPromptTokenData = Boolean(
    props.provider_key ||
      props.prompt_template_key ||
      props.prompt_tokens !== null ||
      props.completion_tokens !== null ||
      props.total_tokens !== null,
  );

  if (!hasProviderPromptTokenData) {
    return null;
  }

  const effectiveTotalTokens =
    props.total_tokens ??
    (props.prompt_tokens !== null || props.completion_tokens !== null
      ? (props.prompt_tokens ?? 0) + (props.completion_tokens ?? 0)
      : null);

  return (
    <div className="mt-3 rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-3">
      <div className="text-xs uppercase tracking-[0.2em] text-cyan-200">
        Provider / Prompt / Token
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <InfoItem label="Provider" value={props.provider_key ?? "—"} />
        <InfoItem
          label="Prompt 模板"
          value={
            props.prompt_template_key
              ? `${props.prompt_template_key}${props.prompt_template_version ? ` @${props.prompt_template_version}` : ""}`
              : "—"
          }
        />
        <InfoItem
          label="Prompt 字符数"
          value={
            props.prompt_char_count !== null
              ? formatTokenCount(props.prompt_char_count)
              : "—"
          }
        />
        <InfoItem
          label="Token (P/C/T)"
          value={
            props.prompt_tokens !== null ||
            props.completion_tokens !== null ||
            effectiveTotalTokens !== null
              ? `${formatTokenCount(props.prompt_tokens ?? 0)} / ${formatTokenCount(props.completion_tokens ?? 0)} / ${formatTokenCount(effectiveTotalTokens ?? 0)}`
              : "—"
          }
        />
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <InfoItem label="记账模式" value={props.token_accounting_mode ?? "—"} />
        <InfoItem label="定价来源" value={props.token_pricing_source ?? "—"} />
        <InfoItem label="Provider 回执" value={props.provider_receipt_id ?? "—"} />
      </div>
    </div>
  );
}

function InfoItem(props: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{props.label}</div>
      <div className="mt-2 text-sm font-medium text-slate-100 break-all">{props.value}</div>
    </div>
  );
}
