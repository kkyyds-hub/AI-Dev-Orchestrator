import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(
  new URL("../src/features/ui-selection-lab/components/ComponentPlayground.tsx", import.meta.url),
  "utf8",
);

const planFlowIndex = source.indexOf('ComponentRow title="Plan Flow / 工作台计划流"');
const userDecisionIndex = source.indexOf('ComponentRow title="User Decision Surfaces / 普通用户承接组件"');
const buttonIndex = source.indexOf('ComponentRow title="Button"');

assert.notEqual(planFlowIndex, -1, "Plan Flow preview row should exist");
assert.notEqual(userDecisionIndex, -1, "User decision surface preview row should exist");
assert.notEqual(buttonIndex, -1, "Button preview row should exist");
assert.ok(
  planFlowIndex < buttonIndex,
  "Plan Flow preview row should appear before basic controls so it is immediately visible",
);
assert.ok(
  planFlowIndex < userDecisionIndex && userDecisionIndex < buttonIndex,
  "User decision surfaces should appear directly after plan flow and before basic controls",
);
