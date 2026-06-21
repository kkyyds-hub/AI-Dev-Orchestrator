import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const workbenchPageSource = readFileSync(
  new URL("../src/pages/workbench/WorkbenchPage.tsx", import.meta.url),
  "utf8",
);
const labPageSource = readFileSync(
  new URL("../src/features/ui-selection-lab/SanshengLiubuUiLabPage.tsx", import.meta.url),
  "utf8",
);
const mockPagesSource = readFileSync(
  new URL("../src/features/ui-selection-lab/components/WorkbenchMockPages.tsx", import.meta.url),
  "utf8",
);
const realSurfaceAdapterSource = readFileSync(
  new URL("../src/features/workbench/adapters/realWorkbenchSurfaceAdapter.ts", import.meta.url),
  "utf8",
);
const deliverablesHooksSource = readFileSync(
  new URL("../src/features/deliverables/hooks.ts", import.meta.url),
  "utf8",
);
const projectsApiSource = readFileSync(
  new URL("../src/features/projects/api.ts", import.meta.url),
  "utf8",
);
const deliverablesApiSource = readFileSync(
  new URL("../src/features/deliverables/api.ts", import.meta.url),
  "utf8",
);
const approvalsApiSource = readFileSync(
  new URL("../src/features/approvals/api.ts", import.meta.url),
  "utf8",
);
const repositoriesApiSource = readFileSync(
  new URL("../src/features/repositories/api.ts", import.meta.url),
  "utf8",
);
const settingsApiSource = readFileSync(
  new URL("../src/features/settings/api.ts", import.meta.url),
  "utf8",
);
const rolesApiSource = readFileSync(
  new URL("../src/features/roles/api.ts", import.meta.url),
  "utf8",
);
const skillsApiSource = readFileSync(
  new URL("../src/features/skills/api.ts", import.meta.url),
  "utf8",
);
const projectDirectorApiSource = readFileSync(
  new URL("../src/features/project-director/api.ts", import.meta.url),
  "utf8",
);
const routerSource = readFileSync(
  new URL("../src/app/router.tsx", import.meta.url),
  "utf8",
);
const accountModalSource = readFileSync(
  new URL("../src/features/ui-selection-lab/components/AccountSettingsModal.tsx", import.meta.url),
  "utf8",
);

assert.match(
  workbenchPageSource,
  /buildWorkbenchSurfaceData/,
  "Formal workbench should build real surface data instead of only relying on mock page constants",
);
assert.match(
  workbenchPageSource,
  /pageAdapterMode="real"/,
  "Formal workbench should mark page surfaces as real after all promoted formal surfaces are connected",
);
assert.match(
  labPageSource,
  /pageAdapterMode \?\? \(mode === "real" \? "hybrid" : "mock"\)/,
  "Shared lab shell should keep lab mode on mock adapters unless a formal caller overrides it",
);
assert.match(
  mockPagesSource,
  /data-testid="workbench-page-adapter-real"/,
  "Connected formal surfaces should expose a real adapter marker",
);
assert.match(
  mockPagesSource,
  /data-testid="workbench-page-adapter-mock"/,
  "Incomplete surfaces should keep a mock adapter marker",
);
assert.match(
  mockPagesSource,
  /function resolveSurfaceAdapterMode/,
  "Hybrid formal pages should resolve mock/real markers per surface instead of showing both globally",
);
assert.match(
  mockPagesSource,
  /input\.surfaceData\?\.projects \? "real" : "mock"/,
  "Project management should show a real adapter marker when real surface data is present",
);
assert.match(
  mockPagesSource,
  /input\.surfaceData\?\.execution \? "real" : "mock"/,
  "Execution center should show a real adapter marker when real surface data is present",
);
assert.match(
  mockPagesSource,
  /input\.surfaceData\?\.deliverables \? "real" : "mock"/,
  "Deliverables center should show a real adapter marker when real surface data is present",
);
assert.match(
  mockPagesSource,
  /input\.surfaceData\?\.repository \? "real" : "mock"/,
  "Repository page should show a real adapter marker when real surface data is present",
);
assert.match(
  mockPagesSource,
  /input\.surfaceData\?\.governance \? "real" : "mock"/,
  "Governance page should show a real adapter marker when real surface data is present",
);
assert.doesNotMatch(
  mockPagesSource,
  /adapterMode === "hybrid" \? realAdapterMarker[\s\S]*adapterMode === "hybrid" \? mockAdapterMarker/,
  "Hybrid adapter mode should not render both markers for the same surface",
);

for (const endpoint of [
  "/console/project-overview",
  "/projects/${projectId}",
  "/tasks",
  "/tasks/${taskId}",
  "/tasks/${taskId}/runs",
  "/runs/${runId}/logs?limit=20",
  "/deliverables/projects/${projectId}",
  "/approvals/projects/${projectId}",
  "/repositories/projects/${projectId}/snapshot",
  "/repositories/projects/${projectId}/verification-baseline",
  "/repositories/projects/${projectId}/change-session",
  "/roles/projects/${projectId}",
  "/roles/projects/${projectId}/consumption",
  "/skills/projects/${projectId}/bindings",
  "/skills/registry",
  "/projects/${projectId}/memory",
  "/projects/${projectId}/memory/governance",
  "/provider-settings/openai",
  "/provider-settings/openai/test",
  "/repositories/workspace-settings",
  "/account/profile",
  "/project-director/projects/${projectId}/agent-team-config",
  "/project-director/projects/${projectId}/skill-binding-config",
  "/project-director/projects/${projectId}/repository-binding-config",
  "/project-director/projects/${projectId}/verification-config",
  "/project-director/projects/${projectId}/setup-readiness",
]) {
  const escaped = endpoint.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const source =
    workbenchPageSource +
    realSurfaceAdapterSource +
    projectsApiSource +
    deliverablesHooksSource +
    deliverablesApiSource +
    approvalsApiSource +
    repositoriesApiSource +
    rolesApiSource +
    skillsApiSource +
    settingsApiSource +
    projectDirectorApiSource;
  assert.match(source, new RegExp(escaped), `Real surface adapter should reference ${endpoint}`);
}

assert.match(
  realSurfaceAdapterSource,
  /directorConfig: buildDirectorConfigSummary/,
  "Governance surface should map project-director config APIs into the lab governance page",
);
assert.match(
  workbenchPageSource,
  /useProjectMemorySnapshot/,
  "Governance surface should fetch project memory through the real project adapter",
);
assert.match(
  workbenchPageSource,
  /useProjectMemoryGovernanceState/,
  "Governance surface should fetch memory governance state through the real project adapter",
);
assert.match(
  realSurfaceAdapterSource,
  /buildGovernanceMemorySummary/,
  "Governance surface should map project memory into the lab governance page",
);
assert.match(
  realSurfaceAdapterSource,
  /sanitizeUserFacingSummary/,
  "Governance memory summaries should be sanitized before display",
);
assert.match(
  mockPagesSource,
  /项目记忆/,
  "Governance lab page should have a product-facing slot for project memory",
);
assert.match(
  mockPagesSource,
  /rows=\{selectedSkill\.evidence_rows\.map/,
  "Governance skill evidence should be controlled by adapter-provided user-facing rows",
);
assert.doesNotMatch(
  mockPagesSource,
  /\["总用量"[\s\S]*selectedSkill\.total_tokens|\["预估成本"[\s\S]*selectedSkill\.estimated_cost/,
  "Governance skill evidence must not expose token or cost internals in ordinary details",
);
assert.match(
  mockPagesSource,
  /AI 主管配置/,
  "Governance lab page should have a product-facing slot for director configuration",
);

assert.match(
  workbenchPageSource,
  /settingsAdapter=\{settingsAdapter\}/,
  "Formal settings surface should receive a real settings adapter",
);
assert.match(
  workbenchPageSource,
  /testProviderConnection/,
  "Formal settings surface should connect provider test through the adapter",
);
assert.match(
  workbenchPageSource,
  /updateWorkspaceSettings/,
  "Formal settings surface should connect workspace settings through the adapter",
);
assert.match(
  workbenchPageSource,
  /base_url:\s*draft\.providerBaseUrl\.trim\(\)/,
  "Formal settings save should persist provider base URL through the real adapter",
);
assert.match(
  workbenchPageSource,
  /timeout_seconds:[\s\S]*timeoutSeconds/,
  "Formal settings save should persist provider timeout through the real adapter",
);
assert.match(
  workbenchPageSource,
  /model_preset: "custom"/,
  "Formal settings save should persist explicit model names through the real adapter",
);
assert.match(
  workbenchPageSource,
  /economy:\s*draft\.economyModel\.trim\(\)/,
  "Formal settings save should persist the economy model through the real adapter",
);
assert.match(
  workbenchPageSource,
  /premium:\s*draft\.premiumModel\.trim\(\)/,
  "Formal settings save should persist the premium model through the real adapter",
);
assert.match(
  workbenchPageSource,
  /\.\.\.\(draft\.providerApiKey\.trim\(\)[\s\S]*api_key: draft\.providerApiKey\.trim\(\)/,
  "Formal settings save should only send provider API key when the user enters a replacement key",
);
assert.match(
  workbenchPageSource,
  /workspaceSettings: workspaceSettingsQuery\.data \?\? null/,
  "Formal repository surface should pass workspace settings into the real surface adapter",
);
assert.match(
  realSurfaceAdapterSource,
  /title: "工作区范围"/,
  "Repository surface should render backend workspace settings in the lab repository page",
);
assert.match(
  workbenchPageSource,
  /useProjectRepositoryVerificationBaseline/,
  "Repository surface should fetch verification baseline through the real repository adapter",
);
assert.match(
  realSurfaceAdapterSource,
  /title: "验证基线"/,
  "Repository surface should render backend verification baseline in the lab repository page",
);
assert.match(
  repositoriesApiSource,
  /requestNullableJson<RepositorySnapshot>/,
  "Repository snapshot 404 should be modeled as an empty repository preparation state",
);
assert.match(
  repositoriesApiSource,
  /requestNullableJson<RepositoryVerificationBaseline>/,
  "Repository verification baseline 404 should be modeled as an empty repository preparation state",
);
assert.match(
  realSurfaceAdapterSource,
  /\?\s*"pending_binding"/,
  "Unbound project repositories should use a pending-binding state instead of the generic error state",
);
assert.match(
  mockPagesSource,
  /viewState === "empty" \|\| viewState === "pending_binding"[\s\S]*repositoryBindingPanel/,
  "Repository empty and pending-binding states should keep the binding panel available",
);
assert.match(
  realSurfaceAdapterSource,
  /formatVerificationCategories/,
  "Repository verification baseline should be mapped into product-facing category labels",
);
assert.doesNotMatch(
  realSurfaceAdapterSource,
  /template\.command|working_directory|timeout_seconds/,
  "Repository verification baseline should not expose raw command details in the ordinary repository surface",
);
assert.doesNotMatch(
  mockPagesSource,
  /onTaskFeedback\?\.\("[^"]*(?:apply-local|git commit|git push|提交|推送)/,
  "Repository page should not expose git write/apply/commit actions as default main UI actions",
);
assert.match(
  workbenchPageSource,
  /fetchWorkbenchTask/,
  "Execution center should fetch selected task detail through /tasks/{taskId}",
);
assert.match(
  realSurfaceAdapterSource,
  /selectedTask: WorkbenchTask \| null/,
  "Execution center should map selected task detail into the lab execution surface",
);
assert.match(
  workbenchPageSource,
  /fetchWorkbenchRunLogs/,
  "Execution center should fetch latest real run logs through the surface adapter",
);
assert.match(
  realSurfaceAdapterSource,
  /sanitizeRunLogMessage/,
  "Run logs must be sanitized before they are mapped into the user-facing execution detail",
);
assert.match(
  mockPagesSource,
  /\["context", "process", "decision", "safety", "run"\]/,
  "Execution detail should expose the sanitized process tab in the lab surface order",
);
assert.match(
  routerSource,
  /path: "me"[\s\S]*initialModal="account"/,
  "/me should open the shared lab account surface, not a legacy account page",
);
assert.match(
  accountModalSource,
  /data-testid=\{\s*adapter\?\.mode === "real"[\s\S]*workbench-account-adapter-real/,
  "Account surface should expose a real adapter marker when the formal backend profile is connected",
);
assert.match(
  workbenchPageSource,
  /accountAdapter=\{accountAdapter\}/,
  "Formal workbench should pass the real account adapter into the shared lab shell",
);
assert.match(
  settingsApiSource,
  /fetchAccountProfile\(\): Promise<AccountProfile>[\s\S]*requestJson\("\/account\/profile"\)/,
  "Formal account surface should fetch the backend account profile through /account/profile",
);
assert.match(
  settingsApiSource,
  /updateAccountProfile[\s\S]*requestJson\("\/account\/profile"[\s\S]*method: "PUT"/,
  "Formal account surface should save editable account fields through /account/profile",
);

assert.doesNotMatch(
  realSurfaceAdapterSource,
  /\/deliverables\?project_id=/,
  "Deliverables center should use the project-scoped deliverables API, not the generic list API",
);

for (const forbidden of ["Run ID", "运行 ID", "provider receipt", "日志路径", "worker 调试", "token"]) {
  assert.doesNotMatch(
    realSurfaceAdapterSource,
    new RegExp(`\\["[^"]*${forbidden}[^"]*"`, "i"),
    `Real surface adapter should not expose ${forbidden} as an ordinary UI row label`,
  );
}

for (const forbiddenInternalField of ["storage_path", "latest_run_id"]) {
  assert.doesNotMatch(
    realSurfaceAdapterSource,
    new RegExp(`\\[\\s*["'][^"']*${forbiddenInternalField}[^"']*["']`, "i"),
    `Governance memory adapter should not expose ${forbiddenInternalField} as a UI row`,
  );
}
