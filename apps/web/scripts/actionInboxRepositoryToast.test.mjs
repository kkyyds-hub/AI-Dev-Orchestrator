import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const surfacesSource = readFileSync(
  new URL("../src/features/ui-selection-lab/components/WorkbenchUserDecisionSurfaces.tsx", import.meta.url),
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
const actionInboxSource = readFileSync(
  new URL("../src/pages/workbench/components/WorkbenchActionInbox.tsx", import.meta.url),
  "utf8",
);

for (const text of ["成果验收", "通过", "拒绝", "真实执行确认", "会做什么", "风险"]) {
  assert.match(surfacesSource, new RegExp(text), `Action inbox should include ${text}`);
}
assert.match(
  surfacesSource,
  /DialogTrigger asChild/,
  "Action inbox processing should open a compact confirmation dialog",
);
assert.match(
  surfacesSource,
  /<Button variant="secondary">拒绝<\/Button>/,
  "Action inbox confirmation dialog should expose reject action",
);
assert.match(
  surfacesSource,
  /<Button>通过<\/Button>/,
  "Action inbox confirmation dialog should expose pass action",
);
assert.doesNotMatch(
  mockPagesSource,
  /通过<\/Button>|不通过<\/Button>|成果验收动作条|要求修改/,
  "Deliverables center should not grow a separate acceptance action bar",
);
assert.match(
  labPageSource,
  /type ToastStatus = "queued" \| "processing" \| "done" \| "failed"/,
  "Workbench toast should use a small status union",
);
assert.match(
  labPageSource,
  /setTimeout\(\(\) => setToast\(null\), 3000\)/,
  "Workbench toast should fade out after three seconds",
);
for (const status of ["已排队", "处理中", "已完成", "失败"]) {
  assert.match(labPageSource, new RegExp(status), `Toast should include status label ${status}`);
}
assert.match(
  mockPagesSource,
  /Input,/,
  "Repository workspace form should reuse the existing UI Input component",
);
for (const fieldId of ["existingRepositoryPath", "newRepositoryName", "newRepositoryRoot"]) {
  assert.match(
    mockPagesSource,
    new RegExp(`ui-lab-repository-input-${fieldId}`),
    `Repository page should expose editable input field ${fieldId}`,
  );
}
assert.match(
  mockPagesSource,
  /const detailItems = data\?\.detailItems \?\? \[/,
  "Repository page should keep a compact detail list that real adapters can override",
);
assert.match(
  actionInboxSource,
  /function buildSurfaceRoute/,
  "Top action inbox should navigate to shared workbench surfaces",
);
assert.doesNotMatch(
  actionInboxSource,
  /buildRunRoute|buildTaskRoute/,
  "Top action inbox should not route ordinary users to run/task ID detail URLs by default",
);
assert.doesNotMatch(
  actionInboxSource,
  /approvalId=\$\{encodeURIComponent\(item\.related_approval_id\)\}/,
  "Top action inbox should not expose backend approval IDs in ordinary URLs by default",
);
assert.match(
  actionInboxSource,
  /to=\{buildSurfaceRoute\("\/execution", item\.project_id\)\}/,
  "Run/task inbox entries should open the execution surface with project context",
);
assert.match(
  actionInboxSource,
  /to=\{buildSurfaceRoute\("\/delivery", item\.project_id, \{ tab: "approvals" \}\)\}/,
  "Approval inbox entries should open the delivery approvals surface with project context",
);
assert.doesNotMatch(
  mockPagesSource,
  /title: "最近快照"[\s\S]*title: "变更准备"[\s\S]*title: "写入边界"/,
  "Repository page should not keep all backend-like detail sections visible",
);
