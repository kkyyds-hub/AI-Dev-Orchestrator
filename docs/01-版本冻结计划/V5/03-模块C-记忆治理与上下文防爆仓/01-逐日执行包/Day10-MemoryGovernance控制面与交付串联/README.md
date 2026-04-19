# Day10：记忆治理控制面与跨层交付

- 版本：`V5`
- Phase：`Phase 2`
- 模块：`模块C：记忆治理与上下文防爆仓`
- 工作包：`memory-governance-cross-layer-delivery`
- 当前状态：**已实现待验证**
- owner skill：`drive-v5-orchestrator-delivery`
- 文档定位：**逐日执行包总入口 / 完整展开**

---

## 1. 本日定位

Day10 负责把 Day09 的治理后端主链收束成老板可见、可触发、可交接的最小控制面，并留下 Day11 可继续消费的上下文恢复前提。

## 2. 背景归属

- Phase：Phase 2
- 模块：模块C：记忆治理与上下文防爆仓
- 工作包：`memory-governance-cross-layer-delivery`
- 关联母本章节：`2.6`、`2.7`、`#3`、`#12`
- 下一线程第一顺位：`drive-v5-orchestrator-delivery`
- 下一线程第二顺位：`manage-v5-plan-and-freeze-docs`

## 3. 当前真实状态

- `apps/web/src/features/memory-governance/` 已落位，并已挂入 `ProjectOverviewPage.tsx`。
- Day10 控制面已可消费 `GET /projects/{project_id}/memory/governance` 与 manual `rehydrate / compact / reset` 动作合同。
- 已吸收一个 Day09 依赖缺口：`context_builder_service.py` 现会把 `run_id` 写入治理 checkpoint，治理状态中的 `latest_run_id` 不再丢失。
- 2026-04-18 已完成真实最小验证：
  1. `python runtime/orchestrator/scripts/v5_day10_memory_governance_smoke.py`
  2. `npm.cmd run build`

## 4. 本日纳入范围

1. 收束治理状态观察面。
2. 收束 manual rehydrate / compact / reset 动作入口。
3. 收束 Day09 -> Day10 的最小跨层交付证据。
4. 为 Day11 保留上下文可恢复性前提，但不提前实现 Day11 主链。

## 5. 本日明确不纳入

1. 不进入 Day11 的 agent session / message / thread 主链实现扩展。
2. 不把 memory governance 扩大成完整产品中心。
3. 不提前吞入 Day13 / Day14 的 team control / cost dashboard 工作包。
4. 不替代独立 `verify-v5-runtime-and-regression` 线程做全量回归裁定。

## 6. 当日产物与改动焦点

- 已落地产物：
  1. Day10 Memory Governance 控制面
  2. Day10 后端 smoke 脚本：`runtime/orchestrator/scripts/v5_day10_memory_governance_smoke.py`
  3. Day09 -> Day10 合同缺口修复：checkpoint 持久化 `run_id`
  4. Day10 状态回填 / 验证记录更新
- 本轮重点改动面：
  1. `apps/web/src/features/memory-governance/api.ts`
  2. `apps/web/src/features/memory-governance/hooks.ts`
  3. `apps/web/src/features/memory-governance/types.ts`
  4. `apps/web/src/features/memory-governance/sections/MemoryGovernanceSection.tsx`
  5. `apps/web/src/features/projects/ProjectOverviewPage.tsx`
  6. `runtime/orchestrator/app/services/context_builder_service.py`
  7. `runtime/orchestrator/app/services/project_memory_service.py`
  8. `runtime/orchestrator/app/api/routes/projects.py`
  9. `runtime/orchestrator/app/api/routes/workers.py`
  10. `runtime/orchestrator/app/workers/task_worker.py`
  11. `runtime/orchestrator/scripts/v5_day10_memory_governance_smoke.py`

## 7. 完成定义 / 非完成定义

### 已满足的完成定义

1. 老板已能看到真实治理状态，而不是静态 mock。
2. manual `rehydrate / compact / reset` 已可通过真实后端合同触发。
3. `run-once` 返回的 `memory_governance_*` 字段已被真实任务执行样本覆盖。
4. `latest_run_id` 已打通到治理状态接口，Day09 -> Day10 合同不再缺失这一关键字段。
5. 已留下可复跑 smoke 命令与前端 build 证据。

### 明确仍不算完成

1. 不能据此宣称 `Phase 2 已通过`。
2. 不能据此宣称 Day11 已启动或已闭环。
3. 不能把一次最小 smoke 替代独立 verify / regression 线程。
4. 不能把 Day13 / Day14 已挂入口的在途内容算进本轮 Day10 完成范围。

## 8. 最低验证与证据要求

1. 至少 1 条治理状态回显路径：已满足。
2. 至少 1 条 manual `rehydrate / reset / compact` 动作入口合同：已满足。
3. 相关 API / action smoke：已满足。
4. 前端最小 build 或等价证据：已满足。

## 9. 风险与接力

- 当前仍在的风险：
  1. 当前 smoke 主要覆盖空项目路径与 `simulate` 执行路径，尚未覆盖高压坏上下文真实样本。
  2. 当前前端 build 仍有 chunk size warning，但不阻塞 Day10 最小闭环。
  3. 当前验证仍属交付线程内最小验证，不替代独立 verify 线程。
- 下一日接力建议：
  - 若继续实现：`drive-v5-orchestrator-delivery` 继续接 Day11
  - 若仅继续收束文档/口径：`manage-v5-plan-and-freeze-docs`
