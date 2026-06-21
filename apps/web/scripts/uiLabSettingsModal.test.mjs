import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

const modalPath = new URL(
  "../src/features/ui-selection-lab/components/WorkbenchSettingsModal.tsx",
  import.meta.url,
);
const accountModalPath = new URL(
  "../src/features/ui-selection-lab/components/AccountSettingsModal.tsx",
  import.meta.url,
);
const labPagePath = new URL("../src/features/ui-selection-lab/SanshengLiubuUiLabPage.tsx", import.meta.url);
const playgroundPath = new URL(
  "../src/features/ui-selection-lab/components/ComponentPlayground.tsx",
  import.meta.url,
);

assert.ok(existsSync(modalPath), "UI lab should have a dedicated workbench settings modal component");
assert.ok(existsSync(accountModalPath), "UI lab should have a dedicated account settings modal component");

const modalSource = readFileSync(modalPath, "utf8");
const accountModalSource = readFileSync(accountModalPath, "utf8");
const labPageSource = readFileSync(labPagePath, "utf8");
const playgroundSource = readFileSync(playgroundPath, "utf8");

assert.match(
  modalSource,
  /data-testid="ui-lab-settings-modal"/,
  "Settings modal should expose a stable test anchor",
);
assert.match(
  modalSource,
  /w-\[min\(1120px,calc\(100vw-32px\)\)\]/,
  "Settings modal should use a large desktop-friendly shell",
);
assert.doesNotMatch(
  modalSource,
  /bg-(emerald|violet|blue|cyan|rose|amber|orange|purple)-/,
  "Settings modal should stay in the minimal black/white/gray token set",
);
assert.match(
  labPageSource,
  /const \[settingsOpen, setSettingsOpen\] = useState\(initialModal === "settings"\)/,
  "Workbench preview should keep route-controllable local settings modal open state",
);
assert.match(
  labPageSource,
  /const \[accountSettingsOpen, setAccountSettingsOpen\] = useState\(initialModal === "account"\)/,
  "Workbench preview should keep route-controllable account settings modal state",
);
assert.match(
  labPageSource,
  /if \(initialModal === "settings"\)[\s\S]*setSettingsOpen\(true\)/,
  "Workbench preview should reopen the settings modal when a formal settings route selects it",
);
assert.match(
  labPageSource,
  /else if \(initialModal === "account"\)[\s\S]*setAccountSettingsOpen\(true\)/,
  "Workbench preview should reopen the account modal when a formal account route selects it",
);
assert.match(
  labPageSource,
  /onSelect=\{\(\) => setAccountSettingsOpen\(true\)\}/,
  "The account menu item should open the standalone account settings modal",
);
assert.match(
  labPageSource,
  /onSelect=\{\(\) => setSettingsOpen\(true\)\}/,
  "The left-bottom workbench settings menu item should open the lab modal",
);
assert.match(
  labPageSource,
  /<WorkbenchSettingsModal[\s\S]*open=\{settingsOpen\}[\s\S]*onOpenChange=\{setSettingsOpen\}[\s\S]*adapter=\{settingsAdapter\}[\s\S]*\/>/,
  "Workbench preview should render the lab settings modal in-page and accept an optional settings adapter",
);
assert.match(
  labPageSource,
  /<AccountSettingsModal[\s\S]*open=\{accountSettingsOpen\}[\s\S]*onOpenChange=\{setAccountSettingsOpen\}[\s\S]*adapter=\{accountAdapter\}[\s\S]*\/>/,
  "Workbench preview should render the standalone account settings modal in-page",
);
assert.match(
  playgroundSource,
  /ComponentRow title="Workbench Settings Modal \/ 工作台设置大弹窗"/,
  "Component playground should include the settings modal preview",
);
assert.match(
  playgroundSource,
  /WorkbenchSettingsModal/,
  "Component playground should render the same settings modal component for review",
);
assert.match(
  modalSource,
  /export type WorkbenchSettingsSection = "workspace" \| "model" \| "security"/,
  "Workbench settings modal should not include account as a settings page",
);
assert.doesNotMatch(
  modalSource,
  /id: "account"|label: "账户"|title: "账户信息"/,
  "Account settings should live only in AccountSettingsModal",
);
assert.match(
  accountModalSource,
  /data-testid="ui-lab-account-settings-modal"/,
  "Account settings modal should expose a stable test anchor",
);
assert.match(
  playgroundSource,
  /ComponentRow title="Account Settings Modal \/ 账户设置弹窗"/,
  "Component playground should include the standalone account modal preview",
);
assert.match(
  modalSource,
  /本地偏好/,
  "Settings modal should keep a concise user-facing status label",
);
assert.doesNotMatch(
  modalSource,
  /mock only|保存 mock 设置|不接真实后端|实验页占位设置|假数据|正式接入/,
  "Settings modal should avoid loud mock placeholder copy in the main UI",
);
assert.match(
  modalSource,
  /data-\[state=closed\]:!scale-100/,
  "Settings modal should disable the default shrinking dialog motion",
);
assert.match(
  modalSource,
  /Input,/,
  "Settings modal should reuse the existing UI Input component for user-editable fields",
);
for (const fieldId of [
  "defaultWorkspace",
  "defaultModel",
  "providerName",
  "providerBaseUrl",
  "providerTimeoutSeconds",
  "providerApiKey",
  "economyModel",
  "premiumModel",
]) {
  assert.match(
    modalSource,
    new RegExp(`ui-lab-setting-input-${fieldId}`),
    `Settings modal should expose editable input field: ${fieldId}`,
  );
}
assert.match(
  modalSource,
  /placeholder: "留空则保留当前密钥"/,
  "Settings modal should never require or echo a plaintext provider key to keep existing config",
);
assert.match(
  modalSource,
  /readOnly=\{field\.id === "providerKeyName"\}/,
  "Settings modal should keep the displayed provider key status read-only",
);
for (const fieldId of ["displayName", "notificationEmail"]) {
  assert.match(
    accountModalSource,
    new RegExp(`ui-lab-account-input-${fieldId}`),
    `Account modal should expose editable input field: ${fieldId}`,
  );
}
assert.doesNotMatch(
  modalSource,
  /className="[^"]*<input|<input/,
  "Settings modal should not hand-roll raw input elements",
);
assert.doesNotMatch(
  accountModalSource,
  /className="[^"]*<input|<input/,
  "Account modal should not hand-roll raw input elements",
);
