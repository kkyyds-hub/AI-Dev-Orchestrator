import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { StatusBadge } from "../../components/StatusBadge";
import { requestJson } from "../../lib/http";

type ProviderSource = "saved_config" | "env" | "none";

type OpenAIProviderSettingsSummary = {
  provider_key: string;
  configured: boolean;
  masked_api_key: string | null;
  base_url: string;
  timeout_seconds: number;
  source: ProviderSource;
};

type OpenAIProviderSettingsUpdateRequest = {
  api_key?: string;
  base_url: string;
  timeout_seconds: number;
};

const SOURCE_LABELS: Record<ProviderSource, string> = {
  saved_config: "saved_config",
  env: "env",
  none: "none",
};

function fetchOpenAIProviderSettings(): Promise<OpenAIProviderSettingsSummary> {
  return requestJson<OpenAIProviderSettingsSummary>("/provider-settings/openai");
}

function updateOpenAIProviderSettings(
  payload: OpenAIProviderSettingsUpdateRequest,
): Promise<OpenAIProviderSettingsSummary> {
  return requestJson<OpenAIProviderSettingsSummary>("/provider-settings/openai", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function ProviderSettingsPanel() {
  const queryClient = useQueryClient();
  const providerSettingsQuery = useQuery({
    queryKey: ["provider-settings", "openai"],
    queryFn: fetchOpenAIProviderSettings,
  });
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [baseUrlInput, setBaseUrlInput] = useState("https://api.openai.com/v1");
  const [timeoutSecondsInput, setTimeoutSecondsInput] = useState("30");
  const [feedback, setFeedback] = useState<{
    tone: "success" | "warning" | "danger";
    text: string;
  } | null>(null);

  useEffect(() => {
    if (!providerSettingsQuery.data) {
      return;
    }
    setBaseUrlInput(providerSettingsQuery.data.base_url);
    setTimeoutSecondsInput(String(providerSettingsQuery.data.timeout_seconds));
  }, [providerSettingsQuery.data]);

  const updateMutation = useMutation({
    mutationFn: updateOpenAIProviderSettings,
    onSuccess: async (result) => {
      setApiKeyInput("");
      setBaseUrlInput(result.base_url);
      setTimeoutSecondsInput(String(result.timeout_seconds));
      setFeedback({
        tone: "success",
        text: "Provider settings saved.",
      });
      await queryClient.invalidateQueries({
        queryKey: ["provider-settings", "openai"],
      });
    },
    onError: (error) => {
      setFeedback({
        tone: "danger",
        text:
          error instanceof Error
            ? `Save failed: ${error.message}`
            : "Save failed due to an unknown error.",
      });
    },
  });

  const summary = providerSettingsQuery.data ?? null;
  const statusTone = summary?.configured ? "success" : "warning";
  const statusLabel = summary?.configured ? "configured" : "not configured";
  const sourceLabel = summary ? SOURCE_LABELS[summary.source] : "none";
  const maskedKeyText = summary?.masked_api_key ?? "not configured";
  const isSaving = updateMutation.isPending;

  const canSubmit = useMemo(() => {
    if (isSaving) {
      return false;
    }
    return baseUrlInput.trim().length > 0 && timeoutSecondsInput.trim().length > 0;
  }, [baseUrlInput, isSaving, timeoutSecondsInput]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFeedback(null);

    const timeoutSeconds = Number.parseInt(timeoutSecondsInput, 10);
    if (!Number.isFinite(timeoutSeconds) || timeoutSeconds < 1) {
      setFeedback({
        tone: "warning",
        text: "Timeout Seconds must be an integer greater than or equal to 1.",
      });
      return;
    }

    const payload: OpenAIProviderSettingsUpdateRequest = {
      base_url: baseUrlInput.trim(),
      timeout_seconds: timeoutSeconds,
    };

    const normalizedApiKey = apiKeyInput.trim();
    if (normalizedApiKey.length > 0) {
      payload.api_key = normalizedApiKey;
    }

    await updateMutation.mutateAsync(payload);
  };

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            Provider Settings
          </div>
          <p className="mt-2 text-sm text-slate-300">
            OpenAI runtime configuration for real provider execution.
          </p>
        </div>
        <StatusBadge label={statusLabel} tone={statusTone} />
      </div>

      {providerSettingsQuery.isLoading ? (
        <p className="mt-3 text-sm text-slate-400">Loading provider settings...</p>
      ) : providerSettingsQuery.isError ? (
        <p className="mt-3 text-sm text-rose-200">
          {providerSettingsQuery.error instanceof Error
            ? `Failed to load provider settings: ${providerSettingsQuery.error.message}`
            : "Failed to load provider settings."}
        </p>
      ) : (
        <>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <InfoItem label="Configured" value={summary?.configured ? "Yes" : "No"} />
            <InfoItem label="Masked API Key" value={maskedKeyText} />
            <InfoItem label="Source" value={sourceLabel} />
          </div>

          <form className="mt-4 space-y-3" onSubmit={handleSubmit}>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="space-y-2 text-xs uppercase tracking-[0.18em] text-slate-400">
                OpenAI API Key
                <input
                  type="password"
                  value={apiKeyInput}
                  onChange={(event) => setApiKeyInput(event.target.value)}
                  placeholder="sk-... (leave blank to keep current key)"
                  className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm normal-case tracking-normal text-slate-100 outline-none ring-cyan-500/40 transition focus:border-cyan-500 focus:ring"
                />
              </label>

              <label className="space-y-2 text-xs uppercase tracking-[0.18em] text-slate-400">
                Timeout Seconds
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={timeoutSecondsInput}
                  onChange={(event) => setTimeoutSecondsInput(event.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm normal-case tracking-normal text-slate-100 outline-none ring-cyan-500/40 transition focus:border-cyan-500 focus:ring"
                />
              </label>
            </div>

            <label className="space-y-2 text-xs uppercase tracking-[0.18em] text-slate-400">
              Base URL
              <input
                type="url"
                value={baseUrlInput}
                onChange={(event) => setBaseUrlInput(event.target.value)}
                placeholder="https://api.openai.com/v1"
                className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm normal-case tracking-normal text-slate-100 outline-none ring-cyan-500/40 transition focus:border-cyan-500 focus:ring"
              />
            </label>

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="submit"
                disabled={!canSubmit}
                className="rounded-xl border border-cyan-500/50 bg-cyan-500/20 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-500/30 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isSaving ? "Saving..." : "Save Provider Settings"}
              </button>
              {feedback ? (
                <span
                  className={`text-xs ${
                    feedback.tone === "success"
                      ? "text-emerald-200"
                      : feedback.tone === "warning"
                        ? "text-amber-200"
                        : "text-rose-200"
                  }`}
                >
                  {feedback.text}
                </span>
              ) : null}
            </div>
          </form>
        </>
      )}
    </section>
  );
}

function InfoItem(props: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2">
      <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
        {props.label}
      </div>
      <div className="mt-2 text-sm text-slate-200">{props.value}</div>
    </div>
  );
}
