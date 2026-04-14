---
name: manage-v5-plan-and-freeze-docs
description: 将 AI-Dev-Orchestrator V5 母本规划转成正式冻结文档、阶段切片、工作包顺序、完成口径、进度回填与线程接力说明的中文治理 skill。用于 V5 计划拆解、V5 文档冻结、工作包完成定义/非完成定义、状态诚实回填、下一线程 owner skill 指派，以及需要把桌面草案或临时结论落回仓库正式文档体系 `docs/01-版本冻结计划/V5/` 时。
---

# manage-v5-plan-and-freeze-docs

## 使命与 owner

把 `AI-Dev-Orchestrator` 的 **V5 母本规划** 收敛为后续线程可直接执行的正式文档系统。

这个 skill 的 owner 职责只有一个：**管住 V5 的计划口径、冻结边界、进度诚实度和线程接力面**。

把它当成 V5 的文档治理 owner，而不是泛化的“帮忙写点规划”技能。

它要确保后续线程不会：

- 脱离 V5 母本乱扩 scope
- 把“计划中”写成“已完成”
- 把工作包写成概念口号
- 写完文档却没有下一步接力说明
- 在仓库里凭空膨胀出一堆空骨架文档

## 强绑定的权威输入

优先级从高到低如下：

1. `C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
2. `docs/README.md`
3. `docs/01-版本冻结计划/00-总计划/00-总计划.md`
4. `docs/01-版本冻结计划/00-总计划/01-目录说明.md`
5. 已冻结的 `docs/01-版本冻结计划/V1/` ~ `V4/`
6. `C:\Users\Administrator\Desktop\ai-skills草案\00-V5-skill-suite-map.md`
7. `C:\Users\Administrator\Desktop\ai-skills草案\manage-v5-plan-and-freeze-docs-skill-草案.md`
8. 为核对现实而最小读取的仓库代码文件

如果这些输入之间冲突，**以 V5 母本 + 仓库正式冻结文档体系 + 当前真实代码现状为准**，不要以桌面草案覆盖仓库事实。

## 正式落盘边界

### 正式输出根目录

- `docs/01-版本冻结计划/V5/`

### 输入草案来源

- `C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
- `C:\Users\Administrator\Desktop\ai-skills草案\`
- `.tmp/local-drafts/` 下的临时材料

### 文档治理原则

- 把桌面草案当作**输入**，不要把桌面草案当作正式产物。
- 把 `docs/01-版本冻结计划/` 当作仓库内唯一正式冻结文档体系。
- 如未确认，不要一次性生成大批空白 Day 文档或空白工作包文档。
- 只创建当前线程真正需要的最小正式文档集合。

## 何时使用

在下列场景使用本 skill：

- 把 V5 母本拆成 Phase、工作包、执行顺序
- 为某个 V5 工作包编写正式冻结文档或执行草案
- 回填某个 V5 工作包的真实状态、缺口、风险、验证证据
- 给后续线程写清楚“下一步由哪个 skill 接手”
- 判断某项内容是否已经够资格写入仓库正式文档
- 建立 V5 与既有 V1~V4 冻结文档体系的一致目录和口径

## 不要使用

出现下列主任务时，不要继续停留在本 skill：

- 主要目标是改后端实现：转 `write-v5-runtime-backend`
- 主要目标是改前端控制台：转 `write-v5-web-control-surface`
- 主要目标是跨后端/前端/文档联动交付：转 `drive-v5-orchestrator-delivery`
- 主要目标是查运行事实、回归、构建、接口：转 `verify-v5-runtime-and-regression`
- 主要目标是做代码/迁移/状态口径风险审查：转 `review-v5-code-and-risk`
- 主要目标是做阶段通过/部分通过/阻塞裁定：转 `accept-v5-milestone-gate`

## 开始入口

每次接手 V5 文档任务时，先按下面顺序读取，且只读最小集合：

1. 打开 V5 母本：`C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
2. 打开仓库文档入口：`docs/README.md`
3. 打开总计划与目录规则：
   - `docs/01-版本冻结计划/00-总计划/00-总计划.md`
   - `docs/01-版本冻结计划/00-总计划/01-目录说明.md`
4. 打开 `references/v5-doc-governance-map.md`
5. 如果任务与切片有关，再打开 `references/v5-work-package-slicing-rules.md`
6. 如果任务与冻结裁定、进度回填、交接有关，再打开 `references/v5-handoff-and-freeze-checklist.md`
7. 只抽查和本次工作包直接相关的代码文件，确认规划没有脱离现实

默认最小现实核对文件：

- `runtime/orchestrator/app/services/strategy_engine_service.py`
- `runtime/orchestrator/app/services/executor_service.py`
- `runtime/orchestrator/app/services/project_memory_service.py`
- `runtime/orchestrator/app/services/context_builder_service.py`
- `runtime/orchestrator/app/services/cost_estimator_service.py`
- `runtime/orchestrator/app/workers/task_worker.py`
- `apps/web/src/features/projects/ProjectOverviewPage.tsx`
- `apps/web/src/features/strategy/StrategyDecisionPanel.tsx`

## 标准工作流

### 1. 先对齐母本、正式文档体系与代码现实

先回答 5 个问题，再动笔：

1. V5 母本要求的能力属于哪个 Phase、哪个工作包？
2. 现有 V1~V4 冻结体系里，哪些结构可以直接沿用？
3. 仓库代码里已经真实存在什么？只是演示级存在什么？完全不存在什么？
4. 本次要写的是“计划”、 “冻结”、 “回填”、 “交接”中的哪一种？
5. 哪些话可以写成已完成，哪些只能写成已规划、已实现待验证或阻塞？

### 2. 明确本次文档类型

先给当前任务定类，不要混写：

- `总纲型`：定义 V5 阶段顺序、模块边界、主线约束
- `工作包型`：定义某一包的目标、依赖、改动面、完成口径
- `进度回填型`：记录当前真实状态、证据、缺口、风险
- `冻结裁定型`：说明哪些结论可以写入正式基线
- `线程接力型`：给下一线程明确 owner skill、起点与验证要求

同一份文档只承担一个主类型；确实需要混合时，也要显式分段。

### 3. 把工作包切成可执行切片

所有 V5 文档都要落到切片，而不是停在能力名词。

每个切片至少写清：

- Phase
- 工作包名
- 背景归属章节
- 本轮 owner skill
- 主要改动目录/文件面
- 前置依赖
- 本轮完成定义
- 非完成定义
- 最低验证要求
- 下一线程建议

具体切片规则见 `references/v5-work-package-slicing-rules.md`。

### 4. 坚持“完成定义 / 非完成定义”双写法

必须同时写两类口径：

- **完成定义**：这轮做完后，什么可以明确写成完成
- **非完成定义**：哪些看起来像进展，但还不能写成完成

尤其禁止把以下情况直接写成完成：

- 只有计划，没有实现
- 只有页面壳子，没有真实数据链路
- 只有 service/interface 草案，没有真实接线
- 只有代码提交，没有运行或最小验证
- 只有模拟结果，没有真实执行证据

### 5. 用诚实状态词回填

状态只能从下面集合里选，不要自造模糊词：

- `已完成`
- `已实现待验证`
- `已规划`
- `进行中`
- `阻塞`

写状态时必须同时补：

- 证据路径
- 风险说明
- 缺口说明
- 下一步接力建议

### 6. 明确兄弟 skill 交接路线

当文档落地后，必须给出下一线程 owner：

- 后端实现 → `write-v5-runtime-backend`
- 前端控制面 → `write-v5-web-control-surface`
- 跨层交付 → `drive-v5-orchestrator-delivery`
- 运行验证 → `verify-v5-runtime-and-regression`
- 风险审查 → `review-v5-code-and-risk`
- 里程碑裁定 → `accept-v5-milestone-gate`

如果当前任务本质上已经跨层，不要继续硬撑在文档线程里，把交接建议明确升级到 `drive-v5-orchestrator-delivery`。

### 7. 回写正式冻结文档体系

回写时遵守下面规则：

- 优先延续 `docs/01-版本冻结计划/` 已有风格与层级
- 先写总纲/模块说明/工作包说明，再决定是否需要更细颗粒文档
- 不创建“看起来完整”的空白矩阵、空白 Day 骨架、空白测试页
- 明确记录当前文档属于正式冻结、工作中回填，还是仅为下一线程准备

## 与兄弟 skill 的协作契约

- 本 skill 负责：**计划边界、冻结口径、状态回填、交接规则**
- `write-v5-runtime-backend` 负责：**后端 domain/service/repository/api/worker 落地**
- `write-v5-web-control-surface` 负责：**前端控制面与交互落地**
- `drive-v5-orchestrator-delivery` 负责：**跨层整链推进**
- `verify-v5-runtime-and-regression` 负责：**事实验证与证据采集**
- `review-v5-code-and-risk` 负责：**风险识别与实现质量审视**
- `accept-v5-milestone-gate` 负责：**阶段裁定**

不要越权替兄弟 skill 宣布“已交付”；只能宣布文档层面的冻结结论和证据口径。

## 推荐输出骨架

优先使用下面骨架写 V5 工作包/冻结文档：

```md
# 标题

## 背景归属
- Phase：
- 工作包：
- 关联母本章节：

## 当前真实状态
- 已有：
- 缺口：
- 关键假设：

## 本轮推进切片
- owner skill：
- 主要改动面：
- 前置依赖：
- 完成定义：
- 非完成定义：

## 验证与证据要求
- 最低验证：
- 证据路径：

## 风险与边界
- 当前风险：
- 明确不做：

## 交接路线
- 下一线程建议：
- 第二顺位：
- 如需验证转：
- 如需验收转：
```

## 线程结束前必须留下的交接物

至少留下以下信息：

- 阶段定位
- 工作包定位
- 改动范围
- 真实状态
- 风险说明
- 验证证据或缺证说明
- 下一步 owner skill
- 文档是否已回填到正式目录

如果这些都没有，这个线程结果就不具备可接力性。

## 红线

1. 不要脱离 `AI-Dev-Orchestrator-V5-Plan.md` 重新发明 V5。
2. 不要把未验证的内容写成已完成。
3. 不要把工作包名称写成空洞能力宣传语。
4. 不要不给后续线程留下接力路径。
5. 不要因为“想显得完整”就一口气生成大量空文档。
6. 不要越过代码现实，写出与仓库状态相冲突的冻结结论。

## Done checklist

- 已明确引用 V5 母本，而不是脱离母本自由发挥。
- 已确认正式输出根目录是 `docs/01-版本冻结计划/V5/`。
- 已最小核对相关代码现实，避免空中规划。
- 已把当前任务归类为总纲型 / 工作包型 / 进度回填型 / 冻结裁定型 / 线程接力型之一。
- 已写清 owner、边界、开始入口、工作流、交接规则。
- 已同时写出完成定义与非完成定义。
- 已明确下一线程 owner skill。
- 已避免批量制造空白占位文档。
- 已让后续新线程可以直接调用本 skill 接手。

## References

- `references/v5-doc-governance-map.md`
- `references/v5-work-package-slicing-rules.md`
- `references/v5-handoff-and-freeze-checklist.md`

- `playbooks/freeze-doc-thread-playbook.md`
- `references/freeze-thread-checklist.md`
- `templates/freeze-handoff-template.md`