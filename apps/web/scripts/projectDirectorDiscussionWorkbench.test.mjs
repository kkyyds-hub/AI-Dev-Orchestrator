/**
 * P26-H1 frontend contract tests for Project Director discussion workbench.
 *
 * Uses TypeScript AST to read and execute production functions:
 *   canOfferDiscussionFormalization
 *   mergeFormalizationWorkspaceVersions
 *   mergeProjectDirectorMessages
 *
 * Also verifies API request contract, hook invalidation, handler gate ordering,
 * explicit button testids, no auto-formalize, and content boundary.
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
  const sf = ts.createSourceFile(
    `${functionName}.ts`,
    source,
    ts.ScriptTarget.Latest,
    true,
  );
  let result = null;
  function visit(node) {
    if (
      ts.isFunctionDeclaration(node) &&
      node.name?.getText(sf) === functionName
    ) {
      result = node;
      return;
    }
    if (
      ts.isVariableStatement(node) &&
      node.declarationList?.declarations
    ) {
      for (const decl of node.declarationList.declarations) {
        if (
          decl.name.getText(sf) === functionName &&
          (ts.isArrowFunction(decl.initializer) ||
            ts.isFunctionExpression(decl.initializer))
        ) {
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
  assert.ok(node, `Function ${functionName} not found in source`);

  const sf = ts.createSourceFile(`${functionName}.ts`, source, ts.ScriptTarget.Latest, true);
  const funcText = node.getText(sf);

  const result = ts.transpileModule(funcText, {
    compilerOptions: {
      target: ts.ScriptTarget.ES2020,
      module: ts.ModuleKind.ESNext,
    },
  });

  const context = vm.createContext({
    Boolean,
    Set,
    Map,
    Array,
    Object,
    Math,
    JSON,
    console,
  });

  const script = new vm.Script(`(${result.outputText})`);
  const fn = script.runInContext(context);
  return fn(...args);
}

// ---------------------------------------------------------------------------
// Source files
// ---------------------------------------------------------------------------

const surfaceSource = readSource(
  "../src/features/workbench/ProjectDirectorWorkbenchSurface.tsx",
);
const typesSource = readSource("../src/features/project-director/types.ts");
const apiSource = readSource("../src/features/project-director/api.ts");
const hooksSource = readSource("../src/features/project-director/hooks.ts");
const decisionSurfacesSource = readSource(
  "../src/features/ui-selection-lab/components/WorkbenchUserDecisionSurfaces.tsx",
);

// ===========================================================================
// §6.2 canOfferDiscussionFormalization — state matrix
// ===========================================================================

const canOffer = (input) =>
  transpileAndExecute(surfaceSource, "canOfferDiscussionFormalization", [input]);

// null workspace → false
assert.equal(
  canOffer({ workspace: null, proposal: null, existingWorkspaceVersions: [], planVersion: null }),
  false,
  "null workspace → false",
);

// processed v1 + matching proposal → false
assert.equal(
  canOffer({
    workspace: { version_no: 1, discussion_status: "ready_to_formalize" },
    proposal: { requires_confirmation: true, workspace_version: 1 },
    existingWorkspaceVersions: [1],
    planVersion: null,
  }),
  false,
  "processed v1 + matching proposal → false",
);

// processed v1 + ready fallback → false
assert.equal(
  canOffer({
    workspace: { version_no: 1, discussion_status: "ready_to_formalize" },
    proposal: null,
    existingWorkspaceVersions: [1],
    planVersion: null,
  }),
  false,
  "processed v1 + ready fallback → false",
);

// processed v1 + plain replacement → false
assert.equal(
  canOffer({
    workspace: { version_no: 1, discussion_status: "ready_to_formalize" },
    proposal: null,
    existingWorkspaceVersions: [1],
    planVersion: { formalization_workspace_version: null },
  }),
  false,
  "processed v1 + plain replacement → false",
);

// processed v1 + rejected formalized → false
assert.equal(
  canOffer({
    workspace: { version_no: 1, discussion_status: "ready_to_formalize" },
    proposal: null,
    existingWorkspaceVersions: [1],
    planVersion: { formalization_workspace_version: 1, status: "rejected" },
  }),
  false,
  "processed v1 + rejected formalized → false",
);

// unprocessed v2 + matching proposal → true
assert.equal(
  canOffer({
    workspace: { version_no: 2, discussion_status: "ready_to_formalize" },
    proposal: { requires_confirmation: true, workspace_version: 2 },
    existingWorkspaceVersions: [1],
    planVersion: null,
  }),
  true,
  "unprocessed v2 + matching proposal → true",
);

// unprocessed v2 + ready fallback → true
assert.equal(
  canOffer({
    workspace: { version_no: 2, discussion_status: "ready_to_formalize" },
    proposal: null,
    existingWorkspaceVersions: [1],
    planVersion: null,
  }),
  true,
  "unprocessed v2 + ready fallback → true",
);

// proposal version mismatch + not ready → false
assert.equal(
  canOffer({
    workspace: { version_no: 2, discussion_status: "exploring" },
    proposal: { requires_confirmation: true, workspace_version: 1 },
    existingWorkspaceVersions: [1],
    planVersion: null,
  }),
  false,
  "proposal mismatch + not ready → false",
);

// ===========================================================================
// §6.3 mergeFormalizationWorkspaceVersions
// ===========================================================================

const mergeVersions = (existing, newV) =>
  transpileAndExecute(surfaceSource, "mergeFormalizationWorkspaceVersions", [
    existing,
    newV,
  ]);

assert.equal(JSON.stringify(mergeVersions([3, 1], 2)), JSON.stringify([1, 2, 3]), "[3,1]+2 → [1,2,3]");
assert.equal(JSON.stringify(mergeVersions([1, 2], 2)), JSON.stringify([1, 2]), "[1,2]+2 → [1,2]");
assert.equal(JSON.stringify(mergeVersions([], 4)), JSON.stringify([4]), "[]+4 → [4]");

// ===========================================================================
// §6.4 mergeProjectDirectorMessages
// ===========================================================================

const mergeMessages = (current, additions) =>
  transpileAndExecute(surfaceSource, "mergeProjectDirectorMessages", [
    current,
    additions,
  ]);

// preserves old, appends new, deduplicates by id, sorts by sequence_no
const old = [
  { id: "a", sequence_no: 1, content: "old" },
  { id: "b", sequence_no: 2, content: "old" },
];
const fresh = [
  { id: "c", sequence_no: 3, content: "new" },
];
const merged = mergeMessages(old, fresh);
assert.equal(merged.length, 3, "preserves old + appends new");
assert.equal(
  JSON.stringify(merged.map((m) => m.id)),
  JSON.stringify(["a", "b", "c"]),
  "sorted by sequence_no",
);

// same id: new overwrites old
const updated = mergeMessages(
  [{ id: "a", sequence_no: 1, content: "old" }],
  [{ id: "a", sequence_no: 1, content: "updated" }],
);
assert.equal(updated.length, 1, "deduplicates by id");
assert.equal(updated[0].content, "updated", "new overwrites old");

// ===========================================================================
// §6.5 API request contract
// ===========================================================================

assert.match(
  apiSource,
  /\/project-director\/sessions\/\$\{input\.sessionId\}\/discussion\/formalize/,
  "formalize endpoint path correct",
);
assert.match(apiSource, /workspace_version:\s*input\.workspaceVersion/, "sends workspace_version");
assert.match(apiSource, /target:\s*"plan_revision"/, "fixed target=plan_revision");
assert.match(apiSource, /user_confirmed:\s*true/, "fixed user_confirmed=true");
assert.doesNotMatch(apiSource, /proposal_id/, "no proposal_id in request body");
assert.doesNotMatch(apiSource, /source_message_ids/, "no source_message_ids in request body");
assert.doesNotMatch(apiSource, /source_event_ids/, "no source_event_ids in request body");

// ===========================================================================
// §6.6 Hook invalidation
// ===========================================================================

assert.match(hooksSource, /session-messages.*result\.session_id/, "invalidates session-messages");
assert.match(hooksSource, /workbench-resume/, "invalidates workbench-resume");
assert.match(hooksSource, /conversation/, "invalidates conversation");
assert.match(hooksSource, /conversations/, "invalidates conversations");
assert.match(hooksSource, /inbox/, "invalidates inbox");

// The formalize hook's onSuccess must not call confirm/create task/run/worker/executor
// Extract just the useFormalizeProjectDirectorDiscussion function body
const formalizeHookMatch = hooksSource.match(
  /export function useFormalizeProjectDirectorDiscussion[\s\S]*?(?=\nexport function |\n$)/,
);
assert.ok(formalizeHookMatch, "formalize hook found");
const formalizeHookBody = formalizeHookMatch[0];
assert.doesNotMatch(formalizeHookBody, /confirm.*plan/i, "formalize hook does not confirm plan");
assert.doesNotMatch(formalizeHookBody, /create.*task/i, "formalize hook does not create task");
assert.doesNotMatch(formalizeHookBody, /create.*run/i, "formalize hook does not create run");
assert.doesNotMatch(formalizeHookBody, /worker|executor/i, "formalize hook does not call worker/executor");

// ===========================================================================
// §6.7 Workbench state restoration and cleanup
// ===========================================================================

// Context switch clears workspace
assert.match(
  surfaceSource,
  /setDiscussionWorkspace\(null\)|setDiscussionWorkspace\(\(\) => null\)/,
  "context switch clears workspace",
);
// Resume restores workspace
assert.match(
  surfaceSource,
  /setDiscussionWorkspace\(resumeResult\.data\.discussion_workspace\)/,
  "resume restores workspace",
);
// Resume restores existing versions
assert.match(
  surfaceSource,
  /setExistingFormalizationWorkspaceVersions\(\s*\n?\s*resumeResult\.data\.existing_formalization_workspace_versions/,
  "resume restores existing versions",
);
// Formalize success merges current version
assert.match(
  surfaceSource,
  /mergeFormalizationWorkspaceVersions\(current,\s*result\.workspace_version\)/,
  "formalize success merges version",
);
// request_changes clears proposal/error
assert.match(
  surfaceSource,
  /setFormalizationProposal\(null\)/,
  "request_changes clears proposal",
);

// ===========================================================================
// §6.8 Handler secondary gate
// ===========================================================================

// The handler must check existingFormalizationWorkspaceVersions BEFORE calling mutateAsync
const handlerMatch = surfaceSource.match(
  /async function handleFormalizeDiscussion[\s\S]*?^  \}/m,
);
assert.ok(handlerMatch, "handleFormalization function found");
const handlerBody = handlerMatch[0];

const includesCheck = handlerBody.indexOf("existingFormalizationWorkspaceVersions.includes");
const mutateAsyncCall = handlerBody.indexOf("formalizeDiscussionMutation.mutateAsync");
assert.ok(includesCheck >= 0, "handler checks existingFormalizationWorkspaceVersions");
assert.ok(mutateAsyncCall >= 0, "handler calls mutateAsync");
assert.ok(
  includesCheck < mutateAsyncCall,
  "includes check occurs BEFORE mutateAsync call",
);

// Already-processed branch must clear proposal, set error, and return
const earlyReturnSection = handlerBody.slice(includesCheck, mutateAsyncCall);
assert.match(earlyReturnSection, /setFormalizationProposal\(null\)/, "early branch clears proposal");
assert.match(earlyReturnSection, /setFormalizationError\(/, "early branch sets error");
assert.match(earlyReturnSection, /return;/, "early branch returns");

// ===========================================================================
// §6.9 Explicit button testids and no auto-formalize
// ===========================================================================

assert.match(
  decisionSurfacesSource,
  /data-testid="workbench-formalization-proposal"/,
  "formalization proposal card has testid",
);
assert.match(
  decisionSurfacesSource,
  /data-testid="workbench-formalize-confirm"/,
  "formalize confirm button has testid",
);
assert.match(
  decisionSurfacesSource,
  /data-testid="workbench-discussion-state"/,
  "discussion state bar has testid",
);

// No useEffect auto-formalize — no useEffect calls mutateAsync for formalize
// Extract all useEffect bodies and verify none call formalizeDiscussionMutation.mutateAsync
const useEffectCalls = surfaceSource.match(/useEffect\([\s\S]*?\}, \[[\s\S]*?\]\);/g) ?? [];
for (const effectBody of useEffectCalls) {
  assert.doesNotMatch(
    effectBody,
    /formalizeDiscussionMutation\.mutateAsync/,
    "no useEffect calls formalize mutateAsync",
  );
}

// ===========================================================================
// §6.10 Entry mutual exclusion
// ===========================================================================

// Old plan entry requires !planVersion && !discussionWorkspace
assert.match(
  surfaceSource,
  /!planVersion\s*&&\s*!discussionWorkspace/,
  "old plan entry requires no workspace",
);

// Formalization card controlled by canOfferDiscussionFormalization
assert.match(
  surfaceSource,
  /canOfferDiscussionFormalization\(/,
  "formalization card uses canOffer gate",
);

// ===========================================================================
// §6.11 User-visible content boundary
// ===========================================================================

// State bar shows topic and counts
assert.match(decisionSurfacesSource, /workspace\.topic/, "state bar shows topic");
assert.match(decisionSurfacesSource, /active_option_ids\.length/, "state bar shows option count");
assert.match(decisionSurfacesSource, /active_constraint_ids\.length/, "state bar shows constraint count");

// Proposal card shows summary/changes/risk/workspace version
assert.match(decisionSurfacesSource, /matchingProposal\.summary/, "proposal shows summary");
assert.match(decisionSurfacesSource, /matchingProposal\.changes/, "proposal shows changes");
assert.match(decisionSurfacesSource, /risk_summary/, "proposal shows risk");

// Formalized plan shows message and event counts
assert.match(
  surfaceSource,
  /formalization_source_message_ids\.length/,
  "plan shows message count",
);
assert.match(
  surfaceSource,
  /formalization_source_event_ids\.length/,
  "plan shows event count",
);

// Must not render raw UUIDs or event JSON
assert.doesNotMatch(
  decisionSurfacesSource,
  /formalization_source_message_ids(?!\.length)/,
  "no raw message IDs rendered",
);
assert.doesNotMatch(
  decisionSurfacesSource,
  /formalization_source_event_ids(?!\.length)/,
  "no raw event IDs rendered",
);

console.log("All P26-H1 frontend contract tests passed.");
