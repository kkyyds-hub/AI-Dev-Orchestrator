import fs from "node:fs/promises";

import { expect, test } from "@playwright/test";

const appOrigin = "http://127.0.0.1:5173";
const evidenceDir =
  "E:/new-AI-Dev-Orchestrator-push/runtime/orchestrator/tmp/day07-browser-evidence";
const sameSampleEvidenceAliasFiles = Object.freeze([
  "28-day07-same-sample-page-consistency.json",
  "32-day07-task-detail-run-log-testid-evidence.json",
  "34-day07-task-detail-to-strategy-preview-roundtrip-evidence.json",
  "36-day07-run-log-to-strategy-preview-roundtrip-evidence.json",
  "38-day07-strategy-preview-to-run-log-drilldown-evidence.json",
  "40-day07-project-latest-run-to-run-log-drilldown-evidence.json",
  "42-day07-project-latest-run-to-strategy-preview-drilldown-evidence.json",
  "44-day07-project-latest-run-to-task-detail-drilldown-evidence.json",
  "46-day07-strategy-preview-to-project-latest-run-drilldown-evidence.json",
]);
const latestBatchIndexAliasFile = "day07-same-sample-latest-batch-index.json";

test.use({
  browserName: "chromium",
  channel: "msedge",
  viewport: { width: 1720, height: 1400 },
});

function createEvidenceBatchId(generatedAt, runId) {
  const timestampPart = generatedAt
    .replace(/[-:.]/g, "")
    .replace("T", "t")
    .replace("Z", "z");
  const runIdPart =
    normalizeValue(String(runId ?? ""))
      .replace(/[^a-zA-Z0-9]/g, "")
      .slice(0, 12) || "norunid";
  return `day07-same-sample-${timestampPart}-${runIdPart}`;
}

function toBatchSnapshotFileName(aliasFileName, evidenceBatchId) {
  const dotIndex = aliasFileName.lastIndexOf(".");
  if (dotIndex <= 0) {
    return `${aliasFileName}--${evidenceBatchId}`;
  }
  const baseName = aliasFileName.slice(0, dotIndex);
  const extension = aliasFileName.slice(dotIndex);
  return `${baseName}--${evidenceBatchId}${extension}`;
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

function normalizeValue(value) {
  return value.replace(/\s+/g, " ").trim();
}

async function readFieldValueByTestId(container, testId) {
  const valueLocator = container
    .getByTestId(testId)
    .locator("[data-slot='value']")
    .first();
  await expect(valueLocator, `Missing field "${testId}"`).toBeVisible();
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
  const homepageTaskRow = page.getByTestId(`home-task-row-${nonLatestSampleTaskId}`);
  await expect(homepageTaskRow).toBeVisible({ timeout: 30000 });
  await expect(homepageTaskRow).toContainText(nonLatestSampleRunId, { timeout: 30000 });
  const homepageRuntimeSummary = page.getByTestId(
    `home-task-runtime-summary-${nonLatestSampleTaskId}`,
  );
  await expect(homepageRuntimeSummary).toBeVisible({ timeout: 30000 });
  await expect(
    page.getByTestId(`home-task-policy-card-${nonLatestSampleTaskId}`),
  ).toBeVisible({ timeout: 30000 });

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
    await page.getByTestId(`home-task-estimated-cost-${nonLatestSampleTaskId}`).innerText(),
  );
  const homepageFields = {
    provider: await readFieldValueByTestId(
      homepageRuntimeSummary,
      `home-task-runtime-field-${nonLatestSampleTaskId}-provider`,
    ),
    promptTemplate: await readFieldValueByTestId(
      homepageRuntimeSummary,
      `home-task-runtime-field-${nonLatestSampleTaskId}-prompt_template`,
    ),
    tokenAccounting: await readFieldValueByTestId(
      homepageRuntimeSummary,
      `home-task-runtime-field-${nonLatestSampleTaskId}-token_accounting`,
    ),
    policySource: await readFieldValueByTestId(
      homepageRuntimeSummary,
      `home-task-policy-field-${nonLatestSampleTaskId}-policy_source`,
    ),
    policyDesired: await readFieldValueByTestId(
      homepageRuntimeSummary,
      `home-task-policy-field-${nonLatestSampleTaskId}-policy_desired_tier`,
    ),
    policyAdjusted: await readFieldValueByTestId(
      homepageRuntimeSummary,
      `home-task-policy-field-${nonLatestSampleTaskId}-policy_adjusted_tier`,
    ),
    policyFinal: await readFieldValueByTestId(
      homepageRuntimeSummary,
      `home-task-policy-field-${nonLatestSampleTaskId}-policy_final_tier`,
    ),
    policyStageOverride: await readFieldValueByTestId(
      homepageRuntimeSummary,
      `home-task-policy-field-${nonLatestSampleTaskId}-policy_stage_override`,
    ),
  };

  const expectedFields = {
    provider: homepageFields.provider,
    promptTemplate: homepageFields.promptTemplate,
    tokenAccounting: homepageFields.tokenAccounting,
    estimatedCost: homepageEstimatedCost,
    policySource: homepageFields.policySource,
    policyDesired: homepageFields.policyDesired,
    policyAdjusted: homepageFields.policyAdjusted,
    policyFinal: homepageFields.policyFinal,
    policyStageOverride: homepageFields.policyStageOverride,
  };
  expect(expectedFields).toEqual({
    provider: expectedProvider,
    promptTemplate: expectedPromptTemplate,
    tokenAccounting: expectedTokenAccounting,
    estimatedCost: homepageEstimatedCost,
    policySource: expectedPolicySource,
    policyDesired: expectedPolicyDesired,
    policyAdjusted: expectedPolicyAdjusted,
    policyFinal: expectedPolicyFinal,
    policyStageOverride: expectedPolicyStageOverride,
  });

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

  const detailControlSurface = projectDetailPanel.getByTestId(
    "project-latest-run-control-surface",
  );
  await expect(detailControlSurface).toBeVisible({ timeout: 30000 });
  await expect
    .poll(
      async () =>
        readFieldValueByTestId(detailControlSurface, "project-latest-run-run-id-field"),
      {
      timeout: 30000,
    },
    )
    .toBe(nonLatestSampleRunId);

  const detailRuntimeCard = detailControlSurface.getByTestId(
    "project-latest-run-runtime-card",
  );
  const detailRolePolicyCard = detailControlSurface.getByTestId(
    "project-latest-run-policy-card",
  );
  await expect(detailRuntimeCard).toBeVisible();
  await expect(detailRolePolicyCard).toBeVisible();

  const detailFields = {
    provider: await readFieldValueByTestId(
      detailRuntimeCard,
      "project-latest-run-runtime-field-provider",
    ),
    promptTemplate: await readFieldValueByTestId(
      detailRuntimeCard,
      "project-latest-run-runtime-field-prompt_template",
    ),
    tokenAccounting: await readFieldValueByTestId(
      detailRuntimeCard,
      "project-latest-run-runtime-field-token_accounting",
    ),
    estimatedCost: await readFieldValueByTestId(
      detailRuntimeCard,
      "project-latest-run-runtime-field-estimated_cost",
    ),
    policySource: await readFieldValueByTestId(
      detailRolePolicyCard,
      "project-latest-run-policy-field-policy_source",
    ),
    policyDesired: await readFieldValueByTestId(
      detailRolePolicyCard,
      "project-latest-run-policy-field-policy_desired_tier",
    ),
    policyAdjusted: await readFieldValueByTestId(
      detailRolePolicyCard,
      "project-latest-run-policy-field-policy_adjusted_tier",
    ),
    policyFinal: await readFieldValueByTestId(
      detailRolePolicyCard,
      "project-latest-run-policy-field-policy_final_tier",
    ),
    policyStageOverride: await readFieldValueByTestId(
      detailRolePolicyCard,
      "project-latest-run-policy-field-policy_stage_override",
    ),
  };

  await detailControlSurface.screenshot({
    path: `${evidenceDir}/27-project-detail-same-sample-runtime-contract.png`,
  });

  expect(detailFields).toEqual(expectedFields);

  await detailControlSurface
    .getByTestId("goto-run-log-from-project-latest-run")
    .click();

  const runLogPanelFromProjectLatestRun = page.locator("#task-run-log-panel");
  await expect(runLogPanelFromProjectLatestRun).toBeVisible({ timeout: 30000 });
  const runLogRuntimeContextFromProjectLatestRun = page.getByTestId(
    "run-log-runtime-context",
  );
  await expect(runLogRuntimeContextFromProjectLatestRun).toBeVisible({
    timeout: 30000,
  });
  await expect(runLogRuntimeContextFromProjectLatestRun).toContainText(
    nonLatestSampleRunId,
    {
      timeout: 30000,
    },
  );
  await expect
    .poll(
      async () =>
        readFieldValueByTestId(
          runLogRuntimeContextFromProjectLatestRun,
          "run-log-runtime-field-run_id",
        ),
      {
        timeout: 30000,
      },
    )
    .toBe(nonLatestSampleRunId);

  const projectLatestRunToRunLogFields = {
    provider: await readFieldValueByTestId(
      runLogRuntimeContextFromProjectLatestRun,
      "run-log-runtime-field-provider",
    ),
    promptTemplate: await readFieldValueByTestId(
      runLogRuntimeContextFromProjectLatestRun,
      "run-log-runtime-field-prompt_template",
    ),
    tokenAccounting: await readFieldValueByTestId(
      runLogRuntimeContextFromProjectLatestRun,
      "run-log-runtime-field-token_accounting",
    ),
  };
  expect(projectLatestRunToRunLogFields).toEqual({
    provider: expectedFields.provider,
    promptTemplate: expectedFields.promptTemplate,
    tokenAccounting: expectedFields.tokenAccounting,
  });

  await runLogRuntimeContextFromProjectLatestRun.screenshot({
    path: `${evidenceDir}/39-project-latest-run-to-run-log-drilldown.png`,
  });

  await page.getByTestId("goto-strategy-preview-from-run-log").click();

  const strategyPanel = page.getByTestId("strategy-preview-panel");
  await expect(strategyPanel).toBeVisible({ timeout: 30000 });

  const strategyRuntimeContext = strategyPanel.getByTestId(
    "strategy-preview-runtime-context",
  );
  await expect(strategyRuntimeContext).toBeVisible({ timeout: 30000 });
  await expect(strategyRuntimeContext).toContainText(nonLatestSampleRunId);

  const strategyRuntimeFields = {
    provider: await readFieldValueByTestId(
      strategyRuntimeContext,
      "strategy-preview-runtime-field-provider",
    ),
    promptTemplate: await readFieldValueByTestId(
      strategyRuntimeContext,
      "strategy-preview-runtime-field-prompt_template",
    ),
    tokenAccounting: await readFieldValueByTestId(
      strategyRuntimeContext,
      "strategy-preview-runtime-field-token_accounting",
    ),
    estimatedCost: await readFieldValueByTestId(
      strategyRuntimeContext,
      "strategy-preview-runtime-field-estimated_cost",
    ),
    policySource: await readFieldValueByTestId(
      strategyRuntimeContext,
      "strategy-preview-policy-field-policy_source",
    ),
    policyDesired: await readFieldValueByTestId(
      strategyRuntimeContext,
      "strategy-preview-policy-field-policy_desired_tier",
    ),
    policyAdjusted: await readFieldValueByTestId(
      strategyRuntimeContext,
      "strategy-preview-policy-field-policy_adjusted_tier",
    ),
    policyFinal: await readFieldValueByTestId(
      strategyRuntimeContext,
      "strategy-preview-policy-field-policy_final_tier",
    ),
    policyStageOverride: await readFieldValueByTestId(
      strategyRuntimeContext,
      "strategy-preview-policy-field-policy_stage_override",
    ),
  };

  await strategyRuntimeContext.screenshot({
    path: `${evidenceDir}/29-strategy-preview-linked-runtime-context.png`,
  });

  expect(strategyRuntimeFields).toEqual(expectedFields);

  await strategyPanel.getByTestId("goto-run-log-from-strategy-preview").click();

  const runLogPanelFromStrategy = page.locator("#task-run-log-panel");
  await expect(runLogPanelFromStrategy).toBeVisible({ timeout: 30000 });
  const runLogRuntimeContextFromStrategy = page.getByTestId("run-log-runtime-context");
  await expect(runLogRuntimeContextFromStrategy).toBeVisible({ timeout: 30000 });
  await expect(runLogRuntimeContextFromStrategy).toContainText(nonLatestSampleRunId, {
    timeout: 30000,
  });
  await expect
    .poll(
      async () =>
        readFieldValueByTestId(runLogRuntimeContextFromStrategy, "run-log-runtime-field-run_id"),
      {
        timeout: 30000,
      },
    )
    .toBe(nonLatestSampleRunId);

  const strategyToRunLogFields = {
    provider: await readFieldValueByTestId(
      runLogRuntimeContextFromStrategy,
      "run-log-runtime-field-provider",
    ),
    promptTemplate: await readFieldValueByTestId(
      runLogRuntimeContextFromStrategy,
      "run-log-runtime-field-prompt_template",
    ),
    tokenAccounting: await readFieldValueByTestId(
      runLogRuntimeContextFromStrategy,
      "run-log-runtime-field-token_accounting",
    ),
  };
  expect(strategyToRunLogFields).toEqual({
    provider: expectedFields.provider,
    promptTemplate: expectedFields.promptTemplate,
    tokenAccounting: expectedFields.tokenAccounting,
  });

  await runLogRuntimeContextFromStrategy.screenshot({
    path: `${evidenceDir}/37-strategy-preview-to-run-log-drilldown.png`,
  });

  await page.getByTestId("goto-strategy-preview-from-run-log").click();
  await expect(strategyRuntimeContext).toBeVisible({ timeout: 30000 });
  await expect(strategyRuntimeContext).toContainText(nonLatestSampleRunId, {
    timeout: 30000,
  });

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
    .poll(
      async () =>
        readFieldValueByTestId(taskDetailRuntimeContext, "task-detail-runtime-field-run_id"),
      {
        timeout: 30000,
      },
    )
    .toBe(nonLatestSampleRunId);

  const taskDetailRuntimeFields = {
    provider: await readFieldValueByTestId(
      taskDetailRuntimeContext,
      "task-detail-runtime-field-provider",
    ),
    promptTemplate: await readFieldValueByTestId(
      taskDetailRuntimeContext,
      "task-detail-runtime-field-prompt_template",
    ),
    tokenAccounting: await readFieldValueByTestId(
      taskDetailRuntimeContext,
      "task-detail-runtime-field-token_accounting",
    ),
    estimatedCost: await readFieldValueByTestId(
      taskDetailRuntimeContext,
      "task-detail-runtime-field-estimated_cost",
    ),
    policySource: await readFieldValueByTestId(
      taskDetailRuntimeContext,
      "task-detail-policy-field-policy_source",
    ),
    policyDesired: await readFieldValueByTestId(
      taskDetailRuntimeContext,
      "task-detail-policy-field-policy_desired_tier",
    ),
    policyAdjusted: await readFieldValueByTestId(
      taskDetailRuntimeContext,
      "task-detail-policy-field-policy_adjusted_tier",
    ),
    policyFinal: await readFieldValueByTestId(
      taskDetailRuntimeContext,
      "task-detail-policy-field-policy_final_tier",
    ),
    policyStageOverride: await readFieldValueByTestId(
      taskDetailRuntimeContext,
      "task-detail-policy-field-policy_stage_override",
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
    .poll(async () => readFieldValueByTestId(runLogRuntimeContext, "run-log-runtime-field-run_id"), {
      timeout: 30000,
    })
    .toBe(nonLatestSampleRunId);

  const runLogRuntimeFields = {
    provider: await readFieldValueByTestId(runLogRuntimeContext, "run-log-runtime-field-provider"),
    promptTemplate: await readFieldValueByTestId(
      runLogRuntimeContext,
      "run-log-runtime-field-prompt_template",
    ),
    tokenAccounting: await readFieldValueByTestId(
      runLogRuntimeContext,
      "run-log-runtime-field-token_accounting",
    ),
    estimatedCost: await readFieldValueByTestId(
      runLogRuntimeContext,
      "run-log-runtime-field-estimated_cost",
    ),
    policySource: await readFieldValueByTestId(
      runLogRuntimeContext,
      "run-log-policy-field-policy_source",
    ),
    policyDesired: await readFieldValueByTestId(
      runLogRuntimeContext,
      "run-log-policy-field-policy_desired_tier",
    ),
    policyAdjusted: await readFieldValueByTestId(
      runLogRuntimeContext,
      "run-log-policy-field-policy_adjusted_tier",
    ),
    policyFinal: await readFieldValueByTestId(
      runLogRuntimeContext,
      "run-log-policy-field-policy_final_tier",
    ),
    policyStageOverride: await readFieldValueByTestId(
      runLogRuntimeContext,
      "run-log-policy-field-policy_stage_override",
    ),
  };
  expect(runLogRuntimeFields).toEqual(expectedFields);

  await runLogRuntimeContext.screenshot({
    path: `${evidenceDir}/31-run-log-linked-runtime-context.png`,
  });

  await page.getByTestId("goto-strategy-preview-from-run-log").click();

  const strategyRoundtripFromRunLogRuntimeContext = page.getByTestId(
    "strategy-preview-runtime-context",
  );
  await expect(strategyRoundtripFromRunLogRuntimeContext).toBeVisible({
    timeout: 30000,
  });
  await expect(strategyRoundtripFromRunLogRuntimeContext).toContainText(
    nonLatestSampleRunId,
    {
      timeout: 30000,
    },
  );

  const strategyRoundtripFromRunLogFields = {
    provider: await readFieldValueByTestId(
      strategyRoundtripFromRunLogRuntimeContext,
      "strategy-preview-runtime-field-provider",
    ),
    promptTemplate: await readFieldValueByTestId(
      strategyRoundtripFromRunLogRuntimeContext,
      "strategy-preview-runtime-field-prompt_template",
    ),
    tokenAccounting: await readFieldValueByTestId(
      strategyRoundtripFromRunLogRuntimeContext,
      "strategy-preview-runtime-field-token_accounting",
    ),
  };
  expect(strategyRoundtripFromRunLogFields).toEqual({
    provider: expectedFields.provider,
    promptTemplate: expectedFields.promptTemplate,
    tokenAccounting: expectedFields.tokenAccounting,
  });

  await strategyRoundtripFromRunLogRuntimeContext.screenshot({
    path: `${evidenceDir}/35-run-log-to-strategy-preview-roundtrip.png`,
  });

  await page.getByTestId("goto-task-detail-from-strategy-preview").click();
  await expect(taskDetailRuntimeContext).toBeVisible({ timeout: 30000 });
  await expect(taskDetailRuntimeContext).toContainText(nonLatestSampleRunId, {
    timeout: 30000,
  });

  await page.getByTestId("goto-strategy-preview-from-task-detail").click();

  const strategyRoundtripRuntimeContext = page.getByTestId(
    "strategy-preview-runtime-context",
  );
  await expect(strategyRoundtripRuntimeContext).toBeVisible({ timeout: 30000 });
  await expect(strategyRoundtripRuntimeContext).toContainText(nonLatestSampleRunId, {
    timeout: 30000,
  });

  const strategyRoundtripFields = {
    provider: await readFieldValueByTestId(
      strategyRoundtripRuntimeContext,
      "strategy-preview-runtime-field-provider",
    ),
    promptTemplate: await readFieldValueByTestId(
      strategyRoundtripRuntimeContext,
      "strategy-preview-runtime-field-prompt_template",
    ),
    tokenAccounting: await readFieldValueByTestId(
      strategyRoundtripRuntimeContext,
      "strategy-preview-runtime-field-token_accounting",
    ),
  };
  expect(strategyRoundtripFields).toEqual({
    provider: expectedFields.provider,
    promptTemplate: expectedFields.promptTemplate,
    tokenAccounting: expectedFields.tokenAccounting,
  });

  await strategyRoundtripRuntimeContext.screenshot({
    path: `${evidenceDir}/33-task-detail-to-strategy-preview-roundtrip.png`,
  });

  await homepageTaskRow
    .getByTestId(`home-task-latest-run-drilldown-${nonLatestSampleTaskId}`)
    .click();

  const projectLatestRunControlSurfaceForStrategy = page.getByTestId(
    "project-latest-run-control-surface",
  );
  await expect(projectLatestRunControlSurfaceForStrategy).toBeVisible({
    timeout: 30000,
  });
  await expect
    .poll(
      async () =>
        readFieldValueByTestId(
          projectLatestRunControlSurfaceForStrategy,
          "project-latest-run-run-id-field",
        ),
      {
        timeout: 30000,
      },
    )
    .toBe(nonLatestSampleRunId);

  await projectLatestRunControlSurfaceForStrategy
    .getByTestId("goto-task-detail-from-project-latest-run")
    .click();

  const taskDetailPanelFromProjectLatestRun = page.locator("#task-detail-panel");
  await expect(taskDetailPanelFromProjectLatestRun).toBeVisible({ timeout: 30000 });
  const taskDetailRuntimeContextFromProjectLatestRun = page.getByTestId(
    "task-detail-runtime-context",
  );
  await expect(taskDetailRuntimeContextFromProjectLatestRun).toBeVisible({
    timeout: 30000,
  });
  await expect(taskDetailRuntimeContextFromProjectLatestRun).toContainText(
    nonLatestSampleRunId,
    {
      timeout: 30000,
    },
  );
  await expect
    .poll(
      async () =>
        readFieldValueByTestId(
          taskDetailRuntimeContextFromProjectLatestRun,
          "task-detail-runtime-field-run_id",
        ),
      {
        timeout: 30000,
      },
    )
    .toBe(nonLatestSampleRunId);

  const projectLatestRunToTaskDetailFields = {
    provider: await readFieldValueByTestId(
      taskDetailRuntimeContextFromProjectLatestRun,
      "task-detail-runtime-field-provider",
    ),
    promptTemplate: await readFieldValueByTestId(
      taskDetailRuntimeContextFromProjectLatestRun,
      "task-detail-runtime-field-prompt_template",
    ),
    tokenAccounting: await readFieldValueByTestId(
      taskDetailRuntimeContextFromProjectLatestRun,
      "task-detail-runtime-field-token_accounting",
    ),
    estimatedCost: await readFieldValueByTestId(
      taskDetailRuntimeContextFromProjectLatestRun,
      "task-detail-runtime-field-estimated_cost",
    ),
    policySource: await readFieldValueByTestId(
      taskDetailRuntimeContextFromProjectLatestRun,
      "task-detail-policy-field-policy_source",
    ),
    policyDesired: await readFieldValueByTestId(
      taskDetailRuntimeContextFromProjectLatestRun,
      "task-detail-policy-field-policy_desired_tier",
    ),
    policyAdjusted: await readFieldValueByTestId(
      taskDetailRuntimeContextFromProjectLatestRun,
      "task-detail-policy-field-policy_adjusted_tier",
    ),
    policyFinal: await readFieldValueByTestId(
      taskDetailRuntimeContextFromProjectLatestRun,
      "task-detail-policy-field-policy_final_tier",
    ),
    policyStageOverride: await readFieldValueByTestId(
      taskDetailRuntimeContextFromProjectLatestRun,
      "task-detail-policy-field-policy_stage_override",
    ),
  };
  expect(projectLatestRunToTaskDetailFields).toEqual(expectedFields);

  await taskDetailRuntimeContextFromProjectLatestRun.screenshot({
    path: `${evidenceDir}/43-project-latest-run-to-task-detail-drilldown.png`,
  });

  await homepageTaskRow
    .getByTestId(`home-task-latest-run-drilldown-${nonLatestSampleTaskId}`)
    .click();

  await expect(projectLatestRunControlSurfaceForStrategy).toBeVisible({
    timeout: 30000,
  });
  await expect
    .poll(
      async () =>
        readFieldValueByTestId(
          projectLatestRunControlSurfaceForStrategy,
          "project-latest-run-run-id-field",
        ),
      {
        timeout: 30000,
      },
    )
    .toBe(nonLatestSampleRunId);

  await projectLatestRunControlSurfaceForStrategy
    .getByTestId("goto-strategy-preview-from-latest-run")
    .click();

  const strategyPanelFromProjectLatestRun = page.getByTestId("strategy-preview-panel");
  await expect(strategyPanelFromProjectLatestRun).toBeVisible({ timeout: 30000 });
  const strategyRuntimeContextFromProjectLatestRun =
    strategyPanelFromProjectLatestRun.getByTestId("strategy-preview-runtime-context");
  await expect(strategyRuntimeContextFromProjectLatestRun).toBeVisible({
    timeout: 30000,
  });
  await expect(strategyRuntimeContextFromProjectLatestRun).toContainText(
    nonLatestSampleRunId,
    {
      timeout: 30000,
    },
  );

  const strategyDrilldownStatusFromProjectLatestRun =
    strategyPanelFromProjectLatestRun.getByTestId("strategy-preview-drilldown-status");
  await expect(strategyDrilldownStatusFromProjectLatestRun).toContainText(
    "source=project_latest_run",
  );

  const projectLatestRunToStrategyFields = {
    provider: await readFieldValueByTestId(
      strategyRuntimeContextFromProjectLatestRun,
      "strategy-preview-runtime-field-provider",
    ),
    promptTemplate: await readFieldValueByTestId(
      strategyRuntimeContextFromProjectLatestRun,
      "strategy-preview-runtime-field-prompt_template",
    ),
    tokenAccounting: await readFieldValueByTestId(
      strategyRuntimeContextFromProjectLatestRun,
      "strategy-preview-runtime-field-token_accounting",
    ),
    estimatedCost: await readFieldValueByTestId(
      strategyRuntimeContextFromProjectLatestRun,
      "strategy-preview-runtime-field-estimated_cost",
    ),
    policySource: await readFieldValueByTestId(
      strategyRuntimeContextFromProjectLatestRun,
      "strategy-preview-policy-field-policy_source",
    ),
    policyDesired: await readFieldValueByTestId(
      strategyRuntimeContextFromProjectLatestRun,
      "strategy-preview-policy-field-policy_desired_tier",
    ),
    policyAdjusted: await readFieldValueByTestId(
      strategyRuntimeContextFromProjectLatestRun,
      "strategy-preview-policy-field-policy_adjusted_tier",
    ),
    policyFinal: await readFieldValueByTestId(
      strategyRuntimeContextFromProjectLatestRun,
      "strategy-preview-policy-field-policy_final_tier",
    ),
    policyStageOverride: await readFieldValueByTestId(
      strategyRuntimeContextFromProjectLatestRun,
      "strategy-preview-policy-field-policy_stage_override",
    ),
  };
  expect(projectLatestRunToStrategyFields).toEqual(expectedFields);

  await strategyRuntimeContextFromProjectLatestRun.screenshot({
    path: `${evidenceDir}/41-project-latest-run-to-strategy-preview-drilldown.png`,
  });

  await strategyPanelFromProjectLatestRun
    .getByTestId("goto-project-latest-run-from-strategy-preview")
    .click();

  await expect(projectLatestRunControlSurfaceForStrategy).toBeVisible({
    timeout: 30000,
  });
  await expect
    .poll(
      async () =>
        readFieldValueByTestId(
          projectLatestRunControlSurfaceForStrategy,
          "project-latest-run-run-id-field",
        ),
      {
        timeout: 30000,
      },
    )
    .toBe(nonLatestSampleRunId);

  const projectLatestRunDrilldownStatusFromStrategyPreview =
    projectLatestRunControlSurfaceForStrategy.getByTestId(
      "project-latest-run-drilldown-status",
    );
  await expect(projectLatestRunDrilldownStatusFromStrategyPreview).toContainText(
    "source=strategy_preview",
  );

  const projectLatestRunRuntimeCardFromStrategyPreview =
    projectLatestRunControlSurfaceForStrategy.getByTestId(
      "project-latest-run-runtime-card",
    );
  const projectLatestRunPolicyCardFromStrategyPreview =
    projectLatestRunControlSurfaceForStrategy.getByTestId(
      "project-latest-run-policy-card",
    );

  const strategyToProjectLatestRunFields = {
    provider: await readFieldValueByTestId(
      projectLatestRunRuntimeCardFromStrategyPreview,
      "project-latest-run-runtime-field-provider",
    ),
    promptTemplate: await readFieldValueByTestId(
      projectLatestRunRuntimeCardFromStrategyPreview,
      "project-latest-run-runtime-field-prompt_template",
    ),
    tokenAccounting: await readFieldValueByTestId(
      projectLatestRunRuntimeCardFromStrategyPreview,
      "project-latest-run-runtime-field-token_accounting",
    ),
    estimatedCost: await readFieldValueByTestId(
      projectLatestRunRuntimeCardFromStrategyPreview,
      "project-latest-run-runtime-field-estimated_cost",
    ),
    policySource: await readFieldValueByTestId(
      projectLatestRunPolicyCardFromStrategyPreview,
      "project-latest-run-policy-field-policy_source",
    ),
    policyDesired: await readFieldValueByTestId(
      projectLatestRunPolicyCardFromStrategyPreview,
      "project-latest-run-policy-field-policy_desired_tier",
    ),
    policyAdjusted: await readFieldValueByTestId(
      projectLatestRunPolicyCardFromStrategyPreview,
      "project-latest-run-policy-field-policy_adjusted_tier",
    ),
    policyFinal: await readFieldValueByTestId(
      projectLatestRunPolicyCardFromStrategyPreview,
      "project-latest-run-policy-field-policy_final_tier",
    ),
    policyStageOverride: await readFieldValueByTestId(
      projectLatestRunPolicyCardFromStrategyPreview,
      "project-latest-run-policy-field-policy_stage_override",
    ),
  };
  expect(strategyToProjectLatestRunFields).toEqual(expectedFields);

  await projectLatestRunControlSurfaceForStrategy.screenshot({
    path: `${evidenceDir}/45-strategy-preview-to-project-latest-run-drilldown.png`,
  });

  const generatedAt = new Date().toISOString();
  const evidenceBatchId = createEvidenceBatchId(generatedAt, nonLatestSampleRunId);
  const primaryEvidenceAlias = sameSampleEvidenceAliasFiles[0];
  const batchSnapshotFileByAlias = Object.fromEntries(
    sameSampleEvidenceAliasFiles.map((aliasFileName) => [
      aliasFileName,
      toBatchSnapshotFileName(aliasFileName, evidenceBatchId),
    ]),
  );

  const evidencePayload = {
    generated_at: generatedAt,
    evidence_batch_id: evidenceBatchId,
    project_id: fixture.projectId,
    project_name: fixture.projectName,
    task_id: nonLatestSampleTaskId,
    task_title: nonLatestSampleTaskTitle,
    run_id: nonLatestSampleRunId,
    latest_task_id: currentLatestTaskId,
    homepage_fields: expectedFields,
    project_detail_fields: detailFields,
    project_latest_run_to_run_log_fields: projectLatestRunToRunLogFields,
    project_latest_run_to_task_detail_fields: projectLatestRunToTaskDetailFields,
    project_latest_run_to_strategy_fields: projectLatestRunToStrategyFields,
    strategy_to_project_latest_run_fields: strategyToProjectLatestRunFields,
    strategy_preview_fields: strategyRuntimeFields,
    strategy_to_run_log_fields: strategyToRunLogFields,
    task_detail_fields: taskDetailRuntimeFields,
    run_log_fields: runLogRuntimeFields,
    run_log_to_strategy_roundtrip_fields: strategyRoundtripFromRunLogFields,
    task_detail_to_strategy_roundtrip_fields: strategyRoundtripFields,
  };
  const taskDetailRunLogEvidencePayload = {
    generated_at: generatedAt,
    evidence_batch_id: evidenceBatchId,
    based_on: primaryEvidenceAlias,
    based_on_batch_snapshot: batchSnapshotFileByAlias[primaryEvidenceAlias],
    slice: "day07-task-detail-run-log-latest-run-runtime-role-model-policy-consistency",
    anchors: [
      "task-detail-runtime-field-*",
      "task-detail-policy-field-*",
      "run-log-runtime-field-*",
      "run-log-policy-field-*",
    ],
    project_id: fixture.projectId,
    task_id: nonLatestSampleTaskId,
    run_id: nonLatestSampleRunId,
    task_detail_fields: taskDetailRuntimeFields,
    run_log_fields: runLogRuntimeFields,
  };
  const taskDetailToStrategyEvidencePayload = {
    generated_at: generatedAt,
    evidence_batch_id: evidenceBatchId,
    based_on: primaryEvidenceAlias,
    based_on_batch_snapshot: batchSnapshotFileByAlias[primaryEvidenceAlias],
    slice: "day07-task-detail-to-strategy-preview-minimal-operable-loop",
    anchors: [
      "goto-strategy-preview-from-task-detail",
      "strategy-preview-runtime-context",
      "strategy-preview-runtime-field-provider",
      "strategy-preview-runtime-field-prompt_template",
      "strategy-preview-runtime-field-token_accounting",
    ],
    project_id: fixture.projectId,
    task_id: nonLatestSampleTaskId,
    run_id: nonLatestSampleRunId,
    strategy_roundtrip_fields: strategyRoundtripFields,
  };
  const runLogToStrategyEvidencePayload = {
    generated_at: generatedAt,
    evidence_batch_id: evidenceBatchId,
    based_on: primaryEvidenceAlias,
    based_on_batch_snapshot: batchSnapshotFileByAlias[primaryEvidenceAlias],
    slice: "day07-run-log-to-strategy-preview-minimal-operable-loop",
    anchors: [
      "goto-strategy-preview-from-run-log",
      "strategy-preview-runtime-context",
      "strategy-preview-runtime-field-provider",
      "strategy-preview-runtime-field-prompt_template",
      "strategy-preview-runtime-field-token_accounting",
    ],
    project_id: fixture.projectId,
    task_id: nonLatestSampleTaskId,
    run_id: nonLatestSampleRunId,
    strategy_roundtrip_fields: strategyRoundtripFromRunLogFields,
  };
  const strategyToRunLogEvidencePayload = {
    generated_at: generatedAt,
    evidence_batch_id: evidenceBatchId,
    based_on: primaryEvidenceAlias,
    based_on_batch_snapshot: batchSnapshotFileByAlias[primaryEvidenceAlias],
    slice: "day07-strategy-preview-to-run-log-minimal-operable-drilldown",
    anchors: [
      "goto-run-log-from-strategy-preview",
      "run-log-runtime-context",
      "run-log-runtime-field-provider",
      "run-log-runtime-field-prompt_template",
      "run-log-runtime-field-token_accounting",
    ],
    project_id: fixture.projectId,
    task_id: nonLatestSampleTaskId,
    run_id: nonLatestSampleRunId,
    strategy_to_run_log_fields: strategyToRunLogFields,
  };
  const projectLatestRunToRunLogEvidencePayload = {
    generated_at: generatedAt,
    evidence_batch_id: evidenceBatchId,
    based_on: primaryEvidenceAlias,
    based_on_batch_snapshot: batchSnapshotFileByAlias[primaryEvidenceAlias],
    slice: "day07-project-latest-run-to-run-log-minimal-operable-drilldown",
    anchors: [
      "goto-run-log-from-project-latest-run",
      "run-log-runtime-context",
      "run-log-runtime-field-provider",
      "run-log-runtime-field-prompt_template",
      "run-log-runtime-field-token_accounting",
    ],
    project_id: fixture.projectId,
    task_id: nonLatestSampleTaskId,
    run_id: nonLatestSampleRunId,
    project_latest_run_to_run_log_fields: projectLatestRunToRunLogFields,
  };
  const projectLatestRunToStrategyEvidencePayload = {
    generated_at: generatedAt,
    evidence_batch_id: evidenceBatchId,
    based_on: primaryEvidenceAlias,
    based_on_batch_snapshot: batchSnapshotFileByAlias[primaryEvidenceAlias],
    slice: "day07-project-latest-run-to-strategy-preview-minimal-operable-drilldown",
    anchors: [
      "goto-strategy-preview-from-latest-run",
      "strategy-preview-runtime-context",
      "strategy-preview-runtime-field-provider",
      "strategy-preview-runtime-field-prompt_template",
      "strategy-preview-runtime-field-token_accounting",
    ],
    project_id: fixture.projectId,
    task_id: nonLatestSampleTaskId,
    run_id: nonLatestSampleRunId,
    project_latest_run_to_strategy_fields: projectLatestRunToStrategyFields,
  };
  const projectLatestRunToTaskDetailEvidencePayload = {
    generated_at: generatedAt,
    evidence_batch_id: evidenceBatchId,
    based_on: primaryEvidenceAlias,
    based_on_batch_snapshot: batchSnapshotFileByAlias[primaryEvidenceAlias],
    slice: "day07-project-latest-run-to-task-detail-minimal-operable-drilldown",
    anchors: [
      "goto-task-detail-from-project-latest-run",
      "task-detail-runtime-context",
      "task-detail-runtime-field-provider",
      "task-detail-runtime-field-prompt_template",
      "task-detail-runtime-field-token_accounting",
    ],
    project_id: fixture.projectId,
    task_id: nonLatestSampleTaskId,
    run_id: nonLatestSampleRunId,
    project_latest_run_to_task_detail_fields: projectLatestRunToTaskDetailFields,
  };
  const strategyToProjectLatestRunEvidencePayload = {
    generated_at: generatedAt,
    evidence_batch_id: evidenceBatchId,
    based_on: primaryEvidenceAlias,
    based_on_batch_snapshot: batchSnapshotFileByAlias[primaryEvidenceAlias],
    slice: "day07-strategy-preview-to-project-latest-run-minimal-operable-drilldown",
    anchors: [
      "goto-project-latest-run-from-strategy-preview",
      "project-latest-run-control-surface",
      "project-latest-run-runtime-field-provider",
      "project-latest-run-runtime-field-prompt_template",
      "project-latest-run-runtime-field-token_accounting",
    ],
    project_id: fixture.projectId,
    task_id: nonLatestSampleTaskId,
    run_id: nonLatestSampleRunId,
    strategy_to_project_latest_run_fields: strategyToProjectLatestRunFields,
  };

  const evidencePayloadByAlias = {
    "28-day07-same-sample-page-consistency.json": evidencePayload,
    "32-day07-task-detail-run-log-testid-evidence.json": taskDetailRunLogEvidencePayload,
    "34-day07-task-detail-to-strategy-preview-roundtrip-evidence.json":
      taskDetailToStrategyEvidencePayload,
    "36-day07-run-log-to-strategy-preview-roundtrip-evidence.json":
      runLogToStrategyEvidencePayload,
    "38-day07-strategy-preview-to-run-log-drilldown-evidence.json":
      strategyToRunLogEvidencePayload,
    "40-day07-project-latest-run-to-run-log-drilldown-evidence.json":
      projectLatestRunToRunLogEvidencePayload,
    "42-day07-project-latest-run-to-strategy-preview-drilldown-evidence.json":
      projectLatestRunToStrategyEvidencePayload,
    "44-day07-project-latest-run-to-task-detail-drilldown-evidence.json":
      projectLatestRunToTaskDetailEvidencePayload,
    "46-day07-strategy-preview-to-project-latest-run-drilldown-evidence.json":
      strategyToProjectLatestRunEvidencePayload,
  };
  for (const aliasFileName of sameSampleEvidenceAliasFiles) {
    const payload = evidencePayloadByAlias[aliasFileName];
    await fs.writeFile(
      `${evidenceDir}/${aliasFileName}`,
      `${JSON.stringify(payload, null, 2)}\n`,
      "utf8",
    );
    await fs.writeFile(
      `${evidenceDir}/${batchSnapshotFileByAlias[aliasFileName]}`,
      `${JSON.stringify(payload, null, 2)}\n`,
      "utf8",
    );
  }

  const batchIndexFileName = `day07-same-sample-batch-index--${evidenceBatchId}.json`;
  const batchIndexPayload = {
    generated_at: generatedAt,
    evidence_batch_id: evidenceBatchId,
    slice: "day07-same-sample-drilldown-evidence-traceability",
    project_id: fixture.projectId,
    project_name: fixture.projectName,
    task_id: nonLatestSampleTaskId,
    task_title: nonLatestSampleTaskTitle,
    run_id: nonLatestSampleRunId,
    latest_task_id: currentLatestTaskId,
    latest_alias_index_file: latestBatchIndexAliasFile,
    latest_aliases: sameSampleEvidenceAliasFiles,
    evidence_files: sameSampleEvidenceAliasFiles.map((aliasFileName) => ({
      latest_alias_file: aliasFileName,
      batch_snapshot_file: batchSnapshotFileByAlias[aliasFileName],
    })),
  };
  await fs.writeFile(
    `${evidenceDir}/${batchIndexFileName}`,
    `${JSON.stringify(batchIndexPayload, null, 2)}\n`,
    "utf8",
  );
  await fs.writeFile(
    `${evidenceDir}/${latestBatchIndexAliasFile}`,
    `${JSON.stringify(
      {
        ...batchIndexPayload,
        latest_alias_points_to_batch_index: batchIndexFileName,
      },
      null,
      2,
    )}\n`,
    "utf8",
  );

  await context.close();
});
