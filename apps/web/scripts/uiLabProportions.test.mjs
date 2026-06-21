import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const labPageSource = readFileSync(
  new URL("../src/features/ui-selection-lab/SanshengLiubuUiLabPage.tsx", import.meta.url),
  "utf8",
);
const planCardSource = readFileSync(
  new URL("../src/features/ui-selection-lab/components/WorkbenchPlanFlowCards.tsx", import.meta.url),
  "utf8",
);
const conversationSource = readFileSync(
  new URL("../src/features/ui-selection-lab/components/WorkbenchMockConversation.tsx", import.meta.url),
  "utf8",
);

assert.match(
  labPageSource,
  /--lab-sidebar-width": "clamp\(220px, 18vw, 260px\)"/,
  "Workbench sidebar should be slimmer than the previous 248-300px range",
);
assert.match(
  planCardSource,
  /className="w-full max-w-\[880px\]/,
  "Plan flow card should use a wider 880px max width",
);
assert.match(
  conversationSource,
  /max-w-\[920px\]/,
  "Conversation plan flow container should allow a wider card",
);
