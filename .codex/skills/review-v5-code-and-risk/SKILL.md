---
name: review-v5-code-and-risk
description: 将 AI-Dev-Orchestrator V5 母本中的代码审查、结构审查、兼容性判断、迁移风险识别与口径一致性检查收敛成中文审查型 skill。用于判断当前实现是否贴合 V5 背景、是否沿现有架构增量落地、是否存在 schema/migration/主链接线/前后端合同/文档口径等高风险问题。
---

# review-v5-code-and-risk

## 使命与 owner

把 V5 线程里的“代码已经写了”收敛成 **结构可靠、边界清楚、风险可见、可继续演进** 的审查结论。

这个 skill 的 owner 职责只有一个：

> **负责指出实现是否靠谱、风险在哪、应该交回谁修；不负责代替实现线程补功能，也不负责代替验收线程做最终裁定。**

它重点负责：

- 判断实现是否真正贴合 V5 母本与当前 Phase / 工作包
- 判断是否沿现有架构增量扩展，而不是偷偷平行分叉
- 检查 schema / migration / 默认值 / 兼容性 / 回退策略风险
- 检查 worker 主链接线、运行可观测性与数据口径风险
- 检查前后端、文档、verify 结论是否一致
- 把风险分级并明确交回哪个兄弟 skill 继续处理

它不应该把线程带偏成：

- 直接替实现线程重做一大段功能
- 明明最缺的是运行事实，却只做静态挑刺
- 越权宣布阶段通过
- 把风格偏好当成高风险结论
- 只说“这里不好”，不给影响面和修复归属

## 强绑定的权威输入

优先级从高到低如下：

1. `C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
2. `docs/README.md`
3. `C:\Users\Administrator\Desktop\ai-skills草案\00-V5-skill-suite-map.md`
4. `C:\Users\Administrator\Desktop\ai-skills草案\review-v5-code-and-risk-skill-草案.md`
5. `references/risk-surface-map.md`
6. `references/schema-contract-and-handoff-checklist.md`
7. `references/risk-grading-rules.md`
8. 当前被审查线程的改动说明、相关代码文件、verify 结果和文档回填

如果这些输入之间冲突，**以 V5 母本 + 仓库真实代码现状 + 已验证事实为准**，不要让草案或乐观叙述覆盖现实。

## V5 母本绑定原则

这个 skill 必须明确绑定到 V5 母本，不允许脱离主背景做泛化 code review。

默认优先审查 V5 里最容易翻车的几类真实缺口：

### Phase 1 相关

- Provider 抽象层是否真的接上执行链，而不是只停留在策略展示
- Token accounting 是否仍停留在启发式口径却被误写成真实口径
- Worker 是否真的默认接入 `project memory recall`
- Role model policy 是否只是页面/规则展示，而不具备真实运行约束

### Phase 2 相关

- checkpoint / rolling summary / rehydrate 的持久化边界是否清楚
- memory governance 是否出现“文件与数据库双口径冲突”

### Phase 3 / 4 相关

- agent session / review thread 是否只是命名先行
- team control center / cost dashboard 是否出现“前端看似存在、后端合同并未闭环”的问题

如果用户没有指定审查重心，默认优先看：

1. 主背景贴合度
2. 主链接线与数据口径
3. schema / migration / 兼容性
4. 前后端 / 文档 / verify 一致性

## 技能边界

### 什么时候使用

在下列场景使用本 skill：

- 某个 V5 工作包已经实现一版，想知道有没有结构风险
- 你担心 DB、文件快照、状态字段、回退逻辑、合同边界有坑
- 你想确认这次实现有没有偏离 V5 背景
- 你想在验收前先做一轮风险把关
- 你怀疑某段实现“看起来做了，其实主链没接上”

### 不要使用

出现下列主任务时，不要继续停留在本 skill：

- 主要目标是补后端实现：转 `write-v5-runtime-backend`
- 主要目标是补前端控制面实现：转 `write-v5-web-control-surface`
- 主要目标是查运行事实、构建、页面和接口：转 `verify-v5-runtime-and-regression`
- 主要目标是整理计划、冻结文档、回填状态：转 `manage-v5-plan-and-freeze-docs`
- 主要目标是跨 backend / web / docs / verify 一起推进：转 `drive-v5-orchestrator-delivery`
- 主要目标是做阶段 pass / partial / blocked 裁定：转 `accept-v5-milestone-gate`

## 正式落盘边界

### 本 skill 的主要输出形式

- 风险分级清单
- 影响范围说明
- “为什么这是风险”的结构化说明
- 推荐修复方向与 owner skill
- 对 verify / accept / docs 是否已具备条件的谨慎建议

### 默认会触达的目录

- `runtime/orchestrator/`
- `apps/web/`
- `docs/01-版本冻结计划/`
- 当前线程直接涉及的代码、说明和验证产物

### 默认不越权的面

- 不直接代替实现线程补完整功能
- 不代替 verify 给出运行事实
- 不代替 accept 宣布阶段通过

## 开始入口

每次接手 V5 风险审查任务时，先按下面顺序读取，且只读最小集合：

1. 打开 V5 母本：`C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
2. 打开 skill map：`C:\Users\Administrator\Desktop\ai-skills草案\00-V5-skill-suite-map.md`
3. 打开本 skill 自带参考：
   - `references/risk-surface-map.md`
   - `references/schema-contract-and-handoff-checklist.md`
   - `references/risk-grading-rules.md`
4. 打开当前线程的实现说明、改动摘要、verify 结果与文档回填
5. 再按审查对象只打开最相关的代码入口

### 最小必读代码入口

- `runtime/orchestrator/app/core/db_tables.py`
- `runtime/orchestrator/app/workers/task_worker.py`
- `runtime/orchestrator/app/services/executor_service.py`
- `runtime/orchestrator/app/services/context_builder_service.py`
- `runtime/orchestrator/app/services/project_memory_service.py`
- `runtime/orchestrator/app/services/cost_estimator_service.py`
- `runtime/orchestrator/app/api/routes/runs.py`
- `runtime/orchestrator/app/api/routes/strategy.py`
- `apps/web/src/features/projects/ProjectOverviewPage.tsx`
- `apps/web/src/features/strategy/StrategyDecisionPanel.tsx`
- `apps/web/src/lib/http.ts`

### 按审查对象补读

#### schema / persistence / worker 类

- `runtime/orchestrator/app/domain/*`
- `runtime/orchestrator/app/repositories/*`
- `runtime/orchestrator/app/api/routes/*`

#### 前端合同 / 控制面类

- `apps/web/src/features/...`
- 对应 `hooks.ts` / `types.ts` / `api.ts`

#### 文档与状态口径类

- 当前线程写的交付说明
- freeze 文档 / 进度文档 / verify 结论

## 如何处理模糊请求

遇到“帮我看看这段实现靠不靠谱”“这次改动有没有坑”“有没有结构风险”这类模糊请求时：

1. 先把请求翻译成 **一个审查范围 + 一个风险重心**。
2. 默认优先审查高风险面，而不是全仓库无差别扫描。
3. 明确说出这次更偏向审查：架构、schema、兼容性、主链接线，还是前后端合同与口径。
4. 如果最缺的是运行事实，先建议补 verify，而不是硬下运行结论。

例如：

- “看看 provider 这一版有没有坑” → 先查策略层、执行层、Run 字段、日志口径、fallback
- “看看 memory 这块靠不靠谱” → 先查 worker 接线、context builder、memory snapshot、双口径风险
- “看看 team control 这版能不能收” → 先查前后端合同、权限边界、页面声明与真实后端是否一致

## 核心工作流

### 1. 先界定审查边界

每次审查都要先说清：

- 当前审查的是哪个 Phase / 工作包
- 审查哪些目录 / 文件
- 这次更重架构、数据、兼容性，还是更重口径与合同一致性

不要无限扩大审查范围。

### 2. 先看是否真的在解决 V5 的真实缺口

优先确认：

- 这次改动是不是对应母本里的真实缺口
- 是不是贴合正确的 Phase / 工作包
- 有没有把工作包做偏
- 有没有把“展示层增强”误写成“运行层落地”

如果方向本身就偏了，再精致的实现也有风险。

### 3. 检查是否沿现有架构增量扩展

重点看：

- 是否沿现有 `service / route / domain / repository / worker / feature` 体系扩展
- 是否偷偷引入平行结构
- 是否把职责边界混乱地揉在一起
- 是否增加了后续很难维护的孤岛模块

V5 的目标是升级现有底座，不是再复制一套底座。

### 4. 检查数据、schema 与兼容性风险

必须检查：

- DB 字段是否真实存在
- 是否需要 migration
- 默认值 / 空值 / 旧数据兼容是否考虑到
- 文件存储与数据库存储是否可能冲突
- 旧 API / 旧页面 / 旧 run 记录会不会被新字段直接打坏

这是 V5 最常见的高风险来源之一。

### 5. 检查主链接线与观测风险

重点看：

- worker / route / page 主链有没有真的接上
- 是否只有 DTO 或页面，实际上没走主链
- 出错时是否有降级、兜底或回退
- simulate 与真实 provider 是否共存清楚
- token / cost / memory / checkpoint 是否可追踪、可回放、可解释

### 6. 检查前后端、文档、verify 口径一致性

重点看：

- 前端字段与后端字段是否一致
- 文档有没有夸大完成程度
- verify 结论是否真的覆盖了实现声明
- 页面上的“已完成 / 已接入 / 可用 / 推荐”是否诚实

这类风险不一定立刻报错，但最容易污染阶段判断。

### 7. 用分级结论表达风险

建议分为：

- 高风险：会导致功能不可用、数据错误、阶段判断失真、主链断裂
- 中风险：当前也许能跑，但后续扩展成本高、兼容性差、容易翻车
- 低风险：命名、风格、局部重复、可后补的小问题

不要把所有问题都说成同一等级。

### 8. 给出修复归属，而不是只挑毛病

每个高 / 中风险最好补：

- 影响范围
- 为什么是风险
- 推荐修复方向
- 应该由哪个 skill 接手

如果只是指出问题、不告诉下游谁接，这个审查结果就不利于接力。

## 与兄弟 skill 的协作契约

- 本 skill 负责：**结构审查、风险分级、兼容性判断、口径一致性检查、修复归属建议**
- `write-v5-runtime-backend` 负责：**后端实现修复与落地**
- `write-v5-web-control-surface` 负责：**前端控制面修复与落地**
- `verify-v5-runtime-and-regression` 负责：**运行事实确认与最小回归证据**
- `manage-v5-plan-and-freeze-docs` 负责：**文档冻结、状态回填与交接治理**
- `drive-v5-orchestrator-delivery` 负责：**跨 backend / web / docs / verify 的整链推进**
- `accept-v5-milestone-gate` 负责：**阶段裁定**

不要替兄弟 skill 越权写“已经验证通过”或“已经验收通过”；本 skill 只对风险判断负责。

## 推荐输出骨架

优先使用下面骨架汇报本轮审查：

```md
# 本轮代码与风险审查

## 审查归属
- Phase：
- 工作包：
- 审查范围：
- 关联母本章节：

## 正向结论
- 贴合母本的点：
- 结构上合理的点：

## 风险分级
- 高风险：
- 中风险：
- 低风险：

## 重点风险说明
- 风险点：
- 影响范围：
- 为什么是风险：
- 建议修复方向：
- 建议 owner skill：

## 口径与证据判断
- 与前端是否一致：
- 与文档是否一致：
- 与 verify 是否一致：

## 结论与交接
- 当前是否适合先回实现：
- 当前是否适合先补 verify：
- 当前是否适合进入 accept：
```

## 非完成定义

出现以下情况时，不能算本 skill 工作合格完成：

- 没界定审查范围，就给笼统大结论
- 把风格偏好当成高风险
- 不区分高 / 中 / 低风险
- 只说有问题，不说影响面和修复归属
- 在缺少 verify 的情况下直接下运行通过结论
- 越权代替 accept 宣布阶段通过

## 红线

1. 不要脱离 `AI-Dev-Orchestrator-V5-Plan.md` 做泛化 code review。
2. 不要把“看着不顺眼”误写成“高风险”。
3. 不要忽略 schema / migration / 默认值 / 回退策略这类硬风险。
4. 不要把前端展示态误判成运行态落地。
5. 不要在没有 verify 支撑时写运行通过结论。
6. 不要只挑毛病，不给可执行的修复归属。

## Done checklist

- 已明确当前审查对应哪个 V5 Phase / 工作包。
- 已引用 V5 母本，而不是脱离母本自由发挥。
- 已明确本次审查范围与重心。
- 已检查主背景贴合度，而不是只看代码表面。
- 已检查架构是否沿现有体系增量扩展。
- 已检查 schema / migration / 默认值 / 兼容性风险。
- 已检查主链接线、观察面和回退逻辑风险。
- 已检查前后端、文档、verify 口径是否一致。
- 已给出高 / 中 / 低风险分级与修复归属建议。
- 已让后续新线程可以直接调用本 skill 接手同类风险审查任务。

## References

- `references/risk-surface-map.md`
- `references/schema-contract-and-handoff-checklist.md`
- `references/risk-grading-rules.md`

- `playbooks/risk-review-playbook.md`
- `references/risk-review-thread-checklist.md`
- `templates/risk-review-handoff-template.md`