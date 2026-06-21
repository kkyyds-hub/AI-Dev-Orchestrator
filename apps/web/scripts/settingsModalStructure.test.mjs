import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

const routerSource = readFileSync(
  new URL("../src/app/router.tsx", import.meta.url),
  "utf8",
);
const labPageSource = readFileSync(
  new URL("../src/features/ui-selection-lab/SanshengLiubuUiLabPage.tsx", import.meta.url),
  "utf8",
);
const settingsModalSource = readFileSync(
  new URL("../src/features/ui-selection-lab/components/WorkbenchSettingsModal.tsx", import.meta.url),
  "utf8",
);
const accountModalSource = readFileSync(
  new URL("../src/features/ui-selection-lab/components/AccountSettingsModal.tsx", import.meta.url),
  "utf8",
);
const apiPath = new URL("../src/features/settings/api.ts", import.meta.url);

assert.ok(existsSync(apiPath), "Settings API calls should remain split from UI surfaces");

assert.match(
  routerSource,
  /path: "settings"[\s\S]*<WorkbenchPage initialModal="settings" \/>/,
  "Formal /settings should open the shared lab workbench settings modal",
);
assert.match(
  routerSource,
  /path: "me"[\s\S]*<WorkbenchPage initialModal="account" \/>/,
  "Formal /me should open the shared lab account modal",
);
assert.doesNotMatch(
  routerSource,
  /SettingsPage|SettingsDialogShell|ProviderSettingsPanel|WorkspaceSettingsPanel|SystemDiagnosticsPanel/,
  "Formal router should not render the deleted settings page shell",
);

for (const anchor of [
  "initialModal",
  "setSettingsOpen(true)",
  "setAccountSettingsOpen(true)",
  "<AccountSettingsModal",
  "<WorkbenchSettingsModal",
]) {
  assert.match(
    labPageSource,
    new RegExp(anchor.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")),
    `Shared workbench shell should support ${anchor}`,
  );
}

assert.match(
  settingsModalSource,
  /工作台设置/,
  "Settings modal should keep the lab workbench settings surface",
);
for (const anchor of [
  "providerBaseUrl",
  "providerTimeoutSeconds",
  "providerApiKey",
  "economyModel",
  "premiumModel",
]) {
  assert.match(
    settingsModalSource,
    new RegExp(anchor),
    `Settings modal should keep provider settings field ${anchor}`,
  );
}
assert.match(
  accountModalSource,
  /账户/,
  "Account route should use the lab account settings modal",
);
