# Day11：agent session / message / review-rework 后端主链

- 版本：`V5`
- Phase：`Phase 3`
- 模块：`模块D：Multi-Agent 协作与老板控制面`
- 工作包：`agent-thread-backend-core`
- 当前状态：**已规划**
- owner skill：`write-v5-runtime-backend`
- 文档定位：**逐日执行包总入口 / 完整展开**

---

## 1. 本日定位

Day11 是 Phase 3 的后端主链冻结日，负责把 agent session / message / review-rework / boss note-event 的最小数据主链写成后续线程可直接接手的正式包。

## 2. 背景归属

- Phase：Phase 3
- 模块：模块D：Multi-Agent 协作与老板控制面
- 工作包：`agent-thread-backend-core`
- 关联母本章节：`2.1`、`2.2`、`2.5`、`#6`、`#9`、`#12`
- 下一线程第一顺位：`write-v5-runtime-backend`
- 下一线程第二顺位：`write-v5-web-control-surface`

## 3. 当前真实状态

- `agent_session.py`、`agent_message.py`、`agent_conversation_service.py` 当前均不存在。
- 当前仓库已有项目总览、角色目录、策略入口，但没有真实的 agent thread 数据实体。
- Day11 必须承接 Day10 的可恢复上下文前提，否则多 Agent 线程会建立在不稳定上下文上。

## 4. 本日纳入范围

1. 冻结 agent session / message / review-rework / boss note-event 的最小后端主链。
2. 冻结 Day12 前端页面可直接消费的 agent thread API / timeline / intervention 合同。
3. 冻结 Day10 提供的可恢复上下文如何成为 agent thread 的前置条件。

## 5. 本日明确不纳入

1. 不进入 Day12 的前端页面实现。
2. 不把 team assembly / control center / cost dashboard 提前吞进 Day11。
3. 不把单条执行日志包装成多 Agent 完整产品。

## 6. 当日产物与改动焦点

- 预期产物：
1. agent session / message 最小持久化主链说明
2. review / rework / boss note-event 后端合同说明
3. Day12 可直接消费的 agent thread API / timeline 合同
4. 多 Agent 后端主链的风险与缺证说明
- 重点改动面：
1. runtime/orchestrator/app/domain/agent_session.py（计划新增）
2. runtime/orchestrator/app/domain/agent_message.py（计划新增）
3. runtime/orchestrator/app/services/agent_conversation_service.py（计划新增）
4. runtime/orchestrator/app/workers/task_worker.py
5. runtime/orchestrator/app/services/context_builder_service.py

## 7. 开始前必须先读

1. docs/01-版本冻结计划/V5/00-V5总纲.md
2. docs/01-版本冻结计划/V5/00-V5正式冻结执行计划.md
3. docs/01-版本冻结计划/V5/04-模块D-Multi-Agent协作与老板控制面/00-模块说明.md
4. docs/01-版本冻结计划/V5/03-模块C-记忆治理与上下文防爆仓/01-逐日执行包/Day10-MemoryGovernance控制面与交付串联/README.md
5. docs/01-版本冻结计划/V5/03-模块C-记忆治理与上下文防爆仓/01-逐日执行包/Day10-MemoryGovernance控制面与交付串联/04-交接模板.md
6. runtime/orchestrator/app/workers/task_worker.py
7. apps/web/src/features/projects/ProjectOverviewPage.tsx

## 8. 完成定义 / 非完成定义

### 完成定义
1. agent session / message / review-rework / boss note-event 已形成最小后端主链，而不是只有概念词。
2. Day12 已有明确的 timeline、message、boss intervention 消费合同。
3. 后续线程能区分 Day11 的最小线程闭环与 Day13 团队控制中心的边界。
4. 风险与缺证被诚实回填，没有把多 Agent 产品化愿景偷写成 Day11 完成。

### 非完成定义
1. 只有 domain/repository 草案，没有主链接线。
2. 把单条执行日志包装成多 Agent 线程。
3. 没有 timeline / intervention 合同就让 Day12 自己猜数据结构。
4. 把团队编排、成本 dashboard 提前写成 Day11 结果。

## 9. 最低验证与证据要求

1. 至少 1 条 agent thread API / 查询 / 回放证据入口。
2. timeline / boss intervention 所需字段和状态流已冻结。
3. Day12 所需接口样例或字段清单已正式写下。
4. 若 Day10 前提未满足，必须在文档中明确阻塞或 partial。

## 10. 风险与接力

- 当前风险：
- 线程状态设计复杂度快速上升。
- Day12 页面合同漂移，导致前后端接力断裂。
- 把 review/rework 做成口号，没有可追踪的 session / message 主链。
- 线程收尾后必须留下：
1. Day11 实际涉及的 domain / service / worker 文件列表
2. Day12 要消费的 timeline / intervention 字段清单
3. Day10->Day11 可恢复上下文前提是否满足
4. 当前缺证与阻塞说明
5. 不要误判为多 Agent 产品已经完成的点
- 下一日接力：`write-v5-web-control-surface` 接手 `Day12：agent thread 页面与 boss intervention 前端入口`
- 当前不要误判为完成：`Day11` 仍处于 **已规划**，必须由后续真实线程回填状态。
