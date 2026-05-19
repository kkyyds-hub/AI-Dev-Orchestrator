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
| 设置页 | 未开始 | Not Started | Not Started | Not Started | Not Started | 空白 | **Not Started** | 治理中心后处理 |
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

### 5.5 端到端闭环总验收

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
| AI 项目主管真实对话 | Partial | 工作台主视觉已收口，但真实主管会话、目标澄清、计划确认仍需后端闭环 |
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
