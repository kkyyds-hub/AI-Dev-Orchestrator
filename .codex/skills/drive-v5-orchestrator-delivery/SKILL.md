---
name: drive-v5-orchestrator-delivery
description: 将 AI-Dev-Orchestrator V5 母本中的跨 backend / web / docs / verify 整链推进任务收敛成中文总控交付型 skill。用于当单一实现 skill 已经不够时，识别工作包归属、锁定最小跨层交付切片、编排后端/前端/文档/验证动作，并把线程推进到真实可交接状态。
---

# drive-v5-orchestrator-delivery

## 使命与 owner

把 V5 线程里的“这已经不是单纯一个目录的问题了”收敛成 **跨层可推进、边界清楚、收口诚实、可继续接力** 的整链交付结果。

这个 skill 的 owner 职责只有一个：

> **负责识别跨边界任务、拉起正确的 backend / web / docs / verify 动作，并把一个工作包推进到真实可交付状态。**

它重点负责：

- 判断当前任务是否已经跨 backend / web / docs / verify
- 识别任务属于哪个 Phase / 工作包
- 锁定一个最小但完整的跨层交付切片
- 编排各面动作顺序，而不是在一个面里硬撑到底
- 保证线程结束时有真实状态、真实证据和下一棒 owner

它不应该把线程带偏成：

- 变成“大而空的总包规划”
- 抢走 backend / web / docs / verify / accept 各自 owner 的具体职责
- 什么都想一起做，结果没有任何一面真正收口
- 在没有最小验证和口径回填的情况下就宣布“整条链打通”

## 强绑定的权威输入

优先级从高到低如下：

1. `C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
2. `docs/README.md`
3. `C:\Users\Administrator\Desktop\ai-skills草案\00-V5-skill-suite-map.md`
4. `C:\Users\Administrator\Desktop\ai-skills草案\drive-v5-orchestrator-delivery-skill-草案.md`
5. `references/cross-surface-delivery-map.md`
6. `references/delivery-slice-and-routing-rules.md`
7. `references/evidence-and-handoff-packaging.md`
8. 当前线程直接涉及的实现、验证、审查、文档与页面现实

如果这些输入之间冲突，**以 V5 母本 + 仓库真实代码/页面现状 + 已验证事实为准**，不要让草案覆盖现实。

## V5 母本绑定原则

这个 skill 必须明确绑定到 V5 母本，不允许脱离 Phase / 工作包去做泛化项目经理式推进。

默认优先接管下列跨层型任务：

### Phase 1 最小闭环跨层推进

- Provider 抽象层 + 前端观察入口 + token / usage 口径 + 最小 verify
- Prompt registry + runtime 接线 + 页面入口 + 状态回填
- Memory recall 接入 worker + 前端可见性 + verify 证据

### Phase 2 / 3 的典型跨层推进

- checkpoint / summary / rehydrate 的后端、页面、验证联动
- agent session / review-rework thread 的后端、页面、证据与口径联动

### Phase 4 的典型跨层推进

- team assembly / team control center 的 backend + web + verify + accept 前置收口
- cost dashboard / cache 治理的口径、页面、证据与文档联动

如果用户没有明确指定阶段，默认先把任务收敛到一个 **工作包级最小交付切片**，而不是直接承诺推进整个 Phase。

## 技能边界

### 什么时候使用

在下列场景使用本 skill：

- 同一线程确实要同时改 backend 与 web
- 同一线程要把实现、文档、验证至少串起两到三个面
- 用户的目标不是“修一个点”，而是“把这一块推进到可交付”
- 某个 V5 工作包已经自然跨了多个 owner 面
- 你需要收口一个“跨层才成立”的最小闭环

### 不要使用

出现下列主任务时，不要继续停留在本 skill：

- 纯后端实现，且范围清晰：转 `write-v5-runtime-backend`
- 纯前端控制面实现，且契约明确：转 `write-v5-web-control-surface`
- 纯计划、冻结、状态回填：转 `manage-v5-plan-and-freeze-docs`
- 纯验证、查真相、回归证据：转 `verify-v5-runtime-and-regression`
- 纯代码与风险把关：转 `review-v5-code-and-risk`
- 纯里程碑裁定：转 `accept-v5-milestone-gate`

一句话：**只有当任务确实跨层、跨角色、跨产物时，这个 skill 才应该接管。**

## 正式落盘边界

### 本 skill 的主要输出形式

- 跨层交付切片定义
- backend / web / docs / verify 的动作编排
- 已完成 / 未完成 / 阻塞的诚实状态
- 最小验证结果
- 文档回填建议
- 下一线程接力建议

### 默认会触达的目录

- `runtime/orchestrator/`
- `apps/web/`
- `docs/01-版本冻结计划/`
- 当前线程直接涉及的验证和说明文件

### 默认不越权的面

- 不替 backend skill 长期接管后端 owner 职责
- 不替 web skill 长期接管前端 owner 职责
- 不替 verify / review / accept 假装完成对应裁定

## 开始入口

每次接手 V5 跨层交付任务时，先按下面顺序读取，且只读最小集合：

1. 打开 V5 母本：`C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
2. 打开 skill map：`C:\Users\Administrator\Desktop\ai-skills草案\00-V5-skill-suite-map.md`
3. 打开本 skill 自带参考：
   - `references/cross-surface-delivery-map.md`
   - `references/delivery-slice-and-routing-rules.md`
   - `references/evidence-and-handoff-packaging.md`
4. 打开仓库总入口：
   - `runtime/orchestrator/README.md`
   - `apps/web/package.json`
   - `docs/README.md`
5. 按任务类型最小补读 backend / web / docs / verify 入口

### 最小必读代码与页面入口

- `runtime/orchestrator/app/workers/task_worker.py`
- `runtime/orchestrator/app/services/strategy_engine_service.py`
- `runtime/orchestrator/app/services/executor_service.py`
- `runtime/orchestrator/app/services/context_builder_service.py`
- `runtime/orchestrator/app/services/project_memory_service.py`
- `runtime/orchestrator/app/core/db_tables.py`
- `apps/web/src/app/App.tsx`
- `apps/web/src/features/projects/ProjectOverviewPage.tsx`
- `apps/web/src/features/strategy/StrategyDecisionPanel.tsx`
- `apps/web/src/features/skills/SkillRegistryPage.tsx`

### 按交付面补读

#### backend 面

- `runtime/orchestrator/app/api/routes/*`
- `runtime/orchestrator/app/services/*`
- `runtime/orchestrator/app/repositories/*`

#### web 面

- `apps/web/src/features/...`
- 对应 `hooks.ts / types.ts / api.ts`

#### docs / freeze 面

- 当前阶段 / 工作包说明
- 当前线程说明
- 已有回填文档

#### verify / review 面

- `runtime/orchestrator/scripts/*_smoke.py`
- 最近一轮 verify 结论
- 最近一轮 review 结论

## 如何处理模糊请求

遇到“继续推进 V5 当前工作包”“把这一块整条链推过去”“别只修一个点”这类模糊请求时：

1. 先判断这是不是**真的跨层任务**。
2. 再锁定一个最小可交付切片。
3. 明确说出这次需要动哪些面、为什么不能只交给单一 owner skill。
4. 如果实际上只涉及一个面，应主动降级给对应 skill，不要滥用总控。

例如：

- “把 provider / memory 这一块完整推过去” → 可能需要 runtime + web 观察面 + verify + docs
- “把 team control 这一块推进到可交接” → 可能需要 web + backend 合同 + verify + accept 前置材料
- “把 prompt registry 做成真实交付” → 可能需要 runtime + web + verify + freeze 回填

## 核心工作流

### 1. 先判断这是不是跨边界任务

必须先回答：

- 当前属于哪个 Phase / 工作包
- 影响哪些面：backend / web / docs / verify / accept
- 是否至少跨两个 owner 面
- 如果只涉及一个面，是否应该降级给别的 skill

如果这个判断没做，本 skill 很容易变成“大而空的总包”。

### 2. 锁定最小交付切片

不要一上来就想做完整大系统。

优先选择如下切片：

- 一条 runtime 能力 + 一个前端入口 + 一层 verify
- 一个 team / strategy / memory 子能力的 backend-web 闭环
- 一个工作包的“实现 + 验证 + 文档回填准备”闭环

切片必须满足：**小到能推进，大到足以交接。**

### 3. 拆成多面动作，但保持一个 owner 线程

常见动作面：

- backend：补 service / route / worker / schema
- web：补页面 / 面板 / 抽屉 / 状态反馈
- docs：补完成定义、状态回填、证据路径
- verify：补 build / API / page / smoke 证据

本 skill 的职责不是把这些面平均展开，而是决定：

- 哪些本轮必须做
- 哪些本轮明确不做
- 哪些留给下一线程

### 4. 先收口“依赖链”，再收口“漂亮程度”

跨层任务最常见的问题是：

- 页面先做了，但后端合同没接
- 后端先做了，但没有观察面和验证
- 文档先写了，但实现和验证不闭合

因此优先顺序通常应是：

1. 依赖链闭合
2. 最小验证成立
3. 再做文档回填与交接美化

### 5. 保证状态诚实，不夸大交付

本 skill 线程结束时，必须同时写清：

- 已经做到什么
- 明确没做到什么
- 当前是已完成 / 部分完成 / 阻塞
- 为什么还不能上升为更大范围结论

总控线程最容易犯的错，就是把“推进了一截”写成“整条链完成”。

### 6. 给兄弟 skill 留明确接棒位

线程结束时，必须至少指定：

- 如果还需补实现，先给哪个 skill
- 如果还需补验证，先给哪个 skill
- 如果还需补冻结/回填，先给哪个 skill
- 如果已经具备裁定材料，下一步是否进入 `accept-v5-milestone-gate`

### 7. 只在必要时同时改多面

虽然这是跨层总控 skill，但仍应坚持：

- 不要为了“看起来完整”同时改太多面
- 只有真正阻塞交付闭环的面才在本轮纳入
- 其余内容明确列为遗留项，交给后续 owner

## 与兄弟 skill 的协作契约

- 本 skill 负责：**跨层切片定义、动作编排、状态收口、最小交付闭环、接棒安排**
- `write-v5-runtime-backend` 负责：**后端实现落地**
- `write-v5-web-control-surface` 负责：**前端控制面落地**
- `manage-v5-plan-and-freeze-docs` 负责：**完成口径、冻结文档、状态回填与交接治理**
- `verify-v5-runtime-and-regression` 负责：**运行事实、构建/API/页面验证与回归证据**
- `review-v5-code-and-risk` 负责：**结构、兼容性、主链、合同与风险把关**
- `accept-v5-milestone-gate` 负责：**阶段或工作包裁定**

这个 skill 不替代兄弟 skill，而是负责在同一线程里正确调用和串联它们的 owner 边界。

## 推荐输出骨架

优先使用下面骨架汇报本轮总控推进：

```md
# 本轮跨层交付切片

## 背景归属
- Phase：
- 工作包：
- 为什么属于跨层任务：
- 关联母本章节：

## 本轮切片
- 目标：
- 本轮纳入的面：backend / web / docs / verify
- 本轮明确不做：

## 动作与产出
- backend：
- web：
- docs：
- verify：

## 当前真实状态
- 已完成：
- 部分完成：
- 阻塞：
- 当前不能宣布完成的范围：

## 证据与风险
- 关键证据：
- 关键风险：
- 仍需补的前置条件：

## 交接路线
- 下一线程建议：
- 第二顺位：
- 如需 accept：
```

## 非完成定义

出现以下情况时，不能算本 skill 工作合格完成：

- 没证明是跨层任务，就直接滥用总控 skill
- 本轮切片过大，导致每一面都只做了一点点
- backend / web / docs / verify 的边界混乱
- 没有真实状态和证据，只剩空泛推进叙述
- 不写遗留项和下一棒 owner
- 把切片推进夸大成整阶段完成

## 红线

1. 不要把本 skill 用成“什么都包”的空洞总包。
2. 不要抢走兄弟 skill 的细分 owner 职责。
3. 不要在没有最小验证和诚实状态的情况下写“整条链打通”。
4. 不要因为跨层就一次性摊开过大范围。
5. 不要把局部推进误写成阶段完成。
6. 不要让线程结束后没有明确接棒位。

## Done checklist

- 已明确当前任务属于哪个 V5 Phase / 工作包。
- 已证明这次任务确实跨了至少两个 owner 面。
- 已引用 V5 母本，而不是脱离母本自由发挥。
- 已锁定一个最小但完整的跨层交付切片。
- 已明确本轮纳入哪些面、明确不纳入哪些面。
- 已编排 backend / web / docs / verify 的动作顺序或接力关系。
- 已诚实写出已完成、未完成、阻塞与不能宣布完成的范围。
- 已给出验证、风险与文档回填建议。
- 已明确下一线程应接的 owner skill。
- 已让后续新线程可以直接调用本 skill 接手同类跨层交付任务。

## References

- `references/cross-surface-delivery-map.md`
- `references/delivery-slice-and-routing-rules.md`
- `references/evidence-and-handoff-packaging.md`

- `playbooks/cross-surface-delivery-playbook.md`
- `references/cross-surface-delivery-thread-checklist.md`
- `templates/cross-surface-handoff-template.md`