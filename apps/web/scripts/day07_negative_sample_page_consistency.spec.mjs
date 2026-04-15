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

function normalizeValue(value) {
  return value.replace(/\s+/g, " ").trim();
}

async function readInfoItemValue(container, label) {
  const valueLocator = container
    .locator(
      `xpath=.//div[contains(@class,'rounded-xl')][div[1][normalize-space()='${label}']]/div[2]`,
    )
    .first();
  await expect(valueLocator, `Missing field "${label}"`).toBeVisible();
  return normalizeValue(await valueLocator.innerText());
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

async function createNoRunFixture(request) {
  const fixtureSuffix = Date.now();
  const project = await requestJson(request, "POST", "/projects", {
    name: `Day07 No-Run Page Fixture ${fixtureSuffix}`,
    summary: "Negative sample for no_run page-level closure evidence.",
    stage: "execution",
  });
  const task = await requestJson(request, "POST", "/tasks", {
    project_id: project.id,
    title: `Day07 no-run task ${fixtureSuffix}`,
    input_summary: "Create task without any run to keep latest_run empty.",
    priority: "high",
    risk_level: "normal",
    owner_role_code: "engineer",
    acceptance_criteria: [
      "Homepage row keeps no-run state.",
      "Project detail and task detail keep no-run context.",
    ],
  });

  return {
    projectId: project.id,
    projectName: project.name,
    taskId: task.id,
    taskTitle: task.title,
  };
}

async function createNoRoutableFixture(request) {
  const fixtureSuffix = Date.now();
  const project = await requestJson(request, "POST", "/projects", {
    name: `Day07 No-Routable Page Fixture ${fixtureSuffix}`,
    summary: "Negative sample for no_routable page-level closure evidence.",
    stage: "execution",
  });

  const prerequisiteTask = await requestJson(request, "POST", "/tasks", {
    project_id: project.id,
    title: `Day07 no-routable prerequisite ${fixtureSuffix}`,
    input_summary: "Paused prerequisite keeps dependent task non-routable.",
    priority: "high",
    risk_level: "normal",
    owner_role_code: "engineer",
    acceptance_criteria: [
      "Prerequisite remains paused.",
      "Dependent task is blocked for routing.",
    ],
  });
  await requestJson(request, "POST", `/tasks/${prerequisiteTask.id}/pause`, {
    reason: "Day07 no-routable page consistency fixture",
  });

  const task = await requestJson(request, "POST", "/tasks", {
    project_id: project.id,
    title: `Day07 no-routable task ${fixtureSuffix}`,
    input_summary: "Blocked by paused prerequisite so worker cannot claim.",
    priority: "high",
    risk_level: "normal",
    owner_role_code: "engineer",
    depends_on_task_ids: [prerequisiteTask.id],
    acceptance_criteria: [
      "Manual worker run returns no-routable.",
      "Task row remains no-run.",
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
    projectName: project.name,
    taskId: task.id,
    taskTitle: task.title,
  };
}

async function createBudgetFallbackFixture(request) {
  const fixtureSuffix = Date.now();
  const project = await requestJson(request, "POST", "/projects", {
    name: `Day07 Degraded Budget-Fallback Fixture ${fixtureSuffix}`,
    summary: "Negative degraded sample for budget_fallback page-level closure.",
    stage: "execution",
  });

  const task = await requestJson(request, "POST", "/tasks", {
    project_id: project.id,
    title: `Day07 degraded budget_fallback task ${fixtureSuffix}`,
    input_summary:
      "Route architect execution with no explicit preference to trigger budget_fallback.",
    priority: "high",
    risk_level: "normal",
    owner_role_code: "architect",
    acceptance_criteria: [
      "Role policy runtime source is budget_fallback.",
      "Run context remains consistent from homepage to run-log.",
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
      "Budget-fallback fixture preview did not select expected task/source.",
    );
  }

  return {
    projectId: project.id,
    projectName: project.name,
    taskId: task.id,
    taskTitle: task.title,
  };
}

async function gotoHome(page) {
  await page.goto(`${appOrigin}/`, { waitUntil: "domcontentloaded" });
  await page.reload({ waitUntil: "domcontentloaded" });
}

async function locateTaskListTable(page) {
  const taskListTable = page
    .locator("table")
    .filter({
      has: page.getByRole("columnheader", { name: "Estimated Cost" }),
    })
    .first();
  await expect(taskListTable).toBeVisible({ timeout: 30000 });
  return taskListTable;
}

async function locateTaskRow(page, taskTitle) {
  const taskListTable = await locateTaskListTable(page);
  const row = taskListTable
    .locator("tbody tr")
    .filter({ hasText: taskTitle })
    .first();
  await expect(row).toBeVisible({ timeout: 30000 });
  return row;
}

async function selectProjectDetail(page, projectName) {
  const projectTable = page
    .locator("section")
    .filter({
      has: page.getByRole("heading", { name: "项目总览列表" }),
    })
    .first();
  await expect(projectTable).toBeVisible({ timeout: 30000 });
  const projectRow = projectTable
    .locator("tbody tr")
    .filter({ hasText: projectName })
    .first();
  await expect(projectRow).toBeVisible({ timeout: 30000 });
  await projectRow.getByRole("button").last().click();

  const projectDetailPanel = page.getByTestId("project-detail-panel");
  await expect(projectDetailPanel).toContainText(projectName, { timeout: 30000 });
  return projectDetailPanel;
}

async function openTaskDetailFromHome(page, taskTitle) {
  const row = await locateTaskRow(page, taskTitle);
  await row.locator("td").first().getByRole("button").click();
  const taskDetailPanel = page.locator("#task-detail-panel");
  await expect(taskDetailPanel).toBeVisible({ timeout: 30000 });
  return taskDetailPanel;
}

async function runOnceViaHome(page, projectId) {
  await page.unroute("**/workers/run-once").catch(() => undefined);
  await page.route("**/workers/run-once", async (route) => {
    const scopedUrl = new URL(route.request().url());
    scopedUrl.searchParams.set("project_id", projectId);
    await route.continue({ url: scopedUrl.toString() });
  });

  const runButton = page.getByRole("button", { name: /Worker 一次/ }).first();
  await runButton.waitFor({ state: "visible", timeout: 20000 });
  const runResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/workers/run-once")
      && response.request().method() === "POST",
  );
  await runButton.click();
  const runResponse = await runResponsePromise;
  const payload = await runResponse.json();
  return payload;
}

test("day07 negative sample page-level closure (no_run / no_routable / degraded budget_fallback)", async ({
  browser,
  request,
}) => {
  test.setTimeout(360000);
  await fs.mkdir(evidenceDir, { recursive: true });

  const noRunFixture = await createNoRunFixture(request);
  const noRoutableFixture = await createNoRoutableFixture(request);

  const strategyRulesSnapshot = await requestJson(request, "GET", "/strategy/rules");
  const originalRules = strategyRulesSnapshot.rules ?? {};
  const budgetFallbackRules = buildBudgetFallbackRules(originalRules);
  await requestJson(request, "PUT", "/strategy/rules", { rules: budgetFallbackRules });

  let budgetFixture = null;
  try {
    budgetFixture = await createBudgetFallbackFixture(request);

    const context = await browser.newContext({
      viewport: { width: 1720, height: 1400 },
    });
    const page = await context.newPage();

    // no_run chain: homepage -> project detail -> task detail -> run log
    await gotoHome(page);
    const noRunRow = await locateTaskRow(page, noRunFixture.taskTitle);
    await expect(noRunRow).toContainText("尚未运行");
    await noRunRow.screenshot({
      path: `${evidenceDir}/32-home-no-run-task-row.png`,
    });

    const noRunProjectDetail = await selectProjectDetail(page, noRunFixture.projectName);
    const noRunPreviewSection = noRunProjectDetail
      .locator("section")
      .filter({ hasText: "最近任务预览" })
      .first();
    await expect(noRunPreviewSection).toContainText(noRunFixture.taskTitle);
    await expect(noRunPreviewSection).toContainText("尚无运行");
    await noRunPreviewSection.screenshot({
      path: `${evidenceDir}/33-project-detail-no-run-preview.png`,
    });

    const noRunTaskDetail = await openTaskDetailFromHome(page, noRunFixture.taskTitle);
    await expect(noRunTaskDetail).toContainText(noRunFixture.taskId);
    await expect(page.getByTestId("task-detail-runtime-context")).toHaveCount(0);
    await noRunTaskDetail.screenshot({
      path: `${evidenceDir}/34-task-detail-no-run.png`,
    });

    const noRunRunLogPanel = page.locator("#task-run-log-panel");
    await expect(noRunRunLogPanel).toBeVisible({ timeout: 30000 });
    await expect(noRunRunLogPanel).toContainText("当前还没有选中的运行记录。");
    await expect(page.getByTestId("run-log-runtime-context")).toHaveCount(0);
    await noRunRunLogPanel.screenshot({
      path: `${evidenceDir}/35-run-log-no-run.png`,
    });

    // no_routable chain: homepage run card -> project detail -> task detail -> run log
    await gotoHome(page);
    const noRoutableRunPayload = await runOnceViaHome(page, noRoutableFixture.projectId);
    expect(noRoutableRunPayload.claimed).toBe(false);
    expect(noRoutableRunPayload.run_id).toBeNull();
    expect(String(noRoutableRunPayload.message ?? "")).toContain(
      "none are currently routable",
    );

    const noRoutableResultSection = page
      .locator("section")
      .filter({
        has: page.getByRole("heading", { name: "最近一次手动执行" }),
      })
      .first();
    await expect(noRoutableResultSection).toContainText("none are currently routable");
    await expect(noRoutableResultSection).toContainText("未领取任务");
    await noRoutableResultSection.screenshot({
      path: `${evidenceDir}/36-home-no-routable-result-card.png`,
    });

    await page.reload({ waitUntil: "domcontentloaded" });
    const noRoutableRow = await locateTaskRow(page, noRoutableFixture.taskTitle);
    await expect(noRoutableRow).toContainText("尚未运行");

    const noRoutableProjectDetail = await selectProjectDetail(
      page,
      noRoutableFixture.projectName,
    );
    const noRoutablePreviewSection = noRoutableProjectDetail
      .locator("section")
      .filter({ hasText: "最近任务预览" })
      .first();
    await expect(noRoutablePreviewSection).toContainText(noRoutableFixture.taskTitle);
    await expect(noRoutablePreviewSection).toContainText("尚无运行");
    await noRoutablePreviewSection.screenshot({
      path: `${evidenceDir}/37-project-detail-no-routable-preview.png`,
    });

    const noRoutableTaskDetail = await openTaskDetailFromHome(
      page,
      noRoutableFixture.taskTitle,
    );
    await expect(noRoutableTaskDetail).toContainText(noRoutableFixture.taskId);
    await expect(page.getByTestId("task-detail-runtime-context")).toHaveCount(0);
    await noRoutableTaskDetail.screenshot({
      path: `${evidenceDir}/38-task-detail-no-routable.png`,
    });

    const noRoutableRunLogPanel = page.locator("#task-run-log-panel");
    await expect(noRoutableRunLogPanel).toContainText("当前还没有选中的运行记录。");
    await expect(page.getByTestId("run-log-runtime-context")).toHaveCount(0);
    await noRoutableRunLogPanel.screenshot({
      path: `${evidenceDir}/39-run-log-no-routable.png`,
    });

    // degraded(budget_fallback) chain: homepage -> project detail -> task detail -> run log
    await gotoHome(page);
    const budgetRunPayload = await runOnceViaHome(page, budgetFixture.projectId);
    expect(budgetRunPayload.claimed).toBe(true);
    expect(budgetRunPayload.run_id).toBeTruthy();
    expect(budgetRunPayload.role_model_policy_source).toBe("budget_fallback");
    const budgetRunId = normalizeValue(String(budgetRunPayload.run_id));

    await page.reload({ waitUntil: "domcontentloaded" });
    const budgetRow = await locateTaskRow(page, budgetFixture.taskTitle);
    await expect(budgetRow).toContainText(budgetRunId);
    await expect(budgetRow).toContainText("budget_fallback");
    await budgetRow.screenshot({
      path: `${evidenceDir}/40-home-budget-fallback-task-row.png`,
    });

    const manualRunDrilldownButton = page.getByTestId("home-manual-run-drilldown");
    await expect(manualRunDrilldownButton).toBeVisible({ timeout: 30000 });
    await manualRunDrilldownButton.click();

    const budgetProjectDetailPanel = page.getByTestId("project-detail-panel");
    await expect(budgetProjectDetailPanel).toContainText(budgetFixture.projectName, {
      timeout: 30000,
    });
    const budgetControlSurface = budgetProjectDetailPanel
      .locator("section")
      .filter({ hasText: "Latest Run Control Surface" })
      .first();
    await expect(budgetControlSurface).toBeVisible({ timeout: 30000 });
    await expect
      .poll(async () => readInfoItemValue(budgetControlSurface, "Run ID"), {
        timeout: 30000,
      })
      .toBe(budgetRunId);
    await expect(budgetControlSurface).toContainText("budget_fallback");
    await budgetControlSurface.screenshot({
      path: `${evidenceDir}/41-project-detail-budget-fallback-runtime.png`,
    });

    await budgetControlSurface.getByTestId("goto-strategy-preview-from-latest-run").click();
    const strategyPanel = page.getByTestId("strategy-preview-panel");
    await expect(strategyPanel).toBeVisible({ timeout: 30000 });
    await strategyPanel.getByTestId("goto-task-detail-from-strategy-preview").click();

    const budgetTaskDetailRuntime = page.getByTestId("task-detail-runtime-context");
    await expect(budgetTaskDetailRuntime).toBeVisible({ timeout: 30000 });
    await expect
      .poll(async () => readInfoItemValue(budgetTaskDetailRuntime, "Run ID"), {
        timeout: 30000,
      })
      .toBe(budgetRunId);
    await expect(budgetTaskDetailRuntime).toContainText("budget_fallback");
    await budgetTaskDetailRuntime.screenshot({
      path: `${evidenceDir}/42-task-detail-budget-fallback-runtime.png`,
    });

    const budgetRunLogRuntime = page.getByTestId("run-log-runtime-context");
    await expect(budgetRunLogRuntime).toBeVisible({ timeout: 30000 });
    await expect
      .poll(async () => readInfoItemValue(budgetRunLogRuntime, "Run ID"), {
        timeout: 30000,
      })
      .toBe(budgetRunId);
    await expect(budgetRunLogRuntime).toContainText("budget_fallback");
    await budgetRunLogRuntime.screenshot({
      path: `${evidenceDir}/43-run-log-budget-fallback-runtime.png`,
    });

    const evidencePayload = {
      generated_at: new Date().toISOString(),
      no_run: {
        project_id: noRunFixture.projectId,
        task_id: noRunFixture.taskId,
        task_title: noRunFixture.taskTitle,
        homepage_status: "no_run",
        project_detail_latest_run: "尚无运行",
        task_detail_runtime_context_present: false,
        run_log_runtime_context_present: false,
      },
      no_routable: {
        project_id: noRoutableFixture.projectId,
        task_id: noRoutableFixture.taskId,
        task_title: noRoutableFixture.taskTitle,
        worker_claimed: noRoutableRunPayload.claimed,
        worker_message: noRoutableRunPayload.message,
        worker_run_id: noRoutableRunPayload.run_id,
        homepage_status: "no_run",
        project_detail_latest_run: "尚无运行",
        task_detail_runtime_context_present: false,
        run_log_runtime_context_present: false,
      },
      degraded_budget_fallback: {
        project_id: budgetFixture.projectId,
        task_id: budgetFixture.taskId,
        task_title: budgetFixture.taskTitle,
        run_id: budgetRunPayload.run_id,
        role_model_policy_source: budgetRunPayload.role_model_policy_source,
        budget_action: budgetRunPayload.budget_action,
        project_detail_run_id: await readInfoItemValue(budgetControlSurface, "Run ID"),
        task_detail_run_id: await readInfoItemValue(budgetTaskDetailRuntime, "Run ID"),
        run_log_run_id: await readInfoItemValue(budgetRunLogRuntime, "Run ID"),
      },
    };

    await fs.writeFile(
      `${evidenceDir}/44-day07-negative-page-consistency.json`,
      `${JSON.stringify(evidencePayload, null, 2)}\n`,
      "utf8",
    );

    await context.close();
  } finally {
    await requestJson(request, "PUT", "/strategy/rules", { rules: originalRules });
  }
});

