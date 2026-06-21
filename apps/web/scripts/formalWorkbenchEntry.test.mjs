import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const workbenchPageSource = readFileSync(
  new URL("../src/pages/workbench/WorkbenchPage.tsx", import.meta.url),
  "utf8",
);
const workbenchExperienceSource = readFileSync(
  new URL("../src/features/ui-selection-lab/SanshengLiubuUiLabPage.tsx", import.meta.url),
  "utf8",
);
const formalWorkbenchFeatureSource = readFileSync(
  new URL("../src/features/workbench/WorkbenchExperience.tsx", import.meta.url),
  "utf8",
);
const realAdapterSource = readFileSync(
  new URL("../src/features/workbench/adapters/realWorkbenchAdapter.ts", import.meta.url),
  "utf8",
);
const directorAdapterSurfaceSource = readFileSync(
  new URL("../src/features/workbench/ProjectDirectorWorkbenchSurface.tsx", import.meta.url),
  "utf8",
);
const mockAdapterSource = readFileSync(
  new URL("../src/features/workbench/adapters/mockWorkbenchAdapter.ts", import.meta.url),
  "utf8",
);
const mockPageContentSource = readFileSync(
  new URL("../src/features/ui-selection-lab/components/WorkbenchMockPages.tsx", import.meta.url),
  "utf8",
);
const appShellSource = readFileSync(
  new URL("../src/app/AppShell.tsx", import.meta.url),
  "utf8",
);
const routerSource = readFileSync(
  new URL("../src/app/router.tsx", import.meta.url),
  "utf8",
);

assert.match(
  workbenchPageSource,
  /<WorkbenchExperience/,
  "Formal /workbench should render the shared full workbench shell",
);
assert.match(
  formalWorkbenchFeatureSource,
  /WorkbenchPreview as WorkbenchExperience/,
  "Formal workbench feature should expose the shared experiment workbench component",
);
assert.match(
  appShellSource,
  /<Outlet \/>/,
  "Formal routes should not wrap the lab workbench in a second app shell",
);
assert.doesNotMatch(
  appShellSource,
  /Sidebar|Topbar|CommandMenu|MinimalCapabilitySurface/,
  "Formal AppShell should not render the deleted formal navigation shell",
);

for (const [route, surface] of [
  ['path: "projects"', 'initialMainPage="projects"'],
  ['path: "projects/:projectId/repository"', 'initialMainPage="repository"'],
  ['path: "tasks"', 'initialMainPage="execution"'],
  ['path: "runs"', 'initialMainPage="execution"'],
  ['path: "execution"', 'initialMainPage="execution"'],
  ['path: "delivery"', 'initialMainPage="deliverables"'],
  ['path: "deliverables"', 'initialMainPage="deliverables"'],
  ['path: "approvals"', 'initialMainPage="deliverables"'],
  ['path: "governance"', 'initialMainPage="governance"'],
  ['path: "settings"', 'initialModal="settings"'],
  ['path: "me"', 'initialModal="account"'],
]) {
  assert.match(
    routerSource,
    new RegExp(`${route.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}[\\s\\S]*${surface.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`),
    `Formal route ${route} should be collected into the shared lab workbench surface`,
  );
}

assert.doesNotMatch(
  routerSource,
  /ProjectsPage|TasksPage|RunsPage|ExecutionCenterPage|DeliveryCenterPage|DeliverablesPage|ApprovalsPage|GovernancePage|MePage|SettingsPage|MinimalCapabilitySurface/,
  "Formal router should not import or render old formal pages",
);

for (const anchor of [
  'data-testid={mode === "real" ? "workbench-main-shell" : "ui-lab-workbench-preview"}',
  'data-testid="ui-lab-sidebar"',
  "新建项目会话",
  "项目管理",
  "执行中心",
  "成果中心",
  "仓库",
  "治理",
  "<WorkbenchPromptBox",
]) {
  assert.match(
    workbenchExperienceSource,
    new RegExp(anchor.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")),
    `Shared workbench shell should keep ${anchor}`,
  );
}

assert.match(
  workbenchPageSource,
  /renderTopActionSlot=\{\(context\) => \(/,
  "Formal workbench should inject the real top action inbox into the shared shell",
);
assert.match(
  workbenchPageSource,
  /<WorkbenchActionInbox projectId=\{resolveProjectId\(context\)\}/,
  "Formal workbench top action inbox should use the real project-director inbox hook component",
);
assert.match(
  workbenchPageSource,
  /renderDirectorSurface=\{\(context\) =>/,
  "Formal workbench should inject the real AI director adapter into the shared shell",
);
assert.match(
  workbenchPageSource,
  /<ProjectDirectorWorkbenchSurface/,
  "Formal workbench should use the experiment-native project-director adapter surface",
);
assert.match(
  workbenchPageSource,
  /suppressPromptBox/,
  "Formal workbench should suppress the shell mock PromptBox when the real director surface owns input",
);
assert.doesNotMatch(
  workbenchPageSource,
  /DirectorChatEntry/,
  "Formal workbench should not import or render the old DirectorChatEntry",
);
assert.match(
  directorAdapterSurfaceSource,
  /<ConversationMessages/,
  "Real project-director adapter should drive the experiment conversation renderer",
);
assert.match(
  directorAdapterSurfaceSource,
  /data-testid="workbench-director-welcome"/,
  "Real project-director adapter should preserve the experiment welcome empty state",
);
assert.match(
  directorAdapterSurfaceSource,
  /欢迎[\s\S]*我们来构建什么？/,
  "Formal workbench should keep the experiment welcome copy before a session starts",
);
assert.match(
  directorAdapterSurfaceSource,
  /const promptBox = <WorkbenchPromptBox onSend=\{adapter\.handlePromptSend\} \/>;/,
  "Real project-director adapter should send through the experiment PromptBox",
);
assert.equal(
  (directorAdapterSurfaceSource.match(/<WorkbenchPromptBox /g) ?? []).length,
  1,
  "Real project-director adapter should render exactly one experiment PromptBox",
);
assert.doesNotMatch(
  workbenchPageSource,
  /<WorkbenchPromptBox/,
  "Formal workbench page should not render a second PromptBox",
);
assert.match(
  directorAdapterSurfaceSource,
  /<WorkbenchPlanFlowCard/,
  "Real project-director adapter should render plan versions through the experiment plan card",
);
assert.match(
  directorAdapterSurfaceSource,
  /useCreateProjectDirectorSession|usePostProjectDirectorSessionMessage|useProjectDirectorSessionMessages/,
  "Real project-director adapter should use the existing project-director API hooks",
);
assert.match(
  workbenchPageSource,
  /renderRepositoryBindingPanel=\{\(context\) => \(/,
  "Formal workbench should inject the real repository binding panel into the shared repository page",
);
assert.match(
  workbenchPageSource,
  /<WorkbenchRepositoryBindingPanel/,
  "Formal workbench should reuse the repository binding API panel",
);

assert.match(
  realAdapterSource,
  /ProjectDirectorWorkbenchResumableSession/,
  "Real adapter should align sidebar conversations with project-director sessions",
);
assert.match(
  realAdapterSource,
  /BossProjectItem/,
  "Real adapter should align sidebar projects with existing project overview data",
);
assert.match(
  mockAdapterSource,
  /getMockWorkbenchProjectGroups/,
  "Mock adapter should remain available for the hidden lab preview",
);
assert.match(
  mockPageContentSource,
  /adapterMode\?: WorkbenchPageAdapterMode/,
  "Main pages should declare explicit mock/real/hybrid adapter mode",
);
assert.match(
  mockPageContentSource,
  /data-testid="workbench-page-adapter-mock"/,
  "Mock main pages should expose a stable mock-adapter marker",
);
assert.match(
  mockPageContentSource,
  /data-testid="workbench-page-adapter-real"/,
  "Real main pages should expose a stable real-adapter marker",
);

assert.doesNotMatch(
  workbenchPageSource,
  /WorkbenchP0ControlSurface|formal-workbench-main|formal-workbench-p0-control-surface/,
  "Formal /workbench should not keep the old two-column P0 shell",
);
assert.doesNotMatch(
  workbenchPageSource + workbenchExperienceSource,
  /联调 contract 顺序/,
  "Ordinary users should not see backend contract sequence copy in the workbench",
);
