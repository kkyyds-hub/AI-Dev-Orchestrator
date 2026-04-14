# Day10：记忆治理控制面与跨层交付

- 版本：`V5`
- Phase：`Phase 2`
- 模块：`模块C：记忆治理与上下文防爆仓`
- 工作包：`memory-governance-cross-layer-delivery`
- 当前状态：**已规划**
- owner skill：`drive-v5-orchestrator-delivery`
- 文档定位：**逐日执行包总入口 / 完整展开**

---

## 1. 本日定位

Day10 是 Phase 2 的跨层交付日，负责把 Day09 的治理后端骨架变成可观察、可触发、可交接的最小控制面与联调入口。

## 2. 背景归属

- Phase：Phase 2
- 模块：模块C：记忆治理与上下文防爆仓
- 工作包：`memory-governance-cross-layer-delivery`
- 关联母本章节：`2.6`、`2.7`、`#3`、`#12`
- 下一线程第一顺位：`drive-v5-orchestrator-delivery`
- 下一线程第二顺位：`review-v5-code-and-risk`

## 3. 当前真实状态

- `apps/web/src/features/memory-governance/` 当前不存在。
- 现有 `ProjectMemoryPanel.tsx` 主要展示 V3/V4 的 project memory snapshot，还不是线程治理控制面。
- `ProjectOverviewPage.tsx` 已能挂载记忆、策略、角色入口，可作为 Day10 的现实承载点。

## 4. 本日纳入范围

1. 冻结 checkpoint timeline / summary / risk 标记面板的最小观察面。
2. 冻结 manual rehydrate / reset / compact 等治理动作的跨层入口。
3. 冻结 Day11 继续进入 agent session/message 之前的上下文可恢复性交接条件。

## 5. 本日明确不纳入

1. 不进入 Day11 的 agent session/message 数据结构实现。
2. 不把 memory governance 扩大为完整产品中心。
3. 不把成本 dashboard、team control 等 Day13/Day14 内容提前纳入。

## 6. 当日产物与改动焦点

- 预期产物：
1. 治理控制面的正式观察面说明
2. manual rehydrate / reset / compact 的动作合同说明
3. Day11 可依赖的上下文可恢复性结论
4. Phase 2 跨层交付的风险与缺证说明
- 重点改动面：
1. apps/web/src/features/memory-governance/（计划新增）
2. apps/web/src/features/projects/ProjectMemoryPanel.tsx
3. apps/web/src/features/projects/ProjectOverviewPage.tsx
4. runtime/orchestrator/app/services/context_builder_service.py
5. runtime/orchestrator/app/services/project_memory_service.py

## 7. 开始前必须先读

1. docs/01-版本冻结计划/V5/00-V5总纲.md
2. docs/01-版本冻结计划/V5/00-V5正式冻结执行计划.md
3. docs/01-版本冻结计划/V5/03-模块C-记忆治理与上下文防爆仓/00-模块说明.md
4. docs/01-版本冻结计划/V5/03-模块C-记忆治理与上下文防爆仓/01-逐日执行包/Day09-CheckpointRollingSummary与Rehydrate后端主链/README.md
5. docs/01-版本冻结计划/V5/03-模块C-记忆治理与上下文防爆仓/01-逐日执行包/Day09-CheckpointRollingSummary与Rehydrate后端主链/04-交接模板.md
6. apps/web/src/features/projects/ProjectMemoryPanel.tsx
7. apps/web/src/features/projects/ProjectOverviewPage.tsx

## 8. 完成定义 / 非完成定义

### 完成定义
1. 老板能看到治理状态，并有最小动作入口，而不是只看静态列表。
2. Day10 已把 Day09 的后端边界转成可观察、可解释的跨层合同。
3. Day11 开始前已明确哪些治理状态可被多 Agent 线程依赖。
4. Phase 2 交付回填与风险说明已经正式落盘。

### 非完成定义
1. 只有静态时间线，没有真实状态或动作入口。
2. 只有后端能力，没有观察和控制面。
3. 把 ProjectMemoryPanel 的旧能力直接包装成完整治理控制面。
4. 没有给 Day11 留下上下文可恢复性前提就进入 agent thread 规划。

## 9. 最低验证与证据要求

1. 至少 1 条治理状态回显路径。
2. 至少 1 条 manual rehydrate / reset / compact 动作入口合同。
3. API smoke + 页面 build 或等价证据入口已明确。
4. Day11 依赖的交接前提写入交接模板。

## 10. 风险与接力

- 当前风险：
- 前后端合同漂移，导致治理动作只写在文档里不落到观察面。
- 控制面只展示 project memory，不展示线程治理状态。
- Day11 未拿到可恢复性前提，后续 agent thread 容易建立在脆弱上下文上。
- 线程收尾后必须留下：
1. Day10 实际涉及的前后端目录列表
2. 治理状态回显字段与动作入口
3. Day11 开始前必须满足的可恢复性前提
4. Phase 2 仍未解决的风险 / 缺证
5. 不要误判为 Phase 2 已整体通过的点
- 下一日接力：`write-v5-runtime-backend` 接手 `Day11：agent session / message / review-rework 后端主链`
- 当前不要误判为完成：`Day10` 仍处于 **已规划**，必须由后续真实线程回填状态。
