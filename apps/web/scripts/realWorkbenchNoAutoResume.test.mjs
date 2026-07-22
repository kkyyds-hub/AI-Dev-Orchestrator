/**
 * P26-H1: Verify workbench does NOT auto-resume without an explicit session target.
 *
 * Correct contract:
 *   "No auto resume" means no historical session is fetched when there is no
 *   explicit Session ID target. It does NOT prohibit a directed Resume read
 *   for the session the user has already entered or explicitly selected.
 *
 * Production expression (via AST):
 *   sessionId: session?.id ?? input.resumeSessionId
 *   enabled:   Boolean(session?.id ?? input.resumeSessionId)
 *
 * This means:
 *   - Initial blank workbench (session=null, resumeSessionId=null) → enabled=false
 *   - Current session exists (session.id set, resumeSessionId=null) → enabled=true (directed)
 *   - Explicit selection (session=null, resumeSessionId=set) → enabled=true
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

function findCallExpression(source, callName) {
  const sf = ts.createSourceFile("x.ts", source, ts.ScriptTarget.Latest, true);
  let result = null;
  function visit(node) {
    if (
      ts.isCallExpression(node) &&
      node.expression.getText(sf) === callName
    ) {
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

function transpileAndExecute(exprText, context) {
  const wrapped = `(${exprText})`;
  const result = ts.transpileModule(wrapped, {
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ESNext },
  });
  const script = new vm.Script(result.outputText);
  const fn = script.runInContext(vm.createContext({ Boolean, console }));
  return typeof fn === "function" ? fn() : fn;
}

// ---------------------------------------------------------------------------
// Source files
// ---------------------------------------------------------------------------

const directorSurfaceSource = readSource(
  "../src/features/workbench/ProjectDirectorWorkbenchSurface.tsx",
);
const hooksSource = readSource("../src/features/project-director/hooks.ts");
const workbenchPageSource = readSource("../src/pages/workbench/WorkbenchPage.tsx");

// ---------------------------------------------------------------------------
// §4.1 AST: find useProjectDirectorWorkbenchResume call
// ---------------------------------------------------------------------------

const resumeCall = findCallExpression(directorSurfaceSource, "useProjectDirectorWorkbenchResume");
assert.ok(resumeCall, "useProjectDirectorWorkbenchResume call found in surface");

const sessionIdExpr = getArgPropertyText(resumeCall, 0, "sessionId", directorSurfaceSource);
const enabledExpr = getArgPropertyText(resumeCall, 1, "enabled", directorSurfaceSource);

assert.ok(sessionIdExpr, "sessionId property found in first arg");
assert.ok(enabledExpr, "enabled property found in second arg");

// Verify the production expressions match the expected form
assert.match(
  sessionIdExpr,
  /session\?\.id\s*\?\?\s*input\.resumeSessionId/,
  "sessionId: session?.id ?? input.resumeSessionId",
);
assert.match(
  enabledExpr,
  /Boolean\(session\?\.id\s*\?\?\s*input\.resumeSessionId\)/,
  "enabled: Boolean(session?.id ?? input.resumeSessionId)",
);

// ---------------------------------------------------------------------------
// §4.2 Execute production expressions via vm
// ---------------------------------------------------------------------------

function evalResume(session, resumeSessionId) {
  const ctx = { session, input: { resumeSessionId }, Boolean };
  const sandbox = vm.createContext(ctx);
  const sid = new vm.Script(sessionIdExpr).runInContext(sandbox);
  const en = new vm.Script(enabledExpr).runInContext(sandbox);
  return { sessionId: sid, enabled: en };
}

// Initial blank workbench: no target → disabled
{
  const r = evalResume(null, null);
  assert.equal(r.sessionId, null, "blank: sessionId → null");
  assert.equal(r.enabled, false, "blank: enabled → false");
}

// Current session exists: directed read
{
  const r = evalResume({ id: "current-session" }, null);
  assert.equal(r.sessionId, "current-session", "current session: sessionId → session.id");
  assert.equal(r.enabled, true, "current session: enabled → true");
}

// Explicit selection: user picked a history session
{
  const r = evalResume(null, "selected-session");
  assert.equal(r.sessionId, "selected-session", "explicit: sessionId → resumeSessionId");
  assert.equal(r.enabled, true, "explicit: enabled → true");
}

// Both exist: session.id takes precedence (nullish coalescing)
{
  const r = evalResume({ id: "current-session" }, "selected-session");
  assert.equal(r.sessionId, "current-session", "both: sessionId → session.id");
  assert.equal(r.enabled, true, "both: enabled → true");
}

// ---------------------------------------------------------------------------
// §4.3 Preserve existing boundaries
// ---------------------------------------------------------------------------

assert.match(
  hooksSource,
  /useProjectDirectorWorkbenchResume\([\s\S]*options\?: ProjectDirectorConversationQueryOptions/,
  "Resume hook accepts query options",
);
assert.match(
  hooksSource,
  /enabled: options\?\.enabled/,
  "Resume hook allows callers to disable automatic resume queries",
);

assert.match(
  directorSurfaceSource,
  /project_id: input\.mode === "project" \? input\.projectId : null/,
  "New-project prompt payload must not inherit a stale project_id",
);
assert.match(
  workbenchPageSource,
  /navigate\("\/workbench\?mode=new-project"\)/,
  "New project entry routes to clean new-project mode",
);
assert.doesNotMatch(
  workbenchPageSource,
  /workbench\/resume|fetchProjectDirectorWorkbenchResume/,
  "Formal page does not directly invoke resume outside the adapter gate",
);

console.log("All P26-H1 no-auto-resume contract tests passed.");
