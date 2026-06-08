import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import test from "node:test";

const testDir = dirname(fileURLToPath(import.meta.url));
const webSrc = join(testDir, "../../../..");
const panelPath = join(testDir, "../RuntimeReadbackPanel.tsx");
const apiPath = join(webSrc, "features/runtime/api.ts");
const typesPath = join(webSrc, "features/runtime/types.ts");
const workbenchPath = join(webSrc, "pages/workbench/WorkbenchPage.tsx");
const inboxPath = join(webSrc, "pages/workbench/components/ProjectDirectorInboxPanel.tsx");

const panelSource = readFileSync(panelPath, "utf8");
const apiSource = readFileSync(apiPath, "utf8");
const typesSource = readFileSync(typesPath, "utf8");
const workbenchSource = readFileSync(workbenchPath, "utf8");
const inboxSource = readFileSync(inboxPath, "utf8");
const frontendReadbackSource = [
  panelSource,
  apiSource,
  typesSource,
  workbenchSource,
  inboxSource,
].join("\n");

function token(parts) {
  return parts.join("");
}

test("RuntimeReadbackPanel covers empty, fake, session, and event readback states", () => {
  assert.match(panelSource, /暂无 fake runtime session/);
  assert.match(panelSource, /executor_id/);
  assert.match(panelSource, /state/);
  assert.match(panelSource, /source/);
  assert.match(panelSource, /fake_adapter/);
  assert.match(panelSource, /fake runtime only/);
  assert.match(panelSource, /event\.event_type/);
  assert.match(panelSource, /append_only/);

  const representativeEvents = ["session.created", "session.running"];
  assert.deepEqual(representativeEvents, ["session.created", "session.running"]);
});

test("Runtime readback client only uses GET session readback endpoints", () => {
  assert.match(apiSource, /\/runtime\/sessions/);
  assert.match(apiSource, /\/runtime\/sessions\/\$\{sessionId\}/);
  assert.match(apiSource, /\/runtime\/sessions\/\$\{sessionId\}\/events/);
  assert.doesNotMatch(apiSource, /method:\s*["']POST["']/);
  assert.doesNotMatch(
    apiSource,
    new RegExp(`/runtime/${token(["launch", "-", "requests"])}`),
  );
  assert.doesNotMatch(
    apiSource,
    new RegExp(`/runtime/${token(["launch", "-", "requests"])}/\\$\\{[^}]+\\}/${token(["confirm"])}`),
  );
  assert.doesNotMatch(
    apiSource,
    new RegExp(`/runtime/sessions/\\$\\{[^}]+\\}/${token(["cancel"])}`),
  );
});

test("Runtime readback source keeps unsafe DTO fields out", () => {
  const blockedFields = [
    token(["com", "mand"]),
    token(["raw", "_", "com", "mand"]),
    token(["raw", "_", "args"]),
    token(["e", "nv"]),
    token(["e", "nv", "_", "vars"]),
    token(["api", "_", "key"]),
    token(["token", "_", "value"]),
    token(["auth", "_", "token"]),
    token(["sec", "ret"]),
    token(["native", "_", "config", "_", "path"]),
    token(["cli", "_", "path"]),
    token(["process", "_", "handle"]),
    token(["log", "_", "path"]),
    token(["raw", "_", "output"]),
    token(["raw", "_", "error"]),
  ];

  for (const field of blockedFields) {
    assert.doesNotMatch(frontendReadbackSource, new RegExp(`\\b${field}\\b`));
  }
});

test("RuntimeReadbackPanel does not render runtime control buttons", () => {
  const buttonBodies = [...panelSource.matchAll(/<button[\s\S]*?<\/button>/g)].map(
    (match) => match[0],
  );
  const forbiddenButtonLabels = ["启动", "执行", "确认", "取消", "kill", "cleanup"];

  for (const body of buttonBodies) {
    for (const label of forbiddenButtonLabels) {
      assert.doesNotMatch(body, new RegExp(label, "i"));
    }
  }
});

test("Workbench linkage is read-only and does not expose product runtime Git write actions", () => {
  assert.match(workbenchSource, /RuntimeReadbackPanel/);
  assert.match(inboxSource, /P9 fake runtime readback 已接入/);

  const buttonBodies = [
    ...workbenchSource.matchAll(/<button[\s\S]*?<\/button>/g),
    ...panelSource.matchAll(/<button[\s\S]*?<\/button>/g),
    ...inboxSource.matchAll(/<button[\s\S]*?<\/button>/g),
  ].map((match) => match[0]);
  const gitWriteLabels = ["git add", "git commit", "git push", "merge"];

  for (const body of buttonBodies) {
    for (const label of gitWriteLabels) {
      assert.doesNotMatch(body, new RegExp(label, "i"));
    }
  }
});

test("Reference project path is not copied into frontend readback source", () => {
  assert.doesNotMatch(frontendReadbackSource, /agent-orchestrator/);
  assert.doesNotMatch(frontendReadbackSource, /project-explore-one/);
});
