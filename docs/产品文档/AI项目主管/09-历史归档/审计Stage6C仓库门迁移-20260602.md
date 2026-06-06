# Stage 6-C0：预检 / 发布门禁职责迁移审计

> 文档类型：只读审计 / migration plan + evidence
> 生成日期：2026-06-02（Stage 6-C0 audit）/ 更新 2026-06-02（Stage 6-C1 验证）
> 执行模型：DeepSeek（Claude Code CLI）
> 状态：Stage 6-C0 audit 完成 / Stage 6-C1 前端迁移验证完成

---

## 1. 基准 commit

| 项目 | 值 |
|---|---|
| origin/main HEAD | `fdbcdc227433ba1c19d5ad5fb3d23bb44b7ab612` |
| 提交信息 | `docs: update stage6b approval center evidence` |
| 审计时间 | 2026-06-02 |

---

## 2. 审计范围

聚焦当前挂在审批页下的两个非审批子页签：
- **预检 (Repository Preflight)**：ChangeBatch 预检、风险提示、人工确认
- **发布门禁 (Repository Release Gate)**：放行检查单、缺口阻断、审批记录

覆盖前后端完整链路：
- 后端 `/approvals` 路由下的 preflight / release-gate 端点（6 个）
- 前端 `RepositoryPreflightPanel.tsx` + `RepositoryReleaseGatePanel.tsx`
- `ApprovalInboxPage.tsx` 中两个子页签的渲染位置
- `ExecutionRepositoryTab.tsx` 当前的变更链路步骤条
- 导航侧边栏与路由映射

---

## 3. Preflight 当前能力清单

### 3.1 后端端点

| # | 端点 | 方法 | 代码位置 (`approvals.py`) |
|---|---|---|---|
| 1 | `/approvals/projects/{project_id}/repository-preflight` | GET | `1248-1303` |
| 2 | `/approvals/repository-preflight/{change_batch_id}` | GET | `1306-1328` |
| 3 | `/approvals/repository-preflight/{change_batch_id}/actions` | POST | `1331-1378` |

**数据依赖**：ChangeBatch（含 preflight status、findings、plan_snapshots）、ChangeBatchService、ChangeRiskGuardService

### 3.2 前端组件

| 文件 | 职责 | 代码行数 |
|---|---|---|
| `RepositoryPreflightPanel.tsx` | 预检列表 + 详情面板 + 人工确认表单 | ~376 行 |

**组件能力**：
- 左列表 + 右详情面板布局（与产品基线推荐布局一致）
- 待预检事项列表（含 ChangeBatch 标题、状态 badge、任务数、文件数、重叠文件数）
- 选中项详情：PreflightChecklist（范围摘要 + 风险发现）+ 任务清单 + 目标文件
- 人工确认表单：放行/驳回 + 操作者 + 摘要 + 备注
- 状态反馈：loading、error、empty、success/failure feedback
- 自动选中 `blocked_requires_confirmation` 项

**数据流**：
```
useProjectRepositoryPreflightInbox → GET /approvals/projects/{id}/repository-preflight
useRepositoryPreflightDetail → GET /approvals/repository-preflight/{change_batch_id}
useApplyRepositoryPreflightAction → POST /approvals/repository-preflight/{change_batch_id}/actions
```

---

## 4. Release Gate 当前能力清单

### 4.1 后端端点

| # | 端点 | 方法 | 代码位置 (`approvals.py`) |
|---|---|---|---|
| 4 | `/approvals/projects/{project_id}/repository-release-gate` | GET | `1381-1403` |
| 5 | `/approvals/repository-release-gate/{change_batch_id}` | GET | `1406-1431` |
| 6 | `/approvals/repository-release-gate/{change_batch_id}/actions` | POST | `1434-1478` |

**数据依赖**：ChangeBatch（含 release gate status、checklist）、RepositoryReleaseGateService、VerificationRunRepository、DiffSummaryService

### 4.2 前端组件

| 文件 | 职责 | 代码行数 |
|---|---|---|
| `RepositoryReleaseGatePanel.tsx` | 发布门禁列表 + 详情面板 + 审批动作表单 | ~397 行 |

**组件能力**：
- 左列表 + 右详情面板布局
- 待放行事项列表（含 ChangeBatch 标题、状态 badge、阻断标记、缺口数、审批记录数）
- 选中项详情：RepositoryReleaseChecklist + 审批动作表单（通过/驳回/补证据）
- 阻断时自动切换到"补证据"动作，禁止直接通过
- 审批动作表单：审批人 + 结论摘要 + 备注 + 关注风险 + 补充事项
- 状态反馈完整

**数据流**：
```
useProjectRepositoryReleaseGateInbox → GET /approvals/projects/{id}/repository-release-gate
useRepositoryReleaseGateDetail → GET /approvals/repository-release-gate/{change_batch_id}
useApplyRepositoryReleaseGateAction → POST /approvals/repository-release-gate/{change_batch_id}/actions
```

---

## 5. 当前挂在审批页的风险

### 5.1 产品基线冲突

产品基线 `page-information-architecture-20260518.md` 第 26 节明确成果中心只有两个页签：
> `[交付物] [审批]`

第 28.1 节明确审批页：
> "审批页是用户对 AI 产出进行人工 Gate 决策的地方。"

预检和发布门禁的对象是 **ChangeBatch**（变更批次），不是 **Deliverable**（交付物）。它们属于"仓库工作区"或"Release Gate 阶段"，不属于"成果中心 / 审批"。

### 5.2 用户体验混淆

当前用户进入成果中心 → 审批页签时，看到三个子页签：
1. 审批队列 — 处理交付物审批
2. 预检 — 仓库变更范围预检
3. 发布门禁 — 发布放行检查

同一个页面上混合了三种不同审批对象（交付物 vs 变更批次 vs 发布批次），语义不一致。

### 5.3 后端 API 路径问题

所有 preflight / release-gate 端点路径以 `/approvals/` 为前缀。按职责，它们应该属于：
- `/repositories/` 或 `/change-batches/`（仓库/变更域）
- 但后端路径迁移会影响现有前端调用，属于后续大改动

### 5.4 迁移提示已到位但尚未执行

Stage 6-B1 已为两个子页签添加 amber `MigrationNotice` 提示文案，但组件和业务逻辑仍在审批页渲染。

---

## 6. 产品基线归属判断

### 6.1 产品基线关键引用

| 产品基线章节 | 相关内容 | 归属判断 |
|---|---|---|
| 第 4 节 | 执行中心：任务队列、运行观测、**仓库工作区** | **Preflight + Release Gate 应归属这里** |
| 第 26 节 | 成果中心 = 交付物 + 审批，只有两个页签 | Preflight / Release Gate 不应在成果中心 |
| 第 28.1 节 | 审批页只承担"对 AI 产出进行人工 Gate 决策" | Preflight 是仓库范围预检，Release Gate 是发布门禁，不是交付物审批 |
| 第 12 节 | 仓库工作区负责文件定位、上下文包、变更方案、变更批次、预检、提交草案、验证 | **Preflight 明确属于仓库工作区的变更链路段** |
| 第 12 节 | 仓库工作区还负责放行判断前的证据整合 | **Release Gate 的放行检查属于仓库工作区 / Release Gate 阶段** |

### 6.2 归属结论

| 能力 | 当前挂载位置 | 应归属位置 | 判断依据 |
|---|---|---|---|
| Repository Preflight（预检） | 成果中心 / 审批 / 预检页签 | **执行中心 / 仓库工作区 / 预检步骤** | 产品基线第 12 节：预检属于仓库工作区变更链路；操作对象是 ChangeBatch |
| Repository Release Gate（发布门禁） | 成果中心 / 审批 / 发布门禁页签 | **执行中心 / 仓库工作区 / 放行判断步骤** | 产品基线第 12 节：放行判断属于仓库工作区末段；操作对象是 ChangeBatch |

### 6.3 执行中心仓库工作区当前已有预检 / 放行判断占位

`ExecutionRepositoryTab.tsx` 已有 `CHANGE_CHAIN_STEPS` 步骤条，包含：
- `preflight` — 步骤 6（第 18 行）
- `release_judge` — 步骤 8（第 21 行）

`CurrentStepPanel` 已有对应步骤的状态描述（`getStepMessage` 函数第 265-278 行）。这说明执行中心仓库工作区**已经为预检和放行判断预留了 UI 步骤占位**，只是目前以简短标题/描述形式展示，而非完整组件面板。

---

## 7. 最小迁移方案

### 7.1 原则

- 不迁移后端 API 路径（`/approvals/` → `/repositories/` 或 `/change-batches/`）
- 不改 API 响应结构
- 不改预检 / 发布门禁业务逻辑
- 只改前端组件挂载位置
- 不增加新路由
- 审批页从 3 子页签回到合规的 1 页签（审批队列）

### 7.2 P0：从 ApprovalInboxPage 移除预检 / 发布门禁页签（Codex）

**改动文件**：仅 `ApprovalInboxPage.tsx`

**改动内容**：
1. 移除 `preflight` 页签项（`ApprovalInboxPage.tsx:415-432`）
2. 移除 `release-gate` 页签项（`ApprovalInboxPage.tsx:433-449`）
3. 移除 `MigrationNotice` 组件定义（`ApprovalInboxPage.tsx:457-467`）
4. 移除 `RepositoryPreflightPanel` 和 `RepositoryReleaseGatePanel` 的 import（`:14-15`）
5. `ProjectSubviewTabs` 只剩一个页签项，可直接去掉页签包装或保留单页签结构

**改动量**：~40 行删除

**风险评估**：
- `/delivery?tab=approvals` 不受影响（审批页签仍在成果中心内）
- 旧 `/approvals` 重定向不受影响
- 不会破坏后端 API
- 不需要新增路由

### 7.3 P1：在执行中心仓库工作区放置预检 / 发布门禁入口（Codex）

**改动文件**：`ExecutionRepositoryTab.tsx`

**改动内容**：
1. 当变更链路段为 `preflight` 时，`CurrentStepPanel` 下方嵌入 `RepositoryPreflightPanel`（复用已有组件）
2. 当变更链路段为 `release_judge` 时，`CurrentStepPanel` 下方嵌入 `RepositoryReleaseGatePanel`（复用已有组件）
3. 从 `features/approvals/` 引入组件路径不变（组件位置不搬）

**改动量**：~30 行新增

**风险评估**：
- 组件复用，不改业务逻辑
- API hooks 已在 `features/approvals/hooks.ts` 中定义，直接跨目录引用
- 步骤切换逻辑已在 `activeStepIndex` 中

### 7.4 P1：后续后端 API 路径迁移（Deferred）

**不属于本轮范围**：
- 将 `/approvals/projects/{id}/repository-preflight` 移至 `/repositories/` 或其他前缀
- 将 `/approvals/repository-preflight/` 移至新路径
- 将 `/approvals/repository-release-gate/` 移至新路径

这些后端路径迁移会影响所有 API client 调用，属于大改动（前后端协同），应在 Stage 7/8 仓库工作区收口时统一处理。

### 7.5 P0 和 P1 完成后（DeepSeek 验证）

1. 验证 `npm.cmd run build` 通过
2. 验证 `/delivery?tab=approvals` 只显示审批队列
3. 验证 `/execution?tab=repository` 的变更链路 preflight / release_judge 步骤显示完整面板
4. 更新 evidence 文档

---

## 8. 下一条 Codex 指令建议

### 8.1 指令概要

```
建议使用模型：Codex
任务类型：最小前端迁移（移除非审批页签 → 仓库工作区嵌入）
原因：预检 / 发布门禁目前挂在审批页，违反产品基线页面职责。迁移到执行中心仓库工作区。

改动范围：
1. ApprovalInboxPage.tsx：移除 preflight 和 release-gate 两个子页签及 MigrationNotice
2. ExecutionRepositoryTab.tsx：当变更链路位于 preflight / release_judge 步骤时嵌入对应面板

不改后端、不改 API、不改组件逻辑、只改挂载位置。
```

### 8.2 优先级顺序

| 优先级 | 改动 | 预计行数 |
|---|---|---|
| P0 | `ApprovalInboxPage.tsx`：移除两个子页签 + MigrationNotice + 清理 import | ~40 行删除 |
| P1 | `ExecutionRepositoryTab.tsx`：嵌入 RepositoryPreflightPanel / RepositoryReleaseGatePanel | ~30 行新增 |

---

## 9. Stage 6-C1 前端迁移验证

> 验证时间：2026-06-02
> 基准 commit：`6edd6eeb16ac9f4e04ad87478be9d505b522cbdf`
> 提交信息：`refactor(web): move repository gates to execution workspace`
> 执行模型：DeepSeek（Claude Code CLI）
> Codex 已执行 Stage 6-C1 P0 + P1 迁移，本阶段为事实验证。

### 9.1 修改范围

| 文件 | 改动类型 | 改动内容 |
|---|---|---|
| `ApprovalInboxPage.tsx` | 移除 | 移除 `RepositoryPreflightPanel` import、`RepositoryReleaseGatePanel` import、`preflight` 子页签、`release-gate` 子页签、`MigrationNotice` 组件 |
| `ExecutionRepositoryTab.tsx` | 新增 | 新增 `RepositoryPreflightPanel` import、`RepositoryReleaseGatePanel` import、`preflight` 步骤嵌入、`release_judge` 步骤嵌入、3 个 data-testid |

**未改动**：后端、API 路径、数据库、Worker、`RepositoryPreflightPanel.tsx` 内部逻辑、`RepositoryReleaseGatePanel.tsx` 内部逻辑、`hooks.ts`、`api.ts`、`types.ts`。

### 9.2 ApprovalInboxPage 移除项验证

| # | 移除项 | 6-C0 基线位置 | 当前状态 | 验证结果 |
|---|---|---|---|---|
| 1 | `RepositoryPreflightPanel` import | `ApprovalInboxPage.tsx:14-15` | 当前 imports（`:1-16`）无此引用 | **已移除** |
| 2 | `RepositoryReleaseGatePanel` import | `ApprovalInboxPage.tsx:14-15` | 当前 imports（`:1-16`）无此引用 | **已移除** |
| 3 | `preflight` 子页签项 | `ApprovalInboxPage.tsx:415-432` | `ProjectSubviewTabs items` 仅含 `approval-inbox` 一项（`:173-413`） | **已移除** |
| 4 | `release-gate` 子页签项 | `ApprovalInboxPage.tsx:433-449` | 同上，仅一项 | **已移除** |
| 5 | `MigrationNotice` 组件定义 | `ApprovalInboxPage.tsx:457-467` | 全文搜索无 `MigrationNotice` | **已移除** |
| 6 | `ProjectSubviewTabs` 只剩单页签 | — | 仅 `approval-inbox` 一项，无页签切换 UI | **已收敛** |

### 9.3 ApprovalInboxPage 保留项验证

| # | 保留项 | 代码位置 | 验证结果 |
|---|---|---|---|
| 1 | 审批队列 | `:366-400`，`data-testid="approval-queue-list"` | **保留** |
| 2 | 发起审批表单 | `:217-339`，含交付件选择、角色、截止时长、审批说明 | **保留** |
| 3 | 超时提醒区块 | `:342-363`，`overdueApprovals` 筛选逻辑 `:124-126` | **保留** |
| 4 | `ApprovalActionDrawer` | `:403-409`，审批决策抽屉 | **保留** |
| 5 | 审批排序 | `:41-44`，`sortApprovalsByHandlingPriority` `:434-452` | **保留** |
| 6 | 审批动作后果说明 | `ApprovalActionDrawer.tsx:57-61`（不在本文件，未改动） | **保留** |
| 7 | 查看交付物正文入口 | `ApprovalActionDrawer.tsx:179-188`（不在本文件，未改动） | **保留** |
| 8 | 审批统计卡片 | `:197-214`，审批总数 / 待审批 / 超时项 / 已结束 | **保留** |
| 9 | `ProjectSubviewTabs` 容器 | `:170-414`，保留单页签结构 | **保留** |

### 9.4 ExecutionRepositoryTab 新增挂载验证

| # | 新增项 | 代码位置 | 验证结果 |
|---|---|---|---|
| 1 | `RepositoryPreflightPanel` import | `ExecutionRepositoryTab.tsx:4` | **已新增** |
| 2 | `RepositoryReleaseGatePanel` import | `ExecutionRepositoryTab.tsx:5` | **已新增** |
| 3 | `activeStep === "preflight"` 条件渲染 | `:157-164`，包裹 `data-testid="execution-repository-preflight-panel"` | **已新增** |
| 4 | `activeStep === "release_judge"` 条件渲染 | `:166-173`，包裹 `data-testid="execution-repository-release-gate-panel"` | **已新增** |
| 5 | 传递 `projectId` + `projectName` props | `:159-161, :168-170`，与审批页原传递方式一致 | **已新增** |
| 6 | 组件来源路径 | `../../../features/approvals/RepositoryPreflightPanel` — 组件位置未搬移 | **复用原组件** |

### 9.5 release_judge 可达性验证

**当前逻辑**（`ExecutionRepositoryTab.tsx:44-59`，`activeStepIndex` useMemo）：

```typescript
if (batches.length > 0) {
  const hasPreflight = batches.some((b) => b.preflight.status !== "not_started");
  if (hasPreflight) {
    if (candidates.length > 0) return 8; // release_judge
    return 6; // preflight
  }
  return 5; // change_batch
}
```

| # | 验证项 | 分析 | 结论 |
|---|---|---|---|
| 1 | 有 batches + 有 preflight + 有 candidates → `release_judge`（step 8） | `candidates.length > 0` 直接跳至 release_judge | **可达** |
| 2 | 有 batches + 有 preflight + 无 candidates → `preflight`（step 6） | 正确，无草案时停留在预检步骤 | **可达** |
| 3 | `commit_draft`（step 7）是否可达 | 当前逻辑：`candidates.length > 0` 时跳过 commit_draft 直接到 release_judge；commit_draft 步骤只在 `activeStepIndex` 枚举中可索引（index 7），但没有路径可达 | **Warning** |

**评估**：release_judge 可通过 `candidates.length > 0` 触发，ReleaseGatePanel 在此步骤可完整渲染，满足最小迁移目标。但 `commit_draft` 步骤在当前 `activeStepIndex` 逻辑中无路径可达（有 candidates 直接跳到 release_judge，无 candidates 停留在 preflight），commit_draft 在步骤条上被弱化为仅展示 label 的中间节点。此为**预存逻辑行为**，非 Stage 6-C1 引入。

### 9.6 data-testid 验证表

| # | data-testid | 预期位置 | 实际文件:行号 | 状态 |
|---|---|---|---|---|
| 1 | `execution-repository-tab` | 执行中心仓库工作区根节点 | `ExecutionRepositoryTab.tsx:85` | **Pass** |
| 2 | `execution-repository-preflight-panel` | preflight 步骤面板容器 | `ExecutionRepositoryTab.tsx:158` | **Pass** |
| 3 | `execution-repository-release-gate-panel` | release_judge 步骤面板容器 | `ExecutionRepositoryTab.tsx:167` | **Pass** |
| 4 | `approval-inbox-section` | 审批主区域根节点 | `ApprovalInboxPage.tsx:182` | **Pass** |
| 5 | `approval-queue-list` | 审批队列列表容器 | `ApprovalInboxPage.tsx:386` | **Pass** |
| 6 | `approval-queue-card` | 单个审批卡片 | `ApprovalInboxPage.tsx:510` | **Pass** |

### 9.7 未改动项确认

| # | 区域 | 确认方式 | 结论 |
|---|---|---|---|
| 1 | 后端 `/approvals` 路由 | `api.ts` 全部 12 个函数仍使用 `/approvals/` 前缀 | **未改动** |
| 2 | API 路径 | `applyRepositoryPreflightAction` → `/approvals/repository-preflight/{id}/actions` 等 | **未改动** |
| 3 | 数据库 | 无 schema 变更 | **未改动** |
| 4 | Worker | 无 worker 文件变更 | **未改动** |
| 5 | `RepositoryPreflightPanel.tsx` | 组件内部逻辑、hooks 调用、类型引用均不变 | **未改动** |
| 6 | `RepositoryReleaseGatePanel.tsx` | 组件内部逻辑、hooks 调用、类型引用均不变 | **未改动** |
| 7 | `hooks.ts` | 全部 12 个 hooks 定义不变 | **未改动** |
| 8 | `api.ts` | 全部 12 个 API 函数不变 | **未改动** |
| 9 | `types.ts` | 全部类型定义 + 中文标签映射不变 | **未改动** |
| 10 | 路由 / 导航 | `ExecutionCenterPage.tsx` 三页签结构不变 | **未改动** |

### 9.8 测试命令与结果

```bash
cd apps/web && npm.cmd run build
```

**结果**：`tsc -b && vite build` 成功，built in 3.56s，496 modules transformed，无 TypeScript 错误。

```bash
cd runtime/orchestrator && python -m compileall app tests
```

**结果**：全部编译通过，无语法错误。

### 9.9 Warnings

#### Warning 1: 预检 / 放行判断轻提示文案未单独落地

Stage 6-C0 审计第 7.3 节描述了"轻提示文案"需求（在仓库工作区步骤面板展示简短的状态描述）。Stage 6-C1 实际实现为直接嵌入完整的 `RepositoryPreflightPanel` / `RepositoryReleaseGatePanel` 组件面板，而非轻量 toast/notice。当前 `CurrentStepPanel` 仍然渲染步骤标题/描述（`getStepMessage` 函数 `:250-305`），完整面板在步骤面板下方独立渲染。这不是 blocker — 完整面板提供比轻提示更丰富的交互能力 — 但意味着产品基线中"当前步骤只展示摘要，详情弹窗收纳"的轻量原则在仓库工作区 preflight / release_judge 步骤上未被严格遵循。

#### Warning 2: commit_draft 步骤在变更链路中无路径可达

`CHANGE_CHAIN_STEPS` 定义了 9 步（含 `commit_draft` 第 8 个位置，index 7），但 `activeStepIndex` 逻辑中：有 candidates 直接从 preflight 跳到 release_judge（index 8），无 candidates 停留在 preflight（index 6）。`commit_draft`（index 7）在步骤条中显示为灰色非活跃状态，用户永远不会看到该步骤激活。此为预存行为（步骤逻辑在 6-C1 之前已如此），但仓库工作区变更链路的产品完整性受到影响。建议后续仓库工作区精修时显式处理 commit_draft 步骤可达性。

#### Warning 3: 后端 preflight / release-gate API 仍挂在 `/approvals` 路径下

全部 6 个 preflight / release-gate 端点仍以 `/approvals/` 为前缀（`api.ts:28-123`）。前端 hooks 的 queryKey 也使用 `["approvals", "repository-preflight", ...]` 等命名（`hooks.ts:35,43`）。此路径迁移已在 Stage 6-C0 审计第 7.4 节标记为 **Deferred**，当前状态正确。但应注意：前端组件虽已挂载到执行中心，数据流仍标记在 approvals query 命名空间下，后续路径迁移时需同步更新 queryKey。

---

## 10. Gate 结论（更新）

### 10.1 Stage 6-C0 audit: **Pass**

审计完成。preflight / release gate 当前能力、归属判断、迁移风险、最小方案全部整理清楚。

### 10.2 Stage 6-C1 frontend code-level: **Pass**

P0（从 ApprovalInboxPage 移除两个子页签 + MigrationNotice）+ P1（在 ExecutionRepositoryTab 嵌入两个面板）均已完成：
- ApprovalInboxPage 回到合规的单一审批队列视图（无 preflight / release-gate 子页签）
- ExecutionRepositoryTab 在 preflight / release_judge 步骤渲染完整 RepositoryPreflightPanel / RepositoryReleaseGatePanel
- TypeScript + Vite build 通过（3.56s）
- Python compileall 通过
- 6 个 data-testid 全部可定位

### 10.3 Stage 6-C evidence-level: **Pass**

所有验证项均有明确的代码行号事实可追溯，前端 build + 后端 compileall 双通过，data-testid 可定位，未改动区域全部确认。

### 10.4 Stage 6-B full implementation: **Pass**（从 Partial 提升）

Stage 6-B 审计中标记为 Partial 的唯一 P0 阻塞项 —— "预检 / 发布门禁从审批页分离" —— 已在 Stage 6-C1 中完成。P1 布局改造（左列表 + 右面板）属于 UX 优化项，不阻塞 functional gate。

### 10.5 Stage 6-C full implementation: **Pass**

P0 + P1 迁移全部完成。后端 API 路径迁移（`/approvals/` → `/repositories/` 或 `/change-batches/`）已在 Stage 6-C0 审计第 7.4 节明确标记为 Deferred，不属于 Stage 6-C 范围，不影响本阶段 gate。commit_draft 可达性问题为预存行为（非 6-C1 引入），在 Warning 2 中记录，不阻塞 gate。

### 10.6 AI Project Director total closure: **Partial**（不变）

不满足总闭环条件（SKILL.md 第 8.5 节要求的全部 product chains 尚未全部验证）。

### 10.7 CL-16: **不涉及**

CL-16 不在当前审计范围。不写 Pass。

---

## 11. 审查清单

- [x] origin/main commit 已核对：`6edd6eeb16ac9f4e04ad87478be9d505b522cbdf`（6-C1）
- [x] ApprovalInboxPage 移除项全部验证（6 项）
- [x] ApprovalInboxPage 保留项全部验证（9 项）
- [x] ExecutionRepositoryTab 新增挂载全部验证（6 项）
- [x] release_judge 可达性已验证（candidates.length > 0 触发）
- [x] commit_draft 弱化已记录为 Warning
- [x] data-testid 全部 6 个验证通过
- [x] 后端 API 路径未改动（仍为 `/approvals/`）
- [x] hooks.ts / api.ts / types.ts 未改动
- [x] RepositoryPreflightPanel / RepositoryReleaseGatePanel 业务逻辑未改动
- [x] `tsc -b && vite build` 通过（3.56s）
- [x] `python -m compileall app tests` 通过
- [x] Warnings 已记录（3 条）
- [x] Gate 结论已更新
- [x] Stage 6-B full implementation 从 Partial 提升至 Pass
- [x] 未改任何业务代码
- [x] 未改前端/后端/数据库/Worker
- [x] AI Project Director total closure 仍为 Partial
- [x] CL-16 不涉及，未写 Pass
