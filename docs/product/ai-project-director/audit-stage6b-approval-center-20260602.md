# Stage 6-B0：成果中心审批页现状审计

> 文档类型：只读审计 / gap analysis
> 生成日期：2026-06-02
> 执行模型：DeepSeek（Claude Code CLI）
> 状态：完成

---

## 1. 基准 commit

| 项目 | 值 |
|---|---|
| origin/main HEAD | `80344cdb0e000e1011f0ebbb6d6d8cedba96c3b8` |
| 提交信息 | `docs: update stage6a deliverable evidence verification` |
| 审计时间 | 2026-06-02 |

---

## 2. 审计范围

本次审计覆盖审批相关的全部前后端能力：

- 后端 `/approvals` 路由全部 14 个端点
- 前端 `ApprovalInboxPage.tsx`（审批入口页，含 3 个子页签）
- 前端 `ApprovalActionDrawer.tsx`（审批决策抽屉）
- 前端 `DeliveryCenterPage.tsx`（成果中心页，交付物/审批 双页签）
- 前端 `ApprovalsPage.tsx`（旧路由重定向）
- 前端 `approval-route.ts`（审批路由构建）
- 前端类型定义 `approvals/types.ts`

以产品基线 `page-information-architecture-20260518.md` 第 28 节（审批页设计）为对照标准。

---

## 3. 现有审批后端 API 清单

| # | 端点 | 方法 | 职责分类 | 文件:行号 | 状态 |
|---|---|---|---|---|---|
| 1 | `/approvals` | POST | **审批核心** — 创建审批请求 | `approvals.py:1193-1224` | 已实现 |
| 2 | `/approvals/projects/{project_id}` | GET | **审批核心** — 项目审批 inbox | `approvals.py:1227-1245` | 已实现 |
| 3 | `/approvals/{approval_id}` | GET | **审批核心** — 审批详情 | `approvals.py:1687-1705` | 已实现 |
| 4 | `/approvals/{approval_id}/actions` | POST | **审批核心** — 应用审批决策 | `approvals.py:1708-1741` | 已实现 |
| 5 | `/approvals/{approval_id}/history` | GET | **审批核心** — 审批回放历史 | `approvals.py:1659-1684` | 已实现 |
| 6 | `/approvals/projects/{project_id}/repository-preflight` | GET | **预检（混入）** — 仓库预检 inbox | `approvals.py:1248-1303` | 已实现 — 不在审批页职责内 |
| 7 | `/approvals/repository-preflight/{change_batch_id}` | GET | **预检（混入）** — 预检详情 | `approvals.py:1306-1328` | 已实现 — 不在审批页职责内 |
| 8 | `/approvals/repository-preflight/{change_batch_id}/actions` | POST | **预检（混入）** — 应用预检决策 | `approvals.py:1331-1378` | 已实现 — 不在审批页职责内 |
| 9 | `/approvals/projects/{project_id}/repository-release-gate` | GET | **发布门禁（混入）** — 发布门禁 inbox | `approvals.py:1381-1403` | 已实现 — 不在审批页职责内 |
| 10 | `/approvals/repository-release-gate/{change_batch_id}` | GET | **发布门禁（混入）** — 门禁详情 | `approvals.py:1406-1431` | 已实现 — 不在审批页职责内 |
| 11 | `/approvals/repository-release-gate/{change_batch_id}/actions` | POST | **发布门禁（混入）** — 应用门禁决策 | `approvals.py:1434-1478` | 已实现 — 不在审批页职责内 |
| 12 | `/approvals/projects/{project_id}/day15-release-judgement` | GET | **发布门禁（混入）** — Day15 放行判断 | `approvals.py:1481-1611` | 已实现 — 不在审批页职责内 |
| 13 | `/approvals/projects/{project_id}/retrospective` | GET | **项目回顾** — 审批 + 失败回顾 | `approvals.py:1614-1632` | 已实现 |
| 14 | `/approvals/projects/{project_id}/change-rework` | GET | **返工追踪** — 变更返工链 | `approvals.py:1635-1656` | 已实现 |

### 3.1 职责分类统计

| 分类 | 端点数 | 属于审批页职责 |
|---|---|---|
| 审批核心 | 5 | 是 |
| 预检（repository preflight） | 3 | **否** — 应属于仓库工作区 |
| 发布门禁（release gate） | 3 | **否** — 应属于 release gate 阶段 |
| 项目回顾 + 返工 | 2 | 边缘 — 治理/回顾视角 |

---

## 4. 现有审批前端页面 / 组件清单

### 4.1 页面入口与路由

| 文件 | 职责 | 状态 |
|---|---|---|
| `DeliveryCenterPage.tsx` | 成果中心双页签：交付物 / 审批 | 已实现 — 符合产品基线双页签结构 |
| `ApprovalsPage.tsx` | 旧审批路由 → 重定向到 `/delivery?tab=approvals` | 已实现 — 正确的重定向 |
| `approval-route.ts` | 构建审批 URL（`/approvals?projectId=...&approvalId=...`） | 已实现 |

### 4.2 审批页主体

| 文件 | 职责 | 状态 |
|---|---|---|
| `ApprovalInboxPage.tsx` | 审批主页面，含 3 个子页签 + 发起审批表单 + 超时提醒 + 审批队列 + 审批抽屉 | 已实现 — **但混入预检和发布门禁页签** |

### 4.3 子页签（ApprovalInboxPage 内部）

| 页签 ID | 标签 | 组件 | 是否属于审批页 |
|---|---|---|---|
| `approval-inbox` | 审批队列 | 审批队列 + 发起审批表单 + 超时提醒 + `ApprovalActionDrawer` | 是 |
| `preflight` | 预检 | `RepositoryPreflightPanel` | **否** — 仓库工作区职责 |
| `release-gate` | 发布门禁 | `RepositoryReleaseGatePanel` | **否** — release gate 阶段职责 |

### 4.4 审批决策与辅助组件

| 组件 | 文件 | 职责 | 状态 |
|---|---|---|---|
| `ApprovalActionDrawer` | `ApprovalActionDrawer.tsx` | 审批决策抽屉：交付件快照、请求说明、动作选择（通过/驳回/要求修改）、决策人/结论/补充说明/风险/补充项表单、审批回放记录、证据面板、历史面板 | 已实现 |
| `ChangeEvidencePanel` | `deliverables/ChangeEvidencePanel.tsx` | 代码变更证据包展示 | 已实现 |
| `ApprovalHistoryPanel` | `ApprovalHistoryPanel.tsx` | 审批历史回放面板 | 已实现 |
| `RepositoryPreflightPanel` | `RepositoryPreflightPanel.tsx` | 仓库预检面板（混入） | 已实现 — 不在审批页职责内 |
| `RepositoryReleaseGatePanel` | `RepositoryReleaseGatePanel.tsx` | 发布门禁面板（混入） | 已实现 — 不在审批页职责内 |

### 4.5 API 层

| 文件 | 提供的 API 调用 | 状态 |
|---|---|---|
| `approvals/api.ts` | 12 个 API 函数，覆盖审批、预检、发布门禁、回顾、返工 | 已实现 |
| `approvals/hooks.ts` | React Query hooks | 已实现 |
| `approvals/types.ts` | 完整类型定义 + 中文标签映射 | 已实现 |

---

## 5. 与产品基线差距表

产品基线参考：`docs/product/ai-project-director/page-information-architecture-20260518.md`
- 第 28 节：审批页设计
- 第 26 节：成果中心整体结构（交付物 / 审批双页签）

| # | 产品基线要求 | 当前实现 | 差距 | 优先级 |
|---|---|---|---|---|
| 1 | 审批页只承担"人工 Gate 决策" | `ApprovalInboxPage` 混入预检和发布门禁两个子页签（`ApprovalInboxPage.tsx:411-432`） | 预检和发布门禁不属于审批页职责，应从审批页分离 | **P0** |
| 2 | 审批页布局：左侧审批轻列表 + 右侧决策面板 | 当前：发起审批表单 + 超时提醒 + 审批队列（上下排列），决策通过抽屉弹出 | 布局未匹配产品基线，但功能可用。可作为 P1 UX 优化 | P1 |
| 3 | 审批按钮必须说明后果 | 通过/驳回/要求修改 各有描述文案（`ApprovalActionDrawer.tsx:52-63`） | **已满足** | — |
| 4 | 能从交付物页跳转审批并定位 | URL 参数 `approvalId` 支持定位（`DeliveryCenterPage.tsx:24`），`ApprovalsPage.tsx` 重定向保留参数 | **已满足** | — |
| 5 | 能从审批页回看交付物正文 / 证据 / 版本 | `ApprovalActionDrawer` 仅展示 `ChangeEvidencePanel`（代码证据包）+ `ApprovalHistoryPanel`（审批历史） | **缺少直接跳转到交付物正文/版本的入口** | P1 |
| 6 | 审批决策面板只展示审批相关信息 | `ApprovalActionDrawer` 展示：交付件快照、请求说明、动作选择、决策表单、回放记录、证据、历史 | **已满足** | — |
| 7 | 审批列表排序：待我审批优先 | `ApprovalInboxPage` 审批队列按 `requested_at` 倒序，超时项独立展示 | **缺乏按处理优先级排序**（如 `pending_approval > overdue > decided`） | P1 |
| 8 | 不管理完整成果库 | 移交 `ApprovalsPage` → 重定向到 `/delivery`，正确的职责分离 | **已满足** | — |
| 9 | 空态 / loading / error 反馈 | 审批队列有空态、loading、error 状态（`ApprovalInboxPage.tsx:377-397`）；抽屉有 loading/error（`ApprovalActionDrawer.tsx:137-144`） | **已满足** | — |
| 10 | 高风险放行动作说明后果 | 审批按钮有描述性文案 | **部分满足** — 建议更明确说明通过后"下一阶段将自动推进" | P1 |
| 11 | 假按钮 | 所有按钮调用真实 API：发起审批 → `POST /approvals`，处理审批 → `POST /approvals/{id}/actions`，查看回放 → `GET /approvals/{id}` | **无假按钮** | — |

---

## 6. 风险点

### 6.1 预检 / 发布门禁混入审批页（P0）

**现状**：`ApprovalInboxPage.tsx:168-433` 使用 `ProjectSubviewTabs` 在审批页内创建三个页签：
1. `审批队列` — 正确
2. `预检` — 错误：应属于仓库工作区（执行中心 / 仓库工作区）
3. `发布门禁` — 错误：应属于 Release Gate 阶段

**影响**：
- 违反了产品基线"审批页只承担 Gate 决策"的页面职责
- 用户进入审批页后发现三个不同概念，混淆审批对象（交付物 vs 变更批次）
- 后端 `/approvals` 路由下挂载了 `repository-preflight` 和 `repository-release-gate` 端点是历史遗留

**不需要本轮大改**：这些子页签的后端逻辑和前端组件已完整实现，只是挂载位置不对。建议标记为 Deferred 迁移项，不在 Stage 6-B 范围内大动。

### 6.2 审批决策缺少检查单后果说明（P1）

**现状**：`ApprovalActionDrawer.tsx:52-63` 提供了动作描述文案，但缺少：
- 通过后的具体后果（如"此版本将标记为已批准，下一阶段可基于通过结论推进。"）
- 驳回后的具体后果（如"此版本将被关闭，需要提交新版本后重新发起审批。"）
- 要求修改后的具体后果（如"会创建返工任务，由对应角色处理修改后再重新发起审批。"）

产品基线第 28.5 节明确要求每个按钮说明后果。

### 6.3 无直接跳转到交付物查看正文 / 证据 / 版本的入口（P1）

**现状**：`ApprovalActionDrawer` 有 `ChangeEvidencePanel`（代码变更证据）和 `ApprovalHistoryPanel`（审批历史），但缺少直接的"查看交付物正文"或"查看交付物版本记录"按钮。

审批决策人需要看到交付物正文来做决策，目前需要通过交付物页签切换过去查看。

---

## 7. 下一条 Codex 最小实现建议

### 7.1 P0：预检 / 发布门禁从审批页分离（Deferred）

**结论**：不做本轮改动。

预检和发布门禁的完整前后端已实现。将它们从审批页分离需要：
- 修改 `ApprovalInboxPage.tsx` 移除两个子页签
- 找到或创建预检/发布门禁的独立页面入口
- 可能涉及导航栏调整

这超出了 Stage 6-B "审批页收口"的边界，应作为独立迁移任务（建议标记为 Stage 7/8 仓库工作区收口时处理）。

**本轮最小处理**：在审批页文案中标记预检和发布门禁为"仓库工作区视角，不属于成果中心审批；后续版本迁移至执行中心。"

### 7.2 P1：审批列表按处理优先级排序（Codex）

**建议模型**：Codex
**改动范围**：仅 `ApprovalInboxPage.tsx`
**目标**：
- 审批队列排序改为 `pending_approval (overdue) > pending_approval (not overdue) > changes_requested > rejected > approved`
- 同状态按 `requested_at` 倒序
- 超时项继续保持独立区块展示

### 7.3 P1：审批动作增加后果说明文案（Codex）

**建议模型**：Codex
**改动范围**：仅 `ApprovalActionDrawer.tsx` 的 `selectedActionDescription`
**目标**：
- `approve`：除"确认该版本可以通过审批"外，补充"通过后此版本将标记为已批准，下游可基于此版本继续推进。"
- `reject`：补充"驳回后此版本将被关闭。如需继续，请提交新版本后重新发起审批。"
- `request_changes`：补充"将自动创建返工任务，由对应角色处理后重新提交版本再发起审批。"

### 7.4 P1：审批抽屉增加"查看交付物正文"入口（Codex）

**建议模型**：Codex
**改动范围**：`ApprovalActionDrawer.tsx`，增加一个链接/按钮跳转到交付物详情
**目标**：
- 在审批抽屉的"交付件快照"区域增加"查看交付物正文"按钮
- 点击后切换到成果中心 / 交付物页签并定位到对应交付物，或打开交付物正文弹窗

### 7.5 P1：审批页布局改造为左列表 + 右决策面板（Codex）

**建议模型**：Codex
**改动范围**：`ApprovalInboxPage.tsx` 主体布局
**目标**：
- 将当前"发起审批表单 + 超时提醒 + 审批队列"的纵向布局改为左侧审批队列 + 右侧决策面板
- 决策面板默认显示当前选中审批项的摘要，无需再打开抽屉
- 发起审批表单可通过抽屉或顶部折叠区展开

**注意**：这是最大的单次改动，建议优先完成 7.2-7.4 后再做。

### 7.6 Evidence 验证（DeepSeek）

在 Codex 完成以上修改后，DeepSeek 需要：
- 验证所有审批端点仍可通过测试
- 运行前端 build
- 更新 6-B evidence 文档

---

## 8. Gate 结论

### 8.1 Stage 6-B0 audit: **Pass**

审计完成。现有审批前后端能力完整，主要差距已识别：
- P0：预检/发布门禁混入（标记为 Deferred，不在本轮处理）
- P1：排序、后果说明、查看正文入口、布局

### 8.2 Stage 6-B implementation: **Pending**

等待 Codex 按 7.2-7.5 执行最小实现。

### 8.3 AI Project Director total closure: **Partial**（不变）

不满足总闭环条件。

### 8.4 CL-16: **不涉及**

CL-16 不在当前审计范围。不写 Pass。

---

## 9. 审查清单

- [x] origin/main commit 已核对：`80344cd`
- [x] 后端审批 API 全部 14 个端点已审计
- [x] 前端审批页面/组件全部 7 个文件已审计
- [x] 产品基线对照表已完成（11 项）
- [x] 风险点已识别（3 项）
- [x] 下一条 Codex 实现建议已明确（5 项，含优先级）
- [x] 未改任何业务代码
- [x] 未改前端/后端/数据库/Worker
- [x] AI Project Director total closure 仍为 Partial
- [x] CL-16 不涉及，未写 Pass
