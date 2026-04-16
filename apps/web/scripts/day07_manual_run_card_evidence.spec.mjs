import fs from "node:fs/promises";

import { expect, test } from "@playwright/test";

const appOrigin = "http://127.0.0.1:5173";
const evidenceDir =
  "E:/new-AI-Dev-Orchestrator-push/runtime/orchestrator/tmp/day07-browser-evidence";

test.use({
  browserName: "chromium",
  channel: "msedge",
  viewport: { width: 1720, height: 1400 },
});

async function captureViewportScreenshot(page, path) {
  await page.screenshot({
    path,
    animations: "disabled",
  });
}

async function captureLocatorScreenshot(locator, path) {
  await locator.waitFor({ state: "visible", timeout: 20000 });
  await locator.scrollIntoViewIfNeeded();
  await locator.screenshot({
    path,
    animations: "disabled",
  });
}

async function requestJson(request, method, path, data) {
  const response = await request.fetch(`${appOrigin}${path}`, {
    method,
    data,
  });
  if (!response.ok()) {
    throw new Error(
      `${method} ${path} failed: ${response.status()} ${response.statusText()}`,
    );
  }
  return response.json();
}

function buildBudgetFallbackRules(rules) {
  const nextRules = JSON.parse(JSON.stringify(rules ?? {}));
  const rolePreferences = { ...(nextRules.role_model_tier_preferences ?? {}) };
  delete rolePreferences.architect;
  nextRules.role_model_tier_preferences = rolePreferences;

  const stageOverrides = { ...(nextRules.stage_model_tier_overrides ?? {}) };
  for (const stage of Object.keys(stageOverrides)) {
    const stageOverride = stageOverrides[stage];
    if (!stageOverride || typeof stageOverride !== "object") {
      continue;
    }
    const cleaned = { ...stageOverride };
    delete cleaned.architect;
    stageOverrides[stage] = cleaned;
  }
  nextRules.stage_model_tier_overrides = stageOverrides;
  return nextRules;
}

async function createBudgetFallbackFixture(request) {
  const fixtureSuffix = Date.now();
  const project = await requestJson(request, "POST", "/projects", {
    name: `Day07 Budget Fallback Browser Fixture ${fixtureSuffix}`,
    summary:
      "Capture Day07 homepage manual worker run evidence under budget_fallback policy source.",
    stage: "execution",
  });

  const taskTitle = `Day07 budget fallback task ${fixtureSuffix}`;
  const task = await requestJson(request, "POST", "/tasks", {
    project_id: project.id,
    title: taskTitle,
    input_summary:
      "Route architect-owned execution work with no explicit role preference to trigger budget_fallback.",
    priority: "high",
    risk_level: "normal",
    owner_role_code: "architect",
    acceptance_criteria: [
      "Role policy runtime source is visible",
      "Manual run card evidence is recordable",
    ],
  });

  const preview = await requestJson(
    request,
    "GET",
    `/strategy/projects/${project.id}/preview`,
  );
  if (
    preview.selected_task_id !== task.id
    || preview.role_model_policy_runtime?.source !== "budget_fallback"
  ) {
    throw new Error(
      "Budget-fallback fixture preview did not select the expected task/source.",
    );
  }

  return {
    projectId: project.id,
    taskId: task.id,
    taskTitle,
  };
}

async function createScopedManualRunFixture(request) {
  const fixtureSuffix = Date.now();
  const project = await requestJson(request, "POST", "/projects", {
    name: `Day07 Manual Run Browser Fixture ${fixtureSuffix}`,
    summary: "Capture Day07 homepage manual worker run evidence.",
    stage: "planning",
  });
  const taskTitle = `Day07 manual run task ${fixtureSuffix}`;
  const task = await requestJson(request, "POST", "/tasks", {
    project_id: project.id,
    title: taskTitle,
    input_summary: "Prepare planning outline and acceptance criteria for Day07 evidence.",
    priority: "high",
    risk_level: "normal",
    owner_role_code: "product_manager",
    acceptance_criteria: [
      "Manual run card fields are visible",
      "Latest task row contract is visible",
    ],
  });
  return {
    projectId: project.id,
    taskId: task.id,
    taskTitle,
  };
}

async function createNoRoutableFixture(request) {
  const fixtureSuffix = Date.now();
  const project = await requestJson(request, "POST", "/projects", {
    name: `Day07 No-Routable Browser Fixture ${fixtureSuffix}`,
    summary:
      "Capture Day07 homepage no-routable manual worker run evidence.",
    stage: "execution",
  });

  const prerequisiteTask = await requestJson(request, "POST", "/tasks", {
    project_id: project.id,
    title: `Day07 no-routable prerequisite ${fixtureSuffix}`,
    input_summary:
      "This prerequisite task stays paused so downstream task remains blocked for routing.",
    priority: "high",
    risk_level: "normal",
    owner_role_code: "engineer",
    acceptance_criteria: [
      "Prerequisite remains paused",
      "Dependent task is blocked in readiness",
    ],
  });
  await requestJson(request, "POST", `/tasks/${prerequisiteTask.id}/pause`, {
    reason: "Day07 no-routable browser evidence fixture",
  });

  const taskTitle = `Day07 no-routable task ${fixtureSuffix}`;
  const task = await requestJson(request, "POST", "/tasks", {
    project_id: project.id,
    title: taskTitle,
    input_summary:
      "Keep this task non-routable by depending on a paused prerequisite task.",
    priority: "high",
    risk_level: "normal",
    owner_role_code: "engineer",
    depends_on_task_ids: [prerequisiteTask.id],
    acceptance_criteria: [
      "Manual run card reports no-routable message",
      "Task row remains no-run after click",
    ],
  });

  const preview = await requestJson(
    request,
    "GET",
    `/strategy/projects/${project.id}/preview`,
  );
  if (
    preview.selected_task_id !== null
    || typeof preview.message !== "string"
    || !preview.message.includes("none are currently routable")
  ) {
    throw new Error(
      "No-routable fixture preview did not return expected no-routable signal.",
    );
  }

  return {
    projectId: project.id,
    taskId: task.id,
    taskTitle,
  };
}

test("capture manual worker run card interaction evidence", async ({
  browser,
  request,
}) => {
  test.setTimeout(180000);
  await fs.mkdir(evidenceDir, { recursive: true });
  const fixture = await createScopedManualRunFixture(request);
  const context = await browser.newContext({
    viewport: { width: 1720, height: 1400 },
    recordVideo: {
      dir: evidenceDir,
      size: { width: 1720, height: 1400 },
    },
  });
  const page = await context.newPage();
  const pageVideo = page.video();

  await page.route("**/workers/run-once", async (route) => {
    const scopedUrl = new URL(route.request().url());
    scopedUrl.searchParams.set("project_id", fixture.projectId);
    await route.continue({ url: scopedUrl.toString() });
  });

  await page.goto(`${appOrigin}/`, { waitUntil: "domcontentloaded" });

  const runButton = page.getByRole("button", { name: "执行 Worker 一次" });
  await runButton.waitFor({ state: "visible", timeout: 20000 });

  const headerSection = page.getByTestId("home-header-section");
  await captureLocatorScreenshot(
    headerSection,
    `${evidenceDir}/04-home-manual-run-before-trigger.png`,
  );

  await runButton.click();
  await page.waitForTimeout(250);
  await captureViewportScreenshot(
    page,
    `${evidenceDir}/07-home-manual-run-transition-frame.png`,
  );

  const resultHeading = page.getByRole("heading", { name: "最近一次手动执行" });
  await resultHeading.waitFor({ state: "visible", timeout: 30000 });
  const resultSection = page.locator("section").filter({ has: resultHeading }).first();
  await expect(resultSection.getByText("Run ID")).toBeVisible();
  await expect(resultSection.getByText(fixture.taskTitle).first()).toBeVisible();
  await expect(resultSection.getByText("创建时间")).toBeVisible();
  await expect(resultSection.getByText("结束时间")).toBeVisible();
  await expect(resultSection.getByText("Provider / Prompt / Token")).toBeVisible();
  await expect(resultSection.getByText("Role Model Policy Runtime")).toBeVisible();
  await captureLocatorScreenshot(
    resultSection,
    `${evidenceDir}/08-home-manual-run-visible-frame.png`,
  );

  await page.waitForTimeout(1200);
  await captureLocatorScreenshot(
    resultSection,
    `${evidenceDir}/05-home-manual-run-result-card-after-trigger.png`,
  );
  await captureLocatorScreenshot(
    resultSection,
    `${evidenceDir}/06-home-manual-run-result-card-focus.png`,
  );
  await captureViewportScreenshot(
    page,
    `${evidenceDir}/09-home-manual-run-stable-frame.png`,
  );

  await page.reload({ waitUntil: "domcontentloaded" });
  const taskListSection = page
    .locator("section")
    .filter({ has: page.getByRole("heading", { name: "任务列表" }) })
    .first();
  const latestRunRow = taskListSection
    .locator("tbody tr")
    .filter({ hasText: fixture.taskTitle })
    .first();
  await expect(latestRunRow).toBeVisible({ timeout: 30000 });
  await expect(latestRunRow).toContainText("provider：");
  await expect(latestRunRow).toContainText("prompt：");
  await expect(latestRunRow).toContainText("accounting：");
  await expect(latestRunRow).toContainText("role policy：");
  await latestRunRow.screenshot({
    path: `${evidenceDir}/11-home-task-table-latest-run-contract.png`,
  });

  await context.close();
  if (pageVideo) {
    const rawVideoPath = await pageVideo.path();
    await fs.copyFile(rawVideoPath, `${evidenceDir}/10-home-manual-run-click-flow.webm`);
    await fs.unlink(rawVideoPath).catch(() => undefined);
  }
});

test("capture budget_fallback manual run evidence on homepage", async ({
  browser,
  request,
}) => {
  test.setTimeout(150000);
  await fs.mkdir(evidenceDir, { recursive: true });

  const strategyRulesSnapshot = await requestJson(request, "GET", "/strategy/rules");
  const originalRules = strategyRulesSnapshot.rules ?? {};
  const budgetFallbackRules = buildBudgetFallbackRules(originalRules);
  await requestJson(request, "PUT", "/strategy/rules", {
    rules: budgetFallbackRules,
  });

  let fixture;
  try {
    fixture = await createBudgetFallbackFixture(request);
    const context = await browser.newContext({
      viewport: { width: 1720, height: 1400 },
      recordVideo: {
        dir: evidenceDir,
        size: { width: 1720, height: 1400 },
      },
    });
    const page = await context.newPage();
    const pageVideo = page.video();

    await page.route("**/workers/run-once", async (route) => {
      const scopedUrl = new URL(route.request().url());
      scopedUrl.searchParams.set("project_id", fixture.projectId);
      await route.continue({ url: scopedUrl.toString() });
    });

    await page.goto(`${appOrigin}/`, { waitUntil: "domcontentloaded" });
    const runButton = page.getByRole("button", { name: "执行 Worker 一次" });
    await runButton.waitFor({ state: "visible", timeout: 20000 });

    const headerSection = page.getByTestId("home-header-section");
    await captureLocatorScreenshot(
      headerSection,
      `${evidenceDir}/12-home-budget-fallback-before-trigger.png`,
    );

    await runButton.click();
    await page.waitForTimeout(250);
    await captureViewportScreenshot(
      page,
      `${evidenceDir}/13-home-budget-fallback-transition-frame.png`,
    );

    const resultHeading = page.getByRole("heading", { name: "最近一次手动执行" });
    await resultHeading.waitFor({ state: "visible", timeout: 30000 });
    const resultSection = page.locator("section").filter({ has: resultHeading }).first();
    await expect(resultSection.getByText("Run ID")).toBeVisible();
    await expect(resultSection.getByText(fixture.taskTitle).first()).toBeVisible();
    await expect(resultSection.getByText("Role Model Policy Runtime")).toBeVisible();
    await expect(resultSection.getByText("budget_fallback").first()).toBeVisible();
    await captureLocatorScreenshot(
      resultSection,
      `${evidenceDir}/14-home-budget-fallback-visible-frame.png`,
    );

    // The manual-run result card is mutation-scoped; capture post-trigger evidence before reload.
    await page.waitForTimeout(1200);
    await captureLocatorScreenshot(
      resultSection,
      `${evidenceDir}/15-home-budget-fallback-result-card-after-trigger.png`,
    );
    await captureViewportScreenshot(
      page,
      `${evidenceDir}/16-home-budget-fallback-stable-frame.png`,
    );

    await page.reload({ waitUntil: "domcontentloaded" });
    const taskListSection = page
      .locator("section")
      .filter({ has: page.getByRole("heading", { name: "任务列表" }) })
      .first();
    const latestRunRow = taskListSection
      .locator("tbody tr")
      .filter({ hasText: fixture.taskTitle })
      .first();
    await expect(latestRunRow).toBeVisible({ timeout: 30000 });
    await expect(latestRunRow).toContainText("role policy：");
    await expect(latestRunRow).toContainText("budget_fallback");
    await latestRunRow.screenshot({
      path: `${evidenceDir}/17-home-budget-fallback-task-row-contract.png`,
    });

    await context.close();
    if (pageVideo) {
      const rawVideoPath = await pageVideo.path();
      await fs.copyFile(rawVideoPath, `${evidenceDir}/18-home-budget-fallback-click-flow.webm`);
      await fs.unlink(rawVideoPath).catch(() => undefined);
    }
  } finally {
    await requestJson(request, "PUT", "/strategy/rules", {
      rules: originalRules,
    });
  }
});

test("capture no-routable manual run evidence on homepage", async ({
  browser,
  request,
}) => {
  test.setTimeout(150000);
  await fs.mkdir(evidenceDir, { recursive: true });
  const fixture = await createNoRoutableFixture(request);
  const context = await browser.newContext({
    viewport: { width: 1720, height: 1400 },
    recordVideo: {
      dir: evidenceDir,
      size: { width: 1720, height: 1400 },
    },
  });
  const page = await context.newPage();
  const pageVideo = page.video();

  await page.route("**/workers/run-once", async (route) => {
    const scopedUrl = new URL(route.request().url());
    scopedUrl.searchParams.set("project_id", fixture.projectId);
    await route.continue({ url: scopedUrl.toString() });
  });

  await page.goto(`${appOrigin}/`, { waitUntil: "domcontentloaded" });
  const runButton = page.getByRole("button", { name: "执行 Worker 一次" });
  await runButton.waitFor({ state: "visible", timeout: 20000 });

  const headerSection = page.getByTestId("home-header-section");
  await captureLocatorScreenshot(
    headerSection,
    `${evidenceDir}/19-home-no-routable-before-trigger.png`,
  );

  await runButton.click();
  await page.waitForTimeout(250);
  await captureViewportScreenshot(
    page,
    `${evidenceDir}/20-home-no-routable-transition-frame.png`,
  );

  const resultHeading = page.getByRole("heading", { name: "最近一次手动执行" });
  await resultHeading.waitFor({ state: "visible", timeout: 30000 });
  const resultSection = page.locator("section").filter({ has: resultHeading }).first();
  await expect(resultSection).toContainText("none are currently routable");
  await expect(resultSection.getByText("未领取任务")).toBeVisible();
  await captureLocatorScreenshot(
    resultSection,
    `${evidenceDir}/21-home-no-routable-visible-frame.png`,
  );

  await page.waitForTimeout(1200);
  await captureLocatorScreenshot(
    resultSection,
    `${evidenceDir}/22-home-no-routable-result-card-after-trigger.png`,
  );
  await captureViewportScreenshot(
    page,
    `${evidenceDir}/23-home-no-routable-stable-frame.png`,
  );

  await page.reload({ waitUntil: "domcontentloaded" });
  const taskListSection = page
    .locator("section")
    .filter({ has: page.getByRole("heading", { name: "任务列表" }) })
    .first();
  const noRoutableRow = taskListSection
    .locator("tbody tr")
    .filter({ hasText: fixture.taskTitle })
    .first();
  await expect(noRoutableRow).toBeVisible({ timeout: 30000 });
  await expect(noRoutableRow).toContainText("尚未运行");
  await noRoutableRow.screenshot({
    path: `${evidenceDir}/24-home-no-routable-task-row-no-run.png`,
  });

  await context.close();
  if (pageVideo) {
    const rawVideoPath = await pageVideo.path();
    await fs.copyFile(rawVideoPath, `${evidenceDir}/25-home-no-routable-click-flow.webm`);
    await fs.unlink(rawVideoPath).catch(() => undefined);
  }
});
