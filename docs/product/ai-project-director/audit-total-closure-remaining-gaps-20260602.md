# AI Project Director 总闭环剩余缺口审计

> 文档类型：只读审计 / gap analysis
> 生成日期：2026-06-02
> 执行模型：DeepSeek（Claude Code CLI）
> 基准 commit：`b23a0da4f26133ca981a84ae38e52d35fc5c45ca`
> 状态：完成

---

## 1. 基准 commit

| 项目 | 值 |
|---|---|
| origin/main HEAD | `b23a0da4f26133ca981a84ae38e52d35fc5c45ca` |
| 提交信息 | `docs: verify stage6d repository commit draft reachability` |
| 审计时间 | 2026-06-02 |

---

## 2. 已完成阶段清单

| 阶段 | 文档 | Gate 结论 | 覆盖范围 |
|---|---|---|---|
| Stage 4 | `verification-stage4-ai-project-director-project-creation-closure-20260531.md` | **Pass** | 目标澄清→计划生成→草案审核→正式项目+Task 队列创建→4 类配置项确认→setup-readiness 总览。48 tests pass。 |
| Stage 6-A | `verification-stage6a-deliverable-center-20260602.md` | **Pass** | 成果中心交付物页：后端兼容合同（6 端点）、EvidenceProjector 最小推导、前端摘要面板。9 tests pass。 |
| Stage 6-B | `audit-stage6b-approval-center-20260602.md` | **Pass**（6-C1 后从 Partial 提升） | 成果中心审批页：审批队列、发起审批、ApprovalActionDrawer、审批排序、后果文案、超时提醒、查看交付物正文入口。 |
| Stage 6-C | `audit-stage6c-repository-gate-migration-20260602.md` | **Pass** | 预检/发布门禁从审批页迁移到执行中心仓库工作区。P0 移除+P1 嵌入完成。 |
| Stage 6-D1 | `verification-stage6d-repository-commit-draft-20260602.md` | **Pass** | commit_draft 步骤可达性修复 + 人工确认门控。 |

---

## 3. 闭环节点状态总表（对照 SKILL.md §8.5）

按 SKILL.md 第 8.5 节"AI Project Director total closure rule"列出的全部 product chains，逐一标定当前证据状态：

| # | Chain | SKILL.md 要求 | 当前证据 | 状态 |
|---|---|---|---|---|
| 1 | goal / plan | 目标澄清 + 计划生成 | CL-01~04 Runtime Pass，Stage 4 全链路 | **Pass** |
| 2 | task creation | 任务队列创建 | CL-07 Runtime Pass，Stage 4 已验证 | **Pass** |
| 3 | worker run | Worker 调度 + 运行 | CL-08 Runtime Pass（**simulate-only**） | **Partial** |
| 4 | run logs | Run 日志 | CL-09 Runtime Pass（**simulate-only**） | **Partial** |
| 5 | AI summary | AI 运行摘要 | CL-10 Runtime Pass（**simulate-only**） | **Partial** |
| 6 | deliverable | 交付物生成 | CL-13 Runtime Pass + Stage 6-A Pass | **Pass** |
| 7 | approval | 审批决策 | CL-14 Runtime Pass + Stage 6-B Pass | **Pass** |
| 8 | rework chain | 返工链路 | CL-11 + CL-14 Runtime Pass | **Pass** |
| 9 | repository binding | 仓库绑定 | CL-12 Runtime Pass。Stage 4 仓库绑定配置 confirmed 为"仅确认快照" | **Partial** |
| 10 | snapshot | 仓库快照 | ExecutionRepositoryTab 展示快照状态，但无独立端到端验证 | **Partial** |
| 11 | file locator | 文件定位器 | 后端 API 存在（`/repositories/{id}/files/search`），前端 hooks 已定义，无独立 stage 验证 | **Partial** |
| 12 | context pack | 上下文包 | 后端 API 存在（`/repositories/{id}/code-context-pack`），无独立 stage 验证 | **Partial** |
| 13 | change plan | 变更方案 | 后端 API 存在，CL-12 chain 包含但无独立前端验收 | **Partial** |
| 14 | change batch | 变更批次 | 后端 API 存在，ExecutionRepositoryTab 展示批次数量，无完整面板验证 | **Partial** |
| 15 | preflight | 预检 | Stage 6-C 前端面板挂载完成；后端 API 存在；**无真实数据流验证** | **Partial** |
| 16 | commit candidate | 提交草案 | Stage 6-D1 前端面板可达；后端 API 存在；**无真实数据流验证** | **Partial** |
| 17 | release gate | 放行判断 | Stage 6-C 前端面板挂载完成；后端 API 存在；**无真实数据流验证** | **Partial** |
| 18 | governance | 治理中心 | CL-15 Runtime Pass。GOV-04~GOV-10 多项 Partial（沉淀闭环缺后端） | **Partial** |
| 19 | cost telemetry | 成本台账 | CL-16 **Evidence Partial**（全部 heuristic，无 real provider 成本） | **Partial** |
| 20 | rollup | 总汇总判断 | 无任何 rollup/总览端点或页面实现 | **Missing** |
| 21 | frontend integration | 前端集成 | Stage 6-C/6-D1 覆盖执行中心+审批页；工作台/项目页多项未验证 | **Partial** |
| — | apply-local / git-commit | 显式不在 scope | SKILL.md 明确"if in scope"，当前产品明确不允许 | **N/A** |

---

## 4. 剩余 Blocker 表

按阻塞严重程度排列。每个缺口标注是否可 Deferred。

### 4.1 真实 Provider 运行态证据（Blocker #1）

| 字段 | 值 |
|---|---|
| 缺口编号 | GAP-01 |
| 所属链路 | Worker Run / Run Logs / AI Summary / Cost Telemetry（#3, #4, #5, #19） |
| 当前证据 | simulate-only：`WORKER_SIMULATE_EXECUTION_OVERRIDE=1` 下全部通过；CL-16 成本全部 heuristic |
| 阻塞原因 | SKILL.md §8.1 要求 "real API or real service path is used"。当前所有 Worker/Run/AI Summary 证据均来自 simulate 模式。simulate 通过 = 代码路径正确，但 **不等于真实 AI provider 调用可行**。total closure 要求 "real persisted data is read back" 中的 "real" 指通过真实 provider 生成的数据。 |
| 建议模型 | Codex（如需修复 provider 集成）+ DeepSeek（evidence 验证） |
| 是否需要真实运行 | **是** — 需要配置真实 AI provider、启动 Worker、执行真实 Run 并产生真实 summary/cost |
| 是否可 Deferred | **否** — 这是 total closure 的核心前提 |

### 4.2 仓库工作区完整端到端数据流（Blocker #2）

| 字段 | 值 |
|---|---|
| 缺口编号 | GAP-02 |
| 所属链路 | Repository Binding / Snapshot / File Locator / Context Pack / Change Plan / Change Batch / Preflight / Commit Candidate / Release Gate（#9~#17） |
| 当前证据 | 后端 API 全部存在；前端面板（preflight/commit_draft/release_judge）已挂载；hooks/types 已定义。但**无任何 stage 验证了从 repository binding → snapshot → file locator → context pack → change plan → change batch → preflight → commit candidate → release gate 的完整真实数据流**。 |
| 阻塞原因 | 仓库工作区是产品基线第 12 节定义的核心页面。9 步变更链路（`CHANGE_CHAIN_STEPS`）的前端步骤条和面板已完整，但缺少真实 ChangeBatch 数据下的端到端验证。当前只有"面板能渲染"的证据，没有"面板能正确响应真实数据"的证据。 |
| 建议模型 | Codex（如需修复变更链路数据流）+ DeepSeek（evidence） |
| 是否需要真实运行 | **是** — 需要创建真实 ChangeBatch、运行 preflight、生成 commit candidate、执行 release gate |
| 是否可 Deferred | **否** — 仓库工作区是产品基线的核心页面组，且已投入 Stage 6-C/6-D1 前端工作 |

### 4.3 治理中心沉淀闭环（Blocker #3）

| 字段 | 值 |
|---|---|
| 缺口编号 | GAP-03 |
| 所属链路 | Governance（#18） |
| 当前证据 | GOV-04~GOV-10 全部 Partial：角色/Skill 生命周期流转缺后端闭环；"建议沉淀"→用户确认→正式资产链路未通；临时 Skill 清理策略仅有前端文案。GOV-13 成本来源可信度标注为 heuristic。GOV-14 记忆 compact/rehydrate/reset 按钮正确禁用（无后端）。 |
| 阻塞原因 | 产品基线 closure flow 第 9 节明确要求"角色、Skill、成本、摘要、经验进入治理台账"。当前治理中心仅能读取静态配置和 consumption 聚合数据，不能驱动角色/Skill 生命周期。 |
| 建议模型 | Codex（后端角色/Skill 沉淀接口） |
| 是否需要真实运行 | **是**（部分：角色/Skill 沉淀可在 simulate 模式下验证 API） |
| 是否可 Deferred | **可 Deferred 到 Stage 8** — 治理沉淀需要上游（Worker/Run/Deliverable/Approval）先产生足够的消费证据 |

### 4.4 工作台 / 项目页前端验收（Blocker #4）

| 字段 | 值 |
|---|---|
| 缺口编号 | GAP-04 |
| 所属链路 | Frontend Integration（#21） |
| 当前证据 | CL-17 全站按钮审计通过（Runtime Pass）。但 closure-checklist 中 WB-01~WB-10、PRJ-01~PRJ-10、UI-01~UI-10 大部分未回填。Stage 4 验证了工作台草案审核链路（WB-03/WB-06/WB-09），但工作台整体布局、态势摘要、项目页卡片顺序等 UX 一致性未审计。 |
| 阻塞原因 | 产品基线第 2 节（工作台）和第 3 节（项目页）定义了完整的页面职责，但缺乏对照验证。 |
| 建议模型 | DeepSeek（只读审计，不改代码） |
| 是否需要真实运行 | **否** — 仅需页面审计 |
| 是否可 Deferred | **可 Deferred 到 Stage 7** — UX 一致性不阻塞功能闭环 |

### 4.5 成本台账真实 Provider 成本（Blocker #5）

| 字段 | 值 |
|---|---|
| 缺口编号 | GAP-05 |
| 所属链路 | Cost Telemetry（#19） |
| 当前证据 | CL-16 Evidence Partial。Worker→Run→Cost Dashboard→GovernancePage 成本结构链路闭合，但**所有成本为 heuristic（simulate 模式，~$0.002/run）**。cost source credibility note 标注"heuristic.simulate.char_count.v1"。 |
| 阻塞原因 | 与 GAP-01 同一根因：没有真实 AI provider 运行就没有真实 token/cost 数据。 |
| 建议模型 | 随 GAP-01 一起解决 |
| 是否需要真实运行 | **是** — 需要真实 AI provider |
| 是否可 Deferred | **否** — CL-16 是 closure checklist 的独立验收项 |

### 4.6 Rollup 总汇总（Blocker #6）

| 字段 | 值 |
|---|---|
| 缺口编号 | GAP-06 |
| 所属链路 | Rollup（#20） |
| 当前证据 | 无任何 rollup 端点或页面。`setup-readiness`（Stage 4）是项目初始配置总览，不是运行态 rollup。产品基线未单独定义 rollup 页面，但 closure flow 第 10 节要求"项目闭环完成"判断。 |
| 阻塞原因 | SKILL.md §8.5 明确列出 "rollup"。产品基线第 7 节（全局自动摘要机制）可解释为 rollup 能力的基础。 |
| 建议模型 | 待定（需先明确 rollup 的产品定义） |
| 是否需要真实运行 | **是** — rollup 需消费上游全部链条的数据 |
| 是否可 Deferred | **可 Deferred 到 Stage 8** — rollup 是最终汇总层 |

### 4.7 审批页 P1 布局改造（Blocker #7，低优先级）

| 字段 | 值 |
|---|---|
| 缺口编号 | GAP-07 |
| 所属链路 | Frontend Integration（#21） |
| 当前证据 | Stage 6-B 审计记录 P1 布局改造（"左侧审批轻列表 + 右侧决策面板"）未实现。当前仍为"发起审批表单 + 超时提醒 + 审批队列"纵向排列 + 抽屉决策。 |
| 阻塞原因 | 产品基线第 28.2 节定义左列表右面板布局。 |
| 建议模型 | Codex（前端布局改造） |
| 是否需要真实运行 | **否** |
| 是否可 Deferred | **可 Deferred** — 功能性完整（审批可闭环），布局是 UX 优化 |

---

## 5. 按链路总览

### 5.1 用户真实首次使用路径分析

模拟用户首次使用 AI Project Director 的完整路径及其障碍：

| 步骤 | 链路节点 | 当前状态 | 阻塞点 |
|---|---|---|---|
| 1 | 用户打开工作台 | 页面存在，按钮闭环通过 | 无阻塞 |
| 2 | 输入目标 | 工作台对话可用，goal_text 持久化 | 无阻塞 |
| 3 | AI 主管澄清 | 澄清问题生成+回答+goal_summary | 无阻塞 |
| 4 | 生成作战计划 | 计划版本生成+展示 | 无阻塞 |
| 5 | 审核草案 | 弹窗审核 approve/reject/request_changes | 无阻塞 |
| 6 | 创建正式项目+任务队列 | create-formal-project 全链路 | 无阻塞 |
| 7 | 确认 Agent/Skill/仓库/验证配置 | 4 类配置 confirm/reject | 无阻塞 |
| 8 | **启动 Worker 执行** | simulate-only，**需真实 provider** | **GAP-01** |
| 9 | 查看 Run 日志/摘要 | Run 记录+日志+summary 在 simulate 下正常 | 随 GAP-01 |
| 10 | 查看交付物 | 交付物页+EvidenceProjector 正常 | 无阻塞 |
| 11 | 发起审批 | 审批创建+approve/reject/request_changes | 无阻塞 |
| 12 | **仓库变更链路** | 面板已挂载，**缺真实数据流验证** | **GAP-02** |
| 13 | 查看治理中心 | 消费证据可用，沉淀闭环缺后端 | GAP-03 |
| 14 | 查看成本台账 | heuristic only | GAP-05 |

**结论**：用户能无障碍走通步骤 1-7（目标→计划→项目→任务→配置）。步骤 8（Worker 执行）是当前最大断层：simulate 模式下代码路径正确但缺少真实 AI provider 验证。步骤 12（仓库变更链路）前端完整但后端数据流未端到端验证。

---

## 6. 下一阶段建议

### 6.1 Stage 7 应该做什么

**首要目标**：解决 GAP-01（真实 Provider 运行态证据），这是解除当前最大阻塞的唯一路径。

具体动作：
1. **Provider 配置验证**：确认设置页 Provider 配置可真实连接 AI API
2. **Worker 真实执行**：至少完成 1 次非 simulate 的 Worker 调度+Run 执行+日志+AI summary
3. **端到端验收**：目标→计划→任务→Worker→Run→Deliverable→Approval 全链路
4. **成本台账真实数据**：非 heuristic 的 provider_reported 成本至少 1 条

**次要目标**：解决 GAP-02（仓库变更链路真实数据流）

### 6.2 第一条任务建议

```text
建议使用模型：Codex
任务类型：最小 Provider 集成验证 + Worker 真实执行准备
原因：当前 Worker simulate-only，需要确保真实 AI provider 调用链路完整。

目标：验证并修复从设置页 Provider 配置到 Worker 真实调用的全链路。

必须先检查：
- apps/web/src/pages/settings/ 中 Provider 配置组件
- runtime/orchestrator/app/api/routes/provider_settings.py
- runtime/orchestrator/app/workers/ 中 Worker 调度和 AI 调用逻辑
- runtime/orchestrator/app/services/ 中 run summary service

要求：
1. 确认 Provider 配置可正确读写
2. 确认 Worker 在非 simulate 模式下可正确调用 AI provider
3. 确认 AI summary 在真实 provider 下可生成
4. 不自动启动 Worker，不自动创建 Run
5. 不改产品逻辑，只修明确的集成缺陷

严格边界：
- 不自动启动 Worker
- 不自动创建 Run
- 不调用 apply-local / git-commit
- 只做最小修复
```

---

## 7. Gate 结论

### 7.1 Stage 6 aggregate: **Pass**

Stage 6-A（交付物）、6-B（审批）、6-C（仓库门禁迁移）、6-D1（commit_draft 可达性）四个子阶段全部 Pass。Stage 6 的原始范围（成果中心+执行中心前端收口+审批页职责合规）已全部完成。

### 7.2 AI Project Director total closure: **Partial**

**不满足 total closure 条件**。SKILL.md §8.5 列出的 21 条 product chains 中：

| 状态 | 数量 | 链条 |
|---|---|---|
| Pass | 5 | goal/plan, task creation, deliverable, approval, rework chain |
| Partial | 12 | worker run, run logs, AI summary, repository binding, snapshot, file locator, context pack, change plan, change batch, preflight, commit candidate, release gate, governance, cost telemetry, frontend integration |
| Missing | 1 | rollup |
| N/A | 1 | apply-local/git-commit（明确不在 scope） |

**核心阻塞**：GAP-01（真实 Provider 运行态证据）和 GAP-02（仓库工作区完整端到端数据流）必须在 total closure Pass 之前解除。

### 7.3 CL-16: **不涉及**

CL-16（成本闭环）当前 Evidence Partial，且依赖 GAP-01/GAP-05（真实 provider 运行）解除。不得写 Pass。

---

## 8. 审查清单

- [x] origin/main commit 已核对：`b23a0da4f26133ca981a84ae38e52d35fc5c45ca`
- [x] SKILL.md §8.5 全部 21 条 chain 已对照
- [x] closure-checklist CL-01~CL-18 全部状态已核对
- [x] Stage 4/6-A/6-B/6-C/6-D1 全部 evidence 文档已读取
- [x] closure-flow 流程已对照
- [x] 产品基线 page-information-architecture 已对照
- [x] 7 个 blocker 已列出（GAP-01~GAP-07）
- [x] 4 条可 Deferred，3 条不可 Deferred
- [x] 用户首次使用路径已分析（14 步）
- [x] Stage 7 建议已明确
- [x] 第一条 Codex 指令建议已给出
- [x] 未改任何业务代码
- [x] 未改前端/后端/数据库/Worker
- [x] AI Project Director total closure 仍为 Partial
- [x] CL-16 不涉及，未写 Pass
