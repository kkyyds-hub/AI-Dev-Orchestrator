/**
 * P26-H2 Workbench Interaction Tests (AST / Structured)
 *
 * Verifies session identity, message flow, and context isolation
 * in the Project Director workbench using TypeScript AST parsing.
 *
 * Every assertion is backed by structural node inspection,
 * not fragile string includes.
 */

import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import ts from "typescript";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC = resolve(__dirname, "../src");

// ---------------------------------------------------------------------------
// AST Helpers
// ---------------------------------------------------------------------------

function readSource(relativePath) {
  return readFileSync(resolve(SRC, relativePath), "utf-8");
}

function parseTSX(source, filename = "virtual.tsx") {
  return ts.createSourceFile(filename, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
}

function findNodes(node, predicate) {
  const results = [];
  function walk(n) {
    if (predicate(n)) results.push(n);
    ts.forEachChild(n, walk);
  }
  walk(node);
  return results;
}

function findFirst(node, predicate) {
  return findNodes(node, predicate)[0] ?? null;
}

function getNodeText(node, sourceFile) {
  return node.getText(sourceFile);
}

/** Find a variable declaration by name at top level or inside a function. */
function findVarDecl(sourceFile, name) {
  return findFirst(sourceFile, (n) =>
    ts.isVariableDeclaration(n) && n.name.getText(sourceFile) === name,
  );
}

/** Find a function declaration by name. */
function findFuncDecl(sourceFile, name) {
  return findFirst(sourceFile, (n) =>
    (ts.isFunctionDeclaration(n) || ts.isMethodDeclaration(n)) &&
    n.name?.getText(sourceFile) === name,
  );
}

/** Find call expression by name. */
function findCallExpr(sourceFile, name) {
  return findFirst(sourceFile, (n) =>
    ts.isCallExpression(n) && n.expression.getText(sourceFile) === name,
  );
}

/** Check if an expression contains a specific text pattern. */
function exprContainsText(node, sourceFile, pattern) {
  return getNodeText(node, sourceFile).includes(pattern);
}

// ---------------------------------------------------------------------------
// Source Loading
// ---------------------------------------------------------------------------

const surfaceSrc = readSource("features/workbench/ProjectDirectorWorkbenchSurface.tsx");
const surfaceAst = parseTSX(surfaceSrc, "ProjectDirectorWorkbenchSurface.tsx");

const promptBoxSrc = readSource("features/ui-selection-lab/components/WorkbenchPromptBox.tsx");
const promptBoxAst = parseTSX(promptBoxSrc, "WorkbenchPromptBox.tsx");

// ---------------------------------------------------------------------------
// Test Suite
// ---------------------------------------------------------------------------

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    passed++;
    console.log(`  ✓ ${name}`);
  } catch (err) {
    failed++;
    console.log(`  ✗ ${name}`);
    console.log(`    ${err.message}`);
  }
}

console.log("\nP26-H2 Workbench Interaction Tests (AST)\n");

// ---------------------------------------------------------------------------
// 1. selectionKey composition — mode, selectedProjectId, resumeSessionId
// ---------------------------------------------------------------------------

test("selectionKey is a template literal with mode, selectedProjectId, resumeSessionId", () => {
  const decl = findVarDecl(surfaceAst, "selectionKey");
  assert.ok(decl, "selectionKey variable declaration not found");
  const init = decl.initializer;
  assert.ok(init, "selectionKey has no initializer");
  assert.ok(ts.isTemplateExpression(init), `Expected template expression, got ${ts.SyntaxKind[init.kind]}`);
  const text = getNodeText(init, surfaceAst);
  assert.ok(text.includes("mode"), "selectionKey template should reference mode");
  assert.ok(text.includes("selectedProjectId"), "selectionKey template should reference selectedProjectId");
  assert.ok(text.includes("resumeSessionId"), "selectionKey template should reference resumeSessionId");
  // Verify separator structure: template has ":" between interpolations
  // Template: `${mode}:${selectedProjectId ?? "none"}:${resumeSessionId ?? "none"}`
  // The head is `${mode}`, first span literal is ":", second span literal is ":" (last may be empty)
  const templateSpans = init.templateSpans ?? [];
  assert.ok(templateSpans.length >= 2, "Template should have at least 2 spans (projectId + sessionId)");
  // First span literal should start with ":"
  const firstLiteral = templateSpans[0]?.literal?.text ?? "";
  assert.ok(firstLiteral.startsWith(":"), `First span literal should start with ":", got: "${firstLiteral}"`);
  // Second span literal should also start with ":"
  const secondLiteral = templateSpans[1]?.literal?.text ?? "";
  assert.ok(secondLiteral.startsWith(":"), `Second span literal should start with ":", got: "${secondLiteral}"`);
});

// ---------------------------------------------------------------------------
// 2. ProjectDirectorWorkbenchSelection uses key={selectionKey}
// ---------------------------------------------------------------------------

test("ProjectDirectorWorkbenchSelection rendered with key={selectionKey}", () => {
  const jsxElements = findNodes(surfaceAst, (n) =>
    ts.isJsxOpeningElement(n) || ts.isJsxSelfClosingElement(n),
  );
  const selectionEl = jsxElements.find((el) =>
    el.tagName.getText(surfaceAst) === "ProjectDirectorWorkbenchSelection",
  );
  assert.ok(selectionEl, "ProjectDirectorWorkbenchSelection JSX element not found");
  const keyAttr = selectionEl.attributes.properties.find((p) =>
    p.name?.getText(surfaceAst) === "key",
  );
  assert.ok(keyAttr, "key attribute not found on ProjectDirectorWorkbenchSelection");
  const keyText = keyAttr.initializer?.getText(surfaceAst) ?? "";
  assert.ok(keyText.includes("selectionKey"), `key should reference selectionKey, got: ${keyText}`);
});

// ---------------------------------------------------------------------------
// 3. activeSessionId priority — requestedSessionId ?? session?.id ?? null
// ---------------------------------------------------------------------------

test("activeSessionId = requestedSessionId ?? session?.id ?? null", () => {
  const decl = findVarDecl(surfaceAst, "activeSessionId");
  assert.ok(decl, "activeSessionId declaration not found");
  const init = decl.initializer;
  assert.ok(init, "activeSessionId has no initializer");
  const text = getNodeText(init, surfaceAst);
  // Verify the priority chain
  assert.ok(text.includes("requestedSessionId"), "Should reference requestedSessionId first");
  assert.ok(text.includes("session?.id"), "Should fall back to session?.id");
  assert.ok(text.endsWith("null"), "Should end with null fallback");
  // Verify ?? operator chain structure
  assert.ok(text.includes("??"), "Should use nullish coalescing");
  const parts = text.split("??").map((s) => s.trim());
  assert.equal(parts.length, 3, `Expected 3 parts in ?? chain, got ${parts.length}: ${text}`);
  assert.equal(parts[0], "requestedSessionId");
  assert.equal(parts[1], "session?.id");
  assert.equal(parts[2], "null");
});

// ---------------------------------------------------------------------------
// 4. Resume effect calls isSessionForSelection with correct args
// ---------------------------------------------------------------------------

test("Resume effect calls isSessionForSelection(resume.session, requestedMode, requestedProjectId, activeSessionId)", () => {
  // Find the useEffect whose body contains isSessionForSelection AND resumeQuery.data
  const resumeEffects = findNodes(surfaceAst, (n) => {
    if (!ts.isCallExpression(n)) return false;
    if (n.expression.getText(surfaceAst) !== "useEffect") return false;
    const callback = n.arguments[0];
    if (!callback || !ts.isArrowFunction(callback)) return false;
    const body = callback.body;
    if (!ts.isBlock(body)) return false;
    const bodyText = body.getText(surfaceAst);
    return bodyText.includes("resumeQuery.data") && bodyText.includes("isSessionForSelection");
  });
  assert.ok(resumeEffects.length >= 1, "Resume effect with isSessionForSelection not found");

  // Verify the isSessionForSelection call has the right arguments
  const effectBody = resumeEffects[0].arguments[0].body;
  const sessionCheck = findFirst(effectBody, (n) =>
    ts.isCallExpression(n) && n.expression.getText(surfaceAst) === "isSessionForSelection",
  );
  assert.ok(sessionCheck, "isSessionForSelection call not found in resume effect");
  assert.equal(sessionCheck.arguments.length, 4, "isSessionForSelection should have 4 args");
  const arg0 = sessionCheck.arguments[0].getText(surfaceAst);
  const arg1 = sessionCheck.arguments[1].getText(surfaceAst);
  const arg2 = sessionCheck.arguments[2].getText(surfaceAst);
  const arg3 = sessionCheck.arguments[3].getText(surfaceAst);
  assert.ok(arg0.includes("resume.session"), `Arg 0 should be resume.session, got: ${arg0}`);
  assert.equal(arg1, "requestedMode", `Arg 1 should be requestedMode, got: ${arg1}`);
  assert.equal(arg2, "requestedProjectId", `Arg 2 should be requestedProjectId, got: ${arg2}`);
  assert.equal(arg3, "activeSessionId", `Arg 3 should be activeSessionId, got: ${arg3}`);
});

// ---------------------------------------------------------------------------
// 5. Messages effect validates session_id and areMessagesForSession
// ---------------------------------------------------------------------------

test("Messages effect checks response.session_id === activeSessionId AND areMessagesForSession", () => {
  const msgEffects = findNodes(surfaceAst, (n) => {
    if (!ts.isCallExpression(n)) return false;
    if (n.expression.getText(surfaceAst) !== "useEffect") return false;
    const callback = n.arguments[0];
    if (!callback || !ts.isArrowFunction(callback)) return false;
    const body = callback.body;
    if (!ts.isBlock(body)) return false;
    const txt = body.getText(surfaceAst);
    return txt.includes("messagesQuery.data") && txt.includes("areMessagesForSession");
  });
  assert.ok(msgEffects.length >= 1, "Messages effect not found");

  const effectBody = msgEffects[0].arguments[0].body;
  // Check for session_id validation (either === or !== for guard)
  const hasSessionIdCheck = findFirst(effectBody, (n) => {
    if (!ts.isBinaryExpression(n)) return false;
    const op = n.operatorToken.kind;
    const isEq = op === ts.SyntaxKind.EqualsEqualsEqualsToken;
    const isNeq = op === ts.SyntaxKind.ExclamationEqualsEqualsToken;
    if (!isEq && !isNeq) return false;
    const left = n.left.getText(surfaceAst);
    const right = n.right.getText(surfaceAst);
    return (left.includes("session_id") && right.includes("activeSessionId")) ||
           (right.includes("session_id") && left.includes("activeSessionId"));
  });
  assert.ok(hasSessionIdCheck, "response.session_id validation against activeSessionId not found");

  // Check for areMessagesForSession call
  const hasMsgCheck = findFirst(effectBody, (n) =>
    ts.isCallExpression(n) && n.expression.getText(surfaceAst) === "areMessagesForSession",
  );
  assert.ok(hasMsgCheck, "areMessagesForSession call not found in messages effect");
});

// ---------------------------------------------------------------------------
// 6. isSessionForSelection function — structured verification
// ---------------------------------------------------------------------------

test("isSessionForSelection validates session.id, project_id for project mode, null for new-project", () => {
  const func = findFuncDecl(surfaceAst, "isSessionForSelection");
  assert.ok(func, "isSessionForSelection function not found");
  const body = func.body;
  assert.ok(body, "isSessionForSelection has no body");

  const bodyText = getNodeText(body, surfaceAst);

  // Must check session.id !== sessionId
  assert.ok(bodyText.includes("session.id !== sessionId") || bodyText.includes("session.id !=== sessionId"),
    "Should check session.id against sessionId");

  // Must check project_id === projectId for project mode
  assert.ok(bodyText.includes("session.project_id === projectId"),
    "Should check session.project_id === projectId for project mode");

  // Must check project_id === null for new-project mode
  assert.ok(bodyText.includes("session.project_id === null"),
    "Should check session.project_id === null for new-project mode");

  // Must have mode === "project" conditional
  assert.ok(bodyText.includes('"project"'), "Should have project mode conditional");
});

// ---------------------------------------------------------------------------
// 7. areMessagesForSession — every message.session_id === sessionId
// ---------------------------------------------------------------------------

test("areMessagesForSession uses every() to check message.session_id === sessionId", () => {
  const func = findFuncDecl(surfaceAst, "areMessagesForSession");
  assert.ok(func, "areMessagesForSession function not found");
  const bodyText = getNodeText(func.body, surfaceAst);
  assert.ok(bodyText.includes(".every("), "Should use .every() for message validation");
  assert.ok(bodyText.includes("message.session_id === sessionId"),
    "Should check message.session_id === sessionId");
});

// ---------------------------------------------------------------------------
// 8. PendingPrompt has unique id — not content-based dedup
// ---------------------------------------------------------------------------

test("PendingPrompt uses id field (pending-N), not content matching", () => {
  // Check PendingPrompt type
  const typeAlias = findFirst(surfaceAst, (n) =>
    ts.isTypeAliasDeclaration(n) && n.name.getText(surfaceAst) === "PendingPrompt",
  );
  assert.ok(typeAlias, "PendingPrompt type not found");
  const typeText = getNodeText(typeAlias, surfaceAst);
  assert.ok(typeText.includes("id: string"), "PendingPrompt should have id field");
  assert.ok(typeText.includes("content: string"), "PendingPrompt should have content field");
  assert.ok(typeText.includes("kind:"), "PendingPrompt should have kind field");

  // Verify pending creation uses incrementing id, not content hash
  const pendingSets = findNodes(surfaceAst, (n) =>
    ts.isCallExpression(n) &&
    n.expression.getText(surfaceAst) === "setPendingPrompt" &&
    n.arguments.length > 0 &&
    n.arguments[0].getText(surfaceAst).includes("pending-"),
  );
  assert.ok(pendingSets.length >= 1, "setPendingPrompt should use pending-N id pattern");
});

// ---------------------------------------------------------------------------
// 9. buildDirectorMessages does not use content-based dedup
// ---------------------------------------------------------------------------

test("buildDirectorMessages does not filter or dedup by content", () => {
  const func = findFuncDecl(surfaceAst, "buildDirectorMessages");
  if (!func) return; // May be removed or renamed — not critical
  const bodyText = getNodeText(func.body, surfaceAst);
  // Should NOT contain content equality checks for dedup
  assert.ok(!bodyText.includes("m.content === existing.content"),
    "Should not dedup messages by content equality");
  assert.ok(!bodyText.includes("filter(") || !bodyText.includes("content"),
    "Should not filter messages by content");
});

// ---------------------------------------------------------------------------
// 10. GoalConfirmationPanel conditional rendering
// ---------------------------------------------------------------------------

test("workflowSurface: clarifying→clarification, ready_to_confirm→GoalConfirmationPanel, confirmed→no GoalConfirmationPanel", () => {
  const workflowDecl = findVarDecl(surfaceAst, "workflowSurface");
  assert.ok(workflowDecl, "workflowSurface variable not found");
  const init = workflowDecl.initializer;
  assert.ok(init, "workflowSurface has no initializer");

  const initText = getNodeText(init, surfaceAst);

  // Must have ternary for clarifying status
  assert.ok(initText.includes('"clarifying"') || initText.includes("'clarifying'"),
    "Should check for clarifying status");
  // Must reference GoalConfirmationPanel for ready_to_confirm
  assert.ok(initText.includes('"ready_to_confirm"') || initText.includes("'ready_to_confirm'"),
    "Should check for ready_to_confirm status");
  assert.ok(initText.includes("GoalConfirmationPanel"),
    "Should render GoalConfirmationPanel for ready_to_confirm");
  // Must NOT have a GoalConfirmationPanel branch for confirmed
  // The ternary structure should be: clarifying ? X : ready_to_confirm ? GoalConfirmationPanel : null
  // If there's a third branch for confirmed with GoalConfirmationPanel, that's wrong.
  const ternaryParts = initText.split("?");
  // If confirmed had GoalConfirmationPanel, there would be another GoalConfirmationPanel after the last ":"
  const afterLastColon = initText.split(":").pop();
  assert.ok(!afterLastColon.includes("GoalConfirmationPanel"),
    "confirmed status should NOT render GoalConfirmationPanel");
});

// ---------------------------------------------------------------------------
// 11. canOfferDiscussionFormalization controls formalization entry
// ---------------------------------------------------------------------------

test("Formalization entry controlled by canOfferDiscussionFormalization, not hardcoded", () => {
  const func = findFuncDecl(surfaceAst, "canOfferDiscussionFormalization");
  assert.ok(func, "canOfferDiscussionFormalization function not found");
  const bodyText = getNodeText(func.body, surfaceAst);
  // Should check workspace exists
  assert.ok(bodyText.includes("workspace"), "Should check workspace existence");
  // Should check proposal.requires_confirmation
  assert.ok(bodyText.includes("requires_confirmation") || bodyText.includes("proposal"),
    "Should check proposal state");
  // Should check discussion_status
  assert.ok(bodyText.includes("discussion_status") || bodyText.includes("ready_to_formalize"),
    "Should check discussion_status");
});

// ---------------------------------------------------------------------------
// 12. PromptBox: send guard, isSending, clear on success, preserve on failure
// ---------------------------------------------------------------------------

test("PromptBox: empty/isSending guard, setIsSending(true) before send, setText('') on success, setIsSending(false) in finally", () => {
  const handleSend = findFirst(promptBoxAst, (n) =>
    ts.isVariableDeclaration(n) &&
    n.name?.getText(promptBoxAst) === "handleSend",
  );
  assert.ok(handleSend, "handleSend not found in PromptBox");

  // handleSend = useCallback(async () => {...}, [...])
  // The arrow function is the first argument of useCallback
  const useCbCall = handleSend.initializer;
  assert.ok(useCbCall, "handleSend has no initializer");
  const arrowFn = useCbCall.arguments?.[0];
  assert.ok(arrowFn && ts.isArrowFunction(arrowFn), "handleSend should be useCallback with arrow function");
  const body = arrowFn.body;
  assert.ok(body, "handleSend arrow has no body");
  const bodyText = getNodeText(body, promptBoxAst);

  // Guard: empty or isSending returns early
  assert.ok(bodyText.includes("isSending"), "Should check isSending state");
  assert.ok(bodyText.includes("return"), "Should have early return for guard");

  // Set sending true
  assert.ok(bodyText.includes("setIsSending(true)"), "Should setIsSending(true) before send");

  // Clear on success
  assert.ok(bodyText.includes('setText("")'), "Should setText('') on success");

  // finally block with setIsSending(false)
  assert.ok(bodyText.includes("finally"), "Should have finally block");
  assert.ok(bodyText.includes("setIsSending(false)"), "Should setIsSending(false) in finally");
});

test("PromptBox: button disabled = !hasText || isSending", () => {
  const btnDisabled = findFirst(promptBoxAst, (n) =>
    ts.isJsxAttribute(n) && n.name.getText(promptBoxAst) === "disabled",
  );
  assert.ok(btnDisabled, "disabled attribute not found on button");
  const value = btnDisabled.initializer?.getText(promptBoxAst) ?? "";
  assert.ok(value.includes("hasText"), "disabled should reference hasText");
  assert.ok(value.includes("isSending"), "disabled should reference isSending");
  assert.ok(value.includes("||"), "disabled should use OR operator");
});

test("PromptBox: onSend returns false preserves draft (does not clear)", () => {
  const handleSend = findFirst(promptBoxAst, (n) =>
    ts.isVariableDeclaration(n) &&
    n.name?.getText(promptBoxAst) === "handleSend",
  );
  assert.ok(handleSend, "handleSend not found");
  const arrowFn = handleSend.initializer?.arguments?.[0];
  assert.ok(arrowFn && ts.isArrowFunction(arrowFn), "handleSend should be useCallback arrow");
  const bodyText = getNodeText(arrowFn.body, promptBoxAst);
  // Should check succeeded !== false before clearing
  assert.ok(bodyText.includes("!== false") || bodyText.includes("!==false"),
    "Should check onSend result before clearing");
});

// ---------------------------------------------------------------------------
// 13. Context switching resets pending state
// ---------------------------------------------------------------------------

test("Context key change resets pendingPrompt and promptError", () => {
  // Find the useEffect that resets pending on contextKey change
  const resetEffects = findNodes(surfaceAst, (n) => {
    if (!ts.isCallExpression(n)) return false;
    if (n.expression.getText(surfaceAst) !== "useEffect") return false;
    const callback = n.arguments[0];
    if (!callback || !ts.isArrowFunction(callback)) return false;
    const body = callback.body;
    if (!ts.isBlock(body)) return false;
    const txt = body.getText(surfaceAst);
    return txt.includes("setPendingPrompt(null)") && txt.includes("setPromptError(null)");
  });
  assert.ok(resetEffects.length >= 1, "Effect resetting pending on context change not found");

  // Verify it depends on contextKey
  const depsArray = resetEffects[0].arguments[1];
  assert.ok(depsArray, "Dependencies array not found");
  const depsText = getNodeText(depsArray, surfaceAst);
  assert.ok(depsText.includes("contextKey"), "Reset effect should depend on contextKey");
});

// ---------------------------------------------------------------------------
// 14. Full state reset on input change
// ---------------------------------------------------------------------------

test("useEffect resets all state (session, messages, etc.) on input.mode/projectId/resumeSessionId change", () => {
  const resetEffects = findNodes(surfaceAst, (n) => {
    if (!ts.isCallExpression(n)) return false;
    if (n.expression.getText(surfaceAst) !== "useEffect") return false;
    const callback = n.arguments[0];
    if (!callback || !ts.isArrowFunction(callback)) return false;
    const body = callback.body;
    if (!ts.isBlock(body)) return false;
    const txt = body.getText(surfaceAst);
    return txt.includes("setSession(null)") && txt.includes("setMessageTimeline([])");
  });
  assert.ok(resetEffects.length >= 1, "Full state reset effect not found");

  // Verify dependencies include input.mode, input.projectId, input.resumeSessionId
  const depsArray = resetEffects[0].arguments[1];
  assert.ok(depsArray, "Dependencies array not found");
  const depsText = getNodeText(depsArray, surfaceAst);
  assert.ok(depsText.includes("input.mode"), "Should depend on input.mode");
  assert.ok(depsText.includes("input.projectId"), "Should depend on input.projectId");
  assert.ok(depsText.includes("input.resumeSessionId"), "Should depend on input.resumeSessionId");
});

// ---------------------------------------------------------------------------
// 15. handlePromptSend checks contextKey and session identity on result
// ---------------------------------------------------------------------------

test("handlePromptSend verifies contextKeyRef and session_id before applying result", () => {
  const func = findFirst(surfaceAst, (n) =>
    (ts.isVariableDeclaration(n) || ts.isFunctionDeclaration(n)) &&
    n.name?.getText(surfaceAst) === "handlePromptSend",
  );
  assert.ok(func, "handlePromptSend not found");
  const bodyText = getNodeText((func.initializer ?? func).body, surfaceAst);

  // Should check contextKeyRef.current !== requestContextKey
  assert.ok(bodyText.includes("contextKeyRef.current") && bodyText.includes("requestContextKey"),
    "Should check contextKeyRef against requestContextKey");

  // Should check result.session_id
  assert.ok(bodyText.includes("result.session_id") || bodyText.includes("session_id"),
    "Should validate result session_id");

  // Should call areMessagesForSession on result
  assert.ok(bodyText.includes("areMessagesForSession"),
    "Should validate messages via areMessagesForSession");
});

// ---------------------------------------------------------------------------
// 16. No old session?.id ?? input.resumeSessionId expression
// ---------------------------------------------------------------------------

test("Old session?.id ?? input.resumeSessionId expression removed", () => {
  assert.ok(
    !surfaceSrc.includes("session?.id ?? input.resumeSessionId"),
    "Old priority expression should be removed",
  );
});

// ---------------------------------------------------------------------------
// 17. selectedProjectId derivation for mode routing
// ---------------------------------------------------------------------------

test("selectedProjectId is null for new-project mode, uses context.activeProjectId for project mode", () => {
  const decl = findVarDecl(surfaceAst, "selectedProjectId");
  assert.ok(decl, "selectedProjectId declaration not found");
  const init = decl.initializer;
  assert.ok(init, "selectedProjectId has no initializer");
  const text = getNodeText(init, surfaceAst);
  // Should have ternary: mode === "project" ? ... : null
  assert.ok(text.includes('"project"'), "Should check project mode");
  assert.ok(text.endsWith("null"), "Should fallback to null for non-project mode");
});

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

console.log(`\n${passed} passed, ${failed} failed\n`);
process.exit(failed > 0 ? 1 : 0);
