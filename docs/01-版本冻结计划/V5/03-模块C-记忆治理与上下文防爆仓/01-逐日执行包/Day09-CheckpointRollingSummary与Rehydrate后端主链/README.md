# Day09：记忆治理与上下文防爆仓后端主链

- 版本：`V5`
- Phase：`Phase 2`
- 模块：`模块C：记忆治理与上下文防爆仓`
- 工作包：`memory-governance-backend-core`
- 当前状态：**已规划**
- owner skill：`write-v5-runtime-backend`
- 文档定位：**逐日执行包总入口 / 完整展开**

---

## 1. 本日定位

Day09 是 Phase 2 的后端主链冻结日，负责把 checkpoint / summary / bad context / rehydrate / compaction 的最小执行骨架写成后续线程可直接接手的正式包。

## 2. 背景归属

- Phase：Phase 2
- 模块：模块C：记忆治理与上下文防爆仓
- 工作包：`memory-governance-backend-core`
- 关联母本章节：`2.6`、`2.7`、`#3`、`#12`
- 下一线程第一顺位：`write-v5-runtime-backend`
- 下一线程第二顺位：`drive-v5-orchestrator-delivery`

## 3. 当前真实状态

- `context_builder_service.py` 已有 project memory recall 与 context summary 压缩基础，但没有 checkpoint / rehydrate / compaction 主链。
- `project_memory_service.py` 已有项目记忆搜索与 task memory context 能力，但尚不是线程治理 OS。
- `task_worker.py` 当前仍停留在 build_context_package(task=task) 的较轻量模式，未体现长线程治理主链。
- `context_budget_service.py` 与 `memory_compaction_service.py` 当前均不存在。

## 4. 本日纳入范围

1. 冻结 checkpoint / rolling summary / bad context / rehydrate 后端主链入口。
2. 冻结 memory compaction 与 context budget 相关服务的最小后端边界。
3. 冻结 Day10 可直接消费的 API / 状态 / 治理动作合同。

## 5. 本日明确不纳入

1. 不在 Day09 进入前端控制面实现。
2. 不把 Day11 的 agent session/message 提前纳入。
3. 不承诺外部向量库、跨项目记忆图谱、复杂自治恢复系统。

## 6. 当日产物与改动焦点

- 预期产物：
1. checkpoint / rolling summary / bad context / rehydrate 后端主链说明
2. context budget / memory compaction 最小服务边界说明
3. Day10 可直接消费的治理状态与动作合同
4. Phase 2 后端链路的风险与缺证说明
- 重点改动面：
1. runtime/orchestrator/app/services/context_builder_service.py
2. runtime/orchestrator/app/services/project_memory_service.py
3. runtime/orchestrator/app/workers/task_worker.py
4. runtime/orchestrator/app/services/context_budget_service.py（计划新增）
5. runtime/orchestrator/app/services/memory_compaction_service.py（计划新增）

## 7. 开始前必须先读

1. docs/01-版本冻结计划/V5/00-V5总纲.md
2. docs/01-版本冻结计划/V5/00-V5正式冻结执行计划.md
3. docs/01-版本冻结计划/V5/03-模块C-记忆治理与上下文防爆仓/00-模块说明.md
4. docs/01-版本冻结计划/V5/02-模块B-Provider、Prompt、Token与记忆主链/01-逐日执行包/Day08-Phase1Smoke回归与Gate输入/README.md
5. runtime/orchestrator/app/services/context_builder_service.py
6. runtime/orchestrator/app/services/project_memory_service.py
7. runtime/orchestrator/app/workers/task_worker.py
8. apps/web/src/features/projects/ProjectMemoryPanel.tsx

## 8. 完成定义 / 非完成定义

### 完成定义
1. checkpoint / summary / bad context / rehydrate 已形成最小后端主链，而不是只有概念说明。
2. Day10 有明确的治理状态、手动动作与回显合同可接。
3. 后续线程能区分哪些是正式主链，哪些仍只是风险或 backlog。
4. Phase 2 的后端风险与缺证已被诚实保留。

### 非完成定义
1. 只有 checkpoint schema，没有主链入口。
2. 只有 summary 压缩，没有恢复路径。
3. 只写新增服务名，不写与 worker / context builder 的接线位置。
4. 把 Day09 写成上下文治理已经全面完成。

## 9. 最低验证与证据要求

1. 至少 1 条 checkpoint / rehydrate 场景证据入口。
2. context builder / worker 主链接线位置已明确。
3. Day10 需要消费的状态字段和动作入口已冻结。
4. 缺证时必须明确写成已规划 / 已实现待验证 / 进行中 / 阻塞之一。

## 10. 风险与接力

- 当前风险：
- 压缩策略过度导致上下文误伤。
- 恢复链路不稳定，可能放大错误上下文。
- 仅新增服务名但未接入主链，会造成 Day10 无法落地。
- 线程收尾后必须留下：
1. Day09 实际涉及的后端文件列表
2. checkpoint / rehydrate 场景说明
3. Day10 需要消费的治理状态字段
4. 当前缺证与风险边界
5. 不要误判为 Phase 2 已整体完成的点
- 下一日接力：`drive-v5-orchestrator-delivery` 接手 `Day10：记忆治理控制面与跨层交付`
- 当前不要误判为完成：`Day09` 仍处于 **已规划**，必须由后续真实线程回填状态。
