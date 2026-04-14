---
name: write-v5-runtime-backend
description: 将 AI-Dev-Orchestrator V5 母本中的后端工作包真正落到 `runtime/orchestrator` 的中文实现型 skill。用于推进 worker、service、route、domain、repository、schema、运行日志、成本口径与最小验证，并明确与文档、前端、验证、验收线程的交接边界。
---

# write-v5-runtime-backend

## 使命与 owner

把 `AI-Dev-Orchestrator-V5-Plan.md` 里的 V5 后端能力，收敛成 **真实存在、可调用、可持久化、可验证、可交接** 的 `runtime/orchestrator` 改动。

这个 skill 的 owner 职责只有一个：

> **对 V5 后端落地负责，而不是对泛化规划、前端收口、验收裁定或文档冻结负责。**

它重点负责：

- worker 主链接入
- service / repository / domain / route 落地
- DB schema / 持久化结构变更
- 运行日志、token / cost、provider 回执等后端事实口径
- 最小可执行验证
- 给兄弟 skill 留下明确接力面

它不应该把线程带偏成：

- 继续抽象讨论架构但不动真实后端
- 改前端控制台页面
- 只写规划文档或冻结文档
- 只做评审、验收、回归结论
- 不做兼容性判断就宣布“后端已完成”

## 强绑定的权威输入

优先级从高到低如下：

1. `C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
2. `docs/README.md`
3. `C:\Users\Administrator\Desktop\ai-skills草案\00-V5-skill-suite-map.md`
4. `C:\Users\Administrator\Desktop\ai-skills草案\write-v5-runtime-backend-skill-草案.md`
5. `references/backend-surface-map.md`
6. `references/provider-memory-routing.md`
7. `references/migration-risk-checklist.md`
8. 为核对真实现状而最小读取的仓库代码文件

如果这些输入之间冲突，**以 V5 母本 + 仓库真实代码现状为准**，不要让桌面草案覆盖仓库事实。

## V5 母本绑定原则

这个 skill 必须明确绑定到 V5 母本，不允许脱离主背景自由发挥。

当用户没有明确指定阶段、工作包或切片时，默认优先按母本的 **Phase 1 最小闭环** 判断是否属于当前线程：

1. Provider 抽象层
2. Prompt registry v1
3. Token accounting v1
4. Role model policy v1
5. Worker 默认接入 project memory recall

如果任务明显跨到 Phase 2 及以后，也要先说明：

- 当前属于哪一阶段
- 为什么现在可以推进到这个阶段
- 与前置 Phase 1 基座是否存在依赖或缺口

## 技能边界

### 什么时候使用

在下列场景使用本 skill：

- 把 V5 的 provider gateway / model routing 真正接进执行链
- 把 prompt registry / prompt render / token accounting 落到后端
- 把 `project memory recall` 接进 worker 主链或上下文构造链
- 给 checkpoint / recovery / session / team control 增加 runtime 支撑
- 给运行记录、日志、成本统计增加真实 provider / usage 字段
- 把 strategy / skill / role policy 从“展示能力”推进到“运行时能力”
- 对某个 V5 后端工作包做增量实现、兼容处理和最小验证

### 不要使用

出现下列主任务时，不要继续停留在本 skill：

- 主要目标是拆规划、冻结文档、回填进度：转 `manage-v5-plan-and-freeze-docs`
- 主要目标是改 `apps/web` 控制台、面板或交互：转 `write-v5-web-control-surface`
- 主要目标是跨 backend / web / docs / verify 一起推进：转 `drive-v5-orchestrator-delivery`
- 主要目标是查运行事实、构建、接口、回归证据：转 `verify-v5-runtime-and-regression`
- 主要目标是做 schema / 兼容性 / 设计偏差风险审查：转 `review-v5-code-and-risk`
- 主要目标是宣布阶段通过、部分通过或阻塞：转 `accept-v5-milestone-gate`

## 正式落盘边界

### 本 skill 的主要输出目录

- `runtime/orchestrator/app/`
- `runtime/orchestrator/scripts/`
- `runtime/orchestrator/README.md`
- `runtime/orchestrator/pyproject.toml`

### 默认可改动的后端面

- `app/workers/`
- `app/services/`
- `app/api/routes/`
- `app/domain/`
- `app/repositories/`
- `app/core/`

### 默认不越权的面

- `apps/web/`：前端 owner 面，除非用户明确要求顺手做极小合同同步，否则交接给 `write-v5-web-control-surface`
- `docs/01-版本冻结计划/`：文档 owner 面，除非用户明确要求同步最小进度回填，否则交给 `manage-v5-plan-and-freeze-docs`
- 验收裁定与 pass/block 结论：交给 `accept-v5-milestone-gate`

## 开始入口

每次接手 V5 后端任务时，先按下面顺序读取，且只读最小集合：

1. 打开 V5 母本：`C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
2. 打开 skill map：`C:\Users\Administrator\Desktop\ai-skills草案\00-V5-skill-suite-map.md`
3. 打开本 skill 自带参考：
   - `references/backend-surface-map.md`
   - `references/provider-memory-routing.md`
   - `references/migration-risk-checklist.md`
4. 打开 `runtime/orchestrator/README.md` 与 `runtime/orchestrator/pyproject.toml`，确认当前运行方式与依赖边界
5. 按任务类型只打开最相关的后端文件

### 最小必读代码入口

- `runtime/orchestrator/app/workers/task_worker.py`
- `runtime/orchestrator/app/services/strategy_engine_service.py`
- `runtime/orchestrator/app/services/executor_service.py`
- `runtime/orchestrator/app/services/context_builder_service.py`
- `runtime/orchestrator/app/services/project_memory_service.py`
- `runtime/orchestrator/app/services/cost_estimator_service.py`
- `runtime/orchestrator/app/services/skill_registry_service.py`
- `runtime/orchestrator/app/core/db_tables.py`

### 按工作包补读

#### Provider / prompt / token 类

- `app/services/strategy_engine_service.py`
- `app/services/executor_service.py`
- `app/services/cost_estimator_service.py`
- `app/api/routes/strategy.py`
- `app/api/routes/runs.py`
- `app/domain/run.py`
- `app/core/db_tables.py`

#### Memory / checkpoint / context 类

- `app/workers/task_worker.py`
- `app/services/context_builder_service.py`
- `app/services/project_memory_service.py`
- `app/services/run_logging_service.py`
- 相关 `domain` / `repository` / `route` 文件

#### Skill / role / session / team control 类

- `app/services/skill_registry_service.py`
- `app/services/role_catalog_service.py`
- `app/services/task_service.py`
- `app/api/routes/skills.py`
- `app/api/routes/roles.py`
- 相关 `domain` / `repository` / `route` 文件

## 如何处理模糊请求

遇到“继续做 V5 后端”“把 runtime 补起来”“先把 provider / memory / token 接进去”这类模糊请求时：

1. 先把请求翻译成 **一个工作包 + 一个后端切片**。
2. 默认选择最接近 V5 Phase 1 的最小闭环切片。
3. 明确说出你选择的切片、入口文件和为什么不是更大范围。
4. 没有必要时，不要把线程升级成跨层交付。

例如：

- “继续做模型执行” → 先落 `Provider 抽象 + Executor 接线 + Run usage 口径`
- “把记忆接起来” → 先落 `TaskWorker -> ContextBuilder(include_project_memory) -> ProjectMemoryService`
- “补成本统计” → 先落 `provider usage 回执 -> RunTable / logs / API DTO`

## 核心工作流

### 1. 先把任务翻译成后端对象

先明确：

- 属于哪个 Phase / 工作包
- 最终落在哪些对象上：worker、service、route、domain、repository、schema、日志还是脚本
- 现有代码里最接近的能力是什么
- 这次是沿已有结构扩展，还是确实需要新增一条后端子链

如果这一步不做，很容易平行造出“第二套系统”。

### 2. 先确认当前真实状态

至少确认下面几件事：

- 当前仓库是否已经有半成品逻辑
- 当前 worker 主链是否已经调用到该能力
- 当前 API 是否已有入口或观察面
- 当前 DB / JSON / 日志落点分别在哪里
- 当前前端是否已经依赖了某些字段

优先核对以下真实事实，不要靠猜：

- `task_worker.py` 当前是 `build_context_package(task=task)`，默认没有显式打开 `include_project_memory=True`
- `executor_service.py` 当前核心执行模式仍是 `shell` / `simulate`
- `cost_estimator_service.py` 当前仍是启发式 token/cost 估算
- `db_tables.py` 中 `RunTable` 已有 `model_name`、`prompt_tokens`、`completion_tokens`、`estimated_cost`，但新增 provider / tier / usage 字段前必须先核对现状
- `project_memory_service.py` 当前会把快照写到 `settings.runtime_data_dir / project-memories / ...`

### 3. 做单线程可交付的后端切片

每个线程尽量只选一个清晰切片，例如：

- 给 `ExecutorService` 引入 provider adapter 抽象
- 给 `TaskWorker` 默认接入 `include_project_memory`
- 给 `Run` / 运行日志增加 provider usage 与 model tier 口径
- 给 checkpoint 新增 domain + persistence + worker 读写入口
- 给 session / team control 增加最小 domain + route + service 主链

切片设计必须回答五个问题：

1. 入口在哪
2. 主处理链在哪
3. 结果存在哪
4. 谁会消费这个结果
5. 失败时如何降级或回退

### 4. 优先沿现有结构增量扩展

V5 不是推翻 V1-V4 重写，所以默认优先：

- 在现有 `services/` 中扩展
- 在现有 `workers/` 主链中接线
- 在现有 `api/routes/` 中补接口或 DTO
- 在现有 `domain/` 与 `db_tables.py` 中补结构
- 在现有 `repositories/` 中补持久化行为

除非明确被现有结构阻塞，否则不要新增与原体系平行的 runtime 主链。

### 5. 先做文件级实现清单，再动手

开始改代码前，至少在脑中或回复里明确：

- 要改哪些文件
- 每个文件承担什么职责
- 哪些是新增文件，哪些是扩展旧文件
- 是否需要 migration 或数据兼容
- 是否需要接口 DTO 同步
- 是否需要 worker / route / script 验证入口

### 6. 显式处理兼容性与迁移风险

必须检查：

- 是否需要 migration
- 老数据是否允许为空
- 新字段是否需要默认值
- API 响应是否会破坏旧前端
- `simulate` 和真实 provider 模式如何共存
- JSON 快照、运行日志和数据库字段之间是否会出现双重口径
- 失败时是否能退回旧链路而不是让 worker 全面中断

详细检查项见：`references/migration-risk-checklist.md`

### 7. 做最小验证，不要空口宣布完成

最低建议：

- 至少做一次导入级或脚本级验证
- 如改了后端启动入口，确认应用可启动
- 如改了 route，至少做一次请求级验证或构造数据验证
- 如改了 worker 主链，至少跑一次最短链路
- 如改了 schema / 持久化，至少确认写入与读取都没有明显断裂

可优先参考：

- `runtime/orchestrator/README.md` 中的运行方式
- 现有 `runtime/orchestrator/scripts/` 下可复用脚本
- `python -m compileall app`

### 8. 明确交接路线

线程结束时必须明确下一棒是谁：

- 需要补前端展示 / 表单 / 控制台 → `write-v5-web-control-surface`
- 需要把状态写回冻结文档 / 计划文档 → `manage-v5-plan-and-freeze-docs`
- 需要查构建、接口、联调或回归证据 → `verify-v5-runtime-and-regression`
- 需要审查 schema / 风险 / 实现质量 → `review-v5-code-and-risk`
- 需要阶段裁定 → `accept-v5-milestone-gate`
- 如果线程已经自然跨层 → 直接升级 `drive-v5-orchestrator-delivery`

## 与兄弟 skill 的协作契约

- 本 skill 负责：**后端代码落地、主链接线、持久化、最小验证、交接说明**
- `manage-v5-plan-and-freeze-docs` 负责：**阶段定位、冻结文档、状态回填、交接治理**
- `write-v5-web-control-surface` 负责：**前端控制面、页面、交互、展示接线**
- `drive-v5-orchestrator-delivery` 负责：**跨 backend / web / docs / verify 的整链推进**
- `verify-v5-runtime-and-regression` 负责：**运行事实、构建、接口、联调、回归证据**
- `review-v5-code-and-risk` 负责：**实现质量、兼容性、迁移与口径风险识别**
- `accept-v5-milestone-gate` 负责：**阶段 pass / partial / blocked 裁定**

不要替兄弟 skill 越权宣布“已验收通过”；本 skill 只能就当前后端切片给出实现与验证事实。

## 推荐输出骨架

优先使用下面骨架汇报当前线程结果：

```md
# 本轮后端切片

## 背景归属
- Phase：
- 工作包：
- 关联母本章节：

## 当前真实状态
- 已有链路：
- 本轮补的缺口：
- 明确未动：

## 文件级改动
- workers：
- services：
- api/routes：
- domain / repositories / db：
- scripts / docs：

## 兼容性与风险
- migration：
- 默认值 / 回退逻辑：
- simulate / provider 共存策略：
- 仍未解决的问题：

## 验证与证据
- 已执行：
- 结果：
- 未执行：

## 交接路线
- 下一线程建议：
- 如需前端：
- 如需 verify：
- 如需 docs：
- 如需 acceptance：
```

## 非完成定义

出现以下情况时，不能算本 skill 工作合格完成：

- 只写了 route / DTO，没有接入真实处理链
- 只写了 service 草图，没有接入 worker / repository / schema
- 只新增了字段设想，没有处理迁移与兼容性
- 只说“应该可以”，没有任何最小验证
- 把未验证内容写成“V5 后端已完成”
- 把明显跨层任务硬塞在本 skill，不做升级交接

## 红线

1. 不要脱离 `AI-Dev-Orchestrator-V5-Plan.md` 重发明 V5。
2. 不要另起一套与 `runtime/orchestrator` 平行的后端系统。
3. 不要把“策略展示层已有字段”误写成“真实 provider 执行层已落地”。
4. 不要跳过 migration / 默认值 / 回退策略判断。
5. 不要把 JSON 快照路径、Run 字段、API DTO 等关键事实当成猜测。
6. 不要在没有最小验证的情况下写“后端完成”。

## Done checklist

- 已明确当前任务属于哪个 V5 Phase / 工作包。
- 已引用 V5 母本，而不是脱离母本自由发挥。
- 已最小核对 `runtime/orchestrator` 真实代码现状。
- 已把任务收敛成一个明确的后端切片，而不是空泛大任务。
- 已写清入口、主链、持久化落点、消费方与失败回退。
- 已沿现有 `workers / services / routes / domain / repositories / core` 结构增量扩展。
- 已说明 schema / migration / 默认值 / 兼容策略。
- 已做至少一级最小验证，或明确说明缺证原因。
- 已给出下一线程应接的 owner skill。
- 已让后续新线程可以直接调用本 skill 接手同类后端工作包。

## References

- `references/backend-surface-map.md`
- `references/provider-memory-routing.md`
- `references/migration-risk-checklist.md`

- `playbooks/backend-delivery-playbook.md`
- `references/backend-thread-checklist.md`
- `templates/backend-handoff-template.md`