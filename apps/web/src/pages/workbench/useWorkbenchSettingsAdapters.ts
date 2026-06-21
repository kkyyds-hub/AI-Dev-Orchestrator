import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";

import {
  fetchAccountProfile,
  fetchProvider,
  fetchWorkspaceSettings,
  testProviderConnection,
  updateAccountProfile,
  updateProvider,
  updateWorkspaceSettings,
} from "../../features/settings/api";
import type { WorkbenchAccountAdapter } from "../../features/ui-selection-lab/components/AccountSettingsModal";
import type { SettingsDraft } from "../../features/ui-selection-lab/components/WorkbenchSettingsModal";
import type { WorkbenchActionToastStatus } from "./components/WorkbenchActionToast";

type WorkbenchActionFeedback = (
  message: string,
  status?: WorkbenchActionToastStatus,
) => void;

export function useWorkbenchSettingsAdapters(
  showActionFeedback: WorkbenchActionFeedback,
) {
  const queryClient = useQueryClient();

  const providerSettingsQuery = useQuery({
    queryKey: ["settings", "provider", "openai"],
    queryFn: fetchProvider,
    retry: false,
  });
  const workspaceSettingsQuery = useQuery({
    queryKey: ["settings", "workspace"],
    queryFn: fetchWorkspaceSettings,
    retry: false,
  });
  const accountProfileQuery = useQuery({
    queryKey: ["settings", "account-profile"],
    queryFn: fetchAccountProfile,
    retry: false,
  });
  const providerTestMutation = useMutation({
    mutationFn: testProviderConnection,
    retry: false,
  });
  const saveAccountMutation = useMutation({
    mutationFn: updateAccountProfile,
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["settings", "account-profile"],
      });
      showActionFeedback("账户信息已保存", "done");
    },
    onError: () => {
      showActionFeedback("账户信息保存失败", "failed");
    },
  });
  const saveSettingsMutation = useMutation({
    mutationFn: async (draft: SettingsDraft) => {
      const roots = draft.trustedRoot
        .split(/[\n,]/)
        .map((item) => item.trim())
        .filter(Boolean);
      const updates: Promise<unknown>[] = [];

      if (providerSettingsQuery.data) {
        const timeoutSeconds = Number.parseInt(draft.providerTimeoutSeconds, 10);
        const providerPayload = {
          base_url:
            draft.providerBaseUrl.trim() ||
            providerSettingsQuery.data.base_url,
          timeout_seconds:
            Number.isFinite(timeoutSeconds) && timeoutSeconds > 0
              ? timeoutSeconds
              : providerSettingsQuery.data.timeout_seconds,
          model_preset: "custom" as const,
          model_names: {
            economy:
              draft.economyModel.trim() ||
              providerSettingsQuery.data.model_names.economy,
            balanced:
              draft.defaultModel.trim() ||
              providerSettingsQuery.data.model_names.balanced,
            premium:
              draft.premiumModel.trim() ||
              providerSettingsQuery.data.model_names.premium,
          },
          ...(draft.providerApiKey.trim()
            ? { api_key: draft.providerApiKey.trim() }
            : {}),
        };

        updates.push(updateProvider(providerPayload));
      }

      if (roots.length > 0) {
        updates.push(updateWorkspaceSettings({ allowed_workspace_roots: roots }));
      }

      await Promise.all(updates);
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["settings", "provider", "openai"] }),
        queryClient.invalidateQueries({ queryKey: ["settings", "workspace"] }),
      ]);
      showActionFeedback("设置已保存", "done");
    },
    onError: () => {
      showActionFeedback("设置保存失败", "failed");
    },
  });

  const settingsAdapter = useMemo(
    () => ({
      mode: "real" as const,
      loading: providerSettingsQuery.isLoading || workspaceSettingsQuery.isLoading,
      errorMessage:
        providerSettingsQuery.error?.message ??
        workspaceSettingsQuery.error?.message ??
        null,
      provider: providerSettingsQuery.data
        ? {
            configured: providerSettingsQuery.data.configured,
            source: providerSettingsQuery.data.source,
            baseUrl: providerSettingsQuery.data.base_url,
            timeoutSeconds: providerSettingsQuery.data.timeout_seconds,
            detectedProviderType: providerSettingsQuery.data.detected_provider_type,
            modelPreset: providerSettingsQuery.data.model_preset,
            modelNames: providerSettingsQuery.data.model_names,
            maskedApiKey: providerSettingsQuery.data.masked_api_key,
          }
        : null,
      workspace: workspaceSettingsQuery.data
        ? {
            defaultWorkspaceRoot: workspaceSettingsQuery.data.default_workspace_root,
            allowedWorkspaceRoots: workspaceSettingsQuery.data.allowed_workspace_roots,
            usingDefault: workspaceSettingsQuery.data.using_default,
          }
        : null,
      providerTest: {
        status: providerTestMutation.isPending
          ? ("testing" as const)
          : providerTestMutation.data?.status === "passed"
            ? ("passed" as const)
            : providerTestMutation.isError
              ? ("failed" as const)
              : ("idle" as const),
        summary: providerTestMutation.isPending
          ? "正在测试连接"
          : providerTestMutation.data?.status === "passed"
            ? "连接可用"
            : providerTestMutation.error
              ? "连接失败"
              : "尚未测试",
        testedAt: providerTestMutation.data?.tested_at ?? null,
        modelName: providerTestMutation.data?.model_name ?? null,
      },
      onTestProvider: () => {
        providerTestMutation.mutate(undefined, {
          onSuccess: (result) => {
            showActionFeedback(
              result.status === "passed"
                ? "Provider 测试通过"
                : "Provider 测试未通过",
              result.status === "passed" ? "done" : "failed",
            );
          },
          onError: () => {
            showActionFeedback("Provider 测试失败", "failed");
          },
        });
      },
      onSave: (draft: SettingsDraft) => {
        saveSettingsMutation.mutate(draft);
      },
      saving: saveSettingsMutation.isPending,
    }),
    [
      providerSettingsQuery.data,
      providerSettingsQuery.error,
      providerSettingsQuery.isLoading,
      providerTestMutation,
      saveSettingsMutation,
      showActionFeedback,
      workspaceSettingsQuery.data,
      workspaceSettingsQuery.error,
      workspaceSettingsQuery.isLoading,
    ],
  );

  const accountAdapter = useMemo<WorkbenchAccountAdapter>(
    () => ({
      mode: "real",
      loading: accountProfileQuery.isLoading,
      errorMessage: accountProfileQuery.error?.message ?? null,
      profile: accountProfileQuery.data
        ? {
            accountId: accountProfileQuery.data.account_id,
            displayName: accountProfileQuery.data.display_name,
            notificationEmail: accountProfileQuery.data.notification_email,
            loginMethod: accountProfileQuery.data.login_method,
            defaultRole: accountProfileQuery.data.default_role,
            source: accountProfileQuery.data.source,
          }
        : null,
      onSave: (draft) => {
        saveAccountMutation.mutate({
          display_name: draft.displayName,
          notification_email: draft.notificationEmail,
        });
      },
      saving: saveAccountMutation.isPending,
    }),
    [
      accountProfileQuery.data,
      accountProfileQuery.error?.message,
      accountProfileQuery.isLoading,
      saveAccountMutation,
    ],
  );

  return {
    accountAdapter,
    settingsAdapter,
    workspaceSettingsQuery,
  };
}
