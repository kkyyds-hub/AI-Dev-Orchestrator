import { requestJson } from "../../lib/http";
import type { RepositoryWorkspace } from "../projects/types";

export type ProviderSource = "saved_config" | "env" | "none";
export type ProviderModelPreset = "openai" | "deepseek" | "custom";
export type ProviderType = "openai" | "deepseek" | "openai_compatible";
export type TierModelNames = { economy: string; balanced: string; premium: string };

export type ProviderSettingsSummary = {
  provider_key: string;
  configured: boolean;
  masked_api_key?: string | null;
  base_url: string;
  timeout_seconds: number;
  source: ProviderSource;
  detected_provider_type: ProviderType;
  model_preset: ProviderModelPreset;
  model_names: TierModelNames;
};

export type ProviderTestResponse = {
  provider_key: string;
  configured: boolean;
  base_url: string;
  auth_valid: boolean;
  endpoint_reachable: boolean;
  api_family: string;
  model_name: string;
  model_usable: boolean;
  latency_ms: number;
  status: string;
  error_category: string | null;
  error_summary: string | null;
  tested_at: string | null;
};

export type ProviderUpdateRequest = {
  api_key?: string;
  base_url: string;
  timeout_seconds: number;
  model_preset?: ProviderModelPreset;
  model_names?: TierModelNames;
};

export type WorkspaceSettings = {
  allowed_workspace_roots: string[];
  default_workspace_root: string;
  using_default: boolean;
};

export type WorkspaceSettingsUpdate = {
  allowed_workspace_roots: string[];
};

export type WorkspaceBindRequest = {
  root_path: string;
  display_name?: string | null;
  access_mode: "read_only";
  default_base_branch: string;
  ignore_rule_summary: string[];
};

export type AccountProfileSource = "saved_config" | "env" | "default";

export type AccountProfile = {
  account_id: string;
  display_name: string;
  notification_email: string;
  login_method: string;
  default_role: string;
  source: AccountProfileSource;
};

export type AccountProfileUpdate = {
  display_name: string;
  notification_email: string;
};

export type HealthStatus = {
  status: string;
  detail?: string;
};

export function fetchProvider(): Promise<ProviderSettingsSummary> {
  return requestJson("/provider-settings/openai");
}

export function updateProvider(payload: ProviderUpdateRequest): Promise<ProviderSettingsSummary> {
  return requestJson("/provider-settings/openai", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function testProviderConnection(): Promise<ProviderTestResponse> {
  return requestJson("/provider-settings/openai/test", { method: "POST" });
}

export function fetchHealth(): Promise<HealthStatus> {
  return requestJson("/health");
}

export function fetchWorkspaceSettings(): Promise<WorkspaceSettings> {
  return requestJson("/repositories/workspace-settings");
}

export function fetchAccountProfile(): Promise<AccountProfile> {
  return requestJson("/account/profile");
}

export function updateAccountProfile(payload: AccountProfileUpdate): Promise<AccountProfile> {
  return requestJson("/account/profile", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function updateWorkspaceSettings(payload: WorkspaceSettingsUpdate): Promise<WorkspaceSettings> {
  return requestJson("/repositories/workspace-settings", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function bindProjectRepo(input: {
  projectId: string;
  payload: WorkspaceBindRequest;
}): Promise<RepositoryWorkspace> {
  return requestJson(`/repositories/projects/${input.projectId}`, {
    method: "PUT",
    body: JSON.stringify(input.payload),
  });
}
