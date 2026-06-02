# Stage 6-C0：预检 / 发布门禁职责迁移审计

> 文档类型：只读审计 / migration plan
> 生成日期：2026-06-02
> 执行模型：DeepSeek（Claude Code CLI）
> 状态：完成

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

## 9. Gate 结论

### 9.1 Stage 6-C0 audit: **Pass**

审计完成。preflight / release gate 当前能力、归属判断、迁移风险、最小方案全部整理清楚。

### 9.2 Stage 6-C implementation: **Pending**

等待 Codex 按 7.2 / 7.3 执行最小迁移。

### 9.3 Stage 6-B full implementation: **仍 Partial**

P0（预检 / 发布门禁从审批页分离）在 6-B 审计中被标记为 Deferred，当前审计确认迁移方案，等待 Codex 执行。

### 9.4 AI Project Director total closure: **Partial**（不变）

不满足总闭环条件。

### 9.5 CL-16: **不涉及**

---

## 10. 审查清单

- [x] origin/main commit 已核对：`fdbcdc2`
- [x] 后端 preflight / release-gate 端点已审计（6 个）
- [x] 前端 RepositoryPreflightPanel 已审计（376 行，完整面板）
- [x] 前端 RepositoryReleaseGatePanel 已审计（397 行，完整面板）
- [x] 执行中心 ExecutionRepositoryTab 已审计（含 9 步变更链路，预检/放行判断已占位）
- [x] 导航侧边栏与路由映射已核对（执行中心→执行，成果中心→审批）
- [x] 产品基线归属判断已明确（preflight → 执行中心/仓库工作区，release-gate → 仓库工作区/放行判断）
- [x] 迁移风险已评估（不破坏现有路由、不破坏后端 API）
- [x] 最小迁移方案已给出（P0 移除页签 + P1 嵌入仓库工作区）
- [x] 下一条 Codex 建议已明确
- [x] 未改任何业务代码
- [x] 未改前端/后端/数据库/Worker
- [x] AI Project Director total closure 仍为 Partial
- [x] CL-16 不涉及，未写 Pass
