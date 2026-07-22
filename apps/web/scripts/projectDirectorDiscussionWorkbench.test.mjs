/**
 * P26-H1 frontend contract tests for Project Director discussion workbench.
 *
 * Uses TypeScript AST to read and execute production functions:
 *   canOfferDiscussionFormalization
 *   mergeFormalizationWorkspaceVersions
 *   mergeProjectDirectorMessages
 *
 * Also verifies API request contract, hook invalidation, handler gate ordering,
 * context cleanup, request_changes branch, 409 recovery, and no auto-formalize.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";

// ---------------------------------------------------------------------------
// AST helpers
// ---------------------------------------------------------------------------

function readSource(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), "utf8");
}

function extractFunctionNode(source, functionName) {
  const sf = ts.createSourceFile(`${functionName}.ts`, source, ts.ScriptTarget.Latest, true);
  let result = null;
  function visit(node) {
    if (ts.isFunctionDeclaration(node) && node.name?.getText(sf) === functionName) {
      result = node;
      return;
    }
    if (ts.isVariableStatement(node) && node.declarationList?.declarations) {
      for (const decl of node.declarationList.declarations) {
        if (decl.name.getText(sf) === functionName &&
            (ts.isArrowFunction(decl.initializer) || ts.isFunctionExpression(decl.initializer))) {
          result = decl.initializer;
          return;
        }
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sf);
  return result;
}

function transpileAndExecute(source, functionName, args) {
  const node = extractFunctionNode(source, functionName);
  assert.ok(node, `Function ${functionName} not found`);
  const sf = ts.createSourceFile(`${functionName}.ts`, source, ts.ScriptTarget.Latest, true);
  const funcText = node.getText(sf);
  const result = ts.transpileModule(funcText, {
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ESNext },
  });
  const context = vm.createContext({ Boolean, Set, Map, Array, Object, Math, JSON, console });
  const script = new vm.Script(`(${result.outputText})`);
  const fn = script.runInContext(context);
  return fn(...args);
}

function findCallExpression(source, callName) {
  const sf = ts.createSourceFile("x.ts", source, ts.ScriptTarget.Latest, true);
  let result = null;
  function visit(node) {
    if (ts.isCallExpression(node) && node.expression.getText(sf) === callName) {
      result = node;
      return;
    }
    ts.forEachChild(node, visit);
  }
  visit(sf);
  return result;
}

function getArgPropertyText(callNode, argIndex, propName, source) {
  const sf = ts.createSourceFile("x.ts", source, ts.ScriptTarget.Latest, true);
  const arg = callNode.arguments[argIndex];
  if (!arg || !ts.isObjectLiteralExpression(arg)) return null;
  for (const prop of arg.properties) {
    if (ts.isPropertyAssignment(prop) && prop.name.getText(sf) === propName) {
      return prop.initializer.getText(sf);
    }
  }
  return null;
}

function findUseEffectWithDeps(source, depArrayContent) {
  const sf = ts.createSourceFile("x.ts", source, ts.ScriptTarget.Latest, true);
  let result = null;
  function visit(node) {
    if (ts.isCallExpression(node) && node.expression.getText(sf) === "useEffect") {
      const deps = node.arguments[1];
      if (deps && ts.isArrayLiteralExpression(deps)) {
        const depsText = deps.getText(sf);
        if (depsText.includes(depArrayContent)) {
          result = { call: node, body: node.arguments[0] };
        }
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sf);
  return result;
}

// ---------------------------------------------------------------------------
// Source files
// ---------------------------------------------------------------------------

const surfaceSource = readSource("../src/features/workbench/ProjectDirectorWorkbenchSurface.tsx");
const hooksSource = readSource("../src/features/project-director/hooks.ts");
const apiSource = readSource("../src/features/project-director/api.ts");
const decisionSurfacesSource = readSource(
  "../src/features/ui-selection-lab/components/WorkbenchUserDecisionSurfaces.tsx",
);

// ===========================================================================
// §6.2 canOfferDiscussionFormalization — state matrix
// ===========================================================================

const canOffer = (input) =>
  transpileAndExecute(surfaceSource, "canOfferDiscussionFormalization", [input]);

assert.equal(canOffer({ workspace: null, proposal: null, existingWorkspaceVersions: [], planVersion: null }), false);
assert.equal(canOffer({ workspace: { version_no: 1, discussion_status: "ready_to_formalize" }, proposal: { requires_confirmation: true, workspace_version: 1 }, existingWorkspaceVersions: [1], planVersion: null }), false);
assert.equal(canOffer({ workspace: { version_no: 1, discussion_status: "ready_to_formalize" }, proposal: null, existingWorkspaceVersions: [1], planVersion: null }), false);
assert.equal(canOffer({ workspace: { version_no: 1, discussion_status: "ready_to_formalize" }, proposal: null, existingWorkspaceVersions: [1], planVersion: { formalization_workspace_version: null } }), false);
assert.equal(canOffer({ workspace: { version_no: 1, discussion_status: "ready_to_formalize" }, proposal: null, existingWorkspaceVersions: [1], planVersion: { formalization_workspace_version: 1, status: "rejected" } }), false);
assert.equal(canOffer({ workspace: { version_no: 2, discussion_status: "ready_to_formalize" }, proposal: { requires_confirmation: true, workspace_version: 2 }, existingWorkspaceVersions: [1], planVersion: null }), true);
assert.equal(canOffer({ workspace: { version_no: 2, discussion_status: "ready_to_formalize" }, proposal: null, existingWorkspaceVersions: [1], planVersion: null }), true);
assert.equal(canOffer({ workspace: { version_no: 2, discussion_status: "exploring" }, proposal: { requires_confirmation: true, workspace_version: 1 }, existingWorkspaceVersions: [1], planVersion: null }), false);

// ===========================================================================
// §6.3 mergeFormalizationWorkspaceVersions
// ===========================================================================

const mergeVersions = (existing, newV) =>
  transpileAndExecute(surfaceSource, "mergeFormalizationWorkspaceVersions", [existing, newV]);

assert.equal(JSON.stringify(mergeVersions([3, 1], 2)), JSON.stringify([1, 2, 3]));
assert.equal(JSON.stringify(mergeVersions([1, 2], 2)), JSON.stringify([1, 2]));
assert.equal(JSON.stringify(mergeVersions([], 4)), JSON.stringify([4]));

// ===========================================================================
// §6.4 mergeProjectDirectorMessages
// ===========================================================================

const mergeMessages = (current, additions) =>
  transpileAndExecute(surfaceSource, "mergeProjectDirectorMessages", [current, additions]);

const merged = mergeMessages(
  [{ id: "a", sequence_no: 1, content: "old" }, { id: "b", sequence_no: 2, content: "old" }],
  [{ id: "c", sequence_no: 3, content: "new" }],
);
assert.equal(merged.length, 3);
assert.equal(JSON.stringify(merged.map(m => m.id)), JSON.stringify(["a", "b", "c"]));

const updated = mergeMessages(
  [{ id: "a", sequence_no: 1, content: "old" }],
  [{ id: "a", sequence_no: 1, content: "updated" }],
);
assert.equal(updated.length, 1);
assert.equal(updated[0].content, "updated");

// ===========================================================================
// §6.5 API request contract
// ===========================================================================

assert.match(apiSource, /\/project-director\/sessions\/\$\{input\.sessionId\}\/discussion\/formalize/);
assert.match(apiSource, /workspace_version:\s*input\.workspaceVersion/);
assert.match(apiSource, /target:\s*"plan_revision"/);
assert.match(apiSource, /user_confirmed:\s*true/);
assert.doesNotMatch(apiSource, /proposal_id/);
assert.doesNotMatch(apiSource, /source_message_ids/);
assert.doesNotMatch(apiSource, /source_event_ids/);

// ===========================================================================
// §6.6 Hook invalidation
// ===========================================================================

assert.match(hooksSource, /session-messages.*result\.session_id/);
assert.match(hooksSource, /workbench-resume/);
assert.match(hooksSource, /conversation/);
assert.match(hooksSource, /conversations/);
assert.match(hooksSource, /inbox/);

// Formalize hook must not call confirm/create task/run/worker/executor
const formalizeHookMatch = hooksSource.match(
  /export function useFormalizeProjectDirectorDiscussion[\s\S]*?(?=\nexport function |\n$)/,
);
assert.ok(formalizeHookMatch, "formalize hook found");
const formalizeHookBody = formalizeHookMatch[0];
assert.doesNotMatch(formalizeHookBody, /confirm.*plan/i);
assert.doesNotMatch(formalizeHookBody, /create.*task/i);
assert.doesNotMatch(formalizeHookBody, /create.*run/i);
assert.doesNotMatch(formalizeHookBody, /worker|executor/i);

// ===========================================================================
// §6.7 Context cleanup — AST proof
// ===========================================================================

const cleanupEffect = findUseEffectWithDeps(surfaceSource, "input.mode");
assert.ok(cleanupEffect, "context cleanup useEffect found with [input.mode, ...] deps");

const cleanupDeps = cleanupEffect.call.arguments[1];
const depsText = cleanupDeps.getText(ts.createSourceFile("x.ts", surfaceSource, ts.ScriptTarget.Latest, true));
assert.match(depsText, /input\.mode/, "cleanup deps include input.mode");
assert.match(depsText, /input\.projectId/, "cleanup deps include input.projectId");
assert.match(depsText, /input\.resumeSessionId/, "cleanup deps include input.resumeSessionId");

const cleanupBody = cleanupEffect.body.getText(
  ts.createSourceFile("x.ts", surfaceSource, ts.ScriptTarget.Latest, true),
);
assert.match(cleanupBody, /setSession\(null\)/, "cleanup resets session");
assert.match(cleanupBody, /setPlanVersion\(null\)/, "cleanup resets planVersion");
assert.match(cleanupBody, /setMessageTimeline\(\[\]\)/, "cleanup resets messages");
assert.match(cleanupBody, /setDiscussionWorkspace\(null\)/, "cleanup resets workspace");
assert.match(cleanupBody, /setFormalizationProposal\(null\)/, "cleanup resets proposal");
assert.match(cleanupBody, /setFormalizationError\(null\)/, "cleanup resets error");
assert.match(cleanupBody, /setExistingFormalizationWorkspaceVersions\(\[\]\)/, "cleanup resets existing versions");

// ===========================================================================
// §6.8 request_changes branch — AST proof
// ===========================================================================

// Find the handleReviewPlanVersion function and its request_changes branch
const reviewFn = extractFunctionNode(surfaceSource, "handleReviewPlanVersion");
assert.ok(reviewFn, "handleReviewPlanVersion found");
const reviewFnText = reviewFn.getText(
  ts.createSourceFile("x.ts", surfaceSource, ts.ScriptTarget.Latest, true),
);

// Find the request_changes conditional
const rcMatch = reviewFnText.match(
  /if\s*\(action\s*===\s*"request_changes"\)\s*\{([\s\S]*?)\}/,
);
assert.ok(rcMatch, "request_changes branch found");
const rcBody = rcMatch[1];
assert.match(rcBody, /setFormalizationProposal\(null\)/, "request_changes clears proposal");
assert.match(rcBody, /setFormalizationError\(null\)/, "request_changes clears error");
assert.doesNotMatch(rcBody, /setExistingFormalizationWorkspaceVersions\(\[\]\)/,
  "request_changes does NOT clear existing versions");

// ===========================================================================
// §6.8b Handler secondary gate — AST proof
// ===========================================================================

const handlerFn = extractFunctionNode(surfaceSource, "handleFormalizeDiscussion");
assert.ok(handlerFn, "handleFormalizeDiscussion found");
const handlerText = handlerFn.getText(
  ts.createSourceFile("x.ts", surfaceSource, ts.ScriptTarget.Latest, true),
);

const includesCheck = handlerText.indexOf("existingFormalizationWorkspaceVersions.includes");
const mutateAsyncCall = handlerText.indexOf("formalizeDiscussionMutation.mutateAsync");
assert.ok(includesCheck >= 0, "handler checks existingFormalizationWorkspaceVersions");
assert.ok(mutateAsyncCall >= 0, "handler calls mutateAsync");
assert.ok(includesCheck < mutateAsyncCall, "includes check before mutateAsync — static proof");

// Already-processed branch must clear proposal, set error, return
const earlySection = handlerText.slice(includesCheck, mutateAsyncCall);
assert.match(earlySection, /setFormalizationProposal\(null\)/, "early branch clears proposal");
assert.match(earlySection, /setFormalizationError\(/, "early branch sets error");
assert.match(earlySection, /return;/, "early branch returns");

// ===========================================================================
// §6.9 409 recovery — AST proof
// ===========================================================================

// Find the catch block in handleFormalizeDiscussion
const catchMatch = handlerText.match(/catch\s*\(error\)\s*\{([\s\S]*?)\}\s*$/);
assert.ok(catchMatch, "catch block found in handleFormalizeDiscussion");
const catchBody = catchMatch[1];

// Must restore from resumeResult
assert.match(catchBody, /resumeQuery\.refetch\(\)/, "409 triggers refetch");
assert.match(catchBody, /setSession\(resumeResult\.data\.session\)/, "409 restores session");
assert.match(catchBody, /setPlanVersion\(resumeResult\.data\.plan_version\)/, "409 restores plan_version");
assert.match(catchBody, /setTaskCreation\(resumeResult\.data\.task_creation\)/, "409 restores task_creation");
assert.match(catchBody, /setMessageTimeline\(resumeResult\.data\.recent_messages/, "409 restores messages");
assert.match(catchBody, /setDiscussionWorkspace\(resumeResult\.data\.discussion_workspace\)/, "409 restores workspace");
assert.match(catchBody, /setExistingFormalizationWorkspaceVersions\(/, "409 restores existing versions");

// Must NOT auto-retry with old workspace version
assert.doesNotMatch(catchBody, /formalizeDiscussionMutation\.mutateAsync/, "409 does not auto-retry formalize");

// ===========================================================================
// §6.10 No auto-formalize — AST proof
// ===========================================================================

// Find all useEffect bodies and verify none call formalize mutateAsync
const sf = ts.createSourceFile("x.ts", surfaceSource, ts.ScriptTarget.Latest, true);
const allEffects = [];
function collectEffects(node) {
  if (ts.isCallExpression(node) && node.expression.getText(sf) === "useEffect") {
    allEffects.push(node);
  }
  ts.forEachChild(node, collectEffects);
}
collectEffects(sf);

for (const effect of allEffects) {
  const effectBody = effect.arguments[0].getText(sf);
  assert.doesNotMatch(effectBody, /formalizeDiscussionMutation\.mutateAsync/,
    "no useEffect calls formalize mutateAsync");
  assert.doesNotMatch(effectBody, /handleFormalizeDiscussion\(\)/,
    "no useEffect calls handleFormalizeDiscussion");
}

// ===========================================================================
// §6.9b Explicit button testids
// ===========================================================================

assert.match(decisionSurfacesSource, /data-testid="workbench-formalization-proposal"/);
assert.match(decisionSurfacesSource, /data-testid="workbench-formalize-confirm"/);
assert.match(decisionSurfacesSource, /data-testid="workbench-discussion-state"/);

// ===========================================================================
// §6.10b Entry mutual exclusion
// ===========================================================================

assert.match(surfaceSource, /!planVersion\s*&&\s*!discussionWorkspace/, "old entry requires no workspace");
assert.match(surfaceSource, /canOfferDiscussionFormalization\(/, "formalization card uses gate");

// ===========================================================================
// §6.11 User-visible content boundary
// ===========================================================================

assert.match(decisionSurfacesSource, /workspace\.topic/, "state bar shows topic");
assert.match(decisionSurfacesSource, /active_option_ids\.length/, "state bar shows option count");
assert.match(decisionSurfacesSource, /active_constraint_ids\.length/, "state bar shows constraint count");
assert.match(decisionSurfacesSource, /matchingProposal\.summary/, "proposal shows summary");
assert.match(decisionSurfacesSource, /matchingProposal\.changes/, "proposal shows changes");
assert.match(decisionSurfacesSource, /risk_summary/, "proposal shows risk");
assert.match(surfaceSource, /formalization_source_message_ids\.length/, "plan shows message count");
assert.match(surfaceSource, /formalization_source_event_ids\.length/, "plan shows event count");
assert.doesNotMatch(decisionSurfacesSource, /formalization_source_message_ids(?!\.length)/, "no raw message IDs");
assert.doesNotMatch(decisionSurfacesSource, /formalization_source_event_ids(?!\.length)/, "no raw event IDs");

console.log("All P26-H1 frontend contract tests passed.");
