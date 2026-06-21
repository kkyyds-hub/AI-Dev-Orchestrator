import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const directorSurfaceSource = readFileSync(
  new URL("../src/features/workbench/ProjectDirectorWorkbenchSurface.tsx", import.meta.url),
  "utf8",
);
const hooksSource = readFileSync(
  new URL("../src/features/project-director/hooks.ts", import.meta.url),
  "utf8",
);
const workbenchPageSource = readFileSync(
  new URL("../src/pages/workbench/WorkbenchPage.tsx", import.meta.url),
  "utf8",
);

assert.match(
  hooksSource,
  /useProjectDirectorWorkbenchResume\([\s\S]*options\?: ProjectDirectorConversationQueryOptions/,
  "Project Director resume hook should accept query options",
);
assert.match(
  hooksSource,
  /enabled: options\?\.enabled/,
  "Project Director resume hook should allow callers to disable automatic resume queries",
);
assert.match(
  directorSurfaceSource,
  /enabled: Boolean\(input\.resumeSessionId\)/,
  "Real workbench adapter should only call workbench/resume after an explicit session selection",
);
assert.match(
  directorSurfaceSource,
  /sessionId: input\.resumeSessionId/,
  "Explicit session selection should still be passed to the resume endpoint",
);
assert.match(
  directorSurfaceSource,
  /project_id: input\.mode === "project" \? input\.projectId : null/,
  "New-project prompt payload must not inherit a stale project_id",
);
assert.match(
  workbenchPageSource,
  /navigate\("\/workbench\?mode=new-project"\)/,
  "New project entry should route to the clean new-project mode",
);
assert.doesNotMatch(
  workbenchPageSource,
  /workbench\/resume|fetchProjectDirectorWorkbenchResume/,
  "Formal page should not directly invoke resume outside the adapter gate",
);
