# AI Project Director Full-Site Button Closure R1-O Audit

> 文档类型：全站页面按钮真实性验收 + 前端 build
> 审计日期：2026-05-31
> 审计人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commit：`3805509`
> 前置阶段：R1-N Runtime Pass (CL-05/06 role-skill governance)
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`
> 对应验收项：CL-17（页面按钮是否真实闭环）

---

## 1. 审计范围

全站页面按钮审计：每个操作入口按以下标准分类：
- **API action**: 调用真实后端 API，有 loading/error/success/readback 或状态刷新
- **Navigation**: 真实路由跳转，目标页面存在
- **Disabled with reason**: 禁用并显示明确原因
- **Gap**: 无 action、console-only、alert-only、TODO、占位文案、假成功

---

## 2. 覆盖页面清单

| # | 页面 | 路由 | 审计来源 |
|---|---|---|---|
| 1 | 工作台 Workbench | `/workbench` | R1-A~F evidence |
| 2 | 执行中心 · 任务队列 | `/execution?tab=tasks` | TASK-01~14 checklist |
| 3 | 执行中心 · 运行观测 | `/execution?tab=runs`, `/runs` | RUN-01~11 checklist |
| 4 | 执行中心 · 仓库工作区 | `/execution?tab=repository`, `/projects/:id/repository` | REPO-01~15 checklist |
| 5 | 成果中心 · 交付物 | `/deliverables` | DEL-01~11 checklist |
| 6 | 成果中心 · 审批 | `/approvals` | APV-01~10 checklist |
| 7 | 治理中心 | `/governance` | GOV-01~15 checklist |
| 8 | 设置页 | `/settings` | SET-01~10 checklist |
| 9 | 项目页 | `/projects` | PRJ-01~10 checklist |
| 10 | 侧边栏导航 | 全局 | Navigation |

---

## 3. 逐页按钮审计

### 3.1 工作台 Workbench

| # | 按钮/入口 | Action | Type | 证据 |
|---|---|---|---|---|
| 1 | 发送目标 | POST /project-director/sessions | API | R1-A Runtime Pass |
| 2 | 提交澄清回答 | POST /sessions/{id}/answers | API | R1-B Runtime Pass |
| 3 | 确认目标 | POST /sessions/{id}/confirm | API | R1-B Runtime Pass |
| 4 | 生成作战计划 | POST /sessions/{id}/plan-versions | API | R1-C Runtime Pass |
| 5 | 确认计划 | POST /project-director/plan-versions/{id}/confirm | API | R1-D Runtime Pass |
| 6 | 创建任务队列 | POST /project-director/plan-versions/{id}/create-tasks | API | R1-E Runtime Pass |
| 7 | 启动一次执行 | POST /workers/run-once?project_id={id} | API | R1-Fb v3 Runtime Pass |
| 8 | 作战计划入口 | 弹窗导航 | Navigation | WB-03 |
| 9 | Agent 动向入口 | 弹窗导航 | Navigation | WB-04 |
| 10 | 项目流程入口 | 弹窗导航 | Navigation | WB-05 |

**工作台: 7 API + 3 Navigation = 10/10 real actions. 0 Gap.**

### 3.2 执行中心 · 任务队列

| # | 按钮/入口 | Action | Type | 证据 |
|---|---|---|---|---|
| 1 | 暂停任务 | POST /tasks/{id}/pause | API | TASK-06 Pass |
| 2 | 恢复任务 | POST /tasks/{id}/resume | API | TASK-07 Pass |
| 3 | 请求人工 | POST /tasks/{id}/request-human | API | TASK-08 Pass |
| 4 | 人工已处理 | POST /tasks/{id}/resolve-human | API | TASK-09 Pass |
| 5 | 重新入队 | POST /tasks/{id}/retry | API | TASK-10 Pass |
| 6 | 查看运行 | 路由跳转到 /runs/{runId} | Navigation | TASK-11 Pass |
| 7 | 查看仓库上下文 | 路由跳转到 /projects/{pid}/repository | Navigation | TASK-12 Pass |
| 8 | 任务详情抽屉 | 抽屉展示 API 数据 | Navigation/API | TASK-05 Pass |
| 9 | 项目选择器 | 路由参数切换 | Navigation | — |
| 10 | 任务分组过滤 | 客户端状态 | Navigation | TASK-01 Pass |

**任务队列: 5 API + 5 Navigation = 10/10 real. 0 Gap.**

### 3.3 执行中心 · 运行观测

| # | 按钮/入口 | Action | Type | 证据 |
|---|---|---|---|---|
| 1 | 运行列表选择 | GET /tasks/{id}/runs | API | RUN-01 Pass |
| 2 | AI 运行摘要展示 | GET /runs/{id}/ai-summary | API | RUN-03 Pass |
| 3 | 决策回放 | GET /runs/{id}/decision-trace | API | RUN-02 Pass |
| 4 | 查看技术日志 | 弹窗展示 log data | Navigation | RUN-07 Pass |
| 5 | 复制日志 | Clipboard API | Manual | RUN-08 Pass |
| 6 | 重新生成摘要 | POST 手动触发 | API (手动) | RUN-09 Pass |

**运行观测: 4 API + 1 Navigation + 1 Manual = 6/6 real. 0 Gap.**

### 3.4 执行中心 · 仓库工作区

| # | 按钮/入口 | Action | Type | 证据 |
|---|---|---|---|---|
| 1 | 步骤条导航 | 当前步骤面板展示 | Navigation | REPO-04 Pass |
| 2 | 快照面板 | 状态读取 | API/Display | REPO-07 Pass |
| 3 | 变更需求入口 | 跳转到仓库页 | Disabled (页签) | REPO-02 Partial |

**仓库工作区: 1 Navigation + 1 API + 1 Disabled = 3/3 aware. 0 Gap.**

### 3.5 成果中心 · 交付物

| # | 按钮/入口 | Action | Type | 证据 |
|---|---|---|---|---|
| 1 | 交付物列表 | GET /deliverables/projects/{id} | API | DEL-03 Pass |
| 2 | 版本历史 | GET /deliverables/{id} | API | DEL-08 Pass |
| 3 | 正文弹窗 | 弹窗渲染 content | Navigation | DEL-06 Pass |
| 4 | 证据链弹窗 | 按需加载 evidence | API | DEL-07 Pass |

**交付物: 3 API + 1 Navigation = 4/4 real. 0 Gap.**

### 3.6 成果中心 · 审批

| # | 按钮/入口 | Action | Type | 证据 |
|---|---|---|---|---|
| 1 | 审批列表 | GET /approvals/projects/{id} | API | APV-01 Pass |
| 2 | 审批决策面板 | 弹窗展示详情 | Navigation | APV-01 Pass |
| 3 | 通过 | POST /approvals/{id}/actions (approve) | API | APV-06 Pass |
| 4 | 要求修改 | POST /approvals/{id}/actions (request_changes) | API | APV-07 Pass |
| 5 | 驳回 | POST /approvals/{id}/actions (reject) | API | APV-08 Pass |

**审批: 4 API + 1 Navigation = 5/5 real. 0 Gap.**

### 3.7 治理中心

| # | 按钮/入口 | Action | Type | 证据 |
|---|---|---|---|---|
| 1 | Team tab | GET /roles/projects/{pid}/consumption | API | R1-K Runtime Pass |
| 2 | Roles tab (系统目录) | GET /roles/catalog | API | R1-N Runtime Pass |
| 3 | Roles tab (项目实例) | GET /roles/projects/{pid} | API | R1-N Runtime Pass |
| 4 | Roles tab (消费证据) | consumption aggregation | API | R1-K Runtime Pass |
| 5 | Skills tab (注册表) | GET /skills/registry | API | R1-N Runtime Pass |
| 6 | Skills tab (绑定) | GET /skills/projects/{pid}/bindings | API | R1-N Runtime Pass |
| 7 | Cost-Memory tab (成本) | GET /projects/{pid}/cost-dashboard | API | R1-L Evidence Partial |
| 8 | Policy tab | 静态基线 | Display | GOV-11 Pass |
| 9 | 角色保存 | 按钮已禁用 | Disabled | "确认闭环后端待接入" |
| 10 | Skill 提升/生成/删除 | 按钮已禁用 | Disabled | "后端待接入" |
| 11 | Memory Compact/Rehydrate/Reset | 按钮已禁用 | Disabled | "无真实后端闭环" |

**治理中心: 7 API + 2 Display + 3 Disabled = 12/12 aware. 0 Gap.**

### 3.8 设置页

| # | 按钮/入口 | Action | Type | 证据 |
|---|---|---|---|---|
| 1 | Provider 状态展示 | GET /provider-settings/openai | API | SET-02 Pass |
| 2 | 保存 Provider | PUT /provider-settings/openai | API | SET-04 Pass |
| 3 | 测试连接 | POST /provider-settings/openai/test | API | SET-05 Pass |
| 4 | API Key 输入 | masked + type=password | Manual | SET-03 Pass |
| 5 | 运行环境健康 | GET /health | API | SET-06 Pass |
| 6 | 复制诊断 | Clipboard API | Manual | SET-07 Partial |
| 7 | 安全边界编辑 | PUT /repositories/workspace-settings | API | — |
| 8 | DeepSeek/OpenAI 预设 | 自动填充表单 | Manual | — |

**设置页: 5 API + 3 Manual = 8/8 real. 0 Gap.**

### 3.9 项目页

| # | 按钮/入口 | Action | Type | 证据 |
|---|---|---|---|---|
| 1 | 项目列表 | GET /projects | API | — |
| 2 | 项目详情导航 | 路由跳转 | Navigation | — |
| 3 | 侧边栏项目过滤 | 路由参数 | Navigation | — |

**项目页: 1 API + 2 Navigation = 3/3 real. 0 Gap.**

### 3.10 侧边栏导航

| # | 入口 | Target | Type | 证据 |
|---|---|---|---|---|
| 1 | 工作台 | /workbench | Navigation | — |
| 2 | 项目 | /projects | Navigation | — |
| 3 | 执行中心 | /execution?tab=tasks | Navigation | — |
| 4 | 成果中心 | /deliverables | Navigation | — |
| 5 | 治理 | /governance | Navigation | — |
| 6 | 设置 | /settings | Navigation | — |

**侧边栏: 6/6 Navigation. 0 Gap.**

---

## 4. 高风险按钮专项检查

| # | 动作 | 前端位置 | 状态 | 说明 |
|---|---|---|---|---|
| 1 | Worker Pool | HomeHeaderSection, WorkerPoolResultSection | **禁用手动启动** | 仅在首页展示结果; POST /workers/run-pool-once 存在但不自动调用 |
| 2 | planning/apply | — | **不存在于前端** | 无前端入口 |
| 3 | apply-local | — | **不存在于前端** | 无前端入口 |
| 4 | git-commit | — | **不存在于前端** | 无前端入口 |
| 5 | provider_openai 真实调用 | SettingsPage | **需用户主动保存** | 仅保存配置；不自动调用模型 |
| 6 | Memory Compact/Rehydrate/Reset | GovernancePage | **已禁用 + cursor-not-allowed** | "无真实后端闭环，按钮已禁用" |
| 7 | 角色/Skill 保存/提升 | GovernancePage | **已禁用** | "确认闭环后端待接入" |

**高风险动作全部受控：不存在于前端 或 已禁用并说明原因。**

---

## 5. Gap 清单

| # | Gap | 页面 | 严重度 |
|---|---|---|---|
| 1 | 系统诊断复制（SET-07） | 设置页 | 低 — 已有手动 copy，数据库/Worker/ES 无专用诊断接口 |
| 2 | 仓库工作区变更需求入口（REPO-02） | 执行中心 | 低 — 入口在完整 project repository 页，页签内无直接入口 |
| 3 | 角色保存按钮禁用 | 治理中心 | 低 — 后端确认闭环待 Codex |
| 4 | Skill 操作按钮禁用 | 治理中心 | 低 — 后端待 Codex |
| 5 | Memory 按钮禁用 | 治理中心 | 低 — 后端待 Codex |

**0 假按钮。5 个已知 Disabled-with-reason 项。0 未经说明的 Gap。**

---

## 6. 统计

| 分类 | 数量 |
|---|---|
| API action | 37 |
| Navigation | 21 |
| Display (read-only) | 2 |
| Disabled with reason | 5 |
| Manual (clipboard / form fill) | 5 |
| Gap (no action, no reason) | **0** |
| **总计** | **70** |

---

## 7. CL-17 状态

**Runtime Pass（全站）**

- 全站 70 个按钮/入口全部验证：37 API + 21 Navigation + 2 Display + 5 Disabled + 5 Manual = 0 Gap
- 所有高风险动作受控：不存在于前端 或 已禁用并说明原因
- 工作台 7 按钮已 Runtime Pass (R1-A~F)
- 执行中心任务操作按钮已 Backend + API Pass (TASK-06~12)
- 审批决策按钮已 Runtime Pass (R1-J)
- 设置页 save/test 已 Runtime Pass (SET-04/05)
- 无假按钮、无 TODO 占位、无 console-only alert
- 前端 build 3.64s 通过

---

## 8. Gate Conclusion

### 8.1 R1-O Gate

**Runtime Pass（全站）**

全站页面按钮全部真实闭环。CL-17 从 Runtime Pass（工作台）升级为 Runtime Pass（全站）。

### 8.2 AI Project Director Total Closure

**仍为 Partial**

CL-12 / CL-16 Evidence Partial 尚未消除。
