import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const cardSource = readFileSync(
  new URL("../src/features/ui-selection-lab/components/WorkbenchPlanFlowCards.tsx", import.meta.url),
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

assert.match(cardSource, /defaultCollapsed\?: boolean/, "Plan flow card should accept a defaultCollapsed prop");
assert.match(cardSource, /useState\(defaultCollapsed\)/, "Plan flow card should own collapsed state");
assert.match(cardSource, /aria-expanded=\{!isCollapsed\}/, "Toggle should expose expanded state for accessibility");
assert.match(cardSource, /transition-\[max-height,opacity,transform\]/, "Expanded content should animate open and closed");
assert.match(cardSource, /data-testid="ui-lab-plan-flow-gradient-toggle"/, "Toggle should be the bottom gradient control");
assert.match(cardSource, /bg-gradient-to-b/, "Toggle control should use a bottom white gradient treatment");
assert.doesNotMatch(
  cardSource,
  /data-testid="ui-lab-plan-flow-gradient-toggle"[\s\S]{0,700}rounded-full/,
  "Toggle should not look like a separate pill button",
);
assert.match(labPageSource, /defaultCollapsed/, "AI supervisor conversation card should default to collapsed");
assert.match(playgroundSource, /defaultCollapsed/, "All preview cards should demonstrate collapsed state by default");
