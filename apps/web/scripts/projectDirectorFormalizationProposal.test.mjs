/**
 * P26-H2-M6 frontend contract tests for formalization proposal confirmation.
 *
 * Verifies 15 contract points using TypeScript AST extraction + execution
 * (not just string grep):
 *
 *  1. Proposal type requires top-level source_event_ids
 *  2. Change-level source_event_ids still exists
 *  3. Confirm request sends proposal_id
 *  4. Confirm request sends workspace_version
 *  5. Confirm request sends target
 *  6. user_confirmed is hardcoded true
 *  7. Cannot confirm without a Proposal
 *  8. ready_to_formalize Workspace alone cannot replace Proposal
 *  9. Proposal must have status=proposed
 * 10. Proposal and Workspace version must match
 * 11. Resume restores Proposal
 * 12. Resume restores top-level source_event_ids (via type)
 * 13. Confirm success clears Proposal
 * 14. stale/mismatch clears Proposal and refetches
 * 15. Displays "讨论状态已更新，请重新确认"
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

/** Extract all property names from a TypeScript interface declaration. */
function getInterfacePropertyNames(source, interfaceName) {
  const sf = ts.createSourceFile("types.ts", source, ts.ScriptTarget.Latest, true);
  let props = null;
  function visit(node) {
    if (ts.isInterfaceDeclaration(node) && node.name.getText(sf) === interfaceName) {
      props = node.members
        .filter(ts.isPropertySignature)
        .map((m) => m.name.getText(sf));
      return;
    }
    ts.forEachChild(node, visit);
  }
  visit(sf);
  return props;
}

/** Extract the JSON.stringify object-literal body from a named API function. */
function extractApiBodyObject(source, functionName) {
  const sf = ts.createSourceFile("api.ts", source, ts.ScriptTarget.Latest, true);
  let objText = null;
  function visit(node) {
    if (ts.isFunctionDeclaration(node) && node.name?.getText(sf) === functionName) {
      // Find JSON.stringify({...}) call
      function inner(n) {
        if (ts.isCallExpression(n) && n.expression.getText(sf) === "JSON.stringify") {
          const arg = n.arguments[0];
          if (arg && ts.isObjectLiteralExpression(arg)) {
            objText = arg.getText(sf);
          }
        }
        ts.forEachChild(n, inner);
      }
      inner(node);
      return;
    }
    ts.forEachChild(node, visit);
  }
  visit(sf);
  return objText;
}

/** Get property names from an object literal text snippet. */
function getObjectLiteralKeys(objText) {
  const sf = ts.createSourceFile("obj.ts", `const _x = ${objText};`, ts.ScriptTarget.Latest, true);
  let keys = [];
  function visit(node) {
    if (ts.isObjectLiteralExpression(node)) {
      keys = node.properties
        .filter(ts.isPropertyAssignment)
        .map((p) => p.name.getText(sf));
      return;
    }
    ts.forEachChild(node, visit);
  }
  visit(sf);
  return keys;
}

// ---------------------------------------------------------------------------
// Source files
// ---------------------------------------------------------------------------

const typesSource = readSource("../src/features/project-director/types.ts");
const apiSource = readSource("../src/features/project-director/api.ts");
const surfaceSource = readSource("../src/features/workbench/ProjectDirectorWorkbenchSurface.tsx");

// ===========================================================================
// §1 Proposal type requires top-level source_event_ids
// ===========================================================================

const proposalProps = getInterfacePropertyNames(typesSource, "ProjectDirectorFormalizationProposal");
assert.ok(proposalProps, "ProjectDirectorFormalizationProposal interface found");
assert.ok(
  proposalProps.includes("source_event_ids"),
  "Proposal type has top-level source_event_ids",
);
assert.ok(
  proposalProps.includes("source_message_ids"),
  "Proposal type has top-level source_message_ids",
);
assert.ok(
  proposalProps.includes("proposal_id"),
  "Proposal type has proposal_id",
);
assert.ok(
  proposalProps.includes("workspace_version"),
  "Proposal type has workspace_version",
);
assert.ok(
  proposalProps.includes("requires_confirmation"),
  "Proposal type has requires_confirmation",
);
assert.ok(
  proposalProps.includes("status"),
  "Proposal type has status",
);

// ===========================================================================
// §2 Change-level source_event_ids still exists
// ===========================================================================

const changeProps = getInterfacePropertyNames(typesSource, "ProjectDirectorFormalizationChange");
assert.ok(changeProps, "ProjectDirectorFormalizationChange interface found");
assert.ok(
  changeProps.includes("source_event_ids"),
  "Change type has source_event_ids",
);
assert.ok(
  changeProps.includes("change_type"),
  "Change type has change_type",
);
assert.ok(
  changeProps.includes("subject_key"),
  "Change type has subject_key",
);

// ===========================================================================
// §3–§6 API request body contract (AST extraction, not grep)
// ===========================================================================

const apiBody = extractApiBodyObject(apiSource, "formalizeProjectDirectorDiscussion");
assert.ok(apiBody, "formalizeProjectDirectorDiscussion JSON.stringify body found");
const apiKeys = getObjectLiteralKeys(apiBody);

// §3 sends proposal_id
assert.ok(
  apiKeys.includes("proposal_id"),
  "API body sends proposal_id",
);
assert.match(apiBody, /proposal_id:\s*input\.proposalId/, "proposal_id mapped from input.proposalId");

// §4 sends workspace_version
assert.ok(
  apiKeys.includes("workspace_version"),
  "API body sends workspace_version",
);
assert.match(apiBody, /workspace_version:\s*input\.workspaceVersion/, "workspace_version mapped from input.workspaceVersion");

// §5 sends target
assert.ok(
  apiKeys.includes("target"),
  "API body sends target",
);
assert.match(apiBody, /target:\s*input\.target/, "target mapped from input.target");

// §6 user_confirmed hardcoded true
assert.ok(
  apiKeys.includes("user_confirmed"),
  "API body sends user_confirmed",
);
assert.match(apiBody, /user_confirmed:\s*true/, "user_confirmed is hardcoded true");

// FormalizeProjectDirectorDiscussionInput type includes proposalId
const formalizeInputProps = getInterfacePropertyNames(typesSource, "FormalizeProjectDirectorDiscussionInput");
assert.ok(formalizeInputProps, "FormalizeProjectDirectorDiscussionInput interface found");
assert.ok(formalizeInputProps.includes("proposalId"), "Input type has proposalId");
assert.ok(formalizeInputProps.includes("workspaceVersion"), "Input type has workspaceVersion");
assert.ok(formalizeInputProps.includes("target"), "Input type has target");

// ===========================================================================
// §7–§10 canOfferDiscussionFormalization — executed decision function
// ===========================================================================

const canOffer = (input) =>
  transpileAndExecute(surfaceSource, "canOfferDiscussionFormalization", [input]);

const validProposal = {
  requires_confirmation: true,
  status: "proposed",
  target: "plan_revision",
  workspace_version: 3,
};
const readyWorkspace = { version_no: 3, discussion_status: "ready_to_formalize" };

// §7 Cannot confirm without a Proposal
assert.equal(
  canOffer({ workspace: readyWorkspace, proposal: null, existingWorkspaceVersions: [] }),
  false,
  "§7: null proposal → cannot confirm",
);

// §8 ready_to_formalize Workspace alone cannot replace Proposal
assert.equal(
  canOffer({ workspace: readyWorkspace, proposal: null, existingWorkspaceVersions: [1, 2] }),
  false,
  "§8: ready workspace without proposal → cannot confirm",
);
assert.equal(
  canOffer({
    workspace: { version_no: 3, discussion_status: "ready_to_formalize" },
    proposal: undefined,
    existingWorkspaceVersions: [],
  }),
  false,
  "§8: undefined proposal → cannot confirm",
);

// §9 Proposal must have status=proposed
assert.equal(
  canOffer({
    workspace: readyWorkspace,
    proposal: { ...validProposal, status: "confirmed" },
    existingWorkspaceVersions: [],
  }),
  false,
  "§9: status=confirmed → cannot confirm",
);
assert.equal(
  canOffer({
    workspace: readyWorkspace,
    proposal: { ...validProposal, status: "stale" },
    existingWorkspaceVersions: [],
  }),
  false,
  "§9: status=stale → cannot confirm",
);
assert.equal(
  canOffer({
    workspace: readyWorkspace,
    proposal: { ...validProposal, status: "proposed" },
    existingWorkspaceVersions: [],
  }),
  true,
  "§9: status=proposed → can confirm",
);

// §10 Proposal and Workspace version must match
assert.equal(
  canOffer({
    workspace: { version_no: 3, discussion_status: "ready_to_formalize" },
    proposal: { ...validProposal, workspace_version: 2 },
    existingWorkspaceVersions: [],
  }),
  false,
  "§10: version mismatch (proposal=2, workspace=3) → cannot confirm",
);
assert.equal(
  canOffer({
    workspace: { version_no: 3, discussion_status: "ready_to_formalize" },
    proposal: { ...validProposal, workspace_version: 4 },
    existingWorkspaceVersions: [],
  }),
  false,
  "§10: version mismatch (proposal=4, workspace=3) → cannot confirm",
);
assert.equal(
  canOffer({
    workspace: { version_no: 3, discussion_status: "ready_to_formalize" },
    proposal: { ...validProposal, workspace_version: 3 },
    existingWorkspaceVersions: [],
  }),
  true,
  "§10: version match → can confirm",
);

// Additional: already-formalized workspace version blocks
assert.equal(
  canOffer({
    workspace: readyWorkspace,
    proposal: validProposal,
    existingWorkspaceVersions: [3],
  }),
  false,
  "already-formalized workspace version → cannot confirm",
);

// Additional: target must be plan_revision
assert.equal(
  canOffer({
    workspace: readyWorkspace,
    proposal: { ...validProposal, target: "other" },
    existingWorkspaceVersions: [],
  }),
  false,
  "wrong target → cannot confirm",
);

// Additional: requires_confirmation must be truthy
assert.equal(
  canOffer({
    workspace: readyWorkspace,
    proposal: { ...validProposal, requires_confirmation: false },
    existingWorkspaceVersions: [],
  }),
  false,
  "requires_confirmation=false → cannot confirm",
);

// ===========================================================================
// §11 Resume restores Proposal — AST proof of resume effect
// ===========================================================================

{
  const sf = ts.createSourceFile("surface.tsx", surfaceSource, ts.ScriptTarget.Latest, true);
  let resumeEffect = null;
  function findResumeEffect(node) {
    if (ts.isCallExpression(node) && node.expression.getText(sf) === "useEffect") {
      const body = node.arguments[0]?.getText(sf) ?? "";
      if (body.includes("resumeQuery.data") && body.includes("setFormalizationProposal")) {
        resumeEffect = body;
      }
    }
    ts.forEachChild(node, findResumeEffect);
  }
  findResumeEffect(sf);
  assert.ok(resumeEffect, "§11: resume useEffect found that sets formalization proposal");
  assert.match(
    resumeEffect,
    /setFormalizationProposal\(resume\.formalization_proposal\s*\?\?\s*null\)/,
    "§11: resume restores proposal from resume.formalization_proposal",
  );
  assert.match(
    resumeEffect,
    /setDiscussionWorkspace\(resume\.discussion_workspace\)/,
    "§11: resume restores discussion workspace",
  );
  assert.match(
    resumeEffect,
    /setExistingFormalizationWorkspaceVersions/,
    "§11: resume restores existing formalization workspace versions",
  );
}

// ===========================================================================
// §12 Resume response type includes formalization_proposal with source_event_ids
// ===========================================================================

{
  const resumeProps = getInterfacePropertyNames(typesSource, "ProjectDirectorWorkbenchResume");
  assert.ok(resumeProps, "ProjectDirectorWorkbenchResume interface found");
  assert.ok(
    resumeProps.includes("formalization_proposal"),
    "§12: resume type has formalization_proposal field",
  );
  // The formalization_proposal is typed as ProjectDirectorFormalizationProposal | null
  // which we already proved in §1 has source_event_ids
  assert.match(
    typesSource,
    /formalization_proposal:\s*ProjectDirectorFormalizationProposal\s*\|\s*null/,
    "§12: formalization_proposal typed as ProjectDirectorFormalizationProposal | null",
  );
}

// ===========================================================================
// §13 Confirm success clears Proposal — AST proof of handler success path
// ===========================================================================

{
  const handlerFn = extractFunctionNode(surfaceSource, "handleFormalizeDiscussion");
  assert.ok(handlerFn, "handleFormalizeDiscussion found");
  const handlerSf = ts.createSourceFile("h.ts", surfaceSource, ts.ScriptTarget.Latest, true);
  const handlerText = handlerFn.getText(handlerSf);

  // Find the success path: after mutateAsync, before catch
  const mutateIdx = handlerText.indexOf("formalizeDiscussionMutation.mutateAsync");
  assert.ok(mutateIdx >= 0, "§13: mutateAsync call found in handler");

  // The success path is between mutateAsync and catch
  const catchIdx = handlerText.indexOf("} catch", mutateIdx);
  assert.ok(catchIdx >= 0, "§13: catch block found after mutateAsync");
  const successPath = handlerText.slice(mutateIdx, catchIdx);

  assert.match(
    successPath,
    /setFormalizationProposal\(null\)/,
    "§13: success path clears proposal",
  );
  assert.match(
    successPath,
    /setFormalizationError\(null\)/,
    "§13: success path clears error",
  );
  assert.match(
    successPath,
    /setPlanVersion\(result\.plan_version\)/,
    "§13: success path sets plan version from result",
  );
  assert.match(
    successPath,
    /mergeFormalizationWorkspaceVersions\(current,\s*result\.workspace_version\)/,
    "§13: success path merges workspace version into existing list",
  );

  // Verify the mutateAsync call passes proposalId
  const mutateCallSection = handlerText.slice(mutateIdx, mutateIdx + 300);
  assert.match(
    mutateCallSection,
    /proposalId:\s*formalizationProposal\.proposal_id/,
    "§13: mutateAsync sends proposal_id from proposal",
  );
  assert.match(
    mutateCallSection,
    /workspaceVersion:\s*discussionWorkspace\.version_no/,
    "§13: mutateAsync sends workspace version from workspace",
  );
  assert.match(
    mutateCallSection,
    /target:\s*formalizationProposal\.target/,
    "§13: mutateAsync sends target from proposal",
  );
}

// ===========================================================================
// §14 stale/mismatch clears Proposal and refetches — AST proof of catch path
// ===========================================================================

{
  const handlerFn = extractFunctionNode(surfaceSource, "handleFormalizeDiscussion");
  const handlerSf = ts.createSourceFile("h.ts", surfaceSource, ts.ScriptTarget.Latest, true);
  const handlerText = handlerFn.getText(handlerSf);

  // Extract catch block
  const catchMatch = handlerText.match(/catch\s*\(error\)\s*\{([\s\S]*?)\}\s*$/);
  assert.ok(catchMatch, "§14: catch block found in handleFormalizeDiscussion");
  const catchBody = catchMatch[1];

  // Stale detection: checks for project_director_formalization_ prefix
  assert.match(
    catchBody,
    /project_director_formalization_/,
    "§14: catch checks for project_director_formalization_ error prefix",
  );

  // Clears proposal
  assert.match(
    catchBody,
    /setFormalizationProposal\(null\)/,
    "§14: stale path clears proposal",
  );

  // Triggers refetch
  assert.match(
    catchBody,
    /resumeQuery\.refetch\(\)/,
    "§14: stale path triggers resume refetch",
  );

  // After refetch, restores full state from resume
  assert.match(
    catchBody,
    /setSession\(resumeResult\.data\.session\)/,
    "§14: refetch restores session",
  );
  assert.match(
    catchBody,
    /setDiscussionWorkspace\(resumeResult\.data\.discussion_workspace\)/,
    "§14: refetch restores workspace",
  );
  assert.match(
    catchBody,
    /setFormalizationProposal\(resumeResult\.data\.formalization_proposal\s*\?\?\s*null\)/,
    "§14: refetch restores proposal from fresh resume data",
  );
  assert.match(
    catchBody,
    /setExistingFormalizationWorkspaceVersions/,
    "§14: refetch restores existing workspace versions",
  );

  // Must NOT auto-retry formalize
  assert.doesNotMatch(
    catchBody,
    /formalizeDiscussionMutation\.mutateAsync/,
    "§14: stale path does NOT auto-retry formalize",
  );
}

// ===========================================================================
// §15 Displays "讨论状态已更新，请重新确认"
// ===========================================================================

{
  const handlerFn = extractFunctionNode(surfaceSource, "handleFormalizeDiscussion");
  const handlerSf = ts.createSourceFile("h.ts", surfaceSource, ts.ScriptTarget.Latest, true);
  const handlerText = handlerFn.getText(handlerSf);

  const catchMatch = handlerText.match(/catch\s*\(error\)\s*\{([\s\S]*?)\}\s*$/);
  const catchBody = catchMatch[1];

  // Error message shown to user
  assert.match(
    catchBody,
    /setFormalizationError\("讨论状态已更新，请重新确认"\)/,
    "§15: stale path sets formalization error to '讨论状态已更新，请重新确认'",
  );

  // Status message also set
  assert.match(
    catchBody,
    /setStatusMessage\("讨论状态已更新，请重新确认"\)/,
    "§15: stale path sets status message to '讨论状态已更新，请重新确认'",
  );
}

// ===========================================================================
// §Extra: Handler gate ordering — proposal required before mutateAsync
// ===========================================================================

{
  const handlerFn = extractFunctionNode(surfaceSource, "handleFormalizeDiscussion");
  const handlerSf = ts.createSourceFile("h.ts", surfaceSource, ts.ScriptTarget.Latest, true);
  const handlerText = handlerFn.getText(handlerSf);

  // Guard: !formalizationProposal check comes before mutateAsync
  const proposalGuardIdx = handlerText.indexOf("!formalizationProposal");
  const mutateIdx = handlerText.indexOf("formalizeDiscussionMutation.mutateAsync");
  assert.ok(proposalGuardIdx >= 0, "handler guards on !formalizationProposal");
  assert.ok(mutateIdx >= 0, "handler calls mutateAsync");
  assert.ok(
    proposalGuardIdx < mutateIdx,
    "proposal null-guard appears before mutateAsync — cannot confirm without proposal",
  );

  // canOfferDiscussionFormalization gate also before mutateAsync
  const canOfferIdx = handlerText.indexOf("canOfferDiscussionFormalization");
  assert.ok(canOfferIdx >= 0, "handler calls canOfferDiscussionFormalization");
  assert.ok(
    canOfferIdx < mutateIdx,
    "canOfferDiscussionFormalization gate appears before mutateAsync",
  );
}

// ===========================================================================
// §Extra: FormalizeProjectDirectorDiscussionResponse type contract
// ===========================================================================

{
  const responseProps = getInterfacePropertyNames(typesSource, "FormalizeProjectDirectorDiscussionResponse");
  assert.ok(responseProps, "FormalizeProjectDirectorDiscussionResponse interface found");
  assert.ok(responseProps.includes("proposal_id"), "response has proposal_id");
  assert.ok(responseProps.includes("workspace_version"), "response has workspace_version");
  assert.ok(responseProps.includes("source_event_ids"), "response has source_event_ids");
  assert.ok(responseProps.includes("source_message_ids"), "response has source_message_ids");
  assert.ok(responseProps.includes("plan_version"), "response has plan_version");
  assert.ok(responseProps.includes("idempotent_replay"), "response has idempotent_replay");
}

console.log("All P26-H2-M6 formalization proposal frontend contract tests passed.");
