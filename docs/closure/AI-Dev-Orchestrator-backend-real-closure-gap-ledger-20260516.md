# AI-Dev-Orchestrator 后端真实闭环缺口最终台账

- 项目：`AI-Dev-Orchestrator`
- 仓库：`kkyyds-hub/AI-Dev-Orchestrator`
- 基准提交：`558eea61f87331677512c1a6529972cd0d9c7f03`
- 生成日期：`2026-05-16`
- 台账定位：**后端能力补齐台账 / 只列真实缺口 / 不重复已验证项**
- 当前目标：让前端关键按钮背后都有真实后端闭环，而不是只读、草案、占位或误导性“看似完成”。

---

## 0. 本台账和上一版的区别

上一版偏“按钮闭环审计”。本版改成你真正要的口径：

1. **不再把所有按钮重新审计一遍。**
2. **不重复 docs 里已经验证过的能力。**
3. **只列“为了让后端能力真正闭环还必须补的部分”。**
4. **把 docs 里的 Day15 / Day16 / 整体里程碑级 Partial 当作事实边界，而不是重新推翻。**
5. **明确哪些不是缺口，避免后续让 Codex 做无用功。**

---

## 1. 当前正式事实边界

### 1.1 已完成但不能外推

仓库 `docs/01-版本冻结计划/V5/00-V5总纲.md` 和 `V5-整体里程碑级裁定说明.md` 已经给出统一口径：

- `Day01-Day16 工作包级已完成`
- `Day16 工作包级 Pass 已成立`
- `V5 整体里程碑级仍为 Partial`
- 不得写成 `V5 全局最终全部通过`

这说明：**很多工作包已经有实现和验证，不应该重复检测；但整体后端真实闭环还没达到“全局可放行”的级别。**

### 1.2 docs 中明确保留的剩余边界

后续后端补齐主要围绕这几类边界展开：

1. `missing=replay` 解释边界  
   当前 `missing` 主要来自 replay 消费事实，不等于自然 worker 主链稳定产出。

2. fresh project `day15-repository-flow=blocked`  
   接口能返回 `HTTP 200 + blocked`，不是接口失败；但 fresh project 的仓库闭环前置条件没有自动闭合。

3. `R3` 观察项  
   `npm.cmd run build` 可通过；`npm run build` 受 PowerShell `ExecutionPolicy` 影响；Vite 仍有大 chunk warning。此项偏工程观察，不是后端闭环主缺口。

4. 缺更大层级 `review + verify + accept` 汇总闭环  
   这是最终验收层级缺口，不代表每个后端功能都缺实现。

---

## 2. 已存在能力：不要重复开发

下面这些能力已经有代码或 docs 验证事实支撑。后续不要再让 Codex 重新做一遍。

| 能力 | 当前判断 | 依据路径 | 后续处理 |
|---|---|---|---|
| OpenAI / 兼容网关真实 Provider 调用 | 已有真实执行路径，不是完全缺失 | `runtime/orchestrator/app/services/openai_provider_executor_service.py` | 不要重写 Provider Executor；只补测试连接入口 |
| Provider fallback 到 mock / simulate | 已有 | `runtime/orchestrator/app/services/executor_service.py` | 保留，不重做 |
| Worker 默认接入 project memory recall | 已接入 | `runtime/orchestrator/app/workers/task_worker.py` 中 `include_project_memory=True` | 不重复做 |
| Worker 创建 Run、写日志、写 token/cost、写 agent session | 已有主链 | `runtime/orchestrator/app/workers/task_worker.py` | 只补诊断与证据聚合 |
| Task 重试 / 暂停 / 恢复 / 请求人工 / 解除人工 | 后端路由已存在 | `runtime/orchestrator/app/api/routes/tasks.py` | 不重复做 |
| 计划草案生成与 apply 生成真实项目/任务 | 后端路由已存在 | `runtime/orchestrator/app/api/routes/planning.py` | 不重复做 |
| 仓库绑定 / 快照 / 文件定位 / context-pack | 后端路由已存在 | `runtime/orchestrator/app/api/routes/repositories.py` | 不重复做 |
| change batch / preflight / release checklist / commit candidate draft | 后端路由已存在 | `runtime/orchestrator/app/api/routes/repositories.py` | 只补“真实 Git 写入” |
| Skill registry / role binding | 后端路由已存在 | `runtime/orchestrator/app/api/routes/skills.py` | 不重复做 |
| Team control center 基础保存与 role-model policy 写入 strategy rules | 后端路由已存在 | `runtime/orchestrator/app/api/routes/team_control_center.py` | 只补预算硬消费 |
| Cost dashboard 聚合与 fallback contract | 后端路由已存在 | `runtime/orchestrator/app/api/routes/projects.py` | 只补真实 cache / 更强 usage 证据 |
| Memory governance / compact / rehydrate / reset | 后端路由已存在 | `runtime/orchestrator/app/api/routes/projects.py` | 不重复做 |
| Agent thread 基础会话与干预记录 | docs 已验证到工作包级 | `docs/01-版本冻结计划/V5/04-模块D-Multi-Agent协作与老板控制面/` | 不重复做 |

---

## 3. 最终真实缺口总览

### 缺口分级说明

- `P0`：不补就无法说“关键后端闭环真实可用”。
- `P1`：不补会导致能力边界仍不完整，但不影响最小演示链。
- `P2`：增强型闭环，主要用于冲更高层级验收或产品化。

| 编号 | 优先级 | 真缺口 | 为什么是真缺口 | 不要误做成 |
|---|---:|---|---|---|
| BCL-01 | P0 | Provider 测试连接后端接口 | 现在能保存配置，也有真实 provider executor，但用户无法在配置页确认 key/base_url/model 是否可用 | 不要重写 executor |
| BCL-02 | P0 | 首次使用/闭环诊断后端聚合接口 | 已有很多接口，但缺一个聚合判断“当前为什么不能闭环”的后端诊断面 | 不要再做全仓库测试 |
| BCL-03 | P0 | 仓库真实 Git 写入链路 | 当前仓库链路主要是 read-only + commit candidate draft；release gate 明确 `git_write_actions_triggered=False` | 不要把提交草案伪装成 git commit |
| BCL-04 | P1 | Team Control 的 budget_policy 被 BudgetGuard 硬消费 | Team Control 保存了 budget policy，但当前口径仍说预算硬拦截在既有 BudgetGuard 路径 | 不要只改前端文案 |
| BCL-05 | P1 | Cost/cache 真实 telemetry | Cost dashboard 当前 cache signal 使用 project memory counts，不是 provider cache hit/miss telemetry | 不要把 memory counts 写成真实 cache 命中 |
| BCL-06 | P1 | `missing` 不再只依赖 replay 解释 | docs 明确 `missing=replay` 仍是解释边界，不能写成自然主链稳定产出 | 不要重复 Day15 replay 测试 |
| BCL-07 | P2 | fresh project repository flow 的后端引导/自动补前置条件 | 当前 fresh project 能返回 blocked，但缺自动告诉后端下一步怎么补齐/是否可一键 bootstrap | 不要把 blocked 当接口 bug |
| BCL-08 | P2 | 整体里程碑级后端 closure evidence 汇总 | 现有工作包级证据分散，缺一个后端闭环总证据包用于冲更高层级 accept | 不要重新跑所有已验证项 |

---

# 4. P0 后端缺口详表

## BCL-01：Provider 测试连接后端接口

### 当前事实

已存在：

- `GET /provider-settings/openai`
- `PUT /provider-settings/openai`
- OpenAI / 兼容网关真实执行服务
- worker 中 provider route + fallback + provider receipt 写入路径

但缺少：

- `POST /provider-settings/openai/test`

### 为什么必须补

用户配置 OpenAI API Key 后，后端只能告诉前端“已保存/已配置”，不能告诉用户：

- API Key 是否有效
- base_url 是否能连通
- model 是否支持
- Responses / Chat Completions 哪个 endpoint 可用
- 鉴权失败、网络失败、模型不存在、schema 不兼容分别是什么原因

这会导致配置按钮“看起来闭环”，但首次使用仍可能卡住。

### 建议实现范围

后端新增最小接口：

```txt
POST /provider-settings/openai/test
```

建议返回字段：

```json
{
  "provider_key": "openai",
  "configured": true,
  "base_url": "https://api.openai.com/v1",
  "auth_valid": true,
  "endpoint_reachable": true,
  "api_family": "responses",
  "model_name": "gpt-4.1-mini",
  "model_usable": true,
  "latency_ms": 1234,
  "status": "passed",
  "error_category": null,
  "error_summary": null,
  "tested_at": "..."
}
```

### 验收打勾项

- [x] 未配置 key 时返回 `configured=false`，不抛 500。
- [x] key 错误时返回稳定错误分类，例如 `auth_error`。
- [x] base_url 错误时返回 `network_error` 或 `endpoint_not_supported`。
- [x] model 不可用时返回 `model_error` 或 `request_schema_error`。
- [x] 成功时返回 `status=passed`、`latency_ms`、`api_family`。
- [x] 响应不得泄露明文 API Key。
- [x] 复用现有 `ProviderConfigService` / `OpenAIProviderExecutorService`，不重写一套 provider。
- [x] 后端最小测试或 smoke 覆盖通过。

### owner skill

`write-v5-runtime-backend`

### 建议 Codex 指令

```txt
请按 V5 后端 skill 补 Provider 测试连接闭环。

目标：
新增 POST /provider-settings/openai/test，复用现有 ProviderConfigService 和 OpenAIProviderExecutorService，返回 OpenAI 配置可用性诊断。

边界：
- 不重写 provider executor。
- 不改已有 GET/PUT /provider-settings/openai 协议。
- 不泄露明文 API Key。
- 不改前端。
- 不扩大到其他 provider。

验收：
- 未配置、鉴权失败、网络失败、endpoint 不兼容、成功场景都有稳定响应结构。
- 后端测试或最小 smoke 通过。
```

---

## BCL-02：首次使用/闭环诊断后端聚合接口

### 当前事实

系统已有多个独立接口：

- provider settings
- projects
- repositories
- planning
- tasks
- workers
- runs
- memory
- agent threads
- cost dashboard
- day15 repository flow

但没有一个后端接口能回答：

> “这个项目现在为什么还不能从配置 → 仓库 → 任务 → worker → run → 交付证据形成闭环？”

### 为什么必须补

现在的问题不是接口完全没有，而是闭环前置条件分散在十几个接口里。前端很容易出现：

- 页面显示一堆“未配置/暂无数据”
- 用户不知道下一步该点哪里
- Codex 后续开发时重复跑已经验证过的项
- 问题定位变成手工拼图

### 建议实现范围

新增：

```txt
GET /projects/{project_id}/closure-diagnostics
```

可选新增全局：

```txt
GET /closure-diagnostics
```

建议项目级响应字段：

```json
{
  "project_id": "...",
  "generated_at": "...",
  "overall_status": "blocked|ready|running|completed",
  "blocking_reason_codes": [
    "provider_not_tested",
    "repository_not_bound",
    "snapshot_missing",
    "no_pending_tasks"
  ],
  "provider": {
    "configured": true,
    "last_test_status": "passed|failed|not_tested"
  },
  "repository": {
    "bound": true,
    "snapshot_exists": true,
    "snapshot_status": "success",
    "day15_flow_status": "blocked"
  },
  "task_runtime": {
    "task_count": 3,
    "pending_task_count": 1,
    "run_count": 2,
    "latest_run_status": "completed",
    "latest_run_log_path": "..."
  },
  "governance": {
    "memory_checkpoint_count": 1,
    "agent_session_count": 1,
    "approval_count": 0,
    "change_batch_count": 0,
    "commit_candidate_count": 0
  },
  "next_actions": [
    {
      "code": "refresh_repository_snapshot",
      "label": "刷新仓库快照",
      "api": "POST /repositories/projects/{project_id}/snapshot/refresh"
    }
  ]
}
```

### 验收打勾项

- [ ] project 不存在时返回 404。
- [ ] fresh project 能返回 `overall_status=blocked` 和明确 `next_actions`。
- [ ] 已配置 provider、已绑定仓库、已有 task/run 时能聚合真实数量。
- [ ] 不触发真实 worker、不执行写入动作，只做诊断读取。
- [ ] 复用现有 repository/service，不新增平行数据源。
- [ ] 可被前端用于“首次使用路径”和“为什么按钮禁用”的判断。
- [ ] 后端 smoke 覆盖至少 fresh project / partially configured project 两类场景。

### owner skill

`write-v5-runtime-backend`

### 建议 Codex 指令

```txt
请按 V5 后端 skill 补项目闭环诊断接口。

目标：
新增 GET /projects/{project_id}/closure-diagnostics，聚合 provider、repository、snapshot、task、run、memory、agent、approval、change batch、commit candidate 的当前闭环状态，并返回 next_actions。

边界：
- 只读诊断，不触发 worker，不写仓库，不修改现有接口协议。
- 复用现有 repository/service。
- 不改前端。
- 不重新跑全量 verify。

验收：
- fresh project 返回 blocked 和明确 next_actions。
- 已有运行记录的项目返回 run/log/memory/agent 聚合状态。
- 后端最小 smoke 通过。
```

---

## BCL-03：仓库真实 Git 写入链路

### 当前事实

已存在：

- 仓库绑定
- 快照刷新
- 文件定位
- context-pack
- change plan
- change batch
- preflight
- diff evidence
- commit candidate draft
- release checklist

但当前 release gate service 返回：

```txt
git_write_actions_triggered=False
```

并且 commit candidate 是“提交草案”，不是实际 `git commit`。

### 为什么必须补

这是当前最核心的后端闭环缺口。

如果你的目标是“每个按钮点下去都是真实闭环”，那么仓库链路最终必须能做到：

1. 生成补丁或变更内容
2. 写入本地工作区
3. 执行验证命令
4. 创建 git commit
5. 返回 commit SHA
6. 可选创建 branch / push / PR
7. 将执行结果写回数据库和放行证据

否则前端里“提交草案 / 放行判断 / 交付证据”永远只能停留在审阅层，不是真正开发闭环。

### 建议实现分层

#### 第一步：本地安全写入，不 push

新增后端能力：

```txt
POST /repositories/change-batches/{change_batch_id}/apply-local
POST /repositories/change-batches/{change_batch_id}/git-commit
```

最小能力：

- 校验 release gate 是否 approved
- 校验 preflight 是否通过
- 校验 commit candidate 是否存在
- 写入本地 workspace
- 执行验证命令
- 创建 git commit
- 返回 commit SHA
- 写入 change batch / commit candidate / release gate 执行记录

#### 第二步：可选远端动作

后续再补：

```txt
POST /repositories/change-batches/{change_batch_id}/push-branch
POST /repositories/change-batches/{change_batch_id}/pull-request
```

### 必须加的安全边界

- 默认只允许项目绑定的本地 workspace。
- 禁止路径穿越。
- 禁止写入 `.git` 内部敏感路径。
- 必须先 dry-run diff。
- 必须保留 rollback 或失败记录。
- push/PR 默认关闭，需显式配置。
- 所有执行动作写入 JSONL 日志和数据库状态。

### 验收打勾项

- [ ] 未通过 release gate 时禁止 apply/commit。
- [ ] commit candidate 不存在时禁止 commit。
- [ ] preflight 未通过时禁止 commit。
- [ ] 成功 commit 后返回 `commit_sha`、`branch_name`、`changed_files`。
- [ ] release gate 或 day15 flow 中 `git_write_actions_triggered=true`。
- [ ] 失败时有稳定错误分类和日志路径。
- [ ] 不影响现有 read-only 仓库能力。
- [ ] 最小 smoke 能创建临时 git repo 并完成本地 commit。

### owner skill

`write-v5-runtime-backend`

### 建议 Codex 指令

```txt
请按 V5 后端 skill 补仓库真实 Git 写入最小闭环第一阶段。

目标：
在现有 repository/change batch/commit candidate/release gate 链路上，新增本地 git commit 能力。先只做本地 commit，不做 push，不做 PR。

边界：
- 不改现有仓库绑定、快照、文件定位、commit candidate 协议。
- 不做远端 push。
- 不绕过 release gate / preflight / commit candidate。
- 不改前端。
- 必须有路径安全校验。

验收：
- 临时 git repo smoke 能完成 apply + commit 并返回 commit_sha。
- gate 未通过、preflight 未过、candidate 缺失时均阻断。
- day15 flow 或 release gate 能看到 git_write_actions_triggered=true。
```

---

# 5. P1 后端缺口详表

## BCL-04：Team Control 的 budget_policy 被 BudgetGuard 硬消费

### 当前事实

Team Control Center 已能保存：

- team assembly
- team policy
- budget policy
- role model policy

其中 role model policy 会写入 strategy rules。当前 runtime boundary 文案也说明：

- role model policy 被 strategy engine / worker routing 消费
- budget policy 当前更多是 Day14 aggregation inputs
- hard enforcement 仍在 existing budget guard paths

### 真缺口

`budget_policy.hard_stop_enabled`、`daily_budget_usd`、`per_run_budget_usd` 如果只是保存和展示，而没有被 `BudgetGuardService` 在 worker 执行前硬消费，就不能说“团队控制中心预算策略真实闭环”。

### 建议实现范围

- 让 `BudgetGuardService.evaluate_before_execution(task.id)` 能解析 task.project_id 对应的 project budget policy。
- 当 `hard_stop_enabled=true` 时，以项目 budget policy 覆盖或参与现有 guard 判断。
- 将 budget policy 来源写入 run strategy/budget 字段和 JSONL 日志。
- cost dashboard 返回 budget policy source。

### 验收打勾项

- [ ] Team Control 保存 hard_stop budget policy。
- [ ] worker run-once 执行前读取项目 budget policy。
- [ ] 超预算时 task/run 被 block。
- [ ] run log 记录 budget_policy_source。
- [ ] cost dashboard 能显示项目预算策略来源。
- [ ] 不破坏现有默认 BudgetGuard 行为。

### owner skill

`write-v5-runtime-backend`

---

## BCL-05：Cost/cache 真实 telemetry

### 当前事实

Cost dashboard 已经能聚合：

- provider_reported
- heuristic
- missing
- role breakdown
- thread breakdown
- fallback contract

但 cache summary 当前使用的是 project memory counts，并且文档/代码口径已经明确：

```txt
Cache signal currently uses Day14 project-memory counts,
not provider-level cache hit/miss telemetry.
```

### 真缺口

如果未来页面写“缓存命中 / cache saving / provider cache 成本节省”，后端必须有真实 telemetry。当前不能把 memory counts 当 provider cache hit/miss。

### 建议实现范围

新增或扩展 provider usage receipt：

```json
{
  "cache_read_tokens": 0,
  "cache_write_tokens": 0,
  "cache_hit": false,
  "cache_source": "provider_reported|not_reported|heuristic"
}
```

Cost dashboard 增加：

```json
{
  "provider_cache": {
    "supported": true,
    "reported_run_count": 3,
    "cache_hit_run_count": 1,
    "cache_read_tokens": 1234,
    "cache_write_tokens": 456,
    "estimated_cache_savings_usd": 0.01
  }
}
```

### 验收打勾项

- [ ] provider receipt 可记录 provider 返回的 cache 字段。
- [ ] 不支持 cache telemetry 的 provider 明确返回 `not_reported`。
- [ ] cost dashboard 不再把 memory counts 写成 provider cache。
- [ ] fallback/heuristic/missing 三态仍保留。
- [ ] 测试覆盖 provider reported + not reported 两类。

### owner skill

`write-v5-runtime-backend`

---

## BCL-06：`missing` 不再只依赖 replay 解释

### 当前事实

docs 已明确：

- `missing` 当前主要是 replay 消费事实
- 不能扩写为自然 worker 主链稳定产出
- Day15 / Day16 已经把这个作为整体里程碑级 Partial 的边界之一

### 注意：不要误判

这不是说当前 worker 必须自然生成 `missing`。正常 worker 已经会写入 token accounting mode。`missing` 更多是兼容历史 run / 异常 run / 旧数据的 fallback 解释边界。

### 真缺口

缺少一个正式的后端策略来处理“历史/异常 run 的 token_accounting_mode 缺失”：

- 是迁移补齐？
- 是保留 missing 分类？
- 是在 dashboard 明确 legacy_missing？
- 是提供 backfill endpoint/script？

现在只是靠 replay 证明 dashboard 能消费 missing，不够产品化。

### 建议实现范围

二选一即可，建议不要都做：

#### 方案 A：保留 missing，但产品化

- `missing` 改名或补充为 `legacy_missing`
- cost dashboard 明确 `missing_source=legacy_or_replay`
- 后端文档/DTO 写清楚不是自然主链

#### 方案 B：提供 backfill

新增脚本：

```txt
runtime/orchestrator/scripts/backfill_missing_token_accounting.py
```

将旧 run 的 missing 记录按规则补为 heuristic。

### 验收打勾项

- [ ] 不再依赖 Day15 replay 作为唯一解释。
- [ ] dashboard 对 missing 的来源有稳定字段。
- [ ] 旧数据可通过脚本 backfill，或明确保留为 legacy。
- [ ] docs 中 `missing=replay` 边界可被降级或关闭。
- [ ] 不改变正常 worker 写入 token accounting 的现有主链。

### owner skill

`write-v5-runtime-backend`

---

# 6. P2 后端缺口详表

## BCL-07：fresh project repository flow 的后端引导/自动补前置条件

### 当前事实

fresh project 的 `day15-repository-flow` 返回 blocked 是合理的，不是接口失败。

### 真缺口

如果想让新用户更顺地跑通闭环，后端可以进一步提供：

- 当前缺什么前置条件
- 下一步该调用哪个接口
- 是否允许一键 bootstrap demo data
- 哪些步骤必须人工完成

这和 BCL-02 的诊断接口有关，可以后续合并。

### 建议实现

优先不单独做。等 BCL-02 完成后，看是否还需要：

```txt
POST /projects/{project_id}/closure-bootstrap
```

只用于本地/demo，不建议默认启用生产写入。

### 验收打勾项

- [ ] fresh project 可以明确拿到下一步动作。
- [ ] 不把 blocked 误判成接口错误。
- [ ] bootstrap 如存在，必须显式标记 demo/local-only。

### owner skill

`drive-v5-orchestrator-delivery`

---

## BCL-08：整体里程碑级后端 closure evidence 汇总

### 当前事实

docs 已有很多工作包级证据，但它们分散在 Day12 / Day15 / Day16 / tmp evidence 文件里。

### 真缺口

如果以后要冲 `V5 整体里程碑级 Pass`，需要一个更高层级的后端证据汇总产物，而不是人工翻多个 docs 和 tmp 文件。

### 建议实现

新增脚本或只读 endpoint：

```txt
runtime/orchestrator/scripts/v5_backend_closure_evidence_rollup.py
```

输出：

```txt
runtime/orchestrator/tmp/v5-backend-closure-rollup/v5_backend_closure_rollup.json
```

聚合：

- provider configured/tested
- provider real run receipt
- fallback/missing status
- memory checkpoint
- agent session
- team control policy consumed
- budget guard consumed
- repository gate status
- git_write_actions_triggered
- latest commit_sha if any
- unresolved backend gaps

### 验收打勾项

- [ ] 不重新跑所有测试，只消费已存在证据和当前 DB/文件状态。
- [ ] 输出一个 JSON 证据包。
- [ ] 能明确给出 `pass_ready=false/true` 和 blockers。
- [ ] 可被 `accept-v5-milestone-gate` 直接消费。

### owner skill

`verify-v5-runtime-and-regression`

---

# 7. 最终建议执行顺序

## 第一阶段：最小真实闭环，不动 Git 写入

先做：

1. `BCL-01 Provider 测试连接`
2. `BCL-02 项目闭环诊断接口`

原因：

- 这两项成本最低。
- 不会破坏现有 V5 主链。
- 能立刻解决“我不知道哪里没闭环”的问题。
- 后续不会重复检测已验证项。

## 第二阶段：真正补最核心后端能力

再做：

3. `BCL-03 仓库真实 Git 写入链路`

原因：

- 这是从“审阅系统”变成“执行系统”的关键。
- 也是前端按钮是否真实闭环的最大分水岭。

## 第三阶段：治理配置硬闭环

再做：

4. `BCL-04 Team Control budget policy 硬消费`
5. `BCL-05 Cost/cache telemetry`
6. `BCL-06 missing legacy/backfill 口径`

原因：

- 这些影响整体里程碑级 Pass。
- 但不应该阻塞最小可用闭环。

## 第四阶段：冲整体里程碑级验收

最后做：

7. `BCL-08 后端 closure evidence rollup`

原因：

- 只有前面缺口补完，rollup 才有意义。
- 不要一开始就再做一轮验收汇总。

---

# 8. 当前不建议做的事情

以下任务会浪费时间，暂不建议给 Codex：

1. **不要重写 OpenAI Provider Executor**  
   已经有真实请求路径。

2. **不要重复做 Worker memory recall**  
   worker 已经 `include_project_memory=True`。

3. **不要重复做 Task actions 后端**  
   retry/pause/resume/request-human/resolve-human 已有。

4. **不要重复做 repository read-only 链路**  
   绑定、快照、locator、context-pack 已有。

5. **不要重复做 commit candidate draft**  
   缺的是 draft 之后的真实 git write，不是再生成一个 draft。

6. **不要重复跑 Day15 / Day16 全量 verify**  
   docs 已有证据。当前应按缺口补实现，不是继续审计。

7. **不要先做前端美化**  
   后端闭环没补齐前，前端越像正式系统，误导越强。

---

# 9. 当前最推荐的第一条 Codex 指令

```txt
请按 V5 后端 skill 补 Provider 测试连接闭环。

仓库：
https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git

目标：
新增 POST /provider-settings/openai/test，复用现有 ProviderConfigService 和 OpenAIProviderExecutorService，返回 OpenAI 配置可用性诊断，供前端判断 API Key / base_url / model 是否真实可用。

边界：
- 不重写 provider executor。
- 不改已有 GET/PUT /provider-settings/openai 协议。
- 不改前端。
- 不扩大到其他 provider。
- 不泄露明文 API Key。
- 不做全量 verify。

验收：
- 未配置 key 时返回 configured=false。
- key 错误时返回 auth_error。
- base_url/endpoint 不通时返回稳定错误分类。
- 成功时返回 status=passed、api_family、latency_ms、tested_at。
- 后端最小测试或 smoke 通过。
- 提交并 push，给出提交哈希。
```

---

# 10. 进度记录区

| 日期 | 缺口编号 | Codex 提交 | build / test | 验收结论 | 备注 |
|---|---|---|---|---|---|
| 2026-05-16 | 初始台账 | - | - | 待执行 | 基于 origin/main `558eea61` 生成 |
| 2026-05-16 | BCL-01 | `4a5bb9e` | smoke 5/5 passed; app loads | Pass | 新增 POST /provider-settings/openai/test；复用 ProviderConfigService + OpenAIProviderExecutorService；5 场景 smoke 通过 |
| 2026-05-16 | BCL-01 返工 | `8814bfe` | smoke 8/8 passed; compileall clean | Pass（返工） | 返工修复：1) test_connectivity() 增加 _extract_output_text() 内容校验，HTTP 200+非OpenAI JSON 不可误判 passed；2) smoke 补 monkeypatch 模拟 responses/chat_completions 成功场景并断言 passed shape；3) 错误分类测试改用 mock 精确断言 auth_error/endpoint_not_supported/network_error/invalid_response；4) 清理未使用 import（json/ProviderConfigService） |
| 2026-05-16 | BCL-02 | `4a9386f` | smoke 3/3 passed; compileall clean | Pass（初版，需返工） | 新增 GET /projects/{project_id}/closure-diagnostics 只读诊断接口；聚合 provider/repository/task_runtime/governance 状态并返回 blocking_reason_codes + next_actions；复用现有 repository/service，不产生副作用 |
| 2026-05-16 | BCL-02 返工 | `f443e80` | smoke 6/6 passed; compileall clean | Pass（返工） | 返工修复：1) day15_flow_status 改为 not_available（不伪造 project.stage）；2) overall_status 修正为 blocking_reason_codes 优先 blocked；3) 新增 provider_not_tested 阻塞码；4) smoke 扩至 6 场景覆盖 404/fresh/provider-not-tested/tasks-blocked/completed-blocked/partial-config |
| 2026-05-16 | BCL-02 next_actions 路径修正 | `df6c95a` | smoke 6/6 passed; compileall clean | Pass | 修正 next_actions.api：bind_repository 改为 PUT /repositories/projects/{project_id}；apply_sop_plan 改为 create_plan_draft 指向 POST /planning/drafts；smoke 新增 _assert_actions_have_real_api_paths 验证每个 api 真实存在 |
| 2026-05-16 | BCL-03 | `02370b9` | smoke 4/4 passed; compileall clean | Pass（初版，需返工） | 新增 POST apply-local + git-commit；接入 workspace/gate/preflight/commit_candidate 完整 guard chain；安全校验：路径穿越/.git/workspace 边界；git_write_actions_triggered 动态追踪；不做 push/PR |
| 2026-05-16 | BCL-03 返工 | `afed0c3` | smoke 7/7 passed; compileall clean | Pass（返工） | 返工修复：1) git add --all → git add -- <apply.changed_files>，禁止提交无关脏文件；2) verification 失败时 status=applied_with_failed_verification，git_commit 被 apply_verification_failed 阻断；3) 新增 preflight/candidate/verification-fail/dirty-file 4 个 smoke 场景；4) 失败记录含 rollback_performed=false |
| 2026-05-16 | BCL-03 index 返工 | `8346a93` | smoke 8/8 passed; compileall clean | Pass（返工） | 返工修复：1) git_commit 前执行 git reset -- . 清空 index，防止预先 staged 的无关文件被提交；2) 新增 git diff --cached --name-only 精确校验，staged 与 changed_files 不一致时返回 staged_files_mismatch 阻断；3) smoke 新增 pre-staged unrelated file 场景 |
| 2026-05-16 | BCL-04 | `de09e6b` | smoke 6/6 passed; compileall clean | Pass | BudgetGuard 消费项目 budget_policy：hard_stop_enabled 时 project daily_budget_usd 覆盖默认值；evaluate_before_execution 新增 project_id 参数；cost dashboard 返回 budget_policy_source；worker run-once 传递 project_id；默认行为不受影响 |

---

## 11. 一句话结论

当前项目不是“后端全没做”，而是**工作包级能力很多已经存在，真正缺的是少数关键后端闭环：Provider 测试连接、闭环诊断聚合、真实 Git 写入、预算策略硬消费、真实 cache/usage telemetry、missing 口径产品化，以及最终证据汇总**。

下一步不要再大范围审计；直接从 `BCL-01 Provider 测试连接` 开始补。
