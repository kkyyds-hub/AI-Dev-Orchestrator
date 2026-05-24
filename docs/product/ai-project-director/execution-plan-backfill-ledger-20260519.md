# AI-Dev-Orchestrator AI 项目主管执行计划与回填台账

> 文档日期：2026-05-19  
> 建议仓库路径：`docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md`  
> 适用范围：AI Project Director / AI 项目主管方向后续所有 Codex 阶段任务  
> 当前基线 commit：`e8efd01bfea391cc5f1cefed1c296549aeff84ab`  
> 文档定位：这是 `closure-checklist-20260518.md` 的治理补充台账，用来区分“前端职责收口”“真实 API 接入”“后端状态闭环”“运行证据闭环”，避免只看到 Pass 而无法判断到底完成到哪一层。

---

## 0. 为什么新增这份文档

当前已有三份产品基线文档：

1. `page-information-architecture-20260518.md`：定义页面职责和布局边界。
2. `closure-flow-20260518.md`：定义 AI 项目主管从目标到交付审批的完整闭环流程。
3. `closure-checklist-20260518.md`：定义每个页面和闭环项的验收清单。

但 `closure-checklist` 更偏“逐项验收”，容易出现一个问题：

> 某个页面视觉和入口已经收口，状态被回填为 Pass，但读文档的人看不出来它到底是“前端完成”，还是“后端真实闭环也完成”。

因此新增本台账，专门记录每个阶段的四层完成状态：

| 层级 | 含义 | 是否等于最终闭环 |
|---|---|---|
| L1 页面职责收口 | 页面位置、入口、布局、信息边界正确 | 否 |
| L2 前端真实接入 | 使用真实 hooks / API / 路由，不是假按钮 | 否 |
| L3 后端状态闭环 | 后端接口能真实改变状态、产生记录、刷新证据 | 接近闭环 |
| L4 运行证据闭环 | 本地/联调环境真实运行通过，有截图、日志、回填文档 | 是 |

以后每一阶段除回填 `closure-checklist` 外，还必须同步回填本台账。

---

## 1. 总执行策略

当前项目不采用“先把所有前端改完，再集中补后端”的方式。

采用以下策略：

```text
按闭环链路推进 → 每个页面先做职责收口 → 同步检查真实 API →
遇到后端缺口就标 Partial / Blocked → 单独生成后端闭环补齐任务 →
最后做端到端运行证据 Gate。
```

### 1.1 执行顺序

执行顺序来自闭环流程，而不是页面美化顺序：

```text
工作台
→ 项目页
→ 执行中心：任务队列
→ 执行中心：运行观测
→ 执行中心：仓库工作区
→ 成果中心：交付物
→ 成果中心：审批
→ 治理中心
→ 设置页
→ 后端缺口补齐
→ 端到端闭环验收
```

### 1.2 当前阶段优先级

当前已完成执行中心三页签接入，下一阶段应进入：

```text
成果中心 Phase1：交付物 / 审批入口与职责收口
```

原因：闭环流程中，执行中心之后就是交付物与审批，不应继续在执行中心里反复抛光。

---

## 2. 状态定义

本台账使用以下状态，避免笼统写 Pass。

| 状态 | 含义 |
|---|---|
| Not Started | 尚未处理 |
| UI Pass | 页面职责、布局、入口、禁忌项已收口 |
| API Pass | 前端已接真实 API / hooks / 路由，不是假按钮 |
| Backend Pass | 后端能真实改变状态、生成记录、返回证据 |
| Runtime Pass | 已在前后端联调环境真实操作验证通过 |
| Partial | 部分完成，主链路可用，但还有明确缺口 |
| Blocked | 被后端、数据、权限或接口缺失阻塞 |
| Deferred | 有意延后，且不影响当前阶段 Gate |
| Fail | 不满足要求或存在误导性实现 |

### 2.1 Gate 口径

| Gate 类型 | 通过条件 |
|---|---|
| 页面 Gate | UI Pass + 不越界 + 无假按钮 |
| 接入 Gate | API Pass + 请求真实接口 + 成功后刷新数据 |
| 后端 Gate | Backend Pass + 状态流转真实可追踪 |
| 运行 Gate | Runtime Pass + build / 测试 / 截图 / 日志证据 |
| 总闭环 Gate | 目标、计划、任务、运行、仓库、交付、审批、治理、成本均有证据链 |

---

## 3. 当前总进度回填

| 模块 | 当前阶段 | 页面职责 | 前端真实接入 | 后端闭环 | 运行证据 | 文档回填 | 当前结论 | 下一步 |
|---|---|---|---|---|---|---|---|---|
| `/workbench` 工作台 | AI 项目主管轻量指挥室 | UI Pass | Partial | Partial | Partial | 待补本台账 | **Partial** | 后续需要真实 AI 主管会话 / 待确认处理闭环 |
| `/execution?tab=tasks` 任务队列 | 任务队列真实接入 | UI Pass | API Pass | Backend Pass | Partial | checklist 已回填 TASK-01~14 | **Pass（实现级）** | 最后做运行截图总验收 |
| `/tasks` 路由兼容 | 重定向到执行中心任务页签 | UI Pass | API Pass | N/A | Partial | 已记录 | **Pass** | 保持兼容 |
| `/execution?tab=runs` 运行观测 | Phase1 真实接入 | UI Pass | API Pass | Partial | Partial | checklist 已回填 RUN-01~11 | **Pass（Phase1）** | 后续补自动摘要/失败闭环运行证据 |
| `/runs` 路由兼容 | 保留运行观测独立路由 | UI Pass | API Pass | N/A | Partial | 已记录 | **Pass** | 保持兼容 |
| `/execution?tab=repository` 仓库工作区 | Phase1 状态+步骤工作区 | UI Pass | API Pass | Partial | Partial | checklist 已回填 REPO-01~15 | **Pass（Phase1）** | 后续补变更需求入口、文件定位/上下文包页签内证据 |
| 侧边栏导航 | 收敛导航 | UI Pass | N/A | N/A | Partial | 已记录 | **Pass** | 不恢复任务/运行观测一级入口 |
| 成果中心：交付物 | Phase1 审计+返工收敛 | UI Pass | API Pass | Backend Pass | Partial | checklist 已回填 DEL-01~11（9 Pass / 2 Partial） | **Pass（Phase1）** | 返工: /delivery 父页面收敛双页签；DEL-09/DEL-10 保持 Partial |
| 成果中心：审批 | Phase1 审计+返工收敛 | UI Pass | API Pass | Backend Pass（审批动作真实写状态） | Partial | checklist 已回填 APV-01~10 | **Pass（Phase1）** | 返工: 审批页签收敛至成果中心；后续补端到端截图 |
| 治理中心 | Phase1 职责收口+返工+补强 | UI Pass | Partial（5 个读 API 全部接入；角色/Skill 搜索已补；写操作按钮禁用） | Partial（角色/Skill 保存 API 存在，确认闭环/记忆闭环无后端） | Partial（build 通过，运行时证据不足） | checklist GOV-01~15（6P/9P）；verification 含数据量稳定性检查 | **Partial** | 搜索+文档修正完成 |
| 设置页 | Phase1 职责收口 + 账户合并 | UI Pass | API Pass（7 个真实 API 全部接入） | Partial（数据库/Worker/ES 诊断后端缺口） | Partial（build 通过，运行证据不足） | checklist SET-01~10（9P/1P）；账户入口合并完成 | **Pass（Phase1）** | 账户一级入口移除；/me 重定向；无新增后端 |
| 成本治理 | 未开始总验收 | Partial | Partial | Partial | Not Started | 空白 | **Partial** | 最后按 COST-* 统一验收 |
| 总闭环 CL-01~18 | 未做总 Gate | Partial | Partial | Partial | Not Started | 空白 | **Partial** | 页面阶段完成后统一回填 |

---

## 4. 已完成阶段详细回填

### 4.1 工作台 `/workbench`

| 字段 | 回填 |
|---|---|
| 阶段名称 | 工作台改造为 AI 项目主管轻量指挥室 |
| 关键提交 | `36ed7c7` 第一版骨架；`025da48` 返工消除伪装能力与死代码 |
| 页面目标 | 工作台不做统计大屏，改为 AI 项目主管入口、当前态势、轻量弹窗入口 |
| 页面职责 | UI Pass |
| 前端真实接入 | Partial：阻塞跳转、Worker 单次调度等存在真实链路；AI 主管对话发送仍未形成完整真实会话闭环 |
| 后端闭环 | Partial：仍缺真实 AI 项目主管会话、待确认事项处理、计划重评估应用链路 |
| 运行证据 | Partial：build 曾通过，但仍需最终截图和接口链路验证 |
| 文档状态 | 需要在本台账记录；`closure-checklist` 中 WB-* 仍需后续系统性回填 |
| 当前结论 | **不能写总 Pass。应写：工作台页面职责收口 Pass，AI 主管真实闭环 Partial。** |
| 后续动作 | 在成果中心与治理中心完成后，单独开“工作台后端闭环补齐”阶段 |

### 4.2 执行中心：任务队列 `/execution?tab=tasks`

| 字段 | 回填 |
|---|---|
| 阶段名称 | 任务队列真实接入与最终收口 |
| 关键提交 | `3319c3e` 分组与优先级修正；`376e340` 第一阶段回填；`96caeb5` 操作按钮接入；`2960e0c` 状态机对齐；`9ba114f` 最终验收文档 |
| 页面目标 | 左侧轻任务队列 + 右侧执行态势面板 + 任务详情抽屉 |
| 页面职责 | UI Pass |
| 前端真实接入 | API Pass：暂停、恢复、请求人工、人工已处理、重新入队等调用真实 task action API |
| 后端闭环 | Backend Pass：相关后端状态机接口存在，并已对齐前端按钮可见性 |
| 运行证据 | Partial：本地 build 回传通过；还需要最终人工截图/端到端运行记录汇总 |
| 文档状态 | `closure-checklist` 已回填 TASK-01~TASK-14 |
| 当前结论 | **实现级 Pass，运行证据级 Partial** |
| 后续动作 | 不再继续抛光任务队列；最终总 Gate 时补截图证据 |

### 4.3 执行中心：运行观测 `/execution?tab=runs`

| 字段 | 回填 |
|---|---|
| 阶段名称 | 运行观测 Phase1 真实接入 |
| 关键提交 | `6e6c1eb` |
| 页面目标 | 在执行中心页签内展示左侧运行轻列表 + 右侧诊断详情 |
| 页面职责 | UI Pass |
| 前端真实接入 | API Pass：复用运行列表、运行详情、AI 摘要读取、技术日志弹窗等能力 |
| 后端闭环 | Partial：能读取运行摘要/日志/质量闸门等证据，但自动摘要触发、失败处置联动仍需后续总闭环验证 |
| 运行证据 | Partial：build 回传通过；仍需截图和真实失败/成功 Run 样例验证 |
| 文档状态 | `closure-checklist` 已回填 RUN-01~RUN-11；RUN-10 为 N/A |
| 当前结论 | **Phase1 Pass，运行闭环总体验收 Partial** |
| 后续动作 | 暂不继续改运行观测；后续在失败闭环和成本摘要总 Gate 里复查 |

### 4.4 执行中心：仓库工作区 `/execution?tab=repository`

| 字段 | 回填 |
|---|---|
| 阶段名称 | 仓库工作区 Phase1 状态 + 步骤工作区 |
| 关键提交 | `e8efd01` |
| 页面目标 | 从跳转占位升级为仓库状态条、变更链路步骤条、当前步骤面板 |
| 页面职责 | UI Pass |
| 前端真实接入 | API Pass：读取仓库快照、变更会话、变更批次、提交草案 |
| 后端闭环 | Partial：Phase1 以读取状态为主；变更需求、文件定位、上下文包、预检、提交草案生成等仍主要在完整仓库页 |
| 运行证据 | Partial：build 回传通过；仍需真实项目数据截图验证 |
| 文档状态 | `closure-checklist` 已回填 REPO-01~REPO-15 |
| 当前结论 | **Phase1 Pass，仓库闭环总体验收 Partial** |
| 统计修正 | 当前报告中 REPO 统计应为 11 Pass / 2 Partial / 2 N/A，不是 10 Pass / 3 Partial / 2 N/A |
| 后续动作 | 不继续抛光执行中心仓库页签；后续如做仓库闭环，应回到完整仓库页和后端链路 |

---

## 5. 待处理阶段计划

### 4.5 成果中心 Phase1：交付物 / 审批审计回填 + 返工收敛

| 字段 | 回填 |
|---|---|
| 阶段名称 | 成果中心交付物 / 审批审计回填 + 返工建立父页面 |
| 关键提交 | 5da6dc8（审计回填）、d82e6d7（口径修正）、(本次)（返工收敛） |
| 页面目标 | 建立 /delivery 成果中心父页面，页签收敛交付物+审批；旧路由兼容重定向 |
| 页面职责 | UI Pass：/delivery 成果中心父页面（双页签），/deliverables 和 /approvals 重定向兼容 |
| 说明 | 5da6dc8 是旧散页审计回填，本轮才是成果中心父页面收敛 |
| 前端真实接入 | API Pass：交付物 snapshot/detail/diff/evidence；审批 inbox/detail/history/action；全部真实 GET/POST |
| 后端闭环 | Backend Pass：审批通过/驳回/要求修改 → POST /approvals/:id/actions → 真实状态变更 |
| 运行证据 | Partial：build 通过，代码级审计完成；需最终人工审批截图验证 |
| 文档状态 | `closure-checklist` DEL-01~11、APV-01~10 已回填；`verification-delivery-center-phase1` 已创建 |
| 后端缺口清单 | DEL-10 返工→任务队列链路需后端端到端验证（审批要求修改后是否在任务页可见返工请求）；其余无后端缺口 |
| 当前结论 | **Phase1 Pass，运行证据级 Partial**（DEL 9 Pass / 2 Partial；APV 10 Pass） |
| Gate 结论 | Pass（页面职责+API 接入+审批后端闭环均完成；DEL-09/DEL-10 保持 Partial） |
| 假审批按钮检查 | **无假按钮**。通过/驳回/要求修改均调用 `applyApprovalAction()` → POST /approvals/:id/actions |
| 后续动作 | 总 Gate 时补审批截图证据；返工闭环在任务队列侧补充端到端测试 |

### 4.6 治理中心 Phase1：AI 团队资产治理中心职责收口

| 字段 | 回填 |
|---|---|
| 阶段名称 | 治理中心 Phase1：AI 团队资产治理中心职责收口 |
| 关键提交 | (本次) |
| 页面目标 | 从旧 section nav 重构为 5 页签 AI 团队资产治理中心 |
| 页面职责 | UI Pass：5 页签（团队、角色、Skill、策略、成本与记忆），默认团队 |
| Existing Resource Audit | 旧 API 已存在（roles/skills/costs），旧组件（RoleCatalogPage/SkillRegistryPage）未删除；旧 GovernancePage 使用 section nav 已替换 |
| New Phase Work | 完全重写 GovernancePage：新 Header、新页签、新团队编队卡、新策略三列、新成本与记忆；AppShell 适配 breadcrumb/Topbar |
| 前端真实接入 | Partial：GOV-01~03/11/12/15 为 Pass；GOV-04~10/13~14 为 Partial（后端确认闭环/消费证据/记忆闭环未完成） |
| 后端闭环 | Partial：角色/Skill CRUD API 存在，但用户确认沉淀、Skill 消费证据、Compact/Rehydrate/Reset 无后端 |
| 运行证据 | Partial：build 通过，前端代码完成；后端运行时证据未收集 |
| 文档状态 | `closure-checklist` GOV-01~15 已回填；`verification-governance-center-phase1` 已创建 |
| 后端缺口清单 | 角色/Skill 用户确认闭环 API；Skill 消费证据查询 API；记忆 Compact/Rehydrate/Reset API；成本仪表板真实数据连调 |
| 当前结论 | **Phase1 Pass（UI），后端 Partial.** GOV 6/15 Pass，9/15 Partial。COST-* 合理延后，未强行回填。 |
| Gate 结论 | Partial |
| 后续动作 | 治理中心后端闭环补齐阶段：确认沉淀 API、消费证据 API、记忆管理 API |

### 4.7 设置页 Phase1：系统配置中心职责收口

| 字段 | 回填 |
|---|---|
| 阶段名称 | 设置页 Phase1：重构为系统配置中心 |
| 关键提交 | (本次) |
| 页面目标 | 四区块：Provider 与模型、运行环境、安全与权限、系统诊断 |
| Existing Resource | Provider GET/PUT API、仓库安全边界 API、仓库绑定 API 均为旧 API，本轮保留并继续使用 |
| New Phase Work | 新增 POST /provider-settings/openai/test 测试连接；接入 GET /health；新增诊断复制；Provider 编辑折叠；中文文案全覆盖 |
| 前端真实接入 | API Pass：7 个真实 API 全部接入（含 test 和 health） |
| 后端闭环 | Partial：数据库/Worker/Event Stream 无专用诊断接口 |
| 运行证据 | Partial：build 通过，运行时截图待补 |
| 文档状态 | `closure-checklist` SET-01~10 已回填；verification-settings 已创建 |
| 当前结论 | **Phase1 Pass，诊断 Partial.** SET 9/10 Pass，1 Partial (SET-07) |
| Gate 结论 | Pass（Phase1） |
| 后续动作 | 后端补数据库/Worker/Event Stream 诊断接口后 SET-07 可升 Pass |

### 5.1 成果中心 Phase1：交付物 / 审批职责收口（已完成）

| 字段 | 计划 |
|---|---|
| 阶段性质 | 前端职责收口 + 真实 API 审计 |
| 是否允许后端改动 | 默认不允许；若发现审批动作是假按钮，则进入后端缺口清单 |
| 目标页面 | `/deliverables`、`/approvals`，以及可能的成果中心聚合页 |
| 主要验收 | DEL-01~DEL-11，APV-01~APV-10 |
| 关键边界 | 交付物页看成果，不做审批决策；审批页做决定，不展示完整成果库 |
| 预期 Gate | 大概率 Phase1 Pass + 若干 Partial |
| 风险 | 发起审批、要求修改、驳回、返工请求可能存在后端缺口 |
| 完成后回填 | `closure-checklist` + 本台账 |

### 5.2 治理中心 Phase1

| 字段 | 计划 |
|---|---|
| 阶段性质 | 页面职责收口 + AI 团队资产治理审计 |
| 目标 | 区分本项目 AI 团队、角色治理、Skill 治理、策略权限、成本记忆 |
| 主要验收 | GOV-01~GOV-15 |
| 关键边界 | 治理中心不做任务执行，不做审批，不做 Provider 设置 |
| 预期 Gate | Partial |
| 风险 | 角色/Skill 生命周期、消费证据、沉淀确认可能后端不完整 |

### 5.3 设置页 Phase1

| 字段 | 计划 |
|---|---|
| 阶段性质 | 系统配置职责收口 + Provider 诊断闭环审计 |
| 目标 | Provider、模型、运行环境、安全、系统诊断 |
| 关键边界 | 设置页不做 Agent/Skill 治理，不做成本策略，不做任务调度 |
| 预期 Gate | Partial 或 Pass，取决于现有后端诊断接口 |

### 5.4 后端缺口补齐阶段

| 字段 | 计划 |
|---|---|
| 触发条件 | 任一页面出现按钮无法真实写状态、无法产生记录、只能禁用或模拟成功 |
| 输出 | 后端闭环缺口台账 + 每次只补一个接口/状态流 |
| 重点对象 | AI 主管会话、作战计划确认、交付物审批、返工请求、角色/Skill 沉淀、成本台账 |
| Gate | 后端测试通过 + 前端按钮解除禁用 + 文档回填 |

### 5.5 后端闭环补齐：BCG-01 Phase1 — AI Project Director Session

| 字段 | 回填 |
|---|---|
| 阶段名称 | BCG-01 Phase1：AI 项目主管目标澄清与会话闭环 |
| 阶段性质 | 后端闭环补齐 |
| 起始 commit | `472d028` |
| 结束 commit | （本次提交） |
| 修改文件 | `app/core/db_tables.py`、`app/api/router.py`、`docs/product/ai-project-director/backend-closure-gap-freeze-20260519-v2.md` |
| 新增文件 | `.kkr/skills/ai-project-director/SKILL.md`、`app/domain/project_director_session.py`、`app/repositories/project_director_session_repository.py`、`app/services/project_director_service.py`、`app/api/routes/project_director.py`、`tests/test_project_director_sessions.py`、`docs/product/ai-project-director/verification-project-director-session-phase1-20260519.md` |
| 涉及页面 | 无（未改前端） |
| 涉及接口 | `POST /project-director/sessions`、`GET /project-director/sessions/{id}`、`POST /project-director/sessions/{id}/answers`、`POST /project-director/sessions/{id}/confirm` |
| 页面职责 | N/A |
| 前端真实接入 | N/A（未改前端） |
| 后端闭环 | Backend Pass：4 个 API 真实读写，确定性澄清规则，状态机 draft→clarifying→ready_to_confirm→confirmed |
| 运行证据 | Runtime Evidence Missing：当前环境未做 E2E 运行截图 |
| checklist 回填 | 不适用（后端闭环任务，非页面任务） |
| verification 文档 | `docs/product/ai-project-director/verification-project-director-session-phase1-20260519.md` |
| 禁用按钮清单 | N/A |
| 假按钮检查 | 无（纯后端） |
| 越界检查 | 无：未改前端、未接 AI Provider、未创建任务、未调度 Worker、未写仓库、未改现有接口语义 |
| Gate 结论 | Partial（Backend Pass / Runtime Evidence Missing） |
| 后续动作 | Phase2 补运行证据；后续 Plan Draft 阶段需单独触发 |


### 5.5.1 BCG-01 Hardening Patch（2026-05-19）

| 字段 | 回填 |
|---|---|
| 阶段名称 | BCG-01 Phase1 Hardening Patch |
| 阶段性质 | 后端闭环修补（不新增功能，强化流程约束） |
| 起始 commit | `49a6edf` |
| 结束 commit | （本次提交） |
| 修改文件 | `app/domain/project_director_session.py`、`app/services/project_director_service.py`、`app/api/routes/project_director.py`、`tests/test_project_director_sessions.py` |
| 行为变化 | ClarifyingQuestion 新增 required 字段；submit_answers 检查 required 才进入 ready_to_confirm；confirm_goal 校验 required；confirm 返回完整 SessionResponse；空白 goal 返回 422；短目标检测改用字符数 |
| 涉及接口 | 4 个端点行为微调，无新增/删除 |
| 测试结果 | 38/38 通过（新增 7 个，更新 3 个） |
| Gate 结论 | Partial（Backend Pass / Runtime Evidence Missing，同 Phase1） |


### 5.5.2 BCG-02 Phase1 — Plan Version / Plan Approval（2026-05-19）

| 字段 | 回填 |
|---|---|
| 阶段名称 | BCG-02 Phase1：计划版本生成与确认 |
| 阶段性质 | 后端闭环补齐 |
| 起始 commit | `c260f0a` |
| 结束 commit | （本次提交） |
| 新增文件 | `app/domain/project_director_plan_version.py`、`app/repositories/project_director_plan_version_repository.py`、`app/services/project_director_plan_service.py`、`tests/test_project_director_plan_versions.py` |
| 修改文件 | `app/core/db_tables.py`、`app/api/routes/project_director.py` |
| 涉及页面 | 无（未改前端） |
| 涉及接口 | `POST /project-director/sessions/{id}/plan-versions`、`GET /project-director/sessions/{id}/plan-versions`、`GET /project-director/plan-versions/{id}`、`POST /project-director/plan-versions/{id}/confirm` |
| 页面职责 | N/A |
| 前端真实接入 | N/A（未改前端） |
| 后端闭环 | Backend Pass：4 个 API 真实读写；确定性计划生成；状态机 pending_confirmation→confirmed/superseded；版本递增；confirmed 不创建任务 |
| 运行证据 | Runtime Evidence Missing |
| 测试结果 | 21/21 通过（+ 原有 38/38 无回归 = 总计 59/59） |
| verification 文档 | `docs/product/ai-project-director/verification-project-director-plan-version-phase1-20260519.md` |
| Gate 结论 | Partial（Backend Pass / Runtime Evidence Missing） |
| 后续动作 | 后续接 Task Creation 阶段，需单独触发 |


### 5.5.2.1 BCG-02 Hardening Patch（2026-05-19）

| 字段 | 回填 |
|---|---|
| 阶段名称 | BCG-02 Phase1 Hardening Patch |
| 阶段性质 | 后端闭环修补（role code 对齐 ProjectRoleCode + TaskTable 行数断言） |
| 起始 commit | `68fed10` |
| 结束 commit | （本次提交） |
| 修改文件 | `app/domain/project_director_plan_version.py`、`app/services/project_director_plan_service.py`、`tests/test_project_director_plan_versions.py` |
| 行为变化 | ProposedTask.suggested_role_code → ProjectRoleCode 枚举；developer→engineer；frontend_developer→engineer；tester→reviewer；confirm 后 TaskTable 行数断言 |
| 测试结果 | 24/24 通过（新增 3 个 role code 测试）+ 38/38 无回归 = 62/62 |
| Gate 结论 | Partial（Backend Pass / Runtime Evidence Missing，同 BCG-02） |


### 5.5.3 BCG-03 Phase1 — Pending Confirmation Inbox（2026-05-19）

| 字段 | 回填 |
|---|---|
| 阶段名称 | BCG-03 Phase1：待确认事项聚合 Inbox（只读） |
| 阶段性质 | 后端闭环补齐 |
| 起始 commit | `81da300` |
| 结束 commit | （本次提交） |
| 新增文件 | `app/services/project_director_confirmation_service.py`、`tests/test_project_director_confirmations.py` |
| 修改文件 | `app/repositories/project_director_session_repository.py`、`app/repositories/project_director_plan_version_repository.py`、`app/api/routes/project_director.py` |
| 涉及页面 | 无（未改前端） |
| 涉及接口 | `GET /project-director/confirmations`、`GET /project-director/projects/{id}/confirmations`、`GET /project-director/sessions/{id}/confirmations` |
| 页面职责 | N/A |
| 前端真实接入 | N/A（未改前端） |
| 后端闭环 | Backend Pass：3 个只读 API 聚合 goal_confirmation + plan_confirmation；按 project/session 过滤；confirm_api_hint 指引 |
| 运行证据 | Runtime Evidence Missing |
| 测试结果 | 12/12 通过（+ 原有 62/62 无回归 = 总计 74/74） |
| verification 文档 | `docs/product/ai-project-director/verification-project-director-confirmation-inbox-phase1-20260519.md` |
| Gate 结论 | Partial（Backend Pass / Runtime Evidence Missing） |
| 后续动作 | 后续补确认动作接口 + 扩展更多聚合源 |

### 5.5.3.1 BCG-03 Hardening Patch（2026-05-20）

| 字段 | 回填 |
|---|---|
| 阶段名称 | BCG-03 Phase1 Hardening Patch |
| 阶段性质 | 测试证据补强（不新增功能，不新增 API，不改前端） |
| 起始 commit | `83a7fbf` |
| 结束 commit | （本次提交） |
| 修改文件 | `tests/test_project_director_confirmations.py` |
| 行为变化 | 无（仅新增/增强测试） |
| 新增测试 | `test_project_id_positive_filter_goal_confirmation`：真实 project + session → project 过滤命中 goal_confirmation；`test_project_id_positive_filter_plan_confirmation`：真实 project + plan version → project 过滤命中 plan_confirmation；`test_plan_version_read_only_state_invariant`：三端点查询后 plan version 状态不变 |
| 原有测试 | `test_filter_by_project_id` 重命名为 `test_filter_by_random_project_id_returns_empty`（语义更明确），功能不变 |
| 测试结果 | 确认收件箱 15/15 通过（+3 new）；全局 77/77 通过（38 sessions + 24 plan versions + 15 confirmations） |
| 涉及接口 | 无新增/删除 |
| 涉及页面 | 无（未改前端） |
| Gate 结论 | Partial（Backend Pass / Runtime Evidence Missing，同 BCG-03 Phase1） |
| 后续动作 | 后续补确认动作接口 + 扩展更多聚合源 |


### 5.5.4 BCG-04A Phase1 — Plan-to-Task Creation（2026-05-20）

| 字段 | 回填 |
|---|---|
| 阶段名称 | BCG-04A Phase1：Confirmed Plan → Real Task Queue |
| 阶段性质 | 后端闭环补齐 |
| 起始 commit | `678f12d` |
| 结束 commit | （本次提交） |
| 新增文件 | `app/domain/project_director_task_creation.py`、`app/repositories/project_director_task_creation_repository.py`、`app/services/project_director_task_creation_service.py`、`tests/test_project_director_task_creation.py`、`docs/product/ai-project-director/verification-project-director-task-creation-phase1-20260520.md` |
| 修改文件 | `app/core/db_tables.py`（新增 `ProjectDirectorTaskCreationRecordTable`）、`app/api/routes/project_director.py`（新增 2 个路由 + DTO + 依赖注入） |
| 涉及页面 | 无（未改前端） |
| 涉及接口 | `POST /project-director/plan-versions/{id}/create-tasks`、`GET /project-director/plan-versions/{id}/created-tasks` |
| 页面职责 | N/A |
| 前端真实接入 | N/A（未改前端） |
| 后端闭环 | Backend Pass：confirmed plan version → real task queue；TaskCreationRecord 追溯；重复创建 409；project_id 缺失 409；source_draft_id 追溯 |
| 运行证据 | Runtime Evidence Missing |
| 测试结果 | 13/13 通过（+ 原有 77/77 无回归 = 总计 90/90） |
| 重点策略 | 重复 create-tasks → 409 Conflict；project_id 缺失 → 409 Conflict；不调用 Worker/planning/apply/repo |
| 优先级映射 | high→HIGH, urgent→URGENT, low→LOW, default→NORMAL |
| 追溯设计 | `Task.source_draft_id` 存储 `pdv:{plan_version_id}:{version_no}`；新增 `project_director_task_creation_records` 表记录完整映射 |
| verification 文档 | `docs/product/ai-project-director/verification-project-director-task-creation-phase1-20260520.md` |
| 禁用按钮清单 | N/A |
| 假按钮检查 | 无（纯后端） |
| 越界检查 | 无：未改前端、未接 AI Provider、未调度 Worker、未调用 planning/apply、未写仓库、未改现有接口语义 |
| Gate 结论 | Partial（Backend Pass / Runtime Evidence Missing） |
| 后续动作 | 后续接 Worker 调度执行；不做本阶段自动执行 |


### 5.5.4.1 BCG-04A Hardening Patch（2026-05-20）

| 字段 | 回填 |
|---|---|
| 阶段名称 | BCG-04A Phase1 Hardening Patch |
| 阶段性质 | 后端闭环加固（不新增功能，不新增 API，不改前端） |
| 起始 commit | `0c47547` |
| 结束 commit | （本次提交） |
| 修改文件 | `app/repositories/task_repository.py`（新增 `add_no_commit`）、`app/services/project_director_task_creation_service.py`（原子事务 + 前置预校验 + 空 description 兜底）、`tests/test_project_director_task_creation.py`（+4 hardening 测试） |
| 行为变化 | 1) Task + TaskCreationRecord 原子事务（add_no_commit + 单 commit）；2) 前置预校验（title/role_code/priority_hint 在 DB 写入前校验）；3) 空 description → `"由计划版本生成的任务：{title}"` 兜底 |
| 新增测试 | `test_create_tasks_atomic_task_count_matches_record`：原子性验证；`test_empty_proposed_task_description_falls_back_to_title`：空 description 兜底；`test_duplicate_create_tasks_still_returns_409`：hardening 后重复创建仍 409；`test_atomic_rollback_on_record_creation_failure`：记录失败时无残留 Task |
| 原有测试 | 13 个测试全部继续通过 |
| 测试结果 | 任务创建 17/17 通过；全局 94/94 通过（38 + 24 + 15 + 17） |
| 涉及接口 | 无新增/删除 |
| 涉及页面 | 无（未改前端） |
| Gate 结论 | Partial（Backend Pass / Runtime Evidence Missing，同 BCG-04A Phase1） |
| 后续动作 | 后续接 Worker 调度执行 |


### IPV4_REDACTED BCG-04A Event-Consistency Hardening Patch (2026-05-24)

| Field | Backfill |
|---|---|
| Phase | BCG-04A Phase1 Event-Consistency Hardening Patch |
| Scope | Backend event-consistency hardening only; no new API; no frontend change; no Worker scheduling |
| Start commit | `cdf3205` |
| End commit | this commit |
| Goal | Prevent ghost task_created events when add_no_commit flushes Task rows but TaskCreationRecord creation later fails and rolls back |
| Changed files | `app/repositories/task_repository.py` (`add_no_commit` no longer publishes; new `publish_created()` for post-commit emission), `app/services/project_director_task_creation_service.py` (publish created events only after TaskCreationRecord commit succeeds), `tests/test_project_director_task_creation.py` (event consistency + rollback row-count validation) |
| Behavior change | 1) `TaskRepository.create()` still publishes after its own commit; 2) `TaskRepository.add_no_commit()` only flushes/refreshes and emits no event; 3) BCG-04A batch emits created events after the single Task + TaskCreationRecord commit point succeeds; 4) rollback path emits no task_created event |
| Added/enhanced tests | `test_create_tasks_publishes_events_only_after_commit`: success path emits one created event per committed Task and event IDs match DB rows; `test_atomic_rollback_on_record_creation_failure`: enhanced to verify zero committed `TaskTable` rows and zero ghost events after rollback |
| Test command | `cd runtime/orchestrator && .\.venv\Scripts\python.exe -m pytest tests/test_project_director_task_creation.py -q` |
| Test result | 18/18 task-creation tests passed; 1 existing DeprecationWarning (`HTTP_422_UNPROCESSABLE_ENTITY`) |
| Boundary | No Worker scheduling; no task execution; no planning/apply; no frontend change; apps/web build not run |
| Gate | Partial (Backend Pass / Runtime Evidence Missing, same as BCG-04A Phase1; not total closure Pass) |
| Next | Worker/runtime evidence remains future work for total Gate |


### IPV4_REDACTED BCG-05A Phase1 - Created Task to Worker Run Evidence (2026-05-24)

| Field | Backfill |
|---|---|
| Phase | BCG-05A Created Task -> Worker Run Evidence Phase1 |
| Scope | Backend/runtime evidence only; no auto scheduling; no frontend change |
| Baseline | `cb2a33e` (BCG-04A event-consistency hardening) |
| End commit | this commit |
| Goal | Prove a real Task created by BCG-04A can be manually claimed by the existing Worker entrypoint and converted into a persisted Run |
| Worker entrypoint | `POST /workers/run-once?project_id={project_id}` |
| Evidence chain | Project Director session confirm -> plan version confirm -> `POST /project-director/plan-versions/{id}/create-tasks` creates real Task rows with `source_draft_id=pdv:{plan_version_id}:{version_no}` -> `POST /workers/run-once?project_id=...` claims one created Task -> Worker creates and finalizes a `RunTable` row linked by `run.task_id == task.id` |
| Executor mode | Explicit `simulate:` input_summary was used in the test to avoid real Provider/network dependency. No provider_mock and no provider_reported call were used. |
| Changed files | `tests/test_project_director_worker_run_evidence.py` (new evidence test), `backend-closure-gap-freeze-20260519-v2.md`, `execution-plan-backfill-ledger-20260519.md`, `verification-project-director-created-task-worker-run-phase1-20260524.md` |
| Test command | `cd runtime/orchestrator && .\.venv\Scripts\python.exe -m pytest tests/test_project_director_worker_run_evidence.py tests/test_project_director_task_creation.py -q` |
| Test result | 19 passed, 1 existing DeprecationWarning (`HTTP_422_UNPROCESSABLE_ENTITY`) |
| Boundary | Manual Worker entrypoint only; no automatic dispatch after task creation; no Worker pool requirement; no planning/apply; no repository write; no frontend change; apps/web build not run |
| Gate | Partial: BCG-05A created-task -> worker -> run evidence passed with simulate executor; BCG-05 provider_reported runtime evidence and AI Project Director total closure remain not passed |
| Next | Run provider_reported Worker evidence separately for full BCG-05/runtime gate |


### IPV4_REDACTED BCG-05B Provider-Reported Worker Runtime Evidence (2026-05-24)

| Field | Backfill |
|---|---|
| Phase | BCG-05B Provider-Reported Worker Runtime Evidence |
| Scope | Runtime evidence for existing manual Worker entrypoint; no frontend change; no automatic scheduling |
| Baseline | `59e32f3` (BCG-05A simulate Worker evidence) |
| End commit | this commit |
| Provider config | Saved provider config was present: provider type `deepseek`, base URL `https://api.deepseek.com`, model preset `deepseek`, model `deepseek-v4-pro`, timeout 30s. API key was present but not printed. |
| Worker entrypoint | `POST /workers/run-once?project_id=423367da-966b-4c2e-b8c8-a4ff5f7f2377` |
| Evidence chain | Project Director session confirm -> plan version confirm -> BCG-04A create-tasks -> manual Worker run-once -> task completed -> Run succeeded with `token_accounting_mode=provider_reported` |
| Evidence IDs | project_id `423367da-966b-4c2e-b8c8-a4ff5f7f2377`; session_id `1177d06d-1c71-4e17-979a-855645ea87d8`; plan_version_id `8b906cf9-b7c0-49b3-b7e7-1d7a918ad956`; task_id `db204e31-f244-4f9b-a469-abcc5e0b873f`; run_id `834b38aa-3669-4121-9424-3aa4999cad2e` |
| Provider evidence | provider_key `deepseek`; model_name `deepseek-v4-pro`; provider_receipt_id `3d8bf6e7-fdfd-43db-bd9a-3abee685521d`; prompt_tokens 380; completion_tokens 66; total_tokens 446; estimated_cost 0.000768; log_path `logs/task-runs/db204e31-f244-4f9b-a469-abcc5e0b873f/834b38aa-3669-4121-9424-3aa4999cad2e.jsonl` |
| Executor mode | Real provider execution: Worker response `execution_mode=provider_openai`; persisted Run `token_accounting_mode=provider_reported`. Verification step used existing simulate verifier. |
| Test command | `cd runtime/orchestrator && .\.venv\Scripts\python.exe -m pytest tests/test_project_director_sessions.py tests/test_project_director_plan_versions.py tests/test_project_director_confirmations.py tests/test_project_director_task_creation.py tests/test_project_director_worker_run_evidence.py -q` |
| Test result | 96 passed, 3 existing DeprecationWarnings (`HTTP_422_UNPROCESSABLE_ENTITY`) |
| Boundary | No automatic Worker dispatch; no Worker pool requirement; no planning/apply; no repository write; no frontend change; apps/web build not run |
| Gate | BCG-05B provider_reported runtime evidence passed. AI Project Director total closure remains Partial; do not mark total closure Pass. |
| Next | Feed this evidence into the later total Gate rollup with repository/delivery/approval/governance/cost evidence. |

### IPV4_REDACTED BCG-07A Run Evidence Replay / Decision History Evidence (2026-05-24)

| Field | Backfill |
|---|---|
| Phase | BCG-07A Run Evidence Replay / Decision History Evidence |
| Scope | Backend/runtime read evidence only; no frontend change; no automatic scheduling |
| Baseline | `e14b857` (BCG-05B provider-reported Worker evidence on latest `origin/main`) |
| End commit | this commit |
| Goal | Prove a Project Director-created task and its manual Worker run can be replayed through task/run/log/decision-history read APIs |
| Read-only API | Reused existing `GET /tasks/{task_id}/runs`, `GET /runs/{run_id}/logs`, `GET /runs/{run_id}/decision-trace`, `GET /tasks/{task_id}/decision-history`; no new read-only API was required |
| New write API | None |
| Evidence chain | Project Director session confirm -> plan version confirm -> BCG-04A create-tasks -> manual Worker run-once -> persisted task/run -> run JSONL logs -> run decision trace -> task decision history |
| Runtime events asserted | `task_routed`, `role_handoff`, `run_claimed`, `context_built`, `execution_finished`, `verification_finished`, `cost_estimated`, `run_finalized` |
| Backend adjustment | `DecisionReplayService._build_headline` now prefers core run replay events such as `run_finalized`, guard, verification, and execution events before falling back to later auxiliary log events |
| Changed files | `runtime/orchestrator/app/services/decision_replay_service.py`, `runtime/orchestrator/tests/test_project_director_run_evidence_replay.py`, `docs/product/ai-project-director/verification-project-director-run-evidence-replay-20260524.md`, `docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md` |
| Test command | Focused: `cd runtime/orchestrator && .\.venv\Scripts\python.exe -m pytest tests/test_project_director_run_evidence_replay.py -q`; regression: `cd runtime/orchestrator && .\.venv\Scripts\python.exe -m pytest tests/test_project_director_sessions.py tests/test_project_director_plan_versions.py tests/test_project_director_confirmations.py tests/test_project_director_task_creation.py tests/test_project_director_worker_run_evidence.py tests/test_project_director_run_evidence_replay.py -q` |
| Test result | Focused: 1 passed; regression: 97 passed, 3 existing `HTTP_422_UNPROCESSABLE_ENTITY` deprecation warnings |
| Frontend/build | No frontend files changed; `apps/web` build not run |
| Boundary | Manual Worker evidence only; no planning/apply; no repository write; no new write API; no UI work; this is run evidence replay, not total closure Pass |
| Gate | BCG-07A evidence-replay phase Pass. AI Project Director total closure remains Partial; do not mark total closure Pass. |
| Next | Feed BCG-07A replay evidence into later total Gate rollup together with repository/delivery/approval/governance/cost evidence. |

### IPV4_REDACTED BCG-07B Provider-Reported Run Evidence Replay (2026-05-24)

| Field | Backfill |
|---|---|
| Phase | BCG-07B Provider-Reported Run Evidence Replay |
| Scope | Backend/runtime read evidence only; replay existing provider-reported run; no frontend change; no automatic scheduling |
| Baseline | `e30d05e` (BCG-07A run logs / decision trace / decision history read-path evidence) |
| End commit | this commit |
| Reuse decision | Reused BCG-05B old run `834b38aa-3669-4121-9424-3aa4999cad2e`; no new provider run was triggered because local DB/log evidence was present |
| Evidence IDs | project_id `423367da-966b-4c2e-b8c8-a4ff5f7f2377`; session_id `1177d06d-1c71-4e17-979a-855645ea87d8`; plan_version_id `8b906cf9-b7c0-49b3-b7e7-1d7a918ad956`; task_id `db204e31-f244-4f9b-a469-abcc5e0b873f`; run_id `834b38aa-3669-4121-9424-3aa4999cad2e` |
| Provider evidence | provider_key `deepseek`; model_name `deepseek-v4-pro`; execution_mode `provider_openai`; actual_execution_mode `provider_openai`; fallback_applied `false`; token_accounting_mode `provider_reported`; receipt `3d8bf6e7-fdfd-43db-bd9a-3abee685521d`; prompt_tokens 380; completion_tokens 66; total_tokens 446; estimated_cost 0.000768 |
| Log path | `logs/task-runs/db204e31-f244-4f9b-a469-abcc5e0b873f/834b38aa-3669-4121-9424-3aa4999cad2e.jsonl` |
| Read-only API | Reused existing `GET /project-director/sessions/{session_id}`, `GET /project-director/plan-versions/{plan_version_id}`, `GET /project-director/plan-versions/{plan_version_id}/created-tasks`, `GET /tasks/{task_id}/runs`, `GET /runs/{run_id}/logs`, `GET /runs/{run_id}/decision-trace`, `GET /tasks/{task_id}/decision-history`; no new read-only API was required |
| New write API | None |
| Evidence chain | BCG-05B Project Director session/plan/task -> existing provider Worker run -> persisted provider_reported run row -> JSONL logs -> run decision trace -> task decision history |
| Runtime events replayed | `task_routed`, `role_handoff`, `run_claimed`, `context_built`, `memory_governance_checkpointed`, `execution_plan_ready`, `prompt_contract_built`, `execution_finished`, `verification_finished`, `token_accounting_ready`, `cost_estimated`, `run_finalized`, `approval_auto_created` |
| Decision replay summary | `GET /runs/{run_id}/decision-trace` returned 13 trace items including provider execution, provider-reported token accounting, cost, and finalize; `GET /tasks/{task_id}/decision-history` returned one succeeded item with headline `Task and run were finalized.` |
| Changed files | `runtime/orchestrator/scripts/bcg07b_provider_reported_replay_live.py`, `docs/product/ai-project-director/verification-project-director-provider-reported-run-evidence-replay-20260524.md`, `docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md` |
| Live command | `cd runtime/orchestrator && .\.venv\Scripts\python.exe scripts\bcg07b_provider_reported_replay_live.py` |
| Live result | Passed; reused existing BCG-05B run; log_event_count 13; trace_item_count 13; decision_history_items 1 |
| Regression command | `cd runtime/orchestrator && .\.venv\Scripts\python.exe -m pytest tests/test_project_director_sessions.py tests/test_project_director_plan_versions.py tests/test_project_director_confirmations.py tests/test_project_director_task_creation.py tests/test_project_director_worker_run_evidence.py tests/test_project_director_run_evidence_replay.py -q` |
| Regression result | 97 passed, 3 existing `HTTP_422_UNPROCESSABLE_ENTITY` deprecation warnings |
| Frontend/build | No frontend files changed; `apps/web` build not run |
| Boundary | No mock/simulate execution substituted for provider evidence; the original run's verifier was simulate, but provider execution was real `provider_openai` with `provider_reported` accounting and no fallback. No planning/apply; no repository write; no new write API; no UI work; this is provider run evidence replay, not total closure Pass |
| Gate | BCG-07B provider-reported replay phase Pass. AI Project Director total closure remains Partial; do not mark total closure Pass. |
| Next | Feed BCG-07B provider replay evidence into later total Gate rollup together with repository/delivery/approval/governance/cost evidence. |

### IPV4_REDACTED BCG-08A Real AI Run Summary Evidence (2026-05-24)

| Field | Backfill |
|---|---|
| Phase | BCG-08A Real AI Run Summary Evidence |
| Scope | Backend/runtime live AI summary evidence only; reuse existing provider-reported run; no frontend change |
| Baseline | `6544372` (BCG-07B provider-reported run evidence replay) |
| End commit | this commit |
| Target run | run_id `834b38aa-3669-4121-9424-3aa4999cad2e`; task_id `db204e31-f244-4f9b-a469-abcc5e0b873f`; provider_key `deepseek`; model_name `deepseek-v4-pro`; token_accounting_mode `provider_reported` |
| Summary API | `POST /runs/{run_id}/ai-summary/regenerate`, `GET /runs/{run_id}/ai-summary`, `GET /runs/{run_id}/ai-summaries` |
| Real model call | Yes. Existing `RunAISummaryService` used provider config and `OpenAIProviderExecutorService.generate_text`; no API key was printed or written. |
| Summary evidence | summary_id `9a229984-f5bd-4773-a6de-9db61786b837`; source `ai`; status `succeeded`; model_provider `deepseek`; model_name `deepseek-v4-pro`; provider_receipt_id `dbec655b-49b2-4639-9757-70b71ce4347f`; error_summary `null`; stale `false` |
| Persistence/readback | `GET /runs/{run_id}/ai-summary` returned the generated summary as active; `GET /runs/{run_id}/ai-summaries` returned it in history with `history_active_summary_id=9a229984-f5bd-4773-a6de-9db61786b837` and `history_count=2` |
| Traceability | source_version `run.summary.v2`; source_fingerprint/source_hash `dfa78dc0fa548a858295ae7b742e4f9b14dbe833c60c977c61ed5b81df6c5df0`; prompt_hash `080d4beb982c1dd76dca985e0cbee2e208adf650f942cbe35c7a3d1b67a05126` |
| Content summary | AI markdown says the provider run succeeded, `deepseek/deepseek-v4-pro` returned the expected evidence sentence, the original run verifier passed, and the quality gate allowed completion; it cites original run receipt `3d8bf6e7-fdfd-43db-bd9a-3abee685521d` and execution mode `provider_openai` |
| Changed files | `runtime/orchestrator/scripts/bcg08a_real_ai_run_summary_live.py`, `docs/product/ai-project-director/verification-project-director-real-ai-run-summary-20260524.md`, `docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md` |
| Live command | `cd runtime/orchestrator && .\.venv\Scripts\python.exe scripts\bcg08a_real_ai_run_summary_live.py` |
| Live result | Passed; real_model_called `true`; source `ai`; fallback not used; generated summary persisted and read back through current/history APIs |
| Regression command | `cd runtime/orchestrator && .\.venv\Scripts\python.exe -m pytest tests/test_run_ai_summaries.py tests/test_project_director_sessions.py tests/test_project_director_plan_versions.py tests/test_project_director_confirmations.py tests/test_project_director_task_creation.py tests/test_project_director_worker_run_evidence.py tests/test_project_director_run_evidence_replay.py -q` |
| Regression result | 132 passed, 3 existing `HTTP_422_UNPROCESSABLE_ENTITY` deprecation warnings |
| Frontend/build | No frontend files changed; `apps/web` build not run |
| Boundary | No new write API; no frontend work; no mock/simulate substitute for summary generation; original target run remains the BCG-05B real provider run; this is run summary evidence, not total closure Pass |
| Gate | BCG-08A real AI run summary evidence phase Pass. AI Project Director total closure remains Partial; do not mark total closure Pass |
| Next | Feed BCG-08A summary evidence into later total Gate rollup with repository/delivery/approval/governance/cost evidence. |

### BCG-08A-R2 Real AI Run Summary Copy Guard Closure (2026-05-24)

| Field | Backfill |
|---|---|
| Phase | BCG-08A-R2 Real AI Run Summary Evidence minimum closure |
| Scope | Minimum acceptance hardening only; no new feature work; do not enter BCG-09 |
| Baseline | `350ed7a` (BCG-08A-R1 real AI summary evidence closure) |
| Target run | Reused run_id `834b38aa-3669-4121-9424-3aa4999cad2e`; task_id `db204e31-f244-4f9b-a469-abcc5e0b873f`; provider_key `deepseek`; model_name `deepseek-v4-pro`; token_accounting_mode `provider_reported` |
| Summary API | Reused existing `POST /runs/{run_id}/ai-summary/regenerate`, `GET /runs/{run_id}/ai-summary`, `GET /runs/{run_id}/ai-summaries`; no new API |
| Service change | None in R2. `run_ai_summary_service.py` was not changed; R2 only tightens live evidence copy-guard assertions and docs |
| Copy guard | Added hard assertions that `summary_markdown.strip()` differs from raw `run.result_summary.strip()` and raw `run.verification_summary.strip()`, and that markdown is not a raw result/verification excerpt followed only by trailing punctuation/formatting and end-of-text |
| Live evidence | summary_id `74fe9426-e869-43a7-95ed-933fcc75edc0`; source `ai`; fallback_used `false`; error_summary `null`; history active summary points to generated summary |
| Copy guard result | `summary_differs_from_result_summary=true`; `summary_differs_from_verification_summary=true`; `summary_not_result_summary_then_end=true`; `summary_not_verification_summary_then_end=true` |
| Evidence coverage | provider_key/model_name/original_run_receipt/execution_mode/token_accounting_mode/total_tokens/estimated_cost/log_path/quality_gate all `true` |
| Live command | `python runtime/orchestrator/scripts/bcg08a_real_ai_run_summary_live.py` |
| Live result | Passed; real provider summary generation persisted and read back; copy guard passed |
| Regression command | `cd runtime/orchestrator && python -m pytest tests` |
| Regression result | 132 passed, 127 warnings |
| Frontend/build | No frontend files changed; `apps/web` build not run |
| Boundary | No new write API; no mock/simulate substitute for summary generation; no repository write; no BCG-09 work; not total closure Pass |
| Gate | BCG-08A-R2 minimum closure Pass. AI Project Director total closure remains Partial |


### BCG-09A Provider Run Deliverable & Approval Live Evidence (2026-05-24)

| Field | Backfill |
|---|---|
| Phase | BCG-09A Provider Run → Auto Deliverable → Auto Approval Evidence |
| Scope | Runtime evidence verification only; no new API; no frontend change |
| Baseline | `681c39a` (BCG-08A copy guard evidence on latest `origin/main`) |
| End commit | this commit |
| Target run | Reused BCG-05B provider_reported run `834b38aa-3669-4121-9424-3aa4999cad2e`; task_id `db204e31-f244-4f9b-a469-abcc5e0b873f`; provider_key `deepseek`; model_name `deepseek-v4-pro`; token_accounting_mode `provider_reported` |
| Reused BCG-05B | Yes. Deliverable and approval were already auto-generated during original BCG-05B Worker execution. No new run was needed. |
| Evidence IDs | project_id `423367da-966b-4c2e-b8c8-a4ff5f7f2377`; task_id `db204e31-f244-4f9b-a469-abcc5e0b873f`; run_id `834b38aa-3669-4121-9424-3aa4999cad2e`; deliverable_id `3ae2a721-4396-453e-8d1b-529a50efb29c`; approval_id `90714664-41d5-41fb-8156-59fc9a784a22`; deliverable_version `1`; approval_status `pending_approval` |
| Auto-created | Yes. Deliverable created by `_auto_create_run_deliverable()` in Worker pipeline (task_worker.py:798-813). Approval created by `_auto_create_run_approval()` immediately after. Both during original BCG-05B Worker execution. |
| Not forged | Confirmed. No manual POST /deliverables or POST /approvals used. request_note contains `[自动生成]` marker with Task ID and Run ID. |
| Changed files | `runtime/orchestrator/scripts/bcg09a_provider_run_deliverable_approval_live.py` (new), `docs/product/ai-project-director/verification-project-director-provider-run-deliverable-approval-20260524.md` (new), `docs/product/ai-project-director/backend-closure-gap-freeze-20260519-v2.md` (update BCG-09 status), `docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md` (this record) |
| Read APIs used | `GET /tasks/{task_id}/runs`, `GET /runs/{run_id}/logs`, `GET /deliverables/projects/{project_id}`, `GET /deliverables/tasks/{task_id}`, `GET /approvals/projects/{project_id}`, `GET /approvals/{approval_id}`, `GET /approvals/{approval_id}/history` |
| New write API | None |
| Repository paths used | `DeliverableRepository.find_by_source_run_id()`, `ApprovalRepository.get_latest_record_by_deliverable_id()` |
| Live command | `cd runtime/orchestrator && .\.venv\Scripts\python.exe scripts\bcg09a_provider_run_deliverable_approval_live.py` |
| Live result | Passed; 46/46 checks; reused BCG-05B run; auto-created deliverable and approval confirmed |
| Run verification | run found; task_id matches; provider_key=deepseek; model_name=deepseek-v4-pro; token_accounting_mode=provider_reported; provider_receipt_id=3d8bf6e7-fdfd-43db-bd9a-3abee685521d; status=succeeded; quality_gate_passed=true; fallback_applied false; execution not provider_mock |
| Deliverable verification | found by source_run_id; project_id matches; source_task_id matches; source_run_id matches; title/content/summary non-empty; content has Task ID/Run ID/Execution mode/Run status/Verification evidence/Token/Cost evidence; readable via project and task APIs |
| Approval verification | found for deliverable; project_id matches; deliverable_id matches; request_note has `[自动生成]` + Task ID + Run ID; status=pending_approval; readable via project API, detail API, and history API |
| Regression command | `cd runtime/orchestrator && .\.venv\Scripts\python.exe -m pytest tests/test_project_director_sessions.py tests/test_project_director_plan_versions.py tests/test_project_director_confirmations.py tests/test_project_director_task_creation.py tests/test_project_director_worker_run_evidence.py tests/test_project_director_run_evidence_replay.py tests/test_run_ai_summaries.py -q` |
| Regression result | 132 passed, 3 existing `HTTP_422_UNPROCESSABLE_ENTITY` deprecation warnings |
| Frontend/build | No frontend files changed; `apps/web` build not run |
| Boundary | No mock/simulate/provider_mock; no manual deliverable/approval creation; no new write API; no planning/apply; no repository write; no Worker pool; no frontend change; no total closure Pass |
| Gate | BCG-09A provider run deliverable/approval evidence Pass. BCG-09 is now Runtime Evidence Pass for provider-run deliverable/approval evidence. AI Project Director total closure remains Partial. Do not mark total closure Pass. |
| Next | BCG-10 (approval rework → task queue), BCG-11+ (repository binding/snapshots), Release Gate (BCG-18), governance/cost, total rollup |


### BCG-10A Approval Request Changes → Rework Live Evidence (2026-05-24)

| Field | Backfill |
|---|---|
| Phase | BCG-10A Approval Request Changes → Rework Evidence Chain |
| Scope | Runtime evidence verification; applies real request_changes decision; no new API; no frontend change |
| Baseline | `3060b6c` (BCG-09A deliverable/approval evidence on latest `origin/main`) |
| End commit | this commit |
| Target approval | Reused BCG-09A auto-generated approval `90714664-41d5-41fb-8156-59fc9a784a22` (pending_approval); project_id `423367da-966b-4c2e-b8c8-a4ff5f7f2377`; deliverable_id `3ae2a721-4396-453e-8d1b-529a50efb29c` |
| Reused BCG-09A | Yes. Approval was still pending_approval. Applied request_changes via POST /approvals/{id}/actions. |
| Evidence IDs | project_id `423367da-966b-4c2e-b8c8-a4ff5f7f2377`; task_id `db204e31-f244-4f9b-a469-abcc5e0b873f`; run_id `834b38aa-3669-4121-9424-3aa4999cad2e`; deliverable_id `3ae2a721-4396-453e-8d1b-529a50efb29c`; approval_id `90714664-41d5-41fb-8156-59fc9a784a22`; decision_id `6c1e2340-762f-4e19-a5c0-2ac6a5176c55` |
| Status change | pending_approval → changes_requested |
| Action API | `POST /approvals/{approval_id}/actions` with action=request_changes |
| Request body | action=request_changes, actor_name=老板, summary="BCG-10A requests changes for rework evidence", comment="要求根据 BCG-10A 验收补充返工说明", requested_changes=[2 items], highlighted_risks=[1 item] |
| Changed files | `runtime/orchestrator/scripts/bcg10a_approval_request_changes_rework_live.py` (new), `docs/product/ai-project-director/verification-project-director-approval-request-changes-rework-20260524.md` (new), `docs/product/ai-project-director/backend-closure-gap-freeze-20260519-v2.md` (update BCG-10 status), `docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md` (this record) |
| Read APIs used | `GET /approvals/{approval_id}`, `POST /approvals/{approval_id}/actions`, `GET /deliverables/tasks/{task_id}`, `GET /approvals/{approval_id}/history`, `GET /approvals/projects/{project_id}`, `GET /approvals/projects/{project_id}/change-rework`, `GET /tasks` |
| New write API | None (POST /approvals/{id}/actions is existing) |
| Live command | `cd runtime/orchestrator && .\.venv\Scripts\python.exe scripts\bcg10a_approval_request_changes_rework_live.py` |
| Live result | 61/61 passed; approval status changed pending_approval → changes_requested; decision persisted; history shows rework_required; change-rework snapshot shows rework cycle |
| Idempotency | Second run correctly skips Phase 3 and re-verifies all read paths |
| Approval detail | status=changes_requested; decided_at populated; latest_decision.action=request_changes; requested_changes and highlighted_risks preserved |
| Approval history | deliverable_id matches; latest_approval_status=changes_requested; negative_decision_count=1; rework_status=rework_required; steps: approval_requested + approval_decided; decided step has decision_action=request_changes with full data |
| Change-rework snapshot | approval rework item found; deliverable_id matches; decision_action=request_changes; chain_source=approval_rework; closed=false; requested_changes/highlighted_risks preserved; steps: decision + rework stages; approval_status=null (representation gap: uses latest_higher_record, no resubmitted version yet) |
| Rework task | NOT auto-created. Gap: `visible_rework_no_executable_task` — rework evidence is visible in history + change-rework snapshot but no executable task is created. |
| Regression command | `cd runtime/orchestrator && .\.venv\Scripts\python.exe -m pytest tests/test_project_director_sessions.py tests/test_project_director_plan_versions.py tests/test_project_director_confirmations.py tests/test_project_director_task_creation.py tests/test_project_director_worker_run_evidence.py tests/test_project_director_run_evidence_replay.py tests/test_run_ai_summaries.py -q` |
| Regression result | 132 passed, 3 existing `HTTP_422_UNPROCESSABLE_ENTITY` deprecation warnings |
| Frontend/build | No frontend files changed; `apps/web` build not run |
| Boundary | No mock/simulate/provider_mock; no database modification; no manual deliverable/approval creation; no new write API; no planning/apply; no repository write; no Worker; no frontend change; no total closure Pass |
| Gate | BCG-10A approval rework evidence Pass (61/61). BCG-10 overall Partial (approval rework evidence Pass / executable rework task creation Missing). AI Project Director total closure remains Partial. Do not mark total closure Pass. |
| Next | BCG-12 (file locator / context pack), BCG-13 (change plan / change batch), BCG-14 (preflight), Release Gate (BCG-18), executable rework task creation (if needed), governance/cost, total rollup |


### BCG-11A Repository Binding & Snapshot Live Evidence (2026-05-24)

| Field | Backfill |
|---|---|
| Phase | BCG-11A Repository Binding & Snapshot Live Evidence |
| Scope | Runtime evidence verification; creates sample Git repo, configures allowed roots, binds repo, refreshes snapshot, verifies read-back; no new API; no frontend change |
| Baseline | `800fc95` (BCG-10A approval rework evidence on latest `origin/main`) |
| End commit | this commit |
| Project | Reused BCG evidence project `423367da-966b-4c2e-b8c8-a4ff5f7f2377` |
| Sample repo | Created `runtime/tmp/bcg11a-sample-repo` (7 files, 5 trackable + 2 ignored) |
| Evidence IDs | project_id `423367da-966b-4c2e-b8c8-a4ff5f7f2377`; workspace_id `e1e32ddb-e858-4224-b301-5362f97c1864`; snapshot_id `4a769201-f0f4-4f64-806a-b09b7606950e`; allowed_workspace_root `E:\new-AI-Dev-Orchestrator-push\runtime\tmp` |
| Changed files | `runtime/orchestrator/scripts/bcg11a_repository_binding_snapshot_live.py` (new), `docs/product/ai-project-director/verification-project-director-repository-binding-snapshot-20260524.md` (new), `docs/product/ai-project-director/backend-closure-gap-freeze-20260519-v2.md` (update BCG-11 status), `docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md` (this record) |
| APIs used | `GET /repositories/workspace-settings`, `PUT /repositories/workspace-settings`, `PUT /repositories/projects/{project_id}`, `GET /repositories/projects/{project_id}`, `POST /repositories/projects/{project_id}/snapshot/refresh`, `GET /repositories/projects/{project_id}/snapshot` |
| New write API | None (all APIs are existing) |
| Live command | `cd runtime/orchestrator && .\.venv\Scripts\python.exe scripts\bcg11a_repository_binding_snapshot_live.py` |
| Live result | 57/57 passed; sample Git repo created; allowed roots configured; safety boundary verified; repo bound; snapshot refreshed; read-back consistent |
| Safety boundary | Out-of-bounds path → 422; non-Git directory → 422; valid Git repo → 200 (bind success) |
| Bind result | workspace_id `e1e32ddb-e858-4224-b301-5362f97c1864`; root_path matches; display_name="BCG-11A Evidence Repo"; access_mode=read_only; default_base_branch=main |
| Snapshot result | snapshot_id `4a769201-f0f4-4f64-806a-b09b7606950e`; status=success; scan_error=null; file_count=5; directory_count=4; languages: Markdown(2) JSON(1) Python(1) TypeScript(1); tree includes README.md/src/web/config/docs; ignored: .git/node_modules/__pycache__ applied correctly |
| Snapshot read-back | GET snapshot matches POST refresh in id, file_count, directory_count, root_path, workspace_id, language_breakdown, tree |
| Regression command | `cd runtime/orchestrator && .\.venv\Scripts\python.exe -m pytest tests/test_project_director_sessions.py tests/test_project_director_plan_versions.py tests/test_project_director_confirmations.py tests/test_project_director_task_creation.py tests/test_project_director_worker_run_evidence.py tests/test_project_director_run_evidence_replay.py tests/test_run_ai_summaries.py -q` |
| Regression result | 132 passed, 3 existing `HTTP_422_UNPROCESSABLE_ENTITY` deprecation warnings |
| Frontend/build | No frontend files changed; `apps/web` build not run |
| Boundary | No apply-local; no git-commit; no repository write to main repo; no new write API; no planning/apply; no frontend change; no total closure Pass |
| Gate | BCG-11A repository binding & snapshot evidence Pass (57/57). BCG-11 is now Runtime Evidence Pass for repository binding/snapshot evidence. AI Project Director total closure remains Partial. |
| R1 | 2026-05-24 BCG-11A-R1 hardening: sample repo moved outside main repo tree (`E:\bcg11a-workspaces\`), allowed roots preserved (not overwritten), out-of-bounds existing Git repo rejection test added, language assertions strengthened (Markdown/Python/TypeScript/JSON each verified), location assertions added (71/71). |
| Next | BCG-12 (file locator / context pack), BCG-13 (change plan / change batch), BCG-14 (preflight), Release Gate (BCG-18), governance/cost, total rollup |

### BCG-12A File Locator + Context Pack Live Evidence (2026-05-24)

| Field | Backfill |
|---|---|
| Phase | BCG-12A File Locator + Context Pack Live Evidence |
| Scope | Runtime evidence verification plus BCG-12A-R1 ignored-directory security closeout; reuses BCG-11A bound sample repo; validates file-locator search (3 query types), context-pack build (real file excerpts), and ignored-directory selected_paths blocking; no new API; no frontend change |
| Baseline | `3b05b3c` (Close context pack API acceptance tests on latest `origin/main`) |
| End commit | this commit |
| Evidence project | Reused BCG evidence project `423367da-966b-4c2e-b8c8-a4ff5f7f2377` |
| Reused BCG-11A | Yes. Reused workspace `e1e32ddb-e858-4224-b301-5362f97c1864`, snapshot `4a769201-f0f4-4f64-806a-b09b7606950e`, sample repo `E:\bcg11a-workspaces\bcg11a-sample-repo` |
| Evidence IDs | project_id `423367da-966b-4c2e-b8c8-a4ff5f7f2377`, workspace_id `e1e32ddb-e858-4224-b301-5362f97c1864`, snapshot_id `4a769201-f0f4-4f64-806a-b09b7606950e` |
| Changed files | `runtime/orchestrator/scripts/bcg12a_file_locator_context_pack_live.py` (new), `docs/product/ai-project-director/verification-project-director-file-locator-context-pack-20260524.md` (new), `docs/product/ai-project-director/backend-closure-gap-freeze-20260519-v2.md` (update BCG-12 status), `docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md` (this record) |
| APIs used | `GET /repositories/projects/{project_id}`, `GET /repositories/projects/{project_id}/snapshot`, `POST /repositories/projects/{project_id}/file-locator/search`, `POST /repositories/projects/{project_id}/context-pack` |
| New write API | None (all APIs are existing) |
| Workspace verification | root_path is absolute, read_only, .git exists, outside main repo/runtime_data_dir/system temp |
| Snapshot verification | status=success, scan_error=null, file_count=5, languages=Markdown(2)/JSON(1)/Python(1)/TypeScript(1), tree includes README.md/src/web/config/docs, ignored dirs include `.git`, `.venv`, `__pycache__`, `node_modules`, `dist`, `build` and excluded files stay out of tree |
| File locator A (keywords) | keywords: evidence/repository/context, limit=5, candidate_count=4, candidates: README.md/config/app.json/src/main.py/web/app.tsx |
| File locator B (path_prefixes + file_types) | path_prefixes: src/web/config/docs, file_types: py/tsx/json/md, candidate_count=5, all 5 expected files found |
| File locator C (task_query) | task_query="build context pack for repository binding snapshot evidence", candidate_count=5, scanned_file_count=5 |
| Context pack (from locator B) | selected_paths: README.md/src/main.py/web/app.tsx/config/app.json/docs/spec.md, included_file_count=5, total_included_bytes=419, all entries have non-empty excerpt/match_reasons, source_summary from locator, focus_terms=evidence/context/binding/snapshot |
| Budget truncation | Sample files too small (~215 bytes) to exceed API minimum (512 bytes). Truncation logic verified by `tests/test_repository_context_pack_api.py::test_build_project_context_pack_marks_truncated_when_total_budget_is_exhausted`. |
| Security ../ | ../outside.txt → 422 (Pass) |
| Security absolute path | Absolute script path → 422 (Pass) |
| Security node_modules | node_modules/ignored.js -> 422 blocked (Pass) |
| Security __pycache__ | __pycache__/ignored.py -> 422 blocked (Pass) |
| Security .git | .git/config -> 422 blocked (Pass) |
| Security .venv | .venv/ignored.py -> 422 blocked (Pass) |
| Security dist | dist/ignored.js -> 422 blocked (Pass) |
| Security build | build/ignored.js -> 422 blocked (Pass) |
| Runtime Evidence Gaps | 0 gaps. BCG-12A-R1 blocks `.git`, `node_modules`, `__pycache__`, `.venv`, `dist`, and `build` selected_paths before file read. |
| Live command | `cd runtime/orchestrator && python scripts/bcg12a_file_locator_context_pack_live.py` |
| Live result | 178/178 passed, 0 failed; 0 Runtime Evidence Gaps |
| Regression command | `cd runtime/orchestrator && python -m pytest tests -q` |
| Regression result | 143 passed, 135 warnings in 36.06s |
| Frontend/build | No frontend files changed; `apps/web` build not run |
| Boundary | No apply-local; no git-commit; no repository write to main repo; no new write API; no planning/apply; no frontend change; no mock/simulate; no total closure Pass |
| Gate | **BCG-12A-R1 Pass / BCG-12 Runtime Evidence Pass**. AI Project Director total closure remains Partial. Do not mark total closure Pass. |
| Next | BCG-13 (change plan / change batch), BCG-14 (preflight), Release Gate (BCG-18), governance/cost, total rollup |

### 5.6 端到端闭环总验收

| 字段 | 计划 |
|---|---|
| 阶段性质 | 总 Gate |
| 验收对象 | CL-01~CL-18 |
| 要求 | 目标、计划、任务、运行、仓库、交付、审批、治理、成本全部有证据 |
| 产物 | 总验收报告、截图清单、缺口清单、冻结结论 |
| 预期 | 第一轮大概率 Partial，不应强行总 Pass |

---

## 6. 后续每条 Codex 指令必须声明的字段

以后每条指令开头必须包含：

```text
当前总阶段：AI Project Director 闭环收口
当前子阶段：xxx PhaseN
本阶段性质：前端职责收口 / 真实 API 接入 / 后端闭环补齐 / 运行证据验收 / 文档回填
是否允许后端改动：允许 / 不允许
是否允许新增 API：允许 / 不允许
是否允许改已收口页面：不允许，除非修复回归
本阶段 checklist 范围：xxx-01 ~ xxx-xx
Gate 预期：Pass / Partial / Blocked / Fail
```

并且完成后必须回填：

```text
1. closure-checklist-20260518.md 对应章节
2. execution-plan-backfill-ledger-20260519.md 对应阶段表格
3. 如需要，新增 verification-xxx-phaseN-YYYYMMDD.md
```

---

## 7. 回填模板

以后每个阶段都复制这个模板回填。

```md
### X.X 阶段名称

| 字段 | 回填 |
|---|---|
| 阶段名称 |  |
| 阶段性质 | 前端职责收口 / 真实 API 接入 / 后端闭环补齐 / 运行证据验收 / 文档回填 |
| 起始 commit |  |
| 结束 commit |  |
| 修改文件 |  |
| 涉及页面 |  |
| 涉及接口 |  |
| 页面职责 | Not Started / UI Pass / Partial / Fail |
| 前端真实接入 | Not Started / API Pass / Partial / Fail |
| 后端闭环 | Not Started / Backend Pass / Partial / Blocked / Fail |
| 运行证据 | Not Started / Runtime Pass / Partial / Blocked / Fail |
| checklist 回填 | 已回填 / 未回填 / 不适用 |
| verification 文档 |  |
| 禁用按钮清单 |  |
| 假按钮检查 | 无 / 有，说明 |
| 越界检查 | 无 / 有，说明 |
| Gate 结论 | Pass / Partial / Blocked / Fail |
| 后续动作 |  |
```

---

## 8. 当前不能误判为总 Pass 的事项

以下事项虽然部分页面已完成，但不能误判为总闭环完成：

| 事项 | 当前判断 | 原因 |
|---|---|---|
| AI 项目主管真实对话 | Partial | 工作台主视觉已收口；目标澄清/确认后端已完成（BCG-01 Phase1 Backend Pass）；计划草案/任务创建/Worker 调度尚未接续 |
| 自动作战计划生成与确认 | Partial | 尚未作为完整目标→计划→确认链路验收 |
| 运行摘要自动生成 | Partial | 运行页可读取/手动生成摘要，但全局事件触发自动摘要仍需总验收 |
| 仓库变更需求入口 | Partial | 执行中心页签展示状态，完整操作仍在项目仓库页 |
| 交付物闭环 | Not Started | DEL-* 尚未处理 |
| 审批闭环 | Not Started | APV-* 尚未处理 |
| 治理沉淀 | Not Started | GOV-* 尚未处理 |
| 成本闭环 | Partial | 部分页面展示 token/cost，但 AI 生成资产台账和成本可信度需总验收 |
| 总闭环 CL-01~18 | Partial | 还没有端到端证据链 |

---

## 9. 当前下一步

下一步应执行：

```text
成果中心 Phase1：交付物 / 审批入口与职责收口
```

执行目标不是直接写一堆 UI，而是：

1. 先看现有交付物和审批页面。
2. 明确哪些按钮有真实 API。
3. 没有真实后端闭环的按钮必须禁用或标 Partial。
4. 回填 DEL-* 和 APV-*。
5. 同步更新本台账。

---

## 10. 文档治理规则

1. `page-information-architecture-20260518.md` 只在产品定义变化时修改。
2. `closure-flow-20260518.md` 只在闭环流程变化时修改。
3. `closure-checklist-20260518.md` 每个阶段都必须回填对应验收项。
4. 本文档 `execution-plan-backfill-ledger-20260519.md` 每个阶段都必须回填阶段性质和四层状态。
5. `verification-xxx-phaseN-YYYYMMDD.md` 用于保存单阶段详细验收证据。
6. 禁止把没有运行证据的阶段写成总 Pass。
7. 禁止把 UI Pass 等同于 Backend Pass。
8. 禁止把 Phase1 Pass 等同于项目总闭环 Pass。

---

## 10A. BCG-12A-P0-R2 ledger backfill (2026-05-24)

| Field | Backfill |
|---|---|
| Phase name | BCG-12A-P0-R2 Context Pack API acceptance closeout |
| Phase type | Minimal test hardening + documentation ledger backfill |
| Start commit | `57c3eb43f1dce14c6e8dbbaa69315d19e8a64a11` |
| Changed files | `runtime/orchestrator/tests/test_repository_context_pack_api.py`; `docs/product/ai-project-director/backend-closure-gap-freeze-20260519-v2.md`; `docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md` |
| Involved API | `POST /repositories/projects/{project_id}/context-pack` |
| Backend closure | Backend Pass for API readiness |
| Runtime evidence | Pass after BCG-12A-R1 live evidence; no ignored-directory gap remains |
| Test closeout | Success covers `README.md` + `src/service.py`; budget truncation covered; `../` escape 422; absolute path escape 422; unbound repository 404 |
| Frontend changes | None |
| Gate conclusion | BCG-12A-R1 Pass / BCG-12 Runtime Evidence Pass |

