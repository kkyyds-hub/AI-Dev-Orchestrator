# AI-Dev-Orchestrator AI 项目主管后端闭环缺口冻结审计 v2

> 建议仓库路径：`docs/product/ai-project-director/backend-closure-gap-freeze-20260519.md`  
> 文档版本：`v2`  
> 审计日期：`2026-05-19`  
> 仓库：`kkyyds-hub/AI-Dev-Orchestrator`  
> 审计基线 commit：`ad66a498fc0c1346527ac2267714f0589ad88fbb`  
> 审计方式：静态代码审计 + 既有验收文档对照 + 已完成阶段回填口径复核。  
> 重要限制：本文没有启动后端、没有连接数据库、没有发起 HTTP 请求、没有执行 smoke/E2E、没有执行前端 build。本文用于冻结“后端闭环计划与缺口”，不能冒充运行验收报告。

---

## 0. v2 更新说明

v1 主要冻结了 AI Project Director 方向的大类后端缺口，但漏收了部分已经单独做过的后端能力，尤其是“AI 运行摘要 / 运行摘要”链路。

v2 做以下补全：

1. 新增 `BCG-15 AI 运行摘要闭环`，避免后续误判为缺口消失或重复开发。
2. 将“真正缺后端”和“已有后端但缺运行证据”分开。
3. 将“前端入口未开放 / 不应开放 / 需要禁用”的项单独列出。
4. 将后续实施顺序改成：先补 P0 真缺口，再做运行证据，再做 P1 体验/诊断。
5. 将摘要、Provider、Worker、Git 写入、Release Gate、Skill 消费、记忆治理、成本 telemetry、系统诊断、E2E rollup 都纳入同一份总计划。

---

## 1. 结论先行

当前项目不是“后端没做”的状态。更准确的判断是：

1. 后端 route 覆盖面已经较广，包括 `health`、`events`、`console`、`agent_threads`、`approvals`、`deliverables`、`tasks`、`provider_settings`、`projects`、`repositories`、`roles`、`skills`、`strategy`、`planning`、`runs`、`team_control_center`、`workers`。
2. BCL 阶段曾完成一批后端实现级补齐，包含 Provider 测试、项目闭环诊断、本地 Git 写入、BudgetGuard、Provider cache telemetry、legacy missing 产品化、rollup 等。
3. AI 运行摘要不是当前 P0 后端缺口：已有独立摘要存储、单数接口、generate/regenerate、AI 优先 + rule fallback、DeepSeek 运行时验收记录。
4. 当前最关键缺口不是“接口全缺”，而是三类问题：
   - AI 项目主管顶层闭环还不完整：目标澄清、用户确认、计划版本、待确认事项、任务分派的一体化链路不足。
   - 已有后端能力缺运行证据：Provider、Worker、仓库、Release Gate、apply-local、git-commit、摘要、成本、记忆等需要当前环境 E2E 验证。
   - 前端入口与后端能力边界需要收口：有些后端存在但前端未开放，有些前端按钮应继续禁用，有些能力只能读或生成草案。

本阶段 Gate 结论：

```text
后端闭环缺口冻结审计 v2：Pass（计划与缺口台账完成）
AI Project Director 总闭环：Partial
运行证据闭环：Partial
后续开发策略：每次只补一个后端闭环，不做大爆炸式重构
```

---

## 2. 审计基线与依据

### 2.1 基线 commit

```text
ad66a498fc0c1346527ac2267714f0589ad88fbb
feat: 设置页 Phase1 — 重构为系统配置中心（四区块 + 测试连接 + 诊断复制）
```

### 2.2 对照文档

1. `docs/product/ai-project-director/page-information-architecture-20260518.md`
2. `docs/product/ai-project-director/closure-flow-20260518.md`
3. `docs/product/ai-project-director/closure-checklist-20260518.md`
4. `docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md`
5. `docs/closure/AI-Dev-Orchestrator-backend-real-closure-gap-ledger-20260516.md`
6. `docs/closure/AI-Dev-Orchestrator-backend-real-closure-gate-acceptance-20260516.md`
7. `docs/product/AI-Dev-Orchestrator-ai-run-summary-backend-design.md`
8. `docs/product/AI-Dev-Orchestrator-run-summary-log-modal-design-audit-20260517.md`

### 2.3 关键代码范围

1. `runtime/orchestrator/app/api/router.py`
2. `runtime/orchestrator/app/api/routes/provider_settings.py`
3. `runtime/orchestrator/app/api/routes/planning.py`
4. `runtime/orchestrator/app/api/routes/tasks.py`
5. `runtime/orchestrator/app/api/routes/workers.py`
6. `runtime/orchestrator/app/api/routes/runs.py`
7. `runtime/orchestrator/app/api/routes/repositories.py`
8. `runtime/orchestrator/app/api/routes/approvals.py`
9. `runtime/orchestrator/app/api/routes/deliverables.py`
10. `runtime/orchestrator/app/api/routes/projects.py`
11. `runtime/orchestrator/app/api/routes/roles.py`
12. `runtime/orchestrator/app/api/routes/skills.py`
13. `runtime/orchestrator/app/api/routes/agent_threads.py`
14. `runtime/orchestrator/app/api/routes/team_control_center.py`
15. `runtime/orchestrator/app/workers/task_worker.py`
16. `runtime/orchestrator/app/services/local_git_write_service.py`
17. `runtime/orchestrator/scripts/v5_backend_closure_evidence_rollup.py`

---

## 3. 状态定义

| 状态 | 含义 | 后续处理 |
|---|---|---|
| Backend Pass | 后端 route/service/repository 已具备真实读写或执行语义 | 不重复开发，只补运行证据 |
| API Pass | 前端已调用真实 API，不是假按钮 | 继续核验后端闭环与运行证据 |
| Runtime Evidence Missing | 静态代码存在，但当前环境未跑通或未回填证据 | 做 E2E/截图/日志/rollup |
| Partial | 能力部分存在，但产品闭环、消费链路、前端入口、状态证据不完整 | 拆小任务补齐 |
| Blocked | 缺接口、缺数据、缺运行环境或缺配置导致无法闭环 | 优先处理 |
| Deferred | 明确延后，不进入当前阶段验收 | 文档说明，不能误写 Pass |
| Not a Gap | 已实现且有证据，或不属于当前产品目标 | 不再投入 |

---

## 4. 总体闭环拆解

目标闭环不是单页面闭环，而是以下全链路：

```text
用户目标
→ AI 项目主管澄清需求
→ 用户确认目标/约束
→ AI 生成计划草案
→ 用户确认计划版本
→ 后端生成任务队列
→ Worker 调度角色/Skill/模型
→ 运行产生日志、摘要、交付件
→ 仓库定位/上下文包/变更计划/变更批次
→ 预检/验证/证据包/提交草案
→ Release Gate / 审批
→ 受控 apply-local / git-commit
→ 成本、记忆、Skill 消费、角色治理沉淀
→ Rollup 证据判定总 Gate
```

当前后端最弱的部分在链路头部和总证据闭环：

- 头部：AI 项目主管“主动澄清、确认、分派”的产品闭环不足。
- 中部：很多执行能力已存在，但运行环境证据不足。
- 尾部：apply-local/git-commit 已有后端，但前端入口、Release Gate 联动、真实 E2E 证据还没闭合。

---

## 5. 后端闭环缺口总表 v2

| ID | 闭环环节 | 当前前端入口 | 当前 API / route | 当前后端状态 | 当前状态 | 缺口说明 | 用户可见风险 | 优先级 | 后续建议任务 |
|---|---|---|---|---|---|---|---|---|---|
| BCG-01 | AI 项目主管目标澄清与会话闭环 | `/workbench` | `POST /project-director/sessions`、`GET /project-director/sessions/{id}`、`POST /project-director/sessions/{id}/answers`、`POST /project-director/sessions/{id}/confirm` | Phase1 后端已实现：创建会话、确定性规则澄清问题、提交回答、确认目标、输出契约字段 | Backend Pass / Runtime Evidence Missing | Phase1 完成目标澄清与确认闭环；不含计划生成、任务创建、Worker 调度、AI Provider 调用；后续 Phase2 需补运行证据 | 用户可提交目标并获得澄清问题，但仍需后续阶段补计划/任务/运行链路 | P0（Phase1 Backend Pass） | Phase1 已完成（含 hardening patch）；后续补 Plan Draft + 运行证据 |
| BCG-02 | 计划版本与确认审计 | 项目创建 / 计划草案入口 | `POST /project-director/sessions/{id}/plan-versions`、`GET /project-director/plan-versions/{id}`、`POST /project-director/plan-versions/{id}/confirm` | Phase1 后端已实现：从 confirmed session 生成 plan version、pending_confirmation→confirmed 状态流、superseded 旧版本 | Backend Pass / Runtime Evidence Missing | Phase1 完成 plan version 生成与确认；不含任务创建、不含 planning/apply 调用；后续需接任务队列 | 计划可审阅可确认，但还未下达为任务 | P0（Phase1 Backend Pass） | Phase1 已完成（含 role code 对齐 hardening）；后续接 Task Creation |
| BCG-03 | 待确认事项 / 人工决策池 | 工作台 / 执行中心 | `GET /project-director/confirmations`、`GET /project-director/projects/{id}/confirmations`、`GET /project-director/sessions/{id}/confirmations` | Phase1 后端已实现：只读聚合 goal_confirmation + plan_confirmation，支持 project/session 过滤。2026-05-20 hardening patch 追加 project_id 正向过滤测试（goal + plan）和 plan version 只读状态不变测试，15/15 通过 | Backend Pass / Runtime Evidence Missing | Phase1 完成只读聚合；不含审批动作、不含 human intervention、不含 preflight/approval 聚合；后续可扩展更多 source_type | 用户可统一查看待确认事项，但还不能从 inbox 直接操作确认 | P0（Phase1 Backend Pass） | Phase1 已完成（含 hardening patch）；后续补确认动作和更多聚合源 |
| BCG-04A | Plan-to-Task Creation | 无（纯后端） | `POST /project-director/plan-versions/{id}/create-tasks`、`GET /project-director/plan-versions/{id}/created-tasks` | Phase1 后端已实现：confirmed plan version → real task queue，含 TaskCreationRecord 追溯、重复创建 409、project_id 缺失 409。2026-05-20 hardening patch 新增原子事务（add_no_commit + 单 commit）、前置预校验、空 description 兜底，18/18 测试通过  2026-05-24 event-consistency hardening: add_no_commit no longer publishes before commit; BCG-04A publishes task_created only after TaskCreationRecord commit; rollback has no ghost events. | Backend Pass / Runtime Evidence Missing | Phase1 完成 confirmed plan → task queue 创建；不含 Worker 调度、不含任务执行、不含 planning/apply；后续接 Worker 执行 | 用户可将确认的计划下达为真实任务，但还不能自动执行 | P0（Phase1 Backend Pass） | Phase1 已完成（含 hardening + event-consistency hardening patch）；后续接 Worker 调度执行 |
| BCG-04 | 任务状态机与人工干预 | `/execution?tab=tasks` | `/tasks/{id}/retry/pause/resume/request-human/resolve-human` | 状态机动作存在 | Backend Pass / Runtime Evidence Missing | 后端真实动作存在；需证明状态变化和重试后 worker 产生新 run | 误以为”重试”会立即执行 | P0 证据 | 做任务状态机 E2E 证据包 |
| BCG-05 | Worker 调度与运行生成 | 工作台 / 执行中心 | `POST /workers/run-once`、`POST /workers/run-pool-once` | 单次/池化调度存在，返回 run/strategy/role/skill/memory/cost/log; 2026-05-24 BCG-05A Phase1 evidence: BCG-04A created task was manually claimed through `POST /workers/run-once?project_id={project_id}` and produced a persisted Run using explicit simulate executor. 2026-05-24 BCG-05B provider_reported evidence: real manual Worker run succeeded via provider_openai/deepseek, run_id=834b38aa-3669-4121-9424-3aa4999cad2e, token_accounting_mode=provider_reported, receipt=3d8bf6e7-fdfd-43db-bd9a-3abee685521d. | Backend Pass / Runtime Evidence Partial | BCG-05A simulate bridge and BCG-05B real provider_reported Worker run evidence exist; still not AI Project Director total closure because broader E2E rollup/approval/repository evidence remains open. | 页面有运行，但总 Gate 没证据 | P0 证据 | BCG-05B provider_reported Worker evidence completed; include in total Gate rollup, but do not mark AI Project Director total closure Pass |
| BCG-06 | 常驻 Worker / 后台调度 | 无明确后台控制入口 | 当前看到 run-once / run-pool-once | 更像手动触发的一次循环 | Partial | 若目标是“AI 自己持续调度”，需要后台 worker daemon/slot 心跳/暂停恢复策略 | 用户需要手点执行，调度感不足 | P1 | 设计 Worker daemon/slot status，只读状态先行，执行开关后置 |
| BCG-07 | 运行日志与决策回放 | 运行页 / 任务详情 | `/tasks/{id}/decision-history`、`GET /runs/{run_id}/logs`、`GET /runs/{run_id}/decision-trace` | run logging / decision replay 存在；2026-05-24 BCG-07A 已用 Project Director-created task + simulate Worker run 证明 run logs / decision trace / decision history 读路径；2026-05-24 BCG-07B 已复用 BCG-05B provider_reported run `834b38aa-3669-4121-9424-3aa4999cad2e` 证明真实 provider run 的日志、decision-trace、decision-history 回放可读 | Backend Pass / Runtime Evidence Partial | provider run 回放证据已补齐；仍需纳入总 Gate rollup，并补成功/失败/阻断多类型样例后再声明 BCG-07 总 Pass | 运行详情可能空或看似调试页；已降低 provider run replay 风险但总闭环仍未放行 | P1 证据 | BCG-07A/07B 已完成 replay 证据；后续补多类型 run 样例并纳入总 Gate |
| BCG-08 | AI 运行摘要闭环 | 运行页摘要卡 | `/runs/{run_id}/ai-summary`、generate、regenerate、history | 独立 `run_ai_summaries`，AI 优先 + rule fallback；2026-05-24 BCG-08A 已复用 BCG-05B provider_reported run 真实调用 DeepSeek 生成 `source=ai` summary；2026-05-24 BCG-08A-R1 live 断言禁止 `rule_fallback/local_rule_engine`，要求 `error_summary=null`、summary provider receipt、当前/历史读回一致，并覆盖 run provider/model/receipt、execution mode、token/cost/log/quality gate evidence | Backend Pass / Runtime Evidence Pass for real AI summary evidence | BCG-08A-R1 已满足 Real AI Run Summary Evidence；2C-C 失败回退体验仍未开始，且 AI Project Director 总闭环不能因此标记 Pass | 若只看 source=ai 容易误判证据不足；R1 已补摘要内容证据覆盖验收 | P0 证据 / P2 体验 | BCG-08A-R1 已收口真实 AI summary 证据；不进入 BCG-09 |
| BCG-09 | 自动交付件与审批创建 | Worker 成功后 / `/delivery` | deliverables / approvals | Worker 成功后可自动创建运行交付快照与审批请求 | Backend Pass / Runtime Evidence Pass for provider-run deliverable/approval evidence | 2026-05-24 BCG-09A 复用 BCG-05B provider_reported run 确认 deliverable_id=3ae2a721-4396-453e-8d1b-529a50efb29c, approval_id=90714664-41d5-41fb-8156-59fc9a784a22 已自动生成，46/46 checks passed | 自动交付件/审批链路已验收 | P1 证据 / P0 收口 | BCG-09A deliverable + approval evidence 已完成；不进入 BCG-10 范围 |
| BCG-10 | 审批要求修改到返工队列 | `/delivery` / 审批页 | approval actions、retrospective、rework chain | 审批动作存在，rework 聚合 DTO 存在 | Partial | “要求修改”后是否创建可执行返工任务/返工项仍需确认 | 审批要求修改后没有明确处理人和下一步 | P1 | 做 request changes → rework item/task 可见链路，缺则补接口 |
| BCG-11 | 仓库绑定与快照 | 设置页 / 仓库工作区 | workspace settings、bind repo、snapshot refresh | 后端存在，安全边界存在 | Backend Pass / Runtime Evidence Missing | 需要真实本地仓库路径验证 allowed root、快照、树、语言统计 | 页面空不等于没后端 | P0 证据 | 准备真实 git workspace 跑仓库基础证据 |
| BCG-12 | 文件定位与上下文包 | 仓库工作区 | file-locator、context-pack | 后端存在 | Backend Pass / Runtime Evidence Missing | 需真实任务/关键词/文件验证定位质量和文件大小限制 | AI 修改文件前缺可靠上下文 | P0 证据 | 做 task_query → candidate files → context pack E2E |
| BCG-13 | 变更计划与变更批次 | 仓库工作区 | change-plans、change-batches | 后端存在 | Backend Pass / Runtime Evidence Missing | 需确认计划版本、批次、预检前置关系完整 | 变更链路断点多，用户可能不知下一步 | P0 证据 | change plan → change batch → preflight E2E |
| BCG-14 | 预检与人工放行 | 仓库工作区 / 审批 | preflight、repository-preflight actions | 后端存在 | Backend Pass / Runtime Evidence Missing | 需验证阻断、人工确认、拒绝、通过四种状态 | 危险变更可能被误放行或无法放行 | P1 证据 | 做 preflight manual confirmation 场景证据 |
| BCG-15 | 提交草案 | 仓库工作区 | commit-candidate GET/POST | 后端存在，明确是 review-only draft | Backend Pass / Runtime Evidence Missing | 草案不是 Git 写入；需避免与 apply-local 混淆 | 用户误以为已改代码 | P0 文案/证据 | 保持“提交草案”边界；后续接 apply-local 要单独入口 |
| BCG-16 | 本地 Git 写入 apply-local / git-commit | 可能尚未开放或不明显 | `POST /repositories/change-batches/{id}/apply-local`、`git-commit` | BCL-03 已实现，含 guard chain、路径安全、本地 commit | Partial | 后端存在；但前端入口、Release Gate 联动、真实 E2E 未确认；不含 push/PR；rollback 未实现 | 用户无法从页面完成真实写入，或误触发危险写入 | P0 | 明确受控前端入口；跑 approve → apply-local → git-commit 证据 |
| BCG-17 | 远程 push / PR / 合并 | 无 | 未作为当前 API 确认 | 不在当前闭环主线 | Deferred | 本地 commit 后是否推远端/建 PR 需要单独设计，不应偷偷接入 | 越权写远端仓库风险 | P2 / Deferred | 先不做；以后单独做 Remote Git Safety Phase |
| BCG-18 | Release Gate 总放行 | 审批 / 仓库 | release gate checklist/actions/judgement | 后端存在 | Backend Pass / Runtime Evidence Missing | 需用真实 evidence、candidate、preflight 验证 gate 可通过/可拒绝 | UI 显示可审阅但不等于满足放行 | P0 证据 | release gate approve / reject / changes requested E2E |
| BCG-19 | 角色治理保存 | 治理中心 | roles catalog / project roles PUT | 后端存在 | Backend Pass / Runtime Evidence Missing | 保存角色配置已有；缺 AI 建议角色 → 用户确认沉淀的产品闭环 | 治理页像配置表，不像 AI 资产沉淀 | P1 | 补 Role suggestion confirmation 或保持禁用说明 |
| BCG-20 | Skill 注册、绑定、升级/删除 | 治理中心 | registry、upsert、bindings | 注册和绑定存在 | Partial | 升级/删除生命周期不完整；消费证据不够可见 | 用户不知道 Skill 是否真的被运行使用 | P0/P1 | 先补 Skill consumption evidence 查询；升级/删除后置 |
| BCG-21 | Skill 消费证据 | 治理中心 / 运行详情 | worker response 含 selected_skill_codes/names | 运行结果中可携带 Skill 选择 | Partial | 缺独立按 project/role/run 查询 Skill 消费证据 API/视图 | Skill 治理无法验收 | P0 | 新增只读 `/skills/projects/{id}/usage` 或复用 runs 聚合 |
| BCG-22 | 记忆治理 Compact/Rehydrate/Reset | 治理中心 | `/projects/{id}/memory/governance/*` | 后端接口存在 | Backend Pass / Runtime Evidence Missing | 之前可能误判缺口；现在主要缺 checkpoint 数据与运行证据 | 空状态容易被误判为没接 | P1 证据 | 准备 checkpoint 后验证 compact/rehydrate/reset |
| BCG-23 | 成本与 Provider telemetry | 成本页 / 治理中心 | cost-dashboard | provider_reported/heuristic/missing、cache telemetry 已聚合 | Backend Pass / Runtime Evidence Missing | 需要真实 provider usage / receipt / cache 数据证明 | 估算成本被当真实账单 | P0 证据 | 跑真实 provider run，验证 cost dashboard 来源标识 |
| BCG-24 | BudgetGuard 项目预算硬阻断 | 团队控制 / Worker | team-control + budget guard | BCL-04 实现级 Pass | Backend Pass / Runtime Evidence Missing | 需要真实项目预算策略触发阻断 | 用户设置预算但不知是否生效 | P1 证据 | 造低预算项目，跑 worker 触发 budget blocked |
| BCG-25 | Team Control Center 策略消费 | 团队控制中心 | team-control-center、strategy preview、worker | 策略保存和 worker 字段存在 | Partial | 需证明 role model policy / stage override 被 worker 实际消费 | 配了团队策略但运行没体现 | P1 证据 | 保存策略 → strategy preview → worker run 验证字段 |
| BCG-26 | Agent 会话与人工干预 | Agent / 项目页 / 运行链路 | agent-threads sessions/timeline/interventions/write | 后端存在 | Backend Pass / Runtime Evidence Missing | Agent 线程偏运行中会话，不等价项目主管顶层会话；但干预写入存在 | 页面空会被误判未接；或用户以为它就是项目主管 | P1 证据 / P0 分界 | 验证 worker 生成 AgentSession；顶层主管会话另做 BCG-01 |
| BCG-27 | 项目阶段推进与时间线 | 项目详情 | advance-stage、timeline | 后端存在，stage guard 存在 | Backend Pass / Runtime Evidence Missing | 需验证阶段阻断/推进/时间线事件 | 用户不知道为什么不能进入下一阶段 | P1 证据 | 构造 stage guard blocking 与 pass 两类场景 |
| BCG-28 | 系统级诊断 | 设置页 | `/health`、provider test、workspace settings | `/health` 是最小健康检查 | Partial | 缺 DB、Worker、Event Stream、runtime data、rollup 状态的系统级诊断接口 | 设置页只能证明服务活着，不证明依赖健康 | P1 | 新增只读 `/diagnostics/system`，不触发 AI、不写数据 |
| BCG-29 | Project closure diagnostics | 项目页 / 总 Gate | `/projects/{id}/closure-diagnostics` | BCL-02 已实现 | Backend Pass / Runtime Evidence Missing | 需确认当前 main rollup 不再有 diagnostics_unavailable | 总 Gate blockers 不清 | P0 证据 | 运行 diagnostics + rollup，回填 blockers |
| BCG-30 | Evidence Rollup 总验收 | 文档/脚本 | `v5_backend_closure_evidence_rollup.py` | rollup 存在 | Backend Pass / Runtime Evidence Missing | 既有 Gate 是 Partial；必须在当前环境重新跑 | 无法判断后端总闭环是否 Pass | P0 证据 | 以真实项目跑 rollup，产出 JSON + 截图 + Gate 文档 |
| BCG-31 | Event Stream 运行状态 | 运行页/设置页 | `events` route 注册；具体能力待联调 | route 存在 | Runtime Evidence Missing | 未在本文静态审计中确认 Event Stream 的前后端完整运行证据 | 运行状态实时性不可靠 | P1 证据 | 做事件流连接、任务更新推送、断线重连验证 |
| BCG-32 | 数据初始化 / Seed / 最小验收数据 | 全局 | 多模块依赖数据 | 需要手动准备或脚本 | Partial | 页面空状态多，缺最小验收数据会拖慢联调 | 容易把“没数据”误判为“没后端” | P0 | 做最小验收数据脚本或手动 runbook |

---

## 6. P0 分类清单

### 6.1 P0-A：真正需要补后端的产品闭环

这些是“代码可能还不够”的部分，应作为后端开发任务：

| ID | 任务 | 原因 |
|---|---|---|
| BCG-01 | AI Project Director 顶层会话 API | Phase1 Backend Pass：目标澄清/确认链路已完成 |
| BCG-02 | 计划版本与用户确认记录 | Phase1 Backend Pass：plan version 生成/确认/版本递增/superseded 已完成 |
| BCG-03 | 待确认事项聚合 inbox | Phase1 Backend Pass：只读聚合 goal + plan confirmations |
| BCG-04A | Plan-to-Task Creation | Phase1 Backend Pass：confirmed plan → task queue，含 TaskCreationRecord 追溯、重复创建 409、project_id 缺失 409 |
| BCG-21 | Skill 消费证据查询 | Skill 治理验收需要证明运行消费 |

### 6.2 P0-B：已有后端，必须补运行证据

这些不应先改代码，应先跑通证据：

| ID | 任务 | 应取得的证据 |
|---|---|---|
| BCG-04 | 任务状态机 E2E | 暂停/恢复/人工/重试状态变化截图和 API 响应 |
| BCG-05 | Worker 真实运行 | provider_reported run、run log、token/cost、strategy 字段 |
| BCG-08 | AI 运行摘要 | 当前环境已完成 BCG-08A-R1：真实 provider_reported run 通过 `POST /runs/{run_id}/ai-summary/regenerate` 生成 `source=ai` 摘要，并通过 GET current/history 读回；摘要覆盖 provider/model/receipt、execution mode、token/cost/log/quality gate evidence |
| BCG-11~13 | 仓库基础链路 | 绑定、快照、定位、上下文、变更计划、变更批次 |
| BCG-16 | apply-local/git-commit | gate approve 后本地写入、验证、commit SHA |
| BCG-18 | Release Gate | blocked/pending/approved/rejected/change_requested 证据 |
| BCG-23 | 成本 telemetry | provider receipt、provider_reported、fallback 标识 |
| BCG-29~30 | diagnostics/rollup | closure diagnostics + rollup JSON |
| BCG-32 | 最小验收数据 | 能支撑前后端联调的固定数据集 |

---

## 7. P1 / P2 清单

### 7.1 P1：建议补，但不阻塞第一轮后端闭环

| ID | 任务 | 说明 |
|---|---|---|
| BCG-06 | 常驻 Worker / Worker daemon | 当前一次性 worker 可用；持续调度可后补 |
| BCG-07 | 成功/失败/阻断 run 日志样例 | BCG-07A/07B 已补 simulate + provider_reported replay 证据；后续补多类型样例并纳入总 Gate |
| BCG-09 | 自动交付件与审批证据 | 2026-05-24 BCG-09A live evidence: reuse BCG-05B provider_reported run, 46/46 passed, deliverable + approval confirmed auto-generated |
| BCG-10 | 审批返工链路 | 审批要求修改后的后续处理 |
| BCG-14 | 预检人工确认多状态 | 安全链路证据 |
| BCG-19 | 角色建议确认沉淀 | 治理体验增强 |
| BCG-22 | 记忆治理 E2E | 数据依赖强，可后于 Worker 证据 |
| BCG-24 | BudgetGuard 硬阻断证据 | 成本治理验收 |
| BCG-25 | Team Control 策略消费证据 | 证明配置生效 |
| BCG-26 | Agent 执行会话证据 | 不等于顶层项目主管，但要验证 |
| BCG-27 | 阶段推进和时间线证据 | 项目页验收 |
| BCG-28 | 系统级诊断接口 | 设置页体验与排障 |
| BCG-31 | Event Stream 证据 | 实时状态体验 |

### 7.2 P2 / Deferred

| ID | 任务 | 延后原因 |
|---|---|---|
| BCG-17 | Remote push / PR / merge | 权限和安全风险高，应在本地 commit 稳定后做 |
| BCG-20 部分 | Skill 删除/升级复杂生命周期 | 先补消费证据，再做生命周期治理 |
| BCG-08 部分 | 2C-C 摘要失败回退体验 | 不阻塞后端总闭环，但影响体验 |

---

## 8. 已经不是后端缺口的能力

以下能力不要重复开发：

| 能力 | 当前判断 | 后续动作 |
|---|---|---|
| Provider GET/PUT/test | 已实现 | 做运行证据，不重复写接口 |
| `/health` 最小健康检查 | 已实现 | 不把它当完整诊断；另补系统诊断 |
| 任务 pause/resume/request-human/resolve-human/retry | 已实现 | 做 E2E 证据 |
| Worker run-once/run-pool-once | 已实现 | 做真实 provider run 证据 |
| AI 运行摘要 GET/generate/regenerate | 已实现 | 总 Gate 重新跑 source=ai 证据 |
| 仓库绑定/快照/定位/context-pack/change-batch/preflight/commit-candidate | 已实现 | 做真实仓库证据 |
| apply-local/git-commit | 后端已实现 | 前端入口和 E2E 证据待补 |
| 角色 catalog / project role PUT | 已实现 | 后续补“AI 建议确认”而不是重写角色配置 |
| Skill registry / binding | 已实现 | 后续补消费证据和生命周期 |
| 记忆治理 compact/rehydrate/reset | 已实现 | 准备 checkpoint 做证据 |
| cost-dashboard | 已实现 | 做 provider telemetry 证据 |
| closure diagnostics / rollup | 已实现 | 当前环境重新跑 |

---

## 9. 继续禁用或谨慎开放的按钮

| 按钮/能力 | 当前建议 | 原因 |
|---|---|---|
| 远程 push | 禁用 / 不显示 | 当前未纳入安全闭环 |
| 创建 PR | 禁用 / 不显示 | 需要远端权限、分支策略、回滚策略 |
| 自动合并 | 禁用 | 高风险，不属于当前目标 |
| Skill 删除 | 禁用或隐藏 | 生命周期与影响范围未收口 |
| Skill 一键升级全部角色 | 禁用 | 缺消费影响评估 |
| 角色“AI 建议一键沉淀” | 禁用，除非补确认接口 | 缺确认审计 |
| 摘要“强制 AI 生成” | 谨慎开放 | Provider 不可用时必须清晰 fallback |
| apply-local | 只在 Release Gate 通过后开放 | 防止绕过预检/审批 |
| git-commit | 只在 apply-local 验证通过后开放 | 防止提交失败或混入脏文件 |

---

## 10. 推荐实施顺序

### 第一阶段：冻结并补顶层产品闭环

1. BCG-01：Project Director session Phase1
2. BCG-02：PlanVersion / PlanApproval 证据
3. BCG-03：Pending Confirmation Inbox 只读聚合
4. BCG-04A：Plan-to-Task Creation（confirmed plan → task queue）
5. BCG-21：Skill Consumption Evidence 只读接口

说明：这四个最能解决”AI 项目主管不像主管”的问题。BCG-04A 于 2026-05-20 完成 Phase1。

### 第二阶段：跑通最小 E2E 运行证据

1. BCG-32：最小验收数据准备
2. BCG-05：Worker 真实 provider run
3. BCG-08：AI 运行摘要 source=ai 重跑
4. BCG-23：成本 telemetry 证据
5. BCG-29/30：closure diagnostics + rollup

说明：这阶段优先证明“已有能力能跑”。

### 第三阶段：仓库真实闭环证据

1. BCG-11：仓库绑定/快照
2. BCG-12：文件定位/context-pack
3. BCG-13：change plan/change batch/preflight
4. BCG-18：Release Gate
5. BCG-16：apply-local/git-commit

说明：这是“AI 真正修改项目”的关键链路，但必须在安全 gate 后做。

### 第四阶段：治理与体验补齐

1. BCG-10：审批返工回任务队列
2. BCG-22：记忆治理证据
3. BCG-24：BudgetGuard 阻断证据
4. BCG-25：Team Control 策略消费证据
5. BCG-28：系统级诊断
6. BCG-31：Event Stream 证据

---

## 11. 下一条 Codex 任务建议

优先做 BCG-01，不要直接做 Git 写入，也不要先补诊断。

原因：用户当前最大的产品感知问题是“AI 不像项目主管，还是我自己分任务”。这不是 Git 写入能解决的。

建议下一条任务：

```text
当前阶段：BCG-01 AI Project Director session Phase1
性质：后端顶层产品闭环补齐
允许改后端：允许
允许改前端：不允许，除非只补 API 类型或极小入口
允许新增 API：允许，但只限 Project Director session
Gate 预期：Partial / Backend Pass

目标：
新增 AI 项目主管顶层会话后端，不替代现有 planning/tasks/agent_threads。
只负责记录：用户目标、AI 澄清问题、用户回答、待确认事项、生成计划草案前的确认状态。

严格边界：
- 不重建项目。
- 不改现有 planning/apply 语义。
- 不改任务状态机。
- 不改仓库链路。
- 不接真实 Git 写入。
- 不改前端页面大结构。
- 不假装已经完成总闭环。

建议 API：
- POST /project-director/sessions
- GET /project-director/sessions/{session_id}
- POST /project-director/sessions/{session_id}/messages
- POST /project-director/sessions/{session_id}/confirmations
- POST /project-director/sessions/{session_id}/planning-draft

验收：
- 能创建 session。
- 能记录用户目标。
- 能生成或保存澄清问题。
- 能记录用户回答和确认事项。
- 能把确认后的 brief 传给现有 planning draft，但不直接 apply。
- 有数据库或持久化模型。
- 有 tests/smoke。
- 文档回填 BCG-01。
```

---

## 12. BCG-01 Phase1 实施记录（2026-05-19）

BCG-01 Phase1 已于 2026-05-19 完成后端实现。

### 实现范围

- 新增 Project Director Session 后端模型 / 存储 / 服务 / API
- 支持创建会话（输入：目标文本、可选 project_id、可选 constraints）
- 支持读取会话详情（含输出契约字段）
- 支持提交澄清回答（确定性规则匹配 question_id，合并式提交）
- 支持确认目标摘要（状态转换 ready_to_confirm → confirmed）
- 澄清问题 Phase1 使用确定性规则生成，不调用 AI，不依赖 Provider

### 状态流转

```
draft → clarifying → ready_to_confirm → confirmed
```

### 新增 API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/project-director/sessions` | 创建会话，返回澄清问题 |
| GET | `/project-director/sessions/{session_id}` | 读取会话详情 |
| POST | `/project-director/sessions/{session_id}/answers` | 提交澄清回答 |
| POST | `/project-director/sessions/{session_id}/confirm` | 确认目标摘要 |

### 新增文件

- `.kkr/skills/ai-project-director/SKILL.md` — AI 项目主管 Skill 契约
- `app/domain/project_director_session.py` — 领域模型
- `app/repositories/project_director_session_repository.py` — 数据仓库
- `app/services/project_director_service.py` — 确定性澄清规则
- `app/api/routes/project_director.py` — API 路由
- `tests/test_project_director_sessions.py` — 31 个测试

### 严格边界

- 未改前端页面
- 未接真实 AI
- 未调用 OpenAI / DeepSeek / Provider
- 未调用 Worker
- 未创建任务
- 未调用 planning/apply
- 未写仓库
- 未改现有 planning / tasks / workers / repositories 接口语义
- confirmed 后不自动生成计划、不自动创建任务

### BCG-01 状态

**Backend Pass / Runtime Evidence Missing**

Phase1 只完成目标澄清与确认，不代表 AI Project Director 总闭环 Pass。

Hardening patch（2026-05-19）追加了 required question 校验、partial answers 状态保持、confirm 返回完整 SessionResponse、中文短目标检测修正、空白 goal 拒绝。

---

## 13. v2 最终结论

当前后端计划不能只写“缺什么接口”。更准确的执行策略是：

1. 先补 AI 项目主管顶层产品闭环：BCG-01、BCG-02、BCG-03。
2. 再补 Skill 消费证据：BCG-21。
3. 然后跑现有后端能力的 E2E 证据：Worker、摘要、成本、仓库、Release Gate、apply-local、git-commit、rollup。
4. 最后做诊断、Event Stream、体验收口、失败回退。

本文件 v2 的核心判断：

```text
后端并非空壳。
摘要不是 P0 缺口。
Git 本地写入后端已存在但未完成前端入口和总证据闭环。
真正最该补的是 AI 项目主管顶层会话、计划确认、待确认事项、Skill 消费证据。
其余大量事项是运行证据与联调问题，不应重复开发。
```
