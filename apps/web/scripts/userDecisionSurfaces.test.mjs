import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const surfacesSource = readFileSync(
  new URL("../src/features/ui-selection-lab/components/WorkbenchUserDecisionSurfaces.tsx", import.meta.url),
  "utf8",
);
const conversationSource = readFileSync(
  new URL("../src/features/ui-selection-lab/components/WorkbenchMockConversation.tsx", import.meta.url),
  "utf8",
);
const labPageSource = readFileSync(
  new URL("../src/features/ui-selection-lab/SanshengLiubuUiLabPage.tsx", import.meta.url),
  "utf8",
);
const playgroundSource = readFileSync(
  new URL("../src/features/ui-selection-lab/components/ComponentPlayground.tsx", import.meta.url),
  "utf8",
);

assert.match(
  surfacesSource,
  /data-testid="ui-lab-clarification-panel"/,
  "Clarification panel should expose a stable preview/test anchor",
);
assert.match(
  surfacesSource,
  /data-testid="ui-lab-project-next-step-panel"/,
  "Project next step panel should expose a stable preview/test anchor",
);
assert.match(
  surfacesSource,
  /data-testid="ui-lab-topbar-action-inbox"/,
  "User action inbox should expose a stable topbar preview/test anchor",
);
assert.match(
  surfacesSource,
  /absolute right-0 top-\[calc\(100%\+12px\)\]/,
  "User action inbox expansion should overlay the page without pushing the topbar",
);
assert.match(
  surfacesSource,
  /w-\[min\(38vw,420px\)\]/,
  "Topbar action inbox should stay short enough for the status bar",
);
assert.match(
  surfacesSource,
  /defaultCollapsed = true/,
  "Collapsible decision surfaces should default to collapsed",
);
assert.doesNotMatch(
  surfacesSource,
  /bg-(emerald|violet|blue|cyan|rose|amber)-/,
  "Decision surfaces should avoid colorful UI blocks in the minimal lab",
);
assert.match(
  conversationSource,
  /topSurface\?: React\.ReactNode/,
  "Conversation view should support a minimal top surface slot",
);
assert.doesNotMatch(
  labPageSource,
  /topSurface=\{activeTopSurface\}|const activeTopSurface/,
  "User action inbox should no longer render inside the conversation surface",
);
assert.match(
  labPageSource,
  /<WorkbenchUserActionStrip \/>/,
  "Workbench preview should render the user action inbox in the top context bar",
);
assert.match(
  labPageSource,
  /renderTopActionSlot\?\.\(directorContext\) \?\? topActionSlot \?\? <WorkbenchUserActionStrip \/>/,
  "User action inbox should remain globally available from the top context bar",
);
assert.match(
  labPageSource,
  /<div className="mr-3 hidden shrink-0 md:block">\s*\{renderTopActionSlot\?\.\(directorContext\) \?\? topActionSlot \?\? <WorkbenchUserActionStrip \/>\}/,
  "Topbar action inbox should render without being gated by active conversation state",
);
assert.match(
  labPageSource,
  /planFlowState\.stage === "draft" \? <WorkbenchClarificationPanel \/> : null/,
  "Clarification should appear before plan flow while the draft is pending",
);
assert.match(
  labPageSource,
  /planFlowState\.stage === "created" \? <WorkbenchProjectNextStepPanel \/> : null/,
  "Project next steps should appear after the formal project is created",
);
assert.match(
  playgroundSource,
  /WorkbenchUserDecisionSurfacePreview/,
  "Component playground should include the user decision surface preview",
);
