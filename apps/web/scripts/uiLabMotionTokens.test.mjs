import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const labPageSource = readFileSync(
  new URL("../src/features/ui-selection-lab/SanshengLiubuUiLabPage.tsx", import.meta.url),
  "utf8",
);
const mockPagesSource = readFileSync(
  new URL("../src/features/ui-selection-lab/components/WorkbenchMockPages.tsx", import.meta.url),
  "utf8",
);
const userDecisionSource = readFileSync(
  new URL("../src/features/ui-selection-lab/components/WorkbenchUserDecisionSurfaces.tsx", import.meta.url),
  "utf8",
);
const planFlowSource = readFileSync(
  new URL("../src/features/ui-selection-lab/components/WorkbenchPlanFlowCards.tsx", import.meta.url),
  "utf8",
);
const settingsSource = readFileSync(
  new URL("../src/features/ui-selection-lab/components/WorkbenchSettingsModal.tsx", import.meta.url),
  "utf8",
);
const accountSource = readFileSync(
  new URL("../src/features/ui-selection-lab/components/AccountSettingsModal.tsx", import.meta.url),
  "utf8",
);
const runtimeModalsSource = readFileSync(
  new URL("../src/features/ui-selection-lab/components/WorkbenchRuntimeModals.tsx", import.meta.url),
  "utf8",
);
const conversationSource = readFileSync(
  new URL("../src/features/ui-selection-lab/components/WorkbenchMockConversation.tsx", import.meta.url),
  "utf8",
);
const promptBoxSource = readFileSync(
  new URL("../src/features/ui-selection-lab/components/WorkbenchPromptBox.tsx", import.meta.url),
  "utf8",
);
const playgroundSource = readFileSync(
  new URL("../src/features/ui-selection-lab/components/ComponentPlayground.tsx", import.meta.url),
  "utf8",
);

for (const className of [
  "ui-lab-page-enter",
  "ui-lab-panel-enter",
  "ui-lab-popover-enter",
  "ui-lab-dialog-enter",
  "ui-lab-detail-switch",
]) {
  assert.match(labPageSource, new RegExp(`\\.${className}`), `Motion token ${className} should be defined locally`);
}

assert.match(
  labPageSource,
  /@media \(prefers-reduced-motion: reduce\)/,
  "UI lab motion should respect reduced-motion preferences",
);
assert.match(
  labPageSource,
  /animation-duration: 1ms !important;/,
  "Reduced-motion mode should collapse animation duration",
);
assert.doesNotMatch(
  labPageSource,
  /transform: none !important;/,
  "Reduced-motion mode should not break transform-based centering",
);
assert.match(
  labPageSource,
  /translate: 0 8px;/,
  "Motion tokens should use independent translate so existing transforms keep working",
);

assert.match(
  mockPagesSource,
  /className="ui-lab-page-enter /,
  "Main mock pages should use the page-enter motion token",
);
assert.match(
  userDecisionSource,
  /ui-lab-popover-enter/,
  "Topbar action inbox popover should use the popover motion token",
);
assert.match(
  planFlowSource,
  /ui-lab-panel-enter/,
  "Plan flow cards should use the panel motion token",
);
assert.match(
  settingsSource,
  /ui-lab-dialog-enter/,
  "Workbench settings modal should use the dialog motion token",
);
assert.match(
  accountSource,
  /ui-lab-dialog-enter/,
  "Account settings modal should use the dialog motion token",
);
assert.match(
  mockPagesSource,
  /className="ui-lab-detail-switch/,
  "Tabbed detail panes should use the detail-switch motion token",
);
assert.match(
  runtimeModalsSource,
  /ui-lab-dialog-enter/,
  "Runtime modals should use the dialog motion token",
);
assert.match(
  runtimeModalsSource,
  /ui-lab-detail-switch/,
  "Runtime modal tab/detail surfaces should use the detail-switch motion token",
);
assert.match(
  conversationSource,
  /ui-lab-page-enter/,
  "Conversation page should use the page-enter motion token",
);
assert.match(
  conversationSource,
  /ui-lab-panel-enter/,
  "Conversation cards should use the panel-enter motion token",
);
assert.match(
  promptBoxSource,
  /ui-lab-panel-enter/,
  "Prompt box should use the panel-enter motion token",
);
assert.match(
  playgroundSource,
  /ui-lab-dialog-enter/,
  "Component playground should preview dialog motion",
);
assert.match(
  playgroundSource,
  /ui-lab-detail-switch/,
  "Component playground should preview detail switch motion",
);
