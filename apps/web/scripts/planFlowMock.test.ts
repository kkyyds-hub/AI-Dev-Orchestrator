import assert from "node:assert/strict";

import {
  applyPlanFlowAction,
  createInitialPlanFlowState,
} from "../src/features/ui-selection-lab/planFlowMock.ts";

const initial = createInitialPlanFlowState();

assert.equal(initial.stage, "draft");
assert.equal(initial.feedbackDraft, "");
assert.equal(initial.projectCreated, false);

const changeRequested = applyPlanFlowAction(initial, {
  type: "request_changes",
  feedback: "第一版先不要做支付，保留聊天和商品发布。",
});

assert.equal(changeRequested.stage, "changes_requested");
assert.equal(changeRequested.feedbackDraft, "第一版先不要做支付，保留聊天和商品发布。");
assert.equal(changeRequested.revisionCount, 1);

const confirmed = applyPlanFlowAction(changeRequested, { type: "confirm_plan" });
assert.equal(confirmed.stage, "confirmed");
assert.equal(confirmed.confirmedAt, "刚刚");

const created = applyPlanFlowAction(confirmed, {
  type: "create_project",
  projectName: "二手交易平台 MVP",
});

assert.equal(created.stage, "created");
assert.equal(created.projectCreated, true);
assert.equal(created.createdProjectName, "二手交易平台 MVP");
