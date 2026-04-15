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

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function extractBetween(text, start, end) {
  const pattern = new RegExp(
    `${escapeRegExp(start)}\\s+(.+?)\\s+${escapeRegExp(end)}`,
    "i",
  );
  const match = text.match(pattern);
  if (!match) {
    throw new Error(`Unable to extract value between "${start}" and "${end}".`);
  }
  return normalizeValue(match[1]);
}

function extractAfter(text, start) {
  const pattern = new RegExp(`${escapeRegExp(start)}\\s+(.+)$`, "i");
  const match = text.match(pattern);
  if (!match) {
    throw new Error(`Unable to extract value after "${start}".`);
  }
  return normalizeValue(match[1]);
}

function extractStageOverride(text) {
  const match = text.match(/STAGE\s*OVERRIDE\s*([A-Za-z_]+)/i);
  if (!match) {
    throw new Error('Unable to extract value for "STAGE OVERRIDE".');
  }
  return normalizeValue(match[1]);
}

async function readContractLineValue(container, label) {
  const allLines = await container.locator("div.leading-5").allInnerTexts();
  const normalizedLines = allLines.map((line) => normalizeValue(line));
  const matchedLine = normalizedLines.find((line) =>
    line.toLowerCase().startsWith(label.toLowerCase()),
  );
  if (!matchedLine) {
    throw new Error(`Unable to find contract line "${label}".`);
  }
  const value = matchedLine.replace(
    new RegExp(`^${escapeRegExp(label)}\\s*:?[\\s]*`, "i"),
    "",
  );
  return normalizeValue(value);
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

async function createFixture(request) {
  const fixtureSuffix = Date.now();
  const project = await requestJson(request, "POST", "/projects", {
    name: `Day07 Page Consistency Fixture ${fixtureSuffix}`,
    summary:
      "Create two tasks under one project and use a non-latest task sample for drill-down consistency evidence.",
    stage: "execution",
  });
  const sampleTask = await requestJson(request, "POST", "/tasks", {
    project_id: project.id,
    title: `Day07 non-latest sample task ${fixtureSuffix}`,
    input_summary:
      "Produce one real run that will later become a non-latest drill-down sample.",
    priority: "high",
    risk_level: "normal",
    owner_role_code: "architect",
    acceptance_criteria: [
      "This task can be used as non-latest sample in homepage drill-down.",
      "Runtime fields remain consistent through project detail and strategy preview.",
    ],
  });
  const latestTask = await requestJson(request, "POST", "/tasks", {
    project_id: project.id,
    title: `Day07 latest pivot task ${fixtureSuffix}`,
    input_summary:
      "Create a second run so the first sample task is no longer latest_task in project overview.",
    priority: "normal",
    risk_level: "normal",
    owner_role_code: "architect",
    acceptance_criteria: [
      "Second run becomes project latest_task snapshot anchor.",
      "First run remains available for non-latest drill-down verification.",
    ],
  });
  return {
    projectId: project.id,
    projectName: project.name,
    sampleTaskId: sampleTask.id,
    sampleTaskTitle: sampleTask.title,
    latestTaskId: latestTask.id,
    latestTaskTitle: latestTask.title,
  };
}

test("day07 non-latest sample drill-down runtime consistency", async ({
  browser,
  request,
}) => {
  test.setTimeout(180000);
  await fs.mkdir(evidenceDir, { recursive: true });

  const fixture = await createFixture(request);
  const context = await browser.newContext({
    viewport: { width: 1720, height: 1400 },
  });
  const page = await context.newPage();

  const firstRunPayload = await requestJson(
    request,
    "POST",
    `/workers/run-once?project_id=${fixture.projectId}`,
  );
  const secondRunPayload = await requestJson(
    request,
    "POST",
    `/workers/run-once?project_id=${fixture.projectId}`,
  );
  expect(firstRunPayload.claimed).toBe(true);
  expect(secondRunPayload.claimed).toBe(true);

  const firstRunTaskId = normalizeValue(String(firstRunPayload.task_id ?? ""));
  const secondRunTaskId = normalizeValue(String(secondRunPayload.task_id ?? ""));
  const firstRunId = normalizeValue(String(firstRunPayload.run_id ?? ""));
  const secondRunId = normalizeValue(String(secondRunPayload.run_id ?? ""));
  expect(firstRunTaskId.length).toBeGreaterThan(0);
  expect(secondRunTaskId.length).toBeGreaterThan(0);
  expect(firstRunId.length).toBeGreaterThan(0);
  expect(secondRunId.length).toBeGreaterThan(0);
  expect(secondRunTaskId).not.toBe(firstRunTaskId);

  const taskTitleById = new Map([
    [fixture.sampleTaskId, fixture.sampleTaskTitle],
    [fixture.latestTaskId, fixture.latestTaskTitle],
  ]);
  const nonLatestSampleTaskId = firstRunTaskId;
  const nonLatestSampleTaskTitle =
    taskTitleById.get(nonLatestSampleTaskId) ?? `Task ${nonLatestSampleTaskId}`;
  const nonLatestSampleRunId = firstRunId;

  const projectOverview = await requestJson(request, "GET", "/console/project-overview");
  const fixtureProject = projectOverview.projects.find(
    (project) => normalizeValue(String(project.id)) === fixture.projectId,
  );
  expect(fixtureProject).toBeTruthy();
  const currentLatestTaskId = normalizeValue(
    String(fixtureProject.latest_task?.task_id ?? ""),
  );
  expect(currentLatestTaskId).toBe(secondRunTaskId);
  expect(currentLatestTaskId).not.toBe(nonLatestSampleTaskId);

  await page.goto(`${appOrigin}/`, { waitUntil: "domcontentloaded" });

  await page.reload({ waitUntil: "domcontentloaded" });
  const taskListTable = page
    .locator("table")
    .filter({
      has: page.getByRole("columnheader", { name: "Estimated Cost" }),
    })
    .first();
  await expect(taskListTable).toBeVisible({ timeout: 30000 });
  const homepageTaskRow = taskListTable
    .locator("tbody tr")
    .filter({ hasText: nonLatestSampleTaskTitle })
    .first();
  await expect(homepageTaskRow).toBeVisible({ timeout: 30000 });
  await expect(homepageTaskRow).toContainText(nonLatestSampleRunId, { timeout: 30000 });
  await expect(homepageTaskRow).toContainText("Role Model Policy Runtime", {
    timeout: 30000,
  });

  const expectedProvider = normalizeValue(String(firstRunPayload.provider_key ?? "n/a"));
  const expectedPromptTemplate = normalizeValue(
    firstRunPayload.prompt_template_key
      ? `${firstRunPayload.prompt_template_key}${
          firstRunPayload.prompt_template_version
            ? ` @${firstRunPayload.prompt_template_version}`
            : ""
        }`
      : "n/a",
  );
  const expectedTokenAccounting = normalizeValue(
    String(firstRunPayload.token_accounting_mode ?? "n/a"),
  );
  const expectedPolicySource = normalizeValue(
    String(firstRunPayload.role_model_policy_source ?? "n/a"),
  );
  const expectedPolicyDesired = normalizeValue(
    String(firstRunPayload.role_model_policy_desired_tier ?? "n/a"),
  );
  const expectedPolicyAdjusted = normalizeValue(
    String(firstRunPayload.role_model_policy_adjusted_tier ?? "n/a"),
  );
  const expectedPolicyFinal = normalizeValue(
    String(firstRunPayload.role_model_policy_final_tier ?? "n/a"),
  );
  const expectedPolicyStageOverride = firstRunPayload.role_model_policy_stage_override_applied
    ? "yes"
    : "no";
  const homepageEstimatedCost = normalizeValue(
    await homepageTaskRow.locator("td").nth(3).innerText(),
  );

  await expect(homepageTaskRow).toContainText(expectedProvider);
  await expect(homepageTaskRow).toContainText(expectedPromptTemplate);
  await expect(homepageTaskRow).toContainText(expectedTokenAccounting);
  await expect(homepageTaskRow).toContainText(expectedPolicySource);
  await expect(homepageTaskRow).toContainText(expectedPolicyDesired);
  await expect(homepageTaskRow).toContainText(expectedPolicyAdjusted);
  await expect(homepageTaskRow).toContainText(expectedPolicyFinal);
  await expect(homepageTaskRow).toContainText("Stage Override");
  await expect(homepageTaskRow).toContainText(expectedPolicyStageOverride);

  const expectedFields = {
    provider: expectedProvider,
    promptTemplate: expectedPromptTemplate,
    tokenAccounting: expectedTokenAccounting,
    estimatedCost: homepageEstimatedCost,
    policySource: expectedPolicySource,
    policyDesired: expectedPolicyDesired,
    policyAdjusted: expectedPolicyAdjusted,
    policyFinal: expectedPolicyFinal,
    policyStageOverride: expectedPolicyStageOverride,
  };

  await homepageTaskRow.screenshot({
    path: `${evidenceDir}/26-home-task-row-same-sample-runtime-contract.png`,
  });

  await homepageTaskRow
    .getByTestId(`home-task-latest-run-drilldown-${nonLatestSampleTaskId}`)
    .click();

  const projectDetailPanel = page.getByTestId("project-detail-panel");
  await expect(projectDetailPanel).toContainText(fixture.projectName, {
    timeout: 30000,
  });

  const detailControlSurface = projectDetailPanel
    .locator("section")
    .filter({ hasText: "Latest Run Control Surface" })
    .filter({ hasText: "Run ID" })
    .filter({ hasText: "Role Model Policy Runtime" })
    .first();
  await expect(detailControlSurface).toBeVisible({ timeout: 30000 });
  await expect
    .poll(async () => readInfoItemValue(detailControlSurface, "Run ID"), {
      timeout: 30000,
    })
    .toBe(nonLatestSampleRunId);

  const detailRuntimeCard = detailControlSurface
    .locator("div")
    .filter({ hasText: "Latest Run Runtime" })
    .first();
  const detailRolePolicyCard = detailControlSurface
    .locator("div")
    .filter({ hasText: "Role Model Policy Runtime" })
    .first();
  await expect(detailRuntimeCard).toBeVisible();
  await expect(detailRolePolicyCard).toBeVisible();

  const detailFields = {
    provider: await readInfoItemValue(detailRuntimeCard, "Provider"),
    promptTemplate: await readInfoItemValue(detailRuntimeCard, "Prompt Template"),
    tokenAccounting: await readInfoItemValue(detailRuntimeCard, "Token Accounting"),
    estimatedCost: await readInfoItemValue(detailRuntimeCard, "Estimated Cost"),
    policySource: await readInfoItemValue(detailRolePolicyCard, "Source"),
    policyDesired: await readInfoItemValue(detailRolePolicyCard, "Desired Tier"),
    policyAdjusted: await readInfoItemValue(detailRolePolicyCard, "Adjusted Tier"),
    policyFinal: await readInfoItemValue(detailRolePolicyCard, "Final Tier"),
    policyStageOverride: await readInfoItemValue(
      detailRolePolicyCard,
      "Stage Override",
    ),
  };

  await detailControlSurface.screenshot({
    path: `${evidenceDir}/27-project-detail-same-sample-runtime-contract.png`,
  });

  expect(detailFields).toEqual(expectedFields);

  await detailControlSurface
    .getByTestId("goto-strategy-preview-from-latest-run")
    .click();

  const strategyPanel = page.getByTestId("strategy-preview-panel");
  await expect(strategyPanel).toBeVisible({ timeout: 30000 });
  await expect(strategyPanel).toContainText("Linked Latest Run Runtime Context", {
    timeout: 30000,
  });

  const strategyRuntimeContext = strategyPanel.getByTestId(
    "strategy-preview-runtime-context",
  );
  await expect(strategyRuntimeContext).toContainText(nonLatestSampleRunId);

  const strategyRuntimeFields = {
    provider: await readInfoItemValue(strategyRuntimeContext, "Provider"),
    promptTemplate: await readInfoItemValue(
      strategyRuntimeContext,
      "Prompt Template",
    ),
    tokenAccounting: await readInfoItemValue(
      strategyRuntimeContext,
      "Token Accounting",
    ),
    estimatedCost: await readInfoItemValue(strategyRuntimeContext, "Estimated Cost"),
    policySource: await readInfoItemValue(strategyRuntimeContext, "Source"),
    policyDesired: await readInfoItemValue(strategyRuntimeContext, "Desired Tier"),
    policyAdjusted: await readInfoItemValue(
      strategyRuntimeContext,
      "Adjusted Tier",
    ),
    policyFinal: await readInfoItemValue(strategyRuntimeContext, "Final Tier"),
    policyStageOverride: await readInfoItemValue(
      strategyRuntimeContext,
      "Stage Override",
    ),
  };

  await strategyRuntimeContext.screenshot({
    path: `${evidenceDir}/29-strategy-preview-linked-runtime-context.png`,
  });

  expect(strategyRuntimeFields).toEqual(expectedFields);

  await strategyPanel.getByTestId("goto-task-detail-from-strategy-preview").click();

  const taskDetailPanel = page.locator("#task-detail-panel");
  await expect(taskDetailPanel).toBeVisible({ timeout: 30000 });
  await expect(taskDetailPanel).toContainText(nonLatestSampleTaskId, {
    timeout: 30000,
  });

  const taskDetailRuntimeContext = page.getByTestId("task-detail-runtime-context");
  await expect(taskDetailRuntimeContext).toBeVisible({ timeout: 30000 });
  await expect(taskDetailRuntimeContext).toContainText(nonLatestSampleRunId, {
    timeout: 30000,
  });
  await expect
    .poll(async () => readInfoItemValue(taskDetailRuntimeContext, "Run ID"), {
      timeout: 30000,
    })
    .toBe(nonLatestSampleRunId);

  const taskDetailRuntimeFields = {
    provider: await readInfoItemValue(taskDetailRuntimeContext, "Provider"),
    promptTemplate: await readInfoItemValue(taskDetailRuntimeContext, "Prompt Template"),
    tokenAccounting: await readInfoItemValue(taskDetailRuntimeContext, "Token Accounting"),
    estimatedCost: await readInfoItemValue(taskDetailRuntimeContext, "Estimated Cost"),
    policySource: await readInfoItemValue(taskDetailRuntimeContext, "Source"),
    policyDesired: await readInfoItemValue(taskDetailRuntimeContext, "Desired Tier"),
    policyAdjusted: await readInfoItemValue(taskDetailRuntimeContext, "Adjusted Tier"),
    policyFinal: await readInfoItemValue(taskDetailRuntimeContext, "Final Tier"),
    policyStageOverride: await readInfoItemValue(
      taskDetailRuntimeContext,
      "Stage Override",
    ),
  };
  expect(taskDetailRuntimeFields).toEqual(expectedFields);

  await taskDetailRuntimeContext.screenshot({
    path: `${evidenceDir}/30-task-detail-linked-runtime-context.png`,
  });

  const runLogPanel = page.locator("#task-run-log-panel");
  await expect(runLogPanel).toBeVisible({ timeout: 30000 });
  const runLogRuntimeContext = page.getByTestId("run-log-runtime-context");
  await expect(runLogRuntimeContext).toBeVisible({ timeout: 30000 });
  await expect(runLogRuntimeContext).toContainText(nonLatestSampleRunId, {
    timeout: 30000,
  });
  await expect
    .poll(async () => readInfoItemValue(runLogRuntimeContext, "Run ID"), {
      timeout: 30000,
    })
    .toBe(nonLatestSampleRunId);

  const runLogRuntimeFields = {
    provider: await readInfoItemValue(runLogRuntimeContext, "Provider"),
    promptTemplate: await readInfoItemValue(runLogRuntimeContext, "Prompt Template"),
    tokenAccounting: await readInfoItemValue(runLogRuntimeContext, "Token Accounting"),
    estimatedCost: await readInfoItemValue(runLogRuntimeContext, "Estimated Cost"),
    policySource: await readInfoItemValue(runLogRuntimeContext, "Source"),
    policyDesired: await readInfoItemValue(runLogRuntimeContext, "Desired Tier"),
    policyAdjusted: await readInfoItemValue(runLogRuntimeContext, "Adjusted Tier"),
    policyFinal: await readInfoItemValue(runLogRuntimeContext, "Final Tier"),
    policyStageOverride: await readInfoItemValue(runLogRuntimeContext, "Stage Override"),
  };
  expect(runLogRuntimeFields).toEqual(expectedFields);

  await runLogRuntimeContext.screenshot({
    path: `${evidenceDir}/31-run-log-linked-runtime-context.png`,
  });

  const evidencePayload = {
    generated_at: new Date().toISOString(),
    project_id: fixture.projectId,
    project_name: fixture.projectName,
    task_id: nonLatestSampleTaskId,
    task_title: nonLatestSampleTaskTitle,
    run_id: nonLatestSampleRunId,
    latest_task_id: currentLatestTaskId,
    homepage_fields: expectedFields,
    project_detail_fields: detailFields,
    strategy_preview_fields: strategyRuntimeFields,
    task_detail_fields: taskDetailRuntimeFields,
    run_log_fields: runLogRuntimeFields,
  };

  await fs.writeFile(
    `${evidenceDir}/28-day07-same-sample-page-consistency.json`,
    `${JSON.stringify(evidencePayload, null, 2)}\n`,
    "utf8",
  );

  await context.close();
});
