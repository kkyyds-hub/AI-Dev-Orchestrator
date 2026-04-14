# V5 文档治理地图

## 1. 目的

把 V5 文档治理统一绑定到：

- 桌面母本：`C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
- 仓库正式冻结体系：`docs/01-版本冻结计划/`

本参考文件回答三个问题：

1. V5 正式文档应该落到哪里
2. V5 应该延续 V1~V4 的哪些文档习惯
3. 新线程在开始写 V5 文档前，最低要核对哪些事实

## 2. 正式与草案的边界

### 正式文档

- 根目录：`docs/01-版本冻结计划/`
- V5 正式目标目录：`docs/01-版本冻结计划/V5/`

### 草案 / 临时来源

- `C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
- `C:\Users\Administrator\Desktop\ai-skills草案\`
- `.tmp/local-drafts/`

### 规则

- 草案可以提供方向，但不能直接代替仓库正式文档。
- 写入仓库前，必须经过母本约束和代码现实核对。
- 如果结论还不稳定，先留在临时材料，不要强行写入正式目录。

## 3. V1~V4 已形成的稳定文档模式

当前仓库已存在：

- `docs/README.md`
- `docs/01-版本冻结计划/00-总计划/00-总计划.md`
- `docs/01-版本冻结计划/00-总计划/01-目录说明.md`
- `docs/01-版本冻结计划/V1/`
- `docs/01-版本冻结计划/V2/`
- `docs/01-版本冻结计划/V3/`
- `docs/01-版本冻结计划/V4/`

V4 已明确展示出可复用的冻结风格：

- `00-V4总纲.md`
- `00-V4总览.md`
- 模块目录
- `00-模块说明.md`
- `01-计划文档/`
- `02-测试验证/`

V5 应优先继承这种结构语言，而不是另起一套完全不同的目录哲学。

## 4. V5 推荐最小落盘策略

除非用户明确要求更多，否则 V5 先采用 **最小正式集合**：

1. `V5/00-V5总纲.md`
2. `V5/00-V5总览.md`
3. 只为当前线程真正推进的模块/工作包创建说明文档

不要一开始就：

- 生成整套 Day01-Day24 空文档
- 生成大量尚未确定 owner 的模块空壳
- 生成没有验证计划的“测试验证”空白文件

## 5. 写 V5 文档前的最低事实核对

至少核对以下文件，再下结论：

- `runtime/orchestrator/app/services/strategy_engine_service.py`
- `runtime/orchestrator/app/services/executor_service.py`
- `runtime/orchestrator/app/services/project_memory_service.py`
- `runtime/orchestrator/app/services/context_builder_service.py`
- `runtime/orchestrator/app/services/cost_estimator_service.py`
- `runtime/orchestrator/app/workers/task_worker.py`
- `apps/web/src/features/projects/ProjectOverviewPage.tsx`
- `apps/web/src/features/strategy/StrategyDecisionPanel.tsx`

## 6. 截至当前已核对到的关键现实

以下事实可作为新线程的起始背景，但仍应在具体任务里做最小复核：

### 6.1 策略预览已存在，但 provider 执行层未真正落地

- `strategy_engine_service.py` 已支持预算压力、阶段、角色、skill 偏好的策略决策与预览。
- `executor_service.py` 当前主要仍是 `shell` / `simulate` 执行模式。
- 这意味着“模型路由”目前更像规划与展示能力，不是稳定的真实 provider 执行层。

### 6.2 project memory 能力已存在，但 worker 主链默认未显式接入

- `context_builder_service.py` 已提供 `include_project_memory` 参数。
- `task_worker.py` 当前调用 `build_context_package(task=task)`，没有显式打开 `include_project_memory=True`。
- 因此 V5 Phase 1 中“Worker 默认接入 project memory recall”仍然属于真实缺口。

### 6.3 成本估算仍是启发式估算

- `cost_estimator_service.py` 顶部说明仍是 `Heuristic token and cost estimation for Day 9.`
- 说明真实 token accounting 与 provider 回执对接仍未完成。

### 6.4 UI 已能看策略与项目视角，但 V5 老板控制面仍未完整产品化

- `ProjectOverviewPage.tsx`、`StrategyDecisionPanel.tsx` 已表明项目与策略控制面有现成基础。
- 但 V5 母本里提到的 team assembly、team control center、cost dashboard 等仍未完整落地。

## 7. V5 文档治理最重要的判断规则

### 可以写进正式冻结文档的内容

- 已被代码或已完成验证证据支持的事实
- 已经明确 Phase、owner skill、切片边界、完成定义的计划
- 已被明确标注为“已规划”“进行中”“待验证”的诚实状态

### 不应直接写进正式冻结文档的内容

- 未核对代码现实的想象性规划
- 没有 owner skill 的工作包命名
- 没有验证要求的“完成”声明
- 只是桌面草案里的乐观判断

## 8. 与兄弟 skills 的目录协同

- `manage-v5-plan-and-freeze-docs`：负责把 V5 文档体系搭稳
- `write-v5-runtime-backend`：负责把工作包落到后端代码
- `write-v5-web-control-surface`：负责把工作包落到前端控制面
- `drive-v5-orchestrator-delivery`：负责跨层收口
- `verify-v5-runtime-and-regression`：负责验证结果与证据
- `review-v5-code-and-risk`：负责指出实现/迁移/口径风险
- `accept-v5-milestone-gate`：负责阶段裁定

V5 文档里必须明确“谁接下一棒”，否则冻结文档只会变成静态说明书。
