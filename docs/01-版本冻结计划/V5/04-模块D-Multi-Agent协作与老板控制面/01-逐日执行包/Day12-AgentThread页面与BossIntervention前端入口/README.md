# Day12：agent thread 页面与 boss intervention 前端入口

- 版本：`V5`
- Phase：`Phase 3`
- 模块：`模块D：Multi-Agent 协作与老板控制面`
- 工作包：`agent-thread-control-surface`
- 当前状态：**已完成**
- owner skill：`write-v5-web-control-surface`
- 文档定位：**逐日执行包总入口 / 完整展开**

---

## 1. 本日定位

Day12 是 Phase 3 的前端入口冻结日，负责把 Day11 的 agent thread 后端主链变成可查看、可干预、可回填的最小前端入口包。

## 2. 背景归属

- Phase：Phase 3
- 模块：模块D：Multi-Agent 协作与老板控制面
- 工作包：`agent-thread-control-surface`
- 关联母本章节：`2.1`、`2.2`、`2.5`、`#6`、`#9`、`#12`
- 实现 owner skill：`write-v5-web-control-surface`
- verify owner skill：`verify-v5-runtime-and-regression`
- 本轮文档总线同步 owner：`manage-v5-plan-and-freeze-docs`

## 3. 当前真实状态

- `apps/web/src/features/agents/` 已落地 Day12 所需的 `types / api / hooks / components / sections`。
- `ProjectOverviewPage.tsx` 已接入 `AgentThreadControlSection`，Day12 页面入口已可见。
- boss intervention 写入链路已按 Day11 合同接通；running session 可写入，`completed / failed / blocked` 且 `current_phase=finalized` 的终态 session 会返回 `HTTP 409`。
- `2026-04-19` 独立 verify 已补齐页面级 B 证据，并确认页面可见 session list 与 submit feedback。

## 4. 本日纳入范围

1. 冻结 agent thread 页面、message timeline、boss intervention 提交入口的最小前端边界。
2. 冻结页面如何消费 Day11 的 session / message / review-rework 合同。
3. 冻结 Day13 进入 team assembly 之前的 UI 接力前提。
4. 在本轮仅基于既有 verify 证据完成 Day12 工作包级状态回填与文档总线同步。

## 5. 本日明确不纳入

1. 不展开 Day13 team assembly / control center。
2. 不把成本 dashboard、cache 可视性提前写进 Day12。
3. 不把完整多页面信息架构重构提前吞进本日。
4. 不把 Day12 已完成外推成 `Phase 3 已通过`。
5. 不改 Day15 / Day16 的正式结论。

## 6. 当日产物与改动焦点

- 预期产物：
1. agent thread 页面最小结构说明
2. message timeline / boss intervention 交互合同
3. Day13 可直接接手的前端状态与入口清单
4. 前端观察面风险与缺证说明
5. Day12 工作包级状态回填与正式口径同步
- 重点改动面：
1. `apps/web/src/features/agents/`（已落地）
2. `apps/web/src/features/projects/ProjectOverviewPage.tsx`
3. `apps/web/src/features/strategy/StrategyDecisionPanel.tsx`
4. `apps/web/src/features/roles/RoleCatalogPage.tsx`
5. `docs/01-版本冻结计划/V5/` 下 Day12 / 模块D / 根文档

## 7. 开始前必须先读

1. `docs/01-版本冻结计划/V5/00-V5总纲.md`
2. `docs/01-版本冻结计划/V5/00-V5正式冻结执行计划.md`
3. `docs/01-版本冻结计划/V5/04-模块D-Multi-Agent协作与老板控制面/00-模块说明.md`
4. `docs/01-版本冻结计划/V5/04-模块D-Multi-Agent协作与老板控制面/01-逐日执行包/Day11-AgentSessionMessageReviewRework后端主链/README.md`
5. `docs/01-版本冻结计划/V5/04-模块D-Multi-Agent协作与老板控制面/01-逐日执行包/Day11-AgentSessionMessageReviewRework后端主链/04-交接模板.md`
6. `runtime/orchestrator/tmp/day12-verify-20260419-independent/day12_boss_intervention_write_contract_smoke.json`
7. `runtime/orchestrator/tmp/day12-verify-20260419-independent/day12_terminal_session_intervention_gate_probe.json`
8. `runtime/orchestrator/tmp/day12-verify-20260419-independent/day12_terminal_session_intervention_gate_blocked_probe.json`
9. `runtime/orchestrator/tmp/day12-verify-20260419-independent/day12_page_interaction_result.json`

## 8. 完成定义 / 非完成定义

### 完成定义
1. 老板可在前端看到最小 agent thread 页面与 message timeline 入口。
2. boss intervention 提交入口有明确交互合同，而不是只停留在按钮占位。
3. Day13 已拿到前端入口、状态与路由前提。
4. `2026-04-19` 独立 verify 已补齐页面级 B 证据，并确认终态 session intervention 写入门禁生效。
5. 当前缺证与未完成项已诚实回填，没有把 Day12 写成整条 `Phase 3 已完成`。

### 非完成定义
1. 只有静态 mock timeline，没有真实数据合同。
2. 页面不接 Day11 冻结的字段合同。
3. 只出现按钮占位，没有 boss intervention 提交规则。
4. 把 Day12 工作包级完成偷换成 `Phase 3 已通过`。
5. 借 Day12 状态升级改写 Day15 / Day16 正式结论。

## 9. 最低验证与证据要求

1. `runtime/orchestrator/tmp/day12-verify-20260419-independent/day12_boss_intervention_write_contract_smoke.json` 已证明 running session 写入成功、completed / failed 终态写入返回 `409`。
2. `runtime/orchestrator/tmp/day12-verify-20260419-independent/day12_terminal_session_intervention_gate_probe.json` 与 `day12_terminal_session_intervention_gate_blocked_probe.json` 已覆盖 completed / failed / blocked 三类终态门禁。
3. `runtime/orchestrator/tmp/day12-verify-20260419-independent/day12_page_interaction_result.json` 已证明页面 section 可见、session list 可见、submit feedback 可见。
4. `runtime/orchestrator/tmp/day12-verify-20260419-independent/web_build_npm_cmd.txt` 已保留前端构建通过记录。
5. 若后续需要里程碑消费，由 accept 线程直接消费既有证据，不在本线程重新执行 verify。

## 10. 风险与接力

- 当前风险：
  - Day12 已完成只成立于工作包级，不能外推成 `Phase 3 已通过`。
  - Day12 的新增 verify 事实不能被误写成 Day13 / Day14 已重新验证通过。
  - Day12 当前回填不能被误写成 Day15 / Day16 需要重写。
- 线程收尾后必须留下：
1. Day12 实际涉及的页面/组件/路由列表
2. message timeline / boss intervention 的状态与交互合同
3. Day12 本轮已消费的 verify 证据路径
4. 当前仍然生效的边界与误判红线
5. 不要误判为 `Phase 3 已整体完成` 的说明
- 历史下一日接力：`drive-v5-orchestrator-delivery` 接手 `Day13：team assembly 与 team control center 串联交付（本轮不展开）`
- 当前不要误判为完成：Day12 的“已完成”仅限工作包级，不外推为 `Phase 3 已通过`。

## 11. 2026-04-19 回切收束（drive-v5-orchestrator-delivery）

- 本线程目标：回切收束 Day12 页面链路，并冻结终态 session intervention 写入门禁策略。
- 本线程实际修复：
  1. `apps/web/vite.config.ts` 已补 `/agent-threads` dev proxy，Day12 页面链路不再绕过后端。
  2. `apps/web/src/features/projects/ProjectOverviewPage.tsx` 已把默认项目选择收束为最近更新优先，降低 Day12 fixture project 漂移导致的误判。
  3. `runtime/orchestrator/app/services/agent_conversation_service.py` 已冻结终态门禁：`current_phase=finalized`，以及 `completed/failed/blocked` / `finished_at` 终态 session 不再接受 boss intervention 写入。
  4. `runtime/orchestrator/app/api/routes/agent_threads.py` 已把上述门禁冲突固定为 `HTTP 409`，避免继续误写成成功。
  5. `apps/web/src/features/agents/components/BossInterventionForm.tsx` 已补 server-side write gate 提示，前端不再把终态写入当作无语义成功路径。
  6. `runtime/orchestrator/scripts/v5_day12_boss_intervention_write_contract_smoke.py` 已改为：
     - 非终态 session 验证 `201` 成功写入；
     - `completed/failed` 终态 session 验证 `409` 门禁冲突。
- 本线程最小验证：
  - `python runtime/orchestrator/scripts/v5_day12_boss_intervention_write_contract_smoke.py`：通过。
  - `npm.cmd run build`（`apps/web`）：通过。
- 该线程时点口径：
  - Day12 当时仍维持 **已实现待验证**；
  - 本线程已把 R2 主缺口从“终态仍可写入”收束为“代码已冻结，待独立 verify 回流确认页面/API 证据”。
- 后续回流目标：独立复核 Day12 页面链路、终态写入门禁、以及 Day12 是否可升级为 `已完成`。

## 12. 2026-04-19 独立 verify 正式同步（manage-v5-plan-and-freeze-docs）

- 本轮只消费既有 Day12 独立 verify 证据，不补实现、不重跑 Day12 全量 verify、不改 Day15 / Day16 正式结论。
- 正式回填结果：Day12 当前状态升级为 **已完成**（仅限 `Day12 / agent-thread-control-surface` 工作包级）。
- 证据等级：`E1`；风险分级：`R1`；缺口清零：`是`（仅限 Day12 本轮 verify 目标）。
- 关键证据：
  1. `runtime/orchestrator/tmp/day12-verify-20260419-independent/day12_boss_intervention_write_contract_smoke.json`
  2. `runtime/orchestrator/tmp/day12-verify-20260419-independent/day12_terminal_session_intervention_gate_probe.json`
  3. `runtime/orchestrator/tmp/day12-verify-20260419-independent/day12_terminal_session_intervention_gate_blocked_probe.json`
  4. `runtime/orchestrator/tmp/day12-verify-20260419-independent/day12_page_interaction_result.json`
- 页面 / API 事实：
  - 页面已可见 `agent-thread-control-surface`、session list 与 submit feedback；
  - 页面反馈文案与后端门禁一致，明确显示 finalized-session conflict；
  - `completed / failed / blocked` 且 `current_phase=finalized` 的终态 session 写入均返回 `HTTP 409`。
- 继续生效的红线：
  - 不写 `Phase 3 已通过`；
  - 不写 `Day13/Day14 已重新验证通过`；
  - 不写 `Day15/Day16 需要改写`；
  - 不写 `V5 全局最终全部通过`。
- 默认下一棒 owner：无强制新 owner；若后续需要消费里程碑口径，再由 `accept-v5-milestone-gate` 独立读取既有证据。
